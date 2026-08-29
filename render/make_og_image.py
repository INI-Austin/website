"""Bake the social preview card served as og:image.

Link previews are flat images: the site's live backdrop is a repeating tile plus
CSS gradients, none of which a scraper can run. This reproduces that look at the
1200x630 size Facebook, LinkedIn, Slack and iMessage expect, with the full white
lockup centred over it.

    python3 render/make_og_image.py
"""
from __future__ import annotations

import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
TILE = ROOT / "web/data/cortex-tile.png"
LOGO = ROOT / "web/assets/ini-logo-white.png"
OUT = ROOT / "web/assets/og-preview.png"

W, H = 1200, 630
NAVY = (4, 9, 26)          # --navy-900
TILE_PX = 760              # matches background-size in css/style.css
TILE_OPACITY = 0.72        # matches body::before
LOGO_WIDTH_FRAC = 0.82     # lockup fills most of the card


def backdrop() -> Image.Image:
    """Navy ground with the cortex tile repeated over it at site scale."""
    base = Image.new("RGB", (W, H), NAVY)
    tile = Image.open(TILE).convert("RGB").resize((TILE_PX, TILE_PX), Image.Resampling.LANCZOS)

    layer = Image.new("RGB", (W, H), NAVY)
    for x in range(0, W, TILE_PX):
        for y in range(0, H, TILE_PX):
            layer.paste(tile, (x, y))

    return Image.blend(base, layer, TILE_OPACITY)


def darken_edges(img: Image.Image) -> Image.Image:
    """Vignette so the white lockup keeps contrast against bright gyri."""
    veil = Image.new("RGB", (W, H), NAVY)
    cx, cy = W / 2, H / 2
    buf = bytearray(W * H)
    for y in range(H):
        dy2 = ((y - cy) / cy) ** 2
        row = y * W
        for x in range(W):
            # normalised distance from centre, clamped to the 0-255 mask range
            d = (((x - cx) / cx) ** 2 + dy2) ** 0.5
            buf[row + x] = min(255, int(max(0.0, d - 0.15) * 210))
    mask = Image.frombytes("L", (W, H), bytes(buf))
    return Image.composite(veil, img, mask)


def main() -> None:
    card = darken_edges(backdrop()).convert("RGBA")

    logo = Image.open(LOGO).convert("RGBA")
    lw = int(W * LOGO_WIDTH_FRAC)
    lh = round(lw * logo.height / logo.width)
    logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)

    card.alpha_composite(logo, ((W - lw) // 2, (H - lh) // 2))
    card.convert("RGB").save(OUT, optimize=True)
    print(f"wrote {OUT.relative_to(ROOT)} ({W}x{H}), logo {lw}x{lh}")


if __name__ == "__main__":
    main()
