"""Export a decimated tractogram as a compact binary for the WebGL hero.

Every streamline is resampled to the same number of points by arc length, which
means the client can build its index buffer arithmetically instead of shipping
per-line offsets. Positions are quantised to int16 over the bounding box; at
brain scale that is roughly 5 microns per step, far below anything visible.

Colour is not stored. The shader derives it from the segment tangent, which
costs nothing and halves the payload.
"""
from __future__ import annotations

import argparse
import struct
import numpy as np


def resample(pts: np.ndarray, n: int) -> np.ndarray:
    """Resample one polyline to n points evenly spaced along its arc length."""
    d = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(d)])
    if s[-1] <= 0:
        return np.repeat(pts[:1], n, axis=0)
    t = np.linspace(0.0, s[-1], n)
    out = np.empty((n, 3), dtype=np.float32)
    for k in range(3):
        out[:, k] = np.interp(t, s, pts[:, k])
    return out


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--tracts", default="work/tracts_v2.npz")
    p.add_argument("--out", default="../web/data/fibers.bin")
    p.add_argument("--lines", type=int, default=14000)
    p.add_argument("--points", type=int, default=22)
    p.add_argument("--min-len", type=float, default=32.0)
    p.add_argument("--seed", type=int, default=11)
    a = p.parse_args()

    z = np.load(a.tracts)
    pts = z["points"].astype(np.float32)
    offsets = z["offsets"]
    lens = np.diff(offsets)

    seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
    seg[offsets[1:-1] - 1] = 0.0
    cum = np.concatenate([[0.0], np.cumsum(seg)])
    arc = cum[offsets[1:] - 1] - cum[offsets[:-1]]

    ok = np.flatnonzero(arc >= a.min_len)
    print(f"{len(lens):,} streamlines, {len(ok):,} at >= {a.min_len:.0f} mm")
    rng = np.random.default_rng(a.seed)
    pick = rng.choice(ok, size=min(a.lines, len(ok)), replace=False)
    pick.sort()

    N = a.points
    out = np.empty((len(pick), N, 3), dtype=np.float32)
    for i, si in enumerate(pick):
        out[i] = resample(pts[offsets[si]:offsets[si + 1]], N)

    # Centre on the tract centroid so the shader can rotate about the brain's
    # own axis rather than a corner of the bounding box.
    c = out.reshape(-1, 3).mean(axis=0)
    out -= c
    lo = out.reshape(-1, 3).min(axis=0)
    hi = out.reshape(-1, 3).max(axis=0)
    span = float(np.max(hi - lo))
    q = np.clip(np.round(out / (span * 0.5) * 32000.0), -32767, 32767).astype("<i2")

    import pathlib
    path = pathlib.Path(a.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    # 16-byte header. The line count is uint32: uint16 caps at 65535, which a
    # dense export passes. Padding keeps the point data 2-byte aligned so the
    # client can wrap it in an Int16Array without copying.
    with open(path, "wb") as f:
        f.write(b"INIG")                                    # magic, v2 header
        f.write(struct.pack("<IHHf", len(pick), N, 0, span))
        f.write(q.tobytes())
    print(f"wrote {path}  {path.stat().st_size/1e6:.2f} MB  "
          f"{len(pick):,} lines x {N} pts, span {span:.0f} mm")


if __name__ == "__main__":
    main()
