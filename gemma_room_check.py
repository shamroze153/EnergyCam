"""EnergyCam + Gemma 4: ask a vision model what the camera sees.

YOLO (on this machine) counts people and blurs them, so no face ever leaves the
building. The blurred frame then goes to Gemma 4 through the Gemini API, which
reports what YOLO cannot: are the lights on, is the AC running, is energy being
wasted, and a short alert in English and Roman Urdu.

Usage:
    python gemma_room_check.py --image room.jpg        # check a saved photo
    python gemma_room_check.py                         # one frame from RTSP_URL
    python gemma_room_check.py --watch 10              # every 10 minutes
    python gemma_room_check.py --image room.jpg --dry-run   # no API call

Needs GEMINI_API_KEY in .env (free key: https://aistudio.google.com/apikey).
"""
import argparse
import json
import os
import re
import time
from datetime import datetime

import cv2
from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

DEFAULT_MODEL = "gemma-4-26b-a4b-it"     # or gemma-4-31b-it
LOG_FILE = "gemma_checks.jsonl"

PROMPT = """You are EnergyCam, an energy auditor looking at one office CCTV frame.
People in the image are pixelated for privacy; a separate detector counted {people} person(s).
Look at the room and answer ONLY with a JSON object, no other text:
{{
  "lights_on": true | false | null,
  "ac_visible": true | false,
  "ac_running": true | false | null,
  "ac_evidence": "what you saw: open louvers, lit display/LED, closed flap, ...",
  "other_devices_on": ["monitor", "projector", ...],
  "energy_waste": true | false,
  "waste_reason": "one short sentence",
  "alert_en": "one short alert for the facility team, or empty if nothing is wrong",
  "alert_ur": "the same alert in simple Roman Urdu, or empty"
}}
Use null when you cannot tell. Energy is wasted when the room is empty
(0 people) but lights, AC or other devices are on."""


def grab_frame(image_path):
    if image_path:
        frame = cv2.imread(image_path)
        if frame is None:
            raise SystemExit(f"Could not read image: {image_path}")
        return frame
    url = os.getenv("RTSP_URL")
    if not url:
        raise SystemExit("Set RTSP_URL in .env or pass --image")
    cap = cv2.VideoCapture(url)
    ok, frame = False, None
    for _ in range(5):                    # skip stale buffered frames
        ok, frame = cap.read()
    cap.release()
    if not ok:
        raise SystemExit("Could not read a frame from the camera")
    return frame


def count_and_blur(frame, use_yolo=True):
    """People count + privacy blur, both on this machine."""
    if not use_yolo:
        return frame, None
    from ultralytics import YOLO
    from privacy_blur import anonymize
    model = YOLO("yolov8n.pt")
    people = sum(1 for c in model(frame, classes=[0], verbose=False)[0].boxes.cls.tolist())
    return anonymize(frame, model), people


def build_prompt(people):
    return PROMPT.format(people="an unknown number of" if people is None else people)


def ask_gemma(jpeg_bytes, people, model_name):
    from google import genai
    from google.genai import types
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    response = client.models.generate_content(
        model=model_name,
        contents=[types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg"),
                  build_prompt(people)],
    )
    return parse_json(response.text)


def parse_json(text):
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        return {"error": "no JSON in reply", "raw": text}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"error": "bad JSON in reply", "raw": text}


def check_once(args):
    frame = grab_frame(args.image)
    safe, people = count_and_blur(frame, use_yolo=not args.no_yolo)
    ok, buf = cv2.imencode(".jpg", safe, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not ok:
        raise SystemExit("Could not encode the frame")
    if args.dry_run:
        result = {"dry_run": True, "prompt": build_prompt(people)}
    else:
        if not os.getenv("GEMINI_API_KEY"):
            raise SystemExit("Set GEMINI_API_KEY in .env (https://aistudio.google.com/apikey)")
        result = ask_gemma(buf.tobytes(), people, args.model)
    record = {"time": datetime.now().isoformat(timespec="seconds"), "people": people,
              "model": args.model, **result}
    with open(LOG_FILE, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    cv2.imwrite("gemma_last_frame.jpg", safe)       # the exact (blurred) image that was sent
    print(json.dumps(record, indent=2, ensure_ascii=False))
    if result.get("energy_waste"):
        print("\n*** ENERGY WASTE ***")
        print(result.get("alert_en", ""))
        print(result.get("alert_ur", ""))
    return record


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--image", help="check a saved image instead of the camera")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--watch", type=float, default=0, help="repeat every N minutes")
    ap.add_argument("--no-yolo", action="store_true", help="skip local people count and blur")
    ap.add_argument("--dry-run", action="store_true", help="do everything except the API call")
    args = ap.parse_args()
    while True:
        check_once(args)
        if not args.watch:
            break
        time.sleep(args.watch * 60)


if __name__ == "__main__":
    main()
