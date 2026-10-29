# Monet design

Monet should feel calm and obvious. If something needs explaining, the design
isn't finished.

## Principles

1. **It just works.** Good defaults instead of settings. No terminal for
   everyday use.
2. **One thing at a time.** One main action per screen, one question per dialog.
3. **Plain words.** Say what will happen, in the user's words.
4. **Quiet.** No ads, no badges, no numbers nobody asked for.
5. **Honest.** Say what didn't work and what to do next. Never pretend.

## Words

Short sentences. Sentence case. Talk about games and the PC, not boot entries.

| Write | Not |
|---|---|
| Restart in Windows? | Set BootNext to Boot0000 and reboot? |
| Play on Windows | Launch via Windows Boot Manager |
| Back to Monet | Return to Linux bootloader |
| Windows wasn't found on this PC. | ERROR: no EFI load option matching bootmgfw.efi |
| Your PC will restart. Open apps will close. | Unsaved data may be lost. Continue? (Y/N) |

Buttons name the action: **Restart**, **Play**, **Cancel**. Never "OK" when a
word would be clearer, except where Windows forces it.

### In every language

Monet's words are written in English in the code and translated in `po/`
(one file per language, 29 besides English; `po/monet.pot` is the list).
`tools/make-translations.py` gathers every text from the sources (QML's
`i18n` calls, Setup's `tr`, the helpers' and scripts' `say`, the Rust tools'
`t!`, menu entries and widgets' names) and builds what each part reads:

- `linux/share/locale/<language>/LC_MESSAGES/monet.mo`, one catalog that
  install.sh also links under the names Plasma looks for a widget's words by
  (`plasma_applet_<widget>.mo`, `plasma_wallpaper_org.monet.hours.mo`). KDE's
  own screens that Monet replaces (lock, shut down, the widget gallery, edit
  mode, the password prompt) ask for `monet` by name (`i18nd`).
- `setup/locale/<language>/LC_MESSAGES/monet-setup.mo`: Monet Setup switches
  language as soon as one is picked, and mirrors for Arabic and Hebrew.
- The menu entries' and widgets' own names (`Name[de]=` and the like), the
  apps' plain names (`linux/share/monet/names.tsv`, which `monet-look` gives
  the apps it renames) and the USB stick maker's table (it picks Windows'
  display language).
