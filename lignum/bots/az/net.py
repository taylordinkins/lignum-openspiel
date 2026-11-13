"""Numpy inference of the AZ policy-value net (weights exported by ``tools/az_train.py``).

Architecture (mirrored by the torch model in ``tools/az_train.py``): normalised input, a linear
stem, ``blocks`` pre-norm residual MLP blocks, a final LayerNorm, then a policy head (one logit per
decision id) and a value head (each seat's final dollars / ``VALUE_SCALE``, encoding seat first).
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

VALUE_SCALE = 100.0


def _ln(x: np.ndarray, g: np.ndarray, b: np.ndarray) -> np.ndarray:
    m = x.mean(-1, keepdims=True)
    v = x.var(-1, keepdims=True)
    return (x - m) / np.sqrt(v + 1e-5) * g + b


class NumpyNet:
    def __init__(self, path: str | Path) -> None:
        z = np.load(path)
        self.p = {k: z[k].astype(np.float32) for k in z.files}
        self.blocks = int(self.p["meta_blocks"][0])
        self.mean = self.p["norm_mean"]
        self.inv = self.p["norm_inv"]

    def forward(self, x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        """x: (B, D) raw features -> (policy logits (B, A), values (B, n) in dollars)."""
        p = self.p
        h = np.clip((x - self.mean) * self.inv, -5.0, 5.0)
        h = h @ p["stem.weight"].T + p["stem.bias"]
        for i in range(self.blocks):
            k = f"blocks.{i}."
            y = _ln(h, p[k + "ln1.weight"], p[k + "ln1.bias"])
            y = np.maximum(y @ p[k + "fc1.weight"].T + p[k + "fc1.bias"], 0)
            y = y @ p[k + "fc2.weight"].T + p[k + "fc2.bias"]
            h = h + y
        h = np.maximum(_ln(h, p["ln.weight"], p["ln.bias"]), 0)
        logits = h @ p["pi.weight"].T + p["pi.bias"]
        v = np.maximum(h @ p["v1.weight"].T + p["v1.bias"], 0)
        v = v @ p["v2.weight"].T + p["v2.bias"]
        return logits, v * VALUE_SCALE


def random_params(
    d_in: int,
    width: int = 64,
    blocks: int = 1,
    n_seats: int = 2,
    n_actions: int = 440,
    seed: int = 0,
) -> dict[str, np.ndarray]:
    """Random weights in the exported layout (tests and smoke runs)."""
    r = np.random.default_rng(seed)

    def lin(name: str, o: int, i: int) -> dict[str, np.ndarray]:
        return {
            f"{name}.weight": (r.standard_normal((o, i)) / np.sqrt(i)).astype(np.float32),
            f"{name}.bias": np.zeros(o, np.float32),
        }

    p: dict[str, np.ndarray] = {}
    p |= lin("stem", width, d_in)
    for b in range(blocks):
        p |= lin(f"blocks.{b}.fc1", width, width) | lin(f"blocks.{b}.fc2", width, width)
        p[f"blocks.{b}.ln1.weight"] = np.ones(width, np.float32)
        p[f"blocks.{b}.ln1.bias"] = np.zeros(width, np.float32)
    p["ln.weight"] = np.ones(width, np.float32)
    p["ln.bias"] = np.zeros(width, np.float32)
    p |= lin("pi", n_actions, width) | lin("v1", 256, width) | lin("v2", n_seats, 256)
    p["norm_mean"] = np.zeros(d_in, np.float32)
    p["norm_inv"] = np.ones(d_in, np.float32)
    p["meta_blocks"] = np.array([blocks])
    return p
