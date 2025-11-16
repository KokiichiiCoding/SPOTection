"""
Enhanced Multi-Image Detection System
Process any image with its corresponding layout
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
import logging

from src.utils.image_enhancer import enhance_for_vehicle_detection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MultiImageDetectionSystem:
    """Detection system that works with any image"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config = self.load_config(config_path)
        self.model = None
        self.load_model()
        
    def load_config(self, config_path: str) -> Dict:
        """Load configuration"""
        default_config = {
            "model_path": "yolov8n.pt",
            "confidence_threshold": 0.25,
            "overlap_threshold": 0.15,
            "images_dir": "data/images",
            "layouts_dir": "data/layouts",
            "output_dir": "output/",
            "vehicle_classes": ["car", "truck", "bus", "van", "motorcycle", "bicycle"],
            "auto_generate_spots": True,
            "save_debug_images": True,
            "preprocessing": {
                "apply_white_balance": True,
                "apply_clahe": True,
                "clahe_clip_limit": 2.5,
                "clahe_tile_grid_size": [8, 8],
                "apply_gamma": True,
                "gamma": 1.1,
                "smooth_noise": True,
                "bilateral_filter_diameter": 5,
                "bilateral_filter_sigma_color": 60,
                "bilateral_filter_sigma_space": 60
            }
        }

        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)

        return default_config
    
    def load_model(self):
        """Load YOLO model"""
        try:
            model_path = self.config["model_path"]
            logger.info(f"Loading model: {model_path}")
            self.model = YOLO(model_path)
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            raise
    
    def find_layout_for_image(self, image_path: str) -> Optional[str]:
        """Find corresponding layout file for an image"""
        
        image_name = Path(image_path).stem
        layouts_dir = Path(self.config["layouts_dir"])
        
        # Try exact match first
        layout_file = layouts_dir / f"{image_name}_layout.json"
        
        if layout_file.exists():
            return str(layout_file)
        
        # Try without _layout suffix
        layout_file = layouts_dir / f"{image_name}.json"
        if layout_file.exists():
            return str(layout_file)
        
        # Look for any layout files
        if layouts_dir.exists():
            all_layouts = list(layouts_dir.glob("*.json"))
            if len(all_layouts) == 1:
                logger.warning(f"Using only available layout: {all_layouts[0].name}")
                return str(all_layouts[0])
        
        return None
    
    def ensure_spot_layout(self, image_path: str) -> Optional[str]:
        """Ensure spot layout exists for image"""
        
        # Try to find existing layout
        layout_path = self.find_layout_for_image(image_path)
        
        if layout_path and os.path.exists(layout_path):
            logger.info(f"Using layout: {layout_path}")
            return layout_path
        
        # Auto-generate if enabled
        if self.config.get("auto_generate_spots", True):
            logger.info("Layout not found, auto-generating...")
            try:
                from polygon_generator import ImprovedPolygonGenerator
                
                image_name = Path(image_path).stem
                output_path = f"{self.config['layouts_dir']}/{image_name}_layout.json"
                
                generator = ImprovedPolygonGenerator(image_path)
                success = generator.auto_generate(output_path=output_path)
                
                if success:
                    logger.info("Layout auto-generated successfully")
                    return output_path
            except Exception as e:
                logger.warning(f"Auto-generation failed: {e}")
        
        logger.error(f"No layout available for {Path(image_path).name}")
        logger.info("Run calibration: python src/core/calibration_tool.py --image " + image_path)
        return None
    
    def detect_vehicles(self, image_path: str) -> List[Dict]:
        """Detect vehicles in image"""
        
        image = cv2.imread(image_path)
        if image is None:
            raise FileNotFoundError(f"Image not found: {image_path}")

        processed = enhance_for_vehicle_detection(image, self.config.get("preprocessing"))

        results = self.model(
            processed,
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
                    "box": shapely_box(x1, y1, x2, y2),
                    "center": ((x1 + x2) // 2, (y1 + y2) // 2)
                })
        
        logger.info(f"Detected {len(detections)} vehicles")
        return detections
    
    def calculate_overlap(self, spot_polygon: Polygon, detection_box: shapely_box) -> float:
        """Calculate overlap ratio"""
        try:
            intersection = spot_polygon.intersection(detection_box)
            if intersection.area == 0:
                return 0.0
            
            smaller_area = min(spot_polygon.area, detection_box.area)
            overlap_ratio = intersection.area / smaller_area
            
            return overlap_ratio
        except Exception as e:
            logger.warning(f"Overlap calculation error: {e}")
            return 0.0
    
    def analyze_spot(self, spot: Dict, detections: List[Dict]) -> Dict:
        """Analyze single parking spot"""
        
        spot_id = spot["id"]
        polygon_coords = spot["polygon"]
        
        try:
            spot_polygon = Polygon(polygon_coords)
            
            best_match = None
            max_overlap = 0.0
            
            for detection in detections:
                overlap = self.calculate_overlap(spot_polygon, detection["box"])
                
                if overlap > max_overlap:
                    max_overlap = overlap
                    best_match = detection
            
            threshold = self.config["overlap_threshold"]
            
            if max_overlap > threshold:
                status = "OCCUPIED"
                vehicle_info = {
                    "class": best_match["class"],
                    "confidence": best_match["confidence"],
                    "overlap": max_overlap
                } if best_match else None
            else:
                status = "FREE"
                vehicle_info = None
            
            return {
                "id": spot_id,
                "status": status,
                "confidence": max_overlap if best_match else 0.0,
                "timestamp": datetime.now().isoformat(),
                "vehicle": vehicle_info,
                "polygon": polygon_coords
            }
            
        except Exception as e:
            logger.error(f"Error analyzing {spot_id}: {e}")
            return {
                "id": spot_id,
                "status": "UNKNOWN",
                "confidence": 0.0,
                "timestamp": datetime.now().isoformat(),
                "vehicle": None,
                "polygon": polygon_coords
            }
    
    def visualize_results(self, image_path: str, results: List[Dict], 
                         detections: List[Dict], output_path: str):
        """Create annotated visualization"""
        
        image = cv2.imread(image_path)
        if image is None:
            logger.error(f"Could not load image: {image_path}")
            return
        
        overlay = image.copy()
        
        for result in results:
            polygon = np.array(result["polygon"], dtype=np.int32)
            
            if result["status"] == "OCCUPIED":
                color = (0, 0, 255)
            elif result["status"] == "FREE":
                color = (0, 255, 0)
            else:
                color = (0, 165, 255)
            
            cv2.fillPoly(overlay, [polygon], color)
            cv2.addWeighted(overlay, 0.3, image, 0.7, 0, image)
            
            cv2.polylines(image, [polygon], True, color, 2)
            
            center_x = int(np.mean([p[0] for p in result["polygon"]]))
            center_y = int(np.mean([p[1] for p in result["polygon"]]))
            
            label = f"{result['id']}: {result['status']}"
            if result['vehicle']:
                label += f" ({result['vehicle']['class'][:3]})"
            
            (w, h), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(image, (center_x - w//2 - 5, center_y - h - 5),
                         (center_x + w//2 + 5, center_y + 5), (0, 0, 0), -1)
            
            cv2.putText(image, label, (center_x - w//2, center_y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
        for detection in detections:
            x1, y1, x2, y2 = detection["bbox"]
            cv2.rectangle(image, (x1, y1), (x2, y2), (255, 0, 255), 2)
            
            label = f"{detection['class']} {detection['confidence']:.2f}"
            cv2.putText(image, label, (x1, y1 - 10),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)
        
        occupied = sum(1 for r in results if r["status"] == "OCCUPIED")
        free = sum(1 for r in results if r["status"] == "FREE")
        
        stats_text = [
            f"Image: {Path(image_path).name}",
            f"Total: {len(results)}",
            f"Free: {free}",
            f"Occupied: {occupied}",
            f"Vehicles: {len(detections)}"
        ]
        
        y_offset = 30
        for text in stats_text:
            cv2.putText(image, text, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            cv2.putText(image, text, (10, y_offset),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 1)
            y_offset += 30
        
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(output_path, image)
        logger.info(f"Visualization saved: {output_path}")
    
    def run_detection(self, image_path: str, spot_layout_path: Optional[str] = None) -> Dict:
        """Run detection on specified image"""
        
        image_name = Path(image_path).name
        logger.info("="*60)
        logger.info(f"DETECTION: {image_name}")
        logger.info("="*60)
        
        # Find or generate layout
        if not spot_layout_path:
            spot_layout_path = self.ensure_spot_layout(image_path)
        
        if not spot_layout_path or not os.path.exists(spot_layout_path):
            logger.error("Cannot proceed without spot layout")
            return {}
        
        # Load spots
        with open(spot_layout_path, 'r') as f:
            spots_data = json.load(f)
        
        logger.info(f"Loaded {len(spots_data)} parking spots from {Path(spot_layout_path).name}")
        
        # Detect vehicles
        detections = self.detect_vehicles(image_path)
        
        # Analyze spots
        results = []
        for spot in spots_data:
            result = self.analyze_spot(spot, detections)
            results.append(result)
        
        # Generate summary
        occupied = sum(1 for r in results if r["status"] == "OCCUPIED")
        free = sum(1 for r in results if r["status"] == "FREE")
        unknown = sum(1 for r in results if r["status"] == "UNKNOWN")
        
        summary = {
            "image": image_name,
            "timestamp": datetime.now().isoformat(),
            "total_spots": len(results),
            "free_spots": free,
            "occupied_spots": occupied,
            "unknown_spots": unknown,
            "occupancy_rate": occupied / len(results) if results else 0,
            "spots": results
        }
        
        logger.info("\nRESULTS:")
        logger.info(f"  Total Spots: {len(results)}")
        logger.info(f"  Free: {free}")
        logger.info(f"  Occupied: {occupied}")
        logger.info(f"  Occupancy Rate: {summary['occupancy_rate']:.1%}")
        
        # Save results
        output_dir = Path(self.config["output_dir"])
        output_dir.mkdir(parents=True, exist_ok=True)
        
        image_stem = Path(image_path).stem
        results_file = output_dir / f"{image_stem}_results.json"
        with open(results_file, 'w') as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Results saved: {results_file}")
        
        # Create visualization
        if self.config.get("save_debug_images", True):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            viz_path = output_dir / f"{image_stem}_annotated_{timestamp}.jpg"
            self.visualize_results(image_path, results, detections, str(viz_path))
        
        return summary
    
    def batch_detect(self, images_dir: str = None) -> List[Dict]:
        """Run detection on all images in directory"""
        
        if images_dir is None:
            images_dir = self.config["images_dir"]
        
        images_path = Path(images_dir)
        
        if not images_path.exists():
            logger.error(f"Directory not found: {images_dir}")
            return []
        
        # Find all images
        image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
        images = []
        for ext in image_extensions:
            images.extend(images_path.glob(f'*{ext}'))
            images.extend(images_path.glob(f'*{ext.upper()}'))
        
        if not images:
            logger.error(f"No images found in {images_dir}")
            return []
        
        logger.info(f"\n{'='*60}")
        logger.info(f"BATCH DETECTION: {len(images)} images")
        logger.info('='*60)
        
        all_results = []
        
        for i, image_path in enumerate(images, 1):
            logger.info(f"\n[{i}/{len(images)}] Processing: {image_path.name}")
            logger.info("-"*60)
            
            try:
                summary = self.run_detection(str(image_path))
                if summary:
                    all_results.append(summary)
            except Exception as e:
                logger.error(f"Error processing {image_path.name}: {e}")
                import traceback
                traceback.print_exc()
        
        # Overall summary
        logger.info("\n" + "="*60)
        logger.info("BATCH DETECTION COMPLETE")
        logger.info("="*60)
        logger.info(f"Processed: {len(all_results)}/{len(images)} images")
        
        total_spots = sum(r['total_spots'] for r in all_results)
        total_free = sum(r['free_spots'] for r in all_results)
        total_occupied = sum(r['occupied_spots'] for r in all_results)
        
        logger.info(f"Total spots: {total_spots}")
        logger.info(f"Total free: {total_free}")
        logger.info(f"Total occupied: {total_occupied}")
        logger.info(f"Overall occupancy: {(total_occupied/total_spots*100):.1f}%")
        
        # Save batch results
        batch_summary = {
            "timestamp": datetime.now().isoformat(),
            "total_images": len(images),
            "processed_images": len(all_results),
            "total_spots": total_spots,
            "total_free": total_free,
            "total_occupied": total_occupied,
            "overall_occupancy": total_occupied / total_spots if total_spots > 0 else 0,
            "results": all_results
        }
        
        output_path = Path(self.config["output_dir"]) / "batch_detection_results.json"
        with open(output_path, 'w') as f:
            json.dump(batch_summary, f, indent=2)
        logger.info(f"\nBatch results saved: {output_path}")
        
        return all_results


def select_image_interactive(images_dir: str = "data/images") -> Optional[str]:
    """Interactive image selection"""
    
    images_path = Path(images_dir)
    if not images_path.exists():
        print(f"Directory not found: {images_dir}")
        return None
    
    image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
    images = []
    for ext in image_extensions:
        images.extend(images_path.glob(f'*{ext}'))
        images.extend(images_path.glob(f'*{ext.upper()}'))
    
    if not images:
        print(f"No images found in {images_dir}")
        return None
    
    print("\n" + "="*60)
    print("AVAILABLE IMAGES")
    print("="*60)
    
    for i, img_path in enumerate(images, 1):
        # Check if layout exists
        layout_file = Path(f"data/layouts/{img_path.stem}_layout.json")
        status = "✓" if layout_file.exists() else "○"
        print(f"{i}. {status} {img_path.name}")
    
    print("\n✓ = Has layout, ○ = No layout")
    
    while True:
        try:
            choice = input(f"\nSelect image (1-{len(images)}) or 'q' to quit: ").strip()
            
            if choice.lower() == 'q':
                return None
            
            idx = int(choice) - 1
            if 0 <= idx < len(images):
                return str(images[idx])
            else:
                print(f"Please enter a number between 1 and {len(images)}")
        except ValueError:
            print("Invalid input. Please enter a number.")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-Image Detection System")
    parser.add_argument("--image", help="Path to specific image")
    parser.add_argument("--spots", help="Path to spot layout JSON")
    parser.add_argument("--batch", action="store_true",
                       help="Process all images in directory")
    parser.add_argument("--images-dir", default="data/images",
                       help="Directory containing images")
    parser.add_argument("--select", action="store_true",
                       help="Interactively select image to process")
    parser.add_argument("--config", default="config.json",
                       help="Config file")
    
    args = parser.parse_args()
    
    try:
        system = MultiImageDetectionSystem(args.config)
        
        if args.select:
            # Interactive selection
            image_path = select_image_interactive(args.images_dir)
            if image_path:
                summary = system.run_detection(image_path, args.spots)
                
                if summary:
                    print("\n" + "="*60)
                    print("DETECTION COMPLETE")
                    print("="*60)
                    print(f"Image: {summary['image']}")
                    print(f"Free spots: {summary['free_spots']}/{summary['total_spots']}")
                    print(f"Occupancy: {summary['occupancy_rate']:.1%}")
        
        elif args.batch:
            # Batch processing
            system.batch_detect(args.images_dir)
        
        elif args.image:
            # Single image
            summary = system.run_detection(args.image, args.spots)
            
            if summary:
                print("\n" + "="*60)
                print("DETECTION COMPLETE")
                print("="*60)
                print(f"Image: {summary['image']}")
                print(f"Free spots: {summary['free_spots']}/{summary['total_spots']}")
                print(f"Occupancy: {summary['occupancy_rate']:.1%}")
        
        else:
            # Show menu
            print("\n" + "="*60)
            print("MULTI-IMAGE DETECTION SYSTEM")
            print("="*60)
            print("\nNo image specified. Use one of these options:")
            print("  --image <path>        Detect specific image")
            print("  --select              Select image interactively")
            print("  --batch               Process all images")
            print("\nExamples:")
            print("  python detection_system.py --select")
            print("  python detection_system.py --image data/images/parking1.jpg")
            print("  python detection_system.py --batch")
            
    except Exception as e:
        logger.error(f"Detection failed: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())