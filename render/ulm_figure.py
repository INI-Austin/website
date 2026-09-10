"""Render the ULM vascular volume from Aleph Neuro's open track data.

This is the still the section falls back to when WebGL is unavailable, so it
has to say the same thing the live viewer says: the same speed field, the same
`ulm_decode.RAMP_DIVISOR`, the same ramp label, and the full-spectrum stops
their published figure uses, which is the convention in velocity-encoded flow
imaging.
"""
from __future__ import annotations

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import ulm_decode

TRACKS = "work/ulm-tracks.bin.gz"  # fetched from alephneuro.com/data/
STOPS = [(0.00, "#1a33cc"), (0.25, "#00b3e6"), (0.50, "#1ae633"),
         (0.75, "#f2d91a"), (1.00, "#e61a1a")]
BG = (4, 9, 26)  # the site's --navy-900
FONT = "/System/Library/Fonts/Helvetica.ttc"


def ramp_fn(stops):
    pos = np.array([p for p, _ in stops], np.float32)
    cols = np.array([[int(c.lstrip("#")[i:i+2], 16) for i in (0, 2, 4)]
                     for _, c in stops], np.float32) / 255.0

    def f(x):
        x = np.clip(x, 0, 1)
        return np.stack([np.interp(x, pos, cols[:, i]) for i in range(3)], -1)
    return f


def view_matrix(azim_deg, elev_deg):
    a, e = np.radians(azim_deg), np.radians(elev_deg)
    ca, sa, ce, se = np.cos(a), np.sin(a), np.cos(e), np.sin(e)
    return (np.array([[1.0, 0, 0], [0, ce, -se], [0, se, ce]])
            @ np.array([[ca, -sa, 0], [sa, ca, 0], [0, 0, 1.0]]))


def render(t, azim, elev, w, h, speed, cap,
           ss=2, margin=0.07, radius=1.0, boost=1.0):
    """Point splat with max compositing.

    Averaging washes a sparse point cloud toward the mean speed; taking the
    brightest contribution per pixel keeps a fast vessel crossing behind a slow
    one legible, which is the whole point of colouring by speed.
    """
    W, H = w * ss, h * ss
    p = t.xyz @ view_matrix(azim, elev).T
    u, v, depth = p[:, 0], p[:, 2], p[:, 1]

    s = max((u.max() - u.min()) / (W * (1 - 2 * margin)),
            (v.max() - v.min()) / (H * (1 - 2 * margin)))
    px = ((u - (u.max() + u.min()) / 2) / s + W / 2).astype(np.int32)
    py = (H / 2 - (v - (v.max() + v.min()) / 2) / s).astype(np.int32)

    d = (depth - depth.min()) / max(float(depth.max() - depth.min()), 1e-9)
    near = (0.45 + 0.55 * d).astype(np.float32)

    colour = ramp_fn(STOPS)(np.clip(speed / cap, 0, 1)) * boost

    # Brightest contributor wins the pixel, colour and all. Taking a per
    # channel maximum instead would blend a red track crossing a cyan one into
    # white, inventing a speed that is in neither of them. Sorting by weight and
    # scattering in that order makes NumPy's last-write-wins the depth test.
    r = int(np.ceil(radius * ss))
    offsets = [(ox, oy, float(np.exp(-(ox * ox + oy * oy) /
                                     (2 * (radius * ss / 1.5) ** 2))))
               for oy in range(-r, r + 1) for ox in range(-r, r + 1)]
    offsets = [o for o in offsets if o[2] >= 0.05]

    flat, wgt, src = [], [], []
    for ox, oy, fall in offsets:
        xx, yy = px + ox, py + oy
        keep = np.flatnonzero((xx >= 0) & (xx < W) & (yy >= 0) & (yy < H))
        flat.append(yy[keep].astype(np.int64) * W + xx[keep])
        wgt.append(near[keep] * fall)
        src.append(keep)
    flat, wgt, src = (np.concatenate(a) for a in (flat, wgt, src))

    order = np.argsort(wgt, kind="stable")
    flat, wgt, src = flat[order], wgt[order], src[order]

    canvas = np.zeros((H * W, 3), np.float32)
    canvas[flat] = colour[src] * wgt[:, None]
    acc = canvas.reshape(H, W, 3)

    acc = acc.reshape(h, ss, w, ss, 3).mean(axis=(1, 3))
    ground = np.array(BG, np.float32) / 255.0
    lum = acc.max(axis=2, keepdims=True)
    alpha = np.clip(lum * 3.0, 0, 1)
    tone = np.divide(acc, np.maximum(lum, 1e-6))
    rgb = ground * (1 - alpha) + np.clip(tone, 0, 1) * alpha
    return Image.fromarray((np.clip(rgb, 0, 1) * 255).astype(np.uint8), "RGB")


def annotate(img, mm_per_px, cap):
    """Flow-speed ramp and a scale bar, the two things the render cannot say."""
    d = ImageDraw.Draw(img)
    w, h = img.size
    try:
        f = ImageFont.truetype(FONT, max(11, w // 82))
    except OSError:
        f = ImageFont.load_default()
    ink, dim = (233, 241, 255), (150, 175, 210)

    bar_w, bar_h = max(10, w // 90), int(h * 0.30)
    bx, by = w - bar_w - int(w * 0.085), int(h * 0.10)
    ramp = ramp_fn(STOPS)
    for i in range(bar_h):
        c = ramp(np.array([1.0 - i / (bar_h - 1)]))[0]
        d.line([(bx, by + i), (bx + bar_w, by + i)],
               fill=tuple((c * 255).astype(int)))
    d.rectangle([bx, by, bx + bar_w, by + bar_h], outline=(90, 110, 150))
    d.text((bx + bar_w + 6, by - 6), f"{round(cap)}", font=f, fill=ink)
    d.text((bx + bar_w + 6, by + bar_h // 2 - 7), f"{round(cap / 2)}",
           font=f, fill=dim)
    d.text((bx + bar_w + 6, by + bar_h - 11), "0", font=f, fill=dim)
    d.text((bx + bar_w + 6, by + bar_h + 20), "mm/s", font=f, fill=dim)

    target = 10.0
    length = int(target / mm_per_px)
    sx, sy = w - int(w * 0.085) - length, h - int(h * 0.10)
    d.line([(sx, sy), (sx + length, sy)], fill=ink, width=max(2, h // 300))
    d.text((sx + length // 2, sy + 8), "10 mm", font=f, fill=dim, anchor="ma")
    return img


def mm_per_pixel(t, azim, elev, w, h, ss=2, margin=0.07):
    p = t.xyz @ view_matrix(azim, elev).T
    u, v = p[:, 0], p[:, 2]
    W, H = w * ss, h * ss
    s = max((u.max() - u.min()) / (W * (1 - 2 * margin)),
            (v.max() - v.min()) / (H * (1 - 2 * margin)))
    return s * ss


if __name__ == "__main__":
    import sys
    t = ulm_decode.load(TRACKS)
    az, el = (float(sys.argv[1]), float(sys.argv[2])) if len(sys.argv) > 2 else (35.0, 18.0)
    w, h = 1800, 1290
    im = render(t, az, el, w, h,
                speed=t.speed, cap=ulm_decode.RAMP_DIVISOR)
    im = annotate(im, mm_per_pixel(t, az, el, w, h),
                  ulm_decode.RAMP_TOP_MM_S)
    im.save("ulm_first_light.png")
    print("wrote ulm_first_light.png", im.size, "az", az, "el", el)
