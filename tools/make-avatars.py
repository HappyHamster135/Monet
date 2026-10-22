"""Paints Monet's account pictures: what KDE's Change Avatar offers, instead of
its dragon and photos. Square, filled to the edges (the picture is shown round):
pieces of The Hours (the sun at dawn, midday on the water, dusk, the moon, a
boatman, the harbor's lights at night) and small paintings from Monet's world
(a water lily, poppies, the Japanese bridge, a haystack, the magpie, irises, a
parasol on the hill, a sailboat), with the brush that paints Monet's icons.

Run from the repository root:  python3 tools/make-avatars.py
Writes linux/share/plasma/avatars/Monet/*.jpg (512 x 512).
"""

import importlib.util
import math
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "linux" / "share" / "plasma" / "avatars" / "Monet"
SIZE = 512

spec = importlib.util.spec_from_file_location("make_icons", Path(__file__).with_name("make-icons.py"))
mi = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mi)
S, N = mi.S, mi.N
box, circle, poly, ellipse, band, join, cut = mi.box, mi.circle, mi.poly, mi.ellipse, mi.band, mi.join, mi.cut
lit, one, flat, around = mi.lit, mi.one, mi.flat, mi.around

# Pieces of The Hours: painting, then the square's left, top and side in the 3840 x 2160 original.
HOURS = {
    "Sunrise": ("dawn", 1780, 300, 1200),
    "Midday": ("day", 2560, 760, 1200),
    "Dusk": ("dusk", 620, 560, 1300),
    "Moonlight": ("night", 300, 260, 1500),
    "Boatman": ("dawn", 560, 1260, 800),
    "Harbor lights": ("night", 2700, 600, 1000),
}


def everywhere():
    return np.ones((N, N), np.float32)


def leaf_notch(cx, cy, rx, ry, angle, at):
    """A lily pad's notch: a thin wedge from its middle to the edge."""
    a, w = math.radians(at), math.radians(9)
    far = 1.3
    return poly([(cx, cy), (cx + far * rx * math.cos(a - w), cy + far * ry * math.sin(a - w)),
                 (cx + far * rx * math.cos(a + w), cy + far * ry * math.sin(a + w))])


def water_lily():
    """Water lily: one open on its pad, the pond around it."""
    c = mi.Canvas(401)
    c.paint(everywhere(), lit("#3E7A7A", "#1E3A50", warm="#BFE3D4", cool="#2C3C78", light=0.2, shade=0.3), 5.0, flat(0),
            wander=0.12, accents=["#5E9AA8", "#2A5070", "#9FC8C0", "#C8B8E0"], accent_rate=0.18)
    pad = lit("#72B262", "#2F5E3E", warm="#D8E8A0", cool="#2A4A5A")
    for cx, cy, rx, ry, angle, at in ((46, 84, 32, 14, -6, 20), (104, 106, 22, 9, 4, 200), (98, 38, 19, 7, -3, 140),
                                      (16, 30, 13, 5, 8, 300), (26, 116, 14, 5, -5, 60)):
        shape = cut(poly(ellipse(cx, cy, rx, ry, angle, 72)), leaf_notch(cx, cy, rx, ry, angle, at))
        c.paint(shape, pad, 2.6, around(cx, cy), layers=2, wander=0.25, accents=["#8ACA6A", "#3E7A4A", "#B8D880"],
                accent_rate=0.2, thick=1.2)
    fx, fy = 48, 74
    petal = lit("#FFF6F8", "#E89AB8", y0=58, y1=84, warm="#FFFFFF", cool="#B07AA8", light=0.3, shade=0.25)
    for row, (reach, rx, ry, count, turn) in enumerate(((11, 9.5, 4.2, 8, 0), (7, 7.5, 3.6, 7, 22))):
        for k in range(count):
            a = math.radians(turn + k * 360 / count)
            px, py = fx + reach * math.cos(a), fy + 0.55 * reach * math.sin(a) - 2 * row
            c.paint(poly(ellipse(px, py, rx, ry, math.degrees(a) * 0.6, 40)), petal, 1.8, around(fx, fy), layers=2,
                    wander=0.2, accents=["#FFFFFF", "#F2B8CC"], accent_rate=0.2, thick=1.4)
    c.paint(circle(fx, fy - 3, 3.4), one("#F2B84B"), 1.4, around(fx, fy - 3), layers=2, thick=1.8)
    return c


