"""Checks for Monet's look: the Plasma pieces, the app style and the paintings.

    python3 -m unittest discover -s tests
"""

import base64
import configparser
import importlib.machinery
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
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
            + list((SHARE / "monet/games").glob("*.qml"))
            + list((SHARE / "monet/settings-app").glob("*.qml"))
            + list((ROOT / "image/password").glob("*.qml")) + list((ROOT / "setup/qml").rglob("*.qml")))
PLASMA = SHARE / "plasma"
GAMES_APP = SHARE / "monet/games/Games.qml"
# Settings, an app of its own since 0.9.4 (monet-settings); a sheet of Quick Settings before.
SETTINGS_QML = SHARE / "monet/settings-app/MonetSettings.qml"


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
            meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
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
        # Item's FINAL properties (Qt 6): declaring one again stops the whole file loading,
        # as 0.9.0's wallpaper did with "focus" (a black desktop and lock screen).
        final = ("activeFocus|activeFocusOnTab|anchors|baseline|bottom|childrenRect|focus|height|"
                 "horizontalCenter|layer|left|opacity|parent|right|top|transform|verticalCenter|"
                 "visible|width|x|y|z")
        for qml in qml_files():
            text = qml.read_text()
            self.assertNotRegex(text, r"property \w+ (state|on)\b", qml.name)
            self.assertNotRegex(text, rf"(?m)^\s*(readonly |required |default )*property [\w.<>]+ ({final})\b", qml.name)


class PlasmaStyle(unittest.TestCase):
    STYLES = [PLASMA / "desktoptheme/monet", PLASMA / "desktoptheme/monet-matte", PLASMA / "desktoptheme/monet-solid"]
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
        # An opaque panel (Plasma's own setting) is drawn from solid/;
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
    THEMES = ("Monet", "MonetDark", "MonetMatte", "MonetDarkMatte", "MonetSolid", "MonetDarkSolid")

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

    def test_series_each_in_four_lights(self):
        # Water Lilies and Haystacks beside The Hours, painted by the same tool, chosen in Settings.
        quick = quick_helper()
        # "seasons" hangs one of the four a season: no painting of its own, but a preview. "photo"
        # is a photo of yours, painted (monet-paint): its preview is its own.
        self.assertEqual(quick.SERIES, ("hours", "lilies", "haystacks", "magpie", "seasons", "photo"))
        painted = quick.SERIES[:4]
        for series in painted:
            for hour in ("dawn", "day", "dusk", "night"):
                self.assertGreater((self.WALL / series / f"{hour}.jpg").stat().st_size, 100_000, f"{series} {hour}")
        for series in quick.SERIES[:5]:
            self.assertTrue((SHARE / f"monet/settings/series-{series}.png").is_file(), series)
        tool = (ROOT / "tools/make-paintings.py").read_text(encoding="utf-8")
        for series in painted:
            self.assertIn(f'    "{series}": dict(hours=', tool)
        wallpaper = (PLASMA / "wallpapers/org.monet.hours/contents/ui/main.qml").read_text()
        self.assertIn('["hours", "lilies", "haystacks", "magpie"].indexOf(root.configuration.Series)', wallpaper)
        self.assertIn('"file://@DATADIR@/wallpapers/Monet/contents/" + series + "/"', wallpaper)
        self.assertIn('<entry name="Series" type="String">',
                      (PLASMA / "wallpapers/org.monet.hours/contents/config/main.xml").read_text())
        self.assertIn('<entry name="Series" type="String">',
                      (PLASMA / "plasmoids/org.monet.placard/contents/config/main.xml").read_text())
        light = (ROOT / "linux/libexec/monet-light").read_text()
        self.assertIn("--group General --key Series \"$set\"", light)  # the lock screen
        self.assertIn("d.writeConfig('Series', '$set');", light)        # each desktop
        self.assertIn("w.writeConfig('Series', '$set');", light)        # each placard
        qml = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('["lilies", i18n("Water Lilies"), i18n("The pond at Giverny")]', qml)
        self.assertIn('ask("series " + name)', qml)

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
    settings in one JSON file, so monet-light can run without Plasma. Each
    change is written out as KDE's own files too, since monet-light reads those."""

    TOOL = """#!/usr/bin/env python3
import fcntl, json, os, sys
# One at a time: monet-light writes its files side by side, and here they share one store.
lock = open(os.path.join(os.environ["FAKE_KDE"], "settings.lock"), "w")
fcntl.flock(lock, fcntl.LOCK_EX)
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
    if os.path.isabs(opt("--file")):
        data.setdefault("__paths", {})[os.path.basename(opt("--file"))] = opt("--file")
json.dump(data, open(store, "w"))
files = {}
for key, value in data.items():
    if not key.startswith("__"):
        file, group, name = key.split("|")
        files.setdefault(file, {}).setdefault(group, {})[name] = value
for file, groups in files.items():
    path = data.get("__paths", {}).get(file) or os.path.join(os.environ["XDG_CONFIG_HOME"], file)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as out:
        out.write("".join("[%s]\\n%s\\n" % (g, "".join("%s=%s\\n" % kv for kv in keys.items())) for g, keys in groups.items()))
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
        """As someone would: through KDE's tool, so its files have it too."""
        file, groups, name = key.split("|")
        path = self.settings().get("__paths", {}).get(file, file)
        subprocess.run([str(self.dir / "bin/kwriteconfig6"), "--file", path,
                        *[a for g in groups.split("][") for a in ("--group", g)], "--key", name, value],
                       env=self.env, check=True, timeout=30)

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
        # The painting keeps following the whole day (only the colors are Smoke's).
        self.assertEqual(kde.settings()[Light.PAINTING], "hours")
        # KDE's Automatic is Follow the hours, and KDE's own switching stays off.
        kde.set("kdeglobals|KDE|AutomaticLookAndFeel", "true")
        kde.light("sync")
        self.assertEqual(kde.choice(), "hours")
        self.assertEqual(kde.settings()["kdeglobals|KDE|AutomaticLookAndFeel"], "false")
        self.assertEqual(kde.settings()[Light.PAINTING], "hours")

    PAINTING = "kscreenlockerrc|Greeter][Wallpaper][org.monet.hours][General|Painting"

    def test_the_painting_goes_with_the_light(self):
        kde = FakeKDE(self.tmp.name, hour=12)
        # The Hours on: the painting goes through the whole day, dawn to night, whatever Mist or
        # Smoke the colors keep (people wanted the day and seasons with their colors). Plasma
        # hears of it once: reloading the painting at every switch held up the bar and Settings.
        for light in ("mist", "smoke", "hours"):
            kde.light("set", light)
            self.assertEqual(kde.settings()[self.PAINTING], "hours")
        self.assertEqual(kde.told_plasma().count("d.writeConfig('Painting', 'hours')"), 1)
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
        self.assertIn('"paint" if args[0] in ("hours", "weather")', quick)
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
        # KDE's own for GTK 4 also imports its window shape (no newline at its end, as KDE writes it).
        gtk4 = Path(self.tmp.name) / "noon/config/gtk-4.0/gtk.css"
        gtk4.parent.mkdir(parents=True)
        gtk4.write_text("@import 'colors.css';\n@import 'kde_window_geometry.css';")
        subprocess.run(["bash", str(light), "apply"], env=noon.env, check=True, timeout=30)
        self.assertIn("Mist", sheet.read_text().splitlines()[0])
        made = gtk4.read_text()
        self.assertIn("Mist", made.splitlines()[0])
        self.assertIn("@import 'colors.css';\n@import 'kde_window_geometry.css';\n", made)   # KDE's shape kept
        self.assertIn("windowcontrols > button > image", made)
        # A person can customize a generated sheet too; its header is not consent
        # to replace their additions on the next sign-in or upgrade.
        custom = made + "window { padding: 9px; }\n"
        gtk4.write_text(custom)
        subprocess.run(["bash", str(light), "apply"], env=noon.env, check=True, timeout=30)
        self.assertEqual(gtk4.read_text(), custom)

    def test_a_custom_terminal_color_scheme_survives_light_changes(self):
        kde = FakeKDE(self.tmp.name, hour=21)
        data = Path(self.tmp.name) / "data"
        profile = data / "konsole/Monet.profile"
        profile.parent.mkdir(parents=True)
        profile.write_text("[Appearance]\nColorScheme=MyTerminalColors\n")
        kde.env["XDG_DATA_HOME"] = str(data)
        kde.light("apply")
        self.assertEqual(profile.read_text(), "[Appearance]\nColorScheme=MyTerminalColors\n")

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
        # Matte glass (Settings' Glass slider), with KWin's blur stronger and grained.
        prefs.write_text('{"glass": "matte"}')
        kde.light("apply")
        self.assertEqual(kde.settings()[frame], "__aurorae__svg__MonetSmokeMatte")
        self.assertEqual(kde.settings()["kwinrc|Effect-blur|NoiseStrength"], "5")
        prefs.write_text('{"glass": "clear"}')
        kde.light("apply")
        self.assertEqual(kde.settings()[frame], "__aurorae__svg__MonetSmoke")
        self.assertEqual(kde.settings()["kwinrc|Effect-blur|BlurStrength"], "3")
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
        # A theme applied from KDE's settings (its Light and Dark buttons) keeps Monet's glass app
        # style and The Hours. Naming no style, KDE wrote Qt's plain Windows style as the default
        # and dropped the account's: every window and menu turned plain (found by the owner).
        for theme in ("org.monet.desktop", "org.monet.smoke.desktop"):
            defaults = (self.LNF / theme / "contents/defaults").read_text()
            self.assertIn("[kdeglobals][KDE]\nwidgetStyle=kvantum\n", defaults)
            self.assertNotIn("[Wallpaper]", defaults)

    def test_the_glass_app_style_comes_back(self):
        # Whatever took it, monet-light puts it back: at every apply, and right after KDE's
        # buttons (sync), unless the account set a style of its own.
        light = (ROOT / "linux/libexec/monet-light").read_text()
        self.assertIn("keep_app_style\n    light=\"$(now)\"", light)
        self.assertIn("    # Whatever KDE's buttons picked, the glass app style stays.\n    keep_app_style", light)
        self.assertIn("busctl --user emit /KGlobalSettings org.kde.KGlobalSettings notifyChange ii 2 0", light)
        # Asked as one `ls` of both library folders, Kvantum was never found on Fedora (lib64 only).
        look = (ROOT / "linux/libexec/monet-look").read_text()
        for script in (light, look):
            self.assertNotIn("if ls /usr/lib*/qt6/plugins/styles/libkvantum.so /usr/lib*/*/", script)
            self.assertNotIn("ls /usr/lib*/qt6/plugins/styles/libkvantum.so /usr/lib*/*/qt6/plugins/styles/libkvantum.so >/dev/null", script)
        self.assertIn("if kvantum_here; then", look)
        if not (shutil.which("bash") and sys.platform != "win32"
                and any(Path(p).exists() for p in ("/usr/lib64/qt6/plugins/styles/libkvantum.so",
                                                   "/usr/lib/qt6/plugins/styles/libkvantum.so",
                                                   "/usr/lib/x86_64-linux-gnu/qt6/plugins/styles/libkvantum.so"))):
            self.skipTest("needs Kvantum")
        with tempfile_dir() as tmp:
            kde = FakeKDE(tmp, hour=12)
            defaults = Path(tmp) / "config/kdedefaults/kdeglobals"
            defaults.parent.mkdir(parents=True)
            defaults.write_text("[KDE]\nwidgetStyle=Windows\n")
            kde.light("sync")
            self.assertEqual(kde.settings()["kdeglobals|KDE|widgetStyle"], "kvantum")
            # One set in the account's own file stays.
            kde.set("kdeglobals|KDE|widgetStyle", "Fusion")
            kde.light("apply")
            self.assertEqual(kde.settings()["kdeglobals|KDE|widgetStyle"], "Fusion")

    def test_monets_look_can_be_put_back(self):
        # Light & Wallpaper's Put back: Monet's look again for this account, what changed since
        # included, and its painting on the wall even where KDE's dialog put another one.
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('sheet.ask("look-reset"', settings)
        self.assertIn('i18nc("Monet\'s look, as it was", "Put back")', settings)
        quick = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn('run(f"{LIBEXECDIR}/monet-look", "--reset", timeout=300)', quick)
        self.assertEqual(quick.count('run(f"{LIBEXECDIR}/monet-light", "paint", "wall"'), 2)  # Put back, and a painting picked
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertIn('if [ "${1:-}" = --reset ]; then\n    reset=1\n    export MONET_PROFILE_FORCE=1\n    set -- --keep\nfi', look)
        light = (ROOT / "linux/libexec/monet-light").read_text()
        self.assertIn("if ('$wall' !== 'wall') return;\n                d.wallpaperPlugin = 'org.monet.hours';", light)
        self.assertIn('[ "$wall" != wall ] && [ "$(cat "$said" 2>/dev/null)" = "$these" ] && return 0', light)

    def test_kdes_settings_are_more_settings(self):
        # KDE's System Settings, opened from Monet Settings' "More settings", says so in its titles.
        tool = (ROOT / "tools/make-translations.py").read_text(encoding="utf-8")
        self.assertIn('"systemsettings": ("More settings", [(None, "System Settings")]),', tool)
        for language in ("de", "sv", "ja"):
            self.assertTrue((SHARE / f"locale/{language}@monet/LC_MESSAGES/systemsettings.mo").exists(), language)
        self.assertIn("Weitere Einstellungen".encode(), (SHARE / "locale/de@monet/LC_MESSAGES/systemsettings.mo").read_bytes())

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
    def test_only_monets_own_updater_runs(self):
        # Bazzite's and KDE's updaters stay masked; Monet's timer does it, once a day.
        install = (ROOT / "linux/install.sh").read_text()
        for unit in ("uupd.timer", "rpm-ostreed-automatic.timer", "bootc-fetch-apply-updates.timer"):
            self.assertIn(unit, install)
        self.assertIn('systemctl mask "$unit"', install)
        self.assertIn("AutomaticUpdatePolicy=none", install)
        self.assertIn("systemctl enable monet-sync.service monet-windows-setup.service monet-update.timer monet-apps.timer", install)
        self.assertIn("for unit in monet-sync.service monet-windows-setup.service monet-update.timer monet-apps.timer monet-charge.service; do", install)
        uninstall = (ROOT / "linux/uninstall.sh").read_text()
        for unit in ("monet-update.timer", "monet-apps.timer", "monet-update.service", "monet-apps.service"):
            self.assertIn(unit, uninstall)

    def test_updates_by_itself_unless_turned_off(self):
        service = (ROOT / "linux/systemd/monet-update.service").read_text()
        self.assertIn("ExecStart=@BINDIR@/monet helper update\n", service)
        self.assertIn("ConditionPathExists=!/var/lib/monet/auto-updates-off", service)
        self.assertIn("After=network-online.target", service)
        timer = (ROOT / "linux/systemd/monet-update.timer").read_text()
        for line in ("OnCalendar=daily", "Persistent=true", "WantedBy=timers.target"):
            self.assertIn(line, timer)
        # The switch: Settings → Updates, through the helper, which keeps the same file.
        rust = (ROOT / "crates/monet/src/main.rs").read_text()
        self.assertIn('const AUTO_UPDATES_OFF: &str = "auto-updates-off";', rust)
        self.assertIn('["auto-updates", which @ ("on" | "off")] => elevate(&["helper", "auto-updates", *which])', rust)
        quick = (ROOT / "linux/libexec/monet-quick").read_text()
        self.assertIn('"autoUpdates": not Path("/var/lib/monet/auto-updates-off").exists()', quick)
        self.assertIn('run(f"{BINDIR}/monet", "auto-updates", args[0], timeout=30)', quick)
        qml = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('title: i18n("Update automatically")', qml)
        self.assertIn('ask("auto-updates " + (on ? "on" : "off")', qml)

    def test_zen_is_the_browser(self):
        # Setup's everyday apps bring it, web links open in it, and it wears Monet's painted window.
        self.assertIn('EVERYDAY="app.zen_browser.zen ', (ROOT / "linux/libexec/monet-apps").read_text())
        install = (ROOT / "linux/install.sh").read_text()
        image_only = install.split('if [ "$IMAGE" = 1 ]; then', 2)[2]
        self.assertIn("browser=app.zen_browser.zen.desktop", image_only)
        self.assertIn("mimeapps=/etc/xdg/mimeapps.list", image_only)
        self.assertIn('--group General --key BrowserApplication "$browser"', image_only)
        self.assertTrue((SHARE / "icons/Monet/apps/scalable/app.zen_browser.zen.svg").is_file())  # its own rings, painted

    def test_files_open_in_their_built_in_apps(self):
        # Not in whichever app claims them first (the browser claims pictures and PDFs too).
        install = (ROOT / "linux/install.sh").read_text()
        image_only = install.split('if [ "$IMAGE" = 1 ]; then', 2)[2]
        defaults = image_only.split("<<'DEFAULTS'\n", 1)[1].split("\nDEFAULTS\n", 1)[0]
        apps = {line.split()[0]: line.split()[1:] for line in defaults.splitlines()}
        self.assertIn("image/jpeg", apps["org.kde.gwenview.desktop"])
        self.assertIn("application/pdf", apps["org.kde.okular.desktop"])
        self.assertIn("video/mp4", apps["org.kde.haruna.desktop"])
        self.assertIn("audio/mpeg", apps["org.kde.elisa.desktop"])
        self.assertIn("application/zip", apps["org.kde.ark.desktop"])
        self.assertIn("text/plain", apps["org.kde.kate.desktop;org.kde.kwrite.desktop"])
        types = [t for listed in apps.values() for t in listed]
        self.assertEqual(len(types), len(set(types)))
        self.assertIn('sed -i "\\|^$type=|d" "$mimeapps"', image_only)
        # And they're built in, with what Files needs to show what's inside PDFs and videos.
        image = (ROOT / "image/Containerfile").read_text()
        self.assertIn("gwenview okular haruna elisa-player kcalc ark", image)
        self.assertIn("kdegraphics-thumbnailers ffmpegthumbs", image)

    def test_arriving_apps_get_their_plain_names(self):
        # The names are given once per look, before Setup's apps have arrived: again as they do.
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertIn('if [ "${1:-}" = --names ]; then\n    plain_names\n', look)
        self.assertIn('"org.kde.gwenview:Photos"', look.split("plain_names() {", 1)[1].split("\n}\n", 1)[0])
        self.assertIn("PathChanged=/var/lib/monet/apps-done", (ROOT / "linux/systemd/user/monet-names.path").read_text())
        self.assertIn("ExecStart=@LIBEXECDIR@/monet-look --names", (ROOT / "linux/systemd/user/monet-names.service").read_text())
        self.assertIn('if [ /var/lib/monet/apps-done -nt "$looks/names" ]; then', (ROOT / "linux/libexec/monet-session").read_text())
        install = (ROOT / "linux/install.sh").read_text()
        self.assertEqual(install.count("monet-fresh.service monet-keys.service monet-names.path"), 2)
        self.assertIn("monet-names.path", (ROOT / "linux/uninstall.sh").read_text())

    def test_going_back_to_the_monet_before(self):
        rust = (ROOT / "crates/monet/src/main.rs").read_text()
        self.assertIn('["rollback"] => elevate(&["helper", "rollback"])', rust)
        self.assertIn('Command::new("bootc").arg("rollback")', rust)
        qml = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('ask("rollback"', qml)
        self.assertIn('i18n("Go back at restart")', qml)  # asked once more before it's chosen
        # Updating also clears what no app uses anymore, which Storage says.
        self.assertIn('["uninstall", "--unused", "-y", "--noninteractive"]', rust)

    def test_reduced_motion_outlasts_the_look(self):
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertIn('--key AnimationDurationFactor 2>/dev/null)" = 0 ] ||\n    look --file kdeglobals --group KDE --key AnimationDurationFactor 0.8', look)

    def test_an_update_leaves_what_someone_chose(self):
        # Each Monet version runs the look again: it put back every font, pointer and sound people
        # had picked. Now a setting that holds something other than Monet's last value stays.
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertIn('look --file kdeglobals --group General --key font "Inter', look)
        # Real KConfig behavior, including empty/deleted values and undo, is covered in
        # test_profile_upgrades. Verify every appearance write goes through that policy.
        self.assertIn('look() { "$PROFILE" put "$@"', look)
        self.assertIn('kw() { "$PROFILE" put --default-only "$@"', look)
        self.assertIn('look --file kcminputrc --group Mouse --key cursorTheme Monet-cursors', look)
        session = (ROOT / "linux/libexec/monet-session").read_text()
        self.assertIn('if "$LIBEXECDIR/monet-profile" run "$LIBEXECDIR/monet-look" --keep; then', session)

    def test_the_chosen_apps_arrive_after_setup(self):
        service = (ROOT / "linux/systemd/monet-apps.service").read_text()
        self.assertIn("ExecStart=@LIBEXECDIR@/monet-apps", service)
        self.assertIn("ConditionPathExists=!/var/lib/monet/apps-done", service)
        self.assertIn("OnUnitInactiveSec=", (ROOT / "linux/systemd/monet-apps.timer").read_text())
        script = (ROOT / "linux/libexec/monet-apps").read_text()
        self.assertIn("flatpak install --system --noninteractive --or-update -y flathub", script)
        self.assertIn('touch "$DONE"', script)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn("monet-widgets monet-apps monet-charge monet-paint monet-games monet-settings monet-store monet-store-jobs; do", install)
        self.assertIn("monet-apps", (ROOT / "linux/uninstall.sh").read_text())
        self.assertIn("/var/lib/monet/apps-done", (ROOT / "linux/libexec/monet-session").read_text())

    def test_settings_checks_before_installing(self):
        qml = (SETTINGS_QML).read_text()
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
        apps = ("monet", "monet-settings", "monet-store", "systemsettings", "org.kde.dolphin", "org.kde.konsole", "org.kde.discover",
                "io.github.kolunmi.Bazaar", "org.kde.plasma-systemmonitor", "org.kde.gwenview", "org.kde.okular",
                "org.kde.kate", "org.kde.ark", "org.kde.spectacle", "org.kde.haruna", "org.kde.kcalc", "org.kde.elisa",
                # What Bazzite brings to the dock and the menu.
                "org.mozilla.firefox", "steam", "net.lutris.Lutris", "io.github.ublue_os.yafti_gtk",
                "com.github.tchx84.Flatseal", "io.github.flattool.Warehouse", "it.mijorus.gearlever",
                "com.ranfdev.DistroShelf", "net.davidotek.pupgui2", "waydroid", "input-remapper",
                # Big apps people add: their own marks, kept recognizable, in paint.
                "app.zen_browser.zen", "com.discordapp.Discord", "com.spotify.Client", "com.obsproject.Studio",
                "org.kde.krita", "org.libreoffice.LibreOffice", "org.libreoffice.LibreOffice.writer",
                "org.libreoffice.LibreOffice.calc", "org.libreoffice.LibreOffice.impress", "org.mozilla.Thunderbird",
                "com.google.Chrome", "org.videolan.VLC", "org.telegram.desktop",
                "com.heroicgameslauncher.hgl", "org.prismlauncher.PrismLauncher", "org.libretro.RetroArch",
                "com.usebottles.bottles", "org.gimp.GIMP", "org.blender.Blender", "org.kde.kdenlive",
                "org.audacityteam.Audacity", "com.visualstudio.code", "md.obsidian.Obsidian", "org.signal.Signal")
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

    def test_unpainted_apps_get_a_canvas(self):
        # In a made-up home: each menu app Monet hasn't painted gets its own icon on Monet's canvas.
        import tempfile
        quick = quick_helper()
        with tempfile.TemporaryDirectory() as tmp:
            home, share = Path(tmp) / "home", Path(tmp) / "share"
            quick.data_dirs = lambda: [home, share]
            quick.DATADIR = str(SHARE)
            told = []
            quick.run = lambda *args, **kw: told.append(args)
            apps = share / "applications"
            apps.mkdir(parents=True)
            for app, icon, extra in (("flat", "flatapp", ""), ("vector", "vectorapp", ""), ("files", "org.kde.dolphin", ""),
                                     ("hidden", "hiddenapp", "NoDisplay=true\n"), ("odd", "oddapp", ""),
                                     ("path", "/opt/app/icon.png", "")):
                (apps / f"{app}.desktop").write_text(f"[Desktop Entry]\nType=Application\nName={app}\nIcon={icon}\n{extra}")
            painted = share / "icons/Monet/apps/scalable"
            painted.mkdir(parents=True)
            (painted / "org.kde.dolphin.svg").write_text("<svg/>")
            for folder in ("128x128/apps", "scalable/apps"):
                (share / "icons/hicolor" / folder).mkdir(parents=True)
            png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (128).to_bytes(4, "big") + (64).to_bytes(4, "big") + b"\x08\x06"
            (share / "icons/hicolor/128x128/apps/flatapp.png").write_bytes(png)
            (share / "icons/hicolor/scalable/apps/vectorapp.svg").write_text(
                '<?xml version="1.0"?>\n<svg xmlns="http://www.w3.org/2000/svg" xmlns:inkscape="http://www.inkscape.org/'
                'namespaces/inkscape" width="64" height="64" fill="none" version="1.1"><rect inkscape:label="a" '
                'width="64" height="64" fill="#2a2"/></svg>\n')
            (share / "icons/hicolor/scalable/apps/oddapp.svg").write_text(
                '<!DOCTYPE svg [<!ENTITY ns "http://www.w3.org/2000/svg">]><svg xmlns="&ns;"/>')
            self.assertEqual(quick.frames(), ["flatapp", "vectorapp"])
            out = home / "icons/Monet/apps/scalable"
            vector = (out / "vectorapp.svg").read_text()
            self.assertTrue(vector.startswith("<!-- Monet frame: vectorapp,"))
            ET.fromstring(vector)
            self.assertIn('xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape"', vector)
            self.assertIn('<g transform="translate(26.000,26.000) scale(1.18750)" fill="none">', vector)
            # A wide PNG keeps its shape, centered on the canvas.
            self.assertIn('<image x="26.00" y="45.00" width="76.00" height="38.00"', (out / "flatapp.svg").read_text())
            self.assertEqual(len(told), 1)  # KDE told to look again
            # Unchanged: nothing written, KDE not bothered. An app gone, or painted since: its frame goes.
            self.assertEqual(quick.frames(), ["flatapp", "vectorapp"])
            self.assertEqual(len(told), 1)
            (apps / "flat.desktop").unlink()
            (painted / "vectorapp.svg").write_text("<svg/>")
            mine = out / "mine.svg"
            mine.write_text("<svg/>")  # someone's own icon there is left alone
            self.assertEqual(quick.frames(), [])
            self.assertEqual(sorted(p.name for p in out.iterdir()), ["mine.svg"])

    def test_frames_come_at_sign_in_and_as_apps_arrive(self):
        for part in ("canvas", "relief"):
            self.assertTrue((SHARE / f"monet/textures/frame-{part}.png").is_file())
        self.assertIn('"$LIBEXECDIR/monet-quick" frames >/dev/null 2>&1\n', (ROOT / "linux/libexec/monet-session").read_text())
        self.assertIn("PathChanged=/var/lib/flatpak/exports/share/applications",
                      (ROOT / "linux/systemd/user/monet-frames.path").read_text())
        self.assertIn("ExecStart=@LIBEXECDIR@/monet-quick frames", (ROOT / "linux/systemd/user/monet-frames.service").read_text())
        install = (ROOT / "linux/install.sh").read_text()
        self.assertEqual(install.count("monet-names.path monet-frames.path"), 2)
        uninstall = (ROOT / "linux/uninstall.sh").read_text()
        self.assertIn("/etc/systemd/user/monet-frames.path /etc/systemd/user/monet-frames.service", uninstall)
        self.assertIn("grep -rl --include='*.svg' 'Monet frame:'", uninstall)

    def test_zen_wears_monets_look(self):
        # In a made-up home: nothing before Zen is installed; then Monet's own profile, dressed;
        # and an existing profile keeps what its person wrote.
        import tempfile
        quick = quick_helper()
        with tempfile.TemporaryDirectory() as tmp:
            apps, root = Path(tmp) / "applications", Path(tmp) / ".zen"
            apps.mkdir()
            quick.app_dirs = lambda: [apps]
            quick.zen_root = lambda: root
            quick.DATADIR = str(SHARE)
            self.assertEqual(quick.zen(), [])
            self.assertFalse(root.exists())
            (apps / "app.zen_browser.zen.desktop").write_text("[Desktop Entry]\nName=Zen\n")
            self.assertEqual(quick.zen(), [root / "monet.default"])
            self.assertIn("Path=monet.default\nDefault=1", (root / "profiles.ini").read_text())
            # Zen's installation starts in Monet's profile, not one of its own (found in a test VM).
            self.assertIn("[Install2953CB39A2589173]\nDefault=monet.default\nLocked=1", (root / "profiles.ini").read_text())
            self.assertEqual((root / "installs.ini").read_text(), "[2953CB39A2589173]\nDefault=monet.default\nLocked=1\n")
            chrome = root / "monet.default/chrome"
            self.assertEqual((chrome / "userChrome.css").read_text(), '@import url("monet/zen.css");\n')
            self.assertEqual((chrome / "userContent.css").read_text(), '@import url("monet/newtab.css");\n')
            newtab = (chrome / "monet/newtab.css").read_text()
            self.assertEqual(newtab.count('url("data:image/jpeg;base64,'), 2)
            self.assertNotIn('url("newtab-', newtab)
            for name in ("zen.css", "window-buttons.css", "mist.jpg", "smoke.jpg"):
                self.assertTrue((chrome / "monet" / name).is_file(), name)
            self.assertIn('user_pref("zen.urlbar.replace-newtab", false);', (root / "monet.default/user.js").read_text())
            # Zen's own profile, with someone's own style and prefs and an older Monet part.
            own = root / "abcd1234.Default (release)"
            (own / "chrome").mkdir(parents=True)
            (own / "chrome/userChrome.css").write_text("#nav-bar { color: red; }\n")
            (own / "user.js").write_text('user_pref("mine", 1);\n// Monet: begin (monet-quick zen writes this part)\n'
                                         'user_pref("old", 0);\n// Monet: end\nuser_pref("also.mine", 2);\n')
            with open(root / "profiles.ini", "a") as ini:
                ini.write("\n[Profile1]\nName=default-release\nIsRelative=1\nPath=abcd1234.Default (release)\n"
                          "\n[Install4F96D1932A9F858E]\nDefault=abcd1234.Default (release)\nLocked=1\n")
            self.assertEqual(quick.zen(), [root / "monet.default", own])
            self.assertEqual((own / "chrome/userChrome.css").read_text(),
                             '@import url("monet/zen.css");\n#nav-bar { color: red; }\n')
            prefs = (own / "user.js").read_text()
            self.assertTrue(prefs.startswith('user_pref("mine", 1);\n// Monet: begin'))
            self.assertTrue(prefs.endswith('// Monet: end\nuser_pref("also.mine", 2);\n'))
            self.assertNotIn('"old"', prefs)
            self.assertEqual(prefs.count("// Monet: begin"), 1)
            before = {p: p.read_bytes() for p in root.rglob("*") if p.is_file()}
            quick.zen()  # again: nothing changes
            self.assertEqual({p: p.read_bytes() for p in root.rglob("*") if p.is_file()}, before)

    def test_zen_claims_monets_profile_an_older_monet_made(self):
        quick = quick_helper()
        with tempfile_dir() as tmp:
            root = Path(tmp) / ".zen"
            (root / "monet.default").mkdir(parents=True)
            (root / "profiles.ini").write_text("[Profile0]\nName=Monet\nIsRelative=1\nPath=monet.default\nDefault=1\n\n"
                                              "[General]\nStartWithLastProfile=1\nVersion=2\n")
            self.assertEqual(quick.zen_profiles(root), [root / "monet.default"])
            self.assertTrue((root / "profiles.ini").read_text().endswith("[Install2953CB39A2589173]\nDefault=monet.default\nLocked=1\n"))
            self.assertTrue((root / "installs.ini").is_file())
            # Once Zen has a profile of its own, it's left as it is.
            (root / "installs.ini").write_text("[2953CB39A2589173]\nDefault=own.default\nLocked=1\n")
            before = (root / "profiles.ini").read_text()
            quick.zen_profiles(root)
            self.assertEqual((root / "profiles.ini").read_text(), before)

    def test_zen_follows_at_sign_in_and_leaves_with_monet(self):
        css = (SHARE / "monet/zen/zen.css").read_text()
        self.assertIn("--zen-primary-color: light-dark(#357F72, #4DB4A0) !important;", css)  # lily
        self.assertIn('url("mist.jpg")', css)
        self.assertIn('url("smoke.jpg")', css)
        self.assertIn("background-blend-mode: normal !important;", css)  # Zen lightens its layers: paper would win
        self.assertIn("#urlbar[focused] .urlbar-background", css)
        self.assertIn('font-family: "Fraunces 72pt SuperSoft"', css)
        self.assertEqual(css.count("{"), css.count("}"))
        prefs = quick_helper().ZEN_PREFS
        self.assertIn('user_pref("zen.welcome-screen.seen", true);', prefs)
        # None of Zen's own pages as tabs, nor its Update Complete note.
        for line in ('user_pref("startup.homepage_welcome_url", "");', 'user_pref("startup.homepage_welcome_url.additional", "");',
                     'user_pref("startup.homepage_override_url", "");', 'user_pref("browser.startup.homepage_override.mstone", "ignore");',
                     'user_pref("zen.updates.show-update-notification", false);'):
            self.assertIn(line, prefs)
        self.assertIn('user_pref("browser.shell.checkDefaultBrowser", false);', prefs)
        newtab = (SHARE / "monet/zen/newtab.css").read_text()
        self.assertIn('@-moz-document url("about:newtab"), url("about:home")', newtab)
        self.assertEqual(newtab.count("{"), newtab.count("}"))
        for name in ("mist.jpg", "smoke.jpg", "newtab-mist.jpg", "newtab-smoke.jpg"):
            self.assertTrue((SHARE / "monet/zen" / name).is_file(), name)
        self.assertIn('"$LIBEXECDIR/monet-quick" zen >/dev/null 2>&1\n', (ROOT / "linux/libexec/monet-session").read_text())
        self.assertIn("PathChanged=%h/.var/app/app.zen_browser.zen/.zen", (ROOT / "linux/systemd/user/monet-zen.path").read_text())
        self.assertIn("ExecStart=@LIBEXECDIR@/monet-quick zen", (ROOT / "linux/systemd/user/monet-zen.service").read_text())
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('cp -r "$SRC/share/monet/zen" "$DATADIR/monet/zen"', install)
        self.assertEqual(install.count("monet-frames.path monet-zen.path"), 2)
        uninstall = (ROOT / "linux/uninstall.sh").read_text()
        self.assertIn('rm -rf "${profile}chrome/monet"', uninstall)
        self.assertIn("/etc/systemd/user/monet-zen.path /etc/systemd/user/monet-zen.service", uninstall)

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
        icons = {w: json.loads((PLASMA / "plasmoids" / w / "metadata.json").read_text(encoding="utf-8"))["KPlugin"]["Icon"] for w in desktop}
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
                     "document-edit", "system-lock-screen", "system-log-out", "go-previous", "edit-copy", "edit-find",
                     # KDE's standard menus and the everyday apps' toolbars: no flat Breeze sign among the ink.
                     "document-save-as", "document-print", "document-open-recent", "application-exit", "edit-clear",
                     "edit-find-replace", "zoom-original", "zoom-fit-best", "view-fullscreen", "view-restore",
                     "view-filter", "object-rotate-left", "object-rotate-right", "transform-crop",
                     "media-playlist-shuffle", "media-playlist-repeat", "tools-report-bug", "overflow-menu"):
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
        listed = (SHARE / "monet/hidden-settings-pages").read_text()
        hidden = [line for line in listed.splitlines() if line and not line.startswith("#")]
        for kcm in ("kcm_lookandfeel", "kcm_nighttime", "kcm_colors", "kcm_desktoptheme", "kcm_kwindecoration",
                    "kcm_icons", "kcm_sddm", "kcm_updates", "kcm_about-distro", "kcm_landingpage", "kcm_wallpaper",
                    "kcm_kwallet5", "kcm_activities"):
            self.assertIn(kcm, hidden)
        for kcm in ("kcm_kscreen", "kcm_pulseaudio", "kcm_networkmanagement", "kcm_bluetooth", "kcm_mouse",
                    "kcm_workspace", "kcm_fonts"):
            self.assertNotIn(kcm, hidden)
        self.assertTrue(all(re.fullmatch(r"kcm_[\w-]+", kcm) for kcm in hidden), hidden)
        self.assertIn('for kcm in $(grep -v \'^#\' "$DATADIR/monet/hidden-settings-pages" 2>/dev/null); do\n'
                      '    kw --file kdeglobals --group "KDE Control Module Restrictions" --key "$kcm" false', self.LOOK)
        self.assertIn('install -m 644 "$SRC/share/monet/hidden-settings-pages" "$DATADIR/monet/hidden-settings-pages"',
                      self.INSTALL)
        self.assertIn("help_about_kde", self.LOOK)
        # The two looks are just Mist and Smoke.
        for theme, name in (("org.monet.desktop", "Mist"), ("org.monet.smoke.desktop", "Smoke")):
            meta = json.loads((PLASMA / "look-and-feel" / theme / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["KPlugin"]["Name"], name)

    @unittest.skipIf(sys.platform == "win32", "bash on Windows is WSL's, which can't see this folder")
    def test_more_settings_hides_its_pages_for_everyone(self):
        # Bazzite locks the group in /etc/xdg/kdeglobals ([$i]), so an account's own list never
        # counted: install.sh adds Monet's to that group as it stands, once, and uninstall takes
        # only Monet's lines out again.
        hide_pages = re.search(r"\nhide_pages\(\) \{.*?\n\}\n", self.INSTALL, re.S).group(0)
        self.assertIn('hide_pages /etc/xdg/kdeglobals "$SRC/share/monet/hidden-settings-pages"', self.INSTALL)
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "list").write_text("# what\nkcm_colors\nkcm_updates\nkcm_landingpage\n")
            Path(tmp, "locked").write_text("[General]\nX=1\n\n[KDE Control Module Restrictions][$i]\n"
                                           "kcm_updates[$i]=false\n\n[Sounds]\nTheme=monet\n")
            Path(tmp, "plain").write_text("[General]\nX=1\n")
            script = hide_pages + 'cd "$1" && for f in locked plain; do hide_pages $f list; hide_pages $f list; done'
            subprocess.run(["bash", "-c", script, "-", tmp], check=True, timeout=30)
            self.assertEqual(Path(tmp, "locked").read_text(),
                             "[General]\nX=1\n\n[KDE Control Module Restrictions][$i]\nkcm_colors=false\n"
                             "kcm_landingpage=false\nkcm_updates[$i]=false\n\n[Sounds]\nTheme=monet\n")
            self.assertEqual(Path(tmp, "plain").read_text(),
                             "[General]\nX=1\n\n[KDE Control Module Restrictions]\nkcm_colors=false\n"
                             "kcm_updates=false\nkcm_landingpage=false\n")
        uninstall = (ROOT / "linux/uninstall.sh").read_text()
        self.assertIn('sed -i "/^$kcm=false\\$/d" /etc/xdg/kdeglobals', uninstall)
        self.assertLess(uninstall.index("hidden-settings-pages"), uninstall.index('"$PREFIX/share/monet" \\'))

    def test_more_settings_opens_at_a_page_with_monets_group_names(self):
        # Without KDE's own first page, its settings open at the page for the one open in Monet
        # Settings, or at General Behavior: never at the page saying Plasma.
        quick = quick_helper()
        self.assertEqual(quick.KDE_PAGES["all"], "kcm_workspace")
        self.assertTrue(all(quick.KDE_PAGES.values()))
        hidden = (SHARE / "monet/hidden-settings-pages").read_text()
        for page in quick.KDE_PAGES.values():
            self.assertNotIn(f"\n{page}\n", hidden, page)
        source = (ROOT / "linux/libexec/monet-quick").read_text()
        self.assertIn('page = KDE_PAGES.get(page, KDE_PAGES["all"])', source)
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        body = re.search(r"function kdePage\(\) \{\n(.*?)\n    \}\n", settings, re.S).group(1)
        pages = re.findall(r'(\w+): "(\w+)"', body)
        self.assertIn(("light", "fonts"), pages)
        self.assertIn('[page] || "all"', body)
        for _, page in pages:
            self.assertIn(page, quick.KDE_PAGES)
        self.assertIn("sed -i 's/^Exec=systemsettings$/Exec=systemsettings kcm_workspace/'", self.LOOK)
        # Its groups say what Monet Settings says.
        names = (SHARE / "monet/names.tsv").read_text(encoding="utf-8")
        for group, name in (("settings-hardware-display.desktop", "Display"), ("settings-hardware-multimedia.desktop", "Sound"),
                            ("settings-applications-defaults.desktop", "Default Apps"), ("settings-workspace.desktop", "Desktop")):
            self.assertIn(f'"{group}:{name}"', self.LOOK)
            self.assertIn(f"\n{name}\tsv\t", names)
        self.assertIn('out="$DATA/systemsettings/categories/$1"', self.LOOK)

    def test_kdes_brightness_panel_and_its_dark_mode_stay_out_of_the_bar(self):
        # Plasma 6 keeps the tray's items in the tray's own settings: the layout writes them there,
        # and monet-fresh finds the tray among the bar's applets ([Containments][bar][Applets][tray]).
        for theme in ("org.monet.desktop", "org.monet.smoke.desktop"):
            layout = (PLASMA / "look-and-feel" / theme / "contents/layouts/org.kde.plasma.desktop-layout.js").read_text()
            self.assertNotIn("SystrayContainmentId", layout)
            for piece in ('tray.currentConfigGroup = ["General"]', 'tray.writeConfig("knownItems", union(',
                          '"org.kde.plasma.brightness"', '"org.kde.plasma.volume"',
                          'right.addWidget("org.monet.quick")\nright.addWidget("org.monet.sound")', "tray.reloadConfig()"):
                self.assertIn(piece, layout)
        fresh = (ROOT / "linux/libexec/monet-fresh").read_text()
        self.assertIn(r"/^plugin=org\.kde\.plasma\.systemtray$/", fresh)
        self.assertIn('--group Containments --group "$bar" --group Applets --group "$tray" --group General', fresh)
        self.assertNotIn("private.systemtray", fresh)
        # Accounts the old way missed get it once more; one without a tray yet, at the next sign-in.
        self.assertIn('[ -n "$trays" ] && mkdir -p "$CONFIG/monet" && touch "$flag"', fresh)
        self.assertIn("tray_swap tray-brightness-6 org.kde.plasma.brightness\n", fresh)

    def test_renamed_apps_are_found_by_their_own_names(self):
        # Guides online say Dolphin and KCalc: the menu's search still finds Files and Calculator.
        self.assertIn("""old="$(sed -n 's/^Name=//p' "$f" | head -1)\"""", self.LOOK)
        self.assertIn(r'sed -i "s|^\(Keywords[^=]*=\)|\1$old;|" "$work"', self.LOOK)
        self.assertIn('sed -i "/^X-Monet=true$/a Keywords=$old;" "$work"', self.LOOK)

    def test_apps_go_by_plain_names(self):
        for app, name in (("org.kde.dolphin", "Files"), ("org.kde.konsole", "Terminal"), ("org.kde.gwenview", "Photos"),
                          ("org.kde.spectacle", "Screenshot")):
            self.assertIn(f'"{app}:{name}"', self.LOOK)
        self.assertIn('    store=io.github.kolunmi.Bazaar\n    if store_shortcuts; then', self.LOOK)
        self.assertIn('    elif rename "$store" Store "Apps and games for Monet"; then', self.LOOK)
        hidden = re.search(r"for app in (systemsettings .*?); do\n        hide", self.LOOK, re.S).group(1).split()
        for app in ("systemsettings", "org.kde.kinfocenter", "bazzite-documentation", "discourse", "bbrew",
                    # Bazzite's name, and the Linux penguin (Fcitx's), seen in the built image's menu.
                    "io.github.rfrench3.bazzite-updater", "fcitx5-configtool", "kvantummanager"):
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
        # Every menu entry (and More settings group) monet-look writes carries the mark uninstall.sh
        # looks for (and localized() puts an app's names in other languages under it, and rename()
        # its own name among its keywords).
        for function in ("stand_in", "rename", "hide", "group_name", "games_gpu"):
            body = self.LOOK.split(function + "() {", 1)[1].split("\n}", 1)[0]
            self.assertIn("X-Monet=true", body, function)
        self.assertIn('"$HOME"/.local/share/systemsettings/categories/*.desktop 2>/dev/null | xargs -r rm -f', uninstall)

    def test_command_line_tools_go_in_a_container(self):
        # People from Linux find no dnf: About says why, and gets BoxBuddy (Distrobox's) for them.
        from unittest import mock
        q = quick_helper()
        ran, started = [], []
        with mock.patch.object(q, "run", lambda *a, **k: ran.append(a) or ("installed" if len(ran) > 2 else None)), \
                mock.patch.object(q.subprocess, "Popen", lambda command, **kw: started.append(command)):
            self.assertTrue(q.get_flatpak(q.TOOLS_APP))
        self.assertEqual(ran[1], ("flatpak", "install", "--system", "--noninteractive", "-y", "flathub", "io.github.dvlv.boxbuddyrs"))
        self.assertEqual(started, [["flatpak", "run", "io.github.dvlv.boxbuddyrs"]])
        settings = SETTINGS_QML.read_text(encoding="utf-8")
        self.assertIn('title: i18n("Command-line tools")', settings)
        self.assertIn('sheet.ask("get-tools", () => sheet.gettingTools = false)', settings)
        self.assertIn("          - io.github.dvlv.boxbuddyrs\n", (SHARE / "monet/store/content.yaml").read_text())

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
        qml = (SETTINGS_QML).read_text(encoding="utf-8")
        said = re.findall(r'i18n\("([^"]*)"', qml)
        self.assertIn("More settings ›", said)
        self.assertEqual([s for s in said if re.search(r"\b(KDE|Plasma|Linux|Bazzite)\b", s)], [])
        # Nor is KDE's About page, with its KDE, Qt and kernel versions, one click away.
        self.assertNotIn('ask("kde about")', qml)




class SoundInTheBar(unittest.TestCase):
    """0.9.4: Monet's own Sound in the tray, in glass like Quick Settings, where KDE's volume
    item was (the user: "the tray's volume popup is still KDE's own")."""
    WIDGET = PLASMA / "plasmoids/org.monet.sound"

    def test_beside_quick_settings(self):
        meta = json.loads((self.WIDGET / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual(meta["KPlugin"]["Id"], "org.monet.sound")
        # Not a tray item: in the tray its popover gets KDE's header and box (seen on the test bench).
        self.assertNotIn("X-Plasma-NotificationArea", meta)
        look = (ROOT / "linux/libexec/monet-look").read_text(encoding="utf-8")
        for line in ('var sound = panel.addWidget("org.monet.sound");', "sound.index = quick.index + 1;",
                     'return item !== "org.kde.plasma.volume";', 'touch "$sound"'):
            self.assertIn(line, look)
        self.assertIn("org.monet.sound", (ROOT / "linux/install.sh").read_text())
        self.assertIn("plasmoids/org.monet.sound", (ROOT / "linux/uninstall.sh").read_text())
        qml = (self.WIDGET / "contents/ui/main.qml").read_text(encoding="utf-8")
        for line in ('readonly property string level: "wpctl get-volume @DEFAULT_AUDIO_SINK@"', 'runner.connectSource(helper + " sound")',
                     'run("mute " + (muted ? "on" : "off"))', 'root.queue("app-volume " + modelData.id, value)',
                     "acceptedButtons: Qt.LeftButton | Qt.MiddleButton", 'run("open sound")',
                     'i18n("No speakers or headphones")'):
            self.assertIn(line, qml)
        self.assertNotIn("org.kde.plasma.private.volume", qml)  # KDE's insides change; wpctl doesn't

    def test_the_helper_answers_it(self):
        from unittest import mock
        quick = quick_helper()
        with mock.patch.object(quick, "outputs", return_value=[{"id": 53, "name": "Dummy Output", "default": True, "none": True},
                                                                {"id": 60, "name": "Speakers", "default": False, "none": False}]), \
                mock.patch.object(quick, "apps_sound", return_value=[{"id": 80, "name": "Zen", "volume": 70}]), \
                mock.patch.object(quick, "microphones", return_value=[]):
            self.assertEqual(quick.bar_sound(), {"outputs": [{"id": 60, "name": "Speakers", "default": False, "none": False}],
                                             "apps": [{"id": 80, "name": "Zen", "volume": 70}], "inputs": [], "microphone": None})
        said = []
        with mock.patch.object(quick, "run", lambda *args, **kw: said.append(args)):
            quick.main(["mute", "on"])
            quick.main(["mute", "loud"])  # not a word it takes: nothing
        self.assertEqual(said, [("wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "1")])


class DesktopWidgets(unittest.TestCase):
    """Weather, Calendar, Now Playing, Note, Photo Frame, System, Recently Played, Timer and World Clock,
    on the desktop."""
    WIDGETS = ("org.monet.weather", "org.monet.calendar", "org.monet.nowplaying", "org.monet.notes", "org.monet.frame",
               "org.monet.system", "org.monet.played", "org.monet.timer", "org.monet.worldclock", "org.monet.batteries")

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

    def test_glass_off_reaches_the_widgets_and_the_lock_screen(self):
        # Glass off (Settings, or Monet on a PC whose processor draws): monet-light leaves glass-off, and the
        # widgets and the lock screen stop blurring the painting, the heaviest thing on an old PC's screen.
        light = (ROOT / "linux/libexec/monet-light").read_text()
        self.assertIn('solid/off|frosted/frosted|matte/matte) [ -e "$CONFIG/monet/glass-$flag" ] || : > "$CONFIG/monet/glass-$flag"', light)
        self.assertIn('*) rm -f "$CONFIG/monet/glass-$flag"', light)
        glass = (SHARE / "monet/widgets/Glass.qml").read_text()
        lock = (SHARE / "monet/lockscreen/MonetLockScreen.qml").read_text()
        for qml in (glass, lock):
            self.assertIn('nameFilters: ["glass-off"]', qml)
            self.assertIn('StandardPaths.writableLocation(StandardPaths.GenericConfigLocation) + "/monet"', qml)
        self.assertIn("live: glass.frosted", glass)
        self.assertIn("visible: glass.frosted", glass)
        self.assertIn("visible: monetLock.blurred && opacity > 0", lock)

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
        self.assertIn('elif monets_panels; then', look)
        self.assertIn('if [ "$reset" = 1 ]; then', look)

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
        for piece in ("compactRepresentation:", "fullRepresentation:", "clockFormat.time("):
            self.assertIn(piece, clock)

    def test_files_never_says_the_drive_is_full(self):
        # Found by the test bench: Dolphin's full status bar said "0 B free" in every folder (KDE
        # reads the room left from the read-only system layer), so Files keeps the small one.
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertNotIn("ShowStatusBar FullWidth", look)
        self.assertIn("kw --file dolphinrc --group General --key ShowStatusBar Small", look)

    def test_weather_place_is_chosen_on_the_card(self):
        # Never KDE's settings window: a search right on the widget, and the place's name for another.
        weather = (PLASMA / "plasmoids/org.monet.weather/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertNotIn('internalAction("configure")', weather)
        self.assertIn("geocoding-api.open-meteo.com/v1/search", weather)
        self.assertIn("shared.write({place: place.name", weather)
        self.assertIn("onClicked: root.choosing = true", weather)

    def test_weather_goes_through_its_places(self):
        # Every place is kept in order; the arrows step through them, a new one joins the end, one can go.
        weather = (PLASMA / "plasmoids/org.monet.weather/contents/ui/main.qml").read_text(encoding="utf-8")
        for piece in ("onClicked: root.step(-1)", "onClicked: root.step(1)", "visible: root.places.length > 1",
                      "places.concat([place])", "onTriggered: root.forget()", "readonly property var weather: shared.weather"):
            self.assertIn(piece, weather)
        schema = (PLASMA / "plasmoids/org.monet.weather/contents/config/main.xml").read_text()
        self.assertIn('<entry name="places" type="StringList">', schema)
        settings = (PLASMA / "plasmoids/org.monet.weather/contents/ui/ConfigPlace.qml").read_text(encoding="utf-8")
        for piece in ("property var cfg_places", "onClicked: page.add(modelData)", "onClicked: page.remove(placeRow.index)"):
            self.assertIn(piece, settings)

    def test_widgets_leave_qts_anchor_names_alone(self):
        # An Item's left, right, top and bottom are its anchor lines (FINAL): a property named so never loads.
        for qml in (PLASMA / "plasmoids").glob("*/contents/ui/*.qml"):
            text = qml.read_text(encoding="utf-8")
            self.assertIsNone(re.search(r"property \w+ (left|right|top|bottom|horizontalCenter|verticalCenter|baseline)\b", text),
                              qml)

    def test_new_widgets_read_what_they_show(self):
        system = (PLASMA / "plasmoids/org.monet.system/contents/ui/main.qml").read_text(encoding="utf-8")
        for sensor in ("cpu/all/usage", "memory/physical/usedPercent", "gpu/gpu0/usage", "network/all/download"):
            self.assertIn(f'sensorId: "{sensor}"', system)
        played = (PLASMA / "plasmoids/org.monet.played/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn('runner.connectSource(root.helper + " played")', played)
        self.assertIn('runner.connectSource(helper + " play " + game.play)', played)
        self.assertIn("runner.connectSource(monet + \" play '\" + game.windows + \"' --confirm\")", played)
        quick = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn('elif cmd == "play" and args and PLAYABLE.fullmatch(args[0]):', quick)
        timer = (PLASMA / "plasmoids/org.monet.timer/contents/ui/main.qml").read_text(encoding="utf-8")
        # The end is kept, not the count: a timer keeps going if Plasma starts again.
        self.assertIn("Plasmoid.configuration.ends = now + ", timer)
        self.assertIn('helper + " ring " + hex(', timer)
        self.assertIn("ring(unhex(args[0]), unhex(args[1]))", quick)
        self.assertTrue((SHARE / "sounds/monet/stereo/alarm-clock-elapsed.oga").is_file())
        clock = (PLASMA / "plasmoids/org.monet.worldclock/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn("TimeZonesI18n.i18nCity(town.modelData)", clock)

    def test_calendar_and_clock_share_the_day_notes(self):
        # One month and one day's note for both widgets; the notes themselves are kept by Monet's helper.
        calendar = (PLASMA / "plasmoids/org.monet.calendar/contents/ui/main.qml").read_text(encoding="utf-8")
        clock = (PLASMA / "plasmoids/org.monet.clock/contents/ui/main.qml").read_text(encoding="utf-8")
        for widget in (calendar, clock):
            for piece in ("NoteStore {", "Month {", "NotesPopup {", "store: noteStore"):
                self.assertIn(piece, widget)
        # The notes the Calendar kept in its own settings are handed over once.
        self.assertIn("noteStore.merge(older);", calendar)
        self.assertIn("for part in Month DayNotes NoteStore NotesPopup; do", (ROOT / "linux/install.sh").read_text(encoding="utf-8"))
        month = (ROOT / "linux/share/monet/widgets/Month.qml").read_text(encoding="utf-8")
        for piece in ("WheelHandler {", "onDoubleClicked: month.opened(cell.modelData)"):
            self.assertIn(piece, month)
        import tempfile
        from unittest import mock
        quick = quick_helper()
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(quick, "NOTES", Path(tmp) / "notes.json"):
            self.assertEqual(quick.notes(), {})
            quick.set_note("2026-10-22", "Buy linseed oil")
            # Older notes never write over a day already kept.
            quick.merge_notes({"2026-10-22": "older", "2026-10-24": "Varnish"})
            self.assertEqual(quick.notes(), {"2026-10-22": "Buy linseed oil", "2026-10-24": "Varnish"})
            quick.set_note("2026-10-22", "")
            self.assertEqual(quick.notes(), {"2026-10-24": "Varnish"})

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
        for widget in ("org.monet.weather", "org.monet.notes", "org.monet.menu", "org.monet.calendar", "org.monet.timer",
                       "org.monet.worldclock"):
            schema = (PLASMA / "plasmoids" / widget / "contents/config/main.xml").read_text()
            used = set(re.findall(r"Plasmoid\.configuration\.(\w+)", (PLASMA / "plasmoids" / widget / "contents/ui/main.qml").read_text()))
            for key in used:
                self.assertIn(f'name="{key}"', schema, f"{widget}: {key}")


class LiquidGlass(unittest.TestCase):
    STYLE = PLASMA / "desktoptheme/monet"

    def test_rim_of_light_catches_the_top_left_and_bottom_right(self):
        svg = (self.STYLE / "dialogs/background.svg").read_text()
        self.assertIn('id="hint-stretch-borders"', svg)  # so each side's fade spans it whole
        for gradient in ("rim-top", "rim-bottom", "rim-left", "rim-right", "sheen"):
            self.assertIn(f'<linearGradient id="{gradient}"', svg)
            self.assertIn(f'url(#{gradient})', svg)
        # Tooltips keep the hairline and the sheen, not the rim: on glass that small, a bright
        # line inside the hairline reads as a second box.
        for folder in ("", "translucent/", "solid/", "opaque/"):
            tooltip = (self.STYLE / f"{folder}widgets/tooltip.svg").read_text()
            self.assertNotIn("url(#rim-", tooltip, folder)
            self.assertIn('fill-opacity="0.13"', tooltip)  # the hairline

    def test_bar_and_popovers_have_the_lens_too(self):
        # The same lens of light inside the edge as the widgets' glass; Quick Settings' pebbles are lighter glass.
        for frame in ("dialogs/background", "widgets/panel-background"):
            svg = (self.STYLE / f"{frame}.svg").read_text()
            for side in ("down", "up", "right", "left"):
                self.assertIn(f'url(#lens-{side})', svg, frame)
            self.assertIn('<radialGradient id="lens-topleft"', svg, frame)
        quick = (PLASMA / "plasmoids/org.monet.quick/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn("component GlassRim: Rectangle {", quick)
        self.assertEqual(quick.count("GlassRim {"), 4)  # tiles, sliders, light choices, All Settings

    def test_widget_glass_is_clear_with_a_lens_at_the_edge(self):
        # As Apple's: the painting's strokes show through, softened; a lens along the edge magnifies
        # and brightens them, and a rim catches the light at the top left and bottom right.
        glass = (SHARE / "monet/widgets/Glass.qml").read_text()
        for piece in ("id: lensGrab", "sourceRect: glass.lensPatch", "maskSource: middleMask", "PathRectangle {",
                      "fillRule: ShapePath.OddEvenFill"):
            self.assertIn(piece, glass)
        self.assertEqual(glass.count("live: glass.frosted"), 2)
        self.assertIn("property real wash: 0.16", glass)

    def test_vibrancy_behind_the_glass(self):
        for style in ("monet", "monet-matte", "monet-solid"):
            meta = json.loads((PLASMA / "desktoptheme" / style / "metadata.json").read_text(encoding="utf-8"))
            self.assertTrue(meta["ContrastEffect"]["enabled"])
            self.assertGreater(meta["ContrastEffect"]["saturation"], 1)

class GlassSlider(unittest.TestCase):
    """0.9.4: Glass from none to clear in four steps (the user found clear glass too clear in the
    VM, where KWin hadn't loaded its blur: the painting showed through sharp)."""

    def test_four_steps_and_the_old_switch(self):
        quick = quick_helper()
        quick.drawn_by_processor = lambda: False
        self.assertEqual(quick.GLASS, ("solid", "matte", "frosted", "clear"))
        for chosen, level in ((True, "clear"), (False, "solid"), ("matte", "matte"), ("frosted", "frosted"),
                              (None, "clear"), ("nonsense", "clear")):
            self.assertEqual(quick.glass_level(chosen), level, chosen)
        quick.drawn_by_processor = lambda: True
        self.assertEqual(quick.glass_level(None), "solid")
        from unittest import mock
        with tempfile_dir() as tmp, mock.patch.object(quick, "run") as run:
            quick.PREFS = Path(tmp) / "prefs.json"
            quick.main(["glass", "matte"])
            self.assertEqual(quick.prefs()["glass"], "matte")
            run.assert_called_once()
            quick.main(["glass", "see-through"])  # not a step: nothing
            self.assertEqual(quick.prefs()["glass"], "matte")

    def test_monet_light_dresses_the_desktop_in_each(self):
        light = (ROOT / "linux/libexec/monet-light").read_text()
        for line in ('matte) kvantum="${kvantum}Matte" style=monet-matte strength=12 noise=5 ;;',
                     "frosted) strength=8 noise=3 ;;", '[ "$style" = monet-matte ] && frame="${frame}Matte"',
                     '""|monet|monet-matte|monet-solid)', "MonetMatte|MonetDarkMatte",
                     "reconfigureEffect s blur", '[ "$level" = solid ] || busctl --user call org.kde.KWin /Effects org.kde.kwin.Effects loadEffect s blur'):
            self.assertIn(line, light)
        glass = (SHARE / "monet/widgets/Glass.qml").read_text()
        for line in ('nameFilters: ["glass-frosted"]', 'nameFilters: ["glass-matte"]', "blur: [0.35, 0.7, 1][glass.level]",
                     "readonly property bool lensed: !lite && level < 2"):
            self.assertIn(line, glass)

    def test_matte_is_between_clear_and_solid(self):
        def fills(svg):
            return [float(v) for v in re.findall(r'class="ColorScheme-Background" fill="currentColor" fill-opacity="([0-9.]+)"', svg)]
        frame = "dialogs/background.svg"
        clear, matte, solid = (max(fills((PLASMA / "desktoptheme" / s / frame).read_text())) for s in ("monet", "monet-matte", "monet-solid"))
        self.assertLess(clear, matte)
        self.assertLess(matte, solid)
        kv = {name: (SHARE / "Kvantum" / name / f"{name}.kvconfig").read_text() for name in ("MonetMatte", "MonetSolid")}
        self.assertIn("translucent_windows=true", kv["MonetMatte"])
        self.assertIn("translucent_windows=false", kv["MonetSolid"])
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('tree "$SRC/share/plasma/desktoptheme/monet-matte"', install)
        self.assertIn("MonetMatte MonetDarkMatte", install)
        self.assertIn("MonetSmokeMatte", install)

    def test_settings_has_the_slider(self):
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertNotIn('["glass", i18n("Glass")', settings)  # no longer a switch
        for line in ('readonly property var levels: ["solid", "matte", "frosted", "clear"]', 'tell("glass " + level)',
                     "snapMode: T.Slider.SnapAlways", "onPressedChanged: if (!pressed) sheet.chooseGlass("):
            self.assertIn(line, settings)


class SnapLikeWindows(unittest.TestCase):
    """0.9.4: Windows 11's snap layouts in Monet's glass (the user: "if the user drags a window up
    to the top it suggests a size and place, and stretched to the bottom it takes the top too"),
    with Snap Assist, Windows+Z, and windows gliding into place."""
    SNAP = SHARE / "kwin/scripts/monet-snap"
    MOTION = SHARE / "kwin/effects/monet-motion"

    def qml(self, name):
        return (self.SNAP / "contents/ui" / name).read_text(encoding="utf-8")

    def test_a_kwin_script_and_effect_of_monets(self):
        snap = json.loads((self.SNAP / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual((snap["KPlugin"]["Id"], snap["X-Plasma-API"], snap["X-Plasma-MainScript"]),
                         ("monet-snap", "declarativescript", "ui/main.qml"))
        motion = json.loads((self.MOTION / "metadata.json").read_text(encoding="utf-8"))
        self.assertEqual((motion["KPlugin"]["Id"], motion["X-Plasma-API"]), ("monet-motion", "javascript"))
        # In KWin's Stretch effect's place, so only one animates a maximize.
        self.assertEqual(motion["X-KWin-Exclusive-Category"], "maximize")
        for part in ("Assist.qml", "Layouts.qml", "Pebble.qml", "Picker.qml", "main.qml"):
            self.assertTrue((self.SNAP / "contents/ui" / part).is_file(), part)
        self.assertTrue((self.MOTION / "contents/code/main.js").is_file())
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('tree "$SRC/share/kwin/scripts/monet-snap" "$DATADIR/kwin/scripts/monet-snap"', install)
        self.assertIn('tree "$SRC/share/kwin/effects/monet-motion" "$DATADIR/kwin/effects/monet-motion"', install)
        self.assertIn('"$PREFIX/share/kwin/scripts/monet-snap" "$PREFIX/share/kwin/effects/monet-motion"',
                      (ROOT / "linux/uninstall.sh").read_text())
        look = (ROOT / "linux/libexec/monet-look").read_text()
        for line in ("--group Plugins --key monet-snapEnabled true", "--group Plugins --key monet-motionEnabled true",
                     "--group Plugins --key maximizeEnabled false", "--group Windows --key ElectricBorderMaximize false",
                     "--group Windows --key ElectricBorderTiling false"):
            self.assertIn(line, look)

    def test_the_layouts_fill_the_screen(self):
        try:
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtQml import QJSEngine
        except ImportError as e:
            self.skipTest(f"no Qt for Python ({e})")
        app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841 (QJSEngine needs one)
        main = self.qml("main.qml")
        js = QJSEngine()
        js.evaluate("var Qt = { rect: (x, y, width, height) => ({ x: x, y: y, width: width, height: height }) };"
                    "var gap = 0;")
        js.evaluate("var layouts = " + re.search(r"readonly property var layouts: (\[.*?\n    \])", main, re.S).group(1))
        js.evaluate(re.search(r"\n    (function partRect\(.*?\n    })\n", main, re.S).group(1))
        count = js.evaluate("layouts.length").toInt()
        self.assertEqual(count, 5)
        for layout in range(count):
            parts = json.loads(js.evaluate(
                f"JSON.stringify(layouts[{layout}].map((z, i) => partRect({layout}, i, Qt.rect(100, 40, 1920, 1040))))").toString())
            # Every pixel of the work area in exactly one part: the areas add up, and none overlap.
            self.assertEqual(sum(r["width"] * r["height"] for r in parts), 1920 * 1040, layout)
            for i, a in enumerate(parts):
                self.assertGreaterEqual(a["x"], 100)
                self.assertLessEqual(a["x"] + a["width"], 2020)
                for b in parts[i + 1:]:
                    overlap_w = min(a["x"] + a["width"], b["x"] + b["width"]) - max(a["x"], b["x"])
                    overlap_h = min(a["y"] + a["height"], b["y"] + b["height"]) - max(a["y"], b["y"])
                    self.assertFalse(overlap_w > 0 and overlap_h > 0, (layout, a, b))

    def test_the_islands_stay_on_one_row_while_widgets_are_edited(self):
        # Plasma's edit mode gives each island room of its own and KWin piles them up; Monet Snap
        # puts each back down, naming the size KWin is about to give it (the one it has would be
        # sent back to Plasma, and the middle one ended up off center in the VM).
        try:
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtQml import QJSEngine
        except ImportError as e:
            self.skipTest(f"no Qt for Python ({e})")
        app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841 (QJSEngine needs one)
        main = self.qml("main.qml")
        self.assertIn("if (w && w.dock) {\n            const hook = { window: w, line: () => root && root.lineUp() }", main)
        self.assertIn("h.window.frameGeometryChanged.disconnect(h.line)", main)
        js = QJSEngine()
        js.evaluate("var Qt = { rect: (x, y, width, height) => ({ x: x, y: y, width: width, height: height }) };"
                    "var liningUp = false, barSides = {}, Workspace = { stackingOrder: [] };"
                    "var screen = { geometry: Qt.rect(0, 0, 1920, 1080) };"
                    "function dock(id, x, y, w, h) { return { internalId: id, dock: true, deleted: false, output: screen,"
                    "  frameGeometry: Qt.rect(x, y, w, h) }; }")
        js.evaluate(re.search(r"\n    (function key\(w\) \{.*?\n    })\n", main, re.S).group(1))
        js.evaluate(re.search(r"\n    (function lineUp\(\) \{.*?\n    })\n", main, re.S).group(1))

        def run(setup):
            js.evaluate(setup + "; lineUp()")
            return json.loads(js.evaluate("JSON.stringify(Workspace.stackingOrder.map(w => w.frameGeometry))").toString())

        # The three islands as they are, then as edit mode piles them up (wider, the new size not there yet).
        bar = run("var left = dock(1, 0, 1004, 136, 76), middle = dock(2, 709.5, 1004, 501, 76),"
                  " right = dock(3, 1605, 1004, 315, 76), top = dock(4, 0, 0, 1920, 40), side = dock(5, 0, 200, 60, 680);"
                  "Workspace.stackingOrder = [left, middle, right, top, side]")
        self.assertEqual([r["y"] for r in bar], [1004, 1004, 1004, 0, 200])
        bar = run("left.frameGeometry = Qt.rect(0, 1004, 136, 76); middle.frameGeometry = Qt.rect(686, 928, 501, 76);"
                  "right.frameGeometry = Qt.rect(1575, 852, 315, 76)")
        self.assertEqual(bar[:3], [{"x": 0, "y": 1004, "width": 136, "height": 76},
                                   {"x": 686, "y": 1004, "width": 548, "height": 76},
                                   {"x": 1575, "y": 1004, "width": 345, "height": 76}])
        self.assertEqual(bar[3:], [{"x": 0, "y": 0, "width": 1920, "height": 40}, {"x": 0, "y": 200, "width": 60, "height": 680}])
        # A panel stacked above them on purpose stays; one sliding away below the screen too.
        bar = run("var over = dock(6, 0, 928, 1920, 76); middle.frameGeometry = Qt.rect(686, 1040, 548, 76);"
                  "Workspace.stackingOrder = [left, middle, right, over]")
        self.assertEqual([(r["y"], r["width"]) for r in bar], [(1004, 136), (1040, 548), (1004, 345), (928, 1920)])
        # Without Plasma's edit mode nothing moves at all.
        bar = run("middle.frameGeometry = Qt.rect(686, 1004, 548, 76); Workspace.stackingOrder = [left, middle, right]")
        self.assertEqual([r["y"] for r in bar], [1004, 1004, 1004])

    def test_what_a_drag_does(self):
        main = self.qml("main.qml")
        for line in (
                # The bar, the edges, the corners, the top.
                "return { rect: partRect(halves, side, a), layout: halves, zone: side }",
                "return { rect: Qt.rect(a.x, a.y, a.width, a.height), maximize: true }",
                "w.setMaximize(true, true)",
                # Dragged away: its own size again.
                "w.frameGeometry = Qt.rect(Math.round(p.x - along * was.width), g.y, was.width, was.height)",
                # Stretched by an edge to the screen's: the whole height, without an inset.
                "w.frameGeometry = Qt.rect(g.x, a.y, g.width, a.height)",
                # Snap Assist, after a drag, Windows+arrows or Windows+Z.
                "assist.offer(w, t.layout, t.zone, area)", "w.tileChanged.connect(hook.tile)",
                'sequence: "Meta+Z"',
                # Nothing from a script KWin has stopped (it can keep the window's end of a connection).
                "start: () => root && root.started(w)"):
            self.assertIn(line, main)
        # Windows the script shows by hand: KWin ignores a script window's first visible: true.
        self.assertIn("show()", main)
        for name in ("main.qml", "Assist.qml", "Picker.qml"):
            self.assertNotIn("visible: true", self.qml(name), name)
        # A property can't take a name Qt keeps for its own (z, x, ...): the script wouldn't load.
        for name in ("main.qml", "Assist.qml", "Layouts.qml", "Pebble.qml", "Picker.qml"):
            self.assertNotRegex(self.qml(name), r"property \w+ (x|y|z|width|height|visible|opacity|scale|state)\b", name)

    def test_snap_assist_offers_only_real_windows(self):
        assist = self.qml("Assist.qml")
        for check in ("!o.hidden", 'o.caption !== ""', 'o.resourceClass !== "kwin_wayland"', "!o.skipSwitcher",
                      "o.output === w.output", "o.desktops.indexOf(KWin.Workspace.currentDesktop) >= 0"):
            self.assertIn(check, assist)
        self.assertIn("Workspace.activeWindow = w", self.qml("main.qml"))  # picked, it comes to the front

    def test_windows_glide_into_place(self):
        motion = (self.MOTION / "contents/code/main.js").read_text(encoding="utf-8")
        for line in ("window.windowMaximizedStateAboutToChange.connect", "window.windowFinishUserMovedResized.connect",
                     "type: Effect.CrossFadePrevious", "type: Effect.Size", "type: Effect.Translation",
                     # Never a window held by hand, nor one an app resizes in place.
                     "window.monetHeld || window.move || window.resize", "if (letGo || (moved > 16 && grown > 0.1))",
                     "new MonetMotion();"):
            self.assertIn(line, motion)

    def test_windows_meet_edge_to_edge(self):
        # The user saw the painting around snapped windows: no gap of Monet Snap's, and no frame
        # reaching past its glass (which also put the resize arrows away from the window).
        self.assertIn("readonly property int gap: 0", self.qml("main.qml"))
        self.assertNotIn("GRIP", (ROOT / "tools/make-decoration.py").read_text(encoding="utf-8"))
        for theme in ("Monet", "MonetMatte", "MonetSolid", "MonetSmoke", "MonetSmokeMatte", "MonetSmokeSolid"):
            rc = configparser.ConfigParser(interpolation=None)
            rc.read_string((SHARE / "aurorae/themes" / theme / f"{theme}rc").read_text())
            layout = rc["Layout"]
            # Only shadow outside the window: extra padding used to paint a white rim here.
            # KWin's invisible resize area does not need a visible border.
            self.assertEqual((layout["BorderLeft"], layout["PaddingLeft"], layout["PaddingRight"], layout["PaddingBottom"],
                              layout["TitleEdgeTop"]), ("4", "40", "40", "54", "5"), theme)
        self.assertIn("--group org.kde.kdecoration2 --key BorderSize None", (ROOT / "linux/libexec/monet-look").read_text(encoding="utf-8"))
        # Native and client-decorated windows both fill their part, with no leftover rim gap.
        main = self.qml("main.qml")
        self.assertNotIn("rimOf", main)
        self.assertEqual(main.count("w.frameGeometry = part"), 2)

    def test_settings_is_a_window_like_the_others(self):
        # The user: Settings resized from inside its glass, then only from two sides, and closed
        # with the bar. Now an app of its own (as Games): Monet's frame resizes, fills the screen
        # and snaps it, and its size is kept as a window's.
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn("\nShared.MonetWindow {\n    id: sheet\n", settings)
        for gone in ("PlasmaCore", "PlasmaComponents", "P5Support", "Plasmoid", "mainItem", "startSystemResize",
                     "toggleBig", "chosenWidth", "@DATADIR@", "@BINDIR@"):
            self.assertNotIn(gone, settings)
        for piece in ("minimumWidth: Math.min(760, Screen.desktopAvailableWidth - 32)",
                      "property alias windowWidth: sheet.width", 'category: "Window"',
                      'if (search.text !== "") { search.text = ""; search.forceActiveFocus() }',
                      "else sheet.close()", "Component.onCompleted: open(firstPage)",
                      "function onWanted(which) {\n            sheet.open(which)"):
            self.assertIn(piece, settings)
        self.assertNotIn("translation.x", settings)

    def test_monets_own_apps_come_forward_when_opened_again(self):
        # Settings opened again from Quick Settings only flashed in the taskbar (no activation
        # token from the bar): KWin lets Monet's own apps through when they ask.
        main = self.qml("main.qml")
        self.assertIn('if (w.resourceClass === "monet-settings" || w.resourceClass === "monet-games") {\n'
                      "            w.demandsAttentionChanged.connect(() => root && w.demandsAttention && (Workspace.activeWindow = w))",
                      main)

    def test_snap_assist_closes_on_its_empty_glass(self):
        # As in Windows: only a window's picture takes a click; the pane's empty glass says no, thanks.
        assist = self.qml("Assist.qml")
        self.assertEqual(assist.count("MouseArea {"), 1)
        self.assertIn("gesturePolicy: TapHandler.ReleaseWithinBounds", assist)

    def test_snap_layouts_can_be_switched_off(self):
        # Settings → Light & Wallpaper → Snap layouts: off, Monet Snap leaves windows alone and
        # KWin's own edges and top take them; Monet Snap stays loaded for the bar's islands.
        from unittest import mock
        quick = quick_helper()
        with tempfile_dir() as tmp:
            quick.PREFS = Path(tmp) / "prefs.json"
            quick.drawn_by_processor = lambda: False
            self.assertTrue(quick.prefs()["snap"])
            quick.save_pref("snap", False)
            self.assertFalse(quick.prefs()["snap"])
        written, called = [], []
        with mock.patch.object(quick, "kwrite", lambda *a: written.append(a)), \
                mock.patch.object(quick, "busctl", lambda *a: called.append(a)):
            quick.set_snap(False)
            quick.set_snap(True)
        self.assertEqual(written, [("kwinrc", "Script-monet-snap", "Snapping", "false"),
                                   ("kwinrc", "Windows", "ElectricBorderMaximize", "true"),
                                   ("kwinrc", "Windows", "ElectricBorderTiling", "true"),
                                   ("kwinrc", "Script-monet-snap", "Snapping", "true"),
                                   ("kwinrc", "Windows", "ElectricBorderMaximize", "false"),
                                   ("kwinrc", "Windows", "ElectricBorderTiling", "false")])
        self.assertEqual(called, [("call", "org.kde.KWin", "/KWin", "org.kde.KWin", "reconfigure")] * 2)
        source = (ROOT / "linux/libexec/monet-quick").read_text()
        self.assertIn('args[0] in ("hours", "placard", "glass", "weather", "dodge", "snap")', source)
        self.assertIn('dodge = set_dodge(values["dodge"])\n    snap = set_snap(values["snap"])', source)  # Put back keeps it
        # An update keeps the choice: monet-look's record, not a plain write, for KWin's own edges.
        look = (ROOT / "linux/libexec/monet-look").read_text()
        for key in ("ElectricBorderMaximize false", "ElectricBorderTiling false", "monet-snapEnabled true"):
            self.assertIn(f"look --file kwinrc --group {'Plugins' if 'snap' in key else 'Windows'} --key {key}", look)
        self.assertNotIn("Snapping", look)
        main = self.qml("main.qml")
        self.assertIn('property bool snapping: KWin.readConfig("Snapping", true)', main)
        self.assertIn("target: Options\n        function onConfigChanged() {", main)
        for guard in ("if (!snapping || !w.resizeable", "if (!snapping || !tile", "if (!snapping || placing || sharing",
                      "w.normalWindow && root.snapping"):
            self.assertIn(guard, main)
        self.assertNotIn("snapping", main[main.index("function lineUp()"):main.index("Component.onCompleted")])
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('["snap", i18n("Snap layouts"), i18n("Drag a window to the top of the screen', settings)
        self.assertIn('...(sheet.prefs.snap !== false ? [[i18n("Snap layouts"), ["Meta", "Z"]]] : []),', settings)

    def test_snap_assist_and_the_layouts_take_keys_while_they_are_up(self):
        # KWin never gives a script's window the keyboard: KWin shortcuts for the arrows, Tab, Enter,
        # Space and Esc exist only while one of them is up, and a moment after (handing over).
        main = self.qml("main.qml")
        for key in ("Left", "Right", "Up", "Down", "Tab", "Return", "Enter", "Space", "Escape"):
            self.assertIn(f'["{key}", "', main)
        # And the numbers, for Windows+Z only (Snap Assist has no use for them).
        self.assertIn('.concat(["1", "2", "3", "4", "5", "6", "7", "8", "9"].map(n => [n, n]))', main)
        self.assertIn("} else if (assist.shown && !/^[1-9]$/.test(k)) {", main)
        self.assertIn("numbered: picker.numbered", self.qml("Picker.qml"))
        self.assertIn("visible: row.numbered === screenPicture.layoutIndex", self.qml("Layouts.qml"))
        for piece in ("readonly property bool keysWanted: assist.shown || picker.shown",
                      "keysOff.restart()", "onTriggered: keys.active = false",
                      'name: "Monet Snap Assist " + modelData[0]', "onActivated: Qt.callLater(root.pressed, modelData[1])"):
            self.assertIn(piece, main)
        try:
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtQml import QJSEngine
        except ImportError as e:
            self.skipTest(f"no Qt for Python ({e})")
        app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841 (QJSEngine needs one)
        press = r"\n    (function press\(k\) \{.*?\n    })\n"

        # The layouts: left and right part by part through all of them, up and down layout by layout.
        js = QJSEngine()
        js.evaluate("var layouts = " + re.search(r"readonly property var layouts: (\[.*?\n    \])", main, re.S).group(1)
                    + "; var litLayout = -1, litZone = -1, numbered = -1, chosen = [], closed = 0;"
                    "function close() { closed++; litLayout = -1 } function choose(l, z) { chosen.push([l, z]) }")
        js.evaluate(re.search(press, self.qml("Picker.qml"), re.S).group(1))

        def lit(*keys):
            for k in keys:
                js.evaluate(f'press("{k}")')
            return json.loads(js.evaluate("JSON.stringify([litLayout, litZone])").toString())
        self.assertEqual(lit("choose"), [-1, -1])  # nothing lit, nothing chosen
        self.assertEqual(lit("right"), [0, 0])
        self.assertEqual(lit("right", "right"), [1, 0])
        self.assertEqual(lit("left"), [0, 1])
        self.assertEqual(lit("down"), [1, 1])
        self.assertEqual(lit("down", "down", "down", "down", "down"), [4, 1])
        self.assertEqual(lit("right", "right", "right", "right"), [4, 3])  # the last part stays
        self.assertEqual(lit("next"), [0, 0])  # Tab goes round
        lit("right", "choose")
        self.assertEqual(json.loads(js.evaluate("JSON.stringify(chosen)").toString()), [[0, 1]])
        lit("close")
        self.assertEqual(js.evaluate("closed").toInt(), 1)
        # Windows' numbers: a layout's, then a part's in it; one that isn't there does nothing.
        js.evaluate("numbered = -1; chosen = []; litZone = -1")
        self.assertEqual(lit("9"), [-1, -1])
        self.assertEqual(lit("4"), [3, 0])
        self.assertEqual(js.evaluate("numbered").toInt(), 3)
        lit("9", "3")
        self.assertEqual(json.loads(js.evaluate("JSON.stringify(chosen)").toString()), [[3, 2]])

        # Snap Assist: the pictures in rows, the first press lights the first one.
        js = QJSEngine()
        js.evaluate("var choices = ['a', 'b', 'c', 'd', 'e'], keyed = -1, picked = [], closed = 0;"
                    "var grid = { columns: 2, y: 0 }, tiles = { itemAt: i => null };"
                    "function close() { closed++ } function pick(o) { picked.push(o) }")
        js.evaluate(re.search(press, self.qml("Assist.qml"), re.S).group(1))

        def keyed(*keys):
            for k in keys:
                js.evaluate(f'press("{k}")')
            return js.evaluate("keyed").toInt()
        self.assertEqual(keyed("down"), 0)
        self.assertEqual(keyed("down"), 2)
        self.assertEqual(keyed("right", "down", "down"), 4)
        self.assertEqual(keyed("left", "up"), 1)
        self.assertEqual(keyed("next", "next", "next", "next"), 0)
        js.evaluate('keyed = -1; press("choose"); keyed = 3; press("choose"); press("close")')
        self.assertEqual(json.loads(js.evaluate("JSON.stringify(picked)").toString()), ["a", "d"])
        self.assertEqual(js.evaluate("closed").toInt(), 1)

    def test_notifications_stay_inside_the_screen(self):
        # Plasma placed them by their content's width; Monet's frame is wider, so they stuck out.
        main = self.qml("main.qml")
        self.assertIn("if (w && (w.notification || w.criticalNotification)) {", main)
        self.assertIn("h.window.frameGeometryChanged.disconnect(h.inside)", main)
        try:
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtQml import QJSEngine
        except ImportError as e:
            self.skipTest(f"no Qt for Python ({e})")
        app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841 (QJSEngine needs one)
        js = QJSEngine()
        js.evaluate("var Qt = { rect: (x, y, w, h) => ({ x: x, y: y, width: w, height: h }) };"
                    "function note(x, y) { return { output: { geometry: { x: 0, y: 0, width: 1920, height: 1080 } },"
                    " frameGeometry: { x: x, y: y, width: 344, height: 89 } } }")
        js.evaluate(re.search(r"\n    (function keepInside\(w\) \{.*?\n    })\n", main, re.S).group(1))
        where = lambda x: json.loads(js.evaluate(f"(() => {{ const w = note({x}, 879); keepInside(w);"
                                                 " return JSON.stringify(w.frameGeometry) })()").toString())
        self.assertEqual(where(1588), {"x": 1576, "y": 879, "width": 344, "height": 89})   # ends at the edge
        self.assertEqual(where(-12)["x"], 0)
        self.assertEqual(where(1200)["x"], 1200)                                            # inside: left alone

    def test_the_islands_keep_their_glass_as_they_slide_away(self):
        # They turned white on the way down: Plasma drew them solid once a window touched them.
        for style in ("monet", "monet-matte", "monet-solid"):
            meta = json.loads((PLASMA / "desktoptheme" / style / "metadata.json").read_text(encoding="utf-8"))
            self.assertFalse(meta["AdaptiveTransparency"]["enabled"], style)
            self.assertIn("[AdaptiveTransparency]\nenabled=false", (PLASMA / "desktoptheme" / style / "plasmarc").read_text())


class WindowFrames(unittest.TestCase):
    """Monet's title bars (tools/make-decoration.py), one per light."""
    THEMES = SHARE / "aurorae/themes"
    NAMES = ("Monet", "MonetMatte", "MonetSolid", "MonetSmoke", "MonetSmokeMatte", "MonetSmokeSolid")
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
        self.assertIn("look --file kdeglobals --group Sounds --key Theme monet",
                      (ROOT / "linux/libexec/monet-look").read_text())
        uninstall = (ROOT / "linux/uninstall.sh").read_text()
        self.assertIn('"$PREFIX/share/sounds/monet"', uninstall)
        self.assertIn("kwriteconfig6 --file kdeglobals --group Sounds --key Theme ocean", uninstall)


class Crashes(unittest.TestCase):
    """An app that closes unexpectedly gets Monet's note, not KDE's crash reporter (Bazzite leaves it out)."""

    def test_app_units_name_their_menu_entry(self):
        # systemd's names for an app's unit: Plasma's menu and autostart, Flatpak's sandbox, another launcher.
        app_of = quick_helper().app_of_unit
        self.assertEqual(app_of("app-org.kde.dolphin@0123456789abcdef0123456789abcdef.service"), "org.kde.dolphin.desktop")
        self.assertEqual(app_of("app-steam@autostart.service"), "steam.desktop")
        self.assertEqual(app_of("app-flatpak-app.zen_browser.zen-12345.scope"), "app.zen_browser.zen.desktop")
        self.assertEqual(app_of("app-org.kde.konsole-4242.scope"), "org.kde.konsole.desktop")
        self.assertEqual(app_of("app-gnome-org.gnome.Calculator-77.scope"), "org.gnome.Calculator.desktop")
        self.assertEqual(app_of(r"app-my\x2dgame@1.service"), "my-game.desktop")
        # Not apps: Plasma's own pieces, D-Bus services, Monet's note itself.
        for unit in ("plasma-plasmashell.service", "dbus-:1.2-org.kde.kded6@0.service", "run-u42.service", "app.slice", ""):
            self.assertEqual(app_of(unit), "", unit)

    def test_a_persons_crash_reaches_their_session(self):
        from unittest import mock
        quick = quick_helper()

        def crash(*journal):
            told, journal = [], list(journal)

            def run(*args, **kw):
                told.append(args)
                if args[0] == "journalctl":
                    return journal.pop(0) if journal else None
                return "ada\n" if args[0] == "id" else ""
            with mock.patch.object(quick, "run", run), mock.patch.object(quick.time, "sleep"):
                quick.crash("3-4567-1000", "0" * 32)
            return told

        def dump(uid, unit):
            return json.dumps({"COREDUMP_EXE": "/usr/bin/dolphin", "COREDUMP_UID": uid, "COREDUMP_USER_UNIT": unit}) + "\n"
        # The crash reaches the journal a moment after systemd-coredump starts.
        told = crash(None, "", dump("1000", "app-org.kde.dolphin@ab.service"))
        journal = [args for args in told if args[0] == "journalctl"]
        self.assertEqual(len(journal), 3)
        self.assertIn("_SYSTEMD_UNIT=systemd-coredump@3-4567-1000.service", journal[0])
        self.assertIn("_BOOT_ID=" + "0" * 32, journal[0])
        self.assertEqual(told[-1], ("systemd-run", "--user", "--machine=ada@.host", "--quiet", "--collect",
                                    "--property=KillMode=process", "@LIBEXECDIR@/monet-quick", "crashed",
                                    b"app-org.kde.dolphin@ab.service".hex()))
        # Not the system's own crashes, nor what isn't an app.
        for uid, unit in (("0", "app-org.kde.dolphin@ab.service"), ("1000", "plasma-kwin_wayland.service")):
            self.assertNotIn("systemd-run", [args[0] for args in crash(dump(uid, unit))])
        # What systemd hands over is checked first.
        with mock.patch("sys.stderr"):
            self.assertEqual(quick.main(["crash", "1-2 3", "0" * 32]), 1)
            self.assertEqual(quick.main(["crashed", "not hex"]), 1)

    def test_the_note_only_once_the_app_is_gone(self):
        from unittest import mock
        quick = quick_helper()
        files = quick.desktop_entry("[Desktop Entry]\nType=Application\nName=Files\nName[sv]=Filer\nIcon=system-file-manager\n")

        def note(still_open=False, answer="", entry=files):
            told = []

            def run(*args, **kw):
                told.append(args)
                return answer if args[0] == "notify-send" else None
            with mock.patch.object(quick, "entry_by_id", lambda app: entry if app == "org.kde.dolphin.desktop" else None), \
                    mock.patch.object(quick, "ok", lambda *args, **kw: still_open), \
                    mock.patch.object(quick, "run", run), mock.patch.object(quick, "launch") as launch, \
                    mock.patch.object(quick.time, "sleep"), \
                    mock.patch.dict(quick.os.environ, {"LANGUAGE": "", "LC_ALL": "", "LC_MESSAGES": "", "LANG": "sv_SE.UTF-8"}):
                quick.crashed("app-org.kde.dolphin@ab.service")
            return told, launch
        # The app's own name (in your language) and picture; "Open it again" starts it the menu's way.
        told, launch = note(answer="open\n")
        self.assertEqual(told, [("notify-send", "--app-name=Monet", "--icon=system-file-manager",
                                 "--action=open=Open it again", "--wait", "Filer closed unexpectedly")])
        launch.assert_called_once_with("org.kde.dolphin.desktop")
        told, launch = note(answer="")
        self.assertEqual(len(told), 1)
        launch.assert_not_called()
        # Still open (a tab or a game under Steam crashed), not in the menu, or not an app Monet knows: nothing.
        for kept in (note(still_open=True), note(entry=quick.desktop_entry("[Desktop Entry]\nName=Helper\nNoDisplay=true\n")),
                     note(entry=None)):
            self.assertEqual(kept[0], [])
            kept[1].assert_not_called()

    def test_wired_beside_systemd_coredump(self):
        service = (ROOT / "linux/systemd/monet-crash@.service").read_text()
        self.assertIn("ExecStart=@LIBEXECDIR@/monet-quick crash %i %b\n", service)
        self.assertIn("RuntimeMaxSec=5min", service)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn("monet-apps.timer monet-crash@.service monet-charge.service; do", install)
        self.assertIn('ln -sfn ../monet-crash@.service "$UNITDIR/systemd-coredump@.service.wants/monet-crash@.service"',
                      install)
        self.assertIn("/etc/systemd/system/systemd-coredump@.service.wants/monet-crash@.service",
                      (ROOT / "linux/uninstall.sh").read_text())
        for command in ("crash INSTANCE BOOT", "crashed UNIT"):
            self.assertRegex(quick_helper().__doc__, rf"monet-quick {re.escape(command)}\s")


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
        self.assertIn("ARG BASE=ghcr.io/ublue-os/bazzite-nvidia-open:stable", containerfile)
        self.assertIn("FROM ${BASE} AS password", containerfile)
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

    def test_the_desktop_menu_is_monets(self):
        # As Windows has it: Display settings and Personalize open Monet Settings' pages (The Hours
        # adds them: a wallpaper's entries are the only ones Plasma's menu takes in), and KDE's
        # Desktop and Wallpaper, Display Configuration, edit mode, Lock Screen and Show Logout
        # Screen are out of it.
        wallpaper = (PLASMA / "wallpapers/org.monet.hours/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn('text: i18n("Display settings")\n            icon.name: "preferences-desktop-display"\n'
                      '            onTriggered: root.settings("display")', wallpaper)
        self.assertIn('text: i18n("Personalize")\n            icon.name: "preferences-desktop-wallpaper"\n'
                      '            onTriggered: root.settings("light")', wallpaper)
        self.assertIn('runner.connectSource("@LIBEXECDIR@/monet-quick open " + page)', wallpaper)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('"$SRC/share/monet/desktop-menu.conf" /etc/xdg/plasma-org.kde.plasma.desktop-appletsrc', install)
        # The runner only once asked for: the lock screen shows this painting and has none.
        imports = [line for line in wallpaper.splitlines() if line.startswith("import ")]
        self.assertNotIn("import org.kde.plasma.plasma5support as P5Support", imports)
        fresh = (ROOT / "linux/libexec/monet-fresh").read_text()
        block = fresh[fresh.index('if [ ! -e "$CONFIG/monet/menu-monet" ]'):]
        for entry in ("configure=false", "_display_settings=false", '"desktop edit mode=false"', "_lock_screen=false",
                      "_logout=false", "_open_terminal=true", "_wallpaper=true"):
            self.assertIn(entry, block)
        self.assertIn('--group ActionPlugins --group 0 --group "RightButton;NoModifier" \\\n            --key "${entry%=*}" "${entry#*=}"', block)
        self.assertLess(fresh.index("menu-monet"), fresh.index('[ "$(cat "$stamp" 2>/dev/null)" = "$version" ] && exit "$failed"'))

    def test_adding_widgets_is_easy_to_find(self):
        # The desktop's right-click menu offers Add or Manage Widgets (KDE hides it there), set before
        # Plasma starts, and again after a fresh layout forgot it.
        fresh = (ROOT / "linux/libexec/monet-fresh").read_text()
        self.assertIn('--group ActionPlugins --group 0 --group "RightButton;NoModifier" --key "add widgets" true', fresh)
        self.assertIn('--key "RightButton;NoModifier" org.kde.contextmenu', fresh)
        self.assertLess(fresh.index("add widgets"), fresh.index('[ "$(cat "$stamp" 2>/dev/null)" = "$version" ] && exit "$failed"'))
        look = (ROOT / "linux/libexec/monet-look").read_text()
        reset = look.split("--resetLayout >/dev/null 2>&1", 1)[1].split("\nfi\n", 1)[0]
        self.assertIn('rm -f "$CONFIG/monet/menu-add-widgets" "$CONFIG/monet/menu-monet"', reset)
        # Monet Settings' Light & Wallpaper opens the gallery too.
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('sheet.ask("widgets")', settings)
        quick = (ROOT / "linux/libexec/monet-quick").read_text()
        self.assertIn('elif cmd == "widgets":', quick)
        self.assertIn('"org.kde.PlasmaShell", "toggleWidgetExplorer"', quick)


class MonetSettings(unittest.TestCase):
    QUICK = PLASMA / "plasmoids/org.monet.quick/contents/ui"

    @unittest.skipIf(sys.platform == "win32", "sysfs names have colons, which Windows folders can't")
    def test_controllers_come_from_the_kernel(self):
        import tempfile
        quick = quick_helper()
        with tempfile.TemporaryDirectory() as tmp:
            # A DualSense over Bluetooth (HID bus 0005) with its battery, and a wired pad without one.
            pad = Path(tmp) / "0005:054C:0CE6.0003"
            (pad / "input/input23").mkdir(parents=True)
            (pad / "input/input23/name").write_text("DualSense Wireless Controller\n")
            (pad / "power_supply/ps-controller-battery").mkdir(parents=True)
            (pad / "power_supply/ps-controller-battery/capacity").write_text("80\n")
            (pad / "power_supply/ps-controller-battery/status").write_text("Discharging\n")
            wired = Path(tmp) / "1-1:1.0"
            (wired / "input/input5").mkdir(parents=True)
            (wired / "input/input5/name").write_text("Microsoft X-Box 360 pad\n")
            found = quick.controller(pad / "input/input23")
            self.assertEqual({k: found[k] for k in ("name", "battery", "charging", "wireless")},
                             {"name": "DualSense Wireless Controller", "battery": 80, "charging": False, "wireless": True})
            found = quick.controller(wired / "input/input5")
            self.assertEqual((found["battery"], found["wireless"]), (None, False))

    def test_a_mouse_isnt_a_controller(self):
        # The kernel makes a joystick of any absolute pointer (the test bench's VM mouse); udev knows better.
        with tempfile_dir() as tmp:
            js, udev = Path(tmp) / "js0", Path(tmp) / "udev"
            js.mkdir()
            udev.mkdir()
            (js / "dev").write_text("13:0\n")
            quick = quick_helper()
            self.assertTrue(quick.joystick(js, udev))  # no word from udev
            (udev / "c13:0").write_text("I:35637945\nE:ID_INPUT=1\nE:ID_INPUT_MOUSE=1\nV:1\n")
            self.assertFalse(quick.joystick(js, udev))
            (udev / "c13:0").write_text("I:35637945\nE:ID_INPUT=1\nE:ID_INPUT_JOYSTICK=1\nV:1\n")
            self.assertTrue(quick.joystick(js, udev))

    def test_games_are_found_where_steam_keeps_them(self):
        import tempfile
        quick = quick_helper()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            quick.HOME, quick.DATA_HOME = home, home / ".local/share"
            steam, other = quick.DATA_HOME / "Steam", Path(tmp) / "disk/SteamLibrary"
            (steam / "steamapps").mkdir(parents=True)
            other.mkdir(parents=True)
            (steam / "steamapps/libraryfolders.vdf").write_text(
                '"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"%s"\n\t\t"label"\t\t""\n\t\t"apps"\n\t\t{\n'
                '\t\t\t"228980"\t\t"1000"\n\t\t\t"1091500"\t\t"70000000000"\n\t\t}\n\t}\n\t"1"\n\t{\n\t\t"path"\t\t"%s"\n'
                '\t\t"apps"\n\t\t{\n\t\t\t"570"\t\t"30000000000"\n\t\t}\n\t}\n}\n' % (steam.as_posix(), other.as_posix()))
            (home / "Games/Heroic").mkdir(parents=True)
            found = quick.game_libraries()
            self.assertEqual([(f["games"], f["size"]) for f in found[:2]], [(2, 70000001000), (1, 30000000000)])
            self.assertTrue(all(f["name"].startswith("Steam") for f in found[:2]))
            self.assertEqual(found[0]["path"], str(steam / "steamapps/common"))
            self.assertEqual((found[2]["name"], found[2]["games"]), ("Games folder", 1))

    def test_recently_played_comes_from_steam(self):
        import tempfile
        quick = quick_helper()
        with tempfile.TemporaryDirectory() as tmp:
            steam = Path(tmp) / "Steam"
            quick.STEAM_ROOTS = (steam,)
            apps = steam / "steamapps"
            apps.mkdir(parents=True)

            def manifest(appid, name, last=None):
                lines = [f'"appid"\t\t"{appid}"', f'"name"\t\t"{name}"'] + ([f'"LastPlayed"\t\t"{last}"'] if last else [])
                (apps / f"appmanifest_{appid}.acf").write_text('"AppState"\n{\n' + "\n".join(lines) + "\n}\n")

            manifest("620", "Portal 2", 1700000000)
            manifest("1091500", "Cyberpunk 2077")  # its time is in the account's settings
            manifest("1493710", "Proton Experimental", 1800000000)  # a tool, not a game
            manifest("570", "Dota 2")  # never played
            config = steam / "userdata/123/config"
            config.mkdir(parents=True)
            (config / "localconfig.vdf").write_text('"UserLocalConfigStore"\n{\n"Software"\n{\n"Valve"\n{\n"Steam"\n{\n"apps"\n'
                                                    '{\n"1091500"\n{\n"LastPlayed"\t\t"1750000000"\n}\n}\n}\n}\n}\n}\n')
            cache = steam / "appcache/librarycache"
            (cache / "1091500").mkdir(parents=True)
            (cache / "1091500/library_600x900.jpg").write_bytes(b"jpg")
            (cache / "620_header.jpg").write_bytes(b"jpg")
            found = quick.played(heroic_roots=(), lutris_roots=(), windows_played={})
            self.assertEqual([game["id"] for game in found], ["1091500", "620"])
            self.assertEqual(found[0]["last"], 1750000000)
            self.assertTrue(found[0]["art"].endswith("/1091500/library_600x900.jpg"))
            self.assertTrue(found[1]["art"].endswith("/620_header.jpg"))
            self.assertEqual((found[0]["play"], found[0]["windows"]), ("1091500", ""))
            # Heroic's (its own play times), and the games Monet sent to Windows; the latest of a
            # game on both sides counts.
            heroic = Path(tmp) / "heroic"
            (heroic / "legendaryConfig/legendary").mkdir(parents=True)
            (heroic / "store").mkdir()
            (heroic / "legendaryConfig/legendary/installed.json").write_text(json.dumps(
                {"Sugar": {"app_name": "Sugar", "title": "Rocket League", "install_path": "/games/Sugar"}}))
            (heroic / "store/timestamp.json").write_text(json.dumps(
                {"Sugar": {"firstPlayed": "2026-01-01T10:00:00.000Z", "lastPlayed": "2026-10-20T18:00:00.000Z", "totalPlayed": 300}}))
            games = Path(tmp) / "games.json"
            games.write_text(json.dumps({"v": 1, "games": [{"id": "riot:valorant", "name": "VALORANT"},
                                                           {"id": "steam:620", "name": "Portal 2"}]}))
            quick.WINDOWS_GAMES = (games,)
            found = quick.played(heroic_roots=(heroic,), lutris_roots=(),
                                 windows_played={"riot:valorant": 1793000000, "steam:620": 1600000000, "gone:x": 1})
            self.assertEqual([g["id"] for g in found], ["riot:valorant", "heroic:legendary:Sugar", "1091500", "620"])
            self.assertEqual((found[0]["play"], found[0]["windows"], found[0]["name"]), ("", "riot:valorant", "VALORANT"))
            self.assertEqual((found[1]["play"], found[1]["last"]), ("heroic:legendary:Sugar", 1792519200))
            self.assertEqual(found[3]["play"], "620")  # played here after it was played in Windows
        quick.TRIP_APPS_OFF = Path(tmp) / "off"
        with tempfile_dir() as tmp:
            quick.PLAYED_WINDOWS, quick.TRIP_APPS = Path(tmp) / "played-windows.json", Path(tmp) / "trip-apps.json"
            quick.remember_apps([], game="riot:valorant")
            quick.remember_apps([], game="bad id; rm")
            self.assertEqual(list(json.loads(quick.PLAYED_WINDOWS.read_text())), ["riot:valorant"])

    def test_downloads_are_where_the_account_keeps_them(self):
        import tempfile
        quick = quick_helper()
        with tempfile.TemporaryDirectory() as tmp:
            quick.HOME, quick.CONFIG = Path(tmp), Path(tmp) / ".config"
            self.assertEqual(quick.downloads_dir(), Path(tmp) / "Downloads")
            quick.CONFIG.mkdir()
            (quick.CONFIG / "user-dirs.dirs").write_text('XDG_DOWNLOAD_DIR="$HOME/Hämtningar"\n', encoding="utf-8")
            self.assertEqual(quick.downloads_dir(), Path(tmp) / "Hämtningar")

    def test_the_overlay_switches_and_keeps_your_own_look(self):
        import tempfile
        quick = quick_helper()
        with tempfile.TemporaryDirectory() as tmp:
            quick.OVERLAY, quick.MANGOHUD_CONF = Path(tmp) / "environment.d/monet-mangohud.conf", Path(tmp) / "MangoHud.conf"
            quick.set_overlay(True)
            self.assertIn("MANGOHUD=1", quick.OVERLAY.read_text())
            self.assertIn("round_corners=10", quick.MANGOHUD_CONF.read_text())  # Monet's colors, the first time
            quick.MANGOHUD_CONF.write_text("fps\n")
            quick.set_overlay(False)
            self.assertFalse(quick.OVERLAY.exists())
            quick.set_overlay(True)
            self.assertEqual(quick.MANGOHUD_CONF.read_text(), "fps\n")  # someone's own is never replaced

    def test_whats_new_comes_from_this_releases_notes(self):
        found = quick_helper().whats_new((ROOT / "RELEASE_NOTES.md").read_text(encoding="utf-8"))
        self.assertEqual(found["version"], (ROOT / "VERSION").read_text().strip())
        self.assertGreaterEqual(len(found["items"]), 4)
        for item in found["items"]:
            self.assertTrue(item["title"] and item["text"][-1] in ".!?", item)
        self.assertIn('cp "$ROOT/RELEASE_NOTES.md" "$OUT/share/monet/release-notes.md"', (ROOT / "tools/package.sh").read_text())
        self.assertIn('"$DATADIR/monet/release-notes.md"', (ROOT / "linux/install.sh").read_text())
        session = (ROOT / "linux/libexec/monet-session").read_text()
        self.assertIn('--action=open="$(say "See what\'s new")" --wait', session)
        self.assertIn('[ "$answer" = open ] && "$LIBEXECDIR/monet-quick" open updates', session)
        qml = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('ask("whats-new", out => sheet.whatsNew = sheet.json(out, {}))', qml)

    def test_printers_come_from_cups(self):
        found = quick_helper().printers_from(
            "HP_OfficeJet\nBrother\nCanon_Found_On_Wifi\n",
            "printer HP_OfficeJet is idle.  enabled since Thu 22 Oct\nprinter Brother now printing Brother-12.  enabled since x\n",
            "system default destination: HP_OfficeJet\n",
            "Brother-12   jon   1024   Thu 22 Oct\nBrother-13   jon   2048   Thu 22 Oct\n")
        self.assertEqual([(p["label"], p["state"], p["jobs"], p["default"]) for p in found],
                         [("HP OfficeJet", "ready", 0, True), ("Brother", "printing", 2, False),
                          ("Canon Found On Wifi", "ready", 0, False)])

    def test_lock_privacy_and_the_rest_go_to_kde_by_name(self):
        quick = quick_helper()
        for page, kcm in (("gamecontroller", "kcm_gamecontroller"), ("screenlocker", "kcm_screenlocker"),
                          ("recentfiles", "kcm_recentFiles"), ("printers", "kcm_printer_manager"), ("keys", "kcm_keys")):
            self.assertEqual(quick.KDE_PAGES[page], kcm)
        source = (ROOT / "linux/libexec/monet-quick").read_text()
        self.assertIn('"DeleteRecentStats", "sis", "", "0", "everything"', source)
        self.assertIn('kwrite("kscreenlockerrc", "Daemon", "LockOnResume"', source)
        self.assertEqual(quick.LOCK_TIMES, (1, 5, 15, 30, 0))
        qml = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn("options: [[1, i18n(\"1 min\")], [5, i18n(\"5 min\")], [15, i18n(\"15 min\")], [30, i18n(\"30 min\")]", qml)
        self.assertIn('onClicked: sheet.ask("kde keys")', qml)

    def test_every_page_has_its_picture(self):
        qml = (SETTINGS_QML).read_text()
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
        qml = (SETTINGS_QML).read_text(encoding="utf-8")
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
            self.assertIn("clockFormat.time(", clock.read_text(encoding="utf-8"))

    def test_power_input_notifications_and_apps_are_monets(self):
        qml = (SETTINGS_QML).read_text(encoding="utf-8")
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
        self.assertTrue(set(times("batterySleepTimes")) <= set(helper.SLEEP_TIMES))
        # KDE's own times (what a new account has) are among the choices, so one is always shown as chosen.
        for name, (group, screen, sleep) in helper.POWER_STATES.items():
            self.assertIn(screen, times("screenTimes"), name)
            self.assertIn(sleep, times("batterySleepTimes" if name == "battery" else "sleepTimes"), name)
        offered = [[int(v) for v in re.findall(r"\[(\d+), i18n", found)]
                   for found in re.findall(r"options: (\[\[\d+, i18n.*)", qml)]
        self.assertIn(sorted(helper.BUTTON_ACTIONS), [sorted(o) for o in offered])
        self.assertIn(sorted(helper.LID_ACTIONS), [sorted(o) for o in offered])
        places = re.search(r'options: (\[\["clock".*)', qml).group(1)
        self.assertEqual(set(re.findall(r'\["(\w+)", i18n', places)), set(helper.POPUP_PLACES))
        self.assertIn("[3, 5, 10].map(", qml)
        self.assertEqual(helper.POPUP_TIMES, (3, 5, 10))

    def test_quick_settings_opens_it(self):
        main = (self.QUICK / "main.qml").read_text(encoding="utf-8")
        self.assertNotIn("MonetSettings", main)  # an app of its own now (monet-settings)
        self.assertIn('function openSettings(page) {\n        expanded = false\n        run("open " + page)', main)
        self.assertNotIn('asked[0] === "open"', main)
        self.assertFalse((self.QUICK / "MonetSettings.qml").exists())
        self.assertIn('onTapped: root.openSettings("")', main)  # All Settings, a pebble of glass
        # Every tile's chevron opens its page (Night Light's is Display), apart from the switch.
        for page in ("wifi", "bluetooth", "display", "notifications"):
            self.assertIn(f'page: "{page}"', main)
        self.assertEqual(main.count("onOpened: root.openSettings(page)"), 4)
        self.assertIn('" listen")', main)
        self.assertNotIn('connectSource("systemsettings")', main)

    def test_settings_search_speaks_every_language(self):
        # Every page's search words are translated, and a search ignores accents ("ecran" finds "écran").
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertEqual(settings.count('words: i18nc("Settings search words, space-separated",'), 22)
        self.assertNotIn('words: "', settings)
        self.assertIn('const all = fold(entry.name + " " + entry.words)', settings)
        self.assertIn('words.every(word => all.indexOf(word) !== -1)', settings)
        german = (ROOT / "po/de.po").read_text(encoding="utf-8")
        self.assertIn('msgstr "wlan wifi', german)

    def test_app_menu_and_dock_open_it(self):
        entry = (SHARE / "applications/monet-settings.desktop").read_text(encoding="utf-8")
        self.assertIn("Exec=@LIBEXECDIR@/monet-settings\n", entry)
        self.assertIn("SingleMainWindow=true\n", entry)
        self.assertIn("StartupNotify=true\n", entry)
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

    def test_quick_measures_storage_and_finds_the_monet_before(self):
        quick = quick_helper()
        GB = 10**9
        # Home holds the games, your apps and the Trash; the system is what's used besides.
        parts = quick.storage_parts(total=1000 * GB, free=400 * GB, home=450 * GB, games=300 * GB, apps=20 * GB,
                                    user_apps=10 * GB, trash=5 * GB)
        self.assertEqual(parts, {"games": 300 * GB, "apps": 30 * GB, "files": 140 * GB, "system": 130 * GB,
                                 "free": 400 * GB})
        self.assertEqual(sum(parts.values()), 1000 * GB)
        self.assertEqual(quick.storage_parts(100, 10, 0, 0, 0, 0, 0)["system"], 90)
        booted, earlier = {"booted": True, "version": "0.8.3"}, {"version": "0.8.2", "timestamp": 1792000000}
        found = quick.previous_monet({"deployments": [booted, earlier]})
        self.assertEqual((found["version"], found["pending"]), ("0.8.2", False))
        self.assertTrue(quick.previous_monet({"deployments": [earlier, booted]})["pending"])
        self.assertEqual(quick.previous_monet({"deployments": [{"staged": True}, booted]}), {})

    def test_quick_accessibility_takes_only_its_own_values(self):
        from unittest import mock
        quick = quick_helper()
        with mock.patch.object(quick, "kwrite") as kwrite, mock.patch.object(quick, "run") as run, \
                mock.patch.object(quick.subprocess, "Popen") as popen, mock.patch("sys.stderr"):
            for argv in (["access-scale", "130"], ["access-scale", "x"], ["access-cursor", "30"],
                         ["access-motion", "fast"], ["access-reader", "maybe"]):
                quick.main(argv)
            kwrite.assert_not_called()
            run.assert_not_called()
            popen.assert_not_called()

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
            # Error feedback may read the current values, but invalid input must never write.
            for call in run.call_args_list:
                self.assertEqual(call.args[0], "kreadconfig6")

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
        # Saved networks join without asking again; work and school ones want a name too.
        nets = quick.wifi_list(":Harbor:72:WPA2\n:Campus:60:WPA2 802.1X\n", saved={"Harbor"})
        self.assertEqual([(n["name"], n["known"], n["enterprise"]) for n in nets],
                         [("Harbor", True, False), ("Campus", False, True)])

    def test_quick_reads_the_battery(self):
        from unittest import mock
        quick = quick_helper()
        found = lambda **p: quick.battery_state({k: {"type": "x", "data": v} for k, v in p.items()})
        # UPower: every battery together, with how long it lasts (or until full).
        self.assertEqual(found(IsPresent=True, Type=2, Percentage=76.4, State=2, TimeToEmpty=8100),
                         {"battery": 76, "charging": False, "plugged": False, "minutes": 135})
        self.assertEqual(found(IsPresent=True, Type=2, Percentage=40.0, State=1, TimeToFull=2400),
                         {"battery": 40, "charging": True, "plugged": True, "minutes": 40})
        # Full, or held at a charge limit: plugged in, not charging.
        self.assertEqual(found(IsPresent=True, Type=2, Percentage=100.0, State=4)["plugged"], True)
        with mock.patch.object(quick, "Path") as path:
            path.return_value.glob.return_value = []
            self.assertIsNone(quick.battery_state(None)["battery"])

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
        qml = (SETTINGS_QML).read_text()
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

    def test_no_speakers_isnt_called_dummy_output(self):
        # Found by the test bench: Sound said "Playing through Dummy Output" in a VM with no sound card.
        from unittest import mock
        quick = quick_helper()
        answers = {("wpctl", "status"): "Audio\n ├─ Sinks:\n │  *   53. Dummy Output   [vol: 1.00]\n │\n",
                   ("wpctl", "inspect", "53"): 'id 53, type PipeWire:Interface:Node\n  * node.name = "auto_null"\n'}
        with mock.patch.object(quick, "run", lambda *args, **kw: answers.get(args)):
            self.assertEqual(quick.outputs(), [{"id": 53, "name": "Dummy Output", "default": True, "none": True}])
        qml = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('i18n("No speakers or headphones")', qml)
        self.assertIn("model: soundColumn.speakers", qml)

    def test_no_wifi_row_without_wifi(self):
        # NetworkManager says Wi-Fi is enabled on a PC that has none (the test bench's VM, on a cable).
        from unittest import mock
        quick = quick_helper()
        for devices, expected in (("ethernet\nloopback\n", None), ("wifi\nethernet\n", True)):
            answers = {("nmcli", "-t", "-f", "TYPE", "device"): devices, ("nmcli", "radio", "wifi"): "enabled\n"}
            with mock.patch.object(quick, "run", lambda *args, **kw: answers.get(args)):
                self.assertIs(quick.wifi_state(), expected)

    def test_no_bluetooth_isnt_waited_for(self):
        # bluetoothctl waits forever for an adapter that isn't there: Quick Settings took 3 s a refresh.
        from unittest import mock
        quick = quick_helper()
        with tempfile_dir() as tmp, mock.patch.object(quick, "run") as run:
            self.assertFalse(quick.bluetooth_here(Path(tmp)))
            with mock.patch.object(quick, "bluetooth_here", return_value=False):
                self.assertIsNone(quick.bluetooth_state())
                self.assertEqual(quick.bt_list(), [])
            run.assert_not_called()
            (Path(tmp) / "hci0").mkdir()
            self.assertTrue(quick.bluetooth_here(Path(tmp)))
        main = (ROOT / "linux/share/plasma/plasmoids/org.monet.quick/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn('visible: typeof root.info.volume === "number" || typeof root.info.brightness === "number"', main)
        # And no Wi-Fi or Bluetooth tile on a PC without them, as in Windows (not "Unavailable").
        self.assertIn("visible: root.info.wifi !== null", main)
        self.assertIn("visible: root.info.bluetooth !== null", main)

    def test_play_on_windows_without_windows(self):
        # Found by the test bench: a Monet-only PC was told "Windows isn't ready" and "Not found".
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('readonly property bool noWindows: sheet.pc.windows === "Not found" && ["", "no-space"].includes(sheet.pc.setup || "")', settings)
        self.assertIn('raise Stop("no-space"', (ROOT / "linux/libexec/monet-prepare-windows").read_text(encoding="utf-8"))
        self.assertIn('windowsColumn.noWindows ? i18n("No Windows on this PC")', settings)
        self.assertIn('&& !windowsColumn.noWindows', settings)
        monet = (ROOT / "crates/monet/src/main.rs").read_text(encoding="utf-8")
        self.assertIn('Err(_) => t!("Not found").to_string(),', monet)  # what Settings looks for, in English
        games = (ROOT / "linux/share/monet/games/Games.qml").read_text(encoding="utf-8")
        self.assertIn('run(["monet"], out => root.windowsHere = !/Windows\\s+(Not found|Unavailable)/.test(out))', games)

    def test_search_enter_opens_the_page_called_that(self):
        # Found by the test bench: "Games" and Enter opened Storage, which mentions games.
        qml = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn("shown.find(p => side.fold(p.name) === typed)", qml)

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
        with mock.patch.object(quick, "run", run), mock.patch.object(quick, "ok", run), contextlib.redirect_stderr(io.StringIO()):
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
                         {"login": "claude", "name": "Claude Monet", "picture": "", "admin": True, "you": True, "guest": False})
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
        qml = (SETTINGS_QML).read_text(encoding="utf-8")
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

    def test_no_game_is_listed_that_windows_doesnt_have(self):
        # Slay the Spire was, for testing; found by the test bench in a Monet with no Windows at all.
        games = json.loads((SHARE / "monet/windows-games.json").read_text())
        self.assertEqual(games["games"], [])


class WhatOtherSystemsHave(unittest.TestCase):
    """0.8.5: each app's volume, battery care, a hotspot, the Batteries widget and a welcome."""
    SETTINGS = SETTINGS_QML

    def test_each_app_has_its_volume(self):
        quick = quick_helper()
        status = ("Audio\n ├─ Sinks:\n │  *   52. Built-in Audio Analog Stereo        [vol: 0.40]\n │\n"
                  " └─ Streams:\n        81. Firefox\n             82. output_FL       > Built-in Audio:playback_FL\t[active]\n"
                  "        95. Discord\n             96. input_FL        < Built-in Audio:capture_FL\t[active]\n\n"
                  "Video\n └─ Streams:\n        99. obs\n             100. output_0       > Camera:input_0\t[active]\n")
        # Apps that play, not ones that only record, nor video.
        self.assertEqual(quick.app_streams(status), [(81, "Firefox")])
        self.assertEqual(quick.sinks(status)[0]["id"], 52)
        settings = self.SETTINGS.read_text(encoding="utf-8")
        self.assertIn('onMoved: value => sheet.queue("app-volume " + modelData.id, value)', settings)
        panel = (PLASMA / "plasmoids/org.monet.quick/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn("onTapped: root.playThrough(place.modelData)", panel)

    def test_battery_care_stops_at_80(self):
        import tempfile
        quick = quick_helper()
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(quick.battery_care(Path(tmp)), {"supported": False, "limit": 100})
            (Path(tmp) / "BAT0").mkdir()
            (Path(tmp) / "BAT0/charge_control_end_threshold").write_text("80\n")
            self.assertEqual(quick.battery_care(Path(tmp)), {"supported": True, "limit": 80})
        # Root writes only the limit, only 80 or 100; it's kept and put back at every start.
        charge = (ROOT / "linux/libexec/monet-charge").read_text()
        self.assertIn("    80|100) limit=$1 ;;", charge)
        self.assertIn('KEPT=/var/lib/monet/charge-limit', charge)
        unit = (ROOT / "linux/systemd/monet-charge.service").read_text()
        self.assertIn("ExecStart=@LIBEXECDIR@/monet-charge apply", unit)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('\\"$LIBEXECDIR/monet-charge\\"', install)
        self.assertIn("monet-charge.service", install)
        self.assertIn('run("pkexec", f"{LIBEXECDIR}/monet-charge", args[0], timeout=60)',
                      (ROOT / "linux/libexec/monet-quick").read_text())

    def test_hotspot_shares_the_internet(self):
        quick = (ROOT / "linux/libexec/monet-quick").read_text()
        self.assertIn('["nmcli", "device", "wifi", "hotspot"]', quick)
        settings = self.SETTINGS.read_text(encoding="utf-8")
        self.assertIn('sheet.ask(on ? "hotspot-on" : "hotspot-off"', settings)

    def test_batteries_list_this_laptop_first(self):
        quick = quick_helper()
        found = quick.battery_list([
            {"Type": 5, "Model": "MX Master 3", "Percentage": 91.0, "State": 2},
            {"Type": 1, "Percentage": 0.0},  # the mains
            {"Type": 2, "PowerSupply": True, "IsPresent": False, "Percentage": 0.0},  # an empty second bay
            {"Type": 2, "PowerSupply": True, "IsPresent": True, "Percentage": 76.4, "State": 1},
            {"Type": 12, "Model": "DualSense", "Percentage": 18.0, "State": 2},
        ])
        self.assertEqual([(b["kind"], b["level"], b["charging"]) for b in found],
                         [("laptop", 76, True), ("mouse", 91, False), ("controller", 18, False)])
        widget = (PLASMA / "plasmoids/org.monet.batteries/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn('onTriggered: runner.connectSource(root.helper + " batteries")', widget)
        ring = widget.split("component Ring")[1].split("fullRepresentation")[0]
        self.assertNotIn("root.", ring)  # an inline component can't see the widget's ids

    def test_ready_when_you_come_back(self):
        import importlib.machinery
        import importlib.util
        import tempfile
        from unittest import mock
        loader = importlib.machinery.SourceFileLoader("monet_ready", str(ROOT / "linux/libexec/monet-ready"))
        spec = importlib.util.spec_from_loader("monet_ready", loader)
        ready = importlib.util.module_from_spec(spec)
        loader.exec_module(ready)

        def option(name, path):
            # An EFI load option: attributes, the path's length, the name and the path (UTF-16).
            text = (name + "\0" + path + "\0").encode("utf-16-le")
            return b"\x07\0\0\0" + b"\x01\0\0\0" + len(path).to_bytes(2, "little") + text

        with tempfile.TemporaryDirectory() as tmp:
            efi = Path(tmp)
            self.assertFalse(ready.boots_windows_next(efi))  # no BootNext: a plain start
            (efi / f"BootNext-{ready.GLOBAL}").write_bytes(b"\x07\0\0\0\x01\0")
            (efi / f"Boot0001-{ready.GLOBAL}").write_bytes(option("Windows Boot Manager", r"\EFI\Microsoft\Boot\bootmgfw.efi"))
            self.assertTrue(ready.boots_windows_next(efi))
            (efi / f"Boot0001-{ready.GLOBAL}").write_bytes(option("Monet", r"\EFI\fedora\shimx64.efi"))
            self.assertFalse(ready.boots_windows_next(efi))

            # Armed on the way to Windows, the next start signs in by itself, once.
            state = Path(tmp) / "state"
            paths = {"STATE": state, "USER": state / "ready-user", "ARMED": state / "ready-armed",
                     "DROPIN": Path(tmp) / "plasmalogin.conf.d/zz-monet-ready.conf", "FLAG": Path(tmp) / "run/ready-auto"}
            with mock.patch.multiple(ready, **paths), mock.patch.object(ready, "kept_user", return_value="claude"), \
                    mock.patch.object(ready, "boots_windows_next", return_value=True):
                self.assertEqual(ready.main(["arm"]), 0)
                self.assertTrue(paths["ARMED"].exists())
                ready.main(["boot"])
                self.assertIn("[Autologin]\nUser=claude\nSession=plasma.desktop", paths["DROPIN"].read_text())
                self.assertEqual(paths["FLAG"].read_text().strip(), "claude")
                self.assertFalse(paths["ARMED"].exists())
                ready.main(["boot"])  # the start after asks for the password again
                self.assertFalse(paths["DROPIN"].exists())
                # Armed long ago (a trip that never came back to Monet): no automatic sign-in.
                paths["ARMED"].write_text("1000\n")
                ready.main(["boot"])
                self.assertFalse(paths["DROPIN"].exists())
        # The session locks before the desktop shows, and only one that signed in by itself.
        unit = (ROOT / "linux/systemd/user/monet-ready-lock.service").read_text()
        for line in ("ConditionPathExists=/run/monet/ready-auto", "Before=plasma-plasmashell.service",
                     "ExecStart=@LIBEXECDIR@/monet-quick ready-lock"):
            self.assertIn(line, unit)
        quick = (ROOT / "linux/libexec/monet-quick").read_text()
        self.assertIn('if service in ("", "plasmalogin-autologin") or "autologin" in service:', quick)
        self.assertIn("Before=display-manager.service", (ROOT / "linux/systemd/monet-ready-boot.service").read_text())
        self.assertIn("ExecStop=@LIBEXECDIR@/monet-ready arm", (ROOT / "linux/systemd/monet-ready-leave.service").read_text())
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('\\"$LIBEXECDIR/monet-ready\\"', install)
        self.assertIn("systemctl --global enable monet-ready-lock.service", install)
        settings = self.SETTINGS.read_text(encoding="utf-8")
        self.assertIn('sheet.ask(on ? "ready-on" : "ready-off"', settings)

    def test_last_start_shows_where_the_time_went(self):
        quick = quick_helper()
        found = quick.startup("Startup finished in 7.216s (firmware) + 3.008s (loader) + 1.240s (kernel) + 2.531s (initrd)"
                              " + 1min 2.302s (userspace) = 1min 16.297s", 10_000_000, 16_500_000)
        self.assertEqual(found, {"pc": 7.2, "monet": 69.1, "desktop": 6.5, "total": 82.8})
        self.assertEqual(quick.startup("Bootup is not yet finished"), {})
        self.assertIn('ask("startup", out => sheet.startup = sheet.json(out, {}))', self.SETTINGS.read_text(encoding="utf-8"))

    def test_a_new_account_is_welcomed_once(self):
        session = (ROOT / "linux/libexec/monet-session").read_text()
        self.assertIn('touch "$looks/welcomed"', session)
        self.assertIn('"$LIBEXECDIR/monet-quick" open welcome', session)
        self.assertIn('args[0] in PAGES or args[0] == "welcome"', (ROOT / "linux/libexec/monet-quick").read_text())
        settings = self.SETTINGS.read_text(encoding="utf-8")
        self.assertIn("welcome: welcomePage", settings)
        self.assertIn('destination[0] === "welcome" || pages.some(p => p.id === destination[0])', settings)


class EasierOnOlderPCs(unittest.TestCase):
    """0.8.5: 8 GB of memory or less, or a spinning disk, and Monet goes easier on the PC."""

    def test_what_counts_as_older(self):
        import tempfile
        from unittest import mock
        quick = quick_helper()
        with tempfile.TemporaryDirectory() as tmp:
            meminfo = Path(tmp) / "meminfo"
            meminfo.write_text("MemTotal:        8040000 kB\n")  # an 8 GB laptop's 7.7
            self.assertTrue(quick.older_pc(meminfo, spinning=False))
            meminfo.write_text("MemTotal:       16300000 kB\n")
            self.assertFalse(quick.older_pc(meminfo, spinning=False))
            self.assertTrue(quick.older_pc(meminfo, spinning=True))
            # The disk under /sysroot, as lsblk tells it.
            answers = {"findmnt": "/dev/sda3\n", "lsblk": "1\n"}
            with mock.patch.object(quick, "run", lambda *a, **k: answers.get(a[0])):
                self.assertTrue(quick.older_pc(meminfo))
            answers["lsblk"] = "0\n"
            with mock.patch.object(quick, "run", lambda *a, **k: answers.get(a[0])):
                self.assertFalse(quick.older_pc(meminfo))
        self.assertFalse(quick.older_pc(Path("/nonexistent/meminfo"), spinning=False))

    def test_sign_in_goes_easier(self):
        session = (ROOT / "linux/libexec/monet-session").read_text()
        self.assertIn('older_pc="$("$LIBEXECDIR/monet-quick" older-pc 2>/dev/null)"', session)
        self.assertIn(': > "$looks/glass-lite"', session)
        # Files: names only, once, unless it's been chosen.
        self.assertIn("put --default-only --file baloofilerc --group General --key 'only basic indexing' true",
                      session)
        # Steam: hidden from autostart (only Monet's own copy is ever replaced or removed), started later.
        self.assertIn("Hidden=true\\nX-Monet=true", session)
        self.assertIn('{ [ ! -e "$steam_later" ] || grep -q \'^X-Monet=true\' "$steam_later"; }', session)
        self.assertIn("--unit=monet-steam-later --on-active=45", session)
        self.assertIn('rm -f "$looks/glass-lite"', session)

    def test_lighter_glass_without_the_lens(self):
        glass = (ROOT / "linux/share/monet/widgets/Glass.qml").read_text(encoding="utf-8")
        self.assertIn('nameFilters: ["glass-lite"]', glass)
        # Nor on matte glass (Settings' Glass slider): only the painting's color comes through it.
        self.assertIn("readonly property bool lensed: !lite && level < 2", glass)
        self.assertIn("visible: glass.frosted && glass.lensed", glass)
        self.assertIn("live: glass.frosted && glass.lensed", glass)
        self.assertIn("readonly property real band: glass.lensed ? glass.lensWidth : 0", glass)


class FilesFromWindows(unittest.TestCase):
    def test_they_go_into_this_accounts_folders(self):
        import tempfile
        quick = quick_helper()
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            staged = home / ".local/share/monet/from-windows"
            for rel in ("Documents/letter.txt", "Documents/Taxes/2025.pdf", "Pictures/sea.jpg"):
                (staged / rel).parent.mkdir(parents=True, exist_ok=True)
                (staged / rel).write_text(rel)
            # A Swedish account: Documents is called Dokument; a letter.txt is there already.
            (home / ".config").mkdir()
            (home / ".config/user-dirs.dirs").write_text('XDG_DOCUMENTS_DIR="$HOME/Dokument"\nXDG_PICTURES_DIR="$HOME/Bilder"\n')
            (home / "Dokument").mkdir()
            (home / "Dokument/letter.txt").write_text("mine")
            self.assertEqual(quick.bring_files(home), 3)
            self.assertEqual((home / "Dokument/letter.txt").read_text(), "mine")
            self.assertEqual((home / "Dokument/letter (Windows).txt").read_text(), "Documents/letter.txt")
            self.assertTrue((home / "Dokument/Taxes/2025.pdf").is_file())
            self.assertTrue((home / "Bilder/sea.jpg").is_file())
            self.assertFalse(staged.exists())
            self.assertEqual(quick.bring_files(home), 0)
        session = (ROOT / "linux/libexec/monet-session").read_text()
        self.assertIn('"$LIBEXECDIR/monet-quick" bring-files', session)


def libexec_helper(name):
    """One of Monet's helpers in linux/libexec, loaded as a module (they have no .py)."""
    loader = importlib.machinery.SourceFileLoader(name.replace("-", "_"), str(ROOT / "linux/libexec" / name))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def keep_helper():
    return libexec_helper("monet-keep")


class Backups(unittest.TestCase):
    """0.9: earlier versions every hour, and a copy on a drive."""

    def test_snapshots_thin_out_like_time_machine(self):
        from datetime import datetime, timedelta
        keep = keep_helper()
        now = datetime(2026, 10, 23, 14, 0)
        names = [(now - timedelta(hours=h)).strftime(keep.STAMP) for h in range(0, 24 * 80)]
        gone = set(keep.thin(names, now))
        kept = [n for n in names if n not in gone]
        # The last day, every hour; then one a day for two weeks, one a week for two months.
        self.assertEqual(sum(1 for n in kept if now - datetime.strptime(n, keep.STAMP) <= timedelta(days=1)), 25)
        days = {datetime.strptime(n, keep.STAMP).date() for n in kept
                if timedelta(days=1) < now - datetime.strptime(n, keep.STAMP) <= timedelta(days=14)}
        self.assertEqual(len(days), 14)
        self.assertLessEqual(len(kept), 25 + 14 + 9)
        self.assertTrue(all(now - datetime.strptime(n, keep.STAMP) <= timedelta(weeks=9) for n in kept))
        # The newest of each day stays.
        self.assertIn((now - timedelta(days=3)).replace(hour=23).strftime(keep.STAMP), kept)
        self.assertEqual(keep.thin(["not a time"], now), [])

    def test_the_homes_become_a_subvolume_only_before_sign_in(self):
        keep = (ROOT / "linux/libexec/monet-keep").read_text()
        prepare = keep.split("def prepare", 1)[1].split("\ndef ", 1)[0]
        self.assertIn("or signed_in()", prepare)
        self.assertIn('"--reflink=always"', prepare)
        # Put back after a stop between the renames.
        self.assertIn("if not home.exists() and old.is_dir():", prepare)
        unit = (ROOT / "linux/systemd/monet-keep-prepare.service").read_text()
        self.assertIn("Before=display-manager.service plasmalogin.service", unit)
        self.assertIn("OnCalendar=hourly", (ROOT / "linux/systemd/monet-keep.timer").read_text())
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('put 755 "$SRC/libexec/monet-keep" "$LIBEXECDIR/monet-keep"', install)
        self.assertIn('\\"$LIBEXECDIR/monet-keep\\"', install)
        self.assertIn("systemctl enable monet-keep-prepare.service monet-keep.timer", install)
        self.assertIn("systemctl --global enable monet-backup.timer", install)
        uninstall = (ROOT / "linux/uninstall.sh").read_text()
        self.assertIn('"$PREFIX/libexec/monet-keep" off', uninstall)

    def test_earlier_versions_of_a_file(self):
        import os
        import tempfile
        quick = quick_helper()
        with tempfile.TemporaryDirectory() as tmp:
            homes, snaps = Path(tmp) / "home", Path(tmp) / "snapshots"
            letter = homes / "ann/Documents/letter.txt"
            letter.parent.mkdir(parents=True)
            letter.write_text("now")
            for name, text, stamp in (("2026-10-23 14.00", "now", None), ("2026-10-23 13.00", "noon", 1792000000),
                                      ("2026-10-23 12.00", "noon", 1792000000), ("2026-10-22 09.00", "morning", 1791900000)):
                there = snaps / name / "ann/Documents/letter.txt"
                there.parent.mkdir(parents=True)
                there.write_text(text)
                os.utime(there, (stamp, stamp) if stamp else os.stat(letter)[7:9])
            found = quick.versions(letter, snaps, homes)
            # The same as now, and the same as the one after it, aren't listed twice.
            self.assertEqual([v["name"] for v in found], ["2026-10-23 13.00", "2026-10-22 09.00"])
            back = quick.put_back(found[1], letter)
            self.assertEqual(back.name, "letter (2026-10-22 09.00).txt")
            self.assertEqual(back.read_text(), "morning")
            self.assertEqual(letter.read_text(), "now")
            self.assertEqual(quick.versions(Path(tmp) / "elsewhere.txt", snaps, homes), [])
        names = ["2026-10-23 14.00", "2026-10-23 13.00", "2026-10-22 13.00", "2026-10-15 09.00"]
        now = quick.snapshot_time("2026-10-23 14.30")
        self.assertEqual({k: v and v["name"] for k, v in quick.look_back(names, now).items()},
                         {"hour": "2026-10-23 13.00", "day": "2026-10-22 13.00", "week": "2026-10-15 09.00"})

    def test_the_drives_a_copy_can_go_on(self):
        quick = quick_helper()
        listing = [
            {"path": "/dev/nvme0n1", "tran": "nvme", "hotplug": False, "children": [
                {"path": "/dev/nvme0n1p3", "uuid": "aaaa", "fstype": "btrfs", "label": "monet", "size": 900}]},
            {"path": "/dev/sdb", "tran": "usb", "hotplug": True, "children": [
                {"path": "/dev/sdb1", "uuid": "1234-ABCD", "fstype": "exfat", "label": "T7", "size": 10**12,
                 "mountpoints": ["/run/media/ann/T7"]}]},
            {"path": "/dev/sdc", "tran": "usb", "hotplug": True, "children": [
                {"path": "/dev/sdc1", "uuid": "5678-EF01", "fstype": "vfat", "label": "Monet-0.8.5", "size": 8}]},
        ]
        self.assertEqual(quick.backup_drives(listing), [{"uuid": "1234-ABCD", "label": "T7", "size": 10**12,
                                                         "fstype": "exfat", "mount": "/run/media/ann/T7"}])
        code = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        run = code.split("def backup_run", 1)[1].split("\ndef ", 1)[0]
        # What a copy replaces or deletes is kept beside it; games aren't copied.
        self.assertIn('"--delete", "--backup"', run)
        self.assertIn('"/.local/share/Steam/steamapps/"', code)
        self.assertIn("rsync", (ROOT / "image/Containerfile").read_text())

    def test_settings_and_files_have_it(self):
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn("backups: backupsPage", settings)
        self.assertIn('sheet.ask("keep " + (on ? "on" : "off")', settings)
        self.assertIn('onClicked: sheet.ask("put-back " + index)', settings)
        self.assertTrue((SHARE / "monet/settings/swatch-backups.png").is_file())
        menu = (SHARE / "kio/servicemenus/monet-earlier.desktop").read_text(encoding="utf-8")
        self.assertIn("Exec=@LIBEXECDIR@/monet-quick earlier %f", menu)
        self.assertIn("X-Monet=true", menu)
        self.assertIn("Name[sv]=", menu)


class ScreensForGames(unittest.TestCase):
    def test_hdr_and_smoother_games_where_the_screen_can(self):
        from unittest import mock
        quick = quick_helper()
        outputs = [{"name": "eDP-1", "enabled": True},  # a laptop panel that can do neither
                   {"name": "DP-1", "enabled": True, "hdr": False, "vrrPolicy": 2},
                   {"name": "HDMI-A-1", "enabled": True, "vrrPolicy": 0},
                   {"name": "DP-2", "enabled": False, "hdr": True}]
        self.assertEqual(quick.screen_features(outputs), [{"name": "DP-1", "hdr": False, "vrr": True},
                                                          {"name": "HDMI-A-1", "hdr": None, "vrr": False}])
        said = []
        with mock.patch.object(quick, "run", lambda *a, **k: said.append(a)):
            quick.set_screen_feature("DP-1", "hdr", True)
            quick.set_screen_feature("DP-1", "vrr", True)
            quick.set_screen_feature("HDMI-A-1", "vrr", False)
            quick.set_screen_feature("x; rm -rf ~", "hdr", True)
        self.assertEqual(said, [("kscreen-doctor", "output.DP-1.hdr.enable"), ("kscreen-doctor", "output.DP-1.vrrpolicy.automatic"),
                                ("kscreen-doctor", "output.HDMI-A-1.vrrpolicy.never")])
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('ask("screen-" + what + " " + name + (on ? " on" : " off")', settings)


class TheHoursFollowTheSun(unittest.TestCase):
    """0.9: the lights come at this place's sunrise and sunset, under its weather."""
    HOURS = PLASMA / "wallpapers/org.monet.hours/contents/ui/main.qml"

    def test_sunrise_and_sunset(self):
        try:
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtQml import QJSEngine
        except ImportError as e:
            self.skipTest(f"no Qt for Python ({e})")
        app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841 (QJSEngine needs one)
        qml = self.HOURS.read_text(encoding="utf-8")
        js = QJSEngine()
        js.evaluate(re.search(r"\n    (function sun\(.*?\n    })\n", qml, re.S).group(1))

        def day(args):
            found = js.evaluate(f"JSON.stringify(sun({args}))").toString()
            times = json.loads(found)
            return times and (times["set"] - times["rise"]) % 1440

        # Stockholm: 18 h 37 min at midsummer, 6 h 4 min at midwinter; Svalbard's sun doesn't set in June.
        self.assertAlmostEqual(day("59.33, 18.07, new Date(2026, 5, 21)"), 1117, delta=6)
        self.assertAlmostEqual(day("59.33, 18.07, new Date(2026, 11, 21)"), 364, delta=6)
        self.assertIsNone(day("78.22, 15.65, new Date(2026, 5, 21)"))

    def test_place_and_weather(self):
        import tempfile
        quick = quick_helper()
        with tempfile.TemporaryDirectory() as tmp:
            applets = Path(tmp) / "appletsrc"
            applets.write_text("[Containments][1][Applets][23]\nplugin=org.monet.weather\n\n"
                               "[Containments][1][Applets][23][Configuration][General]\nlatitude=49.49\nlongitude=0.11\n")
            tab = Path(tmp) / "zone1970.tab"
            tab.write_text("# comment\nSE\t+5920+01803\tEurope/Stockholm\nAR\t-3436-05827\tAmerica/Argentina/Buenos_Aires\n")
            # The Weather widget's place first, then the time zone's city.
            self.assertEqual(quick.place(applets, tab, "Europe/Stockholm"), "49.49,0.11")
            applets.write_text("")
            self.assertEqual(quick.place(applets, tab, "Europe/Stockholm"), "59.33,18.05")
            self.assertEqual(quick.place(applets, tab, "America/Argentina/Buenos_Aires"), "-34.60,-58.45")
            self.assertEqual(quick.place(applets, tab, "Etc/UTC"), "")
        light = (ROOT / "linux/libexec/monet-light").read_text()
        self.assertIn("d.writeConfig('Place', '$where');", light)
        qml = self.HOURS.read_text(encoding="utf-8")
        self.assertIn('"https://api.open-meteo.com/v1/forecast?latitude="', qml)
        self.assertIn("if (root.configuration.Weather === false || !place) {", qml)
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('["weather", i18n("Weather"),', settings)

class WhichSideAGamePlaysOn(unittest.TestCase):
    def test_marks_from_areweanticheatyet(self):
        import tempfile
        quick = quick_helper()
        listed = [{"name": "Slay the Spire", "status": "Supported", "storeIds": {"steam": "646570"}},
                  {"name": "Apex Legends", "status": "Denied", "storeIds": {"steam": "1172470"}},
                  {"name": "Rainbow Six Siege", "status": "Broken", "storeIds": {"steam": "359550"}},
                  {"name": "Escape from Tarkov", "status": "Planned", "storeIds": {}},
                  {"name": "Elden Ring", "status": "Running", "storeIds": {"steam": "1245620"}},
                  "not a game"]
        marks = quick.anticheat_marks(listed)
        self.assertEqual(marks, {"646570": "here", "1172470": "windows", "359550": "windows", "1245620": "here"})
        with tempfile.TemporaryDirectory() as tmp:
            games = Path(tmp) / "games.json"
            games.write_text(json.dumps({"v": 1, "games": [{"id": "steam:646570", "name": "Slay the Spire"},
                                                           {"id": "riot:valorant", "name": "Valorant"},
                                                           {"id": "steam:1172470", "name": "Apex Legends"}]}))
            windows = quick.windows_steam_ids([games, Path(tmp) / "missing.json"])
        self.assertEqual(windows, {"646570", "1172470"})
        # Installed here: Apex (on Windows too) and Siege (only here) need Windows; Elden Ring doesn't.
        here = {"1172470": "Apex Legends", "359550": "Rainbow Six Siege", "1245620": "ELDEN RING"}
        found = quick.game_marks(marks, here, windows, set())
        self.assertEqual(found["blocked"], [{"id": "1172470", "name": "Apex Legends", "onWindows": True, "shared": False},
                                            {"id": "359550", "name": "Rainbow Six Siege", "onWindows": False, "shared": False}])
        self.assertEqual(found["marks"]["646570"], "here")
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('text: i18n("Which games need Windows comes from AreWeAntiCheatYet and ProtonDB.")', settings)
        # Epic's games by namespace, as Heroic's library knows them.
        fortnite = {"name": "Fortnite", "status": "Denied", "storeIds": {"epic": {"namespace": "fn", "slug": "fortnite"}}}
        self.assertEqual(quick.anticheat_marks([fortnite])["epic/fn"], "windows")

    def test_what_you_play_comes_first(self):
        q = quick_helper()
        now = 1_800_000_000
        steam = {"10": "Zeta", "11": "Alpha", "12": "Mid", "13": "Old Favourite"}
        lasts = {"steam:10": now - 3600, "steam:12": now - 5 * 86400, "steam:13": now - 90 * 86400}
        names = [g["name"] for g in q.library({}, steam, [], [], set(), False, [], {}, {}, lasts, now)]
        # Played this month, newest first; then the rest (one played long ago too) by name.
        self.assertEqual(names, ["Zeta", "Mid", "Alpha", "Old Favourite"])
        quick = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn('games = library(lasts={g["key"]: g["last"] for g in stats}, minutes={g["key"]: g.get("minutes", 0) for g in stats})', quick)

    def test_players_reports_from_protondb(self):
        q = quick_helper()
        now = 1_800_000_000
        kept = {"10": ["borked", "borked", now], "20": ["borked", "gold", now], "30": ["platinum", "platinum", now - 8 * 86400],
                "40": ["", "", now], "50": "junk"}
        # Borked lately too: Windows. A game players got going again plays here.
        self.assertEqual(q.proton_marks(kept), {"10": "windows"})
        self.assertEqual(q.protondb_stale(["10", "30", "50", "60"], kept, now), ["30", "50", "60"])
        found = {g["id"]: g for g in q.library({"20": "here"}, {"10": "Broken Game", "20": "Fine Game", "30": "Siege"},
                                               [], [], set(), False, [], {}, {"10": "windows", "30": "windows"})}
        self.assertEqual((found["steam:10"]["plays"], found["steam:10"]["why"]), ("windows", "reports"))
        self.assertEqual((found["steam:20"]["plays"], found["steam:20"]["why"]), ("monet", ""))
        # Only for a game Steam runs through Proton (its Windows build here): a Linux build of its
        # own isn't judged by Proton reports.
        from unittest import mock
        with tempfile_dir() as tmp:
            steam = Path(tmp) / "Steam"
            (steam / "steamapps/common/Broken Game/Binaries/Win64").mkdir(parents=True)
            (steam / "steamapps/common/Broken Game/Binaries/Win64/Game.exe").write_bytes(b"MZ")
            (steam / "steamapps/common/Native Game/bin").mkdir(parents=True)
            (steam / "steamapps/common/Native Game/bin/game").write_bytes(b"\x7fELF")
            self.assertTrue(q.windows_build(steam, {"installdir": "Broken Game"}))
            self.assertFalse(q.windows_build(steam, {"installdir": "Native Game"}))
            self.assertFalse(q.windows_build(steam, {"installdir": "../.."}))
            found = [(steam, "10", "Broken Game", {"installdir": "Broken Game"}), (steam, "11", "Native Game", {"installdir": "Native Game"})]
            with mock.patch.object(q, "protondb_kept", lambda: {"10": ["borked", "borked", now], "11": ["borked", "borked", now]}):
                self.assertEqual(q.proton_reports(found), {"10": "windows"})
        if not hasattr(os, "geteuid"):
            return  # fcntl
        from unittest import mock
        with tempfile_dir() as tmp, mock.patch.object(q, "PROTONDB", Path(tmp) / "protondb.json"), \
                mock.patch.object(q, "PROTONDB_LOCK", Path(tmp) / "protondb.lock"):
            answers = {"10": {"tier": "borked", "trendingTier": "borked"}, "20": {}, "30": None}
            self.assertEqual(q.protondb_refresh(["10", "20", "30"], answers.get), 2)   # offline at 30: next time
            self.assertEqual(q.protondb_kept()["10"][:2], ["borked", "borked"])
            self.assertEqual(q.protondb_kept()["20"][:2], ["", ""])                     # nobody reported: not again this week
        games = GAMES_APP.read_text(encoding="utf-8")
        self.assertIn('if (game.plays === "windows" && game.why === "reports")\n            items.push(["monet", i18n("Play in Monet")])', games)

    def test_heroic_games_from_its_own_files(self):
        import tempfile
        quick = quick_helper()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "heroic"

            def put(path, value):
                (root / path).parent.mkdir(parents=True, exist_ok=True)
                (root / path).write_text(json.dumps(value), encoding="utf-8")

            put("legendaryConfig/legendary/installed.json", {
                "Fortnite": {"app_name": "Fortnite", "title": "Fortnite", "is_dlc": False},
                "SomeDLC": {"app_name": "SomeDLC", "title": "A DLC", "is_dlc": True},
                "Sugar": {"app_name": "Sugar", "title": "Rocket League"}})
            put("store_cache/legendary_library.json", {"library": [
                {"app_name": "Fortnite", "title": "Fortnite", "art_cover": "https://cdn.epic/fortnite.jpg", "namespace": "fn"}]})
            put("gog_store/installed.json", {"installed": [{"appName": "1207658924", "platform": "windows"},
                                                           {"appName": "bad name; rm -rf", "platform": "linux"}]})
            put("store_cache/gog_library.json", {"games": [
                {"app_name": "1207658924", "title": "Unreal Tournament 2004", "art_cover": "file:///etc/passwd"},
                {"app_name": "bad name; rm -rf", "title": "Sneaky"}]})
            put("nile_config/nile/installed.json", [{"id": "amzn1.adg.product.abc-123", "path": "/games/x"}])
            put("store_cache/nile_library.json", {"library": [{"app_name": "amzn1.adg.product.abc-123", "title": "Amazon Game"}]})
            put("sideload_apps/library.json", {"games": [{"app_name": "x9Kq_1", "title": "My Game", "is_installed": True},
                                                         {"app_name": "gone", "title": "Removed", "is_installed": False}]})
            put("store_cache/legendary_library.json", {"library": [
                {"app_name": "Fortnite", "title": "Fortnite", "art_cover": "https://cdn.epic/fortnite.jpg", "namespace": "fn"},
                {"app_name": "Kinglet", "title": "Owned, not installed", "art_cover": "https://cdn.epic/kinglet.jpg"}]})
            covers = {}
            found = {(g["runner"], g["app"]): g for g in quick.heroic_games((root, Path(tmp) / "missing"), covers=covers)}
        # Every owned game's cover, for the ones Windows has: only https ones.
        self.assertEqual(covers, {("epic", "Fortnite"): ("https://cdn.epic/fortnite.jpg", ""), ("epic", "Kinglet"): ("https://cdn.epic/kinglet.jpg", "")})
        self.assertEqual(set(found), {("legendary", "Fortnite"), ("legendary", "Sugar"), ("gog", "1207658924"),
                                      ("nile", "amzn1.adg.product.abc-123"), ("sideload", "x9Kq_1")})
        self.assertEqual(found[("legendary", "Fortnite")]["art"], "https://cdn.epic/fortnite.jpg")
        self.assertEqual(found[("legendary", "Fortnite")]["namespace"], "fn")
        self.assertEqual(found[("legendary", "Sugar")]["title"], "Rocket League")  # from installed.json, no cache
        self.assertEqual(found[("gog", "1207658924")]["art"], "")  # only https covers
        self.assertEqual(found[("nile", "amzn1.adg.product.abc-123")]["title"], "Amazon Game")

    def test_one_library_says_where_each_game_plays(self):
        quick = quick_helper()
        marks = {"1172470": "windows", "1245620": "here", "epic/fn": "windows"}
        steam = {"1172470": "Apex Legends", "1245620": "ELDEN RING", "359550": "Rainbow Six Siege"}
        heroic = [{"runner": "legendary", "app": "Fortnite", "title": "Fortnite", "art": "", "namespace": "fn"},
                  {"runner": "gog", "app": "1207658924", "title": "Unreal Tournament 2004", "art": "", "namespace": ""}]
        windows = [{"id": "steam:1172470", "name": "Apex Legends"}, {"id": "riot:valorant", "name": "VALORANT"},
                   {"id": "epic:Fortnite", "name": "Fortnite"}, {"id": "steam:359550", "name": "Rainbow Six Siege"}]
        found = {g["id"]: g for g in quick.library(marks, steam, heroic, windows)}
        self.assertEqual([g["name"] for g in quick.library(marks, steam, heroic, windows)],
                         ["Apex Legends", "ELDEN RING", "Fortnite", "Rainbow Six Siege", "Unreal Tournament 2004", "VALORANT"])
        # Installed here and needing Windows, and on Windows: plays there, one game.
        self.assertEqual((found["steam:1172470"]["plays"], found["steam:1172470"]["windows"]), ("windows", "steam:1172470"))
        self.assertEqual((found["epic:Fortnite"]["plays"], found["epic:Fortnite"]["windows"]), ("windows", "epic:Fortnite"))
        # On both sides with no anti-cheat that minds: plays here.
        self.assertEqual((found["steam:359550"]["plays"], found["steam:359550"]["here"]), ("monet", "steam:359550"))
        self.assertEqual(found["steam:1245620"]["plays"], "monet")
        self.assertEqual((found["gog:1207658924"]["plays"], found["gog:1207658924"]["here"]), ("monet", "heroic:gog:1207658924"))
        self.assertEqual((found["riot:valorant"]["plays"], found["riot:valorant"]["here"]), ("windows", ""))
        self.assertTrue(found["steam:1172470"]["art"].endswith("/1172470/header.jpg"))
        # Installed here, needs Windows, not there yet: Windows, with nothing to start there.
        alone = {g["id"]: g for g in quick.library(marks, steam, [], [])}["steam:1172470"]
        self.assertEqual((alone["plays"], alone["windows"]), ("windows", ""))
        games = GAMES_APP.read_text(encoding="utf-8")
        self.assertIn('run(["helper", "library"], out => {', games)
        self.assertIn('run(["helper", "play", game.here])', games)
        self.assertIn('launch.command = game ? ["monet", "play", game.windows] : ["monet", "windows"]', games)

    def test_play_starts_steam_and_heroic_games_only(self):
        from unittest import mock
        quick = quick_helper()
        started = []
        with mock.patch.object(quick.shutil, "which", lambda name: name in ("xdg-open", "steam")), \
                mock.patch.object(quick.subprocess, "Popen", lambda command, **kw: started.append(command)):
            for game in ("730", "steam:730", "heroic:legendary:Fortnite", "heroic:gog:1207658924"):
                self.assertTrue(quick.PLAYABLE.fullmatch(game))
                quick.play(game)
        # Quietly: Steam in the tray if it wasn't running, Heroic without its window when it's here.
        self.assertEqual(started, [["steam", "-silent", "steam://rungameid/730"], ["steam", "-silent", "steam://rungameid/730"],
                                   ["xdg-open", "heroic://launch?appName=Fortnite&runner=legendary"],
                                   ["xdg-open", "heroic://launch?appName=1207658924&runner=gog"]])
        started.clear()
        with mock.patch.object(quick.shutil, "which", lambda name: name == "heroic"), \
                mock.patch.object(quick.subprocess, "Popen", lambda command, **kw: started.append(command)):
            quick.play("heroic:legendary:Fortnite")
        self.assertEqual(started, [["heroic", "--no-gui", "heroic://launch?appName=Fortnite&runner=legendary"]])
        for game in ("heroic:legendary:a b", "heroic:wine:x", "heroic:gog:..", "epic:Fortnite", "steam:73o", "heroic:gog:a&b=c",
                     "lutris:x1", "lutris:1;rm"):
            self.assertIsNone(quick.PLAYABLE.fullmatch(game))
        started.clear()
        with mock.patch.object(quick.shutil, "which", lambda name: name == "lutris"),                 mock.patch.object(quick.subprocess, "Popen", lambda command, **kw: started.append(command)):
            quick.play("lutris:12")
        self.assertEqual(started, [["lutris", "lutris:rungameid/12"]])

    def test_lutris_games_from_its_own_database(self):
        import sqlite3
        quick = quick_helper()
        with tempfile_dir() as tmp:
            root = Path(tmp) / "lutris"
            (root / "banners").mkdir(parents=True)
            (root / "banners/celeste.jpg").write_bytes(b"jpg")
            with sqlite3.connect(root / "pga.db") as db:
                db.execute("CREATE TABLE games (id INTEGER PRIMARY KEY, name TEXT, slug TEXT, runner TEXT, installed INTEGER)")
                db.executemany("INSERT INTO games VALUES (?, ?, ?, ?, ?)", [
                    (1, "Celeste", "celeste", "linux", 1), (2, "Diablo II", "diablo-ii", "wine", 1),
                    (3, "Portal", "portal", "steam", 1), (4, "Not here", "not-here", "wine", 0),
                    (5, "  Odd   name ", "../etc", "wine", 1)])
            db.close()
            found = {g["id"]: g for g in quick.lutris_games((root, Path(tmp) / "missing"))}
        self.assertEqual(set(found), {1, 2, 5})
        self.assertTrue(found[1]["art"].startswith("file:") and found[1]["art"].endswith("/banners/celeste.jpg"))
        self.assertEqual((found[2]["art"], found[5]["title"], found[5]["art"]), ("", "Odd name", ""))
        games = {g["id"]: g for g in quick.library({}, {}, [], [], set(), False, [found[1]])}
        self.assertEqual((games["lutris:1"]["plays"], games["lutris:1"]["here"], games["lutris:1"]["store"]),
                         ("monet", "lutris:1", "lutris"))


class SmallFixesFor090(unittest.TestCase):
    """What the owner saw on 0.8.5: the USB stick, the update's name, Settings, the glass, the clock."""
    SETTINGS = SETTINGS_QML

    def test_the_usb_stick_maker_finds_sticks(self):
        disk = (ROOT / "crates/monet-usb/src/disk.rs").read_text(encoding="utf-8")
        found = disk.split("pub fn sticks()", 1)[1].split("\npub fn ", 1)[0]
        # The drives are opened with no access; the length question needs read access and failed for all.
        self.assertIn('open(&format!("\\\\\\\\.\\\\PhysicalDrive{number}"), 0, 0)', found)
        self.assertNotIn("ioctl(&h, IOCTL_DISK_GET_LENGTH_INFO", found)
        self.assertIn("describe(h.0)", found)
        self.assertIn("IOCTL_DISK_GET_DRIVE_GEOMETRY_EX", disk)
        self.assertIn("let Ok(system) = system_disk() else { return Vec::new() }", found)

    def test_updates_say_monets_version(self):
        containerfile = (ROOT / "image/Containerfile").read_text()
        self.assertIn('LABEL org.opencontainers.image.version="${VERSION}" version="${VERSION}"', containerfile)
        workflow = (ROOT / ".github/workflows/image.yml").read_text()
        self.assertEqual(workflow.count('--build-arg VERSION="$VERSION"'), 2)
        settings = self.SETTINGS.read_text(encoding="utf-8")
        self.assertIn('i18n("Fixes for Monet %1 are ready", found.version)', settings)
        self.assertIn("/^\\d{1,2}\\.\\d{1,2}(\\.\\d{1,2})?$/.test(found.version", settings)

    def test_settings_list_keeps_clear_of_the_scrollbar(self):
        settings = self.SETTINGS.read_text(encoding="utf-8")
        self.assertIn("width: navList.width - (navList.interactive ? navScroll.width + 4 : 0)", settings)
        self.assertIn("T.ScrollBar.vertical: Rail { id: navScroll; tone: look }", settings)
        # Quick Settings no longer keeps Settings' size: the window does (QtCore's Settings).
        self.assertFalse((PLASMA / "plasmoids/org.monet.quick/contents/config/main.xml").exists())

    def test_clearer_glass_everywhere(self):
        # Clear by default, as Apple's glass: little blur, no grain (monet-light, by Settings' Glass slider).
        light = (ROOT / "linux/libexec/monet-light").read_text()
        self.assertIn("local level flag strength=3 noise=0", light)
        self.assertNotIn("BlurStrength", (ROOT / "linux/libexec/monet-look").read_text())
        style = (ROOT / "tools/make-plasma-style.py").read_text(encoding="utf-8")
        self.assertIn('"dialogs/background": dict(radius=20, margin=10, blur=14, drop=8, strength=0.34, glass=0.24)', style)
        self.assertIn('"widgets/background": dict(radius=20, margin=10, blur=14, drop=8, strength=0.34, glass=0.24)', style)
        menu = (PLASMA / "plasmoids/org.monet.menu/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn("color: dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.34)", menu)
        # A new look for every account at the next sign-in after each release.
        version = (ROOT / "VERSION").read_text().strip()
        self.assertIn(f'current="$looks/look-{version}"', (ROOT / "linux/libexec/monet-session").read_text())

    def test_the_clocks_page_and_highlight(self):
        clock = (PLASMA / "plasmoids/org.monet.clock/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn("Layout.maximumWidth: Kirigami.Units.gridUnit * 19", clock)
        self.assertIn("Kirigami.Units.largeSpacing * 3", clock)
        self.assertIn('ix = iy = FRAMES["widgets/panel-background"]["margin"]',
                      (ROOT / "tools/make-plasma-style.py").read_text(encoding="utf-8"))
        store = (SHARE / "monet/widgets/NoteStore.qml").read_text(encoding="utf-8")
        self.assertIn('nameFilters: ["notes.json"]', store)
        self.assertIn("onFileModifiedChanged: Qt.callLater(store.refresh)", store)

    def test_every_settings_page_is_found_by_search(self):
        entry = (SHARE / "applications/monet-settings.desktop").read_text(encoding="utf-8")
        actions = re.search(r"^Actions=(.*)$", entry, re.M).group(1).strip(";").split(";")
        self.assertEqual(tuple(actions), tuple(p for p in quick_helper().PAGES))
        for page in actions:
            self.assertIn(f"Exec=@LIBEXECDIR@/monet-settings {page}\n", entry)


class For090(unittest.TestCase):
    """0.9: a painting for each season, plein-air focus, and the last 30 seconds."""

    def test_a_painting_for_each_season(self):
        light = (ROOT / "linux/libexec/monet-light").read_text()
        body = re.search(r"\nseason_series\(\) \{\n(.*?)\n\}\n", light, re.S).group(1)
        for month, place, series in ((7, "59.33,18.07", "lilies"), (10, "59.33,18.07", "haystacks"),
                                     (1, "59.33,18.07", "magpie"), (4, "", "hours"), (1, "-33.87,151.21", "lilies"),
                                     (4, "-33.87,151.21", "haystacks"), (7, "-33.87,151.21", "magpie")):
            script = f"date() {{ echo {month:02d}; }}\nplace() {{ echo '{place}'; }}\n{body}\n"
            out = subprocess.run(["bash", "-c", script], capture_output=True, text=True, timeout=30)
            self.assertEqual(out.stdout.strip(), series, (month, place))
        self.assertIn("seasons", quick_helper().SERIES)
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('["seasons", i18n("Through the year"), i18n("Each season its painting")]', settings)

    def test_plein_air_focus(self):
        from unittest import mock
        quick = quick_helper()
        said = []
        with mock.patch.object(quick, "run", lambda *a, **k: said.append(a)), \
                mock.patch.object(quick, "focus_quiet", return_value={"ok": True, "remaining": 0}) as quiet:
            quick.focus(2000000000)
            quick.focus(None)
        self.assertEqual(quiet.call_args_list, [mock.call(2000000000, "default"), mock.call(None, "default")])
        self.assertEqual(said[0][1], "focus")
        self.assertTrue(said[0][2].endswith(",2000000000"))
        self.assertEqual(said[1][1:], ("focus", ""))
        hours = (PLASMA / "wallpapers/org.monet.hours/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn("minute = today.dawn + share * (today.night + drift - today.dawn)", hours)
        self.assertIn("interval: root.focusing ? 4000 : 60 * 1000", hours)
        timer = (PLASMA / "plasmoids/org.monet.timer/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn('requestFocus(String(Math.round(Plasmoid.configuration.ends / 1000)))', timer)
        self.assertIn('requestFocus("off")', timer)
        self.assertIn('command + " " + Plasmoid.id', timer)

    def test_the_last_30_seconds(self):
        from unittest import mock
        quick = quick_helper()
        calls = []

        def fake_run(*args, **kw):
            calls.append(args)
            return None if args[:2] == ("flatpak", "info") and len(calls) < 3 else ""

        with mock.patch.object(quick, "run", fake_run), mock.patch.object(quick, "ok", lambda *a, **k: True):
            self.assertTrue(quick.set_replay(True))
        self.assertIn(("flatpak", "install", "--system", "--noninteractive", "-y", "flathub", quick.REPLAY_APP), calls)
        unit = (ROOT / "linux/systemd/user/monet-replay.service").read_text()
        self.assertIn("ExecStart=@LIBEXECDIR@/monet-quick replay-run", unit)
        code = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        run = code.split("def replay_run", 1)[1].split("\ndef ", 1)[0]
        self.assertIn('"-r", "30"', run)
        self.assertIn('"-restore-portal-session", "yes"', run)
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertIn('--group services --group monet-replay.desktop --key _launch "Meta+Alt+G"', look)
        self.assertIn('put 644 "$SRC/systemd/user/monet-replay.service"', (ROOT / "linux/install.sh").read_text())


class TheBarStepsAside(unittest.TestCase):
    def test_the_islands_step_aside_unless_kept_in_view(self):
        from unittest import mock
        # 0.9.4: stepping aside by default again, now that pointing at the edge brings them back.
        for theme in ("org.monet.desktop", "org.monet.smoke.desktop"):
            layout = (PLASMA / "look-and-feel" / theme / "contents/layouts/org.kde.plasma.desktop-layout.js").read_text()
            self.assertIn('set(p, "hiding", "dodgewindows")', layout)
            self.assertNotIn('"hiding", "none"', layout)
        look = (ROOT / "linux/libexec/monet-look").read_text()
        # Once for accounts 0.9.1 kept them in view for, unless someone chose that.
        self.assertIn('''    if (panel.location === "bottom") panel.hiding = "$hiding";''', look)
        self.assertIn("hiding=dodgewindows", look)
        self.assertIn("&& hiding=windowsgobelow", look)
        self.assertIn('''grep -q '"dodge": false' "$CONFIG/monet/prefs.json"''', look)
        self.assertNotIn("bar-shown", look)  # it would put a new account's bar back in view
        # A pen, a touchscreen or a VM's mouse can't push past the edge.
        self.assertIn("--group Windows --key ElectricBorderPushbackPixels 0", look)
        quick = quick_helper()
        with tempfile_dir() as tmp:
            quick.PREFS = Path(tmp) / "prefs.json"
            quick.drawn_by_processor = lambda: False
            self.assertTrue(quick.prefs()["dodge"])
        self.assertIn("dodge: true })", (SETTINGS_QML).read_text(encoding="utf-8"))
        self.assertIn("--group Effect-slidingpopups --key SlideOutTime 240", look)
        self.assertIn("--group Plugins --key slidingpopupsEnabled true", look)
        quick = quick_helper()
        said = []
        with mock.patch.object(quick, "plasma_script", said.append):
            quick.set_dodge(False)
            quick.set_dodge(True)
        # All three alike, and never "always shown": each such island got room of its own and
        # KWin stacked those rooms (the right one stood a bar's height higher). Kept in view,
        # windows go below them, as the owner asked.
        self.assertIn("p.hiding = 'windowsgobelow'", said[0])
        self.assertIn("p.hiding = 'dodgewindows'", said[1])
        self.assertNotIn("'none'", said[0] + said[1])
        self.assertNotIn('"none"', look[look.index('aside="$CONFIG/monet/bar-steps-aside"'):])
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('["dodge", i18n("Bar steps aside")', settings)


class LaptopGaming(unittest.TestCase):
    """0.8.5: games on a laptop's NVIDIA chip, and LACT in the Store."""

    def test_games_start_on_the_nvidia_chip(self):
        look = (ROOT / "linux/libexec/monet-look").read_text()
        games = look.split("games_gpu() {", 1)[1].split("\n}\n", 1)[0]
        self.assertIn("hybrid_nvidia || return 0", games)
        self.assertIn("PrefersNonDefaultGPU=true", games)
        for app in ("org.prismlauncher.PrismLauncher", "org.libretro.RetroArch", "net.pcsx2.PCSX2"):
            self.assertIn(app, games)
        # Not the launchers that stay open in the tray: they'd keep the NVIDIA chip awake.
        for app in ("com.valvesoftware.Steam", "com.heroicgameslauncher.hgl", "io.itch.itch"):
            self.assertNotIn(app, games)
        # Your own copy stays yours; Monet's follows the app's.
        self.assertIn("grep -q '^X-Monet=true$' \"$mine\" && [ \"$f\" -nt \"$mine\" ] || continue", games)
        self.assertIn('[ -d /sys/module/nvidia ] || return 1', look)
        self.assertIn('"$LIBEXECDIR/monet-look" --games-gpu >/dev/null 2>&1\n',
                      (ROOT / "linux/libexec/monet-session").read_text())
        self.assertIn("ExecStart=@LIBEXECDIR@/monet-look --games-gpu",
                      (ROOT / "linux/systemd/user/monet-frames.service").read_text())

    def test_lact_in_the_store(self):
        content = (SHARE / "monet/store/content.yaml").read_text()
        play = content.split('title: "Play"', 1)[1].split("- banner:", 1)[0]
        self.assertIn("- io.github.ilya_zlobintsev.LACT", play)


class SignInWaitsLess(unittest.TestCase):
    """0.9.1: what can wait waits until the desktop is up, and nothing runs when there's nothing to do."""

    def test_the_jobs_that_can_wait_run_later_and_only_when_needed(self):
        session = (ROOT / "linux/libexec/monet-session").read_text()
        later = session.split('if [ "${1:-}" = --later ]; then', 1)[1].split("\nfi\n", 1)[0]
        jobs = ('"$LIBEXECDIR/monet-quick" frames', '"$LIBEXECDIR/monet-look" --games-gpu', '"$LIBEXECDIR/monet-quick" zen')
        for job in jobs:
            self.assertIn(job, later)
            # Not at sign-in itself any more.
            self.assertEqual(session.count(job), 1, job)
        # What they looked at is noted after they ran, and the sign-in itself never runs in --later.
        self.assertGreater(later.index('apps_now > "$apps_seen"'), later.index('"$LIBEXECDIR/monet-quick" zen'))
        self.assertIn("exit 0", later)
        self.assertLess(session.index("= --later ]"), session.index('"$BINDIR/monet" shortcuts'))
        # A minute after sign-in, at the lowest priority, and only when something changed.
        self.assertIn('if [ "$(apps_now)" != "$(cat "$apps_seen" 2>/dev/null)" ]; then', session)
        self.assertIn("--unit=monet-after-sign-in --on-active=60 --nice=19", session)
        self.assertIn('--property=IOSchedulingClass=idle "$LIBEXECDIR/monet-session" --later', session)
        self.assertIn('(sleep 60; nice -n 19 ionice -c 3 "$LIBEXECDIR/monet-session" --later)', session)
        # What they look at: a new Monet, the apps arrived while signed out, Zen's profiles.
        looked = session.split("apps_now() {", 1)[1].split("\n}\n", 1)[0]
        for where in ('"$BINDIR/monet" --version', "/var/lib/flatpak/exports/share/applications",
                      '"$DATA/flatpak/exports/share/applications"', '"$DATA/applications"',
                      '"$HOME/.var/app/app.zen_browser.zen/.zen"'):
            self.assertIn(where, looked)

    def test_an_older_pc_is_worked_out_once(self):
        session = (ROOT / "linux/libexec/monet-session").read_text()
        self.assertIn('older_key="$("$BINDIR/monet" --version 2>/dev/null) $(grep -m1 \'^MemTotal\' /proc/meminfo 2>/dev/null)"',
                      session)
        self.assertIn('if [ "$(head -1 "$older" 2>/dev/null)" = "$older_key" ]; then', session)
        # Only an answer is kept: a failed check is tried again next time.
        self.assertIn('[ -n "$older_pc" ] && mkdir -p', session)
        self.assertIn('if [ "$older_pc" = yes ]; then', session)
        self.assertEqual(session.count('"$LIBEXECDIR/monet-quick" older-pc'), 1)

    def test_starts_skip_what_has_nothing_to_do(self):
        ready = (ROOT / "linux/systemd/monet-ready-boot.service").read_text()
        self.assertIn("ConditionPathExists=|/var/lib/monet/ready-armed", ready)
        self.assertIn("ConditionPathExists=|/etc/plasmalogin.conf.d/zz-monet-ready.conf", ready)
        # The same places monet-ready arms and signs in from.
        script = (ROOT / "linux/libexec/monet-ready").read_text()
        self.assertIn('ARMED = STATE / "ready-armed"', script)
        self.assertIn('DROPIN = Path("/etc/plasmalogin.conf.d/zz-monet-ready.conf")', script)
        self.assertIn('STATE = Path("/var/lib/monet")', script)
        keep = keep_helper()
        unit = (ROOT / "linux/systemd/monet-keep-prepare.service").read_text()
        self.assertIn(f"ConditionPathExists=!{keep.PREPARED.as_posix()}", unit)

    def test_the_homes_are_marked_once_they_need_nothing_more(self):
        import tempfile
        keep = keep_helper()
        with tempfile.TemporaryDirectory() as tmp:
            home, prepared = Path(tmp) / "home", Path(tmp) / "state" / "home-subvolume"
            home.mkdir()
            keep.signed_in = lambda: True
            # Someone signed in before it could swap: tried again at the next start.
            keep.on_btrfs, keep.subvolume = (lambda path: True), (lambda path: False)
            keep.prepare(home, prepared)
            self.assertFalse(prepared.exists())
            # A subvolume already: marked, whoever is signed in.
            keep.subvolume = lambda path: True
            keep.prepare(home, prepared)
            self.assertTrue(prepared.exists())
            # Not btrfs: never a subvolume, so marked too.
            prepared.unlink()
            keep.on_btrfs, keep.subvolume = (lambda path: False), (lambda path: False)
            keep.prepare(home, prepared)
            self.assertTrue(prepared.exists())


def bootc(booted, staged=None, rollback=None, offered=None):
    """bootc status --json's status, for deployments given as (digest, version)."""
    def entry(found):
        return {"image": {"imageDigest": found[0], "version": found[1]}} if found else None
    status = {"booted": entry(booted), "staged": entry(staged), "rollback": entry(rollback)}
    if offered:
        status["booted"]["cachedUpdate"] = {"imageDigest": offered}
    return status


OLD, NEW = ("sha256:aaa", "0.9.1"), ("sha256:bbb", "0.9.2")


class GoingBackByItself(unittest.TestCase):
    """0.9.1: a new Monet that doesn't start goes back by itself (monet-boot)."""

    def setUp(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.boot = libexec_helper("monet-boot")
        self.boot.TRIAL = Path(self.tmp.name) / "trial.json"
        self.boot.WENT_BACK = Path(self.tmp.name) / "went-back.json"
        self.ran = []
        self.boot.run = lambda *args, timeout=120: self.ran.append([str(a) for a in args]) or ""

    def tearDown(self):
        self.tmp.cleanup()

    def on_trial(self):
        self.boot.arm(bootc(OLD, staged=NEW), counts=True)

    def test_a_staged_monet_goes_on_trial_at_shutdown(self):
        self.on_trial()
        trial = json.loads(self.boot.TRIAL.read_text())
        self.assertEqual(trial, {"digest": NEW[0], "version": NEW[1], "before": OLD[0], "beforeVersion": OLD[1]})
        # GRUB counts its tries, where its menu can.
        self.assertIn(["grub2-editenv", "-", "set", "boot_counter=3", "boot_success=0"], self.ran)
        self.boot.TRIAL.unlink()
        self.ran.clear()
        self.boot.arm(bootc(OLD, staged=NEW), counts=False)
        self.assertTrue(self.boot.TRIAL.exists())
        self.assertEqual(self.ran, [])
        # Nothing staged, or the same Monet with other kernel arguments: nothing on trial.
        self.boot.TRIAL.unlink()
        self.boot.arm(bootc(OLD), counts=True)
        self.boot.arm(bootc(OLD, staged=OLD), counts=True)
        self.assertFalse(self.boot.TRIAL.exists())
        with tempfile_dir() as tmp:
            cfg = Path(tmp) / "grub.cfg"
            cfg.write_text("if [ -n \"${boot_counter}\" -a \"${boot_success}\" = \"0\" ]; then\n")
            self.assertTrue(self.boot.grub_counts([cfg, Path(tmp) / "missing.cfg"]))
            cfg.write_text("set default=0\n")
            self.assertFalse(self.boot.grub_counts([cfg]))

    def test_a_monet_that_starts_passes(self):
        self.on_trial()
        self.boot.WENT_BACK.write_text(json.dumps({"version": "0.9.0", "digest": "sha256:old"}))
        self.ran.clear()
        self.assertEqual(self.boot.check(bootc(NEW, rollback=OLD), up=lambda: True, env={}), "passed")
        self.assertFalse(self.boot.TRIAL.exists())
        self.assertFalse(self.boot.WENT_BACK.exists())
        self.assertIn(["grub2-editenv", "-", "unset", "boot_counter"], self.ran)
        self.assertNotIn(["bootc", "rollback"], self.ran)

    def test_one_that_doesnt_goes_back_and_restarts(self):
        self.on_trial()
        self.ran.clear()
        self.assertEqual(self.boot.check(bootc(NEW, rollback=OLD), up=lambda: False, env={}), "went back")
        self.assertEqual(json.loads(self.boot.WENT_BACK.read_text())["version"], "0.9.2")
        self.assertEqual(json.loads(self.boot.WENT_BACK.read_text())["to"], "0.9.1")
        self.assertLess(self.ran.index(["bootc", "rollback"]), self.ran.index(["systemctl", "reboot"]))
        self.assertFalse(self.boot.TRIAL.exists())
        # With nothing to go back to, it stays, and is no longer on trial.
        self.on_trial()
        self.ran.clear()
        self.assertEqual(self.boot.check(bootc(NEW), up=lambda: False, env={}), "nothing to go back to")
        self.assertNotIn(["bootc", "rollback"], self.ran)

    def test_grub_giving_up_keeps_the_one_before(self):
        self.on_trial()
        self.ran.clear()
        self.assertEqual(self.boot.check(bootc(OLD, rollback=NEW), env={"boot_counter": "-1"}), "went back")
        self.assertIn(["bootc", "rollback"], self.ran)
        self.assertNotIn(["systemctl", "reboot"], self.ran)
        self.assertTrue(self.boot.WENT_BACK.exists())

    def test_failed_rollback_keeps_trial_without_reboot_or_success_record(self):
        for status, env in ((bootc(NEW, rollback=OLD), {}),
                            (bootc(OLD, rollback=NEW), {"boot_counter": "-1"})):
            with self.subTest(booted=status["booted"]):
                self.on_trial()
                before = self.boot.TRIAL.read_bytes()
                previous = '{"digest":"sha256:earlier-failure"}'
                self.boot.WENT_BACK.write_text(previous)
                self.ran.clear()
                def fail_rollback(*args, timeout=120):
                    self.ran.append(list(args))
                    return None if args == ("bootc", "rollback") else ""
                self.boot.run = fail_rollback
                with self.assertRaisesRegex(OSError, "rollback"):
                    self.boot.check(status, up=lambda: False, env=env)
                self.assertEqual(self.boot.TRIAL.read_bytes(), before)
                self.assertEqual(self.boot.WENT_BACK.read_text(), previous)
                self.assertEqual(self.ran, [["bootc", "rollback"]])

    def test_failed_rollback_is_reported_to_systemd(self):
        import contextlib
        import io
        def failed():
            raise OSError("Could not schedule rollback")
        self.boot.check = failed
        errors = io.StringIO()
        with contextlib.redirect_stderr(errors):
            self.assertEqual(self.boot.main(["check"]), 1)
        self.assertIn("Could not schedule rollback", errors.getvalue())

    def test_the_one_before_picked_in_the_menu_leaves_the_trial_waiting(self):
        self.on_trial()
        self.assertEqual(self.boot.check(bootc(OLD, rollback=NEW), env={"boot_counter": "2"}), "waiting")
        self.assertTrue(self.boot.TRIAL.exists())
        # An update that never reached the disk (the PC stopped while shutting down) isn't on trial.
        self.assertEqual(self.boot.check(bootc(OLD), env={}), "none")
        self.assertFalse(self.boot.TRIAL.exists())

    def test_the_sign_in_screen_has_to_stay_up(self):
        import types
        clock = types.SimpleNamespace(t=0.0)
        fake = types.SimpleNamespace(monotonic=lambda: clock.t, sleep=lambda s: setattr(clock, "t", clock.t + s))
        self.assertTrue(self.boot.desktop_up(lambda: ((True, "0", "100"), frozenset({"c1"})), clock=fake))
        self.assertLessEqual(clock.t, 70)
        # A sign-in screen that keeps crashing comes back as a new session: never steady, and it ends.
        clock.t, polls = 0.0, iter(range(10000))
        crashing = lambda: ((True, "0", "100"), frozenset({f"c{next(polls) // 3}"}))
        self.assertFalse(self.boot.desktop_up(crashing, clock=fake))
        self.assertLessEqual(clock.t, self.boot.WAIT + self.boot.STEADY + 5)
        clock.t = 0.0
        self.assertFalse(self.boot.desktop_up(lambda: ((False, "0", ""), frozenset()), clock=fake))
        clock.t = 0.0
        restarting = iter(str(n // 4) for n in range(10000))
        self.assertFalse(self.boot.desktop_up(lambda: ((True, next(restarting), "1"), frozenset({"c1"})), clock=fake))

    def test_remote_and_text_sessions_do_not_reset_a_healthy_desktop_trial(self):
        import types
        clock = types.SimpleNamespace(t=0.0)
        fake = types.SimpleNamespace(monotonic=lambda: clock.t, sleep=lambda s: setattr(clock, "t", clock.t + s))
        def run(*args, timeout=120):
            if args[1] == "list-sessions":
                return f"desktop\nssh-{clock.t}\ntty\nremote-graphics\nmanager\nunknown\n"
            session = args[2]
            props = {"desktop": "Class=user\nType=wayland\nRemote=no\nState=active\n",
                     "tty": "Class=user\nType=tty\nRemote=no\nState=online\n",
                     "remote-graphics": "Class=user\nType=x11\nRemote=yes\nState=active\n",
                     "manager": "Class=manager\nType=unspecified\nRemote=no\nState=online\n",
                     "unknown": "Class=user\nState=active\n"}
            return props.get(session, "Class=user\nType=tty\nRemote=yes\nState=online\n")
        self.boot.run = run
        self.assertEqual(self.boot.sessions(), frozenset({"desktop"}))
        self.assertTrue(self.boot.desktop_up(lambda: ((True, "0", "100"), self.boot.sessions()), clock=fake))
        self.assertEqual(clock.t, 60)

    def test_the_daily_update_skips_the_one_that_didnt_start(self):
        self.assertEqual(self.boot.may_update(bootc(OLD, offered=NEW[0]), refresh=False), 0)
        self.boot.WENT_BACK.write_text(json.dumps({"version": "0.9.2", "digest": NEW[0], "to": "0.9.1"}))
        self.assertEqual(self.boot.may_update(bootc(OLD, offered=NEW[0]), refresh=False), 1)
        self.assertEqual(self.boot.may_update(bootc(OLD, offered="sha256:ccc"), refresh=False), 0)
        update = (ROOT / "linux/systemd/monet-update.service").read_text()
        self.assertIn("ExecCondition=@LIBEXECDIR@/monet-boot may-update", update)

    def test_it_runs_at_shutdown_and_after_the_sign_in_screen(self):
        arm = (ROOT / "linux/systemd/monet-boot-arm.service").read_text()
        self.assertIn("ExecStop=@LIBEXECDIR@/monet-boot arm", arm)
        self.assertIn("After=local-fs.target ostree-finalize-staged.service", arm)
        self.assertIn("RemainAfterExit=yes", arm)
        check = (ROOT / "linux/systemd/monet-boot-check.service").read_text()
        for line in ("ConditionPathExists=/var/lib/monet/trial.json", "After=display-manager.service", "Type=exec"):
            self.assertIn(line, check)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn("systemctl enable --now monet-boot-arm.service", install)
        self.assertIn("monet-boot-arm.service monet-boot-check.service monet-reset.service", install)
        # Settings and the next sign-in say so, and Go back doesn't offer the one that didn't start.
        quick = quick_helper()
        with tempfile_dir() as tmp:
            note = Path(tmp) / "went-back.json"
            self.assertEqual(quick.went_back(note), {})
            note.write_text(json.dumps({"version": "0.9.2", "digest": "x", "to": "0.9.1", "when": 1}))
            self.assertEqual(quick.went_back(note), {"version": "0.9.2", "to": "0.9.1"})
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('ask("went-back", out => sheet.wentBack = sheet.json(out, {}))', settings)
        self.assertIn("&& !(sheet.wentBack.version && sheet.wentBack.version === sheet.previous.version)", settings)
        session = (ROOT / "linux/libexec/monet-session").read_text()
        self.assertIn('[ "$went" -nt "$looks/went-back-seen" ]', session)


class ResetThisPC(unittest.TestCase):
    """0.9.1: Monet as it comes, with files, games and apps kept (monet-reset)."""

    def setUp(self):
        self.reset = libexec_helper("monet-reset")

    def test_what_makes_this_pc_this_one_stays(self):
        for rel in ("passwd", "shadow-", "group", "machine-id", "hostname", "fstab", "crypttab", "locale.conf",
                    "NetworkManager/system-connections/Harbor.nmconnection", "ssh/ssh_host_ed25519_key",
                    "cups/printers.conf", "X11/xorg.conf.d/00-keyboard.conf", ".updated", "pki/tls/cert.pem"):
            self.assertTrue(self.reset.kept(rel), rel)
        for rel in ("ssh/sshd_config", "sudoers.d/mine", "systemd/system/multi-user.target.wants/sshd.service",
                    "plasmalogin.conf.d/zz-monet-ready.conf", "environment", "modprobe.d/mine.conf"):
            self.assertFalse(self.reset.kept(rel), rel)
        self.assertEqual(self.reset.changes("A    b/c\nM    a\nD    b\nnot a change\n"),
                         [("M", "a"), ("D", "b"), ("A", "b/c")])

    def test_the_systems_settings_go_back(self):
        import shutil
        copy = lambda source, target: (shutil.copytree(source, target, symlinks=True) if Path(source).is_dir()
                                       else shutil.copy2(source, target)) and ""
        with tempfile_dir() as tmp:
            etc, defaults, into = (Path(tmp) / name for name in ("etc", "usr-etc", "kept"))
            for base in (etc, defaults):
                (base / "ssh").mkdir(parents=True)
            (defaults / "ssh/sshd_config").write_text("Monet's\n")
            (etc / "ssh/sshd_config").write_text("mine\n")
            (etc / "mine.conf").write_text("added\n")
            (defaults / "environment").write_text("Monet's environment\n")
            (defaults / "hostname").write_text("monet\n")
            (etc / "hostname").write_text("ann-pc\n")
            (etc / "added").mkdir()
            (etc / "added/x").write_text("x\n")
            found = self.reset.changes("M ssh/sshd_config\nA mine.conf\nD environment\nM hostname\nA added\nA added/x\n")
            done = self.reset.reset_etc(found, into, etc=etc, defaults=defaults, copy=copy)
            self.assertEqual((etc / "ssh/sshd_config").read_text(), "Monet's\n")
            self.assertEqual((into / "ssh/sshd_config").read_text(), "mine\n")
            self.assertFalse((etc / "mine.conf").exists())
            self.assertEqual((into / "mine.conf").read_text(), "added\n")
            self.assertEqual((etc / "environment").read_text(), "Monet's environment\n")
            self.assertEqual((etc / "hostname").read_text(), "ann-pc\n")
            self.assertEqual((into / "added/x").read_text(), "x\n")
            self.assertNotIn("added/x", done)
            self.assertEqual(sorted(p.name for p in etc.rglob("*.monet-reset")), [])
            # When Monet's copy can't be made, what's there stays as it is.
            (etc / "ssh/sshd_config").write_text("mine again\n")
            self.reset.reset_etc([("M", "ssh/sshd_config")], into, etc=etc, defaults=defaults, copy=lambda s, t: None)
            self.assertEqual((etc / "ssh/sshd_config").read_text(), "mine again\n")

    def test_an_accounts_desktop_starts_afresh_and_its_files_stay(self):
        with tempfile_dir() as tmp:
            home = Path(tmp) / "ann"
            for rel in (".config/kdeglobals", ".config/kwinrc", ".config/plasma-org.kde.plasma.desktop-appletsrc",
                        ".config/monet/prefs.json", ".config/autostart/steam.desktop", ".config/user-dirs.dirs",
                        ".config/lutris/system.yml", ".local/share/plasma/look.json", ".local/share/Steam/steamapps/x",
                        ".local/share/monet/notes.json", ".local/share/applications/game.desktop",
                        ".cache/thumbnails/x.png", ".cache/fontconfig", "Documents/letter.txt"):
                (home / rel).parent.mkdir(parents=True, exist_ok=True)
                (home / rel).write_text(rel)
            moved = self.reset.reset_home(home, "2026-10-24 09.00")
            kept = home / ".local/share/monet/before-reset/2026-10-24 09.00"
            for rel in (".config/kdeglobals", ".config/kwinrc", ".config/plasma-org.kde.plasma.desktop-appletsrc",
                        ".config/monet/prefs.json", ".config/autostart/steam.desktop", ".local/share/plasma/look.json"):
                self.assertFalse((home / rel).exists(), rel)
                self.assertEqual((kept / rel).read_text(), rel)
            for rel in (".config/user-dirs.dirs", ".config/lutris/system.yml", ".local/share/Steam/steamapps/x",
                        ".local/share/monet/notes.json", ".local/share/applications/game.desktop", "Documents/letter.txt"):
                self.assertEqual((home / rel).read_text(), rel)
            self.assertEqual(list((home / ".cache").iterdir()), [])
            self.assertIn(".config/kdeglobals", [m.replace("\\", "/") for m in moved])
        Entry = __import__("types").SimpleNamespace
        found = self.reset.accounts([Entry(pw_name="root", pw_uid=0, pw_gid=0, pw_dir="/root"),
                                     Entry(pw_name="ann", pw_uid=1000, pw_gid=1000, pw_dir="/var/home/ann"),
                                     Entry(pw_name="nobody", pw_uid=65534, pw_gid=65534, pw_dir="/"),
                                     Entry(pw_name="gone", pw_uid=1001, pw_gid=1001, pw_dir="/var/home/gone")],
                                    there=lambda path: path != "/var/home/gone")
        self.assertEqual([name for name, *_ in found], ["ann"])

    def test_it_asks_for_a_password_and_resets_before_the_sign_in_screen(self):
        script = (ROOT / "linux/libexec/monet-reset").read_text()
        now = script.split("def now():", 1)[1].split("\ndef ", 1)[0]
        # Each home is reset as its own account, never as root; Earlier versions has it all first.
        self.assertIn("as_account(uid, gid, lambda home=home: reset_home(home, stamp))", now)
        self.assertLess(now.index("monet-keep"), now.index("reset_etc("))
        for name in ("keep-off", "charge-limit", "ready-user", "auto-updates-off"):
            self.assertIn(name, self.reset.MONET)
        unit = (ROOT / "linux/systemd/monet-reset.service").read_text()
        self.assertIn("ConditionPathExists=/var/lib/monet/reset", unit)
        self.assertIn("Before=display-manager.service plasmalogin.service systemd-user-sessions.service", unit)
        quick = (ROOT / "linux/libexec/monet-quick").read_text()
        self.assertIn('run("pkexec", f"{LIBEXECDIR}/monet-reset", "arm" if args[0] == "on" else "cancel", timeout=600)',
                      quick)
        # Not among the helpers Monet's polkit rule lets run without a password.
        programs = next(line for line in (ROOT / "linux/install.sh").read_text().splitlines() if line.startswith("programs="))
        self.assertNotIn("monet-reset", programs)
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('sheet.ask("reset on", out => sheet.resetState = sheet.json(out, sheet.resetState))', settings)
        self.assertIn('"updates update version upgrade new reset restore rollback"', settings)


class EncryptedDisk(unittest.TestCase):
    """0.9.1: Monet Setup encrypts the disk; Monet's first start hands its key to the TPM (monet-seal)."""

    CMDLINE = ("BOOT_IMAGE=(hd0,gpt2)/vmlinuz root=UUID=1 rd.luks.uuid=luks-ab12 rd.luks.options=ab12=tpm2-device=auto "
               "rd.luks.key=ab12=/monet-firstboot.key:UUID=cd34 rw")

    def setUp(self):
        self.seal = libexec_helper("monet-seal")

    def test_the_disk_and_its_start_up_key_come_from_the_command_line(self):
        device, key = self.seal.disk(self.CMDLINE)
        self.assertEqual(device.as_posix(), "/dev/disk/by-uuid/ab12")
        self.assertEqual(key, "rd.luks.key=ab12=/monet-firstboot.key:UUID=cd34")
        self.assertEqual(self.seal.disk("root=UUID=1 rw"), (None, ""))
        self.assertEqual(self.seal.key_slot("No usable token is available.\nKey slot 2 unlocked.\n"), 2)
        self.assertIsNone(self.seal.key_slot(None))

    def test_the_first_start_hands_the_key_to_the_tpm(self):
        from contextlib import redirect_stderr
        import io
        with tempfile_dir() as tmp:
            key = Path(tmp) / "monet-firstboot.key"
            key.write_bytes(b"k" * 64)
            self.seal.FIRST_KEY, self.seal.CMDLINE = key, Path(tmp) / "cmdline"
            self.seal.CMDLINE.write_text(self.CMDLINE)
            ran = []

            def run(*args, timeout=300):
                ran.append([str(a) for a in args])
                return "Key slot 0 unlocked.\n" if args[0] == "cryptsetup" else ""

            self.seal.run = run
            self.assertEqual(self.seal.first_start(), 0)
            device = str(Path("/dev/disk/by-uuid/ab12"))
            self.assertEqual(ran[0], ["systemd-cryptenroll", f"--unlock-key-file={key}", "--wipe-slot=tpm2",
                                      "--tpm2-device=auto", "--tpm2-pcrs=7", device])
            self.assertIn(["cryptsetup", "luksKillSlot", "-q", device, "0"], ran)
            self.assertIn(["rpm-ostree", "kargs", "--delete-if-present=rd.luks.key=ab12=/monet-firstboot.key:UUID=cd34"], ran)
            self.assertFalse(key.exists())
            # When the chip can't learn it, the start-up key stays for the next start.
            key.write_bytes(b"k")
            ran.clear()
            self.seal.run = lambda *args, timeout=300: ran.append(args) and None
            with redirect_stderr(io.StringIO()):
                self.assertEqual(self.seal.first_start(), 1)
            self.assertTrue(key.exists())
            self.assertEqual(len(ran), 1)

    def test_after_the_recovery_key_the_tpm_learns_the_pc_again(self):
        from contextlib import redirect_stdout
        import io
        with tempfile_dir() as tmp:
            self.seal.CMDLINE, self.seal.RUNDIR = Path(tmp) / "cmdline", tmp
            self.seal.CMDLINE.write_text("rd.luks.uuid=ab12")
            tried = []

            def run(*args, timeout=300):
                unlock = next(a for a in map(str, args) if a.startswith("--unlock-key-file="))
                tried.append(Path(unlock.split("=", 1)[1]).read_bytes())
                return "" if tried[-1] == b"right" else None

            self.seal.run = run
            with redirect_stdout(io.StringIO()):
                self.seal.relearn([b"wrong", b"right", b"never"])
            self.assertEqual(tried, [b"wrong", b"right"])
            self.assertEqual(list(Path(tmp).iterdir()), [self.seal.CMDLINE])
            tried.clear()
            self.seal.relearn([])
            self.assertEqual(tried, [])

    def test_the_image_unlocks_by_itself(self):
        first = (ROOT / "linux/systemd/monet-seal.service").read_text()
        self.assertIn("ConditionPathExists=/boot/monet-firstboot.key", first)
        again = (ROOT / "linux/systemd/monet-seal-relearn.service").read_text()
        for line in ("ConditionKernelCommandLine=rd.luks.uuid", "ConditionPathExists=!/boot/monet-firstboot.key",
                     "KeyringMode=shared"):
            self.assertIn(line, again)
        image = (ROOT / "image/Containerfile").read_text()
        self.assertIn("--add tpm2-tss", image)
        self.assertIn(" cryptsetup tpm2-tss", image)
        self.assertIn("\ncryptsetup\n", (ROOT / "image/setup/packages.txt").read_text())
        build = (ROOT / ".github/workflows/build.yml").read_text()
        for name in ("monet-boot", "monet-reset", "monet-seal"):
            self.assertIn(f"linux/libexec/{name} ", build)
            self.assertIn(name, (ROOT / "linux/uninstall.sh").read_text())


class HiveFile:
    """A small Windows registry file (regf) for tests, built cell by cell, keys after their
    subkeys. Real files were checked by hand (C:\\Users\\Default\\NTUSER.DAT)."""

    def __init__(self):
        import struct
        self.struct = struct
        self.body = bytearray(b"hbin" + bytes(28))

    def cell(self, data):
        size = (len(data) + 4 + 7) // 8 * 8
        at = len(self.body)
        self.body += self.struct.pack("<i", -size) + data + bytes(size - 4 - len(data))
        return at

    def key(self, name, values=(), subkeys=(), written=0, ri=False):
        """values: [(name, type, bytes)]; subkeys: offsets of keys; ri: list them in two parts."""
        pack = self.struct.pack
        offsets = []
        for value_name, kind, data in values:
            raw = value_name.encode("latin-1")
            size, where = (len(data) | 0x80000000, int.from_bytes(data.ljust(4, b"\0"), "little")) \
                if len(data) <= 4 else (len(data), self.cell(data))
            offsets.append(self.cell(b"vk" + pack("<HIIIHH", len(raw), size, where, kind, 1, 0) + raw))
        value_list = self.cell(b"".join(pack("<I", o) for o in offsets)) if offsets else 0xFFFFFFFF
        subkeys = list(subkeys)
        if not subkeys:
            subkey_list = 0xFFFFFFFF
        elif ri:
            parts = [subkeys[:len(subkeys) // 2], subkeys[len(subkeys) // 2:]]
            lists = [self.cell(b"li" + pack("<H", len(p)) + b"".join(pack("<I", o) for o in p)) for p in parts]
            subkey_list = self.cell(b"ri" + pack("<H", 2) + b"".join(pack("<I", o) for o in lists))
        else:
            subkey_list = self.cell(b"lh" + pack("<H", len(subkeys)) + b"".join(pack("<II", o, 0) for o in subkeys))
        raw = name.encode("latin-1")
        filetime = int(written * 10 ** 7) + 116444736000000000
        return self.cell(b"nk" + pack("<HQ", 0x20, filetime) + pack("<15I", 0, 0, len(subkeys), 0, subkey_list,
                         0xFFFFFFFF, len(offsets), value_list, 0, 0xFFFFFFFF, 0, 0, 0, 0, 0)
                         + pack("<HH", len(raw), 0) + raw)

    def file(self, root):
        base = bytearray(4096)
        base[:4] = b"regf"
        self.struct.pack_into("<II", base, 4, 1, 1)
        self.struct.pack_into("<II", base, 36, root, len(self.body))
        return bytes(base + self.body)


def windows_system(link_key, le, current=2, written=2_000_000_000):
    """A Windows SYSTEM file with one adapter: a classic device and a Low Energy one."""
    hive = HiveFile()
    adapter = hive.key("0a1b2c3d4e5f", written=written, values=[
        ("112233445566", 3, link_key), ("CentralIRK", 3, bytes(range(16))), ("notadevice", 4, b"\x01\0\0\0")],
        subkeys=[hive.key("665544332211", written=written, values=le)])
    keys = hive.key("Keys", subkeys=[adapter])
    bthport = hive.key("BTHPORT", subkeys=[hive.key("Parameters", subkeys=[keys])])
    # Enough services that they're listed in parts ("ri"), as in a real SYSTEM file.
    services = hive.key("Services", ri=True, subkeys=[hive.key("Audiosrv"), bthport, hive.key("bthserv")])
    stale = hive.key("ControlSet001", subkeys=[hive.key("Services")])
    used = hive.key(f"ControlSet{current:03d}", subkeys=[services])
    select = hive.key("Select", values=[("Current", 4, current.to_bytes(4, "little"))])
    return hive.file(hive.key("ROOT", subkeys=[select, stale, used]))


LE_VALUES = [("LTK", 3, bytes.fromhex("00112233445566778899AABBCCDDEEFF")), ("KeyLength", 4, b"\x10\0\0\0"),
             ("ERand", 11, (1234567890123456789).to_bytes(8, "little")), ("EDIV", 4, (4660).to_bytes(4, "little")),
             ("IRK", 3, bytes.fromhex("0102030405060708090A0B0C0D0E0F10")), ("AddressType", 4, b"\x01\0\0\0")]


class PairingsFromWindows(unittest.TestCase):
    """0.9.1: a controller or headset paired in Windows works in Monet too (monet-pairings)."""

    def setUp(self):
        self.pairings = libexec_helper("monet-pairings")

    def test_it_reads_windows_keys_off_its_registry(self):
        p = self.pairings
        found = p.windows_pairings(p.Hive(windows_system(bytes(range(16)), LE_VALUES)))
        self.assertEqual(sorted(found), [("0A:1B:2C:3D:4E:5F", "11:22:33:44:55:66"),
                                         ("0A:1B:2C:3D:4E:5F", "66:55:44:33:22:11")])
        classic, written = found[("0A:1B:2C:3D:4E:5F", "11:22:33:44:55:66")]
        self.assertEqual(classic, {"LinkKey": {"Key": "000102030405060708090A0B0C0D0E0F"}})
        self.assertAlmostEqual(written, 2_000_000_000, places=3)
        le, _ = found[("0A:1B:2C:3D:4E:5F", "66:55:44:33:22:11")]
        self.assertEqual(le["LongTermKey"], {"Key": "00112233445566778899AABBCCDDEEFF", "Authenticated": "0",
                                             "EncSize": "16", "EDiv": "4660", "Rand": "1234567890123456789"})
        self.assertEqual(le["IdentityResolvingKey"], {"Key": "100F0E0D0C0B0A090807060504030201"})
        self.assertEqual(p.mac("0a1b2c3d4e5f"), "0A:1B:2C:3D:4E:5F")
        self.assertIsNone(p.mac("CentralIRK"))
        self.assertFalse(p.Hive(windows_system(bytes(16), LE_VALUES)).unsaved())
        with self.assertRaises(ValueError):
            p.Hive(b"MZ" + bytes(9000))

    def test_secure_connections_and_a_passing_address(self):
        p = self.pairings
        # Named after a passing address; its own (static: top bits 11) is in Address. Secure
        # Connections: no EDIV or Rand, so marked to work in either role; no key length: 16.
        values = [("LTK", 3, bytes(range(16))), ("KeyLength", 4, bytes(4)), ("ERand", 11, bytes(8)),
                  ("EDIV", 4, bytes(4)), ("Address", 11, (0xDA5B4A88508C).to_bytes(8, "little")),
                  ("AddressType", 4, b"\x01\0\0\0")]
        found = p.windows_pairings(p.Hive(windows_system(bytes(16), values)))
        sections, _ = found[("0A:1B:2C:3D:4E:5F", "DA:5B:4A:88:50:8C")]
        self.assertEqual(sections["LongTermKey"], {"Key": "000102030405060708090A0B0C0D0E0F", "Authenticated": "2",
                                                   "EncSize": "16", "EDiv": "0", "Rand": "0"})
        # A private (not static) random address in Address isn't the device's own: the key's name is.
        values[4] = ("Address", 11, (0x4A5B4A88508C).to_bytes(8, "little"))
        found = p.windows_pairings(p.Hive(windows_system(bytes(16), values)))
        self.assertIn(("0A:1B:2C:3D:4E:5F", "66:55:44:33:22:11"), found)

    @unittest.skipIf(sys.platform == "win32", "BlueZ names its folders with colons")
    def test_the_newer_pairing_wins(self):
        import os
        p = self.pairings
        device = ("0A:1B:2C:3D:4E:5F", "11:22:33:44:55:66")
        with tempfile_dir() as tmp:
            bluez, seen = Path(tmp) / "bluetooth", Path(tmp) / "pairings.json"
            info = bluez / device[0] / device[1] / "info"
            info.parent.mkdir(parents=True)
            info.write_text("[General]\nName=DualSense Wireless Controller\nSupportedTechnologies=BR/EDR;\n"
                            "Trusted=true\n\n[LinkKey]\nKey=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\nType=4\nPINLength=0\n\n"
                            "[ServiceRecords]\n0x00010001=36010035\n")
            os.utime(info, (1_000_000_000, 1_000_000_000))
            windows = lambda key, when: {device: ({"LinkKey": {"Key": key}}, when)}
            # Paired again in Windows after Monet: Monet takes Windows' key, keeping the rest
            # (Bluetooth stopped first, once).
            stops = []
            self.assertEqual(p.sync(windows("B" * 32, 2_000_000_000), bluez, seen, lambda: stops.append(1)),
                             ["DualSense Wireless Controller"])
            self.assertEqual(stops, [1])
            text = info.read_text()
            self.assertIn("[LinkKey]\nKey=" + "B" * 32 + "\nType=4\nPINLength=0\n", text)
            self.assertIn("SupportedTechnologies=BR/EDR;\n", text)
            self.assertIn("[ServiceRecords]\n0x00010001=36010035\n", text)
            # Nothing new: nothing to do.
            self.assertEqual(p.sync(windows("B" * 32, 2_000_000_000), bluez, seen), [])
            # Paired again in Monet since: Windows' key is the old one, so Monet keeps its own.
            info.write_text(text.replace("B" * 32, "C" * 32))
            self.assertEqual(p.sync(windows("B" * 32, 2_000_000_000), bluez, seen), [])
            self.assertIn("C" * 32, info.read_text())
            # Then paired in Windows again: taken.
            self.assertEqual(len(p.sync(windows("D" * 32, 2_100_000_000), bluez, seen)), 1)
            self.assertIn("D" * 32, info.read_text())
            # The first look at a device Windows paired before Monet did: Monet's stays.
            seen.unlink()
            os.utime(info, (2_200_000_000, 2_200_000_000))
            self.assertEqual(p.sync(windows("E" * 32, 2_100_000_000), bluez, seen), [])
            # Only devices Monet has paired: none made up, none half-known filled in.
            other = ("0A:1B:2C:3D:4E:5F", "77:88:99:AA:BB:CC")
            (bluez / other[0] / other[1]).mkdir()
            (bluez / other[0] / other[1] / "info").write_text("[General]\nName=Seen nearby\n")
            gone = ("0A:1B:2C:3D:4E:5F", "DD:EE:FF:00:11:22")
            self.assertEqual(p.sync({other: ({"LinkKey": {"Key": "F" * 32}}, 3_000_000_000),
                                     gone: ({"LinkKey": {"Key": "F" * 32}}, 3_000_000_000)}, bluez, seen), [])
            self.assertNotIn("LinkKey", (bluez / other[0] / other[1] / "info").read_text())
            self.assertFalse((bluez / gone[0] / gone[1]).exists())

    def test_a_low_energy_pairing_replaces_the_old_keys(self):
        p = self.pairings
        info = configparser.ConfigParser(interpolation=None, strict=False, delimiters=("=",))
        info.optionxform = str
        info.read_string("[General]\nName=Xbox Wireless Controller\nAddressType=public\n\n"
                         "[PeripheralLongTermKey]\nKey=00\nAuthenticated=0\nEncSize=16\nEDiv=1\nRand=2\n")
        found = p.windows_pairings(p.Hive(windows_system(bytes(16), LE_VALUES)))
        sections, _ = found[("0A:1B:2C:3D:4E:5F", "66:55:44:33:22:11")]
        p.apply(info, sections)
        self.assertFalse(info.has_section("PeripheralLongTermKey"))
        self.assertEqual(info.get("LongTermKey", "Key"), "00112233445566778899AABBCCDDEEFF")
        self.assertEqual(info.get("LongTermKey", "Authenticated"), "0")
        self.assertEqual(info.get("General", "AddressType"), "public")

    def test_it_runs_at_every_start(self):
        unit = (ROOT / "linux/systemd/monet-pairings.service").read_text()
        for line in ("ExecStart=@LIBEXECDIR@/monet-pairings", "After=local-fs.target bluetooth.service",
                     "ConditionPathIsDirectory=/var/lib/bluetooth", "WantedBy=multi-user.target"):
            self.assertIn(line, unit)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('put 755 "$SRC/libexec/monet-pairings" "$LIBEXECDIR/monet-pairings"', install)
        self.assertEqual(install.count("systemctl enable monet-pairings.service"), 2)
        self.assertIn("rm -f /etc/systemd/system/monet-pairings.service", (ROOT / "linux/uninstall.sh").read_text())
        self.assertIn("linux/libexec/monet-pairings ", (ROOT / ".github/workflows/build.yml").read_text())
        # Read with ntfscat, which ships with Monet: Windows' drive is never mounted.
        self.assertIn(" ntfsprogs ", (ROOT / "image/Containerfile").read_text())


class SaveAReport(unittest.TestCase):
    """About → Save a report: what helps find out why something went wrong, in one file."""

    def test_the_report_has_every_part_cut_to_size(self):
        quick = quick_helper()
        with tempfile_dir() as tmp:
            log = Path(tmp) / "switch.log"
            log.write_text("".join(f"trip {i}\n" for i in range(10)))
            parts = (("Trips to Windows", log, ("tail", 3)), ("Missing", Path(tmp) / "none", None),
                     ("Not here", ("no-such-program-anywhere",), None),
                     ("Coloured", (sys.executable, "-c", "print('\\x1b[1mbold\\x1b[0m')"), None))
            quick.DMI = Path(tmp) / "dmi"
            text = quick.report_text(parts, now=(2026, 10, 24, 9, 30, 0, 5, 297, 0))
        self.assertTrue(text.startswith("Monet report, 2026-10-24 09:30\n"))
        self.assertIn("== Trips to Windows\ntrip 7\ntrip 8\ntrip 9\n", text)
        self.assertIn("== Not here\n(no-such-program-anywhere isn't here)\n", text)
        self.assertIn("== Coloured\nbold\n", text)       # without the terminal's colours
        self.assertIn("== Missing\n(", text)
        # Monet's own records, the start before, sleep and the hardware are all asked for.
        headings = [part[0] for part in quick.REPORT_PARTS]
        for heading in ("monet doctor", "Errors since this start", "Errors in the start before", "Sleep and waking",
                        "Graphics and other devices", "Battery and power", "Bluetooth", "Trips to Windows",
                        "Crashes in the last week", "Monet's services"):
            self.assertIn(heading, headings)

    def test_it_lands_in_documents_and_settings_says_so(self):
        quick = quick_helper()
        quick.report_text = lambda now=None: "Monet report\n"
        with tempfile_dir() as tmp:
            path = quick.save_report(Path(tmp) / "Dokument", now=(2026, 10, 24, 9, 30, 0, 5, 297, 0))
            self.assertEqual(path.name, "Monet report 2026-10-24 09.30.txt")
            self.assertEqual(path.read_text(encoding="utf-8"), "Monet report\n")
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('title: i18n("Save a report")', settings)
        self.assertIn('sheet.ask("report", out => {', settings)
        self.assertIn("report logs problem", settings)   # search finds it
        script = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn('elif cmd == "report":', script)
        self.assertIn('tr("Saved a report"), tr("In Documents, as %1.", Path(path).name)', script)


class Magnifier(unittest.TestCase):
    def test_kwins_zoom_turns_on_and_off(self):
        from unittest import mock
        quick = quick_helper()
        calls = []
        with mock.patch.object(quick, "busctl", lambda *a: calls.append(a) or "b true\n"), \
                mock.patch.object(quick, "kwrite", lambda *a: calls.append(("kwrite",) + a)):
            self.assertIs(quick.zoom_on(), True)
            quick.set_zoom(False)
        self.assertIn(("call", "org.kde.KWin", "/Effects", "org.kde.kwin.Effects", "isEffectLoaded", "s", "zoom"), calls)
        self.assertIn(("kwrite", "kwinrc", "Plugins", "zoomEnabled", "false"), calls)
        self.assertIn(("call", "org.kde.KWin", "/Effects", "org.kde.kwin.Effects", "unloadEffect", "s", "zoom"), calls)
        with mock.patch.object(quick, "busctl", lambda *a: None):
            self.assertIsNone(quick.zoom_on())       # no KWin to ask: Settings hides the switch
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('title: i18n("Magnifier")', settings)
        self.assertIn('visible: typeof sheet.accessInfo.zoom === "boolean"', settings)
        self.assertIn('reader: "reader", zoom: "zoom" })[what]', settings)


class WindowsWearsThePainting(unittest.TestCase):
    def test_only_a_windows_monet_installed(self):
        package = (ROOT / "tools/package.sh").read_text()
        self.assertIn('cp "$ROOT/linux/share/wallpapers/Monet/contents/hours/day.jpg" "$OUT/wallpaper.jpg"', package)
        install = (ROOT / "windows/Install-Monet.ps1").read_text()
        block = install[install.index("if ($FromMonet) {\n    # A Windows that Monet installed"):]
        self.assertIn("if (Test-Path $painting) {", block)
        self.assertIn("SystemParametersInfo(0x14, 0, $wallpaper, 3)", block)
        # A Windows kept from before gets Bridge's files only, without the painting.
        payload = (ROOT / "crates/monet/src/windows_setup.rs").read_text()
        self.assertNotIn("wallpaper", payload)


class SecurityAtAGlance(unittest.TestCase):
    """Settings → Security: Secure Boot, encryption, the firewall, updates, firmware and backups,
    each with a fix; the ones that need an administrator ask for the password."""

    def test_secure_boot_from_the_firmware(self):
        quick = quick_helper()
        with tempfile_dir() as tmp:
            efivars = Path(tmp) / "efivars"
            self.assertEqual(quick.secure_boot(efivars), "")            # not started in UEFI mode
            efivars.mkdir()
            self.assertEqual(quick.secure_boot(efivars), "off")         # no SecureBoot variable
            (efivars / quick.SECURE_BOOT_VAR).write_bytes(b"\x06\x00\x00\x00\x01")
            self.assertEqual(quick.secure_boot(efivars), "on")
            (efivars / quick.SECURE_BOOT_VAR).write_bytes(b"\x06\x00\x00\x00\x00")
            self.assertEqual(quick.secure_boot(efivars), "off")

    def test_monets_key_before_secure_boot(self):
        from unittest import mock
        quick = quick_helper()
        with tempfile_dir() as tmp:
            key = Path(tmp) / "akmods-ublue.der"
            key.write_bytes(b"0\x82key")
            with mock.patch.object(quick.shutil, "which", return_value="/usr/bin/mokutil"):
                for said, trusted in ((f"{key} is already enrolled\n", True), (f"{key} is not enrolled\n", False), ("", None)):
                    with mock.patch.object(quick, "said", return_value=said):
                        self.assertEqual(quick.key_trusted(key), trusted)
            self.assertIsNone(quick.key_trusted(Path(tmp) / "missing.der"))

    def test_encryption_firewall_and_a_waiting_update(self):
        from unittest import mock
        quick = quick_helper()

        def disks(source, chain):
            def run(*args, timeout=10):
                return {"findmnt": source, "lsblk": chain}.get(args[0])
            return run

        for source, chain, expected in (("/dev/mapper/luks-1a2b\n", "crypt\npart\ndisk\n", True),
                                        ("/dev/nvme0n1p3[/root]\n", "part\ndisk\n", False),
                                        (None, None, None)):
            with mock.patch.object(quick, "run", disks(source, chain)):
                self.assertEqual(quick.encrypted(), expected)
        with mock.patch.object(quick.shutil, "which", return_value=None):
            self.assertEqual(quick.firewall(), "")
        with mock.patch.object(quick.shutil, "which", return_value="/usr/bin/firewall-cmd"):
            with mock.patch.object(quick, "run", return_value="active\n"):
                self.assertEqual(quick.firewall(), "on")
            with mock.patch.object(quick, "run", return_value=None):           # "inactive" exits 3
                self.assertEqual(quick.firewall(), "off")
        staged = json.dumps({"deployments": [{"staged": True}, {"booted": True}]})
        with mock.patch.object(quick, "run", return_value=staged):
            self.assertTrue(quick.update_waiting())
        with mock.patch.object(quick, "run", return_value=json.dumps({"deployments": [{"booted": True}]})):
            self.assertFalse(quick.update_waiting())

    def test_fixes_that_need_an_administrator(self):
        secure = (ROOT / "linux/libexec/monet-secure").read_text(encoding="utf-8")
        self.assertIn('["systemctl", "enable", "--now", "firewalld"]', secure)
        self.assertIn('["mokutil", "--timeout", "-1"]', secure)
        self.assertIn('input=f"{MOK_PASSWORD}\\n{MOK_PASSWORD}\\n"', secure)
        self.assertIn('MOK_PASSWORD = "monetsetup"', secure)               # the blue screen's, as Setup's
        quick = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn('ok("pkexec", f"{LIBEXECDIR}/monet-secure", cmd, timeout=300)', quick)
        install = (ROOT / "linux/install.sh").read_text(encoding="utf-8")
        self.assertIn('put 755 "$SRC/libexec/monet-secure" "$LIBEXECDIR/monet-secure"', install)
        # Never on the list Monet's polkit rule lets through without a password.
        programs = next(line for line in install.splitlines() if line.startswith("programs="))
        self.assertNotIn("monet-secure", programs)
        self.assertIn("monet-secure", (ROOT / "linux/uninstall.sh").read_text(encoding="utf-8"))

    def test_apps_can_be_let_in_one_at_a_time(self):
        # Hosting a Minecraft world, LocalSend, Syncthing... were turned away without a word:
        # Security lets each in by name (a fixed set of ports), in a policy of its own beside
        # Monet's zone, which stays as the image has it.
        from unittest import mock
        secure = libexec_helper("monet-secure")
        with tempfile_dir() as tmp:
            state, policy = Path(tmp) / "allowed.json", Path(tmp) / "policies/monet-allowed.xml"
            ran = []
            with mock.patch.object(secure, "said", return_value="active"), \
                    mock.patch.object(secure.subprocess, "run", lambda args, **kw: ran.append(args) or mock.Mock(returncode=0)):
                secure.firewall_allow("syncthing", True, state, policy)
                secure.firewall_allow("games", True, state, policy)
                self.assertEqual(secure.allowed(state), ["games", "syncthing"])
                root = ET.parse(policy).getroot()
                self.assertEqual((root.tag, root.get("target"), root.get("priority")), ("policy", "CONTINUE", "-10"))
                self.assertEqual([z.get("name") for z in root.findall("ingress-zone") + root.findall("egress-zone")], ["ANY", "HOST"])
                ports = {(p.get("protocol"), p.get("port")) for p in root.findall("port")}
                self.assertIn(("tcp", "25565"), ports)
                self.assertIn(("udp", "21027"), ports)
                self.assertNotIn(("tcp", "53317"), ports)                   # LocalSend wasn't let in
                secure.firewall_allow("games", False, state, policy)
                secure.firewall_allow("syncthing", False, state, policy)
                self.assertFalse(policy.exists())                           # nothing let in: no policy at all
                self.assertEqual(secure.allowed(state), [])
            self.assertEqual(ran, [["firewall-cmd", "--reload"]] * 4)
        with mock.patch.object(secure, "firewall_allow") as allow, mock.patch("sys.stderr"):
            self.assertEqual(secure.main(["firewall-allow", "22/tcp", "on"]), 2)  # only names it knows
            allow.assert_not_called()
        quick = quick_helper()
        self.assertEqual(quick.FIREWALL_APPS, tuple(secure.APPS))
        with tempfile_dir() as tmp:
            (Path(tmp) / "a.json").write_text('["deskflow", "nonsense", "games"]')
            self.assertEqual(quick.firewall_allowed(Path(tmp) / "a.json"), ["games", "deskflow"])
        source = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn('args[0] in FIREWALL_APPS and args[1] in ("on", "off")', source)
        settings = SETTINGS_QML.read_text(encoding="utf-8")
        self.assertIn('onTapped: sheet.fixSecurity("firewall-allow " + modelData[0] + (open ? " off" : " on"))', settings)
        self.assertIn('visible: safetyCard.s.firewall === "on" && safetyCard.s.firewallStrict === true', settings)
        self.assertIn("rm -f /etc/firewalld/policies/monet-allowed.xml", (ROOT / "linux/uninstall.sh").read_text(encoding="utf-8"))

    def test_a_program_that_starts_accepting_connections_is_asked_about(self):
        # As Windows asks: the program's own port let in when the person allows it, by name.
        from unittest import mock
        secure = libexec_helper("monet-secure")
        with tempfile_dir() as tmp:
            state, ports, policy = Path(tmp) / "allowed.json", Path(tmp) / "ports.json", Path(tmp) / "monet-allowed.xml"
            with mock.patch.object(secure, "said", return_value="inactive"):
                secure.firewall_allow_port("python3", "tcp/8765", True, state, policy, ports)
                secure.firewall_allow("games", True, state, policy, ports)
                found = {(p.get("protocol"), p.get("port")) for p in ET.parse(policy).getroot().findall("port")}
                self.assertIn(("tcp", "8765"), found)
                self.assertIn(("tcp", "25565"), found)                       # the games' too, both kept
                self.assertEqual(secure.allowed_ports(ports), [{"name": "python3", "port": "tcp/8765"}])
                secure.firewall_allow("games", False, state, policy, ports)
                self.assertIn('port="8765"', policy.read_text())             # the program's stays
                secure.firewall_allow_port("python3", "tcp/8765", False, state, policy, ports)
                self.assertFalse(policy.exists())
            ports.write_text('[{"name": "x", "port": "tcp/22"}, {"name": "a\\nb", "port": "tcp/9000"}, "junk"]')
            self.assertEqual(secure.allowed_ports(ports), [])                # never one it couldn't have asked for
        with mock.patch.object(secure, "firewall_allow_port") as allow, mock.patch("sys.stderr"):
            for args in (["python3", "tcp/80", "on"], ["python3", "udp/8765", "on"], ["a\nb", "tcp/8765", "on"],
                         ["python3", "tcp/8765", "maybe"], ["", "tcp/8765", "on"]):
                self.assertEqual(secure.main(["firewall-allow-port", *args]), 2, args)
            allow.assert_not_called()
            secure.main(["firewall-allow-port", "Minecraft server", "tcp/25570", "on"])
            allow.assert_called_once_with("Minecraft server", "tcp/25570", True)

        quick = quick_helper()
        ss = ("LISTEN 0 5 0.0.0.0:8765 0.0.0.0:* users:((\"python3\",pid=41,fd=3))\n"
              "LISTEN 0 50 *:1716 *:* users:((\"kdeconnectd\",pid=42,fd=17))\n"
              "LISTEN 0 4096 127.0.0.1:631 0.0.0.0:*\n"
              "LISTEN 0 10 127.0.0.1:6463 0.0.0.0:* users:((\"Discord\",pid=43,fd=40))\n"
              "LISTEN 0 10 [::1]:9000 [::]:* users:((\"node\",pid=44,fd=20))\n"
              "LISTEN 0 10 [::]:25565 [::]:* users:((\"java\",pid=45,fd=9))\n")
        with mock.patch.object(quick, "run", return_value=ss):
            self.assertEqual(quick.listening_now(), [(8765, 41, "python3"), (1716, 42, "kdeconnectd"), (25565, 45, "java")])
        with tempfile_dir() as tmp:
            zone = Path(tmp) / "monet.xml"
            zone.write_text('<zone><port protocol="tcp" port="1714-1764"/><port protocol="udp" port="5353"/></zone>')

            class Secure:
                APPS = {"games": ("tcp/25565", "udp/25565")}
                allowed = staticmethod(lambda: ["games"])
                allowed_ports = staticmethod(lambda: [{"name": "x", "port": "tcp/9001"}])
            open_ports = quick.let_in((Path(tmp) / "unreadable.xml", zone), Secure)
            self.assertEqual({1714, 1764, 25565, 9001} <= open_ports, True)
            self.assertNotIn(5353, open_ports)                               # UDP's aren't TCP's
            self.assertNotIn(8765, open_ports)

            # One round: python3 asked about, the phone's port and what's let in never, nor what's answered.
            asked = []
            quick.LISTENING = Path(tmp) / "listening.json"
            quick.LISTENING.write_text('{"/usr/bin/node 3000": {"name": "node", "port": 3000, "allowed": false}}')
            with mock.patch.object(quick, "firewall_strict", return_value=True), \
                    mock.patch.object(quick, "let_in", return_value=open_ports), \
                    mock.patch.object(quick, "listening_now", return_value=[(8765, 41, "python3"), (1716, 42, "kdeconnectd"),
                                                                             (3000, 46, "node"), (80, 47, "x")]), \
                    mock.patch.object(quick, "program_of", lambda pid, name: (f"/usr/bin/{name}", name)), \
                    mock.patch.object(quick, "ask_listening", lambda *a: asked.append(a[:3])), \
                    mock.patch.object(quick.getpass, "getuser", return_value="ann"), \
                    mock.patch.object(quick.time, "sleep"):
                quick.listening_watch(rounds=2)
                import threading
                for t in threading.enumerate():
                    if t is not threading.current_thread() and t.daemon:
                        t.join(2)
            self.assertEqual(asked, [("/usr/bin/python3 8765", "python3", 8765)])   # once, though seen twice
            with mock.patch.object(quick.getpass, "getuser", return_value="guest"):
                self.assertEqual(quick.listening_watch(rounds=1), 0)

            # The answer: Allow lets it in (asking for an administrator), Keep blocked is kept too.
            for said, allows, kept in (("allow\n", True, True), ("block\n", False, False), ("", None, None)):
                quick.LISTENING.write_text("{}")
                with mock.patch.object(quick, "run", return_value=said), \
                        mock.patch.object(quick, "listening_allow", return_value=True) as allow:
                    self.assertEqual(quick.ask_listening("/usr/bin/python3 8765", "python3", 8765), allows)
                self.assertEqual(allow.called, said == "allow\n")
                known = json.loads(quick.LISTENING.read_text())
                self.assertEqual(known.get("/usr/bin/python3 8765", {}).get("allowed"), kept)
            quick.LISTENING.write_text(json.dumps({"/usr/bin/python3 8765": {"name": "python3", "port": 8765, "allowed": True},
                                                   "/usr/bin/java 25570": {"name": "java", "port": 25570, "allowed": True}}))
            rows = quick.listening_list(secure=Secure)
            self.assertEqual([(r["name"], r["port"], r["allowed"]) for r in rows], [("java", 25570, False), ("python3", 8765, False)])
            self.assertEqual(bytes.fromhex(rows[1]["key"]).decode(), "/usr/bin/python3 8765")
        self.assertEqual(quick.program_of(999999999, "python3"), ("python3", "python3"))   # gone: by its name

        unit = (ROOT / "linux/systemd/user/monet-listening.service").read_text(encoding="utf-8")
        self.assertIn("ExecStart=@LIBEXECDIR@/monet-quick listening", unit)
        self.assertIn("PartOf=graphical-session.target", unit)
        install = (ROOT / "linux/install.sh").read_text(encoding="utf-8")
        self.assertEqual(install.count("systemctl --global enable monet-ready-lock.service monet-listening.service"), 2)
        self.assertIn('put 644 "$SRC/systemd/user/monet-listening.service"', install)
        uninstall = (ROOT / "linux/uninstall.sh").read_text(encoding="utf-8")
        self.assertIn("/etc/systemd/user/monet-listening.service", uninstall)
        self.assertIn("/var/lib/monet/firewall-allowed-ports.json", uninstall)
        source = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn('"--urgency=critical"', source)
        settings = SETTINGS_QML.read_text(encoding="utf-8")
        self.assertIn('onTapped: sheet.fixSecurity("listening-allow " + modelData.key + (modelData.allowed ? " off" : " on"))',
                      settings)

    def test_only_what_monet_uses_comes_in(self):
        zone = ET.parse(SHARE.parent / "firewalld/monet.xml").getroot()
        self.assertEqual(zone.get("target"), "default")                 # everything else is turned away
        self.assertEqual(zone.findall("service"), [])                   # ports: a missing service stops a zone
        ports = {(p.get("protocol"), p.get("port")) for p in zone.findall("port")}
        self.assertEqual(ports, {("udp", "546"), ("udp", "5353"), ("tcp", "1714-1764"), ("udp", "1714-1764"),
                                 ("udp", "27031-27036"), ("tcp", "27036-27037"), ("tcp", "27040")})
        install = (ROOT / "linux/install.sh").read_text(encoding="utf-8")
        image = install[install.index("# The firewall's Monet zone"):install.index("install -D -m 644 \"$SRC/firewalld/monet.xml\" /etc")]
        self.assertIn('install -D -m 644 "$SRC/firewalld/monet.xml" /usr/lib/firewalld/zones/monet.xml', image)
        self.assertIn('echo "$before" > "$DATADIR/monet/firewall-zone-before"', image)
        # A firewall that won't take it never stops the image's build.
        self.assertIn("firewall-offline-cmd --set-default-zone=monet >/dev/null \\\n            || echo", image)
        uninstall = (ROOT / "linux/uninstall.sh").read_text(encoding="utf-8")
        self.assertLess(uninstall.index("--set-default-zone="), uninstall.index("rm -f /etc/firewalld/zones/monet.xml"))

    def test_the_switch_remembers_the_zone_before(self):
        from unittest import mock
        path = str(ROOT / "linux/libexec/monet-secure")
        loader = importlib.machinery.SourceFileLoader("monet_secure", path)
        secure = importlib.util.module_from_spec(importlib.util.spec_from_loader("monet_secure", loader))
        loader.exec_module(secure)
        with tempfile_dir() as tmp:
            chosen, image = Path(tmp) / "chosen", Path(tmp) / "image"
            self.assertEqual(secure.zone_before((chosen, image)), "public")
            image.write_text("FedoraWorkstation\n")
            self.assertEqual(secure.zone_before((chosen, image)), "FedoraWorkstation")
            chosen.write_text("monet\n")                                  # never Monet's own as "before"
            self.assertEqual(secure.zone_before((chosen, image)), "FedoraWorkstation")
            chosen.write_text("home\n")
            self.assertEqual(secure.zone_before((chosen, image)), "home")
        quick = quick_helper()
        for said, strict in (("monet\n", True), ("FedoraWorkstation\n", False), (None, None)):
            with mock.patch.object(quick, "run", return_value=said):
                self.assertEqual(quick.firewall_strict(), strict)
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('sheet.fixSecurity("firewall-strict " + (safetyCard.s.firewallStrict ? "off" : "on"))', settings)
        self.assertIn('ok("pkexec", f"{LIBEXECDIR}/monet-secure", cmd, args[0], timeout=120)',
                      (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8"))

    def test_the_page(self):
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('{ id: "security", name: i18n("Security")', settings)
        self.assertIn("security: securityPage,", settings)
        self.assertIn('ask("security", out => sheet.safety = sheet.json(out, sheet.safety))', settings)
        for fix in ('sheet.fixSecurity("trust-key")', 'sheet.ask("firmware-setup")', 'sheet.fixSecurity("firewall-on")',
                    'sheet.ask("auto-updates on"', "sheet.installFirmware()", 'sheet.ask("keep on"'):
            self.assertIn(fix, settings)
        # Secure Boot goes on only once Monet's key is trusted, or Monet wouldn't start.
        self.assertIn('safetyCard.s.secureBoot === "off" && safetyCard.s.keyTrusted !== true', settings)
        self.assertTrue((ROOT / "linux/share/monet/settings/swatch-security.png").exists())
        self.assertIn('"security": ("dusk"', (ROOT / "tools/make-icons.py").read_text(encoding="utf-8"))


class YourPhone(unittest.TestCase):
    """Settings → Phone: KDE Connect's phones, pairing, battery, ring, send, texts."""

    LISTED = ("- Pixel 8: 1a2b3c4d_5e6f (paired and reachable)\n"
              "- Old phone: 9f8e7d (paired)\n"
              "- Galaxy S24: c0ffee_01 (reachable)\n"
              "3 devices found\n")
    # KDE 26.08.2: cli/kdeconnect-cli.cpp at 2a0a8c0cee6e2ae0c1ae842be9e1a9fb6cea2a69.
    CURRENT_LISTED = ("- Pixel 8: pixel_01 on 192.0.2.10 via LAN (paired and reachable)\n"
                      "- Galaxy S24: galaxy_02 on 2001:db8::7 via LAN (reachable)\n"
                      "- Dual link: dual_03 on fe80::1%enp0s3, AA:BB:CC:DD:EE:FF via LAN, Bluetooth (beta) (paired and reachable)\n"
                      "- Old phone: old_04 (paired)\n")

    def test_phones_as_kde_connect_lists_them(self):
        quick = quick_helper()
        found = quick.phones(self.LISTED, battery=lambda ident: (82, True))
        self.assertEqual(found, [
            {"id": "1a2b3c4d_5e6f", "name": "Pixel 8", "paired": True, "near": True, "battery": 82, "charging": True},
            {"id": "9f8e7d", "name": "Old phone", "paired": True, "near": False, "battery": None, "charging": None},
            {"id": "c0ffee_01", "name": "Galaxy S24", "paired": False, "near": True, "battery": None, "charging": None}])
        self.assertEqual(quick.phones("0 devices found\n"), [])
        # An id that isn't plain never reaches a command line: that phone is left out.
        self.assertEqual(quick.phones("- Evil: x;reboot (reachable)\n- Evil2: $(id) (paired and reachable)\n"), [])
        self.assertEqual(quick.phones("- Away: abc (unpaired and unreachable)\n")[0],
                         {"id": "abc", "name": "Away", "paired": False, "near": False, "battery": None, "charging": None})
        current = quick.phones(self.CURRENT_LISTED, battery=lambda ident: (82, True))
        self.assertEqual([(p["id"], p["paired"], p["near"], p["battery"]) for p in current],
                         [("pixel_01", True, True, 82), ("galaxy_02", False, True, None),
                          ("dual_03", True, True, 82), ("old_04", True, False, None)])

    def test_discovery_empty_missing_and_failed_are_distinct(self):
        from unittest import mock
        quick = quick_helper()
        with mock.patch.object(quick.shutil, "which", return_value=None), mock.patch.object(quick.subprocess, "run") as run:
            self.assertIsNone(quick.phones())
            run.assert_not_called()
        with mock.patch.object(quick.shutil, "which", return_value="/usr/bin/kdeconnect-cli"):
            with mock.patch.object(quick.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, self.LISTED, "")), \
                    mock.patch.object(quick, "phone_battery", return_value=(82, True)):
                self.assertEqual(len(quick.phones()), 3)
            with mock.patch.object(quick.subprocess, "run", return_value=
                    subprocess.CompletedProcess([], 0, self.CURRENT_LISTED, "4 devices found\n")), \
                    mock.patch.object(quick, "phone_battery", return_value=(82, True)):
                self.assertEqual([p["id"] for p in quick.phones()], ["pixel_01", "galaxy_02", "dual_03", "old_04"])
            for stdout, stderr in (("", "0 devices found\n"), ("0 devices found\n", "")):
                with self.subTest(stdout=stdout, stderr=stderr), mock.patch.object(quick.subprocess, "run", return_value=
                        subprocess.CompletedProcess([], 0, stdout, stderr)):
                    self.assertEqual(quick.phones(), [])
            for failure in (OSError("missing"), subprocess.TimeoutExpired("kdeconnect-cli", 10)):
                with self.subTest(failure=failure), mock.patch.object(quick.subprocess, "run", side_effect=failure):
                    with self.assertRaises((OSError, subprocess.TimeoutExpired)):
                        quick.phones()
            with mock.patch.object(quick.subprocess, "run", return_value=
                    subprocess.CompletedProcess([], 1, self.LISTED, "failed")), mock.patch.object(quick, "phone_battery") as battery:
                with self.assertRaises(subprocess.CalledProcessError):
                    quick.phones()
                battery.assert_not_called()
            malformed = ["- Bad: id on 192.0.2.1 (reachable)", "- Bad: id via LAN (reachable)",
                         "- Bad: id on  via LAN (reachable)", "- Bad: id on 192.0.2.1 via  (reachable)",
                         "- Bad: id on 192.0.2.1  via LAN (reachable)", "- Bad: id on 192.0.2.1 via LAN\tbad (reachable)",
                         "- Bad: id on " + "a" * 1025 + " via LAN (reachable)",
                         "- Bad: id on 192.0.2.1 via " + "a" * 257 + " (reachable)",
                         "- Bad: id on 192.0.2.1 via LAN (" + "a" * 256 + ") (reachable)",
                         "- Bad: x;reboot on 192.0.2.1 via LAN (reachable)"]
            failures = [("", ""), ("3 devices found\n", ""), ("service unavailable", ""), (self.LISTED + "broken row", "")]
            failures += [(line + "\n", "1 device found\n") for line in malformed]
            for stdout, stderr in failures:
                with self.subTest(stdout=stdout), mock.patch.object(quick.subprocess, "run", return_value=
                        subprocess.CompletedProcess([], 0, stdout, stderr)), mock.patch.object(quick, "phone_battery", return_value=(None, None)):
                    with self.assertRaises(ValueError):
                        quick.phones()

    def test_discovery_failure_is_a_failed_helper_call(self):
        import contextlib
        import io
        from unittest import mock
        quick = quick_helper()
        for failure in (OSError(), ValueError(), subprocess.TimeoutExpired("kdeconnect-cli", 10)):
            stdout, stderr = io.StringIO(), io.StringIO()
            with self.subTest(failure=failure), mock.patch.object(quick, "phones", side_effect=failure), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                self.assertEqual(quick.main(["phones"]), 1)
            self.assertEqual(stdout.getvalue(), "")
            self.assertIn("Couldn't check phones", stderr.getvalue())

    def test_the_battery_as_kde_connect_says_it(self):
        from unittest import mock
        quick = quick_helper()
        said = {"charge": "i 64\n", "isCharging": "b false\n"}
        with mock.patch.object(quick, "busctl", lambda *a: said[a[-1]]):
            self.assertEqual(quick.phone_battery("x"), (64, False))
        with mock.patch.object(quick, "busctl", lambda *a: None):
            self.assertEqual(quick.phone_battery("x"), (None, None))
        for charge, charging, expected in (("i -1", "b true", (None, True)), ("i 101", "b false", (None, False)),
                                           ("i 0", "b false", (0, False)), ("i 100", "b true", (100, True)),
                                           ("i 42", "unreadable", (42, None)), ("d 42.5", "", (None, None))):
            said = {"charge": charge, "isCharging": charging}
            with self.subTest(charge=charge, charging=charging), mock.patch.object(quick, "busctl", lambda *a: said[a[-1]]):
                self.assertEqual(quick.phone_battery("x"), expected)

    def test_file_dispatch_preserves_the_selected_path_and_recipient(self):
        from unittest import mock
        quick = quick_helper()
        for path in ("/tmp/ Pictures /Lily – 東京 .jpg ", "/tmp/a picture\r\n"):
            results = [subprocess.CompletedProcess([], 0, os.fsencode(path) + b"\n", b""), subprocess.CompletedProcess([], 0, "", "")]
            with self.subTest(path=path), mock.patch.object(quick.shutil, "which", return_value="/usr/bin/kdeconnect-cli"), \
                    mock.patch.object(quick.subprocess, "run", side_effect=results) as run:
                self.assertEqual(quick.phone_send("second_phone"), {"state": "dispatched"})
                self.assertEqual(run.call_args.args[0], ("kdeconnect-cli", "--share", path, "-d", "second_phone"))

    def test_file_cancel_and_failure_do_not_claim_dispatch(self):
        from unittest import mock
        quick = quick_helper()
        for code, stdout, expected in ((1, b"", "canceled"), (2, b"", "failed"), (0, b"", "failed")):
            with self.subTest(code=code), mock.patch.object(quick.subprocess, "run", return_value=
                    subprocess.CompletedProcess([], code, stdout, "")), mock.patch.object(quick, "run") as share:
                self.assertEqual(quick.phone_send("phone"), {"state": expected})
                share.assert_not_called()
        for failure in (OSError(), subprocess.TimeoutExpired("kdialog", 3600)):
            with self.subTest(failure=failure), mock.patch.object(quick.subprocess, "run", side_effect=failure):
                self.assertEqual(quick.phone_send("phone"), {"state": "failed"})
        with mock.patch.object(quick.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, b"/tmp/photo.jpg\n", b"")), \
                mock.patch.object(quick, "run", return_value=None):
            self.assertEqual(quick.phone_send("phone"), {"state": "failed"})

    def test_file_helper_returns_the_dispatch_outcome(self):
        import contextlib
        import io
        from unittest import mock
        quick = quick_helper()
        for state, code in (("canceled", 0), ("failed", 1), ("dispatched", 0)):
            stdout = io.StringIO()
            with self.subTest(state=state), mock.patch.object(quick, "phone_send", return_value={"state": state}), \
                    contextlib.redirect_stdout(stdout):
                self.assertEqual(quick.main(["phone-send", "phone"]), code)
            self.assertEqual(json.loads(stdout.getvalue()), {"state": state})

    def test_phone_page_callbacks_clear_stale_actions_and_report_dispatch_honestly(self):
        settings = SETTINGS_QML.read_text(encoding="utf-8")
        functions = "\n".join(re.search(r"\n    (function " + name + r"\(.*?\n    })\n", settings, re.S).group(1)
                              for name in ("loadPhones", "sendPhoneFile"))
        source = '''
function check(ok, message) { if (!ok) throw new Error(message); }
var pending = [];
function ask(command, callback) { pending.push({ command, callback }); }
function reply(value, code) { pending.shift().callback(value, code); }
var row = { id: "second", name: "Phone", paired: true, near: true, battery: 42, charging: false };
var sheet = { phoneList: [row], phoneApp: true, phoneAsked: "second", phoneChecking: false,
    phoneFailed: false, phoneSending: false, phoneFileState: "",
    json: function(text, fallback) { try { return JSON.parse(text); } catch (_) { return fallback; } } };
''' + functions + '''
loadPhones(); loadPhones();
check(pending.length === 1, "discovery requests overlap");
reply(JSON.stringify([row]), 1);
check(sheet.phoneFailed && !sheet.phoneChecking && sheet.phoneList.length === 0 && sheet.phoneAsked === "",
      "failed discovery retained stale actions");
for (var broken of ["", "{}", "[null]", JSON.stringify([Object.assign({}, row, { paired: 1 })]),
                    JSON.stringify([Object.assign({}, row, { battery: 101 })])]) {
    loadPhones(); reply(broken, 0);
    check(sheet.phoneFailed && sheet.phoneList.length === 0, "invalid result became usable");
}
loadPhones(); reply("null", 0);
check(!sheet.phoneFailed && !sheet.phoneApp && sheet.phoneList.length === 0, "missing transport became a discovery error");
loadPhones(); reply("[]", 0);
check(!sheet.phoneFailed && sheet.phoneApp && sheet.phoneList.length === 0, "valid empty discovery became an error");
loadPhones(); reply(JSON.stringify([row]), 0);
check(!sheet.phoneFailed && sheet.phoneList[0].id === "second", "retry did not recover");
for (var item of [["dispatched", 0, "dispatched"], ["canceled", 0, "canceled"],
                 ["dispatched", 1, "failed"], ["unknown", 0, "failed"]]) {
    sendPhoneFile("second"); sendPhoneFile("first");
    check(pending.length === 1 && pending[0].command === "phone-send second", "file target changed or requests overlapped");
    reply(JSON.stringify({ state: item[0] }), item[1]);
    check(!sheet.phoneSending && sheet.phoneFileState === item[2], "wrong file outcome");
}
sendPhoneFile("second"); reply("null", 0);
check(sheet.phoneFileState === "failed", "null file result was accepted");
'''
        try:
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtQml import QJSEngine
        except ImportError:
            node = shutil.which("node")
            if not node:
                self.skipTest("no Qt JavaScript engine or Node")
            result = subprocess.run([node, "-e", source], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        else:
            app = QCoreApplication.instance() or QCoreApplication([])  # noqa: F841
            engine = QJSEngine()
            result = engine.evaluate(source)
            self.assertFalse(result.isError(), result.toString())

    def test_the_page(self):
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('{ id: "phone", name: i18n("Phone")', settings)
        self.assertIn("phone: phonePage", settings)
        self.assertIn('source: sheet.art + "phone-qr.png"', settings)
        self.assertTrue((SHARE / "monet/settings/phone-qr.png").is_file())
        self.assertTrue((SHARE / "monet/settings/swatch-phone.png").is_file())
        script = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn('"phone": "kcm_kdeconnect"', script)
        self.assertIn('PAGES = ("light", "wifi", "bluetooth", "phone",', script)
        self.assertIn('sheet.ask("phone-files " + modelData.id)', settings)
        self.assertNotIn('phoneColumn.paired.find(p => p.near).id', settings)
        # Ids from the helper only, checked: never anything else on the command line.
        self.assertIn('elif cmd in ("phone-pair", "phone-unpair", "phone-ring") and args and re.fullmatch(r"[\\w-]+", args[0]):', script)


class Fingerprint(unittest.TestCase):
    def test_a_reader_and_whether_a_finger_is_set_up(self):
        quick = quick_helper()
        none = "found 0 devices\nNo devices available\n"
        unset = ("found 1 devices\nDevice at /net/reactivated/Fprint/Device/0\nUsing device /net/reactivated/Fprint/Device/0\n"
                 "User jon has no fingers enrolled for Goodix MOC Fingerprint Sensor.\n")
        done = ("found 1 devices\nDevice at /net/reactivated/Fprint/Device/0\nUsing device /net/reactivated/Fprint/Device/0\n"
                "Fingerprints for user jon on Goodix MOC Fingerprint Sensor (press):\n - #0: right-index-finger\n")
        self.assertIsNone(quick.fingerprint_state(none))
        self.assertEqual(quick.fingerprint_state(unset), {"enrolled": False})
        self.assertEqual(quick.fingerprint_state(done), {"enrolled": True})
        # The image turns authselect's fingerprint step on; Settings shows the row only with a reader.
        image = (ROOT / "image/Containerfile").read_text()
        self.assertIn("authselect enable-feature with-fingerprint ||", image)   # never stops the build
        self.assertIn("dnf5 -y install fprintd-pam", image)
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn("visible: !!sheet.privacyInfo.fingerprint", settings)


class TextFromAPicture(unittest.TestCase):
    """Screenshot's Extract Text reads your language, and the image has every one Monet speaks."""

    def test_your_language_and_english(self):
        look = (ROOT / "linux/libexec/monet-look").read_text(encoding="utf-8")
        function = look[look.index("ocr_language() {"):look.index("}", look.index("    esac")) + 1]
        script = function + '\nfor l in sv_SE.UTF-8 pt_BR.UTF-8 zh_TW.UTF-8 zh_CN.UTF-8 nb_NO.UTF-8 "de:en" en_US.UTF-8; do echo "$(ocr_language "$l")"; done\n'
        said = subprocess.run(["bash", "-c", script], capture_output=True, text=True, check=True).stdout.split("\n")
        self.assertEqual(said[:7], ["swe", "por", "chi_tra", "chi_sim", "nor", "deu", ""])
        self.assertIn('kw_default spectaclerc General ocrLanguages "${ocr:+$ocr,}eng"', look)
        # Each of Monet's languages has its Tesseract name, and its language pack is in the image
        # (Bazzite's own fifteen, then the rest).
        bazzite = {"eng", "ces", "chi_sim", "chi_tra", "deu", "ell", "fra", "ita", "jpn", "nld", "pol", "por", "rus", "spa", "tur"}
        image = (ROOT / "image/Containerfile").read_text()
        named = set(re.findall(r"echo (\w+) ;;", function))
        self.assertEqual(len(named), 28)
        for code in named - bazzite:
            self.assertIn(f"tesseract-langpack-{code}", image)


class BridgeKeepsItselfUpToDate(unittest.TestCase):
    """On the way back to Monet, Monet Bridge updates itself from the newest release, then restarts."""

    def test_the_way_out_hands_the_restart_to_the_update(self):
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        go_back = bridge[bridge.index("fn go_back("):bridge.index("fn back()")]
        # The update first; the restart of its own only when the task didn't take over.
        self.assertLess(go_back.index("if update_then_restart() {"), go_back.index('run_hidden("shutdown", &["/r", "/t", "0"])'))
        self.assertIn('win::run_hidden("schtasks", &["/run", "/tn", "\\\\Monet\\\\Update"])', bridge)
        self.assertIn("while started.elapsed() < Duration::from_secs(30)", bridge)
        self.assertIn("fs::remove_file(&marker).is_err() && claimed.exists()", bridge)

    def test_the_update_always_restarts_and_checks_what_it_installs(self):
        update = (ROOT / "windows/Update-Monet.ps1").read_text(encoding="utf-8")
        self.assertIn("Move-Item -Force $marker $claimed", update)
        finally_block = update[update.index("} finally {"):]
        self.assertIn("& shutdown.exe /r /t 0", finally_block)
        self.assertIn("(Get-FileHash -Algorithm SHA256 $zip).Hash", update)
        self.assertIn("releases?per_page=10", update)     # every Monet is a pre-release for now
        self.assertIn("[timespan]::FromHours(20)", update)
        self.assertIn("if (-not $CheckOnly -and -not $restart) { return }", update)   # too late: not while Windows goes down
        self.assertIn("$ProgressPreference = 'SilentlyContinue'", update)
        self.assertIn("elseif ((Get-Date) -gt $deadline)", update)
        install = (ROOT / "windows/Install-Monet.ps1").read_text(encoding="utf-8")
        self.assertIn("Where-Object { $_.TaskName -ne 'Update' }", install)   # never stops what's running it
        self.assertIn("'Uninstall-Monet.ps1', 'GameProfile.ps1', 'Update-Monet.ps1'", install)
        self.assertIn("if ($Quiet) { return }", install)
        self.assertIn('Move-Item -Force "$exe.new" $exe', install)
        self.assertIn('"Update-Monet.ps1",', (ROOT / "crates/monet/src/windows_setup.rs").read_text())
        self.assertIn('"$ROOT"/windows/*.ps1', (ROOT / "tools/package.sh").read_text())


class ASmootherTripToWindows(unittest.TestCase):
    """0.9.3: Monet's cover over Windows on a trip, the launchers signed in to once, and Windows
    games updated before the PC switches off."""

    def test_the_cover_travels_with_bridge(self):
        package = (ROOT / "tools/package.sh").read_text()
        payload = (ROOT / "crates/monet/src/windows_setup.rs").read_text()
        install = (ROOT / "windows/Install-Monet.ps1").read_text()
        cover = (ROOT / "crates/monet-bridge/src/cover.rs").read_text(encoding="utf-8")
        for name in ("cover.jpg", "monet-mark.png", "Fraunces-Light.ttf", "Fraunces-Regular.ttf", "OFL-Fraunces.txt"):
            self.assertIn(f'"$OUT/{name}"', package)      # in Windows.zip, so in a Windows Monet installs
            self.assertIn(f'"{name}",', payload)           # and in a Windows kept from before
            self.assertIn(f"'{name}'", install)             # next to monet-bridge.exe
        for name in ("cover.jpg", "monet-mark.png", "Fraunces-Light.ttf", "Fraunces-Regular.ttf"):
            self.assertIn(f'"{name}"', cover)
        self.assertIn('"Update-Windows.ps1",', payload)
        self.assertIn("'Update-Windows.ps1'", install)
        # The taskbar slides away only on a Windows that Monet installed.
        painted = install[install.index("if (Test-Path $painting) {"):install.index("# Setup ran once from the Startup folder")]
        self.assertIn("StuckRects3", painted)

    def test_settings_ask_bridge_for_a_task(self):
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('(asking.task === "launchers" || asking.task === "update") ? asking.task : ""', settings)
        self.assertIn('task ? ["monet", "windows", "--" + task]', settings)
        self.assertIn('call(["monet", "games", "--updated"]', settings)
        main = (ROOT / "crates/monet/src/main.rs").read_text(encoding="utf-8")
        self.assertIn('["windows"] if args.iter().any(|a| a == "--launchers") => switch(None, Some("launchers"), confirm)', main)
        self.assertIn('["windows"] if args.iter().any(|a| a == "--update") => switch(None, Some("update"), confirm)', main)
        self.assertIn('command.args(["--task", task])', main)
        core = (ROOT / "crates/monet-core/src/request.rs").read_text(encoding="utf-8")
        self.assertIn('pub const TASKS: &[&str] = &["launchers", "update"];', core)
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        self.assertIn('Some("launchers") => return sign_in_trip(efi, state)', bridge)
        self.assertIn('Some("update") => return update_trip(efi, now(), false)', bridge)

    def test_launchers_open_as_the_person_never_as_administrator(self):
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        pending = bridge[bridge.index("fn launch_pending()"):bridge.index("/// How long to wait for Steam")]
        self.assertIn("launchers::open(key, pending.quietly)", pending)
        trip = bridge[bridge.index("fn sign_in_trip("):bridge.index("/// An update trip that's restarting")]
        self.assertIn("run_as_person(&pending)", trip)
        self.assertNotIn("launchers::open(", trip)
        self.assertIn('&["/run", "/tn", "\\\\Monet\\\\Launch"]', bridge)

    def test_windows_update_on_the_update_trip(self):
        script = (ROOT / "windows/Update-Windows.ps1").read_text(encoding="utf-8")
        self.assertIn("Type='Software'", script)                      # not drivers: the game's driver stays
        self.assertIn("CanRequestUserInput) { continue }", script)     # nobody is there to answer
        self.assertIn("Tell 'done' $wanted.Count $result.RebootRequired", script)
        self.assertIn("[IO.File]::WriteAllText", script)              # no BOM for Bridge's JSON reader
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        trip = bridge[bridge.index("fn update_trip("):bridge.index("/// Where monet-bridge.exe and its files are.")]
        # Restarted once into Windows only when it signs in by itself and nobody chose Switch off now.
        self.assertIn("if said.reboot && !resumed && !early && signs_in_by_itself {", trip)
        self.assertIn("boot::set_boot_next(efi, current)", trip)
        self.assertIn('win::run_hidden("shutdown", &["/s", "/t", "0"])', trip)


class OneGamesFolderForBoth(unittest.TestCase):
    """After 0.9.3: Windows' Games folder, a Steam library on both sides, so a game installs once
    (monet-windows-drive, monet-quick steam-share, Monet Bridge's share_with_steam)."""

    STEAM_LIST = ('"libraryfolders"\n{\n\t"0"\n\t{\n\t\t"path"\t\t"/var/home/ann/.local/share/Steam"\n'
                  '\t\t"label"\t\t""\n\t\t"apps"\n\t\t{\n\t\t\t"228980"\t\t"1"\n\t\t}\n\t}\n}\n')
    CONFIG = ('"InstallConfigStore"\n{\n\t"Software"\n\t{\n\t\t"Valve"\n\t\t{\n\t\t\t"Steam"\n\t\t\t{\n'
              '\t\t\t\t"AutoUpdateWindowEnabled"\t\t"0"\n\t\t\t\t"CompatToolMapping"\n\t\t\t\t{\n'
              '\t\t\t\t\t"1245620"\n\t\t\t\t\t{\n\t\t\t\t\t\t"name"\t\t""\n\t\t\t\t\t\t"config"\t\t""\n'
              '\t\t\t\t\t\t"priority"\t\t"250"\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t}\n\t\t}\n\t}\n}\n')

    def setUp(self):
        self.drive = libexec_helper("monet-windows-drive")
        self.quick = quick_helper()

    def test_only_a_windows_with_bridge_and_a_clean_drive_is_opened(self):
        tree = {"blockdevices": [{"path": "/dev/nvme0n1", "fstype": None, "children": [
            {"path": "/dev/nvme0n1p1", "fstype": "vfat"}, {"path": "/dev/nvme0n1p3", "fstype": "btrfs"},
            {"path": "/dev/nvme0n1p4", "fstype": "ntfs"}]}]}
        volumes = self.drive.ntfs_volumes(tree)
        self.assertEqual(volumes[1:], [("/dev/nvme0n1p1", "vfat"), ("/dev/nvme0n1p3", "btrfs"), ("/dev/nvme0n1p4", "ntfs")])
        windows = {"/windows/system32": {"winload.efi", "drivers"}, "/program files/monet": {"monet-bridge.exe"}}
        ls = lambda device, folder: windows.get(folder.lower(), set())
        self.assertEqual(self.drive.find_windows(volumes, ls), ("/dev/nvme0n1p4", ""))
        self.assertEqual(self.drive.find_windows(volumes, lambda d, f: windows["/windows/system32"] if "System32" in f else set()),
                         (None, "no-bridge"))
        self.assertEqual(self.drive.find_windows([("/dev/sda2", "bitlocker")], ls), (None, "bitlocker"))
        self.assertEqual(self.drive.find_windows([("/dev/sda1", "ntfs")], lambda d, f: set()), (None, "no-windows"))
        # ntfs-3g's probe decides: hibernated or Fast Startup, a drive Windows must check, no probe.
        from unittest import mock
        for code, state in ((0, "open"), (14, "asleep"), (15, "unclean"), (12, "unknown"), (None, "unknown")):
            with mock.patch.object(self.drive, "run", lambda *a, **k: (code, "")):
                self.assertEqual(self.drive.safe_to_write("/dev/nvme0n1p4"), state)

    def test_the_drive_is_roots_and_only_games_is_shared(self):
        script = (ROOT / "linux/libexec/monet-windows-drive").read_text(encoding="utf-8")
        # Mounted a level down: the drive's own top folder (the person's, 0755) would let anyone in.
        self.assertIn('LOCKED = Path("/run/monet/windows-drive")', script)
        self.assertIn('DRIVE = LOCKED / "c"', script)
        self.assertIn("os.chmod(LOCKED, 0o700)", script)
        d = self.drive
        with tempfile_dir() as tmp:
            passwd = Path(tmp) / "passwd"
            passwd.write_text("root:x:0:0::/root:/bin/bash\nguest:x:1000:1000:Guest:/var/home/guest:/bin/bash\n"
                              "ann:x:1001:1001:Ann:/var/home/ann:/bin/bash\n")
            self.assertEqual(d.owner(passwd)[0], "ann")       # never the guest
            # Windows' own drive isn't one of Files' devices (its Games folder is shared instead).
            from unittest import mock
            calls = []
            with mock.patch.object(d, "HIDDEN", Path(tmp) / "rules.d/90-monet-windows.rules"), \
                    mock.patch.object(d, "run", lambda *a, **k: calls.append(a) or (0, "1A2B3C4D5E6F7A8B\n")):
                d.hide("/dev/nvme0n1p4")
                self.assertIn('ENV{ID_FS_UUID}=="1A2B3C4D5E6F7A8B", ENV{UDISKS_IGNORE}="1"', d.HIDDEN.read_text())
            self.assertEqual(calls[-1], ("udevadm", "trigger", "--action=change", "/dev/nvme0n1p4"))
            with mock.patch.object(d, "HIDDEN", Path(tmp) / "other.rules"), mock.patch.object(d, "run", lambda *a, **k: (0, '"; RUN+="x\n')):
                d.hide("/dev/sda1")
                self.assertFalse(d.HIDDEN.exists())             # never a rule from a strange answer
            # Nothing reached through a link (a junction made in Windows).
            root = Path(tmp) / "drive"
            (root / "Users/ann/Pictures/Screenshots").mkdir(parents=True)
            self.assertTrue(d.no_links(root / "Users/ann/Pictures/Screenshots", root))
            try:
                (root / "Users/bob").symlink_to(root / "Users/ann", target_is_directory=True)
            except OSError:
                pass  # no links on this PC
            else:
                self.assertFalse(d.no_links(root / "Users/bob/Pictures/Screenshots", root))
        self.assertIn('SHARED = Path("/run/media/Windows games")', script)
        self.assertIn('run("mount", "--bind", games, SHARED)', script)
        self.assertIn('options = f"rw,nosuid,nodev,uid={uid},gid={gid},umask=077"', script)
        # Never written when it couldn't be checked.
        self.assertIn('return "unknown"  # no probe, no writing', script)
        self.assertIn(" ntfs-3g ", (ROOT / "image/Containerfile").read_text())
        quick = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn('SHARED = Path("/run/media/Windows games")', quick)
        person = self.drive.owner
        with tempfile_dir() as tmp:
            passwd = Path(tmp) / "passwd"
            passwd.write_text("root:x:0:0:root:/root:/bin/bash\nnobody:x:65534:65534::/:/sbin/nologin\n"
                              "ann:x:1000:1000:Ann:/var/home/ann:/bin/bash\nbo:x:1001:1001::/var/home/bo:/bin/bash\n")
            self.assertEqual(person(passwd), ("ann", 1000, 1000, Path("/var/home/ann")))

    def test_units_run_it_before_the_sign_in_screen(self):
        unit = (ROOT / "linux/systemd/monet-windows-drive.service").read_text()
        for line in ("ExecStart=@LIBEXECDIR@/monet-windows-drive", "After=local-fs.target monet-windows-setup.service NetworkManager.service",
                     "Before=display-manager.service plasmalogin.service", "RemainAfterExit=yes"):
            self.assertIn(line, unit)
        files = (ROOT / "linux/systemd/monet-windows-files.service").read_text()
        self.assertIn("ExecStart=@LIBEXECDIR@/monet-windows-drive bring", files)
        self.assertIn("ConditionPathIsMountPoint=/run/monet/windows-drive/c", files)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('put 755 "$SRC/libexec/monet-windows-drive" "$LIBEXECDIR/monet-windows-drive"', install)
        self.assertEqual(install.count("systemctl enable monet-windows-drive.service monet-windows-files.service"), 2)
        uninstall = (ROOT / "linux/uninstall.sh").read_text()
        self.assertIn("rm -f /etc/systemd/system/monet-windows-drive.service", uninstall)
        self.assertIn(" monet-windows-drive monet-paint monet-guest monet-prepare-windows monet-games monet-settings monet-store monet-store-jobs; do", uninstall)
        self.assertIn("linux/libexec/monet-windows-drive ", (ROOT / ".github/workflows/build.yml").read_text())
        session = (ROOT / "linux/libexec/monet-session").read_text()
        self.assertIn('"$LIBEXECDIR/monet-quick" steam-share >/dev/null 2>&1', session)
        # And before Steam's own autostart, which starts alongside monet-session.
        dropin = (ROOT / "linux/systemd/user/app-steam@autostart.service.d/monet-steam-share.conf").read_text()
        self.assertIn("ExecStartPre=-@LIBEXECDIR@/monet-quick steam-share", dropin)
        self.assertIn('"$USERUNITDIR/app-steam@autostart.service.d/monet-steam-share.conf"', install)
        # Before anything else at sign-in: Steam may start any moment.
        self.assertLess(session.index("steam-share"), session.index('"$BINDIR/monet" shortcuts'))

    @unittest.skipUnless(hasattr(os, "geteuid"), "links and Unix permissions")
    def test_the_games_folder_is_a_steam_library_for_both(self):
        with tempfile_dir() as tmp:
            root, steam = Path(tmp) / "drive", Path(tmp) / "home/.local/share/Steam"
            (root / "GAMES/steamapps/compatdata").mkdir(parents=True)  # an empty one Steam made
            games = self.drive.prepare_games(root, steam)
            self.assertEqual(games, root / "GAMES")  # Windows' own spelling kept
            mark = (games / "libraryfolder.vdf").read_text()
            self.assertRegex(mark, r'^"libraryfolder"\n\{\n\t"contentid"\t\t"\d+"\n\t"label"\t\t""\n\}\n$')
            for name in ("compatdata", "shadercache"):
                self.assertEqual(os.readlink(games / "steamapps" / name), str(steam / "steamapps" / name))
            # Again: nothing changes, the mark stays.
            self.drive.prepare_games(root, steam)
            self.assertEqual((games / "libraryfolder.vdf").read_text(), mark)
            # A folder with Proton's files in it is left alone.
            shutil.rmtree(Path(tmp) / "drive")
            (root / "Games/steamapps/shadercache/730").mkdir(parents=True)
            self.drive.prepare_games(root, steam)
            self.assertTrue((root / "Games/steamapps/shadercache/730").is_dir())
            # C:\Games as a junction someone made in Windows: never followed, nor shared.
            shutil.rmtree(Path(tmp) / "drive")
            (root / "Users/Bob").mkdir(parents=True)
            try:
                (root / "Games").symlink_to(root / "Users/Bob", target_is_directory=True)
            except OSError:
                return  # no links on this PC
            with self.assertRaises(OSError):
                self.drive.prepare_games(root, steam)
            self.assertFalse((root / "Users/Bob/steamapps").exists())

    def test_steam_here_gets_the_folder_and_proton_for_its_games(self):
        q = self.quick
        with tempfile_dir() as tmp:
            steam, shared = Path(tmp) / "Steam", Path(tmp) / "Windows games"
            (steam / "steamapps").mkdir(parents=True)
            (steam / "config").mkdir()
            (steam / "steamapps/libraryfolders.vdf").write_text(self.STEAM_LIST)
            (steam / "config/config.vdf").write_text(self.CONFIG)
            (shared / "steamapps").mkdir(parents=True)
            (shared / "libraryfolder.vdf").write_text('"libraryfolder"\n{\n\t"contentid"\t\t"77"\n\t"label"\t\t""\n}\n')
            for appid in ("1172470", "1245620", "359550"):
                (shared / f"steamapps/appmanifest_{appid}.acf").write_text('"AppState" { }')
            self.assertEqual(q.share_with_steam(steam, shared), "added")
            listed = q.vdf((steam / "steamapps/libraryfolders.vdf").read_text())["libraryfolders"]
            self.assertEqual(listed["1"]["path"], str(shared))
            self.assertEqual((listed["1"]["contentid"], listed["1"]["apps"]), ("77", {}))
            self.assertEqual(listed["0"]["apps"], {"228980": "1"})
            tools = q.pick(q.vdf((steam / "config/config.vdf").read_text()), "InstallConfigStore", "Software", "Valve",
                           "Steam", "CompatToolMapping")
            self.assertEqual(tools["1172470"], {"name": "proton_experimental", "config": "", "priority": "250"})
            self.assertEqual(tools["359550"]["name"], "proton_experimental")
            self.assertEqual(tools["1245620"]["name"], "")  # chosen before: kept
            self.assertEqual(q.pick(q.vdf((steam / "config/config.vdf").read_text()), "InstallConfigStore", "Software",
                                    "Valve", "Steam")["AutoUpdateWindowEnabled"], "0")
            # Steam's files as they were, kept once.
            self.assertEqual((steam / "config/config.vdf.before-monet").read_text(), self.CONFIG)
            # Again: nothing more.
            before = (steam / "steamapps/libraryfolders.vdf").read_text(), (steam / "config/config.vdf").read_text()
            self.assertEqual(q.share_with_steam(steam, shared), "ok")
            self.assertEqual(((steam / "steamapps/libraryfolders.vdf").read_text(), (steam / "config/config.vdf").read_text()), before)
            # A config without a tool list gets one.
            (steam / "config/config.vdf").write_text(self.CONFIG.replace('"CompatToolMapping"', '"Other"'))
            q.share_with_steam(steam, shared)
            tools = q.pick(q.vdf((steam / "config/config.vdf").read_text()), "InstallConfigStore", "Software", "Valve",
                           "Steam", "CompatToolMapping")
            self.assertEqual(set(tools), {"1172470", "1245620", "359550"})
            self.assertEqual(q.share_with_steam(Path(tmp) / "none", shared), "no-steam")

    def test_keyvalues_blocks_are_found_by_their_place(self):
        q = self.quick
        text = '"a"\n{\n\t"b" "x"\n\t"c"\n\t{\n\t\t"d" "{"\n\t}\n}\n'
        start, end = q.vdf_block(text, ["A", "c"])
        self.assertEqual(text[start:end].strip(), '"d" "{"')
        self.assertIsNone(q.vdf_block(text, ["b"]))
        self.assertEqual(q.vdf_children(text, ["a"]), {"b", "c"})
        self.assertEqual(q.vdf_insert(text, ["a", "c"], '\t\t"e"\t\t"1"\n'),
                         '"a"\n{\n\t"b" "x"\n\t"c"\n\t{\n\t\t"d" "{"\n\t\t"e"\t\t"1"\n\t}\n}\n')
        self.assertEqual(q.vdf_lines({"k": 'say "hi"', "b": {"c": "C:\\x"}}, 1),
                         '\t"k"\t\t"say \\"hi\\""\n\t"b"\n\t{\n\t\t"c"\t\t"C:\\\\x"\n\t}\n')

    def test_a_game_in_the_folder_is_on_both_sides(self):
        q = self.quick
        marks = {"1172470": "windows"}
        steam = {"1172470": "Apex Legends", "359550": "Rainbow Six Siege", "730": "Counter-Strike 2"}
        found = {g["id"]: g for g in q.library(marks, steam, [], [], {"1172470", "359550"}, True)}
        self.assertEqual((found["steam:1172470"]["plays"], found["steam:1172470"]["windows"], found["steam:1172470"]["shared"]),
                         ("windows", "steam:1172470", True))
        self.assertEqual((found["steam:359550"]["plays"], found["steam:359550"]["windows"]), ("monet", "steam:359550"))
        self.assertEqual((found["steam:730"]["windows"], found["steam:730"]["shared"]), ("", False))
        # Needs Windows, only in Monet's own folder: Steam here can move it to Windows games.
        moving = {g["id"]: g for g in q.library(marks, steam, [], [], set(), True)}
        self.assertEqual((moving["steam:1172470"]["move"], moving["steam:730"]["move"]), (True, False))
        self.assertFalse(found["steam:1172470"]["move"])  # already there
        self.assertFalse({g["id"]: g for g in q.library(marks, steam, [], [], set(), False)}["steam:1172470"]["move"])
        blocked = q.game_marks(marks, steam, set(), {"1172470"})["blocked"]
        self.assertEqual(blocked, [{"id": "1172470", "name": "Apex Legends", "onWindows": True, "shared": True}])

    def test_a_game_steam_is_downloading_says_how_far(self):
        q = self.quick
        self.assertIsNone(q.steam_progress({"StateFlags": "4"}))
        self.assertEqual(q.steam_progress({"StateFlags": "1026", "BytesDownloaded": "45", "BytesToDownload": "100"}), 45)
        self.assertEqual(q.steam_progress({"StateFlags": "1030", "BytesDownloaded": "0", "BytesToDownload": "0"}), 0)
        self.assertEqual(q.steam_progress({"StateFlags": "2"}), 0)       # wants a download, not started
        self.assertIsNone(q.steam_progress({"StateFlags": "6"}))         # an update Steam waits to do
        self.assertEqual(q.steam_progress({"StateFlags": "1026", "BytesDownloaded": "100", "BytesToDownload": "100"}), 99)
        found = {g["id"]: g for g in q.library({}, {"730": "Counter-Strike 2", "570": "Dota 2"}, [], [], set(), False, [],
                                               {"730": 45, "570": None})}
        self.assertEqual((found["steam:730"]["progress"], found["steam:570"]["progress"]), (45, None))
        games = GAMES_APP.read_text(encoding="utf-8")
        self.assertIn('i18n("%1 · Downloading, %2%", storeName(game.store), game.progress)', games)

    def test_heroic_is_one_tap_away(self):
        q = self.quick
        from unittest import mock
        calls = []
        answers = iter([None, None, "com.heroicgameslauncher.hgl"])
        with mock.patch.object(q, "run", lambda *a, **k: calls.append(a) or next(answers)), \
                mock.patch.object(q.subprocess, "Popen", lambda *a, **k: calls.append(("Popen", *a[0]))):
            self.assertTrue(q.get_heroic())
        self.assertEqual(calls[1], ("flatpak", "install", "--system", "--noninteractive", "-y", "flathub", "com.heroicgameslauncher.hgl"))
        self.assertEqual(calls[-1], ("Popen", "flatpak", "run", "com.heroicgameslauncher.hgl"))
        with tempfile_dir() as tmp, mock.patch.object(q, "HEROIC_ROOTS", (Path(tmp) / "heroic",)), \
                mock.patch.object(q, "DATA_HOME", Path(tmp)), mock.patch.object(q.shutil, "which", lambda name: None):
            self.assertFalse(q.heroic_here())
            (Path(tmp) / "flatpak/app/com.heroicgameslauncher.hgl").mkdir(parents=True)
            self.assertTrue(q.heroic_here())
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('visible: sharedCard.s.state === "open" && sharedCard.s.heroic === false', settings)
        self.assertIn('sheet.ask("get-heroic", out => {', settings)

    def test_widgets_buttons_are_monets_pills(self):
        # Plasma's own text buttons look like KDE's, not Monet's: the widgets draw their own
        # (KDE's settings windows, styled by Monet's app theme, may keep theirs).
        for qml in PLASMA.glob("plasmoids/org.monet.*/contents/ui/*.qml"):
            if qml.name.startswith("Config"):
                continue
            text = qml.read_text(encoding="utf-8")
            self.assertNotIn("PlasmaComponents.Button {", text, qml)
            for at in [m.start() for m in re.finditer(r"PlasmaComponents\.ToolButton \{", text)]:
                block = text[at:text.index("\n                }", at)]
                self.assertIn("AbstractButton.IconOnly", block, f"{qml}: a ToolButton with words")
        # Games, the app, draws its own too, with nothing of Plasma's: it's an app, not a widget.
        for qml in GAMES_APP.parent.glob("*.qml"):
            self.assertNotIn("org.kde.plasma", qml.read_text(encoding="utf-8"), qml.name)
        pill = (GAMES_APP.parent / "Pill.qml").read_text(encoding="utf-8")
        self.assertIn("MouseArea {", pill)
        shared = (SHARE / "monet/widgets/ActionButton.qml").read_text(encoding="utf-8")
        self.assertIn("T.AbstractButton {", shared)
        self.assertIn("control.visualFocus", shared)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn("for applet in org.monet.sound org.monet.quick; do", install)
        self.assertIn('"$SRC/share/monet/widgets/ActionButton.qml"', install)

    def test_the_gallery_works_with_the_keys(self):
        widget = GAMES_APP.read_text(encoding="utf-8")
        grid = widget[widget.index("id: grid"):widget.index("delegate: Item {")]
        for line in ("keyNavigationEnabled: true", "[Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space].includes(event.key) && at >= 0",
                     "root.openPage(root.shown[at])", "event.key === Qt.Key_Menu && at >= 0", "search.forceActiveFocus()",
                     "if (root.sheetOpen)\n                            return", "!(event.modifiers & modifiers)"):
            self.assertIn(line, grid)
        # The game the keys are on is kept by its id: a refresh while a download runs never moves it.
        self.assertIn("const at = root.shown.findIndex(g => g.id === root.keyed)", grid)
        self.assertIn("visible: root.keys && grid.activeFocus && tile.modelData.id === root.keyed", widget)
        # A game's page: Play has the keys, Escape goes back to the covers.
        page = (GAMES_APP.parent / "GamePage.qml").read_text(encoding="utf-8")
        self.assertIn("Keys.onEscapePressed: page.back()", page)
        self.assertIn("Qt.callLater(() => gamePage.focusPlay())", widget)
        # The sheet takes the keys, its bright button first; Escape clears the search, binding kept.
        self.assertIn("Qt.callLater(() => sheetGo.visible ? sheetGo.forceActiveFocus() : sheetCancel.forceActiveFocus())", widget)
        self.assertIn("Keys.onEscapePressed: root.sheetOpen = false", widget)
        self.assertNotIn('text = ""', widget)

    def test_the_gallery_offers_windows_games_to_steam_until_put_away(self):
        q = self.quick
        from unittest import mock
        with tempfile_dir() as tmp, mock.patch.object(q, "SHARED_HINT_OFF", Path(tmp) / "monet/shared-hint-off"), \
                mock.patch.object(q, "shared_state", lambda: {"state": "open"}):
            self.assertTrue(q.shared_info([])["hint"])
            q.main(["shared-hint-off"])
            self.assertFalse(q.shared_info([])["hint"])
        games = GAMES_APP.read_text(encoding="utf-8")
        self.assertIn('root.shared.state === "open" && root.shared.mine === true && root.shared.steam !== true', games)
        self.assertIn('run(["helper", "steam-share", "now"], out => {', games)
        self.assertIn('root.run(["helper", "shared-hint-off"])', games)

    def test_heroics_epic_games_there_are_left_ready_for_epics_launcher(self):
        q = self.quick
        with tempfile_dir() as tmp:
            shared, legendary = Path(tmp) / "Windows games", Path(tmp) / "heroic/legendaryConfig/legendary"
            (shared / "Fortnite").mkdir(parents=True)
            (legendary / "metadata").mkdir(parents=True)
            (legendary / "manifests").mkdir()
            (legendary / "installed.json").write_text(json.dumps({
                "Fortnite": {"app_name": "Fortnite", "title": "Fortnite", "install_path": str(shared / "Fortnite"),
                             "platform": "Windows", "version": "++Fortnite+Release-32.00", "executable": "FortniteGame/Binaries/Win64/FortniteLauncher.exe",
                             "launch_parameters": "", "install_size": 98765, "install_tags": [], "base_urls": ["https://cdn"],
                             "requires_ot": False, "can_run_offline": False, "is_dlc": False},
                "Sugar": {"app_name": "Sugar", "title": "Rocket League", "install_path": str(Path(tmp) / "Games/Heroic/Sugar"),
                          "platform": "Windows"}}))
            (legendary / "metadata/Fortnite.json").write_text(json.dumps({"app_name": "Fortnite", "metadata": {
                "id": "4fe75bbc5a674f4f9b356b5c90567da5", "namespace": "fn", "customAttributes": {"FolderName": {"value": "Fortnite"}}}}))
            (legendary / "manifests/Fortnite.manifest").write_bytes(b"\x0c\xc0\xbe\x44manifest")
            (shared / ".monet/epic").mkdir(parents=True)
            (shared / ".monet/epic/Gone.json").write_text("{}")
            self.assertEqual(q.epic_share([legendary], shared), ["Fortnite"])
            note = json.loads((shared / ".monet/epic/Fortnite.json").read_text())
            self.assertRegex(note["guid"], r"^[0-9A-F]{32}$")
            self.assertEqual((note["folder"], note["CatalogNamespace"], note["MandatoryAppFolderName"]), ("Fortnite", "fn", "Fortnite"))
            egstore = shared / "Fortnite/.egstore"
            self.assertEqual((egstore / f"{note['guid']}.manifest").read_bytes(), b"\x0c\xc0\xbe\x44manifest")
            self.assertEqual(json.loads((egstore / f"{note['guid']}.mancpn").read_text()),
                             {"AppName": "Fortnite", "CatalogItemId": "4fe75bbc5a674f4f9b356b5c90567da5", "CatalogNamespace": "fn",
                              "FormatVersion": 0})
            self.assertFalse((shared / ".monet/epic/Gone.json").exists())     # no longer there
            # Again: the same guid, nothing new.
            q.epic_share([legendary], shared)
            self.assertEqual(json.loads((shared / ".monet/epic/Fortnite.json").read_text())["guid"], note["guid"])
            # Heroic's list says where each game is: in the folder, it's on both sides.
            heroic = {g["app"]: g for g in q.heroic_games((Path(tmp) / "heroic",), shared)}
            self.assertEqual((heroic["Fortnite"]["shared"], heroic["Sugar"]["shared"]), (True, False))
            found = {g["id"]: g for g in q.library({"epic/fn": "windows"}, {}, [heroic["Fortnite"]], [], set(), False, [])}
            self.assertEqual((found["epic:Fortnite"]["plays"], found["epic:Fortnite"]["windows"], found["epic:Fortnite"]["shared"]),
                             ("windows", "epic:Fortnite", True))
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        agent = bridge[bridge.index("fn agent()"):bridge.index("/// Windows updates sometimes put Windows first")]
        self.assertLess(agent.index("share_with_epic();"), agent.index("publish(&scan())"))
        self.assertIn("found.extend(scan_gog());", bridge)
        # The launcher a shared game needs (Epic's here), installed on the first trip for it when
        # Windows hasn't got it: from the installer Monet fetched, when its maker signed it.
        handle = bridge[bridge.index("fn handle("):bridge.index("/// Each launcher Monet can fetch the installer of")]
        self.assertLess(handle.index("missing_launcher(&id, &scan())"), handle.index("let found = scan();"))
        self.assertIn('.arg(install_dir().join("Install-Launcher.ps1"))', bridge)
        self.assertIn('"Install-Launcher.ps1",', (ROOT / "crates/monet/src/windows_setup.rs").read_text(encoding="utf-8"))
        self.assertIn("'Install-Launcher.ps1'", (ROOT / "windows/Install-Monet.ps1").read_text(encoding="utf-8"))
        script = (ROOT / "windows/Install-Launcher.ps1").read_text(encoding="utf-8")
        self.assertIn("https://launcher-public-service-prod06.ol.epicgames.com/launcher/api/installer/download/EpicGamesLauncherInstaller.msi", script)
        self.assertIn("'/qn'", script)
        self.assertIn("$signature.Status -eq 'Valid' -and $signature.SignerCertificate.Subject -match $known.Signer", script)
        self.assertIn("Signer = 'O=\"?Blizzard Entertainment'", script)

    WLAN = ('<?xml version="1.0"?>\n<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">\n'
            '\t<name>{name}</name>\n\t<SSIDConfig>\n\t\t<SSID>\n\t\t\t<hex>00</hex>\n\t\t\t<name>{name}</name>\n\t\t</SSID>\n'
            '\t</SSIDConfig>\n\t<connectionType>ESS</connectionType>\n\t<MSM>\n\t\t<security>\n\t\t\t<authEncryption>\n'
            '\t\t\t\t<authentication>{auth}</authentication>\n\t\t\t\t<encryption>AES</encryption>\n'
            '\t\t\t\t<useOneX>false</useOneX>\n\t\t\t</authEncryption>\n\t\t\t<sharedKey>\n\t\t\t\t<keyType>passPhrase</keyType>\n'
            '\t\t\t\t<protected>false</protected>\n\t\t\t\t<keyMaterial>{key}</keyMaterial>\n\t\t\t</sharedKey>\n'
            '\t\t</security>\n\t</MSM>\n\t<MacRandomization xmlns="http://www.microsoft.com/networking/WLAN/profile/v3">\n'
            '\t\t<enableRandomization>false</enableRandomization>\n\t</MacRandomization>\n</WLANProfile>\n')

    def test_wifi_works_in_both(self):
        d = self.drive
        self.assertEqual(d.windows_network(self.WLAN.format(name="Cafe Monet", auth="WPA2PSK", key="croissant42")),
                         ("Cafe Monet", "wpa-psk", "croissant42", False))
        self.assertEqual(d.windows_network(self.WLAN.format(name="Home", auth="WPA3SAE", key="s3cret!"))[1], "sae")
        self.assertIsNone(d.windows_network(self.WLAN.format(name="Work", auth="WPA2", key="")))  # 802.1X
        self.assertIsNone(d.windows_network(self.WLAN.format(name="Hidden key", auth="WPA2PSK", key="")))
        self.assertIsNone(d.windows_network("not xml"))
        with tempfile_dir() as tmp:
            root, nm = Path(tmp) / "drive", Path(tmp) / "system-connections"
            out = root / "ProgramData/Monet/wifi-out"
            out.mkdir(parents=True)
            nm.mkdir()
            (nm / "Home.nmconnection").write_text("[connection]\nid=Home\ntype=wifi\n\n[wifi]\nssid=Home\n")
            (out / "Wi-Fi-Cafe Monet.xml").write_text(self.WLAN.format(name="Cafe Monet", auth="WPA2PSK", key="croissant42"))
            (out / "Wi-Fi-Home.xml").write_text(self.WLAN.format(name="Home", auth="WPA2PSK", key="other"))
            from unittest import mock
            with mock.patch.object(d, "run", lambda *a, **k: (0, "")):
                self.assertEqual(d.take_wifi(root, nm), 1)        # Home is known here already
            self.assertEqual(list(out.glob("*.xml")), [])          # gone: they hold passwords
            taken = (nm / "Cafe-Monet.nmconnection").read_text()
            for line in ("ssid=Cafe Monet", "key-mgmt=wpa-psk", "psk=croissant42", "type=wifi"):
                self.assertIn(line, taken)
            if hasattr(os, "geteuid"):
                self.assertEqual((nm / "Cafe-Monet.nmconnection").stat().st_mode & 0o777, 0o600)
            # Monet's networks for Windows, each once (again when its password changes), made as
            # Monet Setup makes them for a Windows it installs.
            self.assertTrue(callable(d.prepare_windows().wifi_profiles))
            given = Path(tmp) / "given.json"
            profiles = ["<WLANProfile>a</WLANProfile>", "<WLANProfile>b</WLANProfile>"]
            # Only into the folder Bridge made, for administrators only: none made here.
            self.assertEqual(d.give_wifi(root, profiles, given), 0)
            self.assertFalse((root / "ProgramData/Monet/wifi").exists())
            (root / "ProgramData/Monet/wifi").mkdir()
            self.assertEqual(d.give_wifi(root, profiles, given), 2)
            self.assertEqual(len(list((root / "ProgramData/Monet/wifi").glob("monet-*.xml"))), 2)
            self.assertEqual(d.give_wifi(root, profiles, given), 0)
            self.assertEqual(d.give_wifi(root, profiles + ["<WLANProfile>c</WLANProfile>"], given), 1)
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        self.assertIn('"wlan", "export", "profile", "key=clear"', bridge)
        self.assertIn('"*S-1-5-32-544:(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"', bridge)
        back = bridge[bridge.index("fn go_back("):bridge.index("/// Hands the restart to")]
        self.assertLess(back.index("export_wifi();"), back.index("boot::set_boot_next"))
        add = bridge[bridge.index("fn add_wifi("):bridge.index("fn export_wifi(")]
        self.assertLess(add.index('"/inheritance:r"'), add.index("fs::read_dir(&dir)"))

    def test_windows_clock_follows_monets_time_zone(self):
        prepare = (ROOT / "linux/libexec/monet-prepare-windows").read_text(encoding="utf-8")
        main = prepare[prepare.index("def main():"):]
        # Asked for on a trip, as the person's helper: before the checks the installer needs.
        self.assertLess(main.index('"--windows-zone" in args'), main.index("os.geteuid() != 0"))
        monet = (ROOT / "crates/monet/src/main.rs").read_text(encoding="utf-8")
        self.assertIn('.arg("--windows-zone")', monet)
        self.assertIn(".map(|r| r.with_zone(zone))", monet)
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        self.assertIn('win::run_hidden("tzutil", &["/s", zone])', bridge)

    def test_settings_shows_the_folder_in_its_own_card(self):
        q = self.quick
        with tempfile_dir() as tmp:
            q.SHARED, q.SHARED_STATE = Path(tmp) / "Windows games", Path(tmp) / "windows-drive.json"
            (q.SHARED / "steamapps").mkdir(parents=True)
            q.SHARED_STATE.write_text('{"state": "open", "path": "/run/media/Windows games", "owner": "ann"}')
            libraries = [{"name": "Steam", "shared": False, "games": 4, "size": 5, "free": 6},
                         {"name": "Windows games", "shared": True, "games": 2, "size": 9, "free": 1}]
            info = q.shared_info(libraries)
            self.assertEqual((info["state"], info["steam"], info["mine"], info["games"], info["size"]), ("open", True, True, 2, 9))
            self.assertFalse(q.shared_info(libraries[:1])["steam"])
            q.SHARED_STATE.write_text('{"state": "asleep"}')
            self.assertEqual(q.shared_info(libraries), {"state": "asleep", "unlocked": False, "handover": False})
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('sheet.ask("steam-share now", out => {', settings)
        self.assertIn('i18n("Windows didn\'t shut down fully, so its drive isn\'t open to Monet this time.', settings)

    def test_windows_keeps_shutting_down_fully(self):
        # Fast Startup left Windows' drive asleep, closed to Monet: installing Monet switches it
        # off, and Bridge switches it off again at each sign-in when a Windows update put it back
        # (the clock in UTC too).
        install = (ROOT / "windows/Install-Monet.ps1").read_text(encoding="utf-8")
        self.assertIn("-Name HiberbootEnabled -Value 0 -Type DWord", install)
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        self.assertIn("    repair_boot_order(&mut efi, &state);\n    keep_install_settings();\n", bridge)
        for setting in ('"HiberbootEnabled", 0)', '"RealTimeIsUniversal", 1)'):
            self.assertIn(setting, bridge)
        self.assertIn('format!("HKLM\\\\{key}"), "/v", value, "/t", "REG_DWORD"', bridge)
        self.assertIn("pub fn reg_machine_dword(key: &str, value: &str) -> Option<u32> {",
                      (ROOT / "crates/monet-bridge/src/win.rs").read_text(encoding="utf-8"))

    def test_bridge_adds_the_folder_to_windows_steam(self):
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        self.assertIn('let folder = PathBuf::from(format!("{drive}\\\\Games"));', bridge)
        pending = bridge[bridge.index("fn launch_pending()"):bridge.index("/// How long to wait for Steam")]
        # As the person, before Steam starts for the game.
        self.assertLess(pending.index("share_with_steam();"), pending.index("launchers::open(key"))
        self.assertIn('.arg("-shutdown")', bridge)
        self.assertIn(".chain(shared_games())", bridge)

    @unittest.skipUnless(hasattr(os, "geteuid"), "Unix files")
    def test_what_windows_saved_moves_into_monets_folders(self):
        d = self.drive
        with tempfile_dir() as tmp:
            root, home = Path(tmp) / "drive", Path(tmp) / "home"
            ann = root / "Users/Ann"
            (ann / "Pictures/Screenshots").mkdir(parents=True)
            (ann / "Videos/Captures").mkdir(parents=True)
            (ann / "NTUSER.DAT").write_bytes(b"regf")
            (root / "Users/Public/Pictures/Screenshots").mkdir(parents=True)
            (root / "Users/Public/Pictures/Screenshots/shared.png").write_bytes(b"x")
            (ann / "Pictures/Screenshots/Screenshot 1.png").write_bytes(b"one")
            (ann / "Pictures/Screenshots/desktop.ini").write_text("[x]")
            (ann / "Videos/Captures/Apex Legends 2026-10-25.mp4").write_bytes(b"clip" * 1000)
            (home / ".config").mkdir(parents=True)
            (home / ".config/user-dirs.dirs").write_text('XDG_PICTURES_DIR="$HOME/Bilder"\nXDG_VIDEOS_DIR="$HOME/Videos"\n')
            (home / "Bilder/Screenshots").mkdir(parents=True)
            (home / "Bilder/Screenshots/Screenshot 1.png").write_bytes(b"older")  # a different one, same name
            (ann / "Pictures/Screenshots/Screenshot 2.png").write_bytes(b"two")
            (home / "Bilder/Screenshots/Screenshot 2.png").write_bytes(b"TWO")  # same size, not the same
            (ann / "Pictures/Screenshots/Screenshot 3.png").write_bytes(b"three")
            (home / "Bilder/Screenshots/Screenshot 3.png").write_bytes(b"three")  # brought before
            shots = root / "Program Files (x86)/Steam/userdata/123/760/remote/1245620/screenshots"
            (shots / "thumbnails").mkdir(parents=True)
            (shots / "20261025120000_1.jpg").write_bytes(b"steam shot")
            (shots / "thumbnails/20261025120000_1.jpg").write_bytes(b"small")
            (home / ".local/share/Steam/userdata/123").mkdir(parents=True)    # Ann's Steam account here
            # Someone else's: their own Windows account and Steam account stay theirs.
            bob = root / "Users/Bob"
            (bob / "Pictures/Screenshots").mkdir(parents=True)
            (bob / "NTUSER.DAT").write_bytes(b"regf")
            (bob / "Pictures/Screenshots/Bob's.png").write_bytes(b"bob")
            theirs = root / "Program Files (x86)/Steam/userdata/456/760/remote/1245620/screenshots"
            theirs.mkdir(parents=True)
            (theirs / "20261025130000_1.jpg").write_bytes(b"not ann's")
            seen = Path(tmp) / "seen.json"
            person = ("ann", os.getuid(), os.getgid(), home)
            self.assertEqual(d.bring(root, person, seen), {"pictures": 4, "videos": 1})
            self.assertTrue((bob / "Pictures/Screenshots/Bob's.png").exists())
            self.assertFalse((home / "Bilder/Screenshots/Bob's.png").exists())
            self.assertFalse((home / "Bilder/Screenshots/20261025130000_1.jpg").exists())
            self.assertEqual(d.own_windows(root, "ANN"), [ann])
            self.assertEqual(d.own_windows(root, "carl"), [])                    # two accounts, neither theirs
            # Steam's are copied, not moved (Steam in Windows lists them), and only once.
            self.assertEqual((home / "Bilder/Screenshots/20261025120000_1.jpg").read_bytes(), b"steam shot")
            self.assertTrue((shots / "20261025120000_1.jpg").exists())
            (home / "Bilder/Screenshots/20261025120000_1.jpg").unlink()
            self.assertEqual((home / "Bilder/Screenshots/Screenshot 1 (2).png").read_bytes(), b"one")
            self.assertEqual((home / "Bilder/Screenshots/Screenshot 1.png").read_bytes(), b"older")
            self.assertEqual((home / "Bilder/Screenshots/Screenshot 2 (2).png").read_bytes(), b"two")
            self.assertFalse((home / "Bilder/Screenshots/Screenshot 3 (2).png").exists())
            self.assertEqual((home / "Videos/Apex Legends 2026-10-25.mp4").stat().st_size, 4000)
            self.assertFalse((ann / "Pictures/Screenshots/Screenshot 1.png").exists())
            self.assertTrue((ann / "Pictures/Screenshots/desktop.ini").exists())   # not a picture
            self.assertTrue((root / "Users/Public/Pictures/Screenshots/shared.png").exists())  # not a person
            self.assertEqual(list((home / "Bilder/Screenshots").glob(".*.part")), [])
            # Nothing new: nothing brought (not even the Steam screenshot deleted here since).
            self.assertEqual(d.bring(root, person, seen), {"pictures": 0, "videos": 0})


class YourAppsAgainAfterWindows(unittest.TestCase):
    """After 0.9.3: the apps open before a trip to Windows start again when Monet's back."""

    def test_apps_are_known_by_plasmas_units(self):
        q = quick_helper()
        for unit, app in (("app-org.kde.dolphin@a1b2c3.service", "org.kde.dolphin.desktop"),
                          ("app-flatpak-app.zen_browser.zen-23456.scope", "app.zen_browser.zen.desktop"),
                          ("app-com.discordapp.Discord-1234.scope", "com.discordapp.Discord.desktop"),
                          ("app-org.kde.kdeconnect\\x2dindicator@9.service", "org.kde.kdeconnect-indicator.desktop"),
                          ("app-gnome-org.gnome.Nautilus-77.scope", "org.gnome.Nautilus.desktop")):
            self.assertEqual(q.app_from_unit(unit), app, unit)
        for unit in ("app-org.kde.kdeconnect.daemon@autostart.service", "plasma-plasmashell.service",
                     "app-x.slice", "app-a;b@1.service"):
            self.assertIsNone(q.app_from_unit(unit), unit)

    def test_open_apps_are_remembered_and_start_again_once(self):
        from unittest import mock
        q = quick_helper()
        entries = {"org.kde.dolphin.desktop": {"Type": "Application"}, "steam.desktop": {"Type": "Application"},
                   "app.zen_browser.zen.desktop": {"Type": "Application"},
                   "org.kde.kdeconnect.daemon.desktop": {"Type": "Application", "NoDisplay": "true"},
                   "com.discordapp.Discord.desktop": {"Type": "Application"}}
        with tempfile_dir() as tmp:
            q.TRIP_APPS, q.TRIP_APPS_OFF = Path(tmp) / "state/monet/trip-apps.json", Path(tmp) / "trip-apps-off"
            launched = []
            with mock.patch.object(q, "entry_by_id", entries.get), \
                    mock.patch.object(q, "starts_anyway", lambda app: app == "com.discordapp.Discord.desktop"), \
                    mock.patch.object(q, "launch", launched.append), mock.patch.object(q.time, "sleep", lambda s: None):
                kept = q.remember_apps(["org.kde.dolphin.desktop", "steam.desktop", "app.zen_browser.zen.desktop",
                                        "org.kde.kdeconnect.daemon.desktop", "com.discordapp.Discord.desktop", "gone.desktop"])
                self.assertEqual(kept, ["org.kde.dolphin.desktop", "app.zen_browser.zen.desktop"])
                with mock.patch.object(q, "running_apps", lambda: ["app.zen_browser.zen.desktop"]):
                    self.assertEqual(q.trip_apps_again(), ["org.kde.dolphin.desktop"])
                    self.assertEqual(launched, ["org.kde.dolphin.desktop"])
                    self.assertFalse(q.TRIP_APPS.exists())          # once
                    self.assertEqual(q.trip_apps_again(), [])
                    # Too long ago (a trip that switched the PC off for days): nothing.
                    q.TRIP_APPS.write_text(json.dumps({"time": 1, "apps": ["org.kde.dolphin.desktop"]}))
                    self.assertEqual(q.trip_apps_again(), [])
                    # Off in Settings: nothing remembered.
                    q.set_trip_apps(False)
                    self.assertEqual(q.remember_apps(["org.kde.dolphin.desktop"]), [])
                    self.assertEqual(q.ready_state()["apps"], False)
                    q.set_trip_apps(True)
                    self.assertEqual(q.ready_state()["apps"], True)

    def test_monet_remembers_them_before_the_restart(self):
        main = (ROOT / "crates/monet/src/main.rs").read_text(encoding="utf-8")
        switch = main[main.index("fn switch("):main.index("fn doctor(")]
        self.assertIn('"--unit=monet-switch"', switch)
        self.assertIn('dir.join("monet-leave")', switch)
        self.assertNotIn("elevate(&args)", switch)
        session = (ROOT / "linux/libexec/monet-session").read_text()
        self.assertIn('"$LIBEXECDIR/monet-quick" trip-apps-again', session)
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('sheet.ask("trip-apps " + (on ? "on" : "off")', settings)


class YourPhotoPainted(unittest.TestCase):
    """After 0.9.3: a photo of yours painted in Monet's hand, in The Hours' four lights (monet-paint)."""

    def test_a_photo_becomes_four_lights(self):
        try:
            import numpy as np
            from PIL import Image
        except ImportError as e:
            self.skipTest(f"no NumPy or Pillow ({e})")
        paint = libexec_helper("monet-paint")
        with tempfile_dir() as tmp:
            # A made-up photo: sky over a field, a dark tree, a bright window.
            y, x = np.mgrid[0:300, 0:400]
            img = np.zeros((300, 400, 3), np.float32)
            img[...] = np.where((y < 140)[..., None], [0.45, 0.62, 0.86], [0.32, 0.5, 0.22])
            img[(x - 120) ** 2 + (y - 120) ** 2 < 40 ** 2] = [0.1, 0.22, 0.08]
            img[200:230, 280:320] = [1.0, 0.85, 0.4]
            Image.fromarray((img * 255).astype(np.uint8)).save(Path(tmp) / "photo.png")
            out = Path(tmp) / "painted"
            self.assertEqual(paint.main([str(Path(tmp) / "photo.png"), str(out), "640x360"]), 0)
            lights = {}
            for n in ("dawn", "day", "dusk", "night"):
                with Image.open(out / f"{n}.jpg") as im:
                    lights[n] = im.copy()
            self.assertEqual({im.size for im in lights.values()}, {(640, 360)})
            with Image.open(out / "preview.png") as im:
                self.assertEqual(im.size, (480, 236))
            self.assertEqual((out / "progress").read_text().strip(), "100")
            mean = {n: np.asarray(im, np.float32).mean() for n, im in lights.items()}
            self.assertLess(mean["night"], mean["dawn"] * 0.75)             # night is dark
            day = np.asarray(lights["day"], np.float32)
            self.assertGreater(day[:100, :, 2].mean(), day[:100, :, 0].mean())  # the sky stays blue at midday
            # Painted, not copied: the sky has strokes in it, not one flat color.
            self.assertGreater(day[20:120, 300:600].std(), 2)
            # Not a picture: says so, paints nothing.
            (Path(tmp) / "not.jpg").write_text("hello")
            self.assertEqual(paint.main([str(Path(tmp) / "not.jpg"), str(Path(tmp) / "none")]), 3)
            self.assertFalse((Path(tmp) / "none/day.jpg").exists())

    def test_settings_paints_it_in_the_background_and_the_wall_shows_it(self):
        q = quick_helper()
        self.assertIn("photo", q.SERIES)
        from unittest import mock
        with tempfile_dir() as tmp:
            q.PAINTINGS = Path(tmp) / "paintings"
            started = []
            with mock.patch.object(q, "ok", lambda *a, **k: started.append(a) or True), mock.patch.object(q, "run", lambda *a, **k: ""):
                self.assertFalse(q.paint_photo(str(Path(tmp) / "missing.jpg")))
                (Path(tmp) / "notes.txt").write_text("x")
                self.assertFalse(q.paint_photo(str(Path(tmp) / "notes.txt")))
                (Path(tmp) / "Summer 2026.JPG").write_bytes(b"jpeg")
                self.assertTrue(q.paint_photo(str(Path(tmp) / "Summer 2026.JPG")))
                self.assertEqual(started[-1][-2:], ("paint-run", (Path(tmp) / "Summer 2026.JPG").as_posix().encode().hex()))
                self.assertEqual(q.paint_state()["state"], "")
                (q.PAINTINGS / "photo").mkdir(parents=True)
                for light in ("dawn", "day", "dusk", "night"):
                    (q.PAINTINGS / f"photo/{light}.jpg").write_bytes(b"x")
                (q.PAINTINGS / "photo/preview.png").write_bytes(b"x")
                state = q.paint_state()
                self.assertEqual(state["state"], "ready")
                self.assertRegex(state["preview"], r"^file:///.*/photo/preview\.png\?\d+$")
        light = (ROOT / "linux/libexec/monet-light").read_text()
        self.assertIn('photo) if [ -f "$PHOTO/night.jpg" ]; then echo photo; else echo hours; fi ;;', light)
        self.assertIn("d.writeConfig('PhotoFolder', 'file://$PHOTO/');", light)
        wall = (PLASMA / "wallpapers/org.monet.hours/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn('readonly property string folder: series === "photo" ? photo :', wall)
        self.assertIn('<entry name="PhotoFolder" type="String">',
                      (PLASMA / "wallpapers/org.monet.hours/contents/config/main.xml").read_text(encoding="utf-8"))
        self.assertIn(" python3-numpy python3-pillow ", (ROOT / "image/Containerfile").read_text())


def windows_shortcut(target, unicode=True, id_list=b"\x12\x00" + b"\x1f" * 16 + b"\0\0"):
    """A Windows shortcut (.lnk) to target, as MS-SHLLINK lays one out: the header, an item ID
    list, and the LinkInfo with the local path (ANSI, and Unicode when asked)."""
    import struct
    header = bytearray(0x4C)
    header[0:4] = struct.pack("<I", 0x4C)
    header[0x14:0x18] = struct.pack("<I", 0x01 | 0x02 | 0x80)
    volume = struct.pack("<IIII", 0x10, 3, 0, 0x10)
    ansi, wide = target.encode("cp1252", "replace") + b"\0", target.encode("utf-16-le") + b"\0\0"
    size = 0x24 if unicode else 0x1C
    base = size + len(volume)
    suffix = base + len(ansi)
    fields = [1, size, base, 0, suffix] + ([suffix + 1, suffix + 1 + len(wide)] if unicode else [])
    body = struct.pack(f"<{len(fields)}I", *fields) + volume + ansi + b"\0" + (wide + b"\0\0" if unicode else b"")
    info = struct.pack("<II", 8 + len(body), size) + body
    return bytes(header) + id_list + info


class BitLockerWindows(unittest.TestCase):
    """After 0.9.3 (the user's backlog, item 7): Windows encrypted with BitLocker (device
    encryption, on by default on many laptops) opens with its recovery key, typed once in
    Settings and kept sealed, so games, files and Wi-Fi work in both as on any Windows."""

    KEY = "123453-246906-370359-493812-617265-000011-111111-222222"

    def setUp(self):
        self.drive = libexec_helper("monet-windows-drive")

    @unittest.skipUnless(shutil.which("openssl") and hasattr(os, "geteuid"), "openssl")
    def test_windows_hands_its_key_over_through_monets_lock(self):
        # Encrypted after Monet put Bridge in: Bridge locks the recovery key with Monet's lock and
        # leaves it on the EFI partition; Monet opens it, tries it, keeps it, and takes it away.
        from unittest import mock
        d = self.drive
        code, pem = d.feed(["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:3072"], b"")
        self.assertEqual(code, 0)
        lock = d.public_lock(pem)
        self.assertRegex(lock, r"^<RSAKeyValue><Modulus>[A-Za-z0-9+/=]{512}</Modulus><Exponent>AQAB</Exponent></RSAKeyValue>$")
        with tempfile_dir() as tmp, mock.patch.object(d, "handover_key", lambda keys=None: pem):
            root, keys = Path(tmp) / "drive", Path(tmp) / "keys"
            (root / "ProgramData/Monet").mkdir(parents=True)
            keys.mkdir()
            self.assertFalse(d.give_lock(root, keys))                        # Bridge hasn't made its folder
            self.assertFalse((root / "ProgramData/Monet/monet-key.xml").exists())
            (root / "ProgramData/Monet/from-monet").mkdir()
            self.assertTrue(d.give_lock(root, keys))
            self.assertEqual((root / "ProgramData/Monet/from-monet/monet-key.xml").read_text().strip(), lock)
            self.assertTrue((keys / "lock-given").exists())                  # Settings: start Windows once

            # What Bridge leaves: the key locked with the lock (RSA-OAEP, as .NET's Encrypt(data, true)).
            public = Path(tmp) / "public.pem"
            self.assertEqual(d.feed(["openssl", "pkey", "-pubout", "-out", public], pem)[0], 0)
            code, sealed = d.feed(["openssl", "pkeyutl", "-encrypt", "-pubin", "-inkey", public, "-pkeyopt",
                                   "rsa_padding_mode:oaep"], self.KEY.encode())
            esp = Path(tmp) / "esp"
            (esp / "EFI/Monet").mkdir(parents=True)
            handed = esp / "EFI/Monet/bitlocker.json"
            handed.write_text(json.dumps({"keys": [{"id": "{x}", "key": "not base64!"},
                                                   {"id": "{y}", "key": base64.b64encode(b"junk").decode()},
                                                   {"id": "{z}", "key": base64.b64encode(sealed).decode()}]}))
            tried = []
            with mock.patch.object(d, "unlock", lambda text, volumes=None: tried.append(text) or "open"):
                self.assertEqual(d.take_handed([("/dev/sda3", "abc")], roots=[(esp, False)]), 1)
            self.assertEqual(tried, [self.KEY])
            self.assertFalse(handed.exists())                                 # taken off the EFI partition
            with mock.patch.object(d, "unlock", lambda *a: self.fail("nothing to try")):
                self.assertEqual(d.take_handed([("/dev/sda3", "abc")], roots=[(esp, False)]), 0)
        script = (ROOT / "linux/libexec/monet-windows-drive").read_text(encoding="utf-8")
        self.assertIn("    if volumes:\n        try:\n            take_handed(volumes)\n", script)
        self.assertIn("    give_lock(DRIVE)\n", script)
        self.assertIn('"-inkey", f"/dev/fd/{read}"', script)                 # never a file or a command line
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        self.assertIn("std::thread::spawn(hand_over_bitlocker_key);", bridge)
        self.assertIn('const HANDED: &str = "EFI/Monet/bitlocker.json";', bridge)
        self.assertIn('HANDED = "EFI/Monet/bitlocker.json"', script)
        self.assertIn(".ConversionStatus -ne 1", bridge)                     # fully encrypted only
        self.assertIn('handover=(BITLOCKER_KEYS / "lock-given").exists()', script)
        self.assertIn('"handover": bool(shared_state().get("handover"))',
                      (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8"))
        self.assertIn('sharedCard.s.state === "bitlocker" && sharedCard.s.handover === true',
                      SETTINGS_QML.read_text(encoding="utf-8"))

    def test_a_recovery_key_however_it_was_typed(self):
        d = self.drive
        self.assertEqual(d.recovery_key(self.KEY), self.KEY)
        self.assertEqual(d.recovery_key(" 123453 246906370359-493812 617265000011 111111-222222\n"), self.KEY)
        for wrong in ("", "123", self.KEY[:-1], self.KEY.replace("222222", "222223"),  # each group a multiple of 11
                      self.KEY.replace("000011", "720907"), self.KEY.replace("1", "a")):  # and below 720896
            self.assertIsNone(d.recovery_key(wrong), wrong)

    def test_bitlocker_drives_are_found_and_opened_with_the_key_on_stdin(self):
        from unittest import mock
        d = self.drive
        lsblk = {"blockdevices": [{"path": "/dev/nvme0n1", "fstype": None, "uuid": None, "children": [
            {"path": "/dev/nvme0n1p1", "fstype": "vfat", "uuid": "AB12-CD34"},
            {"path": "/dev/nvme0n1p3", "fstype": "BitLocker", "uuid": "8C1F3A55-21D4-4E8A-9B0B-5C7E2D0A1F33"},
            {"path": "/dev/nvme0n1p4", "fstype": "crypto_LUKS", "uuid": "1234abcd-0000-0000-0000-000000000000"}]}]}
        found = d.bitlocker_volumes(lsblk)
        self.assertEqual(found, [("/dev/nvme0n1p3", "8c1f3a55-21d4-4e8a-9b0b-5c7e2d0a1f33")])
        self.assertEqual(d.mapper_name(found[0][1]), "monet-windows-8c1f3a5521d4")
        fed = []
        with mock.patch.object(d, "feed", lambda args, data, timeout=60: (fed.append((args, data)), (0, b""))[1]):
            self.assertTrue(d.open_bitlocker("/dev/nvme0n1p3", found[0][1], self.KEY))
        args, data = fed[0]
        self.assertEqual(args, ["cryptsetup", "open", "--type", "bitlk", "--key-file=-", "/dev/nvme0n1p3", "monet-windows-8c1f3a5521d4"])
        self.assertEqual(data, self.KEY.encode())
        self.assertNotIn(self.KEY, " ".join(map(str, args)))  # never on a command line

    def test_settings_key_opens_the_drive_it_fits_and_is_kept(self):
        from unittest import mock
        d = self.drive
        volumes = [("/dev/sda3", "aaaa-1111"), ("/dev/sdb2", "bbbb-2222")]
        sealed = []
        with mock.patch.object(d, "opens", lambda device, key: device == "/dev/sdb2"), \
                mock.patch.object(d, "open_bitlocker", lambda *a: True), \
                mock.patch.object(d, "seal_key", lambda uuid, key: sealed.append((uuid, key)) or True):
            self.assertEqual(d.unlock("not a key", volumes), "bad-key")
            self.assertEqual(d.unlock(self.KEY, volumes[:1]), "wrong-key")
            self.assertEqual(d.unlock(self.KEY.replace("-", " "), volumes), "open")
        self.assertEqual(sealed, [("bbbb-2222", self.KEY)])
        # At every start, before Windows' setup and the shared folders look for Windows.
        with mock.patch.object(d, "sealed_key", lambda uuid: self.KEY if uuid == "bbbb-2222" else None), \
                mock.patch.object(d, "open_bitlocker", lambda *a: True), \
                mock.patch.object(d, "esp_roots", lambda: []):
            self.assertEqual(d.unlock_saved(volumes), 1)
        script = (ROOT / "linux/libexec/monet-windows-drive").read_text(encoding="utf-8")
        self.assertIn("    unlocked = unlock_saved()\n    device, why = find_windows(ntfs_volumes())", script)
        self.assertIn('["systemd-creds", "encrypt", f"--name={CRED_NAME}", "-", keys / f"{uuid}.cred"]', script)
        self.assertIn('BITLOCKER_KEYS = Path("/var/lib/monet/bitlocker")', script)
        setup = (ROOT / "linux/systemd/monet-windows-setup.service").read_text(encoding="utf-8")
        self.assertIn("ExecStartPre=-@LIBEXECDIR@/monet-windows-drive unlock-saved\nExecStart=@BINDIR@/monet helper stage-windows", setup)
        install = (ROOT / "linux/install.sh").read_text(encoding="utf-8")
        self.assertIn('\\"$LIBEXECDIR/monet-windows-drive\\"', install)  # pkexec without a password, as Settings' other helpers

    def test_settings_asks_for_the_key_and_sends_it_sealed(self):
        from unittest import mock
        q = quick_helper()
        ran = []

        class Done:
            stdout = '{"result": "open", "state": "no-bridge"}\n'

        def fake(command, **kw):
            ran.append((command, kw.get("input")))
            return Done()
        pad = bytes(range(64))
        sealed = bytes(a ^ b for a, b in zip(self.KEY.encode(), pad)).hex()
        with mock.patch.object(q, "take_pad", lambda: pad), mock.patch.object(q.subprocess, "run", fake):
            self.assertEqual(q.unlock_windows(sealed), {"result": "open", "state": "no-bridge"})
        self.assertEqual(ran, [(["pkexec", f"{q.LIBEXECDIR}/monet-windows-drive", "unlock"], self.KEY)])
        settings = SETTINGS_QML.read_text(encoding="utf-8")
        for piece in ('const sealed = sheet.seal(key.trim(), pad.trim())', 'sheet.ask("bitlocker " + sealed, out => {',
                      'onClicked: Qt.openUrlExternally("https://aka.ms/myrecoverykey")',
                      '|| (s.state === "no-bridge" && s.unlocked === true)', 'visible: sharedCard.s.state === "bitlocker"'):
            self.assertIn(piece, settings)
        main = (ROOT / "crates/monet/src/main.rs").read_text(encoding="utf-8")
        self.assertIn("Type its recovery key in Settings › Games & Controllers", main)


class BookmarksFromWindows(unittest.TestCase):
    """After 0.9.3 (the user's backlog, item 8): what Edge, Chrome and Firefox keep as bookmarks
    in Windows goes to Zen, and Settings says how passwords follow."""

    def setUp(self):
        self.q = quick_helper()
        self.drive = libexec_helper("monet-windows-drive")

    @unittest.skipUnless(hasattr(os, "geteuid"), "Unix files")
    def test_each_browsers_bookmarks_come_from_your_own_windows_account(self):
        import sqlite3
        d = self.drive
        with tempfile_dir() as tmp:
            root, home = Path(tmp) / "drive", Path(tmp) / "home"
            ann = root / "Users/Ann"
            edge = ann / "AppData/Local/Microsoft/Edge/User Data/Default"
            edge.mkdir(parents=True)
            (ann / "NTUSER.DAT").write_bytes(b"regf")
            (edge / "Bookmarks").write_text(json.dumps({"roots": {
                "bookmark_bar": {"children": [
                    {"type": "url", "name": "Mail", "url": "https://mail.example/", "date_added": "13370000000000000"},
                    {"type": "url", "name": "Settings", "url": "edge://settings"},
                    {"type": "folder", "name": "Work", "children": [
                        {"type": "url", "name": "Wiki <team>", "url": "https://wiki.example/?a=1&b=2"}]},
                    {"type": "folder", "name": "Empty", "children": []}]},
                "other": {"children": [{"type": "url", "name": "Recipes", "url": "http://food.example/"}]}}}))
            fox = ann / "AppData/Roaming/Mozilla/Firefox/Profiles/abc.default-release"
            fox.mkdir(parents=True)
            db = sqlite3.connect(fox / "places.sqlite")
            db.executescript(
                "CREATE TABLE moz_places (id INTEGER PRIMARY KEY, url TEXT);"
                "CREATE TABLE moz_bookmarks (id INTEGER PRIMARY KEY, type INT, fk INT, parent INT, position INT,"
                " title TEXT, dateAdded INT, guid TEXT);"
                "INSERT INTO moz_places VALUES (1, 'https://news.example/'), (2, 'place:sort=8');"
                "INSERT INTO moz_bookmarks VALUES (1, 2, NULL, 0, 0, '', 0, 'root________'),"
                " (2, 2, NULL, 1, 0, 'menu', 0, 'menu________'), (3, 2, NULL, 1, 1, 'toolbar', 0, 'toolbar_____'),"
                " (4, 1, 1, 3, 0, 'News', 1700000000000000, 'aaaaaaaaaaaa'), (5, 1, 2, 2, 0, 'Most visited', 0, 'bbbbbbbbbbbb');")
            db.commit()
            db.close()
            # Someone else's Windows account stays theirs.
            bob = root / "Users/Bob/AppData/Local/Google/Chrome/User Data/Default"
            bob.mkdir(parents=True)
            (root / "Users/Bob/NTUSER.DAT").write_bytes(b"regf")
            (bob / "Bookmarks").write_text(json.dumps({"roots": {"bookmark_bar": {"children": [
                {"type": "url", "name": "Bob's", "url": "https://bob.example/"}]}}}))
            self.assertEqual([name for name, _, _ in d.windows_bookmarks(root, "ann")], ["Edge", "Firefox"])  # most first
            person = ("ann", os.getuid(), os.getgid(), home)
            self.assertEqual(d.bring_bookmarks(root, person), 4)
            html = (home / d.BOOKMARKS_HTML).read_text(encoding="utf-8")
            for piece in ("<DT><H3>Edge</H3>", '<A HREF="https://mail.example/" ADD_DATE="1725526400">Mail</A>',
                          '<A HREF="https://wiki.example/?a=1&amp;b=2"', "Wiki &lt;team&gt;", "<DT><H3>Work</H3>",
                          '<A HREF="https://news.example/" ADD_DATE="1700000000">News</A>'):
                self.assertIn(piece, html)
            for gone in ("edge://", "place:", "Empty", "bob.example"):
                self.assertNotIn(gone, html)
            said = json.loads((home / d.BOOKMARKS_JSON).read_text())
            self.assertEqual((said["browsers"], said["count"]), (["Edge", "Firefox"], 4))
            self.assertEqual(oct((home / d.BOOKMARKS_HTML).stat().st_mode & 0o777), "0o600")
        # One browser: its bar is Zen's toolbar, the rest Zen's bookmarks.
        one = d.bookmarks_html([("Edge", [{"title": "Mail", "url": "https://mail.example/", "added": 0}],
                                 [{"title": "Recipes", "url": "http://food.example/", "added": 0}])])
        self.assertIn('<DT><H3 PERSONAL_TOOLBAR_FOLDER="true">Bookmarks Toolbar</H3>', one)
        self.assertLess(one.index("Mail"), one.index("</DL><p>"))
        self.assertTrue(one.startswith("<!DOCTYPE NETSCAPE-Bookmark-file-1>"))
        script = (ROOT / "linux/libexec/monet-windows-drive").read_text(encoding="utf-8")
        self.assertIn("bookmarks = bring_bookmarks(DRIVE, person)", script)

    def test_zen_takes_them_in_once_and_never_touches_a_zen_in_use(self):
        from unittest import mock
        q = self.q
        with tempfile_dir() as tmp:
            source = Path(tmp) / "windows-bookmarks.html"
            source.write_text("<DL>")
            fresh, used = Path(tmp) / "fresh", Path(tmp) / "used"
            fresh.mkdir()
            used.mkdir()
            (used / "places.sqlite").write_bytes(b"x")
            self.assertTrue(q.bookmarks_for_zen(fresh, source))
            self.assertEqual((fresh / "bookmarks.html").read_text(), "<DL>")
            self.assertFalse(q.bookmarks_for_zen(used, source))
            self.assertFalse((used / "bookmarks.html").exists())
            # Older entry points open the review before any export is written.
            with mock.patch.object(q, "open_settings") as open_settings:
                out = q.bookmarks_to_zen()
            self.assertTrue(out["ok"])
            open_settings.assert_called_once_with("apps#bookmarks")
            # What Settings is told.
            (Path(tmp) / "said.json").write_text(json.dumps({"browsers": ["Edge"], "count": 12}))
            with mock.patch.object(q, "WINDOWS_BOOKMARKS", source), \
                    mock.patch.object(q, "WINDOWS_BOOKMARKS_SAID", Path(tmp) / "said.json"), \
                    mock.patch.object(q, "zen_here", return_value=False), mock.patch.object(q, "FILES", Path(tmp) / "none"), \
                    mock.patch.object(q, "bookmarks_helper") as helper:
                helper.return_value.recent.return_value = []
                self.assertEqual(q.windows_browsers(), {"count": 12, "browsers": ["Edge"], "zen": "none", "shared": "", "profiles": [], "imports": []})
        script = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn("            write_if_changed(prefs, with_part(text, ZEN_PREFS).encode())\n            bookmarks_for_zen(profile)", script)
        path = (ROOT / "linux/systemd/user/monet-zen.path").read_text(encoding="utf-8")
        self.assertIn("PathChanged=%h/.local/share/monet/windows-bookmarks.html", path)

    def test_settings_says_what_came_and_how_passwords_follow(self):
        settings = SETTINGS_QML.read_text(encoding="utf-8")
        for piece in ('ask("windows-browsers", out => sheet.browserInfo = sheet.json(out, sheet.browserInfo))',
                      'title: i18n("Destination profile")', 'bookmarkImport.act("prepare")',
                      'title: i18n("Passwords")', 'bookmarkImport.act("verify")',
                      'bookmarkImport.preparedImport.file || ""'):
            self.assertIn(piece, settings)


class DownloadedOnce(unittest.TestCase):
    """After 0.9.3: a folder for files on both sides, launchers fetched in Monet, and
    Battle.net's and Ubisoft's games installed once for both."""

    def setUp(self):
        self.q = quick_helper()
        self.drive = libexec_helper("monet-windows-drive")

    def test_monet_knows_which_launchers_windows_has(self):
        d = self.drive
        with tempfile_dir() as tmp:
            root = Path(tmp) / "drive"
            # Windows' drive in any case (one folder of each name, as NTFS keeps them).
            (root / "PROGRAM FILES (X86)/battle.net").mkdir(parents=True)
            (root / "PROGRAM FILES (X86)/battle.net/BATTLE.NET.EXE").write_bytes(b"MZ")
            (root / "PROGRAM FILES (X86)/Ubisoft/Ubisoft Game Launcher").mkdir(parents=True)
            self.assertEqual(d.windows_launchers(root), ["battlenet"])      # Ubisoft's folder, no program
        script = (ROOT / "linux/libexec/monet-windows-drive").read_text(encoding="utf-8")
        self.assertIn('FILES = Path("/run/media/Shared with Windows")', script)
        self.assertIn('write_state("open", path=str(SHARED), owner=person[0], files=str(FILES) if files else ""', script)
        share = script[script.index("def share_files("):script.index("def windows_launchers(")]
        self.assertLess(share.index("no_links(folder, root)"), share.index('run("mount", "--bind", folder, FILES)'))

    def test_installers_are_fetched_in_monet_and_let_go_after(self):
        q = self.q
        with tempfile_dir() as tmp:
            shared = Path(tmp) / "Windows games"
            (shared / ".monet/epic").mkdir(parents=True)
            (shared / ".monet/epic/Fortnite.json").write_text("{}")
            (shared / "Call of Duty").mkdir()
            (shared / "Call of Duty/.build.info").write_text("Product!STRING:0\nauks\n")
            self.assertEqual(q.needed_launchers(shared), {"epic", "battlenet"})
            folder, fetched = shared / ".monet/installers", []

            def fetch(url, target):
                fetched.append(url)
                target.write_bytes(b"installer")
                return True
            # Windows has Battle.net already: only Epic's comes.
            self.assertEqual(q.fetch_launchers({"battlenet"}, {"epic", "battlenet"}, folder, fetch), ["epic"])
            self.assertEqual(sorted(p.name for p in folder.iterdir()), ["EpicGamesLauncherInstaller.msi"])
            self.assertEqual(q.fetch_launchers({"battlenet"}, {"epic", "battlenet"}, folder, fetch), [])  # fresh: not again
            # Windows installed Epic's: its installer goes.
            q.fetch_launchers({"battlenet", "epic"}, {"epic", "battlenet"}, folder, fetch)
            self.assertEqual(list(folder.iterdir()), [])
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        for key, (file, _) in q.INSTALLERS.items():
            self.assertIn(f'("{key}", "{file}")', bridge)                        # the same names on both sides
        session = (ROOT / "linux/libexec/monet-session").read_text(encoding="utf-8")
        self.assertIn('"$LIBEXECDIR/monet-quick" wine-share; "$LIBEXECDIR/monet-quick" launchers', session)

    def test_discord_comes_along_for_calls_in_windows(self):
        # A voice call dropped on the way to Windows: someone who uses Discord here gets it in
        # Windows on the trip to sign in to launchers (as them: it installs for one account),
        # and Windows starts it at sign-in from then on.
        from unittest import mock
        q = self.q
        with tempfile_dir() as tmp:
            shared = Path(tmp) / "Windows games"
            shared.mkdir()
            with mock.patch.object(q, "run", lambda *a, **k: "installed" if a[-1] == "dev.vencord.Vesktop" else None):
                self.assertEqual(q.needed_launchers(shared), {"discord"})
            with mock.patch.object(q, "run", lambda *a, **k: None):
                self.assertEqual(q.needed_launchers(shared), set())
        self.assertEqual(q.INSTALLERS["discord"][0], "DiscordSetup.exe")
        self.assertTrue(q.INSTALLERS["discord"][1].startswith("https://discord.com/api/downloads/"))
        d = self.drive
        with tempfile_dir() as tmp:
            root = Path(tmp) / "drive"
            ann = root / "Users/Ann"
            (ann / "AppData/Local/Discord").mkdir(parents=True)
            (ann / "NTUSER.DAT").write_bytes(b"regf")
            (ann / "AppData/Local/Discord/Update.exe").write_bytes(b"MZ")
            self.assertEqual(d.windows_launchers(root, "ann"), ["discord"])
            self.assertEqual(d.windows_launchers(root, "bob"), ["discord"])  # the only account there is
            self.assertEqual(d.windows_launchers(root), [])
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        self.assertIn('if !launcher_installed("discord") && installer_fetched("discord") {', bridge)
        self.assertIn('if !matches!(key, "battlenet" | "ea" | "discord") {', bridge)
        launchers = (ROOT / "crates/monet-bridge/src/launchers.rs").read_text(encoding="utf-8")
        self.assertIn(r'("discord", "Discord", vec![env_dir("LOCALAPPDATA", "").join("Discord\\Update.exe")]),', launchers)
        self.assertIn('command.args(["--processStart", "Discord.exe"]);', launchers)
        installer = (ROOT / "windows/Install-Launcher.ps1").read_text(encoding="utf-8")
        self.assertIn("'discord' { (Start-Process -FilePath $setup -PassThru).WaitForExit() }", installer)

    def test_wines_launchers_install_on_windows_games_folder(self):
        q = self.q
        with tempfile_dir() as tmp:
            games, shared = Path(tmp) / "Games", Path(tmp) / "Windows games"
            for prefix in ("battlenet", "ubisoft-connect", "not-wine"):
                (games / prefix).mkdir(parents=True)
            for prefix in ("battlenet", "ubisoft-connect"):
                (games / prefix / "dosdevices").mkdir()
                (games / prefix / "drive_c").mkdir()
            prefixes = q.wine_prefixes((games,))
            self.assertEqual(sorted(p.name for p in prefixes), ["battlenet", "ubisoft-connect"])
            shared.mkdir()
            if os.name == "nt":
                self.skipTest("Wine's drive names (w:) can't be file names on Windows")
            self.assertTrue(q.map_wine_drive(games / "battlenet", shared))
            self.assertEqual(Path(os.readlink(games / "battlenet/dosdevices/w:")), shared)
            self.assertFalse(q.map_wine_drive(games / "battlenet", shared))       # a W: stays as it is

    def test_battlenets_games_there_show_before_windows_lists_them(self):
        q = self.q
        # Monet's table is Bridge's, entry for entry.
        bridge = (ROOT / "crates/monet-bridge/src/parse.rs").read_text(encoding="utf-8")
        table = bridge[bridge.index("const BATTLENET"):bridge.index("];", bridge.index("const BATTLENET"))]
        self.assertEqual(dict(re.findall(r'\("(\w+)", "(\w+)"\)', table)), q.BATTLENET)
        self.assertEqual((q.battlenet_code("Fenris"), q.battlenet_code("wow_classic"), q.battlenet_code("auks")), ("Fen", None, "AUKS"))
        with tempfile_dir() as tmp:
            shared = Path(tmp) / "Windows games"
            (shared / "Call of Duty").mkdir(parents=True)
            (shared / "Call of Duty/.build.info").write_text(
                "Branch!STRING:0|Active!DEC:1|Product!STRING:0\neu|0|odin\neu|1|auks\n")
            (shared / "Blizzard/Overwatch").mkdir(parents=True)
            (shared / "Blizzard/Overwatch/.build.info").write_text("Product!STRING:0\nprometheus\n")
            found = {g["id"]: g for g in q.shared_battlenet(shared)}
            self.assertEqual(found["battlenet:AUKS"], {"id": "battlenet:AUKS", "name": "Call of Duty",
                                                        "locate": "C:\\Games\\Call of Duty"})
            self.assertEqual(found["battlenet:Pro"]["locate"], "C:\\Games\\Blizzard\\Overwatch")

    def test_battlenet_and_ubisoft_connect_are_one_tap_away(self):
        q = self.q
        from unittest import mock
        with tempfile_dir() as tmp:
            games = Path(tmp) / "Games"
            (games / "battlenet/drive_c").mkdir(parents=True)
            self.assertEqual((q.launcher_here("battlenet", (games,)), q.launcher_here("ubisoft", (games,))), (True, False))
            calls = []
            with mock.patch.object(q, "run", lambda *a, **k: calls.append(a) or ""), \
                    mock.patch.object(q.shutil, "which", lambda name: "/usr/bin/" + name):
                self.assertEqual(q.flatpaks_see_shared(flags=Path(tmp) / "flags"), [q.LUTRIS_APP, q.HEROIC_APP])
                self.assertEqual(q.flatpaks_see_shared(flags=Path(tmp) / "flags"), [])      # once for each
            self.assertIn(("flatpak", "override", "--user", f"--filesystem={q.SHARED}", q.LUTRIS_APP), calls)
            started = []
            with mock.patch.object(q, "lutris_command", lambda: ["lutris"]), mock.patch.object(q, "flatpaks_see_shared", lambda: []), \
                    mock.patch.object(q, "launcher_here", lambda key: key == "battlenet"), \
                    mock.patch.object(q.subprocess, "Popen", lambda args, **k: started.append(args)):
                q.get_launcher("ubisoft")
                q.get_launcher("battlenet")
            self.assertEqual(started[0], ["lutris", "lutris:ubisoft-connect"])          # installed by Lutris
            self.assertEqual(started[2], ["lutris", "lutris:rungame/battlenet"])        # here already: opened
            self.assertEqual(started[1][1:], ["wine-watch"])                            # W: as soon as there's a prefix
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn('sheet.ask("get-launcher " + modelData[0], out => {', settings)
        quick = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn("'\"$0\" epic-share; \"$0\" wine-share; \"$0\" launchers', quick", quick)   # when the gallery opens too
        cover = (ROOT / "crates/monet-bridge/src/cover.rs").read_text(encoding="utf-8")
        self.assertIn('l.text(TITLE, 0xFFFFFF, &trf("Getting %1 ready", &[launcher]));', cover)
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        self.assertIn("let _preparing = Cover::open(Scene::Preparing { launcher: name.into() });", bridge)

    def test_ubisofts_games_on_w_are_noted_for_windows(self):
        q = self.q
        reg = ('WINE REGISTRY Version 2\n\n'
               '[Software\\\\Wow6432Node\\\\Ubisoft\\\\Launcher\\\\Installs\\\\635] 1700000000\n'
               '#time=1da\n"InstallDir"="W:/Assassin\'s Creed Unity/"\n\n'
               '[Software\\\\Wow6432Node\\\\Ubisoft\\\\Launcher\\\\Installs\\\\720] 1700000000\n'
               '"InstallDir"="C:\\\\Program Files (x86)\\\\Ubisoft\\\\games\\\\Far Cry\\\\"\n\n'
               '[Software\\\\Wine] 1700000000\n"InstallDir"="W:/nope"\n')
        self.assertEqual(q.ubisoft_installs(reg), {"635": "W:/Assassin's Creed Unity/",
                                                   "720": "C:\\Program Files (x86)\\Ubisoft\\games\\Far Cry\\"})
        with tempfile_dir() as tmp:
            prefix, shared = Path(tmp) / "Games/ubisoft-connect", Path(tmp) / "Windows games"
            prefix.mkdir(parents=True)
            (prefix / "system.reg").write_text(reg, encoding="utf-8")
            (shared / "Assassin's Creed Unity").mkdir(parents=True)
            (shared / ".monet/ubisoft").mkdir(parents=True)
            (shared / ".monet/ubisoft/999.json").write_text("{}")          # uninstalled since
            self.assertEqual(q.ubisoft_share([prefix], shared), ["635"])
            self.assertEqual(json.loads((shared / ".monet/ubisoft/635.json").read_text()),
                             {"id": "635", "folder": "Assassin's Creed Unity"})
            self.assertFalse((shared / ".monet/ubisoft/999.json").exists())
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        self.assertIn("share_with_epic();\n    share_with_ubisoft();", bridge)
        self.assertIn("found.extend(scan_shared_battlenet());", bridge)
        self.assertIn('"/v", "InstallDir", "/t", "REG_SZ"', bridge)
        games = GAMES_APP.read_text(encoding="utf-8")
        self.assertIn("root.storeName(root.asking.store), root.asking.locate)", games)


class GamesTheApp(unittest.TestCase):
    """After 0.9.3: Games is an app of its own, a library like Steam's in Monet's look:
    sections and stores down the side, covers sorted by when, name, play time or size,
    favorites, and a page for each game."""

    def test_the_library_says_how_long_and_how_big(self):
        q = quick_helper()
        steam = {"10": "Zeta", "11": "Alpha"}
        windows = [{"id": "epic:Fortnite", "name": "Fortnite", "minutes": 90}, {"id": "steam:10", "name": "Zeta", "minutes": 30}]
        found = {g["id"]: g for g in q.library({}, steam, [], windows, set(), False, [], {}, {}, {"steam:10": 5}, 100,
                                               minutes={"steam:10": 600, "epic:Fortnite": 15}, liked={"steam:11"},
                                               sizes={"10": 4096})}
        zeta, alpha, fortnite = found["steam:10"], found["steam:11"], found["epic:Fortnite"]
        # Steam counts an account's time on every PC; the rest, each side its own.
        self.assertEqual((zeta["minutes"], fortnite["minutes"], alpha["minutes"]), (600, 105, 0))
        self.assertEqual((zeta["last"], zeta["size"], alpha["size"]), (5, 4096, 0))
        self.assertEqual((zeta["favorite"], alpha["favorite"]), (False, True))
        self.assertTrue(alpha["tall"].endswith("/11/library_600x900.jpg"))
        self.assertTrue(alpha["hero"].endswith("/11/library_hero.jpg"))
        self.assertEqual((fortnite["tall"], fortnite["hero"]), ("", ""))

    def test_steam_heroic_and_lutris_count_play_time(self):
        q = quick_helper()
        with tempfile_dir() as tmp:
            config = Path(tmp) / "steam/userdata/1/config/localconfig.vdf"
            config.parent.mkdir(parents=True)
            config.write_text('"UserLocalConfigStore" { "Software" { "Valve" { "Steam" { "apps" {'
                              ' "620" { "LastPlayed" "1700000000" "Playtime" "125" } "730" { "Playtime" "x" } } } } } }')
            self.assertEqual(q.steam_stats(Path(tmp) / "steam"), ({"620": 1700000000}, {"620": 125}))
            self.assertEqual(q.last_played(Path(tmp) / "steam"), {"620": 1700000000})
        played = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn('"minutes": int(total) if isinstance(total, (int, float)) else 0', played)          # Heroic: minutes
        self.assertIn('"minutes": round(hours * 60) if isinstance(hours, (int, float)) else 0', played)  # Lutris: hours
        self.assertEqual([q.byte_size(v) for v in (1234, "12.5 GiB", "300 MB", "7 B", "big", None, True)],
                         [1234, 13421772800, 314572800, 7, 0, 0, 0])

    def test_favorites_are_kept(self):
        q = quick_helper()
        from unittest import mock
        with tempfile_dir() as tmp, mock.patch.object(q, "FAVORITES", Path(tmp) / "monet/favorite-games.json"):
            self.assertEqual(q.favorites(), set())
            q.main(["favorite", "steam:620", "on"])
            q.main(["favorite", "lutris:3", "on"])
            q.main(["favorite", "steam:620", "off"])
            self.assertEqual(q.favorites(), {"lutris:3"})
            with self.assertRaises(SystemExit):
                q.main(["favorite", "../x", "on"])
            with self.assertRaises(SystemExit):
                q.main(["favorite", "steam:620", "maybe"])
            (Path(tmp) / "monet/favorite-games.json").write_text('["steam:1", 5, "no good"]')
            self.assertEqual(q.favorites(), {"steam:1"})

    def test_windows_play_time_comes_from_bridge(self):
        core = (ROOT / "crates/monet-core/src/games.rs").read_text(encoding="utf-8")
        self.assertIn('#[serde(default, skip_serializing_if = "is_zero")]\n    pub minutes: u64,', core)
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        self.assertIn("if let Some(time) = played {\n        add_playtime(&id, time);", bridge)
        self.assertIn("minutes: played.get(&g.id).copied().unwrap_or(0),", bridge)
        q = quick_helper()
        with tempfile_dir() as tmp:
            games = Path(tmp) / "games.json"
            games.write_text(json.dumps({"games": [{"id": "riot:valorant", "name": "VALORANT", "minutes": 300},
                                                   {"id": "epic:Fortnite", "name": "Fortnite", "minutes": "lots"}]}))
            found = {g["id"]: g["minutes"] for g in q.windows_games([games])}
        self.assertEqual(found, {"riot:valorant": 300, "epic:Fortnite": 0})

    def test_games_is_an_app(self):
        app = (ROOT / "linux/libexec/monet-games").read_text(encoding="utf-8")
        # Its taskbar entry and icon come from its menu entry; one window, brought forward again.
        self.assertIn('app.setDesktopFileName("monet-games")', app)
        self.assertIn("if already_open(name):\n        return 0", app)
        self.assertIn('PROGRAMS = {"helper": f"{LIBEXECDIR}/monet-quick", "monet": f"{BINDIR}/monet"}', app)
        entry = (SHARE / "applications/monet-games.desktop").read_text(encoding="utf-8")
        self.assertIn("Exec=@LIBEXECDIR@/monet-games\n", entry)
        self.assertIn("Categories=Game;\n", entry)
        install = (ROOT / "linux/install.sh").read_text(encoding="utf-8")
        self.assertIn('cp -r "$SRC/share/monet/games" "$DATADIR/monet/games"', install)
        self.assertIn('put 644 "$SRC/share/applications/monet-games.desktop"', install)
        self.assertIn("python3-pyside6", (ROOT / "image/Containerfile").read_text(encoding="utf-8"))
        # The panel's Games button and Windows+G open the app.
        widget = (PLASMA / "plasmoids/org.monet.games/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn('for (const c of "monet-games.desktop")', widget)
        self.assertIn("Plasmoid.onActivated: open()", widget)
        # No popup any more, but an empty full view: without one, Plasma lifted the button
        # itself out of the bar (seen in the VM: no Games button at all). And a size, as the
        # bar's other buttons have.
        self.assertIn("    fullRepresentation: Item {}\n", widget)
        self.assertIn("Layout.minimumWidth: Plasmoid.formFactor === PlasmaCore.Types.Vertical ? 0 : height", widget)

    def test_the_app_speaks_monets_words(self):
        loader = importlib.machinery.SourceFileLoader("monet_games_words", str(ROOT / "linux/libexec/monet-games"))
        try:
            spec = importlib.util.spec_from_loader("monet_games_words", loader)
            games = importlib.util.module_from_spec(spec)
            loader.exec_module(games)
        except ImportError:
            self.skipTest("no Qt for Python here")
        self.assertEqual(games.fill("%1 of %2", (3.0, "x")), "3 of x")
        self.assertEqual(games.fill("%1%2", (1.5, 2)), "1.52")
        self.assertEqual(games.Words().i18np("%1 game", "%1 games", 1.0), "1 game")
        self.assertEqual(games.Words().i18np("%2 of %1 game", "%2 of %1 games", 4, 2), "2 of 4 games")

    def test_settings_is_an_app_too(self):
        # Settings (monet-settings) is built as Games is, from Games' own pieces: its words, its
        # helper runner and its one window.
        app = (ROOT / "linux/libexec/monet-settings").read_text(encoding="utf-8")
        for piece in ('_loader = SourceFileLoader("monet_games", f"{LIBEXECDIR}/monet-games")', "_loader.exec_module(games)",
                      'app.setDesktopFileName("monet-settings")', "if games.already_open(name, page):\n        return 0",
                      "helper = games.Helper()\n    games.answer(server, helper)",
                      'f"{DATADIR}/monet/settings-app/MonetSettings.qml"'):
            self.assertIn(piece, app)
        settings = SETTINGS_QML.read_text(encoding="utf-8")
        for name in ("pictures", "brush", "firstPage", "helper"):  # what monet-settings hands the window
            self.assertIn(f'setContextProperty("{name}"', app)
            self.assertRegex(settings, rf"\b{name}\b")
        install = (ROOT / "linux/install.sh").read_text(encoding="utf-8")
        self.assertIn('cp -r "$SRC/share/monet/settings-app" "$DATADIR/monet/settings-app"', install)

    def test_a_second_start_hands_over_its_page(self):
        # Opened again (Settings at Bluetooth, say): the window that's open goes there, with the
        # desktop's activation token so it may come forward.
        from unittest import mock
        loader = importlib.machinery.SourceFileLoader("monet_games_again", str(ROOT / "linux/libexec/monet-games"))
        try:
            spec = importlib.util.spec_from_loader("monet_games_again", loader)
            games = importlib.util.module_from_spec(spec)
            loader.exec_module(games)
            from PySide6.QtCore import QCoreApplication
            from PySide6.QtNetwork import QLocalServer
        except ImportError:
            self.skipTest("no Qt for Python here")
        app = QCoreApplication.instance() or QCoreApplication([])
        name = f"monet-test-{os.getpid()}"
        server = QLocalServer()
        self.assertTrue(server.listen(name))
        helper = games.Helper()
        got = []
        helper.wanted.connect(got.append)
        games.answer(server, helper)
        with mock.patch.dict(os.environ, {"XDG_ACTIVATION_TOKEN": "token-1"}):
            self.assertTrue(games.already_open(name, "bluetooth"))
            os.environ["XDG_ACTIVATION_TOKEN"] = ""
            deadline = __import__("time").time() + 5
            while not got and __import__("time").time() < deadline:
                app.processEvents()
            self.assertEqual(got, ["bluetooth"])
            self.assertEqual(os.environ["XDG_ACTIVATION_TOKEN"], "token-1")
        server.close()
        self.assertFalse(games.already_open(f"monet-nobody-{os.getpid()}"))

    def test_the_library_window(self):
        games = GAMES_APP.read_text(encoding="utf-8")
        for sort in ('["recent", i18n("Recent")]', '["name", i18n("Name")]', '["playtime", i18n("Play time")]', '["size", i18n("Size")]'):
            self.assertIn(sort, games)
        # The size and the order are kept for next time.
        self.assertIn("property alias sort: root.sort", games)
        self.assertIn('{ id: "favorites", name: i18n("Favorites")', games)
        self.assertIn('run(["helper", "favorite", game.id, on ? "on" : "off"])', games)
        page = (GAMES_APP.parent / "GamePage.qml").read_text(encoding="utf-8")
        for stat in ('i18n("Last played")', 'i18n("Play time")', 'i18n("Size on disk")'):
            self.assertIn(stat, page)


class EAGames(unittest.TestCase):
    """After 0.9.3: EA's games, in Windows and from the EA app in Monet, started without the EA
    app in sight, which closes after."""

    XML = ('<?xml version="1.0"?><DiPManifest><contentIDs><contentID>Origin.OFR.50.0005831</contentID>'
           '<contentID>1026480</contentID></contentIDs><gameTitles><gameTitle locale="de_DE">FC 26 DE</gameTitle>'
           '<gameTitle locale="en_US">EA SPORTS FC&#8482; 26 &amp; Co</gameTitle></gameTitles></DiPManifest>')

    def test_ea_games_read_as_bridge_reads_them(self):
        q = quick_helper()
        self.assertEqual(q.ea_game(self.XML), (["Origin.OFR.50.0005831", "1026480"], "EA SPORTS FC™ 26 & Co"))
        self.assertIsNone(q.ea_game("<contentIDs><contentID>1;rm</contentID></contentIDs>"))
        self.assertIsNone(q.ea_game("<DiPManifest/>"))
        parse = (ROOT / "crates/monet-bridge/src/parse.rs").read_text(encoding="utf-8")
        self.assertIn('id.len() <= 48 && !id.starts_with(\'.\')', parse)

    def test_the_shared_folders_ea_games_before_windows_has_them(self):
        q = quick_helper()
        with tempfile_dir() as tmp:
            shared = Path(tmp) / "Windows games"
            (shared / "FC 26/__Installer").mkdir(parents=True)
            (shared / "FC 26/__Installer/installerdata.xml").write_text(self.XML, encoding="utf-8")
            (shared / "Broken/__Installer").mkdir(parents=True)
            (shared / "Broken/__Installer/installerdata.xml").write_bytes(b"\xff\xfe" + "<x/>".encode("utf-16-le"))
            found = q.shared_ea(shared)
            self.assertEqual(found, [{"id": "ea:Origin.OFR.50.0005831", "name": "EA SPORTS FC™ 26 & Co", "locate": "C:\\Games"}])
            self.assertIn("ea", q.needed_launchers(shared))
        self.assertTrue(q.WINDOWS_ID.fullmatch("ea:Origin.OFR.50.0005831"))
        self.assertEqual(q.LUTRIS_SLUGS["ea"], "ea-app")
        self.assertTrue(q.INSTALLERS["ea"][1].startswith("https://origin-a.akamaihd.net/"))

    def test_windows_starts_them_quietly_and_closes_the_launcher(self):
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        # Started by the EA app from the game's own offer ids; a shared one it doesn't know yet
        # opens its page instead of downloading it again.
        self.assertIn('format!("origin2://game/launch?offerIds={}{}", game.offers.join(","), if known { "&autoDownload=1" } else { "" })', bridge)
        self.assertIn("found.extend(scan_ea());", bridge)
        # The painting stays in front of the launcher until the game runs, a minute at most.
        self.assertIn("cover.hold(true);", bridge)
        self.assertIn("if since.elapsed() > LAUNCHER_PATIENCE {\n            let_go();", bridge)
        self.assertIn("win::minimize_windows_of(&launchers::running(key, game_dir.as_deref()));", bridge)
        # Staying in Windows: the launcher closes, after its cloud saves.
        self.assertIn("wait_for_quiet(Duration::from_secs(60));", bridge)
        self.assertIn("win::end_processes(&left);", bridge)
        launchers = (ROOT / "crates/monet-bridge/src/launchers.rs").read_text(encoding="utf-8")
        self.assertIn('["ea", "battlenet", "ubisoft", "epic", "rockstar", "riot"]', launchers)
        self.assertIn('!name.ends_with("service.exe")', launchers)
        installer = (ROOT / "windows/Install-Launcher.ps1").read_text(encoding="utf-8")
        self.assertIn("ValidateSet('epic', 'ubisoft', 'battlenet', 'ea', 'discord')", installer)
        self.assertIn("Signer = 'O=\"?Electronic Arts'", installer)
        games = GAMES_APP.read_text(encoding="utf-8")
        self.assertIn('root.asking.locate && root.asking.store === "ea"', games)
        self.assertIn('ea: "EA"', games)


class PathTriggered(unittest.TestCase):
    """Found by the test bench: a service started by a .path unit ran six times in four seconds
    at sign-in and hit systemd's start limit, which stopped it for the rest of the session."""

    def test_one_setting_saved_leaves_the_others_unchosen(self):
        # Found by the test bench: choosing a series saved every setting, glass included, so a
        # VM (the processor drawing its screen) kept glass on for good instead of turning it off.
        q = quick_helper()
        from unittest import mock
        with tempfile_dir() as tmp, mock.patch.object(q, "PREFS", Path(tmp) / "monet/prefs.json"), \
                mock.patch.object(q, "drawn_by_processor", lambda: True), mock.patch.object(q, "run", lambda *a, **k: ""):
            q.main(["series", "lilies"])
            q.main(["pref", "dodge", "on"])
            self.assertEqual(json.loads(q.PREFS.read_text()), {"series": "lilies", "dodge": True})
            self.assertEqual(q.prefs()["glass"], "solid")
            q.main(["pref", "glass", "on"])
            self.assertEqual(q.prefs()["glass"], "clear")

    def test_path_started_services_are_never_turned_away(self):
        units = ROOT / "linux/systemd/user"
        paths = sorted(units.glob("*.path"))
        self.assertTrue(paths)
        for path in paths:
            started = re.search(r"(?m)^Unit=(\S+)$", path.read_text())
            service = units / (started.group(1) if started else path.name.replace(".path", ".service"))
            text = service.read_text()
            self.assertIn("StartLimitIntervalSec=0", text, service.name)
            self.assertRegex(text, r"(?m)^ExecStartPre=/usr/bin/sleep \d$", service.name)


class MonetsNamesEverywhere(unittest.TestCase):
    """Found by the test bench: window titles said Konsole and Dolphin (Qt ends every title with
    the app's own name), the system's description said Bazzite, Files listed the boot partition,
    and Input Remapper held up the start."""

    def test_kde_apps_say_monets_names_in_every_language(self):
        import gettext
        spec = importlib.util.spec_from_file_location("mt_names", ROOT / "tools/make-translations.py")
        mt = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mt)
        locale = SHARE / "locale"
        names = {}
        for line in (SHARE / "monet/names.tsv").read_text(encoding="utf-8").splitlines():
            english, language, said = line.split("\t")
            names[(english, language)] = said
        for language in ["en", *mt.LANGUAGES]:
            # A name that isn't a menu's ("More settings") is said as Monet Settings says it.
            po = mt.read_po(mt.PO / f"{language}.po") if language in mt.LANGUAGES else {}
            for domain, (name, messages) in mt.APP_NAMES.items():
                catalog = gettext.translation(domain, localedir=str(locale), languages=[f"{language}@monet"])
                wanted = names.get((name, language)) or (po.get((None, name)) or {}).get("text") or name
                for context, text in messages:
                    said = catalog.pgettext(context, text) if context else catalog.gettext(text)
                    self.assertEqual(said, wanted, (language, domain, text))
        en = gettext.translation("konsole", localedir=str(locale), languages=["en@monet"])
        self.assertEqual(en.pgettext("@title", "Konsole"), "Terminal")

    def test_the_session_puts_monets_names_before_its_language(self):
        script = SHARE / "plasma-workspace/env/monet-names.sh"
        cases = {"LANG=en_US.UTF-8": "en_US@monet:en@monet:en_US",
                 "LANG=sv_SE.UTF-8 LANGUAGE=sv:en_US": "sv@monet:sv:en_US@monet:en@monet:en_US",
                 "LANG=pt_BR.UTF-8": "pt_BR@monet:pt@monet:pt_BR", "LANG=C": "", "LANGUAGE=de@monet:de LANG=de_DE.UTF-8": "de@monet:de"}
        try:
            subprocess.run(["sh", "-c", "true"], check=True, capture_output=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            self.skipTest("no sh here")
        for case, wanted in cases.items():
            env = dict(item.split("=", 1) for item in case.split())
            got = subprocess.run(["sh", "-c", '. "$1"; . "$1"; printf %s "$LANGUAGE"', "sh", str(script)],
                                 env=env, capture_output=True, text=True, timeout=10).stdout
            self.assertEqual(got, wanted, case)

    def test_animations_where_the_processor_draws(self):
        # Found by the test bench: KWin leaves animations out without a graphics card's driver,
        # so the bar never slid in the VM. No render node there; a PC with processor to spare.
        script = (SHARE / "plasma-workspace/env/monet-motion.sh").read_text()
        self.assertIn("ls /dev/dri/renderD*", script)
        self.assertIn('-ge 6 ]', script)
        self.assertIn("export KWIN_EFFECTS_FORCE_ANIMATIONS", script)
        self.assertIn("/etc/xdg/plasma-workspace/env/monet-motion.sh", (ROOT / "linux/install.sh").read_text())

    def test_installed_with_monet(self):
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('for catalog in "$SRC"/share/locale/*@monet/LC_MESSAGES/*.mo; do', install)
        self.assertIn("/etc/xdg/plasma-workspace/env/monet-names.sh", install)
        self.assertIn("/etc/udev/rules.d/90-monet-system.rules", install)
        uninstall = (ROOT / "linux/uninstall.sh").read_text()
        self.assertIn("/etc/xdg/plasma-workspace/env/monet-names.sh /etc/xdg/plasma-workspace/env/monet-motion.sh", uninstall)
        self.assertIn('rm -rf "$PREFIX"/share/locale/*@monet', uninstall)

    def test_the_system_describes_itself_as_monet(self):
        install = (ROOT / "linux/install.sh").read_text()
        for line in ("-e 's/^NAME=.*/NAME=\"Monet\"/'", "BOOTLOADER_NAME=\"Monet\"", 'VERSION=\\"${monet_version:-0}\\"',
                     'DOCUMENTATION_URL="https://github.com/HappyHamster135/Monet'):
            self.assertIn(line, install)
        # ID and VARIANT_ID stay Bazzite's: its tools go by them.
        self.assertNotIn("s/^ID=", install)
        self.assertNotIn("VARIANT_ID", install)

    def test_monets_partitions_stay_out_of_files(self):
        rule = (ROOT / "linux/udev/90-monet-system.rules").read_text()
        self.assertIn('ENV{ID_BUS}!="usb", ENV{ID_FS_TYPE}=="ext4", ENV{ID_FS_LABEL}=="boot", ENV{UDISKS_IGNORE}="1"', rule)
        setup = (ROOT / "setup/monet_setup/install.py").read_text(encoding="utf-8")
        self.assertIn('run("mkfs.ext4", "-F", "-q", "-L", "boot", parts["boot"])', setup)

    def test_input_remapper_is_out_of_the_way(self):
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertRegex(look, r"yad-icon-browser \\\n\s+input-remapper-gtk; do")
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn("systemctl disable input-remapper.service", install)
        self.assertIn("rm -f /etc/xdg/autostart/input-remapper-autoload.desktop", install)


class FirmwareIds(unittest.TestCase):
    """Found by the test bench: Settings said Secure Boot was off on a PC where it was on, and
    Ready when you come back never saw Windows coming next: both read UEFI's variables under a
    mistyped id."""

    def test_every_uefi_id_is_uefis(self):
        core = (ROOT / "crates/monet-core/src/efi.rs").read_text(encoding="utf-8")
        guid = re.search(r'GLOBAL_GUID: &str = "([0-9a-f-]+)"', core).group(1)
        self.assertEqual(guid, "8be4df61-93ca-11d2-aa0d-00e098032b8c")  # EFI_GLOBAL_VARIABLE, the UEFI spec's
        for path in [*sorted((ROOT / "linux/libexec").iterdir()), ROOT / "tests/fake-efi.py"]:
            if not path.is_file():
                continue
            for found in re.findall(r"8be4df61-[0-9a-f-]+", path.read_text(encoding="utf-8", errors="replace")):
                self.assertEqual(found, guid, path.name)

    def test_documents_opens_pdfs_through_its_hidden_entry(self):
        # Found by the test bench: PDFs opened in Documents, but Settings said nothing was chosen,
        # since Okular names PDFs in a hidden entry of its own, not in Documents'.
        q = quick_helper()
        documents = {"Type": "Application", "Name": "Documents", "Exec": "okular %U", "MimeType": "application/x-okular;"}
        pdf = {"Type": "Application", "Name": "Okular", "Exec": "okular %U", "NoDisplay": "true", "MimeType": "application/pdf;"}
        zen = {"Type": "Application", "Name": "Zen", "Exec": "flatpak run app.zen_browser.zen %u", "MimeType": "application/pdf;"}
        other = {"Type": "Application", "Name": "Hidden helper", "Exec": "flatpak run other.app %u", "NoDisplay": "true",
                 "MimeType": "text/plain;"}
        found = q.takers([("org.kde.okular.desktop", documents), ("okularApplication_pdf.desktop", pdf),
                          ("app.zen_browser.zen.desktop", zen), ("other.desktop", other)], "pdf")
        self.assertEqual([a["id"] for a in found], ["org.kde.okular.desktop", "app.zen_browser.zen.desktop"])
        self.assertEqual(found[0]["types"], ["application/pdf"])
        texts = q.takers([("app.zen_browser.zen.desktop", zen), ("other.desktop", other)], "text")
        self.assertEqual(texts, [])  # another flatpak's hidden entry is never Zen's

    def test_secure_boot_is_read_where_the_firmware_keeps_it(self):
        q = quick_helper()
        with tempfile_dir() as tmp:
            efivars = Path(tmp)
            self.assertEqual(q.secure_boot(efivars), "off")
            (efivars / "SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c").write_bytes(bytes([7, 0, 0, 0, 1]))
            self.assertEqual(q.secure_boot(efivars), "on")

    def test_ready_sees_windows_coming_next(self):
        ready = libexec_helper("monet-ready")
        with tempfile_dir() as tmp:
            efivars = Path(tmp)
            guid = "8be4df61-93ca-11d2-aa0d-00e098032b8c"
            (efivars / f"BootNext-{guid}").write_bytes(bytes([7, 0, 0, 0, 3, 0]))
            name = "Windows Boot Manager".encode("utf-16-le") + b"\0\0"
            path = "\\EFI\\Microsoft\\Boot\\bootmgfw.efi".encode("utf-16-le")
            (efivars / f"Boot0003-{guid}").write_bytes(bytes([7, 0, 0, 0]) + bytes([1, 0, 0, 0, 0x74, 0]) + name + path)
            self.assertTrue(ready.boots_windows_next(efivars))

    def test_the_firewall_is_asked_of_systemd(self):
        quick = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn('run("systemctl", "is-active", "firewalld")', quick)
        self.assertNotIn('"firewall-cmd", "--state"', quick)


class OneOfEachName(unittest.TestCase):
    """Found by the test bench: monet-quick had two ring()s, the Timer's alarm and Quick Settings'
    doorbell; the later one won, so opening Settings from the menu crashed."""

    def test_no_helper_defines_a_function_twice(self):
        import ast
        scripts = [p for p in sorted((ROOT / "linux/libexec").iterdir())
                   if p.is_file() and p.read_text(encoding="utf-8", errors="replace").startswith("#!/usr/bin/env python3")]
        self.assertIn("monet-quick", [p.name for p in scripts])
        for path in scripts + sorted((ROOT / "setup/monet_setup").glob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            names = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
            self.assertEqual(sorted({n for n in names if names.count(n) > 1}), [], path.name)

    def test_settings_opens_as_its_own_app(self):
        # `monet-quick open PAGE` (the desktop's menu, Quick Settings, notifications) starts
        # monet-settings in a scope of its own, so a bar restart doesn't close it, and returns at
        # once; without it, KDE's System Settings at the matching page.
        from unittest import mock
        quick = quick_helper()
        started, ran = [], []
        with mock.patch.object(quick.os, "access", return_value=True), \
                mock.patch.object(quick.shutil, "which", return_value="/usr/bin/systemd-run"), \
                mock.patch.object(quick.subprocess, "Popen", lambda command, **kw: started.append((command, kw))):
            quick.open_settings("sound")
            quick.open_settings("")
        self.assertEqual(started[0][0], ["systemd-run", "--user", "--scope", "--collect", "--quiet", "--slice=app.slice",
                                         f"{quick.LIBEXECDIR}/monet-settings", "sound"])
        self.assertEqual(started[1][0][-1], f"{quick.LIBEXECDIR}/monet-settings")
        self.assertTrue(started[0][1]["start_new_session"])
        with mock.patch.object(quick.os, "access", return_value=False), \
                mock.patch.object(quick.os, "execvpe", lambda *a: ran.append(a)):
            quick.open_settings("sound")
        self.assertEqual(len(ran), 1)
        self.assertEqual(ran[0][:2], ("systemsettings", ["systemsettings", "kcm_pulseaudio"]))
        self.assertIsInstance(ran[0][2], dict)


class WindowsKeys(unittest.TestCase):
    """After 0.9.3: Windows' keyboard shortcuts, for hands that learned them there."""

    def test_windows_keys_are_added_before_kwin_reads_them(self):
        look = (ROOT / "linux/libexec/monet-look").read_text(encoding="utf-8")
        keys = look[look.index('if [ "${1:-}" = --keys ]; then'):look.index('if [ "${1:-}" = --widget-keys ]; then')]
        for line in ('add_launch org.kde.plasma-systemmonitor.desktop _launch "Ctrl+Shift+Esc"',
                     'add_launch monet-settings.desktop _launch "Meta+I"',
                     'add_launch org.kde.krunner.desktop _launch "Meta+R"',
                     'add_launch org.kde.spectacle.desktop RectangularRegionScreenShot "Meta+Shift+S"',
                     'kwin_keys "Window Quick Tile Top" "none"', 'kwin_keys "Window Quick Tile Bottom" "none"',
                     'touch "$CONFIG/monet/keys-windows"'):
            self.assertIn(line, keys)
        # Once per account: a key someone changes later stays theirs.
        self.assertLess(keys.index('[ -e "$CONFIG/monet/keys-windows" ] && exit "$failed"'), keys.index("add_launch"))
        # Windows+Space for the next keyboard layout, beside KDE's own key, for accounts that had
        # Windows' keys already too (its own once).
        self.assertIn('add_keys "KDE Keyboard Layout Switcher" "Switch to Next Keyboard Layout" "Meta+Space"', keys)
        self.assertLess(keys.index('touch "$CONFIG/monet/keys-094"'), keys.index('[ -e "$CONFIG/monet/keys-windows" ] && exit "$failed"'))
        # Windows+Tab for the overview of the windows, as Windows' Task View (not a second Alt+Tab).
        self.assertIn('kwin_keys "Walk Through Windows" "Alt+Tab" "Alt+Tab,Walk Through Windows"', keys)
        self.assertIn('''kwin_keys "Overview" "Meta+W$(printf '\\t')Meta+Tab" "Meta+W,Toggle Overview"''', keys)
        widgets = look[look.index('if [ "${1:-}" = --widget-keys ]; then'):]
        self.assertIn('if (!w.globalShortcut) w.globalShortcut = "Meta+A"', widgets)
        self.assertIn('if (!w.globalShortcut) w.globalShortcut = "Meta+G"', widgets)
        # KWin's Grid View held Windows+G (seen in the VM), so Games' button never got it: freed
        # first, before KWin starts.
        self.assertIn('kwin_keys "Grid View" "none" "Meta+G,Toggle Grid View"', keys)
        self.assertLess(keys.index('kwin_keys "Grid View"'), keys.index('touch "$CONFIG/monet/keys-094"'))
        unit = (ROOT / "linux/systemd/user/monet-keys.service").read_text()
        self.assertIn("Before=plasma-kwin_wayland.service", unit)
        self.assertIn("ExecStart=@LIBEXECDIR@/monet-look --keys", unit)
        self.assertIn('[ -e "$looks/widget-keys" ] || "$LIBEXECDIR/monet-look" --widget-keys',
                      (ROOT / "linux/libexec/monet-session").read_text(encoding="utf-8"))
        self.assertIn("X-KDE-Shortcuts=Meta+I", (ROOT / "linux/share/applications/monet-settings.desktop").read_text(encoding="utf-8"))
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        for pair in ('[i18n("Settings"), ["Meta", "I"]]', '[i18n("What\'s running"), ["Ctrl", "Shift", "Esc"]]',
                     '[i18n("A window on the whole screen"), ["Meta", "\\u2191"]]',
                     '[i18n("Snap layouts"), ["Meta", "Z"]]', '[i18n("Next keyboard layout"), ["Meta", "Space"]]'):
            self.assertIn(pair, settings)

    def test_office_files_keep_their_lines(self):
        # Calibri and Cambria, Office's own since 2007: fonts as wide, or Word files reflow.
        image = (ROOT / "image/Containerfile").read_text(encoding="utf-8")
        self.assertIn("google-carlito-fonts google-crosextra-caladea-fonts", image)


class WindowsPrograms(unittest.TestCase):
    """After 0.9.3: a Windows program opened in Files runs in Monet (Proton) or opens in Windows."""

    def setUp(self):
        self.q = quick_helper()

    def test_its_id_is_named_as_monet_bridge_names_it(self):
        q = self.q
        # The same names as Bridge's own test (parse.rs): both sides find the program by it.
        self.assertEqual(q.program_slug("PaintDotNet Setup (2).exe"), "paintdotnet-setup-2-exe")
        self.assertEqual(q.program_slug("Ünïcode Tool.msi"), "n-code-tool-msi")
        bridge = (ROOT / "crates/monet-bridge/src/parse.rs").read_text(encoding="utf-8")
        self.assertIn('assert_eq!(slug("PaintDotNet Setup (2).exe"), "paintdotnet-setup-2-exe");', bridge)
        self.assertIn('assert_eq!(slug("Ünïcode Tool.msi"), "n-code-tool-msi");', bridge)

    def test_files_double_click_asks_monets_sheet(self):
        q = self.q
        from unittest import mock
        with tempfile_dir() as tmp:
            exe, text = Path(tmp) / "Setup.exe", Path(tmp) / "notes.txt"
            exe.write_bytes(b"MZ" + b"\0" * 100)
            text.write_text("x")
            ran, rang = [], []
            with mock.patch.object(q, "PROGRAM_PENDING", Path(tmp) / "pending.json"), \
                    mock.patch.object(q, "program_here", ran.append), mock.patch.object(q, "doorbell", lambda w: rang.append(w) or True):
                self.assertFalse(q.windows_program(str(text)))
                self.assertTrue(q.windows_program(str(exe)))
                self.assertEqual((rang, ran), (["program"], []))       # Quick Settings asks
                with mock.patch.object(q, "shared_info", lambda libs: {"state": "open", "mine": True, "free": 50 << 30}), \
                        mock.patch.object(q.shutil, "which", lambda name: "/usr/bin/umu-run"):
                    (Path(tmp) / "Shared").mkdir()
                    info = q.program_info(files=Path(tmp) / "Shared")
                self.assertEqual((info["name"], info["installer"], info["here"], info["windows"]), ("Setup.exe", True, True, "ok"))
                for shared, said in (({"state": "asleep"}, "closed"), ({"state": "open", "mine": False}, "not-yours"),
                                     ({"state": "open", "mine": True, "free": 1000}, "full"), ({"state": "no-windows"}, "no-windows")):
                    with mock.patch.object(q, "shared_info", lambda libs, s=shared: s):
                        self.assertEqual(q.program_info(files=Path(tmp) / "Shared")["windows"], said)
            with mock.patch.object(q, "PROGRAM_PENDING", Path(tmp) / "pending2.json"), \
                    mock.patch.object(q, "program_here", ran.append), mock.patch.object(q, "doorbell", lambda w: False):
                q.windows_program(str(exe))
                self.assertEqual(ran, [str(exe.absolute())])           # no Quick Settings: it runs here

    def test_it_runs_here_through_proton_in_monets_own_windows(self):
        q = self.q
        from unittest import mock
        with tempfile_dir() as tmp:
            steam = Path(tmp) / "Steam"
            for name in ("Proton 8.0", "Proton 9.0", "Proton Hotfix"):
                (steam / "steamapps/common" / name).mkdir(parents=True)
                (steam / "steamapps/common" / name / "proton").write_text("#!/bin/sh")
            self.assertEqual(q.steam_proton([steam]).name, "Proton 9.0")
            (steam / "steamapps/common/Proton - Experimental").mkdir()
            (steam / "steamapps/common/Proton - Experimental/proton").write_text("#!/bin/sh")
            self.assertEqual(q.steam_proton([steam]).name, "Proton - Experimental")
            self.assertIsNone(q.steam_proton([Path(tmp) / "none"]))
            msi = Path(tmp) / "Tool.msi"
            msi.write_bytes(b"\xd0\xcf")
            calls = []
            with mock.patch.object(q.subprocess, "run", lambda args, **k: calls.append((args, k["env"]))), \
                    mock.patch.object(q, "steam_proton", lambda: steam / "steamapps/common/Proton - Experimental"), \
                    mock.patch.object(q, "program_menu", lambda: 0), mock.patch.object(q, "PROGRAMS_PREFIX", Path(tmp) / "prefix"), \
                    mock.patch.object(q, "DATA_HOME", Path(tmp)), mock.patch.object(q.shutil, "which", lambda n: None):
                self.assertEqual(q.program_proton(str(msi)), 0)
            args, env = calls[0]
            self.assertEqual(args, ["umu-run", "msiexec", "/i", str(msi)])
            self.assertEqual((env["WINEPREFIX"], env["GAMEID"]), (str(Path(tmp) / "prefix"), "0"))
            self.assertTrue(env["PROTONPATH"].endswith("Proton - Experimental"))

    def test_what_an_installer_puts_in_the_start_menu_comes_into_the_app_menu(self):
        q = self.q
        self.assertEqual(q.lnk_target(windows_shortcut("C:\\Program Files\\Paint.NET\\paintdotnet.exe")),
                         "C:\\Program Files\\Paint.NET\\paintdotnet.exe")
        self.assertEqual(q.lnk_target(windows_shortcut("C:\\Tools\\tool.exe", unicode=False)), "C:\\Tools\\tool.exe")
        self.assertEqual(q.lnk_target(b"not a shortcut"), "")
        self.assertEqual(q.lnk_target(windows_shortcut("C:\\x.exe")[:0x50]), "")   # cut short
        with tempfile_dir() as tmp:
            prefix, apps = Path(tmp) / "prefix", Path(tmp) / "applications"
            menu = prefix / "drive_c/ProgramData/Microsoft/Windows/Start Menu/Programs/Paint.NET"
            menu.mkdir(parents=True)
            (prefix / "drive_c/Program Files/Paint.NET").mkdir(parents=True)
            (prefix / "drive_c/Program Files/Paint.NET/paintdotnet.exe").write_bytes(b"MZ")
            (prefix / "drive_c/Program Files/Paint.NET/unins000.exe").write_bytes(b"MZ")
            (menu / "Paint.NET.lnk").write_bytes(windows_shortcut("C:\\Program Files\\Paint.NET\\paintdotnet.exe"))
            (menu / "Uninstall Paint.NET.lnk").write_bytes(windows_shortcut("C:\\Program Files\\Paint.NET\\unins000.exe"))
            (menu / "Gone.lnk").write_bytes(windows_shortcut("C:\\Program Files\\Gone\\gone.exe"))
            apps.mkdir()
            (apps / "monet-program-old.desktop").write_text("[Desktop Entry]\n")
            self.assertEqual(q.program_menu(prefix, apps), 1)
            entry = (apps / "monet-program-paint-net.desktop").read_text()
            self.assertIn("Name=Paint.NET\n", entry)
            program = prefix / "drive_c/Program Files/Paint.NET/paintdotnet.exe"
            self.assertIn(f"monet-quick program-start {str(program).encode().hex()}\n", entry)
            self.assertFalse((apps / "monet-program-old.desktop").exists())     # its program is gone

    def test_it_opens_in_windows_through_the_shared_folder(self):
        q = self.q
        with tempfile_dir() as tmp:
            files = Path(tmp) / "Shared with Windows"
            files.mkdir()
            one, other = Path(tmp) / "a/Setup.exe", Path(tmp) / "b/Setup.exe"
            one.parent.mkdir()
            other.parent.mkdir()
            one.write_bytes(b"MZ one")
            other.write_bytes(b"MZ two")
            self.assertEqual(q.program_windows(str(one), files), "program:setup-exe")
            self.assertEqual(q.program_windows(str(one), files), "program:setup-exe")      # sent before
            self.assertEqual(q.program_windows(str(other), files), "program:setup-2-exe")  # another one
            self.assertEqual((files / "Setup.exe").read_bytes(), b"MZ one")
            self.assertEqual((files / "Setup (2).exe").read_bytes(), b"MZ two")
            # Saved there already (a download, in a folder of its own): nothing to copy.
            (files / "Mods").mkdir()
            (files / "Mods/Tool.exe").write_bytes(b"MZ tool")
            self.assertEqual(q.program_windows(str(files / "Mods/Tool.exe"), files), "program:mods-tool-exe")
            self.assertEqual(sorted(p.name for p in files.iterdir()), ["Mods", "Setup (2).exe", "Setup.exe"])
            self.assertIsNone(q.program_windows(str(one), Path(tmp) / "not there"))
        bridge = (ROOT / "crates/monet-bridge/src/parse.rs").read_text(encoding="utf-8")
        self.assertIn(r'assert_eq!(slug("Mods\\Tool.exe"), "mods-tool-exe");', bridge)

    def test_files_shows_the_shared_folder_while_its_there(self):
        q = self.q
        with tempfile_dir() as tmp:
            places, files = Path(tmp) / "user-places.xbel", Path("/run/media/Shared with Windows")
            self.assertFalse(q.files_place(True, places, files))           # KDE's own list first
            places.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<xbel>\n <bookmark href="file:///home/ann">\n'
                              '  <title>Home</title>\n </bookmark>\n</xbel>\n', encoding="utf-8")
            self.assertTrue(q.files_place(True, places, files))
            text = places.read_text(encoding="utf-8")
            self.assertIn('<bookmark href="file:///run/media/Shared%20with%20Windows">', text)
            self.assertIn("<ID>monet-shared-with-windows</ID>", text)
            self.assertFalse(q.files_place(True, places, files))           # there already
            self.assertTrue(q.files_place(False, places, files))
            self.assertEqual(places.read_text(encoding="utf-8").count("<bookmark"), 1)   # only KDE's Home left
            self.assertIn("<title>Home</title>", places.read_text(encoding="utf-8"))
        session = (ROOT / "linux/libexec/monet-session").read_text(encoding="utf-8")
        self.assertIn('[ -z "$GUEST" ] && "$LIBEXECDIR/monet-quick" files-place', session)

    def test_files_status_bar_keeps_its_words(self):
        # Files' small status bar keeps two splitters' width of margin and a character's room:
        # Kvantum's 7 cut "9 folders" to "9 f…ers", once the glass app style really applied.
        for theme in ("Monet", "MonetDark", "MonetMatte", "MonetDarkMatte", "MonetSolid", "MonetDarkSolid"):
            self.assertIn("\nsplitter_width=2\n", (SHARE / "Kvantum" / theme / f"{theme}.kvconfig").read_text(), theme)
        # The Sound widget is placed only where it's there: without it the speaker went too.
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertIn('[ -d "$DATADIR/plasma/plasmoids/org.monet.sound" ]', look)
        # Num Lock on for a desktop's number pad, as in Windows; laptops left alone (KDE: 0 = on).
        self.assertIn("    desktop|server) kw_default kcminputrc Keyboard NumLock 0 ;;", look)
        # Documents and the text editor keep their menus behind the toolbar's ≡, as Files and the
        # terminal do (seen in the VM); the Calculator has no ≡, so it keeps its menu bar.
        self.assertIn("kw_default okularrc MainWindow MenuBar Disabled\n", look)
        self.assertIn('kw_default katerc General "Show Menu Bar" false\n', look)
        self.assertNotIn("kcalcrc", look)

    def test_files_leaves_out_the_systems_own_drives(self):
        # An unnamed drive with a full red bar (the read-only system root), "boot" and "monet".
        q = self.q
        with tempfile_dir() as tmp:
            places = Path(tmp) / "user-places.xbel"
            self.assertFalse(q.hide_system_root(places))                  # KDE's own list first
            places.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<xbel>\n</xbel>\n', encoding="utf-8")
            self.assertTrue(q.hide_system_root(places))
            text = places.read_text(encoding="utf-8")
            self.assertIn("<UDI>/org/kde/fstab/overlay/</UDI>", text)
            self.assertIn("<IsHidden>true</IsHidden>", text)
            ET.fromstring(text)
            self.assertFalse(q.hide_system_root(places))                  # once: shown again, it stays
        self.assertIn("        hide_system_root()", (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8"))
        rules = (ROOT / "linux/udev/90-monet-system.rules").read_text()
        self.assertIn('ENV{ID_FS_TYPE}=="btrfs|crypto_LUKS", ENV{ID_FS_LABEL}=="monet", ENV{UDISKS_IGNORE}="1"', rules)

    def test_files_monet_and_windows_know_it(self):
        entry = (ROOT / "linux/share/applications/monet-windows-program.desktop").read_text()
        self.assertIn("MimeType=application/x-ms-dos-executable;application/x-msdownload;", entry)
        self.assertIn("NoDisplay=true", entry)
        menu = (ROOT / "linux/share/kio/servicemenus/monet-windows-program.desktop").read_text()
        self.assertIn("Exec=@LIBEXECDIR@/monet-quick program-here %f", menu)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn("monet-windows-program.desktop application/x-ms-dos-executable", install)
        self.assertIn('"$SRC/share/kio/servicemenus/monet-windows-program.desktop"', install)
        self.assertIn(" umu-launcher ", (ROOT / "image/Containerfile").read_text())
        quick = (PLASMA / "plasmoids/org.monet.quick/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn('if (asked[0] === "program") {\n                program.open()', quick)
        sheet = (PLASMA / "plasmoids/org.monet.quick/contents/ui/WindowsProgram.qml").read_text(encoding="utf-8")
        for line in ('ask("program-here", () => {})', 'ask("program-windows", (out, code, err) => {',
                     'readonly property bool canWindows: info.windows === "ok"'):
            self.assertIn(line, sheet)
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        self.assertIn('let folder = PathBuf::from(format!("{drive}\\\\Shared with Monet"));', bridge)
        self.assertIn('"*S-1-5-11:(OI)(CI)M", "/T"', bridge)                                  # Windows' accounts write there
        self.assertIn("std::thread::spawn(open_shared_folders);", bridge)
        trip = bridge[bridge.index('if id.starts_with("program:") || id.starts_with("app:") {'):
                      bridge.index("// A game in the shared Games folder whose launcher")]
        self.assertIn("run_as_person(&pending)", trip)
        self.assertNotIn("launch(", trip.replace("launch task", ""))                      # never as administrator
        self.assertIn('"program"', (ROOT / "crates/monet-core/src/games.rs").read_text())


class AGuest(unittest.TestCase):
    """After 0.9.3: a Guest account that leaves nothing behind (monet-guest)."""

    def test_the_guests_home_is_only_ever_the_guests(self):
        if not hasattr(os, "geteuid"):
            self.skipTest("pwd")
        g = libexec_helper("monet-guest")

        class Entry:
            def __init__(self, home):
                self.pw_dir = home
        homes = Path("/var/home")
        self.assertEqual(g.safe_home(Entry("/var/home/guest"), homes), Path("/var/home/guest").resolve())
        for bad in ("/", "/var/home", "/var/home/ann", "/etc/guest", "/var/home/guest/../ann"):
            self.assertIsNone(g.safe_home(Entry(bad), homes), bad)
        # Only the account monet-guest added (its uid noted): never someone's own called guest.
        from unittest import mock
        someone = mock.Mock(pw_uid=1003, pw_dir="/var/home/guest")
        with tempfile_dir() as tmp, mock.patch.object(g, "MARK", Path(tmp) / "guest"), \
                mock.patch.object(g, "account", lambda: someone), mock.patch.object(g, "run", lambda *a, **k: True):
            self.assertIsNone(g.guest())
            self.assertEqual(g.turn_on(), 1)                    # refused, and nothing removed
            self.assertEqual(g.wipe(), 0)
            g.MARK.write_text("1003\n")
            self.assertIs(g.guest(), someone)
        script = (ROOT / "linux/libexec/monet-guest").read_text(encoding="utf-8")
        self.assertIn('st.st_ino == 256', script)                # subvolumes they made inside go first
        self.assertIn('run("loginctl", "disable-linger", GUEST)', script)
        self.assertIn('"org.freedesktop.login1.set-self-linger" && subject.user == "guest"',
                      (ROOT / "linux/polkit/49-monet.rules").read_text())

    def test_a_guest_signs_in_without_a_password_and_asks_for_admins(self):
        script = (ROOT / "linux/libexec/monet-guest").read_text(encoding="utf-8")
        self.assertIn('run("passwd", "-d", GUEST)', script)
        self.assertIn('dropin.write_text(f"[Service]\\nExecStopPost=+{LIBEXECDIR}/monet-guest wipe\\n")', script)
        self.assertIn('run("btrfs", "subvolume", "create", new)', script)    # kept out of earlier versions
        # Built root's only under another name, then given to the guest; the old one aside first.
        wipe = script[script.index("def wipe("):script.index("def turn_on(")]
        self.assertLess(wipe.index("put_aside(home)"), wipe.index("fresh(home"))
        self.assertLess(wipe.index("fresh(home"), wipe.index("remove(left)"))
        self.assertIn("leftovers(entry.pw_uid)", wipe)
        self.assertIn('if not run("userdel", GUEST):', script)
        # Nothing of theirs keeps running after they sign out, and su never becomes them.
        logind = (ROOT / "linux/systemd/logind-monet-guest.conf").read_text()
        self.assertIn("KillUserProcesses=yes\nKillOnlyUsers=guest\n", logind)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('install -D -m 644 "$SRC/systemd/logind-monet-guest.conf" "$logind/50-monet-guest.conf"', install)
        self.assertIn("pam_succeed_if.so user != guest quiet' /etc/pam.d/su", install)
        self.assertIn("/etc/systemd/logind.conf.d/50-monet-guest.conf", (ROOT / "linux/uninstall.sh").read_text())
        self.assertIn('run("restorecon", "-RF", home)', script)
        # Never wiped while they're signed in.
        wipe = script[script.index("def wipe("):script.index("def turn_on(")]
        self.assertLess(wipe.index("signed_in(entry.pw_uid)"), wipe.index("pkill"))
        rule = (ROOT / "linux/polkit/49-monet.rules").read_text()
        self.assertIn('subject.local && subject.active && subject.user != "guest"', rule)
        unit = (ROOT / "linux/systemd/monet-guest-wipe.service").read_text()
        for line in ("ConditionPathExists=/var/lib/monet/guest", "Before=display-manager.service plasmalogin.service",
                     "ExecStart=@LIBEXECDIR@/monet-guest wipe"):
            self.assertIn(line, unit)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn('put 755 "$SRC/libexec/monet-guest" "$LIBEXECDIR/monet-guest"', install)
        self.assertEqual(install.count("systemctl enable monet-guest-wipe.service"), 2)
        # Monet's polkit list never has it: turning it on asks for an administrator's password.
        programs = install[install.index('programs="['):install.index('install -d -m 755 /etc/polkit-1/rules.d')]
        self.assertNotIn("monet-guest", programs)
        quick = quick_helper()
        from unittest import mock
        with mock.patch.object(quick, "run", lambda *a, **k: '{"on": true}'):
            self.assertEqual(quick.guest_state(), {"on": True})
        # Called Guest in the language Settings speaks, on the sign-in screen too.
        self.assertIn('name = [tr("Guest").encode().hex()] if cmd == "guest-on" else []', (ROOT / "linux/libexec/monet-quick").read_text())
        self.assertIn('if not 0 < len(name) <= 32 or any(c in name for c in ":,\\\\")', script)
        settings = (SETTINGS_QML).read_text(encoding="utf-8")
        self.assertIn("sheet.people.filter(p => !p.you && !p.guest)", settings)
        # Nothing of Windows for a guest: not its games, not its notes.
        with tempfile_dir() as tmp:
            games = Path(tmp) / "games.json"
            games.write_text(json.dumps({"v": 1, "games": [{"id": "riot:valorant", "name": "VALORANT"}]}))
            with mock.patch.object(quick.getpass, "getuser", lambda: "guest"):
                self.assertEqual(quick.windows_games([games]), [])
            with mock.patch.object(quick.getpass, "getuser", lambda: "ann"):
                self.assertEqual(len(quick.windows_games([games])), 1)
        session = (ROOT / "linux/libexec/monet-session").read_text(encoding="utf-8")
        self.assertIn('[ -z "$GUEST" ] && "$BINDIR/monet" shortcuts', session)
        self.assertIn('if [ -z "$GUEST" ] && [ "$(cat /var/lib/monet/windows-setup', session)
        self.assertIn('sheet.ask(on ? "guest-on" : "guest-off", out => {', settings)


class OneDrive(unittest.TestCase):
    """Settings → Storage → OneDrive: rclone signs in once in the browser and mounts it in Files."""

    def setUp(self):
        self.q = quick_helper()

    def test_rclones_questions_take_their_defaults_and_the_browser(self):
        answer = self.q.onedrive_answer
        self.assertEqual(answer({"Name": "config_is_local", "Default": False}), "true")   # the browser here
        self.assertEqual(answer({"Name": "region", "Default": "global"}), "global")
        self.assertEqual(answer({"Name": "config_driveid", "Default": True}), "true")
        self.assertEqual(answer({"Name": "x", "Default": False}), "false")
        self.assertEqual(answer({}), "")

    def test_connecting_follows_rclones_steps_then_mounts_it_and_adds_the_place(self):
        from unittest import mock
        q = self.q
        steps = [{"State": "*oauth-islocal,teams,,", "Option": {"Name": "config_is_local", "Default": True}},
                 {"State": "*oauth-done,choose_type", "Option": {"Name": "config_type", "Default": "onedrive"}},
                 {"State": "", "Option": None}]
        asked, remotes, ran, placed = [], [], [], []

        def ask(args):
            asked.append(args)
            step = steps[len(asked) - 1]
            if not step["State"]:
                remotes.append("OneDrive:")
            return json.dumps(step)
        with tempfile_dir() as tmp, mock.patch.object(q.shutil, "which", lambda name: "/usr/bin/" + name):
            q.ONEDRIVE_DIR = Path(tmp) / "OneDrive"
            q.onedrive_remotes = lambda: list(remotes)
            q.run = lambda *args, **kw: ran.append(args) or ""
            q.files_place = lambda *args, **kw: placed.append((args, kw)) or True
            self.assertTrue(q.onedrive_connect(ask))
            self.assertTrue(q.ONEDRIVE_DIR.is_dir())
        self.assertEqual(asked[0], ["rclone", "config", "create", "OneDrive", "onedrive", "--non-interactive"])
        self.assertEqual(asked[1], ["rclone", "config", "update", "OneDrive", "--continue", "--state",
                                    "*oauth-islocal,teams,,", "--result", "true", "--non-interactive"])
        self.assertEqual(asked[2][asked[2].index("--result") + 1], "onedrive")
        self.assertIn(("systemctl", "--user", "enable", "--now", "monet-onedrive.service"), ran)
        self.assertEqual(placed[0][0], (True,))
        self.assertEqual(placed[0][1]["place_id"], "monet-onedrive")
        self.assertEqual(placed[0][1]["title"], "OneDrive")

    def test_a_sign_in_that_fails_leaves_nothing_on(self):
        from unittest import mock
        q = self.q
        ran = []
        with mock.patch.object(q.shutil, "which", lambda name: "/usr/bin/" + name):
            q.onedrive_remotes = lambda: []
            q.run = lambda *args, **kw: ran.append(args) or ""
            self.assertFalse(q.onedrive_connect(lambda args: json.dumps({"Error": "the browser was closed"})))
            self.assertFalse(q.onedrive_connect(lambda args: "not json"))
        with mock.patch.object(q.shutil, "which", lambda name: None):
            self.assertFalse(q.onedrive_connect(lambda args: self.fail("asked without rclone")))
            self.assertEqual(q.onedrive_state()["here"], False)
        self.assertEqual(ran, [])
        # Cancelled while the browser waited: rclone stops without a word, and what it kept goes.
        answers = iter([json.dumps({"State": "*oauth-islocal,teams,,", "Option": {"Name": "config_is_local"}}), None])
        with mock.patch.object(q.shutil, "which", lambda name: "/usr/bin/" + name):
            q.onedrive_remotes = lambda: ["OneDrive:"]
            self.assertFalse(q.onedrive_connect(lambda args: next(answers)))
        self.assertEqual(ran, [("rclone", "config", "delete", "OneDrive")])
        ran.clear()
        q.ok = lambda *args, **kw: ran.append(args) or True
        self.assertTrue(q.onedrive_cancel())
        self.assertEqual(ran[0][:4], ("pkill", "-u", q.getpass.getuser(), "-f"))
        self.assertEqual(ran[0][4], "^rclone config (create|update) OneDrive ")
        settings = SETTINGS_QML.read_text(encoding="utf-8")
        self.assertIn('sheet.ask("onedrive-cancel", () => {})', settings)

    def test_disconnecting_stops_the_mount_and_takes_the_place_away(self):
        q = self.q
        ran, placed = [], []
        with tempfile_dir() as tmp:
            q.ONEDRIVE_DIR = Path(tmp) / "OneDrive"
            q.ONEDRIVE_DIR.mkdir()
            q.onedrive_remotes = lambda: []
            q.run = lambda *args, **kw: ran.append(args) or ""
            q.files_place = lambda *args, **kw: placed.append((args, kw)) or True
            self.assertTrue(q.onedrive_disconnect())
            self.assertFalse(q.ONEDRIVE_DIR.exists())             # only the empty folder it was mounted on
        self.assertIn(("systemctl", "--user", "disable", "--now", "monet-onedrive.service"), ran)
        self.assertIn(("rclone", "config", "delete", "OneDrive"), ran)
        self.assertEqual((placed[0][0], placed[0][1]["place_id"]), ((False,), "monet-onedrive"))

    def test_its_place_in_files_is_its_own(self):
        q = self.q
        with tempfile_dir() as tmp:
            places, cloud = Path(tmp) / "user-places.xbel", Path("/home/ann/OneDrive")
            places.write_text('<?xml version="1.0" encoding="UTF-8"?>\n<xbel>\n <bookmark href="file:///home/ann">\n'
                              '  <title>Home</title>\n </bookmark>\n</xbel>\n', encoding="utf-8")
            self.assertTrue(q.files_place(True, places, Path("/run/media/Shared with Windows")))
            self.assertTrue(q.files_place(True, places, cloud, place_id="monet-onedrive", title="OneDrive",
                                          icon="folder-cloud"))
            text = places.read_text(encoding="utf-8")
            self.assertIn('<bookmark href="file:///home/ann/OneDrive">', text)
            self.assertIn("<title>OneDrive</title>", text)
            self.assertIn('<bookmark:icon name="folder-cloud"/>', text)
            self.assertTrue(q.files_place(False, places, cloud, place_id="monet-onedrive"))
            text = places.read_text(encoding="utf-8")
            self.assertNotIn("monet-onedrive", text)
            self.assertIn("<ID>monet-shared-with-windows</ID>", text)   # the shared folder stays

    def test_the_mount_comes_with_each_sign_in(self):
        unit = (ROOT / "linux/systemd/user/monet-onedrive.service").read_text(encoding="utf-8")
        self.assertIn("ConditionPathExists=%h/.config/rclone/rclone.conf", unit)
        self.assertIn("Type=notify", unit)
        self.assertIn("ExecStart=/usr/bin/rclone mount OneDrive: %h/OneDrive --vfs-cache-mode full", unit)
        self.assertIn("ExecStop=/usr/bin/fusermount3 -u %h/OneDrive", unit)
        self.assertIn('put 644 "$SRC/systemd/user/monet-onedrive.service"',
                      (ROOT / "linux/install.sh").read_text(encoding="utf-8"))
        uninstall = (ROOT / "linux/uninstall.sh").read_text(encoding="utf-8")
        self.assertIn("monet-onedrive.service >/dev/null", uninstall)
        self.assertIn("/etc/systemd/user/monet-onedrive.service", uninstall)
        self.assertRegex((ROOT / "image/Containerfile").read_text(encoding="utf-8"), r"tpm2-tss rclone")
        settings = SETTINGS_QML.read_text(encoding="utf-8")
        self.assertIn('ask("onedrive", out => sheet.oneDrive = sheet.json(out, sheet.oneDrive))', settings)
        self.assertIn('sheet.ask("onedrive-" + what, out => {', settings)
        quick = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        for cmd in ('"onedrive"', '"onedrive-connect"', '"onedrive-disconnect"'):
            self.assertIn(f"elif cmd == {cmd}:", quick)


def start_menu_shortcut(target="", env="", darwin=False):
    """A Windows shortcut (.lnk) as Windows writes one: the target in its LinkInfo, or only in
    the block kept with environment variables, or neither (an installer's advertised one)."""
    u32 = lambda n: n.to_bytes(4, "little")
    data = bytearray(u32(0x4C) + bytes(16) + u32(0x80 | (0x02 if target else 0)) + bytes(0x4C - 0x18))
    if target:
        volume = u32(17) + u32(3) + u32(0) + u32(16) + b"\0"
        ansi = target.encode("cp1252") + b"\0"
        wide = target.encode("utf-16-le") + b"\0\0"
        base = 0x24 + len(volume)
        offsets = [0x24, base, 0, base + len(ansi), base + len(ansi) + 1,
                   base + len(ansi) + 1 + len(wide)]
        rest = volume + ansi + b"\0" + wide + b"\0\0"
        info = u32(0x24 + len(rest)) + u32(0x24) + u32(1) + b"".join(u32(o) for o in offsets) + rest
        data += info
    if env:
        data += u32(0x314) + u32(0xA0000001) + env.encode("cp1252").ljust(260, b"\0") + env.encode("utf-16-le").ljust(520, b"\0")
    if darwin:
        data += u32(0x314) + u32(0xA0000006) + bytes(0x314 - 8)
    return bytes(data + u32(0))


def windows_program_with(icon, width=32, bits=32):
    """A tiny Windows program (PE32+) whose resources hold one icon group with one icon."""
    u16, u32 = (lambda n: n.to_bytes(2, "little")), (lambda n: n.to_bytes(4, "little"))
    group = u16(0) + u16(1) + u16(1) + bytes([width % 256, width % 256, 0, 0]) + u16(1) + u16(bits) + u32(len(icon)) + u16(1)

    def folder(*entries):
        return bytes(12) + u16(0) + u16(len(entries)) + b"".join(u32(i) + u32(o) for i, o in entries)
    rva = 0x1000
    tree = (folder((3, 0x80000000 | 32), (14, 0x80000000 | 56)) + folder((1, 0x80000000 | 80)) + folder((1, 0x80000000 | 104))
            + folder((0x409, 128)) + folder((0x409, 144))
            + u32(rva + 160) + u32(len(icon)) + bytes(8) + u32(rva + 160 + len(icon)) + u32(len(group)) + bytes(8)
            + icon + group)
    optional = bytearray(240)
    optional[0:2] = u16(0x20B)
    optional[128:136] = u32(rva) + u32(len(tree))
    section = b".rsrc\0\0\0" + u32(len(tree)) + u32(rva) + u32(len(tree)) + u32(0x200) + bytes(16)
    head = b"MZ" + bytes(0x3A) + u32(0x40) + b"PE\0\0" + u16(0x8664) + u16(1) + bytes(12) + u16(240) + u16(0x22)
    head += bytes(optional) + section
    return head.ljust(0x200, b"\0") + tree


class WindowsApps(unittest.TestCase):
    """The backlog's item 9: the apps in Windows' Start menu (Word, Photoshop) in Monet's app
    menu and search, each opening in Windows, where it is."""

    def setUp(self):
        self.q = quick_helper()
        self.drive = libexec_helper("monet-windows-drive")

    def test_a_shortcut_says_where_it_leads(self):
        target = self.drive.shortcut_target
        word = r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"
        self.assertEqual(target(start_menu_shortcut(word)), word)
        self.assertEqual(target(start_menu_shortcut(env=r"%ProgramFiles%\Tool\tool.exe")), r"%ProgramFiles%\Tool\tool.exe")
        self.assertEqual(target(start_menu_shortcut(darwin=True)), "")       # advertised: not followed
        self.assertEqual(target(b"not a shortcut"), "")
        self.assertEqual(target(start_menu_shortcut(word)[:0x60]), "")       # cut short

    def test_a_programs_own_icon_comes_out_as_a_png(self):
        import io
        png = b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + bytes(17)
        self.assertEqual(self.drive.program_icon(io.BytesIO(windows_program_with(png, 0))), png)
        self.assertIsNone(self.drive.program_icon(io.BytesIO(b"MZ" + bytes(200))))
        self.assertIsNone(self.drive.program_icon(io.BytesIO(windows_program_with(png)[:0x150])))
        try:
            from PIL import Image
        except ImportError:
            return
        # A bitmap icon (what older programs keep): 16 x 16, 32 bits, with its mask.
        bitmap = ((40).to_bytes(4, "little") + (16).to_bytes(4, "little") + (32).to_bytes(4, "little")
                  + (1).to_bytes(2, "little") + (32).to_bytes(2, "little") + bytes(24)
                  + bytes([200, 100, 50, 255]) * 256 + bytes(64))
        made = self.drive.program_icon(io.BytesIO(windows_program_with(bitmap, 16)))
        self.assertEqual(made[:4], b"\0\0\1\0")                       # as an .ico, not decoded here
        self.assertEqual(Image.open(io.BytesIO(self.drive.png_of(made))).size, (16, 16))
        self.assertIsNone(self.drive.png_of(b"\0\0\1\0junk"))
        self.assertEqual(self.drive.png_of(png), png)

    @unittest.skipUnless(hasattr(os, "fork"), "Unix processes")
    def test_icons_are_decoded_by_the_person_never_root(self):
        d = self.drive
        self.assertEqual(d.as_person(os.getuid(), os.getgid(), lambda b: b[::-1] if b else None, [b"ab", None, b"c"]),
                         [b"ba", None, b"c"])
        self.assertEqual(d.as_person(os.getuid(), os.getgid(), lambda b: 1 / 0, [b"x", b"y"]), [None, None])
        script = (ROOT / "linux/libexec/monet-windows-drive").read_text(encoding="utf-8")
        self.assertIn("as_person(uid, gid, png_of, [a[\"icon\"] for a in found])", script)
        self.assertNotIn("PIL", script.split("def png_of", 1)[0])           # Pillow only in png_of

    @unittest.skipUnless(hasattr(os, "geteuid"), "Unix files")
    def test_your_start_menu_comes_over_without_windows_own_tools_or_games(self):
        d = self.drive
        png = b"\x89PNG\r\n\x1a\n" + b"\0\0\0\rIHDR" + bytes(17)
        with tempfile_dir() as tmp:
            root, home = Path(tmp) / "drive", Path(tmp) / "home"
            ann = root / "Users/Ann"
            (ann).mkdir(parents=True)
            (ann / "NTUSER.DAT").write_bytes(b"regf")
            word = root / "Program Files/Microsoft Office/root/Office16/WINWORD.EXE"
            word.parent.mkdir(parents=True)
            word.write_bytes(windows_program_with(png, 0))
            tool = root / "Program Files/Tool/tool.exe"
            tool.parent.mkdir(parents=True)
            tool.write_bytes(b"MZ")
            mine = ann / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs"
            everyone = root / "ProgramData/Microsoft/Windows/Start Menu/Programs"
            links = {mine / "Word.lnk": start_menu_shortcut(r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"),
                     everyone / "Word.lnk": start_menu_shortcut(r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"),
                     everyone / "Tools/Tool.lnk": start_menu_shortcut(env=r"%ProgramFiles%\Tool\tool.exe"),
                     everyone / "Adobe Photoshop 2025.lnk": start_menu_shortcut(r"D:\Adobe\Photoshop.exe"),
                     everyone / "Tools/Uninstall Tool.lnk": start_menu_shortcut(r"C:\Program Files\Tool\unins000.exe"),
                     everyone / "Gone.lnk": start_menu_shortcut(r"C:\Program Files\Gone\gone.exe"),
                     everyone / "Steam/Steam.lnk": start_menu_shortcut(r"C:\Program Files (x86)\Steam\steam.exe"),
                     everyone / "Microsoft Edge.lnk": start_menu_shortcut(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
                     everyone / "Accessibility/Magnify.lnk": start_menu_shortcut(env=r"%windir%\system32\magnify.exe"),
                     everyone / "Notepad.lnk": start_menu_shortcut(r"C:\Windows\notepad.exe"),
                     everyone / "Help.lnk": start_menu_shortcut(r"C:\Program Files\Tool\help.exe"),
                     everyone / "Office.lnk": start_menu_shortcut(darwin=True)}
            for path, data in links.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
            # The Store's apps, as Monet Bridge lists them, and one's own logo in its package.
            (root / "Games/.monet").mkdir(parents=True)
            (root / "Games/.monet/store-apps.json").write_text(json.dumps([
                {"name": "WhatsApp", "id": "5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"},
                {"name": "Photos", "id": "Microsoft.Windows.Photos_8wekyb3d8bbwe!App"},
                {"name": "Settings", "id": "windows.immersivecontrolpanel_cw5n1h2txyewy!microsoft.windows.immersivecontrolpanel"},
                {"name": "Word", "id": "Microsoft.Office.Word_8wekyb3d8bbwe!Word"},
                {"name": "Bad", "id": "../../etc!x"}]))
            package = root / "Program Files/WindowsApps/5319275A.WhatsAppDesktop_2.2443.3.0_x64__cv1g1gvanyjgm"
            (package / "Assets").mkdir(parents=True)
            (root / "Program Files/WindowsApps/5319275A.WhatsAppDesktop_2.24.1.0_x64__cv1g1gvanyjgm").mkdir()
            (package / "AppxManifest.xml").write_text(
                '<Package><Applications><Application Id="App" Executable="WhatsApp.exe">'
                '<uap:VisualElements DisplayName="WhatsApp" Square150x150Logo="Assets\\Square150x150Logo.png" '
                'Square44x44Logo="Assets\\AppList.png"/></Application></Applications></Package>')
            unplated = png + b"unplated"
            for name, data in (("AppList.scale-100.png", png + b"44"), ("AppList.targetsize-256.png", png + b"256"),
                               ("AppList.targetsize-256_altform-unplated.png", unplated),
                               ("AppList.targetsize-16_altform-unplated.png", png + b"16")):
                (package / "Assets" / name).write_bytes(data)
            apps = d.windows_apps(root, "ann")
            self.assertEqual([(a["id"], a["name"]) for a in apps],
                             [("app:adobe-photoshop-2025", "Adobe Photoshop 2025"), ("app:tools-tool", "Tool"),
                              ("app:5319275a-whatsappdesktop-cv1g1gvanyjgm-app", "WhatsApp"), ("app:word", "Word")])
            self.assertEqual([bool(a["icon"]) for a in apps], [False, False, True, True])   # Photoshop's drive isn't here
            self.assertEqual(apps[2]["icon"], unplated)                     # the biggest unplated logo, newest package
            person = ("ann", os.getuid(), os.getgid(), home)
            self.assertEqual(d.bring_apps(root, person), 4)
            listed = json.loads((home / d.APPS_JSON).read_text(encoding="utf-8"))
            self.assertEqual(listed[3], {"id": "app:word", "name": "Word", "icon": True})
            icons = home / d.APPS_ICONS
            self.assertEqual((icons / "monet-windows-app-word.png").read_bytes(), png)
            (icons / "monet-windows-app-old.png").write_bytes(png)
            (icons / "someone-elses.png").write_bytes(png)
            d.bring_apps(root, person)
            self.assertEqual(sorted(p.name for p in icons.iterdir()),
                             ["monet-windows-app-5319275a-whatsappdesktop-cv1g1gvanyjgm-app.png",
                              "monet-windows-app-word.png", "someone-elses.png"])
        script = (ROOT / "linux/libexec/monet-windows-drive").read_text(encoding="utf-8")
        self.assertIn("apps = bring_apps(DRIVE, person)", script)

    def test_the_app_menu_gets_an_entry_for_each_unless_monet_has_it(self):
        from unittest import mock
        q = self.q
        with tempfile_dir() as tmp:
            listed, apps = Path(tmp) / "windows-apps.json", Path(tmp) / "applications"
            listed.write_text(json.dumps([{"id": "app:word", "name": "Word", "icon": True},
                                          {"id": "app:discord", "name": "Discord", "icon": True},
                                          {"id": "app:adobe-photoshop-2025", "name": "Adobe Photoshop 2025", "icon": False},
                                          {"id": "app:../evil", "name": "Evil"}, {"id": "app:x", "name": " \n "}]))
            apps.mkdir()
            (apps / "monet-windows-app-uninstalled.desktop").write_text("[Desktop Entry]\n")
            q.menu_entries = lambda: [("com.discordapp.Discord.desktop", {"Name": "Discord"}),
                                      ("monet-windows-app-word.desktop", {"Name": "Word"})]
            with mock.patch.object(q.getpass, "getuser", lambda: "ann"):
                self.assertEqual(q.windows_apps_menu(listed, apps), 2)
            self.assertEqual(sorted(p.name for p in apps.iterdir()),
                             ["monet-windows-app-adobe-photoshop-2025.desktop", "monet-windows-app-word.desktop"])
            word = q.desktop_entry((apps / "monet-windows-app-word.desktop").read_text(encoding="utf-8"))
            self.assertEqual(word["Exec"], f"{q.LIBEXECDIR}/monet-quick windows-app app:word")
            self.assertEqual((word["Icon"], word["Categories"]), ("monet-windows-app-word", "Office;X-Monet-Windows-Apps;"))
            photoshop = q.desktop_entry((apps / "monet-windows-app-adobe-photoshop-2025.desktop").read_text(encoding="utf-8"))
            self.assertEqual((photoshop["Icon"], photoshop["Categories"]), ("monet-windows", "Graphics;X-Monet-Windows-Apps;"))
            with mock.patch.object(q.getpass, "getuser", lambda: "guest"):
                self.assertEqual(q.windows_apps_menu(listed, apps), 0)

    def test_choosing_one_asks_on_monets_sheet_before_the_restart(self):
        from unittest import mock
        q = self.q
        with tempfile_dir() as tmp:
            apps = Path(tmp) / "applications"
            apps.mkdir()
            (apps / "monet-windows-app-word.desktop").write_text(
                "[Desktop Entry]\nName=Word\nIcon=monet-windows-app-word\n", encoding="utf-8")
            q.PROGRAM_PENDING = Path(tmp) / "monet-program.json"
            rang = []
            q.doorbell = lambda words: rang.append(words) or True
            self.assertTrue(q.windows_app("app:word", apps))
            self.assertFalse(q.windows_app("app:nothing-here", apps))
            self.assertFalse(q.windows_app("steam:440", apps))
            self.assertEqual(rang, ["program"])
            self.assertEqual(q.program_info(), {"app": "app:word", "name": "Word", "icon": "monet-windows-app-word",
                                                "here": False, "windows": "ok"})
            q.doorbell = lambda words: False                       # no Quick Settings: Monet's own question
            with mock.patch.object(q.subprocess, "Popen") as popen:
                q.windows_app("app:word", apps)
            self.assertEqual(popen.call_args[0][0], [f"{q.BINDIR}/monet", "play", "app:word", "--confirm"])
        sheet = (PLASMA / "plasmoids/org.monet.quick/contents/ui/WindowsProgram.qml").read_text(encoding="utf-8")
        self.assertIn('readonly property bool app: (info.app || "") !== ""', sheet)
        self.assertIn("sun: sheet.app", sheet)
        quick = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn('game = info["app"] if info.get("app") else program_windows(info["path"]) if info else None', quick)
        session = (ROOT / "linux/libexec/monet-session").read_text(encoding="utf-8")
        self.assertIn('"$LIBEXECDIR/monet-quick" windows-files; "$LIBEXECDIR/monet-quick" windows-apps', session)
        monet = (ROOT / "crates/monet/src/main.rs").read_text(encoding="utf-8")
        self.assertIn('(None, Some(_), _) if app => t!("Open in Windows?")', monet)
        bridge = (ROOT / "crates/monet-bridge/src/bridge.rs").read_text(encoding="utf-8")
        self.assertIn('Some("app") => scan_apps(),', bridge)
        # The Store's apps: listed as the person at each sign-in, opened by their app id.
        self.assertIn("std::thread::spawn(list_store_apps);", bridge)
        self.assertIn('args: vec![format!("shell:AppsFolder\\\\{app}")]', bridge)
        self.assertIn('const STORE_APPS: &str = ".monet\\\\store-apps.json";', bridge)
        self.assertIn('STORE_APPS = "Games/.monet/store-apps.json"',
                      (ROOT / "linux/libexec/monet-windows-drive").read_text(encoding="utf-8"))
        self.assertIn('"app"]', (ROOT / "crates/monet-core/src/games.rs").read_text(encoding="utf-8"))
        uninstall = (ROOT / "linux/uninstall.sh").read_text(encoding="utf-8")
        self.assertIn("applications/monet-windows-app-*.desktop", uninstall)


STORE_CATALOG = """<?xml version="1.0" encoding="UTF-8"?>
<components version="0.8" origin="flathub">
  <component type="desktop-application">
    <id>org.gimp.GIMP</id>
    <name>GNU Image Manipulation Program</name>
    <name xml:lang="sv">GNU-bildmanipuleringsprogram</name>
    <summary>Create images and edit photographs</summary>
    <summary xml:lang="sv">Skapa bilder och redigera fotografier</summary>
    <description><p>GIMP is an <em>image</em> editor.</p><ul><li>Layers</li><li>Brushes</li></ul></description>
    <description xml:lang="sv"><p>GIMP är en bildredigerare.</p></description>
    <developer id="org.gimp"><name>The GIMP team</name></developer>
    <project_license>GPL-3.0+</project_license>
    <categories><category>Graphics</category></categories>
    <keywords><keyword>photoshop</keyword></keywords>
    <keywords xml:lang="sv"><keyword>bildredigering</keyword></keywords>
    <icon type="cached" width="128" height="128">org.gimp.GIMP.png</icon>
    <screenshots>
      <screenshot><caption>Second</caption><image type="source">https://example.org/2.png</image></screenshot>
      <screenshot type="default"><caption>First</caption><caption xml:lang="sv">Första</caption>
        <image type="thumbnail" width="624">https://example.org/1-small.png</image>
        <image type="thumbnail" width="1248">https://example.org/1-big.png</image>
        <image type="source">https://example.org/1.png</image></screenshot>
    </screenshots>
    <releases><release version="3.0.4" timestamp="1700000000"/></releases>
    <url type="homepage">https://www.gimp.org/</url>
    <launchable type="desktop-id">org.gimp.GIMP.desktop</launchable>
    <bundle type="flatpak">app/org.gimp.GIMP/x86_64/stable</bundle>
    <custom><value key="flathub::verification::verified">true</value></custom>
  </component>
  <component type="desktop-application">
    <id>org.kde.krita.desktop</id>
    <name>Krita</name>
    <summary>Digital painting</summary>
    <project_license>LicenseRef-proprietary</project_license>
    <categories><category>Graphics</category></categories>
    <bundle type="flatpak">app/org.kde.krita/x86_64/stable</bundle>
  </component>
  <component type="runtime">
    <id>org.gnome.Platform</id>
    <bundle type="flatpak">runtime/org.gnome.Platform/x86_64/47</bundle>
  </component>
  <component type="desktop-application">
    <id>com.example.Blocked</id>
    <name>Blocked</name>
    <bundle type="flatpak">app/com.example.Blocked/x86_64/stable</bundle>
  </component>
  <component type="desktop-application">
    <id>notanid</id>
    <name>Odd</name>
    <bundle type="flatpak">app/notanid/x86_64/stable</bundle>
  </component>
</components>
"""


class OurOwnStore(unittest.TestCase):
    """The Store is Monet's own window over Flathub's catalog, with the apps in your Windows."""

    def setUp(self):
        self.store = libexec_helper("monet-store")

    def catalog(self, langs, blocked=frozenset()):
        with tempfile_dir() as tmp:
            folder = Path(tmp)
            (folder / "appstream.xml").write_text(STORE_CATALOG, encoding="utf-8")
            (folder / "icons/128x128").mkdir(parents=True)
            (folder / "icons/128x128/org.gimp.GIMP.png").write_bytes(b"png")
            return self.store.read_catalog(folder, langs, blocked), folder

    def test_the_catalog_in_your_language(self):
        apps, folder = self.catalog(self.store.languages({"LANG": "sv_SE.UTF-8"}), frozenset({"com.example.Blocked"}))
        # Only apps with a Flathub ref and a proper id; nothing blocked, no runtimes.
        self.assertEqual(sorted(apps), ["org.gimp.GIMP", "org.kde.krita"])
        gimp = apps["org.gimp.GIMP"]
        self.assertEqual((gimp["name"], gimp["summary"]), ("GNU-bildmanipuleringsprogram", "Skapa bilder och redigera fotografier"))
        self.assertEqual(gimp["description"], "<p>GIMP är en bildredigerare.</p>")
        self.assertEqual(gimp["keywords"], ["bildredigering", "photoshop"])
        self.assertEqual(gimp["icon"], (folder / "icons/128x128/org.gimp.GIMP.png").as_uri())
        self.assertEqual(gimp["screenshots"][0], {"image": "https://example.org/1-big.png",
                                                  "thumb": "https://example.org/1-small.png", "caption": "Första"})
        self.assertEqual(gimp["screenshots"][1]["image"], "https://example.org/2.png")
        self.assertEqual((gimp["developer"], gimp["verified"], gimp["free"], gimp["version"], gimp["released"]),
                         ("The GIMP team", True, True, "3.0.4", 1700000000))
        self.assertEqual((gimp["launch"], gimp["ref"]), ("org.gimp.GIMP.desktop", "app/org.gimp.GIMP/x86_64/stable"))
        krita = apps["org.kde.krita"]
        self.assertEqual((krita["free"], krita["verified"], krita["launch"]), (False, False, "org.kde.krita.desktop"))
        english, _ = self.catalog([])
        self.assertEqual(english["org.gimp.GIMP"]["description"],
                         "<p>GIMP is an <i>image</i> editor.</p><ul><li>Layers</li><li>Brushes</li></ul>")
        self.assertEqual(english["org.gimp.GIMP"]["keywords"], ["photoshop"])

    def test_languages_nearest_first(self):
        self.assertEqual(self.store.languages({"LANG": "pt_BR.UTF-8"}), ["pt-BR", "pt_BR", "pt"])
        self.assertEqual(self.store.languages({"LANGUAGE": "sv:en", "LANG": "en_US.UTF-8"}), ["sv"])
        self.assertEqual(self.store.languages({"LANG": "C"}), [])

    def test_search_wants_every_word_and_puts_popular_apps_first(self):
        apps, _ = self.catalog([])
        self.assertEqual(self.store.search(apps, "Photoshop", {}), ["org.gimp.GIMP"])
        self.assertEqual(self.store.search(apps, "gimp krita", {}), [])
        self.assertEqual(self.store.search(apps, "   ", {}), [])
        apps["org.kde.krita"]["summary"] = "Digital painting of photos"
        self.assertEqual(self.store.search(apps, "photo", {}), ["org.gimp.GIMP", "org.kde.krita"])
        self.assertEqual(self.store.search(apps, "photo", {"org.kde.krita": 10 ** 6}), ["org.kde.krita", "org.gimp.GIMP"])

    def test_familiar_app_names_suggest_available_apps(self):
        apps, _ = self.catalog([])
        self.assertEqual(self.store.instead("Photoshop", apps), {"name": "Photoshop", "apps": ["org.gimp.GIMP", "org.kde.krita"]})
        self.assertEqual(self.store.instead("phot", apps)["name"], "Photoshop")
        self.assertIsNone(self.store.instead("ph", apps))
        self.assertEqual(self.store.instead("word", apps), {"name": "Microsoft Office", "apps": []})
        for _, _, others in self.store.FAMILIAR_APPS:
            for app_id in others:
                self.assertRegex(app_id, self.store.APP_ID)

    def test_mac_and_nearby_sharing_queries_only_offer_available_suggestions(self):
        apps = {name: {} for name in ("org.libreoffice.LibreOffice", "org.kde.kdenlive",
                                      "org.ardour.Ardour", "org.localsend.localsend_app")}
        for query, expected in (("Pages", "org.libreoffice.LibreOffice"),
                                ("Keynote", "org.libreoffice.LibreOffice"),
                                ("iMovie", "org.kde.kdenlive"),
                                ("Final Cut Pro", "org.kde.kdenlive"),
                                ("GarageBand", "org.ardour.Ardour"),
                                ("AirDrop", "org.localsend.localsend_app"),
                                ("Nearby Sharing", "org.localsend.localsend_app")):
            self.assertEqual(self.store.instead(query, apps)["apps"], [expected])
        self.assertEqual(self.store.instead("AirDrop", {})["apps"], [])
        self.assertIsNone(self.store.instead("pages of documents", apps))

    def test_bazzites_blocklist_for_this_desktop(self):
        with tempfile_dir() as tmp:
            path = Path(tmp) / "blocklist.yaml"
            path.write_text("blocks:\n"
                            "  - priority: 0\n    block:\n      - com.example.Blocked\n      - org.example.Other\n"
                            "  - priority: 1\n    conditions:\n      - match-envvar:\n          var: XDG_CURRENT_DESKTOP\n"
                            "          regex: ^GNOME$\n    block:\n      - org.gnome.Only\n"
                            "  - priority: 2\n    conditions:\n      - match-envvar:\n          var: XDG_CURRENT_DESKTOP\n"
                            "          regex: ^KDE$\n    block:\n      - org.kde.Only\n")
            self.assertEqual(self.store.blocklist(path), {"com.example.Blocked", "org.example.Other", "org.kde.Only"})
            self.assertEqual(self.store.blocklist(Path(tmp) / "missing.yaml"), frozenset())

    def test_the_front_page_is_monets_picks(self):
        rows = self.store.picks(SHARE / "monet/store/content.yaml")
        self.assertEqual([r for r, _ in rows], ["play", "talk", "watch", "work", "everyday"])
        self.assertIn("com.heroicgameslauncher.hgl", rows[0][1])
        for _, apps in rows:
            for app_id in apps:
                self.assertRegex(app_id, self.store.APP_ID)
        for row, _ in rows:
            for light in ("mist", "smoke"):
                self.assertTrue((SHARE / f"monet/store/{row}-{light}.jpg").is_file(), row)

    def test_what_went_wrong_in_plain_words(self):
        self.assertEqual(self.store.trouble("GDBus.Error:org.freedesktop.Flatpak.Error.NotAllowed: Deploy not allowed for user"),
                         "not-allowed")
        self.assertEqual(self.store.trouble("Could not resolve host: dl.flathub.org"), "offline")
        self.assertEqual(self.store.trouble("Something else"), "failed")

    def test_what_an_app_can_reach(self):
        self.assertEqual(self.store.reach("[Application]\nname=org.example.App\n[Context]\nshared=network;ipc;\n"
                                          "devices=dri;all;\nfilesystems=xdg-pictures;home;!host;\n"
                                          "[Session Bus Policy]\norg.freedesktop.Flatpak=talk\n"),
                         ["programs", "home", "devices", "network"])
        self.assertEqual(self.store.reach("[Context]\nfilesystems=xdg-download;\n"), ["folders"])
        self.assertEqual(self.store.reach("[Context]\nfilesystems=host;xdg-download;\n"), ["all-files"])
        self.assertEqual(self.store.reach("[Context]\nshared=ipc;\n"), [])

    def test_only_an_app_goes_in_or_out(self):
        import contextlib
        import io
        for action, ref in (("install", "app/../evil"), ("install", "runtime/org.gnome.Platform/x86_64/47"),
                            ("update", "app/org.gimp.GIMP/x86_64/stable"), ("install", "app/org.gimp.GIMP/x86_64/stable;rm")):
            said = io.StringIO()
            with contextlib.redirect_stdout(said):
                self.assertEqual(self.store.do(action, ref), 2)
            self.assertEqual(json.loads(said.getvalue()), {"error": "not an app"})

    def test_flathubs_installs_kept_a_day(self):
        with tempfile_dir() as tmp:
            cache = Path(tmp) / "store/popular.json"
            asked = []

            def fetch(url):
                asked.append(url)
                return {"hits": [{"app_id": "org.gimp.GIMP", "installs_last_month": 500}, {"app_id": "x", "installs_last_month": "?"}]}

            def offline(url):
                raise OSError("offline")
            self.assertEqual(self.store.popular(cache, fetch, now=1000), {"org.gimp.GIMP": 500})
            self.assertEqual(len(asked), self.store.POPULAR_PAGES)
            self.assertEqual(self.store.popular(cache, offline, now=1000 + 3600), {"org.gimp.GIMP": 500})
            # Older than a day and offline: what was kept, however old.
            self.assertEqual(self.store.popular(cache, offline, now=1000 + 2 * 86400), {"org.gimp.GIMP": 500})
            self.assertEqual(self.store.popular(Path(tmp) / "none.json", offline, now=1000), {})

    def test_whats_on_the_pc(self):
        self.assertEqual(self.store.installed_apps(lambda args: "org.gimp.GIMP\tsystem\nnot an app line\ncom.example.App\tuser\n"),
                         {"org.gimp.GIMP": "system", "com.example.App": "user"})
        with tempfile_dir() as tmp:
            (Path(tmp) / "org.kde.okular.desktop").write_text("[Desktop Entry]\n")
            self.assertTrue(self.store.built_in({"launch": "org.kde.okular.desktop"}, Path(tmp)))
            self.assertFalse(self.store.built_in({"launch": "org.gimp.GIMP.desktop"}, Path(tmp)))
            listed = Path(tmp) / "windows-apps.json"
            listed.write_text(json.dumps([{"id": "app:photoshop", "name": "Photoshop", "icon": True},
                                          {"id": "app:notepad", "name": "Notepad"},
                                          {"id": "app:../evil", "name": "Bad"}, "odd"]), encoding="utf-8")
            self.assertEqual(self.store.windows_apps(listed),
                             [{"id": "app:photoshop", "name": "Photoshop", "icon": "monet-windows-app-photoshop"},
                              {"id": "app:notepad", "name": "Notepad", "icon": "monet-windows"}])

    def test_the_store_is_monets_store_everywhere(self):
        entry = (SHARE / "applications/monet-store.desktop").read_text(encoding="utf-8")
        for line in ("Name=Store\n", "Exec=@LIBEXECDIR@/monet-store %u\n", "Icon=monet-store\n",
                     "MimeType=x-scheme-handler/appstream;\n", "SingleMainWindow=true\n"):
            self.assertIn(line, entry)
        self.assertTrue((SHARE / "icons/Monet/apps/scalable/monet-store.svg").is_file())
        install = (ROOT / "linux/install.sh").read_text(encoding="utf-8")
        self.assertIn('cp -r "$SRC/share/monet/store-app" "$DATADIR/monet/store-app"', install)
        self.assertIn('tree "$SRC/share/monet/store" "$DATADIR/monet/store"', install)
        self.assertIn("monet-store.desktop x-scheme-handler/appstream\n", install)
        self.assertIn("org.kde.konsole.desktop;monet-store.desktop;monet-settings.desktop;", install)
        self.assertNotIn("io.github.kolunmi.Bazaar.desktop;", install)
        look = (ROOT / "linux/libexec/monet-look").read_text(encoding="utf-8")
        # Bazaar or Discover pinned before opens the Store, out of the menu.
        self.assertIn('stand_in io.github.kolunmi.Bazaar "$DATADIR/applications/monet-store.desktop"', look)
        self.assertIn('stand_in org.kde.discover "$DATADIR/applications/monet-store.desktop"', look)
        self.assertIn('"ALIASES".split("|").indexOf(id)', look)
        for look_and_feel in ("org.monet.desktop", "org.monet.smoke.desktop"):
            layout = (SHARE / f"plasma/look-and-feel/{look_and_feel}/contents/layouts/org.kde.plasma.desktop-layout.js")
            self.assertIn('"applications:monet-store.desktop",', layout.read_text(encoding="utf-8"))
        self.assertIn("python3-pyside6 python3-gobject", (ROOT / "image/Containerfile").read_text(encoding="utf-8"))
        from unittest import mock
        quick = quick_helper()
        with tempfile_dir() as tmp:
            for name in ("io.github.kolunmi.Bazaar.desktop", "monet-store.desktop"):
                (Path(tmp) / name).write_text("[Desktop Entry]\n")
            with mock.patch.object(quick, "app_dirs", lambda: [Path(tmp)]):
                self.assertEqual(quick.store_entry(), "monet-store.desktop")

    @staticmethod
    def shelves():
        def app(name, categories, released, verified=False, shots=True):
            return {"name": name, "categories": categories, "released": released, "verified": verified,
                    "screenshots": [{"thumb": "t", "image": "i", "caption": ""}] if shots else []}
        return {
            "org.example.Chess": app("Chess", ["Game", "BoardGame"], 300, verified=True),
            "org.example.Cards": app("Cards", ["Game", "CardGame"], 100),
            "org.example.Blaster": app("Blaster", ["Game", "ActionGame", "Shooter"], 200, verified=True),
            "org.example.Go": app("Go", ["Game", "BoardGame", "Qt"], 50, shots=False),
            "org.example.Paint": app("Paint", ["Graphics", "2DGraphics"], 400),
        }

    def test_a_room_in_the_order_and_of_the_kind_asked(self):
        apps, shelf = self.shelves(), self.store.shelf
        popular = {"org.example.Cards": 9, "org.example.Chess": 5}
        games = ["org.example." + n for n in ("Cards", "Chess", "Blaster", "Go")]
        self.assertEqual(shelf(apps, "games", "popular", popular=popular), games)
        self.assertEqual(shelf(apps, "games", "nonsense", popular=popular), games)
        self.assertEqual(shelf(apps, "games", "updated"), ["org.example." + n for n in ("Chess", "Blaster", "Cards", "Go")])
        self.assertEqual(shelf(apps, "games", "name"), ["org.example." + n for n in ("Blaster", "Cards", "Chess", "Go")])
        self.assertEqual(shelf(apps, "games", "popular", "board", popular=popular),
                         ["org.example.Cards", "org.example.Chess", "org.example.Go"])
        self.assertEqual(shelf(apps, "games", "popular", "action", popular=popular), ["org.example.Blaster"])
        self.assertEqual(shelf(apps, "games", "popular", checked=True, popular=popular), ["org.example.Chess", "org.example.Blaster"])
        self.assertEqual(shelf(apps, "installed", "name", installed={"org.example.Go": "system", "gone.App.x": "user"}),
                         ["org.example.Go"])
        self.assertEqual(self.store.kinds_in(apps, "games", least=1), [("action", 1), ("board", 3)])
        self.assertEqual(self.store.kinds_in(apps, "games"), [("board", 3)])
        self.assertEqual(self.store.section_of(apps["org.example.Paint"]), "graphics")
        self.assertEqual(self.store.section_of({"categories": ["Settings2"]}), "tools")
        # Every kind belongs to a section, and the window has a name for each.
        self.assertLessEqual(set(self.store.KINDS), set(self.store.SECTIONS))
        store_qml = (SHARE / "monet/store-app/Store.qml").read_text(encoding="utf-8")
        named = set(re.findall(r'^\s+"?(\w+)"?: i18nc\("a kind of app, a filter in the Store"', store_qml, re.M))
        self.assertEqual(named, {k for kinds in self.store.KINDS.values() for k, _ in kinds})
        self.assertEqual(self.store.ORDERS, ("popular", "updated", "name"))

    def test_the_front_page_shelves(self):
        apps, store = self.shelves(), self.store
        popular = {"org.example.Cards": 9, "org.example.Chess": 5, "org.example.Paint": 1, "not.in.Catalog": 99}
        self.assertEqual(store.top(apps, popular, 2), ["org.example.Cards", "org.example.Chess"])
        # Fresh paint: the most installed with a release lately, the newest first; none without installs.
        self.assertEqual(store.fresh(apps, popular, now=1000, days=1),
                         ["org.example.Paint", "org.example.Chess", "org.example.Cards"])
        self.assertEqual(store.fresh(apps, popular, now=1000 + 86400, days=1), [])
        self.assertEqual(store.fresh(apps, {}, now=1000), [])
        # Today's pick: one of Monet's picks with a screenshot, the same all day.
        rows = [("play", ["org.example.Go", "org.example.Chess", "missing.App.x"]), ("work", ["org.example.Paint"])]
        picked = {store.today(rows, apps, day) for day in range(40)}
        self.assertEqual(picked, {"org.example.Chess", "org.example.Paint"})
        self.assertEqual(store.today(rows, apps, 7), store.today(rows, apps, 7))
        self.assertEqual(store.today([("play", ["org.example.Go"])], apps, 1), "")
        # More like this: a kind in common counts most; toolkits don't count; then by name.
        self.assertEqual(store.similar(apps, "org.example.Chess", {}),
                         ["org.example.Go", "org.example.Blaster", "org.example.Cards"])
        self.assertEqual(store.similar(apps, "org.example.Chess", {"org.example.Cards": 3}, limit=2),
                         ["org.example.Go", "org.example.Cards"])

    def test_the_store_is_hung_like_a_gallery(self):
        folder = SHARE / "monet/store-app"
        for name in ("Home", "Shelf", "Framed", "Tile", "Strip", "Pebble", "AppPage", "AppCard"):
            self.assertTrue((folder / f"{name}.qml").is_file(), name)
        # QtQuick has a Canvas of its own, which a file of that name would never win over.
        self.assertFalse((folder / "Canvas.qml").exists())
        # A wheel's turn glides, everywhere the Store scrolls; no sideways list catches it.
        for name in ("Home", "Shelf", "AppPage"):
            self.assertIn("Kirigami.WheelHandler {", (folder / f"{name}.qml").read_text(encoding="utf-8"), name)
        store_qml = (folder / "Store.qml").read_text(encoding="utf-8")
        self.assertIn("Kirigami.WheelHandler {\n                    target: results", store_qml)
        self.assertNotIn("ListView.Horizontal", (folder / "AppPage.qml").read_text(encoding="utf-8"))
        # Each section has packaged artwork in both appearance modes.
        for room in [*self.store.SECTIONS, "installed", "windows"]:
            for light in ("mist", "smoke"):
                self.assertTrue((SHARE / f"monet/store/{room}-{light}.jpg").is_file(), room)
        self.assertIn("property alias order: root.order", store_qml)

    def test_the_stand_in_opens_the_store(self):
        # By its whole path: on Windows a bare "bash" is WSL's, and Git's is the one with sed.
        bash = shutil.which("bash")
        if not bash or sys.platform == "win32":
            self.skipTest("no bash")
        look = (ROOT / "linux/libexec/monet-look").read_text(encoding="utf-8")
        stand_in = re.search(r"\n(stand_in\(\) \{.*?\n\})\n", look, re.S).group(1)
        with tempfile_dir() as tmp:
            store = Path(tmp) / "monet-store.desktop"
            store.write_bytes(b"[Desktop Entry]\nName=Store\nExec=/usr/libexec/monet-store %u\nMimeType=x-scheme-handler/appstream;\n")
            bazaar = Path(tmp) / "io.github.kolunmi.Bazaar.desktop"
            bazaar.write_bytes(b"[Desktop Entry]\nName=Bazaar\nExec=bazaar\n")
            script = (f'PROFILE="{ROOT / "linux/libexec/monet-profile"}"; entry() {{ [ "$1" = io.github.kolunmi.Bazaar ] && echo x; }}\n{stand_in}\n'
                      f'DATA="$1/data"; stand_in io.github.kolunmi.Bazaar "$1/monet-store.desktop" && '
                      f'! stand_in org.kde.discover "$1/monet-store.desktop"\n')
            (Path(tmp) / "t.sh").write_bytes(script.encode())
            subprocess.run([bash, (Path(tmp) / "t.sh").as_posix(), Path(tmp).as_posix()], check=True, timeout=30,
                           env={**os.environ, "XDG_DATA_HOME": str(Path(tmp) / "data"), "XDG_STATE_HOME": str(Path(tmp) / "state")})
            made = (Path(tmp) / "data/applications/io.github.kolunmi.Bazaar.desktop").read_text()
            self.assertEqual(made, "[Desktop Entry]\nNoDisplay=true\nX-Monet=true\nName=Store\nExec=/usr/libexec/monet-store %u\n")


class MonetsAppsAreGlass(unittest.TestCase):
    """Games, Settings and the Store sit on glass, as the bar does: KWin blurs behind their
    windows and their side is washed over it as thickly as the Glass slider says."""

    def test_each_window_is_see_through_over_its_glass(self):
        for qml, component in (("games/Games.qml", "MonetWindow"), ("store-app/Store.qml", "MonetWindow"),
                               ("settings-app/MonetSettings.qml", "Shared.MonetWindow")):
            text = (SHARE / "monet" / qml).read_text(encoding="utf-8")
            self.assertIn('    color: "transparent"\n', text, qml)
            self.assertIn(f"\n{component} {{\n", text, qml)
            self.assertNotIn("WindowGlass {", text, qml)  # One wash, shared with the title.
        shared = (SHARE / "monet/games/MonetWindow.qml").read_text(encoding="utf-8")
        self.assertEqual(shared.count("WindowGlass {"), 1)
        self.assertIn("blurred: blurBehind\n", shared)
        settings = (SHARE / "monet/settings-app/MonetSettings.qml").read_text(encoding="utf-8")
        self.assertIn('import "../games" as Shared', settings)
        # Its page stays all paper over the glass.
        self.assertIn("color: Qt.rgba(look.paper.r, look.paper.g, look.paper.b, 1)", settings)

    def test_the_glass_follows_the_slider(self):
        glass = (SHARE / "monet/games/WindowGlass.qml").read_text(encoding="utf-8")
        light = (ROOT / "linux/libexec/monet-light").read_text(encoding="utf-8")
        # The flags monet-light leaves for the desktop widgets.
        for flag in ("off", "frosted", "matte"):
            self.assertIn(f'nameFilters: ["glass-{flag}"]', glass)
            self.assertIn(f"{flag}", re.search(r"for flag in (.*?); do", light).group(1))
        self.assertIn('readonly property bool seeThrough: blurred && level !== "solid" && GraphicsInfo.api !== GraphicsInfo.Software', glass)

    def test_kwin_is_asked_to_blur_behind(self):
        games = (ROOT / "linux/libexec/monet-games").read_text(encoding="utf-8")
        self.assertIn("_ZN14KWindowEffects16enableBlurBehindEP7QWindowbRK7QRegion", games)
        self.assertIn("_ZN14KWindowEffects17isEffectAvailableENS_6EffectE", games)
        self.assertIn('context.setContextProperty("blurBehind", True)', games)
        for program, call in (("monet-games", "    glaze(engine.rootObjects()[0], engine.rootContext())"),
                              ("monet-settings", "    games.glaze(engine.rootObjects()[0], engine.rootContext())"),
                              ("monet-store", "    games.glaze(engine.rootObjects()[0], engine.rootContext())")):
            text = (ROOT / "linux/libexec" / program).read_text(encoding="utf-8")
            self.assertIn('engine.rootContext().setContextProperty("blurBehind", False)', text, program)
            self.assertIn(call, text, program)
            self.assertLess(text.index('setContextProperty("blurBehind", False)'), text.index("engine.load("), program)

    def test_without_kdes_library_the_window_stays_paper(self):
        try:
            import PySide6  # noqa: F401
        except ImportError:
            self.skipTest("no PySide6")
        import types
        from unittest import mock
        games = libexec_helper("monet-games")
        told = []
        with mock.patch.object(games, "KDE_WINDOWS", "libNoSuchLibrary.so.0"):
            self.assertIsNone(games.glaze(object(), types.SimpleNamespace(setContextProperty=lambda *a: told.append(a))))
        self.assertEqual(told, [])

    def test_put_back_says_it_did(self):
        settings = (SHARE / "monet/settings-app/MonetSettings.qml").read_text(encoding="utf-8")
        self.assertIn(': sheet.restored ? i18n("Put back again")', settings)
        self.assertIn("sheet.restored = code === 0 && sheet.json(out, {}).done === true", settings)
        self.assertIn('kind: sheet.restored ? "lily" : "plain"', settings)
        # A wheel's turn glides in Settings and Games too.
        self.assertIn("target: scroller", settings)
        self.assertIn("target: grid", (SHARE / "monet/games/Games.qml").read_text(encoding="utf-8"))
        self.assertIn("target: page", (SHARE / "monet/games/GamePage.qml").read_text(encoding="utf-8"))


class tempfile_dir:
    """A folder for one test, removed afterwards (read-only files too)."""

    def __enter__(self):
        import tempfile
        self.tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        return self.tmp.name

    def __exit__(self, *exc):
        self.tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
