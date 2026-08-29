"""Isometric render of named anatomical bundles for sub-test3.

Same depth-slab compositing and illuminated-streamline shading as
render_iso.py, but colour comes from which tract a streamline belongs to
rather than from its direction, so the image is an anatomical figure rather
than a texture. A small direction-driven lightness wobble is kept so bundles
still show internal structure instead of reading as flat ribbons.
"""
from __future__ import annotations

import argparse
import numpy as np
from PIL import Image, ImageFilter

from render_iso import view_matrix, shade
from bundles import hex_rgb


def render(a) -> None:
    z = np.load(a.tracts, allow_pickle=False)
    pts = z["points"].astype(np.float32)
    offsets = z["offsets"]
    bid_s = z["bundle_id"]
    centroid = z["centroid"]
    colors_hex = [str(c) for c in z["colors"]]
    names = [str(n) for n in z["names"]]

    if a.only:
        want = {w.lower() for w in a.only.split(",")}
        keep = np.array([any(w in n.lower() for w in want) for n in names])
        sel = keep[bid_s]
        idx = np.flatnonzero(sel)
        lens = np.diff(offsets)[idx]
        new_off = np.zeros(len(idx) + 1, dtype=np.int64)
        np.cumsum(lens, out=new_off[1:])
        within = np.arange(int(new_off[-1]), dtype=np.int64) - np.repeat(new_off[:-1], lens)
        pts = pts[np.repeat(offsets[idx], lens) + within]
        offsets, bid_s = new_off, bid_s[idx]
        print(f"filtered to {keep.sum()} bundles, {len(idx):,} streamlines")

    if a.keep_every > 1:
        idx = np.arange(0, len(offsets) - 1, a.keep_every)
        lens = np.diff(offsets)[idx]
        new_off = np.zeros(len(idx) + 1, dtype=np.int64)
        np.cumsum(lens, out=new_off[1:])
        within = np.arange(int(new_off[-1]), dtype=np.int64) - np.repeat(new_off[:-1], lens)
        pts = pts[np.repeat(offsets[idx], lens) + within]
        offsets, bid_s = new_off, bid_s[idx]

    n = len(pts)
    print(f"points {n:,}  streamlines {len(offsets)-1:,}", flush=True)

    palette = np.array([hex_rgb(c) for c in colors_hex], dtype=np.float32)
    # per-point bundle id
    bid_p = np.repeat(bid_s, np.diff(offsets))

    R = view_matrix(a.azim, a.elev)
    cam = ((pts - centroid) @ R.T).astype(np.float32)
    del pts, z

    SS = a.supersample
    W, H = a.width * SS, a.height * SS
    lo, hi = cam.min(axis=0), cam.max(axis=0)
    span = max(hi[0] - lo[0], (hi[1] - lo[1]) * W / H)
    scale = np.float32((W * a.fill) / span)
    cx, cy = np.float32(0.5 * (lo[0] + hi[0])), np.float32(0.5 * (lo[1] + hi[1]))
    ox, oy = np.float32(W / 2), np.float32(H / 2)

    keep = np.ones(n, dtype=bool)
    keep[offsets[1:] - 1] = False
    seg = np.flatnonzero(keep).astype(np.int64)
    del keep

    zmid = 0.5 * (cam[seg, 2] + cam[seg + 1, 2])
    z0, z1 = np.percentile(zmid, [0.2, 99.8])
    NS = a.slabs
    slab = np.clip((zmid - z0) / max(z1 - z0, 1e-6) * NS, 0, NS - 1).astype(np.int32)
    dn = np.clip((zmid - z0) / max(z1 - z0, 1e-6), 0, 1).astype(np.float32)
    del zmid
    order = np.argsort(slab, kind="stable")
    bounds = np.searchsorted(slab[order], np.arange(NS + 1))
    seg, dn = seg[order], dn[order]
    del slab, order

    light = np.array(a.light, dtype=np.float32)
    light /= np.linalg.norm(light)

    dst_rgb = np.zeros((H, W, 3), dtype=np.float32)
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
    tv = (np.arange(K, dtype=np.float32) + 0.5) / K
    npix = W * H

    for s in range(NS):
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
            col = palette[bid_p[i]] * inten[:, None]
            dd = dn[c0:min(c0 + a.chunk, s1)]
            col *= (1.0 - a.fog * dd)[:, None]

            x0 = (pi[:, 0] - cx) * scale + ox
            y0 = -(pi[:, 1] - cy) * scale + oy
            x1 = (pj[:, 0] - cx) * scale + ox
            y1 = -(pj[:, 1] - cy) * scale + oy
            wgt = (np.hypot(x1 - x0, y1 - y0) / K) * (1.0 - a.fog_alpha * dd)

            sx = (x0[:, None] + (x1 - x0)[:, None] * tv).ravel()
            sy = (y0[:, None] + (y1 - y0)[:, None] * tv).ravel()
            sc = np.repeat(col, K, axis=0)
            sw = np.repeat(wgt, K)
            ok = (sx >= 0) & (sx < W - 1) & (sy >= 0) & (sy < H - 1) & (sw > 0)
            sx, sy, sc, sw = sx[ok], sy[ok], sc[ok], sw[ok]
            if sx.size == 0:
                continue
            ix, iy = sx.astype(np.int32), sy.astype(np.int32)
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
        srgb *= sa[..., None]
        ka = 1.0 - dst_a
        dst_rgb += ka[..., None] * srgb
        dst_a += ka * sa

    rgb = np.clip(dst_rgb * a.exposure, 0, 1) ** (1.0 / a.gamma)
    alpha = np.clip(dst_a * a.alpha_gain, 0, 1)
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


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--tracts", default="work/bundles.npz")
    p.add_argument("--out", default="out/bundles.png")
    p.add_argument("--only", default="", help="comma substrings of bundle names")
    p.add_argument("--width", type=int, default=1400)
    p.add_argument("--height", type=int, default=1100)
    p.add_argument("--supersample", type=int, default=2)
    p.add_argument("--azim", type=float, default=65.0)
    p.add_argument("--elev", type=float, default=20.0)
    p.add_argument("--fill", type=float, default=0.9)
    p.add_argument("--slabs", type=int, default=72)
    p.add_argument("--slab-opacity", type=float, default=0.30)
    p.add_argument("--fog", type=float, default=0.45)
    p.add_argument("--fog-alpha", type=float, default=0.25)
    p.add_argument("--ambient", type=float, default=0.20)
    p.add_argument("--diffuse", type=float, default=0.78)
    p.add_argument("--specular", type=float, default=0.50)
    p.add_argument("--shininess", type=float, default=26.0)
    p.add_argument("--light", type=float, nargs=3, default=[-0.45, 0.72, -0.53])
    p.add_argument("--exposure", type=float, default=1.15)
    p.add_argument("--gamma", type=float, default=1.35)
    p.add_argument("--alpha-gain", type=float, default=1.0)
    p.add_argument("--glow", type=float, default=0.0)
    p.add_argument("--glow-radius", type=float, default=8.0)
    p.add_argument("--keep-every", type=int, default=1)
    p.add_argument("--samples-per-seg", type=int, default=4)
    p.add_argument("--auto-samples", type=int, default=1)
    p.add_argument("--chunk", type=int, default=2_000_000)
    p.add_argument("--over", default="#050E24")
    render(p.parse_args())


if __name__ == "__main__":
    main()