def poppies():
    """Poppies: a hillside of them under a summer sky."""
    c = mi.Canvas(411)
    c.paint(box(0, 0, 128, 64), lit("#8FB6E6", "#EEF0F0", y0=0, y1=64, warm="#FFF4DC", cool="#7A8AC8"), 5.0, flat(-8),
            wander=0.25, accents=["#FFFFFF", "#C8DCF0", "#F6E8D8"], accent_rate=0.25)
    c.paint(poly([(0, 56), (22, 50), (46, 54), (70, 47), (98, 52), (128, 46), (128, 64), (0, 64)]),
            lit("#6A8A6A", "#4A6A5A", y0=46, y1=64, cool="#5A6A9A"), 2.8, flat(0), layers=2, wander=0.2)
    field = poly([(0, 60), (36, 56), (72, 60), (128, 54), (128, 128), (0, 128)])
    c.paint(field, lit("#A8C070", "#4E7A3A", y0=54, y1=128, warm="#E8D890", cool="#3A5A6A"), 4.4, flat(-12), wander=0.3,
            accents=["#C8B060", "#6A9A4A", "#2F5E3E"], accent_rate=0.2)
    rng = np.random.default_rng(5)
    for _ in range(70):
        y = rng.uniform(60, 126)
        depth = (y - 58) / 68
        x = rng.uniform(-2, 130)
        s = 1.6 + 5.2 * depth ** 1.3
        col = mi.hexrgb(str(rng.choice(["#E8402A", "#D9361A", "#F2552C", "#C42E1E", "#F06A40"])))
        c.dab(x * S, y * S, s * S, s * 0.8 * S, rng.uniform(-0.6, 0.6), col, everywhere(), thick=1.6, dry=0.1)
    return c


def bridge():
    """The Japanese bridge: a green arch over the lily pond, willows behind."""
    c = mi.Canvas(421)
    c.paint(everywhere(), lit("#4E8A4E", "#1E3626", warm="#C8E080", cool="#2A3A5A"), 4.6, flat(95), wander=0.35,
            accents=["#7ABA5E", "#2E5A32", "#A8C46A", "#4A6A9A"], accent_rate=0.25)
    pond = box(0, 80, 128, 128)
    c.paint(pond, lit("#4A8A7A", "#1E4A4A", y0=80, y1=128, warm="#C8E0B0", cool="#2C3C78"), 4.0, flat(0), wander=0.15,
            accents=["#7AB0A0", "#2A5A5A", "#E8D0E0"], accent_rate=0.2)
    for x, y in ((14, 96), (40, 104), (70, 98), (98, 108), (118, 94), (28, 118), (84, 120), (56, 112)):
        c.paint(poly(ellipse(x, y, 8, 2.8, 0, 36)), lit("#7ABA6A", "#3E7A4A"), 1.6, flat(0), layers=1, thick=1.1)
    for x, y in ((40, 102), (98, 106)):
        c.dab(x * S, y * S, 3.4 * S, 2.6 * S, 0, mi.hexrgb("#F6C8D8"), everywhere(), thick=1.6, dry=0)
    arch = [(x, 76 - 30 * math.sin(math.pi * (x - 4) / 120)) for x in range(4, 125, 4)]
    reflection = [(x, 84 + 0.4 * (76 - y)) for x, y in arch]
    c.mark(reflection, 4.6, "#3E7A6A", None, thick=0.6)
    c.paint(band(arch, 7.0), lit("#A8E0B0", "#4E9A6A", y0=46, y1=80, warm="#E8FFD8"), 2.0, flat(0), layers=2, wander=0.1,
            thick=1.5)
    rail = [(x, y - 13) for x, y in arch]
    c.mark(rail, 2.8, "#98D4A4", None, thick=1.3)
    for x, y in arch[1:-1:3]:
        c.mark([(x, y - 1), (x, y - 13)], 2.0, "#7CC090", None, thick=1.1)
    return c


