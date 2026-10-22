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
    """Every QML file: Plasma's pieces, the lock, shut-down and password screens, the widget
    gallery and Monet Setup's screens."""
    return (list(PLASMA.rglob("*.qml")) + list((SHARE / "monet/lockscreen").glob("*.qml"))
            + list((SHARE / "monet/widgets").glob("*.qml")) + list((SHARE / "monet/logout").glob("*.qml"))
            + list((SHARE / "monet/explorer").glob("*.qml")) + list((SHARE / "monet/editmode").glob("*.qml"))
            + list((ROOT / "image/password").glob("*.qml")) + list((ROOT / "setup/qml").rglob("*.qml")))
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

    def test_corners_share_the_glass_arc(self):
        # Rim, sheen and hairline follow the glass's arc (else they jump a pixel where corner meets
        # edge); the blur mask's corner sits 1 px inside it, since KWin blurs whole pixels.
        import math
        for style in self.STYLES:
            svg = (style / "widgets/panel-background.svg").read_text()
            for ident in ("topleft", "mask-topleft"):
                body = element_body(svg, ident)
                x, y, r = (float(v) for v in re.search(r'<rect x="([\d.]+)" y="([\d.]+)" width="([\d.]+)"', body).groups())
                arcs = re.findall(r"A([\d.]+),[\d.]+ 0 0 [01] ([\d.]+),([\d.]+)", body)
                self.assertTrue(arcs, ident)
                for radius, ex, ey in arcs:
                    self.assertAlmostEqual(math.hypot(float(ex) - x - r, float(ey) - y - r), float(radius), 3, ident)
                if ident.startswith("mask-"):
                    self.assertEqual({float(a[0]) for a in arcs}, {r - 1})

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
groups = [args[i + 1] for i, a in enumerate(args[:-1]) if a == "--group"]
if name == "plasma-apply-colorscheme":
    data["kdeglobals|General|ColorScheme"] = args[0]
elif name == "plasma-apply-desktoptheme":
    data["plasmarc|Theme|name"] = args[0]
elif name == "busctl":
    open(os.path.join(os.environ["FAKE_KDE"], "busctl.log"), "a").write(" ".join(" ".join(args).split()) + "\\n")
else:
    key = "|".join((os.path.basename(opt("--file")), "][".join(groups), opt("--key")))
    if name == "kreadconfig6":
        print(data.get(key, opt("--default")))
        sys.exit(0)
    data[key] = [a for a in args if not a.startswith("--") and a not in (opt("--file"), *groups, opt("--key"))][-1]
