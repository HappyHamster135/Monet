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
    hz = int(h * hour.get("horizon", HORIZON))
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

    def __init__(self, w, h, seed=1872, horizon=HORIZON):
        self.w, self.h = w, h
        self.hz = int(h * horizon)
        self.rng = np.random.default_rng(seed)
        self.s = w / 3840
        self.strokes = []
        # Broad, thin strokes blend the underpainting; smaller ones on top
        # give the surface its texture. A pond seen from above has no sky.
        if self.hz > 0:
            self._sky(step=84, size=2.6, alpha=(0.22, 0.4))
        self._water(step=16, size=1.9, alpha=(0.20, 0.38))
        if self.hz > 0:
            self._sky(step=62, size=1.5, alpha=(0.28, 0.55))
        self._water(step=10, size=1.0, alpha=(0.32, 0.62))

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
                width = rng.uniform(18, 38) * s * size * (1.1 - 0.45 * depth)
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
                length = rng.uniform(60, 140) * s * grow * (1 + 1.6 * rng.random() ** 3)  # now and then a long sweep
                width = rng.uniform(12, 22) * s * grow
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


def paint(hour, brushwork, noise, scene=None):
    w, h, s, hz = brushwork.w, brushwork.h, brushwork.s, brushwork.hz
    field = light_field(hour, w, h, *noise)
    base = Image.fromarray((field * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6 * s))
    canvas = base.convert("RGBA")

    def sample(x, y):
        xi = int(min(max(x, 0), w - 1))
        yi = int(min(max(y, 0), h - 1))
        return field[yi, xi]

    accents = {"sky": rgb(hour["accent_sky"]), "water": rgb(hour["accent_water"])}
    rng = np.random.default_rng(7)

    p = Painter(canvas)
    for kind, cx, cy, length, width, angle, bend, jitter, alpha, tint, offset in brushwork.strokes:
        # Keep sky strokes above the water and the other way around.
        if kind == "sky":
            cy = min(cy, hz - width * 0.3)
        color = sample(cx + offset[0], cy + offset[1])
        color = shade(color, jitter, 0.06)  # each stroke a note of its own, the way a brush picks up paint
        if tint:
            color = color * 0.82 + accents[kind] * 0.18
        if kind == "water":
            # Ripples: alternate light and dark bands.
            ripple = math.sin(cy / (9 * s) + cx / (400 * s)) * hour.get("ripple", 0.04)
            color = np.clip(color * (1 + ripple), 0, 1)
        # Every other stroke pulled the other way, so the brush's dry ends don't all fall on one side.
        p.lay(cx, cy, length, width, angle + (math.pi if bend > 0 else 0), color, alpha, 0.1 if kind == "sky" else 0.12)

    # Soften the strokes a little, like wet paint pulled together.
    soft = p.canvas.filter(ImageFilter.GaussianBlur(3 * s))
    p.canvas = Image.blend(p.canvas, soft, 0.08)

    (scene or harbor_scene)(p, hour, w, h, hz, s, rng)

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

    def lay(self, x, y, length, width, angle, color, alpha, streak=0.1):
        """One stroke of a loaded flat brush centered at (x, y): its bristles streak it, its tail breaks up."""
        if length < 1 or width < 1:
            return
        bank = bristles()
        mask, tone = bank[int(abs(x * 7.31 + y * 3.17)) % len(bank)]  # the same stamp wherever the stroke repeats
        ca, sa = math.cos(angle), math.sin(angle)
        hx, hy = abs(ca) * length / 2 + abs(sa) * width / 2 + 2, abs(sa) * length / 2 + abs(ca) * width / 2 + 2
        left, top = int(math.floor(x - hx)), int(math.floor(y - hy))
        size = (int(math.ceil(x + hx)) - left, int(math.ceil(y + hy)) - top)
        cw, ch = self.canvas.size
        if left + size[0] <= 0 or top + size[1] <= 0 or left >= cw or top >= ch:
            return
        # Each pixel of the patch, turned back into the stamp: along the stroke and across it.
        kx, ky, dx, dy = mask.width / length, mask.height / width, left - x, top - y
        data = (ca * kx, sa * kx, (dx * ca + dy * sa) * kx + mask.width / 2,
                -sa * ky, ca * ky, (dy * ca - dx * sa) * ky + mask.height / 2)
        a = np.asarray(mask.transform(size, Image.AFFINE, data, Image.BILINEAR), np.float32) * alpha
        t = np.asarray(tone.transform(size, Image.AFFINE, data, Image.BILINEAR, fillcolor=128), np.float32) / 128 - 1
        rgb = np.clip(np.asarray(color, np.float32) * (1 + streak * t[..., None]), 0, 1) * 255
        patch = Image.fromarray(np.dstack([rgb, a]).astype(np.uint8), "RGBA")
        cl, ct = max(left, 0), max(top, 0)
        patch = patch.crop((cl - left, ct - top, min(left + size[0], cw) - left, min(top + size[1], ch) - top))
        self.canvas.alpha_composite(patch, (cl, ct))


BANK = []


def bristles(n=8, length=320, width=64):
    """Stamps of a loaded flat brush: eighteen bristles side by side, each laying its own streak and running
    dry at its own point, so the tail of a stroke breaks up. Each is (alpha, tone), the tone 128 where even."""
    if BANK:
        return BANK
    rng = np.random.default_rng(1868)
    t = np.linspace(0, 1, length, dtype=np.float32)[None, :]
    v = np.linspace(-1, 1, width, dtype=np.float32)[:, None]
    for _ in range(n):
        alpha = np.zeros((width, length), np.float32)
        tone = np.zeros((width, length), np.float32)
        bow = rng.uniform(-0.4, 0.4) * t * (1 - t)  # the hand swings: some strokes curve a little
        for c in np.linspace(-0.88, 0.88, 18) + rng.normal(0, 0.03, 18):
            # The outer bristles touch down later and lift sooner: a rounded head, a tapering tail.
            start, end = rng.uniform(0, 0.05) + 0.14 * c * c, 1 - rng.uniform(0, 0.28) - 0.22 * c * c
            thick, load, shade = rng.uniform(0.11, 0.16), rng.uniform(0.75, 1.0), rng.normal(0, 1)
            wander = np.interp(t[0], np.linspace(0, 1, 6), rng.normal(0, 0.03, 6))[None, :]
            dry = np.interp(t[0], np.linspace(0, 1, 24), rng.uniform(0, 1, 24))[None, :]
            run = np.clip((t - start) * 30, 0, 1) * np.clip((end - t) * 8, 0, 1)
            run *= np.clip((dry - (t - 0.55) * 1.8) * 3, 0, 1)  # skips, more of them toward the tail
            a = np.exp(-(((v - c - wander - bow) / thick) ** 2)) * run * load
            alpha += a
            tone += a * shade
        tone /= alpha + 1e-6
        BANK.append((Image.fromarray((np.clip(alpha * 1.8, 0, 1) * 255).astype(np.uint8), "L"),
                     Image.fromarray((np.clip(tone, -1, 1) * 127 + 128).astype(np.uint8), "L")))
    return BANK


def harbor_scene(p, hour, w, h, hz, s, rng):
    """The Hours: the harbor, the sun and its reflection, the boats."""
    harbor(p, hour, w, h, hz, s)
    halo(p, hour, w, h, s)
    light_and_reflection(p, hour, w, h, hz, s, rng)
    boats(p, hour, w, h, s)
    if hour.get("harbor_lights"):
        harbor_lights(p, w, h, hz, s, rng)


def harbor(p, hour, w, h, hz, s):
    """Masts, cranes and smoke dissolving in the mist along the horizon."""
    rng = np.random.default_rng(11)
    mist = rgb(hour["mist"])
    haze = rgb(hour["sky"][2][1])
    for x0, x1, count in ((0.02, 0.27, 13), (0.72, 0.99, 11)):
        # Hulls and warehouses: low strokes along the waterline.
        x = x0 * w
        while x < x1 * w:
            bw = rng.uniform(90, 220) * s
            bh = rng.uniform(12, 34) * s
            p.lay(x + bw / 2, hz - bh * 0.35, bw, bh, rng.normal(0, 0.01) + (math.pi if bh > 23 * s else 0),
                  mist * 0.8 + haze * 0.2, rng.uniform(0.2, 0.36), 0.1)
            x += bw * rng.uniform(0.6, 1.2)
        for _ in range(count):
            x = (x0 + (x1 - x0) * rng.beta(1.6, 1.6)) * w
            tall = rng.uniform(0.04, 0.17) * h
            # Opaque but pale: far away things lose their darkness, not their body.
            fade = rng.uniform(0.25, 0.6)
            color = mist * (1 - fade) + haze * fade
            # A soft stroke for its body, then the brush pulled up it from the water, running dry at the top.
            width, lean, bend, alpha = rng.uniform(6, 10) * s, rng.normal(0, 0.02), rng.normal(0, 0.15), \
                rng.uniform(0.55, 0.8)
            p.stroke(x, hz - tall / 2, tall, width, math.pi / 2 + lean, bend, color, alpha * 0.6, 2.4 * s)
            dx = math.sin(lean) * tall / 2
            sweep(p, x - dx, hz + 2 * s, x + dx, hz - tall, width + 2 * s, color, alpha, 0.1)
            if rng.random() < 0.35:
                y = hz - tall * rng.uniform(0.55, 0.85)
                p.lay(x + rng.normal(0, 6 * s), y, tall * rng.uniform(0.15, 0.3), 6 * s,
                      rng.normal(0, 0.12), color, 0.55, 0.1)
    # Smoke drifting up from the chimneys on the right.
    for chimney in (0.80, 0.88):
        x, y = chimney * w, hz - rng.uniform(0.10, 0.14) * h
        for i in range(22):
            x += rng.uniform(6, 16) * s
            y -= rng.uniform(5, 11) * s
            r = (16 + i * 4) * s
            p.lay(x, y, r * 2.6, r, rng.normal(-0.35, 0.2) + (math.pi if rng.normal(0, 0.5) > 0 else 0),
                  mist * 0.5 + haze * 0.5, 0.18 * (1 - i / 26), 0.08)


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
    # The reflection: broken horizontal dabs of a loaded brush, wider and sparser toward us.
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
            length = rng.uniform(26, 80) * s * (0.5 + 1.3 * depth)
            width = rng.uniform(9, 17) * s * (0.5 + 1.1 * depth)
            alpha = (0.95 - 0.5 * depth) * rng.uniform(0.6, 1)
            # Thick dabs, some paler where the paint was loaded with white, some sunk into the water's color.
            tone, flip = rng.random(2)
            color = mix(refl, np.ones(3), 0.35) if tone > 0.8 else mix(refl, rgb(hour["water"][1][1]), 0.35) \
                if tone < 0.2 else refl * (0.9 + 0.15 * tone)
            p.lay(x, y, length, width, rng.normal(0, 0.03) + (math.pi if flip < 0.5 else 0), color, alpha, 0.22)
        y += rng.uniform(7, 14) * s * (0.6 + 1.5 * depth)

    if L["r"] > 0:
        disc(p, lx, ly, L["r"] * h, rgb(L["color"]), s)


