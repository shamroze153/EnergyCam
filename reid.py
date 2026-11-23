"""Whether two pictures of a person are the same person, across cameras.

Shamroze, 23 Nov: follow the Progress employees round every 140-H camera
-- the cafe, the smoking area, the meeting rooms. Shirt colour was not
enough (an employee matched strangers better than their own second
camera), so this uses a network trained for exactly this: OSNet-AIN
(reid_osnet.py, from torchreid, MIT) with its authors' weights trained on
MSMT17 -- 126,000 pictures of 4,101 people on 15 campus cameras, chosen
for how well it does on cameras it never saw (models/, git-ignored).

A person's box becomes 512 numbers; two people are as alike as the cosine
of their numbers. No face is looked at on its own and nothing is kept
but the numbers -- whole-body appearance (clothes, build, bag, hair) on
the day.

    import reid
    vecs = reid.embed(frame, [(x1, y1, x2, y2), ...])   # (n, 512), unit
    reid.similarity(vecs[0], vecs[1])                   # -1 .. 1
"""
import os

import numpy as np

WEIGHTS = os.path.join("models", "osnet_ain_x1_0_msmt17_combineall.pth")
SIZE = (128, 256)                       # width, height the network expects
MEAN = np.array([0.485, 0.456, 0.406], np.float32)
STD = np.array([0.229, 0.224, 0.225], np.float32)
MIN_H = 60                              # px: a smaller person is too few pixels

_model = {"net": None, "failed": False}


def available():
    """The weights are on this machine."""
    return os.path.exists(WEIGHTS)


def model():
    """The network, loaded once. Weights are read with weights_only=True:
    tensors only, nothing in the file can run."""
    if _model["net"] is not None or _model["failed"]:
        return _model["net"]
    try:
        import torch

        import reid_osnet
        net = reid_osnet.osnet_ain_x1_0(num_classes=1, pretrained=False)
        state = torch.load(WEIGHTS, map_location="cpu", weights_only=True)
        state = state.get("state_dict", state)
        state = {(k[7:] if k.startswith("module.") else k): v
                 for k, v in state.items() if "classifier" not in k}
        missing, unexpected = net.load_state_dict(state, strict=False)
        bad = [k for k in missing if not k.startswith("classifier")]
        if bad or unexpected:
            raise RuntimeError("weights do not fit: %s %s"
                               % (bad[:3], unexpected[:3]))
        net.eval()
        _model["net"] = net
    except Exception:                                       # noqa: BLE001
        _model["failed"] = True
    return _model["net"]


def _crop(frame, box):
    import cv2
    x1, y1, x2, y2 = (int(round(float(v))) for v in box[:4])
    h, w = frame.shape[:2]
    x1, y1, x2, y2 = max(0, x1), max(0, y1), min(w, x2), min(h, y2)
    if y2 - y1 < MIN_H or x2 - x1 < 16:
        return None
    patch = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2RGB)
    patch = cv2.resize(patch, SIZE, interpolation=cv2.INTER_LINEAR)
    patch = (patch.astype(np.float32) / 255.0 - MEAN) / STD
    return patch.transpose(2, 0, 1)


def embed(frame, boxes):
    """Each box as a unit vector of 512 (a row of zeros for a box too
    small to tell, or when the network cannot be loaded)."""
    out = np.zeros((len(boxes), 512), np.float32)
    net = model()
    if net is None or not len(boxes):
        return out
    import torch
    crops, idx = [], []
    for i, b in enumerate(boxes):
        c = _crop(frame, b)
        if c is not None:
            crops.append(c)
            idx.append(i)
    if not crops:
        return out
    with torch.no_grad():
        v = net(torch.from_numpy(np.stack(crops))).numpy()
    v /= np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-6)
    out[idx] = v
    return out


def similarity(a, b):
    """Cosine of two unit vectors; 0 when either is empty."""
    if not np.any(a) or not np.any(b):
        return 0.0
    return float(np.dot(a, b))