json.dump(data, open(store, "w"))
"""

    def __init__(self, tmp, hour):
        self.dir = Path(tmp)
        bin_ = self.dir / "bin"
        bin_.mkdir()
        for tool in ("kreadconfig6", "kwriteconfig6", "plasma-apply-colorscheme", "plasma-apply-desktoptheme", "busctl"):
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

    def told_plasma(self):
        path = self.dir / "busctl.log"
        return path.read_text() if path.exists() else ""


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
        self.assertEqual(kde.settings()[Light.PAINTING], "smoke")
        # KDE's Automatic is Follow the hours, and KDE's own switching stays off.
        kde.set("kdeglobals|KDE|AutomaticLookAndFeel", "true")
        kde.light("sync")
        self.assertEqual(kde.choice(), "hours")
        self.assertEqual(kde.settings()["kdeglobals|KDE|AutomaticLookAndFeel"], "false")
        self.assertEqual(kde.settings()[Light.PAINTING], "hours")

    PAINTING = "kscreenlockerrc|Greeter][Wallpaper][org.monet.hours][General|Painting"

    def test_the_painting_goes_with_the_light(self):
        kde = FakeKDE(self.tmp.name, hour=12)
        # The Hours on: the painting drifts through the lights that go with the colors.
        for light in ("mist", "smoke", "hours"):
            kde.light("set", light)
            self.assertEqual(kde.settings()[self.PAINTING], light)
            self.assertIn(f"d.writeConfig('Painting', '{light}')", kde.told_plasma().splitlines()[-1])
        # The Hours off: it stays, on day for mist, night for smoke, or the light it's in now.
        prefs = Path(self.tmp.name) / "config/monet/prefs.json"
        prefs.parent.mkdir(parents=True, exist_ok=True)
        prefs.write_text('{"hours": false}')
        for light, painting in (("mist", "day"), ("smoke", "night"), ("hours", "day")):
            kde.light("set", light)
            self.assertEqual(kde.settings()[self.PAINTING], painting, light)
        # The hourly apply leaves the painting alone, so one that stays, stays.
        kde.set(self.PAINTING, "dawn")
        kde.light("apply")
        self.assertEqual(kde.settings()[self.PAINTING], "dawn")
        # Monet Settings' switches repaint through monet-light, and so does a fresh layout.
        quick = (ROOT / "linux/libexec/monet-quick").read_text()
        self.assertIn('"$0" paint\', f"{LIBEXECDIR}/monet-light"', quick)
        self.assertIn('"paint" if args[0] == "hours"', quick)
        self.assertIn('"$LIBEXECDIR/monet-light" paint', (ROOT / "linux/libexec/monet-look").read_text())
        # The wallpaper knows mist's and smoke's lights.
        wallpaper = (PLASMA / "wallpapers/org.monet.hours/contents/ui/main.qml").read_text()
        self.assertIn('pools: ({ mist: ["dawn", "day"], smoke: ["dusk", "night"] })', wallpaper)

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

    def test_the_bar_gets_ink_signs(self):
        # Plasma 6.7 takes the tray's icons from the icon theme, by name, and tints them only if the
        # theme says it follows the color scheme.
        theme = (self.THEME / "index.theme").read_text()
        self.assertIn("FollowsColorScheme=true", theme)
        self.assertIn("status/scalable", theme.split("Directories=", 1)[1].splitlines()[0])
        status = self.THEME / "status/scalable"
        for name in ("audio-volume-high", "audio-volume-muted", "network-wired-activated", "network-wireless-80",
                     "network-bluetooth-activated", "brightness-high", "media-playback-playing", "notification-inactive",
                     "notifications-disabled", "klipper", "device-notifier", "battery-050", "battery-050-charging",
                     "speedometer", "arrow-up", "kdeconnect-tray", "dialog-ok"):
            svg = (status / f"{name}.svg").read_text()
            self.assertIn('<style id="current-color-scheme"', svg, name)
            self.assertNotIn("data:image", svg, name)
        # A drive in the bar asks for "<name>-symbolic": without that exact sign, the name is shortened
        # to the painting.
        for name in ("drive-harddisk", "drive-removable-media-usb-pendrive", "media-optical", "media-flash-sd-mmc"):
            self.assertTrue((status / f"{name}-symbolic.svg").is_file(), name)

    def test_the_dock_keeps_the_painted_trash(self):
        # In a bar Plasma's Trash asks for "user-trash-symbolic" or "user-trash-full-symbolic": the pot's painting
        # answers at the dock's size, the ink sign only at menu size (actions/16 comes first in the theme).
        for name in ("user-trash-symbolic", "user-trash-full-symbolic"):
            self.assertIn("data:image/png;base64,", (self.THEME / "places/scalable" / f"{name}.svg").read_text(), name)
        self.assertNotIn("data:image", (self.THEME / "actions/16/user-trash-symbolic.svg").read_text())
        self.assertFalse((self.THEME / "actions/scalable/user-trash-symbolic.svg").exists())

    def test_account_pictures_are_monets(self):
        # Change Avatar lists every picture under plasma/avatars: Monet's, and on the image no one else's.
        pictures = sorted((SHARE / "plasma/avatars/Monet").glob("*.jpg"))
        self.assertGreaterEqual(len(pictures), 12)
        for picture in pictures:
            jpeg = picture.read_bytes()
            self.assertEqual(jpeg[:3], b"\xff\xd8\xff", picture.name)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('tree "$SRC/share/plasma/avatars/Monet" "$DATADIR/plasma/avatars/Monet"', install)
        image_only = install.split('if [ "$IMAGE" = 1 ]; then', 2)[2]
        self.assertIn('find "$DATADIR/plasma/avatars" -mindepth 1 -maxdepth 1 ! -name Monet -exec rm -rf {} +', image_only)
        self.assertIn("plasma/avatars/Monet", (ROOT / "linux/uninstall.sh").read_text())

    def test_message_boxes_get_ink_signs(self):
        # Message boxes and apps' inline notes ask for these: Monet's ink, never Breeze's triangle.
        for name in ("dialog-information", "dialog-question", "dialog-warning", "dialog-error", "dialog-positive"):
            svg = (self.THEME / "status/scalable" / f"{name}.svg").read_text()
            self.assertIn('<style id="current-color-scheme"', svg, name)
            self.assertNotIn("data:image", svg, name)

    def test_monets_desktop_widgets_have_an_icon_each(self):
        # The widget gallery lists them by icon: a painting each, not the sun twice.
        desktop = DesktopWidgets.WIDGETS + ("org.monet.placard",)
        icons = {w: json.loads((PLASMA / "plasmoids" / w / "metadata.json").read_text())["KPlugin"]["Icon"] for w in desktop}
        self.assertEqual(len(set(icons.values())), len(desktop), icons)
        for widget, icon in icons.items():
            self.assertTrue(list(self.THEME.glob(f"*/scalable/{icon}.svg")), widget)

    def test_menus_and_toolbars_get_ink_signs(self):
        theme = (self.THEME / "index.theme").read_text()
        dirs = theme.split("Directories=", 1)[1].splitlines()[0].split(",")
        # The menu-size folder comes first, so menus get the sign where a name also has a swatch.
        self.assertEqual(dirs[0], "actions/16")
        self.assertIn("actions/scalable", dirs)
        for name in ("document-new", "edit-paste", "edit-undo", "view-list-icons", "utilities-terminal-symbolic",
                     "document-edit", "system-lock-screen", "system-log-out", "go-previous", "edit-copy", "edit-find"):
            svg = (self.THEME / "actions/scalable" / f"{name}.svg").read_text()
            # One ink KDE can tint: the current-color-scheme sheet, and nothing else painted.
            self.assertIn('<style id="current-color-scheme"', svg, name)
            self.assertNotIn("data:image", svg, name)
        for name in ("preferences-desktop-wallpaper", "preferences-desktop-display"):
            self.assertTrue((self.THEME / "actions/16" / f"{name}.svg").is_file(), name)
            self.assertFalse((self.THEME / "actions/scalable" / f"{name}.svg").exists(), name)

    def test_more_settings_pages_have_monets_marks(self):
        # KDE's sidebar draws these names; each is a swatch with a white sign, like Monet Settings'.
        for name in ("preferences-system-network", "preferences-system-bluetooth", "preferences-desktop-display",
                     "preferences-desktop-sound", "preferences-desktop-mouse", "preferences-desktop-keyboard",
                     "preferences-desktop-wallpaper", "preferences-desktop-notification-bell", "preferences-system-time",
                     "preferences-system-users", "preferences-system-power-management", "preferences-security",
                     "preferences-desktop-locale", "preferences-desktop"):
            svg = (self.THEME / "categories/scalable" / f"{name}.svg").read_text()
            self.assertIn("data:image/png;base64,", svg, name)
            self.assertIn('stroke="#FFFFFF"', svg, name)
        # Names KDE also uses outside its settings get no painted swatch (an ink sign at most).
        for name in ("system-run", "system-log-out", "tools-check-spelling", "redshift-status-on"):
            for svg in self.THEME.glob(f"*/scalable/{name}.svg"):
                self.assertNotIn("data:image", svg.read_text(), name)


class MonetsOwn(unittest.TestCase):
    """Nothing on screen says KDE, Linux or Bazzite."""

    LOOK = (ROOT / "linux/libexec/monet-look").read_text()
    INSTALL = (ROOT / "linux/install.sh").read_text()

    def test_kdes_dark_mode_and_its_own_look_are_hidden(self):
        # More settings leaves out what Monet's light and look take care of.
        hidden = re.search(r"for kcm in (.*?); do", self.LOOK, re.S).group(1).split()
        for kcm in ("kcm_lookandfeel", "kcm_nighttime", "kcm_colors", "kcm_desktoptheme", "kcm_kwindecoration",
                    "kcm_icons", "kcm_sddm", "kcm_updates", "kcm_about-distro"):
            self.assertIn(kcm, hidden)
        for kcm in ("kcm_kscreen", "kcm_pulseaudio", "kcm_networkmanagement", "kcm_bluetooth", "kcm_mouse"):
            self.assertNotIn(kcm, hidden)
        self.assertIn('--group "KDE Control Module Restrictions" --key "$kcm" false', self.LOOK)
        self.assertIn("help_about_kde", self.LOOK)
        # The two looks are just Mist and Smoke.
        for theme, name in (("org.monet.desktop", "Mist"), ("org.monet.smoke.desktop", "Smoke")):
            meta = json.loads((PLASMA / "look-and-feel" / theme / "metadata.json").read_text())
            self.assertEqual(meta["KPlugin"]["Name"], name)

    def test_apps_go_by_plain_names(self):
        for app, name in (("org.kde.dolphin", "Files"), ("org.kde.konsole", "Terminal"), ("org.kde.gwenview", "Photos"),
                          ("org.kde.spectacle", "Screenshot")):
            self.assertIn(f'"{app}:{name}"', self.LOOK)
        self.assertIn('store=io.github.kolunmi.Bazaar\nif rename "$store" Store', self.LOOK)
        hidden = re.search(r"for app in (systemsettings .*?); do\n    hide", self.LOOK, re.S).group(1).split()
        for app in ("systemsettings", "org.kde.kinfocenter", "bazzite-documentation", "discourse", "bbrew"):
            self.assertIn(app, hidden)

    def test_bazzites_greetings_are_gone(self):
        for greeting in ("/etc/skel/.config/autostart/bazzite-portal.desktop",
                         "/etc/xdg/autostart/bazzite-announcement.desktop", "/etc/profile.d/user-motd.sh"):
            self.assertIn(greeting, self.INSTALL)
        self.assertIn("/etc/xdg/plasma-welcomerc", self.INSTALL)
        # The app menu's favorites: Monet Settings, not KDE's or Bazzite's portal.
        favorites = self.INSTALL.split("/etc/xdg/kicker-extra-favoritesrc")[0].rsplit("printf", 1)[1]
        self.assertIn("monet-settings.desktop", favorites)
        self.assertNotIn("systemsettings", favorites)
        self.assertNotIn("yafti", favorites)
        self.assertIn("favorite UnlinkResourceFromActivity systemsettings.desktop", self.LOOK)
        about = self.INSTALL.split("cat > /etc/xdg/kcm-about-distrorc")[1].split("ABOUT\n", 2)[1]
        self.assertIn("Name=Monet", about)
        self.assertIn("LogoPath=$DATADIR/icons/hicolor/scalable/apps/monet.svg", about)

    def test_kde_measures_each_new_version_afresh(self):
        # KDE keeps what it measured in an SVG by path and time, and Monet's image keeps every file's time:
        # before KWin and Plasma start, a new Monet makes it forget (or buttons and frames come out wrong).
        unit = (ROOT / "linux/systemd/user/monet-fresh.service").read_text()
        for before in ("plasma-kwin_wayland.service", "plasma-plasmashell.service"):
            self.assertIn(before, unit.split("Before=", 1)[1].splitlines()[0])
        self.assertIn("WantedBy=plasma-workspace.target", unit)
        fresh = (ROOT / "linux/libexec/monet-fresh").read_text()
        for cache in ('"$CACHE/ksvg-elements"', '"$CACHE"/plasma_theme_*.kcache', '"$CACHE/icon-cache.kcache"'):
            self.assertIn(cache, fresh)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('"$USERUNITDIR/monet-fresh.service"', install)
        self.assertEqual(install.count("monet-light-sync.path monet-fresh.service"), 2)
        self.assertIn("monet-fresh.service", (ROOT / "linux/uninstall.sh").read_text())

    def test_uninstalling_gives_kde_back(self):
        uninstall = (ROOT / "linux/uninstall.sh").read_text()
        self.assertIn("X-Monet=true", uninstall)
        self.assertIn("KDE Control Module Restrictions", uninstall)
        self.assertIn("KDE Action Restrictions", uninstall)
        # Every menu entry monet-look writes carries the mark uninstall.sh looks for.
        self.assertEqual(self.LOOK.count("X-Monet=true"), 3)

    def test_the_stores_front_page_is_monets(self):
        store = SHARE / "monet/store"
        content = (store / "content.yaml").read_text()
        banners = re.findall(r"file://@DATADIR@/monet/store/([\w-]+\.jpg)", content)
        self.assertGreaterEqual(len(set(banners)), 10)
        for banner in banners:
            self.assertTrue((store / banner).is_file(), banner)
        self.assertEqual(content.count("light-uri:"), content.count("dark-uri:"))
        main = (store / "main.yaml").read_text()
        self.assertNotIn("hooks", main)
        for text in (content, main):
            self.assertNotIn("Bazzite", text.replace("Bazzite's", ""))
            self.assertNotIn("ujust", text)
        self.assertIn("/usr/share/ublue-os/bazaar/content.yaml", self.INSTALL)

    def test_monet_settings_doesnt_say_kde(self):
        qml = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
        said = re.findall(r'i18n\("([^"]*)"', qml)
        self.assertIn("More settings ›", said)
        self.assertEqual([s for s in said if re.search(r"\b(KDE|Plasma|Linux|Bazzite)\b", s)], [])
        # Nor is KDE's About page, with its KDE, Qt and kernel versions, one click away.
        self.assertNotIn('ask("kde about")', qml)




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
        # Any desktop without them gets them once: also one laid out before Monet had widgets, or where
        # Plasma's first layout found no desktop. Every desktop, whatever its activity, and done only once
        # Plasma had one: until then, again at every sign-in, after the look.
        placing = (ROOT / "linux/libexec/monet-widgets").read_text()
        self.assertIn("desktops().forEach(", placing)
        self.assertNotIn("desktopsForActivity", placing)
        for widget in ("org.monet.placard", "org.monet.weather", "org.monet.calendar"):
            self.assertIn(f'd.addWidget("{widget}"', placing)
        self.assertIn('d.widgets("org.monet.weather").length > 0', placing)
        self.assertIn('*"desktops "[1-9]*) mkdir -p "$CONFIG/monet" && touch "$placed"', placing)
        self.assertIn("busctl --user status org.kde.plasmashell", placing)
        session = (ROOT / "linux/libexec/monet-session").read_text()
        self.assertGreater(session.index('"$LIBEXECDIR/monet-widgets"'), session.index('"$LIBEXECDIR/monet-look" --keep'))
        self.assertNotIn("widgets-placed", (ROOT / "linux/libexec/monet-look").read_text())
        self.assertIn("monet-widgets", (ROOT / "linux/install.sh").read_text())
        self.assertIn("monet-widgets", (ROOT / "linux/uninstall.sh").read_text())
        # New accounts on the image start with Monet's look, and so its layout; the look then lays the
        # panels out afresh only when they aren't Monet's islands yet.
        self.assertIn("kwriteconfig6 --file /etc/xdg/kdeglobals --group KDE --key LookAndFeelPackage org.monet.desktop",
                      (ROOT / "linux/install.sh").read_text())
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertIn('if [ "${1:-}" = --keep ] || monets_panels; then', look)

    def test_the_panel_clock_is_monets(self):
        for theme in ("org.monet.desktop", "org.monet.smoke.desktop"):
            layout = (PLASMA / "look-and-feel" / theme / "contents/layouts/org.kde.plasma.desktop-layout.js").read_text()
            self.assertIn('right.addWidget("org.monet.clock")', layout)
            self.assertNotIn("digitalclock", layout)
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertIn('panel.widgets("org.kde.plasma.digitalclock")', look)
        self.assertIn("clock-placed", look)
        self.assertIn("org.monet.clock", (ROOT / "linux/install.sh").read_text())
        self.assertIn("plasmoids/org.monet.clock", (ROOT / "linux/uninstall.sh").read_text())
        clock = (PLASMA / "plasmoids/org.monet.clock/contents/ui/main.qml").read_text(encoding="utf-8")
        for piece in ("compactRepresentation:", "fullRepresentation:", "Qt.locale().timeFormat(Locale.ShortFormat)"):
            self.assertIn(piece, clock)

    def test_files_shows_the_room_left(self):
        # Dolphin's small status bar leaves out the free space; the full one shows it.
        self.assertIn("kw_default dolphinrc General ShowStatusBar FullWidth", (ROOT / "linux/libexec/monet-look").read_text())

    def test_weather_place_is_chosen_on_the_card(self):
        # Never KDE's settings window: a search right on the widget, and the place's name for another.
        weather = (PLASMA / "plasmoids/org.monet.weather/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertNotIn('internalAction("configure")', weather)
        self.assertIn("geocoding-api.open-meteo.com/v1/search", weather)
        self.assertIn("Plasmoid.configuration.place = place.name", weather)
        self.assertIn("onClicked: root.choosing = true", weather)

    def test_calendar_days_open_with_their_notes(self):
        # A day is clicked for its page, stepped through, and written on; the notes stay in the widget's settings.
        calendar = (PLASMA / "plasmoids/org.monet.calendar/contents/ui/main.qml").read_text(encoding="utf-8")
        for piece in ("onClicked: root.pick(cell.modelData)", "onClicked: root.step(parent.modelData)",
                      "Plasmoid.configuration.notes = JSON.stringify(all)", "visible: cell.noted", "WheelHandler {",
                      "onClicked: root.pick(root.today)"):
            self.assertIn(piece, calendar)

    def test_now_playing_starts_music_and_seeks(self):
        # Nothing playing: the music apps from the helper, started by it; playing: the line seeks, the cover raises.
        playing = (PLASMA / "plasmoids/org.monet.nowplaying/contents/ui/main.qml").read_text(encoding="utf-8")
        for piece in ('helper + " music"', 'helper + " launch " + out', "row.player.position = placed(mouse.x)",
                      "row.player.updatePosition()", "onClicked: row.player.Raise()"):
            self.assertIn(piece, playing)
        quick = (ROOT / "linux/libexec/monet-quick").read_text()
        self.assertIn('elif cmd == "music":', quick)
        self.assertIn('elif cmd == "launch" and args and re.fullmatch(r"(?:[0-9a-f]{2})+", args[0]):', quick)

    def test_gallery_pictures_are_just_the_widgets(self):
        # Cut out with their shadow, no painting around them: each picture has see-through pixels.
        for widget in self.WIDGETS + ("org.monet.placard",):
            for name in ("screenshot.png", "screenshot-smoke.png"):
                png = (PLASMA / "plasmoids" / widget / "contents" / name).read_bytes()
                color_type = png[25]  # in IHDR, after the signature, the chunk's head, width, height and depth
                self.assertTrue(color_type in (4, 6) or b"tRNS" in png, f"{widget} {name}")

    def test_settings_have_their_schema(self):
        for widget in ("org.monet.weather", "org.monet.notes", "org.monet.menu", "org.monet.calendar"):
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
                # Aurorae draws a state from "<state>-center" and nothing else: without it,
                # the button is there but invisible.
                for state in ("active", "hover", "pressed", "inactive", "hover-inactive", "deactivated"):
                    self.assertIn(f"{state}-center", ids, f"{name} {button}: {state}")
                self.assertNotIn("active", ids, f"{name} {button}")

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
        # The sign-in screen's pointer too.
        self.assertIn("[Mouse]\\ncursorTheme=Monet-cursors", install)


class Sounds(unittest.TestCase):
    """Felt and glass (tools/make-sounds.py) instead of KDE's Ocean."""
    THEME = SHARE / "sounds/monet"

    def test_monet_has_the_sounds_plasma_plays(self):
        index = configparser.ConfigParser(interpolation=None)
        index.read_string((self.THEME / "index.theme").read_text())
        theme = index["Sound Theme"]
        self.assertEqual(theme["Name"], "Monet")
        self.assertEqual(theme["Directories"], "stereo")
        self.assertEqual(index["stereo"]["OutputProfile"], "stereo")
        # Ocean plays the few Monet leaves out.
        self.assertEqual(theme["Inherits"].split(","), ["ocean", "freedesktop"])
        # What Plasma 6.7 plays as it comes: signing in and out, KDE's dialogs, devices, power and the battery,
        # the volume step, the bell, the trash and a timer; and the Example KDE's sound settings preview.
        for name in ("desktop-login", "desktop-logout", "message-new-instant", "complete", "alarm-clock-elapsed",
                     "dialog-information", "dialog-question", "dialog-warning", "dialog-error", "dialog-error-serious",
                     "dialog-error-critical", "bell", "bell-window-system", "audio-volume-change", "device-added",
                     "device-removed", "power-plug", "power-unplug", "battery-caution", "battery-low", "trash-empty",
                     theme["Example"]):
            data = (self.THEME / "stereo" / f"{name}.oga").read_bytes()
            self.assertEqual(data[:4], b"OggS", name)
            self.assertIn(b"\x01vorbis", data[:64], name)

    def test_installed_removed_and_the_default(self):
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('tree "$SRC/share/sounds/monet" "$DATADIR/sounds/monet"', install)
        # For new accounts on Monet's image, and for each account as it gets Monet's look.
        self.assertIn("kwriteconfig6 --file /etc/xdg/kdeglobals --group Sounds --key Theme monet", install)
        self.assertIn("kw --file kdeglobals --group Sounds --key Theme monet",
                      (ROOT / "linux/libexec/monet-look").read_text())
        uninstall = (ROOT / "linux/uninstall.sh").read_text()
        self.assertIn('"$PREFIX/share/sounds/monet"', uninstall)
        self.assertIn("kwriteconfig6 --file kdeglobals --group Sounds --key Theme ocean", uninstall)


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
        # Bazzite's desktop signs in with Plasma Login Manager, not SDDM: its wallpaper, and its home's
        # colors, icons, style and pointer, linked afresh at every boot.
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn("> /usr/lib/plasmalogin/defaults.conf", install)
        self.assertIn("[Greeter][Wallpaper][org.kde.image][General]", install)
        self.assertIn('cat "$SRC/share/color-schemes/MonetDark.colors"', install)
        tmp = install.split("/usr/lib/tmpfiles.d/monet-greeter.conf <<TMP\n")[1].split("TMP\n")[0]
        for config in ("plasmarc", "kdeglobals", "kcminputrc"):
            self.assertIn(f"L+ /var/lib/plasmalogin/.config/{config} ", tmp)
        self.assertNotIn("sddm", install.lower())