def disc(p, x, y, r, col, s):
    """The sun or the moon: thick paint pulled across it in a few strokes, which leave its edge uneven."""
    own = np.random.default_rng(1872)  # numbers of its own, so whatever is painted after it keeps its strokes
    spread = 0.07 * (1 - col.mean())  # a pale moon shows every change of tone as a stripe
    p.dot(x, y, r * 0.98, col, 0.95, 1.6 * s)
    for i in range(7):
        t = -0.82 + 1.64 * i / 6 + own.normal(0, 0.04)  # how far up or down the disc
        chord = 2 * r * math.sqrt(max(0.0, 1 - t * t))
        p.lay(x + own.normal(0, r * 0.05), y + t * r, chord * own.uniform(0.9, 1.08), r * 0.38,
              own.normal(0, 0.06) + (math.pi if i % 2 else 0), col * own.uniform(1 - spread, 1 + spread), 0.92,
              2 * spread)


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
        # Hull: two overlapping dark dabs, the ends lifted, light catching the rim; then the brush
        # dragged along it in a few strokes, so its paint shows.
        p.stroke(x, y, L, 36 * k, -0.03, 0.9, mist, a, soft)
        p.stroke(x - L * 0.06, y + 8 * k, L * 0.8, 22 * k, -0.02, 0.6, mist * 0.85, a * 0.8, soft)
        for u, dy, tone in ((-0.22, 2, 1.12), (0.08, -2, 0.9), (0.24, 6, 1.06)):
            p.lay(x + u * L, y + dy * k, L * 0.42, 18 * k, -0.03 + u * 0.25 + (math.pi if tone < 1 else 0),
                  mist * tone, a * 0.5, 0.2)
        p.lay(x + L * 0.05, y - 13 * k, L * 0.6, 6 * k, -0.04, mix(mist, rim, 0.5), 0.1 * a, 0.1)

        def daub(x0, y0, x1, y1, width, bend, tone=1.0, alpha=1.0):
            # One stroke from where the brush lands (wide) to where it lifts, in boat units, its bristles showing.
            x0, y0, x1, y1 = fx + x0 * k, y + y0 * k, fx + x1 * k, y + y1 * k
            length, angle = math.hypot(x1 - x0, y1 - y0), math.atan2(y1 - y0, x1 - x0)
            p.stroke((x0 + x1) / 2, (y0 + y1) / 2, length, width * k, angle, bend, mist * tone, a * alpha, 1.3 * k)
            p.lay((x0 + x1) / 2, (y0 + y1) / 2, length * 0.9, width * k * 0.7, angle, mist * tone * 1.15,
                  a * alpha * 0.4, 0.2)

        def head(cx, cy, r):
            # A dab and a smaller one beside it: round enough, never a circle.
            p.dot(fx + cx * k, y + cy * k, r * k, mist, a, 1.3 * k)
            p.dot(fx + (cx + 0.35 * r) * k, y + (cy + 0.4 * r) * k, 0.7 * r * k, mist, a, 1.3 * k)

        # The figures are a few quick dark strokes, as Monet put them down.
        lean, nod, hunch = rng.uniform(-1, 1, 3)
        # The rower, standing at the stern: back, a darker stroke into it, the
        # head, an arm reaching for the oar, and the oar dipping into the water.
        fx = x + L * 0.24
        daub(12 + 4 * lean, -102, -4, 2, 22, 0.5)
        daub(7 + 4 * lean, -94, -5, -24, 12, 0.3, tone=0.82)
        head(13 + 6 * lean + 2 * nod, -111, 9)
        daub(14 + 4 * lean, -88, 34, -68, 8, 0.3)
        daub(28, -78, 90, 66, 5.5, 0.12, alpha=0.85)
        # A passenger hunched in the bow: a broad back, the shoulders, the head.
        fx = x - L * 0.17
        daub(8 + 4 * hunch, -54, -4, 10, 36, 0.7)
        daub(-14, -38, 16 + 3 * hunch, -44, 12, 0.4, tone=0.88)
        head(5 + 5 * hunch, -62, 9.5)
        # Its reflection, broken by ripples.
        for i in range(7):
            p.lay(x + rng.normal(0, L * 0.1), y + (30 + i * 14) * k, L * rng.uniform(0.4, 0.9) * (1 - i * 0.09),
                  13 * k, math.pi if i % 2 else 0, mist, a * (0.42 - i * 0.05), 0.12)


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
                p.lay(x + rng.normal(0, 4 * s), hz + (10 + i * 14) * s, rng.uniform(16, 38) * s, 6 * s,
                      math.pi if i % 2 else 0, warm, 0.6 - i * 0.1, 0.15)


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


# Water Lilies --------------------------------------------------------------
# After the Nymphéas: the pond seen from above, no sky but its reflection,
# the willows' reflections falling down it, and islands of lily pads that
# grow as they come closer, some with a flower.

def light(x, y, glow, reach=0.5, strength=0.35, r=0.0, color="#FFFFFF"):
    return dict(x=x, y=y, r=r, color=color, glow=glow, reach=reach, strength=strength)


LILIES = {
    "dawn": dict(sky=[(0, "#C9B6D6"), (1, "#C9B6D6")], water=[(0, "#CDB8D8"), (0.45, "#93A6C8"), (1, "#4E6B8E")],
                 light=light(0.7, 0.18, "#F4CDBE"), reflection="#F6D6C6", accent_sky="#C9B6D6", accent_water="#7C9A92",
                 foliage="#4E6A5E", pad="#5E8C5A", pad_light="#A8C47A", pad_shade="#2E4A4E",
                 flowers=["#F2A9B8", "#FBEAF0", "#E98AA0", "#F4E3A8"], heart="#F2B84E", ripple=0.025),
    "day": dict(sky=[(0, "#A9C9DE"), (1, "#A9C9DE")], water=[(0, "#B4D2E2"), (0.45, "#6E9CC0"), (1, "#2F5E7E")],
                light=light(0.3, 0.12, "#EEF6F4", strength=0.4), reflection="#F4FAF6", accent_sky="#A9C9DE",
                accent_water="#5C9A86", foliage="#3E6B4A", pad="#4F8A4C", pad_light="#A6CC6E", pad_shade="#1E4A4A",
                flowers=["#F28CA0", "#FFFFFF", "#E0607A", "#F6E7A0"], heart="#F2C84A", ripple=0.025),
    "dusk": dict(sky=[(0, "#E7A77A"), (1, "#E7A77A")], water=[(0, "#EDAA7E"), (0.45, "#B4789A"), (1, "#4A3D6A")],
                 light=light(0.62, 0.15, "#F8B47C", strength=0.45), reflection="#FAC08A", accent_sky="#E7A77A",
                 accent_water="#8A6A8A", foliage="#3A3A55", pad="#5A6A4A", pad_light="#B49A5E", pad_shade="#2A2440",
                 flowers=["#F4B0C0", "#FFE4C4", "#E8798A", "#F8DC98"], heart="#F6A84A", ripple=0.025),
    "night": dict(sky=[(0, "#3B4A78"), (1, "#3B4A78")], water=[(0, "#405080"), (0.45, "#26305A"), (1, "#121630")],
                  light=light(0.66, 0.2, "#B8C4EC", strength=0.35, reach=0.35), reflection="#D8E0F8",
                  accent_sky="#3B4A78", accent_water="#2E4A5E", foliage="#1A2A2E", pad="#2E4440", pad_light="#5A7262",
                  pad_shade="#0E1426", flowers=["#B4A6C4", "#CCC8D8", "#A48AB0", "#C0BCA8"], heart="#968A66",
                  ripple=0.03),
}
# Islands of pads: center, spread (fractions of the width) and how many.
ISLANDS = ((0.16, 0.22, 0.08, 18), (0.58, 0.14, 0.12, 22), (0.36, 0.46, 0.12, 22), (0.84, 0.52, 0.08, 12),
           (0.12, 0.78, 0.1, 8), (0.62, 0.86, 0.11, 8), (0.92, 0.2, 0.05, 8))


def mix(a, b, t):
    return a * (1 - t) + b * t


def petal(base, tip, width, bend):
    """Outline of a pointed petal (or sepal) from its base to its tip, a little curved."""
    (bx, by), (tx, ty) = base, tip
    length = math.hypot(tx - bx, ty - by) or 1
    nx, ny = -(ty - by) / length, (tx - bx) / length
    left, right = [], []
    for i in range(9):
        t = i / 8
        half = width / 2 * math.sin(math.pi * t**0.8) ** 0.6
        cx = bx + (tx - bx) * t + nx * bend * math.sin(math.pi * t) * length * 0.12
        cy = by + (ty - by) * t + ny * bend * math.sin(math.pi * t) * length * 0.12
        left.append((cx + nx * half, cy + ny * half))
        right.append((cx - nx * half, cy - ny * half))
    return left + right[::-1]


def spans(points, y):
    """Where the horizontal line at y runs inside the polygon, as (x0, x1) pairs."""
    xs = sorted(x0 + (x1 - x0) * (y - y0) / (y1 - y0)
                for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]) if (y0 > y) != (y1 > y))
    return list(zip(xs[::2], xs[1::2]))


