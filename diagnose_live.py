"""
Live diagnosis: shows WHY the system decides EMPTY/OCCUPIED, DAY/NIGHT and AC ON/OFF.

Reads ~20 frames from the camera (RTSP_URL in .env) and prints, per frame:
  - light mode numbers (colour difference, brightness) -> DAY/NIGHT
  - every person detection YOLO sees, with its confidence
  - AC LED / flap std values vs thresholds

Nothing is saved, nothing is emailed, nothing is written to the database.

Usage (stop unified_system.py first, or run while it runs - both work):
    python diagnose_live.py
"""

import os
import time

import cv2
import numpy as np
from dotenv import load_dotenv
from ultralytics import YOLO

from ac_config import AC_UNITS, NIGHT_BRIGHTNESS_MAX, NIGHT_CHANNEL_DIFF_MAX, check_ac_status, detect_light_mode

FRAMES = 20
PRESENCE_CONF = 0.25   # YOLO default: what unified_system uses for "someone is there"
COUNT_CONF = 0.5       # COUNT_CONFIDENCE in unified_system: what gets counted as People


def light_numbers(frame):
    small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA).astype(np.int16)
    b, g, r = small[:, :, 0], small[:, :, 1], small[:, :, 2]
    return (np.abs(b - g).mean() + np.abs(g - r).mean()) / 2, small.mean()


def main():
    load_dotenv()
    os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
    print("Camera se connect ho raha hai...")
    cap = cv2.VideoCapture(os.getenv("RTSP_URL"))
    model = YOLO("yolov8n.pt")

    for _ in range(10):   # skip the first frames (often grey/partial)
        cap.read()

    print(f"\nNIGHT agar colour-diff < {NIGHT_CHANNEL_DIFF_MAX} YA brightness < {NIGHT_BRIGHTNESS_MAX}")
    print(f"Presence: koi bhi person >= {PRESENCE_CONF} | People count: sirf >= {COUNT_CONF}\n")

    for i in range(1, FRAMES + 1):
        ret, frame = cap.read()
        if not ret or frame is None:
            print(f"[{i:2}] frame nahi mila")
            time.sleep(0.5)
            continue

        diff, bright = light_numbers(frame)
        mode = detect_light_mode(frame)

        res = model(frame, classes=[0], conf=0.1, imgsz=640, verbose=False)[0]
        persons = []
        for box, conf in zip(res.boxes.xyxy.tolist(), res.boxes.conf.tolist()):
            x1, y1, x2, y2 = map(int, box)
            persons.append(f"{conf:.2f}@({x1},{y1})")
        presence = sum(1 for c in res.boxes.conf.tolist() if c >= PRESENCE_CONF)
        counted = sum(1 for c in res.boxes.conf.tolist() if c >= COUNT_CONF)

        ac_parts = []
        for key in AC_UNITS:
            r = check_ac_status(frame, key, mode)
            ac_parts.append(f"{key}={r['status']}({r['confidence']}) led={r['led_std']} flap={r['flap_std']}")

        print(f"[{i:2}] {frame.shape[1]}x{frame.shape[0]} | mode={mode} (colour-diff={diff:.1f}, brightness={bright:.0f})")
        print(f"     persons seen: {persons or 'none'} -> presence={'YES' if presence else 'no'}, People={counted}")
        print(f"     {' | '.join(ac_parts)}")

    cap.release()
    print("\nThresholds (DAY):", {k: v["day"] for k, v in AC_UNITS.items()})
    print("Ye poora output copy karke bhej dein.")


if __name__ == "__main__":
    main()
