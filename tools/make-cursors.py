"""Draws Monet's pointer: ink with a paper edge and a soft shadow, and Monet's
sun, breathing over its rippling reflection, while something is working.

Writes an Xcursor theme (24, 32, 48 and 64 px) to linux/share/icons/Monet-cursors.
Each cursor is drawn once; the other names programs ask for are listed in
`aliases` and linked by install.sh. Anything not drawn here comes from Breeze.

Run from the repository root:  python3 tools/make-cursors.py
"""

import math
import struct
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "linux" / "share" / "icons" / "Monet-cursors"
FONT = ROOT / "image" / "installer" / "product" / "usr" / "share" / "fonts" / "monet" / "Inter-Bold.otf"
SIZES = (24, 32, 48, 64)
INK, PAPER, SHADOW = (28, 27, 25), (251, 247, 238), (28, 27, 25)
SUN_TOP, SUN_BOTTOM, SUN = (255, 154, 94), (229, 64, 28), (242, 85, 44)
K = 4  # drawn at four times the size, then shrunk


def rot(points, degrees, cx=16, cy=16):
    a = math.radians(degrees)
    return [(cx + (x - cx) * math.cos(a) - (y - cy) * math.sin(a), cy + (x - cx) * math.sin(a) + (y - cy) * math.cos(a))
            for x, y in points]


ARROW = [(3, 2), (3, 23.6), (8.3, 18.8), (12, 27.2), (15.5, 25.6), (11.8, 17.4), (18.8, 17.4)]


def double_arrow(angle):
    shaft = [(8.5, 14.9), (23.5, 14.9), (23.5, 17.1), (8.5, 17.1)]
    left = [(3.5, 16), (10, 10.2), (10, 21.8)]
    right = [(28.5, 16), (22, 10.2), (22, 21.8)]
    return [("poly", rot(p, angle)) for p in (shaft, left, right)]


SHAPES = {
    # name: (hotspot on the 32 grid, ink shapes)
    "default": ((3, 2), [("poly", ARROW)]),
    "pointer": ((14.3, 3.6), [("rrect", (12, 3.4, 16.6, 18), 2.3), ("rrect", (9.4, 13.4, 23.6, 27.6), 4.4),
                              ("rrect", (16.2, 11.6, 19.8, 18), 1.8), ("rrect", (19.6, 12.6, 23.2, 19), 1.8),
                              ("poly", [(9.8, 15.2), (6.4, 18.6), (6.8, 21.2), (10.2, 23.4)])]),
    "text": ((16, 16), [("rrect", (15.1, 6.6, 16.9, 25.4), 0.8), ("rrect", (11.4, 5, 20.6, 7.2), 1.1),
                        ("rrect", (11.4, 24.8, 20.6, 27), 1.1)]),
    "crosshair": ((16, 16), [("rrect", (4, 15.1, 13, 16.9), 0.8), ("rrect", (19, 15.1, 28, 16.9), 0.8),
                             ("rrect", (15.1, 4, 16.9, 13), 0.8), ("rrect", (15.1, 19, 16.9, 28), 0.8), ("disc", (16, 16, 1.3))]),
    "not-allowed": ((16, 16), [("ring", (16, 16, 9.6, 7.2)), ("poly", rot([(6.6, 14.8), (25.4, 14.8), (25.4, 17.2), (6.6, 17.2)], 45))]),
    "move": ((16, 16), [("poly", p) for p in ([(7, 14.7), (25, 14.7), (25, 17.3), (7, 17.3)], [(14.7, 7), (17.3, 7), (17.3, 25), (14.7, 25)],
                                              [(3, 16), (8.5, 11.2), (8.5, 20.8)], [(29, 16), (23.5, 11.2), (23.5, 20.8)],
                                              [(16, 3), (11.2, 8.5), (20.8, 8.5)], [(16, 29), (11.2, 23.5), (20.8, 23.5)])]),
    "ew-resize": ((16, 16), double_arrow(0)),
    "ns-resize": ((16, 16), double_arrow(90)),
    "nwse-resize": ((16, 16), double_arrow(45)),
    "nesw-resize": ((16, 16), double_arrow(-45)),
    "help": ((3, 2), [("poly", ARROW), ("text", (17.5, 2.5, "?", 15))]),
    "grab": ((16, 14), [("rrect", (8.6, 13, 23.6, 27.4), 4.6)] + [("rrect", (x, y, x + 3.4, 17), 1.7) for x, y in
                        ((9, 6.6), (12.6, 4.6), (16.2, 4.8), (19.8, 6.8))] + [("poly", [(9, 17), (5, 13.6), (3.8, 15.4), (8.4, 22)])]),
    "grabbing": ((16, 16), [("rrect", (8.6, 11.4, 23.6, 26.4), 4.6)] + [("rrect", (x, 9.6, x + 3.4, 14), 1.7) for x in (9.2, 12.8, 16.4, 20)]
                 + [("poly", [(8.8, 16), (5.6, 15.4), (5, 17.6), (9, 21.6)])]),
}

