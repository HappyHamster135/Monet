"""Shadow edge tiles must repeat without scallops or seams in either state."""
import base64
import importlib.util
import io
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
NS = "{http://www.w3.org/2000/svg}"


class WindowShadows(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("decoration", ROOT / "tools/make-decoration.py")
        cls.generator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.generator)
        cls.source = (ROOT / "linux/share/aurorae/themes/MonetBare/decoration.svg").read_text()
        cls.svg = ET.fromstring(cls.source)

    def tile(self, prefix, part):
        group = next(child for child in self.svg if child.get("id") == prefix + "-" + part)
        image = group.find(NS + "image")
        return np.asarray(Image.open(io.BytesIO(base64.b64decode(
            image.get("{http://www.w3.org/1999/xlink}href").partition(",")[2]))))[:, :, 3].astype(int)

    def test_generated_asset_matches_source(self):
        self.assertEqual(self.source, self.generator.bare_svg())

    def test_straight_edges_have_no_repeating_falloff(self):
        for prefix in ("decoration", "decoration-inactive"):
            for part in ("top", "bottom", "left", "right"):
                with self.subTest(prefix=prefix, part=part):
                    tile = self.tile(prefix, part)
                    axis = 1 if part in ("top", "bottom") else 0
                    self.assertEqual(int(np.ptp(tile, axis=axis).max()), 0)
                    self.assertGreater(int(tile.max()), 0)

    def test_corner_and_edge_tiles_meet_without_opacity_jumps(self):
        for prefix in ("decoration", "decoration-inactive"):
            for corner, horizontal, vertical, x, y in (
                ("topleft", "top", "left", -1, -1),
                ("topright", "top", "right", 0, -1),
                ("bottomleft", "bottom", "left", -1, 0),
                ("bottomright", "bottom", "right", 0, 0)):
                with self.subTest(prefix=prefix, corner=corner):
                    tile = self.tile(prefix, corner)
                    self.assertLessEqual(int(np.abs(tile[:, x]-self.tile(prefix, horizontal)[:, 0]).max()), 1)
                    self.assertLessEqual(int(np.abs(tile[y, :]-self.tile(prefix, vertical)[0, :]).max()), 1)

    def test_no_shadow_is_painted_under_the_client_window(self):
        g = self.generator
        for active in (False, True):
            shadow = np.asarray(g.shadow_image(active, 0, 0, 0, g.BARE_SHADOW_INSET))
            center = shadow[g.TOP*g.K:-g.BOTTOM*g.K, g.SIDE*g.K:-g.SIDE*g.K, 3]
            self.assertEqual(int(center.max()), 0)
