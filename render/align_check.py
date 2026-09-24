"""Determine empirically how the ACPC tracts map onto the fMRIPrep surfaces.

The BIDS `from-X_to-Y` naming and ITK's LPS convention together leave four
plausible ways to apply the stored Euler transform. Rather than reason about
which is right, apply all of them and keep whichever actually puts white-matter
streamlines *inside* the pial surface, measured with a nearest-vertex normal
test.
"""
import numpy as np
import nibabel as nib
from nibabel.gifti import GiftiImage
import scipy.io as sio
from scipy.spatial import KDTree

from dataset import derivatives, subject

Q = derivatives("qsiprep-ABCD")
ANAT = derivatives("fmriprep")
SUB = subject()
FLIP = np.diag([-1.0, -1.0, 1.0])          # RAS <-> LPS


def euler_itk(p):
    ax, ay, az, tx, ty, tz = p
    cx, cy, cz = np.cos([ax, ay, az])
    sx, sy, sz = np.sin([ax, ay, az])
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Rx @ Ry, np.array([tx, ty, tz])   # ITK default ComputeZYX=false


def apply(pts, params, center, lps=True, inverse=False):
    R, t = euler_itk(params)
    c = np.asarray(center[:3])
    q = pts @ FLIP if lps else pts.copy()
    if inverse:
        q = (q - c - t) @ R + c            # R^-1 = R.T -> (x) @ R
    else:
        q = (q - c) @ R.T + c + t
    return q @ FLIP if lps else q


def _gifti(path: str) -> GiftiImage:
    """Load a GIFTI file, checking that it really is one.

    nibabel.load is typed as returning the FileBasedImage base class, which has
    no darrays, so narrow it here rather than failing with an AttributeError
    several lines later.
    """
    img = nib.load(path)
    if not isinstance(img, GiftiImage):
        raise TypeError(f"expected a GIFTI image at {path}, got {type(img).__name__}")
    return img


def load_surface():
    V, N = [], []
    for h in ("L", "R"):
        g = _gifti(f"{ANAT}/{SUB}_hemi-{h}_pial.surf.gii")
        v = np.asarray(g.darrays[0].data, np.float64)
        f = np.asarray(g.darrays[1].data, np.int64)
        fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
        n = np.zeros_like(v)
        for k in range(3):
            np.add.at(n, f[:, k], fn)
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
        V.append(v)
        N.append(n)
    return np.concatenate(V), np.concatenate(N)


def inside_fraction(pts, V, N, tree):
    d, i = tree.query(pts, workers=-1)
    return float((np.einsum("ij,ij->i", pts - V[i], N[i]) < 0).mean()), float(np.median(d))


def main():
    z = np.load("work/bundles.npz")
    pts = z["points"].astype(np.float64)
    pts = pts[:: max(1, len(pts) // 60000)]

    V, N = load_surface()
    tree = KDTree(V)

    m1 = sio.loadmat(f"{Q}/{SUB}_from-ACPC_to-anat_mode-image_xfm.mat")
    m2 = sio.loadmat(f"{Q}/{SUB}_from-anat_to-ACPC_mode-image_xfm.mat")
    p1 = np.asarray(m1["Euler3DTransform_double_3_3"]).ravel()
    c1 = np.asarray(m1["fixed"]).ravel()
    p2 = np.asarray(m2["Euler3DTransform_double_3_3"]).ravel()
    c2 = np.asarray(m2["fixed"]).ravel()

    trials = {
        "identity": pts,
        "A2a fwd LPS": apply(pts, p1, c1, True, False),
        "A2a fwd RAS": apply(pts, p1, c1, False, False),
        "A2a inv LPS": apply(pts, p1, c1, True, True),
        "A2a inv RAS": apply(pts, p1, c1, False, True),
        "a2A fwd LPS": apply(pts, p2, c2, True, False),
        "a2A fwd RAS": apply(pts, p2, c2, False, False),
        "a2A inv LPS": apply(pts, p2, c2, True, True),
        "a2A inv RAS": apply(pts, p2, c2, False, True),
    }
    print(f"{'variant':14s} {'inside%':>8s} {'medDist':>9s}")
    scored = []
    for k, q in trials.items():
        fr, md = inside_fraction(q, V, N, tree)
        print(f"{k:14s} {fr*100:7.1f}% {md:8.1f}mm")
        scored.append((k, fr))
    best_key, best_fr = max(scored, key=lambda kv: kv[1])
    print(f"\nbest: {best_key} ({best_fr*100:.1f}% inside)")


if __name__ == "__main__":
    main()
