"""Writes the pictures Zen wears Monet's look with (linux/share/monet/zen).

Zen, the browser, gets Monet's look from zen.css (its window) and newtab.css
(its new tabs), which monet-quick zen puts into each Zen profile. This makes
the pictures they show: behind the window's glass, a painting blurred and
washed in paper or smoke, the way Monet's glass shows the desktop; on a new
tab, the painting itself. A daylight one for Mist and a night one for Smoke,
as the Store's banners are.

Run from the repository root:  python3 tools/make-zen.py
"""

from pathlib import Path

from PIL import Image, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
HOURS = ROOT / "linux" / "share" / "wallpapers" / "Monet" / "contents" / "hours"
OUT = ROOT / "linux" / "share" / "monet" / "zen"
LIGHTS = {"mist": ("day", (243, 241, 236), 0.34), "smoke": ("night", (36, 35, 33), 0.4)}  # painting, wash, how much


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for light, (name, wash, amount) in LIGHTS.items():
        painting = Image.open(HOURS / f"{name}.jpg").convert("RGB")
        # The window's ground: soft enough that the tabs read on it. Small, since it's only color.
        ground = painting.resize((960, 540), Image.LANCZOS).filter(ImageFilter.GaussianBlur(12))
        Image.blend(ground, Image.new("RGB", ground.size, wash), amount).save(OUT / f"{light}.jpg", quality=86)
        # A new tab: the painting, at the size most screens show it.
        painting.resize((1920, 1080), Image.LANCZOS).save(OUT / f"newtab-{light}.jpg", quality=78, optimize=True,
                                                          progressive=True)
        print("wrote", light)


if __name__ == "__main__":
    main()
