"""Checks for Monet's look: the Plasma pieces, the app style and the paintings.

    python3 -m unittest discover -s tests
"""

import configparser
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SHARE = ROOT / "linux" / "share"
PLASMA = SHARE / "plasma"


def element_ids(svg):
    return set(re.findall(r'id="([^"]+)"', svg))


def element_body(svg, ident):
    match = re.search(r'<g id="%s">(.*?)</g>' % re.escape(ident), svg, re.S)
    return match.group(1) if match else ""


class PlasmaPackages(unittest.TestCase):
    def packages(self):
        for kind in ("plasmoids", "wallpapers", "look-and-feel", "desktoptheme"):
            for folder in sorted((PLASMA / kind).iterdir()):
                yield kind, folder

    def test_ids_match_folders(self):
        for kind, folder in self.packages():
            meta = json.loads((folder / "metadata.json").read_text())
            self.assertEqual(meta["KPlugin"]["Id"], folder.name, folder)

    def test_widgets_have_their_ui(self):
        for kind, folder in self.packages():
            if kind in ("plasmoids", "wallpapers"):
                self.assertTrue((folder / "contents/ui/main.qml").is_file(), folder)

    def test_layout_uses_monet_pieces_that_exist(self):
        layout = (PLASMA / "look-and-feel/org.monet.desktop/contents/layouts/org.kde.plasma.desktop-layout.js").read_text()
        for widget in re.findall(r'"(org\.monet\.[a-z]+)"', layout):
            kind = "wallpapers" if widget == "org.monet.hours" else "plasmoids"
            self.assertTrue((PLASMA / kind / widget).is_dir(), widget)
        # Three islands along the bottom.
        self.assertEqual(layout.count('island("'), 3)

    def test_theme_defaults_point_at_monet(self):
        defaults = (PLASMA / "look-and-feel/org.monet.desktop/contents/defaults").read_text()
        self.assertIn("name=monet", defaults)
        self.assertIn("Theme=Monet", defaults)
        self.assertIn("ColorScheme=MonetLight", defaults)
        self.assertTrue((SHARE / "icons/Monet/index.theme").is_file())

    def test_inline_components_do_not_reach_outside(self):
        # QML inline components can't see the ids of the file around them.
        for qml in PLASMA.rglob("*.qml"):
            text = qml.read_text()
            for match in re.finditer(r"\n([ \t]*)component (\w+): ", text):
                indent = match.group(1)
                end = text.find("\n" + indent + "}", match.end())
                body = text[match.end():end]
                self.assertNotIn("root.", body, f"{qml.parent.parent.parent.name}: component {match.group(2)}")

    def test_qml_avoids_reserved_names(self):
        for qml in PLASMA.rglob("*.qml"):
            text = qml.read_text()
            self.assertNotRegex(text, r"property \w+ (state|on)\b", qml.name)


class PlasmaStyle(unittest.TestCase):
    STYLE = PLASMA / "desktoptheme/monet"
    PIECES = ["topleft", "top", "topright", "left", "center", "right", "bottomleft", "bottom", "bottomright"]

    def test_frames_are_complete(self):
        for name in ("dialogs/background", "widgets/panel-background", "widgets/tooltip"):
            for folder in ("", "translucent/"):
                svg = (self.STYLE / f"{folder}{name}.svg").read_text()
                ids = element_ids(svg)
                for prefix in ("", "mask-", "shadow-"):
                    for piece in self.PIECES:
                        self.assertIn(prefix + piece, ids, f"{name}: {prefix}{piece}")
                for side in ("top", "bottom", "left", "right"):
                    self.assertIn(f"hint-{side}-margin", ids)
                    self.assertIn(f"shadow-hint-{side}-margin", ids)
                self.assertIn('id="current-color-scheme"', svg)

    def test_frames_have_no_strokes(self):
        # Qt counts a stroke's width in an element's size, which shifts pieces.
        for svg in self.STYLE.rglob("*.svg"):
            self.assertNotIn("stroke", svg.read_text(), svg)


