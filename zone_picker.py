"""
Fixed blur zone picker for privacy_blur.py

Grabs one frame from the camera (RTSP_URL in .env) or loads an image, lets you
draw rectangles with the mouse, and prints a ready-to-paste FIXED_ZONES line.
Coordinates are in FULL-resolution frame pixels (x1, y1, x2, y2), even though
the window shows a smaller picture so it fits on screen.

Usage:
    python zone_picker.py                 # live camera frame
    python zone_picker.py some_frame.png  # from an image

In the window:
    drag a rectangle -> ENTER or SPACE to keep it -> draw the next one
    ESC when finished
Nothing is saved to disk.
"""

import os
import sys
import time

import cv2
from dotenv import load_dotenv

MAX_WINDOW_WIDTH = 1280


def grab_camera_frame():
    load_dotenv()
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    url = os.getenv("RTSP_URL")
    if not url:
        sys.exit("RTSP_URL .env mein nahi mila.")
    print("Camera se frame le raha hai...")
    cap = cv2.VideoCapture(url)
    frame = None
    deadline = time.time() + 15
    reads = 0
    while time.time() < deadline and reads < 15:   # skip first frames (often grey/partial)
        ret, f = cap.read()
        if ret:
            frame = f
            reads += 1
    cap.release()
    if frame is None:
        sys.exit("Camera se frame nahi mila. RTSP_URL / network check karein.")
    return frame


def pick_zones(frame):
    h, w = frame.shape[:2]
    scale = min(1.0, MAX_WINDOW_WIDTH / w)
    shown = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale < 1 else frame
    print("Rectangle draw karein -> ENTER/SPACE. Mukammal hone par ESC dabayein.")
    rects = cv2.selectROIs("Blur zones (ESC = done)", shown, showCrosshair=False)
    cv2.destroyAllWindows()

    zones = []
    for (x, y, rw, rh) in (rects if rects is not None else []):
        if rw <= 0 or rh <= 0:
            continue
        x1, y1 = int(round(x / scale)), int(round(y / scale))
        x2, y2 = int(round((x + rw) / scale)), int(round((y + rh) / scale))
        zones.append((max(0, x1), max(0, y1), min(w, x2), min(h, y2)))
    return zones


def main():
    if len(sys.argv) > 1:
        frame = cv2.imread(sys.argv[1])
        if frame is None:
            sys.exit(f"Image nahi mili: {sys.argv[1]}")
    else:
        frame = grab_camera_frame()

    print(f"Frame size: {frame.shape[1]}x{frame.shape[0]}")
    zones = pick_zones(frame)
    if not zones:
        print("Koi zone select nahi hua.")
        return
    print("\n--- privacy_blur.py mein paste karein ---")
    print(f"FIXED_ZONES = {zones}")


if __name__ == "__main__":
    main()
