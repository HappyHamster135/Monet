"""Draws Monet's icon theme: the system's own apps as painted pebbles.

Each icon is a round pebble glazed in a color from the paintings, with a few
brushstrokes of light across it and a white line drawing on top. Apps that
bring their own icon (Firefox, Steam, games) keep it; everything else comes
from Breeze.

Run from the repository root:  python3 tools/make-icons.py
Also writes the brush texture Monet uses for game covers without artwork.
"""

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
THEME = ROOT / "linux" / "share" / "icons" / "Monet"
TEXTURES = ROOT / "linux" / "share" / "monet" / "textures"

# Glyphs drawn with round 7-unit lines on a 128 grid.
GLYPHS = {
    "folder": "M38 50 a6 6 0 0 1 6 -6 h14 l7 7 h20 a6 6 0 0 1 6 6 v24 a6 6 0 0 1 -6 6 h-41 a6 6 0 0 1 -6 -6 Z",
    "terminal": "M40 50 l14 13 l-14 13 M62 80 h26",
    "sliders": "M38 52 h52 M38 76 h52 M54 44 v16 M76 68 v16",
    "bag": "M42 54 h44 l-4 34 a5 5 0 0 1 -5 4 h-26 a5 5 0 0 1 -5 -4 Z M52 56 v-6 a12 12 0 0 1 24 0 v6",
    "pulse": "M36 66 h14 l7 -16 l12 30 l8 -18 h15",
    "bin": "M44 50 h40 M58 50 v-6 h12 v6 M48 50 l3 36 a5 5 0 0 0 5 4 h16 a5 5 0 0 0 5 -4 l3 -36",
    "bin-full": "M44 50 h40 M58 50 v-6 h12 v6 M48 50 l3 36 a5 5 0 0 0 5 4 h16 a5 5 0 0 0 5 -4 l3 -36 M58 60 v20 M70 60 v20",
}

# name: (top color, bottom color, glyph, file names it stands for)
ICONS = {
    "files": ("#4DB4A0", "#1F6A5E", "folder", ["apps/system-file-manager", "apps/org.kde.dolphin"]),
    "terminal": ("#3E4456", "#171A24", "terminal", ["apps/utilities-terminal", "apps/org.kde.konsole"]),
    "settings": ("#A9B1C2", "#5D6577", "sliders", ["apps/preferences-system", "apps/systemsettings"]),
    "store": ("#A897E0", "#5A4A9C", "bag", ["apps/plasmadiscover", "apps/org.kde.discover"]),
    "monitor": ("#5C88D0", "#294985", "pulse", ["apps/utilities-system-monitor", "apps/org.kde.plasma-systemmonitor"]),
    "trash": ("#B9B3A9", "#6C665D", "bin", ["places/user-trash"]),
    "trash-full": ("#B9B3A9", "#6C665D", "bin-full", ["places/user-trash-full"]),
}


def brush_marks(seed):
    """A few diagonal strokes of light across the pebble, different for each icon."""
    rng = np.random.default_rng(seed)
    marks = []
    for i in range(5):
        y = 24 + i * 19 + rng.uniform(-5, 5)
        x0, x1 = rng.uniform(4, 30), rng.uniform(96, 124)
        w = rng.uniform(7, 14)
        a = rng.uniform(0.05, 0.12) if i < 2 else rng.uniform(0.03, 0.07)
        dy = rng.uniform(-10, -4)
        marks.append(f'<path d="M{x0:.1f} {y:.1f} Q64 {y + dy:.1f} {x1:.1f} {y - 6:.1f}" stroke="#FFFFFF" '
                     f'stroke-opacity="{a:.3f}" stroke-width="{w:.1f}" stroke-linecap="round" fill="none"/>')
    return "\n    ".join(marks)


def icon_svg(name, top, bottom, glyph):
    seed = sum(map(ord, name))
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <!-- Monet icon: {name}. A pebble glazed like the paintings, a white line drawing on top. -->
  <defs>
    <linearGradient id="glaze" x1="0.2" y1="0" x2="0.8" y2="1">
      <stop offset="0" stop-color="{top}"/>
      <stop offset="1" stop-color="{bottom}"/>
    </linearGradient>
    <linearGradient id="rim" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#FFFFFF" stop-opacity="0.55"/>
      <stop offset="0.5" stop-color="#FFFFFF" stop-opacity="0.08"/>
      <stop offset="1" stop-color="#FFFFFF" stop-opacity="0.18"/>
    </linearGradient>
    <radialGradient id="shade" cx="0.5" cy="0.95" r="0.6">
      <stop offset="0" stop-color="#000000" stop-opacity="0.22"/>
      <stop offset="1" stop-color="#000000" stop-opacity="0"/>
    </radialGradient>
    <clipPath id="pebble"><circle cx="64" cy="64" r="56"/></clipPath>
  </defs>
  <circle cx="64" cy="64" r="56" fill="url(#glaze)"/>
  <g clip-path="url(#pebble)">
    {brush_marks(seed)}
    <circle cx="64" cy="64" r="56" fill="url(#shade)"/>
  </g>
  <circle cx="64" cy="64" r="55.25" fill="none" stroke="url(#rim)" stroke-width="1.5"/>
  <path d="{GLYPHS[glyph]}" fill="none" stroke="#FFFFFF" stroke-width="7" stroke-linecap="round" stroke-linejoin="round"/>
</svg>
"""


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
            pts = []
            for i in range(17):
                t = -1 + i / 8
                half = width / 2 * max(0.0, 1 - abs(t) ** 2.4) ** (1 / 2.4)
                pts.append((t * length / 2, half))
            pts += [(px, -py) for px, py in reversed(pts)]
            ca, sa = math.cos(angle), math.sin(angle)
            poly = [(x + px * ca - py * sa, y + px * sa + py * ca) for px, py in pts]
            d.polygon(poly, fill=int(rng.uniform(10, 60)))
            x += length * rng.uniform(0.5, 0.9)
        y += rng.uniform(14, 26)
    alpha = big.filter(ImageFilter.GaussianBlur(1.6)).resize((w, h), Image.LANCZOS)
    img = Image.new("RGBA", (w, h), (255, 255, 255, 0))
    img.putalpha(alpha)
    img.save(path, optimize=True)


def main():
    for name, (top, bottom, glyph, files) in ICONS.items():
        svg = icon_svg(name, top, bottom, glyph)
        for f in files:
            out = THEME / f"{f.split('/')[0]}" / "scalable" / f"{f.split('/')[1]}.svg"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(svg)
    (THEME / "index.theme").write_text("""[Icon Theme]
Name=Monet
Comment=Monet's own apps as painted pebbles, Breeze for everything else
Inherits=breeze,hicolor
Example=system-file-manager
DisplayDepth=32
Directories=apps/scalable,places/scalable

[apps/scalable]
Size=48
MinSize=16
MaxSize=512
Context=Applications
Type=Scalable

[places/scalable]
Size=48
MinSize=16
MaxSize=512
Context=Places
Type=Scalable
""")
    print("wrote", THEME.relative_to(ROOT))
    TEXTURES.mkdir(parents=True, exist_ok=True)
    brush_texture(TEXTURES / "brush.png")
    print("wrote", (TEXTURES / "brush.png").relative_to(ROOT))


if __name__ == "__main__":
    main()
