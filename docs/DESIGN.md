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
| Left | The Monet menu (the sun) and Windows Games (the sun as a play button) |
| Middle | Apps and open windows, then Trash. Running apps get a small dab of sun under them: longer for the window you're in, faint when it's minimized, with a warm wash when an app asks for you. Pointing at one raises a pebble of glass |
| Right | Quick Settings, status icons, the clock. Brightness and Night Light live in Quick Settings, beside Mist and Smoke, so KDE's own Brightness panel (with its second "Dark Mode" switch) stays out. The open icon's pebble keeps to its own cell: Plasma grows it by the island's margins on every side, so the style draws it inset by them |

The islands step aside: each is a "dodge windows" panel, so it slides away
when a window comes over it and back when you point at the bottom edge
(KWin's sliding popups, 240 ms going and 200 ms coming). New accounts get it
from the layout, existing ones once from `monet-look` (only from KDE's
always-visible); Light & Wallpaper's "Bar steps aside" keeps them in view.

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
| Islands, popovers, tooltips | Plasma style `monet` (`tools/make-plasma-style.py`), radius 22 / 20 / 12, soft shadow that sits lower than the glass. A solid copy of each (`solid/`) for when a window touches the islands, and an opaque one (`opaque/`) without compositing, so they never turn into Breeze |
| On the glass | The same style draws everything Plasma puts on it, so the app menu, search, the popovers, notifications, the lock screen and Alt+Tab are Monet's too: pebble buttons (radius 8, so check boxes stay round), a well with a lily ring for typing, soft highlights (an ink wash to point, lily for what's chosen), Monet Settings' switch and slider, glass tabs, hairline headings, a lily progress bar and a lily arc for "working" |
| App windows (Files, Kate, ...) | Kvantum themes `Monet` and `MonetDark` (`tools/make-kvantum.py`): glass at the edges (title, toolbar, sidebar), paper or smoke under the content, rounded controls, a soft Lily selection. Menus and tooltips cast a soft shadow, blur with rounded corners, part groups with a hairline and highlight the item in lily, inset from the edge |
| GTK apps (the Store, Flathub's) | `tools/make-gtk.py`: KDE's own colors for GTK first, then paper or smoke, lily and the sun, as named colors and, for libadwaita 1.6 and newer, as CSS variables |
| Zen, the browser | `linux/share/monet/zen`, which `monet-quick zen` copies into each Zen profile and imports from `userChrome.css` and `userContent.css` (at sign-in, and as Zen arrives or makes its profile: `monet-zen.path`; before Zen's first start, Monet makes its profile, already dressed). Behind the sidebar and around the page, the painting blurred and washed in paper or smoke (`tools/make-zen.py`); lily for the accent; Monet's paper and smoke for what pops up; radius 12. Tabs: an ink wash under the pointer, the open one on a pebble of paper. The address field is a well with a lily ring while you type; on a page it floats as a sheet with Monet's soft shadow. The space's name in Fraunces. Zen's welcome and its default-browser question are skipped: Monet makes it the browser. A new tab opens on the painting itself, by daylight in Mist and by night in Smoke. Zen follows the PC's light. Its own theme picker can't override Monet's colors; uninstalling Monet gives Zen its own look back |
| Monet Settings | The Plasma style's dialog glass around a solid paper page |
| Title bars | Monet's own window frames (`tools/make-decoration.py`, KWin's Aurorae): the app style's glass, so title bar and window are one sheet, radius 14 at the top and 10 below, a wide soft shadow in ink. The buttons are signs brushed in ink; under the pointer a dab of paint swells up beneath the sign (lily to minimize, ochre to maximize, the sun to close). One frame per light and glass (`Monet`, `MonetSmoke`, and `Solid` of each), switched by `monet-light` |
| Terminal | Konsole color schemes with opacity and blur; a thin cursor, room around the text, the menu behind a button |

Two global themes carry this into KDE's settings: **Mist** and **Smoke**
(`org.monet.desktop`, `org.monet.smoke.desktop`), KDE's Light and Dark. They
differ only in colors and never set the app style or the wallpaper, so
choosing one keeps the glass and The Hours. Picking one on the first page of
KDE's settings keeps Mist or Smoke, and its Automatic is Follow the hours
(`monet-light sync`); KDE's own Global Theme page, with its "Dark Mode", is
hidden. The painting goes with the light: Mist drifts between dawn and
midday, Smoke between dusk and night (`monet-light paint`).

Glass is for edges; anything you read sits on paper (or smoke). Turning
**Glass** off in Settings switches to `monet-solid` and the `MonetSolid` /
`MonetDarkSolid` app themes: the same shapes and colors, without the
see-through. Monet turns it off by itself where the processor draws the
screen (no graphics driver, or a virtual machine), until it's chosen.
`monet-light` then leaves `~/.config/monet/glass-off`: the desktop widgets
(`Glass.qml`) sit on paper instead of frosting the painting live, and the
lock screen skips its full-screen blur, the two heaviest things to draw on
an old PC.

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
- **Windows Games**: the same, with the sun turned into a play button.
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
- **Recently Played**: the Steam games played last (`monet-quick played`:
  the appmanifests and each account's localconfig, newest first, Steam's
  tools left out), each its tall cover from Steam's picture cache or a
  painted card with its name, and when it was played; the sun comes up over
  a cover under the pointer, and a click starts it the way Steam's Play
  does (`monet-quick play`). As many as the card is wide.
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
  and swapped as with the gallery (`DesktopEditMode.qml`).

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

**Monet Settings** (`org.monet.quick/contents/ui/MonetSettings.qml`): one
glass sheet, about 1000 × 700. What other systems have, Monet's way: Sound
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
kernel's lockdown), so Monet can't stay in memory while Windows runs the
way Windows does; instead, `monet-ready-leave.service` arms at shutdown when
BootNext is Windows' boot manager, `monet-ready-boot.service` (before every
sign-in screen) writes a one-time `[Autologin]` for `plasmalogin` when the
trip is fresh (a day at most) and clears it otherwise, and the session's
`monet-ready-lock.service` (after KWin, before plasmashell) locks a sign-in
whose PAM service is `plasmalogin-autologin`, so the lock screen shows
first and the desktop starts behind it. About shows the last start: the
PC's own (firmware), Monet's (loader, kernel, system: `systemd-analyze`)
and the desktop's (sign-in to plasmashell). On the glass: the name in Fraunces, search,
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
pieces follow too, and which Monet's look then leaves alone) and the screen
reader where Orca is. Storage shows what fills the disk in one bar (games,
apps, your files, Monet) and makes room: the Trash, asked once more before
it's emptied, and Downloads, opened in Files. Updates offers the Monet
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
helper does the work. Settings in the dock and the app menu runs `monet-quick open [page]`,
which rings Quick Settings to open the sheet; without Quick Settings it opens
KDE's System Settings instead. Pictures come from `make-icons.py` into
`linux/share/monet/settings`.

