"""Renders Monet's raster branding: wallpapers, the Windows icon file, and PNG logos.

Run from the repository root:  python3 tools/make-branding.py
Needs Pillow and NumPy.
"""

from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "branding"
WALL = ROOT / "linux" / "share" / "wallpapers" / "Monet" / "contents"
W, H = 3840, 2160
HORIZON = 0.58


def hex_rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32)


def vertical(stops, height):
    """Linear gradient through (position, color) stops, one row per pixel."""
    pos = np.array([p for p, _ in stops])
    cols = np.stack([hex_rgb(c) for _, c in stops])
    t = np.linspace(0, 1, height)
    return np.stack([np.interp(t, pos, cols[:, i]) for i in range(3)], axis=1)


def soft_blur(layer, radius):
    """Gaussian blur for RGBA without dark fringes (blurs premultiplied color)."""
    arr = np.asarray(layer).astype(np.float32) / 255
    alpha = arr[..., 3:4]
    premul = Image.fromarray(((arr[..., :3] * alpha) * 255).astype(np.uint8))
    a = Image.fromarray((alpha[..., 0] * 255).astype(np.uint8))
    premul = np.asarray(premul.filter(ImageFilter.GaussianBlur(radius))).astype(np.float32) / 255
    a = np.asarray(a.filter(ImageFilter.GaussianBlur(radius))).astype(np.float32)[..., None] / 255
    rgb = np.where(a > 1e-4, premul / np.maximum(a, 1e-4), 0)
    out = np.concatenate([np.clip(rgb, 0, 1), a], axis=2)
    return Image.fromarray((out * 255).astype(np.uint8), "RGBA")


def wallpaper(dark, seed=7):
    rng = np.random.default_rng(seed)
    if dark:
        sky = [(0.0, "#141B2E"), (0.7, "#2C3352"), (1.0, "#6B4A55")]
        water = [(0.0, "#22304F"), (1.0, "#0C1222")]
        sun, glow_strength = hex_rgb("#E07A3A"), 0.55
    else:
        sky = [(0.0, "#9DB3DF"), (0.65, "#D9C3D6"), (1.0, "#F4CDB8")]
        water = [(0.0, "#7E98CB"), (1.0, "#2E4A7E")]
        sun, glow_strength = hex_rgb("#F28A3C"), 0.8

    hz = int(H * HORIZON)
    rows = np.concatenate([vertical(sky, hz), vertical(water, H - hz)])
    img = np.repeat(rows[:, None, :], W, axis=1)

    # Soft glow around the sun.
    sx, sy, r = W * 0.62, hz - H * 0.13, H * 0.075
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    d = np.sqrt((xx - sx) ** 2 + ((yy - sy) * 1.15) ** 2)
    glow = np.exp(-((d / (r * 4.5)) ** 2)) * glow_strength
    img = img * (1 - glow[..., None] * 0.6) + sun * glow[..., None] * 0.6
    base = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))

    # Impressionist strokes: short horizontal dabs on the water, brighter
    # under the sun as its reflection.
    strokes = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(strokes)
    for _ in range(2600):
        y = rng.uniform(hz + 8, H)
        depth = (y - hz) / (H - hz)
        x = rng.normal(sx, W * (0.05 + 0.25 * depth)) if rng.random() < 0.45 else rng.uniform(0, W)
        length = rng.uniform(60, 260) * (0.5 + depth)
        thick = rng.uniform(4, 12) * (0.6 + depth)
        near_sun = np.exp(-(((x - sx) / (W * 0.08 + depth * W * 0.1)) ** 2))
        if rng.random() < near_sun:
            color = tuple(int(c) for c in sun) + (int(rng.uniform(70, 150)),)
        else:
            tint = hex_rgb("#C9D6F0" if not dark else "#4A5A86") + rng.normal(0, 12, 3)
            color = tuple(int(np.clip(c, 0, 255)) for c in tint) + (int(rng.uniform(25, 70)),)
        draw.rounded_rectangle([x - length / 2, y - thick / 2, x + length / 2, y + thick / 2], radius=thick / 2, fill=color)
    for _ in range(500):
        # Lighter dabs in the sky.
        y = rng.uniform(0, hz - 20)
        x = rng.uniform(0, W)
        length, thick = rng.uniform(80, 300), rng.uniform(6, 16)
        tint = hex_rgb("#FFFFFF" if not dark else "#5E6A95") + rng.normal(0, 10, 3)
        color = tuple(int(np.clip(c, 0, 255)) for c in tint) + (int(rng.uniform(10, 26)),)
        draw.rounded_rectangle([x - length / 2, y - thick / 2, x + length / 2, y + thick / 2], radius=thick / 2, fill=color)
    strokes = soft_blur(strokes, 2.5)
    base = Image.alpha_composite(base.convert("RGBA"), strokes)

    # The sun itself.
    disc = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(disc).ellipse([sx - r, sy - r, sx + r, sy + r], fill=tuple(int(c) for c in sun) + (235,))
    base = Image.alpha_composite(base, soft_blur(disc, 3))

    # A little grain keeps the gradients from banding.
    arr = np.asarray(base.convert("RGB")).astype(np.float32)
    arr += rng.normal(0, 2.2, arr.shape)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def rounded_gradient(size, top, bottom, split=None, top2=None, bottom2=None):
    s = size * 4
    rows = vertical([(0, top), (1, bottom)], s)
    if split is not None:
        cut = int(s * split)
        rows = np.concatenate([vertical([(0, top), (1, bottom)], cut), vertical([(0, top2), (1, bottom2)], s - cut)])
    img = Image.fromarray(np.repeat(rows[:, None, :], s, axis=1).astype(np.uint8)).convert("RGBA")
    mask = Image.new("L", (s, s), 0)
    m = int(s * 4 / 128)
    ImageDraw.Draw(mask).rounded_rectangle([m, m, s - m, s - m], radius=int(s * 28 / 128), fill=255)
    img.putalpha(mask)
    return img


def logo(size):
    """Raster version of branding/monet.svg."""
    img = rounded_gradient(size, "#9DB3DF", "#F1C7B8", 0.55, "#6F8CC4", "#2E4A7E")
    s = img.width / 128
    d = ImageDraw.Draw(img)
    orange = (242, 138, 60)
    d.ellipse([(64 - 15) * s, (52 - 15) * s, (64 + 15) * s, (52 + 15) * s], fill=orange + (255,))
    for x, y, w, h, a in [(42, 80, 44, 5, 230), (49, 92, 30, 4, 180), (56, 102, 16, 3, 128)]:
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(overlay).rounded_rectangle([x * s, y * s, (x + w) * s, (y + h) * s], radius=h / 2 * s, fill=orange + (a,))
        img = Image.alpha_composite(img, overlay)
    return img.resize((size, size), Image.LANCZOS)


def main():
    for dark, folder in [(False, "images"), (True, "images_dark")]:
        path = WALL / folder / f"{W}x{H}.jpg"
        path.parent.mkdir(parents=True, exist_ok=True)
        wallpaper(dark).save(path, quality=88, optimize=True, progressive=True)
        print("wrote", path.relative_to(ROOT))

    big = logo(512)
    big.save(OUT / "monet-512.png")
    big.save(ROOT / "windows" / "monet.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    wallpaper(False).resize((1280, 720), Image.LANCZOS).save(OUT / "wallpaper-preview.jpg", quality=85)
    print("wrote branding/monet-512.png, windows/monet.ico, branding/wallpaper-preview.jpg")


if __name__ == "__main__":
    main()
