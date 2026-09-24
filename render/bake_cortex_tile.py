"""Bake the cortical surface into a seamlessly tiling relight map.

The page background should be the real cortex, not a procedural imitation of
it, and its lighting should move. Those two wants conflict with shipping a flat
PNG: a rendered image has the light baked in and cannot be relit, and a brain
has a silhouette so it cannot tile.

Both are solved by shipping geometry instead of a picture. This renders the
surface orthographically and stores, per pixel, the camera-space normal and an
occlusion term rather than a colour. The shader can then light it with any
direction it likes, at any time.

Tiling is handled by cropping well inside the silhouette, where the frame is
nothing but folds, and then blending the wrap-around overlap and cropping it
off. The result repeats with no edge, and only a narrow band is ever touched by
the blend.
"""
from __future__ import annotations

import argparse
import numpy as np
from PIL import Image

import render_surface as rs


def render_gbuffer(a):
    """Orthographic normal + occlusion buffer, reusing the surface rasteriser."""
    v, f, sulc = rs.load_surface("pial")
    vn = rs.vertex_normals(v, f)
    centroid = v.mean(axis=0)
    R = rs.view_matrix(a.azim, a.elev)
    vc = (v - centroid) @ R.T
    nc = vn @ R.T

    W = H = a.size
    lo, hi = vc.min(axis=0), vc.max(axis=0)
    span = max(hi[0] - lo[0], hi[1] - lo[1])
    scale = (W * 0.98) / span
    px = (vc[:, 0] - 0.5 * (lo[0] + hi[0])) * scale + W / 2
    py = -(vc[:, 1] - 0.5 * (lo[1] + hi[1])) * scale + H / 2
    pz = vc[:, 2]

    s = (sulc - np.percentile(sulc, 2)) / (np.percentile(sulc, 98) - np.percentile(sulc, 2))
    s = np.clip(s, 0, 1)

    tri = f
    ax_, ay_ = px[tri[:, 0]], py[tri[:, 0]]
    bx_, by_ = px[tri[:, 1]], py[tri[:, 1]]
    cx_, cy_ = px[tri[:, 2]], py[tri[:, 2]]
    area = 0.5 * np.abs((bx_ - ax_) * (cy_ - ay_) - (cx_ - ax_) * (by_ - ay_))

    zbuf = np.full(W * H, np.inf, dtype=np.float32)
    nbuf = np.zeros((W * H, 3), dtype=np.float32)
    sbuf = np.zeros(W * H, dtype=np.float32)
    hit = np.zeros(W * H, dtype=bool)

    rng = np.random.default_rng(3)
    buckets = [1, 4, 16, 64, 256, 1024]
    need = np.clip(np.ceil(area * 2.4), 1, buckets[-1])
    bidx = np.searchsorted(buckets, need)

    for bi, K in enumerate(buckets):
        sel = np.flatnonzero(bidx == bi)
        if sel.size == 0:
            continue
        step = max(1, 6_000_000 // K)
        for c0 in range(0, sel.size, step):
            idx = sel[c0:c0 + step]
            t = tri[idx]
            u = rng.random((len(idx), K), dtype=np.float32)
            w_ = rng.random((len(idx), K), dtype=np.float32)
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

            ok = (sx >= 0) & (sx < W) & (sy >= 0) & (sy < H) & (nz < 0)
            sx, sy, sz, ss_, nx, ny, nz = (q[ok] for q in (sx, sy, sz, ss_, nx, ny, nz))
            if sx.size == 0:
                continue
            nl = np.sqrt(nx * nx + ny * ny + nz * nz)
            np.maximum(nl, 1e-9, out=nl)
            nx, ny, nz = nx / nl, ny / nl, nz / nl

            o = np.argsort(-sz, kind="stable")
            sz = sz[o]
            flat = (sy[o].astype(np.int32) * W + sx[o].astype(np.int32))
            m = sz < zbuf[flat]
            fm = flat[m]
            zbuf[fm] = sz[m]
            nbuf[fm] = np.stack([nx[o][m], ny[o][m], nz[o][m]], axis=1)
            sbuf[fm] = ss_[o][m]
            hit[fm] = True
        print(f"  bucket K={K}: {sel.size:,} tris", flush=True)

    return (nbuf.reshape(H, W, 3), sbuf.reshape(H, W),
            hit.reshape(H, W), zbuf.reshape(H, W))


def make_tileable(img: np.ndarray, feather: float) -> np.ndarray:
    """Blend the wrap-around overlap, then crop it off.

    Only a band of `feather` at two edges is ever mixed, so the interior stays
    exactly as rendered. The returned image tiles with no discontinuity.
    """
    H, W = img.shape[:2]
    fw, fh = int(W * feather), int(H * feather)

    a = np.linspace(0.0, 1.0, fw, dtype=np.float32)[None, :, None]
    left = img[:, :fw] * a + img[:, W - fw:] * (1.0 - a)
    out = np.concatenate([left, img[:, fw:W - fw]], axis=1)

    H2, W2 = out.shape[:2]
    b = np.linspace(0.0, 1.0, fh, dtype=np.float32)[:, None, None]
    top = out[:fh] * b + out[H2 - fh:] * (1.0 - b)
    out = np.concatenate([top, out[fh:H2 - fh]], axis=0)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--size", type=int, default=2200)
    p.add_argument("--azim", type=float, default=135.0)
    p.add_argument("--elev", type=float, default=20.0)
    p.add_argument("--crop", type=float, default=0.44, help="interior fraction to keep")
    p.add_argument("--feather", type=float, default=0.16)
    p.add_argument("--out", default="../web/data/cortex-relight.png")
    p.add_argument("--preview", default="out/cortex_tile_preview.png")
    a = p.parse_args()

    nrm, sulc, hit, _ = render_gbuffer(a)
    S = a.size
    c = int(S * a.crop) // 2 * 2
    y0 = (S - c) // 2
    x0 = (S - c) // 2
    nrm = nrm[y0:y0 + c, x0:x0 + c]
    sulc = sulc[y0:y0 + c, x0:x0 + c]
    cover = hit[y0:y0 + c, x0:x0 + c]
    print(f"crop {c}x{c}, coverage {cover.mean()*100:.1f}%")
    if cover.mean() < 0.999:
        # Any hole would tile as a hard hint of the silhouette; fill from a
        # neighbour so the field stays continuous.
        from scipy.ndimage import distance_transform_edt
        idx = distance_transform_edt(~cover, return_distances=False, return_indices=True)
        nrm = nrm[tuple(idx)]
        sulc = sulc[tuple(idx)]

    stack = np.dstack([nrm, sulc[..., None]]).astype(np.float32)
    stack = make_tileable(stack, a.feather)

    n = stack[..., :3]
    n /= np.maximum(np.linalg.norm(n, axis=2, keepdims=True), 1e-9)
    enc = np.dstack([n * 0.5 + 0.5, np.clip(stack[..., 3], 0, 1)])
    img = Image.fromarray((enc * 255 + 0.5).astype(np.uint8), "RGBA")
    img = img.resize((1024, 1024), Image.Resampling.LANCZOS)
    img.save(a.out)
    print(f"wrote {a.out}  {img.size}")

    # Quick sanity render so the tile can be eyeballed before shipping.
    L = np.array([-0.45, 0.60, -0.66])
    L /= np.linalg.norm(L)
    d = np.clip(-(n @ L), 0, 1)
    prev = np.dstack([d * 0.55, d * 0.78, d]) ** (1 / 1.2)
    Image.fromarray((np.clip(np.tile(prev, (2, 2, 1)), 0, 1) * 255).astype(np.uint8)).save(a.preview)
    print(f"wrote {a.preview} (2x2 tiled, to check for seams)")


if __name__ == "__main__":
    main()
