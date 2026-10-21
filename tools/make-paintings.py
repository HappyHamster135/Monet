"""Paints "The Hours": Monet's wallpaper, one harbor in four lights.

After Claude Monet's "Impression, soleil levant" (1872): a misty harbor, small
boats, and one bright sun. Every painting uses the same brushstrokes in the
same places; only the light changes. That way the desktop can fade from one
hour to the next and it looks like the light moving, not a slideshow.

Run from the repository root:  python3 tools/make-paintings.py [--scale 0.5]
Needs Pillow and NumPy. Writes linux/share/wallpapers/Monet/contents/.
"""

import argparse
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "linux" / "share" / "wallpapers" / "Monet" / "contents"
HORIZON = 0.56


def rgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i : i + 2], 16) for i in (0, 2, 4)], dtype=np.float32) / 255


# Each hour: sky from top to horizon, water from horizon down, the light
# source (sun or moon), its reflection, and the color of things in the mist.
HOURS = {
    "dawn": dict(
        title="Impression, dawn",
        sky=[(0, "#5F7192"), (0.45, "#9C9DB4"), (0.8, "#D7B3AE"), (1, "#E8C0A4")],
        water=[(0, "#A3A2AE"), (0.25, "#7F8E9E"), (1, "#33495A")],
        light=dict(x=0.62, y=0.33, r=0.026, color="#F2552C", glow="#F59A6E", reach=0.30, strength=0.55),
        reflection="#F2662F",
        mist="#3E4B60",
        accent_sky="#B7A3C9",
        accent_water="#5C8C8A",
    ),
    "day": dict(
        title="Impression, midday",
        sky=[(0, "#6E9CCB"), (0.5, "#A8C6E0"), (0.85, "#E3E4DC"), (1, "#F1E7D1")],
        water=[(0, "#BFD3D3"), (0.2, "#93B6BC"), (1, "#3A6878")],
        light=dict(x=0.80, y=-0.12, r=0, color="#FFF6DE", glow="#FFF2D2", reach=0.75, strength=0.45),
        reflection="#FFF8E8",
        mist="#5A6E7E",
        accent_sky="#C9D9C0",
        accent_water="#6FA79A",
    ),
    "dusk": dict(
        title="Impression, dusk",
        sky=[(0, "#3F416F"), (0.4, "#8E6A93"), (0.75, "#E08D72"), (1, "#F5B062")],
        water=[(0, "#C98A72"), (0.2, "#8A6683"), (1, "#252749")],
        light=dict(x=0.34, y=0.47, r=0.034, color="#E33A22", glow="#F7934C", reach=0.38, strength=0.75),
        reflection="#F4A043",
        mist="#2D2742",
        accent_sky="#C77FA0",
        accent_water="#5B5A92",
    ),
    "night": dict(
        title="Impression, night",
        sky=[(0, "#0B1224"), (0.55, "#18264A"), (0.9, "#2F3A62"), (1, "#3A4570")],
        water=[(0, "#323D63"), (0.2, "#1F2A4A"), (1, "#080D1C")],
        light=dict(x=0.26, y=0.22, r=0.020, color="#F3ECD8", glow="#8CA2CC", reach=0.24, strength=0.38),
        reflection="#DCE2EE",
        mist="#060A15",
        accent_sky="#3C4F86",
        accent_water="#2C4A6E",
        harbor_lights=True,
    ),
}


def gradient(stops, n):
    pos = np.array([p for p, _ in stops], dtype=np.float32)
    cols = np.stack([rgb(c) for _, c in stops])
    t = np.linspace(0, 1, n)
    return np.stack([np.interp(t, pos, cols[:, i]) for i in range(3)], axis=1)