def sailboat():
    """A sailboat at Argenteuil, its sail catching the sun."""
    c = mi.Canvas(471)
    c.paint(box(0, 0, 128, 70), lit("#9CC0EC", "#E6EEF4", y0=0, y1=70, warm="#FFF6E0", cool="#7A8AC8"), 5.0, flat(-6),
            wander=0.25, accents=["#FFFFFF", "#C8DCF0", "#F6E8D8"], accent_rate=0.25)
    c.paint(poly([(0, 66), (34, 62), (70, 65), (128, 60), (128, 72), (0, 72)]), lit("#7A9A7A", "#5A7A6A"), 2.6, flat(0),
            layers=2, wander=0.15)
    water = box(0, 70, 128, 128)
    c.paint(water, lit("#5C88D0", "#2C4C88", y0=70, y1=128, warm="#BFE0F0", cool="#2C3C78"), 4.0, flat(0), wander=0.15,
            accents=["#9FC8F0", "#2A4A8A", "#F6E8D0", "#E86A40"], accent_rate=0.2)
    for y, w in ((92, 26), (100, 20), (108, 16), (116, 11)):  # the sail in the water
        c.mark([(62 - w / 2, y), (62 + w / 2, y + 0.6)], 2.4, "#E8E0D0", water, thick=0.8)
    c.paint(poly([(40, 84), (88, 84), (80, 92), (46, 92)]), lit("#B07A4C", "#6A4528"), 2.0, flat(0), layers=2, thick=1.3)
    c.mark([(62, 84), (62, 22)], 2.0, "#4A3A2A", None, thick=1.2)
    c.paint(poly([(64, 24), (92, 80), (64, 80)]), lit("#FFFFFF", "#E0D6C4", y0=24, y1=80, warm="#FFF8E8", cool="#9A90B8"),
            3.0, flat(70), wander=0.15, thick=1.3)
    c.paint(poly([(60, 30), (60, 80), (36, 80)]), lit("#F27A50", "#C8381E", y0=30, y1=80, warm="#FFD0A0"), 2.8, flat(110),
            wander=0.15, thick=1.3)
    return c


def haystack():
    """A haystack at the end of the day, its shadow violet."""
    c = mi.Canvas(431)
    c.paint(box(0, 0, 128, 70), lit("#F6D0A8", "#E8A4B0", y0=0, y1=70, warm="#FFF0D0", cool="#A890C8"), 5.0, flat(-6),
            wander=0.25, accents=["#FFE0B0", "#E8B0C8", "#C8A8D8"], accent_rate=0.25)
    c.paint(poly([(0, 64), (40, 58), (84, 63), (128, 56), (128, 70), (0, 70)]), lit("#A898C0", "#8A7AA8"), 2.6, flat(0),
            layers=2, wander=0.15)
    c.paint(box(0, 66, 128, 128), lit("#DDB474", "#8A6A4A", y0=66, y1=128, warm="#FFE0A0", cool="#7A5A8A"), 4.4, flat(0),
            wander=0.2, accents=["#E8C890", "#A88A5A", "#B898C0"], accent_rate=0.2)
    c.paint(poly(ellipse(90, 106, 40, 6.5, -3, 60)), one("#7A5A9A"), 3.0, flat(0), layers=2, opacity=0.65, thick=0.8)
    # A bell of straw, rounded over the top: the strokes fall from its crown like straw.
    stack = poly([(24, 106), (27, 88), (32, 72), (40, 58), (50, 47), (60, 42), (70, 47), (80, 58), (88, 72), (93, 88),
                  (96, 106)])
    c.paint(stack, lit("#F8C862", "#B05A2A", y0=40, y1=106, warm="#FFEAA8", cool="#7A4A8A", light=0.32, shade=0.38), 3.0,
            lambda x, y: math.atan2(y - 30, x - 60), wander=0.25, accents=["#FFD27A", "#D9731A", "#A86AA8", "#E8A050"],
            accent_rate=0.25, thick=1.5)
    c.paint(poly([(26, 98), (94, 98), (96, 106), (24, 106)]), lit("#C07A3A", "#8A4A3A"), 1.8, flat(0), layers=2,
            wander=0.2, opacity=0.85, thick=1.2)
    return c