def pad(p, x, y, rx, ry, light_at, c, s, rng):
    """A lily pad in short strokes: veins out from the middle, the rim around, the notch left open."""
    notch, gape = rng.uniform(0, 2 * math.pi), rng.uniform(0.05, 0.2)
    # Every pad its own: younger and brighter or older with rust at the rim, a few curled up or torn.
    fresh, age, radial = rng.uniform(-0.15, 0.25), rng.random() ** 2, rng.uniform(0.35, 0.85)
    curl, curl_at, tear, tear_at, tear_to = rng.random(), rng.uniform(0.35, math.pi - 0.35), rng.random(), \
        rng.uniform(0, 2 * math.pi), rng.uniform(0.35, 0.7)
    wobble, jitter = rng.uniform(0, 2 * math.pi, 2), rng.normal(0, 0.012, 49)

    def turn(a, b):  # how far angle a is from angle b
        return abs((a - b + math.pi) % (2 * math.pi) - math.pi)

    def rim(a):  # no pad is a true circle
        return 1 + 0.035 * math.sin(3 * a + wobble[0]) + 0.025 * math.sin(5 * a + wobble[1])

    def at(a, r):
        return x + math.cos(a) * r * rx, y + math.sin(a) * r * ry

    outline = [at(notch, 0.06)]
    for i in range(49):
        a = notch + gape + (2 * math.pi - 2 * gape) * i / 48
        torn = tear < 0.12 and turn(a, tear_at) < 0.1
        outline.append(at(a, tear_to if torn else rim(a) + jitter[i]))
    # Its shadow in the water, soft, and an underlayer for the strokes.
    p.shape([(px, py + ry * 0.2) for px, py in outline], c["dark"], 0.35, max(3 * s, ry * 0.18))
    body = mix(c["green"], c["bright"], np.clip(0.2 + fresh, 0, 1))
    p.shape(outline, body, 0.85, 1.8 * s)
    # The body brushed across, each stroke stopping at the rim or the notch. It draws numbers of its own,
    # so the flowers chosen after the pads stay where they were.
    own = np.random.default_rng(abs(int(x * 7 + y * 13)))
    rows = 3 + int(ry / (10 * s))
    for i, (tone, flip) in enumerate(own.random((rows, 2))):
        row = y - ry * 1.05 + 2.1 * ry * (i + 0.5) / rows
        for x0, x1 in spans(outline, row):
            if x1 - x0 > 4 * s:
                p.lay((x0 + x1) / 2, row, (x1 - x0) * 0.96, 2.8 * ry / rows, math.pi if flip < 0.5 else 0,
                      np.clip(body * (0.9 + 0.2 * tone), 0, 1), 0.7, 0.14)
    for ua, ur, ul, uw, tone, warmth, pick, rust, kind in rng.random((int(14 + 0.3 * rx / s), 9)):
        vein = kind < radial
        length = (0.22 + 0.3 * ul) if vein else (0.3 + 0.35 * ul)
        width = 0.09 + 0.08 * uw
        r = 0.18 + 0.68 * ur if vein else 0.8 + 0.2 * ur
        # Keep each stroke out of the notch, wherever along it the brush goes.
        room = gape + 0.05 + (width if vein else length) / (2 * r)
        a = notch + room + (2 * math.pi - 2 * room) * ua
        if tear < 0.12 and turn(a, tear_at) < 0.1 + length / (2 * r) and r + length / 2 > tear_to:
            r = tear_to - length / 2 if vein else tear_to - 0.08
        if vein:
            r = min(r, rim(a) - length / 2 + 0.03)
        out, along = math.hypot(math.cos(a) * rx, math.sin(a) * ry), math.hypot(math.sin(a) * rx, math.cos(a) * ry)
        angle = math.atan2(math.sin(a) * ry, math.cos(a) * rx) if vein else math.atan2(math.cos(a) * ry, -math.sin(a) * rx)
        # Yellow-green where the light falls, blue-green away from it; some pick up the sky.
        t = 0.5 + 0.5 * math.cos(math.atan2(math.sin(a) * ry, math.cos(a) * rx) - light_at) * min(1.0, r * 1.3)
        color = mix(c["green"], c["bright"], np.clip(0.15 + 0.55 * t + fresh + 0.45 * (tone - 0.5), 0, 1))
        color = color + c["warm"] * (t - 0.5 + 1.2 * (warmth - 0.5))
        if pick < 0.1:
            color = mix(color, c["sky"], 0.35)
        elif pick < 0.25:  # a darker green laid into the shade
            color = mix(color, c["dark"], 0.3 * (1.2 - t))
        if not vein and rust < age and r > 0.86:  # age shows first at the rim
            color, width = mix(color, c["rust"], 0.3 + 0.35 * age), width * 0.6
        cx, cy = at(a, r)
        # Veins pulled out from the middle, the rim brushed round one way or the other.
        p.lay(cx, cy, length * (out if vein else along * 0.85), width * (along if vein else out),
              angle + (math.pi if not vein and tone > 0.5 else 0), np.clip(color, 0, 1), 0.75 + 0.2 * kind, 0.14)
    if curl < 0.15:
        # The near edge curled up, showing the pad's red underside, light along its lip.
        under = mix(c["rust"] * np.array([1.0, 0.7, 0.85]), c["dark"], 0.3)
        for i in range(7):
            a = curl_at + (i - 3) * 0.11
            if turn(a, notch) > gape + 0.12:
                tangent = math.atan2(math.cos(a) * ry, -math.sin(a) * rx)
                along = math.hypot(math.sin(a) * rx, math.cos(a) * ry)
                cx, cy = at(a, rim(a) - 0.05)
                p.lay(cx, cy - ry * 0.03, 0.34 * along, 0.12 * ry * (1 - abs(i - 3) / 5) + 2 * s, tangent, under, 0.8,
                      0.12)
                if 1 <= i <= 5:
                    cx, cy = at(a, rim(a))
                    p.lay(cx, cy - ry * 0.06, 0.3 * along, 0.035 * ry + 2 * s, tangent, np.clip(c["bright"] * 1.12, 0, 1),
                          0.5, 0.1)


def lily(p, x, y, r, color, c, s, rng):
    """A water lily in a few loose petal strokes: a closed bud, half open, or open flat on the water."""
    kind, opening, extra = rng.random(3)
    openness = 0.08 + 0.14 * opening if kind < 0.2 else 0.35 + 0.25 * opening if kind < 0.65 else 0.62 + 0.23 * opening
    pale, squash, spin = rng.uniform(0, 0.35), rng.uniform(0.38, 0.55), rng.uniform(0, 2 * math.pi)
    color = mix(color, c["flowers"][1], pale)
    # An outer ring of long petals and, once it opens, an inner ring standing more upright.
    rings = [(int(4 + 8 * openness + 3 * extra), 1.0, openness, 1.0)]
    if openness > 0.3:
        rings.append((int(3 + 4 * openness), 0.65, openness * 0.45, 1.04))
    back, front = [], []
    for ring, (count, reach, opened, light) in enumerate(rings):
        for i, (da, ln, wd, tone, lift, bend) in enumerate(rng.random((count, 6))):
            a = spin + ring * 0.5 + 2 * math.pi * (i + 0.6 * (da - 0.5)) / count
            length = r * reach * (0.75 + 0.45 * ln) * (0.8 if openness < 0.3 else 1)
            o = min(1.0, opened * (0.75 + 0.5 * lift))
            # Open petals lie flat in a squashed ring; closed ones rise to a point.
            base = (x + math.cos(a) * r * 0.08, y + math.sin(a) * r * 0.04)
            spread = length * o * min(1.0, o / 0.35)  # a bud's petals close over one point
            tip = (base[0] + math.cos(a) * spread, base[1] + math.sin(a) * spread * squash - length * (1 - o) * 0.95)
            col = mix(color * (0.92 + 0.14 * tone) * light, c["flowers"][1], 0.15 * ring)
            (front if math.sin(a) > 0 else back).append(
                (tip[1], ring, base, tip, r * (0.34 + 0.2 * wd) * (0.6 + 0.4 * o), bend - 0.5, col))
    back.sort(key=lambda pt: (pt[1], pt[0]))  # outer ring first, the far petals before the near
    front.sort(key=lambda pt: (-pt[1], pt[0]))  # then the heart, the inner ring, the outer ring over all
    for layer in (back, front):
        if layer is front and openness > 0.3:
            # The heart, sunk deeper in a flower still opening.
            hy, hr = y - r * (0.1 + 0.25 * (1 - openness)), r * (0.07 + 0.12 * openness)
            p.dot(x, hy, hr, c["heart"], 0.95, 0.8 * s)
            p.dot(x - hr * 0.3, hy - hr * 0.25, hr * 0.5, np.clip(c["heart"] * 1.12, 0, 1), 0.8, 0.6 * s)
        for _, _, base, tip, width, bend, col in layer:
            col = mix(col, mix(c["dark"], c["sky"], 0.5), 0.18) if layer is front else col  # the near petals' cooler backs
            p.shape(petal(base, tip, width, bend), np.clip(col, 0, 1), 0.92, 0.8 * s)
            # The brush dragged along the petal from its base, its bristles showing: lighter on a colored
            # petal, and on a white one the sky's blue in its shadow.
            (bx, by), (tx, ty) = base, mix(np.array(base), np.array(tip), 0.82)
            drag = col * 1.08 if col.mean() < 0.8 else mix(col, c["sky"], 0.3)
            p.lay((bx + tx) / 2, (by + ty) / 2, math.hypot(tx - bx, ty - by), width * 0.55, math.atan2(ty - by, tx - bx),
                  np.clip(drag, 0, 1), 0.55, 0.18)
    if openness < 0.3:
        # Green sepals holding the bud.
        for side in (-1, 1):
            tip = (x + side * r * 0.32, y - r * 0.32)
            p.shape(petal((x, y + r * 0.02), tip, r * 0.2, side * 0.3), mix(c["green"], c["bright"], 0.4), 0.9, 0.8 * s)


def lilies_scene(p, hour, w, h, hz, s, rng):
    leaf = rgb(hour["foliage"])
    # The willows on the bank, upside down in the water: long falling strokes.
    for x0, x1, n in ((-0.04, 0.24, 90), (0.76, 1.04, 80), (0.4, 0.54, 26)):
        for _ in range(n):
            x, y = rng.uniform(x0, x1) * w, rng.beta(1.2, 2.6) * 0.85 * h
            fade = 1 - y / (0.9 * h)
            length, width, angle, bend = rng.uniform(160, 520) * s, rng.uniform(24, 60) * s, \
                math.pi / 2 + rng.normal(0, 0.08), rng.normal(0, 0.35)
            color, alpha = leaf * rng.uniform(0.8, 1.2), rng.uniform(0.06, 0.16) * (0.4 + fade)
            # A soft glaze, then the brush pulled down the water through it (or up), its bristles showing.
            p.stroke(x, y, length, width, angle, bend, color, alpha, 14 * s)
            p.lay(x, y, length * 0.9, width * 0.7, angle + (math.pi if bend > 0 else 0), color, alpha * 1.2, 0.14)
    # The sky's light on the water, in broken dabs.
    refl = rgb(hour["reflection"])
    L = hour["light"]
    for _ in range(140):
        x, y = rng.normal(L["x"], 0.08) * w, rng.uniform(0, 0.75) * h
        p.lay(x, y, rng.uniform(40, 120) * s, rng.uniform(8, 14) * s, rng.normal(0, 0.04) + (math.pi if x % 2 < 1 else 0),
              refl, rng.uniform(0.2, 0.45), 0.1)
    c = dict(green=rgb(hour["pad"]), bright=rgb(hour["pad_light"]), dark=rgb(hour["pad_shade"]),
             sky=rgb(hour["accent_sky"]), heart=rgb(hour["heart"]), flowers=[rgb(f) for f in hour["flowers"]])
    c["rust"] = np.clip(c["bright"] * np.array([1.15, 0.82, 0.5]), 0, 1)  # ochre: the light's own green, aged
    c["warm"] = np.array([0.05, 0.03, -0.06]) * c["bright"].mean() / 0.65  # gentler in dim light
    # Place the pads first: one that would land on another is tried again
    # elsewhere in its island, so pads float apart and only just touch.
    pads = []
    for cx, cy, spread, count in ISLANDS:
        placed = 0
        for _ in range(count * 4):
            y = (cy + rng.normal(0, spread * 0.35)) * h
            depth = min(1.0, max(0.03, y / h))
            x = (cx + rng.normal(0, spread)) * w
            rx = rng.uniform(55, 110) * s * (0.3 + 1.6 * depth)
            ry = rx * (0.22 + 0.3 * depth)
            if all(((x - px) / (rx + prx)) ** 2 + ((y - py) / (ry + pry)) ** 2 > 1.0 for px, py, prx, pry in pads):
                pads.append((x, y, rx, ry))
                placed += 1
                if placed == count:
                    break
    pads.sort(key=lambda pad: pad[1])  # far ones first, so nearer pads lie over them
    for x, y, rx, ry in pads:
        pad(p, x, y, rx, ry, math.atan2(L["y"] * h - y, L["x"] * w - x), c, s, rng)
    # Flowers last, so no pad covers one, and never two in the same spot.
    blooms = []
    for x, y, rx, ry in pads:
        if rng.random() < 0.22:
            fx, fy, fr = x + rng.normal(0, rx * 0.2), y - ry * 0.35, rx * rng.uniform(0.45, 0.68)
            color = c["flowers"][rng.integers(len(c["flowers"]))]
            if all(math.hypot(fx - bx, (fy - by) * 1.6) > (fr + br) * 1.5 for bx, by, br in blooms):
                blooms.append((fx, fy, fr))
                lily(p, fx, fy, fr, color, c, s, rng)


