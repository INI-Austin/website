"""Turn the rendered cortex into a seamlessly repeating background tile.

This ships the render's own pixels. No relighting, no recolouring: the shader
experiment that preceded this looked like wet plastic precisely because it
threw the baked shading away and invented its own.

Only two things are done to the crop, and both exist solely to let it repeat:

  1. Optional low-frequency flattening. The render is lit from the upper left,
     so the crop is brighter on one side than the other. Tiling that unchanged
     would print a visible light/dark checker across the page. Dividing by a
     heavily blurred copy removes the gradient while leaving every fold, and
     the original mean colour is put straight back.
  2. Blend the wrap-around overlap, then crop it off. Only a narrow band at two
     edges is ever mixed; the interior is untouched.
"""
from __future__ import annotations

import argparse
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

SRC = "out/final/cortex-isometric.png"


def largest_opaque_square(alpha: np.ndarray, frac: float) -> tuple[int, int, int]:
    """Largest square that lies entirely inside the silhouette.

    A centred crop clips the concavities around the temporal pole and leaves
    transparent wedges, which tile as black holes. A chessboard distance
    transform gives, for every pixel, the half-side of the biggest square that
    fits around it without leaving the mask, so its maximum is exactly the
    crop we want.
    """
    from scipy.ndimage import distance_transform_cdt, binary_fill_holes, binary_closing

    # The render has pinholes between gyri. Left alone they count as
    # background and collapse the inscribed square to a few hundred pixels,
    # so close them before measuring.
    opaque = alpha > 250
    opaque = binary_closing(opaque, np.ones((9, 9), bool))
    opaque = binary_fill_holes(opaque).astype(np.uint8)
    d = distance_transform_cdt(opaque, metric="chessboard")
    cy, cx = np.unravel_index(int(np.argmax(d)), d.shape)
    half = int(d[cy, cx])
    side = (half * 2) // 2 * 2
    if frac > 0:
        side = min(side, int(min(alpha.shape) * frac) // 2 * 2)
    y0, x0 = cy - side // 2, cx - side // 2
    print(f"largest inscribed square: side {side} centred at ({cx},{cy})")
    return y0, x0, side


def flatten(rgb: np.ndarray, sigma: float) -> np.ndarray:
    """Remove the global lighting gradient, keep the folds and the colour."""
    lum = rgb.mean(axis=2, keepdims=True)
    base = gaussian_filter(lum, sigma=(sigma, sigma, 0))
    base = np.maximum(base, 1e-3)
    out = rgb * (lum.mean() / base)
    return np.clip(out, 0, 1)


def make_tileable(img: np.ndarray, feather: float) -> np.ndarray:
    H, W = img.shape[:2]
    fw, fh = int(W * feather), int(H * feather)
    a = np.linspace(0.0, 1.0, fw, dtype=np.float32)[None, :, None]
    left = img[:, :fw] * a + img[:, W - fw:] * (1.0 - a)
    out = np.concatenate([left, img[:, fw:W - fw]], axis=1)
    H2, W2 = out.shape[:2]
    b = np.linspace(0.0, 1.0, fh, dtype=np.float32)[:, None, None]
    top = out[:fh] * b + out[H2 - fh:] * (1.0 - b)
    return np.concatenate([top, out[fh:H2 - fh]], axis=0)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--src", default=SRC)
    p.add_argument("--crop", type=float, default=0.0, help="0 = use the largest inscribed square")
    p.add_argument("--feather", type=float, default=0.15)
    p.add_argument("--flatten-sigma", type=float, default=90.0)
    p.add_argument("--no-flatten", action="store_true")
    p.add_argument("--size", type=int, default=1400)
    p.add_argument("--out", default="../web/data/cortex-tile.png")
    p.add_argument("--preview", default="out/cortex_tile_check.png")
    a = p.parse_args()

    im = Image.open(a.src).convert("RGBA")
    arr = np.asarray(im).astype(np.float32) / 255.0
    alpha = np.asarray(im)[..., 3]
    y0, x0, side = largest_opaque_square(alpha, a.crop)
    print(f"source {im.size}, crop {side}x{side} at ({x0},{y0})")
    cov = (alpha[y0:y0 + side, x0:x0 + side] > 250).mean()
    print(f"crop coverage {cov*100:.2f}% opaque")

    rgb = arr[y0:y0 + side, x0:x0 + side, :3]
    hole = alpha[y0:y0 + side, x0:x0 + side] <= 250
    if hole.any():
        # Pinholes between gyri would tile as black specks. Fill each from its
        # nearest opaque pixel so the field stays continuous.
        from scipy.ndimage import distance_transform_edt
        idx = distance_transform_edt(hole, return_distances=False, return_indices=True)
        rgb = rgb[tuple(idx)]
        print(f"filled {hole.sum():,} transparent pixels ({hole.mean()*100:.2f}%)")
    if not a.no_flatten:
        rgb = flatten(rgb, a.flatten_sigma)
    tile = make_tileable(rgb, a.feather)

    img = Image.fromarray((np.clip(tile, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB")
    img = img.resize((a.size, a.size), Image.Resampling.LANCZOS)
    img.save(a.out, optimize=True)
    print(f"wrote {a.out}  {img.size}  {len(img.tobytes())/1e6:.1f} MB raw")

    grid = Image.new("RGB", (img.width * 2, img.height * 2))
    for gy in range(2):
        for gx in range(2):
            grid.paste(img, (gx * img.width, gy * img.height))
    grid.resize((1100, 1100), Image.Resampling.LANCZOS).save(a.preview)
    print(f"wrote {a.preview} (2x2, check for seams)")


if __name__ == "__main__":
    main()
