"""Writes the Store's front page: Monet's picks under banners cut from The Hours.

The Store (Bazaar) shows a page of picked apps, each row under a banner. Each
banner is a strip of one of the four paintings: a daylight one for Mist and a
night one for Smoke (Bazaar switches with the light), so the page looks like
the desktop it opens on.

Run from the repository root:  python3 tools/make-store.py
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
HOURS = ROOT / "linux" / "share" / "wallpapers" / "Monet" / "contents" / "hours"
OUT = ROOT / "linux" / "share" / "monet" / "store"
SIZE = (2400, 600)  # Bazaar draws banners 300 points tall, cropped to the window

# Each strip: painting, its left and right edge, and its top (fractions); 4:1.
STRIPS = {
    "play-mist": ("day", 0.30, 1.00, 0.445),
    "play-smoke": ("night", 0.10, 1.00, 0.17),
    "talk-mist": ("dawn", 0.20, 1.00, 0.24),
    "talk-smoke": ("dusk", 0.00, 0.80, 0.30),
    "watch-mist": ("day", 0.00, 0.60, 0.40),
    "watch-smoke": ("night", 0.00, 0.70, 0.36),
    "work-mist": ("dawn", 0.00, 0.55, 0.58),
    "work-smoke": ("dusk", 0.00, 0.55, 0.58),
    "everyday-mist": ("day", 0.45, 1.00, 0.32),
    "everyday-smoke": ("night", 0.45, 1.00, 0.32),
}


def strip(painting, left, right, top):
    image = Image.open(HOURS / f"{painting}.jpg").convert("RGB")
    w, h = image.size
    x0, x1 = round(left * w), round(right * w)
    y0 = round(top * h)
    y1 = y0 + round((x1 - x0) * SIZE[1] / SIZE[0])
    assert y1 <= h, painting
    return image.crop((x0, y0, x1, y1)).resize(SIZE, Image.LANCZOS)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, spec in STRIPS.items():
        strip(*spec).save(OUT / f"{name}.jpg", quality=82, optimize=True, progressive=True)
        print("wrote", (OUT / f"{name}.jpg").relative_to(ROOT))


if __name__ == "__main__":
    main()
