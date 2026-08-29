"""Isometric tractography renderer with depth compositing and fibre lighting.

Two things separate this from a naive additive splat, and both matter for the
image reading as a solid three-dimensional brain rather than a smoke cloud:

1. Depth-slab compositing. Segments are counting-sorted into slabs along the
   view axis; each slab is accumulated additively on its own, tone-mapped to a
   premultiplied RGBA layer, then composited front-to-back. Near fibres
   therefore genuinely occlude far ones, which is what produces surface form.

2. Illuminated streamlines (Zoeckler et al. 1996). A line has no surface
   normal, so lighting is derived from the tangent by treating each segment as
   an infinitesimal cylinder and taking the maximum over its normal circle.
   This is what makes bundles look like bundles of tubes.

Colour is direction-encoded and then remapped onto a cool palette, so the
anatomy stays readable while the image stays on-brand.
"""
from __future__ import annotations

import argparse
import numpy as np
from PIL import Image, ImageFilter

# Axis -> colour. x = left-right (callosal), y = anterior-posterior
# (longitudinal association bundles), z = superior-inferior (corticospinal).
PALETTES = {
    "ice":   np.array([[0.37, 0.85, 1.00], [0.16, 0.42, 0.92], [0.88, 0.95, 1.00]]),
    "azure": np.array([[0.55, 0.92, 1.00], [0.20, 0.50, 0.95], [0.98, 0.99, 1.00]]),
    "steel": np.array([[0.60, 0.86, 1.00], [0.28, 0.45, 0.78], [0.93, 0.97, 1.00]]),
    "ember": np.array([[1.00, 0.55, 0.20], [0.20, 0.48, 0.95], [0.97, 0.98, 1.00]]),
    "dec":   np.array([[1.00, 0.18, 0.18], [0.16, 0.95, 0.28], [0.22, 0.42, 1.00]]),
}


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


def shade(t_cam: np.ndarray, light: np.ndarray, a) -> np.ndarray:
    """Illuminated-streamline intensity for unit tangents in camera space."""
    lt = np.abs(t_cam @ light)
    vt = np.abs(t_cam[:, 2])                      # view axis is camera +z
    np.clip(lt, 0.0, 1.0, out=lt)
    np.clip(vt, 0.0, 1.0, out=vt)
    slt = np.sqrt(1.0 - lt * lt)
    svt = np.sqrt(1.0 - vt * vt)
    diffuse = slt
    spec = np.clip(slt * svt - lt * vt, 0.0, 1.0) ** a.shininess
    return a.ambient + a.diffuse * diffuse + a.specular * spec


def select_streamlines(pts, offsets, a):
    """Filter whole streamlines by arc length and/or decimate the bundle.

    Doing this at render time rather than re-running tractography lets the same
    600k-streamline cache serve both the dense anatomical view and the airier
    long-fibre hero view.
    """
    lens = np.diff(offsets)
    if a.min_len > 0 or a.max_len > 0 or a.keep_every > 1:
        seg = np.linalg.norm(np.diff(pts, axis=0), axis=1)
        # Zero out the gaps that span two different streamlines.
        seg[offsets[1:-1] - 1] = 0.0
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        arc = cum[offsets[1:] - 1] - cum[offsets[:-1]]
        sel = np.ones(len(lens), dtype=bool)
        if a.min_len > 0:
            sel &= arc >= a.min_len
        if a.max_len > 0:
            sel &= arc <= a.max_len
        if a.keep_every > 1:
            step = np.zeros(len(lens), dtype=bool)
            step[::a.keep_every] = True
            sel &= step
        if sel.all():
            return pts, offsets
        idx = np.flatnonzero(sel)
        new_lens = lens[idx]
        new_offsets = np.zeros(len(idx) + 1, dtype=np.int64)
        np.cumsum(new_lens, out=new_offsets[1:])
        # Vectorised gather: a Python loop over ~10^5 streamlines is the
        # slowest step in the whole renderer if written the obvious way.
        total = int(new_offsets[-1])
        within = np.arange(total, dtype=np.int64) - np.repeat(new_offsets[:-1], new_lens)
        take = np.repeat(offsets[idx], new_lens) + within
        return pts[take], new_offsets
    return pts, offsets


