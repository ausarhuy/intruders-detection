import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

import cv2
from supervision import LabelAnnotator, Detections, BoxCornerAnnotator, Color
from torch.cuda import is_available
from ultralytics import YOLO


class PersonDetection:
    def __init__(self, capture_index, email_notification):
        self.capture_index = capture_index
        self.total_detected = 0
        self.email_notification = email_notification

        # Load the model
        self.model = YOLO("./weights/yolov8n.pt")

        # Instanciate Supervision Annotators
        self.box_annotator = BoxCornerAnnotator(color=Color.from_hex("#ff0000"), thickness=10, corner_length=30)
        self.label_annotator = LabelAnnotator(color=Color.from_hex("#ff0000"), text_color=Color.from_hex("#fff"))

        self.device = 'cuda:0' if is_available() else 'cpu'

    @staticmethod
    async def async_imwrite(filename, image):
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            await loop.run_in_executor(pool, cv2.imwrite, filename, image)

    async def async_send_email(self, num_detections):
        await asyncio.get_running_loop().run_in_executor(None, self.email_notification.send_email, num_detections)

    @staticmethod
    async def async_delete_files(directory):
        # Function to delete file
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor() as pool:
            tasks = []
            for root, _, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    tasks.append(loop.run_in_executor(pool, os.remove, file_path))

            await asyncio.gather(*tasks)

    def predict(self, img):

        # Detect and track object using YOLOv8 model
        result = self.model.track(img, persist=True, device=self.device)[0]

        # Convert result to Supervision Detection object
        detections = Detections.from_ultralytics(result)

        # In YOLOv8 model, objects with class_id 0 refer to a person. So, we should filter objects detected to only consider person
        detections = detections[detections.class_id == 0]

        return detections

    def plot_bboxes(self, detections: Detections, img):
        labels = [f"Intruder #{track_id}" for track_id in detections.tracker_id]
        # Add the box to the image
        annotated_image = self.box_annotator.annotate(scene=img, detections=detections)

        # Add the label to the image
        annotated_image = self.label_annotator.annotate(scene=annotated_image, detections=detections, labels=labels)

        return annotated_image

    async def start(self):
        cap = cv2.VideoCapture(self.capture_index)
        if not cap.isOpened():
            raise AssertionError
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 640)
        frame_count = 0

        try:
            while True:
                ret, img = cap.read()
                if not ret:
                    print("Failed to grab frame")
                    break

                results = self.predict(img)
                if results and results.tracker_id is not None:
                    img = self.plot_bboxes(results, img)

                    if len(results.class_id) > self.total_detected:  # We will send notification only when new person is detected

                        # Let's crop each person detected and save it into images folder
                        tasks = []
                        for xyxy, track_id in zip(results.xyxy, results.tracker_id):
                            detected_intruders = img[int(xyxy[1] - 25):int(xyxy[3]), int(xyxy[0]):int(xyxy[2])]
                            tasks.append(self.async_imwrite(f"./images/intruder_{track_id}.jpg", detected_intruders))

                        # Send notification
                        await self.async_send_email(len(results.class_id))

                        # Then notification sent, we must delete all previous saved images
                        await self.async_delete_files("./images/")

                        await asyncio.gather(*tasks)

                        self.total_detected = len(results.class_id)
                else:
                    self.total_detected = 0

                cv2.imshow('Intruder Detection', img)
                frame_count += 1

                if cv2.waitKey(1) == 27:  # ESC key to break
                    break
        finally:
            cap.release()
            cv2.destroyAllWindows()
            self.email_notification.quit()
