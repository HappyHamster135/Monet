"""Checks for Monet's look: the Plasma pieces, the app style and the paintings.

    python3 -m unittest discover -s tests
"""

import configparser
import importlib.machinery
import importlib.util
import json
import re
import subprocess
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# No __pycache__ beside the helpers we load: the Linux package copies libexec/.
sys.dont_write_bytecode = True
SHARE = ROOT / "linux" / "share"


def qml_files():
    """Every QML file: Plasma's pieces, the lock screen and Monet Setup's screens."""
    return (list(PLASMA.rglob("*.qml")) + list((SHARE / "monet/lockscreen").glob("*.qml"))
            + list((SHARE / "monet/widgets").glob("*.qml"))
            + list((ROOT / "setup/qml").rglob("*.qml")))
PLASMA = SHARE / "plasma"


def element_ids(svg):
    return set(re.findall(r'id="([^"]+)"', svg))


def quick_helper():
    """linux/libexec/monet-quick as a module (it has no .py ending)."""
    path = str(ROOT / "linux/libexec/monet-quick")
    loader = importlib.machinery.SourceFileLoader("monet_quick", path)
    spec = importlib.util.spec_from_loader("monet_quick", loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


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
        for qml in qml_files():
            text = qml.read_text()
            components = []
            for match in re.finditer(r"\n([ \t]*)component (\w+): ", text):
                indent = match.group(1)
                end = text.find("\n" + indent + "}", match.end())
                components.append((match.group(2), match.start(), end))
            outside = text
            for _, start, end in reversed(components):
                outside = outside[:start] + outside[end:]
            ids = set(re.findall(r"\bid: (\w+)", outside))
            for name, start, end in components:
                body = text[start:end]
                for ident in ids - set(re.findall(r"\bid: (\w+)", body)):
                    self.assertNotRegex(body, r"\b%s\." % ident, f"{qml.name}: component {name} uses {ident}")

    def test_ids_do_not_hide_properties(self):
        # An id wins over a property of the same name, silently.
        for qml in qml_files():
            text = qml.read_text()
            ids = set(re.findall(r"\bid: (\w+)", text))
            props = set(re.findall(r"property [\w<>]+ (\w+)", text))
            self.assertFalse(ids & props, f"{qml.name}: {ids & props}")

    def test_pixel_sizes_are_whole(self):
        # font.pixelSize is an int: 12.5 stops the whole file from loading.
        for qml in qml_files():
            for line in re.findall(r"pixelSize: ([^\n]*)", qml.read_text()):
                if "Math." not in line:
                    self.assertNotRegex(line, r"\b\d+\.\d", f"{qml.name}: pixelSize: {line}")

    def test_dialogs_keep_their_helpers_in_main_item(self):
        # Plasma's Dialog hands everything declared inside it to mainItem, an
        # Item: a Timer or DataSource there stops the whole widget loading.
        for qml in qml_files():
            text = qml.read_text()
            if not re.search(r"(?m)^PlasmaCore\.Dialog \{", text):
                continue
            inside = re.findall(r"(?m)^    ([A-Z][\w.]*) \{$", text)
            self.assertEqual(inside, [], f"{qml.name}: move {inside} into mainItem")

    def test_qml_avoids_reserved_names(self):
        for qml in qml_files():
            text = qml.read_text()
            self.assertNotRegex(text, r"property \w+ (state|on)\b", qml.name)


class PlasmaStyle(unittest.TestCase):
    STYLES = [PLASMA / "desktoptheme/monet", PLASMA / "desktoptheme/monet-solid"]
    PIECES = ["topleft", "top", "topright", "left", "center", "right", "bottomleft", "bottom", "bottomright"]

    def test_frames_are_complete(self):
        for style in self.STYLES:
            for name, folder in [(n, f) for n in ("dialogs/background", "widgets/panel-background", "widgets/tooltip")
                                 for f in ("", "translucent/")]:
                svg = (style / f"{folder}{name}.svg").read_text()
                ids = element_ids(svg)
                for prefix in ("", "mask-", "shadow-"):
                    for piece in self.PIECES:
                        self.assertIn(prefix + piece, ids, f"{style.name} {name}: {prefix}{piece}")
                for side in ("top", "bottom", "left", "right"):
                    self.assertIn(f"hint-{side}-margin", ids)
                    self.assertIn(f"shadow-hint-{side}-margin", ids)
                self.assertIn('id="current-color-scheme"', svg)

    def test_frames_have_no_strokes(self):
        # Qt counts a stroke's width in an element's size, which shifts pieces.
        for style in self.STYLES:
            for svg in style.rglob("*.svg"):
                self.assertNotIn("stroke", svg.read_text(), svg)

    def test_solid_and_opaque_glass(self):
        # A window touching the islands makes Plasma draw them from solid/;
        # without compositing, from opaque/. Missing ones fall back to Breeze.
        for style in self.STYLES:
            for folder in ("solid/", "opaque/"):
                for name in ("dialogs/background", "widgets/panel-background", "widgets/tooltip", "widgets/background"):
                    ids = element_ids((style / f"{folder}{name}.svg").read_text())
                    for piece in self.PIECES:
                        self.assertIn(piece, ids, f"{style.name} {folder}{name}: {piece}")
                        self.assertIn("mask-" + piece, ids, f"{style.name} {folder}{name}: mask-{piece}")

    def test_controls_are_monets(self):
        # Everything the bar and its popovers draw comes from Monet, not Breeze.
        need = {
            "widgets/tasks": [p + "-" + piece for p in ("normal", "focus", "minimized", "attention", "normal-hover",
                                                         "focus-hover", "hover", "launcher-hover", "progress")
                              for piece in self.PIECES] + ["normal-hint-left-margin", "normal-hint-bottom-margin"],
            "widgets/viewitem": [p + "-center" for p in ("normal", "hover", "selected", "selected+hover")],
            "widgets/listitem": ["normal-center", "hover-center", "pressed-center", "section-center", "separator"],
            "widgets/button": [p + "-center" for p in ("normal", "pressed", "hover", "focus", "toolbutton-hover",
                                                        "toolbutton-pressed", "toolbutton-focus")],
            "widgets/actionbutton": ["normal", "hover", "pressed", "focus"],
            "widgets/checkmarks": ["checkbox", "radiobutton"],
            "widgets/radiobutton": ["hint-size", "normal", "checked", "symbol", "focus", "hover", "shadow"],
            "widgets/switch": ["hint-bar-size", "inactive-left", "inactive-center", "inactive-right", "active-left",
                               "active-center", "active-right", "handle", "handle-hover", "handle-pressed",
                               "handle-shadow", "handle-focus"],
            "widgets/slider": ["groove-center", "groove-highlight-center", "hint-handle-size", "horizontal-slider-handle",
                               "horizontal-slider-shadow", "horizontal-slider-focus", "horizontal-slider-hover"],
            "widgets/scrollbar": ["hint-scrollbar-size", "slider-center", "mouseover-slider-center",
                                  "background-vertical-center", "slider-hint-left-inset"],
            "widgets/lineedit": ["base-center", "hover-center", "focus-center", "hint-focus-over-base"],
            "widgets/tabbar": ["north-active-tab-center", "south-active-tab-center"],
            "widgets/plasmoidheading": ["header-center", "footer-center", "hint-top-margin"],
            "widgets/frame": ["plain-center", "raised-center", "sunken-center"],
            "widgets/bar_meter_horizontal": ["hint-bar-size", "bar-inactive-center", "bar-active-center"],
            "widgets/busywidget": ["busywidget"],
            "widgets/line": ["horizontal-line", "vertical-line"],
        }
        for style in self.STYLES:
            for name, elements in need.items():
                ids = element_ids((style / f"{name}.svg").read_text())
                for element in elements:
                    self.assertIn(element, ids, f"{style.name} {name}: {element}")

    def test_tray_icons_are_monets(self):
        # The bar's sound, network, battery and power signs, brushed in ink.
        need = {
            "audio": ["audio-volume-muted", "audio-volume-low", "audio-volume-medium", "audio-volume-high"],
            "network": [f"network-wireless-{n}" for n in (0, 20, 40, 60, 80, 100)] + ["network-wired", "network-vpn"],
            "battery": ["Battery", "Unavailable", "AcAdapter"] + [f"Fill{n}" for n in range(0, 101, 10)],
            "notification": ["notification-inactive", "notification-active", "notification-disabled"],
            "system": ["system-suspend", "system-shutdown", "system-reboot", "system-log-out", "system-lock-screen"],
            "media": ["media-playback-start", "media-playback-pause", "media-skip-forward", "media-skip-backward"],
            "preferences": ["preferences-system-bluetooth", "preferences-desktop-notification"],
        }
        for style in self.STYLES:
            for name, elements in need.items():
                ids = element_ids((style / f"icons/{name}.svg").read_text())
                for element in elements:
                    self.assertIn(element, ids, f"{style.name} icons/{name}: {element}")

    def test_check_boxes_fit_the_button_frame(self):
        # Plasma draws a check box as the button frame at 16 x 16: corners
        # larger than 8 would overlap and cut notches into it.
        svg = (self.STYLES[0] / "widgets/button.svg").read_text()
        for corner in re.findall(r'<g id="normal-topleft"><rect x="[\d.]+" y="[\d.]+" width="([\d.]+)" height="([\d.]+)"', svg):
            self.assertLessEqual(max(float(corner[0]), float(corner[1])), 8)
        self.assertIn('id="normal-topleft"', svg)

    def test_running_apps_get_the_sun(self):
        # The design: a small sun-colored dab under running apps, nothing under launchers.
        svg = (self.STYLES[0] / "widgets/tasks.svg").read_text()
        self.assertIn("#F2552C", element_body(svg, "normal-bottom"))
        self.assertIn("#F2552C", element_body(svg, "focus-bottom"))
        self.assertNotIn('id="topleft"', svg)


class AppStyle(unittest.TestCase):
    KVANTUM = SHARE / "Kvantum"
    THEMES = ("Monet", "MonetDark", "MonetSolid", "MonetDarkSolid")

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
        for theme in self.THEMES:
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

    def test_glass_edges_and_paper_inside(self):
        # Glass around the edges; files and text sit on solid paper.
        for theme in self.THEMES:
            conf = self.sections(self.KVANTUM / theme / f"{theme}.kvconfig")
            glass = "true" if "Solid" not in theme else "false"
            self.assertEqual(conf["%General"]["translucent_windows"], glass, theme)
            self.assertEqual(conf["%General"]["blurring"], glass, theme)
            self.assertEqual(conf["Hacks"]["transparent_dolphin_view"], "false", theme)

    def test_light_switches_between_themes_that_exist(self):
        light = (ROOT / "linux/libexec/monet-light").read_text()
        self.assertIn('kvantum="${kvantum}Solid" style=monet-solid', light)
        for theme in self.THEMES:
            self.assertTrue((self.KVANTUM / theme / f"{theme}.svg").is_file(), theme)

    def test_frame_pieces_have_no_strokes(self):
        for theme in self.THEMES:
            svg = (self.KVANTUM / theme / f"{theme}.svg").read_text()
            for ident in element_ids(svg):
                if re.search(r"-(top|bottom|left|right|topleft|topright|bottomleft|bottomright)$", ident):
                    self.assertNotIn("stroke", element_body(svg, ident), ident)

    def test_menus_and_tooltips_cast_shadows(self):
        # Kvantum draws a popup's shadow from "<element>-shadow-*" pieces, and
        # the hints say how much of each is shadow (so blur stays under the glass).
        for theme in self.THEMES:
            conf = self.sections(self.KVANTUM / theme / f"{theme}.kvconfig")
            ids = element_ids((self.KVANTUM / theme / f"{theme}.svg").read_text())
            general = conf["%General"]
            for section, key in (("Menu", "menu_shadow_depth"), ("ToolTip", "tooltip_shadow_depth")):
                self.assertGreater(int(general[key]), 0, f"{theme} {key}")
                element = self.resolved(conf, section, "frame.element")
                for piece in ("topleft", "top", "topright", "left", "right", "bottomleft", "bottom", "bottomright"):
                    self.assertIn(f"{element}-shadow-{piece}", ids, f"{theme} {element}-shadow-{piece}")
                for side in ("top", "bottom", "left", "right"):
                    self.assertIn(f"{element}-shadow-hint-{side}", ids, f"{theme} {element}-shadow-hint-{side}")
            # Rounded menus get rounded blur, not a square of it at the corners.
            self.assertGreater(int(general["menu_blur_radius"]), 0, theme)
            self.assertGreater(int(general["tooltip_blur_radius"]), 0, theme)

    def test_menu_separators_are_drawn(self):
        # Kvantum draws them as the menu item's indicator element plus "-separator".
        for theme in self.THEMES:
            conf = self.sections(self.KVANTUM / theme / f"{theme}.kvconfig")
            ids = element_ids((self.KVANTUM / theme / f"{theme}.svg").read_text())
            self.assertIn(self.resolved(conf, "MenuItem", "indicator.element") + "-separator", ids, theme)

    def test_solid_menus_are_opaque(self):
        # Without glass there's no blur, so a see-through menu would show the text behind it.
        for theme in ("MonetSolid", "MonetDarkSolid"):
            svg = (self.KVANTUM / theme / f"{theme}.svg").read_text()
            self.assertNotRegex(element_body(svg, "menu-normal"), r'fill-opacity="0\.\d+"', theme)


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

    def test_gtk_sheets(self):
        gtk = SHARE / "monet/gtk"
        for version in ("3.0", "4.0"):
            for light, window in (("light", "#F3F1EC"), ("dark", "#242321")):
                css = (gtk / f"gtk-{version}/{light}.css").read_text()
                # monet-light knows its own sheet by the first line.
                self.assertTrue(css.startswith("/* Monet:"), f"{version} {light}")
                # KDE's colors first (KDE adds the import if it's missing, at the end).
                first = re.sub(r"/\*.*?\*/", "", css, flags=re.S).split()[:2]
                self.assertEqual(first, ["@import", "'colors.css';"], f"{version} {light}")
                # The same paper and smoke as the Qt side.
                self.assertIn(f"@define-color window_bg_color {window};", css)
                # Libadwaita 1.6+ only reads variables, and only GTK 4 parses them.
                self.assertEqual(f"--window-bg-color: {window};" in css, version == "4.0", f"{version} {light}")


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


class FakeKDE:
    """kreadconfig6, kwriteconfig6 and the plasma-apply tools, keeping
    settings in one JSON file, so monet-light can run without Plasma."""

    TOOL = """#!/usr/bin/env python3
import json, os, sys
store = os.path.join(os.environ["FAKE_KDE"], "settings.json")
try:
    data = json.load(open(store))
except (OSError, ValueError):
    data = {}
name, args = os.path.basename(sys.argv[0]), sys.argv[1:]
def opt(flag, default=""):
    return args[args.index(flag) + 1] if flag in args else default
if name == "plasma-apply-colorscheme":
    data["kdeglobals|General|ColorScheme"] = args[0]
elif name == "plasma-apply-desktoptheme":
    data["plasmarc|Theme|name"] = args[0]
else:
    key = "|".join((os.path.basename(opt("--file")), opt("--group"), opt("--key")))
    if name == "kreadconfig6":
        print(data.get(key, opt("--default")))
        sys.exit(0)
    data[key] = [a for a in args if not a.startswith("--") and a not in (opt("--file"), opt("--group"), opt("--key"))][-1]
json.dump(data, open(store, "w"))
"""

    def __init__(self, tmp, hour):
        self.dir = Path(tmp)
        bin_ = self.dir / "bin"
        bin_.mkdir()
        for tool in ("kreadconfig6", "kwriteconfig6", "plasma-apply-colorscheme", "plasma-apply-desktoptheme"):
            (bin_ / tool).write_text(self.TOOL)
            (bin_ / tool).chmod(0o755)
        (bin_ / "date").write_text(f"#!/bin/sh\necho {hour:02d}\n")
        (bin_ / "date").chmod(0o755)
        self.env = {"PATH": f"{bin_}:/usr/bin:/bin", "HOME": str(self.dir), "FAKE_KDE": str(self.dir),
                    "XDG_CONFIG_HOME": str(self.dir / "config"), "XDG_RUNTIME_DIR": str(self.dir)}

    def light(self, *args):
        subprocess.run(["bash", str(ROOT / "linux/libexec/monet-light"), *args], env=self.env, check=True, timeout=30)

    def settings(self):
        return json.loads((self.dir / "settings.json").read_text())

    def set(self, key, value):
        data = self.settings()
        data[key] = value
        (self.dir / "settings.json").write_text(json.dumps(data))

    def choice(self):
        path = self.dir / "config/monet/light"
        return path.read_text().strip() if path.exists() else "hours"


class Light(unittest.TestCase):
    LNF = "kdeglobals|KDE|LookAndFeelPackage"

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def test_hours_follow_the_time_and_kde_shows_it(self):
        kde = FakeKDE(self.tmp.name, hour=12)
        kde.light("apply")
        s = kde.settings()
        self.assertEqual(s["kdeglobals|General|ColorScheme"], "MonetLight")
        self.assertEqual(s[self.LNF], "org.monet.desktop")
        self.assertEqual(s["kvantum.kvconfig|General|theme"], "Monet")
        (Path(self.tmp.name) / "night").mkdir()
        night = FakeKDE(Path(self.tmp.name) / "night", hour=21)
        night.light("apply")
        self.assertEqual(night.settings()["kdeglobals|General|ColorScheme"], "MonetDark")
        self.assertEqual(night.settings()[self.LNF], "org.monet.smoke.desktop")

    def test_kde_dark_button_keeps_smoke(self):
        kde = FakeKDE(self.tmp.name, hour=12)
        kde.light("apply")
        # Monet's own change isn't a choice.
        kde.light("sync")
        self.assertEqual(kde.choice(), "hours")
        # Someone picks Dark in KDE's settings at midday.
        kde.set(self.LNF, "org.monet.smoke.desktop")
        kde.set("kdeglobals|General|ColorScheme", "MonetDark")
        kde.light("sync")
        self.assertEqual(kde.choice(), "smoke")
        self.assertEqual(kde.settings()["kvantum.kvconfig|General|theme"], "MonetDark")

    def test_gtk_apps_get_monet_and_keep_kdes_colors(self):
        kde = FakeKDE(self.tmp.name, hour=21)
        light = Path(self.tmp.name) / "monet-light"
        light.write_text((ROOT / "linux/libexec/monet-light").read_text().replace("@DATADIR@", str(SHARE)))
        config = Path(self.tmp.name) / "config"
        # What KDE writes by itself: only its colors.
        (config / "gtk-3.0").mkdir(parents=True)
        (config / "gtk-3.0/gtk.css").write_text("\n@import 'colors.css';")
        # And a gtk.css someone wrote.
        (config / "gtk-4.0").mkdir(parents=True)
        (config / "gtk-4.0/gtk.css").write_text("window { background: pink; }\n")
        subprocess.run(["bash", str(light), "apply"], env=kde.env, check=True, timeout=30)
        gtk3 = (config / "gtk-3.0/gtk.css").read_text()
        self.assertTrue(gtk3.startswith("/* Monet:"))
        self.assertIn("Smoke", gtk3.splitlines()[0])
        self.assertIn("@import 'colors.css';", gtk3)
        self.assertEqual((config / "gtk-4.0/gtk.css").read_text(), "window { background: pink; }\n")
        # By day, Monet's own sheet turns to mist.
        (Path(self.tmp.name) / "noon").mkdir()
        noon = FakeKDE(Path(self.tmp.name) / "noon", hour=12)
        sheet = Path(self.tmp.name) / "noon/config/gtk-3.0/gtk.css"
        sheet.parent.mkdir(parents=True)
        sheet.write_text(gtk3)
        subprocess.run(["bash", str(light), "apply"], env=noon.env, check=True, timeout=30)
        self.assertIn("Mist", sheet.read_text().splitlines()[0])

    def test_window_frames_follow_the_light(self):
        kde = FakeKDE(self.tmp.name, hour=21)
        kde.light("apply")
        frame = "kwinrc|org.kde.kdecoration2|theme"
        kde.set(frame, "__aurorae__svg__Monet")
        kde.light("apply")
        self.assertEqual(kde.settings()[frame], "__aurorae__svg__MonetSmoke")
        # Without glass, the solid frame.
        prefs = Path(self.tmp.name) / "config/monet/prefs.json"
        prefs.parent.mkdir(parents=True, exist_ok=True)
        prefs.write_text('{"glass": false}')
        kde.light("apply")
        self.assertEqual(kde.settings()[frame], "__aurorae__svg__MonetSmokeSolid")
        # Someone else's frame is theirs.
        kde.set(frame, "__aurorae__svg__Sweet")
        kde.light("apply")
        self.assertEqual(kde.settings()[frame], "__aurorae__svg__Sweet")

    def test_other_themes_are_left_alone(self):
        kde = FakeKDE(self.tmp.name, hour=12)
        kde.light("apply")
        kde.set(self.LNF, "org.kde.breezedark.desktop")
        kde.set("kdeglobals|General|ColorScheme", "BreezeDark")
        kde.light("sync")
        kde.light("apply")
        s = kde.settings()
        self.assertEqual(kde.choice(), "hours")
        self.assertEqual(s[self.LNF], "org.kde.breezedark.desktop")
        self.assertEqual(s["kdeglobals|General|ColorScheme"], "BreezeDark")


class GlobalThemes(unittest.TestCase):
    LNF = PLASMA / "look-and-feel"

    def test_mist_and_smoke_differ_only_in_colors(self):
        mist = (self.LNF / "org.monet.desktop/contents/defaults").read_text()
        smoke = (self.LNF / "org.monet.smoke.desktop/contents/defaults").read_text()
        self.assertEqual(smoke, mist.replace("ColorScheme=MonetLight", "ColorScheme=MonetDark")
                         .replace("theme=__aurorae__svg__Monet\n", "theme=__aurorae__svg__MonetSmoke\n"))
        self.assertIn("ColorScheme=MonetDark", smoke)
        layout = "contents/layouts/org.kde.plasma.desktop-layout.js"
        self.assertEqual((self.LNF / "org.monet.desktop" / layout).read_text(),
                         (self.LNF / "org.monet.smoke.desktop" / layout).read_text())

    def test_applying_from_kde_keeps_glass_and_the_hours(self):
        # A theme applied from KDE's settings must not put Breeze's app style
        # back or swap The Hours for a still picture.
        for theme in ("org.monet.desktop", "org.monet.smoke.desktop"):
            defaults = (self.LNF / theme / "contents/defaults").read_text()
            self.assertNotIn("widgetStyle", defaults)
            self.assertNotIn("[Wallpaper]", defaults)

    def test_kde_light_and_dark_are_monet(self):
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertIn("DefaultLightLookAndFeel org.monet.desktop", look)
        self.assertIn("DefaultDarkLookAndFeel org.monet.smoke.desktop", look)
        self.assertIn("monet-light-sync.path", look)
        path = (ROOT / "linux/systemd/user/monet-light-sync.path").read_text()
        self.assertIn("PathChanged=%h/.config/kdeglobals", path)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn("org.monet.smoke.desktop", install)
        self.assertIn("monet-light-sync.path", install)


class Updates(unittest.TestCase):
    def test_nothing_updates_by_itself(self):
        install = (ROOT / "linux/install.sh").read_text()
        for unit in ("uupd.timer", "rpm-ostreed-automatic.timer", "bootc-fetch-apply-updates.timer"):
            self.assertIn(unit, install)
        self.assertIn('systemctl mask "$unit"', install)
        self.assertIn("AutomaticUpdatePolicy=none", install)

    def test_settings_checks_before_installing(self):
        qml = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text()
        self.assertIn('ask("update-check"', qml)
        self.assertIn('ask("update"', qml)
        quick = (ROOT / "linux/libexec/monet-quick").read_text()
        self.assertIn('"update", "--check", "--json"', quick)
        # Firmware too: looked for with Monet, installed only from its own button.
        self.assertIn('ask("firmware-check"', qml)
        self.assertIn('ask("firmware-update"', qml)
        for command in ('"firmware-check"', '"firmware-update"'):
            self.assertIn(f"cmd == {command}", quick)
        self.assertNotIn("fwupd-refresh", (ROOT / "linux/install.sh").read_text())  # not masked: it only fetches the list


class Fonts(unittest.TestCase):
    def test_fraunces_with_license(self):
        fonts = SHARE / "fonts/monet"
        self.assertTrue((fonts / "OFL.txt").is_file())
        for style in ("Light", "Regular", "SemiBold", "Italic", "LightItalic"):
            self.assertTrue((fonts / f"Fraunces72ptSuperSoft-{style}.ttf").is_file(), style)


class Icons(unittest.TestCase):
    THEME = SHARE / "icons/Monet"

    def test_painted_folders_and_apps(self):
        places = ("folder", "user-home", "user-desktop", "folder-documents", "folder-download", "folder-pictures",
                  "folder-music", "folder-videos", "folder-games", "user-trash", "user-trash-full")
        # Store is Bazaar on Bazzite: the market bouquet is Monet's either way.
        apps = ("monet", "monet-settings", "systemsettings", "org.kde.dolphin", "org.kde.konsole", "org.kde.discover",
                "io.github.kolunmi.Bazaar", "org.kde.plasma-systemmonitor", "org.kde.gwenview", "org.kde.okular",
                "org.kde.kate", "org.kde.ark", "org.kde.spectacle", "org.kde.haruna", "org.kde.kcalc",
                # What Bazzite brings to the dock and the menu.
                "org.mozilla.firefox", "steam", "net.lutris.Lutris", "io.github.ublue_os.yafti_gtk",
                "com.github.tchx84.Flatseal", "io.github.flattool.Warehouse", "it.mijorus.gearlever",
                "com.ranfdev.DistroShelf", "net.davidotek.pupgui2", "waydroid", "input-remapper")
        categories = ("applications-games", "applications-graphics", "applications-internet", "applications-multimedia",
                      "applications-office", "applications-system", "applications-utilities")
        for context, names in (("places", places), ("apps", apps), ("categories", categories)):
            for name in names:
                svg = self.THEME / context / "scalable" / f"{name}.svg"
                self.assertEqual(ET.parse(svg).getroot().tag, "{http://www.w3.org/2000/svg}svg", name)
                # Each one a painting, kept as a picture inside the SVG.
                self.assertIn("data:image/png;base64,", svg.read_text(), name)

    def test_files_and_drives_are_painted_under_every_name(self):
        # Breeze has an icon for nearly every exact type, found before the
        # generic one: install.sh links each name to its painting.
        links = {}
        for line in (self.THEME / "aliases").read_text().splitlines():
            link, target = line.split()
            self.assertFalse((self.THEME / link).exists(), link)
            self.assertTrue((self.THEME / link).parent.joinpath(target).resolve().is_file(), line)
            links[link] = target
        for name in ("mimetypes/scalable/inode-directory.svg", "mimetypes/scalable/image-png.svg",
                     "mimetypes/scalable/text-plain.svg", "mimetypes/scalable/application-zip.svg",
                     "mimetypes/scalable/application-x-msdownload.svg", "devices/scalable/drive-removable-media.svg"):
            self.assertIn(name, links)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('done < "$SRC/share/icons/Monet/aliases"', install)

    def test_bazzites_own_entries_get_paintings(self):
        # They name their pictures by path, so install.sh points them at Monet's.
        install = (ROOT / "linux/install.sh").read_text()
        links = (self.THEME / "aliases").read_text()
        for entry, icon in re.findall(r"(\w[\w.-]*):(monet-[\w-]+)", install.split("Bazzite's own menu entries")[1][:600]):
            painted = (self.THEME / "apps/scalable" / f"{icon}.svg").is_file()
            self.assertTrue(painted or f"apps/scalable/{icon}.svg " in links, icon)

    def test_theme_lists_its_folders(self):
        theme = (self.THEME / "index.theme").read_text()
        for folder in (p.parent.relative_to(self.THEME).as_posix() for p in self.THEME.rglob("*.svg")):
            self.assertIn(f"[{folder}]", theme)




class DesktopWidgets(unittest.TestCase):
    """Weather, Calendar, Now Playing, Note and Photo Frame, on the desktop."""
    WIDGETS = ("org.monet.weather", "org.monet.calendar", "org.monet.nowplaying", "org.monet.notes", "org.monet.frame")

    def test_installed_and_removed(self):
        install = (ROOT / "linux/install.sh").read_text()
        uninstall = (ROOT / "linux/uninstall.sh").read_text()
        for widget in self.WIDGETS:
            self.assertIn(widget, install)
            self.assertIn(f"plasmoids/{widget}", uninstall)

    def test_glass_reaches_every_widget_that_uses_it(self):
        install = (ROOT / "linux/install.sh").read_text()
        self.assertTrue((SHARE / "monet/widgets/Glass.qml").is_file())
        glassed = re.search(r"for applet in ([^;]+); do\n    install -m 644 \"\$SRC/share/monet/widgets/Glass.qml\"", install)
        self.assertIsNotNone(glassed)
        for widget in self.WIDGETS:
            uses = any("Glass {" in f.read_text() for f in (PLASMA / "plasmoids" / widget / "contents/ui").glob("*.qml"))
            self.assertEqual(uses, widget in glassed.group(1).split(), widget)

    def test_glass_frosts_the_hours_it_finds(self):
        glass = (SHARE / "monet/widgets/Glass.qml").read_text()
        hours = (PLASMA / "wallpapers/org.monet.hours/contents/ui/main.qml").read_text()
        # What the glass looks for is what The Hours has.
        for name in ("hours", "below", "above"):
            self.assertIn(f"item.{name} !== undefined", glass)
            self.assertRegex(hours, rf"property [\w ]+\b{name}:")

    def test_desktop_starts_with_weather_and_calendar(self):
        for theme in ("org.monet.desktop", "org.monet.smoke.desktop"):
            layout = (PLASMA / "look-and-feel" / theme / "contents/layouts/org.kde.plasma.desktop-layout.js").read_text()
            for widget in ("org.monet.placard", "org.monet.weather", "org.monet.calendar"):
                self.assertIn(f'd.addWidget("{widget}"', layout)

    def test_settings_have_their_schema(self):
        for widget in ("org.monet.weather", "org.monet.notes"):
            schema = (PLASMA / "plasmoids" / widget / "contents/config/main.xml").read_text()
            used = set(re.findall(r"Plasmoid\.configuration\.(\w+)", (PLASMA / "plasmoids" / widget / "contents/ui/main.qml").read_text()))
            for key in used:
                self.assertIn(f'name="{key}"', schema, f"{widget}: {key}")


class LiquidGlass(unittest.TestCase):
    STYLE = PLASMA / "desktoptheme/monet"

    def test_rim_of_light_fades_down_the_sides(self):
        svg = (self.STYLE / "dialogs/background.svg").read_text()
        self.assertIn('id="hint-stretch-borders"', svg)  # so the fade spans the whole height
        for gradient in ("rim-fall", "sheen"):
            self.assertIn(f'<linearGradient id="{gradient}"', svg)
            self.assertIn(f'url(#{gradient})', svg)

    def test_vibrancy_behind_the_glass(self):
        for style in ("monet", "monet-solid"):
            meta = json.loads((PLASMA / "desktoptheme" / style / "metadata.json").read_text())
            self.assertTrue(meta["ContrastEffect"]["enabled"])
            self.assertGreater(meta["ContrastEffect"]["saturation"], 1)

class WindowFrames(unittest.TestCase):
    """Monet's title bars (tools/make-decoration.py), one per light."""
    THEMES = SHARE / "aurorae/themes"
    NAMES = ("Monet", "MonetSolid", "MonetSmoke", "MonetSmokeSolid")
    PIECES = PlasmaStyle.PIECES

    def test_every_light_has_a_complete_frame(self):
        for name in self.NAMES:
            theme = self.THEMES / name
            meta = configparser.ConfigParser(interpolation=None)
            meta.read_string((theme / "metadata.desktop").read_text())
            self.assertEqual(meta["Desktop Entry"]["X-KDE-PluginInfo-Name"], name)
            rc = configparser.ConfigParser(interpolation=None)
            rc.read_string((theme / f"{name}rc").read_text())
            layout = rc["Layout"]
            # The frame's top row is drawn for a title bar this high.
            self.assertEqual(int(layout["TitleEdgeTop"]) + int(layout["TitleHeight"]) + int(layout["TitleEdgeBottom"]), 36)
            ids = element_ids((theme / "decoration.svg").read_text())
            for prefix in ("decoration", "decoration-inactive", "mask", "decoration-maximized",
                           "decoration-maximized-inactive", "mask-maximized"):
                for piece in self.PIECES:
                    self.assertIn(f"{prefix}-{piece}", ids, f"{name}: {prefix}-{piece}")
            for button in ("minimize", "maximize", "restore", "close"):
                ids = element_ids((theme / f"{button}.svg").read_text())
                for state in ("active", "hover", "pressed", "inactive", "hover-inactive", "deactivated"):
                    self.assertIn(state, ids, f"{name} {button}: {state}")

    def test_frames_have_no_strokes(self):
        for svg in self.THEMES.rglob("*.svg"):
            ET.parse(svg)
            self.assertNotIn("stroke", svg.read_text(), svg)

    def test_frames_in_use_exist(self):
        used = set(re.findall(r"__aurorae__svg__(\w+)", (ROOT / "linux/libexec/monet-look").read_text()))
        for theme in ("org.monet.desktop", "org.monet.smoke.desktop"):
            used |= set(re.findall(r"__aurorae__svg__(\w+)", (PLASMA / "look-and-feel" / theme / "contents/defaults").read_text()))
        self.assertEqual(used, {"Monet", "MonetSmoke"})
        light = (ROOT / "linux/libexec/monet-light").read_text()
        self.assertIn('frame="${frame}Smoke"', light)
        self.assertIn('frame="${frame}Solid"', light)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn("for theme in " + " ".join(self.NAMES) + "; do", install)
        for name in self.NAMES:
            self.assertTrue((self.THEMES / name).is_dir(), name)


class Cursors(unittest.TestCase):
    THEME = SHARE / "icons/Monet-cursors"

    def read(self, name):
        import struct
        data = (self.THEME / "cursors" / name).read_bytes()
        magic, header, _, count = struct.unpack_from("<4sIII", data)
        self.assertEqual((magic, header), (b"Xcur", 16), name)
        sizes = set()
        for i in range(count):
            kind, size, pos = struct.unpack_from("<III", data, 16 + 12 * i)
            chunk = struct.unpack_from("<IIIIIIIII", data, pos)
            self.assertEqual(chunk[:3], (36, kind, size), name)
            width, height, x, y = chunk[4:8]
            self.assertEqual((width, height), (size, size), name)
            self.assertTrue(x < width and y < height, name)
            self.assertEqual(len(data[pos + 36:pos + 36 + width * height * 4]), width * height * 4, name)
            sizes.add(size)
        return sizes, count

    def test_cursors_are_drawn_at_every_size(self):
        for path in (self.THEME / "cursors").iterdir():
            sizes, _ = self.read(path.name)
            self.assertEqual(sizes, {24, 32, 48, 64}, path.name)
        # The sun breathes while something works: frames at each size.
        self.assertGreater(self.read("wait")[1], 4 * 4)

    def test_every_alias_has_its_cursor(self):
        drawn = {p.name for p in (self.THEME / "cursors").iterdir()}
        aliases = []
        for line in (self.THEME / "aliases").read_text().splitlines():
            alias, name = line.split()
            self.assertIn(name, drawn, alias)
            self.assertNotIn(alias, drawn)
            aliases.append(alias)
        for name in ("left_ptr", "hand2", "xterm", "watch", "left_ptr_watch", "size_hor", "size_ver", "fleur"):
            self.assertIn(name, aliases)

    def test_cursors_are_in_use(self):
        index = configparser.ConfigParser(interpolation=None)
        index.read_string((self.THEME / "index.theme").read_text())
        self.assertEqual(index["Icon Theme"]["Inherits"], "breeze_cursors")
        for theme in ("org.monet.desktop", "org.monet.smoke.desktop"):
            self.assertIn("cursorTheme=Monet-cursors", (PLASMA / "look-and-feel" / theme / "contents/defaults").read_text())
        self.assertIn("cursorTheme Monet-cursors", (ROOT / "linux/libexec/monet-look").read_text())
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('done < "$SRC/share/icons/Monet-cursors/aliases"', install)
        self.assertIn("CursorTheme=Monet-cursors", install)


class StartAndSignIn(unittest.TestCase):
    PLYMOUTH = ROOT / "image/setup/files/usr/share/plymouth/themes/monet"

    def test_boot_screen_asks_for_a_disk_password(self):
        script = (self.PLYMOUTH / "monet.script").read_text()
        for hook in ("SetDisplayPasswordFunction", "SetDisplayQuestionFunction", "SetDisplayNormalFunction",
                     "SetMessageFunction", "SetRefreshFunction"):
            self.assertIn(f"Plymouth.{hook}(", script)
        for picture in re.findall(r'Image\("([^"]+)"\)', script):
            self.assertTrue((self.PLYMOUTH / picture).is_file(), picture)

    def test_monet_boots_with_its_own_screen(self):
        containerfile = (ROOT / "image/Containerfile").read_text()
        self.assertIn("plymouth-set-default-theme monet", containerfile)
        self.assertIn("plymouth-plugin-script", containerfile)  # the theme is a script
        self.assertIn("dracut", containerfile)

    def test_lock_screen_is_monets_and_always_unlocks(self):
        lock = SHARE / "monet/lockscreen"
        entry = (lock / "LockScreen.qml").read_text()
        # What kscreenlocker and KDE's lock screen expect of the file it replaces.
        for part in ("property string notification", "signal clearPassword()", "signal notificationRepeated()",
                     "property bool viewVisible"):
            self.assertIn(part, entry)
        # Monet's, and KDE's own whenever Monet's can't load.
        self.assertIn('source: "MonetLockScreen.qml"', entry)
        self.assertIn("active: monet.status === Loader.Error", entry)
        self.assertIn('source: "LockScreenUi.qml"', entry)
        monet = (lock / "MonetLockScreen.qml").read_text()
        for part in ("authenticator.respond(password)", "authenticator.startAuthenticating()", "Qt.quit()",
                     "id: fadeoutTimer",  # KDE's MediaControls.qml stops it by name
                     "PasswordSync.password", 'source: "MediaControls.qml"', 'source: "LockOsd.qml"',
                     "VirtualKeyboardLoader", "visibleBoundary"):
            self.assertIn(part, monet)
        # Installed beside KDE's files in the desktop shell, only where Plasma keeps them.
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn("/usr/share/plasma/shells/org.kde.plasma.desktop/contents/lockscreen", install)
        self.assertIn('[ -f "$lock/LockScreenUi.qml" ]', install)
        for name in ("MonetLockScreen.qml", "LockScreen.qml"):
            self.assertIn(f'"$SRC/share/monet/lockscreen/{name}" "$lock/{name}"', install)

    def test_sign_in_screen_is_monets(self):
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn("name=monet", install)
        self.assertIn("ColorScheme=MonetDark", install)
        self.assertIn("/usr/lib/tmpfiles.d/monet-sddm.conf", install)

class MonetSettings(unittest.TestCase):
    QUICK = PLASMA / "plasmoids/org.monet.quick/contents/ui"

    def test_every_page_has_its_picture(self):
        qml = (self.QUICK / "MonetSettings.qml").read_text()
        entries = re.findall(r'\{ id: "(\w+)", name: [^,]+,( kde: "(\w+)", swatch: "(\w+)",)?', qml)
        pages = [e[0] for e in entries if not e[2]]
        self.assertEqual(tuple(pages), quick_helper().PAGES)
        art = SHARE / "monet/settings"
        # Entries that open KDE's own page: one the helper knows, a swatch that's there.
        for _, _, kde, swatch in (e for e in entries if e[2]):
            self.assertIn(kde, quick_helper().KDE_PAGES)
            self.assertTrue((art / f"swatch-{swatch}.png").is_file(), swatch)
        for page in pages:
            self.assertTrue((art / f"swatch-{page}.png").is_file(), page)
            self.assertIn(f"{page}: {page}Page", qml)
        for picture in ("light-hours.png", "light-mist.png", "light-smoke.png", "about.jpg"):
            self.assertTrue((art / picture).is_file(), picture)

    def test_quick_settings_opens_it(self):
        main = (self.QUICK / "main.qml").read_text()
        self.assertIn("MonetSettings {", main)
        self.assertIn('settings.open("")', main)
        self.assertIn('" listen")', main)
        self.assertNotIn('connectSource("systemsettings")', main)

    def test_app_menu_and_dock_open_it(self):
        entry = (SHARE / "applications/monet-settings.desktop").read_text()
        self.assertIn("Exec=@LIBEXECDIR@/monet-quick open\n", entry)
        self.assertIn("Icon=monet-settings", entry)
        layout = (PLASMA / "look-and-feel/org.monet.desktop/contents/layouts/org.kde.plasma.desktop-layout.js").read_text()
        self.assertIn('"applications:monet-settings.desktop"', layout)
        self.assertNotIn("systemsettings.desktop", layout)

    def test_installer_carries_it(self):
        install = (ROOT / "linux/install.sh").read_text()
        for piece in ("monet-settings.desktop", "share/monet/settings", "desktoptheme/monet-solid",
                      "MonetSolid MonetDarkSolid", "org.monet.*/contents/ui/*.qml"):
            self.assertIn(piece, install)
        uninstall = (ROOT / "linux/uninstall.sh").read_text()
        for piece in ("monet-settings.desktop", "desktoptheme/monet-solid", "Kvantum/MonetSolid", "Kvantum/MonetDarkSolid"):
            self.assertIn(piece, uninstall)


class Scripts(unittest.TestCase):
    def test_shell_scripts_parse(self):
        for script in ("monet-session", "monet-look", "monet-light"):
            subprocess.run(["bash", "-n", str(ROOT / "linux/libexec" / script)], check=True)

    def test_quick_helper_compiles(self):
        source = (ROOT / "linux/libexec/monet-quick").read_text()
        compile(source, "monet-quick", "exec")
        self.assertTrue(source.startswith("#!/usr/bin/env python3\n"))

    def test_quick_status_is_json_without_any_tools(self):
        # On a machine without Wi-Fi, Bluetooth or sound tools it still answers.
        out = subprocess.run(["python3", str(ROOT / "linux/libexec/monet-quick"), "status"],
                             capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"})
        status = json.loads(out.stdout)
        self.assertIn(status["light"], ("hours", "mist", "smoke"))
        self.assertIn("mic", status)

    def test_quick_reads_nmcli(self):
        quick = quick_helper()
        self.assertEqual(quick.nmcli_fields(r"*:Caf\: Monet:80:WPA2"), ["*", "Caf: Monet", "80", "WPA2"])
        nets = quick.wifi_list("\n".join([
            ":Harbor:40:WPA2", "*:Harbor:72:WPA2", ":Le Havre:90:WPA2", ":Open Sea:20:", ":Ghost:30:--", "::99:WPA2",
        ]))
        self.assertEqual([n["name"] for n in nets], ["Harbor", "Le Havre", "Ghost", "Open Sea"])
        self.assertTrue(nets[0]["active"])
        self.assertEqual(nets[0]["signal"], 72)
        self.assertFalse(nets[2]["secure"])
        self.assertFalse(nets[3]["secure"])

    def test_quick_reads_fwupd(self):
        report = {"Devices": [
            {"Name": "System Firmware", "Vendor": "Lenovo", "Version": "1.20", "Flags": ["internal", "updatable", "needs-reboot"],
             "Problems": ["require-ac-power"], "Releases": [{"Version": "1.32", "Summary": "UEFI update"}, {"Version": "1.28"}]},
            {"Name": "Samsung SSD 990 PRO 1TB", "Vendor": "Samsung", "Version": "4B2QJXD7", "Flags": ["updatable"],
             "Releases": [{"Version": "4B2QJXE7"}]},
            {"Name": "Keyboard", "Version": "1.0", "Flags": ["updatable"], "Releases": []},
        ]}
        found = quick_helper().firmware_updates(report)
        self.assertEqual([f["device"] for f in found], ["System Firmware", "Samsung SSD 990 PRO 1TB"])
        uefi, ssd = found
        self.assertEqual((uefi["current"], uefi["version"], uefi["restart"]), ("1.20", "1.32", True))
        self.assertEqual(uefi["blocked"], "Plug in the charger first.")
        self.assertEqual((ssd["restart"], ssd["blocked"]), (False, ""))

    def test_quick_firmware_check_without_updates_or_with_trouble(self):
        from unittest import mock
        quick = quick_helper()
        done = subprocess.CompletedProcess
        answers = [
            # fwupd's "nothing to do": no updates, or no part it can update.
            done([], 2, "", "No updatable devices\n"),
            done([], 1, "", "Failed to connect to daemon\nIs fwupd running?\n"),
            done([], 0, json.dumps({"Devices": [{"Name": "Dock", "Version": "1", "Releases": [{"Version": "2"}]}]}), ""),
        ]
        with mock.patch.object(quick.shutil, "which", lambda name: "/usr/bin/" + name), \
                mock.patch.object(quick.subprocess, "run", lambda args, **kw: answers.pop(0)):
            self.assertEqual(quick.firmware_check(), {"ok": True, "updates": []})
            self.assertEqual(quick.firmware_check(), {"ok": False, "message": "Is fwupd running?"})
            self.assertEqual([f["version"] for f in quick.firmware_check()["updates"]], ["2"])
        # No fwupd at all: nothing to show, not an error.
        with mock.patch.object(quick.shutil, "which", lambda name: None):
            self.assertEqual(quick.firmware_check(), {"ok": True, "updates": []})

    def test_quick_knows_what_a_bluetooth_device_is(self):
        info = "Device AA:BB:CC:DD:EE:FF (public)\n\tName: WH-1000XM5\n\tIcon: audio-headset\n\tConnected: yes\n"
        self.assertEqual(quick_helper().bt_kind(info), "audio-headset")
        self.assertEqual(quick_helper().bt_kind("Device 11:22:33:44:55:66\n\tName: Pad\n"), "")

    def test_text_from_people_reaches_nmcli_as_is(self):
        # Monet Settings sends network names and passwords as hex of their UTF-8.
        self.assertEqual(quick_helper().unhex("436166c3a92024287266292027e2988027"), "Café $(rf) '☀'")
        qml = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text()
        self.assertIn('"wifi-join " + hex(name)', qml)
        self.assertNotIn("Qt.btoa", qml)

    def test_quick_reads_wpctl(self):
        status = """PipeWire 'pipewire-0' [1.2.7, monet@pc, cookie:1]
 └─ Clients:
        33. pipewire                            [1.2.7, monet@pc, pid:1530]

Audio
 ├─ Devices:
 │      48. Navi 31 HDMI/DP Audio               [alsa]
 │
 ├─ Sinks:
 │  *   56. Speakers                            [vol: 0.45]
 │      60. Monitor (HDMI)                      [vol: 1.00]
 │
 ├─ Sources:
 │  *   57. Microphone                          [vol: 0.60]
"""
        self.assertEqual(quick_helper().sinks(status), [
            {"id": 56, "name": "Speakers", "default": True},
            {"id": 60, "name": "Monitor (HDMI)", "default": False},
        ])

    def test_trips_to_windows_are_checked_at_startup(self):
        unit = (ROOT / "linux/systemd/monet-sync.service").read_text()
        check, sync = unit.index("helper check-switch"), unit.index("helper sync")
        self.assertLess(check, sync)
        # A failed check never stops the games list from syncing.
        self.assertIn("ExecStart=-@BINDIR@/monet helper check-switch", unit)

    def test_windows_setup_can_be_tried_again(self):
        deploy = (SHARE / "monet/winpe/deploy.cmd").read_text()
        self.assertLess(deploy.index("format %TARGET%:"), deploy.index("dism /apply-image"))
        prepare = (ROOT / "linux/libexec/monet-prepare-windows").read_text()
        self.assertIn('run("ntfslabel", win["path"], "MONETWIN"', prepare)
        self.assertIn("if not has_windows(win[\"path\"])", prepare)

    def test_slay_the_spire_is_listed_for_testing(self):
        games = json.loads((SHARE / "monet/windows-games.json").read_text())
        self.assertIn("steam:646570", [g["id"] for g in games["games"]])


if __name__ == "__main__":
    unittest.main()
