#!/usr/bin/env python3
"""Art for Monet Setup, the installer on the USB stick.

    python3 tools/make-setup-art.py

Writes setup/art/: the dawn painting behind everything, the same painting
blurred for the glass sheet (drawn in advance, so the installer needs no
graphics card for its glass), the sheet's shadow and Monet's marks; and the
start-up splash's pictures in image/setup/files.
"""

import importlib.util
from pathlib import Path

from PIL import Image, ImageEnhance, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "setup" / "art"
HOURS = ROOT / "linux" / "share" / "wallpapers" / "Monet" / "contents" / "hours"
PLYMOUTH = ROOT / "image" / "setup" / "files" / "usr" / "share" / "plymouth" / "themes" / "monet"


def branding():
    spec = importlib.util.spec_from_file_location("make_branding", ROOT / "tools" / "make-branding.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def shadow():
    """The sheet's shadow as a nine-piece image: a rounded box, blurred and
    dropped. Qt stretches the middle; the corners stay as drawn."""
    from PIL import ImageDraw
    m, box, r = 120, 200, 32
    size = box + 2 * m
    img = Image.new("RGBA", (size, size), (24, 30, 52, 0))
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([m, m + 30, m + box, m + box + 30], r, fill=int(255 * 0.42))
    img.putalpha(mask.filter(ImageFilter.GaussianBlur(36)))
    img.save(OUT / "shadow.png", optimize=True)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    dawn = Image.open(HOURS / "dawn.jpg").convert("RGB").resize((2560, 1440), Image.LANCZOS)
    dawn.save(OUT / "painting.jpg", quality=88, optimize=True, progressive=True)
    # The glass: heavily blurred (at a quarter size, then back up: smoother and
    # faster), a touch brighter and softer in color, like frosted glass.
    small = dawn.resize((640, 360), Image.LANCZOS).filter(ImageFilter.GaussianBlur(14))
    glass = small.resize((2560, 1440), Image.BICUBIC).filter(ImageFilter.GaussianBlur(6))
    glass = ImageEnhance.Color(glass).enhance(0.85)
    glass.save(OUT / "glass.jpg", quality=85, optimize=True, progressive=True)
    shadow()
    b = branding()
    b.raster(b.sun_outline(), 160).save(OUT / "mark.png", optimize=True)
    # The start-up splash (Plymouth): the painting, small enough for the
    # initramfs, and the mark.
    PLYMOUTH.mkdir(parents=True, exist_ok=True)
    dawn.resize((1600, 900), Image.LANCZOS).quantize(colors=256, method=Image.Quantize.MEDIANCUT) \
        .save(PLYMOUTH / "painting.png", optimize=True)
    b.raster(b.sun_outline(), 96).save(PLYMOUTH / "mark.png", optimize=True)
    b.raster(b.play_outline(), 160).save(OUT / "windows.png", optimize=True)
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
