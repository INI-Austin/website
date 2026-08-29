"""Isometric tractography renderer for the INI Austin hero image.

Orthographic (a true isometric projection is orthographic), direction-encoded
colour remapped onto a navy/cyan/ice palette, additive accumulation with a
filmic tone map, and depth fog. Outputs a straight-alpha RGBA PNG so the result
can composite over the site's animated cortex background.

Rasterisation is done by splatting: every streamline segment is subdivided into
a fixed number of samples, each weighted by segment length / K so that sample
density never biases brightness, then bilinearly accumulated with np.bincount
(far faster than np.add.at for this many scattered writes).
"""
from __future__ import annotations

import argparse
import numpy as np
from PIL import Image

# Direction-encoded colour, remapped from the usual RGB into a cool palette.
# The axis each colour is tied to is what makes the anatomy readable:
#   x  left-right     -> corpus callosum fans
#   y  anterior-post.  -> longitudinal bundles (SLF, IFOF, cingulum)
#   z  superior-inf.   -> corticospinal tract / corona radiata
PALETTE = {
    "ice":  np.array([[0.43, 0.90, 1.00],    # x  cyan
                      [0.23, 0.51, 0.96],    # y  azure
                      [0.91, 0.96, 1.00]]),  # z  near-white
    "dec":  np.array([[1.00, 0.20, 0.20],
                      [0.20, 1.00, 0.30],
                      [0.25, 0.45, 1.00]]),
    "gold": np.array([[1.00, 0.84, 0.45],
                      [0.20, 0.55, 0.95],
                      [0.95, 0.98, 1.00]]),
}


def view_matrix(azim_deg: float, elev_deg: float) -> np.ndarray:
    """Rows are the camera's right / up / forward axes in world RAS."""
    a = np.radians(azim_deg)
    e = np.radians(elev_deg)
    # Yaw about the superior (z) axis, then pitch down by elev.
    right = np.array([np.cos(a), np.sin(a), 0.0])
    fwd_h = np.array([-np.sin(a), np.cos(a), 0.0])
    up_w = np.array([0.0, 0.0, 1.0])
    fwd = fwd_h * np.cos(e) - up_w * np.sin(e)
    # right x fwd, not fwd x right: the latter points inferior and flips
    # the whole scene vertically.
    up = np.cross(right, fwd)
    return np.stack([right, up, fwd])


def load(path: str):
    z = np.load(path)
    return z["points"].astype(np.float32), z["offsets"], z["centroid"]


def tangents(pts: np.ndarray, offsets: np.ndarray) -> np.ndarray:
    """Central-difference unit tangent per point, not crossing streamline ends."""
    t = np.empty_like(pts)
    t[1:-1] = pts[2:] - pts[:-2]
    t[0] = pts[1] - pts[0]
    t[-1] = pts[-1] - pts[-2]
    # At streamline boundaries the central difference straddles two different
    # streamlines, so replace those with a one-sided difference.
    starts, ends = offsets[:-1], offsets[1:] - 1
    t[starts] = pts[starts + 1] - pts[starts]
    t[ends] = pts[ends] - pts[ends - 1]
    n = np.linalg.norm(t, axis=1, keepdims=True)
    np.maximum(n, 1e-6, out=n)
    return t / n


