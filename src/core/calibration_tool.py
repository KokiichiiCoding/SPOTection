"""
Enhanced Multi-Image Calibration Tool
Allows selection and calibration of any image in data/images/
"""

import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import cv2
import json
import numpy as np
from pathlib import Path
from typing import List, Tuple


def select_image_from_directory(images_dir: str = "data/images") -> str:
    """Interactive image selection"""
    
    images_path = Path(images_dir)
    if not images_path.exists():
        print(f"Directory not found: {images_dir}")
        return None
    
    # Find all images
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
        print(f"{i}. {img_path.name}")
    
    while True:
        try:
            choice = input(f"\nSelect image (1-{len(images)}) or 'q' to quit: ").strip()
            
            if choice.lower() == 'q':
                return None
            
            idx = int(choice) - 1
            if 0 <= idx < len(images):
                selected = str(images[idx])
                print(f"✓ Selected: {images[idx].name}")
                return selected
            else:
                print(f"Please enter a number between 1 and {len(images)}")
        except ValueError:
            print("Invalid input. Please enter a number.")


def calibrate_image(image_path: str, existing_layout: str = None):
    """
    Enhanced calibration tool for any image
    """
    
    # Load image
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Could not load image from {image_path}")
        return False
    
    # Generate output paths based on image name
    image_name = Path(image_path).stem
    output_json = f"data/layouts/{image_name}_layout.json"
    
    original_image = image.copy()
    height, width = image.shape[:2]
    
    print("\n" + "="*60)
    print(f"CALIBRATING: {Path(image_path).name}")
    print("="*60)
    print(f"Image size: {width}x{height}")
    print(f"Output will be saved to: {output_json}")
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
    if existing_layout and os.path.exists(existing_layout):
        try:
            with open(existing_layout, 'r') as f:
                existing_spots = json.load(f)
                spots.extend(existing_spots)
                spot_counter = len(spots) + 1
                print(f"\n✓ Loaded {len(existing_spots)} existing spots")
        except Exception as e:
            print(f"Could not load existing layout: {e}")
    elif os.path.exists(output_json):
        try:
            with open(output_json, 'r') as f:
                existing_spots = json.load(f)
                spots.extend(existing_spots)
                spot_counter = len(spots) + 1
                print(f"\n✓ Loaded {len(existing_spots)} existing spots from {output_json}")
        except Exception as e:
            print(f"Could not load existing layout: {e}")
    else:
        print("\nStarting fresh calibration")
    
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
            elif i < 30:
                color = (255, 0, 255)  # Magenta
            else:
                color = (255, 255, 0)  # Cyan
                
            cv2.polylines(display, [pts], True, color, 2)
            
            # Semi-transparent fill
            overlay = display.copy()
            cv2.fillPoly(overlay, [pts], color)
            cv2.addWeighted(overlay, 0.2, display, 0.8, 0, display)
            
            # Add spot label
            center_x = int(np.mean([p[0] for p in spot["polygon"]]))
            center_y = int(np.mean([p[1] for p in spot["polygon"]]))
            
            # Background for text
            text = spot["id"]
            (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(display, 
                         (center_x - tw//2 - 3, center_y - th//2 - 3),
                         (center_x + tw//2 + 3, center_y + th//2 + 3),
                         (0, 0, 0), -1)
            
            cv2.putText(display, text, (center_x - tw//2, center_y + th//2), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        
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
            f"Image: {Path(image_path).name}",
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
        cv2.rectangle(overlay, (10, 10), (320, 270), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, display, 0.3, 0, display)
        
        y_pos = 30
        for instruction in instructions:
            cv2.putText(display, instruction, (20, y_pos), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
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
    window_name = f"Calibration: {Path(image_path).name}"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, min(1200, width), min(800, height))
    cv2.setMouseCallback(window_name, mouse_callback)
    
    # Main loop
    while True:
        display = draw_interface()
        cv2.imshow(window_name, display)
        
        key = cv2.waitKey(1) & 0xFF
        
        if key == ord('q'):
            print("Calibration cancelled")
            break
        elif key == ord('s'):
            if len(spots) > 0:
                # Ensure output directory exists
                Path(output_json).parent.mkdir(parents=True, exist_ok=True)
                
                with open(output_json, 'w') as f:
                    json.dump(spots, f, indent=2)
                print(f"✓ Saved {len(spots)} spots to {output_json}")
                
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
    
    # Generate summary
    if len(spots) > 0:
        print(f"\n=== CALIBRATION COMPLETE ===")
        print(f"Image: {Path(image_path).name}")
        print(f"Total spots mapped: {len(spots)}")
        print(f"Saved to: {output_json}")
        
        # Analyze spot positions
        y_positions = [np.mean([p[1] for p in spot["polygon"]]) for spot in spots]
        
        if y_positions:
            y_positions.sort()
            print(f"Y-coordinate range: {int(min(y_positions))} to {int(max(y_positions))}")
            
        print("\nNext steps:")
        print(f"1. Test detection: python src/core/detection_system.py --image {image_path} --spots {output_json}")
        print(f"2. Start web server: python src/api/main.py")
        
        return True
    
    return False


def batch_calibration_menu():
    """Menu for calibrating multiple images"""
    
    print("\n" + "="*60)
    print("MULTI-IMAGE CALIBRATION TOOL")
    print("="*60)
    print("\nThis tool allows you to:")
    print("1. Calibrate a single image")
    print("2. Calibrate multiple images in sequence")
    print("3. Continue calibration of an existing layout")
    
    images_dir = "data/images"
    
    while True:
        print("\n" + "-"*60)
        print("Options:")
        print("1. Select and calibrate single image")
        print("2. Calibrate all images in sequence")
        print("3. List all images and their calibration status")
        print("q. Quit")
        
        choice = input("\nSelect option: ").strip()
        
        if choice == '1':
            # Single image calibration
            image_path = select_image_from_directory(images_dir)
            if image_path:
                calibrate_image(image_path)
        
        elif choice == '2':
            # Batch calibration
            images_path = Path(images_dir)
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
            images = []
            for ext in image_extensions:
                images.extend(images_path.glob(f'*{ext}'))
                images.extend(images_path.glob(f'*{ext.upper()}'))
            
            if not images:
                print(f"No images found in {images_dir}")
                continue
            
            print(f"\nFound {len(images)} images to calibrate")
            confirm = input("Calibrate all in sequence? (y/n): ").strip().lower()
            
            if confirm == 'y':
                for i, img_path in enumerate(images, 1):
                    print(f"\n{'='*60}")
                    print(f"Image {i}/{len(images)}")
                    print('='*60)
                    
                    calibrate_image(str(img_path))
                    
                    if i < len(images):
                        cont = input("\nContinue to next image? (y/n): ").strip().lower()
                        if cont != 'y':
                            break
        
        elif choice == '3':
            # List images and calibration status
            images_path = Path(images_dir)
            layouts_path = Path("data/layouts")
            
            image_extensions = ['.jpg', '.jpeg', '.png', '.bmp']
            images = []
            for ext in image_extensions:
                images.extend(images_path.glob(f'*{ext}'))
                images.extend(images_path.glob(f'*{ext.upper()}'))
            
            print("\n" + "="*60)
            print("IMAGE CALIBRATION STATUS")
            print("="*60)
            
            for img_path in sorted(images):
                layout_file = layouts_path / f"{img_path.stem}_layout.json"
                
                if layout_file.exists():
                    try:
                        with open(layout_file, 'r') as f:
                            spots = json.load(f)
                        status = f"✓ Calibrated ({len(spots)} spots)"
                    except:
                        status = "✗ Invalid layout file"
                else:
                    status = "○ Not calibrated"
                
                print(f"{status:30} {img_path.name}")
        
        elif choice.lower() == 'q':
            print("\nExiting calibration tool")
            break
        
        else:
            print("Invalid option")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Multi-Image Calibration Tool")
    parser.add_argument("--image", help="Calibrate specific image")
    parser.add_argument("--images-dir", default="data/images", 
                       help="Directory containing images")
    parser.add_argument("--existing-layout", help="Continue from existing layout")
    parser.add_argument("--menu", action="store_true",
                       help="Show interactive menu")
    
    args = parser.parse_args()
    
    if args.image:
        # Calibrate specific image
        if not os.path.exists(args.image):
            print(f"Error: Image not found: {args.image}")
            return 1
        
        calibrate_image(args.image, args.existing_layout)
    
    elif args.menu or not args.image:
        # Show interactive menu
        batch_calibration_menu()
    
    return 0


if __name__ == "__main__":
    exit(main())