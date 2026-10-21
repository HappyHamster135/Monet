"""Draws Monet's app style: glass windows for Qt apps (Files, Kate, Ark, ...).

Kvantum is a Qt style that paints every control from one SVG. This script
writes two themes, Monet (mist, for daylight) and MonetDark (smoke, after
dark). Windows are see-through; KWin blurs the painting behind them, so app
windows get the same glass as the panels.

Each control is a rounded rectangle cut into nine pieces (four corners, four
edges and the middle), the way Kvantum stretches them.

Run from the repository root:  python3 tools/make-kvantum.py
"""

import base64
import io
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "linux" / "share" / "Kvantum"

LILY = "#357F72"
LILY_LIGHT = "#4DB4A0"
SUN = "#F2552C"
# How far menus' and tooltips' shadows reach beyond their glass.
MENU_SHADOW = 8
TOOLTIP_SHADOW = 6


@dataclass
class Palette:
    name: str
    dark: bool
    glass_top: str        # window fill, with alpha (#rrggbbaa)
    glass_bottom: str
    text: str
    dim: str
    button: str
    button_hover: str
    button_pressed: str
    line: str
    rim: str               # 1px highlight along the top of raised things
    field: str
    card: str
    hover: str
    menu: str
    tooltip: str
    scroll: str
    scroll_hover: str
    track: str
    knob: str
    window_color: str      # opaque stand-ins for the Qt palette
    base_color: str        # behind files and lists: solid, like paper
    alt_base_color: str
    button_color: str
    selection: str         # a soft Lily wash, with dark text on it
    selection_text: str
    see_through: bool = True


MIST = Palette(
    name="Monet", dark=False,
    glass_top="#F7F5F1C4", glass_bottom="#F1EEE9D4",
    text="#1C1B19", dim="#6B665E",
    button="#FFFFFFA6", button_hover="#FFFFFFD9", button_pressed="#00000012",
    line="#0000001A", rim="#FFFFFFCC",
    field="#FFFFFFB3", card="#FFFFFF73", hover="#0000000D",
    menu="#F8F7F4EB", tooltip="#1C1B19EB",
    scroll="#00000040", scroll_hover="#00000073",
    track="#0000001F", knob="#FFFFFF",
    window_color="#F3F1EC", base_color="#FBFAF7", alt_base_color="#F5F3EF", button_color="#F7F5F1",
    selection="#D3E1DC", selection_text="#1F5249",
)

SMOKE = Palette(
    name="MonetDark", dark=True,
    glass_top="#22211FC4", glass_bottom="#1B1A19D6",
    text="#EFECE6", dim="#B4AEA5",
    button="#FFFFFF17", button_hover="#FFFFFF26", button_pressed="#FFFFFF0D",
    line="#FFFFFF1A", rim="#FFFFFF24",
    field="#00000038", card="#FFFFFF0F", hover="#FFFFFF0F",
    menu="#262523EB", tooltip="#F3F1ECEB",
    scroll="#FFFFFF47", scroll_hover="#FFFFFF80",
    track="#FFFFFF24", knob="#F3F1EC",
    window_color="#242321", base_color="#1F1E1C", alt_base_color="#252422", button_color="#33312E",
    selection="#293F39", selection_text="#CFF0E8",
)


def solid(p: Palette, name):
    """The same style without glass: for slower PCs, or people who prefer it."""
    from dataclasses import replace
    return replace(p, name=name, see_through=False,
                   glass_top=p.window_color + "FF", glass_bottom=p.window_color + "FF",
                   menu=p.menu[:7] + "FF", tooltip=p.tooltip[:7] + "FF")


def rgba(color):
    """'#rrggbbaa' or '#rrggbb' -> (fill, opacity) for SVG attributes."""
    c = color.lstrip("#")
    alpha = int(c[6:8], 16) / 255 if len(c) == 8 else 1.0
    return "#" + c[:6], round(alpha, 3)


def paint(color):
    fill, alpha = rgba(color)
    return f'fill="{fill}" fill-opacity="{alpha}"'


def ink(color, width=1.0):
    fill, alpha = rgba(color)
    return f'fill="none" stroke="{fill}" stroke-opacity="{alpha}" stroke-width="{width}"'


