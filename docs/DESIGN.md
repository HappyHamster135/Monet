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

## The idea: Impression

Monet is painted, not machined. It's named after the painter, so the desktop
is a painting: *Impression, soleil levant* (1872), the harbor at Le Havre in
the morning mist, with one bright orange sun. Everything else follows from it.

- **The Hours.** One harbor in four lights: dawn, midday, dusk and night. The
  wallpaper drifts from one to the next as the day goes, over 45 minutes, the
  way Monet painted the same view at different times.
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
| Right | Quick Settings, status icons, the clock |

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

- **Mist** (dawn and midday): paper at about 50%, a bright line along the top.
- **Smoke** (dusk and night): smoke at about 50%, a faint line along the top.

Behind both: KWin's blur (strength 12, a little noise for grain) plus 1.5x
color, so the glass carries the painting's light instead of looking grey.

| Where | How |
|---|---|
| Islands, popovers, tooltips | Plasma style `monet` (`tools/make-plasma-style.py`), radius 22 / 20 / 12, soft shadow that sits lower than the glass. A solid copy of each (`solid/`) for when a window touches the islands, and an opaque one (`opaque/`) without compositing, so they never turn into Breeze |
| On the glass | The same style draws everything Plasma puts on it, so the app menu, search, the popovers, notifications, the lock screen and Alt+Tab are Monet's too: pebble buttons (radius 8, so check boxes stay round), a well with a lily ring for typing, soft highlights (an ink wash to point, lily for what's chosen), Monet Settings' switch and slider, glass tabs, hairline headings, a lily progress bar and a lily arc for "working" |
| App windows (Files, Kate, ...) | Kvantum themes `Monet` and `MonetDark` (`tools/make-kvantum.py`): glass at the edges (title, toolbar, sidebar), paper or smoke under the content, rounded controls, a soft Lily selection. Menus and tooltips cast a soft shadow, blur with rounded corners, part groups with a hairline and highlight the item in lily, inset from the edge |
| GTK apps (the Store, Flathub's) | `tools/make-gtk.py`: KDE's own colors for GTK first, then paper or smoke, lily and the sun, as named colors and, for libadwaita 1.6 and newer, as CSS variables |
| Monet Settings | The Plasma style's dialog glass around a solid paper page |
| Title bars | Monet's own window frames (`tools/make-decoration.py`, KWin's Aurorae): the app style's glass, so title bar and window are one sheet, radius 14 at the top and 10 below, a wide soft shadow in ink. The buttons are signs brushed in ink; under the pointer a dab of paint swells up beneath the sign (lily to minimize, ochre to maximize, the sun to close). One frame per light and glass (`Monet`, `MonetSmoke`, and `Solid` of each), switched by `monet-light` |
| Terminal | Konsole color schemes with opacity and blur; a thin cursor, room around the text, the menu behind a button |

Two global themes carry this into KDE's settings: **Monet Mist** and
**Monet Smoke** (`org.monet.desktop`, `org.monet.smoke.desktop`), KDE's
Light and Dark. They differ only in colors and never set the app style or
the wallpaper, so choosing one keeps the glass and The Hours. Picking Light
or Dark in KDE's settings keeps Mist or Smoke (`monet-light sync`).

Glass is for edges; anything you read sits on paper (or smoke). Turning
**Glass** off in Settings switches to `monet-solid` and the `MonetSolid` /
`MonetDarkSolid` app themes: the same shapes and colors, without the
see-through.

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
  (pictures), an open book (documents), an abacus, a little stage (videos),
  a sunflower (disk usage), a letter and quill (text), a chest (archives),
  a box camera (screenshots). The app menu's categories as well.
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
- **The bar's signs** (sound, network, battery, power, clipboard, drives) are
  brushed in ink in the Plasma style's `icons/`, tapering like a brush, and
  recolor with the light. Sleep is the moon, shut down the setting sun.
- **One grid.** Every motif is laid out on a 128 grid and fills about 0.8 of
  it along its long side, centered, so the dock reads evenly next to round
  icons like Firefox and Steam. Painted at 512 px, kept at 256 inside SVGs.
- Everything is in the `Monet` icon theme (`tools/make-icons.py`). Apps with
  their own brand (Firefox, Steam, games) keep their icons; toolbar icons
  inside apps are Breeze's, in Monet's colors.

## Pointer

`Monet-cursors` (`tools/make-cursors.py`): ink with a paper edge and a soft
shadow, at 24 to 64 px. While something works, Monet's sun breathes over its
rippling reflection, as at start. Resize, move, text, hand and the rest in
the same ink; anything not drawn falls back to Breeze.