# Haystacks -----------------------------------------------------------------
# After the Meules: two stacks in a field after the harvest, trees and a
# village far off, and the light making the stacks glow on one side and cast
# long colored shadows on the other.

HAYSTACKS = {
    "dawn": dict(sky=[(0, "#9EAFD0"), (0.6, "#E2C6BE"), (1, "#F2D2AC")], water=[(0, "#D2BC92"), (0.4, "#A8946E"), (1, "#6A5A4A")],
                 light=light(0.14, 0.42, "#F7C89A", reach=0.32, strength=0.5, r=0.022, color="#F7A04A"),
                 reflection="#F7C89A", accent_sky="#C0A8C8", accent_water="#9AA07A", mist="#7A7A96",
                 stack_light="#F0B87A", stack_shadow="#6A6A9A", ripple=0.0),
    "day": dict(sky=[(0, "#7FA6D6"), (0.6, "#B8CFE6"), (1, "#E6E8E0")], water=[(0, "#DCC67E"), (0.4, "#B89E5C"), (1, "#7A6A3A")],
                light=light(0.78, 0.08, "#FFF6E0", reach=0.4, strength=0.3), reflection="#FFF6E0", accent_sky="#9FC0E2",
                accent_water="#A8B46A", mist="#7A8AA6", stack_light="#F4C478", stack_shadow="#8A7AA2", ripple=0.0),
    "dusk": dict(sky=[(0, "#6A5A8A"), (0.6, "#D8806A"), (1, "#F4A85A")], water=[(0, "#CC8E5C"), (0.4, "#8A5A5A"), (1, "#4A3A4A")],
                 light=light(0.84, 0.46, "#F79A5A", reach=0.34, strength=0.55, r=0.03, color="#F2552C"),
                 reflection="#F79A5A", accent_sky="#B87A9A", accent_water="#A0605A", mist="#4E3E62",
                 stack_light="#F48A4A", stack_shadow="#4A3A6E", ripple=0.0),
    "night": dict(sky=[(0, "#141C3C"), (0.6, "#2A3664"), (1, "#46527E")], water=[(0, "#3A4468"), (0.4, "#262E50"), (1, "#12162C")],
                  light=light(0.7, 0.16, "#8E9AC6", reach=0.3, strength=0.4, r=0.016, color="#ECE6D0"),
                  reflection="#C8CCE0", accent_sky="#3A4678", accent_water="#2E3A5E", mist="#1E2442",
                  stack_light="#7C86B4", stack_shadow="#1A1E3C", ripple=0.0),
}
# Each stack: center and base (fractions), width and height (fractions of the height).
STACKS = ((0.42, 0.80, 0.42, 0.32), (0.68, 0.70, 0.24, 0.18))


def inside(points, x, y):
    """Whether (x, y) is inside the polygon (ray casting)."""
    hit = False
    for (x0, y0), (x1, y1) in zip(points, points[1:] + points[:1]):
        if (y0 > y) != (y1 > y) and x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
            hit = not hit
    return hit


def stack_outline(cx, base, sw, sh, rng):
    """A round body of hay under a thatched cap whose eaves stick out a little, built by hand."""
    shoulder = base - sh * 0.45
    # The body swells between the ground and the eaves.
    body = [(0.45 + 0.03 * math.sin(math.pi * v), base - (base - shoulder) * v) for v in (0, 0.25, 0.5, 0.75, 0.92)]
    pts = [(cx - sw * hw, y) for hw, y in body] + [(cx - sw * 0.5, shoulder)]
    for i in range(1, 24):
        u = -1 + 2 * i / 24
        # Round, rising to a soft point.
        pts.append((cx + sw * 0.5 * u, shoulder - sh * 0.55 * (1 - abs(u) ** 1.9) - sh * 0.05 * (1 - abs(u)) ** 3))
    pts += [(cx + sw * 0.5, shoulder)] + [(cx + sw * hw, y) for hw, y in body[::-1]] + [(cx, base + sh * 0.03)]
    # No edge ruled straight: every point a little off.
    return [(x + rng.normal(0, sw * 0.012), y + rng.normal(0, sh * 0.015)) for x, y in pts]


