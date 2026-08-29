"""Trace the INI lockup to vector and emit the white assets the site uses.

The only genuine source art is 373x149 (brand/source/ini-logo-tagline-orig.png).
Every earlier "HD" file was a 5x bicubic upscale of it, which is why the wordmark
looked soft and rang around the letters. The art is navy ink on transparency, so
the alpha channel is the true shape: threshold it, trace it with potrace, and the
letterforms come back as curves that stay sharp at any size.

Emits an SVG (used directly in the page header) and a large PNG (for the flat
cards in make_og_image.py, which composite raster).

    python3 render/make_lockup.py

Requires potrace, mkbitmap and rsvg-convert (brew install potrace librsvg).
"""
from __future__ import annotations

import pathlib
import subprocess
import tempfile

from PIL import Image, ImageOps

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = ROOT / "brand/source/ini-logo-tagline-orig.png"
OUT_SVG = ROOT / "web/assets/ini-logo-white.svg"
OUT_PNG = ROOT / "web/assets/ini-logo-white.png"

PNG_WIDTH = 1944       # 5x the source; ample for the 2x header and the cards
TRACE_SCALE = 8        # mkbitmap upsample before thresholding
TRACE_THRESHOLD = 0.5


def run(*cmd: str) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        tmp = pathlib.Path(td)
        pgm, pbm = tmp / "ink.pgm", tmp / "ink.pbm"

        # potrace reads dark pixels as ink, so invert: opaque art -> black.
        alpha = Image.open(SRC).convert("RGBA").getchannel("A")
        ImageOps.invert(alpha).save(pgm)

        run("mkbitmap", "-n", "-s", str(TRACE_SCALE), "-t", str(TRACE_THRESHOLD),
            str(pgm), "-o", str(pbm))
        # -t 2 drops specks left by the source's compression noise
        run("potrace", str(pbm), "--svg", "-o", str(OUT_SVG),
            "-a", "1.0", "-O", "0.2", "-t", "2", "--color", "#ffffff")

        run("rsvg-convert", "-w", str(PNG_WIDTH), "-b", "none",
            str(OUT_SVG), "-o", str(OUT_PNG))

    w, h = Image.open(OUT_PNG).size
    print(f"wrote {OUT_SVG.relative_to(ROOT)}")
    print(f"wrote {OUT_PNG.relative_to(ROOT)} ({w}x{h})")


if __name__ == "__main__":
    main()
