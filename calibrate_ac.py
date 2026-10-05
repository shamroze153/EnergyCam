"""
AC threshold calibration helper.

Give it one image with the AC OFF and one with the AC ON (same camera, same
light mode). It measures the LED and flap "std" (texture/contrast) inside the
ROIs from ac_config.py and suggests midpoint thresholds to paste back into
ac_config.py.

Usage (conda env hfm_energy, project folder):
    python calibrate_ac.py --mode night --off night_ac_off.png --on night_ac_on.png
    python calibrate_ac.py --mode day   --off day_ac_off.png   --on day_ac_on.png

Tips:
  - For NIGHT, switch the room lights off so the camera is in IR (grayscale)
    mode, then take both pictures. Turn BOTH ACs off for the OFF image and
    BOTH on (flaps open) for the ON image.
  - Snapshots of the office stay on this laptop; *.png/*.jpg are git-ignored.
    Delete them after calibration.
"""

import argparse
import sys

import cv2

from ac_config import AC_UNITS, detect_light_mode, get_std

MIN_GAP = 3.0   # if ON and OFF differ by less than this, the ROI can't tell them apart


def load(path):
    img = cv2.imread(path)
    if img is None:
        sys.exit(f"Image nahi mili ya khul nahi saki: {path}")
    return img


def main():
    ap = argparse.ArgumentParser(description="Suggest LED/flap thresholds for ac_config.py")
    ap.add_argument("--mode", choices=["day", "night"], required=True)
    ap.add_argument("--off", required=True, help="image with the AC(s) OFF")
    ap.add_argument("--on", required=True, help="image with the AC(s) ON")
    ap.add_argument("--unit", choices=list(AC_UNITS), help="only calibrate this AC (default: all)")
    args = ap.parse_args()

    img_off, img_on = load(args.off), load(args.on)
    if img_off.shape != img_on.shape:
        print(f">> WARNING: dono images ka size alag hai {img_off.shape[:2]} vs {img_on.shape[:2]}")

    for name, img in (("OFF", img_off), ("ON", img_on)):
        detected = detect_light_mode(img)
        if detected.lower() != args.mode:
            print(f">> WARNING: {name} image {detected} mode mein lagti hai, lekin aap ne --mode {args.mode} diya hai.")

    units = [args.unit] if args.unit else list(AC_UNITS)
    snippets = []
    for key in units:
        cfg = AC_UNITS[key]
        h, w = img_off.shape[:2]
        for roi_name in ("led_roi", "flap_roi"):
            x1, y1, x2, y2 = cfg[roi_name]
            if x2 > w or y2 > h:
                sys.exit(f"{key} {roi_name} {cfg[roi_name]} image ({w}x{h}) se bahar hai — full-resolution frame use karein.")

        led_off, led_on = get_std(img_off, cfg["led_roi"]), get_std(img_on, cfg["led_roi"])
        flap_off, flap_on = get_std(img_off, cfg["flap_roi"]), get_std(img_on, cfg["flap_roi"])
        led_th = round((led_off + led_on) / 2, 1)
        flap_th = round((flap_off + flap_on) / 2, 1)

        print(f"\n=== {key} — {cfg['label']} ({args.mode.upper()}) ===")
        print(f"  LED  std:  OFF={led_off:6.1f}   ON={led_on:6.1f}   -> threshold {led_th}")
        print(f"  Flap std:  OFF={flap_off:6.1f}   ON={flap_on:6.1f}   -> threshold {flap_th}")
        for part, off_v, on_v in (("LED", led_off, led_on), ("Flap", flap_off, flap_on)):
            if on_v - off_v < MIN_GAP:
                print(f"  !! {part}: ON aur OFF mein farq bohat kam hai ({on_v - off_v:.1f}). "
                      f"Images check karein (AC sach mein on/off tha?) ya ROI adjust karein.")
        snippets.append((key, led_th, flap_th))

    print(f"\n--- ac_config.py mein paste karein (har AC ke andar \"{args.mode}\" line replace karein) ---")
    for key, led_th, flap_th in snippets:
        print(f'  # {key}\n  "{args.mode}": {{"led_std_threshold": {led_th}, "flap_std_threshold": {flap_th}}},')


if __name__ == "__main__":
    main()
