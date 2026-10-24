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

    def test_series_each_in_four_lights(self):
        # Water Lilies and Haystacks beside The Hours, painted by the same tool, chosen in Settings.
        quick = quick_helper()
        # "seasons" hangs one of the four a season: no painting of its own, but a preview.
        self.assertEqual(quick.SERIES, ("hours", "lilies", "haystacks", "magpie", "seasons"))
        painted = quick.SERIES[:4]
        for series in painted:
            for hour in ("dawn", "day", "dusk", "night"):
                self.assertGreater((self.WALL / series / f"{hour}.jpg").stat().st_size, 100_000, f"{series} {hour}")
        for series in quick.SERIES:
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
        qml = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
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
        qml = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
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
        self.assertEqual(install.count("monet-fresh.service monet-names.path"), 2)
        self.assertIn("monet-names.path", (ROOT / "linux/uninstall.sh").read_text())

    def test_going_back_to_the_monet_before(self):
        rust = (ROOT / "crates/monet/src/main.rs").read_text()
        self.assertIn('["rollback"] => elevate(&["helper", "rollback"])', rust)
        self.assertIn('Command::new("bootc").arg("rollback")', rust)
        qml = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
        self.assertIn('ask("rollback"', qml)
        self.assertIn('i18n("Go back at restart")', qml)  # asked once more before it's chosen
        # Updating also clears what no app uses anymore, which Storage says.
        self.assertIn('["uninstall", "--unused", "-y", "--noninteractive"]', rust)

    def test_reduced_motion_outlasts_the_look(self):
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertIn('--key AnimationDurationFactor 2>/dev/null)" = 0 ] ||\n    kw --file kdeglobals --group KDE --key AnimationDurationFactor 0.8', look)

    def test_the_chosen_apps_arrive_after_setup(self):
        service = (ROOT / "linux/systemd/monet-apps.service").read_text()
        self.assertIn("ExecStart=@LIBEXECDIR@/monet-apps", service)
        self.assertIn("ConditionPathExists=!/var/lib/monet/apps-done", service)
        self.assertIn("OnUnitInactiveSec=", (ROOT / "linux/systemd/monet-apps.timer").read_text())
        script = (ROOT / "linux/libexec/monet-apps").read_text()
        self.assertIn("flatpak install --system --noninteractive --or-update -y flathub", script)
        self.assertIn('touch "$DONE"', script)
        install = (ROOT / "linux/install.sh").read_text()
        self.assertIn("monet-widgets monet-apps monet-charge; do", install)
        self.assertIn("monet-apps", (ROOT / "linux/uninstall.sh").read_text())
        self.assertIn("/var/lib/monet/apps-done", (ROOT / "linux/libexec/monet-session").read_text())

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
            chrome = root / "monet.default/chrome"
            self.assertEqual((chrome / "userChrome.css").read_text(), '@import url("monet/zen.css");\n')
            self.assertEqual((chrome / "userContent.css").read_text(), '@import url("monet/newtab.css");\n')
            newtab = (chrome / "monet/newtab.css").read_text()
            self.assertEqual(newtab.count('url("data:image/jpeg;base64,'), 2)
            self.assertNotIn('url("newtab-', newtab)
            for name in ("zen.css", "mist.jpg", "smoke.jpg"):
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
            meta = json.loads((PLASMA / "look-and-feel" / theme / "metadata.json").read_text(encoding="utf-8"))
            self.assertEqual(meta["KPlugin"]["Name"], name)

    def test_kdes_brightness_panel_and_its_dark_mode_stay_out_of_the_bar(self):
        # Plasma 6 keeps the tray's items in the tray's own settings: the layout writes them there,
        # and monet-fresh finds the tray among the bar's applets ([Containments][bar][Applets][tray]).
        for theme in ("org.monet.desktop", "org.monet.smoke.desktop"):
            layout = (PLASMA / "look-and-feel" / theme / "contents/layouts/org.kde.plasma.desktop-layout.js").read_text()
            self.assertNotIn("SystrayContainmentId", layout)
            for piece in ('tray.currentConfigGroup = ["General"]', 'tray.writeConfig("knownItems", known)',
                          'item !== "org.kde.plasma.brightness"', "tray.reloadConfig()"):
                self.assertIn(piece, layout)
        fresh = (ROOT / "linux/libexec/monet-fresh").read_text()
        self.assertIn(r"/^plugin=org\.kde\.plasma\.systemtray$/", fresh)
        self.assertIn('--group Containments --group "$bar" --group Applets --group "$tray" --group General', fresh)
        self.assertNotIn("private.systemtray", fresh)
        # Accounts the old way missed get it once more; one without a tray yet, at the next sign-in.
        self.assertIn('[ -n "$trays" ] && mkdir -p "$CONFIG/monet" && touch "$CONFIG/monet/tray-brightness-6"', fresh)

    def test_apps_go_by_plain_names(self):
        for app, name in (("org.kde.dolphin", "Files"), ("org.kde.konsole", "Terminal"), ("org.kde.gwenview", "Photos"),
                          ("org.kde.spectacle", "Screenshot")):
            self.assertIn(f'"{app}:{name}"', self.LOOK)
        self.assertIn('    store=io.github.kolunmi.Bazaar\n    if rename "$store" Store', self.LOOK)
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
        # Every menu entry monet-look writes carries the mark uninstall.sh looks for
        # (and localized() puts an app's names in other languages under it).
        self.assertEqual(self.LOOK.count("X-Monet=true"), 6)

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
        self.assertIn(': > "$CONFIG/monet/glass-off"', light)
        self.assertIn('rm -f "$CONFIG/monet/glass-off"', light)
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

    def test_weather_goes_through_its_places(self):
        # Every place is kept in order; the arrows step through them, a new one joins the end, one can go.
        weather = (PLASMA / "plasmoids/org.monet.weather/contents/ui/main.qml").read_text(encoding="utf-8")
        for piece in ("onClicked: root.step(-1)", "onClicked: root.step(1)", "visible: root.places.length > 1",
                      "keep(places.concat([place]))", "onTriggered: root.forget()", "all[wanted] = answer;"):
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
        self.assertIn('runner.connectSource(helper + " play " + id)', played)
        quick = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn('elif cmd == "play" and args and args[0].isdigit():', quick)
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
            for piece in ("NoteStore {", "Month {", "DayNotes {", "store: noteStore"):
                self.assertIn(piece, widget)
        # The notes the Calendar kept in its own settings are handed over once.
        self.assertIn("noteStore.merge(older);", calendar)
        self.assertIn("for part in Month DayNotes NoteStore; do", (ROOT / "linux/install.sh").read_text(encoding="utf-8"))
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
        for style in ("monet", "monet-solid"):
            meta = json.loads((PLASMA / "desktoptheme" / style / "metadata.json").read_text(encoding="utf-8"))
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
            found = quick.played()
            self.assertEqual([game["id"] for game in found], ["1091500", "620"])
            self.assertEqual(found[0]["last"], 1750000000)
            self.assertTrue(found[0]["art"].endswith("/1091500/library_600x900.jpg"))
            self.assertTrue(found[1]["art"].endswith("/620_header.jpg"))

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
        qml = (self.QUICK / "MonetSettings.qml").read_text(encoding="utf-8")
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
        qml = (self.QUICK / "MonetSettings.qml").read_text(encoding="utf-8")
        self.assertIn("options: [[1, i18n(\"1 min\")], [5, i18n(\"5 min\")], [15, i18n(\"15 min\")], [30, i18n(\"30 min\")]", qml)
        self.assertIn('onClicked: sheet.ask("kde keys")', qml)

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
        self.assertIn("MonetSettings {", main)
        self.assertIn('onTapped: root.openSettings("")', main)  # All Settings, a pebble of glass
        # Every tile's chevron opens its page (Night Light's is Display), apart from the switch.
        for page in ("wifi", "bluetooth", "display", "notifications"):
            self.assertIn(f'page: "{page}"', main)
        self.assertEqual(main.count("onOpened: root.openSettings(page)"), 4)
        self.assertIn('" listen")', main)
        self.assertNotIn('connectSource("systemsettings")', main)

    def test_settings_search_speaks_every_language(self):
        # Every page's search words are translated, and a search ignores accents ("ecran" finds "écran").
        settings = (self.QUICK / "MonetSettings.qml").read_text(encoding="utf-8")
        self.assertEqual(settings.count('words: i18nc("Settings search words, space-separated",'), 21)
        self.assertNotIn('words: "', settings)
        self.assertIn('fold(entry.name + " " + entry.words).indexOf(words)', settings)
        german = (ROOT / "po/de.po").read_text(encoding="utf-8")
        self.assertIn('msgstr "wlan wifi', german)

    def test_app_menu_and_dock_open_it(self):
        entry = (SHARE / "applications/monet-settings.desktop").read_text(encoding="utf-8")
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


