"""Draws Monet's marks and the installer artwork.

The mark is the sun over water from "Impression, soleil levant": a disc and
three brushstrokes of its reflection. "Play on Windows" is the same mark with
the sun turned into a play button.

Run from the repository root, after tools/make-paintings.py:
    python3 tools/make-branding.py
Needs Pillow and NumPy.
"""

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "branding"
HOURS = ROOT / "linux" / "share" / "wallpapers" / "Monet" / "contents" / "hours"
FONTS = ROOT / "linux" / "share" / "fonts" / "monet"
INSTALLER = ROOT / "image" / "installer" / "product" / "usr" / "share" / "anaconda" / "pixmaps"

SUN = "#F2552C"
# Reflection strokes: center x, center y, length, thickness, opacity (128-unit grid).
DABS = [(64, 85, 76, 10, 0.9), (61, 99, 54, 8, 0.66), (66, 111, 30, 6.5, 0.42)]


def stroke(cx, cy, length, width, steps=24):
    """A brushstroke: rounded ends, a little heavier where the brush landed."""
    top, bottom = [], []
    for i in range(steps + 1):
        t = -1 + 2 * i / steps
        half = width / 2 * max(0.0, 1 - abs(t) ** 2.4) ** (1 / 2.4) * (1 - 0.18 * t)
        x = cx + t * length / 2
        bend = (1 - t * t) * 1.2
        top.append((x, cy - half + bend))
        bottom.append((x, cy + half + bend))
    return top + bottom[::-1]


def sun_outline(cx=64, cy=44, r=27, steps=96):
    """The disc, its edge a touch uneven like a painted one."""
    pts = []
    for i in range(steps):
        a = 2 * math.pi * i / steps
        rr = r * (1 + 0.006 * math.sin(3 * a + 0.4) + 0.004 * math.sin(7 * a + 1.3))
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    return pts


def play_outline(corner=10.0, steps=12):
    """A play triangle with rounded corners, sitting where the sun would."""
    tri = [(45.0, 16.0), (45.0, 72.0), (92.0, 44.0)]
    pts = []
    n = len(tri)
    for i in range(n):
        px, py = tri[i - 1]
        vx, vy = tri[i]
        nx, ny = tri[(i + 1) % n]
        # Cut the corner: a curve from a point on the incoming edge to one on
        # the outgoing edge, pulled toward the corner itself.
        dp = math.hypot(px - vx, py - vy)
        dn = math.hypot(nx - vx, ny - vy)
        ax, ay = vx + (px - vx) / dp * corner, vy + (py - vy) / dp * corner
        bx, by = vx + (nx - vx) / dn * corner, vy + (ny - vy) / dn * corner
        for k in range(steps + 1):
            u = k / steps
            pts.append(((1 - u) ** 2 * ax + 2 * (1 - u) * u * vx + u * u * bx,
                        (1 - u) ** 2 * ay + 2 * (1 - u) * u * vy + u * u * by))
    return pts


def path(points):
    return "M" + " L".join(f"{x:.2f},{y:.2f}" for x, y in points) + " Z"


