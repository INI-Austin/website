"""Load the DSI Studio .trk and cache a compact, render-ready form.

The .trk is 149 MB of float32 in voxel space. Everything downstream only needs
world-space points plus per-point tangents, so this converts once and stores
float16 points with an offsets index. Re-rendering then costs a ~0.5 s load
instead of a ~60 s parse.
"""
import sys
import numpy as np
from nibabel.streamlines import load as load_tractogram

SRC = sys.argv[1] if len(sys.argv)>1 else "work/tracts.trk.gz"
OUT = sys.argv[2] if len(sys.argv)>2 else "work/tracts.npz"


def main() -> None:
    tf = load_tractogram(SRC)
    tractogram = tf.tractogram
    # .trk stores points in a voxel-corner space; to_rasmm carries the affine
    # that puts them back into the scanner RAS the affine header describes.
    streamlines = tractogram.streamlines
    n = len(streamlines)
    print(f"streamlines: {n}")
    print(f"affine:\n{tf.header['voxel_to_rasmm']}")

    lengths = np.asarray([len(s) for s in streamlines], dtype=np.int64)
    print(f"points: {lengths.sum():,}  per-streamline min/med/max: "
          f"{lengths.min()}/{int(np.median(lengths))}/{lengths.max()}")

    pts = np.concatenate([np.asarray(s, dtype=np.float32) for s in streamlines], axis=0)
    offsets = np.zeros(n + 1, dtype=np.int64)
    np.cumsum(lengths, out=offsets[1:])

    print(f"world bounds  x[{pts[:,0].min():.1f},{pts[:,0].max():.1f}] "
          f"y[{pts[:,1].min():.1f},{pts[:,1].max():.1f}] "
          f"z[{pts[:,2].min():.1f},{pts[:,2].max():.1f}]")

    centroid = pts.mean(axis=0)
    print(f"centroid: {centroid.round(2)}")

    np.savez_compressed(OUT, points=pts.astype(np.float16),
                        offsets=offsets, centroid=centroid.astype(np.float32))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    sys.exit(main())