# The names programs ask for, by the cursor drawn for them.
ALIASES = {
    "default": ["left_ptr", "arrow", "top_left_arrow", "left_arrow"],
    "pointer": ["hand1", "hand2", "pointing_hand", "e29285e634086352946a0e7090d73106", "9d800788f1b08800ae810202380a0822"],
    "text": ["xterm", "ibeam"],
    "wait": ["watch", "0426c94ea35c87780ff01dc239897213"],
    "progress": ["left_ptr_watch", "half-busy", "3ecb610c1bf2410f44200f48c40d3599", "00000000000000020006000e7e9ffc3f",
                 "08e8e1c95fe2fc01f976f1e063a24ccd"],
    "crosshair": ["cross", "tcross", "cross_reverse", "diamond_cross"],
    "not-allowed": ["forbidden", "crossed_circle", "no-drop", "circle", "03b6e0fcb3499374a867c041f52298f0"],
    "move": ["fleur", "all-scroll", "size_all", "4498f0e0c1937ffe01fd06f973665830", "9081237383d90e509aa00f00170e968f"],
    "ew-resize": ["size_hor", "h_double_arrow", "sb_h_double_arrow", "col-resize", "split_h", "e-resize", "w-resize",
                  "right_side", "left_side", "14fef782d02440884392942c11205230", "028006030e0e7ebffc7f7070c0600140"],
    "ns-resize": ["size_ver", "v_double_arrow", "sb_v_double_arrow", "row-resize", "split_v", "n-resize", "s-resize",
                  "top_side", "bottom_side", "2870a09082c103050810ffdffffe0204", "00008160000006810000408080010102"],
    "nwse-resize": ["size_fdiag", "bd_double_arrow", "nw-resize", "se-resize", "top_left_corner", "bottom_right_corner",
                    "c7088f0f3e6c8088236ef8e1e3e70000"],
    "nesw-resize": ["size_bdiag", "fd_double_arrow", "ne-resize", "sw-resize", "top_right_corner", "bottom_left_corner",
                    "fcf1c3c7cd4491d801f1e1c78f100000"],
    "help": ["question_arrow", "whats_this", "left_ptr_help", "d9ce0ab605698f320427677b458ad60b", "5c6cd98b3f3ebcb1f9c7f1c204630408"],
    "grab": ["openhand", "9141b49c8149039304290b508d208c40", "5aca4d189052212118709018842178c0"],
    "grabbing": ["closedhand", "dnd-none", "208530c400c041818281048008011002", "fcf21c00b30f7e3f83fe0dfd12e71cff"],
}


def draw_ink(shapes, size):
    """The shapes as a mask at K times size."""
    s = size / 32 * K
    img = Image.new("L", (size * K, size * K), 0)
    d = ImageDraw.Draw(img)
    for kind, *geo in shapes:
        if kind == "poly":
            d.polygon([(x * s, y * s) for x, y in geo[0]], fill=255)
        elif kind == "rrect":
            (x0, y0, x1, y1), r = geo
            d.rounded_rectangle([x0 * s, y0 * s, x1 * s, y1 * s], radius=r * s, fill=255)
        elif kind == "disc":
            x, y, r = geo[0]
            d.ellipse([(x - r) * s, (y - r) * s, (x + r) * s, (y + r) * s], fill=255)
        elif kind == "ring":
            x, y, r0, r1 = geo[0]
            d.ellipse([(x - r0) * s, (y - r0) * s, (x + r0) * s, (y + r0) * s], fill=255)
            d.ellipse([(x - r1) * s, (y - r1) * s, (x + r1) * s, (y + r1) * s], fill=0)
        elif kind == "text":
            x, y, text, px = geo[0]
            d.text((x * s, y * s), text, font=ImageFont.truetype(str(FONT), int(px * s)), fill=255)
    return img


def layer(mask, color):
    out = Image.new("RGBA", mask.size, color + (0,))
    out.putalpha(mask)
    return out


