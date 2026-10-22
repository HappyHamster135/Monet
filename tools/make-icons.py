"""Paints Monet's icon theme: every icon a small oil painting, the way Monet
painted. Short strokes of unmixed color laid side by side, shadows in violet
and blue rather than grey, light in warm cream, and the paint thick enough to
catch the light from the top left.

Each motif comes from Monet's world, not from a computer's: a palette for
Settings, a night canvas on an easel for Terminal, the harbor's masts rising
like a graph against the sunset for System Monitor, a market bouquet for the
Store, a garden pot from Giverny for Trash, folders cut from the paintings.
KDE's apps and the ones Bazzite brings (the browser, Steam, Lutris, its portal
and Flatpak tools) get a Monet motif too; games keep their covers, everything
else comes from Breeze.

Icons are painted at 512 x 512 and kept as 256 x 256 images inside SVGs.

Run from the repository root:  python3 tools/make-icons.py
Also writes the brush texture Monet uses for game covers without artwork,
and the pictures in Monet Settings.
"""

import base64
import colorsys
import importlib.util
import io
import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
THEME = ROOT / "linux" / "share" / "icons" / "Monet"
TEXTURES = ROOT / "linux" / "share" / "monet" / "textures"
HOURS = ROOT / "linux" / "share" / "wallpapers" / "Monet" / "contents" / "hours"

N = 512          # the painting's size: four times the 128 grid the motifs are laid out on
S = N / 128
LIGHT = (-0.55, -0.83)  # light from the top left


# The painter ------------------------------------------------------------------

def hexrgb(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


def blur(a, radius):
    img = Image.fromarray(np.clip(a * 255, 0, 255).astype(np.uint8), "L")
    return np.asarray(img.filter(ImageFilter.GaussianBlur(radius))).astype(np.float32) / 255


def shape(draw):
    """A mask drawn at twice the painting's size, then shrunk, for soft edges."""
    big = Image.new("L", (N * 2, N * 2), 0)
    draw(ImageDraw.Draw(big), 2 * S)
    return np.asarray(big.resize((N, N), Image.LANCZOS)).astype(np.float32) / 255


def poly(points):
    return shape(lambda d, k: d.polygon([(x * k, y * k) for x, y in points], fill=255))


def circle(cx, cy, r):
    return shape(lambda d, k: d.ellipse([(cx - r) * k, (cy - r) * k, (cx + r) * k, (cy + r) * k], fill=255))


def box(x0, y0, x1, y1, r=0):
    return shape(lambda d, k: d.rounded_rectangle([x0 * k, y0 * k, x1 * k, y1 * k], radius=r * k, fill=255))


def band(points, width):
    """A thick line with round ends and joints."""
    def draw(d, k):
        d.line([(x * k, y * k) for x, y in points], width=int(width * k), fill=255, joint="curve")
        for x, y in points:
            d.ellipse([(x - width / 2) * k, (y - width / 2) * k, (x + width / 2) * k, (y + width / 2) * k], fill=255)
    return shape(draw)


def ellipse(cx, cy, rx, ry, angle=0.0, steps=90):
    a = math.radians(angle)
    return [(cx + rx * math.cos(t) * math.cos(a) - ry * math.sin(t) * math.sin(a),
             cy + rx * math.cos(t) * math.sin(a) + ry * math.sin(t) * math.cos(a))
            for t in (2 * math.pi * i / steps for i in range(steps))]


def cut(a, *others):
    for o in others:
        a = a - o
    return np.clip(a, 0, 1)


def join(*masks):
    return np.clip(sum(masks), 0, 1)


def vary(rgb, rng, amount):
    """Broken color: each stroke a little off in hue and strength, like unmixed paint."""
    h, l, s = colorsys.rgb_to_hls(*[float(c) for c in rgb])
    h = (h + rng.normal(0, amount * 0.5)) % 1
    l = min(1, max(0, l + rng.normal(0, amount * 0.6)))
    s = min(1, max(0, s + rng.normal(0, amount * 1.8)))
    return np.array(colorsys.hls_to_rgb(h, l, s), np.float32)


def lighting(x, y):
    """Where the light falls: +1 toward the top left, -1 in shade."""
    v = np.asarray((64 - np.asarray(x)) / 64 * 0.35 + (64 - np.asarray(y)) / 64)
    return v[..., None] if np.ndim(v) else v


def lit(top, bottom, y0=0, y1=128, warm="#FFE2B0", cool="#4A4A9A", light=0.22, shade=0.28):
    """Local color: top to bottom, warmed where the light falls and cooled,
    not darkened, in shade, the way Monet painted shadows."""
    t, b, w, c = hexrgb(top), hexrgb(bottom), hexrgb(warm), hexrgb(cool)

    def at(x, y):
        k = np.clip((np.asarray(y) - y0) / (y1 - y0), 0, 1)
        k = k[..., None] if np.ndim(k) else k
        base = t * (1 - k) + b * k
        lv = lighting(x, y)
        wk, ck = np.clip(lv, 0, 1) * light, np.clip(-lv, 0, 1) * shade
        return base * (1 - wk - ck) + w * wk + c * ck
    return at


def sampled(img, frame, light=0.18, warm="#FFE6B8", cool="#3C3E86"):
    """Colors taken from a painting laid over frame (x0, y0, x1, y1), lit like the rest."""
    arr = np.asarray(img).astype(np.float32) / 255
    h, w = arr.shape[:2]
    x0, y0, x1, y1 = frame
    wc, cc = hexrgb(warm), hexrgb(cool)

    def at(x, y):
        xi = np.clip(((np.asarray(x) - x0) / (x1 - x0) * (w - 1)).astype(int), 0, w - 1)
        yi = np.clip(((np.asarray(y) - y0) / (y1 - y0) * (h - 1)).astype(int), 0, h - 1)
        lv = lighting(x, y)
        wk, ck = np.clip(lv, 0, 1) * light, np.clip(-lv, 0, 1) * light
        return arr[yi, xi] * (1 - wk - ck) + wc * wk + cc * ck
    return at


def one(color):
    c = hexrgb(color)
    return lambda x, y: c


def painting(name, crop, color=1.35):
    """A piece of one of the Hours, its color brought back up (small pieces look muddy)."""
    img = Image.open(HOURS / f"{name}.jpg").convert("RGB").crop(crop)
    return ImageEnhance.Contrast(ImageEnhance.Color(img).enhance(color)).enhance(1.1)


def flat(degrees):
    a = math.radians(degrees)
    return lambda x, y: a


def around(cx, cy):
    """Strokes that follow a round form."""
    return lambda x, y: math.atan2(y - cy, x - cx) + math.pi / 2


def outward(cx, cy):
    """Strokes that spread from a center, like petals."""
    return lambda x, y: math.atan2(y - cy, x - cx)


class Canvas:
    """One small oil painting: color, coverage and the paint's relief."""

    def __init__(self, seed):
        self.rgb = np.zeros((N, N, 3), np.float32)
        self.alpha = np.zeros((N, N), np.float32)
        self.height = np.zeros((N, N), np.float32)
        self.rng = np.random.default_rng(seed)

    def ground(self, mask, color_at):
        """The first, thin layer, so no canvas shows between the strokes."""
        ys, xs = np.mgrid[0:N, 0:N].astype(np.float32) + 0.5
        a = mask[..., None]
        self.rgb = self.rgb * (1 - a) + color_at(xs / S, ys / S) * a
        self.alpha = self.alpha + mask * (1 - self.alpha)
        self.height = self.height * (1 - mask) + mask * 0.25

    def dab(self, cx, cy, length, width, angle, color, clip, opacity=1.0, thick=1.0, dry=0.6):
        """One stroke of a loaded brush: heavier where it lands, streaked by the
        bristles, breaking up as the paint runs out."""
        r = length / 2 + width
        x0, x1 = max(0, int(cx - r)), min(N, int(cx + r) + 2)
        y0, y1 = max(0, int(cy - r)), min(N, int(cy + r) + 2)
        if x0 >= x1 or y0 >= y1:
            return
        ys, xs = np.mgrid[y0:y1, x0:x1].astype(np.float32) + 0.5
        dx, dy = xs - cx, ys - cy
        ca, sa = math.cos(angle), math.sin(angle)
        u, v = dx * ca + dy * sa, -dx * sa + dy * ca
        t = u / (length / 2)
        half = width / 2 * np.clip(1 - np.abs(t) ** 2.2, 0, 1) ** (1 / 2.2) * (1 - 0.2 * t)
        # Antialiased, and fading where the stroke is thinner than a pixel (no needles at the tips).
        a = np.clip(half - np.abs(v) + 0.7, 0, 1) * np.clip(half * 1.5, 0, 1)
        p1, p2 = self.rng.uniform(0, 6.3, 2)
        f1, f2 = self.rng.uniform(9, 15), self.rng.uniform(20, 31)
        w = v / max(width / 2, 1)
        bristle = 0.8 + 0.13 * np.sin(w * f1 + p1) + 0.07 * np.sin(w * f2 + p2)
        tail = 1 - dry * np.clip((t - 0.25) / 0.75, 0, 1) ** 1.5 * (0.5 + 0.5 * np.sin(w * f2 * 1.7 + p1))
        a = a * np.clip(bristle, 0, 1) * np.clip(tail, 0, 1) * opacity * clip[y0:y1, x0:x1]
        here = (slice(y0, y1), slice(x0, x1))
        self.rgb[here] = self.rgb[here] * (1 - a[..., None]) + color * a[..., None]
        self.alpha[here] = self.alpha[here] + a * (1 - self.alpha[here])
        # Paint piles where the brush lands and along the stroke's edges.
        ridge = (0.7 + 0.3 * bristle) * (1 + 0.5 * np.clip(-t, 0, 1)) * (0.75 + 0.25 * np.clip(np.abs(v) / np.maximum(half, 1e-3), 0, 1))
        self.height[here] = self.height[here] * (1 - 0.7 * a) + a * thick * ridge

    def paint(self, mask, color_at, size, flow, layers=3, jitter=0.05, wander=0.3, accents=(), accent_rate=0.07,
              opacity=1.0, thick=1.0, ground=True):
        """Paints an area: a thin ground, then strokes over it, coarse to fine.
        size is the stroke width on the 128 grid; flow(x, y) their direction;
        accents, the odd stroke of another color (Monet's broken color)."""
        if ground:
            self.ground(mask * opacity, color_at)
        clip = np.clip(mask * 1.04, 0, 1)
        ys, xs = np.nonzero(mask > 0.5)
        if len(xs) == 0:
            return
        bx0, bx1, by0, by1 = xs.min(), xs.max(), ys.min(), ys.max()
        for layer in range(layers):
            s = size * S * (1.2 - 0.3 * layer)
            step = s * 0.78
            gy, gx = np.mgrid[by0:by1 + 1:step, bx0:bx1 + 1:step]
            pts = np.stack([gx.ravel(), gy.ravel()], 1) + self.rng.uniform(-step / 2, step / 2, (gx.size, 2))
            self.rng.shuffle(pts)
            for px, py in pts:
                if mask[int(min(N - 1, max(0, py))), int(min(N - 1, max(0, px)))] < 0.5:
                    continue
                col = vary(color_at(np.float32(px / S), np.float32(py / S)), self.rng, jitter)
                if accents and self.rng.random() < accent_rate:
                    col = vary(hexrgb(self.rng.choice(accents)), self.rng, jitter)
                ang = flow(px / S, py / S) + self.rng.normal(0, wander)
                self.dab(px, py, s * self.rng.uniform(1.8, 3.0), s * self.rng.uniform(0.6, 0.9), ang, col, clip,
                         opacity=opacity * self.rng.uniform(0.78, 1.0), thick=thick)

    def mark(self, points, width, color, clip=None, thick=1.8):
        """A mark drawn with the brush along a line: a glyph, a mast, a handle."""
        clip = np.ones((N, N), np.float32) if clip is None else clip
        c = hexrgb(color) if isinstance(color, str) else color
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            ax, ay, bx, by = ax * S, ay * S, bx * S, by * S
            seg = math.hypot(bx - ax, by - ay)
            ang = math.atan2(by - ay, bx - ax)
            n = max(1, int(seg / (width * S * 0.9)))
            for k in range(n):
                f = (k + 0.5) / n
                self.dab(ax + (bx - ax) * f, ay + (by - ay) * f, seg / n * 1.9 + width * S * 0.6, width * S, ang,
                         vary(c, self.rng, 0.04), clip, thick=thick, dry=0.25)
        for x, y in points[1:-1]:  # the brush turning a corner
            self.dab(x * S, y * S, width * S * 1.05, width * S, 0, vary(c, self.rng, 0.04), clip, thick=thick, dry=0)

    def finish(self, relief=1.3, shadow=0.2, size=256):
        """Lights the relief, adds a soft shadow below, and shrinks it to size."""
        h = blur(np.clip(self.height / 2, 0, 1), 2.2) * 2
        gy, gx = np.gradient(h)
        lit_side = np.clip(-(gx * LIGHT[0] + gy * LIGHT[1]) * relief * S, -0.35, 0.35)
        rgb = self.rgb * (1 + lit_side[..., None] * 0.55)
        rgb = rgb + (np.clip(lit_side - 0.14, 0, 1) * 0.55)[..., None] * np.array([1.0, 0.96, 0.88], np.float32)
        ys, xs = np.mgrid[0:N, 0:N].astype(np.float32)
        rgb = np.clip(rgb * (1 + (np.sin(xs * 1.9) * np.sin(ys * 1.9) * 0.006)[..., None]), 0, 1)  # canvas weave
        under = np.roll(blur(self.alpha, 2.2 * S), int(1.6 * S), 0) * shadow
        a = self.alpha + under * (1 - self.alpha)
        rgb = rgb * self.alpha[..., None] / np.maximum(a, 1e-4)[..., None]
        img = Image.fromarray((np.concatenate([np.clip(rgb, 0, 1), a[..., None]], 2) * 255).astype(np.uint8), "RGBA")
        return img.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")


# The motifs -------------------------------------------------------------------

FIRE = ["#FFC46B", "#FF7A4A", "#D9361A", "#FF8FA0", "#F2552C"]
WOOD = dict(top="#B07A4C", bottom="#6A4528", cool="#3A2A4A", light=0.2, shade=0.25)


def wood(**kw):
    return lit(**dict(WOOD, **kw))


def branding():
    spec = importlib.util.spec_from_file_location("make_branding", Path(__file__).with_name("make-branding.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reflection(c):
    """The sun's reflection: Monet's mark, three strokes on the water."""
    mb = branding()
    for cx, cy, length, width, opacity in mb.DABS:
        m = poly(mb.stroke(cx, cy, length, width))
        c.paint(m, lit("#FF7A45", "#E2471F", y0=80, y1=116, light=0.15, shade=0.2), 4.4, flat(0), layers=2,
                wander=0.08, accents=FIRE, accent_rate=0.22, opacity=min(1, opacity + 0.04), thick=1.2)


def sun_icon():
    c = Canvas(11)
    c.paint(poly(branding().sun_outline()), lit("#FF9A5E", "#E5401C", y0=17, y1=71, light=0.3, shade=0.12, cool="#B8305A"),
            6.4, around(64, 44), layers=3, wander=0.18, accents=FIRE, accent_rate=0.16, thick=1.3)
    reflection(c)
    return c.finish()


def play_icon():
    c = Canvas(12)
    c.paint(poly(branding().play_outline()), lit("#FF9A5E", "#E5401C", y0=16, y1=72, light=0.3, shade=0.12, cool="#B8305A"),
            6.0, flat(-30), layers=3, wander=0.2, accents=FIRE, accent_rate=0.16, thick=1.3)
    reflection(c)
    return c.finish()


def palette_icon():
    """Settings: the painter's palette, with dabs of the Hours' colors."""
    c = Canvas(21)
    board = cut(poly(ellipse(62, 66, 52, 40, -14, 120)), circle(82, 84, 7.5), circle(108, 88, 15))
    c.paint(board, wood(top="#D7A06A", bottom="#8A5531", cool="#5B3A5E", light=0.26, shade=0.3), 7.0, flat(-14),
            wander=0.12, accents=["#E6B880", "#B07040", "#9C6A4A"], accent_rate=0.2, thick=0.9)
    for x, y, r, col, acc in ((36, 56, 9.5, "#F2552C", ["#FFB070", "#D9361A"]), (52, 40, 8.5, "#F6E7C8", ["#FFFFFF", "#E8D2A8"]),
                              (72, 36, 8.5, "#5C88D0", ["#93C6EA", "#2F5A9E"]), (92, 46, 8.5, "#9C7BC0", ["#C9B5EE", "#6A4C96"]),
                              (42, 80, 8, "#3F9A89", ["#7CD3C0", "#2A6A5F"])):
        blob = poly(ellipse(x, y, r, r * 0.86, c.rng.uniform(0, 180), 40))
        c.paint(blob, lit(col, col, light=0.3, shade=0.18), 3.8, around(x, y), wander=0.5, accents=acc,
                accent_rate=0.3, thick=2.4)
    return c.finish()


def easel_icon():
    """Terminal: a night canvas on an easel, with the prompt painted on it."""
    c = Canvas(31)
    for (a, b), w in ((((44, 70), (30, 120)), 6.5), (((84, 70), (98, 120)), 6.5), (((64, 60), (64, 118)), 4.5)):
        c.paint(band((a, b), w), wood(), 2.4, flat(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))), layers=2, wander=0.05)
    night = box(18, 12, 110, 80, 5)
    c.paint(night, lit("#3A4A82", "#141A33", y0=12, y1=80, light=0.12, shade=0.15, warm="#7E8FD0"), 6.4, flat(0),
            wander=0.08, accents=["#9FB4E8", "#5A4A9C", "#2A3566"], accent_rate=0.14)
    for i, (x, y, length) in enumerate(((88, 58, 16), (90, 64, 12), (87, 70, 8))):  # the moon on the water
        c.dab(x * S, y * S, length * S, 2.6 * S, 0, hexrgb("#E8E2C4"), night, opacity=0.8 - 0.18 * i, thick=1.3)
    c.paint(box(20, 78, 108, 86, 3), wood(), 2.2, flat(0), layers=2, wander=0.04, thick=1.1)
    c.mark([(36, 30), (50, 44), (36, 58)], 7.0, "#F3ECD8", night)
    c.mark([(60, 58), (80, 58)], 6.6, "#7CD3C0", night)
    return c.finish()


def harbor_icon():
    """System Monitor: the harbor at sunset, its masts rising like a graph."""
    c = Canvas(41)
    frame = box(12, 16, 116, 112, 16)
    water = np.clip(frame * box(0, 74, 128, 128), 0, 1)
    sky = lit("#8A6FA8", "#F09A6A", y0=16, y1=74, light=0.08, shade=0.1)
    c.ground(frame, sky)
    c.paint(cut(frame, water), sky, 6.0, flat(0), layers=2, wander=0.12, accents=["#F6B590", "#C49ACB", "#FFD08A"],
            accent_rate=0.18, thick=0.9, ground=False)
    c.paint(water, lit("#5A5E96", "#2C3462", y0=74, y1=112, light=0.1, shade=0.15), 5.4, flat(0), wander=0.06,
            accents=["#7A86C6", "#3A4478", "#E58A62"], accent_rate=0.12, thick=0.9)
    c.paint(circle(36, 60, 9), lit("#FF9A5E", "#E5401C", y0=51, y1=69), 2.4, around(36, 60), layers=2, wander=0.2,
            accents=FIRE, accent_rate=0.2, thick=1.6)
    for i, (y, length) in enumerate(((80, 16), (88, 11), (96, 7))):
        c.dab(36 * S, y * S, length * S, 3.0 * S, 0, hexrgb("#F2552C"), frame, opacity=0.9 - 0.2 * i, thick=1.2)
    for x, top in ((58, 60), (72, 48), (86, 54), (100, 34)):
        c.mark([(x, 74), (x, top)], 3.4, "#2A2338", frame, thick=1.4)
        c.dab((x - 1) * S, 76 * S, 13 * S, 4.2 * S, 0, hexrgb("#2A2338"), frame, thick=1.4)
    return c.finish()


def bouquet_icon():
    """Store: a market bouquet in a paper cone."""
    c = Canvas(51)
    leaves = lit("#5E9A5A", "#2F5E3E", light=0.2, shade=0.25)
    for a, b in (((40, 62), (24, 40)), ((88, 60), (104, 42)), ((64, 58), (62, 22))):
        c.paint(band((a, b), 7), leaves, 2.2, flat(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))), layers=2, wander=0.1)
    for x, y, r, col, acc in ((42, 44, 14, "#E0452E", ["#FF7A5A", "#B82A1E"]), (66, 32, 14, "#E88AAE", ["#FFC0D4", "#C0587E"]),
                              (88, 44, 14, "#A988D6", ["#D2BEF2", "#7A5AB0"]), (54, 56, 12, "#F2B84B", ["#FFE08A", "#D08A28"]),
                              (76, 56, 12, "#F6EEE0", ["#FFFFFF", "#E0D2C0"])):
        m = poly(ellipse(x, y, r, r * 0.92, c.rng.uniform(0, 180), 48))
        c.paint(m, lit(col, col, light=0.28, shade=0.22), 3.6, outward(x, y), wander=0.35, accents=acc,
                accent_rate=0.3, thick=1.9)
        c.dab(x * S, y * S, 4 * S, 3 * S, 0.5, vary(hexrgb("#3A2A1A"), c.rng, 0.05), m, opacity=0.5, thick=1.2)
    cone = poly([(34, 62), (94, 62), (66, 118), (60, 118)])
    c.paint(cone, lit("#F1E2C0", "#C2A373", y0=62, y1=118, light=0.22, shade=0.25, cool="#8A7AA0"), 5.6, flat(62),
            wander=0.1, accents=["#FBF4E4", "#D8BF92"], accent_rate=0.18)
    c.mark([(46, 80), (84, 80)], 3.2, "#C0583A", cone, thick=1.5)  # the ribbon
    return c.finish()