def magpie():
    """The magpie on the gate, in snow the sun is warming."""
    c = mi.Canvas(441)
    c.paint(everywhere(), lit("#FBF4E4", "#C8D4E8", warm="#FFE8C0", cool="#8A9AD0", light=0.25, shade=0.3), 5.0,
            flat(-4), wander=0.25, accents=["#FFFFFF", "#D8E0F0", "#F6E0C0", "#B8C4E8"], accent_rate=0.3)
    wood = "#5A4A52"
    for x in (16, 98):
        c.paint(poly([(x + 8, 112), (x + 30, 120), (x + 26, 124), (x + 4, 116)]), one("#9AA8D8"), 2.2, flat(18),
                layers=1, opacity=0.6, thick=0.6)
        c.mark([(x, 50), (x + 1, 114)], 4.4, wood, None, thick=1.4)
    for y in (66, 92):
        c.mark([(4, y + 1), (124, y - 1)], 3.0, wood, None, thick=1.3)
    c.mark([(16, 92), (98, 66)], 2.6, wood, None, thick=1.2)
    ink = "#1E1E2A"
    c.paint(band([(66, 62), (86, 72)], 3.6), lit("#3A4A8A", "#141420", y0=60, y1=74), 1.4, flat(26), layers=2, thick=1.4)
    c.paint(poly(ellipse(58, 56, 10, 7, -18, 48)), one(ink), 1.8, around(58, 56), layers=2, thick=1.6)
    c.paint(poly(ellipse(60, 59, 5.6, 3.8, -18, 36)), one("#F6F6F2"), 1.4, around(60, 59), layers=2, thick=1.4)
    c.paint(poly(ellipse(56, 53, 6, 2.4, -24, 30)), lit("#4A6AB0", "#2A3A6A"), 1.0, flat(-24), layers=1, thick=1.2)
    c.paint(circle(49, 48, 4.8), one(ink), 1.4, around(49, 48), layers=2, thick=1.6)
    c.mark([(45, 48.5), (40.5, 49.5)], 1.6, "#2A2A30", None, thick=1.2)
    c.dab(48 * S, 46.6 * S, 1.6 * S, 1.6 * S, 0, mi.hexrgb("#F6F2E8"), everywhere(), thick=1.0, dry=0)
    for x in (57, 61):
        c.mark([(x, 62), (x, 66)], 0.9, "#2A2A30", None, thick=0.8)
    return c


def irises():
    """Irises in the garden, purple against the green."""
    c = mi.Canvas(451)
    c.paint(everywhere(), lit("#D0E2B0", "#5E8A5A", warm="#FFF4D0", cool="#4A6A9A"), 5.0, flat(80), wander=0.3,
            accents=["#E8F0C8", "#8AB07A", "#B8C8E8"], accent_rate=0.25)
    leaf = lit("#6AAA5E", "#2F5E3E", warm="#C8E0A0", cool="#2A4A6A")
    for x0, x1, y1 in ((10, 18, 70), (22, 16, 58), (34, 44, 80), (52, 58, 64), (60, 72, 90), (78, 74, 58), (90, 102, 76),
                       (104, 98, 54), (116, 124, 72), (46, 36, 52)):
        c.paint(band([(x0, 130), (x1, y1)], 3.2), leaf, 1.6, flat(math.degrees(math.atan2(y1 - 130, x1 - x0))),
                layers=2, wander=0.1, thick=1.1)
    for fx, fy, s in ((38, 50, 1.05), (86, 38, 0.9), (68, 78, 1.15), (20, 86, 0.85), (106, 66, 0.9)):
        purple = lit("#A27BD6", "#4A2A8A", y0=fy - 14 * s, y1=fy + 12 * s, warm="#E8D8FF", cool="#2A1A5A", light=0.3)
        for dx, dy, rx, ry, a in ((-5, -8, 4.2, 8.0, -18), (5, -8, 4.2, 8.0, 18), (0, -10, 3.6, 8.4, 0),
                                  (-8, 4, 7.6, 4.4, 28), (8, 4, 7.6, 4.4, -28)):
            c.paint(poly(ellipse(fx + dx * s, fy + dy * s, rx * s, ry * s, a, 40)), purple, 1.6, around(fx, fy), layers=2,
                    wander=0.3, accents=["#C8A8F0", "#3A1A6A"], accent_rate=0.2, thick=1.4)
        for dx in (-6, 6):
            c.dab((fx + dx * s) * S, (fy + 3 * s) * S, 3.6 * s * S, 1.8 * s * S, 0.4 if dx > 0 else -0.4,
                  mi.hexrgb("#F2C24B"), everywhere(), thick=1.4, dry=0)
    return c


