"""Package selected details from Claude Monet's actual paintings for the Store.

Museum reproductions, provenance and deliberate crops live in branding/store.
Mist and Smoke share the art; the surrounding paper, glass and caption follow the
user's appearance preference. Keep both filenames for Bazaar's curated page too.

Run from the repository root: python3 tools/make-store.py
"""

import json
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PAINTINGS = ROOT / "branding" / "store"
OUT = ROOT / "linux" / "share" / "monet" / "store"

# Each room uses a detail from Monet's own work, associated with its mood/activity.
PAINTING_FOR = {
    "play": "play", "talk": "talk", "watch": "watch", "work": "work",
    "everyday": "everyday",
    "games": "play", "graphics": "work", "media": "watch", "office": "parliament",
    "internet": "talk", "learning": "cathedral", "developer": "waterloo",
    "tools": "everyday", "installed": "vetheuil", "windows": "venice",
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = json.loads((PAINTINGS / "sources.json").read_text(encoding="utf-8"))
    credits = ["Claude Monet â€” Store paintings", "", catalog["credit"],
               "Museum reproductions released under CC0-1.0.", catalog["license_url"],
               "", "Banners show selected details. Colors and brushwork are unchanged.",
               "Full reproductions and crop coordinates: branding/store in the source tree.", ""]
    paintings = {}
    for name, entry in catalog["paintings"].items():
        with Image.open(PAINTINGS / entry["file"]) as source:
            left, top, right, bottom = entry["crop"]
            if not (0 <= left < right <= source.width and 0 <= top < bottom <= source.height):
                raise ValueError(f"{name}: crop outside its museum reproduction")
            detail = source.crop(entry["crop"]).convert("RGB")
            if detail.size != tuple(catalog["size"]):
                raise ValueError(f"{name}: crop must match the banner size without distortion")
            # Preserve the museum reproduction's color profile through both exports.
            profile = source.info.get("icc_profile", b"")
            detail.save(PAINTINGS / f"{name}.png", icc_profile=profile)
            paintings[name] = (detail, profile)
        credits.extend([f"{name}: {entry['title']}, {entry['date']} (detail)",
                        f"Claude Monet; {catalog['museum']}; {entry['accession']}",
                        entry["page"], ""])
    for name, painting in PAINTING_FOR.items():
        image, profile = paintings[painting]
        for light in ("mist", "smoke"):
            path = OUT / f"{name}-{light}.jpg"
            image.save(path, quality=92, optimize=True, progressive=True, icc_profile=profile)
            print("wrote", path.relative_to(ROOT))
    (OUT / "ARTWORK-CREDITS.txt").write_text("\n".join(credits), encoding="utf-8")


if __name__ == "__main__":
    main()
