"""InsightFace's SCRFD face detector and ArcFace recognisers, run by Intel's
OpenVINO straight from the official ONNX files -- no insightface or
onnxruntime package, and nothing executed from the files (an ONNX file is
a graph of numbers).

27 Nov 2026, Shamroze: "sab tools check karo, jo hamare case mein sabse
mazboot ho use download karke implement karo". Our desk cameras look down
from the ceiling: YuNet (faces.py) finds a face in only some of the passes.
SCRFD-10G (Guo et al., ICLR 2022) is a stronger detector on small and hard
faces (WIDER FACE hard ~83% against YuNet's ~77%), and gives the same five
points for the 112x112 alignment AdaFace and ArcFace need.

Files (models/insightface/, git-ignored), from github.com/deepinsight/
insightface release v0.7 (buffalo_l.zip, antelopev2.zip): det_10g.onnx
(SCRFD-10G with five points), w600k_r50.onnx (ArcFace R50, WebFace600K),
glintr100.onnx (ArcFace R100, Glint360K). InsightFace's pretrained models
are released for non-commercial research use: their licence to be checked
before any use beyond this study.

    det = SCRFD()
    for x1, y1, x2, y2, score, kps in det.detect(img_bgr): ...
    face = norm_crop(img_bgr, kps)                 # 112x112, ArcFace template
    vecs = ArcFace("glintr100.onnx").embed_many([face])   # (n, 512) unit
"""
import os

import numpy as np

FOLDER = os.path.join("models", "insightface")
DETECTOR = os.path.join(FOLDER, "det_10g.onnx")

# the five points' places in the 112x112 face (ArcFace's template, as
# insightface.utils.face_align and OpenCV's SFace alignCrop use)
ARCFACE_DST = np.array([[38.2946, 51.6963], [73.5318, 51.5014],
                        [56.0252, 71.7366], [41.5493, 92.3655],
                        [70.7299, 92.2041]], np.float32)

_core = {"core": None}


def _ov():
    if _core["core"] is None:
        import openvino as ov
        _core["core"] = ov.Core()
    return _core["core"]


def umeyama(src, dst):
    """The similarity transform (rotation, one scale, shift) taking the
    points src onto dst by least squares -- scikit-image's _umeyama, which
    insightface's norm_crop uses. A 2x3 matrix."""
    src = np.asarray(src, np.float64)
    dst = np.asarray(dst, np.float64)
    n, dim = src.shape
    sm, dm = src.mean(0), dst.mean(0)
    sd, dd = src - sm, dst - dm
    A = dd.T @ sd / n
    d = np.ones(dim)
    if np.linalg.det(A) < 0:
        d[dim - 1] = -1
    T = np.eye(dim + 1)
    U, S, V = np.linalg.svd(A)
    rank = np.linalg.matrix_rank(A)
    if rank == 0:
        return None
    if rank == dim - 1:
        if np.linalg.det(U) * np.linalg.det(V) > 0:
            T[:dim, :dim] = U @ V
        else:
            s = d[dim - 1]
            d[dim - 1] = -1
            T[:dim, :dim] = U @ np.diag(d) @ V
            d[dim - 1] = s
    else:
        T[:dim, :dim] = U @ np.diag(d) @ V
    scale = 1.0 / sd.var(0).sum() * (S @ d)
    T[:dim, dim] = dm - scale * (T[:dim, :dim] @ sm)
    T[:dim, :dim] *= scale
    return T[:2]


def norm_crop(img, kps, size=112):
    """The face on the five points (SCRFD's order: the eye on the picture's
    left, the other eye, nose, mouth left, mouth right), turned and scaled
    onto ArcFace's template: size x size BGR."""
    import cv2
    M = umeyama(np.asarray(kps, np.float32).reshape(5, 2),
                ARCFACE_DST * (size / 112.0))
    if M is None:
        return None
    return cv2.warpAffine(img, M, (size, size), borderValue=0.0)


def _nms(dets, thresh):
    x1, y1, x2, y2, s = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], \
        dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = s.argsort()[::-1]
    keep = []
    while order.size > 0:
        i = order[0]
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[np.where(ovr <= thresh)[0] + 1]
    return keep