- `linux/share/locale/<language>@monet/LC_MESSAGES/<app>.mo`: KDE's apps
  that Monet renames (Files, Terminal, Photos...) say their own name through
  their translations, and Qt ends every window title with it ("Home —
  Dolphin"). These small catalogs, one language of Monet's own for each of
  its languages and English, hold only those names (`APP_NAMES`, from the apps'
  own catalogs), and `monet-names.sh` (Plasma sources it as it starts, from
  `plasma-workspace/env`) puts that language before the session's: "Home —
  Files", in Swedish "Filer", and every other word as before. A display
  language picked in KDE's own Region settings comes later in Plasma's start
  and wins: then the titles are KDE's again.
- Scripts say things through `monet-quick say TEXT VALUE...`; the Windows
  setup's progress lines carry their values beside the text.

Every translation keeps the English `%1`s (`--check`, and a test). A text
whose meaning depends on where it shows gets a note (`i18nc`), as "Play"
does for a game and for music. Monet's own windows mirror for right-to-left
languages (`LayoutMirroring` on each window's root).

## The idea: Impression

Monet is painted, not machined. It's named after the painter, so the desktop
is a painting: *Impression, soleil levant* (1872), the harbor at Le Havre in
the morning mist, with one bright orange sun. Everything else follows from it.

- **The Hours.** One harbor in four lights: dawn, midday, dusk and night. The
  wallpaper drifts from one to the next as the day goes, over 45 minutes, the
  way Monet painted the same view at different times: at this place's own
  sunrise and sunset (dawn an hour before sunrise, midday two hours after it,
  dusk an hour and a half before sunset, night just after; the sunrise
  equation, offline, from the Weather widget's place or else the time zone's
  city in `zone1970.tab`, which `monet-light` hands the wallpaper as `Place`),
  falling back to 5, 10, 17 and 21 where the sun doesn't rise and set.
  **The Magpie** (after *La Pie*, 1869) is the fourth: a farm under snow,
  trees in hoarfrost, a wattle fence and gate with one magpie, Monet's
  colored shadows on snow, all laid in strokes of a flat brush.
  **Through the year** hangs one series a season: The Hours in spring, Water
  Lilies in summer, Haystacks in autumn, The Magpie in winter (half a year on
  south of the equator; `monet-light`'s `season_series`). Rain,
  fog and snow there (Open-Meteo, every half hour; Light & Wallpaper turns it
  off) lay a veil of mist over the painting, darker in the dusk and night
  lights, drifting in over three minutes. Two more of his series
  hang beside it, chosen in Light & Wallpaper, each in the same four lights:
  **Water Lilies** (the pond at Giverny from above: no sky but its
  reflection, the willows' reflections falling down it, islands of pads with
  a flower here and there) and **Haystacks** (two stacks in a field after
  the harvest, glowing on the side the light comes from, their long shadows
  colored by it). All are painted by `tools/make-paintings.py` with the same
  brushwork, so each series drifts through the day like The Hours; the
  placard names the one on the wall ("Water Lilies, dusk"). Every stroke is
  laid with a loaded flat brush: its bristles streak the paint, and its
  tail breaks up where the brush runs dry.
- **One sun.** The only bright color is the sun, and it's kept for the one
  thing that matters: **Play**, **Restart & Play**, **Erase & Install**.
- **Glass.** Panels, popovers and app windows are see-through, with the
  painting blurred behind them. Mist while it's light out, smoke after dark.
- **A placard.** Like the card next to a painting in a museum: the time in a
  soft serif, the date, and which light the painting is in.

The design canvas has all of it, clickable: Desktop, Play on Windows, The
Hours, Language, and the installer concept.

## Layout: three islands

No menu bar, no dock. Three floating glass islands along the bottom:

| Island | What |
|---|---|
| Left | The Monet menu (the sun) and Games (the sun as a play button) |
| Middle | Apps and open windows, then Trash. Running apps get a small dab of sun under them: longer for the window you're in, faint when it's minimized, with a warm wash when an app asks for you. Pointing at one raises a pebble of glass |
| Right | Quick Settings, Sound, status icons, the clock. Brightness and Night Light live in Quick Settings, beside Mist and Smoke, so KDE's own Brightness panel (with its second "Dark Mode" switch) stays out. Sound (`org.monet.sound`) is Monet's own, beside Quick Settings rather than in the tray, where KDE gives every item's popover its own header and box: the icon follows the volume, the wheel turns it, a middle click mutes, and its popover has the volume, where the sound plays and the apps playing (wpctl, `monet-quick sound`). KDE's volume item is known but not chosen in the tray; the volume keys and their on-screen level are KDE's audio shortcuts service, which needs no item. The open icon's pebble keeps to its own cell: Plasma grows it by the island's margins on every side, so the style draws it inset by them |

The islands step aside: each is a "dodge windows" panel, so it slides away
when a window comes over it and back when the pointer touches the bottom edge
(KWin's sliding popups, 240 ms going and 200 ms coming). Light & Wallpaper's
"Bar steps aside" keeps them in view. 0.9.0 made it the default and 0.9.1 took
it back: KWin brings a hidden island back only for a pointer pushed past the
last row of pixels, which a pen, a touchscreen or a VM's mouse can't do. Since
0.9.4 `monet-look` sets KWin's `ElectricBorderPushbackPixels=0`, so touching
the edge is enough, the layout has `hiding: dodgewindows` again, and accounts
that hadn't chosen get it once (`bar-steps-aside`). Kept in view, all three
islands are alike: "windows go below" panels, over windows, none keeping room
of its own. Plasma gives an always-shown panel room of its own and KWin stacks
those rooms, so islands stood a bar's height above each other, and the middle
one alone sat flat on the edge (found by the test bench and the owner).

Where the processor draws the screen (a VM, a graphics card whose driver
didn't load: no render node in /dev/dri) KWin leaves every animation out, the
islands' slide too. With 6 or more processor threads Monet keeps them:
`/etc/xdg/plasma-workspace/env/monet-motion.sh` exports
`KWIN_EFFECTS_FORCE_ANIMATIONS=1` before KWin starts.

The placard sits on the painting, top left.

## Color

| Name | Hex | Use |
|---|---|---|
| Sun | `#F2552C` | Play and the one thing to do next. Nothing else |
| Lily | `#357F72` | Accent: selection, toggles, links, focus (lighter `#4DB4A0` on dark) |
| Paper | `#F3F1EC` | Light ground (Monet Light) |
| Smoke | `#242321` | Dark ground (Monet Dark) |
| Ink | `#1C1B19` | Text on light |

Color schemes: `MonetLight` and `MonetDark`. Their title-bar color has an
alpha value, for apps that draw their own title bars.

## Glass

Two kinds, chosen by the light (Quick Settings → Light: Hours, Mist or Smoke):

- **Mist** (dawn and midday): paper at about 10% on the bar, 34% on popovers.
- **Smoke** (dusk and night): smoke at about the same.

Clear rather than frosted, as Apple's Liquid Glass is: the painting's
strokes still show through. The rim catches the light where it falls on
the pane (the top left) and where it leaves (the bottom right), dim at the
other two corners, a lens of light just inside the edge fades into the
middle (`LENS`, thinner on the bar's short islands), and a soft sheen sits
under the top edge. Quick Settings' tiles, sliders and light choices are
pebbles of lighter glass with a bright edge, as in Apple's Control Center.

Behind both: KWin's blur (strength 3, about as soft as the desktop widgets'
`Glass.qml`, no noise, which read as matte, and saturation 1.7 in kwinrc since
KWin 6.7 folded its contrast effect into the blur), so the glass carries the
painting's light instead of looking grey. Popovers, Settings and Plasma's own
popups paint 24% of the background color over it, the bar 10%; fields on the
glass (the menu's search, the Weather's place, a day's note) are pebbles of
lighter glass with a white rim, never darkened wells. KWin blurs whole
pixels with a hard edge behind panels and popovers, so each frame's mask
rounds its corners 1 px inside the glass's, as Breeze does, and the blur
stays under the glass's soft edge instead of making a jagged halo.

Light in the glass: a rim brightest along the top that fades down the sides
(the sides stretch, so it fades over the whole height), the way light gathers
in the thickness of a pane, and a soft sheen under the top edge. A hairline
of ink outside it keeps the edge. In the corners all three follow the glass's
own arc, so they run on from the straight edges without a step. Tooltips
leave the rim out: on glass that small, a bright line just inside the
hairline reads as a second box inside the first.

| Where | How |
|---|---|
| Islands, popovers, tooltips | Plasma style `monet` (`tools/make-plasma-style.py`), radius 22 / 20 / 12, soft shadow that sits lower than the glass. A solid copy of each (`solid/`) and an opaque one (`opaque/`) without compositing, so they never turn into Breeze. Adaptive transparency is off: a window touching the islands leaves them in the glass Settings has, blur and all, even as they slide away (they turned white on the way down) |
| On the glass | The same style draws everything Plasma puts on it, so the app menu, search, the popovers, notifications, the lock screen and Alt+Tab are Monet's too: pebble buttons (radius 8, so check boxes stay round), a well with a lily ring for typing, soft highlights (an ink wash to point, lily for what's chosen), Monet Settings' switch and slider, glass tabs, hairline headings, a lily progress bar and a lily arc for "working" |
| App windows (Files, Kate, ...) | Kvantum themes `Monet` and `MonetDark` (`tools/make-kvantum.py`): glass at the edges (title, toolbar, sidebar), paper or smoke under the content, rounded controls, a soft Lily selection. Menus and tooltips cast a soft shadow, blur with rounded corners, part groups with a hairline and highlight the item in lily, inset from the edge |
| GTK apps (the Store, Flathub's) | `tools/make-gtk.py`: KDE's own colors for GTK first, then paper or smoke, lily and the sun, as named colors and, for libadwaita 1.6 and newer, as CSS variables. GTK 4 apps draw their own title bar, so they also get Monet's window buttons: the sign alone, and under the pointer the title bars' dab (lily, ochre, the sun). Their page and section titles are in Fraunces. `monet-light` puts the sheet in place of KDE's own `gtk.css`, which for GTK 4 also imports KDE's window shape (`kde_window_geometry.css`); Monet's imports it too. Until 0.9.4 that second import made KDE's file look like someone's own, so GTK 4 apps never got Monet's sheet |
| Zen, the browser | `linux/share/monet/zen`, which `monet-quick zen` copies into each Zen profile and imports from `userChrome.css` and `userContent.css` (at sign-in, and as Zen arrives or makes its profile: `monet-zen.path`; before Zen's first start, Monet makes its profile, already dressed). Behind the sidebar and around the page, the painting blurred and washed in paper or smoke (`tools/make-zen.py`); lily for the accent; Monet's paper and smoke for what pops up; radius 12. Tabs: an ink wash under the pointer, the open one on a pebble of paper. The address field is a well with a lily ring while you type; on a page it floats as a sheet with Monet's soft shadow. The space's name in Fraunces. Zen's welcome and its default-browser question are skipped: Monet makes it the browser. A new tab opens on the painting itself, by daylight in Mist and by night in Smoke. Zen follows the PC's light. Its own theme picker can't override Monet's colors; uninstalling Monet gives Zen its own look back |
| Monet Settings | An app window in Monet's frame, as Games: the list on glass, a solid paper page |
| Title bars | Monet's own window frames (`tools/make-decoration.py`, KWin's Aurorae): the app style's glass, so title bar and window are one sheet, radius 14 at the top and 10 below, a wide soft shadow in ink. The buttons are signs brushed in ink; under the pointer a dab of paint swells up beneath the sign (lily to minimize, ochre to maximize, the sun to close). One frame per light and glass (`Monet`, `MonetSmoke`, and `Solid` of each), switched by `monet-light` |
| Terminal | Konsole color schemes with opacity and blur; a thin cursor, room around the text, the menu behind a button |

Two global themes carry this into KDE's settings: **Mist** and **Smoke**
(`org.monet.desktop`, `org.monet.smoke.desktop`), KDE's Light and Dark. They
differ only in colors, name Monet's glass app style (`widgetStyle=kvantum`) and
never the wallpaper, so choosing one keeps the glass and The Hours. Until
0.9.4 they named no style, and KDE then wrote Qt's plain Windows style as the
default and dropped the account's: every window and menu turned plain (found by
the owner). `monet-light` puts the glass style back too, at every apply and
right after KDE's buttons (`sync`), unless the account set a style of its own;
and `monet-look` found Kvantum at all only from 0.9.4: it asked with one `ls`
of two library folders, which fails when either is missing (Fedora has only
lib64), so until then KDE's own style drew every app. Picking one on the first page of
KDE's settings keeps Mist or Smoke, and its Automatic is Follow the hours
(`monet-light sync`); KDE's own Global Theme page, with its "Dark Mode", is
hidden. Mist and Smoke are the colors; the painting goes through the whole
day, dawn to night, whatever colors were picked, while Light & Wallpaper's
Through the day is on (and through the seasons with Through the year). Off,
it stays: on midday with Mist, on night with Smoke (`monet-light paint`).
Until 0.9.4, Mist drifted only between dawn and midday and Smoke between dusk
and night; people wanted the day on the wall with the colors they'd picked.

When something in More settings changed how Monet looks, Light & Wallpaper's
**Monet's look → Put back** brings it back for that account in a few seconds,
no restart: `monet-quick look-reset` runs `monet-look --reset` (an update's
pass, keeping the panels, but every one of Monet's settings again, what was
changed since included) and `monet-light paint wall`, which also brings The
Hours back to a desktop where KDE's dialog put another wallpaper (choosing a
painting in Settings does that too: it used to do nothing there). While it works
the card says Putting it back…, then its pill says Done in lily for a few
seconds (it had looked as if nothing happened). Reset this PC
is the heavier way, for every account at the next start.

KDE's System Settings, opened as More settings, says so in its windows' titles
("Display Configuration — More settings"), through the same `<lang>@monet`
catalogs that call Dolphin Files (`APP_NAMES` in `make-translations.py`, which
takes a name that isn't a menu's from Monet Settings' own words).

Switching takes about a second (it took three, and held up the bar): the
switch reads KDE's settings from the files themselves rather than a
`kreadconfig6` for each, the colors, app style, frames and terminal change side
by side, and the painting goes to Plasma only when something about it changed
(`$XDG_RUNTIME_DIR/monet-painted`), so Mist to Smoke doesn't reload it.

Glass is for edges; anything you read sits on paper (or smoke). **Glass** in
Light & Wallpaper is a slider of four steps (`monet-quick glass LEVEL`, saved
as `"glass"` in prefs.json; 0.9.3's true and false are Clear and Solid):

| Step | Panels and popovers | Apps | Frames | KWin's blur | Desktop widgets |
|---|---|---|---|---|---|
| Clear | `monet` | `Monet` | `Monet` | strength 3, no grain | the painting's strokes softened, with the lens |
| Frosted | `monet` | `Monet` | `Monet` | strength 8, grain 3 | blurred twice as much, a heavier wash (`glass-frosted`) |
| Matte | `monet-matte` | `MonetMatte` | `MonetMatte` | strength 12, grain 5 | only the painting's color, no lens (`glass-matte`) |
| Solid | `monet-solid` | `MonetSolid` | `MonetSolid` | (no glass) | paper (`glass-off`) |

Matte's themes are the glass ones taken 70% of the way to solid
(`tools/make-plasma-style.py`, `make-kvantum.py`, `make-decoration.py`): the
painting's color comes through, its strokes don't, and KWin's grain makes it
read as etched glass rather than a grey film. `monet-light` loads KWin's blur
whenever there's glass: on the first sign-in KWin can start without it, and
glass without blur is a sharp see-through window (found by the test bench).

Monet's own app windows (Games, Settings, the Store) are glass too, the way
Settings' column was while it was a sheet of Quick Settings: each window is
see-through, `glaze` (monet-games) asks KWin to blur behind it through KDE's own
library (`KWindowEffects::enableBlurBehind`, called with ctypes, as there's no
Python binding; the request is taken with the window's next frame), and
`WindowGlass.qml` washes mist or smoke over the blur: 42% on Clear, 56%
Frosted, 80% Matte, paper on Solid, following the slider at once through the
same flags as the desktop widgets. The pages stay all paper. Without KWin's
blur (another desktop, a PC whose processor draws the screen) they're paper.
Monet picks Solid by itself where the processor draws the screen (no graphics
driver, or a virtual machine), until it's chosen. `glass-off` also makes the
lock screen skip its full-screen blur: with the widgets' live frost, the two
heaviest things to draw on an old PC.

An older PC (8 GB of memory or less, or `/sysroot` on a spinning disk:
`monet-quick older-pc`) gets three things at each sign-in from
`monet-session`: `~/.config/monet/glass-lite`, so `Glass.qml` frosts to the
edge without the lens's second grab and blur; Baloo's "only basic indexing"
(names, not contents), once, unless it's been set; and Steam's autostart
hidden by a user copy marked `X-Monet=true`, with Steam started 45 s later
by a transient `monet-steam-later` timer. A PC that's no longer older gets
its glass and Steam back; a Steam autostart of the user's own is left alone.
The answer is kept in `~/.cache/monet/older-pc` with the Monet version and
`MemTotal` it was worked out for, so Python starts for it only when those
change.

Every PC's sign-in leaves what can wait until the desktop is up: framing the
apps Monet hasn't painted, games on a laptop's NVIDIA chip and Zen's look run
as `monet-session --later`, a minute after sign-in at nice 19 and idle I/O
(a transient `monet-after-sign-in` timer), and only when this Monet, the
menu's app folders or Zen's profiles changed since they last ran
(`~/.cache/monet/apps-seen`); while signed in, their `.path` units keep them
current. Before the sign-in screen, `monet-ready-boot` only starts after a
trip to Windows, and `monet-keep-prepare` stops starting once
`/var/lib/monet/home-subvolume` says the homes need nothing more.

Monet comes in two images from one Containerfile (`ARG BASE`): `monet`, on
Bazzite's NVIDIA image (NVIDIA's open driver, Turing and newer: GTX 16 / RTX
20, PCI ids from `1e00`), and `monet-amd`, on Bazzite's AMD and Intel one
(Mesa, whose nouveau also draws with older NVIDIA cards). Both installers
choose by the PC's graphics: the kickstart's `%pre` writes the
`ostreecontainer` line it `%include`s, and Monet Setup uses `pc.image_for`.
Updates follow the image installed.

Monet Setup checks the PC from its first page (`setup/monet_setup/pc.py`):
under 3 GB of memory can't install; an NVIDIA card older than Turing (alone
or beside built-in graphics), or under 7 GB, is said on Ready.
UEFI needs no check: the stick only starts that way.

KDE's System Settings and other apps written in QML keep solid backgrounds
(they draw their own), in Monet's colors. That's why Monet has its own
Settings in front of it.

## Type

- **Fraunces** (SuperSoft, 72pt optical size; SIL OFL, shipped in
  `linux/share/fonts/monet`) for moments: the clock, titles, greetings,
  window titles.
- **Inter** for everything you read and click. Regular and semibold.

## Icons

- **Monet**: the sun and three strokes of its reflection. No container.
- **Games**: the same, with the sun turned into a play button.
- **Every icon is a small oil painting** (`tools/make-icons.py`): short
  strokes of unmixed color side by side, shadows in violet and blue instead
  of grey, light in warm cream, and paint thick enough to catch the light
  from the top left. No tile or circle behind them.
- **Motifs from Monet's world, not a computer's:** a painter's palette for
  Settings, a night canvas on an easel for Terminal, the harbor's masts
  rising like a graph for System Monitor, a market bouquet for the Store, a
  garden pot from Giverny for Trash. KDE's apps too: a gilt frame
  (pictures), an open book (documents), an abacus, a little stage (videos), a gramophone (music),
  a sunflower (disk usage), a letter and quill (text), a chest (archives),
  a box camera (screenshots). The app menu's categories as well, and
  Monet's widgets: the sun behind a cloud (Weather), the card beside a gilt
  frame (Placard). In a bar Plasma asks for Trash's "-symbolic" names, so
  the pot's painting answers those too, and Files' menus get the pot's ink
  sign from the menu-size folder, which comes first.
- **Toolbars and menus are ink too**: the signs KDE's standard menus and the
  everyday apps' toolbars ask for (save as, print, recent, find and replace,
  zoom to fit, full screen, rotate and crop, shuffle and repeat, and so on),
  brushed like the bar's and tinted with the light, so no flat Breeze sign is
  left among them. Rotate sweeps round a picture's corner, so it never reads
  as the padlock.
- **Big apps people add keep their own marks**, painted the same way, so
  they're known at a glance: Zen's three rings as ripples on a night pond,
  Discord's Clyde in blurple, Spotify's green sun with its three waves,
  OBS's three wheeling rings, Krita's veils of color under its brush,
  LibreOffice's pages with the corner folded in each app's color,
  Thunderbird's blue bird round a letter, Chrome's wheel, VLC's striped cone
  and Telegram's paper plane. For games: Heroic's shield and sword, Prism
  Launcher's colored hexagon, RetroArch's space invader, Bottles' three
  bottles. For making things: GIMP's Wilber with his brush, Blender's orange
  eye, Kdenlive's clips and playhead, Audacity's headphones round a wave, VS
  Code's folded ribbon, Obsidian's crystal, Signal's bubble in its ring of
  dashes. Each answers its Flathub name and its plain one.
- **Every other app sits on Monet's canvas**: a small primed canvas, painted
  once (`frame-canvas.png` in textures), with the app's own icon on it and
  the paint's relief (`frame-relief.png`) laid over both, so a flat icon
  looks painted too. `monet-quick frames` makes them in the account's own
  copy of the theme, found before the PC's: at sign-in and whenever the
  Store adds or removes an app (`monet-frames.path`). It frames each menu
  app Monet hasn't painted with the icon KDE would have shown (Breeze's,
  then the app's own), takes a frame away once Monet paints that app or it
  is gone, and leaves any icon it didn't make alone. Steam's games get one
  too.
- **Account pictures** (`tools/make-avatars.py`, what Change Avatar offers):
  pieces of The Hours and small paintings from Monet's world (a water lily,
  poppies, the Japanese bridge, a haystack, the magpie, irises, a parasol,
  a sailboat) with the icons' brush, square to the edges since they're
  shown round. On the image they replace KDE's dragon and photos.
- **Folders** are cut from the paintings: the front of each folder is a piece
  of one of the Hours (Home and the plain folder at dawn, Desktop at midday,
  Pictures, Music and Videos at dusk, Downloads and Games at night), with a
  small white mark for what's inside. Documents is paper with lines of ink.
- **Files** are sheets of paper with something painted on them: lines of
  ink for text, three inks for code, a piece of dawn for pictures, a note
  for music, dusk with the play sign for films, a wax seal for PDFs, a lily
  grid for spreadsheets, the play sign for programs; archives are the chest.
  **Drives** are what a painter carries colors in: a paint box for disks, a
  tube of paint for USB sticks, a disc for discs. Breeze has an icon for
  nearly every exact file type, found before the generic one, so `aliases`
  lists the names and `install.sh` links them to the paintings.
- **The bar's signs** (sound, network, Bluetooth, battery, brightness, media,
  notifications, clipboard, drives, the arrow that opens the rest) are
  brushed in ink, tapering like a brush, and recolor with the light. Sleep is
  the moon, shut down the setting sun. Plasma 6.7 takes them from the icon
  theme by name (`status/`, drawn with the Plasma style's brush), never from
  the Plasma style, and tints them because the theme follows the color
  scheme. A drive gets its sign under its exact `-symbolic` name, or KDE would
  shorten the name to its painting.
- **Message boxes** (Monet's own questions and every app's) carry the same
  ink: a ring with i or ? in lily, ! in amber, a cross in vermilion, a tick
  in green. Never Breeze's warning triangle. Monet's questions are questions
  (a question sign, the answer on the button), not warnings, and when
  something fails the box says why in plain words, with the details behind
  a button instead of a file's path.
- **One grid.** Every motif is laid out on a 128 grid and fills about 0.8 of
  it along its long side, centered, so the dock reads evenly. Painted at
  512 px, kept at 256 inside SVGs.
- **What Bazzite brings** gets Monet's motifs too, so nothing on the dock or in
  the menu is someone else's: a window thrown open onto the harbor for the
  browser, a locomotive steaming into Saint-Lazare for Steam, a rowing boat on
  the Seine for Lutris, the Japanese footbridge at Giverny for Bazzite Portal,
  a sealed letter for Flatseal, market crates for Warehouse, a brass gear for
  Gear Lever, pigment jars for DistroShelf, a balloon for ProtonUp, a watering
  can for Waydroid, piano keys for Input Remapper, café cups for the forum, a
  teapot for Bold Brew. Bazzite's own entries name their pictures by path, so
  the image points them at these.
- **Menus and toolbars** get signs brushed in ink like the bar's (in the
  icon theme's `actions/`, recolored with the light): the desktop's
  right-click menu, Files' toolbar and context menu, the power buttons.
  Names that are also settings pages get their sign only at menu size
  (`actions/16`, first in the theme's folders), so More settings keeps its
  swatches. Signs Monet hasn't drawn yet are Breeze's, in Monet's colors.
- Everything is in the `Monet` icon theme (`tools/make-icons.py`). Games keep
  their covers.
- **After an update**, KDE would draw Monet's new pictures with what it
  measured in the old ones (it keeps that by file and time, and on Monet's
  image every file keeps its time), so `monet-fresh` clears KDE's caches
  once, at the first sign-in of a new version, before KWin and Plasma start.

## Pointer

`Monet-cursors` (`tools/make-cursors.py`): ink with a paper edge and a soft
shadow, at 24 to 64 px. While something works, Monet's sun breathes over its
rippling reflection, as at start. Resize, move, text, hand and the rest in
the same ink; anything not drawn falls back to Breeze.

## Starting and signing in

- **Boot screen** (Plymouth `monet`, the same as Monet Setup's): the harbor
  at dawn with the sun breathing. A disk password is asked for on it, in a
  line of white with a dot per letter. Built into the image's initramfs.
- **Sign-in** (KDE's Plasma Login Manager, as Bazzite's desktop has it): the
  harbor at night, with Monet's fields, buttons, colors, icons and pointer
  (its home links to Monet's at every boot). Its layout is built into it, so
  it stays KDE's.
- **Lock screen** (`linux/share/monet/lockscreen`): at rest, the painting
  and the desktop's placard, low on the left. A key or the mouse softens the
  painting (blurred, washed in mist or smoke) and raises a sheet of glass
  (Rise): your face or your initial on a dab of lily, "Welcome back" in
  Fraunces, the time and date, the password well and the sun to unlock,
  then Sleep and Switch user. A wrong password shakes the sheet. Plasma 6.7
  reads the lock screen from its desktop shell, not the global theme, so the
  image puts `MonetLockScreen.qml` beside KDE's files there and swaps KDE's
  `LockScreen.qml` for one that opens Monet's, or KDE's own if Monet's can't
  load. Everything that unlocks works as in KDE's `LockScreenUi.qml`.
- **Restart and shut down** (`linux/share/monet/logout`, put into both global
  themes' `logout/` by install.sh): the desktop softens behind a sheet of
  glass with one question. Asked to restart, shut down or sign out, it says
  "Restart now?" in Fraunces, counts down from 30 ("Your PC restarts in 30
  seconds. Open apps close, so save your work first.") and puts the sun on
  the answer beside Cancel. From the menu's power sign, Ctrl+Alt+Del or the
  power button, it offers all of them under your face and "See you soon":
  the moon to sleep, restart, the setting sun to shut down, sign out. Going
  ahead, the screen fades to night (Sunset) first; Esc or a click outside
  cancels; a key on any screen stops the countdown on all of them (`timer.js`).
  KDE's logout greeter shows KDE's own if this can't load.
- **Password prompt** (`image/password`): when an app needs more rights, a
  sheet of paper or smoke says "Allow this?", what the app wants in its own
  words and for whom, then the password well, Cancel and the sun to allow;
  Details shows what exactly is asked for. A wrong password shakes it. KDE's
  agent builds its page into itself, so the image builds the agent (the same
  version as its Plasma) with Monet's page instead, keeping KDE's inside for
  when Monet's can't load, and starts that build in KDE's place. If the
  build fails, the image keeps KDE's prompt.

## Widgets

Like a desk: glass cards on the painting, added from the desktop's widget
gallery. A fresh desktop has the placard, Weather and Calendar: on the image a
new account starts with Monet's look, so Plasma lays them out itself as it
first starts, and `monet-widgets` gives any desktop without Weather or Calendar
all three, once (one laid out before there were widgets, or where Plasma's
first layout found no desktop). It looks at every desktop whatever its
activity, and counts it done only once Plasma had one, so a slow first start
is tried again at the next sign-in.

- **The glass** (`linux/share/monet/widgets/Glass.qml`, copied into each widget
  by install.sh): widgets share the desktop's surface with the wallpaper, so
  KWin can't blur behind them. The glass finds The Hours in the scene and
  shows the patch of painting it covers (following the light as it drifts,
  and the widget as it's moved), as through clear glass: the strokes only
  softened, washed lightly in mist or smoke, and along the edge a lens that
  magnifies and brightens them, fading into the middle. The rim catches the
  light at the top left and bottom right (a Shape ring with a diagonal
  gradient); a hairline and a soft shadow outside. Elsewhere, or with glass
  off, paper.
- **Weather**: the temperature in Fraunces, the sky painted beside it (the
  sun and its reflection for a clear day, a crescent at night, clouds, rain,
  snow, fog, a storm) and the next four days. From Open-Meteo once a place is
  chosen: no account, only the place is sent. The place is chosen right on
  the card ("Where are you?", a town, then one of three matches), never in
  KDE's settings window; click the place's name for another. The first
  place sets the degrees the way the PC's region counts them. Every place
  chosen is kept (`places`, in order): ‹ › beside the name go through them,
  each keeps its last forecast so going back is instant, and the widget's
  right-click menu adds one or forgets the one shown.
- **System**: a dial each for the processor, the graphics and the memory,
  a stroke of paint in lily, ochre past 60% and the sun past 85%, the
  temperature (or the memory used) beneath and the network along the foot.
  KDE's own sensors (`org.kde.ksysguard.sensors`, as System Monitor); of two
  graphics chips the busier counts, and a part the PC can't measure leaves.
- **Recently Played**: the games played last (`monet-quick played`, newest
  first): Steam's (the appmanifests and each account's localconfig, Steam's
  tools left out), Heroic's (its `store/timestamp.json`), Lutris' (`lastplayed`
  in its pga.db) and the ones Monet sent to Windows (`monet` records each
  trip's game in `~/.local/state/monet/played-windows.json`); the latest of a
  game played on both sides counts. Each its tall cover (Steam's picture cache
  or its store's, Lutris' cover art) or a painted card with its name, and
  when it was played; the sun comes up over a cover under the pointer, and a
  click starts it the way its launcher does (`monet-quick play`), or, for one
  played in Windows last, asks before restarting there (`monet play …
  --confirm`, as the app menu's games). As many as the card is wide.
- **Timer**: the sun goes round a ring as the time runs out; 3, 5, 10 or 25
  minutes, or the wheel over the time. The end is kept, not the count, so it
  keeps going if Plasma starts again; when it's up, `monet-quick ring` says
  so in a notification and plays the sound theme's alarm. **Focus** makes it
  a plein-air session: Do Not Disturb until it ends, and The Hours runs a
  whole day, dawn to night, over the session (`monet-quick focus`, which
  hands the wallpaper `Focus=start,end`).
- **World Clock**: towns from KDE's time zones (their names in your
  language), each a little face, paper by day and smoke by night, how far
  ahead or behind it is, and its time in Fraunces.
- **Batteries**: everything with a battery, as Apple's widget has it, from
  UPower (`monet-quick batteries`, every minute): this laptop first, then
  the mouse, the keyboard, controllers and headphones, each a ring of paint
  round its sign (Monet Settings' device glyphs), lily while there's plenty,
  ochre under 20% and the sun under 10%, and a dab of the sun beside the
  number while it charges. With nothing to show, a line saying what will.
- **Calendar**: just the month at first, in Fraunces, today on a dab of
  the sun. The arrows or the wheel turn the month, a click on its name comes
  back to today; the arrow keys move the chosen day. A click chooses a day:
  a day with a note has a dot of lily (point at it to read the note), and
  the line under the month says the chosen day's note, or "Nothing planned".
  The Notes button, that line, or a click on the chosen day brings the notes
  out in a panel beside the card (on the side the month reads towards):
  the date in Fraunces (today's in the sun's color), ‹ › to the day before
  or after, Today, the note on a sheet, kept as you type, and what's coming
  up. Wide enough, month and notes sit side by side on the card.
- **Clock** (in the right island, instead of KDE's): the time over the date
  in Inter; a click opens the day in Fraunces and its month, drawn as the
  Calendar draws it, and the same notes come out beside the month. Both
  widgets share `Month.qml`, `DayNotes.qml` and `NoteStore.qml`
  (`linux/share/monet/widgets`, copied into each package by install.sh);
  the notes themselves are `monet-quick notes`/`note`, one JSON file by date
  (`~/.local/share/monet/notes.json`), written whole and swapped in, so a
  note written at the clock shows on the desktop. The Calendar's older
  notes, kept in its own settings, are handed over once (`notes-merge`,
  which never writes over a day already kept).
- **Now Playing**: the cover, the track in Fraunces, back, play or pause on
  the sun, and next; a thin line of how far along, the time gone and left
  at its ends, to click or drag; the cover brings the player forward. With
  nothing playing, the empty stage and "Play something with": chips for the
  music apps there are (`monet-quick music`, the PC's own player first), or
  the Store to find one.
- **Note**: paper pinned with a dab of lily; kept as you type.
- **Photo Frame**: your Pictures in a gilt frame, a new one every ten
  minutes, fading from one to the next; ‹ › on pebbles of glass while
  pointed at, and a click opens the picture in Photos.
- **The gallery** (`linux/share/monet/explorer`), after the way a Mac edits
  its widgets: from the desktop's right-click menu (Add or Manage Widgets,
  which KDE leaves out of it and `monet-fresh` puts back before Plasma
  starts) or Settings → Light & Wallpaper → Edit widgets. Glass down half the
  screen with "Widgets" in Fraunces and Done; down its left a search well and
  Monet's widgets for where you're adding one (the desktop's or the bar's),
  each with its painted icon, then More widgets; beside them big cards, two
  side by side or the chosen one alone, each with the widget's name, what it
  does, a picture of it, + Add in lily, and "On your desktop" with Remove for
  the ones out already. Everyone else's widgets (KDE's too) are a plain list
  under More widgets. Click a card to add it, or drag it where you want it.
- **The desktop's right-click menu**, as Windows has it: Create New, Paste,
  Undo and Icons (Files' part), Open Terminal and Add or Manage Widgets, then
  **Display settings** and **Personalize**, which open Monet Settings' Display
  and Light & Wallpaper pages, in Windows' own words in each language. The
  Hours adds those two (a wallpaper's entries are the only ones Plasma's menu
  takes in), with the runner that opens Settings made only when one is clicked,
  as the lock screen shows The Hours too. KDE's Desktop and Wallpaper and
  Display Configuration (they opened KDE's dialogs), its edit mode, Lock Screen
  and Show Logout Screen are out (`monet-fresh`, once per account, again after
  a fresh layout). With a wallpaper other than The Hours, Light & Wallpaper's
  Put back brings it and the two entries back.
  The pictures are just the widget, cut out with its shadow: its glass as
  it frosts The Hours, but no painting around it. In mist and in smoke
  (`contents/screenshot.png` and `screenshot-smoke.png`, which KDE's
  gallery shows too); the bar's are their islands. Plasma reads the gallery
  from its desktop shell, so the image keeps KDE's as `KdeWidgetExplorer.qml`
  and swaps in a `WidgetExplorer.qml` that opens Monet's, or KDE's if
  Monet's can't load.
- **Edit mode** (`linux/share/monet/editmode`), while the gallery is open or
  after a press and hold on a widget: Plasma shrinks the desktop beside the
  gallery, as the column of current widgets on a Mac. Monet puts it in a
  frame of paper or smoke on a wash of mist or smoke, with a line on how to
  move, resize and remove widgets, More (bars and desktops), Add widgets and
  Done. KDE's edit mode blurs the whole desktop behind the frame and draws it
  twice, at every change, which stutters wherever the processor draws the
  screen (as in a virtual machine); the wash doesn't. Shell file, kept KDE's
  and swapped as with the gallery (`DesktopEditMode.qml`). The bar's islands
  stay on one row: while editing, Plasma gives each its own strip of the screen,
  and KWin used to pile them up a bar's height apart. Monet Snap moves each one
  back down. Plasma widens the islands for editing a moment after it piles them
  up, so the move uses the new width (worked out from where KWin put the
  island), not the one it still has; using that would have sent Plasma's
  width back to it.

## The menu

The sun in the left island (`org.monet.menu`, instead of KDE's Kickoff):
one sheet on the popover's glass. At the top a search well, typed into
straight away; then **Pinned**, six to a row, and **Recent**, the files you
opened last, each with where it is. All apps lists everything from A to Z
under letters in Fraunces, and typing anywhere searches apps, files and
settings at once, with lily on the result Enter opens. At the foot, your
face (or your initial on a dab of lily) and name, which open Accounts, then
Lock and the power sign, which asks on the restart and shut-down screen.
The Meta key and Alt+F1 open it. Right-click an app to pin or unpin it.

KDE's menu models do the work (`org.kde.plasma.private.kicker`), so the
pins are KDE's: a new account starts with Monet's (`kicker-extra-favoritesrc`)
and one that had KDE's menu keeps its own. `monet-look` puts it where KDE's
menu was on kept panels, with its shortcut, once.

## Apps

**Files** (Dolphin with the Monet app style): glass title, toolbar and
sidebar; the files on paper; folders big enough to see their paintings
(80 px, previews on); a soft Lily wash for the selection instead of a solid
block.

**Monet Settings** (`monet-settings`, its window `share/monet/settings-app/MonetSettings.qml`):
one window, about 1000 × 780. What other systems have, Monet's way: Sound
lists the apps playing and gives each its own volume (`wpctl` streams, as
Windows' mixer does); Quick Settings picks where sound plays under its
volume; Wi-Fi offers a hotspot (NetworkManager's own, named after the PC
with a password it makes up, both shown); and Power & Sleep, where the
battery can do it (`charge_control_end_threshold`, as on ThinkPads),
offers Protect the battery: charging stops at 80% (`monet-charge`, the one
root program Monet's polkit rule allows besides `monet`, kept in
`/var/lib/monet/charge-limit` and put back at every start by
`monet-charge.service`). A new account's first sign-in opens Settings on a
welcome page (`monet-quick open welcome`, once): Quick Settings, the
widgets, Play on Windows, the light and search, each with its way there. Play
on Windows offers Ready when you come back (off until chosen, as it signs
in without asking first): Linux can't hibernate with Secure Boot (the
kernel's lockdown), so Monet can't stay in memory while Windows runs
(and Windows doesn't either: Back to Monet restarts it, as a hibernated PC
stays off until the power button); instead, `monet-ready-leave.service` arms at shutdown when
BootNext is Windows' boot manager, `monet-ready-boot.service` (before every
sign-in screen) writes a one-time `[Autologin]` for `plasmalogin` when the
trip is fresh (a day at most) and clears it otherwise, and the session's
`monet-ready-lock.service` (after KWin, before plasmashell) locks a sign-in
whose PAM service is `plasmalogin-autologin`, so the lock screen shows
first and the desktop starts behind it. About shows the last start: the
PC's own (firmware), Monet's (loader, kernel, system: `systemd-analyze`)
and the desktop's (sign-in to plasmashell), and **Save a report** writes one
text file into Documents (`monet-quick report`): Monet's version and `monet
doctor`, `rpm-ostree status`, the PC (DMI, `lscpu`, `lspci -nnk`, `lsusb`, disks),
the screens and KWin's support information, battery (`upower`), network,
radios, Bluetooth and sound, the start's timing, failed services, this start's
errors and the kernel's warnings, sleep and waking, the session's errors,
Monet's services, the start before's errors and how it ended, a week's
crashes, and Monet's records (trips to Windows, going back, Windows' setup),
each cut to its useful end. Headings in English, for whoever it's sent to; it
stays on the PC until it's sent, and a notification shows it in Files. On the glass: the name in Fraunces, search,
and the pages, each marked by a swatch cut from the paintings with a white
glyph, in three groups: the light, the network, printers, the screen, sound,
the clock and you; the pointer, power, the lock and privacy, notifications,
accessibility, default apps and storage; and games and controllers, Windows,
Updates and About. Every page is Monet's own, each with a "More…" button at
its foot for KDE's page of the rarer settings. A pebble of glass glides to the page
you're on. On the paper: the page under its swatch, title and a line saying
how things stand ("Connected to Harbor"), in rounded cards with switches
(Lily when on), devices with what they are (headphones, a controller, a
mouse) in a chip that turns lily while connected, and the sun only for
Restart in Windows. Updates looks for a new Monet, app updates and the PC's
own firmware (UEFI, disks, docks: fwupd, from their makers through LVFS)
together, and installs each from its own button; firmware that installs
during a restart says so. Monet and the apps also update by themselves once
a day (`monet-update.timer`, at low priority: the apps at once, a new Monet
put in place for the next restart, never while you work), until Update
automatically is turned off (`monet auto-updates off`, kept as
`/var/lib/monet/auto-updates-off`). Bazzite's and KDE's own updaters stay
masked, so only Monet's runs. Date & Time shows the time as your clocks will,
sets it from the internet and finds a time zone by its city; 24-hour time
switches the locale Plasma exports at sign-in (`plasma-localerc`'s
`[Formats] LC_TIME`, en_US ↔ en_GB, so dates follow), which Monet's clock,
the placard and the lock screen show. Accounts shows you with your picture
(or your initial on lily), changes your name (AccountsService) and your
password (`passwd` in a terminal of its own, the password sealed with a
one-time pad on its way), and lists the other people; adding or removing
someone is KDE's page, More account settings. Mouse & Keyboard sets every
mouse alike and every touchpad alike (speed, tap to click, natural
scrolling, left-handed, off while typing) through KWin's input devices on
D-Bus, which keep what's set, and keeps the layouts you type in (kxkbrc,
which KWin watches), searched by name, the first one first. Power & Sleep
offers the power mode as three choices (power-profiles-daemon, at once) and,
plugged in and on battery, when the screen turns off and when the PC
sleeps, then what the power button and the lid do: PowerDevil's own
settings in `powerdevilrc`, reread as they change. Choices of a few are
Segments: the chosen one on a pebble. Notifications has Do Not Disturb, the
sounds, when it goes quiet by itself (fullscreen, sharing the screen, urgent
ones let through), where popups go and how long they stay, and each app that
has notified, to let it pop up or not (`plasmanotifyrc`, watched by
Plasma). Default Apps shows what opens web links, mail, folders, music,
video, photos, PDFs and text, and the apps that can, set in
`mimeapps.list`; a kind with no app at all offers the Store. Accessibility
sets the size of everything (each screen's scale, `kscreen-doctor`), the
pointer's size, less motion (KDE's animation speed at 0, which Monet's own
pieces follow too, and which Monet's look then leaves alone), the screen
reader where Orca is, and the magnifier: KWin's Zoom effect, loaded and
unloaded over D-Bus (`org.kde.kwin.Effects`) and kept in `kwinrc`, with
KWin's own shortcuts (Windows key and + or −).

**Phone** is KDE Connect (Bazzite's, with its menu entry renamed Phone), in
Monet's words and never by its name: `kdeconnect-cli --list-devices` (read in
English) for the phones paired and near, their battery from KDE Connect's
D-Bus (`…/battery`, `charge` and `isCharging`), and Pair, Ring, Send a file…
(KDE's file dialog, then `--share`), Texts (`kdeconnect-sms`), Files on your
phone (`kdeconnect://`) and Forget. With no phone yet, a QR code
(`phone-qr.png`, made by `make-icons.py` with segno: ink on a white tile)
leads to KDE Connect's download page, for Android and iPhone alike. The page
looks again every four seconds while it's open, as phones join the Wi-Fi and
pairings are answered on the phone.

**Fingerprint** (Lock & Privacy) shows with a reader (`fprintd-list`, read in
English): set up, a finger unlocks the screen and answers administrator
questions (polkit, `sudo`). Bazzite has fprintd but leaves authselect's
fingerprint step off; the image turns it on (`authselect enable-feature
with-fingerprint`, as Bluefin does), and Monet's lock screen already says "or
scan your fingerprint". Setting a finger up is KDE's Accounts page. The
sign-in screen (Plasma Login Manager) can't take a finger yet.

**Text from a picture** is Screenshot's (Spectacle's) Extract Text, all on the
PC (Tesseract). Bazzite has fifteen of Monet's languages' data; the image adds
the rest, and `monet-look` sets Spectacle's `ocrLanguages` to your language
and English once (`ocr_language`: `sv_SE.UTF-8` is `swe`), unless you've
chosen others. Storage shows what fills the disk in one bar (games,
apps, your files, Monet) and makes room: the Trash, asked once more before
it's emptied, and Downloads, opened in Files. Its OneDrive card puts OneDrive in
Files: `monet-quick onedrive-connect` answers rclone's setup questions with their
defaults (`rclone config create --non-interactive`, then `config update
--continue` for each step) except that the sign-in happens in the browser here,
then `monet-onedrive.service` mounts it at `~/OneDrive` at each sign-in, with a
place of its own in Files (`files_place`'s `monet-onedrive`). Files come down as
they're opened and stay cached a month (up to 20 GB). While the browser's
sign-in waits, Cancel stops rclone (`onedrive-cancel`), and whatever rclone kept
of the unfinished sign-in is deleted. Disconnect stops the
mount, forgets the account here and takes the place away. Updates offers the Monet
before the last update, kept by bootc: Go back, asked once more, starts it
at the next restart, and lists what's new in this Monet (the newest "New in"
section of the release notes, which the package carries); once after an
update, a note offers it at sign-in. Games & Controllers lists the
controllers connected (the kernel's joysticks, with the battery a wireless
one reports), pairs a new one (KDE's Bluetooth wizard) and tests its buttons
(KDE's page), switches the performance overlay (MangoHud, from the next
sign-in, in Monet's colors unless you've made your own) and shows where games
are kept (Steam's libraries, and ~/Games for Heroic and Lutris), each opened
in Files. Lock & Privacy sets when the screen locks and whether waking asks
for the password (KDE's screen locker), and whether Files and the menu
remember what you opened, with forgetting it (asked once more). Printers
shows each printer (the ones on the network turn up by themselves), its
state and what's waiting, and makes one your default (yours alone, no
password); adding one is KDE's page. Mouse & Keyboard ends with the keys to
learn by, as key caps, the Windows key as its four panes. The `monet-quick`
helper does the work. Settings is an app of its own (`monet-settings`, since
0.9.4; a sheet of Quick Settings before), built from Games' pieces: Qt for
Python, Monet's words through KDE's i18n calls (`Words`), `helper.run` for
monet-quick and monet, and one window (a local socket hands a second start's
page and activation token to the open one, which goes to that page). Its
window is `linux/share/monet/settings-app/MonetSettings.qml`, in Monet's frame:
KWin resizes it, fills the screen with it and snaps it, a bar restart doesn't
close it, it keeps its size (QtCore's Settings), and it takes the keyboard (its
search, Esc to close). The menu, the dock and Windows+I start it directly;
Quick Settings, the desktop's menu, links and notifications go through
`monet-quick open [page]`, which starts it in a scope of its own (systemd-run,
app.slice), or KDE's System Settings where it isn't installed. Opened again
from the bar, an open Settings has no token of the desktop's to come forward
with, so Monet Snap lets Monet's own apps (Settings, Games) forward when they
ask (KWin only flashed them in the taskbar). It opens in about 1.3 seconds in
the test VM, which draws on the processor; the sheet was there at once, as
part of the bar. Pictures come from `make-icons.py` into
`linux/share/monet/settings`.

**More settings** is KDE's System Settings, one click away from Monet
Settings for anything rarer, and it shouldn't feel like another product.
Its list has Monet Settings' marks: the same swatches cut from the
paintings with a white sign, one painting per part of the list
(`make-icons.py`, `MARKS`). It leaves out the pages for what Monet's look
and light take care of (KDE's Global Theme with its Dark Mode, Day-Night
Cycle, colors, styles, window frames, icons, splash and sign-in screens,
effects), KDE's updater, and the pages about what's inside, like About
this System. KDE's own first page (Quick Settings, with its own theme
buttons and wallpaper), its wallpaper page, Activities and KDE Wallet go
too. The list is one file, `share/monet/hidden-settings-pages`: `install.sh`
adds it to `/etc/xdg/kdeglobals` for everyone, since Bazzite locks that
group there (`[$i]`) and KDE then ignores an account's own copy, which
`monet-look` still writes for systems without the lock. Without its first
page KDE's settings would open on a page saying Plasma, so Monet always
opens them at a page: the one for where you are in Monet Settings (Light &
Wallpaper goes to Fonts), otherwise General Behavior (`KDE_PAGES` in
`monet-quick`, `kdePage()` in Settings, and the hidden menu entry's `Exec`).
Its groups say what Monet Settings says (Display, Sound, Default Apps,
Desktop): user-level copies of KDE's group files, which it reads first. The
pages keep KDE's names, which are built into each page. Help menus don't
offer About KDE (KDE's kiosk settings, written by `monet-look`).

An update runs `monet-look` again (`--keep`, once per Monet version). It writes
a setting only where it still holds what Monet wrote last time
(`~/.config/monet/look-written`), so a font, pointer, sound or screen edge
someone picked since stays theirs; the global theme's pointer is kept around
its re-apply too. An account from before that record gets Monet's values once
more, as every update did before.

**Built in** (`image/Containerfile`): the everyday apps are part of Monet,
not downloads: Photos, Documents, Video, Music, Calculator and Archives,
built against the Plasma already there (tens of megabytes, where Flathub
would bring KDE's gigabyte runtime), in Monet's glass app style, and there at
the first sign-in. With them come previews of PDFs and videos in Files. Each
kind of file opens in its app from the start (`/etc/xdg/mimeapps.list`,
written by install.sh): pictures in Photos, PDFs and e-books in Documents,
films in Video, songs in Music, archives in Archives, text in the Text
Editor, rather than in whichever app claims it first. Zen and the big apps
come from Flathub (`monet-apps`), which skips anything built in. Carlito and
Caladea, as wide as Calibri and Cambria, keep Word and PowerPoint files' lines
and pages in the office apps (the base has Liberation for Arial, Times New
Roman and Courier New).

Files lists only what people open under Devices: USB sticks, other disks and
Windows' drive. Monet's own disk (Setup's `monet`, btrfs or its encrypted
container) and its start-up files (`boot`) are left out by
`90-monet-system.rules`, and the read-only system root, which Files showed as
a nameless drive with a full red bar, by a hidden place (`monet-quick
files-place` at sign-in, as Files' own Hide does it).

Apps go by what they are, not their project names: Files, Terminal, Text
Editor, Photos, Documents, Screenshot, Store. KDE's and Bazzite's own tools
(Info Center, Welcome Center, Bazzite's portal, links and updater, the
input-method and app-style tools) stay out of the menu, and nothing greets you from Bazzite or KDE. The Store is
Monet's own (below).

When an app closes unexpectedly, a short note says so, with its name and
picture and **Open it again** (`monet-crash@.service`, which install.sh
links in beside each crash `systemd-coredump@` catches, hands it to
`monet-quick crashed` in that person's session). It says nothing while the
app is still open (only a tab, or a game under Steam, stopped), or for what
isn't in the menu. KDE's crash reporter isn't there: Bazzite leaves it out.

## Motion

| Name | Duration | Curve | Used for |
|---|---|---|---|
| Rise | 380 ms | `cubic-bezier(.2, .9, .25, 1.08)` | popovers, sheets, toasts |
| Glide | 320 ms | `cubic-bezier(.2, .9, .25, 1.08)` | a pebble moving to what you chose: Settings' pages, Quick Settings' light |
| Settle | 200 ms | `cubic-bezier(.4, 0, 1, 1)` | closing: leaving is quicker than arriving |
| Press | 160 ms | `cubic-bezier(.2, .9, .25, 1.25)` | buttons, tiles, the islands |
| Sunset | 900 ms | `cubic-bezier(.4, 0, .2, 1)` | the screen fades to night before Windows, a restart or shutting down |

Desktop animation speed 0.8x. Windows scale gently in and out. With
animations turned off in More settings, Monet's widgets fade or cut.

## Windows, snapped as in Windows

Monet Snap (a KWin script, `share/kwin/scripts/monet-snap`) does what Windows 11
does with a window you drag, in Monet's glass. Settings → Light & Wallpaper →
**Snap layouts** turns it off (`monet-quick pref snap`). Off, the script's
snapping stops (kwinrc `[Script-monet-snap] Snapping`), KWin's own edges and
top take a window again (half the screen, all of it), and Windows+Z leaves the
shortcut list. The script itself stays loaded, since it also keeps the bar's
islands on one row while widgets are edited. An update keeps the choice
(`monet-look`'s record), and Put back does too.

- **Snap layouts.** While a window is dragged, a sliver of glass waits at the top
  of its screen (rise). Bring the window up to it and it opens into five layouts
  (halves; two thirds and a third; thirds; a half and two quarters; quarters).
  The part under the pointer lights in lily and a pane of lily-tinted glass shows
  where the window goes (glide between parts); let go and it's there.
- **Edges and corners.** The left and right edges take halves, the corners
  quarters, the top the whole screen, with the same preview. KWin's own edge
  tiling and top-edge maximizing are off (`monet-look`), as they'd answer the
  same drags with KDE's outline.
- **Snap Assist.** After a snap, from a drag, Windows+Left/Right or Windows+Z,
  the rest of the layout offers the other windows as pictures on a pane of glass,
  one part at a time; a picked window takes its part and comes to the front; a
  click anywhere else, the pane's empty glass too, and it's gone. The arrows
  and Tab walk the pictures (a lily ring), Enter or Space picks, Esc closes it.
- **Windows+Z** shows the layouts for the window you're in, to click, or to
  walk with the keys: left and right go part by part through all the layouts,
  up and down from layout to layout, Enter or Space chooses, Esc puts them away.
  Or Windows' numbers: each layout has its number under it, and once one is
  picked (its number turns lily), its parts show theirs, and a part's number
  puts the window there. Monet Snap borrows 1 to 9 too while it's up.
- **Notifications inside the screen.** Plasma places a notification by its
  content's width, which Monet's glass frame is wider than, so Monet Snap moves
  one that reaches past its screen's edge back inside (`keepInside`, on every
  change of its geometry). It then ends where the islands do.
- **Its own size back.** A window Monet Snap put somewhere goes back to its own
  size when it's dragged away, held where it was held.
- **Edges shared.** Snapped windows share their edges, as in Windows: one made
  bigger or smaller by an edge moves the edge
  of each snapped window beside it, so neither goes over the other (Settings,
  made wider, went under the store beside it). Dragged away, a window leaves
  the group.
- **Full height.** A window stretched by its top or bottom edge to the screen's
  takes the whole height.
- **Edge to edge.** Snapped windows meet each other and the screen's edges, with
  no gap: each frame fills its part exactly, including apps that draw their own
  title bar. Resizing a shared edge uses those same frame rectangles.
- **Easy to take hold of.** KWin draws Monet's frames with no borders of its own
  (`BorderSize=None`, `monet-look`), so it gives every window room to resize
  outside it, all along the sides and bottom. The theme's padding matches the
  shadow's actual size (`make-decoration.py`). Adding four pixels to it painted
  a pale outline outside Settings and required compensating gaps when snapping;
  that extra rim is gone. Apps using system decorations retain that frame.
- **A continuous frame for Monet's apps.** Settings, Store and Games use the shared
  `monet/games/MonetWindow.qml`: one glass surface behind their title and sidebar,
  following the user's Clear, Frosted, Matte or Solid choice. Its outer corners and
  KWin blur region use the same 14-pixel radius; maximized windows have square corners.
  The title moves the window and double-clicking it maximizes/restores. Eight grips
  cover every edge and corner, including the top, and hand resizing to KWin so snap
  layouts keep working. Minimize, maximize/restore and close have keyboard focus,
  accessible names and tooltips. These apps draw their own frame instead of adding
  an Aurorae title strip with a different opacity.

Monet Motion (a KWin effect, `share/kwin/effects/monet-motion`, in place of
KWin's Stretch) makes windows glide where they're put: maximized and restored,
snapped (just let go of, or moved and resized at once by KWin or a script),
stretched to full height. The old picture grows into the new place and fades
into the new one (300 ms, out cubic). Never a window held by hand, nor one an
app resizes in place: on Wayland an app can resize its window but not move it.

KWin never gives a script's own windows the keyboard (`InternalWindow`
doesn't take focus), so while Snap Assist or Windows+Z is up, Monet Snap makes
KWin shortcuts for the arrows, Tab, Enter, Space and Esc, and removes them
200 ms after both are gone. Gone, KDE switches them off and the keys reach apps
again. The pause is for the layouts handing over to Snap Assist: removing the
old shortcuts while making the new ones switched the new ones off. KDE's
shortcut list (More settings) shows them as "While Snap Assist or the snap
layouts are open". (A full-screen QML effect could have taken the keyboard, but
it replaces the whole picture of the desktop.)

## Sound

- **Felt and glass** (`monet`, `tools/make-sounds.py`): one soft instrument,
  felt mallets on warm bars and a little struck glass, in a small room. Quiet,
  and every sound fades out without a click. All in F major, so two sounds at
  once never clash. Notes go up for what arrives (signing in, a message, a
  drive or the charger plugged in) and down for what leaves or goes wrong
  (signing out, unplugging, warnings, errors, a low battery). The few names
  Monet has no sound for play KDE's Ocean.

## Signature moments

- **Start:** the dawn painting comes out of the dark, the sun rises from its
  reflection, the reflection ripples.
- **Play on Windows:** a sheet rises with the game's cover. On Restart & Play
  the sun sets: the screen fades to night and the sun sinks into the water.
- **Lock screen and sign-in:** the same painting, in the same light.
- **Restart and shut down:** the desktop softens behind one question, and
  going ahead, the screen fades to night before the PC goes.

## The installer

**Monet Setup** (below) is Monet's installer; the stick gets it whenever the
release has it, which is only once it has installed Monet in a test PC (CI's
`setup-vm`). Make-USB-Stick.exe asks the release for `Monet-<v>-Setup.iso`
first and falls back to the other one. Until then, Fedora's installer
(Anaconda), dressed as Monet, since its screens and wording are fixed:

- **Start menu** (GRUB theme, `image/installer/grub`): the dawn painting,
  Monet's mark and name in Fraunces, the choices on smoked glass and the
  chosen one on paper. Made by `tools/make-boot-menu.py`; loaded by
  `tools/patch-grub.py`, and skipped (plain menu) if anything is missing,
  and with Secure Boot on, where GRUB refuses fonts from the stick. GRUB
  draws the highlight's border outside its line, so lines are spaced by at
  least twice its corner.
- **Installer pages** (`monet.css`, loaded from Anaconda's `conf.d`): the
  painting down the side with the mark, paper pages, Fraunces page titles,
  lily choices, the sun for Begin Installation and Continue, ink for Done,
  and the harbor rising along the foot of the welcome and progress pages.
  Colors and shapes only: Anaconda's screens are laid out for Cantarell at
  its own sizes, and changing either spills labels and buttons out of their
  boxes. `tests/test_installer.py` parses it with GTK 3, because Anaconda
  drops the whole stylesheet on any error.
- **The download** (`/usr/libexec/monet-download`, from the kickstart's
  `%pre-install`): a Monet page over the installer while Monet's 5.7 GB come
  down, with how much and how long; a download that stops moving for four
  minutes starts again, keeping what it has.

## Monet Setup

Monet's own installer (`setup/`), replacing Fedora's: a small live Fedora
(`image/setup`) that starts straight into it, with no menu and Fedora's signed
shim, GRUB and kernel, so it starts with Secure Boot on.

- **The look** is the design board's: the dawn harbor filling the screen, the
  steps on a sheet of frosted glass (the painting blurred in advance by
  `tools/make-setup-art.py` and drawn once with a Canvas, so it needs no
  graphics card: Qt Quick runs in software, in cage), Fraunces titles, Inter
  for reading, ink for Continue and the sun for Erase & Install. Laid out on
  a 1440 x 900 grid and scaled to the screen.
- **The steps:** Hello (language, keyboard and time zone: a region, then a
  city, as Fedora's installer asks; the language's guess, then where the PC
  is from Fedora's location service once it's online, unless chosen; with
  the time there now), Wi-Fi (skipped with a cable), who's using this PC (the password
  twice; any password, or none: then a warning says Monet signs them in by
  itself and anyone at the PC can open the account, and the install deletes
  the password, writes `plasmalogin.conf.d/50-monet-no-password.conf` and
  turns the screen lock off, until `monet-ready boot` sees the account has a
  password), Your apps (Photos, Documents, Video, Music and
  Calculator shown as built in, Zen Browser ticked; Office, Mail, Discord,
  Spotify, Heroic, Prism Launcher, OBS Studio and Krita to tick, in tiles that
  turn lily), Ready (Monet and
  Windows, or next to my Windows, and the disk), installing, All set. Anything that can't go ahead says why on
  the page, in a sentence.
- **Next to Windows, without a full reset** (`monet_setup/disks.py`): with
  too little free space Monet makes room by shrinking Windows' drive with
  `ntfsresize` (the file system first, then the partition with `sfdisk`,
  keeping its start, type and ID). Windows keeps what it uses and half its
  free space, at least 30 GiB. A Windows left asleep (Fast Startup), a drive
  that needs a check, or BitLocker each say what to do instead. **Bring my
  files** copies the account used last's Desktop, Documents, Pictures, Music,
  Videos and Downloads (OneDrive's too) from the drive, read-only, into the
  new account; at the first sign-in `monet-quick bring-files` moves them into
  its folders, named in its language by then, and says so.
- **Installing** (`monet_setup/install.py`, its own process reporting JSON
  lines): partitions (EFI, boot, Monet's btrfs with `root` and `download`
  subvolumes, Windows' share left free), downloads Monet with skopeo into
  `download` (kept across tries; restarted when it stalls), installs it
  with `bootc install to-filesystem`, sets up the person, language, keyboard,
  time zone (the one chosen), Wi-Fi, Windows' waiting state and the apps picked
  (`/var/lib/monet/apps`, which `monet-apps.timer` installs from Flathub
  once Monet is online, until all are in; a PC that never chose gets the
  everyday ones), imports Universal Blue's
  driver key (and leaves a copy at `EFI/Monet/monet-key.der`), and names the
  firmware entry "Monet". All set shows the blue screen at the first start in
  pictures beside the sheet (drawn as shim's MokManager draws it, in its own
  English words), to take a photo of. It opens on Continue boot, which skips
  the key and leaves Monet unable to start ("bad shim signature"). Then GRUB
  falls back (`set fallback=monet-trust` in `/boot/grub2/custom.cfg`, which
  bootupd's grub.cfg reads) to a small start Setup put on the boot partition:
  the stick's own kernel (Fedora's, signed, so Secure Boot takes it) with
  `image/setup/monet-trust` as its only program (`rdinit=`; bash, mount and
  mokutil, packed by `build.sh`) and the key in a second cpio. It asks the
  firmware again with the same password, says so, and restarts: the blue
  screen is back. CI's VM test chooses Continue boot on purpose first. And
  started again, the stick finds the key's copy, sees with `mokutil
  --test-key` that it isn't trusted while Secure Boot is on, and Hello
  offers to ask again (`mokutil --import`, the blue screen waiting) and
  restart.
- **Tested in CI** (`tools/vm-test.py`): QEMU with Secure Boot on installs
  Monet on a blank disk through the real screens and starts it, then looks
  around it: signs in, and shows the desktop, the app menu, Files and
  Settings, then locks the screen and unlocks it with the password (the run's
  summary says whether it did). So every build shows Monet as it really
  looks, KWin's blur and all. The screenshots are kept in the registry:
  `python3 tools/ci-screens.py pull ghcr.io/happyhamster135/monet:ci-screens screens/`
  (or the run's `setup-screens` artifact). It runs with every release and by
  hand from the Actions tab (Monet OS → Run workflow).

## Backups

**Earlier versions.** Every hour `monet-keep` (root, `monet-keep.timer`)
takes a read-only btrfs snapshot of the homes into
`/var/lib/monet/snapshots/"2026-10-23 14.00"`: all from the last day, then the
newest of each day for two weeks and of each week for two months, and the
oldest go first when the disk is over 90% full. Each person reaches only their
own home in them. The homes become a subvolume of their own once, before the
sign-in screen (`monet-keep-prepare.service`: a reflinked copy, then a swap).
Settings → Backups opens your files as they were an hour, a day or a week
ago, and Files' **Earlier versions** lists one file's versions there, each to
show or put back beside it.

**A copy on a drive.** Pick a USB drive once; whenever it's plugged in (looked
for every quarter of an hour), at most once a day, rsync copies the home to
`Monet Backup/<person>` on it, leaving out caches, the Trash and games. What a
copy replaces or deletes is kept beside it by date for three months. A week
without a copy says so once.

## A guest

Settings → Accounts → **Guest** (after an administrator's password: `monet-guest`
isn't on Monet's polkit list) adds a `guest` account with no password, called
Guest in the language Settings speaks ("Gast", "Invité"), a face
from Monet's avatars (through AccountsService) and no screen lock. Its home is a
btrfs subvolume of its own, so the hourly earlier versions of everyone's files
never hold one guest's things for the next (and the guest's Backups page has
none). When the guest signs out, a drop-in on its `user@UID.service`
(`ExecStopPost=+…monet-guest wipe`, as root) ends what they left running,
deletes the subvolume and makes a new one from `/etc/skel`, labelled for
SELinux as useradd would; `monet-guest-wipe.service` does the same before every
sign-in screen, after a crash say, and never while they're signed in. Monet's
own no-password helpers don't apply to a guest (the polkit rule leaves the
`guest` user out): Play on Windows and the rest ask for an administrator.
Settings → Accounts' other people leave the guest out; turning Guest off removes
the account and all it holds. `/var/lib/monet/guest` keeps the uid monet-guest
gave it, and only that account is ever wiped or removed: someone's own account
that happens to be called `guest` is left alone (Guest then doesn't turn on).
A guest can't keep things running after signing out: logind ends what they
left running (`KillUserProcesses` for `guest` only, in `logind.conf.d`), the
polkit rule refuses them lingering, and a wipe ends whatever's left. `su`
never becomes the guest (`pam_succeed_if` in `/etc/pam.d/su`: their empty
password is for the sign-in screen, not for another account here). A wipe
first moves the last guest's home aside, root's only (`/var/home/.guest-…`),
puts a new one in its place, built root's only under another name and given to
the guest when it's ready, and only then removes the old one, subvolumes or
snapshots they made inside it first, deepest first; one that won't all go stays
root's only until the next wipe. What a guest left in `/tmp`, `/var/tmp` and
`/dev/shm`, their mail and their timed jobs go too. Turning Guest off ends the
guest's sessions, waits until nothing of theirs runs, and only forgets the
account when `userdel` has removed it. Windows' Games folder is never the
guest's, and a guest sees nothing of Windows: no games from it in Games or the
menu, no notes about it.

## Safety and recovery

**A new Monet that doesn't start goes back by itself** (`monet-boot`). At
shutdown, a staged update goes on trial (`monet-boot-arm.service`'s
ExecStop, before ostree finalizes it): `/var/lib/monet/trial.json`, and
where GRUB counts tries (Fedora's fallback counting in `grub.cfg`),
`boot_counter=3` in its environment. At its first start
(`monet-boot-check.service`) it has five minutes to bring up the sign-in
screen, which then has to stay up for a minute: the display manager active
and not restarting, and a greeter's or a person's session that stays the
same one (a sign-in screen that keeps crashing comes back as new sessions).
If it doesn't, `bootc rollback` and a restart. A start that hangs before
then is GRUB's: after three it starts the one before (`boot_counter=-1`),
which `bootc rollback` then keeps. Either way `/var/lib/monet/went-back.json`
notes the update; Settings → Updates and the next sign-in say so, and
`monet-update.service`'s ExecCondition skips that image (by digest) until a
newer one is offered. A Monet that starts clears the note.

**Reset this PC** (`monet-reset`, Settings → Updates, after an
administrator's password: it isn't in the polkit rule's list). The reset
happens at the next start, before the sign-in screen
(`monet-reset.service`): a snapshot of the homes first (Earlier versions),
then each path `ostree admin config-diff` shows changed in /etc goes back to
the image's `/usr/etc` (Monet's copy goes in beside it first; what was there
moves to `/var/lib/monet/before-reset/<date>/etc`), except what makes the PC
this one: accounts and passwords, its name and identity, disks and
encryption, language, keyboard and time zone, Wi-Fi, printers and keys.
Monet's own (Earlier versions, battery care, Ready when you come back,
automatic updates) go back to how they come. Each account's desktop settings
(KDE's `k*rc` and `plasma*`, GTK, Kvantum, autostart, Monet's own, its
default apps) move to `~/.local/share/monet/before-reset/<date>` and its
cache is emptied, as that account (a home is its owner's to arrange, so root
never moves things in it). Files, games, apps and their data stay.

**An encrypted disk that unlocks by itself.** On a PC with a TPM 2.0,
Monet Setup's **Encrypt this PC** is ticked: Monet's btrfs goes inside
LUKS2. The TPM can't learn the PC under Setup (Monet's kernel is signed with
Universal Blue's key, so Secure Boot's measurement differs from the stick's),
so the disk's key waits on the boot partition (`rd.luks.key`) for Monet's
first start, when `monet-seal` enrolls the TPM (`systemd-cryptenroll`, PCR 7:
Secure Boot's state, steady through kernel updates and trips to Windows),
wipes the key's slot and the file, and takes `rd.luks.key` off the command
line (`rpm-ostree kargs`). The recovery key (64 letters that type the same
on every keyboard layout) is shown once on Setup's last page and kept
nowhere. A start the TPM can't vouch for asks for it; that start
`monet-seal relearn` reads the key typed from root's kernel keyring
(`KeyringMode=shared`) and enrolls the TPM again, so the next start doesn't
ask. The image's initramfs carries the TPM's libraries (`--add tpm2-tss`).
Fedora's installer doesn't encrypt.

## Security at a glance

Settings → Security shows what keeps the PC safe, one row each, with a lily
tick when it's as it should be, an amber "!" when it wants a look, and what
would fix it; the title says "Your PC is protected" or how many things want a
look. `monet-quick security` only looks, here and now: Secure Boot from the
firmware's `SecureBoot` variable (none at all: not started in UEFI mode),
whether the firmware trusts Monet's key (`mokutil --test-key`), encryption
(the disk Monet runs from inside a `crypt` device, `lsblk -s`), the firewall
(`firewall-cmd --state`), automatic updates and a staged update, and earlier
versions of files (`monet-keep`) with the drive copies go to. Firmware updates
are the Updates page's own question (`firmware-check`), asked as the page
opens.

The fixes: Secure Boot off and Monet's key not trusted yet → **Trust Monet…**
(`monet-secure trust-key`: the import with the blue screen's `monetsetup`,
waiting for an answer), then the blue screen at the next restart; trusted →
**Firmware settings…**, which says what to do there and restarts into them
(logind's `SetRebootToFirmwareSetup`, then KDE's restart question). Secure
Boot is never sent on before Monet's key is trusted, or Monet wouldn't start.
Firewall off → **Turn on** (`monet-secure firewall-on`). Updates only when
asked → **Turn on**; an update waiting → **Restart**. Firmware → **Install**
(fwupd asks for the password itself). Earlier versions off → **Turn on**; no
drive → **Add a drive…** (Backups). Encryption has no fix: only Monet Setup
encrypts, as it installs.

The firewall's default zone is Monet's own (`linux/firewalld/monet.xml`,
`target="default"`): from the network only what Monet uses comes in, as ports
rather than firewalld's service names (a missing service would stop the zone):
DHCPv6 (UDP 546), finding printers and devices (mDNS, UDP 5353), the phone
(KDE Connect, TCP and UDP 1714-1764), and Steam on this network as Steam's help
lists it: finding other PCs and Remote Play (UDP 27031-27036, TCP 27036-27037)
and Local Network Game Transfers (TCP 27040). What the PC asks for itself gets
its answers as always. The image installs it in `/usr/lib/firewalld/zones`,
remembers Bazzite's default (`/usr/share/monet/firewall-zone-before`) and sets
Monet's (`firewall-offline-cmd`, only warning if it can't); an existing system
gets the zone in `/etc/firewalld/zones` and nothing changes. Settings →
Security's switch, "Only what Monet uses comes in", sets it or goes back
(`monet-secure firewall-strict on|off`, remembering the zone it leaves in
`/var/lib/monet/firewall-zone-before`). Under it, while Monet's zone is on,
**Apps that can accept connections** lets in one at a time: games you host
(Minecraft, Terraria, Valheim, Factorio, Stardew Valley), LocalSend, Syncthing,
streaming this PC with Sunshine, and Deskflow. Each is a fixed set of ports in
`monet-secure` (`firewall-allow NAME on|off`: names only, never typed ports),
written as a firewalld policy of its own (`/etc/firewalld/policies/monet-allowed.xml`,
ANY → HOST, CONTINUE, priority -10, the shape of firewalld's own allow-host-ipv6),
so Monet's zone stays as the image has it and an update can still change it. The
names chosen are in `/var/lib/monet/firewall-allowed.json` for Settings to read.

**Windows' question** comes from `monet-listening.service`, a user unit running
`monet-quick listening`.
- **What it watches:** every 5 seconds it reads `ss -Hltnp`. That lists TCP ports
  waiting for others; for anyone but root, only the person's own processes have
  names. It ignores this PC's own addresses, ports below 1024, and ports the
  network reaches already (Monet's zone, the apps above, ports allowed before).
- **When:** only while Monet's zone is the default, checked each minute.
- **What it asks:** once per program and port, it posts a critical notification,
  so it stays until answered: "%1 wants to accept connections", with Allow and
  Keep blocked. The program is named by its app menu entry (from its systemd
  unit, Flatpaks too), otherwise by its process.
- **Allow:** runs `monet-secure firewall-allow-port NAME tcp/PORT on`, which asks
  for an administrator as Windows' shield does. It checks the name and the port
  (TCP, 1024 and up). The port joins the same policy, and the list in
  `/var/lib/monet/firewall-allowed-ports.json`.
- **Afterwards:** the answer, either one, is kept in
  `~/.config/monet/listening.json`. Security lists each program asked about,
  with a switch to let it in or out again.

UDP isn't watched: a UDP socket doesn't say whether it waits for others.
Uninstalling goes back to that zone before removing Monet's. `monet-secure` runs through pkexec and always asks
for an administrator's password: it's not on the list Monet's polkit rule
lets through.

## Bluetooth in both

A Bluetooth device keeps one pairing key for the PC, and Monet and Windows
share its radio, so pairing in one used to make the device forget the other.
At every start `monet-pairings.service` (after `bluetooth.service`) reads
Windows' SYSTEM registry file straight off its drive with `ntfscat` (never
mounted or written; an encrypted Windows is skipped), parses it read-only
(`Hive` in `monet-pairings`), and for each device both have paired takes
Windows' key into BlueZ's `info` when Windows paired it again since Monet last
looked (`/var/lib/monet/pairings.json`; the first time, when Windows' key is
newer than Monet's file). Classic devices take the link key; Low Energy ones
the long-term key as it is, EDIV and ERand as numbers, the identity key
reversed (packet captures showed it; other tools disagree), `Authenticated=2`
for Secure Connections (no EDIV or Rand, so it works in either role), and the
device's `Address` value as its name when Windows filed it under a passing
one. bluetoothd is stopped while files change and started again, only when
something changed (it hands keys to the kernel as it starts). Windows may
keep a fresh pairing in its registry's logs for a while; then it comes over
at a later start. So: pair in Monet, then once in
Windows, and the device works in both. Monet doesn't write Windows' registry:
Windows only learns a device by pairing it itself.

Wi-Fi works in both the same way. Whenever Windows' drive is open
(`monet-windows-drive`, at start), the networks Monet knows that Windows
wasn't given yet, or whose password changed (a hash of each profile in
`/var/lib/monet/wifi-given.json`), go to `C:\ProgramData\Monet\wifi` as
WLAN profiles, made as Monet Setup makes them for a Windows it installs
(`monet-prepare-windows`' `wifi_profiles`); Monet Bridge adds them for
everyone at its next start (`netsh wlan add profile … user=all`) and removes
the files, which hold the passwords. Bridge makes that folder for
administrators only, and Monet writes there only when it's there: Linux's
NTFS drivers give a file they make its folder's permissions (ntfs3 does), so
one Monet made itself would let every Windows account read them. The other way, Bridge exports Windows'
networks on the way back (`netsh wlan export profile key=clear`) into
`wifi-out`, a folder only administrators can read, and at Monet's next start
each one NetworkManager doesn't know (by name) becomes a profile for
everyone (`system-connections`, 0600: WPA, WPA3 or open; work and school
ones need more than a password and stay in Windows); the exported files go.

The PC's clock keeps UTC for both: Monet Bridge's installer sets Windows'
`RealTimeIsUniversal`, so Windows' clock isn't off by the time zone after a
switch. And each trip's request carries Monet's time zone as Windows names it
(`tz`, from `monet-prepare-windows --windows-zone`'s list, checked to be a
name Windows could have; a Bridge from before it ignores it), and Bridge sets
it with `tzutil` when Windows' differs, so after a journey both show the
same time.

A Windows that Monet installed wears The Hours (`wallpaper.jpg` in the
Windows package, set by `Install-Monet.ps1 -FromMonet`); a Windows kept from
before keeps its own, as its setup (`windows_setup.rs`' payload) carries no
painting.

Monet Bridge keeps itself up to date on the way out. `go_back` sets BootNext,
leaves `update-then-restart` in `C:\ProgramData\Monet` and starts the
`\Monet\Update` task (`Update-Monet.ps1`), which renames it `update-claimed`
as it starts; if that hasn't happened within 30 seconds, Bridge restarts by
itself. The task asks GitHub for Monet's releases at most once a day (every
Monet is a pre-release while it's a preview, so not `releases/latest`), and
when the newest is newer than Bridge it downloads `Monet-X-Windows.zip`,
checks it against the release's `SHA256SUMS.txt` and runs its
`Install-Monet.ps1 -Quiet`, which leaves the running Update task alone and
swaps Bridge's program in one step (a copy cut short never leaves half of
it). An update that isn't downloaded within 75 seconds of taking over waits
for the next trip, and a task that starts after Bridge has given up on it
does nothing, as Windows is already going down. Its
`finally` restarts the PC whatever happened, so an update never keeps
anyone in Windows, and a game is never interrupted: it runs only after
you've chosen to go back.

## A trip to Windows

**The cover.** On a trip Monet Bridge puts Monet's painting over Windows
(`cover.rs`): a full-screen window that never takes the focus and stays off
the taskbar, so a launcher (asking to sign in, say) and the game open over it,
and when the game closes it's what's there, never Windows' desktop. It's the
day painting (`cover.jpg`), dusk drawn up from a little above the words, the
mark and "Monet" top right as in Setup, and the words bottom left (bottom
right in Arabic and Hebrew): a small caption, a title in Fraunces (Windows'
own font for a title in another script), a sentence, and buttons. Painted
off-screen with GDI+ (painting, mark, rounded shapes) and GDI (words, which
GDI finds a font for in every script, laid out right to left where it should
be), at the screen's own pixels. Its scenes: **Starting** (the game's name,
Back to Monet now), **Back** (the 15-second countdown that used to be a
message box: Go now, or Stay in Windows; it comes to the front and takes
Enter and Esc), **Launchers** and **Updating**. Its words come from `po/`
through `crates/monet-bridge/src/words_table.rs`, in Windows' language (Make
USB Stick's lookup, `words.rs`, shared). `monet-bridge cover-preview SCENE
OUT.png` paints a scene into a PNG (`MONET_LANGID=0x407` for German). A
Windows that Monet installed also hides its taskbar until it's pointed at.

**Signing in once** (Settings → Play on Windows → Game launchers, `monet
windows --launchers`): the request carries `"task": "launchers"`, and the
cover lists the launchers Windows has (`launchers.rs`: Steam, Epic Games,
Riot Client, Battle.net, EA app, Ubisoft Connect, GOG Galaxy), each with Sign
in, opened as the person through the `\Monet\Launch` task (never as
administrator). Where a launcher's own files say it keeps you signed in, the
card says so instead (Steam's `AutoLoginUser`, Epic's `[RememberMe]`, the
Riot Client's saved `ssid`), looked at again every five seconds. Back to
Monet ends it.

**Updating, then off** (Settings → Update Windows games, `monet windows
--update`, `"task": "update"`): Windows Update (`Update-Windows.ps1`: Windows'
own updates, not drivers, none that would ask something; its progress in
`windows-update.json`) and every launcher, opened quietly as the person (Steam
and Epic with `-silent`), until it's all quiet (`parse::updates_settled`):
Windows Update finished, no Steam game mid-update (StateFlags 256 or 1024),
the network cards' downloads under 250 kB/s for five minutes, after at least
ten; at most an hour and a half. If Windows wants a restart to finish and
signs in by itself, Bridge sets BootNext to Windows, restarts, and the agent
picks the trip up again (`update-trip.json`) before switching off. When it's
done, `games-updated` goes into the games list (`games_updated`) and Settings
says when it was last done. Switch off now stops it there. A Monet Bridge
from before tasks reads either request as opening Windows.

**Your apps again.** A trip restarts the PC, so open apps close. Just before
it, `monet` (the person's side, before it asks the helper to switch) runs
`monet-quick remember-apps`: the apps running now, from the systemd units
Plasma starts each app in (`app-[LAUNCHER-]ID@RANDOM.service` or
`app-[LAUNCHER-]ID-RANDOM.scope`, the menu entry's name with its dashes
escaped), without Steam, Monet's own, the hidden ones and those that start at
every sign-in anyway, at most twelve, into `~/.local/state/monet/trip-apps.json`.
At the next sign-in within twelve hours `monet-session` starts them again,
once, those not running yet. Browsers and the like reopen their own windows
and tabs. Settings → Play on Windows → **Open your apps again** turns it off
(`~/.config/monet/trip-apps-off`).

## The last 30 seconds

Games & Controllers turns on `monet-replay.service` (per person): GPU Screen
Recorder from Flathub (installed the first time) keeps the last 30 seconds
of the screen and its sound in memory, through KDE's screen-sharing question
asked once and then kept. Windows+Alt+G, as Xbox Game Bar has it
(`monet-replay.desktop`'s shortcut, set once by `monet-look`), sends the
recorder SIGUSR1 (it alone: its flatpak and sandbox would stop on it) and it
saves an MP4 in Videos.

## Which games need Windows

`monet-quick game-marks` reads AreWeAntiCheatYet's list (MIT, fetched at most
every three days, kept as Steam ids and a word): Supported and Running play in
Monet, Broken, Denied and Planned need Windows; games it doesn't list mostly
have no anti-cheat and get no mark. Epic's games are marked by their
namespace, which Heroic's library knows too. Play on Windows' covers mark
those that play here too, and Games & Controllers lists the games installed
here that need Windows, with Play on Windows when they're there too.

Players' reports count too, from ProtonDB: a Steam game installed here that
ProtonDB rates borked, overall and by its recent reports, plays on Windows as
an anti-cheat one does (AreWeAntiCheatYet's word wins where it has one), and
its sheet says players report it doesn't run in Monet. Only the Steam games
installed here are asked about (its summaries, one per game), each at most once
a week, by `monet-quick protondb-refresh` in the background after the gallery
opens, at most every ten minutes when it couldn't get through; nothing waits on
it. Reports can be out of date, so the game's menu has Play in Monet. They
speak for Proton only, so they count only for a game whose Windows build Steam
installed here (a program for Windows in its folder); one with a Linux build of
its own runs that.

## Windows' keys

Hands that learned Windows find its keys here: Ctrl+Shift+Esc shows what's
running (System Monitor), Windows+I opens Settings, Windows+A Quick Settings,
Windows+G Games (Windows' Game Bar), Windows+R runs or finds
something, Windows+E opens Files, Windows+Shift+S takes part of the screen, and
Windows+Up and Down maximize and minimize a window (KWin had them tile to the
top and bottom), Windows+Z shows the snap layouts, and Windows+Space switches to
the next keyboard layout (beside KDE's Meta+Alt+K; since 0.9.4, once for every
account, `keys-094`), and Windows+Tab shows all the windows, as Windows' Task View (it was a second Alt+Tab). Each adds to the keys a tool has: its own stay.
`monet-keys.service` sets them once per account before KWin reads its keys
(`monet-look --keys`, into `kglobalshortcutsrc`), so they work from the first
sign-in; Windows+A and Windows+G are the widgets' own keys, given once Plasma's
running (`monet-look --widget-keys`). A key someone changes afterwards stays
theirs. Settings → Mouse & Keyboard lists them to learn them by.

## Windows programs

A Windows program or installer opened in Files (an `.exe` or `.msi`; Monet's entry
is the default for them) brings up Monet's sheet, which Quick Settings shows as
it shows Settings (`monet-quick windows-program` rings the same doorbell): the
program's name and a choice. **Run in Monet** runs it through Proton, as Windows
games run here (`umu-run`, in the image, in a Windows of Monet's own for
programs, `~/.local/share/monet/windows-programs`, with Steam's Proton when
Steam has one and umu's own otherwise; the first time, a note says umu is
getting ready). It runs in a user unit of its own, and afterwards each program
an installer put in the Start menu becomes an entry in Monet's app menu (its
shortcut's target, read from the `.lnk`'s LinkInfo; uninstallers left out,
entries whose program is gone removed). **Open in Windows** copies it into the
folder for files on both sides (`C:\Shared with Monet` in Windows, where it
stays to open again; one saved there already isn't copied at all) and restarts
with `program:<its place there>`; Monet Bridge finds it there and starts it as you, never as administrator, and Windows stays, as when
it's opened from Monet. When Windows' drive isn't open this time, is someone
else's, or has no room, the sheet says so and Open in Windows waits. Files'
menu on a Windows program has Run in Monet and Open in Windows… too.

**Your Windows apps** (Word, Photoshop, iCloud's, G Hub) are in Monet's app menu
and its search, each saying "Opens in Windows". When Windows' drive opens,
`monet-windows-drive bring` reads the Start menu (the person's own Windows
account's, then everyone's). It reads each shortcut's target from its LinkInfo,
or from the path it keeps with environment variables. It leaves out:
- Windows' own tools, and its system folders in the menu.
- Games and their launchers: Games has them.
- Browsers, since Zen has their bookmarks, and OneDrive, since Files has it.
- Uninstallers and help, and shortcuts whose program is gone.

Each app's icon comes from its program's own resources (PE icon groups, a PNG or
a bitmap turned into one with Pillow). The icons go into the person's icon theme
(`hicolor/256x256/apps/monet-windows-app-*.png`), where Monet frames them as it
frames any app's. The list goes beside them (`~/.local/share/monet/windows-apps.json`).

At sign-in, `monet-quick windows-apps` turns the list into entries
(`monet-windows-app-*.desktop`), unless Monet has an app of that name itself
(Discord, Spotify). Choosing one rings the same doorbell as a program
(`windows-app`): the sheet shows the app with its icon and one bright Open in
Windows, and the restart carries `app:<slug of the shortcut's place under
Programs>`. Monet Bridge looks the id up as the person (`scan_apps`, so their own
Start menu counts) and opens the shortcut itself, so its arguments and folder are
Windows' own. Windows stays, as for programs. Without Quick Settings, `monet play
app:… --confirm` asks instead.

**Microsoft Store apps** (iCloud, WhatsApp, the new Teams) have no shortcut on
the drive, so Windows lists them itself.
- **Listing them:** at each sign-in, Monet Bridge's Agent (which runs as the
  person) asks `Get-StartApps` for the apps whose ids are a Store app's
  (`Family_PublisherId!App`). It keeps a checked list in the shared Games
  folder's `.monet/store-apps.json` (`parse::store_apps`).
- **Reading them here:** `monet-windows-drive` reads that list, leaving out
  Windows' own apps (Calculator, Photos, Settings), Xbox's and the like.
- **Logos:** each logo comes from the app's package on the drive (`Program
  Files/WindowsApps`, the newest version). That's its manifest's
  `Square44x44Logo`, the biggest file of it, unplated first.
- **Opening one:** Bridge opens it with `explorer.exe shell:AppsFolder\<id>`.

Advertised shortcuts (an older Office's), which lead to no program, aren't
listed. The app menu's search finds them, and so does the Store's.

## The Store

The Store is Monet's own window (`monet-store`, Qt for Python as Games and
Settings are), in place of Bazaar, which couldn't take results from outside and
didn't look like Monet. It's built from what's on the PC already:
- **The catalog** is Flathub's AppStream file, which Flatpak keeps up to date
  (`/var/lib/flatpak/appstream/flathub/x86_64/active`), read with ElementTree in
  under a second: names, summaries, descriptions, keywords and screenshot
  captions in the nearest language (each is given once per language), its
  cached icons, whether Flathub checked the developer, the licence and the last
  release. A new Monet without the file asks Flatpak for it first.
- **What's kept out:** Bazzite's blocklist (`/usr/share/ublue-os/bazaar/
  blocklist.yaml`, the blocks without conditions and the ones for KDE), runtimes,
  and anything without a proper app id.
- **Hung like a gallery**, so it isn't one more grid of cards:
  - **Today's pick** opens the front page: a screenshot hung in a paper mat on
    the painting of what the app is for, with a placard to install it from (one
    of Monet's picks, another each day).
  - **Rooms:** each row of Monet's picks (`store/content.yaml`) is a strip of
    The Hours with its placard pinned to the edge, the first apps framed (their
    screenshot in a mat, the app's picture pinned to it, the label under it),
    the rest as a wall of small tiles that say what they're for under the
    pointer.
  - **Most installed this month**, numbered in Fraunces, after the first room;
    **Fresh paint** (apps people use with a release in the last 30 days) on a
    band of brushstrokes after the third.
  - **Sections** each have their own painting, cut from all four series by
    daylight and by night (`make-store.py`), with the section's name on a
    placard. They sort by Popular (Flathub's monthly installs, kept a day in
    `~/.cache/monet/store/popular.json`), Recently updated or Name (kept for next
    time), narrow to a kind of app (`KINDS`: Strategy, Emulators, Making music,
    Code editors…, each with how many), and to the apps Flathub checked. In the
    Popular order the top three stand on a podium, framed and numbered.
  - **An app's page** is under its section's painting, fading into the paper,
    with its picture on a paper tile over the painting's edge; its screenshots
    as a gallery (one big in a mat, a caption in Fraunces, the rest to pick
    from), and More like this at the end (the most AppStream categories in
    common, a kind counting more than a section).
- **Scrolling** glides: Kirigami's WheelHandler on every page (a notch is 96
  pixels, as smooth scrolling is set in Plasma), and no sideways list on a page
  catches the wheel.
- **Search** wants every word somewhere (name first, then keywords, the id and
  the summary) and breaks ties by installs. It also looks through the apps in
  the person's Windows (`windows-apps.json`, opening there). An app only made
  for Windows (Photoshop, Office, Premiere) gets a note with what does the same
  here; when it's in their Windows, it's listed under it.
- **An app's page:** screenshots (Flathub's own copies, kept on disk), the
  description, what it can reach (its Flatpak metadata from `flatpak
  remote-info`, said plainly: programs outside, all files, the home folder,
  devices, the internet), download and disk sizes, version and website.
- **Install and remove** run `monet-store --do` in a process of its own, which
  uses libflatpak (PyGObject) and prints its progress as lines of JSON.
  Flatpak's polkit rule lets an administrator in without a password; anyone
  else is told only an administrator can.
- **Everywhere:** the bar's and the menu's Store, `appstream://` links
  (`mimeapps.list`), and a Bazaar or Discover pinned before: `monet-look` leaves
  each a hidden menu entry that opens the Store.

## One game library

Games is an app of its own (`monet-games`, Qt for Python as Monet Setup is, with
its window in `linux/share/monet/games`), opened by the Games button in the bar
(the sun as a play button, left island, now only a launcher), Windows+G, or the
menu; opening it again brings its window forward (one window, by a local
socket that also hands over the desktop's activation token). It's a library the
size of Settings, after Steam's but in Monet's look: down the glass side, the
name, search, the sections (All games, Favorites, Recently played, Plays on
Monet and Plays on Windows when there are both) and under Stores each store with
games, each with its count and a swatch or the launcher's picture; on the paper,
the section's covers, tall (Steam's 600×900 library art, from its cache or its
CDN; Lutris' cover art; Heroic's square art; otherwise a glaze from the
paintings with the game's banner hung on it and its name), sorted by Recent,
Name, Play time or Size (kept with the window's size, QtCore's Settings).
Above every game, Continue playing shows the four played last, wide. A cover
opens its game's page: its wide hero picture with the name, Play (Play on
Windows for one that needs it), where it plays, when it was last played, the
play time and the size on disk, the star and a menu, and a note about where it
plays (installed once for both, its anti-cheat, players' reports) or its
download. Hovering a cover shows the star (favorites keep it) and the sun,
which plays it without the page. Favorites are kept in
`~/.config/monet/favorite-games.json` (`monet-quick favorite GAME on|off`).
Play time comes from each launcher's own count (Steam's localconfig Playtime,
which covers every PC the account plays on; Heroic's timestamps; Lutris'
hours) and, for Windows, from Monet Bridge, which times each game a trip
started from when it appears until it closes (`playtime.json` in
ProgramData\Monet, `minutes` in the games list); a Steam game counts the larger
of the two, anything else both added. The size is Steam's SizeOnDisk or
Heroic's install size. The window uses nothing of Plasma's: Kirigami's colors
only, its own pills, menu and sheets, and Monet's words through KDE's i18n
calls answered from the same catalog (`Words`), so the translation tools find
them as they find the widgets'. Pictures from the web are kept in a disk cache.

The library (`monet-quick library`) has Steam's games installed here (its appmanifests),
Heroic's (Epic through legendary, GOG, Amazon through nile and games added by
hand: what each store's file says is installed, titles and covers from
Heroic's `store_cache`, in `~/.config/heroic` or the Flatpak's), Lutris'
(its `pga.db`, read-only, without the games it plays through Steam; its
banners as covers, started with `lutris:rungameid/…`), and the
games Play on Windows offers (Monet Bridge's list and the extras; an Epic or
GOG game only Windows has takes its cover from Heroic's library cache, which
lists every game you own). A game on
both sides is one: Steam's by its id, Epic's by its app name, the same in
Heroic and in Windows. Each says where it plays: **Plays on Monet** when it's
installed here and its anti-cheat doesn't want Windows, otherwise **Plays on
Windows**. Play starts a Monet game right away, the way Steam's Play or
Heroic's own shortcuts do (`steam://rungameid/…`, `heroic://launch?…`), and a
Windows game the way Play on Windows always has: asked once, the sun sets,
the PC restarts in Windows with it. A game installed here that needs Windows
but isn't there yet says so, and Restart opens Windows to install it. Only
ids of letters, digits, dots, dashes and underscores are listed, as they go
on a command line. Find a game, at the top of the side (or Ctrl+F), finds one
by name, accents and capitals aside, and Enter plays the only one it finds. A game that needs
Windows and is still in Monet's own Steam folder, while Steam here has Windows
games, asks to be moved there instead (Show in Steam opens its page:
Properties, Installed Files, Move install folder), so it plays in Windows with
nothing to download. A right-click (or the Menu key) on a game offers Play on
Windows for one that plays on both sides, and Show in Steam and Uninstall…
(Steam's own question, `steam://uninstall/…`) for Steam's. A game
Steam is downloading says how far it is, with a lily line along its cover,
looked at again every few seconds while Games is in front; with none yet,
Open Steam is there to get some. It works from the keys too: typing on the
covers finds a game; the arrows move a ring between games, Enter or Space opens
the page of the one it's on (where Enter plays), Esc goes back, the Menu key
opens its menu, and Up from the top row goes back to the search. A game that
plays on both sides says so on its cover (Monet · Windows), as Windows' do.
The list itself puts the games played in the last 30 days first, newest first,
then the rest by name (when each was played, as Recently played knows it).
AreWeAntiCheatYet's list is fetched again in the background when it's three
days old, so opening Games never waits on the internet but the first time.

Monet Bridge's list of Windows' games has Steam's, Epic's, Riot's, GOG's in the
shared folder, and, found as Playnite finds them: Ubisoft Connect's (its own
`Ubisoft\Launcher\Installs` key, started with `uplay://launch/ID`), Battle.net's
(Blizzard's uninstaller is given the game's uid, which names the code its client
starts it by: `Battle.net.exe --exec="launch AUKS"` for Call of Duty) and
Rockstar's (its uninstaller's `-uninstall=gta5`, started with the Rockstar Games
Launcher's `-launchTitleInFolder`) and EA's: every folder the EA app installs
a game in has `__Installer\installerdata.xml`, which names the game and the
offer ids the EA app starts it by (`origin2://game/launch?offerIds=…&autoDownload=1`,
as Lutris starts them), found where Windows' list of programs says EA's games
are, in `Program Files\EA Games` and in the shared Games folder. So those play
on Windows from Games with nothing added by hand.

A game a launcher starts seems to start from Monet. While the EA app (or
Battle.net, Ubisoft Connect, Epic's, Rockstar's or the Riot Client) opens and
starts the game, Monet's painting stays in front of it (the cover, held
topmost without taking the keyboard); as soon as the game's own program runs,
the painting goes to the back, under the game, and the launcher's windows are
minimized. If the game hasn't started within a minute the launcher must want
something (signing in the first time, an update), so the painting steps aside
and lets it be seen. When the game closes, the trip back to Monet restarts the
PC, which closes everything; if you stay in Windows instead, the launcher is
closed for you once the network has been quiet for a few seconds (its cloud
saves done), every program in its own folder but its Windows services and the
game's. Steam isn't closed: it's where friends and chat are. In Monet the same
idea goes as far as the launchers allow: Play starts Steam in its tray
(`-silent`) when it wasn't running, and Heroic without its window (`--no-gui`).

## Install a game once

**BitLocker.** Device encryption is on by default on many Windows 11 laptops.
Settings → Games & Controllers → Shared with Windows asks for the drive's
recovery key (48 digits) once, with where to find it (the Microsoft account,
aka.ms/myrecoverykey, or Windows' Manage BitLocker). How it travels and is used:
- **From Settings to root:** sealed with the helper's one-time pad, as a
  password is, then handed to root's `monet-windows-drive unlock` on its stdin
  (pkexec, no password, as Settings' other helpers), never on a command line.
- **Checking it:** the key is first tested against each BitLocker partition
  (`cryptsetup open --type bitlk --test-passphrase`). The one it fits opens as
  `/dev/mapper/monet-windows-…`, where everything else finds Windows as on a
  drive that isn't encrypted.
- **Keeping it:** sealed with `systemd-creds` (the PC's TPM where there is one,
  and the system's own key) in `/var/lib/monet/bitlocker/<uuid>.cred`, root's
  only. At every start it opens the drive before Windows' setup
  (`ExecStartPre` of `monet-windows-setup.service`, which can then put Monet
  Bridge in) and before the shared folders look for Windows.
- **No Bridge yet:** Settings says Bridge installs itself at Windows' next start.

**Windows hands its key over** when it gets encrypted after Monet put Monet
Bridge in. That happens when Windows 11 turns device encryption on as someone
signs in with a Microsoft account, or when BitLocker is turned on. Nobody types
48 digits then:
- **Monet's lock:** a 3072-bit RSA key pair, made the first time and sealed with
  `systemd-creds` as the typed keys are (`/var/lib/monet/bitlocker/handover.cred`).
  While Windows' drive is open, `monet-windows-drive` leaves the public half, as
  .NET's `RSAKeyValue` XML, in `ProgramData\Monet\from-monet`. Bridge makes that
  folder for administrators only, so no other Windows account can leave a lock of
  its own there.
- **In Windows:** at each sign-in, Bridge's Agent (the person, as administrator)
  asks BitLocker's own WMI class (`Win32_EncryptableVolume`) for the system
  drive's numerical-password protectors, once the drive is fully encrypted.
  Windows PowerShell's RSA locks each one (OAEP), and Bridge leaves them on the
  EFI partition (`EFI/Monet/bitlocker.json`), once for each protector (noted in
  the same folder). Only locked keys leave PowerShell.
- **At Monet's next start:** `unlock_saved` reads that file. The private half
  reaches openssl through a pipe, never a file or a command line. Each key is
  tried and kept sealed as a typed one, then the file is deleted from the EFI
  partition.
- **Settings:** once the lock has been left, the BitLocker card says to start
  Windows once, or type the key.
- **Not covered:** a Monet installed beside a Windows that was already
  encrypted. Bridge isn't in it yet, so the key is typed once; after that Bridge
  is put in and hands over later keys (a new one after Windows changes it).

cryptsetup can't open Vista's BitLocker or a partly decrypted drive, and it
never changes BitLocker's header. A Windows whose encryption is only waiting
for activation has no recovery key yet: that one stays closed.

Windows can't read Monet's drive, but Monet can write Windows' when Windows has
shut down fully, so a game lives on Windows' drive and both sides play it from
there. At every start `monet-windows-drive.service` (before the sign-in screen)
looks for a Windows with Monet Bridge (`ntfsls`, nothing mounted), opens one
encrypted with BitLocker whose recovery key was typed once (below), and asks
`ntfs-3g.probe --readwrite` whether its
drive is safe to write: not hibernated or asleep with Fast Startup (Bridge's
installer turns that off), no unfinished journal after a crash. Only then is it
mounted, with the kernel's ntfs3 (the newer ntfs, then ntfs-3g, if it can't),
finding names in any case as Windows does where the driver can (`nocase`), at
`/run/monet/windows-drive/c`, inside a folder only root can enter (the drive's
own top folder would let everyone in; not `windows_names`:
Steam may put Proton beside the first game that needs it, and Proton's own
files have names like `c:`). Only its `Games` folder (`C:\Games`) is shared,
bound at `/run/media/Windows games` and owned by the PC's first person, for
them alone (`umask=077`: no other account here reads Windows' files). A
`C:\Games` that leads somewhere else (a junction a Windows account made) is
neither followed nor shared, and Steam's library mark is made without
following links.
Shutting down unmounts it cleanly before any trip. Files doesn't list that
drive among its devices (a udev rule in `/run/udev/rules.d` sets
`UDISKS_IGNORE` for it): opening it there would ask for an administrator,
or, with Windows asleep, put its files at risk.

The folder is a Steam library: `libraryfolder.vdf` as Steam writes one, and
`steamapps/compatdata` and `shadercache` as links to Monet's own Steam, since
Proton's prefixes hold names and links NTFS can't (Valve's advice). Just before
Steam starts with the session (an `ExecStartPre` drop-in on its autostart unit,
`app-steam@autostart.service`), and at sign-in when it isn't running,
`monet-quick steam-share` adds it to Steam here
(`libraryfolders.vdf`, both copies) and gives every game in it Proton
Experimental unless one was chosen (`CompatToolMapping` in `config.vdf`), so
Steam here keeps Windows' build, the one Windows plays, and never swaps in a
Linux one (what breaks a library shared by hand). Steam's files are edited in
place (KeyValues blocks found by their keys, entries added as Steam writes
them), each kept once as `.before-monet`. Settings → Games & Controllers →
**Add to Steam** does it now, closing Steam for a moment. In Windows, Monet
Bridge adds `C:\Games` to Windows' Steam as the person, before Steam starts for
a trip (`share_with_steam`, asking a running Steam to quit first), and scans
it even before Steam lists it. Files Linux makes there let everyone write, so
Steam in Windows can update them. The Games widget marks such a game as on
both sides (`shared`): installed here, and Play on Windows starts it there
without a download. One that needs Windows and is still in Monet's own library
says how to move it (Steam's Move install folder).

Heroic's games can live there too. An Epic game Heroic (legendary) installed
in Windows games is made ready for Epic's own launcher the way legendary's EGL
sync does it: at sign-in `monet-quick epic-share` copies the install's
manifest into the game's `.egstore` with its `.mancpn`, and leaves a note in
`Games\.monet\epic\APP.json` (the catalog ids, version, program, a stable
installation GUID); notes for games no longer there go. At its start Monet
Bridge writes the launcher's `.item` for each note it hasn't got (legendary's
template, `bNeedsValidation` so the launcher checks the files once), and again
when Heroic updated the game while the launcher's entry is still the one Bridge
wrote (`epic-written.json`); one the launcher updated itself, or has elsewhere,
is left alone. It forgets an `.item` in Games whose folder is gone, and closes
a running launcher so it reads them. On the first trip for such a game, a
Windows without Epic's launcher gets it first (`Install-Launcher.ps1`, with no
questions; see Downloading once). GOG's games are DRM-free:
Bridge finds each one's
`goggame-<id>.info` a folder or two into Games and starts its primary play task
itself, as `gog:<id>`, the id Heroic's GOG games have in Monet too.
Without Heroic, the card offers Get Heroic: Flathub's
(`com.heroicgameslauncher.hgl`, installed as Monet installs the replay
recorder) and opened to sign in (`monet-quick get-heroic`).

## Downloading once

A game or a file is downloaded once, for both. Besides the Games folder,
Windows' drive keeps a folder for files on both sides, `C:\Shared with Monet`:
`monet-windows-drive` shares it at `/run/media/Shared with Windows` (the
person's alone, as the Games folder; a junction there is never followed), Files
lists it with your places while it's there ("Shared with Windows", in
`user-places.xbel`, gone again when the drive isn't open), and Explorer's Quick
Access has it in Windows (Bridge pins it once, as you). A download, a mod or an
installer saved there once is in both, and Open in Windows on a program in it
copies nothing.

Folders Monet makes on Windows' drive get its root's permissions from Linux's
NTFS drivers, which let Windows' accounts add folders but not write in them, so
Bridge grants Windows' accounts Modify on the Games folder and the shared one
once, everything in them then (`icacls … /T`, in the background, a marker in
`ProgramData\Monet`): Steam in Windows installs and updates games there.

Launchers come ready: when a game in the Games folder needs a launcher Windows
hasn't got (Epic's for one Heroic put there, Ubisoft Connect or Battle.net for
one theirs in Monet did), `monet-quick launchers` fetches its installer from its
maker into `Games\.monet\installers` while you're in Monet (about 250 MB each
for Epic's and Ubisoft's, Battle.net's a small one), so the first trip installs
it with nothing to download; `monet-windows-drive` notes which launchers
Windows has (by their programs on its drive), and an installer goes once
Windows has the launcher. In Windows, `Install-Launcher.ps1` runs only an
installer its maker signed (Epic Games, Ubisoft, Blizzard Entertainment, by
Authenticode), else fetches it itself: Epic's and Ubisoft's install with no
questions as administrator; Battle.net's shows its own window, so it runs as
you, and Bridge waits for it.

Discord comes along the same way, for calls during a trip:
- **Fetched here:** someone who uses it in Monet (Discord's or Vesktop's
  Flatpak) gets its Windows installer fetched too (`DiscordSetup.exe`, signed by
  Discord).
- **Installed there:** on the trip to sign in to launchers, Bridge puts it in
  first, as the person, since Discord installs for one account
  (`%LOCALAPPDATA%\Discord`). Then it's on the list to sign in to.
- **After that:** Windows starts it at every sign-in, so a call carries on after
  the switch. `monet-windows-drive` sees it in the person's own Windows account
  (`AppData\Local\Discord\Update.exe`), and Bridge opens it through its
  updater (`--processStart Discord.exe`).

Battle.net's and Ubisoft's games install once too, through their launchers in
Monet (Lutris, Wine): in each Wine prefix in `~/Games`, drive W: is the Games
folder (`dosdevices/w:`, one someone made stays), and Lutris and Heroic from
Flathub are let see it (`flatpak override --filesystem`). A Battle.net game
installed on W: has the `.build.info` Battle.net writes, which names it; Bridge
lists it from there (`battlenet:CODE`), and Windows' Battle.net, asked to play
it the first time, offers to locate it (the Play sheet says where:
`C:\Games\…`, from the games list's `locate`). A Ubisoft game's install
(the Wine prefix's `system.reg`, `Ubisoft\Launcher\Installs\ID`) is noted
in `Games\.monet\ubisoft\ID.json`, and Bridge writes the same key in
Windows (the folder in `C:\Games`) for Ubisoft Connect, leaving one it has
already alone.

The EA app works the same way (Lutris' `ea-app`, on drive W: too). Its games
need nothing noted: Monet Bridge reads their `installerdata.xml` in the shared
Games folder. The EA app in Windows has no Locate, so for one it doesn't know
yet Play opens its page without downloading and the sheet in Monet says to
choose Download with `C:\Games` as the place: the EA app finds the game there
and only checks it.

Getting them is one tap: Settings' Get Battle.net, Get Ubisoft Connect and Get EA app have
Lutris (Flathub's, when there's none) install them with its own installers
(`lutris:battlenet`, `lutris:ubisoft-connect`), and Monet gives the new prefix
drive W: as soon as it's there (`monet-quick wine-watch`); once one's here, the
button opens it. The gallery lists a Battle.net game on W: before Windows has
(Monet reads its `.build.info` as Bridge does, with the same table of codes),
and opening the gallery runs the sharing steps again in the background (at
most every ten minutes), so a game installed since sign-in has its launcher's
installer fetched before the trip. While Windows installs a launcher, Monet's
cover says so ("Getting Battle.net ready") instead of Windows' desktop.

What Windows' own capture tools saved comes over too: after the drive is open,
`monet-windows-files.service` moves the person's own Windows account's
`Pictures\Screenshots` and `Videos\Captures` (pictures and videos only; their
account is the one called as they are here, as Monet's Windows names it, or the
only one there is, never someone else's) into
the first person's Pictures › Screenshots and Videos, named in their language
(`user-dirs.dirs`). Read as root, written as the person (so a link of theirs
can't send it elsewhere), checked, then removed from Windows; a file of the
same name gets a number unless it's the same one. Steam's own screenshots (F12)
in Windows' Steam are copied there too, not moved, as Steam in Windows lists
them, each once (`/var/lib/monet/windows-steam-shots.json`), only those of the
Steam accounts the person uses in Monet too. The next sign-in
says so once.

So do the browsers' bookmarks. The same service reads what Edge, Chrome, Brave,
Vivaldi and Opera keep (each profile's `Bookmarks`, JSON) and Firefox
(`places.sqlite`, copied first with its journal and read read-only) in the
person's own Windows account. Only web addresses are kept, and empty folders
are left out. It writes them as the person into one bookmarks file
(`~/.local/share/monet/windows-bookmarks.html`, Netscape's format, which every
browser imports), with a note of which browsers and how many
(`windows-bookmarks.json`):
- **One browser:** its bar becomes Zen's toolbar, and the rest Zen's bookmarks.
- **Several:** a folder for each, the one with most bookmarks first.

`monet-quick zen` (at sign-in, and when that file changes: `monet-zen.path`)
puts it in a Zen profile that hasn't started yet as `bookmarks.html`.
Firefox's own first start imports that file into a new profile in place of its
few default bookmarks, so nothing of Monet writes Zen's database. A Zen
already in use is never touched. For it, Settings → Default Apps → From Windows
has Add to Zen: the file goes into Downloads as "Bookmarks from Windows", and
Zen's bookmarks window opens (`-chrome
chrome://browser/content/places/places.xhtml`), where Import and Backup adds
it beside Zen's own.

History doesn't come over: a bookmarks file can't carry it, and writing Zen's
database by hand isn't safe. Passwords can't either: Windows seals them
(DPAPI, and Chrome's app-bound keys), so the card says how. Export them from
Edge or Chrome into Shared with Monet, then use Zen's about:logins → Import
from a File, with Show the folder.

## Your photo, painted

Light & Wallpaper's sixth painting is a photo of yours, in Monet's hand and in
The Hours' four lights, so the desktop still drifts from dawn to night with it.
**Choose a photo…** (Qt's file dialog) hands it to `monet-quick paint-photo`,
which paints it in its own unit (`monet-paint.service`, nice 10, idle I/O)
while Settings shows how far it is; the wall changes to it by itself when it's
done, and the last one stays until the new one has all four lights.
`monet-paint` (NumPy and Pillow, in the image) uses the brush The Hours were
painted with (`tools/make-paintings.py`' bristle stamps): the photo the right
way up and cropped to the screen's shape (2560 × 1440, or 3840 × 2160 for a 4K
screen), a little more color, a blurred underpainting, then four layers of
strokes from broad to fine, each along the picture's edges (its smoothed
structure tensor) or level where it's smooth, in the color under it, the finer
ones only where the canvas still strays from the picture. The four lights are
the same strokes, each mapped onto that light's palette from The Hours (rose
and lavender at dawn, near the photo at midday, orange and violet at dusk,
moonlit blue at night), into `~/.local/share/monet/paintings/photo/` with a
preview tile beside them. `monet-light` hands the wallpaper the folder
(`PhotoFolder`), on the desktop and the lock screen, and falls back to The
Hours if it's gone; the placard calls it "Your photo, dusk".

## Not Apple

Monet takes Apple's simplicity, not its look: no menu bar, no dock, no traffic
lights, no San Francisco, no Apple wallpapers or names. Its identity is its
own: the painting, the hours, one sun.

## Making the artwork

Everything is generated, so it can be changed and rendered again:

```sh
python3 tools/make-paintings.py   # The Hours, Water Lilies and Haystacks (4K)
python3 tools/make-branding.py    # marks, Windows icon, installer art
python3 tools/make-icons.py       # icon theme, brush texture
python3 tools/make-cursors.py     # pointer
python3 tools/make-sounds.py      # sounds (needs soundfile)
python3 tools/make-plasma-style.py
python3 tools/make-decoration.py  # window frames (after make-icons.py's painter)
python3 tools/make-kvantum.py
python3 tools/make-gtk.py
python3 tools/make-zen.py         # Zen's window ground and new-tab paintings
```
