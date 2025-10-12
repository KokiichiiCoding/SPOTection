import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import cv2
import json
import numpy as np
from shapely.geometry import Polygon, box
from ultralytics import YOLO

def quick_fix_detection():
    """Quick fix with very aggressive detection and visual debugging"""
    
    # Load everything
    model = YOLO("yolov8n.pt")
    image = cv2.imread("data/test_image.jpg")
    
    with open("data/spot_layout.json", 'r') as f:
        spots_data = json.load(f)
    
    print("=== QUICK FIX DETECTION ===")
    print(f"Image shape: {image.shape}")
    print(f"Spots loaded: {len(spots_data)}")
    
    # Run YOLO with very low confidence threshold
    results = model("data/test_image.jpg", conf=0.1)[0]  # Lower confidence to catch more
    
    # Get ALL detections (not just vehicles)
    all_detections = []
    vehicle_detections = []
    
    vehicle_classes = {"car", "truck", "bus", "van", "motorcycle", "bicycle"}
    
    for i, box_data in enumerate(results.boxes):
        cls_id = int(box_data.cls[0])
        class_name = model.names[cls_id]
        confidence = float(box_data.conf[0])
        x1, y1, x2, y2 = map(int, box_data.xyxy[0])
        
        detection = {
            "id": i,
            "class": class_name,
            "confidence": confidence,
            "bbox": (x1, y1, x2, y2),
            "box": box(x1, y1, x2, y2)
        }
        
        all_detections.append(detection)
        
        # More lenient vehicle detection
        if class_name in vehicle_classes and confidence > 0.1:  # Very low threshold
            vehicle_detections.append(detection)
    
    print(f"Total detections: {len(all_detections)}")
    print(f"Vehicle detections: {len(vehicle_detections)}")
    
    # Print all detections for debugging
    for det in all_detections:
        print(f"  {det['class']}: {det['confidence']:.2f} at {det['bbox']}")
    
    # Create debug image showing ALL detections
    debug_image = image.copy()
    
    # Draw ALL detections in different colors
    for i, det in enumerate(all_detections):
        x1, y1, x2, y2 = det['bbox']
        
        if det in vehicle_detections:
            color = (255, 0, 0)  # Blue for vehicles we'll use
            thickness = 3
        else:
            color = (128, 128, 128)  # Gray for other detections
            thickness = 1
        
        cv2.rectangle(debug_image, (x1, y1), (x2, y2), color, thickness)
        cv2.putText(debug_image, f"{det['class']} {det['confidence']:.2f}", 
                   (x1, y1-5), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)
    
    # Now analyze spots with VERY aggressive overlap detection
    results_data = []
    
    for spot in spots_data:
        spot_id = spot["id"]
        polygon_coords = spot["polygon"]
        
        try:
            spot_polygon = Polygon(polygon_coords)
            
            # Check overlap with ALL detections, not just vehicles
            max_overlap = 0
            best_detection = None
            
            # First try vehicles
            for det in vehicle_detections:
                intersection = spot_polygon.intersection(det['box'])
                if intersection.area > 0:
                    overlap_ratio = intersection.area / min(spot_polygon.area, det['box'].area)
                    if overlap_ratio > max_overlap:
                        max_overlap = overlap_ratio
                        best_detection = det
            
            # If no vehicle overlap, try ANY detection (sometimes YOLO misclassifies)
            if max_overlap == 0:
                for det in all_detections:
                    intersection = spot_polygon.intersection(det['box'])
                    if intersection.area > 0:
                        overlap_ratio = intersection.area / min(spot_polygon.area, det['box'].area)
                        if overlap_ratio > max_overlap:
                            max_overlap = overlap_ratio
                            best_detection = det
            
            # VERY aggressive threshold - even tiny overlaps count
            threshold = 0.01  # 1% overlap!
            
            if max_overlap > threshold:
                status = "OCCUPIED"
                color = (0, 0, 255)  # Red
            else:
                status = "FREE" 
                color = (0, 255, 0)  # Green
            
            print(f"{spot_id}: {status} (overlap: {max_overlap:.4f})")
            if best_detection:
                print(f"  -> {best_detection['class']} at {best_detection['bbox']}")
            
            # Draw spot on debug image
            pts = np.array(polygon_coords, dtype=np.int32)
            
            # Semi-transparent fill
            overlay = debug_image.copy()
            cv2.fillPoly(overlay, [pts], (*color, 100))
            cv2.addWeighted(overlay, 0.3, debug_image, 0.7, 0, debug_image)
            
            # Outline
            cv2.polylines(debug_image, [pts], True, color, 2)
            
            # Label
            label = f"{spot_id}: {status}"
            if best_detection:
                label += f" ({best_detection['class'][:3]})"
            
            cv2.putText(debug_image, label, tuple(polygon_coords[0]), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 255, 255), 1)
            
            results_data.append({
                "id": spot_id,
                "status": status,
                "overlap": max_overlap,
                "detection": best_detection['class'] if best_detection else None
            })
            
        except Exception as e:
            print(f"Error with {spot_id}: {e}")
            continue
    
    # Summary
    occupied = sum(1 for r in results_data if r["status"] == "OCCUPIED")
    free = len(results_data) - occupied
    
    print(f"\nRESULTS:")
    print(f"Free: {free}, Occupied: {occupied}, Total: {len(results_data)}")
    
    # Add summary to image
    cv2.putText(debug_image, f"Free: {free} | Occupied: {occupied} | Total: {len(results_data)}", 
               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    
    # Save debug image
    cv2.imwrite("debug_aggressive_detection.jpg", debug_image)
    print("Saved debug image: debug_aggressive_detection.jpg")
    
    # If still no occupancy detected, there's a fundamental alignment issue
    if occupied == 0:
        print("\n❌ STILL NO OCCUPANCY DETECTED!")
        print("This suggests polygon coordinates don't align with vehicle positions.")
        print("Solutions:")
        print("1. Run calibration again: python spotection_system.py --calibrate")
        print("2. Check if your spot_layout.json has correct coordinates")
        print("3. Manually adjust some polygon coordinates")
        
        # Print sample spot coordinates for manual checking
        print("\nSample spot coordinates:")
        for spot in spots_data[:3]:
            print(f"  {spot['id']}: {spot['polygon']}")
    
    return results_data

if __name__ == "__main__":
    quick_fix_detection()