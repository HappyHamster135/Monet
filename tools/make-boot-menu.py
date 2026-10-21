#!/usr/bin/env python3
"""Art and fonts for the USB stick's start menu (a GRUB theme).

    python3 tools/make-boot-menu.py        needs grub-mkfont (grub-common / grub2-tools-extra)

Writes image/installer/grub/: the dawn painting behind the menu, Monet's mark,
a smoked-glass panel and a paper pill for the chosen line (as GRUB's
nine-piece pixmaps), and the fonts, converted to GRUB's .pf2 format. The
layout itself is image/installer/grub/theme.txt.
"""

import importlib.util
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "image" / "installer" / "grub"
HOURS = ROOT / "linux" / "share" / "wallpapers" / "Monet" / "contents" / "hours"
FONTS = ROOT / "image" / "installer" / "product" / "usr" / "share" / "fonts" / "monet"

# Latin letters, arrows and the middle dot: enough for the menu, and small.
RANGE = "0x20-0x7E,0xA0-0x17F,0x2190-0x2193,0x2022-0x2022"


def branding():
    spec = importlib.util.spec_from_file_location("make_branding", ROOT / "tools" / "make-branding.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def background():
    """The harbor at dawn, a little darker and softer, so white words read."""
    img = Image.open(HOURS / "dawn.jpg").convert("RGB").resize((1920, 1080), Image.LANCZOS)
    img = img.filter(ImageFilter.GaussianBlur(1.5))
    arr = np.asarray(img).astype(np.float32)
    # Darker toward the left, where the menu is.
    x = np.linspace(0, 1, 1920)[None, :, None]
    shade = 0.52 + 0.30 * np.clip((x - 0.15) / 0.6, 0, 1)
    arr = np.clip(arr * shade, 0, 255).astype(np.uint8)
    Image.fromarray(arr).quantize(colors=256, method=Image.Quantize.MEDIANCUT).save(OUT / "background.png", optimize=True)


def nine(prefix, w, h, radius, fill):
    """GRUB's nine-piece box: corners, edges and a centre, from one rounded box."""
    scale = 4
    big = Image.new("RGBA", (w * scale, h * scale), (0, 0, 0, 0))
    ImageDraw.Draw(big).rounded_rectangle([0, 0, w * scale - 1, h * scale - 1], radius * scale, fill=fill)
    box = big.resize((w, h), Image.LANCZOS)
    r = radius
    pieces = {
        "nw": (0, 0, r, r), "n": (r, 0, r + 1, r), "ne": (w - r, 0, w, r),
        "w": (0, r, r, r + 1), "c": (r, r, r + 1, r + 1), "e": (w - r, r, w, r + 1),
        "sw": (0, h - r, r, h), "s": (r, h - r, r + 1, h), "se": (w - r, h - r, w, h),
    }
    for name, crop in pieces.items():
        box.crop(crop).save(OUT / f"{prefix}_{name}.png", optimize=True)


def fonts():
    """Inter for the menu and Fraunces for the name, as GRUB fonts. Each gets
    its own family name (Inter's weights all call themselves "Inter
    Regular"), which is how theme.txt asks for them: "Monet Text Regular 20"."""
    for name, family, size, source in (
        ("text-14", "Monet Text", 14, FONTS / "Inter-Regular.otf"),
        ("text-20", "Monet Text", 20, FONTS / "Inter-Regular.otf"),
        ("strong-20", "Monet Strong", 20, FONTS / "Inter-SemiBold.otf"),
        ("title-56", "Monet Title", 56, FONTS / "Fraunces72ptSuperSoft-Light.ttf"),
    ):
        subprocess.run(["grub-mkfont", "-n", family, "-s", str(size), "-r", RANGE, "-o", str(OUT / f"{name}.pf2"),
                        str(source)], check=True, stderr=subprocess.DEVNULL)


def pf2_name(path):
    """The name a .pf2 font goes by in a theme ("Inter Regular 20")."""
    data = path.read_bytes()
    i = data.index(b"NAME")
    n = int.from_bytes(data[i + 4:i + 8], "big")
    return data[i + 8:i + 8 + n].rstrip(b"\0").decode()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    background()
    mark = branding().raster(branding().sun_outline(), 64)
    mark.save(OUT / "mark.png", optimize=True)
    nine("menu", 120, 120, 22, (20, 22, 36, 150))
    nine("select", 60, 60, 14, (251, 250, 247, 246))
    fonts()
    for f in sorted(OUT.glob("*.pf2")):
        print(f"{f.name}: {pf2_name(f)}")
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