def pot_icon(full):
    """Trash: a terracotta pot from the garden at Giverny; crumpled sketches when full."""
    c = Canvas(61 + full)
    if full:
        for x, y, r, tint in ((50, 40, 13, "#E88AAE"), (74, 36, 14, "#5C88D0"), (62, 46, 12, "#F2B84B")):
            m = poly(ellipse(x, y, r, r * 0.88, c.rng.uniform(0, 180), 14))
            c.paint(m, lit("#FBF6EA", "#D6CAB4", y0=y - r, y1=y + r, cool="#9A8CB8"), 2.6, around(x, y), layers=2,
                    wander=0.9, accents=["#FFFFFF", "#CFC2A8", tint], accent_rate=0.22, thick=1.4)
    body = poly([(30, 56), (98, 56), (88, 110), (84, 114), (44, 114), (40, 110)])
    c.paint(body, lit("#E58A5E", "#9A4A2E", y0=44, y1=114, light=0.24, shade=0.32, cool="#5E3A6A"), 6.0, flat(90),
            wander=0.1, accents=["#F2A47A", "#B8583A", "#C9708E"], accent_rate=0.14)
    c.paint(box(24, 44, 104, 58, 5), lit("#F0A272", "#B05A36", y0=44, y1=58, light=0.28, shade=0.25, cool="#6A3A5A"),
            4.6, flat(0), layers=2, wander=0.06, thick=1.4)
    # The shadow side in violet, the way Monet painted shade.
    c.paint(poly([(74, 58), (96, 58), (87, 110), (78, 112)]), lit("#8A4E5E", "#5E3A5E", y0=58, y1=112), 2.6, flat(92),
            layers=2, wander=0.1, opacity=0.35, thick=0.8, ground=False)
    return c.finish()


