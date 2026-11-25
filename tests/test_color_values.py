"""Round-trip color formats copied by the Command Bar and the screen picker."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "linux/share/monet/utilities"))
from color_values import conversion


class ColorConversions(unittest.TestCase):
    def test_examples(self):
        for query, answer in (
            ("#369 to rgb", "rgb(51, 102, 153)"),
            ("#3698 till hex", "#33669988"),
            ("#01020300 → hsla", "hsla(210, 50%, 0.7843%, 0)"),
            ("#fff as rgba", "rgba(255, 255, 255, 1)"),
            ("Color(red: 0.2, green: 0.4, blue: 0.6) in hex", "#336699"),
            ("RgB(100% 0% 0% / 50%) to hex", "#FF000080"),
            ("hsl(-.5turn 100% 50% / 25%) to swift", "Color(red: 0, green: 1, blue: 1, opacity: 0.25)"),
            ("hsla(120, 100%, 25%, .5) to rgba", "rgba(0, 128, 0, 0.5)"),
        ):
            with self.subTest(query=query):
                self.assertEqual(conversion(query)[1], answer)

    def test_every_byte_of_alpha_survives_conversion_back_to_hex(self):
        for form in ("rgb", "hsl", "swiftui"):
            for alpha in range(256):
                original = f"#B2A0CD{alpha:02X}" if alpha < 255 else "#B2A0CD"
                display = conversion(f"{original} to {form}")[1]
                self.assertEqual(conversion(f"{display} to hex")[1], original)

    def test_other_searches_and_invalid_components(self):
        for query in ("#123", "369 to hex", "a 200 page book", "cat #369 to rgb", "#12345 to rgb",
                      "#fff to paint", "rgb(300, 1, 1) to hex", "hsl(10 4% 5) to hex",
                      "rgba(1,2,3,2) to hex", "rgb(1 2 3 /) to hex", "rgba(1,2,3,.1,.2) to hex",
                      "Color(red: nan, green: 0, blue: 0) to hex", "#fff" + " " * 200 + "to rgb"):
            with self.subTest(query=query):
                self.assertIsNone(conversion(query))