def svg(head, comment):
    dabs = "\n".join(
        f'  <path d="{path(stroke(x, y, l, w))}" fill="{SUN}" opacity="{o}"/>' for x, y, l, w, o in DABS
    )
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">
  <!-- {comment} -->
  <defs>
    <radialGradient id="light" cx="0.4" cy="0.32" r="0.75">
      <stop offset="0" stop-color="#FF8456"/>
      <stop offset="0.55" stop-color="{SUN}"/>
      <stop offset="1" stop-color="#D93E1B"/>
    </radialGradient>
  </defs>
  <path d="{path(head)}" fill="url(#light)"/>
{dabs}
</svg>
"""


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def raster(head, size):
    """The mark as a transparent PNG, drawn large and scaled down for smooth edges."""
    big = size * 4
    k = big / 128
    img = Image.new("RGBA", (big, big), (0, 0, 0, 0))

    # The sun's light: a radial gradient clipped to the disc.
    yy, xx = np.mgrid[0:big, 0:big].astype(np.float32) / k
    d = np.clip(np.hypot(xx - 0.4 * 128 * 0.5 - 38, yy - 0.32 * 128 * 0.5 - 26) / 60, 0, 1)
    stops = [(0, rgb("#FF8456")), (0.55, rgb(SUN)), (1, rgb("#D93E1B"))]
    col = np.stack([np.interp(d, [s for s, _ in stops], [c[i] for _, c in stops]) for i in range(3)], axis=-1)
    mask = Image.new("L", (big, big), 0)
    ImageDraw.Draw(mask).polygon([(x * k, y * k) for x, y in head], fill=255)
    disc = Image.fromarray(col.astype(np.uint8)).convert("RGBA")
    disc.putalpha(mask)
    img = Image.alpha_composite(img, disc)

    for x, y, l, w, o in DABS:
        layer = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        ImageDraw.Draw(layer).polygon([(px * k, py * k) for px, py in stroke(x, y, l, w)], fill=rgb(SUN) + (int(o * 255),))
        img = Image.alpha_composite(img, layer)
    return img.resize((size, size), Image.LANCZOS)


def installer_art():
    """Artwork for Monet's installer (replaces Fedora's in Anaconda)."""
    INSTALLER.mkdir(parents=True, exist_ok=True)
    dawn = Image.open(HOURS / "dawn.jpg").convert("RGB")
    W, H = dawn.size

    # Sidebar: a tall slice of the dawn painting through the sun and its reflection.
    sun_x = int(W * 0.62)
    width = H * 500 // 1600
    dawn.crop((sun_x - width // 2, 0, sun_x + width // 2, H)).resize((500, 1600), Image.LANCZOS) \
        .save(INSTALLER / "sidebar-bg.png", optimize=True)

    # Logo: the mark with "Monet" set in Fraunces beneath it, on transparent.
    # Drawn at twice the size it's shown (monet.css scales it to 128 x 104),
    # so it stays sharp on high-resolution screens and fits the narrow side.
    mark = raster(sun_outline(), 132)
    canvas = Image.new("RGBA", (256, 208), (0, 0, 0, 0))
    canvas.alpha_composite(mark, ((256 - 132) // 2, 0))
    draw = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(str(FONTS / "Fraunces72ptSuperSoft-Light.ttf"), 60)
    text_w = draw.textlength("Monet", font=font)
    draw.text(((256 - text_w) / 2, 128), "Monet", font=font, fill=(255, 255, 255, 255))
    canvas.save(INSTALLER / "sidebar-logo.png", optimize=True)

    # The welcome and progress pages: the harbor at dawn along the bottom,
    # rising out of the page's paper.
    w, h = 1600, 520
    strip = dawn.crop((0, int(H * 0.40), W, int(H * 0.40) + W * h // w)).resize((w, h), Image.LANCZOS).convert("RGBA")
    fade = np.clip((np.arange(h, dtype=np.float32) / h - 0.05) / 0.55, 0, 1) ** 1.6
    alpha = Image.fromarray(np.repeat((fade * 255).astype(np.uint8)[:, None], w, axis=1), "L")
    strip.putalpha(alpha)
    strip.save(INSTALLER / "monet-page.png", optimize=True)


def main():
    (OUT / "monet.svg").write_text(svg(sun_outline(), 'Monet: the sun over water, after "Impression, soleil levant" (1872).'))
    (OUT / "monet-windows.svg").write_text(svg(play_outline(), "Play on Windows: Monet's sun, turned into a play button."))
    print("wrote branding/monet.svg, branding/monet-windows.svg")

    big = raster(sun_outline(), 512)
    big.save(OUT / "monet-512.png")
    raster(play_outline(), 512).save(OUT / "monet-windows-512.png")
    big.save(ROOT / "windows" / "monet.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print("wrote branding/monet-512.png, windows/monet.ico")

    installer_art()
    print("wrote image/installer/product/usr/share/anaconda/pixmaps")

    Image.open(HOURS / "dawn.jpg").convert("RGB").resize((1280, 720), Image.LANCZOS) \
        .save(OUT / "wallpaper-preview.jpg", quality=86)
    print("wrote branding/wallpaper-preview.jpg")


if __name__ == "__main__":
    main()
