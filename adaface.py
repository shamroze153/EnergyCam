"""AdaFace IR-101 (WebFace12M) -- a stronger face recogniser for our CCTV.

27 Nov 2026, Shamroze: "face recognition bahut kamzor hai, GitHub se koi
model dhoondo, check karo, implement karo". AdaFace (Kim et al., CVPR 2022,
github.com/mk-minchul/AdaFace, MIT code) is trained to stay right on
low-quality faces -- surveillance and drone footage (IJB-S, TinyFace).

The network below is the official IR-101 (CVLFace's models/iresnet/
model.py, read before use: plain PyTorch, no file or network access),
without its unused fvcore import. The weights are read from
models/adaface/model.safetensors (huggingface.co/minchul/
cvlface_adaface_ir101_webface12m, 261 MB, git-ignored) by a small reader
of the safetensors format (an 8-byte header length, a JSON header, raw
little-endian numbers) -- no pickle, nothing executed from the file.
The weights' training data carries its own licence (the model card:
"follow the license of the training dataset").

    vec = AdaFace().embed(aligned_112_bgr)   -> 512 numbers, unit length

Input: a face aligned to the 112x112 ArcFace template (OpenCV's SFace
alignCrop gives exactly that, from YuNet's five points), RGB, scaled to
[-1, 1].
"""
import json
import os
import struct
from collections import namedtuple

import numpy as np

WEIGHTS = os.path.join("models", "adaface", "model.safetensors")


def read_safetensors(path):
    """{name: numpy array} from a .safetensors file (F32/F16/BF16/I64)."""
    with open(path, "rb") as fh:
        n = struct.unpack("<Q", fh.read(8))[0]
        header = json.loads(fh.read(n).decode("utf-8"))
        base = 8 + n
        out = {}
        for name, info in header.items():
            if name == "__metadata__":
                continue
            a, b = info["data_offsets"]
            fh.seek(base + a)
            raw = fh.read(b - a)
            dt = info["dtype"]
            if dt == "F32":
                arr = np.frombuffer(raw, "<f4")
            elif dt == "F16":
                arr = np.frombuffer(raw, "<f2").astype(np.float32)
            elif dt == "BF16":
                arr = (np.frombuffer(raw, "<u2").astype(np.uint32) << 16
                       ).view(np.float32)
            elif dt == "I64":
                arr = np.frombuffer(raw, "<i8")
            else:
                raise ValueError("dtype %s" % dt)
            out[name] = arr.reshape(info["shape"]).copy()
    return out


def _build():
    import torch.nn as nn
    from torch.nn import (BatchNorm1d, BatchNorm2d, Conv2d, Dropout, Linear,
                          MaxPool2d, Module, PReLU, Sequential)

    class Flatten(Module):
        def forward(self, x):
            return x.view(x.size(0), -1)

    class BasicBlockIR(Module):
        def __init__(self, in_channel, depth, stride):
            super().__init__()
            if in_channel == depth:
                self.shortcut_layer = MaxPool2d(1, stride)
            else:
                self.shortcut_layer = Sequential(
                    Conv2d(in_channel, depth, (1, 1), stride, bias=False),
                    BatchNorm2d(depth))
            self.res_layer = Sequential(
                BatchNorm2d(in_channel),
                Conv2d(in_channel, depth, (3, 3), (1, 1), 1, bias=False),
                BatchNorm2d(depth), PReLU(depth),
                Conv2d(depth, depth, (3, 3), stride, 1, bias=False),
                BatchNorm2d(depth))

        def forward(self, x):
            return self.res_layer(x) + self.shortcut_layer(x)

    Block = namedtuple("Block", ["in_channel", "depth", "stride"])

    def get_block(in_channel, depth, num_units, stride=2):
        return [Block(in_channel, depth, stride)] + \
            [Block(depth, depth, 1) for _ in range(num_units - 1)]

    class Backbone(Module):
        def __init__(self):
            super().__init__()
            self.input_layer = Sequential(Conv2d(3, 64, (3, 3), 1, 1,
                                                 bias=False),
                                          BatchNorm2d(64), PReLU(64))
            blocks = [get_block(64, 64, 3), get_block(64, 128, 13),
                      get_block(128, 256, 30), get_block(256, 512, 3)]
            self.output_layer = Sequential(BatchNorm2d(512), Dropout(0.4),
                                           Flatten(),
                                           Linear(512 * 7 * 7, 512),
                                           BatchNorm1d(512, affine=False))
            self.body = Sequential(*[BasicBlockIR(b.in_channel, b.depth,
                                                  b.stride)
                                     for blk in blocks for b in blk])

        def forward(self, x):
            x = self.input_layer(x)
            x = self.body(x)
            return self.output_layer(x)

    return Backbone()