class SCRFD:
    """SCRFD-10G with five points: detect(img) -> [(x1, y1, x2, y2, score,
    kps (5, 2))], best first. The picture is fitted into `size` (a multiple
    of 32) the way insightface does it: scaled, padded at the right and
    bottom."""

    def __init__(self, path=DETECTOR, size=640, thresh=0.5, nms=0.4,
                 threads=None):
        self.path, self.size = path, int(size)
        self.thresh, self.nms_thresh = thresh, nms
        self.threads = threads          # OpenVINO's own (the loop: two)
        self.model = _ov().read_model(path)
        self.compiled = {}
        self.centers = {}

    def _net(self, size):
        if size not in self.compiled:
            m = self.model.clone() if hasattr(self.model, "clone") \
                else _ov().read_model(self.path)
            m.reshape([1, 3, size, size])
            cfg = {"PERFORMANCE_HINT": "LATENCY"}
            if self.threads:
                cfg["INFERENCE_NUM_THREADS"] = int(self.threads)
            self.compiled[size] = _ov().compile_model(m, "CPU", cfg)
        return self.compiled[size]

    def detect(self, img, size=None, thresh=None):
        import cv2
        if img is None or img.size == 0:
            return []
        size = int(size or self.size)
        thresh = self.thresh if thresh is None else thresh
        h, w = img.shape[:2]
        if h / float(w) > 1.0:
            nh, nw = size, max(1, int(size * w / float(h)))
        else:
            nw, nh = size, max(1, int(size * h / float(w)))
        scale = nh / float(h)
        canvas = np.zeros((size, size, 3), np.uint8)
        canvas[:nh, :nw] = cv2.resize(img, (nw, nh))
        blob = cv2.dnn.blobFromImage(canvas, 1.0 / 128, (size, size),
                                     (127.5, 127.5, 127.5), swapRB=True)
        net = self._net(size)
        res = net(blob)
        outs = [np.asarray(res[o]) for o in net.outputs]
        outs = [o[0] if o.ndim == 3 else o for o in outs]
        if len(outs) != 9:
            raise ValueError("expected SCRFD with five points (9 outputs)")
        # scores (.., 1), boxes (.., 4), points (.., 10); each kind from
        # the finest stride (most rows) to the coarsest -- by shape, not by
        # trusting the outputs' order
        outs = [o for last in (1, 4, 10) for o in sorted(
            [o for o in outs if o.shape[-1] == last], key=lambda o: -len(o))]
        boxes, scores, points = [], [], []
        for i, stride in enumerate((8, 16, 32)):
            sc = outs[i].reshape(-1)
            bb = outs[i + 3] * stride
            kp = outs[i + 6] * stride
            fh, fw = size // stride, size // stride
            key = (fh, fw, stride)
            if key not in self.centers:
                c = np.stack(np.mgrid[:fh, :fw][::-1], axis=-1).astype(
                    np.float32)
                c = (c * stride).reshape(-1, 2)
                c = np.stack([c] * 2, axis=1).reshape(-1, 2)   # two anchors
                self.centers[key] = c
            c = self.centers[key]
            pos = np.where(sc >= thresh)[0]
            if not len(pos):
                continue
            cp, b, k = c[pos], bb[pos], kp[pos]
            boxes.append(np.stack([cp[:, 0] - b[:, 0], cp[:, 1] - b[:, 1],
                                   cp[:, 0] + b[:, 2], cp[:, 1] + b[:, 3]],
                                  axis=-1))
            pts = np.stack([cp[:, j % 2] + k[:, j] for j in range(10)],
                           axis=-1).reshape(-1, 5, 2)
            points.append(pts)
            scores.append(sc[pos])
        if not boxes:
            return []
        boxes = np.vstack(boxes) / scale
        points = np.vstack(points) / scale
        scores = np.concatenate(scores)
        dets = np.hstack([boxes, scores[:, None]]).astype(np.float32)
        keep = _nms(dets, self.nms_thresh)
        return [(float(dets[i, 0]), float(dets[i, 1]), float(dets[i, 2]),
                 float(dets[i, 3]), float(dets[i, 4]), points[i])
                for i in keep]


def sitter_face(found, crop_shape, min_w=20):
    """Of SCRFD's faces in a person's head crop (faces.head_crop: the top
    of their box, a little wider), the one that is theirs: the face whose
    middle is nearest the crop's middle across -- a neighbour's face sits
    off to a side (27 Nov: on the desk pictures the largest face was at
    times the next desk's sitter). None when no face is min_w px wide."""
    w = float(crop_shape[1])
    got = [f for f in found if f[2] - f[0] >= min_w]
    if not got:
        return None
    return min(got, key=lambda f: (abs((f[0] + f[2]) / 2.0 - w / 2.0) / w,
                                   -f[4]))


class ArcFace:
    """An InsightFace ArcFace recogniser (w600k_r50.onnx, glintr100.onnx):
    embed_many([112x112 BGR]) -> (n, 512) unit rows. Its own scaling read
    from the graph: a model that starts by subtracting and multiplying
    (an MXNet conversion) takes the pixels as they are; else (x-127.5)/127.5."""

    def __init__(self, name="glintr100.onnx", folder=FOLDER):
        import openvino as ov  # noqa: F401
        model = _ov().read_model(os.path.join(folder, name))
        first = [op.get_type_name() for op in model.get_ordered_ops()[:8]]
        raw = "Subtract" in first and "Multiply" in first
        self.mean, self.std = (0.0, 1.0) if raw else (127.5, 127.5)
        self.batch = True
        try:
            model.reshape([-1, 3, 112, 112])
        except Exception:                                   # noqa: BLE001
            self.batch = False               # a graph fixed at one face
        self.net = _ov().compile_model(model, "CPU",
                                       {"PERFORMANCE_HINT": "THROUGHPUT"})

    def embed_many(self, faces_bgr, unit=True):
        import cv2
        if not len(faces_bgr):
            return np.zeros((0, 512), np.float32)
        blob = cv2.dnn.blobFromImages(list(faces_bgr), 1.0 / self.std,
                                      (112, 112),
                                      (self.mean, self.mean, self.mean),
                                      swapRB=True)
        out = self.net.outputs[0]
        if self.batch:
            v = np.asarray(self.net(blob)[out], np.float32)
        else:
            v = np.vstack([np.asarray(self.net(blob[i:i + 1])[out],
                                      np.float32) for i in range(len(blob))])
        if not unit:
            return v
        return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)