class EverydayScreens(unittest.TestCase):
    """Monet's menu, the restart and shut-down screen, the password prompt and the widget gallery."""

    def test_the_menu_is_monets(self):
        folder = PLASMA / "plasmoids/org.monet.menu"
        meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
        # The Meta key opens the panel widget that says it's the app menu.
        self.assertIn("org.kde.plasma.launchermenu", meta["X-Plasma-Provides"])
        self.assertEqual(meta["KPlugin"]["Icon"], "monet")
        menu = (folder / "contents/ui/main.qml").read_text(encoding="utf-8")
        # KDE's own models: the same pins, search, recent files and launching as KDE's menu.
        for piece in ("Kicker.RootModel", "Kicker.RunnerModel", "Kicker.RecentUsageModel", "KICKER_ALL_MODEL",
                      'initForClient("org.monet.menu.favorites.instance-"', "portOldFavorites(",
                      "model.trigger(index", "addFavorite(", "removeFavorite("):
            self.assertIn(piece, menu)
        # Lock, the power sign (Monet's restart and shut-down screen) and Accounts in Monet Settings
        # (KDE's page without Quick Settings).
        for piece in ("sessions.lock()", "sessions.requestLogoutPrompt()", '"@LIBEXECDIR@/monet-quick open users"'):
            self.assertIn(piece, menu)
        self.assertIn("users", quick_helper().PAGES)
        self.assertIn('"users": "kcm_users"', (ROOT / "linux/libexec/monet-quick").read_text())
        for theme in ("org.monet.desktop", "org.monet.smoke.desktop"):
            layout = (PLASMA / "look-and-feel" / theme / "contents/layouts/org.kde.plasma.desktop-layout.js").read_text()
            self.assertIn('left.addWidget("org.monet.menu")', layout)
            self.assertNotIn("kickoff", layout)
        # Kept panels get it too, once, where KDE's menu was and with its shortcut.
        look = (ROOT / "linux/libexec/monet-look").read_text()
        swap = look.split('menu="$CONFIG/monet/menu-placed"')[1].split("\nfi\n")[0]
        for piece in ('panel.widgets("org.kde.plasma.kickoff")', 'panel.addWidget("org.monet.menu")', "kickoff.remove()",
                      "menu.index = place", "menu.globalShortcut = keys", 'touch "$menu"'):
            self.assertIn(piece, swap)
        self.assertIn("org.monet.menu", (ROOT / "linux/install.sh").read_text())
        self.assertIn("plasmoids/org.monet.menu", (ROOT / "linux/uninstall.sh").read_text())

    def test_restart_screen_is_monets_in_both_lights(self):
        logout = (SHARE / "monet/logout/Logout.qml").read_text(encoding="utf-8")
        # KDE's logout greeter connects these by name, and hands over these as context.
        for signal in ("logoutRequested()", "haltRequested()", "haltUpdateRequested()", "suspendRequested(int spdMethod)",
                       "rebootRequested()", "rebootRequested2(int opt)", "rebootUpdateRequested()", "cancelRequested()",
                       "lockScreenRequested()", "cancelSoftwareUpdateRequested()"):
            self.assertIn(f"signal {signal}", logout)
        for context in ("sdtype", "ShutdownType.ShutdownTypeDefault", "ShutdownType.ShutdownTypeReboot",
                        "ShutdownType.ShutdownTypeHalt", "maysd", "canLogout", "spdMethods.SuspendState",
                        "softwareUpdatePending", "rebootToFirmwareSetup", "rebootToBootLoaderEntry"):
            self.assertIn(context, logout)
        # One countdown for all screens: a key on any of them stops it everywhere.
        self.assertIn('import "timer.js" as AutoTriggerTimer', logout)
        timer = (SHARE / "monet/logout/timer.js").read_text()
        for function in ("addCancelAutoTriggerCallback", "cancelAutoTrigger"):
            self.assertIn(f"function {function}(", timer)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('tree "$SRC/share/monet/logout" "$DATADIR/plasma/look-and-feel/$theme/contents/logout"', install)

    def test_password_prompt_is_monets_inside_kdes_agent(self):
        page = (ROOT / "image/password/QuickAuthDialog.qml").read_text(encoding="utf-8")
        # What the agent's C++ sets, reads, connects to and calls by name; its root is a window.
        for part in ("property alias password:", "property int inlineMessageType", "property string inlineMessageText",
                     "property alias identitiesModel:", "property alias identitiesCurrentIndex:", "property alias selectedIdentity:",
                     "property string mainText", "property string descriptionString", "property string descriptionActionId",
                     "property string descriptionVendorName", "property string descriptionVendorUrl",
                     "signal accept()", "signal reject()", "signal userSelected()",
                     "function authenticationFailure()", "function request()", "IdentitiesModel {}"):
            self.assertIn(part, page)
        self.assertRegex(page, r"(?m)^Window \{")
        # Built against the image's own Plasma, with KDE's page kept in for when Monet's can't load.
        build = (ROOT / "image/password/build.sh").read_text()
        self.assertIn("rpm -q --qf '%{version}' polkit-kde", build)
        self.assertIn('--branch "v$version"', build)
        self.assertIn("mv qml/QuickAuthDialog.qml qml/KdeQuickAuthDialog.qml", build)
        self.assertIn('grep -q \'engine->load("qrc:/qml/KdeQuickAuthDialog.qml")\' QuickAuthDialog.cpp', build)
        containerfile = (ROOT / "image/Containerfile").read_text()
        self.assertIn("bazzite-nvidia-open:stable AS password", containerfile)
        self.assertIn("sh /src/password/build.sh /out || rm -rf /out/*", containerfile)
        self.assertIn("COPY --from=password /out /tmp/monet/password", containerfile)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('if [ -x "$SRC/password/monet-password" ]; then', install)
        self.assertIn('"$USERUNITDIR/plasma-polkit-agent.service.d/monet.conf"', install)

    def test_widget_gallery_is_monets_and_always_opens(self):
        explorer = SHARE / "monet/explorer"
        entry = (explorer / "WidgetExplorer.qml").read_text(encoding="utf-8")
        # What Plasma's Desktop.qml gives and reads; Monet's gallery, or KDE's if Monet's can't load.
        for part in ("property QtObject containment", "property PlasmaCore.Dialog sidePanel", "readonly property bool preventWindowHide",
                     "readonly property bool outputOnly", "signal closed()", 'Qt.resolvedUrl("MonetWidgetExplorer.qml")',
                     "monet.status === Loader.Error", 'Qt.resolvedUrl("KdeWidgetExplorer.qml")'):
            self.assertIn(part, entry)
        gallery = (explorer / "MonetWidgetExplorer.qml").read_text(encoding="utf-8")
        for part in ("root.widgetExplorer", "pendingUninstallTimer.running", "explorer.addApplet(pluginName)",
                     "explorer.removeAllInstances(pluginName)", '"text/x-plasmoidservicename"', "widgetsModel.searchTerm",
                     "KItemModels.KSortFilterProxyModel",
                     # Done ends the editing: the desktop comes back to full size.
                     "containment.corona.editMode = false"):
            self.assertIn(part, gallery)
        # Its lists name every Monet widget once: the desktop's and the bar's.
        lists = re.search(r'mineIds: forBar \? "([^"]+)" : "([^"]+)"', gallery)
        named = lists.group(1).split("|") + lists.group(2).split("|")
        widgets = sorted(f.name.removeprefix("org.monet.") for f in (PLASMA / "plasmoids").iterdir())
        self.assertEqual(sorted(named), widgets)
        # Every one of them brings a picture of itself, in mist and in smoke.
        for name in named:
            for picture in ("screenshot.png", "screenshot-smoke.png"):
                self.assertTrue((PLASMA / "plasmoids" / f"org.monet.{name}" / "contents" / picture).is_file(), (name, picture))
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn("explorer=/usr/share/plasma/shells/org.kde.plasma.desktop/contents/explorer", install)
        self.assertIn('mv "$explorer/WidgetExplorer.qml" "$explorer/KdeWidgetExplorer.qml"', install)
        for name in ("MonetWidgetExplorer.qml", "WidgetExplorer.qml"):
            self.assertIn(f'"$SRC/share/monet/explorer/{name}" "$explorer/{name}"', install)

    def test_edit_mode_is_monets_and_light(self):
        editmode = SHARE / "monet/editmode"
        entry = (editmode / "DesktopEditMode.qml").read_text(encoding="utf-8")
        # Desktop.qml places the shrunken desktop by these; Monet's, or KDE's if Monet's can't load.
        for part in ("property real centerX", "property real centerY", 'Qt.resolvedUrl("MonetDesktopEditMode.qml")',
                     "monet.status === Loader.Error", 'Qt.resolvedUrl("KdeDesktopEditMode.qml")'):
            self.assertIn(part, entry)
        page = (editmode / "MonetDesktopEditMode.qml").read_text(encoding="utf-8")
        for part in ("containment.plasmoid.corona.editMode", "editModeRect", "containmentParent.scaleFactor",
                     'internalAction("add widgets")', "sidePanel.visible"):
            self.assertIn(part, page)
        # No blur of the whole desktop at every change: a wash instead.
        self.assertNotIn("blurEnabled", page)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn("views=/usr/share/plasma/shells/org.kde.plasma.desktop/contents/views", install)
        self.assertIn('mv "$views/DesktopEditMode.qml" "$views/KdeDesktopEditMode.qml"', install)
        for name in ("MonetDesktopEditMode.qml", "DesktopEditMode.qml"):
            self.assertIn(f'"$SRC/share/monet/editmode/{name}" "$views/{name}"', install)

    def test_adding_widgets_is_easy_to_find(self):
        # The desktop's right-click menu offers Add or Manage Widgets (KDE hides it there), set before
        # Plasma starts, and again after a fresh layout forgot it.
        fresh = (ROOT / "linux/libexec/monet-fresh").read_text()
        self.assertIn('--group ActionPlugins --group 0 --group "RightButton;NoModifier" --key "add widgets" true', fresh)
        self.assertIn('--key "RightButton;NoModifier" org.kde.contextmenu', fresh)
        self.assertLess(fresh.index("add widgets"), fresh.index('[ "$(cat "$stamp" 2>/dev/null)" = "$version" ] && exit 0'))
        look = (ROOT / "linux/libexec/monet-look").read_text()
        reset = look.split("--resetLayout >/dev/null 2>&1", 1)[1].split("\nfi\n", 1)[0]
        self.assertIn('rm -f "$CONFIG/monet/menu-add-widgets"', reset)
        # Monet Settings' Light & Wallpaper opens the gallery too.
        settings = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
        self.assertIn('sheet.ask("widgets")', settings)
        quick = (ROOT / "linux/libexec/monet-quick").read_text()
        self.assertIn('elif cmd == "widgets":', quick)
        self.assertIn('"org.kde.PlasmaShell", "toggleWidgetExplorer"', quick)


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

    def test_date_time_and_accounts_are_monets(self):
        qml = (self.QUICK / "MonetSettings.qml").read_text(encoding="utf-8")
        for page in ("datetime", "users"):
            entry = re.search(r'\{ id: "%s",[^}]*\}' % page, qml).group(0)
            self.assertNotIn("kde:", entry)
            # KDE's page stays one click away, for what Monet's leaves out.
            self.assertIn(f'sheet.ask("kde {page}")', qml)
        helper = quick_helper()
        for command in ("time", "zones", "zone NAME", "ntp on|off", "time-locale LOCALE|region", "accounts",
                        "name NAME", "pad", "password OLD NEW"):
            self.assertRegex(helper.__doc__, rf"monet-quick {re.escape(command)}\s")
        for asked in ('ask("time"', 'ask("zones"', 'ask("zone " + zone', 'ask("ntp " + ', 'ask("time-locale " + ',
                      'ask("accounts"', 'ask("name " + hex(name)', 'ask("pad"', 'ask("password " + sealed.join(" ")'):
            self.assertIn(asked, qml)
        # 24-hour time is what Monet's clocks follow: the locale's short time.
        for clock in (PLASMA / "plasmoids/org.monet.clock/contents/ui/main.qml", SHARE / "monet/lockscreen/MonetLockScreen.qml"):
            self.assertIn("Qt.locale().timeFormat(Locale.ShortFormat)", clock.read_text(encoding="utf-8"))

    def test_power_input_notifications_and_apps_are_monets(self):
        qml = (self.QUICK / "MonetSettings.qml").read_text(encoding="utf-8")
        for page in ("input", "power", "notifications", "apps"):
            entry = re.search(r'\{ id: "%s",[^}]*\}' % page, qml).group(0)
            self.assertNotIn("kde:", entry)
            self.assertIn(f'sheet.ask("kde {page}")', qml)
        helper = quick_helper()
        for command in ("power", "power-time", "power-button|power-lid", "power-mode", "input", "pointer", "layouts-known",
                        "layouts", "notify", "notify-rule", "notify-place", "notify-time", "notify-app", "defaults", "default"):
            self.assertRegex(helper.__doc__, rf"monet-quick {re.escape(command)}\s")
        # What the pages offer is what the helper takes: times, what the buttons do, popups.
        times = lambda name: [int(s) for s in re.search(name + r": \[([\d, ]+)\]\.map", qml).group(1).split(",")]
        self.assertTrue(set(times("screenTimes")) <= set(helper.SCREEN_TIMES))
        self.assertTrue(set(times("sleepTimes")) <= set(helper.SLEEP_TIMES))
        offered = [[int(v) for v in re.findall(r"\[(\d+), i18n", found)]
                   for found in re.findall(r"options: (\[\[\d+, i18n.*)", qml)]
        self.assertIn(sorted(helper.BUTTON_ACTIONS), [sorted(o) for o in offered])
        self.assertIn(sorted(helper.LID_ACTIONS), [sorted(o) for o in offered])
        places = re.search(r'options: (\[\["clock".*)', qml).group(1)
        self.assertEqual(set(re.findall(r'\["(\w+)", i18n', places)), set(helper.POPUP_PLACES))
        self.assertIn("[3, 5, 10].map(", qml)
        self.assertEqual(helper.POPUP_TIMES, (3, 5, 10))

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
        for script in ("monet-session", "monet-look", "monet-light", "monet-fresh", "monet-widgets"):
            subprocess.run(["bash", "-n", str(ROOT / "linux/libexec" / script)], check=True)
        subprocess.run(["sh", "-n", str(ROOT / "image/password/build.sh")], check=True)

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

    def test_quick_reads_layouts_notifications_and_default_apps(self):
        quick = quick_helper()
        listing = "! model\n  pc104  Generic 104-key PC\n\n! layout\n  us   English (US)\n  se   Swedish\n\n! variant\n  dvorak  us: English (Dvorak)\n"
        self.assertEqual(quick.known_layouts(listing), [("us", "English (US)"), ("se", "Swedish")])
        rc = "[Applications][discord]\nSeen=true\nShowPopups=false\n\n[Applications][org.kde.dolphin]\nSeen=true\n\n[Services][plasma_workspace]\nShowPopups=false\n"
        self.assertEqual(quick.notified_apps(rc), {"discord": False, "org.kde.dolphin": True})
        # A default set keeps every other line of mimeapps.list.
        before = "[Added Associations]\nimage/png=a.desktop;\n\n[Default Applications]\ntext/plain=b.desktop;\naudio/mpeg=c.desktop;\n"
        after = quick.with_defaults(before, {"audio/mpeg": "org.kde.elisa.desktop", "audio/flac": "org.kde.elisa.desktop"})
        for line in ("image/png=a.desktop;", "text/plain=b.desktop;", "audio/mpeg=org.kde.elisa.desktop;", "audio/flac=org.kde.elisa.desktop;"):
            self.assertIn(line, after)
        self.assertNotIn("c.desktop", after)
        self.assertEqual(quick.with_defaults("", {"inode/directory": "org.kde.dolphin.desktop"}),
                         "[Default Applications]\ninode/directory=org.kde.dolphin.desktop;\n")
        browser = quick.desktop_entry("[Desktop Entry]\nType=Application\nName=Firefox\nMimeType=text/html;x-scheme-handler/http;x-scheme-handler/https;\n")
        viewer = quick.desktop_entry("[Desktop Entry]\nType=Application\nName=Viewer\nMimeType=text/html;\n")
        found = quick.takers([("firefox.desktop", browser), ("viewer.desktop", viewer)], "browser")
        self.assertEqual([app["id"] for app in found], ["firefox.desktop"])
        self.assertEqual(found[0]["types"], ["x-scheme-handler/https", "x-scheme-handler/http", "text/html"])

    def test_quick_tells_mice_from_touchpads(self):
        quick = quick_helper()
        self.assertEqual(quick.device_kind({"pointer": True, "supportsPointerAcceleration": True}), "mouse")
        self.assertEqual(quick.device_kind({"touchpad": True, "pointer": True}), "touchpad")
        self.assertEqual(quick.device_kind({"keyboard": True, "pointer": True}), "")  # a keyboard's media keys
        touchpad = {"touchpad": True, "pointerAcceleration": 0.2, "supportsPointerAcceleration": True, "tapFingerCount": 3,
                    "tapToClick": False, "naturalScroll": True, "supportsNaturalScroll": True}
        self.assertEqual(quick.pointer_state({"event5": touchpad}),
                         {"mouse": None, "touchpad": {"speed": 60, "natural": True, "tap": False}})

    def test_quick_settings_commands_take_only_their_own_values(self):
        from unittest import mock
        quick = quick_helper()
        with mock.patch.object(quick, "kwrite") as kwrite, mock.patch.object(quick, "run") as run, \
                mock.patch("sys.stderr"):
            for argv in (["power-time", "ac", "screen", "123"], ["power-time", "home", "sleep", "900"], ["power-button", "4"],
                         ["power-lid", "8"], ["power-mode", "turbo"], ["layouts", "us;rm -rf ~"], ["notify-place", "left"],
                         ["notify-time", "7"], ["notify-app", "zz", "on"], ["default", "browser", "zz"], ["default", "games", "6161"]):
                quick.main(argv)
            kwrite.assert_not_called()
            run.assert_not_called()

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

    def test_quick_finds_the_apps_that_play_music(self):
        # Now Playing's "Play something with": players for music, the PC's default first, the nearest
        # copy of an entry deciding (a hidden copy in the home folder hides the system's).
        quick = quick_helper()
        entry = quick.desktop_entry("[Desktop Entry]\nType=Application\nName=Elisa\nIcon=elisa\n"
                                    "Categories=Qt;KDE;AudioVideo;Audio;Player;\n\n[Desktop Action play]\nName=Play\n")
        self.assertEqual((entry["Name"], entry["Icon"]), ("Elisa", "elisa"))
        app = "[Desktop Entry]\nType=Application\nName={}\nCategories={}\n"
        entries = [
            ("com.spotify.Client.desktop", quick.desktop_entry(app.format("Spotify", "Audio;Music;Player;AudioVideo;"))),
            ("org.kde.elisa.desktop", entry),
            ("org.kde.haruna.desktop", quick.desktop_entry(app.format("Haruna", "Qt;KDE;AudioVideo;Video;Player;"))),
            ("hidden.desktop", quick.desktop_entry(app.format("Hidden", "Audio;Player;") + "NoDisplay=true\n")),
            ("hidden.desktop", quick.desktop_entry(app.format("Hidden", "Audio;Player;"))),
        ]
        found = quick.music_apps(entries, default="org.kde.elisa.desktop")
        self.assertEqual([a["id"] for a in found], ["org.kde.elisa.desktop", "com.spotify.Client.desktop"])
        self.assertEqual([a["name"] for a in quick.music_apps(entries)], ["Elisa", "Spotify"])
        # An app starts only by an entry's file name, never anything else.
        from unittest import mock
        with mock.patch.object(quick.subprocess, "Popen") as popen:
            for bad in ("../../bin/sh.desktop", "x.desktop; rm -rf ~", "elisa"):
                quick.launch(bad)
            popen.assert_not_called()

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

    def test_quick_reads_the_clock(self):
        from unittest import mock
        quick = quick_helper()
        show = "Timezone=Europe/Stockholm\nLocalRTC=no\nCanNTP=yes\nNTP=yes\nNTPSynchronized=yes\n"
        formats = {"LANG": "en_US.UTF-8", "LC_TIME": "en_GB.UTF-8"}
        with mock.patch.object(quick, "kread", lambda file, group, key, default="": formats.get(key, default)):
            self.assertEqual(quick.clock(show), {"zone": "Europe/Stockholm", "ntp": True,
                                                 "locale": "en_GB.UTF-8", "region": "en_US.UTF-8"})
            del formats["LC_TIME"]
            self.assertEqual(quick.clock(show)["locale"], "en_US.UTF-8")
        # Without a time service there's nothing to switch.
        self.assertIsNone(quick.clock("Timezone=UTC\nCanNTP=no\nNTP=no\n")["ntp"])

    def test_quick_takes_only_zones_and_locales_it_knows(self):
        import contextlib
        import io
        from unittest import mock
        quick = quick_helper()
        done = []

        def run(*args, **kw):
            done.append(args)
            return "Europe/Stockholm\nUTC\n" if args[1:] == ("list-timezones",) else ""
        with mock.patch.object(quick, "run", run), contextlib.redirect_stderr(io.StringIO()):
            for argv in (["zone", "Europe/Stockholm"], ["zone", "Mars/Olympus_Mons"], ["time-locale", "en_GB.UTF-8"],
                         ["time-locale", "region"], ["time-locale", "en_GB.UTF-8; rm -rf ~"], ["time-locale", "../x"]):
                quick.main(argv)
        changes = [args for args in done if args[1:] != ("list-timezones",)]
        self.assertEqual(changes, [
            ("timedatectl", "set-timezone", "Europe/Stockholm"),
            ("kwriteconfig6", *quick.TIME_LOCALE, "en_GB.UTF-8"),
            ("kwriteconfig6", *quick.TIME_LOCALE, "--delete"),
        ])
        self.assertEqual(quick.TIME_LOCALE, ("--file", "plasma-localerc", "--group", "Formats", "--key", "LC_TIME"))

    def test_quick_knows_the_people_on_this_pc(self):
        from unittest import mock
        quick = quick_helper()
        found = {"Uid": {"type": "t", "data": 1000}, "UserName": {"type": "s", "data": "claude"},
                 "RealName": {"type": "s", "data": " Claude Monet "}, "AccountType": {"type": "i", "data": 1},
                 "IconFile": {"type": "s", "data": "/nonexistent/claude"}}
        self.assertEqual(quick.person(found, 1000),
                         {"login": "claude", "name": "Claude Monet", "picture": "", "admin": True, "you": True})
        camille = quick.person({"Uid": {"data": 1001}, "UserName": {"data": "camille"}, "AccountType": {"data": 0}}, 1000)
        self.assertEqual((camille["name"], camille["admin"], camille["you"]), ("camille", False, False))
        # Your name goes to AccountsService as it is, unless the password file couldn't keep it.
        calls = []
        with mock.patch.object(quick, "your_account", lambda: "/org/freedesktop/Accounts/User1000"), \
                mock.patch.object(quick, "run", lambda *args, **kw: calls.append(args) or ""):
            self.assertTrue(quick.set_name(" Claude Monet "))
            for name in ("", "   ", "Monet, Claude", "Claude: Monet", "Claude\nMonet", "C" * 65):
                self.assertFalse(quick.set_name(name), name)
        self.assertEqual(calls, [("busctl", "call", "org.freedesktop.Accounts", "/org/freedesktop/Accounts/User1000",
                                  "org.freedesktop.Accounts.User", "SetRealName", "s", "Claude Monet")])

    def test_passwords_come_sealed(self):
        # A command line is anyone's to read: Monet Settings seals passwords with a pad from the helper.
        quick = quick_helper()
        pad = bytes(range(7, 135))
        secret = "Café $(rf) '☀'"
        sealed = bytes(a ^ b for a, b in zip(secret.encode(), pad)).hex()
        self.assertEqual(quick.unseal(sealed, pad), secret)
        self.assertIsNone(quick.unseal("00" * 129, pad))
        qml = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
        self.assertNotRegex(qml, r'"password " \+ (sheet\.)?hex\(')

    @unittest.skipUnless(sys.platform.startswith("linux"), "passwd answers in a Linux terminal")
    def test_quick_changes_a_password_with_passwd(self):
        import os
        import tempfile
        from unittest import mock
        quick = quick_helper()
        with tempfile.TemporaryDirectory() as tmp:
            # A passwd that asks the way Fedora's does.
            fake = Path(tmp) / "passwd"
            fake.write_text(
                "#!/bin/sh\necho 'Changing password for user claude.'\n"
                "printf 'Current password: '; read old\n"
                "[ \"$old\" = Giverny ] || { echo 'passwd: Authentication token manipulation error'; exit 1; }\n"
                "printf 'New password: '; read new\n"
                "[ ${#new} -ge 8 ] || { echo 'BAD PASSWORD: The password is shorter than 8 characters'; exit 1; }\n"
                "printf 'Retype new password: '; read again\n"
                "[ \"$new\" = \"$again\" ] && echo 'passwd: all authentication tokens updated successfully.'\n")
            fake.chmod(0o755)
            with mock.patch.dict(os.environ, {"PATH": tmp + os.pathsep + os.environ["PATH"]}):
                self.assertEqual(quick.change_password("Giverny", "Water lilies"), {"ok": True})
                self.assertEqual(quick.change_password("Argenteuil", "Water lilies"),
                                 {"ok": False, "message": "That isn't your current password."})
                self.assertEqual(quick.change_password("Giverny", "lilies"),
                                 {"ok": False, "message": "The password is shorter than 8 characters."})
            # The pad: only yours to read, and only once.
            with mock.patch.object(quick, "PAD", Path(tmp) / "pad"):
                pad = bytes.fromhex(quick.make_pad())
                self.assertEqual((Path(tmp) / "pad").stat().st_mode & 0o777, 0o600)
                self.assertEqual(quick.take_pad(), pad)
                self.assertEqual(quick.take_pad(), b"")

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
