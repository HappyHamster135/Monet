"""Writes Monet's GTK stylesheets: GTK apps (Flathub's too) in Monet's colors.

KDE puts the color scheme's colors for GTK in colors.css and imports it from
gtk.css. Monet's gtk.css keeps that import first, then sets its own on top:
paper or smoke, lily for choices, the sun for the button that goes ahead, and
Monet's switches, checks and sliders. Libadwaita 1.6 and newer (the Store,
for one) reads its colors from CSS variables instead, so GTK 4 gets those too.

Same colors as the Qt side: MonetLight.colors and MonetDark.colors.

Run from the repository root:  python3 tools/make-gtk.py
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "linux" / "share" / "monet" / "gtk"

LIGHT = dict(
    name="Mist, by day",
    window="#F3F1EC", view="#FBFAF7", ink="#1C1B19", sidebar="#ECE9E3", card="#FBFAF7",
    popover="#FBFAF7", dialog="#F7F5F1", headerbar="#F3F1EC",
    shade="rgba(28, 27, 25, 0.07)", headershade="rgba(28, 27, 25, 0.09)", darkershade="rgba(28, 27, 25, 0.12)",
    lily="#357F72", lilytext="#2A6A5F", lilyhover="#3F9483",
    destructive="#D4462A", destructivetext="#C2401F", success="#2F8A55", successtext="#278050",
    warning="#E39B3D", warningtext="#B06C18", warningfg="rgba(0, 0, 0, 0.8)",
    track="alpha(#1C1B19, 0.16)", trackhover="alpha(#1C1B19, 0.24)", well="#FFFFFF", ring="alpha(#1C1B19, 0.22)",
    tooltip="alpha(#1C1B19, 0.92)", tooltiptext="#F3F1EC", scrolloutline="#FFFFFF",
)

DARK = dict(
    name="Smoke, after dark",
    window="#242321", view="#1E1D1C", ink="#EFECE6", sidebar="#2C2A28", card="#2C2A28",
    popover="#2A2927", dialog="#2A2927", headerbar="#242321",
    shade="rgba(0, 0, 0, 0.25)", headershade="rgba(0, 0, 0, 0.36)", darkershade="rgba(0, 0, 0, 0.5)",
    lily="#357F72", lilytext="#62C4B0", lilyhover="#3F9483",
    destructive="#D4462A", destructivetext="#FF8A66", success="#2F8A55", successtext="#58BE82",
    warning="#C98A2E", warningtext="#E8A040", warningfg="rgba(0, 0, 0, 0.8)",
    track="alpha(#FFFFFF, 0.18)", trackhover="alpha(#FFFFFF, 0.26)", well="#2C2A28", ring="alpha(#FFFFFF, 0.25)",
    tooltip="alpha(#F3F1EC, 0.94)", tooltiptext="#1C1B19", scrolloutline="rgba(0, 0, 0, 0.5)",
)

HEADER = """/* Monet: GTK apps in Monet's colors ({name}). Written by monet-light; a
   gtk.css without this first line is yours, and Monet leaves it alone. */

/* KDE's colors for GTK (the color scheme's), then Monet's on top. */
@import 'colors.css';