def render(a) -> None:
    z = np.load(a.tracts)
    pts = z["points"].astype(np.float32)
    offsets = z["offsets"]
    centroid = z["centroid"]
    print(f"loaded points {len(pts):,}  streamlines {len(offsets)-1:,}", flush=True)

    pts, offsets = select_streamlines(pts, offsets, a)
    n = len(pts)
    print(f"selected points {n:,}  streamlines {len(offsets)-1:,}", flush=True)

    R = view_matrix(a.azim, a.elev)
    cam = ((pts - centroid) @ R.T).astype(np.float32)
    del pts, z

    SS = a.supersample
    W, H = a.width * SS, a.height * SS

    lo = cam.min(axis=0)
    hi = cam.max(axis=0)
    span = max(hi[0] - lo[0], (hi[1] - lo[1]) * W / H)
    scale = np.float32((W * a.fill) / span)
    cx, cy = np.float32(0.5 * (lo[0] + hi[0])), np.float32(0.5 * (lo[1] + hi[1]))
    ox, oy = np.float32(W / 2), np.float32(H / 2)

    # Segments: every point except the last of each streamline.
    keep = np.ones(n, dtype=bool)
    keep[offsets[1:] - 1] = False
    seg = np.flatnonzero(keep).astype(np.int64)
    del keep
    print(f"segments {len(seg):,}", flush=True)

    zmid = 0.5 * (cam[seg, 2] + cam[seg + 1, 2])
    z0, z1 = np.percentile(zmid, [0.2, 99.8])
    NS = a.slabs
    slab = np.clip(((zmid - z0) / max(z1 - z0, 1e-6) * NS), 0, NS - 1).astype(np.int32)
    dnorm = np.clip((zmid - z0) / max(z1 - z0, 1e-6), 0, 1).astype(np.float32)
    del zmid

    order = np.argsort(slab, kind="stable")        # radix sort for ints: O(n)
    bounds = np.searchsorted(slab[order], np.arange(NS + 1))
    seg = seg[order]
    dnorm = dnorm[order]
    del slab, order

    light = np.array(a.light, dtype=np.float32)
    light /= np.linalg.norm(light)
    basis = PALETTES[a.palette].astype(np.float32)

    dst_rgb = np.zeros((H, W, 3), dtype=np.float32)   # premultiplied
    dst_a = np.zeros((H, W), dtype=np.float32)

    # Sample count must track how long a segment is *in pixels*, or the splat
    # leaves visible beads. Atlas bundles come back with a coarser step than the
    # whole-brain track, so a fixed K cannot serve both.
    _sp = seg[:: max(1, len(seg) // 20000)]
    _pl = np.hypot((cam[_sp + 1, 0] - cam[_sp, 0]) * scale,
                   (cam[_sp + 1, 1] - cam[_sp, 1]) * scale)
    K = a.samples_per_seg
    if a.auto_samples:
        K = int(np.clip(np.ceil(np.percentile(_pl, 98) * 1.6), 2, 96))
        print(f"segment px p50={np.percentile(_pl,50):.1f} p98={np.percentile(_pl,98):.1f} -> K={K}")
    tv = ((np.arange(K, dtype=np.float32) + 0.5) / K)
    npix = W * H

    for s in range(NS):                                # near -> far
        s0, s1 = bounds[s], bounds[s + 1]
        if s1 <= s0:
            continue
        acc_rgb = np.zeros(npix * 3, dtype=np.float32)
        acc_w = np.zeros(npix, dtype=np.float32)

        for c0 in range(s0, s1, a.chunk):
            i = seg[c0:min(c0 + a.chunk, s1)]
            j = i + 1
            pi, pj = cam[i], cam[j]

            d = pj - pi
            ln = np.linalg.norm(d, axis=1)
            np.maximum(ln, 1e-6, out=ln)
            t = d / ln[:, None]

            inten = shade(t, light, a)

            w3 = np.abs(t) ** a.color_sharpness
            w3 /= w3.sum(axis=1, keepdims=True)
            col = (w3 @ basis) * inten[:, None]

            # Aerial perspective: far fibres lose intensity and drift toward the
            # background tint so the volume reads front-to-back.
            dd = dnorm[c0:min(c0 + a.chunk, s1)]
            col *= (1.0 - a.fog * dd)[:, None]

            x0 = (pi[:, 0] - cx) * scale + ox
            y0 = -(pi[:, 1] - cy) * scale + oy
            x1 = (pj[:, 0] - cx) * scale + ox
            y1 = -(pj[:, 1] - cy) * scale + oy
            seglen = np.hypot(x1 - x0, y1 - y0)
            wgt = (seglen / K) * (1.0 - a.fog_alpha * dd)

            sx = (x0[:, None] + (x1 - x0)[:, None] * tv).ravel()
            sy = (y0[:, None] + (y1 - y0)[:, None] * tv).ravel()
            sc = np.repeat(col, K, axis=0)
            sw = np.repeat(wgt, K)

            ok = (sx >= 0) & (sx < W - 1) & (sy >= 0) & (sy < H - 1) & (sw > 0)
            sx, sy, sc, sw = sx[ok], sy[ok], sc[ok], sw[ok]
            if sx.size == 0:
                continue

            ix = sx.astype(np.int32)
            iy = sy.astype(np.int32)
            fx, fy = sx - ix, sy - iy
            base = iy * W + ix
            for off, bw in ((0, (1 - fx) * (1 - fy)), (1, fx * (1 - fy)),
                            (W, (1 - fx) * fy), (W + 1, fx * fy)):
                f = base + off
                ww = sw * bw
                acc_w += np.bincount(f, weights=ww, minlength=npix).astype(np.float32)
                for ch in range(3):
                    acc_rgb[ch::3] += np.bincount(
                        f, weights=ww * sc[:, ch], minlength=npix).astype(np.float32)

        acc_w = acc_w.reshape(H, W)
        acc_rgb = acc_rgb.reshape(H, W, 3)
        m = acc_w > 0
        if not m.any():
            continue
        sa = 1.0 - np.exp(-acc_w * a.slab_opacity)
        srgb = np.zeros_like(acc_rgb)
        srgb[m] = acc_rgb[m] / acc_w[m][:, None]
        srgb *= sa[..., None]                          # premultiply

        keep_a = 1.0 - dst_a
        dst_rgb += keep_a[..., None] * srgb
        dst_a += keep_a * sa
        if (s + 1) % 8 == 0:
            print(f"  slab {s+1}/{NS}  cover {dst_a.mean():.3f}", flush=True)

    rgb = np.clip(dst_rgb * a.exposure, 0, 1) ** (1.0 / a.gamma)
    alpha = np.clip(dst_a * a.alpha_gain, 0, 1)

    img = Image.fromarray(
        (np.dstack([rgb, alpha]) * 255 + 0.5).astype(np.uint8), "RGBA")
    if SS > 1:
        img = img.resize((a.width, a.height), Image.Resampling.LANCZOS)

    if a.glow > 0:
        base_i = img.copy()
        bloom = img.filter(ImageFilter.GaussianBlur(a.glow_radius))
        img = Image.blend(base_i, Image.alpha_composite(bloom, base_i), a.glow)

    img.save(a.out)
    print(f"wrote {a.out}")
    if a.over:
        bg = Image.new("RGBA", img.size, a.over)
        Image.alpha_composite(bg, img).convert("RGB").save(
            a.out.replace(".png", "_on-navy.png"))
        print(f"wrote {a.out.replace('.png','_on-navy.png')}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tracts", default="work/tracts_v2.npz")
    p.add_argument("--out", default="out/iso.png")
    p.add_argument("--width", type=int, default=1400)
    p.add_argument("--height", type=int, default=1050)
    p.add_argument("--supersample", type=int, default=2)
    p.add_argument("--azim", type=float, default=35.0)
    p.add_argument("--elev", type=float, default=22.0)
    p.add_argument("--fill", type=float, default=0.9)
    p.add_argument("--palette", default="ice", choices=list(PALETTES))
    p.add_argument("--color-sharpness", type=float, default=2.2)
    p.add_argument("--slabs", type=int, default=64)
    p.add_argument("--slab-opacity", type=float, default=0.55)
    p.add_argument("--fog", type=float, default=0.45)
    p.add_argument("--fog-alpha", type=float, default=0.25)
    p.add_argument("--ambient", type=float, default=0.16)
    p.add_argument("--diffuse", type=float, default=0.80)
    p.add_argument("--specular", type=float, default=0.55)
    p.add_argument("--shininess", type=float, default=24.0)
    p.add_argument("--light", type=float, nargs=3, default=[-0.45, 0.72, -0.53])
    p.add_argument("--exposure", type=float, default=1.15)
    p.add_argument("--gamma", type=float, default=1.35)
    p.add_argument("--alpha-gain", type=float, default=1.0)
    p.add_argument("--glow", type=float, default=0.0)
    p.add_argument("--glow-radius", type=float, default=8.0)
    p.add_argument("--min-len", type=float, default=0.0, help="streamline arc length mm")
    p.add_argument("--max-len", type=float, default=0.0)
    p.add_argument("--keep-every", type=int, default=1)
    p.add_argument("--samples-per-seg", type=int, default=3)
    p.add_argument("--auto-samples", type=int, default=1)
    p.add_argument("--chunk", type=int, default=2_000_000)
    p.add_argument("--over", default="#050E24")
    render(p.parse_args())


if __name__ == "__main__":
    main()
