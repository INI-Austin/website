"""Isometric cortical-surface renderer for sub-test3.

Renders the fMRIPrep pial surfaces as a single lit solid. There is no GPU and
no scene graph here; the whole thing is a vectorised z-buffer:

  * each triangle is sampled barycentrically, with the sample count chosen from
    its projected screen area so small triangles are not oversampled and large
    ones are not left with holes;
  * every sample carries an interpolated normal and sulcal depth;
  * samples are sorted far-to-near and scattered into the frame buffer, so
    NumPy's "last write wins" rule for duplicate fancy indices *is* the depth
    test.

Shading is Blinn-Phong plus a Fresnel rim term, which is what gives the
surface its glass edge-light rather than a flat matte look. Sulcal depth drives
the base colour so the gyral/sulcal pattern reads as the brain's own folding.
"""
from __future__ import annotations

import argparse
import numpy as np
import nibabel as nib
from nibabel.gifti import GiftiImage
from PIL import Image, ImageFilter

ANAT = "$INI_BIDS_ROOT/derivatives/fmriprep/sub-test3/anat"


def view_matrix(azim_deg: float, elev_deg: float) -> np.ndarray:
    a, e = np.radians(azim_deg), np.radians(elev_deg)
    right = np.array([np.cos(a), np.sin(a), 0.0])
    fwd_h = np.array([-np.sin(a), np.cos(a), 0.0])
    up_w = np.array([0.0, 0.0, 1.0])
    fwd = fwd_h * np.cos(e) - up_w * np.sin(e)
    # right x fwd, not fwd x right: the latter points inferior and flips
    # the whole scene vertically.
    up = np.cross(right, fwd)
    return np.stack([right, up, fwd])


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


def load_surface(surf: str):
    vs, fs, ss = [], [], []
    base = 0
    for h in ("L", "R"):
        g = _gifti(f"{ANAT}/sub-test3_hemi-{h}_{surf}.surf.gii")
        v = np.asarray(g.darrays[0].data, dtype=np.float32)
        f = np.asarray(g.darrays[1].data, dtype=np.int64) + base
        s = np.asarray(
            _gifti(f"{ANAT}/sub-test3_hemi-{h}_sulc.shape.gii").darrays[0].data,
            dtype=np.float32)
        vs.append(v)
        fs.append(f)
        ss.append(s)
        base += len(v)
    return np.concatenate(vs), np.concatenate(fs), np.concatenate(ss)


def vertex_normals(v: np.ndarray, f: np.ndarray) -> np.ndarray:
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    n = np.zeros_like(v)
    for k in range(3):
        np.add.at(n, f[:, k], fn)
    ln = np.linalg.norm(n, axis=1, keepdims=True)
    return n / np.maximum(ln, 1e-9)


