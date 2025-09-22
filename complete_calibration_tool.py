import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import cv2
import json
import numpy as np

def complete_lot_calibration():
    """
    Enhanced calibration tool to map ALL parking spots in the lot
    """
    
    image_path = "data/test_image.jpg"
    output_json = "data/spot_layout_complete.json"
    
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image from {image_path}")
        return False
    
    original_image = image.copy()
    height, width = image.shape[:2]
    
    print("=== COMPLETE PARKING LOT CALIBRATION ===")
    print(f"Image size: {width}x{height}")
    print("\nInstructions:")
    print("1. Click 4 corners of each parking spot (clockwise from top-left)")
    print("2. Include ALL visible parking spots in the image")
    print("3. Start with top row, then move to subsequent rows")
    print("4. Press 's' to save, 'u' to undo last spot, 'r' to reset current spot")
    print("5. Press 'q' to quit")
    print("\nTip: Look for all the painted parking lines in the image!")
    
    spots = []
    current_polygon = []
    spot_counter = 1
    
    # Load existing spots if they exist
    try:
        with open("data/spot_layout.json", 'r') as f:
            existing_spots = json.load(f)
            spots.extend(existing_spots)
            spot_counter = len(spots) + 1
            print(f"Loaded {len(existing_spots)} existing spots")
    except:
        print("Starting fresh calibration")
    
    def draw_interface():
        display = original_image.copy()
        
        # Draw completed spots
        for i, spot in enumerate(spots):
            pts = np.array(spot["polygon"], dtype=np.int32)
            
            # Different colors for different rows/areas
            if i < 10:
                color = (0, 255, 0)  # Green for first row
            elif i < 20:
                color = (0, 165, 255)  # Orange for second row  
            else:
                color = (255, 0, 255)  # Magenta for additional spots
                
            cv2.polylines(display, [pts], True, color, 2)
            cv2.fillPoly(display, [pts], (*color, 30))
            
            # Add spot label
            center_x = int(np.mean([p[0] for p in spot["polygon"]]))
            center_y = int(np.mean([p[1] for p in spot["polygon"]]))
            cv2.putText(display, spot["id"], (center_x-15, center_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 2)
        
        # Draw current polygon in progress
        if len(current_polygon) > 0:
            for i, point in enumerate(current_polygon):
                cv2.circle(display, tuple(point), 5, (0, 255, 255), -1)
                cv2.putText(display, str(i+1), (point[0]+10, point[1]), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
            
            if len(current_polygon) >= 2:
                pts = np.array(current_polygon, dtype=np.int32)
                cv2.polylines(display, [pts], False, (0, 255, 255), 2)
                
                # Show preview of completed rectangle
                if len(current_polygon) == 3:
                    # Predict 4th point to complete rectangle
                    p1, p2, p3 = current_polygon
                    p4 = [p1[0] + p3[0] - p2[0], p1[1] + p3[1] - p2[1]]
                    preview_pts = np.array([p1, p2, p3, p4], dtype=np.int32)
                    cv2.polylines(display, [preview_pts], True, (255, 255, 0), 1)
        
        # Instructions overlay
        instructions = [
            f"Calibrating spot: {spot_counter}",
            f"Points clicked: {len(current_polygon)}/4",
            f"Total spots: {len(spots)}",
            "",
            "Controls:",
            "s = Save & Exit",
            "u = Undo last spot", 
            "r = Reset current",
            "q = Quit without saving"
        ]
        
        # Semi-transparent background for text
        overlay = display.copy()
        cv2.rectangle(overlay, (10, 10), (300, 250), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, display, 0.3, 0, display)
        
        y_pos = 30
        for instruction in instructions:
            color = (255, 255, 255) if instruction != "" else (255, 255, 255)
            cv2.putText(display, instruction, (20, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
            y_pos += 25
        
        return display
    
    def mouse_callback(event, x, y, flags, param):
        nonlocal current_polygon, spot_counter
        
        if event == cv2.EVENT_LBUTTONDOWN:
            current_polygon.append([x, y])
            print(f"Point {len(current_polygon)}: ({x}, {y})")
            
            if len(current_polygon) == 4:
                # Complete the spot
                spot_id = f"spot_{spot_counter}"
                spots.append({
                    "id": spot_id,
                    "polygon": current_polygon.copy()
                })
                print(f"✓ Added {spot_id}")
                current_polygon = []
                spot_counter += 1
    
    # Set up window
    cv2.namedWindow("Complete Lot Calibration", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Complete Lot Calibration", min(1200, width), min(800, height))
    cv2.setMouseCallback("Complete Lot Calibration", mouse_callback)
    
    # Main loop
    while True:
        display = draw_interface()
        cv2.imshow("Complete Lot Calibration", display)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("Calibration cancelled")
            break
        elif key == ord('s'):
            if len(spots) > 0:
                with open(output_json, 'w') as f:
                    json.dump(spots, f, indent=2)
                print(f"✓ Saved {len(spots)} spots to {output_json}")
                
                # Also update the main spot layout file
                with open("data/spot_layout.json", 'w') as f:
                    json.dump(spots, f, indent=2)
                print("✓ Updated data/spot_layout.json")
                
                break
            else:
                print("No spots to save!")
        elif key == ord('r'):
            current_polygon = []
            print("Reset current polygon")
        elif key == ord('u'):
            if len(spots) > 0:
                removed = spots.pop()
                spot_counter -= 1
                print(f"Removed {removed['id']}")
            else:
                print("No spots to undo!")
    
    cv2.destroyAllWindows()
    
    # Generate mapping suggestions
    if len(spots) > 0:
        print(f"\n=== CALIBRATION COMPLETE ===")
        print(f"Total spots mapped: {len(spots)}")
        print("\nSpot distribution:")
        
        # Analyze spot positions to suggest grouping
        y_positions = []
        for spot in spots:
            avg_y = np.mean([p[1] for p in spot["polygon"]])
            y_positions.append(avg_y)
        
        if y_positions:
            y_positions.sort()
            print(f"Y-coordinate range: {int(min(y_positions))} to {int(max(y_positions))}")
            
        print("\nNext steps:")
        print("1. Test detection: python spotection_system.py")
        print("2. Run debug if needed: python debug_spotection.py") 
        print("3. Start web server: python webapp/spotection_web_api.py")
        
        return True
    
    return False

def suggest_grid_spots():
    """Helper function to suggest spot coordinates based on common grid patterns"""
    
    print("\n=== GRID PATTERN SUGGESTIONS ===")
    print("If your parking lot follows a regular grid pattern, here are some templates:")
    print("\nStandard parking spot size: ~70x80 pixels")
    print("Common patterns:")
    print("- Two rows of 10-12 spots each")
    print("- Three rows of 7-8 spots each") 
    print("- Single row of 15-20 spots")
    
    # You could extend this to automatically generate grid patterns
    # based on image analysis, but manual calibration is more accurate

if __name__ == "__main__":
    success = complete_lot_calibration()
    if not success:
        suggest_grid_spots()
