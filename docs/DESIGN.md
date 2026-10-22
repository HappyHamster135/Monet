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

Behind both: KWin's blur (strength 12, a little noise for grain, saturation
1.7 in kwinrc since KWin 6.7 folded its contrast effect into the blur), so the
glass carries the painting's light instead of looking grey. KWin blurs whole
pixels with a hard edge behind panels and popovers, so each frame's mask
rounds its corners 1 px inside the glass's, as Breeze does, and the blur
stays under the glass's soft edge instead of making a jagged halo.

Light in the glass: a rim brightest along the top that fades down the sides
(the sides stretch, so it fades over the whole height), the way light gathers
in the thickness of a pane, and a soft sheen under the top edge. A hairline
of ink outside it keeps the edge. In the corners all three follow the glass's
own arc, so they run on from the straight edges without a step.

| Where | How |
|---|---|
| Islands, popovers, tooltips | Plasma style `monet` (`tools/make-plasma-style.py`), radius 22 / 20 / 12, soft shadow that sits lower than the glass. A solid copy of each (`solid/`) for when a window touches the islands, and an opaque one (`opaque/`) without compositing, so they never turn into Breeze |
| On the glass | The same style draws everything Plasma puts on it, so the app menu, search, the popovers, notifications, the lock screen and Alt+Tab are Monet's too: pebble buttons (radius 8, so check boxes stay round), a well with a lily ring for typing, soft highlights (an ink wash to point, lily for what's chosen), Monet Settings' switch and slider, glass tabs, hairline headings, a lily progress bar and a lily arc for "working" |
| App windows (Files, Kate, ...) | Kvantum themes `Monet` and `MonetDark` (`tools/make-kvantum.py`): glass at the edges (title, toolbar, sidebar), paper or smoke under the content, rounded controls, a soft Lily selection. Menus and tooltips cast a soft shadow, blur with rounded corners, part groups with a hairline and highlight the item in lily, inset from the edge |
| GTK apps (the Store, Flathub's) | `tools/make-gtk.py`: KDE's own colors for GTK first, then paper or smoke, lily and the sun, as named colors and, for libadwaita 1.6 and newer, as CSS variables |
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
  a box camera (screenshots). The app menu's categories as well, and
  Monet's widgets: the sun behind a cloud (Weather), the card beside a gilt
  frame (Placard).
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
  frosts the patch of painting it covers (following the light as it drifts,
  and the widget as it's moved), washed in mist or smoke, with the rim of
  light, a hairline and a soft shadow. Elsewhere, frosted paper.
- **Weather**: the temperature in Fraunces, the sky painted beside it (the
  sun and its reflection for a clear day, a crescent at night, clouds, rain,
  snow, fog, a storm) and the next four days. From Open-Meteo once a place is
  chosen: no account, only the place is sent. The place is chosen right on
  the card ("Where are you?", a town, then one of three matches), never in
  KDE's settings window; click the place's name for another. The first
  place sets the degrees the way the PC's region counts them.
- **Calendar**: the month in Fraunces, today on a dab of the sun.
- **Clock** (in the right island, instead of KDE's): the time over the date
  in Inter; a click opens the day in Fraunces and its month, as Calendar
  draws it.
- **Now Playing**: the cover, the track in Fraunces, back, play or pause on
  the sun, and next.
- **Note**: paper pinned with a dab of lily; kept as you type.
- **Photo Frame**: your Pictures in a gilt frame, a new one every ten minutes.
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
glass sheet, about 1000 × 700. On the glass: the name in Fraunces, search,
and the pages, each marked by a swatch cut from the paintings with a white
glyph, in three groups: Monet's own, the ones KDE's settings open (marked
↗), and Windows, Updates and About. A pebble of glass glides to the page
you're on. On the paper: the page under its swatch, title and a line saying
how things stand ("Connected to Harbor"), in rounded cards with switches
(Lily when on), devices with what they are (headphones, a controller, a
mouse) in a chip that turns lily while connected, and the sun only for
Restart in Windows. Updates looks for a new Monet, app updates and the PC's
own firmware (UEFI, disks, docks: fwupd, from their makers through LVFS)
together, and installs each only from its own button; firmware that installs
during a restart says so. The `monet-quick` helper does the
work. Settings in the dock and the app menu runs `monet-quick open [page]`,
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

Apps go by what they are, not their project names: Files, Terminal, Text
Editor, Photos, Documents, Screenshot, Store. KDE's and Bazzite's own tools
(Info Center, Welcome Center, Bazzite's portal and links) stay out of the
menu, and nothing greets you from Bazzite or KDE. The Store's front page
is Monet's picks under strips of The Hours, by daylight in Mist and by
night in Smoke (`make-store.py`).

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
  Monet on a blank disk through the real screens and starts it, then looks
  around it: signs in, and shows the desktop, the app menu, Files and
  Settings, then locks the screen and unlocks it with the password (the run's
  summary says whether it did). So every build shows Monet as it really
  looks, KWin's blur and all. The screenshots are kept in the registry:
  `python3 tools/ci-screens.py pull ghcr.io/happyhamster135/monet:ci-screens screens/`
  (or the run's `setup-screens` artifact). It runs with every release and by
  hand from the Actions tab (Monet OS → Run workflow).

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
python3 tools/make-sounds.py      # sounds (needs soundfile)
python3 tools/make-plasma-style.py
python3 tools/make-decoration.py  # window frames (after make-icons.py's painter)
python3 tools/make-kvantum.py
python3 tools/make-gtk.py
```