def render(a) -> None:
    v, f, sulc = load_surface(a.surface)
    print(f"verts {len(v):,} faces {len(f):,}", flush=True)
    vn = vertex_normals(v, f)

    centroid = v.mean(axis=0)
    R = view_matrix(a.azim, a.elev)
    vc = (v - centroid) @ R.T
    nc = vn @ R.T

    SS = a.supersample
    W, H = a.width * SS, a.height * SS
    lo, hi = vc.min(axis=0), vc.max(axis=0)
    span = max(hi[0] - lo[0], (hi[1] - lo[1]) * W / H)
    scale = (W * a.fill) / span
    px = (vc[:, 0] - 0.5 * (lo[0] + hi[0])) * scale + W / 2
    py = -(vc[:, 1] - 0.5 * (lo[1] + hi[1])) * scale + H / 2
    pz = vc[:, 2]

    # Sulcal depth normalised to 0..1; FreeSurfer's sulc is positive inside
    # sulci, so high values are the folds that should sit in shadow.
    s = (sulc - np.percentile(sulc, 2)) / (np.percentile(sulc, 98) - np.percentile(sulc, 2))
    s = np.clip(s, 0, 1)

    tri = f
    ax_, ay_ = px[tri[:, 0]], py[tri[:, 0]]
    bx_, by_ = px[tri[:, 1]], py[tri[:, 1]]
    cx_, cy_ = px[tri[:, 2]], py[tri[:, 2]]
    area = 0.5 * np.abs((bx_ - ax_) * (cy_ - ay_) - (cx_ - ax_) * (by_ - ay_))

    zbuf = np.full(W * H, np.inf, dtype=np.float32)
    cbuf = np.zeros((W * H, 3), dtype=np.float32)
    hit = np.zeros(W * H, dtype=bool)

    light = np.array(a.light, dtype=np.float32)
    light /= np.linalg.norm(light)
    base_lo = np.array(a.color_sulcus, dtype=np.float32) / 255.0
    base_hi = np.array(a.color_gyrus, dtype=np.float32) / 255.0
    rim_col = np.array(a.color_rim, dtype=np.float32) / 255.0

    rng = np.random.default_rng(7)
    buckets = [1, 4, 16, 64, 256, 1024]
    need = np.clip(np.ceil(area * a.sample_density), 1, buckets[-1])
    bidx = np.searchsorted(buckets, need)

    for bi, K in enumerate(buckets):
        sel = np.flatnonzero(bidx == bi)
        if sel.size == 0:
            continue
        for c0 in range(0, sel.size, max(1, a.budget // K)):
            idx = sel[c0:c0 + max(1, a.budget // K)]
            t = tri[idx]
            n_t = len(idx)
            u = rng.random((n_t, K), dtype=np.float32)
            w_ = rng.random((n_t, K), dtype=np.float32)
            flip = (u + w_) > 1.0
            u[flip] = 1.0 - u[flip]
            w_[flip] = 1.0 - w_[flip]
            g = 1.0 - u - w_

            i0, i1, i2 = t[:, 0][:, None], t[:, 1][:, None], t[:, 2][:, None]
            sx = (g * px[i0] + u * px[i1] + w_ * px[i2]).ravel()
            sy = (g * py[i0] + u * py[i1] + w_ * py[i2]).ravel()
            sz = (g * pz[i0] + u * pz[i1] + w_ * pz[i2]).ravel()
            ss_ = (g * s[i0] + u * s[i1] + w_ * s[i2]).ravel()
            nx = (g * nc[:, 0][i0] + u * nc[:, 0][i1] + w_ * nc[:, 0][i2]).ravel()
            ny = (g * nc[:, 1][i0] + u * nc[:, 1][i1] + w_ * nc[:, 1][i2]).ravel()
            nz = (g * nc[:, 2][i0] + u * nc[:, 2][i1] + w_ * nc[:, 2][i2]).ravel()

            # The camera looks along +z, so a front-facing sample has nz < 0.
            # Rendering the two halves separately is what lets the cortex be
            # used as a glass shell: the back half sits behind the tractography
            # and the front half is composited over it.
            onscreen = (sx >= 0) & (sx < W) & (sy >= 0) & (sy < H)
            if a.faces == "front":
                ok = onscreen & (nz < 0)
            elif a.faces == "back":
                ok = onscreen & (nz > 0)
            else:
                ok = onscreen
            sx, sy, sz, ss_, nx, ny, nz = (q[ok] for q in (sx, sy, sz, ss_, nx, ny, nz))
            if sx.size == 0:
                continue
            nl = np.sqrt(nx * nx + ny * ny + nz * nz)
            np.maximum(nl, 1e-9, out=nl)
            nx, ny, nz = nx / nl, ny / nl, nz / nl
            if a.faces == "back":
                # Flip so the inner surface is lit as though it faces the camera.
                nx, ny, nz = -nx, -ny, -nz

            # Camera looks along +z, so a front-facing normal has nz < 0.
            ndl = np.clip(-(nx * light[0] + ny * light[1] + nz * light[2]), 0, 1)
            ndv = np.clip(-nz, 0, 1)
            # Blinn-Phong halfway vector between light and view (view = -z).
            hx, hy, hz = light[0], light[1], light[2] - 1.0
            hl = np.sqrt(hx * hx + hy * hy + hz * hz)
            ndh = np.clip(-(nx * hx + ny * hy + nz * hz) / hl, 0, 1)
            spec = ndh ** a.shininess
            fres = (1.0 - ndv) ** a.rim_power

            base = base_lo[None, :] + (base_hi - base_lo)[None, :] * (1.0 - ss_)[:, None]
            shade = a.ambient + a.diffuse * ndl
            col = base * shade[:, None]
            col += a.specular * spec[:, None] * np.array([1, 1, 1], dtype=np.float32)
            col += a.rim * fres[:, None] * rim_col[None, :]

            # Far-to-near ordering turns NumPy's last-write-wins into a z-test
            # *within* this chunk. Comparing against the existing zbuf first
            # extends that across chunks: every surviving sample is nearer than
            # whatever is already in the buffer, and among those the last write
            # (the nearest) wins.
            o = np.argsort(-sz, kind="stable")
            sz, col = sz[o], col[o]
            flat = (sy[o].astype(np.int32) * W + sx[o].astype(np.int32))
            m = sz < zbuf[flat]
            fm = flat[m]
            zbuf[fm] = sz[m]
            cbuf[fm] = col[m]
            hit[fm] = True
        print(f"  bucket K={K}: {sel.size:,} tris", flush=True)

    rgb = np.clip(cbuf.reshape(H, W, 3) * a.exposure, 0, 1) ** (1.0 / a.gamma)
    alpha = hit.reshape(H, W).astype(np.float32) * a.opacity

    img = Image.fromarray((np.dstack([rgb, alpha]) * 255 + 0.5).astype(np.uint8), "RGBA")
    if SS > 1:
        img = img.resize((a.width, a.height), Image.Resampling.LANCZOS)
    if a.glow > 0:
        img = Image.blend(img, Image.alpha_composite(
            img.filter(ImageFilter.GaussianBlur(a.glow_radius)), img), a.glow)
    img.save(a.out)
    print(f"wrote {a.out}")
    if a.over:
        bg = Image.new("RGBA", img.size, a.over)
        Image.alpha_composite(bg, img).convert("RGB").save(
            a.out.replace(".png", "_on-navy.png"))
        print(f"wrote {a.out.replace('.png','_on-navy.png')}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--surface", default="pial", choices=["pial", "white", "midthickness", "inflated"])
    p.add_argument("--out", default="out/surface.png")
    p.add_argument("--width", type=int, default=1400)
    p.add_argument("--height", type=int, default=1100)
    p.add_argument("--supersample", type=int, default=2)
    p.add_argument("--azim", type=float, default=135.0)
    p.add_argument("--elev", type=float, default=25.0)
    p.add_argument("--fill", type=float, default=0.92)
    p.add_argument("--color-sulcus", type=int, nargs=3, default=[10, 30, 68])
    p.add_argument("--color-gyrus", type=int, nargs=3, default=[86, 150, 226])
    p.add_argument("--color-rim", type=int, nargs=3, default=[130, 226, 255])
    p.add_argument("--ambient", type=float, default=0.22)
    p.add_argument("--diffuse", type=float, default=0.85)
    p.add_argument("--specular", type=float, default=0.30)
    p.add_argument("--shininess", type=float, default=42.0)
    p.add_argument("--rim", type=float, default=0.45)
    p.add_argument("--rim-power", type=float, default=3.0)
    p.add_argument("--light", type=float, nargs=3, default=[-0.45, 0.60, -0.66])
    p.add_argument("--exposure", type=float, default=1.0)
    p.add_argument("--gamma", type=float, default=1.15)
    p.add_argument("--glow", type=float, default=0.0)
    p.add_argument("--glow-radius", type=float, default=10.0)
    p.add_argument("--faces", default="front", choices=["front", "back", "both"])
    p.add_argument("--opacity", type=float, default=1.0)
    p.add_argument("--sample-density", type=float, default=1.6)
    p.add_argument("--budget", type=int, default=6_000_000)
    p.add_argument("--over", default="#050E24")
    render(p.parse_args())


if __name__ == "__main__":
    main()