def finish(ink, size, extra=None):
    """Paper edge, soft shadow, ink on top; then shrunk to size."""
    big = size * K
    edge = ink.filter(ImageFilter.MaxFilter(2 * int(1.5 * big / 32) + 1))
    if extra is not None:
        edge = Image.fromarray(np.maximum(np.asarray(edge), np.asarray(extra[0].filter(ImageFilter.MaxFilter(2 * int(1.4 * big / 32) + 1)))))
    shadow = edge.filter(ImageFilter.GaussianBlur(1.6 * big / 32)).point(lambda v: int(v * 0.36))
    shadow = shadow.transform(shadow.size, Image.AFFINE, (1, 0, -0.9 * big / 32, 0, 1, -1.4 * big / 32))  # down and right
    img = layer(shadow, SHADOW)
    img.alpha_composite(layer(edge, PAPER))
    img.alpha_composite(layer(ink, INK))
    if extra is not None:
        img.alpha_composite(extra[1])
    return img.resize((size, size), Image.LANCZOS)


def sun_frame(size, frame, frames, cx, cy, r, scale=1.0):
    """Monet's sun over its reflection; the strokes ripple and the light breathes."""
    big = size * K
    s = size / 32 * K
    phase = 2 * math.pi * frame / frames
    mask = Image.new("L", (big, big), 0)
    color = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    d, dc = ImageDraw.Draw(mask), ImageDraw.Draw(color)
    bright = 0.86 + 0.14 * math.sin(phase)
    for i in range(int(r * s), 0, -1):  # the disc, lighter toward the top
        t = 1 - i / (r * s)
        c = tuple(int((a * (1 - t * 0.6) + b * t * 0.6) * bright) for a, b in zip(SUN_BOTTOM, SUN_TOP))
        dc.ellipse([cx * s - i, cy * s - i - (r * s - i) * 0.25, cx * s + i, cy * s + i - (r * s - i) * 0.25], fill=c + (255,))
    d.ellipse([(cx - r) * s, (cy - r) * s, (cx + r) * s, (cy + r) * s], fill=255)
    for k, (dy, length, width, alpha) in enumerate(((1.75, 2.6, 0.42, 0.92), (2.3, 1.85, 0.34, 0.68), (2.8, 1.1, 0.27, 0.46))):
        grow = 1 + 0.18 * math.sin(phase - k * 0.9)
        y = cy + r * dy * scale
        half = r * length * grow * scale / 2
        w = r * width * scale
        box = [(cx - half) * s, (y - w / 2) * s, (cx + half) * s, (y + w / 2) * s]
        d.rounded_rectangle(box, radius=w / 2 * s, fill=255)
        dc.rounded_rectangle(box, radius=w / 2 * s, fill=SUN + (int(255 * alpha),))
    return mask, color


def xcursor(images):
    """Xcursor file: [(nominal size, image, (hot x, hot y), delay ms)]."""
    header = struct.pack("<4sIII", b"Xcur", 16, 0x10000, len(images))
    toc, chunks, pos = b"", b"", 16 + 12 * len(images)
    for nominal, img, (hx, hy), delay in images:
        w, h = img.size
        rgba = np.asarray(img.convert("RGBA")).astype(np.uint32)
        a = rgba[..., 3]
        premul = (rgba[..., :3] * a[..., None] // 255).astype(np.uint32)
        argb = (a << 24) | (premul[..., 0] << 16) | (premul[..., 1] << 8) | premul[..., 2]
        chunk = struct.pack("<IIIIIIIII", 36, 0xFFFD0002, nominal, 1, w, h, int(hx), int(hy), delay) + argb.astype("<u4").tobytes()
        toc += struct.pack("<III", 0xFFFD0002, nominal, pos)
        chunks += chunk
        pos += len(chunk)
    return header + toc + chunks


def cursor(name):
    frames = []
    for size in SIZES:
        f = size / 32
        if name in SHAPES:
            (hx, hy), shapes = SHAPES[name]
            frames.append((size, finish(draw_ink(shapes, size), size), (hx * f, hy * f), 0))
        elif name == "wait":
            for i in range(12):
                mask, color = sun_frame(size, i, 12, 16, 10, 6.4)
                frames.append((size, finish(Image.new("L", mask.size, 0), size, (mask, color)), (16 * f, 16 * f), 70))
        elif name == "progress":
            for i in range(12):
                mask, color = sun_frame(size, i, 12, 24, 19, 3.6)
                frames.append((size, finish(draw_ink([("poly", ARROW)], size), size, (mask, color)), (3 * f, 2 * f), 70))
    return xcursor(frames)


def main():
    folder = OUT / "cursors"
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.iterdir():
        old.unlink()
    for name in list(SHAPES) + ["wait", "progress"]:
        (folder / name).write_bytes(cursor(name))
        print("drew", name)
    (OUT / "aliases").write_text("".join(f"{alias} {name}\n" for name, names in ALIASES.items() for alias in names))
    (OUT / "index.theme").write_text("[Icon Theme]\nName=Monet\nComment=Ink with a paper edge; Monet's sun while it works\n"
                                     "Inherits=breeze_cursors\n")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
