"""Convert Aleph Neuro's published track binary into their viewer's own format.

Two ULMT layouts exist. The one their website serves is v6, delta encoded and
quantised so a whole reconstruction fits in about 700 KB. The one the viewer in
their MIT repo reads is v3, plain float32 per field. Both are theirs; they are
just different ends of the same pipeline, and nothing published converts one to
the other, so this does.

v3 layout, from the exporter's own docstring:

    header, 64 bytes   magic "ULMT", version 3, n_tracks, total_points,
                       max_speed f32, bounds_min 3xf32, bounds_max 3xf32
    track table        n_tracks x (uint32 offset, uint32 length)
    point data         total_points x (f32 x, y, z, frame, speed, intensity)

The header's max_speed is written as the divisor their own figure colours by,
`ulm_decode.RAMP_DIVISOR`, rather than as the largest speed in the file. Their
published viewer passes 0.18 explicitly and lets the fastest bubbles clamp to
the red end; using the maximum instead would leave the top third of the ramp
unused and push the median vessel down into the blue.

    python3 ulm_to_viewer.py work/ulm-tracks.bin.gz ../web/viewer/ulm/data/tracks.bin
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np

import ulm_decode

MAGIC = 0x554C4D54
VERSION = 3


def convert(src: str, dst: str) -> None:
    t = ulm_decode.load(src)
    n_points = len(t.xyz)

    # Points arrive grouped by track and in order, so the table is just the run
    # lengths. Rebuilding it this way avoids re-parsing the v6 header.
    lengths = np.bincount(t.track_id).astype(np.uint32)
    offsets = np.zeros_like(lengths)
    offsets[1:] = np.cumsum(lengths)[:-1]
    n_tracks = len(lengths)

    lo = t.xyz.min(axis=0).astype(np.float32)
    hi = t.xyz.max(axis=0).astype(np.float32)

    speed = t.speed
    intensity = t.intensity

    points = np.column_stack([
        t.xyz, t.time[:, None], speed[:, None], intensity[:, None]
    ]).astype(np.float32)

    header = struct.pack("<IIIIf3f3f", MAGIC, VERSION, n_tracks, n_points,
                         ulm_decode.RAMP_DIVISOR, *lo.tolist(), *hi.tolist())
    table = np.empty((n_tracks, 2), dtype="<u4")
    table[:, 0] = offsets
    table[:, 1] = lengths

    out = Path(dst)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("wb") as fp:
        fp.write(header + b"\x00" * (64 - len(header)))
        fp.write(table.tobytes())
        fp.write(points.tobytes())

    print(f"{n_tracks} tracks, {n_points} points -> {out} "
          f"({out.stat().st_size / 1e6:.2f} MB)")


if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2])
