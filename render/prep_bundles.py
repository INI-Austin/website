"""Concatenate the curated .trk bundles into one render-ready cache.

Stores points, per-streamline offsets and a per-streamline bundle id, so the
renderer can colour by anatomy instead of by direction.
"""
import numpy as np
from nibabel.streamlines import load as load_trk
from bundles import CURATED

OUT = "work/bundles.npz"
pts_all, off_all, bid_all = [], [0], []
base = 0
kept = []

for bi, (stem, col, label) in enumerate(CURATED):
    path = f"work/trk/{stem}.trk.gz"
    try:
        sl = load_trk(path).streamlines
    except Exception as e:                      # bundle absent for this subject
        print(f"skip {stem}: {e}")
        continue
    n = len(sl)
    if n == 0:
        print(f"skip {stem}: empty")
        continue
    lens = np.asarray([len(s) for s in sl])
    pts_all.append(np.concatenate([np.asarray(s, dtype=np.float32) for s in sl]))
    off_all.extend((base + np.cumsum(lens)).tolist())
    base += int(lens.sum())
    bid_all.append(np.full(n, len(kept), dtype=np.int16))
    kept.append((stem, col, label))
    print(f"{stem:52s} {n:6d} streamlines  {lens.sum():9,} pts")

pts = np.concatenate(pts_all)
offsets = np.asarray(off_all, dtype=np.int64)
bid = np.concatenate(bid_all)
centroid = pts.mean(axis=0)
np.savez_compressed(OUT, points=pts.astype(np.float16), offsets=offsets,
                    bundle_id=bid, centroid=centroid.astype(np.float32),
                    names=np.array([k[0] for k in kept]),
                    colors=np.array([k[1] for k in kept]),
                    labels=np.array([k[2] for k in kept]))
print(f"\ntotal {len(offsets)-1:,} streamlines, {len(pts):,} points, {len(kept)} bundles")
print(f"bounds x[{pts[:,0].min():.0f},{pts[:,0].max():.0f}] "
      f"y[{pts[:,1].min():.0f},{pts[:,1].max():.0f}] z[{pts[:,2].min():.0f},{pts[:,2].max():.0f}]")
print(f"wrote {OUT}")