class Sheet:
    """Places SVG elements side by side so their boxes never overlap."""

    def __init__(self):
        self.parts = []
        self.x = 0
        self.y = 0
        self.row = 0

    def place(self, w, h):
        if self.x + w > 1600:
            self.x = 0
            self.y += self.row + 8
            self.row = 0
        x, y = self.x, self.y
        self.x += w + 8
        self.row = max(self.row, h)
        return x, y

    def add(self, ident, body):
        self.parts.append(f'<g id="{ident}">{body}</g>')

    def box(self, ident, w, h, inner):
        """An element whose box is exactly w x h; inner(x, y) returns its shapes."""
        x, y = self.place(w, h)
        clear = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="#000000" fill-opacity="0"/>'
        self.add(ident, clear + inner(x, y))

    def frame(self, ident, f, fill=None, border=None, rim=None, ring=None, interior=True, size=12):
        """Nine pieces of a rounded rectangle with corner radius f."""
        fl = paint(fill) if fill else 'fill="none"'

        def corner(x, y, which):
            # Each corner is a quarter disc around the piece's inner corner.
            # Borders are filled rings, not strokes: Qt counts a stroke's width
            # in the element's size, which would shift every piece.
            cx, cy, start, end = {
                "topleft": (x + f, y + f, (x, y + f), (x + f, y)),
                "topright": (x, y + f, (x, y), (x + f, y + f)),
                "bottomright": (x, y, (x + f, y), (x, y + f)),
                "bottomleft": (x + f, y, (x + f, y + f), (x, y)),
            }[which]
            shapes = ""
            if fill:
                shapes += (f'<path d="M{cx},{cy} L{start[0]},{start[1]} A{f},{f} 0 0 1 {end[0]},{end[1]} Z" {fl}/>')
            for color, width in ((border, 1), (ring, 2)):
                if not color:
                    continue
                r = f - width

                def at(point, radius):
                    return (cx + (point[0] - cx) * radius / f, cy + (point[1] - cy) * radius / f)

                s0, e0 = at(start, f), at(end, f)
                s1, e1 = at(start, r), at(end, r)
                shapes += (f'<path d="M{s0[0]},{s0[1]} A{f},{f} 0 0 1 {e0[0]},{e0[1]} L{e1[0]},{e1[1]} '
                           f'A{r},{r} 0 0 0 {s1[0]},{s1[1]} Z" {paint(color)}/>')
            return shapes

        def edge(x, y, which):
            w, h = (size, f) if which in ("top", "bottom") else (f, size)
            shapes = f'<rect x="{x}" y="{y}" width="{w}" height="{h}" {fl}/>' if fill else ""
            for color, width in ((border, 1), (ring, 2)):
                if not color:
                    continue
                bar = {
                    "top": (x, y, w, width),
                    "bottom": (x, y + h - width, w, width),
                    "left": (x, y, width, h),
                    "right": (x + w - width, y, width, h),
                }[which]
                shapes += f'<rect x="{bar[0]}" y="{bar[1]}" width="{bar[2]}" height="{bar[3]}" {paint(color)}/>'
            if rim and which == "top":
                shapes += f'<rect x="{x}" y="{y + 1}" width="{w}" height="1" {paint(rim)}/>'
            return shapes

        for which in ("topleft", "topright", "bottomright", "bottomleft"):
            self.box(f"{ident}-{which}", f, f, lambda x, y, w=which: corner(x, y, w))
        for which in ("top", "bottom"):
            self.box(f"{ident}-{which}", size, f, lambda x, y, w=which: edge(x, y, w))
        for which in ("left", "right"):
            self.box(f"{ident}-{which}", f, size, lambda x, y, w=which: edge(x, y, w))
        if interior:
            self.box(ident, size, size,
                     lambda x, y: f'<rect x="{x}" y="{y}" width="{size}" height="{size}" {fl}/>' if fill else "")

    def shadowed(self, ident, f, depth, fill, border, strength=0.26, blur=3.2, drop=1.5):
        """A popup's frame together with the soft shadow around it, for
        translucent menus and tooltips: Kvantum's "<element>-shadow-*" pieces,
        each the shadow plus the frame inside it, and the hints that say how
        much of each is only shadow (so the blur stays under the glass)."""
        t = f + depth
        middle = 12
        W = 2 * t + middle
        k = 4
        big = Image.new("L", (W * k, W * k), 0)
        box = [depth * k, depth * k, (W - depth) * k - 1, (W - depth) * k - 1]
        ImageDraw.Draw(big).rounded_rectangle([box[0], box[1] + drop * k, box[2], box[3] + drop * k], radius=f * k, fill=255)
        soft = big.filter(ImageFilter.GaussianBlur(blur * k)).resize((W, W), Image.LANCZOS)
        under = Image.new("L", (W * k, W * k), 0)
        ImageDraw.Draw(under).rounded_rectangle(box, radius=f * k, fill=255)
        under = under.resize((W, W), Image.LANCZOS)
        alpha = np.asarray(soft).astype(np.float32) * strength * (1 - np.asarray(under).astype(np.float32) / 255)
        rgba = np.zeros((W, W, 4), np.uint8)
        rgba[..., 3] = np.clip(alpha, 0, 255).astype(np.uint8)
        shadow = Image.fromarray(rgba, "RGBA")

        def png(crop):
            buf = io.BytesIO()
            shadow.crop(crop).save(buf, "PNG", optimize=True)
            return base64.b64encode(buf.getvalue()).decode()

        fl, edge = paint(fill), paint(border)
        pieces = {
            "topleft": (0, 0, t, t), "top": (t, 0, t + middle, t), "topright": (t + middle, 0, W, t),
            "left": (0, t, t, t + middle), "right": (t + middle, t, W, t + middle),
            "bottomleft": (0, t + middle, t, W), "bottom": (t, t + middle, t + middle, W), "bottomright": (t + middle, t + middle, W, W),
        }
        for which, crop in pieces.items():
            w, h = crop[2] - crop[0], crop[3] - crop[1]
            data = png(crop)

            def body(x, y, which=which, crop=crop, w=w, h=h, data=data):
                out = f'<image x="{x}" y="{y}" width="{w}" height="{h}" xlink:href="data:image/png;base64,{data}"/>'
                # The frame's part of this piece, in the reference frame's coordinates.
                ox, oy = x - crop[0], y - crop[1]
                a, b = depth, W - depth  # the frame's outer edges
                if which in ("top", "bottom"):
                    yy = a if which == "top" else b - f
                    out += f'<rect x="{x}" y="{oy + yy}" width="{w}" height="{f}" {fl}/>'
                    line = oy + (a if which == "top" else b - 1)
                    out += f'<rect x="{x}" y="{line}" width="{w}" height="1" {edge}/>'
                elif which in ("left", "right"):
                    xx = a if which == "left" else b - f
                    out += f'<rect x="{ox + xx}" y="{y}" width="{f}" height="{h}" {fl}/>'
                    line = ox + (a if which == "left" else b - 1)
                    out += f'<rect x="{line}" y="{y}" width="1" height="{h}" {edge}/>'
                else:
                    cx = ox + (a + f if "left" in which else b - f)
                    cy = oy + (a + f if "top" in which else b - f)
                    sx = -1 if "left" in which else 1
                    sy = -1 if "top" in which else 1
                    # A quarter disc of fill, and a 1 px quarter ring for the edge.
                    p0, p1 = (cx + sx * f, cy), (cx, cy + sy * f)
                    sweep = 1 if sx * sy > 0 else 0
                    out += f'<path d="M{cx},{cy} L{p0[0]},{p0[1]} A{f},{f} 0 0 {sweep} {p1[0]},{p1[1]} Z" {fl}/>'
                    r2 = f - 1
                    q0, q1 = (cx + sx * r2, cy), (cx, cy + sy * r2)
                    out += (f'<path d="M{p0[0]},{p0[1]} A{f},{f} 0 0 {sweep} {p1[0]},{p1[1]} L{q1[0]},{q1[1]} '
                            f'A{r2},{r2} 0 0 {1 - sweep} {q0[0]},{q0[1]} Z" {edge}/>')
                return out
            self.box(f"{ident}-shadow-{which}", w, h, body)
        for side in ("top", "bottom", "left", "right"):
            w, h = (2, depth) if side in ("top", "bottom") else (depth, 2)
            self.box(f"{ident}-shadow-hint-{side}", w, h, lambda x, y: "")

    def svg(self):
        height = self.y + self.row + 8
        return ('<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" '
                'width="1600" height="%d" viewBox="0 0 1600 %d">\n'
                "<!-- Monet app style for Kvantum. Generated by tools/make-kvantum.py. -->\n%s\n</svg>\n"
                % (height, height, "\n".join(self.parts)))


