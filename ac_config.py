"""
Calibrated AC detection config - Conference Room Camera 01
Calibrated on: live_snapshot_1.png / ac1_off.png / ac1_on.png / ac2_off.png / ac2_on.png
Method: std-based (variance) detection on LED digit ROI + flap/louver ROI,
midpoint thresholding between real OFF and ON sample frames.
"""

AC_UNITS = {
    "left_ac": {
        "label": "Kenwood (ceiling-mount, left)",
        "led_roi": (870, 410, 915, 450),
        "flap_roi": (810, 455, 1000, 505),
        "led_std_threshold": 14.6,
        "flap_std_threshold": 36.5,
    },
    "right_ac": {
        "label": "Kenwood GNova (right)",
        "led_roi": (1955, 670, 2010, 715),
        "flap_roi": (1820, 780, 2230, 830),
        "led_std_threshold": 18.6,
        "flap_std_threshold": 39.6,
    },
}


def get_std(frame, roi):
    import cv2
    x1, y1, x2, y2 = roi
    crop = frame[y1:y2, x1:x2]
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    return gray.std()


def check_ac_status(frame, unit_key):
    cfg = AC_UNITS[unit_key]
    led_std = get_std(frame, cfg["led_roi"])
    flap_std = get_std(frame, cfg["flap_roi"])

    led_on = led_std > cfg["led_std_threshold"]
    flap_open = flap_std > cfg["flap_std_threshold"]

    if led_on and flap_open:
        status, confidence = "ON", "high"
    elif (not led_on) and (not flap_open):
        status, confidence = "OFF", "high"
    else:
        status = "ON" if flap_open else "OFF"
        confidence = "low_conflict"

    return {
        "unit": unit_key,
        "label": cfg["label"],
        "status": status,
        "confidence": confidence,
        "led_std": round(led_std, 1),
        "flap_std": round(flap_std, 1),
    }


def check_all(frame):
    return [check_ac_status(frame, key) for key in AC_UNITS]


if __name__ == "__main__":
    import cv2
    frame = cv2.imread("test_frame.png")  # apni live frame ka path yahan daalna
    for r in check_all(frame):
        print(r)