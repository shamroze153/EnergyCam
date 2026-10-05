"""
Calibrated AC detection config - Conference Room Camera 01
Calibrated on: live_snapshot_1.png / ac1_off.png / ac1_on.png / ac2_off.png / ac2_on.png
Method: std-based (variance) detection on LED digit ROI + flap/louver ROI,
midpoint thresholding between real OFF and ON sample frames.

Decision rule (LED is primary):
  AC = ON  if LED is lit OR flap is open
  AC = OFF only when LED is off AND flap is closed
  confidence: "high" (both agree) / "led_only" / "flap_only"

DAY / NIGHT:
  The camera switches to IR night mode (grayscale) when the lights are off,
  so each AC has separate "day" and "night" thresholds. The DAY values were
  calibrated on daytime colour frames. Until NIGHT values are calibrated
  (use calibrate_ac.py with night images), NIGHT falls back to DAY values.
"""

import cv2
import numpy as np

AC_UNITS = {
    "left_ac": {
        "label": "Kenwood (ceiling-mount, left)",
        "led_roi": (870, 410, 915, 450),
        "flap_roi": (810, 455, 1000, 505),
        "day": {"led_std_threshold": 14.6, "flap_std_threshold": 36.5},
        "night": None,  # calibrate_ac.py --mode night se bharein
    },
    "right_ac": {
        "label": "Kenwood GNova (right)",
        "led_roi": (1955, 670, 2010, 715),
        "flap_roi": (1820, 780, 2230, 830),
        "day": {"led_std_threshold": 18.6, "flap_std_threshold": 39.6},
        "night": None,  # calibrate_ac.py --mode night se bharein
    },
}

# --- Day / night detection ---
# IR night mode gives a grayscale picture: B, G, R channels almost equal.
NIGHT_CHANNEL_DIFF_MAX = 3.0   # avg |B-G|,|G-R| below this = grayscale = NIGHT
NIGHT_BRIGHTNESS_MAX = 40      # avg brightness (0-255) below this = NIGHT too

_night_fallback_warned = set()


def detect_light_mode(frame):
    """Returns "NIGHT" if the frame is grayscale (IR mode) or very dark, else "DAY"."""
    small = cv2.resize(frame, (160, 90), interpolation=cv2.INTER_AREA).astype(np.int16)
    b, g, r = small[:, :, 0], small[:, :, 1], small[:, :, 2]
    channel_diff = (np.abs(b - g).mean() + np.abs(g - r).mean()) / 2
    brightness = small.mean()
    if channel_diff < NIGHT_CHANNEL_DIFF_MAX or brightness < NIGHT_BRIGHTNESS_MAX:
        return "NIGHT"
    return "DAY"


def get_thresholds(unit_key, mode="DAY"):
    cfg = AC_UNITS[unit_key]
    if mode == "NIGHT":
        if cfg.get("night"):
            return cfg["night"]
        if unit_key not in _night_fallback_warned:
            _night_fallback_warned.add(unit_key)
            print(f">> WARNING: {unit_key} ke NIGHT thresholds abhi calibrate nahi hue — "
                  f"DAY values use ho rahi hain. calibrate_ac.py --mode night chalayein.")
    return cfg["day"]


def get_std(frame, roi):
    x1, y1, x2, y2 = roi
    crop = frame[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return gray.std()


def check_ac_status(frame, unit_key, mode="DAY"):
    cfg = AC_UNITS[unit_key]
    th = get_thresholds(unit_key, mode)
    led_std = get_std(frame, cfg["led_roi"])
    flap_std = get_std(frame, cfg["flap_roi"])

    led_on = led_std > th["led_std_threshold"]
    flap_open = flap_std > th["flap_std_threshold"]

    if led_on and flap_open:
        status, confidence = "ON", "high"
    elif led_on:
        status, confidence = "ON", "led_only"      # LED primary
    elif flap_open:
        status, confidence = "ON", "flap_only"     # e.g. LED display dimmed/off
    else:
        status, confidence = "OFF", "high"

    return {
        "unit": unit_key,
        "label": cfg["label"],
        "mode": mode,
        "status": status,
        "confidence": confidence,
        "led_std": round(float(led_std), 1),
        "flap_std": round(float(flap_std), 1),
    }


def check_all(frame, mode=None):
    mode = mode or detect_light_mode(frame)
    return [check_ac_status(frame, key, mode) for key in AC_UNITS]


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "test_frame.png"  # apni live frame ka path
    frame = cv2.imread(path)
    if frame is None:
        sys.exit(f"Image nahi mili: {path}")
    print("Mode:", detect_light_mode(frame))
    for r in check_all(frame):
        print(r)