def theme_svg(p: Palette):
    s = Sheet()
    states = ("normal", "focused", "pressed", "toggled", "disabled")

    # Window and dialog glass: a soft vertical gradient, see-through.
    for ident in ("window-normal", "window-normal-inactive", "dialog-normal", "dialog-normal-inactive"):
        top, bottom = p.glass_top, p.glass_bottom
        if ident.endswith("inactive"):
            top, bottom = p.glass_bottom, p.glass_bottom
        gid = ident.replace("-", "_")
        t, ta = rgba(top)
        b, ba = rgba(bottom)
        s.parts.append(f'<defs><linearGradient id="{gid}_g" x1="0" y1="0" x2="0" y2="1">'
                       f'<stop offset="0" stop-color="{t}" stop-opacity="{ta}"/>'
                       f'<stop offset="1" stop-color="{b}" stop-opacity="{ba}"/></linearGradient></defs>')
        s.box(ident, 64, 64, lambda x, y, g=gid: f'<rect x="{x}" y="{y}" width="64" height="64" fill="url(#{g}_g)"/>')

    # Push buttons and combo boxes: soft pills of glass with a rim of light.
    looks = {
        "normal": dict(fill=p.button, border=p.line, rim=p.rim),
        "focused": dict(fill=p.button_hover, border=p.line, rim=p.rim),
        "pressed": dict(fill=p.button_pressed, border=p.line),
        "toggled": dict(fill=LILY + "E6", border=None),
        "disabled": dict(fill=p.button_pressed, border=None),
    }
    for st in states:
        s.frame(f"button-{st}", 8, **looks[st])

    # Tool buttons: flat until you touch them.
    tool = {
        "normal": dict(fill=None),
        "focused": dict(fill=p.hover),
        "pressed": dict(fill=p.button_pressed),
        "toggled": dict(fill=p.button, border=p.line, rim=p.rim),
        "disabled": dict(fill=None),
    }
    for st in states:
        s.frame(f"tbutton-{st}", 8, **tool[st])

    # Text fields: a well, ringed in Lily when you type.
    s.frame("lineedit-normal", 8, fill=p.field, border=p.line)
    s.frame("lineedit-focused", 8, fill=p.field, ring=LILY_LIGHT if p.dark else LILY)
    s.frame("lineedit-disabled", 8, fill=p.button_pressed)

    # Frames, group boxes, tab pages: quiet cards.
    s.frame("common-normal", 8, border=p.line, interior=False)
    s.frame("common-focused", 8, ring=LILY_LIGHT if p.dark else LILY, interior=False)
    s.frame("group-normal", 12, fill=p.card, border=p.line)
    s.frame("tabframe-normal", 12, fill=p.card, border=p.line)
    tab = {
        "normal": dict(fill=None),
        "focused": dict(fill=p.hover),
        "pressed": dict(fill=p.button_pressed),
        "toggled": dict(fill=p.button, border=p.line, rim=p.rim),
        "disabled": dict(fill=None),
    }
    for st in states:
        s.frame(f"tab-{st}", 8, **tab[st])

    # Lists and icon views: rounded highlights, Lily for the selection.
    s.frame("itemview-normal", 6, fill=None)
    s.frame("itemview-focused", 6, fill=p.hover)
    wash = (LILY_LIGHT + "38") if p.dark else (LILY + "33")
    s.frame("itemview-pressed", 6, fill=wash)
    s.frame("itemview-toggled", 6, fill=wash)

    # Menus, the menu bar and tooltips. With compositing, menus and tooltips
    # cast a soft shadow, drawn with their frame (see MENU_SHADOW below).
    s.frame("menu-normal", 10, fill=p.menu, border=p.line)
    s.shadowed("menu", 10, MENU_SHADOW, p.menu, p.line)
    s.frame("menuitem-normal", 6, fill=None)
    # Kvantum draws the highlighted menu item as "pressed".
    s.frame("menuitem-focused", 6, fill=LILY + "E6")
    s.frame("menuitem-pressed", 6, fill=LILY + "E6")
    s.frame("menuitem-toggled", 6, fill=LILY + "E6")
    # Between groups of menu items: a hairline (MenuItem's indicator is "arrow").
    s.box("arrow-separator", 40, 9, lambda x, y: f'<rect x="{x}" y="{y + 4}" width="40" height="1" {paint(p.line)}/>')
    s.frame("menubaritem-normal", 6, fill=None)
    s.frame("menubaritem-focused", 6, fill=p.hover)
    s.frame("menubaritem-pressed", 6, fill=p.button)
    s.frame("menubaritem-toggled", 6, fill=p.button)
    s.frame("tooltip-normal", 8, fill=p.tooltip)
    s.shadowed("tooltip", 8, TOOLTIP_SHADOW, p.tooltip, p.tooltip, strength=0.22, blur=2.4, drop=1)

    # Table headers: just a hairline underneath.
    for st in ("normal", "focused", "pressed", "toggled"):
        s.frame(f"header-{st}", 2, fill=p.hover if st != "normal" else None, interior=True)

    # Scrollbars: thin pills that appear over the content.
    s.frame("ss-normal", 4, fill=p.scroll, interior=False)
    s.frame("ss-focused", 4, fill=p.scroll_hover, interior=False)
    s.frame("ss-pressed", 4, fill=p.scroll_hover, interior=False)
    for st, color in (("normal", p.scroll), ("focused", p.scroll_hover), ("pressed", p.scroll_hover), ("disabled", p.track)):
        s.frame(f"scrollbarslider-{st}", 4, fill=color)
    s.frame("scrollbargroove-normal", 4, fill=None)

    # Sliders and progress: a rounded track, Lily where it's filled.
    s.frame("slider-normal", 2, fill=p.track)
    s.frame("slider-toggled", 2, fill=LILY_LIGHT if p.dark else LILY)
    s.frame("slider-disabled", 2, fill=p.track)
    s.frame("progress-normal", 3, fill=p.track)
    s.frame("progress-pattern-normal", 3, fill=LILY_LIGHT if p.dark else LILY)
    s.frame("progress-pattern-disabled", 3, fill=p.track)

    knob_shadow = "#000000" if True else ""

    def knob(x, y, color, pressed=False):
        r = 7.5 if not pressed else 7
        return (f'<circle cx="{x + 9}" cy="{y + 9.8}" r="{r}" fill="{knob_shadow}" fill-opacity="0.22"/>'
                f'<circle cx="{x + 9}" cy="{y + 9}" r="{r}" {paint(color)}/>'
                f'<circle cx="{x + 9}" cy="{y + 9}" r="{r - 0.5}" {ink("#00000014" if not p.dark else "#00000040")}/>')

    for st in ("normal", "focused", "pressed", "disabled"):
        color = p.knob if st != "disabled" else (p.dim + "80")
        s.box(f"slidercursor-{st}", 18, 18, lambda x, y, c=color, st=st: knob(x, y, c, st == "pressed"))

    # Check boxes and radio buttons.
    accent = LILY

    def check_box(x, y, st, checked, tri=False):
        out = ""
        if checked:
            out += f'<rect x="{x + 1}" y="{y + 1}" width="16" height="16" rx="5" {paint(accent if st != "disabled" else p.track)}/>'
            if tri:
                out += f'<path d="M{x + 5},{y + 9} L{x + 13},{y + 9}" fill="none" stroke="#FFFFFF" stroke-width="2" stroke-linecap="round"/>'
            else:
                out += (f'<path d="M{x + 5},{y + 9.2} L{x + 8},{y + 12} L{x + 13.2},{y + 6.4}" fill="none" stroke="#FFFFFF" '
                        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>')
        else:
            fill = p.button_hover if st == "focused" else p.field
            out += f'<rect x="{x + 1}" y="{y + 1}" width="16" height="16" rx="5" {paint(fill)}/>'
            out += f'<rect x="{x + 1.5}" y="{y + 1.5}" width="15" height="15" rx="4.5" {ink(p.dim + "99", 1)}/>'
        return out

    def radio(x, y, st, checked):
        if checked:
            return (f'<circle cx="{x + 9}" cy="{y + 9}" r="8" {paint(accent if st != "disabled" else p.track)}/>'
                    f'<circle cx="{x + 9}" cy="{y + 9}" r="3.2" fill="#FFFFFF"/>')
        fill = p.button_hover if st == "focused" else p.field
        return (f'<circle cx="{x + 9}" cy="{y + 9}" r="8" {paint(fill)}/>'
                f'<circle cx="{x + 9}" cy="{y + 9}" r="7.5" {ink(p.dim + "99", 1)}/>')

    for st in ("normal", "focused", "pressed", "disabled"):
        s.box(f"checkbox-{st}", 18, 18, lambda x, y, st=st: check_box(x, y, st, False))
        s.box(f"checkbox-checked-{st}", 18, 18, lambda x, y, st=st: check_box(x, y, st, True))
        s.box(f"checkbox-tristate-{st}", 18, 18, lambda x, y, st=st: check_box(x, y, st, True, True))
        s.box(f"radio-{st}", 18, 18, lambda x, y, st=st: radio(x, y, st, False))
        s.box(f"radio-checked-{st}", 18, 18, lambda x, y, st=st: radio(x, y, st, True))

    # Chevrons.
    chevrons = {
        "down": "M2.5,4 L6,7.5 L9.5,4", "up": "M2.5,8 L6,4.5 L9.5,8",
        "left": "M8,2.5 L4.5,6 L8,9.5", "right": "M4,2.5 L7.5,6 L4,9.5",
    }
    for direction, d in chevrons.items():
        for st in states:
            color = {"disabled": p.dim + "80", "toggled": "#FFFFFF"}.get(st, p.text)

            def arrow(x, y, d=d, color=color):
                path = "".join(c if not c.isdigit() and c not in ".," else c for c in d)
                # Offset the path into this element's box.
                pts = []
                for token in path.replace("M", " M ").replace("L", " L ").split():
                    if token in ("M", "L"):
                        pts.append(token)
                    else:
                        px, py = token.split(",")
                        pts.append(f"{x + float(px)},{y + float(py)}")
                return (f'<path d="{" ".join(pts)}" fill="none" stroke="{rgba(color)[0]}" stroke-opacity="{rgba(color)[1]}" '
                        f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>')

            s.box(f"arrow-{direction}-{st}", 12, 12, arrow)

    return s.svg()


GENERAL = """[%General]
author=Monet
comment=Monet's glass for Qt apps: see-through windows with the painting behind them.
x11drag=menubar_and_primary_toolbar
alt_mnemonic=true
left_tabs=false
attach_active_tab=false
embedded_tabs=false
mirror_doc_tabs=false
group_toolbar_buttons=false
spread_progressbar=true
composite=true
menu_shadow_depth={menu_shadow}
tooltip_shadow_depth={tooltip_shadow}
menu_blur_radius=10
tooltip_blur_radius=8
spread_menuitems=false
menu_separator_height=9
scroll_width=10
scroll_arrows=false
scroll_min_extent=36
transient_scrollbar=true
transient_groove=false
slider_width=4
slider_handle_width=18
slider_handle_length=18
center_toolbar_handle=true
check_size=18
textless_progressbar=false
progressbar_thickness=6
menubar_mouse_tracking=true
toolbutton_style=0
click_behavior=0
translucent_windows={see_through}
blurring={see_through}
popup_blurring={see_through}
opaque=kaffeine,kmplayer,subtitlecomposer,kdenlive,vlc,smplayer,smplayer2,avidemux,avidemux2_qt4,avidemux3_qt4,avidemux3_qt5,kamoso,QtCreator,VirtualBox,VirtualBoxVM,trojita,dragon,digikam,lyx,obs,haruna,mpv,krita,blender,steam
vertical_spin_indicators=false
fill_rubberband=false
merge_menubar_with_toolbar=true
small_icon_size=16
large_icon_size=32
button_icon_size=16
toolbar_icon_size=22
toolbar_interior_spacing=4
combo_as_lineedit=false
combo_menu=true
combo_focus_rect=false
groupbox_top_label=true
inline_spin_indicators=true
spin_button_width=18
joined_inactive_tabs=false
remove_extra_frames=true
layout_spacing=6
layout_margin=9
submenu_overlap=0
submenu_delay=250
tooltip_delay=-1
animate_states=true
dark_titlebar={dark}
hide_combo_checkboxes=true
no_window_pattern=false
reduce_window_opacity=0
reduce_menu_opacity=0
respect_DE=true
scrollbar_in_view=true
tree_branch_line=false
no_inactiveness=false

[GeneralColors]
window.color={window}
inactive.window.color={window}
base.color={base}
inactive.base.color={base}
alt.base.color={alt}
inactive.alt.base.color={alt}
button.color={button}
light.color={light}
mid.light.color={midlight}
dark.color={darkc}
mid.color={mid}
highlight.color={selection}
inactive.highlight.color={selection}
tooltip.base.color={tooltipbase}
text.color={text}
inactive.text.color={text}
window.text.color={text}
inactive.window.text.color={text}
button.text.color={text}
disabled.text.color={disabled}
tooltip.text.color={tooltiptext}
highlight.text.color={selection_text}
inactive.highlight.text.color={selection_text}
link.color={link}
link.visited.color=#8E7CC3
progress.indicator.text.color={text}

[Hacks]
transparent_ktitle_label=true
transparent_dolphin_view=false
transparent_pcmanfm_sidepane=true
transparent_pcmanfm_view=false
blur_translucent=true
transparent_menutitle=true
respect_darkness=true
force_size_grip=false
iconless_pushbutton=false
iconless_menu=false
disabled_icon_opacity=60
normal_default_pushbutton=true
single_top_toolbar=true
tint_on_mouseover=0
middle_click_scroll=false
no_selection_tint=true
transparent_arrow_button=true
kcapacitybar_as_progressbar=true
"""

SECTIONS = """
[PanelButtonCommand]
frame=true
frame.element=button
frame.top=8
frame.bottom=8
frame.left=8
frame.right=8
interior=true
interior.element=button
indicator.size=12
indicator.element=arrow
text.normal.color={text}
text.focus.color={text}
text.press.color={text}
text.toggle.color=#FFFFFF
text.disabled.color={disabled}
text.shadow=0
text.margin=1
text.iconspacing=6
text.margin.top=2
text.margin.bottom=2
text.margin.left=6
text.margin.right=6
min_width=+0.5font
min_height=+0.4font

[PanelButtonTool]
inherits=PanelButtonCommand
frame.element=tbutton
interior.element=tbutton
text.toggle.color={text}

[ToolbarButton]
inherits=PanelButtonTool
text.toggle.color={text}

[Dock]
inherits=PanelButtonCommand
frame=false
interior=false

[DockTitle]
inherits=PanelButtonCommand
frame=false
interior=false
text.bold=true

[IndicatorSpinBox]
inherits=PanelButtonCommand
frame=false
interior=false
indicator.element=arrow
indicator.size=10

[RadioButton]
inherits=PanelButtonCommand
frame=false
interior.element=radio
text.toggle.color={text}

[CheckBox]
inherits=PanelButtonCommand
frame=false
interior.element=checkbox
text.toggle.color={text}

[Focus]
inherits=PanelButtonCommand
frame=false
interior=false

[GenericFrame]
inherits=PanelButtonCommand
frame=true
interior=false
frame.element=common
interior.element=common
frame.top=8
frame.bottom=8
frame.left=8
frame.right=8

[LineEdit]
inherits=PanelButtonCommand
frame.element=lineedit
interior.element=lineedit
text.margin.left=4
text.margin.right=4

[ToolboxTab]
inherits=PanelButtonCommand
frame.element=tab
interior.element=tab

[Tab]
inherits=PanelButtonCommand
interior.element=tab
frame.element=tab
indicator.element=tab
text.normal.color={dim}
text.focus.color={text}
text.toggle.color={text}
text.margin.left=12
text.margin.right=12
text.margin.top=4
text.margin.bottom=4
min_width=+2font
min_height=+0.6font

[TabFrame]
inherits=PanelButtonCommand
frame.element=tabframe
interior.element=tabframe
frame.top=12
frame.bottom=12
frame.left=12
frame.right=12

[TreeExpander]
inherits=PanelButtonCommand
frame=false
interior=false
indicator.size=10

[HeaderSection]
inherits=PanelButtonCommand
frame.element=header
interior.element=header
frame.top=2
frame.bottom=2
frame.left=2
frame.right=2
text.normal.color={dim}
text.bold=false
text.toggle.color={text}

[SizeGrip]
inherits=PanelButtonCommand
frame=false
interior=false

[Toolbar]
inherits=PanelButtonCommand
frame=false
interior=false
indicator.element=toolbar
indicator.size=5
text.margin=0

[Slider]
inherits=PanelButtonCommand
frame.element=slider
interior.element=slider
frame.top=2
frame.bottom=2
frame.left=2
frame.right=2

[SliderCursor]
inherits=PanelButtonCommand
frame=false
interior.element=slidercursor

[Progressbar]
inherits=PanelButtonCommand
frame.element=progress
interior.element=progress
frame.top=3
frame.bottom=3
frame.left=3
frame.right=3
text.margin=0
text.bold=false
text.normal.color={text}
text.focus.color={text}

[ProgressbarContents]
inherits=PanelButtonCommand
frame=true
frame.element=progress-pattern
interior.element=progress-pattern
frame.top=3
frame.bottom=3
frame.left=3
frame.right=3

[ItemView]
inherits=PanelButtonCommand
frame.element=itemview
interior.element=itemview
frame.top=6
frame.bottom=6
frame.left=6
frame.right=6
text.margin.top=2
text.margin.bottom=2
text.margin.left=4
text.margin.right=4
text.toggle.color={selection_text}
text.press.color={selection_text}
min_height=+0.5font

[Splitter]
inherits=PanelButtonCommand
frame=false
interior=false
indicator.size=0

[Scrollbar]
inherits=PanelButtonCommand
indicator.size=0

[ScrollbarSlider]
inherits=PanelButtonCommand
frame.element=scrollbarslider
interior.element=scrollbarslider
frame.top=4
frame.bottom=4
frame.left=4
frame.right=4

[ScrollbarTransientSlider]
frame=true
frame.element=ss
interior=false
frame.top=4
frame.bottom=4
frame.left=4
frame.right=4

[ScrollbarGroove]
inherits=PanelButtonCommand
frame=false
interior=false

[MenuItem]
inherits=PanelButtonCommand
frame=true
frame.element=menuitem
interior.element=menuitem
indicator.element=arrow
text.focus.color=#FFFFFF
text.press.color=#FFFFFF
text.toggle.color=#FFFFFF
text.margin.top=0
text.margin.bottom=0
text.margin.left=4
text.margin.right=4
frame.top=6
frame.bottom=6
frame.left=6
frame.right=6

[MenuBarItem]
inherits=PanelButtonCommand
frame.element=menubaritem
interior.element=menubaritem
frame.top=6
frame.bottom=6
frame.left=6
frame.right=6
text.margin.left=4
text.margin.right=4
text.toggle.color={text}

[TitleBar]
inherits=PanelButtonCommand
frame=false
interior=false
text.bold=true

[ComboBox]
inherits=PanelButtonCommand
indicator.element=arrow

[Menu]
inherits=PanelButtonCommand
frame.element=menu
interior.element=menu
frame.top=10
frame.bottom=10
frame.left=10
frame.right=10
text.shadow=0

[GroupBox]
inherits=GenericFrame
frame=true
frame.element=group
interior=true
interior.element=group
frame.top=12
frame.bottom=12
frame.left=12
frame.right=12
text.bold=true
text.margin=0

[TabBarFrame]
inherits=GenericFrame
frame=false
interior=false

[ToolTip]
inherits=GenericFrame
frame.element=tooltip
interior.element=tooltip
interior=true
frame.top=8
frame.bottom=8
frame.left=8
frame.right=8
text.normal.color={tooltiptext}
text.margin=2

[StatusBar]
inherits=GenericFrame
frame=false
interior=false

[Window]
interior=true
interior.element=window

[Dialog]
interior=true
interior.element=dialog
"""


def kvconfig(p: Palette):
    fill = dict(
        dark=str(p.dark).lower(), window=p.window_color, base=p.base_color, alt=p.alt_base_color,
        button=p.button_color, text=p.text, dim=p.dim, lily=LILY,
        light="#FFFFFF" if not p.dark else "#45423E", midlight="#E6E3DD" if not p.dark else "#3B3935",
        darkc="#B9B4AB" if not p.dark else "#141312", mid="#D6D2CB" if not p.dark else "#2C2A28",
        tooltipbase=rgba(p.tooltip)[0], tooltiptext="#F3F1EC" if not p.dark else "#1C1B19",
        disabled="#A39D94" if not p.dark else "#6B665E", link=LILY if not p.dark else LILY_LIGHT,
        selection=p.selection, selection_text=p.selection_text, see_through=str(p.see_through).lower(),
        menu_shadow=MENU_SHADOW, tooltip_shadow=TOOLTIP_SHADOW,
    )
    return GENERAL.format(**fill) + SECTIONS.format(**fill)


def main():
    for p in (MIST, SMOKE, solid(MIST, "MonetSolid"), solid(SMOKE, "MonetDarkSolid")):
        folder = OUT / p.name
        folder.mkdir(parents=True, exist_ok=True)
        (folder / f"{p.name}.svg").write_text(theme_svg(p))
        (folder / f"{p.name}.kvconfig").write_text(kvconfig(p))
        print("wrote", folder.relative_to(ROOT))


if __name__ == "__main__":
    main()
