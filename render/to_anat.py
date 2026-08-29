"""Map a cached tractogram from qsiprep ACPC space into fMRIPrep anat space.

Direction and LPS convention were established empirically by align_check.py:
the 'from-ACPC_to-anat' Euler transform applied in its inverse sense, in LPS,
is what actually seats white matter inside the pial surface.
"""
import sys
import numpy as np
import scipy.io as sio

Q = "$INI_BIDS_ROOT/derivatives/qsiprep-ABCD/sub-test3/anat"
FLIP = np.diag([-1.0, -1.0, 1.0])


def transform():
    m = sio.loadmat(f"{Q}/sub-test3_from-ACPC_to-anat_mode-image_xfm.mat")
    ax, ay, az, tx, ty, tz = np.asarray(m["Euler3DTransform_double_3_3"]).ravel()
    c = np.asarray(m["fixed"]).ravel()[:3]
    cx, cy, cz = np.cos([ax, ay, az])
    sx, sy, sz = np.sin([ax, ay, az])
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Rx @ Ry, np.array([tx, ty, tz]), c


def acpc_to_anat(pts):
    R, t, c = transform()
    q = pts.astype(np.float64) @ FLIP
    q = (q - c - t) @ R + c
    return (q @ FLIP).astype(np.float32)


def main(src, dst):
    z = dict(np.load(src, allow_pickle=False))
    pts = acpc_to_anat(z["points"].astype(np.float32))
    z["points"] = pts.astype(np.float16)
    z["centroid"] = pts.mean(axis=0).astype(np.float32)
    np.savez_compressed(dst, **z)
    print(f"{src} -> {dst}")
    print(f"bounds x[{pts[:,0].min():.0f},{pts[:,0].max():.0f}] "
          f"y[{pts[:,1].min():.0f},{pts[:,1].max():.0f}] "
          f"z[{pts[:,2].min():.0f},{pts[:,2].max():.0f}]")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