def haystacks_scene(p, hour, w, h, hz, s, rng):
    mist, haze = rgb(hour["mist"]), rgb(hour["sky"][2][1])
    # Far off: a line of trees, a few poplars and the village's roofs, pale in the air. The trees' leaves are
    # dabbed with numbers of their own, so the stacks' strokes stay where they were.
    own = np.random.default_rng(1891)
    x = -40 * s
    while x < w:
        r = rng.uniform(40, 110) * s
        color, alpha = mix(mist, haze, rng.uniform(0.3, 0.6)), rng.uniform(0.3, 0.55)
        p.dot(x, hz - r * 0.45, r, color, alpha * 0.7, 10 * s)
        for dx, dy, ln, tilt in own.random((5, 4)):
            p.lay(x + (dx - 0.5) * r * 1.2, hz - r * (0.25 + 0.5 * dy), r * (0.6 + 0.4 * ln), r * 0.6,
                  -math.pi / 2 + (tilt - 0.5) * 1.6, color, alpha * 0.55, 0.06)
        x += r * rng.uniform(0.9, 1.6)
    # The poplars and roofs stay soft in the distance, a little of the brush showing in the poplars.
    for _ in range(9):
        x, tall = rng.uniform(0.05, 0.95) * w, rng.uniform(0.07, 0.13) * h
        width = rng.uniform(16, 26) * s
        p.stroke(x, hz - tall / 2, tall, width, math.pi / 2, 0, mix(mist, haze, 0.35), 0.4, 6 * s)
        sweep(p, x, hz, x + (own.random() - 0.5) * 6 * s, hz - tall, width * 0.8, mix(mist, haze, 0.35), 0.15, 0.08)
    for _ in range(7):
        x = rng.uniform(0.55, 0.9) * w
        p.stroke(x, hz - 14 * s, rng.uniform(40, 80) * s, rng.uniform(14, 24) * s, 0, 0, mix(mist, haze, 0.25), 0.4, 3 * s)
    # Stubble: short strokes across the field, bigger nearer.
    near, far = rgb(hour["water"][0][1]), rgb(hour["water"][2][1])
    for _ in range(int(1400 * s * s * 16) // 16 + 300):
        y = hz + (h - hz) * rng.uniform(0.04, 1) ** 1.6
        depth = (y - hz) / (h - hz)
        p.lay(rng.uniform(0, w), y, rng.uniform(20, 60) * s * (0.4 + depth), rng.uniform(6, 13) * s * (0.4 + depth),
              rng.normal(0, 0.25), mix(near, far, depth * rng.uniform(0.6, 1.1)) * rng.uniform(0.9, 1.15),
              rng.uniform(0.25, 0.5), 0.14)
    halo(p, hour, w, h, s)
    L = hour["light"]
    if L["r"] > 0:
        disc(p, L["x"] * w, L["y"] * h, L["r"] * h, rgb(L["color"]), s)
    lit, shade_col = rgb(hour["stack_light"]), rgb(hour["stack_shadow"])
    warm = np.array([0.07, 0.015, -0.06])  # a nudge toward orange; negative leans blue
    side = 1 if L["x"] > 0.5 else -1  # the side the light comes from
    # Every random number below is drawn whatever the light, so all four
    # hours keep the same strokes; only their colors and the shadow move.
    for fx, fb, fw, fh in sorted(STACKS, key=lambda st: st[1]):
        cx, base, sw, sh = fx * w, fb * h, fw * h, fh * h
        k = (sw / (0.42 * h)) ** 0.5  # the far stack takes smaller strokes
        # The long shadow, thrown away from the light across the stubble: a thin
        # glaze, then flat strokes along it, some cooled by the sky.
        long = 1.9 if L["r"] > 0 else 0.9
        near_l, near_r = (cx - sw * 0.42, base), (cx + sw * 0.42, base)
        far_l = (cx - side * sw * long - sw * 0.25, base + sh * 0.12)
        far_r = (cx - side * sw * long + sw * 0.25, base + sh * 0.2)
        p.shape([near_l, near_r, far_r, far_l], shade_col, 0.28, 16 * s)
        axis = math.atan2((far_l[1] + far_r[1]) / 2 - base, (far_l[0] + far_r[0]) / 2 - cx)
        for u, v, ln, wd, tone, a in rng.random((140, 6)):
            x = mix(mix(near_l[0], near_r[0], v), mix(far_l[0], far_r[0], v), u)
            y = mix(mix(near_l[1], near_r[1], v), mix(far_l[1], far_r[1], v), u)
            p.lay(x, y, (50 + 90 * ln) * s * k, (9 + 12 * wd) * s * k, axis + (a - 0.5) * 0.12 + (math.pi if a > 0.5 else 0),
                  mix(shade_col * 0.9, haze, tone * 0.4), (0.55 - 0.3 * u) * (0.7 + 0.3 * a), 0.1)
        outline = stack_outline(cx, base, sw, sh, rng)
        p.shape(outline, mix(shade_col, lit, 0.45), 0.9, 3 * s)
        top, apex = base - sh * 0.45, base - sh
        x0, x1, y0 = cx - sw / 2, cx + sw / 2, base - sh * 1.05
        area = sw * sh / (0.42 * 0.32 * h * h)
        # Broad strokes block in the light and the shade, then smaller ones on
        # top break the color: warm and cool side by side, none of them alike.
        for n, size in ((520, 2.8), (1500, 1.2)):
            for _ in range(int(n * area)):
                x, y = rng.uniform(x0, x1), rng.uniform(y0, base)
                if not inside(outline, x, y):
                    continue
                # Lit toward the light, cooler away from it; the top catches the most.
                t = np.clip(0.5 + 0.65 * side * (x - cx) / (sw / 2) + 0.25 * (top - y) / sh, 0, 1)
                # The thatch runs down from the top; the hay below stands upright.
                if y < top:
                    angle = math.atan2(y - apex, x - cx) + rng.normal(0, 0.3)
                else:
                    angle = math.pi / 2 + rng.normal(0, 0.35)
                color = mix(shade_col, lit, t) * rng.uniform(0.9, 1.08) + warm * (t - 0.5 + rng.normal(0, 0.7))
                if rng.random() < 0.15:  # broken color: the sky in the shade, the light in the light
                    color = mix(color, haze if t < 0.5 else lit * 1.12, 0.4)
                # Pulled down the thatch or up the hay, one way or the other; short near the ground, so
                # none hangs below the stack's foot.
                p.lay(x, y, rng.uniform(24, 64) * s * size * k * min(1.0, 0.3 + (base - y) / (0.35 * sh)),
                      rng.uniform(10, 20) * s * size * k,
                      angle + (math.pi if rng.normal(0, 0.45) > 0 else 0), np.clip(color, 0, 1), rng.uniform(0.55, 0.9),
                      0.16)
        # The shadow under the eaves and at the foot: dabs, not a ruled band.
        for yy, depth, alpha in ((top + sh * 0.05, 1.0, 0.25), (base - sh * 0.01, 0.7, 0.4)):
            for i in range(9):
                p.lay(cx + sw * (-0.36 + 0.72 * i / 8) + rng.normal(0, sw * 0.03), yy + rng.normal(0, sh * 0.018),
                      sw * rng.uniform(0.1, 0.17), sh * rng.uniform(0.03, 0.06),
                      rng.normal(0, 0.12) + (math.pi if rng.normal(0, 0.4) > 0 else 0), shade_col * depth,
                      alpha * rng.uniform(0.5, 1.05), 0.1)
        # Loose hay along the edge and light caught on the side that faces it,
        # broken off here and there so the silhouette is never a line.
        for (ax, ay), (bx, by), (keep, f, ln, out) in zip(outline[:-2], outline[1:-1], rng.random((len(outline), 4))):
            x, y = mix(ax, bx, f), mix(ay, by, f)
            along = math.atan2(by - ay, bx - ax)
            t = np.clip(0.5 + 0.65 * side * (x - cx) / (sw / 2), 0, 1)
            p.lay(x, y, (20 + 40 * ln) * s * k, (6 + 6 * out) * s * k, along + (out - 0.5) * 0.5,
                  np.clip(mix(shade_col, lit, t) * (0.95 + 0.1 * ln), 0, 1), 0.7, 0.14)
            if side * (x - cx) > sw * 0.12 and keep < 0.45:
                p.lay(x, y, math.hypot(bx - ax, by - ay) * (0.6 + 0.8 * ln), (5 + 4 * out) * s * k, along,
                      np.clip(lit * 1.12 + warm * 0.5, 0, 1), 0.6, 0.1)


# The Magpie ----------------------------------------------------------------
# After La Pie (1868-69): a snowy field, a wattle fence across it with a gate
# and one magpie on the gate, farmhouses and frosted trees behind, and the low
# light throwing the fence's shadow toward us across the snow, blue-violet
# against snow warmed wherever the light reaches it. Nothing is ruled: it is
# all laid in strokes of a flat brush, and snow is heaped on everything.

MAGPIE = {
    "dawn": dict(sky=[(0, "#AEB0CC"), (0.6, "#E2CFD4"), (1, "#F4DCC6")],
                 water=[(0, "#DCCAD6"), (0.35, "#F2DDD0"), (1, "#E4D0CE")],
                 light=light(0.06, 0.38, "#F8D0B4", reach=0.5, strength=0.5), reflection="#FFE4C8",
                 accent_sky="#C8B4D2", accent_water="#D2BEDA", mist="#7A6E8E", snow="#FFE6CE", shadow="#A493C6",
                 wood="#5C4A50", wall="#CDAA9A", bird="#1C1A24", flank="#F6EEE6", cast=(0.9, 2.2, 1.0), ripple=0.0),
    "day": dict(sky=[(0, "#9CB2C8"), (0.6, "#C6D2DC"), (1, "#E4E8E8")],
                water=[(0, "#D6DEE6"), (0.35, "#F4F4F0"), (1, "#E2E8EE")],
                light=light(0.62, -0.1, "#FFF8EC", reach=0.7, strength=0.3), reflection="#FFFFF8",
                accent_sky="#B4C6D8", accent_water="#C8D6E6", mist="#7A8496", snow="#FFFEF6", shadow="#7E9ED2",
                wood="#5E5248", wall="#CABDA8", bird="#16161C", flank="#FAFAF6", cast=(0.25, 0.8, 1.0), ripple=0.0),
    "dusk": dict(sky=[(0, "#6A5C8C"), (0.6, "#D48E80"), (1, "#F2AE7A")],
                 water=[(0, "#CC9EA4"), (0.35, "#EEB698"), (1, "#D29E9C")],
                 light=light(0.94, 0.40, "#F8A070", reach=0.5, strength=0.6), reflection="#FFC890",
                 accent_sky="#C47E9C", accent_water="#B88AA8", mist="#5A4462", snow="#FFCC98", shadow="#6A4E94",
                 wood="#4A3442", wall="#B47E72", bird="#1A121E", flank="#F4DCCC", cast=(-1.0, 2.4, 1.0), ripple=0.0),
    "night": dict(sky=[(0, "#0E1630"), (0.6, "#1E2A50"), (1, "#34406A")],
                  water=[(0, "#3A4670"), (0.35, "#4A588C"), (1, "#2A3460")],
                  light=light(0.78, 0.15, "#8EA0CC", reach=0.3, strength=0.4, r=0.018, color="#EEE8D4"),
                  reflection="#C8D2EC", accent_sky="#2E3C6A", accent_water="#3A4A7A", mist="#141A30",
                  snow="#A8B6DA", shadow="#1E2652", wood="#151828", wall="#2C3252", bird="#080A14", flank="#6A7498",
                  cast=(-0.5, 1.4, 0.6), window="#FFB766", ripple=0.0),
}


def brush(p, x0, y0, x1, y1, width, bend, color, alpha, blur):
    """One stroke from where the brush lands (wide) to where it lifts."""
    p.stroke((x0 + x1) / 2, (y0 + y1) / 2, math.hypot(x1 - x0, y1 - y0), width, math.atan2(y1 - y0, x1 - x0),
             bend, np.clip(color, 0, 1), alpha, blur)


def sweep(p, x0, y0, x1, y1, width, color, alpha, streak=0.1):
    """A flat brush pulled from (x0, y0), where it lands, to (x1, y1), where it lifts."""
    p.lay((x0 + x1) / 2, (y0 + y1) / 2, math.hypot(x1 - x0, y1 - y0), width, math.atan2(y1 - y0, x1 - x0),
          np.clip(color, 0, 1), alpha, streak)


def limb(p, points, w0, w1, color, alpha, blur):
    """A branch (or a stick) along points, thinning from w0 to w1."""
    left, right = [], []
    for i, (x, y) in enumerate(points):
        (ax, ay), (bx, by) = points[max(i - 1, 0)], points[min(i + 1, len(points) - 1)]
        d = math.hypot(bx - ax, by - ay) or 1
        half = mix(w0, w1, i / (len(points) - 1)) / 2
        nx, ny = (ay - by) / d * half, (bx - ax) / d * half
        left.append((x + nx, y + ny))
        right.append((x - nx, y - ny))
    p.shape(left + right[::-1], np.clip(color, 0, 1), alpha, blur)


def eased(points, u):
    """The curve through points, spread evenly over u from 0 to 1, eased between them so it has no corners."""
    f = min(max(u, 0.0), 1.0) * (len(points) - 1)
    i = min(int(f), len(points) - 2)
    return mix(points[i], points[i + 1], (1 - math.cos(math.pi * (f - i))) / 2)


def heap(p, x, y, rw, rh, snow, shade, side, tones):
    """A little snow heaped around (x, y): lilac where it curls under, lit along its top."""
    a, b, c, d = tones
    p.lay(x, y + rh * 0.3, rw * 2, rh * 0.9, (a - 0.5) * 0.3, np.clip(mix(snow, shade, 0.55 + 0.25 * b), 0, 1), 0.85, 0.08)
    p.lay(x + side * rw * 0.12, y - rh * 0.15, rw * 1.6, rh * 0.6, (c - 0.5) * 0.3, np.clip(mix(snow, shade, 0.1 * d), 0, 1),
          0.9, 0.06)


def snowbank(p, runs, crest, low, snow, shade, warm, side, s, rng, n):
    """Snow lying deep along runs of a fence or hedge, from its crest down to low(x): lit along the crest,
    lilac down the front, its lower edge hanging over in rounded lumps."""
    total = sum(b - a for a, b in runs)

    def spot(u):  # a point along the runs, as if they were one
        d = u * total
        for a, b in runs:
            if d <= b - a:
                return a + d
            d -= b - a
        return runs[-1][1]

    for a, b in runs:
        xs = np.linspace(a, b, max(2, int((b - a) / (20 * s))))
        p.shape([(x, crest(x) + 4 * s) for x in xs] + [(x, low(x)) for x in xs[::-1]], mix(snow, shade, 0.4), 0.95, 2 * s)
    for u, f, ln, wd, tone, tilt in rng.random((n, 6)):
        x = spot(u)
        color = mix(snow, shade, np.clip(-0.05 + 0.75 * f + 0.25 * (tone - 0.5), 0, 0.9))
        if f < 0.3 and tone > 0.6:
            color = mix(color, warm, 0.35)  # the crest catching the light
        p.lay(x, mix(crest(x), low(x), f ** 0.8), (36 + 70 * ln) * s, (12 + 16 * wd) * s,
              (tilt - 0.5) * 0.5 + (f - 0.4) * 0.3 * (1 if tilt > 0.5 else -1), np.clip(color, 0, 1), 0.85, 0.08)
    for u, ln, tone, tilt in rng.random((n // 5, 4)):
        x = spot(u)
        # The lip, where it hangs over: short rounded strokes in the shadow under it.
        p.lay(x, low(x) - (6 + 6 * tone) * s, (30 + 40 * ln) * s, (14 + 12 * tone) * s,
              (tilt - 0.5) * 0.4 + (math.pi if tilt > 0.5 else 0), np.clip(mix(snow, shade, 0.6 + 0.2 * tone), 0, 1),
              0.85, 0.06)
    for u, ln, tone, tilt in rng.random((n // 4, 4)):
        x = spot(u)
        p.lay(x + side * 4 * s, crest(x) + 3 * s, (30 + 50 * ln) * s, (8 + 8 * tone) * s, (tilt - 0.5) * 0.3,
              np.clip(mix(snow, warm, 0.3 * tone), 0, 1), 0.8, 0.05)


def tree(p, x, base, tall, wood, snow, shade, side, s, rng, frost=1.0, levels=4, alpha=0.92):
    """A tree in hoarfrost: limbs twisting as they fork, snow laid along their tops, the twigs lost in frost.

    side is where the light comes from (1 the right, -1 the left). No random number depends on
    the light, so every hour paints the same tree."""
    limbs, tips = [], []

    def grow(x0, y0, angle, length, width, level):
        pts, a = [(x0, y0)], angle
        for turn in rng.normal(0, 0.15, 4):
            a += turn - 0.1 * a  # twisting, but always back toward the sky
            pts.append((pts[-1][0] + math.sin(a) * length / 4, pts[-1][1] - math.cos(a) * length / 4))
        limbs.append((pts, width, level))
        if level == levels:
            tips.append(pts[-1])
            return
        flip = rng.random() < 0.5
        children = rng.random((4 + int(rng.random() < 0.5) if level == 0 else 2 + int(rng.random() < 0.8), 4))
        for i, (at, spread, ln, wd) in enumerate(children):
            lead = i == len(children) - 1  # the last carries the limb on from its tip, so none ends in a stub
            f = 0.98 if lead else (0.35 if level == 0 else 0.2) + 0.6 * at
            k = min(int(f * 4), 3)
            (ax, ay), (bx, by) = pts[k], pts[k + 1]
            here = math.atan2(bx - ax, ay - by)  # the parent's heading there, from straight up
            sign = 1 if (i + flip) % 2 == 0 else -1
            grow(mix(ax, bx, f * 4 - k), mix(ay, by, f * 4 - k),
                 here + ((spread - 0.5) * 0.7 if lead else sign * (0.35 + 0.55 * spread)),
                 length * (0.5 + 0.3 * ln) * (1.15 - 0.45 * f),
                 width * 0.38 if lead else mix(width, width * 0.4, f) * (0.55 + 0.25 * wd), level + 1)

    grow(x, base, rng.normal(0, 0.05), tall * 0.5, tall * 0.05, 0)
    lit = mix(wood, snow, 0.4)
    for (pts, width, level), draws in zip(limbs, rng.random((len(limbs), 4, 3))):
        # The finest twigs barely show through the frost on them.
        limb(p, pts, width, width * 0.4, wood, alpha * (0.55 if level >= levels - 1 else 1), (0.7 + 0.25 * (levels - level)) * s)
        if width > 6 * s:  # the bark in strokes along the thicker limbs, lit on the side toward the light
            for i, ((ax, ay), (bx, by), (tone, glint, off)) in enumerate(zip(pts, pts[1:], draws)):
                wd = mix(width, width * 0.4, (i + 0.5) / 4)
                ox = side * wd * (0.1 + 0.25 * off)
                sweep(p, ax + ox, ay, bx + ox, by, wd * 0.55, wood * (0.8 + 0.4 * tone), alpha * 0.7, 0.14)
                sweep(p, ax + side * wd * 0.32, ay, bx + side * wd * 0.32, by, wd * 0.25, lit, alpha * (0.3 + 0.4 * glint),
                      0.1)
    # A veil of frost over the crown, so it reads as one pale mass with the limbs inside it.
    for (tx, ty), (ln, tone, a, keep) in zip(tips, rng.random((len(tips), 4))):
        if keep < 0.4:
            p.lay(tx, ty + tall * 0.03, tall * (0.12 + 0.12 * ln), tall * (0.05 + 0.04 * tone), (a - 0.5) * 2.4,
                  np.clip(mix(snow, shade, 0.25 + 0.35 * tone), 0, 1), 0.16 * frost * alpha, 0.03)
    # Snow along the tops of the bigger limbs that lie flat enough to hold it, the flatter the more.
    for (pts, width, level), draws in zip(limbs, rng.random((len(limbs), 4, 3))):
        for (ax, ay), (bx, by), (keep, ln, tone) in zip(pts, pts[1:], draws):
            seg = math.hypot(bx - ax, by - ay) or 1
            flat = abs(bx - ax) / seg
            if level < levels - 1 and flat > 0.35 and keep < (0.2 + 0.8 * flat) * frost:
                p.lay((ax + bx) / 2, (ay + by) / 2 - width * 0.5 - s, seg * (0.8 + 0.5 * ln), max(width * 0.9, 6 * s),
                      math.atan2(by - ay, bx - ax) + (math.pi if bx < ax else 0),
                      np.clip(mix(snow, shade, 0.35 * tone), 0, 1), alpha * (0.5 + 0.45 * flat), 0.06)
    # The twigs themselves rimed white: one stroke along each, far wider than the twig.
    for (pts, width, level), (ln, tone, wd, keep) in zip(limbs, rng.random((len(limbs), 4))):
        (ax, ay), (bx, by) = pts[0], pts[-1]
        if level >= levels - 1 and keep < 0.85:
            p.lay((ax + bx) / 2, (ay + by) / 2, math.hypot(bx - ax, by - ay) * (1.0 + 0.3 * ln), tall * (0.01 + 0.012 * wd),
                  math.atan2(by - ay, bx - ax), np.clip(mix(snow, shade, 0.12 + 0.5 * tone), 0, 1),
                  (0.45 + 0.35 * ln) * frost * alpha, 0.06)
    # And at their ends, frost in small strokes, white where the light reaches, lilac under.
    for (tx, ty), draws in zip(tips, rng.random((len(tips), 4, 5))):
        for dx, dy, ln, tone, a in draws:
            p.lay(tx + (dx - 0.5) * tall * 0.09, ty + (dy - 0.4) * tall * 0.07, tall * (0.025 + 0.045 * ln),
                  tall * (0.012 + 0.018 * ln), (a - 0.5) * 3, np.clip(mix(snow, shade, 0.1 + 0.55 * tone), 0, 1),
                  (0.3 + 0.4 * a) * frost * alpha, 0.06)


def farmhouse(p, x0, x1, eave, ridge, base, hour, side, s, rng, lit=False):
    """A farmhouse in strokes: warm walls, small dark windows, its roof deep in snow, a brick chimney."""
    wall, snow, shade, wood = rgb(hour["wall"]), rgb(hour["snow"]), rgb(hour["shadow"]), rgb(hour["wood"])
    brick = np.clip(mix(wall, wall * np.array([1.15, 0.72, 0.62]), 0.45), 0, 1)
    jog = rng.normal(0, 5, 8) * s  # nothing ruled straight
    p.shape([(x0 + jog[0], eave), (x1 + jog[1], eave), (x1 + jog[2], base), (x0 + jog[3], base)], wall, 0.92, 4 * s)
    # The walls in broad upright strokes, warmer toward the light, which also break their edges.
    for u, v, tone, ln, tilt in rng.random((int(160 * (x1 - x0) / (600 * s)) + 30, 5)):
        color = mix(wall, shade if tone < 0.5 else snow, 0.04 + 0.22 * abs(tone - 0.5)) * (0.95 + 0.1 * ln)
        p.lay(mix(x0 + 4 * s, x1 - 4 * s, u), mix(eave + 14 * s, base - 6 * s, v), (40 + 50 * ln) * s, (22 + 18 * tone) * s,
              math.pi / 2 + (tilt - 0.5) * 0.5, np.clip(color * (1 + 0.08 * side * (u - 0.5)), 0, 1), 0.6, 0.06)
    # Under the eaves, shadow.
    for u, ln, tone in rng.random((8, 3)):
        p.lay(mix(x0, x1, u), eave + 14 * s, (70 + 70 * ln) * s, 24 * s, (tone - 0.5) * 0.1,
              np.clip(mix(wall, shade, 0.5 + 0.15 * tone), 0, 1), 0.5, 0.06)
    # Windows and a door: dark strokes, never square, snow on the sill; at night one is lit.
    glow = hour.get("window")
    for i, ((u, size), (dx, dl, tilt)) in enumerate(zip(((0.2, 0.3), (0.5, 0.55), (0.8, 0.3)), rng.random((3, 3)))):
        wx = mix(x0, x1, u) + jog[4 + i]
        wy, wh = mix(eave, base, 0.3 + size / 2), (base - eave) * size * (0.65 if size < 0.5 else 1)
        color = rgb(glow) if glow and lit and i == 0 else mix(wood * 0.6, shade, 0.25)
        for k in (-1, 1):
            p.lay(wx + k * (9 + 2 * dx) * s, wy + k * (dl - 0.5) * 6 * s, wh * (0.95 + 0.1 * k * (dl - 0.5)), 20 * s,
                  math.pi / 2 * k + (tilt - 0.5) * 0.12, np.clip(color, 0, 1), 0.9, 0.08)
        if size < 0.5:
            p.lay(wx, wy + wh / 2 + 3 * s, 40 * s, 9 * s, (dx - 0.5) * 0.2, snow, 0.85, 0.05)
        if glow and lit and i == 0:
            p.dot(wx, wy, 70 * s, rgb(glow), 0.18, 22 * s)
    # The roof, deep in snow: broad strokes along it, cool on the slope, warmer up at the ridge.
    over = (x1 - x0) * 0.06
    roof = [(x0 - over, eave + 6 * s), (x1 + over, eave + 6 * s), (x1 - over + jog[7], ridge), (x0 + over, ridge)]
    p.shape(roof, mix(snow, shade, 0.45), 0.97, 3 * s)
    for u, v, tone, ln, tilt in rng.random((int(200 * (x1 - x0) / (600 * s)) + 40, 5)):
        half = mix((x1 - x0) / 2 - over, (x1 - x0) / 2 + over, v)
        p.lay((x0 + x1) / 2 + half * (2 * u - 1) * 0.9, mix(ridge + 6 * s, eave, v), (60 + 90 * ln) * s,
              (14 + 16 * tone) * s, (tilt - 0.5) * 0.24 + (math.pi if tilt > 0.5 else 0),
              np.clip(mix(snow, shade, 0.1 + 0.5 * v * tone), 0, 1), 0.7, 0.07)
    # Along the ridge and the eaves the snow lies in lumps, and hangs over the eaves.
    for u, ln, tone, tilt in rng.random((int((x1 - x0) / (50 * s)) + 3, 4)):
        p.lay(mix(x0 + over, x1 - over, u), ridge + 3 * s, (40 + 50 * ln) * s, (12 + 8 * ln) * s, (tilt - 0.5) * 0.16,
              np.clip(mix(snow, shade, 0.1 * tone), 0, 1), 0.85, 0.05)
    for u, ln, tone, tilt in rng.random((11, 4)):
        heap(p, mix(x0 - over, x1 + over, 0.04 + 0.92 * u), eave + 8 * s, (22 + 22 * ln) * s, (12 + 8 * tone) * s,
             snow, shade, side, (tone, tilt, ln, u))
    # A brick chimney, shaded on the side away from the light, capped with snow.
    cx = mix(x0, x1, 0.72)
    sweep(p, cx, ridge + 10 * s, cx + 2 * s, ridge - 72 * s, 32 * s, brick, 0.95, 0.12)
    sweep(p, cx - side * 9 * s, ridge + 6 * s, cx - side * 8 * s, ridge - 66 * s, 13 * s, mix(brick, shade, 0.45), 0.6)
    heap(p, cx + s, ridge - 74 * s, 20 * s, 10 * s, snow, shade, side, rng.random(4))


def magpie(p, x, y, z, hour, side, s, rng):
    """The magpie, perched facing left with its feet at (x, y), in a few strokes: dark body, white flank, long tail."""
    bird, flank, shade, snow = rgb(hour["bird"]), rgb(hour["flank"]), rgb(hour["shadow"]), rgb(hour["snow"])
    sheen = mix(bird, shade, 0.4)  # the blue-green on its wing and tail
    j = rng.normal(0, 0.03, 16) * z  # no stroke lands just where it was meant to
    sweep(p, x + 0.15 * z + j[0], y - 0.36 * z + j[1], x + 1.35 * z + j[2], y + 0.26 * z + j[3], 0.24 * z, bird, 0.97,
          0.2)  # tail
    sweep(p, x + 0.4 * z, y - 0.22 * z, x + 1.15 * z + j[4], y + 0.16 * z + j[5], 0.08 * z, sheen, 0.6)  # its sheen
    sweep(p, x - 0.4 * z + j[6], y - 0.66 * z + j[7], x + 0.38 * z, y - 0.2 * z, 0.46 * z, bird, 0.97, 0.2)  # body
    sweep(p, x - 0.3 * z, y - 0.7 * z, x + 0.3 * z, y - 0.48 * z, 0.07 * z, mix(bird, snow, 0.15), 0.4)  # light on its back
    sweep(p, x - 0.3 * z + j[8], y - 0.44 * z + j[9], x + 0.22 * z, y - 0.24 * z, 0.3 * z, flank, 0.92, 0.12)  # flank
    sweep(p, x - 0.2 * z, y - 0.3 * z, x + 0.14 * z, y - 0.2 * z, 0.08 * z, mix(flank, shade, 0.55), 0.55)
    sweep(p, x - 0.1 * z + j[10], y - 0.64 * z + j[11], x + 0.42 * z, y - 0.36 * z, 0.15 * z, sheen, 0.8)  # wing
    p.dot(x - 0.36 * z + j[12], y - 0.77 * z + j[13], 0.16 * z, bird, 0.97, 1.4 * s)  # head
    sweep(p, x - 0.4 * z + side * 0.04 * z, y - 0.88 * z, x - 0.18 * z, y - 0.8 * z, 0.06 * z, mix(bird, snow, 0.3),
          0.45)  # light on its crown and nape
    brush(p, x - 0.48 * z, y - 0.79 * z + j[14], x - 0.72 * z, y - 0.74 * z + j[15], 0.07 * z, 0, bird, 0.95,
          0.5 * s)  # beak
    brush(p, x - 0.04 * z, y - 0.24 * z, x - 0.02 * z, y, 0.04 * z, 0, bird, 0.85, 0.5 * s)  # legs


def magpie_scene(p, hour, w, h, hz, s, rng):
    mist, haze = rgb(hour["mist"]), rgb(hour["sky"][1][1])
    snow, shade, wood, warm = rgb(hour["snow"]), rgb(hour["shadow"]), rgb(hour["wood"]), rgb(hour["reflection"])
    L = hour["light"]
    side = 1 if L["x"] > 0.5 else -1  # the side the light comes from
    # The winter air is still: the sky laid over again in broad, quiet strokes of its own colors.
    ref = np.asarray(p.canvas.convert("RGB").filter(ImageFilter.GaussianBlur(40 * s)), np.float32) / 255
    for u, v, ln, wd, tilt, tone in rng.random((int(1100 * s) + 100, 6)):
        x, y = (u * 1.08 - 0.04) * w, v ** 0.9 * (hz + 0.01 * h)
        color = ref[int(min(max(y, 0), h - 1)), int(min(max(x, 0), w - 1))] * (0.985 + 0.04 * tone)
        note = 0.22 * min(1.0, color.mean() / 0.55) ** 2  # a cooler note or a warmer one, fainter in the dark
        if tone > 0.88:
            color = mix(color, rgb(hour["accent_sky"]), note)
        elif tone < 0.1:
            color = mix(color, warm, note)
        p.lay(x, y, (180 + 320 * ln) * s, (46 + 50 * wd) * s, -0.12 + (tilt - 0.5) * 0.8 + (math.pi if tone > 0.5 else 0),
              np.clip(color, 0, 1), 0.3 + 0.35 * ln, 0.035)
    halo(p, hour, w, h, s)
    if L["r"] > 0:
        disc(p, L["x"] * w, L["y"] * h, L["r"] * h, rgb(L["color"]), s)
    # Far off: frosted woods along the horizon, pale in the cold air.
    crowns = rng.random(40)
    for u, v, tone, ln, tilt in rng.random((int(1300 * s) + 200, 5)):
        y = hz + 0.006 * h - (0.012 + 0.03 * eased(crowns, u)) * h * v ** 0.7
        color = mix(snow, haze, 0.5) if tone > 0.78 else mix(mist, haze, 0.5 + 0.4 * tone)
        p.lay((u * 1.04 - 0.02) * w, y, (30 + 44 * ln) * s, (16 + 18 * ln) * s, -math.pi / 2 + (tilt - 0.5) * 2.4,
              np.clip(color, 0, 1), 0.2 + 0.25 * ln, 0.05)
    # The snow, laid warm where the light reaches it and cool in its hollows, flecked with both.
    for u, v, tone, ln, tilt, fleck in rng.random((int(3000 * s) + 400, 6)):
        y = hz + (h - hz) * (0.01 + 0.99 * v) ** 1.25
        x = (u * 1.04 - 0.02) * w
        depth = (y - hz) / (h - hz)
        drift = math.sin(x / (700 * s) + y / (150 * s) + math.sin(x / (1300 * s)) * 2)
        color = mix(snow, shade, np.clip(0.18 - 0.12 * drift + 0.3 * (tone - 0.5), 0, 0.55))
        if fleck < 0.12:
            color = mix(color, warm, 0.6)
        elif fleck < 0.16:
            color = mix(color, rgb(hour["accent_water"]), 0.5)
        # Laid into the ground's own color, and closer to it where the two are far apart, as by night.
        ground = ref[int(min(max(y, 0), h - 1)), int(min(max(x, 0), w - 1))]
        color = mix(ground, color, 0.6 * min(1.0, 0.15 / max(0.15, float(np.abs(color - ground).mean()))))
        p.lay(x, y, (40 + 120 * ln ** 2) * s * (0.35 + depth), (16 + 28 * tone * ln) * s * (0.35 + depth),
              (tilt - 0.5) * (0.2 + 0.6 * depth) + (math.pi if fleck > 0.5 else 0), np.clip(color, 0, 1),
              0.3 + 0.35 * ln, 0.045)
    far = mix(mist, haze, 0.4)
    for tx, tall in ((0.04, 0.25), (0.12, 0.32), (0.2, 0.21), (0.5, 0.19), (0.57, 0.3), (0.93, 0.27), (0.98, 0.22)):
        tree(p, tx * w, hz + 0.03 * h, tall * h, far, mix(snow, haze, 0.25), mix(shade, haze, 0.4), side, s, rng,
             frost=1.0, levels=4, alpha=0.75)
    # Hedges on the slope behind the fence: a dark tangle of twigs, lower toward their ends, snow lying along
    # their tops in lumps and frost on the twigs that stick out of it.
    hedge = mix(mist, wood, 0.45)
    for hx0, hx1, hy in ((0.0, 0.24, 0.53), (0.44, 0.6, 0.51)):
        tops, sags = rng.random(10), rng.random(14)

        def crown(x, hy=hy, hx0=hx0, hx1=hx1, tops=tops):
            u = min(max((x / w - hx0) / (hx1 - hx0), 0.0), 1.0)
            return hy * h - (14 + (26 + 34 * eased(tops, u)) * math.sin(math.pi * u) ** 0.5) * s

        def under(x, hx0=hx0, hx1=hx1, sags=sags, crown=crown):
            return crown(x) + (10 + 22 * eased(sags, (x / w - hx0) / (hx1 - hx0))) * s

        for u, v, tone, tilt in rng.random((int(900 * (hx1 - hx0)), 4)):
            x = mix(hx0, hx1, u) * w
            p.lay(x, mix(hy * h, crown(x), v), (20 + 30 * tone) * s, (8 + 8 * tone) * s, -math.pi / 2 + (tilt - 0.5) * 1.6,
                  np.clip(hedge * (0.6 + 0.4 * tone), 0, 1), 0.8, 0.15)
        snowbank(p, ((hx0 * w, hx1 * w),), lambda x, crown=crown: crown(x) - 4 * s, under, snow, shade, warm, side, s,
                 rng, int(1000 * (hx1 - hx0)))
        for u, v, tone, tilt in rng.random((int(400 * (hx1 - hx0)), 4)):
            x = mix(hx0, hx1, u) * w
            y = crown(x) + 2 * s
            sweep(p, x, y, x + (tilt - 0.5) * 40 * s, y - (10 + 26 * v) * s, (3 + 3 * tone) * s,
                  mix(snow, shade, 0.2 + 0.4 * tone) if tone > 0.45 else hedge * 0.8, 0.7, 0.05)
    farmhouse(p, 0.84 * w, 0.95 * w, 0.455 * h, 0.405 * h, 0.56 * h, hour, side, s, rng)
    farmhouse(p, 0.63 * w, 0.8 * w, 0.43 * h, 0.35 * h, 0.57 * h, hour, side, s, rng, lit=True)
    tree(p, 0.6 * w, 0.58 * h, 0.4 * h, mix(wood, mist, 0.25), snow, shade, side, s, rng, levels=5)

    # The fence runs from near on the left to farther on the right, its top as uneven as the weaving.
    def base(x):
        u = x / w
        return (0.665 - 0.075 * u + 0.008 * math.sin(4.5 * u + 0.6)) * h

    def top(x):
        rough = 1 + 0.07 * math.sin(x / (97 * s)) + 0.05 * math.sin(x / (41 * s) + 1)
        return base(x) - (0.085 - 0.03 * x / w) * h * rough

    # The snow on it: heaped above the weave in rounded lumps, hanging down its front nearly to the ground
    # here, hardly at all there.
    lumps, drapes, hangs = rng.random(60), rng.random(16) ** 1.3, rng.random(80)

    def crest(x):
        return top(x) - (6 + 26 * eased(lumps, x / w)) * s

    def low(x):
        u = x / w
        return top(x) + (0.08 + 0.55 * eased(drapes, u) + 0.2 * eased(hangs, u)) * (base(x) - top(x))

    gate0, gate1 = 0.3 * w, 0.4 * w
    runs = ((-0.02 * w, gate0), (gate1, 1.02 * w))
    shift, length, strength = hour["cast"]

    def along(u):  # a point along the fence, skipping the gate
        x = mix(-0.02 * w, 1.02 * w - (gate1 - gate0), u)
        return x + (gate1 - gate0) if x > gate0 else x

    def cast(x, y):  # where a point at (x, y) throws its shadow on the snow
        rise = base(x) - y
        return x + rise * shift, base(x) + rise * length

    # Where the stakes stand out of the snow is settled first, so their shadows can fall with the fence's.
    stakes, x = [], -0.02 * w
    for step, rise, tilt, tone in rng.random((40, 4)):
        x += (120 + 320 * step) * s
        if x > 1.02 * w:
            break
        if not gate0 - 40 * s < x < gate1 + 40 * s:
            stakes.append((x, x + (tilt - 0.5) * 50 * s, crest(x) - (4 + 60 * rise ** 2) * s, (tone, rise, tilt, step)))
    # The shadows first, on the snow toward us: a glaze, broad strokes along it, a grain the way the light runs
    # with light from the sky coming back into it, and the stakes' shadows falling on past it in stripes.
    for x0, x1 in runs:
        xs = np.linspace(x0, x1, 40)
        p.shape([(x, base(x)) for x in xs] + [cast(x, crest(x)) for x in xs[::-1]], shade, 0.34 * strength, 12 * s)
    for u, v, ln, wd, tone in rng.random((360, 5)):
        x = along(u)
        (sx, sy), (ex, ey) = cast(x, mix(base(x), crest(x), v)), cast(x + 40 * s, mix(base(x), crest(x), v))
        p.lay(sx, sy, (100 + 180 * ln) * s, (16 + 24 * wd) * s * min(2.0, 0.6 + 0.5 * length),
              math.atan2(ey - sy, ex - sx) + (tone - 0.5) * 0.1 + (math.pi if tone > 0.5 else 0),
              np.clip(mix(shade, shade * 0.8, tone), 0, 1), (0.18 + 0.2 * tone) * (1 - 0.4 * v) * strength, 0.05)
    ray = math.atan2(length, shift)  # from the fence toward us: each stroke lands near the fence and drags out
    for u, v, ln, wd, tone in rng.random((180, 5)):
        x = along(u)
        (bx, by), (cx, cy) = (x, base(x)), cast(x, crest(x))
        color = mix(shade, shade * 0.8, tone) if tone < 0.6 else mix(shade, snow, 0.3 + 0.6 * (tone - 0.6))
        reach = math.hypot(cx - bx, cy - by) * (0.2 + 0.3 * ln) + 30 * s
        a = ray + (wd - 0.5) * 0.12
        p.lay(mix(bx, cx, 0.6 * v) + math.cos(a) * reach / 2, mix(by, cy, 0.6 * v) + math.sin(a) * reach / 2, reach,
              (24 + 30 * wd) * s, a, np.clip(color, 0, 1), (0.12 + 0.14 * ln) * strength, 0.05)
    for x, tx, ty, (tone, rise, tilt, step) in stakes:
        sweep(p, *cast(x, crest(x)), *cast(tx, ty), (8 + 5 * tone) * s * min(2.0, 0.6 + 0.5 * length), shade * 0.85,
              0.4 * strength, 0.05)
    gb = base((gate0 + gate1) / 2)
    gate_h = 0.1 * h
    rails = [gb - gate_h * f for f in (0.15, 0.55, 0.9)]
    lean = rng.normal(0, 7, 4) * s  # an old gate: the posts lean, the rails are not quite level
    parts = [((gate0, gb + 6 * s), (gate0 + lean[0], gb - gate_h * 1.28), 27, 0.15),
             ((gate1, gb + 6 * s), (gate1 + lean[1], gb - gate_h * 1.24), 25, -0.1)]
    parts += [((gate0 + 6 * s, y), (gate1 - 6 * s, y + lean[2 + i % 2]), 12 + i, 0.25) for i, y in enumerate(rails)]
    parts += [((gate0 + 14 * s, rails[0]), (gate1 - 14 * s, rails[2]), 11, 0.1)]
    parts += [((mix(gate0, gate1, f), rails[0] + 8 * s), (mix(gate0, gate1, f) + 3 * s, rails[2] - 10 * s), 8, 0.2)
              for f in (0.33, 0.66)]
    # The gate's shadow: each bar in a few strokes, wider and fainter as it falls farther.
    for ((ax, ay), (bx, by), width, bend), draws in zip(parts, rng.random((len(parts), 3, 3))):
        for k, (dx, dy, wd) in enumerate(draws):
            t0, t1 = k / 3 - 0.06, (k + 1) / 3 + 0.06
            (cx0, cy0), (cx1, cy1) = cast(mix(ax, bx, t0), mix(ay, by, t0)), cast(mix(ax, bx, t1), mix(ay, by, t1))
            sweep(p, cx0 + (dx - 0.5) * 8 * s, cy0 + (dy - 0.5) * 8 * s, cx1, cy1, width * s * (1.8 + 0.8 * wd),
                  shade * 0.85, 0.42 * strength, 0.05)
    # The wattle: dark withies woven along it, a few catching the light.
    for x0, x1 in runs:
        xs = np.linspace(x0, x1, 60)
        p.shape([(x, top(x) + 4 * s) for x in xs] + [(x, base(x)) for x in xs[::-1]], wood * 0.4, 0.95, 3 * s)
    for u, row, ln, tone, tilt in rng.random((260, 5)):
        x = along(u)
        p.lay(x, mix(base(x), top(x), 0.1 + 0.6 * row), (70 + 120 * ln) * s, (14 + 12 * tone) * s,
              -0.06 + (tilt - 0.5) * 0.3 + (math.pi if tilt > 0.5 else 0), np.clip(wood * (0.35 + 0.4 * tone), 0, 1),
              0.8, 0.2)
    for u, row, ln, tone, tilt in rng.random((700, 5)):
        x = along(u)
        withy = tone > 0.8  # a withy catching the light: long and thin
        color = mix(wood, snow, 0.3) if withy else wood * (0.3 + 0.5 * tone)
        p.stroke(x, mix(base(x), top(x), 0.06 + 0.8 * row), (60 + 120 * ln if withy else 40 + 90 * ln) * s,
                 (2 + 2 * tone if withy else 3 + 4 * tone) * s, -0.06 + (tilt - 0.5) * 0.5, 1.2 * (tilt - 0.5),
                 np.clip(color, 0, 1), 0.85, 1.1 * s)
    snowbank(p, runs, crest, low, snow, shade, warm, side, s, rng, 1600)
    # The stakes, standing up out of the snow here and there, thin and leaning, a few with snow on top.
    for x, tx, ty, (tone, rise, tilt, step) in stakes:
        limb(p, [(x, low(x)), (mix(x, tx, 0.5) + (tone - 0.5) * 6 * s, mix(low(x), ty, 0.5)), (tx, ty)],
             (6 + 4 * tone) * s, (3 + 3 * tone) * s, wood * (0.45 + 0.3 * tone), 0.92, 1.2 * s)
        if rise > 0.4:
            heap(p, tx, ty + 2 * s, 9 * s, 5 * s, snow, shade, side, (tone, rise, tilt, step))
    # Snow drifted against the foot of the fence, in its own shadow.
    for u, ln, tone, tilt in rng.random((200, 4)):
        x = mix(-0.02, 1.02, u) * w
        p.lay(x, base(x) + 6 * s, (60 + 90 * ln) * s, (12 + 14 * tone) * s, -0.06 + (math.pi if tilt > 0.5 else 0),
              np.clip(mix(snow, shade, 0.7 + 0.2 * tone), 0, 1), 0.6, 0.06)
    # The gate: rough sticks, two posts, three rails, a brace and two palings, each bowed a little (the rails
    # sag under the snow). Each is a dark core, then four strokes laid end to end, none quite in line or the
    # same width, and the light caught along the posts.
    def on(part, t, off=0.0):
        (ax, ay), (bx, by), width, bend = part
        d = math.hypot(bx - ax, by - ay) or 1
        o = bend * (1 - (2 * t - 1) ** 2) * 0.12 * d + off
        return mix(ax, bx, t) + (ay - by) / d * o, mix(ay, by, t) + (bx - ax) / d * o

    for part, draws in zip(parts, rng.random((len(parts), 4, 4))):
        (ax, ay), (bx, by), width, bend = part
        limb(p, [on(part, t) for t in (0, 0.25, 0.5, 0.75, 1)], width * s * 0.8, width * s * 0.7, wood * 0.55, 0.9, 1.2 * s)
        for k, (o0, o1, tone, wd) in enumerate(draws):
            t0, t1 = k / 4 - 0.08, (k + 1) / 4 + 0.08
            sweep(p, *on(part, t0, (o0 - 0.5) * 5 * s), *on(part, t1, (o1 - 0.5) * 5 * s), width * s * (0.8 + 0.45 * wd),
                  wood * (0.6 + 0.55 * tone), 0.9, 0.2)
        if abs(by - ay) > abs(bx - ax):
            for t0, t1, o in ((0.05, 0.5, draws[0][0]), (0.45, 0.95, draws[1][1])):
                (x0, y0), (x1, y1) = on(part, t0, side * width * s * 0.3), on(part, t1, side * width * s * 0.3)
                sweep(p, x0, y0, x1, y1, width * s * 0.3, mix(wood, snow, 0.5), 0.4 + 0.3 * o, 0.1)
    for part, (k0, k1, tone) in zip(parts[2:5], rng.random((3, 3))):
        for a0, a1 in ((0.02 + 0.1 * k0, 0.45), (0.5, 0.88 + 0.1 * k1)):
            (x0, y0), (x1, y1) = on(part, a0), on(part, a1)
            sweep(p, x0, y0 - part[2] * 0.6 * s, x1, y1 - part[2] * 0.6 * s, part[2] * 0.8 * s, mix(snow, warm, 0.3 * tone),
                  0.85, 0.06)
    for (gx, gy), tones in zip((parts[0][1], parts[1][1]), rng.random((2, 4))):
        heap(p, gx, gy + 4 * s, 20 * s, 10 * s, snow, shade, side, tones)
    # The magpie stands on the top rail.
    mx, my = on(parts[4], 0.66)
    magpie(p, mx, my - parts[4][2] * 0.45 * s, 0.035 * h, hour, side, s, rng)


SERIES = {
    "hours": dict(hours=HOURS, scene=harbor_scene, seed=1872, horizon=HORIZON),
    "lilies": dict(hours=LILIES, scene=lilies_scene, seed=1914, horizon=0.0),
    "haystacks": dict(hours=HAYSTACKS, scene=haystacks_scene, seed=1890, horizon=0.52),
    "magpie": dict(hours=MAGPIE, scene=magpie_scene, seed=1869, horizon=0.46),
}


def render(scale=1.0, only=None, series="hours"):
    w, h = int(3840 * scale), int(2160 * scale)
    kind = SERIES[series]
    brushwork = Brushwork(w, h, kind["seed"], kind["horizon"])
    rng = np.random.default_rng(99)
    noise = (smooth_noise(rng, w, h, int(260 * scale) or 1), smooth_noise(rng, w, h, int(120 * scale) or 1))
    out = {}
    for name, hour in kind["hours"].items():
        if only and name not in only:
            continue
        out[name] = paint(dict(hour, horizon=kind["horizon"]), brushwork, noise, kind["scene"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scale", type=float, default=1.0)
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--series", choices=list(SERIES), nargs="*", default=list(SERIES))
    args = ap.parse_args()
    for series in args.series:
        paintings = render(args.scale, args.only, series)
        folder = args.out / series
        folder.mkdir(parents=True, exist_ok=True)
        for name, img in paintings.items():
            img.save(folder / f"{name}.jpg", quality=90, optimize=True, progressive=True, subsampling=0)
            print("painted", folder / f"{name}.jpg")


if __name__ == "__main__":
    main()
