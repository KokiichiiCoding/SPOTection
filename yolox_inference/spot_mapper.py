import json
import cv2
import numpy as np
from shapely.geometry import Polygon, box
from ultralytics import YOLO

# Load parking spot layout
with open("data/spot_layout.json", "r") as f:
    spots = json.load(f)

# Load test image
image_path = "data/test_image.jpg"
image = cv2.imread(image_path)

# Run YOLOv8
model = YOLO("yolov8n.pt")
results = model(image_path)[0]

# Prepare output
output = image.copy()

# Convert detection boxes to shapely boxes
detections = []
for box_data in results.boxes:
    x1, y1, x2, y2 = box_data.xyxy[0]
    conf = float(box_data.conf[0])
    cls = int(box_data.cls[0])
    label = model.names[cls]
    if label in ["car", "truck", "van"]:
        x1, y1, x2, y2 = map(int, (x1, y1, x2, y2))
        detections.append({
            "box": (x1, y1, x2, y2),
            "conf": conf,
            "label": label
        })
        # Draw detection box on image (blue)
        cv2.rectangle(output, (x1, y1), (x2, y2), (255, 0, 0), 2)
        cv2.putText(output, label, (x1, y1 - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)

# Analyze each spot
for spot in spots:
    spot_id = spot["id"]
    poly_points = np.array(spot["polygon"], dtype=np.int32)
    spot_poly = Polygon(poly_points)

    occupied = False
    for det in detections:
        x1, y1, x2, y2 = det["box"]
        car_box = box(x1, y1, x2, y2)
        overlap_area = spot_poly.intersection(car_box).area

        # Check overlap from both perspectives
        if (overlap_area / spot_poly.area > 0.15) or (overlap_area / car_box.area > 0.15):
            occupied = True
            print(f"[DEBUG] {spot_id} OCCUPIED by {det['label']} — Overlap area: {overlap_area:.2f}")
            break
        else:
            print(f"[DEBUG] {spot_id} NOT OCCUPIED — Overlap: {overlap_area:.2f}")

    # Draw the spot polygon
    color = (0, 0, 255) if occupied else (0, 255, 0)
    cv2.polylines(output, [poly_points], isClosed=True, color=color, thickness=2)
    label_text = f"{spot_id}: {'OCCUPIED' if occupied else 'FREE'}"
    cv2.putText(output, label_text, tuple(poly_points[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)

# Save visualization
cv2.imwrite("output_spots.jpg", output)
print("[INFO] Annotated image saved as 'output_spots.jpg'")