def render(args) -> None:
    pts, offsets, centroid = load(args.tracts)
    n_pts = len(pts)
    print(f"points {n_pts:,}  streamlines {len(offsets)-1:,}")

    tang = tangents(pts, offsets)
    basis = PALETTE[args.palette]
    # |t| as barycentric-ish weights over the three axis colours. Squaring
    # sharpens the assignment so a mostly-vertical fibre reads as one colour
    # instead of a muddy average.
    w = np.abs(tang) ** args.color_sharpness
    w /= w.sum(axis=1, keepdims=True)
    colors = (w @ basis).astype(np.float32)
    del w, tang

    R = view_matrix(args.azim, args.elev)
    cam = ((pts - centroid) @ R.T).astype(np.float32)
    del pts

    SS = args.supersample
    W, H = args.width * SS, args.height * SS

    ex, ey = cam[:, 0], cam[:, 1]
    span = max(ex.max() - ex.min(), (ey.max() - ey.min()) * W / H)
    scale = (W * args.fill) / span
    px = (ex - 0.5 * (ex.min() + ex.max())) * scale + W / 2
    py = (-(ey - 0.5 * (ey.min() + ey.max()))) * scale + H / 2
    depth = cam[:, 2]
    d0, d1 = np.percentile(depth, [1, 99])
    dn = np.clip((depth - d0) / (d1 - d0), 0, 1)   # 0 = near camera, 1 = far
    del cam, ex, ey, depth

    # Segment list: every point except each streamline's last connects forward.
    seg = np.ones(n_pts, dtype=bool)
    seg[offsets[1:] - 1] = False
    seg_i = np.flatnonzero(seg)
    del seg

    acc_rgb = np.zeros(W * H * 3, dtype=np.float32)
    acc_w = np.zeros(W * H, dtype=np.float32)

    K = args.samples_per_seg
    tvals = ((np.arange(K, dtype=np.float32) + 0.5) / K)
    CHUNK = args.chunk

    for c0 in range(0, len(seg_i), CHUNK):
        idx = seg_i[c0:c0 + CHUNK]
        j = idx + 1
        x0, y0 = px[idx], py[idx]
        x1, y1 = px[j], py[j]
        seg_len = np.hypot(x1 - x0, y1 - y0)

        # Depth fog: far fibres dim toward the background and lose contrast, so
        # the near surface of the brain reads clearly instead of everything
        # piling into one flat slab.
        dmid = 0.5 * (dn[idx] + dn[j])
        atten = (1.0 - args.fog * dmid).astype(np.float32)

        col = 0.5 * (colors[idx] + colors[j])
        # Cool the far side as well as dim it.
        col = col * atten[:, None]

        wgt = (seg_len / K) * atten
        m = seg_len > 1e-4
        if not m.all():
            x0, y0, x1, y1 = x0[m], y0[m], x1[m], y1[m]
            col, wgt = col[m], wgt[m]

        # (nseg, K) sample positions along each segment.
        sx = (x0[:, None] + (x1 - x0)[:, None] * tvals).ravel()
        sy = (y0[:, None] + (y1 - y0)[:, None] * tvals).ravel()
        sc = np.repeat(col, K, axis=0)
        sw = np.repeat(wgt, K)

        inside = (sx >= 0) & (sx < W - 1) & (sy >= 0) & (sy < H - 1)
        sx, sy, sc, sw = sx[inside], sy[inside], sc[inside], sw[inside]
        if sx.size == 0:
            continue

        ix, iy = sx.astype(np.int32), sy.astype(np.int32)
        fx, fy = sx - ix, sy - iy
        base = iy * W + ix
        for off, bw in ((0, (1 - fx) * (1 - fy)), (1, fx * (1 - fy)),
                        (W, (1 - fx) * fy), (W + 1, fx * fy)):
            f = base + off
            ww = (sw * bw).astype(np.float32)
            acc_w += np.bincount(f, weights=ww, minlength=W * H).astype(np.float32)
            for ch in range(3):
                acc_rgb[ch::3] += np.bincount(
                    f, weights=ww * sc[:, ch], minlength=W * H
                ).astype(np.float32)
        print(f"  chunk {c0//CHUNK + 1}/{(len(seg_i)+CHUNK-1)//CHUNK}", flush=True)

    acc_rgb = acc_rgb.reshape(H, W, 3)
    acc_w = acc_w.reshape(H, W)

    # Filmic-ish tone map. Alpha saturates faster than colour so thin outlying
    # fibres stay visible without the dense core blowing out to a white blob.
    k = args.exposure / max(acc_w.mean(), 1e-9)
    alpha = 1.0 - np.exp(-acc_w * k)
    hue = acc_rgb / np.maximum(acc_w, 1e-9)[..., None]
    lum = 1.0 - np.exp(-acc_w * k * args.core_gain)
    rgb = hue * lum[..., None]

    rgb = np.clip(rgb, 0, 1) ** (1.0 / args.gamma)
    alpha = np.clip(alpha * args.alpha_gain, 0, 1)

    out = np.dstack([rgb, alpha])
    img = Image.fromarray((out * 255 + 0.5).astype(np.uint8), "RGBA")
    if SS > 1:
        img = img.resize((args.width, args.height), Image.Resampling.LANCZOS)
    img.save(args.out)
    print(f"wrote {args.out}")

    if args.over:
        bg = Image.new("RGBA", img.size, args.over)
        Image.alpha_composite(bg, img).convert("RGB").save(
            args.out.replace(".png", "_on-navy.png"), quality=95)
        print(f"wrote {args.out.replace('.png', '_on-navy.png')}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tracts", default="work/tracts.npz")
    p.add_argument("--out", default="out/tracts.png")
    p.add_argument("--width", type=int, default=1600)
    p.add_argument("--height", type=int, default=1200)
    p.add_argument("--supersample", type=int, default=2)
    p.add_argument("--azim", type=float, default=35.0)
    p.add_argument("--elev", type=float, default=25.0)
    p.add_argument("--fill", type=float, default=0.88)
    p.add_argument("--palette", default="ice", choices=list(PALETTE))
    p.add_argument("--color-sharpness", type=float, default=2.0)
    p.add_argument("--fog", type=float, default=0.55)
    p.add_argument("--exposure", type=float, default=0.9)
    p.add_argument("--core-gain", type=float, default=0.55)
    p.add_argument("--alpha-gain", type=float, default=1.0)
    p.add_argument("--gamma", type=float, default=1.9)
    p.add_argument("--samples-per-seg", type=int, default=6)
    p.add_argument("--chunk", type=int, default=1_500_000)
    p.add_argument("--over", default="#050E24")
    main_args = p.parse_args()
    render(main_args)


if __name__ == "__main__":
    main()