def frame_icon():
    """Gwenview: a small painting in a gilt frame, as in a museum."""
    c = Canvas(71)
    outer, inner = box(14, 20, 114, 108, 4), box(27, 33, 101, 95, 2)
    gilt = lit("#E8C068", "#9A6A24", y0=20, y1=108, light=0.3, shade=0.3, cool="#6A4A3A")
    c.paint(cut(outer, inner), gilt, 3.4, lambda x, y: 0 if min(y - 20, 108 - y) < min(x - 14, 114 - x) else math.pi / 2,
            wander=0.06, accents=["#FFE7A0", "#B88A3A"], accent_rate=0.25, thick=1.5)
    c.paint(inner, sampled(painting("dawn", (1900, 300, 3100, 1300)), (27, 33, 101, 95)), 4.2, flat(0), wander=0.12,
            jitter=0.04)
    c.mark([(28, 34), (100, 34)], 1.6, "#5A3A1A", outer, thick=0.6)
    return c.finish()


def book_icon():
    """Okular: an open book, its pages written in ink."""
    c = Canvas(81)
    cover = poly([(12, 34), (64, 44), (116, 34), (116, 102), (64, 112), (12, 102)])
    c.paint(cover, lit("#3F9A89", "#245A50", y0=34, y1=112, light=0.2, shade=0.25), 4.0, flat(0), layers=2, wander=0.1)
    paper = lit("#FBF5E6", "#DCCFB4", y0=30, y1=106, light=0.18, shade=0.22, cool="#9A8CB8")
    for page, tilt in ((poly([(16, 30), (62, 38), (62, 104), (16, 96)]), 10), (poly([(66, 38), (112, 30), (112, 96), (66, 104)]), -10)):
        c.paint(page, paper, 5.0, flat(tilt), layers=2, wander=0.08, accents=["#FFFFFF", "#E8DCC4"], accent_rate=0.15)
    for i in range(5):
        y = 46 + i * 10
        c.mark([(22, y), (56, y + 6)], 2.4, "#4A4A7A", None, thick=0.7)
        if i < 4:
            c.mark([(72, y + 6), (106, y)], 2.4, "#4A4A7A", None, thick=0.7)
    c.paint(poly([(60, 38), (68, 38), (68, 106), (60, 106)]), lit("#B8AACC", "#7A6A9A"), 2.0, flat(90), layers=1,
            opacity=0.5, ground=False)
    return c.finish()


def abacus_icon():
    """KCalc: a wooden abacus with beads in the Hours' colors."""
    c = Canvas(91)
    frame = cut(box(16, 22, 112, 106, 6), box(24, 30, 104, 98, 3))
    c.paint(frame, wood(), 3.6, lambda x, y: 0 if (y < 30 or y > 98) else math.pi / 2, wander=0.05, thick=1.3)
    for row, (y, col) in enumerate(zip((40, 56, 72, 88), ("#F2552C", "#5C88D0", "#9C7BC0", "#3F9A89"))):
        c.mark([(24, y), (104, y)], 2.0, "#4A3A2A", None, thick=0.6)
        left = (3, 2, 4, 1)[row]
        for k in range(5):
            x = 34 + k * 11.5 if k < left else 104 - (5 - k) * 11.5 + 6
            bead = poly(ellipse(x, y, 5.6, 6.2, 0, 32))
            c.paint(bead, lit(col, col, light=0.35, shade=0.22), 2.2, around(x, y), layers=2, wander=0.3, thick=1.8)
    return c.finish()


def curtain_icon():
    """Haruna: a little stage, red curtains drawn back from the evening light."""
    c = Canvas(101)
    stage = box(14, 18, 114, 110, 10)
    c.paint(stage, sampled(painting("dusk", (900, 600, 2100, 1500)), (14, 18, 114, 110)), 5.0, flat(0), wander=0.1)
    velvet = lit("#C43A30", "#5E1428", y0=18, y1=110, light=0.24, shade=0.3, cool="#3A1A4A")
    c.paint(poly([(14, 18), (44, 18), (36, 64), (30, 110), (14, 110)]) * stage, velvet, 3.4, flat(95), wander=0.08,
            accents=["#E8604A", "#7A1A2A"], accent_rate=0.2, thick=1.3)
    c.paint(poly([(84, 18), (114, 18), (114, 110), (98, 110), (92, 64)]) * stage, velvet, 3.4, flat(85), wander=0.08,
            accents=["#E8604A", "#7A1A2A"], accent_rate=0.2, thick=1.3)
    c.paint(box(14, 18, 114, 30, 6) * stage, lit("#E8C068", "#9A6A24"), 2.6, flat(0), layers=2, wander=0.05, thick=1.4)
    c.paint(poly([(56, 52), (56, 84), (82, 68)]), one("#FBF6EA"), 2.6, flat(0), layers=2, wander=0.3, thick=2.0)
    return c.finish()


def sunflower_icon():
    """Filelight: a sunflower, its petals and seeds rings around the middle."""
    c = Canvas(111)
    for a, b in (((64, 92), (64, 122)), ((64, 108), (88, 98))):
        c.paint(band((a, b), 6), lit("#5E9A5A", "#2F5E3E"), 2.2, flat(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))),
                layers=2, wander=0.1)
    petals = poly(ellipse(64, 56, 46, 44, 0, 24))
    c.paint(cut(petals, circle(64, 56, 16)), lit("#FFD15A", "#E08A1E", y0=12, y1=100, light=0.3, shade=0.25, cool="#C0602A"),
            4.2, outward(64, 56), wander=0.25, accents=["#FFE89A", "#F2B84B", "#D9731A"], accent_rate=0.25, thick=1.6)
    c.paint(circle(64, 56, 18), lit("#7A4A24", "#3A2214", y0=38, y1=74, light=0.25, shade=0.2), 2.2, around(64, 56),
            wander=0.6, accents=["#A86A34", "#2A1A10", "#C49A5A"], accent_rate=0.3, thick=2.0)
    return c.finish()


def letter_icon():
    """Kate: a letter in ink, a feather quill across it."""
    c = Canvas(121)
    sheet = poly([(26, 18), (98, 12), (104, 108), (32, 114)])
    c.paint(sheet, lit("#FBF5E6", "#DCCFB4", y0=12, y1=114, cool="#9A8CB8"), 5.0, flat(-4), layers=2, wander=0.08)
    for i in range(6):
        y = 34 + i * 12
        c.mark([(36, y + 1), (88 - (18 if i == 5 else 0), y - 3)], 2.6, "#3E4A86", sheet, thick=0.7)
    quill = poly([(108, 14), (114, 22), (60, 92), (56, 90)])
    c.paint(quill, lit("#9FD3C4", "#3F9A89"), 2.4, flat(126), layers=2, wander=0.15, accents=["#E6F4EE"], accent_rate=0.3)
    c.mark([(58, 90), (50, 102)], 2.6, "#2A2338", None)
    return c.finish()


def chest_icon():
    """Ark: a wooden chest with iron bands, to keep things in."""
    c = Canvas(131)
    c.paint(box(18, 50, 110, 106, 6), wood(top="#B8824E", bottom="#6A4226"), 4.4, flat(0), wander=0.06)
    c.paint(box(18, 30, 110, 54, 10), wood(top="#C8925C", bottom="#8A5A34"), 4.0, flat(0), wander=0.06)
    for x in (34, 94):
        c.mark([(x, 30), (x, 106)], 5.0, "#4A4250", None, thick=1.2)
    c.paint(box(56, 46, 72, 64, 3), lit("#F0C870", "#A6742A"), 2.0, around(64, 55), layers=2, thick=1.6)
    return c.finish()


def camera_icon():
    """Spectacle: an old box camera."""
    c = Canvas(141)
    c.paint(box(48, 28, 80, 42, 4), lit("#4A4258", "#2A2436"), 2.6, flat(0), layers=2)
    c.paint(box(16, 38, 112, 102, 12), lit("#5A5068", "#2A2436", y0=38, y1=102, light=0.2, shade=0.2, cool="#1A1A3A"), 5.0,
            flat(0), wander=0.08, accents=["#6A6080", "#3A3448"], accent_rate=0.2)
    c.paint(box(16, 52, 112, 60), lit("#C49A5A", "#8A6430"), 2.2, flat(0), layers=1, opacity=0.8, ground=False)
    c.paint(circle(64, 72, 22), lit("#E8C068", "#9A6A24"), 2.4, around(64, 72), layers=2, thick=1.5)
    c.paint(circle(64, 72, 16), lit("#5A7AC0", "#1A2450", y0=56, y1=88, light=0.3, shade=0.2), 2.6, around(64, 72),
            wander=0.3, accents=["#9FB4E8", "#C49ACB"], accent_rate=0.25, thick=1.4)
    c.dab(58 * S, 66 * S, 7 * S, 4 * S, -0.6, hexrgb("#F3ECD8"), np.ones((N, N), np.float32), opacity=0.85, thick=1.8)
    return c.finish()


def sailboat_icon():
    """Internet: a sailboat setting out over the water."""
    c = Canvas(151)
    c.paint(poly(ellipse(64, 100, 52, 13, 0, 60)), lit("#6A86C6", "#2C3C78", y0=86, y1=114), 4.0, flat(0), layers=2,
            wander=0.06, accents=["#9FB4E8", "#F2B84B"], accent_rate=0.12)
    c.paint(poly([(30, 86), (98, 86), (88, 98), (40, 98)]), wood(), 3.0, flat(0), layers=2, wander=0.05, thick=1.3)
    c.mark([(64, 86), (64, 14)], 3.0, "#4A3A2A", None, thick=1.2)
    c.paint(poly([(68, 18), (100, 80), (68, 80)]), lit("#FBF5E6", "#D6C8B0", y0=18, y1=80, cool="#9A8CB8"), 4.2, flat(70),
            wander=0.12, thick=1.2)
    c.paint(poly([(60, 28), (60, 80), (30, 80)]), lit("#F6B590", "#E2603A", y0=28, y1=80), 3.8, flat(110), wander=0.12, thick=1.2)
    return c.finish()


def brushes_icon():
    """Utilities: brushes standing in a glass jar."""
    c = Canvas(161)
    for (a, b), tip in ((((50, 70), (34, 16)), "#F2552C"), (((64, 70), (66, 10)), "#5C88D0"), (((78, 70), (96, 18)), "#3F9A89")):
        c.mark([a, b], 4.4, "#B07A4C", None, thick=1.2)
        c.paint(poly(ellipse(b[0], b[1], 5.2, 8.5, math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) + 90, 30)),
                one(tip), 2.0, flat(90), layers=2, wander=0.2, thick=2.0)
    jar = box(32, 58, 96, 114, 12)
    c.paint(jar, lit("#BFD6E8", "#6A8AB0", y0=58, y1=114, light=0.3, shade=0.25), 4.0, flat(90), wander=0.1,
            accents=["#FFFFFF", "#9FB4E8"], accent_rate=0.2, opacity=0.82)
    c.mark([(42, 66), (42, 100)], 3.0, "#FFFFFF", jar, thick=1.0)  # light on the glass
    return c.finish()


# Files and drives -------------------------------------------------------------
# Every kind of file is a sheet of paper with something painted on it; drives
# are what a painter carries colors in.

INKS = ["#3E4A86", "#2A2338"]
PAPER = dict(top="#FBF5E6", bottom="#DCCFB4", cool="#9A8CB8")


def paper(seed):
    """A sheet with its corner folded over."""
    c = Canvas(seed)
    page = poly([(26, 10), (82, 10), (102, 30), (102, 118), (26, 118)])
    c.paint(page, lit(y0=10, y1=118, **PAPER), 5.0, flat(-3), layers=2, wander=0.08, accents=["#FFFFFF", "#E8DCC4"],
            accent_rate=0.15)
    c.paint(poly([(82, 10), (82, 30), (102, 30)]), lit("#E6DAC2", "#B8A8B4", y0=10, y1=30, cool="#7A6A9A"), 2.4, flat(45),
            layers=2, wander=0.1, thick=1.5)
    return c, page