**More settings** is KDE's System Settings, one click away from Monet
Settings for anything rarer, and it shouldn't feel like another product.
Its list has Monet Settings' marks: the same swatches cut from the
paintings with a white sign, one painting per part of the list
(`make-icons.py`, `MARKS`). It leaves out the pages for what Monet's look
and light take care of (KDE's Global Theme with its Dark Mode, Day-Night
Cycle, colors, styles, window frames, icons, splash and sign-in screens,
effects), KDE's updater, and the pages about what's inside, like About
this System. Help menus don't offer About KDE (KDE's kiosk settings,
written by `monet-look`).

**Built in** (`image/Containerfile`): the everyday apps are part of Monet,
not downloads: Photos, Documents, Video, Music, Calculator and Archives,
built against the Plasma already there (tens of megabytes, where Flathub
would bring KDE's gigabyte runtime), in Monet's glass app style, and there at
the first sign-in. With them come previews of PDFs and videos in Files. Each
kind of file opens in its app from the start (`/etc/xdg/mimeapps.list`,
written by install.sh): pictures in Photos, PDFs and e-books in Documents,
films in Video, songs in Music, archives in Archives, text in the Text
Editor, rather than in whichever app claims it first. Zen and the big apps
come from Flathub (`monet-apps`), which skips anything built in.

Apps go by what they are, not their project names: Files, Terminal, Text
Editor, Photos, Documents, Screenshot, Store. KDE's and Bazzite's own tools
(Info Center, Welcome Center, Bazzite's portal, links and updater, the
input-method and app-style tools) stay out of the menu, and nothing greets you from Bazzite or KDE. The Store's front page
is Monet's picks under strips of The Hours, by daylight in Mist and by
night in Smoke (`make-store.py`).

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
- **The steps:** Hello (language and keyboard), Wi-Fi (skipped with a cable),
  who's using this PC, Your apps (Photos, Documents, Video, Music and
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
  time zone, Wi-Fi, Windows' waiting state and the apps picked
  (`/var/lib/monet/apps`, which `monet-apps.timer` installs from Flathub
  once Monet is online, until all are in; a PC that never chose gets the
  everyday ones), imports Universal Blue's
  driver key, and names the firmware entry "Monet".
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
have no anti-cheat and get no mark. Play on Windows' covers and the Windows
Games widget mark those that play here too, and Games & Controllers lists the
games installed here that need Windows, with Play on Windows when they're
there too.

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