OV_MODEL = os.path.join("models", "adaface", "adaface_ir101.xml")


class AdaFace:
    """embed(aligned 112x112 BGR uint8) -> 512 unit numbers, or None.

    Runs on Intel's OpenVINO (CPU) where it is installed -- 27 Nov on this
    laptop's i5-1235U: 0.6 s a face against PyTorch's 1.7, the same
    numbers to 4 places (its GPU path gave wrong ones: never used) -- and
    on PyTorch otherwise."""

    def __init__(self, weights=WEIGHTS, threads=None, openvino=True):
        import torch
        if threads:
            torch.set_num_threads(threads)
        self.torch = torch
        self.ov = None
        self.net = _build()
        state = read_safetensors(weights)
        own = self.net.state_dict()
        # the file's names carry the wrapper's prefix ("net." / "model.")
        mapped = {}
        for k, v in state.items():
            for pre in ("", "net.", "model.", "model.net."):
                if k.startswith(pre) and k[len(pre):] in own:
                    mapped[k[len(pre):]] = torch.from_numpy(v)
                    break
        missing = [k for k in own if k not in mapped
                   and not k.endswith("num_batches_tracked")]
        if missing:
            raise ValueError("weights do not fit the network: %d missing, "
                             "e.g. %s" % (len(missing), missing[:3]))
        self.net.load_state_dict(mapped, strict=False)
        self.net.eval()
        if openvino:
            self.ov = self._openvino()

    def _openvino(self):
        """The network compiled by OpenVINO for the CPU (converted once to
        OV_MODEL), or None where OpenVINO is not installed."""
        try:
            import openvino as ov
        except ImportError:
            return None
        try:
            core = ov.Core()
            if os.path.exists(OV_MODEL):
                model = core.read_model(OV_MODEL)
            else:
                model = ov.convert_model(
                    self.net, example_input=self.torch.randn(1, 3, 112, 112))
                model.reshape([-1, 3, 112, 112])
                ov.save_model(model, OV_MODEL, compress_to_fp16=False)
            return core.compile_model(model, "CPU",
                                      {"PERFORMANCE_HINT": "THROUGHPUT"})
        except Exception:                                   # noqa: BLE001
            return None

    def embed_many(self, faces_bgr, unit=True):
        """[aligned 112x112 BGR] -> (n, 512) rows, of unit length -- or,
        with unit=False, as the network gives them: their length is
        AdaFace's own measure of the face's quality (short for a blurred,
        dark or turned face; the paper's "feature norm"), for weighting
        many faces of one seat."""
        torch = self.torch
        if not len(faces_bgr):
            return np.zeros((0, 512), np.float32)
        x = np.stack([f[:, :, ::-1] for f in faces_bgr]).astype(np.float32)
        x = (x / 255.0 - 0.5) / 0.5
        x = np.ascontiguousarray(x.transpose(0, 3, 1, 2))
        if self.ov is not None:
            v = np.asarray(self.ov(x)[0])
        else:
            with torch.no_grad():
                v = self.net(torch.from_numpy(x)).numpy()
        if not unit:
            return v.astype(np.float32)
        return v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)

    def embed(self, face_bgr, unit=True):
        if face_bgr is None:
            return None
        return self.embed_many([face_bgr], unit=unit)[0]
