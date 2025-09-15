from ultralytics import YOLO
import cv2

# Load YOLOv8 pre-trained model (YOLOv8n = nano / v8s = small)
model = YOLO("yolov8n.pt")  # You can also try 'yolov8s.pt' for better accuracy

# Inference on image
image_path = "data/test_image.jpg"
results = model(image_path)

# Plot and save results
res_plotted = results[0].plot()
cv2.imwrite("output.jpg", res_plotted)

# Print detections
for box in results[0].boxes:
    cls = int(box.cls[0])
    conf = float(box.conf[0])
    print(f"[{model.names[cls]}] Confidence: {conf:.2f}")