class WhatOtherSystemsHave(unittest.TestCase):
    """0.8.5: each app's volume, battery care, a hotspot, the Batteries widget and a welcome."""
    SETTINGS = PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml"

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
        self.assertIn('which === "welcome" || pages.some(p => p.id === which)', settings)


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
        self.assertIn("kwriteconfig6 --file baloofilerc --group General --key 'only basic indexing' --type bool true",
                      session)
        # Steam: hidden from autostart (only Monet's own copy is ever replaced or removed), started later.
        self.assertIn("Hidden=true\\nX-Monet=true", session)
        self.assertIn('{ [ ! -e "$steam_later" ] || grep -q \'^X-Monet=true\' "$steam_later"; }', session)
        self.assertIn("--unit=monet-steam-later --on-active=45", session)
        self.assertIn('rm -f "$looks/glass-lite"', session)

    def test_lighter_glass_without_the_lens(self):
        glass = (ROOT / "linux/share/monet/widgets/Glass.qml").read_text(encoding="utf-8")
        self.assertIn('nameFilters: ["glass-lite"]', glass)
        self.assertIn("visible: glass.frosted && !glass.lite", glass)
        self.assertIn("live: glass.frosted && !glass.lite", glass)
        self.assertIn("readonly property real band: glass.lite ? 0 : glass.lensWidth", glass)


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
        settings = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
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
        settings = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
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
        settings = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
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
        found = quick.game_marks(marks, here, windows)
        self.assertEqual(found["blocked"], [{"id": "1172470", "name": "Apex Legends", "onWindows": True},
                                            {"id": "359550", "name": "Rainbow Six Siege", "onWindows": False}])
        self.assertEqual(found["marks"]["646570"], "here")
        settings = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
        self.assertIn('text: i18n("Which games need Windows comes from AreWeAntiCheatYet.")', settings)
        games_widget = (PLASMA / "plasmoids/org.monet.games/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn('runner.connectSource(helper + " game-marks")', games_widget)


class SmallFixesFor090(unittest.TestCase):
    """What the owner saw on 0.8.5: the USB stick, the update's name, Settings, the glass, the clock."""
    SETTINGS = PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml"

    def test_the_usb_stick_maker_finds_sticks(self):
        disk = (ROOT / "crates/monet-usb/src/disk.rs").read_text(encoding="utf-8")
        found = disk.split("pub fn sticks()", 1)[1].split("\npub fn ", 1)[0]
        # The drives are opened with no access; the length question needs read access and failed for all.
        self.assertIn('open(&format!("\\\\\\\\.\\\\PhysicalDrive{number}"), 0, 0)', found)
        self.assertNotIn("ioctl(&h, IOCTL_DISK_GET_LENGTH_INFO", found)
        self.assertIn("IOCTL_DISK_GET_DRIVE_GEOMETRY_EX", found)

    def test_updates_say_monets_version(self):
        containerfile = (ROOT / "image/Containerfile").read_text()
        self.assertIn('LABEL org.opencontainers.image.version="${VERSION}" version="${VERSION}"', containerfile)
        workflow = (ROOT / ".github/workflows/image.yml").read_text()
        self.assertEqual(workflow.count('--build-arg VERSION="$VERSION"'), 2)
        settings = self.SETTINGS.read_text(encoding="utf-8")
        self.assertIn('i18n("Fixes for Monet %1 are ready", found.version)', settings)
        self.assertIn("/^\\d{1,2}\\.\\d{1,2}(\\.\\d{1,2})?$/.test(found.version", settings)

    def test_settings_can_be_resized_and_its_list_keeps_clear_of_the_scrollbar(self):
        settings = self.SETTINGS.read_text(encoding="utf-8")
        self.assertIn("width: navList.width - (navList.interactive ? navScroll.width + 4 : 0)", settings)
        self.assertIn("sheet.chosenWidth = Math.max(760, grip.fromWidth + translation.x)", settings)
        self.assertIn("onDoubleTapped: sheet.toggleBig()", settings)
        quick = (PLASMA / "plasmoids/org.monet.quick/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn("Plasmoid.configuration.SettingsWidth = Math.round(width)", quick)
        self.assertIn('<entry name="SettingsWidth" type="Int">',
                      (PLASMA / "plasmoids/org.monet.quick/contents/config/main.xml").read_text())

    def test_clearer_glass_everywhere(self):
        look = (ROOT / "linux/libexec/monet-look").read_text()
        self.assertIn("--key BlurStrength 3", look)
        self.assertIn("--key NoiseStrength 0", look)
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
        self.assertIn("Layout.maximumWidth: Kirigami.Units.gridUnit * (root.notesOpen ? 42 : 19)", clock)
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
            self.assertIn(f"Exec=@LIBEXECDIR@/monet-quick open {page}\n", entry)


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
        settings = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
        self.assertIn('["seasons", i18n("Through the year"), i18n("Each season its painting")]', settings)

    def test_plein_air_focus(self):
        from unittest import mock
        quick = quick_helper()
        said = []
        with mock.patch.object(quick, "run", lambda *a, **k: said.append(a)):
            quick.focus(2000000000)
            quick.focus(None)
        until = ",".join(str(v) for v in __import__("time").localtime(2000000000)[:6])
        self.assertEqual(said[0][-1], until)
        self.assertEqual(said[1][1:3], ("focus", said[1][2]))
        self.assertTrue(said[1][2].endswith(",2000000000"))
        self.assertEqual(said[2][-1], "--delete")
        self.assertEqual(said[3][1:], ("focus", ""))
        hours = (PLASMA / "wallpapers/org.monet.hours/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn("minute = today.dawn + share * (today.night + drift - today.dawn)", hours)
        self.assertIn("interval: root.focusing ? 4000 : 60 * 1000", hours)
        timer = (PLASMA / "plasmoids/org.monet.timer/contents/ui/main.qml").read_text(encoding="utf-8")
        self.assertIn('runner.connectSource(helper + " focus " + Math.round(Plasmoid.configuration.ends / 1000))', timer)
        self.assertIn('runner.connectSource(helper + " focus off")', timer)

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
    def test_the_islands_stay_in_view_unless_chosen(self):
        from unittest import mock
        # 0.9.1: in view by default (0.9.0's stepping aside left the bar hidden on some PCs).
        for theme in ("org.monet.desktop", "org.monet.smoke.desktop"):
            layout = (PLASMA / "look-and-feel" / theme / "contents/layouts/org.kde.plasma.desktop-layout.js").read_text()
            self.assertIn('set(p, "hiding", "none")', layout)
            self.assertNotIn("dodgewindows", layout)
        look = (ROOT / "linux/libexec/monet-look").read_text()
        # Accounts 0.9.0 turned it on for, once, with Settings' switch off to match.
        self.assertIn('if (panel.location === "bottom" && panel.hiding === "dodgewindows") panel.hiding = "none";', look)
        self.assertIn('''sed -i 's/"dodge": true/"dodge": false/' "$CONFIG/monet/prefs.json"''', look)
        self.assertNotIn('panel.hiding = "dodgewindows"', look)
        quick = quick_helper()
        with tempfile_dir() as tmp:
            quick.PREFS = Path(tmp) / "prefs.json"
            quick.drawn_by_processor = lambda: False
            self.assertFalse(quick.prefs()["dodge"])
        self.assertIn("dodge: false })", (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8"))
        self.assertIn("--group Effect-slidingpopups --key SlideOutTime 240", look)
        self.assertIn("--group Plugins --key slidingpopupsEnabled true", look)
        quick = quick_helper()
        said = []
        with mock.patch.object(quick, "plasma_script", said.append):
            quick.set_dodge(False)
            quick.set_dodge(True)
        self.assertIn("p.hiding = 'none'", said[0])
        self.assertIn("p.hiding = 'dodgewindows'", said[1])
        settings = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
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
        settings = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
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
        settings = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
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
        settings = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
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
        settings = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
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


class YourPhone(unittest.TestCase):
    """Settings → Phone: KDE Connect's phones, pairing, battery, ring, send, texts."""

    LISTED = ("- Pixel 8: 1a2b3c4d_5e6f (paired and reachable)\n"
              "- Old phone: 9f8e7d (paired)\n"
              "- Galaxy S24: c0ffee_01 (reachable)\n"
              "3 devices found\n")

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

    def test_the_battery_as_kde_connect_says_it(self):
        from unittest import mock
        quick = quick_helper()
        said = {"charge": "i 64\n", "isCharging": "b false\n"}
        with mock.patch.object(quick, "busctl", lambda *a: said[a[-1]]):
            self.assertEqual(quick.phone_battery("x"), (64, False))
        with mock.patch.object(quick, "busctl", lambda *a: None):
            self.assertEqual(quick.phone_battery("x"), (None, None))

    def test_the_page(self):
        settings = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
        self.assertIn('{ id: "phone", name: i18n("Phone")', settings)
        self.assertIn("phone: phonePage", settings)
        self.assertIn('source: sheet.art + "phone-qr.png"', settings)
        self.assertTrue((SHARE / "monet/settings/phone-qr.png").is_file())
        self.assertTrue((SHARE / "monet/settings/swatch-phone.png").is_file())
        script = (ROOT / "linux/libexec/monet-quick").read_text(encoding="utf-8")
        self.assertIn('"phone": "kcm_kdeconnect"', script)
        self.assertIn('PAGES = ("light", "wifi", "bluetooth", "phone",', script)
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
        settings = (PLASMA / "plasmoids/org.monet.quick/contents/ui/MonetSettings.qml").read_text(encoding="utf-8")
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