@define-color accent_color {lilytext};
@define-color accent_bg_color {lily};
@define-color accent_fg_color #FFFFFF;
@define-color destructive_color {destructivetext};
@define-color destructive_bg_color {destructive};
@define-color destructive_fg_color #FFFFFF;
@define-color success_color {successtext};
@define-color success_bg_color {success};
@define-color warning_color {warningtext};
@define-color warning_bg_color {warning};
@define-color error_color {destructivetext};
@define-color error_bg_color {destructive};
@define-color window_bg_color {window};
@define-color window_fg_color {ink};
@define-color view_bg_color {view};
@define-color view_fg_color {ink};
@define-color headerbar_bg_color {headerbar};
@define-color headerbar_fg_color {ink};
@define-color headerbar_border_color {ink};
@define-color headerbar_backdrop_color {headerbar};
@define-color sidebar_bg_color {sidebar};
@define-color sidebar_fg_color {ink};
@define-color card_bg_color {card};
@define-color card_fg_color {ink};
@define-color dialog_bg_color {dialog};
@define-color dialog_fg_color {ink};
@define-color popover_bg_color {popover};
@define-color popover_fg_color {ink};
@define-color theme_bg_color {window};
@define-color theme_fg_color {ink};
@define-color theme_base_color {view};
@define-color theme_text_color {ink};
@define-color theme_selected_bg_color {lily};
@define-color theme_selected_fg_color #FFFFFF;
"""

# Libadwaita 1.6+: the same colors as variables (only GTK 4 reads these).
VARIABLES = """
:root {{
    --accent-color: {lilytext};
    --accent-bg-color: {lily};
    --accent-fg-color: #FFFFFF;
    --destructive-color: {destructivetext};
    --destructive-bg-color: {destructive};
    --destructive-fg-color: #FFFFFF;
    --success-color: {successtext};
    --success-bg-color: {success};
    --success-fg-color: #FFFFFF;
    --warning-color: {warningtext};
    --warning-bg-color: {warning};
    --warning-fg-color: {warningfg};
    --error-color: {destructivetext};
    --error-bg-color: {destructive};
    --error-fg-color: #FFFFFF;
    --window-bg-color: {window};
    --window-fg-color: {ink};
    --view-bg-color: {view};
    --view-fg-color: {ink};
    --headerbar-bg-color: {headerbar};
    --headerbar-fg-color: {ink};
    --headerbar-border-color: {ink};
    --headerbar-backdrop-color: {headerbar};
    --headerbar-shade-color: {headershade};
    --headerbar-darker-shade-color: {darkershade};
    --sidebar-bg-color: {sidebar};
    --sidebar-fg-color: {ink};
    --sidebar-backdrop-color: {sidebar};
    --sidebar-shade-color: {shade};
    --secondary-sidebar-bg-color: {sidebar};
    --secondary-sidebar-fg-color: {ink};
    --secondary-sidebar-backdrop-color: {sidebar};
    --secondary-sidebar-shade-color: {shade};
    --card-bg-color: {card};
    --card-fg-color: {ink};
    --card-shade-color: {shade};
    --dialog-bg-color: {dialog};
    --dialog-fg-color: {ink};
    --popover-bg-color: {popover};
    --popover-fg-color: {ink};
    --popover-shade-color: {shade};
    --thumbnail-bg-color: {card};
    --thumbnail-fg-color: {ink};
    --shade-color: {shade};
    --scrollbar-outline-color: {scrolloutline};
}}
"""

RULES = """
/* The button that goes ahead is the sun, as everywhere in Monet. */
button.suggested-action {{
    background-color: #F2552C;
    color: #FFFFFF;
}}

button.suggested-action:hover {{
    background-color: #FF6A42;
}}

button.suggested-action:active,
button.suggested-action:checked {{
    background-color: #D9441F;
}}

/* Monet's switches: a pill that turns lily, with a white knob. And checks,
   radios, sliders and progress in lily, instead of the usual blue. */
switch {{
    background-color: {track};
    background-image: none;
    border: none;
    border-radius: 999px;
    box-shadow: none;
    padding: 2px;
    color: transparent;
}}

switch:hover {{
    background-color: {trackhover};
}}

switch:checked {{
    background-color: {lily};
}}

switch:checked:hover {{
    background-color: {lilyhover};
}}

switch slider {{
    background-color: #FFFFFF;
    background-image: none;
    border: none;
    border-radius: 999px;
    box-shadow: 0 1px 3px alpha(#000000, 0.28);
    min-width: 20px;
    min-height: 20px;
    margin: 0;
}}

switch image {{
    color: transparent;
}}

switch:disabled {{
    opacity: 0.5;
}}

check,
radio {{
    background-color: {well};
    background-image: none;
    border: 1px solid {ring};
    box-shadow: none;
}}

check {{
    border-radius: 6px;
}}

radio {{
    border-radius: 999px;
}}

check:checked,
check:indeterminate,
radio:checked {{
    background-color: {lily};
    border-color: {lily};
    color: #FFFFFF;
}}

scale trough {{
    border-radius: 999px;
    background-color: {track};
    background-image: none;
    border: none;
}}

scale.horizontal trough {{
    min-height: 4px;
}}

scale.vertical trough {{
    min-width: 4px;
}}

scale highlight {{
    border-radius: 999px;
}}

scale highlight,
progressbar progress,
levelbar block.filled {{
    background-color: {lily};
    background-image: none;
    border-color: {lily};
}}

scale slider {{
    background-color: #FFFFFF;
    background-image: none;
    border: none;
    border-radius: 999px;
    box-shadow: 0 1px 3px alpha(#000000, 0.28);
}}

/* Choices are a soft lily wash, as in Files, not a solid block. */
row:selected,
treeview.view:selected,
flowboxchild:selected {{
    background-color: alpha({lily}, 0.22);
    color: {ink};
}}

/* Tooltips: ink on mist, paper on smoke, like the rest of Monet. */
tooltip.background {{
    background-color: {tooltip};
    color: {tooltiptext};
}}
"""


def sheet(colors, gtk4):
    return HEADER.format(**colors) + (VARIABLES.format(**colors) if gtk4 else "") + RULES.format(**colors)


def main():
    for version in ("3.0", "4.0"):
        folder = OUT / f"gtk-{version}"
        folder.mkdir(parents=True, exist_ok=True)
        for name, colors in (("light", LIGHT), ("dark", DARK)):
            (folder / f"{name}.css").write_text(sheet(colors, version == "4.0"))
    print("wrote", OUT.relative_to(ROOT))


if __name__ == "__main__":
    main()
