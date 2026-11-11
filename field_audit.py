"""The whole audit, both campuses, in one command and one zip.

    python field_audit.py

Run it on the laptop on the camera network, with the loop running (the live
check compares the cameras with what the loop last wrote). It takes a few
minutes and does, in order:

  1. doctor.py --cameras   every recorder answers, the database answers
  2. verify_live.py        each room: what the dashboard says against what
                           its cameras show right now, twice over, with a
                           picture of every room where they disagree
  3. ac_survey.py          a full-size picture from every camera of every
                           room with an air conditioner, to find the displays
                           and draw the calibration boxes
  4. check_room.py --all   only out of working hours: every detection on
                           every camera, drawn. With nobody in the building
                           each one is a ghost by definition -- a chair, a
                           coat, a poster -- and this is where they show.

and puts every output in field_audit_<date>.zip for review.

The pictures in it are NOT blurred, and are taken while people are at their
desks. Look through the zip before it goes anywhere.
"""
import glob
import os
import subprocess
import sys
import time
import zipfile
from datetime import datetime

STEPS = [
    ("doctor", ["doctor.py", "--cameras"]),
    ("verify", ["verify_live.py", "--pictures", "faults"]),
    ("ac_survey", ["ac_survey.py"]),
]


def run(cmd, log):
    """Run one step, showing its output and keeping a copy of it."""
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUNBUFFERED="1",
               # Set before the child starts, which is the only time the
               # decoder on Windows listens; see quiet_start.py.
               OPENCV_FFMPEG_LOGLEVEL="0", ENERGYCAM_QUIET_CHILD="1")
    proc = subprocess.Popen([sys.executable] + cmd, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, env=env, text=True,
                            encoding="utf-8", errors="replace")
    with open(log, "w", encoding="utf-8") as fh:
        for line in proc.stdout:
            print(line, end="")
            fh.write(line)
    return proc.wait()


def out_of_hours():
    try:
        import yaml
        from schedule import PKT, in_operations
        hours = yaml.safe_load(open("rooms.yaml", encoding="utf-8")).get("hours")
        return not in_operations(datetime.now(PKT), hours)
    except Exception:                                       # noqa: BLE001
        return False


def main():
    if not os.path.exists("rooms.yaml"):
        sys.exit("run this from the project folder")
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    work = "field_audit_%s" % stamp
    os.makedirs(work, exist_ok=True)
    began = time.time()
    codes = {}
    steps = list(STEPS)
    if out_of_hours():
        steps.append(("night_check", ["check_room.py", "--all"]))
    for name, cmd in steps:
        print("\n" + "=" * 70 + "\n>> %s: python %s\n" % (name, " ".join(cmd))
              + "=" * 70)
        codes[name] = run(cmd, os.path.join(work, name + ".txt"))

    pictures = [p for p in glob.glob(os.path.join("frames", "verify", "*.jpg"))
                if os.path.getmtime(p) >= began]
    survey = [p for p in glob.glob(os.path.join("ac_survey", "**", "*"),
                                   recursive=True)
              if os.path.isfile(p) and os.path.getmtime(p) >= began]
    ghosts = [p for p in glob.glob(os.path.join("frames", "*_boxes.jpg"))
              if os.path.getmtime(p) >= began]
    name = work + ".zip"
    with zipfile.ZipFile(name, "w", zipfile.ZIP_STORED) as z:
        for log in sorted(glob.glob(os.path.join(work, "*.txt"))):
            z.write(log, os.path.basename(log))
        for p in pictures:
            z.write(p, os.path.join("verify", os.path.basename(p)))
        for p in survey:
            z.write(p, os.path.join("ac_survey", os.path.relpath(p, "ac_survey")))
        for p in ghosts:
            z.write(p, os.path.join("night", os.path.basename(p)))
    size = os.path.getsize(name) / 1e6
    print("\n>> done in %d min. %s"
          % ((time.time() - began) // 60,
             ", ".join("%s %s" % (k, "ok" if v == 0 else "exit %d" % v)
                       for k, v in codes.items())))
    print(">> %s -- %d disagreement picture(s), %d survey file(s), %d night"
          " detection(s), %.1f MB"
          % (name, len(pictures), len(survey), len(ghosts), size))
    print(">> These pictures are NOT blurred. Look through the zip before"
          " sending it.")
    if size > 28:
        print(">> Over 28 MB: send verify/ and ac_survey/ as two zips, or"
              " share it from Drive.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
