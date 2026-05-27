import os
import cv2
from ultralytics import YOLO
from PIL import Image

# Load YOLO model
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "ml_model", "yolo_model", "best.pt")
yolo_model = YOLO(MODEL_PATH)

CLASS_NAMES = ["algal", "oil spill", "plastic waste"]

def analyze_image(input_path, output_folder):
    try:
        # Run YOLO detection
        results = yolo_model(input_path)[0]

        img = cv2.imread(input_path)
        pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))

        detected = False
        labels = []

        for box in results.boxes:
            detected = True
            cls_id = int(box.cls[0])
            conf = float(box.conf[0]) * 100
            x1, y1, x2, y2 = map(int, box.xyxy[0])

            label = f"{CLASS_NAMES[cls_id]} ({conf:.2f}%)"
            labels.append(label)

            # Draw rectangle
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 3)
            cv2.putText(
                img,
                label,
                (x1, y1 - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2
            )

        if not detected:
            labels.append("No Pollution Detected")

        # Save processed image
        processed_path = os.path.join(
            output_folder, "processed_" + os.path.basename(input_path)
        )
        cv2.imwrite(processed_path, img)

        result_text = ", ".join(labels)
        percent = round(max([float(b.conf[0]) * 100 for b in results.boxes], default=0), 2)

        coords = (None, None)  # GPS can be added later

        return processed_path, result_text, percent, coords

    except Exception as e:
        return input_path, f"Error: {str(e)}", 0, (None, None)
