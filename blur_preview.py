import cv2
import os
import time
import threading
from dotenv import load_dotenv
from ultralytics import YOLO
from privacy_blur import anonymize

load_dotenv()
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"


class LatestFrame:
    """Background mein camera padhta rehta hai, hum hamesha sirf latest frame lete hain."""
    def __init__(self, url):
        self.cap = cv2.VideoCapture(url)
        self.frame = None
        self.lock = threading.Lock()
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            ret, f = self.cap.read()
            if ret:
                with self.lock:
                    self.frame = f

    def get(self):
        with self.lock:
            return None if self.frame is None else self.frame.copy()


cam = LatestFrame(os.getenv("RTSP_URL"))
model = YOLO("yolov8n.pt")

print("Preview chal raha hai.  's' = test image save,  'q' = band karo")

while True:
    frame = cam.get()
    if frame is None:
        time.sleep(0.2)
        continue

    blurred = anonymize(frame, model)
    cv2.imshow("Blurred preview", cv2.resize(blurred, (1280, 720)))

    key = cv2.waitKey(1) & 0xFF
    if key == ord('s'):
        cv2.imwrite("blur_test.png", blurred)
        print("Saved: blur_test.png")
    elif key == ord('q'):
        break

cv2.destroyAllWindows()