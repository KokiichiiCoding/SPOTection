"""
Live Camera Detection System
Real-time parking spot detection from camera feeds with automatic screenshots
"""

import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import cv2
import json
import numpy as np
from shapely.geometry import Polygon, box as shapely_box
from ultralytics import YOLO
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
import threading
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LiveCameraDetector:
    """Real-time parking detection from camera feed"""
    
    def __init__(self, camera_source, layout_file: str = None, config_path: str = "config.json"):
        self.camera_source = camera_source
        self.layout_file = layout_file
        self.config = self.load_config(config_path)
        
        # Load model
        self.model = YOLO(self.config["model_path"])
        logger.info(f"Model loaded: {self.config['model_path']}")
        
        # Load spot layout if provided
        self.spots_data = None
        if layout_file and os.path.exists(layout_file):
            with open(layout_file, 'r') as f:
                self.spots_data = json.load(f)
            logger.info(f"Loaded {len(self.spots_data)} spots from {layout_file}")
        elif layout_file:
            logger.warning(f"Layout file not found: {layout_file}")
            logger.info("Running in screenshot-only mode")
        
        # Camera setup
        self.cap = None
        self.frame = None
        self.detection_results = None
        self.running = False
        self.paused = False
        
        # Performance tracking
        self.fps = 0
        self.screenshot_interval = self.config.get("screenshot_interval", 120)  # 2 minutes default
        self.last_screenshot_time = 0
        
        # Threading
        self.lock = threading.Lock()
        
    def load_config(self, config_path: str) -> Dict:
        """Load configuration"""
        default_config = {
            "model_path": "yolov8n.pt",
            "confidence_threshold": 0.25,
            "overlap_threshold": 0.15,
            "vehicle_classes": ["car", "truck", "bus", "van", "motorcycle", "bicycle"],
            "screenshot_interval": 120,  # Take screenshot every 2 minutes
            "output_dir": "output/live_feed/",
            "save_raw_screenshots": True,  # Save screenshots even without layout
        }
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def connect_camera(self) -> bool:
        """Connect to camera source"""
        logger.info(f"Connecting to camera: {self.camera_source}")
        
        # Handle different source types
        if isinstance(self.camera_source, int):
            # Webcam
            self.cap = cv2.VideoCapture(self.camera_source)
        elif self.camera_source.startswith(('http://', 'https://', 'rtsp://')):
            # IP camera / RTSP stream
            self.cap = cv2.VideoCapture(self.camera_source)
        elif os.path.isfile(self.camera_source):
            # Video file
            self.cap = cv2.VideoCapture(self.camera_source)
        else:
            logger.error(f"Invalid camera source: {self.camera_source}")
            return False
        
        if not self.cap.isOpened():
            logger.error("Failed to open camera")
            return False
        
        # Get camera properties
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        
        logger.info(f"Camera connected: {width}x{height} @ {fps} FPS")
        return True
    
    def detect_vehicles(self, frame: np.ndarray) -> List[Dict]:
        """Detect vehicles in frame"""
        results = self.model(
            frame,
            conf=self.config["confidence_threshold"],
            verbose=False
        )[0]
        
        detections = []
        vehicle_classes = set(self.config["vehicle_classes"])
        
        for i, box_data in enumerate(results.boxes):
            cls_id = int(box_data.cls[0])
            class_name = self.model.names[cls_id]
            confidence = float(box_data.conf[0])
            x1, y1, x2, y2 = map(int, box_data.xyxy[0])
            
            if class_name in vehicle_classes:
                detections.append({
                    "id": i,
                    "class": class_name,
                    "confidence": confidence,
                    "bbox": (x1, y1, x2, y2),
                    "box": shapely_box(x1, y1, x2, y2)
                })
        
        return detections
    
    def analyze_spots(self, detections: List[Dict]) -> List[Dict]:
        """Analyze parking spots with detected vehicles"""
        if not self.spots_data:
            return []
        
        results = []
        
        for spot in self.spots_data:
            spot_id = spot["id"]
            polygon_coords = spot["polygon"]
            
            try:
                spot_polygon = Polygon(polygon_coords)
                
                best_match = None
                max_overlap = 0.0
                
                for detection in detections:
                    intersection = spot_polygon.intersection(detection["box"])
                    if intersection.area > 0:
                        smaller_area = min(spot_polygon.area, detection["box"].area)
                        overlap_ratio = intersection.area / smaller_area
                        
                        if overlap_ratio > max_overlap:
                            max_overlap = overlap_ratio
                            best_match = detection
                
                threshold = self.config["overlap_threshold"]
                
                if max_overlap > threshold:
                    status = "OCCUPIED"
                    vehicle_info = {
                        "class": best_match["class"],
                        "confidence": best_match["confidence"]
                    } if best_match else None
                else:
                    status = "FREE"
                    vehicle_info = None
                
                results.append({
                    "id": spot_id,
                    "status": status,
                    "confidence": max_overlap if best_match else 0.0,
                    "vehicle": vehicle_info,
                    "polygon": polygon_coords
                })
                
            except Exception as e:
                logger.error(f"Error analyzing {spot_id}: {e}")
                continue
        
        return results
    
    def draw_overlay(self, frame: np.ndarray, results: List[Dict] = None, 
                    detections: List[Dict] = None, show_fps: bool = True) -> np.ndarray:
        """Draw detection overlay on frame"""
        
        # Draw spots if we have them
        if results and len(results) > 0:
            overlay = frame.copy()
            
            for result in results:
                polygon = np.array(result["polygon"], dtype=np.int32)
                
                if result["status"] == "OCCUPIED":
                    color = (0, 0, 255)  # Red
                elif result["status"] == "FREE":
                    color = (0, 255, 0)  # Green
                else:
                    color = (0, 165, 255)  # Orange
                
                # Semi-transparent fill
                cv2.fillPoly(overlay, [polygon], color)
                cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
                
                # Border
                cv2.polylines(frame, [polygon], True, color, 2)
                
                # Label
                center_x = int(np.mean([p[0] for p in result["polygon"]]))
                center_y = int(np.mean([p[1] for p in result["polygon"]]))
                
                label = f"{result['id'][:8]}"
                (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
                cv2.rectangle(frame, (center_x - w//2 - 3, center_y - h - 3),
                             (center_x + w//2 + 3, center_y + 3), (0, 0, 0), -1)
                cv2.putText(frame, label, (center_x - w//2, center_y),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Draw vehicle detections
        if detections:
            for detection in detections:
                x1, y1, x2, y2 = detection["bbox"]
                cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 2)
                label = f"{detection['class']} {detection['confidence']:.2f}"
                cv2.putText(frame, label, (x1, y1 - 5),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)
        
        # Stats overlay
        stats_bg = frame.copy()
        if results:
            occupied = sum(1 for r in results if r["status"] == "OCCUPIED")
            free = sum(1 for r in results if r["status"] == "FREE")
            cv2.rectangle(stats_bg, (10, 10), (350, 160), (0, 0, 0), -1)
        else:
            cv2.rectangle(stats_bg, (10, 10), (350, 100), (0, 0, 0), -1)
        
        cv2.addWeighted(stats_bg, 0.7, frame, 0.3, 0, frame)
        
        y_offset = 35
        if results:
            occupied = sum(1 for r in results if r["status"] == "OCCUPIED")
            free = sum(1 for r in results if r["status"] == "FREE")
            stats_text = [
                f"Total: {len(results)}",
                f"Free: {free}",
                f"Occupied: {occupied}",
            ]
        else:
            stats_text = ["Screenshot Mode"]
        
        if detections:
            stats_text.append(f"Vehicles: {len(detections)}")
        
        if show_fps:
            stats_text.append(f"FPS: {self.fps:.1f}")
        
        for text in stats_text:
            cv2.putText(frame, text, (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            y_offset += 25
        
        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (frame.shape[1] - 220, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        # Next screenshot countdown
        time_to_next = int(self.screenshot_interval - (time.time() - self.last_screenshot_time))
        if time_to_next > 0:
            cv2.putText(frame, f"Next: {time_to_next}s", (frame.shape[1] - 220, 60),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        
        return frame
    
    def save_screenshot_and_detect(self, frame: np.ndarray):
        """Save screenshot and run detection"""
        output_dir = Path(self.config["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        logger.info(f"Taking screenshot and running detection...")
        
        # Run detection
        detections = self.detect_vehicles(frame)
        results = self.analyze_spots(detections) if self.spots_data else []
        
        # Create annotated frame
        annotated = self.draw_overlay(frame.copy(), results, detections, False)
        
        # Save annotated image
        image_path = output_dir / f"screenshot_{timestamp}.jpg"
        cv2.imwrite(str(image_path), annotated)
        logger.info(f"✓ Saved: {image_path.name}")
        
        # Save raw frame too if configured
        if self.config.get("save_raw_screenshots"):
            raw_path = output_dir / f"raw_{timestamp}.jpg"
            cv2.imwrite(str(raw_path), frame)
        
        # Save data
        if results:
            occupied = sum(1 for r in results if r["status"] == "OCCUPIED")
            free = sum(1 for r in results if r["status"] == "FREE")
            
            data = {
                "timestamp": datetime.now().isoformat(),
                "total_spots": len(results),
                "free_spots": free,
                "occupied_spots": occupied,
                "occupancy_rate": occupied / len(results) if results else 0,
                "vehicles_detected": len(detections),
                "spots": results
            }
        else:
            data = {
                "timestamp": datetime.now().isoformat(),
                "vehicles_detected": len(detections),
                "detections": [
                    {
                        "class": d["class"],
                        "confidence": d["confidence"],
                        "bbox": d["bbox"]
                    } for d in detections
                ]
            }
        
        json_path = output_dir / f"screenshot_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"✓ Detected {len(detections)} vehicles" + 
                   (f", {occupied} occupied spots" if results else ""))
    
    def camera_thread(self):
        """Background thread for reading camera frames"""
        while self.running:
            if not self.paused:
                ret, frame = self.cap.read()
                if ret:
                    with self.lock:
                        self.frame = frame
                else:
                    logger.warning("Failed to read frame")
                    time.sleep(0.1)
            else:
                time.sleep(0.1)
    
    def screenshot_thread(self):
        """Background thread for taking screenshots"""
        while self.running:
            if not self.paused and time.time() - self.last_screenshot_time >= self.screenshot_interval:
                with self.lock:
                    if self.frame is not None:
                        frame = self.frame.copy()
                
                try:
                    self.save_screenshot_and_detect(frame)
                    self.last_screenshot_time = time.time()
                except Exception as e:
                    logger.error(f"Error in screenshot: {e}")
            
            time.sleep(1)
    
    def run(self):
        """Run live detection with GUI"""
        if not self.connect_camera():
            return
        
        logger.info("Starting live camera monitoring...")
        logger.info(f"Screenshot interval: {self.screenshot_interval} seconds")
        logger.info("Controls:")
        logger.info("  SPACE - Pause/Resume")
        logger.info("  S - Take screenshot now")
        logger.info("  Q - Quit")
        
        self.running = True
        self.last_screenshot_time = time.time()
        
        # Start background threads
        cam_thread = threading.Thread(target=self.camera_thread, daemon=True)
        shot_thread = threading.Thread(target=self.screenshot_thread, daemon=True)
        
        cam_thread.start()
        shot_thread.start()
        
        # Wait for first frame
        while self.frame is None and self.running:
            time.sleep(0.1)
        
        # Display loop
        window_name = "Spotection - Live Camera"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        
        frame_times = []
        
        try:
            while self.running:
                frame_start = time.time()
                
                with self.lock:
                    if self.frame is not None:
                        display_frame = self.frame.copy()
                
                # Draw overlay (simplified for live view)
                display_frame = self.draw_overlay(display_frame)
                
                # Show pause indicator
                if self.paused:
                    cv2.putText(display_frame, "PAUSED", (display_frame.shape[1]//2 - 80, 50),
                               cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
                
                cv2.imshow(window_name, display_frame)
                
                # Calculate FPS
                frame_time = time.time() - frame_start
                frame_times.append(frame_time)
                if len(frame_times) > 30:
                    frame_times.pop(0)
                self.fps = 1.0 / (sum(frame_times) / len(frame_times)) if frame_times else 0
                
                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q'):
                    logger.info("Quit requested")
                    break
                elif key == ord(' '):
                    self.paused = not self.paused
                    logger.info(f"{'Paused' if self.paused else 'Resumed'}")
                elif key == ord('s'):
                    logger.info("Manual screenshot triggered")
                    with self.lock:
                        if self.frame is not None:
                            frame = self.frame.copy()
                    self.save_screenshot_and_detect(frame)
        
        finally:
            self.running = False
            self.cap.release()
            cv2.destroyAllWindows()
            logger.info("Camera stopped")


class CameraManager:
    """Manage camera sources"""
    
    @staticmethod
    def list_cameras() -> List[int]:
        """Find available webcams"""
        available = []
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return available
    
    @staticmethod
    def test_camera(source) -> bool:
        """Test if camera source works"""
        cap = cv2.VideoCapture(source)
        ret = cap.isOpened()
        if ret:
            ret, _ = cap.read()
        cap.release()
        return ret
    
    @staticmethod
    def capture_calibration_frame(source, output_path: str) -> bool:
        """Capture a single frame for calibration"""
        logger.info(f"Capturing frame from {source}...")
        
        cap = cv2.VideoCapture(source)
        
        if not cap.isOpened():
            logger.error("Failed to open camera")
            return False
        
        # Let camera warm up
        for _ in range(10):
            cap.read()
        
        # Capture frame
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            logger.error("Failed to capture frame")
            return False
        
        # Save frame
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(output_path, frame)
        logger.info(f"Frame saved: {output_path}")
        
        return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Live Camera Detection System")
    parser.add_argument("--camera", default=0, 
                       help="Camera source (0 for webcam, URL for IP camera)")
    parser.add_argument("--layout",
                       help="Path to spot layout JSON (optional)")
    parser.add_argument("--config", default="config.json",
                       help="Config file")
    parser.add_argument("--interval", type=int,
                       help="Screenshot interval in seconds (default: 120)")
    parser.add_argument("--list-cameras", action="store_true",
                       help="List available cameras")
    parser.add_argument("--test-camera", 
                       help="Test camera connection")
    parser.add_argument("--capture-frame", action="store_true",
                       help="Capture single frame for calibration")
    parser.add_argument("--output", default="data/images/camera_capture.jpg",
                       help="Output path for captured frame")
    
    args = parser.parse_args()
    
    if args.list_cameras:
        print("\nSearching for available cameras...")
        cameras = CameraManager.list_cameras()
        if cameras:
            print(f"Found {len(cameras)} camera(s):")
            for i in cameras:
                print(f"  Camera {i}")
        else:
            print("No cameras found")
        return 0
    
    if args.test_camera:
        print(f"\nTesting camera: {args.test_camera}")
        try:
            source = int(args.test_camera)
        except ValueError:
            source = args.test_camera
        
        if CameraManager.test_camera(source):
            print("✓ Camera works!")
        else:
            print("✗ Camera failed")
        return 0
    
    if args.capture_frame:
        try:
            source = int(args.camera)
        except ValueError:
            source = args.camera
        
        if CameraManager.capture_calibration_frame(source, args.output):
            print(f"\n✓ Frame captured: {args.output}")
            print("\nNext steps:")
            print(f"  1. Calibrate: python src/core/calibration_tool.py --image {args.output}")
            print(f"  2. Run live: python src/core/live_camera_system.py --camera {source} --layout data/layouts/camera_capture_layout.json")
        return 0
    
    # Parse camera source
    try:
        camera_source = int(args.camera)
    except ValueError:
        camera_source = args.camera
    
    # Update config if interval specified
    if args.interval:
        config = {}
        if os.path.exists(args.config):
            with open(args.config, 'r') as f:
                config = json.load(f)
        config["screenshot_interval"] = args.interval
        with open(args.config, 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Set screenshot interval to {args.interval} seconds")
    
    # Run with or without layout
    if not args.layout:
        print("\n" + "="*60)
        print("RUNNING IN SCREENSHOT-ONLY MODE")
        print("="*60)
        print("No layout file provided - will save screenshots and detect vehicles")
        print("To add spot detection, provide --layout parameter")
        print("="*60 + "\n")
    
    try:
        detector = LiveCameraDetector(camera_source, args.layout, args.config)
        detector.run()
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
        
    def load_config(self, config_path: str) -> Dict:
        """Load configuration"""
        default_config = {
            "model_path": "yolov8n.pt",
            "confidence_threshold": 0.25,
            "overlap_threshold": 0.15,
            "vehicle_classes": ["car", "truck", "bus", "van", "motorcycle", "bicycle"],
            "detection_interval": 1.0,  # Run detection every N seconds
            "save_snapshots": True,
            "snapshot_interval": 300,  # Save snapshot every 5 minutes
            "output_dir": "output/live_feed/"
        }
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def connect_camera(self) -> bool:
        """Connect to camera source"""
        logger.info(f"Connecting to camera: {self.camera_source}")
        
        # Handle different source types
        if isinstance(self.camera_source, int):
            # Webcam
            self.cap = cv2.VideoCapture(self.camera_source)
        elif self.camera_source.startswith(('http://', 'https://', 'rtsp://')):
            # IP camera / RTSP stream
            self.cap = cv2.VideoCapture(self.camera_source)
        elif os.path.isfile(self.camera_source):
            # Video file
            self.cap = cv2.VideoCapture(self.camera_source)
        else:
            logger.error(f"Invalid camera source: {self.camera_source}")
            return False
        
        if not self.cap.isOpened():
            logger.error("Failed to open camera")
            return False
        
        # Get camera properties
        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(self.cap.get(cv2.CAP_PROP_FPS))
        
        logger.info(f"Camera connected: {width}x{height} @ {fps} FPS")
        return True
    
    def detect_vehicles(self, frame: np.ndarray) -> List[Dict]:
        """Detect vehicles in frame"""
        results = self.model(
            frame,
            conf=self.config["confidence_threshold"],
            verbose=False
        )[0]
        
        detections = []
        vehicle_classes = set(self.config["vehicle_classes"])
        
        for i, box_data in enumerate(results.boxes):
            cls_id = int(box_data.cls[0])
            class_name = self.model.names[cls_id]
            confidence = float(box_data.conf[0])
            x1, y1, x2, y2 = map(int, box_data.xyxy[0])
            
            if class_name in vehicle_classes:
                detections.append({
                    "id": i,
                    "class": class_name,
                    "confidence": confidence,
                    "bbox": (x1, y1, x2, y2),
                    "box": shapely_box(x1, y1, x2, y2)
                })
        
        return detections
    
    def analyze_spots(self, detections: List[Dict]) -> List[Dict]:
        """Analyze parking spots with detected vehicles"""
        results = []
        
        for spot in self.spots_data:
            spot_id = spot["id"]
            polygon_coords = spot["polygon"]
            
            try:
                spot_polygon = Polygon(polygon_coords)
                
                best_match = None
                max_overlap = 0.0
                
                for detection in detections:
                    intersection = spot_polygon.intersection(detection["box"])
                    if intersection.area > 0:
                        smaller_area = min(spot_polygon.area, detection["box"].area)
                        overlap_ratio = intersection.area / smaller_area
                        
                        if overlap_ratio > max_overlap:
                            max_overlap = overlap_ratio
                            best_match = detection
                
                threshold = self.config["overlap_threshold"]
                
                if max_overlap > threshold:
                    status = "OCCUPIED"
                    vehicle_info = {
                        "class": best_match["class"],
                        "confidence": best_match["confidence"]
                    } if best_match else None
                else:
                    status = "FREE"
                    vehicle_info = None
                
                results.append({
                    "id": spot_id,
                    "status": status,
                    "confidence": max_overlap if best_match else 0.0,
                    "vehicle": vehicle_info,
                    "polygon": polygon_coords
                })
                
            except Exception as e:
                logger.error(f"Error analyzing {spot_id}: {e}")
                continue
        
        return results
    
    def draw_overlay(self, frame: np.ndarray, results: List[Dict], 
                    detections: List[Dict], show_fps: bool = True) -> np.ndarray:
        """Draw detection overlay on frame"""
        overlay = frame.copy()
        
        # Draw spots
        for result in results:
            polygon = np.array(result["polygon"], dtype=np.int32)
            
            if result["status"] == "OCCUPIED":
                color = (0, 0, 255)  # Red
            elif result["status"] == "FREE":
                color = (0, 255, 0)  # Green
            else:
                color = (0, 165, 255)  # Orange
            
            # Semi-transparent fill
            cv2.fillPoly(overlay, [polygon], color)
            cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)
            
            # Border
            cv2.polylines(frame, [polygon], True, color, 2)
            
            # Label
            center_x = int(np.mean([p[0] for p in result["polygon"]]))
            center_y = int(np.mean([p[1] for p in result["polygon"]]))
            
            label = f"{result['id'][:8]}"  # Shortened ID
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.4, 1)
            cv2.rectangle(frame, (center_x - w//2 - 3, center_y - h - 3),
                         (center_x + w//2 + 3, center_y + 3), (0, 0, 0), -1)
            cv2.putText(frame, label, (center_x - w//2, center_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
        
        # Draw vehicle detections
        for detection in detections:
            x1, y1, x2, y2 = detection["bbox"]
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 255), 2)
        
        # Stats overlay
        occupied = sum(1 for r in results if r["status"] == "OCCUPIED")
        free = sum(1 for r in results if r["status"] == "FREE")
        
        # Create semi-transparent background for stats
        stats_bg = frame.copy()
        cv2.rectangle(stats_bg, (10, 10), (350, 150), (0, 0, 0), -1)
        cv2.addWeighted(stats_bg, 0.7, frame, 0.3, 0, frame)
        
        stats_text = [
            f"Total: {len(results)}",
            f"Free: {free}",
            f"Occupied: {occupied}",
            f"Vehicles: {len(detections)}"
        ]
        
        if show_fps:
            stats_text.append(f"FPS: {self.fps:.1f}")
        
        y_offset = 35
        for text in stats_text:
            cv2.putText(frame, text, (20, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            y_offset += 25
        
        # Timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (frame.shape[1] - 220, 30),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
        
        return frame
    
    def save_snapshot(self, frame: np.ndarray, results: List[Dict]):
        """Save snapshot of current state"""
        output_dir = Path(self.config["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Save image
        image_path = output_dir / f"snapshot_{timestamp}.jpg"
        cv2.imwrite(str(image_path), frame)
        
        # Save data
        occupied = sum(1 for r in results if r["status"] == "OCCUPIED")
        free = sum(1 for r in results if r["status"] == "FREE")
        
        data = {
            "timestamp": datetime.now().isoformat(),
            "total_spots": len(results),
            "free_spots": free,
            "occupied_spots": occupied,
            "occupancy_rate": occupied / len(results) if results else 0,
            "spots": results
        }
        
        json_path = output_dir / f"snapshot_{timestamp}.json"
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Snapshot saved: {image_path.name}")
    
    def camera_thread(self):
        """Background thread for reading camera frames"""
        while self.running:
            if not self.paused:
                ret, frame = self.cap.read()
                if ret:
                    with self.lock:
                        self.frame = frame
                else:
                    logger.warning("Failed to read frame")
                    time.sleep(0.1)
            else:
                time.sleep(0.1)
    
    def detection_thread(self):
        """Background thread for running detection"""
        last_snapshot_time = time.time()
        
        while self.running:
            if not self.paused and time.time() - self.last_detection_time >= self.detection_interval:
                with self.lock:
                    if self.frame is not None:
                        frame = self.frame.copy()
                
                # Run detection
                detections = self.detect_vehicles(frame)
                results = self.analyze_spots(detections)
                
                with self.lock:
                    self.detection_results = {
                        'results': results,
                        'detections': detections
                    }
                
                self.last_detection_time = time.time()
                
                # Save snapshot periodically
                if self.config.get("save_snapshots") and \
                   time.time() - last_snapshot_time >= self.config.get("snapshot_interval", 300):
                    annotated = self.draw_overlay(frame.copy(), results, detections, False)
                    self.save_snapshot(annotated, results)
                    last_snapshot_time = time.time()
            
            time.sleep(0.1)
    
    def run(self):
        """Run live detection with GUI"""
        if not self.connect_camera():
            return
        
        logger.info("Starting live detection...")
        logger.info("Controls:")
        logger.info("  SPACE - Pause/Resume")
        logger.info("  S - Save snapshot")
        logger.info("  Q - Quit")
        
        self.running = True
        
        # Start background threads
        cam_thread = threading.Thread(target=self.camera_thread, daemon=True)
        det_thread = threading.Thread(target=self.detection_thread, daemon=True)
        
        cam_thread.start()
        det_thread.start()
        
        # Wait for first frame
        while self.frame is None and self.running:
            time.sleep(0.1)
        
        # Display loop
        window_name = "Spotection - Live Detection"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        
        frame_times = []
        
        try:
            while self.running:
                frame_start = time.time()
                
                with self.lock:
                    if self.frame is not None:
                        display_frame = self.frame.copy()
                        current_results = self.detection_results
                
                # Draw overlay if we have detection results
                if current_results:
                    display_frame = self.draw_overlay(
                        display_frame,
                        current_results['results'],
                        current_results['detections']
                    )
                else:
                    # Show "Processing..." message
                    cv2.putText(display_frame, "Processing...", (50, 50),
                               cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)
                
                # Show pause indicator
                if self.paused:
                    cv2.putText(display_frame, "PAUSED", (display_frame.shape[1]//2 - 80, 50),
                               cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)
                
                cv2.imshow(window_name, display_frame)
                
                # Calculate FPS
                frame_time = time.time() - frame_start
                frame_times.append(frame_time)
                if len(frame_times) > 30:
                    frame_times.pop(0)
                self.fps = 1.0 / (sum(frame_times) / len(frame_times))
                
                # Handle keyboard input
                key = cv2.waitKey(1) & 0xFF
                
                if key == ord('q'):
                    logger.info("Quit requested")
                    break
                elif key == ord(' '):
                    self.paused = not self.paused
                    logger.info(f"{'Paused' if self.paused else 'Resumed'}")
                elif key == ord('s') and current_results:
                    self.save_snapshot(display_frame, current_results['results'])
        
        finally:
            self.running = False
            self.cap.release()
            cv2.destroyAllWindows()
            logger.info("Camera stopped")


class CameraManager:
    """Manage multiple camera sources and layouts"""
    
    @staticmethod
    def list_cameras() -> List[int]:
        """Find available webcams"""
        available = []
        for i in range(10):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                available.append(i)
                cap.release()
        return available
    
    @staticmethod
    def test_camera(source) -> bool:
        """Test if camera source works"""
        cap = cv2.VideoCapture(source)
        ret = cap.isOpened()
        if ret:
            ret, _ = cap.read()
        cap.release()
        return ret
    
    @staticmethod
    def capture_calibration_frame(source, output_path: str) -> bool:
        """Capture a single frame for calibration"""
        logger.info(f"Capturing frame from {source}...")
        
        cap = cv2.VideoCapture(source)
        
        if not cap.isOpened():
            logger.error("Failed to open camera")
            return False
        
        # Let camera warm up
        for _ in range(10):
            cap.read()
        
        # Capture frame
        ret, frame = cap.read()
        cap.release()
        
        if not ret:
            logger.error("Failed to capture frame")
            return False
        
        # Save frame
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(output_path, frame)
        logger.info(f"Frame saved: {output_path}")
        
        return True


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Live Camera Detection System")
    parser.add_argument("--camera", default=0, 
                       help="Camera source (0 for webcam, URL for IP camera)")
    parser.add_argument("--layout", required=True,
                       help="Path to spot layout JSON")
    parser.add_argument("--config", default="config.json",
                       help="Config file")
    parser.add_argument("--list-cameras", action="store_true",
                       help="List available cameras")
    parser.add_argument("--test-camera", 
                       help="Test camera connection")
    parser.add_argument("--capture-frame", action="store_true",
                       help="Capture single frame for calibration")
    parser.add_argument("--output", default="data/images/camera_capture.jpg",
                       help="Output path for captured frame")
    
    args = parser.parse_args()
    
    if args.list_cameras:
        print("\nSearching for available cameras...")
        cameras = CameraManager.list_cameras()
        if cameras:
            print(f"Found {len(cameras)} camera(s):")
            for i in cameras:
                print(f"  Camera {i}")
        else:
            print("No cameras found")
        return 0
    
    if args.test_camera:
        print(f"\nTesting camera: {args.test_camera}")
        # Try to parse as int (webcam) or use as string (URL)
        try:
            source = int(args.test_camera)
        except ValueError:
            source = args.test_camera
        
        if CameraManager.test_camera(source):
            print("✓ Camera works!")
        else:
            print("✗ Camera failed")
        return 0
    
    if args.capture_frame:
        try:
            source = int(args.camera)
        except ValueError:
            source = args.camera
        
        if CameraManager.capture_calibration_frame(source, args.output):
            print(f"\n✓ Frame captured: {args.output}")
            print("\nNext steps:")
            print(f"  1. Calibrate: python src/core/calibration_tool.py --image {args.output}")
            print(f"  2. Run live: python live_camera.py --camera {source} --layout data/layouts/[name]_layout.json")
        return 0
    
    # Run live detection
    if not os.path.exists(args.layout):
        print(f"\nError: Layout file not found: {args.layout}")
        print("\nTo create layout:")
        print("  1. Capture frame: python live_camera.py --capture-frame --camera 0")
        print("  2. Calibrate: python src/core/calibration_tool.py --image data/images/camera_capture.jpg")
        return 1
    
    try:
        # Parse camera source
        try:
            camera_source = int(args.camera)
        except ValueError:
            camera_source = args.camera
        
        detector = LiveCameraDetector(camera_source, args.layout, args.config)
        detector.run()
        
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())