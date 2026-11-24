"""The staff roster and their faces, for campus face recognition.

Shamroze, 24 Nov 2026: HR approved face recognition for everybody at the
campus and the staff have been told; take everybody in the members
directory (life.disrupt.com) except the Gadits -- name, employee ID,
designation, photo -- and find where each of them sits on 140-H's cameras.

What lives where (all under people/, git-ignored, this laptop only):
  people/roster.csv       employee_id, name, designation, department,
                          project -- read from the directory by the
                          signed-in browser (no emails kept)
  people/photos/<id>.jpg  the directory's own photo of each, kept here for
                          the double check by eye (a camera crop beside it)
  people/faces.npz        ids, vecs: SFace numbers of each photo's face

    python staff_faces.py roster      people/roster_raw.json -> roster.csv
    python staff_faces.py photos      fetch the photos not yet here
    python staff_faces.py enroll      face numbers of every photo

No name, ID or picture is ever written into the repository.
"""
import csv
import json
import os
import sys
import time
import urllib.request

import numpy as np

import faces

FOLDER = "people"
ROSTER = os.path.join(FOLDER, "roster.csv")
RAW = os.path.join(FOLDER, "roster_raw.json")
PHOTOS = os.path.join(FOLDER, "photos")
FACES = os.path.join(FOLDER, "faces.npz")
PHOTO_URL = "https://life.disrupt.com/assets/profile_pic/GT-%s.jpg"
FIELDS = ["employee_id", "name", "designation", "department", "project"]
LEFT_OUT = ("gadit",)        # Shamroze: not the Gadits (by last name)


def left_out(name):
    return str(name).strip().lower().endswith(LEFT_OUT)


def make_roster(raw=RAW, out=ROSTER):
    """The directory as read ([[id, name, designation, department,
    project], ...]) to roster.csv, the Gadits left out. Returns rows."""
    with open(raw, encoding="utf-8") as fh:
        rows = json.load(fh)
    seen, kept = set(), []
    for r in rows:
        r = (list(r) + [""] * 5)[:5]
        eid, name = str(r[0]).strip(), str(r[1]).strip()
        if not eid or eid in seen or left_out(name):
            continue
        seen.add(eid)
        kept.append(dict(zip(FIELDS, [eid, name] + [str(x).strip()
                                                     for x in r[2:5]])))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(kept)
    return kept


def load_roster(path=ROSTER):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [r for r in csv.DictReader(fh) if not left_out(r["name"])]


def fetch_photos(roster=None, folder=PHOTOS, pause=0.15, opener=None):
    """Each employee's directory photo to people/photos/<id>.jpg, the ones
    not here yet. Returns (fetched, failed)."""
    roster = load_roster() if roster is None else roster
    os.makedirs(folder, exist_ok=True)
    get = opener or (lambda url: urllib.request.urlopen(
        urllib.request.Request(url, headers={"User-Agent": "EnergyCam"}),
        timeout=20).read())
    fetched, failed = 0, []
    for r in roster:
        path = os.path.join(folder, "%s.jpg" % r["employee_id"])
        if os.path.exists(path) and os.path.getsize(path) > 0:
            continue
        try:
            data = get(PHOTO_URL % r["employee_id"])
            if not data or data[:2] != b"\xff\xd8":
                raise ValueError("not a JPEG")
            with open(path, "wb") as fh:
                fh.write(data)
            fetched += 1
        except Exception as e:                              # noqa: BLE001
            failed.append((r["employee_id"], str(e)[:60]))
        time.sleep(pause)
    return fetched, failed


def enroll(roster=None, folder=PHOTOS, out=FACES):
    """Face numbers of every photo with one clear face. Returns (ids,
    no_face): no_face lists the employees whose photo gave none."""
    import cv2
    roster = load_roster() if roster is None else roster
    ids, vecs, no_face = [], [], []
    for r in roster:
        img = cv2.imread(os.path.join(folder, "%s.jpg" % r["employee_id"]))
        v = faces.of_photo(img) if img is not None else None
        if v is None:
            no_face.append(r["employee_id"])
            continue
        ids.append(r["employee_id"])
        vecs.append(v)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    np.savez(out, ids=np.array(ids), vecs=np.array(vecs, np.float32)
             .reshape(-1, 128))
    return ids, no_face


def load_faces(path=FACES):
    """(ids, vecs) of the enrolled photos, or empty ones."""
    if not os.path.exists(path):
        return np.array([]), np.zeros((0, 128), np.float32)
    d = np.load(path, allow_pickle=False)
    return d["ids"], d["vecs"]


def main(argv):
    what = argv[1] if len(argv) > 1 else ""
    if what == "roster":
        print("roster:", len(make_roster()), "people (Gadits left out)")
    elif what == "photos":
        got, failed = fetch_photos()
        print("photos fetched:", got, "failed:", len(failed))
        for eid, why in failed[:10]:
            print("  ", eid, why)
    elif what == "enroll":
        ids, no_face = enroll()
        print("faces enrolled:", len(ids), "photos with no clear face:",
              len(no_face))
    else:
        print(__doc__)


if __name__ == "__main__":
    main(sys.argv)
