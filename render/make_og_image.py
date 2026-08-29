"""Bake the flat brand cards: the og:image share card and the Google Forms banner.

The site's live backdrop is a repeating tile plus CSS gradients, and neither a
link-preview scraper nor Google Forms can run those. This reproduces the look as
a plain image at each size that needs one, with the full white lockup centred.

    python3 render/make_og_image.py
"""
from __future__ import annotations

import pathlib

from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parent.parent
TILE = ROOT / "web/data/cortex-tile.png"
LOGO = ROOT / "web/assets/ini-logo-white.png"

NAVY = (4, 9, 26)          # --navy-900
TILE_PX = 760              # matches background-size in css/style.css
TILE_OPACITY = 0.72        # matches body::before
MAX_W_FRAC = 0.82          # lockup fills most of the card...
MAX_H_FRAC = 0.75          # ...unless the card is short, then height wins

# 1200x630 is what Facebook, LinkedIn, Slack and iMessage expect; Google Forms
# crops its header to a wide strip, so it gets its own 1600x400 render.
CARDS = [
    ("web/assets/og-preview.png", 1200, 630),
    ("web/assets/forms-banner.png", 1600, 400),
]


def backdrop(w: int, h: int) -> Image.Image:
    """Navy ground with the cortex tile repeated over it at site scale."""
    base = Image.new("RGB", (w, h), NAVY)
    tile = Image.open(TILE).convert("RGB").resize(
        (TILE_PX, TILE_PX), Image.Resampling.LANCZOS)

    layer = Image.new("RGB", (w, h), NAVY)
    for x in range(0, w, TILE_PX):
        for y in range(0, h, TILE_PX):
            layer.paste(tile, (x, y))

    return Image.blend(base, layer, TILE_OPACITY)


def darken_edges(img: Image.Image) -> Image.Image:
    """Vignette so the white lockup keeps contrast against bright gyri."""
    w, h = img.size
    veil = Image.new("RGB", (w, h), NAVY)
    cx, cy = w / 2, h / 2
    buf = bytearray(w * h)
    for y in range(h):
        dy2 = ((y - cy) / cy) ** 2
        row = y * w
        for x in range(w):
            # normalised distance from centre, clamped to the 0-255 mask range
            d = (((x - cx) / cx) ** 2 + dy2) ** 0.5
            buf[row + x] = min(255, int(max(0.0, d - 0.15) * 210))
    mask = Image.frombytes("L", (w, h), bytes(buf))
    return Image.composite(veil, img, mask)


def bake(rel_out: str, w: int, h: int) -> None:
    card = darken_edges(backdrop(w, h)).convert("RGBA")

    logo = Image.open(LOGO).convert("RGBA")
    scale = min(w * MAX_W_FRAC / logo.width, h * MAX_H_FRAC / logo.height)
    lw, lh = round(logo.width * scale), round(logo.height * scale)
    logo = logo.resize((lw, lh), Image.Resampling.LANCZOS)

    card.alpha_composite(logo, ((w - lw) // 2, (h - lh) // 2))
    out = ROOT / rel_out
    card.convert("RGB").save(out, optimize=True)
    print(f"wrote {rel_out} ({w}x{h}), logo {lw}x{lh}")


def main() -> None:
    for rel_out, w, h in CARDS:
        bake(rel_out, w, h)


if __name__ == "__main__":
    main()
