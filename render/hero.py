"""Compose the INI Austin hero image: named tracts inside a glass cortex.

Three passes are layered back to front:

  1. the far half of the pial surface, dimmed, so the tracts have a body to sit
     against instead of floating on the page background;
  2. the named tract bundles;
  3. the near half of the pial surface at low opacity, which supplies the
     silhouette, the gyral pattern and the Fresnel edge light.

Rendering the cortex as two halves is what makes it read as a shell containing
the tracts rather than as a solid that hides them.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from PIL import Image, ImageEnhance

PY = [sys.executable]


def run(script: str, args: list[str]) -> None:
    cmd = PY + [script] + args
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:], r.stderr[-3000:])
        raise SystemExit(f"{script} failed")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", default="out/hero.png")
    p.add_argument("--width", type=int, default=1600)
    p.add_argument("--height", type=int, default=1250)
    p.add_argument("--supersample", type=int, default=2)
    p.add_argument("--azim", type=float, default=65.0)
    p.add_argument("--elev", type=float, default=20.0)
    p.add_argument("--fill", type=float, default=0.88)
    p.add_argument("--back-opacity", type=float, default=0.55)
    p.add_argument("--front-opacity", type=float, default=0.26)
    p.add_argument("--back-dim", type=float, default=0.42)
    p.add_argument("--slab-opacity", type=float, default=0.34)
    p.add_argument("--bundle-exposure", type=float, default=1.2)
    p.add_argument("--bg", default="#050E24")
    p.add_argument("--keep", action="store_true", help="keep intermediate layers")
    a = p.parse_args()

    W, H, SS = str(a.width), str(a.height), str(a.supersample)
    view = ["--azim", str(a.azim), "--elev", str(a.elev), "--fill", str(a.fill),
            "--width", W, "--height", H, "--supersample", SS, "--over", ""]

    tmp = Path("work/layers")
    tmp.mkdir(parents=True, exist_ok=True)

    run("render_surface.py", view + [
        "--faces", "back", "--opacity", str(a.back_opacity),
        "--sample-density", "2.4", "--rim", "0.18", "--specular", "0.10",
        "--out", str(tmp / "back.png")])

    run("render_bundles.py", view + [
        "--tracts", "work/bundles_anat.npz",
        "--slab-opacity", str(a.slab_opacity),
        "--exposure", str(a.bundle_exposure),
        "--out", str(tmp / "tracts.png")])

    run("render_surface.py", view + [
        "--faces", "front", "--opacity", str(a.front_opacity),
        "--sample-density", "2.4", "--rim", "0.85", "--rim-power", "2.2",
        "--specular", "0.42", "--ambient", "0.16",
        "--out", str(tmp / "front.png")])

    back = Image.open(tmp / "back.png").convert("RGBA")
    trk = Image.open(tmp / "tracts.png").convert("RGBA")
    front = Image.open(tmp / "front.png").convert("RGBA")

    back = ImageEnhance.Brightness(back).enhance(a.back_dim)

    comp = Image.alpha_composite(back, trk)
    comp = Image.alpha_composite(comp, front)
    comp.save(a.out)
    print(f"wrote {a.out}")

    bg = Image.new("RGBA", comp.size, a.bg)
    Image.alpha_composite(bg, comp).convert("RGB").save(
        a.out.replace(".png", "_on-navy.png"))
    print(f"wrote {a.out.replace('.png','_on-navy.png')}")


if __name__ == "__main__":
    main()
