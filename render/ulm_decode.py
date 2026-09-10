"""Decode Aleph Neuro's ULM track binary (ULMT v6) into plain arrays.

Format read off their published viewer. Tracks are delta encoded: the first
point of a track carries absolute quantised coordinates, every point after it
carries an int16 step, so the whole vascular reconstruction fits in about a
megabyte. Fields per point are position in mm, frame time, flow speed and an
intensity.

The two scalar fields are easy to swap and I had them the wrong way round.
Their own loader takes the byte plane at offset 7n, scales it by the float at
header offset 16, and feeds that to the shader as speed; the plane at 8n, scaled
by the (lo, hi) pair at offset 44, is what it feeds in as intensity. The
telltale is the range: the first spans 0 to 0.404 and their figure divides it by
0.18 to colour the ramp, while the second is exactly 0 to 1, which is a
normalised weight rather than a measurement.
"""
from __future__ import annotations

import gzip
import struct
from dataclasses import dataclass

import numpy as np

MAGIC = 0x554C4D54  # "ULMT"


@dataclass(frozen=True)
class Tracks:
    xyz: np.ndarray      # (n, 3) float32, mm
    time: np.ndarray     # (n,)   float32, frame index
    speed: np.ndarray    # (n,)   float32, flow speed in the file's own units
    intensity: np.ndarray  # (n,) float32, 0 to 1 (empty if absent)
    track_id: np.ndarray  # (n,)  int32
    bbox: tuple


def load(path: str) -> Tracks:
    raw = open(path, "rb").read()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)

    magic, version, n_tracks, n_points = struct.unpack_from("<4I", raw, 0)
    if magic != MAGIC:
        raise ValueError(f"bad magic 0x{magic:08x}")
    if version != 6:
        raise ValueError(f"unsupported version {version}")

    speed_scale = struct.unpack_from("<f", raw, 16)[0]
    lo = np.array(struct.unpack_from("<3f", raw, 20), dtype=np.float64)
    hi = np.array(struct.unpack_from("<3f", raw, 32), dtype=np.float64)
    speed_lo, speed_hi = struct.unpack_from("<2f", raw, 44)
    steps = struct.unpack_from("<I", raw, 52)[0]
    has_speed = struct.unpack_from("<I", raw, 56)[0] & 1

    step = (hi - lo) / (steps - 1)
    v = speed_scale / 255.0
    m = (speed_hi - speed_lo) / 255.0

    table = np.frombuffer(raw, dtype="<u4", count=n_tracks * 4, offset=64)
    table = table.reshape(n_tracks, 4)
    p_off, t0 = table[:, 0], table[:, 2].astype(np.float64)

    a = 64 + 16 * n_tracks
    dx = np.frombuffer(raw, "<i2", n_points, a).astype(np.int64)
    dy = np.frombuffer(raw, "<i2", n_points, a + 2 * n_points).astype(np.int64)
    dz = np.frombuffer(raw, "<i2", n_points, a + 4 * n_points).astype(np.int64)
    dt = np.frombuffer(raw, "u1", n_points, a + 6 * n_points).astype(np.float64)
    sp = np.frombuffer(raw, "u1", n_points, a + 7 * n_points).astype(np.float64)
    ci = (np.frombuffer(raw, "u1", n_points, a + 8 * n_points).astype(np.float64)
          if has_speed else None)

    # Each track restarts the cumulative sum, so mark the first point of every
    # track and undo the running total at those boundaries rather than looping.
    starts = np.zeros(n_points, dtype=bool)
    starts[p_off] = True
    tid = np.cumsum(starts) - 1

    qx, qy, qz, qt = dx.copy(), dy.copy(), dz.copy(), dt.copy()
    qx[starts] += 32768
    qy[starts] += 32768
    qz[starts] += 32768
    qt[starts] = t0

    def running(vals):
        c = np.cumsum(vals)
        base = np.zeros(n_points)
        base[p_off] = c[p_off] - vals[p_off]
        return c - np.maximum.accumulate(np.where(starts, base, -np.inf))

    ix, iy, iz, it = (running(q) for q in (qx, qy, qz, qt))

    xyz = np.empty((n_points, 3), dtype=np.float32)
    xyz[:, 0] = lo[0] + ix * step[0]
    xyz[:, 1] = lo[1] + iy * step[1]
    xyz[:, 2] = lo[2] + iz * step[2]

    return Tracks(
        xyz=xyz,
        time=it.astype(np.float32),
        speed=(sp * v).astype(np.float32),
        intensity=((speed_lo + ci * m).astype(np.float32) if has_speed
                   else np.empty(0, np.float32)),
        track_id=tid.astype(np.int32),
        bbox=(tuple(lo), tuple(hi)),
    )


# What the top of the colour ramp is divided by, in the file's own speed units,
# and what their figure labels that top of the ramp in mm/s. Both are theirs:
# the divisor is the one their published viewer passes, and 38 is the number
# printed beside their bar. Speeds above the divisor clamp to the red end.
RAMP_DIVISOR = 0.18
RAMP_TOP_MM_S = 38.34


if __name__ == "__main__":
    import sys
    t = load(sys.argv[1])
    print("points   ", len(t.xyz))
    print("tracks   ", int(t.track_id.max()) + 1)
    print("bbox mm  ", np.round(t.bbox[0], 2), np.round(t.bbox[1], 2))
    print("extent   ", np.round(t.xyz.min(0), 2), np.round(t.xyz.max(0), 2))
    print("speed    ", round(float(t.speed.min()), 3), "to",
          round(float(t.speed.max()), 3), "(ramp divides by", RAMP_DIVISOR, ")")
    print("intensity", round(float(t.intensity.min()), 3), "to",
          round(float(t.intensity.max()), 3))
