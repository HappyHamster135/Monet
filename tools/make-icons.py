"""Draws Monet's icon theme: painted marks for Monet's own apps, painted folders.

Monet's icons are made the way its logo is: a few confident brushstrokes,
glazed in the paintings' colors, with no circle or tile around them. Folders
are small canvases, each glazed in the light of one painting, so Pictures,
Downloads and Music are told apart by color as much as by their mark.

Apps that bring their own icon (Firefox, Steam, games) keep it; everything
else comes from Breeze.

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


class Icon:
    """One 128 x 128 SVG, built up from gradients and painted shapes."""

    def __init__(self, comment):
        self.comment = comment
        self.defs = []
        self.body = []
        self.ids = 0

    def gradient(self, top, bottom, x1=0.3, y1=0.0, x2=0.7, y2=1.0):
        self.ids += 1
        gid = f"g{self.ids}"
        self.defs.append(f'<linearGradient id="{gid}" x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}">'
                         f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/></linearGradient>')
        return f"url(#{gid})"

    def add(self, shape):
        self.body.append(shape)

    def fit(self, cx, cy, scale):
        """Scales the drawing around (cx, cy) and centers it, so every icon
        sits on the same grid: about 0.8 of the canvas along its long side."""
        self.body = [f'<g transform="translate(64 64) scale({scale}) translate({-cx} {-cy})">'] + self.body + ["</g>"]

    def svg(self):
        return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">\n'
                f"  <!-- {self.comment} -->\n"
                f"  <defs>{''.join(self.defs)}</defs>\n  " + "\n  ".join(self.body) + "\n</svg>\n")


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


def path(points):
    return "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in points) + " Z"


def dab(icon, cx, cy, length, width, fill, angle=0.0, bend=0.0, opacity=1.0, shine=True):
    """A brushstroke with a lighter bristle mark along its upper side."""
    icon.add(f'<path d="{path(dab_points(cx, cy, length, width, angle, bend))}" fill="{fill}" opacity="{opacity}"/>')
    if shine and width >= 6:
        a = math.radians(angle)
        ox, oy = math.sin(a) * width * 0.2, -math.cos(a) * width * 0.2
        icon.add(f'<path d="{path(dab_points(cx + ox, cy + oy, length * 0.72, width * 0.22, angle, bend))}" '
                 f'fill="#ffffff" opacity="{0.28 * opacity:.2f}"/>')


def rounded(x0, y0, x1, y1, r):
    return (f"M{x0 + r},{y0} H{x1 - r} A{r},{r} 0 0 1 {x1},{y0 + r} V{y1 - r} A{r},{r} 0 0 1 {x1 - r},{y1} "
            f"H{x0 + r} A{r},{r} 0 0 1 {x0},{y1 - r} V{y0 + r} A{r},{r} 0 0 1 {x0 + r},{y0} Z")


def line_mark(icon, d, color="#ffffff", width=7.0, shadow=True):
    """A drawn mark on top of a canvas: round ends, a soft shadow below."""
    if shadow:
        icon.add(f'<path d="{d}" fill="none" stroke="#000000" stroke-opacity="0.22" stroke-width="{width}" '
                 f'stroke-linecap="round" stroke-linejoin="round" transform="translate(0 1.6)"/>')
    icon.add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" stroke-linecap="round" stroke-linejoin="round"/>')


# Folders: which painting each one's front is cut from (painting, crop box in
# the 3840 x 2160 original), the color of its back, and the mark drawn on it.
HOURS = ROOT / "linux" / "share" / "wallpapers" / "Monet" / "contents" / "hours"
FOLDERS = {
    "folder": ("dawn", (2080, 1260, 2980, 1843), "#2E4A63", None),
    "user-home": ("dawn", (2183, 538, 3083, 1121), "#6E5878", "M46 78 L64 62 L82 78 M52 73 V92 H76 V73"),
    "user-desktop": ("day", (300, 90, 1200, 673), "#3E6680", "M44 64 H84 V86 H44 Z M58 96 H70"),
    "folder-documents": (None, None, "#A3947A", "M48 64 H80 M48 75 H80 M48 86 H68"),
    "folder-download": ("night", (560, 230, 1460, 813), "#141C38", "M64 58 V88 M52 77 L64 89 L76 77"),
    "folder-pictures": ("dusk", (870, 700, 1770, 1283), "#5B3F6E", "M45 62 H83 V92 H45 Z M48 89 L58 78 L66 86 L72 80 L81 89"),
    "folder-music": ("dusk", (2240, 80, 3140, 663), "#3E3470", "M58 88 V60 L80 56 V82 M58 88 a6 6 0 1 1 -0.1 0 M80 82 a6 6 0 1 1 -0.1 0"),
    "folder-videos": ("dusk", (880, 1240, 1780, 1823), "#4A2448", "play"),
    "folder-games": ("night", (2700, 980, 3600, 1563), "#0E1430", "M48 70 H80 a10 10 0 0 1 0 20 H48 a10 10 0 0 1 0 -20 Z M54 80 H62 M58 76 V84 M74 78 h.1 M78 82 h.1"),
}
FRONT = (10, 40, 118, 110, 11)  # x0, y0, x1, y1, corner radius on the 128 grid


def canvas_image(painting, crop):
    """The folder's front as a small rounded PNG: a piece of a painting, or paper."""
    import base64
    import io
    x0, y0, x1, y1, r = FRONT
    w, h, k = (x1 - x0) * 2, (y1 - y0) * 2, 2
    if painting:
        from PIL import ImageEnhance
        img = Image.open(HOURS / f"{painting}.jpg").convert("RGB").crop(crop).resize((w, h), Image.LANCZOS)
        # Small pieces of a painting look muddy; give them back some color.
        img = ImageEnhance.Contrast(ImageEnhance.Color(img).enhance(1.3)).enhance(1.12)
    else:
        # Documents are paper: cream, with a few strokes of the brush.
        img = Image.new("RGB", (w, h), (247, 242, 232))
        tex = Image.open(TEXTURES / "brush.png").resize((w * 2, h * 2)).crop((0, 0, w, h))
        shade = Image.new("RGB", (w, h), (214, 202, 180))
        img = Image.composite(shade, img, tex.getchannel("A").point(lambda v: min(255, v * 2)))
    arr = np.asarray(img).astype(np.float32)
    # A little light from above, a little shade below: it reads as a sheet.
    ramp = np.linspace(1.10, 0.86, h)[:, None, None]
    arr = np.clip(arr * ramp, 0, 255)
    img = Image.fromarray(arr.astype(np.uint8)).convert("RGBA")
    mask = Image.new("L", (w * 4, h * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, w * 4 - 1, h * 4 - 1], radius=r * k * 4, fill=255)
    img.putalpha(mask.resize((w, h), Image.LANCZOS))
    buf = io.BytesIO()
    img.quantize(colors=128, method=Image.Quantize.FASTOCTREE).save(buf, "PNG", optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def folder_icon(name, painting, crop, back, mark):
    icon = Icon(f"Monet folder: {name}. Its front is cut from one of Monet's paintings.")
    icon.add(f'<path d="M14 30 a8 8 0 0 1 8 -8 H46 a8 8 0 0 1 6.5 3.4 L57 32 H106 a8 8 0 0 1 8 8 V100 H14 Z" fill="{back}"/>')
    x0, y0, x1, y1, _ = FRONT
    icon.add(f'<path d="{rounded(x0, y0 + 2, x1, y1 + 2, 11)}" fill="#000000" opacity="0.2"/>')
    icon.add(f'<image x="{x0}" y="{y0}" width="{x1 - x0}" height="{y1 - y0}" '
             f'href="data:image/png;base64,{canvas_image(painting, crop)}"/>')
    icon.add(f'<path d="M21 41.2 H107" stroke="#ffffff" stroke-opacity="0.6" stroke-width="1.6" stroke-linecap="round"/>')
    ink = "#4A4540" if painting is None else "#ffffff"
    if mark == "play":
        icon.add('<path d="M57 59 Q57 55 60.5 57 L80 69 Q83 71 80 73 L60.5 85 Q57 87 57 83 Z" fill="#000000" opacity="0.22" transform="translate(0 1.6)"/>')
        icon.add('<path d="M57 59 Q57 55 60.5 57 L80 69 Q83 71 80 73 L60.5 85 Q57 87 57 83 Z" fill="#ffffff"/>')
    elif mark:
        line_mark(icon, mark, color=ink, width=6.5, shadow=ink == "#ffffff")
    return icon.svg()


def settings_icon():
    icon = Icon("Monet icon: Settings. Three thick brushstrokes in dawn, midday and dusk, with white knobs.")
    for y, x, top, bottom in ((34, 40, "#F6B590", "#D2603F"), (64, 86, "#93C6EA", "#356FA8"), (94, 54, "#C0AEEE", "#5A4A9C")):
        dab(icon, 64, y + 1.8, 104, 26, "#000000", opacity=0.14, shine=False)
        dab(icon, 64, y, 104, 26, icon.gradient(top, bottom), bend=0.12)
        icon.add(f'<circle cx="{x}" cy="{y + 1.8}" r="15" fill="#000000" opacity="0.22"/>')
        icon.add(f'<circle cx="{x}" cy="{y}" r="15" fill="#FFFFFF"/>')
        icon.add(f'<circle cx="{x}" cy="{y}" r="6" fill="{bottom}" opacity="0.85"/>')
    return icon.svg()


def terminal_icon():
    icon = Icon("Monet icon: Terminal. A night canvas with a prompt.")
    night = icon.gradient("#3A4775", "#141B2E", 0.2, 0, 0.8, 1)
    icon.defs.append(f'<clipPath id="canvas"><path d="{rounded(12, 18, 116, 110, 18)}"/></clipPath>')
    icon.add(f'<path d="{rounded(12, 18, 116, 110, 18)}" fill="{night}"/>')
    strokes = "".join(
        f'<path d="{path(dab_points(cx, cy, length, 7, a, 0.3))}" fill="#9FB4E8" opacity="{o}"/>'
        for cx, cy, length, a, o in ((46, 34, 60, -3, 0.16), (90, 46, 44, 2, 0.12), (40, 100, 56, 2, 0.12), (92, 96, 40, -2, 0.1)))
    icon.add('<g clip-path="url(#canvas)">' + strokes + "</g>")
    icon.add('<path d="M23 19.5 H105" stroke="#ffffff" stroke-opacity="0.35" stroke-width="1.6" stroke-linecap="round"/>')
    line_mark(icon, "M36 50 L52 64 L36 78", color="#F3ECD8", width=8.5, shadow=False)
    dab(icon, 76, 80, 30, 9, "#7CD3C0", shine=False)
    return icon.svg()


def store_icon():
    icon = Icon("Monet icon: Store. A painted bag.")
    body = icon.gradient("#C9B9F2", "#5A4A9C", 0.2, 0, 0.8, 1)
    icon.add('<path d="M28 46 Q29 40 35 40 H93 Q99 40 100 46 L106 102 Q107 112 97 112 H31 Q21 112 22 102 Z" fill="#000000" opacity="0.16" transform="translate(0 2)"/>')
    icon.add(f'<path d="M28 46 Q29 40 35 40 H93 Q99 40 100 46 L106 102 Q107 112 97 112 H31 Q21 112 22 102 Z" fill="{body}"/>')
    for cx, cy, length, o in ((54, 62, 46, 0.26), (78, 84, 40, 0.18)):
        icon.add(f'<path d="{path(dab_points(cx, cy, length, 7, -20, 0.3))}" fill="#ffffff" opacity="{o}"/>')
    icon.add('<path d="M47 50 V40 A17 17 0 0 1 81 40 V50" fill="none" stroke="#3E3175" stroke-width="8" stroke-linecap="round"/>')
    icon.fit(64, 68, 1.16)
    return icon.svg()


def monitor_icon():
    icon = Icon("Monet icon: System Monitor. Four painted bars, rising.")
    for x, length, top, bottom in ((24, 50, "#7CD3C0", "#2E7D70"), (50, 80, "#93C6EA", "#356FA8"),
                                   (76, 62, "#C0AEEE", "#5A4A9C"), (102, 96, "#F6B590", "#D2603F")):
        cy = 108 - length / 2
        dab(icon, x + 1.6, cy + 1.6, length, 25, "#000000", angle=90, opacity=0.14, shine=False)
        dab(icon, x, cy, length, 25, icon.gradient(top, bottom), angle=90)
    dab(icon, 63, 114, 110, 7, "#8C867C", shine=False)
    return icon.svg()


def trash_icon(full):
    icon = Icon("Monet icon: Trash" + (", with something in it" if full else "") + ". A woven basket.")
    body = icon.gradient("#D9D1C3", "#8C867C", 0.2, 0, 0.8, 1)
    icon.add('<path d="M30 44 H98 L91 108 Q90 114 84 114 H44 Q38 114 37 108 Z" fill="#000000" opacity="0.16" transform="translate(0 2)"/>')
    icon.add(f'<path d="M30 44 H98 L91 108 Q90 114 84 114 H44 Q38 114 37 108 Z" fill="{body}"/>')
    for x, top in ((50, 52), (64, 52), (78, 52)):
        dab(icon, x, 82, 50, 6, "#6C665D", angle=90, opacity=0.45, shine=False)
    if full:
        # A sheet of paper sticking out under the lid.
        icon.add('<g transform="rotate(-12 66 40)"><rect x="50" y="26" width="34" height="34" rx="4" fill="#FBF7EE"/>'
                 '<path d="M56 34 H78 M56 41 H72" stroke="#C9BFAC" stroke-width="3" stroke-linecap="round"/></g>')
    lid = icon.gradient("#8C867C", "#5A554D")
    dab(icon, 64, 42 if not full else 41, 84, 11, lid, angle=0 if not full else -4)
    # The same place and size whether it's empty or full, so it doesn't jump.
    icon.fit(64, 76, 1.2)
    return icon.svg()


ICONS = {
    "files": (lambda: folder_icon("folder", *FOLDERS["folder"]), ["apps/system-file-manager", "apps/org.kde.dolphin"]),
    "settings": (settings_icon, ["apps/preferences-system", "apps/systemsettings", "apps/monet-settings"]),
    "terminal": (terminal_icon, ["apps/utilities-terminal", "apps/org.kde.konsole"]),
    "store": (store_icon, ["apps/plasmadiscover", "apps/org.kde.discover"]),
    "monitor": (monitor_icon, ["apps/utilities-system-monitor", "apps/org.kde.plasma-systemmonitor"]),
    "trash": (lambda: trash_icon(False), ["places/user-trash"]),
    "trash-full": (lambda: trash_icon(True), ["places/user-trash-full"]),
}
for name, spec in FOLDERS.items():
    ICONS[name] = ((lambda n=name, s=spec: folder_icon(n, *s)), [f"places/{name}"])


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


def main():
    settings_art()
    TEXTURES.mkdir(parents=True, exist_ok=True)
    brush_texture(TEXTURES / "brush.png")
    for old in THEME.glob("*/scalable/*.svg"):
        old.unlink()
    for name, (draw, files) in ICONS.items():
        svg = draw()
        for f in files:
            context, ident = f.split("/")
            out = THEME / context / "scalable" / f"{ident}.svg"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(svg)
    (THEME / "index.theme").write_text("""[Icon Theme]
Name=Monet
Comment=Painted marks for Monet's own apps, painted folders, Breeze for everything else
Inherits=breeze,hicolor
Example=folder
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
    print("wrote", THEME.relative_to(ROOT), "and", (TEXTURES / "brush.png").relative_to(ROOT))


if __name__ == "__main__":
    main()