def lines(c, page, rows, x0=38, x1=90, y0=46, gap=11, color=INKS[0]):
    for i in range(rows):
        end = x1 - (16 if i == rows - 1 else (6 if i % 3 == 1 else 0))
        c.mark([(x0, y0 + i * gap + 0.6), (end, y0 + i * gap - 0.6)], 2.6, color, page, thick=0.7)


def text_icon():
    """Text: a sheet written in ink."""
    c, page = paper(201)
    lines(c, page, 7, y0=36)
    return c.finish()


def code_icon():
    """Code and scripts: lines in three inks, indented."""
    c, page = paper(202)
    for i, (indent, length, color) in enumerate(((0, 22, "#C0583A"), (8, 34, "#3F9A89"), (16, 26, "#3E4A86"),
                                                  (16, 30, "#3E4A86"), (8, 14, "#3F9A89"), (0, 10, "#C0583A"),
                                                  (0, 28, "#3E4A86"))):
        y = 36 + i * 11
        c.mark([(38 + indent, y), (38 + indent + length, y)], 2.8, color, page, thick=0.8)
    return c.finish()


def image_icon():
    """Pictures: a small painting on the sheet."""
    c, page = paper(203)
    inner = box(34, 40, 94, 96, 2)
    c.paint(inner, sampled(painting("dawn", (1700, 650, 2900, 1550)), (34, 40, 94, 96)), 3.6, flat(0), wander=0.12,
            jitter=0.04)
    return c.finish()


def audio_icon():
    """Music: a note on the sheet."""
    c, page = paper(204)
    c.mark([(56, 90), (56, 46), (84, 40), (84, 82)], 5.2, INKS[1], page, thick=2.0)
    for x, y in ((50, 92), (78, 84)):
        c.paint(poly(ellipse(x, y, 8, 6.4, -20, 30)), one("#C0583A"), 2.4, around(x, y), layers=2, wander=0.4,
                jitter=0.03, thick=2.2)
    return c.finish()


def video_icon():
    """Films: an evening scene with the play sign over it."""
    c, page = paper(205)
    inner = box(34, 40, 94, 96, 2)
    c.paint(inner, sampled(painting("dusk", (900, 600, 2100, 1500)), (34, 40, 94, 96)), 3.6, flat(0), wander=0.12)
    c.paint(poly([(56, 56), (56, 82), (78, 69)]), one("#FBF6EA"), 2.4, flat(0), layers=2, wander=0.3, thick=2.0)
    return c.finish()


def pdf_icon():
    """PDF and books: a written page sealed in vermilion wax."""
    c, page = paper(206)
    lines(c, page, 5, y0=36, x1=88)
    seal = poly(ellipse(78, 96, 13, 12.4, 10, 36))
    c.paint(seal, lit("#E8603A", "#A82A1A", y0=84, y1=108, light=0.3, shade=0.25, cool="#6A1A3A"), 2.6, around(78, 96),
            wander=0.4, accents=FIRE, accent_rate=0.2, thick=2.4)
    c.paint(circle(78, 96, 6), lit("#B83A22", "#8A2214"), 1.8, around(78, 96), layers=1, wander=0.5, thick=0.6, ground=False)
    return c.finish()


def sheet_icon():
    """Spreadsheets: a grid ruled in lily."""
    c, page = paper(207)
    for y in (40, 54, 68, 82, 96):
        c.mark([(36, y), (92, y)], 2.2, "#3F9A89", page, thick=0.7)
    for x in (36, 56, 74, 92):
        c.mark([(x, 40), (x, 96)], 2.2, "#3F9A89", page, thick=0.7)
    c.paint(box(38, 42, 54, 52), one("#9FD3C4"), 2.0, flat(0), layers=1, opacity=0.8, ground=False)
    return c.finish()


def slides_icon():
    """Presentations: three dabs standing like bars on a line."""
    c, page = paper(208)
    c.mark([(36, 98), (92, 98)], 2.6, INKS[0], page, thick=0.8)
    for x, top, color in ((44, 70, "#5C88D0"), (62, 52, "#F2B84B"), (80, 40, "#F2552C")):
        c.paint(box(x - 6, top, x + 6, 94, 3), lit(color, color, light=0.3, shade=0.22), 2.6, flat(90), layers=2,
                wander=0.15, thick=1.8)
    return c.finish()


def program_icon():
    """Programs (Windows games too): the sheet with Monet's play sign."""
    c, page = paper(209)
    c.paint(poly([(46, 44), (46, 96), (90, 70)]), lit("#FF9A5E", "#E5401C", y0=44, y1=96, light=0.3, shade=0.12,
                                                      cool="#B8305A"),
            3.4, flat(-30), layers=2, wander=0.2, accents=FIRE, accent_rate=0.16, thick=1.6)
    return c.finish()


def paintbox_icon():
    """Drives: a painter's box, its colors in a row."""
    c = Canvas(211)
    c.paint(box(10, 30, 118, 104, 9), wood(top="#B8824E", bottom="#6A4226"), 4.6, flat(0), wander=0.06)
    tray = box(18, 38, 110, 88, 5)
    c.paint(tray, lit("#5A3E2E", "#3A2620", y0=38, y1=88, light=0.1, shade=0.15), 3.6, flat(0), layers=2, wander=0.06,
            thick=0.7)
    for x, col, acc in ((32, "#F2552C", FIRE), (51, "#F2B84B", ["#FFE08A"]), (70, "#3F9A89", ["#7CD3C0"]),
                        (89, "#5C88D0", ["#93C6EA"])):
        blob = poly(ellipse(x + 3, 62, 8.5, 13, c.rng.uniform(-10, 10), 36))
        c.paint(blob, lit(col, col, light=0.3, shade=0.2), 3.0, around(x + 3, 62), wander=0.5, accents=acc, accent_rate=0.25,
                thick=2.4)
    c.paint(circle(98, 96, 4), lit("#F0C870", "#A6742A"), 1.8, around(98, 96), layers=1, thick=1.4)  # the clasp
    return c.finish()


def tube_icon():
    """USB sticks and memory cards: a tube of paint to carry along."""
    c = Canvas(212)
    a, b = (36, 92), (80, 48)
    body = band((a, b), 30)
    c.paint(body, lit("#E4E0EC", "#8E88A8", y0=30, y1=110, light=0.34, shade=0.3, cool="#5A5288"), 4.0, flat(-45),
            wander=0.08, accents=["#FFFFFF", "#B8B0D0"], accent_rate=0.2, thick=1.2)
    c.paint(band(((54, 74), (64, 64)), 31) * body, lit("#F2552C", "#C0381E", light=0.25, shade=0.2), 3.0, flat(-45),
            layers=2, wander=0.12, accents=FIRE, accent_rate=0.15, thick=1.3)  # the label
    c.paint(band(((18, 98), (30, 110)), 9), lit("#C8C2D8", "#7A7298"), 2.0, flat(45), layers=2, thick=1.0)  # crimped end
    c.paint(band(((84, 44), (98, 30)), 18), lit("#3A3448", "#1A1626"), 2.4, flat(-45), layers=2, thick=1.4)  # the cap
    return c.finish()


def disc_icon():
    """Discs and disc images: the light of the Hours in rings."""
    c = Canvas(213)
    disc = cut(circle(64, 64, 52), circle(64, 64, 9))
    c.paint(disc, sampled(painting("dusk", (1100, 300, 2300, 1500)), (12, 12, 116, 116), light=0.25), 4.4, around(64, 64),
            wander=0.12, accents=["#FFE2B0", "#C9B5EE", "#93C6EA"], accent_rate=0.2, thick=1.1)
    c.paint(cut(circle(64, 64, 18), circle(64, 64, 9)), lit("#E8E4F0", "#A8A0C0", y0=46, y1=82), 2.0, around(64, 64),
            layers=2, wander=0.2, thick=1.0)
    return c.finish()


# The apps on the dock and in the menu that Bazzite brings ------------------------

def window_icon():
    """Browser: a window thrown open onto the harbor."""
    c = Canvas(171)
    view = box(30, 20, 98, 108, 3)
    c.paint(view, sampled(painting("day", (1500, 250, 2700, 1450)), (30, 20, 98, 108)), 4.4, flat(0), wander=0.12, jitter=0.04)
    frame = cut(box(24, 14, 104, 114, 5), view)
    c.paint(frame, lit("#F6EEE0", "#C9B8A0", y0=14, y1=114, cool="#8A7AA0"), 3.0,
            lambda x, y: 0 if min(y - 14, 114 - y) < min(x - 24, 104 - x) else math.pi / 2, wander=0.06, thick=1.4)
    c.mark([(64, 20), (64, 108)], 3.0, "#EFE6D6", None, thick=1.2)
    c.mark([(30, 64), (98, 64)], 3.0, "#EFE6D6", None, thick=1.2)
    shutter = lit("#4E9A7A", "#2A5A48", y0=14, y1=114, light=0.22, shade=0.25)
    for side in (poly([(6, 20), (24, 14), (24, 114), (6, 108)]), poly([(104, 14), (122, 20), (122, 108), (104, 114)])):
        c.paint(side, shutter, 3.0, flat(90), layers=2, wander=0.08, thick=1.3)
    for y in range(28, 104, 12):  # the shutters' slats
        c.mark([(9, y + 1), (21, y - 2)], 1.6, "#2A5A48", None, thick=0.6)
        c.mark([(107, y - 2), (119, y + 1)], 1.6, "#2A5A48", None, thick=0.6)
    return c.finish()


def locomotive_icon():
    """Steam: an engine coming into Saint-Lazare in a cloud of steam."""
    c = Canvas(181)
    for x, y, r in ((44, 34, 20), (70, 24, 19), (94, 38, 16), (28, 52, 13), (62, 46, 15)):
        c.paint(poly(ellipse(x, y, r, r * 0.82, c.rng.uniform(0, 180), 30)),
                lit("#EEF0F6", "#9AA4C8", y0=y - r, y1=y + r, cool="#7A7AB0", light=0.3), 4.0, around(x, y), wander=0.5,
                accents=["#FFFFFF", "#C9B5EE", "#F6E0C0"], accent_rate=0.3, thick=1.2)
    c.paint(box(56, 44, 72, 62, 2), lit("#3A3448", "#1A1626"), 2.4, flat(90), layers=2, thick=1.2)  # the chimney
    engine = lit("#4A4258", "#1A1626", y0=56, y1=110, light=0.18, shade=0.2, cool="#101030")
    c.paint(box(24, 62, 104, 106, 8), engine, 4.0, flat(0), wander=0.08)
    c.paint(circle(64, 80, 22), lit("#5A5068", "#2A2436", y0=58, y1=102, light=0.25), 3.0, around(64, 80), wander=0.2,
            thick=1.4)
    c.paint(circle(64, 80, 8), lit("#FFE08A", "#F2A040", y0=72, y1=88, light=0.3), 2.0, around(64, 80), layers=2,
            accents=["#FFF4C8"], accent_rate=0.3, thick=1.8)  # the lamp
    c.paint(box(20, 100, 108, 108, 2), lit("#D0603A", "#8A2A1A"), 2.2, flat(0), layers=2, thick=1.2)  # buffer beam
    c.mark([(16, 116), (112, 116)], 2.4, "#6A6080", None, thick=0.8)
    return c.finish()


def rowboat_icon():
    """Lutris: a rowing boat on the Seine, for games from everywhere else."""
    c = Canvas(191)
    c.paint(poly(ellipse(64, 94, 58, 22, 0, 60)), lit("#6A9AC6", "#2C4C78", y0=72, y1=116), 4.4, flat(0), layers=2,
            wander=0.06, accents=["#9FC4E8", "#F6E7C8", "#3F9A89"], accent_rate=0.18)
    for y, length in ((96, 56), (103, 40), (109, 24)):  # its reflection
        c.dab(64 * S, y * S, length * S, 3.2 * S, 0, hexrgb("#5A3A28"), np.ones((N, N), np.float32), opacity=0.45, thick=0.8)
    c.paint(poly([(14, 66), (114, 66), (100, 88), (28, 88)]), wood(top="#C8925C", bottom="#6A4226"), 3.2, flat(0), layers=2,
            thick=1.3)
    c.mark([(16, 66), (112, 66)], 3.2, "#F0D2A0", None, thick=1.2)
    for a, b in (((26, 40), (84, 100)), ((102, 40), (44, 100))):  # the oars
        c.mark([a, b], 3.0, "#C89A5A", None, thick=1.2)
        c.paint(poly(ellipse(b[0], b[1], 6, 3.2, math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])), 24)), one("#B07A4C"),
                1.6, flat(0), layers=1, thick=1.4)
    return c.finish()