def parasol():
    """A parasol on the hill, against a windy summer sky."""
    c = mi.Canvas(461)
    c.paint(everywhere(), lit("#78A8E0", "#D8E6F2", warm="#FFF6E8", cool="#6A7AC0"), 5.0, flat(-20), wander=0.3,
            accents=["#FFFFFF", "#B8D0F0", "#E8EEF6"], accent_rate=0.3)
    for cx, cy, rx, ry in ((30, 26, 22, 9), (96, 18, 20, 7), (84, 46, 16, 6)):
        c.paint(poly(ellipse(cx, cy, rx, ry, -10, 48)), lit("#FFFFFF", "#D8DCEC", y0=cy - ry, y1=cy + ry, cool="#9AA0D0"),
                2.6, around(cx, cy), layers=2, wander=0.4, opacity=0.9, thick=1.2)
    hill = poly([(0, 100), (40, 92), (80, 96), (128, 88), (128, 128), (0, 128)])
    c.paint(hill, lit("#9AC070", "#4E7A3A", y0=88, y1=128, warm="#F0E8A0", cool="#3A5A6A"), 4.0, flat(-10), wander=0.3,
            accents=["#C8D890", "#5E8A4A", "#E8C8A0"], accent_rate=0.25)
    dress = poly([(62, 58), (72, 58), (82, 98), (54, 98)])
    c.paint(dress, lit("#FFFFFF", "#C8CCE4", y0=58, y1=98, warm="#FFF8E8", cool="#8A90C8", light=0.3, shade=0.4), 2.2,
            flat(80), layers=2, wander=0.3, accents=["#E8ECF8", "#B0B8E0"], accent_rate=0.25, thick=1.3)
    c.paint(circle(67, 53, 4.2), lit("#E8C0A0", "#B08070"), 1.2, around(67, 53), layers=2, thick=1.3)
    c.mark([(68, 56), (78, 36)], 1.2, "#4A3A3A", None, thick=0.9)
    canopy = poly([(58, 40), (64, 28), (76, 22), (90, 24), (98, 32), (96, 38), (84, 36), (72, 38)])
    c.paint(canopy, lit("#4E9A6A", "#245A40", y0=22, y1=40, warm="#B8E0A0", cool="#2A4A5A", light=0.3), 2.0, around(78, 44),
            layers=2, wander=0.3, accents=["#7AC08A", "#1E4A34"], accent_rate=0.2, thick=1.3)
    c.paint(poly([(54, 98), (82, 98), (92, 102), (48, 102)]), one("#6A7AA8"), 1.6, flat(0), layers=1, opacity=0.6,
            thick=0.6)
    return c


PAINTED = {"Water lily": water_lily, "Poppies": poppies, "Japanese bridge": bridge, "Haystack": haystack,
           "Magpie": magpie, "Irises": irises, "Parasol": parasol, "Sailboat": sailboat}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("*.jpg"):
        old.unlink()
    for name, (painting, x, y, side) in HOURS.items():
        img = Image.open(mi.HOURS / f"{painting}.jpg").convert("RGB").crop((x, y, x + side, y + side))
        img.resize((SIZE, SIZE), Image.LANCZOS).save(OUT / f"{name}.jpg", quality=90, optimize=True)
        print("cut", name)
    for name, paint in PAINTED.items():
        img = paint().finish(shadow=0, size=SIZE).convert("RGB")
        img.save(OUT / f"{name}.jpg", quality=90, optimize=True)
        print("painted", name)
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