def smooth_noise(rng, w, h, cell):
    """Low-frequency noise in [-1, 1]: random values on a coarse grid, enlarged smoothly."""
    gw, gh = max(2, w // cell + 2), max(2, h // cell + 2)
    grid = rng.uniform(-1, 1, (gh, gw)).astype(np.float32)
    img = Image.fromarray(((grid + 1) * 127.5).astype(np.uint8), "L")
    img = img.resize((gw * cell, gh * cell), Image.BICUBIC).crop((0, 0, w, h))
    return np.asarray(img).astype(np.float32) / 127.5 - 1


def light_field(hour, w, h, noise_a, noise_b):
    """The underpainting: smooth color everywhere, before any brushstroke."""
    hz = int(h * HORIZON)
    sky = gradient(hour["sky"], hz)
    water = gradient(hour["water"], h - hz)
    field = np.repeat(np.concatenate([sky, water])[:, None, :], w, axis=1)

    # The glow of the sun (or moon), and its glow on the water.
    L = hour["light"]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    lx, ly = L["x"] * w, L["y"] * h
    d = np.hypot(xx - lx, (yy - ly) * 1.25) / (L["reach"] * h)
    glow = np.exp(-(d**2) * 1.6)[..., None] * L["strength"]
    field = field * (1 - glow) + rgb(L["glow"]) * glow

    below = yy > hz
    dx = np.abs(xx - lx) / (w * (0.05 + 0.25 * np.clip((yy - hz) / (h - hz), 0, 1)))
    col = np.exp(-(dx**2)) * np.clip(1 - (yy - hz) / (h - hz) * 0.6, 0, 1) * L["strength"] * 0.9
    col = np.where(below, col, 0)[..., None]
    field = field * (1 - col) + rgb(L["glow"]) * col

    # Mist hugging the horizon.
    haze = np.exp(-(((yy - hz) / (h * 0.06)) ** 2))[..., None] * 0.35
    field = field * (1 - haze) + field.mean(axis=(0, 1)) * haze

    # Mottled paint, so no area is a flat gradient.
    field *= 1 + 0.05 * noise_a[..., None]
    field += 0.025 * noise_b[..., None] * np.array([0.6, -0.2, 0.8])
    return np.clip(field, 0, 1)


def stroke_polygon(cx, cy, length, width, angle, bend):
    """Outline of a tapered brushstroke with rounded ends and a slight curve."""
    ca, sa = math.cos(angle), math.sin(angle)
    top, bottom = [], []
    for i in range(13):
        t = -1 + 2 * i / 12
        half = width / 2 * math.sqrt(max(0.0, 1 - t**6)) * (1 - 0.25 * t)
        along = t * length / 2
        off = bend * (1 - t * t) * length * 0.12
        for sign, side in ((1, top), (-1, bottom)):
            px = along
            py = off + sign * half
            side.append((cx + px * ca - py * sa, cy + px * sa + py * ca))
    return top + bottom[::-1]


class Brushwork:
    """The strokes of one painting. Built once, drawn in each hour's colors."""

    def __init__(self, w, h, seed=1872):
        self.w, self.h = w, h
        self.hz = int(h * HORIZON)
        self.rng = np.random.default_rng(seed)
        self.s = w / 3840
        self.strokes = []
        # Broad, thin strokes blend the underpainting; smaller ones on top
        # give the surface its texture.
        self._sky(step=70, size=2.2, alpha=(0.18, 0.34))
        self._water(step=11, size=1.9, alpha=(0.20, 0.38))
        self._sky(step=40, size=1.0, alpha=(0.28, 0.55))
        self._water(step=6.5, size=1.0, alpha=(0.32, 0.62))

    def _add(self, layer, cx, cy, length, width, angle, bend, jitter, alpha, tint, offset):
        self.strokes.append((layer, cx, cy, length, width, angle, bend, jitter, alpha, tint, offset))

    def _sky(self, step, size, alpha):
        rng, s = self.rng, self.s
        step *= s
        y = 0.0
        while y < self.hz + 10 * s:
            x = -60 * s + rng.uniform(0, step)
            while x < self.w + 60 * s:
                cy = y + rng.normal(0, step * 0.35)
                # Long, loose strokes high up; shorter and flatter near the horizon.
                depth = min(1.0, max(cy, 0) / self.hz) if self.hz else 1
                length = rng.uniform(60, 200) * s * size * (1.2 - 0.5 * depth)
                width = rng.uniform(12, 26) * s * size * (1.1 - 0.45 * depth)
                swirl = math.sin(x / (900 * s) + cy / (500 * s)) * 0.22
                angle = (rng.normal(-0.08, 0.16) + swirl) * (1 - depth * 0.85)
                self._add("sky", x, cy, length, width, angle, rng.normal(0, 0.5),
                          rng.normal(0, 1, 3), rng.uniform(*alpha),
                          rng.random() < 0.07, rng.normal(0, 22 * s, 2))
                x += length * rng.uniform(0.5, 0.85)
            y += step * rng.uniform(0.55, 0.8)

    def _water(self, step, size, alpha):
        rng, s = self.rng, self.s
        y = float(self.hz)
        while y < self.h + 20 * s:
            depth = (y - self.hz) / (self.h - self.hz)
            # Strokes grow as the water comes closer.
            grow = (0.35 + 1.4 * depth) * size
            x = -80 * s + rng.uniform(0, 80 * s)
            while x < self.w + 80 * s:
                length = rng.uniform(60, 150) * s * grow
                width = rng.uniform(6, 11) * s * grow
                self._add("water", x, y + rng.normal(0, 3 * s * grow), length, width,
                          rng.normal(0, 0.02), rng.normal(0, 0.22),
                          rng.normal(0, 1, 3), rng.uniform(*alpha),
                          rng.random() < 0.08, rng.normal(0, 10 * s, 2) * np.array([3, 0.4]))
                x += length * rng.uniform(0.55, 0.9)
            y += rng.uniform(0.8, 1.2) * step * s * (0.35 + 1.4 * depth)


def shade(color, jitter, amount):
    c = color * (1 + jitter[0] * amount) + jitter * amount * 0.12
    return np.clip(c, 0, 1)


def to255(c, alpha):
    return tuple(int(v * 255) for v in c) + (int(alpha * 255),)


def paint(hour, brushwork, noise):
    w, h, s, hz = brushwork.w, brushwork.h, brushwork.s, brushwork.hz
    field = light_field(hour, w, h, *noise)
    base = Image.fromarray((field * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6 * s))
    canvas = base.convert("RGBA")
    draw = ImageDraw.Draw(canvas, "RGBA")

    def sample(x, y):
        xi = int(min(max(x, 0), w - 1))
        yi = int(min(max(y, 0), h - 1))
        return field[yi, xi]

    accents = {"sky": rgb(hour["accent_sky"]), "water": rgb(hour["accent_water"])}
    rng = np.random.default_rng(7)

    for kind, cx, cy, length, width, angle, bend, jitter, alpha, tint, offset in brushwork.strokes:
        # Keep sky strokes above the water and the other way around.
        if kind == "sky":
            cy = min(cy, hz - width * 0.3)
        color = sample(cx + offset[0], cy + offset[1])
        color = shade(color, jitter, 0.035)
        if tint:
            color = color * 0.82 + accents[kind] * 0.18
        if kind == "water":
            # Ripples: alternate light and dark bands.
            ripple = math.sin(cy / (9 * s) + cx / (400 * s)) * 0.04
            color = np.clip(color * (1 + ripple), 0, 1)
        poly = stroke_polygon(cx, cy, length, width, angle, bend)
        draw.polygon(poly, fill=to255(color, alpha))
        # Bristle marks: two faint streaks along the stroke.
        if length > 40 * s:
            for k in (-0.22, 0.24):
                c2 = np.clip(color * (1 + k * 0.25), 0, 1)
                ox, oy = -math.sin(angle) * width * k, math.cos(angle) * width * k
                inner = stroke_polygon(cx + ox, cy + oy, length * 0.8, width * 0.18, angle, bend)
                draw.polygon(inner, fill=to255(c2, alpha * 0.35))

    # Soften the strokes a little, like wet paint pulled together.
    soft = canvas.filter(ImageFilter.GaussianBlur(3 * s))
    canvas = Image.blend(canvas, soft, 0.35)

    p = Painter(canvas)
    harbor(p, hour, w, h, hz, s)
    halo(p, hour, w, h, s)
    light_and_reflection(p, hour, w, h, hz, s, rng)
    boats(p, hour, w, h, s)
    if hour.get("harbor_lights"):
        harbor_lights(p, w, h, hz, s, rng)

    img = p.canvas.convert("RGB").filter(ImageFilter.GaussianBlur(0.6 * s))
    return grain(img, s)


class Painter:
    """Lays soft, semi-transparent shapes over the canvas one at a time.

    Each shape is drawn as its own small patch, blurred, and composited, so
    overlapping strokes mix the way glazes do, without dark fringes.
    """

    def __init__(self, canvas):
        self.canvas = canvas

    def shape(self, points, color, alpha, blur=0.0, ellipse=None):
        if ellipse:
            x0, y0, x1, y1 = ellipse
        else:
            xs = [x for x, _ in points]
            ys = [y for _, y in points]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        pad = int(blur * 3) + 2
        left, top = int(math.floor(x0)) - pad, int(math.floor(y0)) - pad
        right, bottom = int(math.ceil(x1)) + pad, int(math.ceil(y1)) + pad
        cw, ch = self.canvas.size
        if right <= 0 or bottom <= 0 or left >= cw or top >= ch:
            return
        mask = Image.new("L", (right - left, bottom - top), 0)
        d = ImageDraw.Draw(mask)
        if ellipse:
            d.ellipse((x0 - left, y0 - top, x1 - left, y1 - top), fill=int(255 * alpha))
        else:
            d.polygon([(x - left, y - top) for x, y in points], fill=int(255 * alpha))
        if blur > 0.3:
            mask = mask.filter(ImageFilter.GaussianBlur(blur))
        patch = Image.new("RGBA", mask.size, tuple(int(c * 255) for c in np.clip(color, 0, 1)) + (0,))
        patch.putalpha(mask)
        # Clip the patch to the canvas.
        cl, ct = max(left, 0), max(top, 0)
        patch = patch.crop((cl - left, ct - top, min(right, cw) - left, min(bottom, ch) - top))
        self.canvas.alpha_composite(patch, (cl, ct))

    def stroke(self, cx, cy, length, width, angle, bend, color, alpha, blur):
        self.shape(stroke_polygon(cx, cy, length, width, angle, bend), color, alpha, blur)

    def dot(self, x, y, r, color, alpha, blur):
        self.shape(None, color, alpha, blur, ellipse=(x - r, y - r, x + r, y + r))


def harbor(p, hour, w, h, hz, s):
    """Masts, cranes and smoke dissolving in the mist along the horizon."""
    rng = np.random.default_rng(11)
    mist = rgb(hour["mist"])
    haze = rgb(hour["sky"][2][1])
    for x0, x1, count in ((0.02, 0.27, 13), (0.72, 0.99, 11)):
        # Hulls and warehouses: low, soft shapes on the waterline.
        x = x0 * w
        while x < x1 * w:
            bw = rng.uniform(90, 220) * s
            bh = rng.uniform(12, 34) * s
            p.stroke(x + bw / 2, hz - bh * 0.35, bw, bh, rng.normal(0, 0.01), 0,
                     mist * 0.8 + haze * 0.2, rng.uniform(0.16, 0.30), 3 * s)
            x += bw * rng.uniform(0.6, 1.2)
        for _ in range(count):
            x = (x0 + (x1 - x0) * rng.beta(1.6, 1.6)) * w
            tall = rng.uniform(0.04, 0.17) * h
            # Opaque but pale: far away things lose their darkness, not their body.
            fade = rng.uniform(0.25, 0.6)
            color = mist * (1 - fade) + haze * fade
            p.stroke(x, hz - tall / 2, tall, rng.uniform(6, 10) * s, math.pi / 2 + rng.normal(0, 0.02),
                     rng.normal(0, 0.15), color, rng.uniform(0.55, 0.8), 2.4 * s)
            if rng.random() < 0.35:
                y = hz - tall * rng.uniform(0.55, 0.85)
                p.stroke(x + rng.normal(0, 6 * s), y, tall * rng.uniform(0.15, 0.3), 5 * s,
                         rng.normal(0, 0.12), 0, color, 0.5, 2 * s)
    # Smoke drifting up from the chimneys on the right.
    for chimney in (0.80, 0.88):
        x, y = chimney * w, hz - rng.uniform(0.10, 0.14) * h
        for i in range(22):
            x += rng.uniform(6, 16) * s
            y -= rng.uniform(5, 11) * s
            r = (16 + i * 4) * s
            p.stroke(x, y, r * 2.6, r, rng.normal(-0.35, 0.2), rng.normal(0, 0.5),
                     mist * 0.5 + haze * 0.5, 0.10 * (1 - i / 26), 8 * s)


def halo(p, hour, w, h, s):
    L = hour["light"]
    if L["r"] <= 0:
        return
    r = L["r"] * h
    p.dot(L["x"] * w, L["y"] * h, r * 2.4, rgb(L["color"]), 0.30, 34 * s)


def light_and_reflection(p, hour, w, h, hz, s, rng):
    L = hour["light"]
    lx, ly = L["x"] * w, L["y"] * h
    refl = rgb(hour["reflection"])
    # The reflection: broken horizontal dabs, wider and sparser toward us.
    y = hz + 4 * s
    while y < h:
        depth = (y - hz) / (h - hz)
        wide = 1.8 if L["r"] == 0 else 1
        spread = (0.010 + 0.075 * depth) * w * wide
        dabs = int(2 + 4 * (1 - depth) * (2.5 if L["r"] == 0 else 1))
        for _ in range(dabs):
            if rng.random() < 0.3 + depth * 0.35:
                continue
            x = lx + rng.normal(0, spread * 0.45)
            length = rng.uniform(24, 80) * s * (0.5 + 1.3 * depth)
            width = rng.uniform(4, 8) * s * (0.5 + 1.1 * depth)
            alpha = (0.85 - 0.55 * depth) * rng.uniform(0.6, 1)
            p.stroke(x, y, length, width, rng.normal(0, 0.03), rng.normal(0, 0.2),
                     refl * rng.uniform(0.92, 1.06), alpha, 1.0 * s)
        y += rng.uniform(7, 14) * s * (0.6 + 1.5 * depth)

    if L["r"] <= 0:
        return
    # The disc, painted a touch unevenly.
    r = L["r"] * h
    col = rgb(L["color"])
    p.dot(lx, ly, r, col, 0.97, 1.2 * s)
    for _ in range(8):
        a = rng.uniform(0, 2 * math.pi)
        p.stroke(lx + math.cos(a) * r * 0.82, ly + math.sin(a) * r * 0.82, r * 0.8, r * 0.3,
                 a + math.pi / 2, 0, col * 1.04, 0.5, 1.2 * s)


def boats(p, hour, w, h, s):
    """Three rowboats with a standing rower, the closest large and dark, after the painting."""
    rng = np.random.default_rng(3)
    mist = rgb(hour["mist"])
    rim = rgb(hour["reflection"])
    for bx, by, size, a in ((0.25, 0.80, 1.2, 0.92), (0.41, 0.695, 0.62, 0.74), (0.13, 0.66, 0.42, 0.52)):
        x, y = bx * w, by * h
        k = s * size
        L = 250 * k
        soft = 2.2 * k
        # Hull: two overlapping dark dabs, the ends lifted, light catching the rim.
        p.stroke(x, y, L, 36 * k, -0.03, 0.9, mist, a, soft)
        p.stroke(x - L * 0.06, y + 8 * k, L * 0.8, 22 * k, -0.02, 0.6, mist * 0.85, a * 0.8, soft)
        p.stroke(x + L * 0.05, y - 14 * k, L * 0.6, 4 * k, -0.04, 0.4, rim, 0.07 * a, 3 * k)
        # The rower: one leaning stroke for the body, a smaller one for the head.
        fx = x + L * 0.24
        p.stroke(fx, y - 60 * k, 98 * k, 24 * k, math.pi / 2 + 0.16, 0.5, mist, a, soft)
        p.stroke(fx - 5 * k, y - 118 * k, 26 * k, 19 * k, math.pi / 2 + 0.2, 0.2, mist, a, soft)
        # The oar, a long thin stroke dipping into the water.
        p.stroke(fx + 38 * k, y - 22 * k, 210 * k, 5 * k, 1.12, 0.1, mist, a * 0.85, 1.2 * k)
        # A passenger: a low, rounded mass in the front.
        px, py = x - L * 0.17, y - 26 * k
        p.shape(None, mist, a, soft, ellipse=(px - 24 * k, py - 22 * k, px + 22 * k, py + 20 * k))
        p.dot(px - 2 * k, py - 30 * k, 12 * k, mist, a, soft)
        # Its reflection, broken by ripples.
        for i in range(7):
            p.stroke(x + rng.normal(0, L * 0.1), y + (30 + i * 14) * k,
                     L * rng.uniform(0.4, 0.9) * (1 - i * 0.09), 11 * k, 0, 0,
                     mist, a * (0.36 - i * 0.045), 2.5 * k)


def harbor_lights(p, w, h, hz, s, rng):
    warm = rgb("#FFB766")
    for x0, x1, n in ((0.04, 0.30, 9), (0.70, 0.97, 8)):
        for _ in range(n):
            x = rng.uniform(x0, x1) * w
            y = hz - rng.uniform(4, 40) * s
            r = rng.uniform(2.5, 4.5) * s
            p.dot(x, y, r * 4, warm, 0.22, 6 * s)
            p.dot(x, y, r, warm, 0.95, 0.8 * s)
            for i in range(5):
                p.stroke(x + rng.normal(0, 4 * s), hz + (10 + i * 14) * s, rng.uniform(14, 34) * s, 3.5 * s, 0, 0,
                         warm, 0.55 - i * 0.09, 1.2 * s)


def grain(img, s):
    """Canvas texture: fine noise, a little stronger in the shadows."""
    rng = np.random.default_rng(5)
    arr = np.asarray(img).astype(np.float32)
    n = rng.normal(0, 3.2, arr.shape[:2]).astype(np.float32)[..., None]
    weave = (np.sin(np.arange(arr.shape[1]) * 1.9 / max(s, 0.25))[None, :, None]
             * np.sin(np.arange(arr.shape[0]) * 1.7 / max(s, 0.25))[:, None, None]) * 1.4
    lum = arr.mean(axis=2, keepdims=True) / 255
    arr = arr + (n + weave) * (1.15 - lum * 0.5)
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def render(scale=1.0, only=None):
    w, h = int(3840 * scale), int(2160 * scale)
    brushwork = Brushwork(w, h)
    rng = np.random.default_rng(99)
    noise = (smooth_noise(rng, w, h, int(260 * scale) or 1), smooth_noise(rng, w, h, int(120 * scale) or 1))
    out = {}
    for name, hour in HOURS.items():
        if only and name not in only:
            continue
        out[name] = paint(hour, brushwork, noise)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--only", nargs="*")
    args = ap.parse_args()
    paintings = render(args.scale, args.only)
    hours = args.out / "hours"
    hours.mkdir(parents=True, exist_ok=True)
    for name, img in paintings.items():
        img.save(hours / f"{name}.jpg", quality=90, optimize=True, progressive=True, subsampling=0)
        print("painted", hours / f"{name}.jpg")


if __name__ == "__main__":
    main()