def bridge_icon():
    """Bazzite Portal: the Japanese footbridge over the lily pond at Giverny."""
    c = Canvas(201)
    garden = box(8, 10, 120, 72, 14)
    c.paint(garden, lit("#3E6A5A", "#1E3A34", y0=10, y1=72, light=0.2, shade=0.25, cool="#2A2A5A"), 5.0, flat(100),
            wander=0.4, accents=["#5E8A6A", "#2A4A44", "#9A88C0", "#C8A85A"], accent_rate=0.25)  # willows, in shade
    pond = box(8, 62, 120, 118, 14)
    c.paint(pond, lit("#4A7A9A", "#1E3E52", y0=62, y1=118, light=0.15, shade=0.2), 4.4, flat(0), wander=0.1,
            accents=["#5C88D0", "#7CD3C0", "#2A5A48"], accent_rate=0.2)
    for x, y, r in ((26, 94, 8), (52, 106, 7), (86, 98, 9), (106, 110, 6), (70, 86, 5)):  # lily pads
        c.paint(poly(ellipse(x, y, r, r * 0.55, 0, 24)), lit("#6AAE6A", "#2E6A44"), 2.0, around(x, y), layers=2, thick=1.4)
    for x, y in ((28, 92), (88, 96)):
        c.dab(x * S, y * S, 5 * S, 3.4 * S, 0.3, hexrgb("#F2A0C0"), np.ones((N, N), np.float32), thick=2.0)
    span = [(10 + 108 * t / 20, 72 - 30 * math.sin(math.pi * t / 20)) for t in range(21)]
    c.paint(band(span, 8), lit("#B8E08A", "#5EA060", y0=40, y1=76, light=0.32), 2.4, flat(0), layers=2, thick=1.6)
    rail = [(x, y - 15) for x, y in span[2:-2]]
    c.mark(rail, 3.2, "#A8D880", None, thick=1.3)
    for i in range(3, 19, 3):
        c.mark([span[i], (span[i][0], span[i][1] - 15)], 2.4, "#A8D880", None, thick=1.0)
    return c.finish()


def seal_icon():
    """Flatseal: a letter closed with a vermilion seal: what each app may open."""
    c = Canvas(211)
    letter = box(12, 28, 116, 100, 6)
    c.paint(letter, lit(y0=28, y1=100, **PAPER), 5.0, flat(0), layers=2, wander=0.08, accents=["#FFFFFF", "#E8DCC4"],
            accent_rate=0.15)
    for a in ((14, 30), (114, 30)):
        c.mark([a, (64, 70)], 2.0, "#B8A88C", letter, thick=0.7)
    c.paint(poly(ellipse(64, 70, 19, 18, 10, 36)), lit("#E8603A", "#A82A1A", y0=52, y1=88, light=0.3, shade=0.25,
                                                       cool="#6A1A3A"),
            2.6, around(64, 70), wander=0.4, accents=FIRE, accent_rate=0.2, thick=2.4)
    c.paint(cut(circle(64, 70, 10), circle(64, 70, 7.5)), lit("#B83A22", "#8A2214"), 1.6, around(64, 70), layers=1,
            thick=0.6, ground=False)
    return c.finish()


def crates_icon():
    """Warehouse: crates stacked at the market, apps kept in them."""
    c = Canvas(221)
    for x0, y0, x1, y1, top in ((10, 70, 62, 114, "#C8925C"), (66, 70, 118, 114, "#B8824E"), (36, 26, 92, 70, "#D09A62")):
        c.paint(box(x0, y0, x1, y1, 3), wood(top=top, bottom="#6A4226", y0=y0, y1=y1), 3.6, flat(0), wander=0.05)
        for y in (y0 + (y1 - y0) / 3, y0 + 2 * (y1 - y0) / 3):  # the gaps between slats
            c.mark([(x0 + 2, y), (x1 - 2, y)], 1.8, "#4A2E1C", None, thick=0.6)
    for x, y, col in ((48, 24, "#F2552C"), (62, 21, "#F2B84B"), (78, 24, "#E8603A")):  # oranges on top
        c.paint(circle(x, y, 7), lit(col, col, light=0.3, shade=0.22), 1.8, around(x, y), layers=2, thick=1.8)
    return c.finish()