## Starting and signing in

- **Boot screen** (Plymouth `monet`, the same as Monet Setup's): the harbor
  at dawn with the sun breathing. A disk password is asked for on it, in a
  line of white with a dot per letter. Built into the image's initramfs.
- **Sign-in** (SDDM): the harbor at night and Monet's mark, with Monet's
  fields, buttons and colors (its home gets Monet's Plasma style and colors
  at boot) and Monet's pointer.

## Apps

**Files** (Dolphin with the Monet app style): glass title, toolbar and
sidebar; the files on paper; folders big enough to see their paintings
(80 px, previews on); a soft Lily wash for the selection instead of a solid
block.

**Monet Settings** (`org.monet.quick/contents/ui/MonetSettings.qml`): one
glass sheet, about 1000 × 700. On the glass: the name in Fraunces, search,
and the pages, each marked by a swatch cut from the paintings with a white
glyph, in three groups: Monet's own, the ones KDE's settings open (marked
↗), and Windows, Updates and About. A pebble of glass glides to the page
you're on. On the paper: the page under its swatch, title and a line saying
how things stand ("Connected to Harbor"), in rounded cards with switches
(Lily when on), devices with what they are (headphones, a controller, a
mouse) in a chip that turns lily while connected, and the sun only for
Restart in Windows. The `monet-quick` helper does the
work. Settings in the dock and the app menu runs `monet-quick open [page]`,
which rings Quick Settings to open the sheet; without Quick Settings it opens
KDE's System Settings instead. Pictures come from `make-icons.py` into
`linux/share/monet/settings`.

## Motion

| Name | Duration | Curve | Used for |
|---|---|---|---|
| Rise | 380 ms | `cubic-bezier(.2, .9, .25, 1.08)` | popovers, sheets, toasts |
| Glide | 320 ms | `cubic-bezier(.2, .9, .25, 1.08)` | a pebble moving to what you chose: Settings' pages, Quick Settings' light |
| Settle | 200 ms | `cubic-bezier(.4, 0, 1, 1)` | closing: leaving is quicker than arriving |
| Press | 160 ms | `cubic-bezier(.2, .9, .25, 1.25)` | buttons, tiles, the islands |
| Sunset | 900 ms | `cubic-bezier(.4, 0, .2, 1)` | the screen fades to night before Windows |

Desktop animation speed 0.8x. Windows scale gently in and out. With
animations turned off in System Settings, Monet's widgets fade or cut.

## Signature moments

- **Start:** the dawn painting comes out of the dark, the sun rises from its
  reflection, the reflection ripples.
- **Play on Windows:** a sheet rises with the game's cover. On Restart & Play
  the sun sets: the screen fades to night and the sun sinks into the water.
- **Lock screen and sign-in:** the same painting, in the same light.

## The installer

Fedora's installer (Anaconda), dressed as Monet, since its screens and
wording are fixed:

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
  who's using this PC, Ready (Monet and Windows, or next to my Windows, and
  the disk), installing, All set. Anything that can't go ahead says why on
  the page, in a sentence.
- **Installing** (`monet_setup/install.py`, its own process reporting JSON
  lines): partitions (EFI, boot, Monet's btrfs with `root` and `download`
  subvolumes, Windows' share left free), downloads Monet with skopeo into
  `download` (kept across tries; restarted when it stalls), installs it
  with `bootc install to-filesystem`, sets up the person, language, keyboard,
  time zone, Wi-Fi and Windows' waiting state, imports Universal Blue's
  driver key, and names the firmware entry "Monet".
- **Tested in CI** (`tools/vm-test.py`): QEMU with Secure Boot on installs
  Monet on a blank disk through the real screens and starts it; the
  screenshots are kept in the registry (`tools/ci-screens.py`).

## Not Apple

Monet takes Apple's simplicity, not its look: no menu bar, no dock, no traffic
lights, no San Francisco, no Apple wallpapers or names. Its identity is its
own: the painting, the hours, one sun.

## Making the artwork

Everything is generated, so it can be changed and rendered again:

```sh
python3 tools/make-paintings.py   # The Hours (4K)
python3 tools/make-branding.py    # marks, Windows icon, installer art
python3 tools/make-icons.py       # icon theme, brush texture
python3 tools/make-cursors.py     # pointer
python3 tools/make-plasma-style.py
python3 tools/make-decoration.py  # window frames (after make-icons.py's painter)
python3 tools/make-kvantum.py
python3 tools/make-gtk.py
```