class AppStyle(unittest.TestCase):
    KVANTUM = SHARE / "Kvantum"

    def sections(self, path):
        parser = configparser.RawConfigParser(strict=False)
        parser.optionxform = str
        parser.read_string(path.read_text())
        return parser

    def resolved(self, conf, section, key):
        seen = set()
        while section and section not in seen:
            seen.add(section)
            if key in conf[section]:
                return conf[section][key]
            section = conf[section].get("inherits")
        return None

    def test_every_used_element_is_drawn(self):
        for theme in ("Monet", "MonetDark"):
            conf = self.sections(self.KVANTUM / theme / f"{theme}.kvconfig")
            ids = element_ids((self.KVANTUM / theme / f"{theme}.svg").read_text())
            for section in conf.sections():
                if section.startswith("%") or section in ("GeneralColors", "Hacks"):
                    continue
                if self.resolved(conf, section, "frame") == "true":
                    element = self.resolved(conf, section, "frame.element")
                    self.assertIn(f"{element}-normal-top", ids, f"{theme} [{section}] frame {element}")
                if self.resolved(conf, section, "interior") == "true":
                    element = self.resolved(conf, section, "interior.element")
                    self.assertIn(f"{element}-normal", ids, f"{theme} [{section}] interior {element}")

    def test_windows_are_see_through(self):
        for theme in ("Monet", "MonetDark"):
            conf = self.sections(self.KVANTUM / theme / f"{theme}.kvconfig")
            self.assertEqual(conf["%General"]["translucent_windows"], "true")
            self.assertEqual(conf["%General"]["blurring"], "true")
            self.assertEqual(conf["Hacks"]["transparent_dolphin_view"], "true")

    def test_frame_pieces_have_no_strokes(self):
        for theme in ("Monet", "MonetDark"):
            svg = (self.KVANTUM / theme / f"{theme}.svg").read_text()
            for ident in element_ids(svg):
                if re.search(r"-(top|bottom|left|right|topleft|topright|bottomleft|bottomright)$", ident):
                    self.assertNotIn("stroke", element_body(svg, ident), ident)


class Colors(unittest.TestCase):
    def test_schemes(self):
        for name in ("MonetLight", "MonetDark"):
            conf = configparser.RawConfigParser(strict=False)
            conf.optionxform = str
            conf.read_string((SHARE / "color-schemes" / f"{name}.colors").read_text())
            for group in ("Colors:Window", "Colors:View", "Colors:Button", "Colors:Selection", "Colors:Header",
                          "Colors:Tooltip", "Colors:Complementary", "WM", "General"):
                self.assertIn(group, conf, f"{name}: {group}")
            # The title bar is glass: its color has an alpha value.
            self.assertEqual(len(conf["WM"]["activeBackground"].split(",")), 4)
            self.assertEqual(conf["Colors:Selection"]["BackgroundNormal"], "53,127,114")


class Paintings(unittest.TestCase):
    WALL = SHARE / "wallpapers/Monet/contents"

    def test_four_lights(self):
        for hour in ("dawn", "day", "dusk", "night"):
            self.assertGreater((self.WALL / "hours" / f"{hour}.jpg").stat().st_size, 100_000, hour)

    def test_static_wallpaper_points_at_paintings(self):
        self.assertTrue((self.WALL / "images/3840x2160.jpg").resolve().is_file())
        self.assertTrue((self.WALL / "images_dark/3840x2160.jpg").resolve().is_file())

    def test_hours_agree(self):
        # The wallpaper, the placard and the light switch use the same hours.
        wallpaper = (PLASMA / "wallpapers/org.monet.hours/contents/ui/main.qml").read_text()
        self.assertIn('{ name: "dawn", from: 5 * 60 }', wallpaper)
        self.assertIn('{ name: "dusk", from: 17 * 60 }', wallpaper)
        light = (ROOT / "linux/libexec/monet-light").read_text()
        self.assertIn("DAY_FROM=5", light)
        self.assertIn("DAY_UNTIL=17", light)
        self.assertIn("05,17:00:00", (ROOT / "linux/systemd/user/monet-light.timer").read_text())


class Fonts(unittest.TestCase):
    def test_fraunces_with_license(self):
        fonts = SHARE / "fonts/monet"
        self.assertTrue((fonts / "OFL.txt").is_file())
        for style in ("Light", "Regular", "SemiBold", "Italic", "LightItalic"):
            self.assertTrue((fonts / f"Fraunces72ptSuperSoft-{style}.ttf").is_file(), style)


class Scripts(unittest.TestCase):
    def test_shell_scripts_parse(self):
        for script in ("monet-session", "monet-look", "monet-light", "monet-quick"):
            subprocess.run(["bash", "-n", str(ROOT / "linux/libexec" / script)], check=True)

    def test_quick_status_is_json_without_any_tools(self):
        # On a machine without Wi-Fi, Bluetooth or sound tools it still answers.
        out = subprocess.run(["bash", str(ROOT / "linux/libexec/monet-quick"), "status"],
                             capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"})
        status = json.loads(out.stdout)
        self.assertIn(status["light"], ("hours", "mist", "smoke"))

    def test_slay_the_spire_is_listed_for_testing(self):
        games = json.loads((SHARE / "monet/windows-games.json").read_text())
        self.assertIn("steam:646570", [g["id"] for g in games["games"]])


if __name__ == "__main__":
    unittest.main()