def gear_icon():
    """Gear Lever: a brass gear, for programs that come in one piece."""
    c = Canvas(231)
    teeth = [(64 + (46 if (k // 3) % 2 == 0 else 37) * math.cos(2 * math.pi * k / 60),
              64 + (46 if (k // 3) % 2 == 0 else 37) * math.sin(2 * math.pi * k / 60)) for k in range(60)]
    gear = cut(poly(teeth), circle(64, 64, 14))
    c.paint(gear, lit("#E8C068", "#8A5A24", light=0.3, shade=0.3, cool="#5A3A4A"), 3.6, around(64, 64), wander=0.15,
            accents=["#FFE7A0", "#B88A3A", "#C9708E"], accent_rate=0.2, thick=1.6)
    c.paint(cut(circle(64, 64, 24), circle(64, 64, 14)), lit("#C89A48", "#7A4E1E"), 2.2, around(64, 64), layers=2,
            thick=1.2, ground=False, opacity=0.8)
    return c.finish()


def jars_icon():
    """DistroShelf: jars of pigment on a shelf, each a little world of its own."""
    c = Canvas(241)
    c.paint(box(8, 98, 120, 108, 2), wood(), 2.6, flat(0), layers=2, thick=1.2)
    for x, col, acc in ((30, "#3F9A89", ["#7CD3C0"]), (64, "#5C88D0", ["#93C6EA"]), (98, "#F2552C", FIRE)):
        jar = box(x - 15, 46, x + 15, 98, 7)
        c.paint(box(x - 13, 58, x + 13, 96, 5), lit(col, col, light=0.3, shade=0.25), 3.0, flat(90), layers=2,
                accents=acc, accent_rate=0.2, thick=1.6)
        c.paint(jar, lit("#DCE8F2", "#8AA0C0", y0=46, y1=98, light=0.3), 3.0, flat(90), layers=1, opacity=0.35,
                ground=False, thick=0.6)
        c.paint(box(x - 13, 38, x + 13, 48, 3), lit("#6A5A48", "#3A2A20"), 2.0, flat(0), layers=2, thick=1.2)  # the lid
        c.mark([(x - 9, 60), (x - 9, 90)], 2.4, "#FFFFFF", jar, thick=0.6)  # light on the glass
    return c.finish()


def balloon_icon():
    """ProtonUp: a balloon going up, carrying what Windows games need."""
    c = Canvas(251)
    envelope = poly([(64 + 36 * math.sin(t) * (1 - 0.45 * max(0, -math.cos(t))), 46 - 40 * math.cos(t))
                     for t in (math.pi * k / 40 for k in range(-40, 41))])
    stripes = [("#F2552C", FIRE), ("#F2B84B", ["#FFE08A"]), ("#3F9A89", ["#7CD3C0"]), ("#F6EEE0", ["#FFFFFF"])]
    for i in range(8):
        x0 = 28 + i * 9
        part = np.clip(envelope * box(x0, 0, x0 + 9, 128), 0, 1)
        col, acc = stripes[i % 4]
        c.paint(part, lit(col, col, light=0.32, shade=0.25), 2.6, flat(90), layers=2, accents=acc, accent_rate=0.15,
                thick=1.3)
    for a, b in (((46, 82), (58, 100)), ((82, 82), (70, 100))):
        c.mark([a, b], 1.6, "#4A3A2A", None, thick=0.6)
    c.paint(box(54, 100, 74, 114, 3), wood(), 2.2, flat(0), layers=2, thick=1.3)
    return c.finish()


def watering_can_icon():
    """Waydroid: the garden's green watering can, for Android's apps."""
    c = Canvas(261)
    green = lit("#6AB07A", "#2E6A44", y0=40, y1=108, light=0.3, shade=0.25, cool="#2A3A5A")
    c.paint(box(24, 52, 90, 108, 14), green, 4.0, around(57, 80), wander=0.2,
            accents=["#A8D08A", "#3F7A5A"], accent_rate=0.2, thick=1.3)
    c.paint(poly(ellipse(57, 54, 28, 6, 0, 30)), lit("#4E9A6A", "#2E6A44"), 1.8, flat(0), layers=1, thick=1.3)  # its mouth
    c.paint(band([(84, 92), (116, 46)], 7), green, 2.4, flat(-55), layers=2, thick=1.3)  # the spout
    c.paint(poly(ellipse(116, 44, 7, 4.5, -55, 24)), lit("#4E9A6A", "#2E6A44"), 1.8, flat(0), layers=1, thick=1.4)
    c.mark([(32, 50), (44, 26), (72, 26), (84, 50)], 4.4, "#4E9A6A", None, thick=1.4)  # the handle
    for x, y in ((112, 58), (106, 66), (118, 64)):  # a few drops
        c.dab(x * S, y * S, 4 * S, 2.4 * S, 1.2, hexrgb("#9FC4E8"), np.ones((N, N), np.float32), thick=1.4)
    return c.finish()


def piano_icon():
    """Input Remapper: piano keys, for keys that play another note."""
    c = Canvas(271)
    keys = box(12, 30, 116, 102, 6)
    c.paint(keys, lit("#FBF5E6", "#D9CCB2", y0=30, y1=102, cool="#9A8CB8"), 4.4, flat(90), layers=2, wander=0.06,
            accents=["#FFFFFF"], accent_rate=0.12)
    for x in range(27, 116, 15):
        c.mark([(x, 32), (x, 100)], 1.6, "#9A8C78", keys, thick=0.5)
    for x in (27, 42, 72, 87, 102):
        c.paint(box(x - 5, 30, x + 5, 74, 2), lit("#3A3448", "#1A1626"), 2.0, flat(90), layers=2, thick=1.4)
    c.paint(box(12, 26, 116, 34, 3), lit("#C43A30", "#7A1A2A"), 2.0, flat(0), layers=2, thick=1.2)  # the felt
    return c.finish()


def cafe_icon():
    """Discourse: two cups on a café table, for talking it over."""
    c = Canvas(281)
    c.paint(poly(ellipse(64, 84, 54, 26, 0, 60)), lit("#F6EEE0", "#C9B8A0", y0=58, y1=110, cool="#8A7AA0"), 4.4, flat(0),
            layers=2, wander=0.08)
    for x, col in ((44, "#5C88D0"), (82, "#F2552C")):
        c.paint(box(x - 12, 54, x + 12, 80, 8), lit(col, col, light=0.3, shade=0.22), 2.4, flat(90), layers=2, thick=1.6)
        c.paint(poly(ellipse(x, 55, 12, 4, 0, 24)), lit("#7A4A24", "#3A2214"), 1.6, flat(0), layers=1, thick=1.4)
        c.mark([(x + 12, 60), (x + 18, 64), (x + 12, 72)], 2.4, col, None, thick=1.2)
    for x in (40, 46, 80, 86):  # warmth rising
        c.mark([(x, 48), (x + 3, 40), (x, 32)], 1.6, "#D0D4E4", None, thick=0.5)
    return c.finish()


def calendar_icon():
    """Calendar: a page of the month, today in the sun."""
    c = Canvas(301)
    page = box(16, 22, 112, 112, 10)
    c.paint(page, lit(y0=22, y1=112, **PAPER), 5.0, flat(0), layers=2, wander=0.08, accents=["#FFFFFF", "#E8DCC4"],
            accent_rate=0.15)
    c.paint(box(16, 22, 112, 44, 10) * page, lit("#4E9A8A", "#245A50", y0=22, y1=44, light=0.25), 3.0, flat(0),
            layers=2, wander=0.08, thick=1.3)
    for x in (40, 88):  # the rings
        c.mark([(x, 14), (x, 30)], 4.2, "#6A6080", None, thick=1.4)
    for row in range(4):
        for col in range(5):
            x, y = 30 + col * 17, 56 + row * 14
            today = (row, col) == (2, 3)
            c.dab(x * S, y * S, (8 if today else 5.5) * S, (8 if today else 4.2) * S, 0,
                  hexrgb("#F2552C" if today else "#3E4A86"), page, opacity=1 if today else 0.75, thick=2.0 if today else 0.9)
    return c.finish()


def teapot_icon():
    """Bold Brew: a teapot from Giverny's blue kitchen."""
    c = Canvas(291)
    blue = lit("#5C88D0", "#2C3C78", y0=36, y1=104, light=0.3, shade=0.25)
    c.paint(poly(ellipse(60, 74, 32, 28, 0, 60)), blue, 3.6, around(60, 74), wander=0.2, accents=["#93C6EA", "#F6EEE0"],
            accent_rate=0.2, thick=1.5)
    c.paint(band([(88, 78), (112, 52)], 7), blue, 2.2, flat(-45), layers=2, thick=1.3)
    c.mark([(30, 60), (18, 70), (30, 88)], 4.4, "#3A5A9A", None, thick=1.3)  # handle
    c.paint(box(46, 40, 74, 50, 4), lit("#4A6AB0", "#2C3C78"), 2.0, flat(0), layers=2, thick=1.3)  # the lid
    c.paint(circle(60, 36, 4.5), one("#F2B84B"), 1.6, around(60, 36), layers=1, thick=1.6)
    c.mark([(42, 74), (78, 74)], 2.6, "#F6EEE0", None, thick=0.8)  # a painted band of white
    return c.finish()


# Folders: which painting each one's front is cut from (painting, crop box in
# the 3840 x 2160 original), the color of its back, and its mark: lines the
# brush follows, "dot:x,y" for a round dab, or "fill:" for a shape painted solid.
FOLDERS = {
    "folder": ("dawn", (2080, 1260, 2980, 1843), "#2E4A63", []),
    "user-home": ("dawn", (2183, 538, 3083, 1121), "#6E5878", [[(46, 78), (64, 62), (82, 78)], [(52, 73), (52, 92), (76, 92), (76, 73)]]),
    "user-desktop": ("day", (300, 90, 1200, 673), "#3E6680", [[(44, 64), (84, 64), (84, 86), (44, 86), (44, 64)], [(58, 96), (70, 96)]]),
    "folder-documents": (None, None, "#A3947A", [[(48, 64), (80, 64)], [(48, 75), (80, 75)], [(48, 86), (68, 86)]]),
    "folder-download": ("night", (560, 230, 1460, 813), "#141C38", [[(64, 58), (64, 88)], [(52, 77), (64, 89), (76, 77)]]),
    "folder-pictures": ("dusk", (870, 700, 1770, 1283), "#5B3F6E",
                        [[(45, 62), (83, 62), (83, 92), (45, 92), (45, 62)], [(49, 88), (58, 78), (66, 86), (72, 80), (79, 88)]]),
    "folder-music": ("dusk", (2240, 80, 3140, 663), "#3E3470", [[(58, 86), (58, 60), (80, 56), (80, 80)], "dot:54,88", "dot:76,82"]),
    "folder-videos": ("dusk", (880, 1240, 1780, 1823), "#4A2448", ["fill:57,58:57,86:83,72"]),
    "folder-games": ("night", (2700, 980, 3600, 1563), "#0E1430",
                     [[(52, 68), (76, 68), (82, 72), (84, 80), (82, 88), (76, 92), (52, 92), (46, 88), (44, 80), (46, 72), (52, 68)],
                      [(52, 80), (60, 80)], [(56, 76), (56, 84)], "dot:72,78", "dot:77,83"]),
}


def folder_icon(name, source, crop, back, mark):
    """A folder: its back in one color, its front repainted from a piece of the Hours."""
    c = Canvas(sum(map(ord, name)))
    c.paint(join(box(14, 22, 56, 44, 8), box(14, 30, 114, 100, 8)), lit(back, back, light=0.18, shade=0.2), 6.0, flat(0),
            layers=2, wander=0.08, thick=0.8)
    front = box(10, 40, 118, 110, 11)
    if source:
        c.paint(front, sampled(painting(source, crop), (10, 40, 118, 110)), 5.6, flat(0), wander=0.1, jitter=0.035)
        ink = "#FBF7EE"
    else:  # Documents is paper.
        c.paint(front, lit("#FBF4E6", "#D9CCB2", y0=40, y1=110, cool="#9A8CB0"), 5.6, flat(0), wander=0.1,
                accents=["#FFFFFF", "#E8DCC4"], accent_rate=0.15)
        ink = "#4A4540"
    c.mark([(20, 42), (108, 42)], 1.8, "#FFFFFF", front, thick=0.6)
    for part in mark:
        if isinstance(part, str) and part.startswith("dot:"):
            x, y = (float(v) for v in part[4:].split(","))
            c.paint(poly(ellipse(x, y, 6.2, 5.2, -20, 30)), one(ink), 2.4, around(x, y), layers=2, wander=0.4, jitter=0.03,
                    thick=2.2)
        elif isinstance(part, str):
            pts = [tuple(float(v) for v in p.split(",")) for p in part[5:].split(":")]
            c.paint(poly(pts), one(ink), 2.6, flat(0), layers=2, wander=0.3, jitter=0.03, thick=2.2)
        else:
            c.mark(part, 6.4, ink, None, thick=2.2)
    return c.finish()


# Which painting each icon name gets. Several names share one painting.
ICONS = {
    "monet": (sun_icon, ["apps/monet"]),
    "monet-windows": (play_icon, ["apps/monet-windows", "categories/applications-games"]),
    "files": (lambda: folder_icon("folder", *FOLDERS["folder"]), ["apps/system-file-manager", "apps/org.kde.dolphin", "places/folder"]),
    "settings": (palette_icon, ["apps/preferences-system", "apps/systemsettings", "apps/monet-settings",
                                "categories/applications-graphics", "categories/preferences-system"]),
    "terminal": (easel_icon, ["apps/utilities-terminal", "apps/org.kde.konsole", "categories/applications-development"]),
    # Store is Bazaar when Bazzite has it, otherwise Discover: the same bouquet either way.
    "store": (bouquet_icon, ["apps/plasmadiscover", "apps/org.kde.discover", "apps/io.github.kolunmi.Bazaar"]),
    "monitor": (harbor_icon, ["apps/utilities-system-monitor", "apps/org.kde.plasma-systemmonitor", "categories/applications-system"]),
    "trash": (lambda: pot_icon(False), ["places/user-trash"]),
    "trash-full": (lambda: pot_icon(True), ["places/user-trash-full"]),
    # KDE's apps that Bazzite brings (Flatpaks) or might.
    "pictures": (frame_icon, ["apps/org.kde.gwenview", "apps/gwenview"]),
    "documents": (book_icon, ["apps/org.kde.okular", "apps/okular", "categories/applications-office", "categories/applications-education"]),
    "calculator": (abacus_icon, ["apps/org.kde.kcalc", "apps/accessories-calculator"]),
    "player": (curtain_icon, ["apps/org.kde.haruna", "apps/haruna", "categories/applications-multimedia"]),
    "disk": (sunflower_icon, ["apps/org.kde.filelight", "apps/filelight", "categories/applications-science"]),
    "editor": (letter_icon, ["apps/org.kde.kate", "apps/kate", "apps/org.kde.kwrite", "apps/kwrite", "apps/accessories-text-editor"]),
    "archives": (chest_icon, ["apps/org.kde.ark", "apps/ark", "apps/utilities-file-archiver"]),
    "camera": (camera_icon, ["apps/org.kde.spectacle", "apps/spectacle"]),
    "internet": (sailboat_icon, ["categories/applications-internet"]),
    "utilities": (brushes_icon, ["categories/applications-utilities"]),
}
for name, spec in FOLDERS.items():
    if name != "folder":
        ICONS[name] = ((lambda n=name, s=spec: folder_icon(n, *s)), [f"places/{name}"])

# Paintings asked for by many names: one file under a name, the others linked
# by install.sh. Files and drives (Breeze has an icon for nearly every exact
# type, and those come before the generic one), and the apps Bazzite brings.
OFFICE = "application-vnd.openxmlformats-officedocument"
OPEN = "application-vnd.oasis.opendocument"
FILES = {
    "text": (text_icon, "mimetypes/text-x-generic", [
        "text-plain", "text-markdown", "text-x-readme", "text-x-log", "text-rtf", "application-rtf", "x-office-document",
        f"{OPEN}.text", f"{OFFICE}.wordprocessingml.document", "application-msword", "application-x-zerosize", "unknown",
        "application-octet-stream"]),
    "code": (code_icon, "mimetypes/text-x-script", [
        "application-x-shellscript", "text-x-python", "text-x-python3", "application-json", "text-html", "text-css",
        "application-javascript", "text-javascript", "text-x-csrc", "text-x-chdr", "text-x-c++src", "text-x-c++hdr",
        "text-rust", "text-x-rust", "application-xml", "text-xml", "text-x-makefile", "text-x-cmake", "application-x-yaml",
        "application-toml", "application-x-desktop", "text-x-java", "text-x-go", "application-x-php", "text-x-qml"]),
    "image": (image_icon, "mimetypes/image-x-generic", [
        "image-png", "image-jpeg", "image-gif", "image-webp", "image-bmp", "image-tiff", "image-svg+xml", "image-avif",
        "image-heif", "image-jxl", "image-x-xcf", "image-vnd.microsoft.icon", "image-x-icon"]),
    "audio": (audio_icon, "mimetypes/audio-x-generic", [
        "audio-mpeg", "audio-x-wav", "audio-wav", "audio-flac", "audio-x-flac", "audio-ogg", "audio-x-vorbis+ogg",
        "audio-x-opus+ogg", "audio-mp4", "audio-aac", "audio-x-m4a", "audio-x-mpegurl", "audio-x-ms-wma"]),
    "video": (video_icon, "mimetypes/video-x-generic", [
        "video-mp4", "video-x-matroska", "video-webm", "video-quicktime", "video-x-msvideo", "video-mpeg", "video-x-flv",
        "video-ogg", "video-x-ms-wmv"]),
    "pdf": (pdf_icon, "mimetypes/application-pdf", ["application-epub+zip", "application-postscript", "application-x-cbz"]),
    "sheet": (sheet_icon, "mimetypes/x-office-spreadsheet", [
        f"{OPEN}.spreadsheet", f"{OFFICE}.spreadsheetml.sheet", "application-vnd.ms-excel", "text-csv"]),
    "slides": (slides_icon, "mimetypes/x-office-presentation", [
        f"{OPEN}.presentation", f"{OFFICE}.presentationml.presentation", "application-vnd.ms-powerpoint"]),
    "program": (program_icon, "mimetypes/application-x-executable", [
        "application-x-ms-dos-executable", "application-x-msdownload", "application-x-msi", "application-x-ms-shortcut",
        "application-x-sharedlib", "application-x-pie-executable", "application-vnd.appimage", "application-x-appimage"]),
    "package": (chest_icon, "mimetypes/package-x-generic", [
        "application-zip", "application-x-tar", "application-x-compressed-tar", "application-x-bzip-compressed-tar",
        "application-x-xz-compressed-tar", "application-x-zstd-compressed-tar", "application-x-7z-compressed",
        "application-x-rar", "application-vnd.rar", "application-gzip", "application-x-gzip", "application-x-xz",
        "application-zstd", "application-x-rpm", "application-x-deb", "application-vnd.debian.binary-package",
        "application-vnd.flatpak", "application-vnd.flatpak.ref", "application-vnd.flatpak.repo", "application-x-archive"]),
    "drive": (paintbox_icon, "devices/drive-harddisk", [
        "drive-harddisk-solidstate", "drive-harddisk-root", "drive-harddisk-system", "drive-harddisk-windows",
        "drive-harddisk-encrypted", "drive-multidisk", "computer", "computer-laptop"]),
    "stick": (tube_icon, "devices/drive-removable-media-usb", [
        "drive-removable-media", "drive-removable-media-usb-pendrive", "media-removable", "media-flash",
        "media-flash-sd-mmc", "media-flash-memory-stick"]),
    "disc": (disc_icon, "devices/media-optical", [
        "drive-optical", "media-optical-dvd", "media-optical-cd", "media-optical-data", "media-optical-audio",
        "mimetypes/application-x-cd-image", "mimetypes/application-x-iso9660-image"]),
    "browser": (window_icon, "apps/org.mozilla.firefox", ["firefox", "web-browser", "internet-web-browser"]),
    "steam": (locomotive_icon, "apps/steam", ["com.valvesoftware.Steam"]),
    "lutris": (rowboat_icon, "apps/net.lutris.Lutris", ["lutris"]),
    "portal": (bridge_icon, "apps/io.github.ublue_os.yafti_gtk", ["yafti", "bazzite-portal"]),
    "flatseal": (seal_icon, "apps/com.github.tchx84.Flatseal", []),
    "warehouse": (crates_icon, "apps/io.github.flattool.Warehouse", []),
    "gearlever": (gear_icon, "apps/it.mijorus.gearlever", []),
    "distroshelf": (jars_icon, "apps/com.ranfdev.DistroShelf", ["io.github.DenysMb.Kontainer"]),
    "protonup": (balloon_icon, "apps/net.davidotek.pupgui2", ["com.vysp3r.ProtonPlus", "com.github.Matoking.protontricks"]),
    "waydroid": (watering_can_icon, "apps/waydroid", ["id.waydro.waydroid"]),
    "remapper": (piano_icon, "apps/input-remapper", ["input-remapper-gtk", "io.github.sezanzeb.input_remapper"]),
    "discourse": (cafe_icon, "apps/monet-discourse", []),
    "bbrew": (teapot_icon, "apps/monet-bbrew", []),
    "calendar": (calendar_icon, "apps/x-office-calendar", ["office-calendar", "org.kde.merkuro.calendar", "korganizer"]),
}
# Folders asked for by their type, not their place.
# Bazzite's documentation names its picture by path; install.sh points it here.
LINKS = {"mimetypes/inode-directory": "places/folder", "apps/monet-documentation": "apps/org.kde.okular"}


def links():
    """'<link> <target>' lines, the target relative to the link."""
    pairs = dict(LINKS)
    for _, main, names in FILES.values():
        for name in names:
            pairs[name if "/" in name else f"{main.split('/')[0]}/{name}"] = main
    out = []
    for link, target in pairs.items():
        (lc, ln), (tc, tn) = link.split("/"), target.split("/")
        out.append(f"{lc}/scalable/{ln}.svg {tn if lc == tc else f'../../{tc}/scalable/{tn}'}.svg")
    return "".join(line + "\n" for line in out)


def svg(img, comment):
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    data = base64.b64encode(buf.getvalue()).decode()
    return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 128 128">\n'
            f"  <!-- {comment} Painted by tools/make-icons.py. -->\n"
            f'  <image width="128" height="128" xlink:href="data:image/png;base64,{data}"/>\n</svg>\n')


# Textures and Monet Settings' pictures --------------------------------------------

def dab_points(cx, cy, length, width, angle=0.0, bend=0.0, taper=0.16, steps=28):
    """Outline of a brushstroke: rounded ends, heavier where the brush landed."""
    a = math.radians(angle)
    ca, sa = math.cos(a), math.sin(a)
    top, bottom = [], []
    for i in range(steps + 1):
        t = -1 + 2 * i / steps
        half = width / 2 * max(0.0, 1 - abs(t) ** 2.4) ** (1 / 2.4) * (1 - taper * t)
        off = bend * (1 - t * t) * length * 0.1
        for sign, side in ((-1, top), (1, bottom)):
            px, py = t * length / 2, off + sign * half
            side.append((cx + px * ca - py * sa, cy + px * sa + py * ca))
    return top + bottom[::-1]


def brush_texture(path, w=640, h=320, seed=4):
    """White brushstrokes on transparent, laid over flat color to make it look painted."""
    rng = np.random.default_rng(seed)
    big = Image.new("L", (w * 2, h * 2), 0)
    d = ImageDraw.Draw(big)
    y = -20.0
    while y < h * 2 + 20:
        x = rng.uniform(-80, 0)
        while x < w * 2 + 80:
            length = rng.uniform(90, 260)
            width = rng.uniform(16, 40)
            angle = rng.normal(-0.12, 0.08)
            d.polygon(dab_points(x, y, length, width, math.degrees(angle), 0, 0.1), fill=int(rng.uniform(10, 60)))
            x += length * rng.uniform(0.5, 0.9)
        y += rng.uniform(14, 26)
    alpha = big.filter(ImageFilter.GaussianBlur(1.6)).resize((w, h), Image.LANCZOS)
    img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    img.putalpha(alpha)
    img.save(path, optimize=True)


# Monet Settings: a small piece of a painting behind each section's mark.
SETTINGS = ROOT / "linux" / "share" / "monet" / "settings"
SWATCHES = {
    "light": ("dawn", (2160, 360, 2600, 800)),
    "wifi": ("day", (500, 200, 940, 640)),
    "bluetooth": ("night", (800, 260, 1240, 700)),
    "display": ("day", (2900, 120, 3340, 560)),
    "sound": ("dusk", (2600, 300, 3040, 740)),
    "windows": ("night", (2900, 1050, 3340, 1490)),
    "updates": ("dawn", (900, 1500, 1340, 1940)),
    "about": ("dusk", (1090, 800, 1530, 1240)),
}


def rounded_png(img, radius, path):
    w, h = img.size
    mask = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w * 4 - 1, h * 4 - 1], radius=radius * 4, fill=255)
    out = img.convert("RGBA")
    out.putalpha(mask.resize((w, h), Image.LANCZOS))
    out.save(path, optimize=True)


def settings_art():
    from PIL import ImageEnhance
    SETTINGS.mkdir(parents=True, exist_ok=True)
    paint = {n: Image.open(HOURS / f"{n}.jpg").convert("RGB") for n in ("dawn", "day", "dusk", "night")}
    for name, (painting, box) in SWATCHES.items():
        img = paint[painting].crop(box).resize((56, 56), Image.LANCZOS)
        img = ImageEnhance.Color(img).enhance(1.25)
        rounded_png(img, 16, SETTINGS / f"swatch-{name}.png")
    # Previews for Light: the four hours side by side, mist, and smoke.
    w, h = 480, 236
    strip = Image.new("RGB", (w, h))
    for i, (name, cx) in enumerate((("dawn", 0.62), ("day", 0.7), ("dusk", 0.35), ("night", 0.28))):
        src = paint[name]
        cw = src.height * (w / 4) / h
        x0 = int(src.width * cx - cw / 2)
        strip.paste(src.crop((x0, 0, int(x0 + cw), src.height)).resize((w // 4, h), Image.LANCZOS), (i * w // 4, 0))
    rounded_png(strip, 24, SETTINGS / "light-hours.png")
    for name, painting, cx, glass in (("mist", "dawn", 0.62, (255, 255, 255, 140)), ("smoke", "night", 0.28, (30, 30, 40, 115))):
        src = paint[painting]
        # As wide a piece as the painting allows, at the preview's proportions.
        cw = min(src.width, src.height * w / h)
        ch = cw * h / w
        x0 = max(0, min(src.width - cw, src.width * cx - cw / 2))
        y0 = max(0, min(src.height - ch, src.height * 0.32 - ch / 2))
        img = src.crop((int(x0), int(y0), int(x0 + cw), int(y0 + ch))).resize((w, h), Image.LANCZOS).convert("RGBA")
        chip = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ImageDraw.Draw(chip).rounded_rectangle([44, h - 80, w - 44, h - 30], radius=20, fill=glass)
        img.alpha_composite(chip)
        rounded_png(img.convert("RGB"), 24, SETTINGS / f"light-{name}.png")
    banner = paint["dusk"].crop((0, 520, 3840, 1672)).resize((1200, 360), Image.LANCZOS)
    banner.save(SETTINGS / "about.jpg", quality=86, optimize=True, progressive=True)


# More settings (KDE's System Settings): each page's mark the way Monet
# Settings draws its own, a swatch cut from the paintings with a white sign
# (24-grid paths, as in MonetSettings.qml), so both lists look alike. One
# painting per part of the list. Names KDE also uses outside its settings
# (Log Out, Run, spelling, Night Light's tray icon) keep Breeze's.
MARK_GLYPHS = {
    "light": "M5 15a7 7 0 0 1 14 0M3 19h18",
    "wifi": "M4 10a12 12 0 0 1 16 0M7 13.5a7.5 7.5 0 0 1 10 0M10 17a3 3 0 0 1 4 0",
    "bluetooth": "M7 7l10 10-5 5V2l5 5L7 17",
    "display": "M4 5h16v11H4zM10 20h4",
    "sound": "M5 10h3l5-4v12l-5-4H5zM17 9a4.5 4.5 0 0 1 0 6",
    "mouse": "M9 3h6a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3H9a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3zM12 3v5",
    "power": "M12 3v8M7 6.5a7 7 0 1 0 10 0",
    "bell": "M6 16v-5a6 6 0 0 1 12 0v5l2 2H4zM10 20h4",
    "clock": "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 7v5l3 2",
    "person": "M8 8a4 4 0 1 0 8 0a4 4 0 1 0-8 0M4 21a8 8 0 0 1 16 0",
    "apps": "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
    "sliders": "M4 7h9M17 7h3M15 5v4M4 17h3M11 17h9M9 15v4",
    "touchpad": "M5 4h14a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V5a1 1 0 0 1 1-1zM4 15h16M12 15v5",
    "keyboard": "M3 7h18v10H3zM7 10.5h.01M10.5 10.5h.01M14 10.5h.01M17.5 10.5h.01M8 14h8",
    "keys": "M3 4h18v9H3zM7 7.5h.01M12 7.5h.01M17 7.5h.01M8 10.5h8M9 17l3 3 3-3",
    "shortcut": "M9 9h6v6H9zM9 9V7a2 2 0 1 0-2 2h2M15 9V7a2 2 0 1 1 2 2h-2M9 15v2a2 2 0 1 1-2-2h2M15 15v2a2 2 0 1 0 2-2h-2",
    "touch": "M7 3h10v18H7zM10.5 18h3M12 9.5a2.5 2.5 0 1 0 .01 0",
    "swipe": "M4 12h14M14 8l4 4-4 4M4 7v10",
    "edges": "M4 5h16v14H4zM7.5 9v6M16.5 9v6",
    "gamepad": "M7 8h10a4 4 0 0 1 4 4l-.5 3.5a2 2 0 0 1-3.5 1L15.5 15h-7L7 16.5a2 2 0 0 1-3.5-1L3 12a4 4 0 0 1 4-4zM8 10.5v3M6.5 12h3M15.5 11.5h.01M17.5 13h.01",
    "pen": "M4 5h16v14H4zM9 15l5.5-5.5 2 2L11 17H9z",
    "access": "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 7.5h.01M7.5 10.5l4.5 1 4.5-1M12 11.5v3l-2.5 3M12 14.5l2.5 3",
    "disk": "M4 7h16v10H4zM4 13h16M16.5 15h.01",
    "bolt": "M13 3L6 13h5l-1 8 7-10h-5z",
    "printer": "M7 8V4h10v4M7 17H4v-7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v7h-3M7 13h10v7H7z",
    "shield": "M12 3l7 3v5c0 5-3.5 8-7 10-3.5-2-7-5-7-10V6z",
    "shieldcheck": "M12 3l7 3v5c0 5-3.5 8-7 10-3.5-2-7-5-7-10V6zM9 12l2 2 4-4",
    "relay": "M3 12h4M17 12h4M7 8h10v8H7zM12 3v5M12 16v5",
    "cloud": "M7.5 18a4.5 4.5 0 0 1-.5-9 5.5 5.5 0 0 1 10.5 1.5A3.75 3.75 0 0 1 17 18z",
    "picture": "M4 5h16v14H4zM4 15l4.5-4.5 4 4 2.5-2.5 5 5M15.5 9h.01",
    "palette": "M12 3a9 9 0 1 0 0 18c1.2 0 2-.8 2-2 0-1.4-1.3-1.6-1.3-2.7 0-1 .8-1.6 1.8-1.6H17a4 4 0 0 0 4-4C21 6.5 17 3 12 3zM7.5 12h.01M9 7.5h.01M14.5 7.5h.01",
    "pointer": "M6 3l12 9.5-5.5 1L15.5 20l-2.5 1-3-6.3L6 18.5z",
    "type": "M5 7V5h14v2M12 5v14M9 19h6",
    "typeplus": "M4 7V5h11v2M9.5 5v14M7 19h5M18 13v6M15 16h6",
    "motion": "M13 12a4 4 0 1 0 8 0a4 4 0 1 0-8 0M3 8.5h7M4.5 12h6M3 15.5h7",
    "fileopen": "M6 3h8l4 4v14H6zM14 3v4h4M9 14l2 2 4-4",
    "windows": "M3 5h12v9H3zM9 10h12v9H9z",
    "window": "M3 5h18v14H3zM3 9h18M6.5 7h.01M9.5 7h.01",
    "cards": "M5 9h14v11H5zM7 6h10M9 3h6",
    "desks": "M3 5h8v6H3zM13 5h8v6h-8zM3 13h8v6H3zM13 13h8v6h-8z",
    "search": "M4 10.5a6.5 6.5 0 1 0 13 0a6.5 6.5 0 1 0-13 0M15.5 15.5L20 20",
    "lock": "M6 11h12v9H6zM8.5 11V8a3.5 3.5 0 0 1 7 0v3M12 14.5v2",
    "remote": "M3 4h18v12H3zM9 20h6M12 16v4M9 10l3-3 3 3M12 7v6",
    "globe": "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18",
    "door": "M14 4h5v16h-5M3 12h11M10 8l4 4-4 4",
}
# Pieces of the paintings, 440 pixels square (the first eight as in Monet Settings).
SPOTS = {
    "dawn-sun": ("dawn", (2160, 360)), "dawn-water": ("dawn", (900, 1500)), "dawn-sky": ("dawn", (300, 300)),
    "dawn-glow": ("dawn", (1600, 1300)), "dawn-boat": ("dawn", (500, 1350)), "dawn-east": ("dawn", (2700, 1300)),
    "dawn-high": ("dawn", (3200, 300)), "dawn-cloud": ("dawn", (1200, 200)), "dawn-swell": ("dawn", (2400, 1600)),
    "dawn-shore": ("dawn", (150, 1600)), "dawn-mid": ("dawn", (1200, 600)), "dawn-masts": ("dawn", (2600, 900)),
    "day-sky": ("day", (500, 200)), "day-high": ("day", (2900, 120)), "day-masts": ("day", (3300, 700)),
    "day-sparkle": ("day", (2750, 1200)), "day-smoke": ("day", (2850, 600)), "day-water": ("day", (300, 1400)),
    "day-cloud": ("day", (1700, 300)), "day-calm": ("day", (1200, 1500)), "day-deep": ("day", (2200, 1700)),
    "day-west": ("day", (100, 700)),
    "dusk-sky": ("dusk", (2600, 300)), "dusk-sun": ("dusk", (1090, 800)), "dusk-violet": ("dusk", (100, 100)),
    "dusk-glow": ("dusk", (1150, 1350)), "dusk-boat": ("dusk", (500, 1450)), "dusk-high": ("dusk", (3300, 200)),
    "dusk-haze": ("dusk", (2300, 900)), "dusk-rose": ("dusk", (2000, 200)),
    "night-moon": ("night", (800, 260)), "night-lights": ("night", (2900, 1050)), "night-harbor": ("night", (100, 950)),
    "night-sky": ("night", (2800, 200)), "night-water": ("night", (2000, 1500)), "night-east": ("night", (3300, 600)),
    "night-deep": ("night", (1500, 1200)), "night-high": ("night", (2400, 400)), "night-shore": ("night", (100, 1600)),
}
MARKS = {
    # Input & Output: dawn (Display and Sound as in Monet Settings).
    "preferences-desktop-mouse": ("dawn-sky", "mouse"),
    "preferences-desktop-touchpad": ("dawn-glow", "touchpad"),
    "preferences-desktop-keyboard": ("dawn-boat", "keyboard"),
    "input-keyboard-virtual": ("dawn-east", "keys"),
    "preferences-desktop-keyboard-shortcut": ("dawn-high", "shortcut"),
    "preferences-desktop-touchscreen": ("dawn-cloud", "touch"),
    "preferences-desktop-gestures-touch": ("dawn-swell", "swipe"),
    "preferences-desktop-gestures-screenedges": ("dawn-shore", "edges"),
    "preferences-desktop-gaming": ("night-lights", "gamepad"),
    "preferences-desktop-tablet": ("dawn-mid", "pen"),
    "preferences-desktop-sound": ("dusk-sky", "sound"),
    "preferences-desktop-display": ("day-high", "display"),
    "preferences-desktop-display-randr": ("day-high", "display"),
    "preferences-desktop-accessibility": ("day-water", "access"),
    # Connected Devices: night.
    "preferences-system-bluetooth": ("night-moon", "bluetooth"),
    "preferences-system-disks": ("night-harbor", "disk"),
    "preferences-desktop-thunderbolt": ("night-sky", "bolt"),
    "preferences-devices-printer": ("night-water", "printer"),
    # Networking: day.
    "preferences-system-network": ("day-sky", "wifi"),
    "preferences-security-firewall": ("day-masts", "shield"),
    "preferences-system-network-proxy": ("day-sparkle", "relay"),
    "preferences-online-accounts": ("day-smoke", "cloud"),
    # Appearance & Style: dusk (Wallpaper as Monet Settings' Light & Wallpaper).
    "preferences-desktop-wallpaper": ("dawn-sun", "picture"),
    "preferences-desktop-theme-global": ("dusk-haze", "palette"),
    "preferences-desktop-cursors": ("dusk-violet", "pointer"),
    "preferences-desktop-font": ("dusk-glow", "type"),
    "preferences-desktop-font-installer": ("dusk-boat", "typeplus"),
    "preferences-desktop-animations": ("dusk-high", "motion"),
    # Apps & Windows: day (Default Apps and Notifications as in Monet Settings).
    "preferences-desktop-default-applications": ("day-high", "apps"),
    "preferences-desktop-filetype-association": ("day-water", "fileopen"),
    "preferences-desktop-notification-bell": ("dusk-sky", "bell"),
    "preferences-system-windows": ("day-cloud", "windows"),
    "preferences-system-windows-actions": ("day-calm", "window"),
    "preferences-system-tabbox": ("day-deep", "cards"),
    "preferences-desktop-virtual": ("day-west", "desks"),
    # Workspace: dawn.
    "preferences-desktop": ("dawn-mid", "sliders"),
    "preferences-desktop-search": ("dawn-masts", "search"),
    "preferences-desktop-baloo": ("dawn-masts", "search"),
    # Security & Privacy: night.
    "preferences-desktop-user-password": ("night-east", "lock"),
    "preferences-security": ("night-deep", "shieldcheck"),
    "preferences-system-network-remote": ("night-high", "remote"),
    # Language & Time: dusk (Date & Time as in Monet Settings).
    "preferences-desktop-locale": ("dusk-rose", "globe"),
    "preferences-system-time": ("dawn-water", "clock"),
    # System: (Power and Users as in Monet Settings).
    "preferences-system-power-management": ("dawn-sun", "power"),
    "preferences-system-users": ("dusk-sun", "person"),
    "preferences-system-login": ("night-shore", "door"),
}


def mark_svg(spot, glyph, paint):
    painting, (x, y) = SPOTS[spot]
    img = paint[painting].crop((x, y, x + 440, y + 440)).resize((160, 160), Image.LANCZOS)
    img = ImageEnhance.Color(img).enhance(1.25)
    # Pale daylight is deepened, so a white sign always reads.
    light = np.asarray(img.convert("L")).mean() / 255
    if light > 0.52:
        img = ImageEnhance.Color(ImageEnhance.Brightness(img).enhance(0.52 / light)).enhance(1.35)
    mask = Image.new("L", (640, 640), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, 639, 639], radius=186, fill=255)
    img = img.convert("RGBA")
    img.putalpha(mask.resize((160, 160), Image.LANCZOS))
    buf = io.BytesIO()
    img.quantize(256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG).save(buf, "PNG", optimize=True)
    data = base64.b64encode(buf.getvalue()).decode()
    # The sign: 58% of the swatch, centered, with a faint shadow a little below (as in Monet Settings).
    d = MARK_GLYPHS[glyph]
    sign = ('fill="none" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"')
    return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="0 0 128 128">\n'
            f"  <!-- Monet's mark for a page of More settings. Painted by tools/make-icons.py. -->\n"
            f'  <image x="6" y="6" width="116" height="116" xlink:href="data:image/png;base64,{data}"/>\n'
            f'  <path transform="translate(30.4 34.9) scale(2.8)" d="{d}" stroke="#000000" stroke-opacity="0.3" {sign}/>\n'
            f'  <path transform="translate(30.4 30.4) scale(2.8)" d="{d}" stroke="#FFFFFF" {sign}/>\n</svg>\n')


def settings_marks():
    paint = {n: Image.open(HOURS / f"{n}.jpg").convert("RGB") for n in ("dawn", "day", "dusk", "night")}
    out = THEME / "categories" / "scalable"
    out.mkdir(parents=True, exist_ok=True)
    for name, (spot, glyph) in MARKS.items():
        (out / f"{name}.svg").write_text(mark_svg(spot, glyph, paint))
    print("marked", len(MARKS), "pages of More settings")


INDEX = """[Icon Theme]
Name=Monet
Comment=Small oil paintings for Monet's apps, folders and menu, Breeze for everything else
Inherits=breeze,hicolor
Example=folder
DisplayDepth=32
Directories=apps/scalable,categories/scalable,devices/scalable,mimetypes/scalable,places/scalable

[apps/scalable]
Size=48
MinSize=16
MaxSize=512
Context=Applications
Type=Scalable

[categories/scalable]
Size=48
MinSize=16
MaxSize=512
Context=Categories
Type=Scalable

[devices/scalable]
Size=48
MinSize=16
MaxSize=512
Context=Devices
Type=Scalable

[mimetypes/scalable]
Size=48
MinSize=16
MaxSize=512
Context=MimeTypes
Type=Scalable

[places/scalable]
Size=48
MinSize=16
MaxSize=512
Context=Places
Type=Scalable
"""


def main():
    settings_art()
    TEXTURES.mkdir(parents=True, exist_ok=True)
    brush_texture(TEXTURES / "brush.png")
    for old in THEME.glob("*/scalable/*.svg"):
        old.unlink()
    paintings = {name: (paint, files) for name, (paint, files) in ICONS.items()}
    paintings.update({name: (paint, [main]) for name, (paint, main, _) in FILES.items()})
    for name, (paint, files) in paintings.items():
        text = svg(paint(), f"Monet icon: {(paint.__doc__ or name).splitlines()[0].rstrip('.')}.")
        for f in files:
            out = THEME / f.split("/")[0] / "scalable" / f"{f.split('/')[1]}.svg"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(text)
        print("painted", name)
    settings_marks()
    (THEME / "index.theme").write_text(INDEX)
    (THEME / "aliases").write_text(links())
    print("wrote", THEME.relative_to(ROOT), "and", (TEXTURES / "brush.png").relative_to(ROOT))


if __name__ == "__main__":
    main()
