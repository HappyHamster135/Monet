One USB stick installs everything: Monet, and a games-only Windows that sets itself up.

**Start here: [Install Monet](https://github.com/HappyHamster135/Monet/blob/HEAD/docs/INSTALL.md)**

### Downloads

| File | What |
|---|---|
| **Monet-0.8.0-Make-USB-Stick.exe** | **Start here** (on Windows): makes the Monet USB stick for you. |
| Monet-0.8.0-Setup.iso | Monet Setup, Monet's own installer: the USB stick's image, for writing it yourself (on Linux or a Mac). Here once it has installed Monet in a test PC. |
| Monet-0.8.0-Installer.iso | Fedora's installer dressed as Monet: the stick's image when there's no Setup.iso. |
| Monet-0.8.0-Windows.zip | Only for "next to my Windows" when Windows is encrypted |
| Monet-0.8.0-Linux.tar.gz | Only for adding Monet to an existing Bazzite install |

### New in 0.8: Monet's own, down to the pointer

- **Every icon is a small oil painting,** in short strokes the way Monet
  painted, with violet shadows and warm light. Settings is a painter's
  palette, Terminal a night canvas on an easel, System Monitor the harbor's
  masts at sunset, the Store a market bouquet, Trash a garden pot. KDE's
  apps (Gwenview, Okular, Kate, Ark, Spectacle, ...) and the app menu's
  categories get paintings too.
- **The rest of the dock and the menu too.** The browser is a window thrown
  open onto the harbor, Steam a locomotive steaming into Saint-Lazare,
  Lutris a rowing boat, Bazzite Portal the Japanese footbridge at Giverny,
  and the Flatpak tools, Waydroid and Input Remapper have paintings of their
  own.
- **Files and drives are painted.** Text, code, pictures, music, films,
  PDFs, spreadsheets, programs and archives each have their own painted
  sheet; disks are a paint box, USB sticks a tube of paint.
- **Monet's own window frames.** Title bars are the same glass as the
  window. The buttons are signs brushed in ink, and a dab of paint swells
  up under the one you point at: lily, ochre, or the sun to close.
- **Monet's pointer:** ink with a paper edge, and Monet's sun breathing
  over its reflection while something works.
- **Clearer glass.** The painting's color comes through the panels and
  popovers more, and their edges catch the light like a pane of glass:
  brightest along the top, fading down the sides.
- **Widgets on the desktop.** Weather, Calendar, Now Playing, a Note and a
  Photo Frame, as glass cards that frost the painting behind them. A new
  desktop starts with the weather and the month at the top right; the rest
  are in the widget gallery. The weather comes from Open-Meteo once you
  choose a place (no account; only the place is sent).
- **Monet's own lock screen.** At rest, the painting and its placard: the
  date, the time in Fraunces, which light it is. Touch a key and the
  painting softens behind a sheet of glass with your name, a well for the
  password and the sun to go back in. If it ever can't load, KDE's lock
  screen takes its place, so you can always unlock.
- **The bar's signs** for sound, Wi-Fi, battery, notifications, the
  clipboard, drives and power are brushed in ink. Sleep is the moon, shut
  down the setting sun.
- **Starting and signing in are Monet's.** The boot screen is the harbor at
  dawn (and asks for a disk password there), and the sign-in screen has
  Monet's fields, buttons, colors and pointer.
- **Monet's own installer on the USB stick.** Make-USB-Stick.exe now writes
  Monet Setup whenever the release has it, and Fedora's installer only
  otherwise. Monet Setup couldn't be built before: a check in its build
  stopped it every time.
- **Firmware updates in Settings.** Updates now also finds new firmware for
  the PC's own parts (its UEFI, disks, docks), from their makers, and
  installs it when you press Install, never by itself. It says when one
  installs during the next restart, and what's in the way (like "Plug in
  the charger first").

- **The first start can't be missed.** Both installers now say, before you
  restart, what the blue screen at the first start wants: Enroll MOK, then
  `monetsetup`. Choosing Continue boot there left Monet unable to start with
  Secure Boot on ("bad shim signature"); the install guide says how to
  recover if it happened.

- **The painting goes with the light.** Choosing Mist or Smoke now changes
  the painting too, on the desktop and the lock screen: Mist drifts between
  dawn and midday, Smoke between dusk and night (or stays on midday or
  night with The Hours off). Before, only the colors changed.
- **Smoke, not Dark Mode.** KDE's own Global Theme page, with its "Switch to
  Dark Mode at Night" and Day-Night Cycle, is gone from More settings; its
  first page offers Mist and Smoke, and its Automatic means Follow the hours.
- **More settings looks like Monet Settings.** KDE's settings, one click
  away as More settings, get the same painted marks as Monet Settings'
  list, leave out the pages Monet looks after (themes, colors, window
  frames, icons, splash and sign-in screens, effects, KDE's updater, About
  this System), and Help menus no longer offer About KDE.
- **Apps by plain names.** Files, Terminal, Text Editor, Photos, Documents,
  Screenshot, Calculator, Music, Phone... instead of Dolphin, Konsole and
  the rest. KDE's and Bazzite's own tools leave the menu, and nothing
  greets you from Bazzite anymore: no portal or announcements at sign-in,
  no welcome in Terminal, no KDE Welcome Center after updates. KDE's
  About page says Monet.
- **The Store's front page is Monet's:** Play, Talk & stream, Music & film,
  Work & make and Everyday, each under a strip of The Hours (by daylight in
  Mist, by night in Smoke), without Bazzite's notes.

Updating from 0.7: Settings → Updates → Install, then restart. The new look
arrives when you sign in; your panels stay as they are, and the weather and
the other widgets are in the desktop's widget gallery.

### New in 0.7: Monet all the way through

- **Quick Settings and Monet Settings open.** In 0.6.4 they didn't load at
  all ("Sorry! There was an error loading Quick Settings"). Now they do,
  and Settings → Windows & Games → Check Monet works again.
- **Make-USB-Stick.exe opens.** It closed right after asking for
  administrator rights. Now its window shows, and if something ever goes
  wrong it says what, instead of disappearing.
- **The bar is Monet's everywhere.** Running apps get a small dab of sun
  under them: longer for the window you're in, faint when it's minimized.
  The app menu, search, notifications, the popovers, the lock screen and
  Alt+Tab use Monet's buttons, switches, sliders and highlights instead of
  KDE's. When a window touches the islands they turn solid but stay
  Monet's, instead of becoming plain KDE panels.
- **Menus float.** Right-click menus and tooltips in apps like Files and
  Terminal cast a soft shadow, have dividers between groups again and a
  lily highlight.
- **The Store and other Flathub apps in Monet's colors.** Paper or smoke,
  lily for choices, the sun for the button that goes ahead. Before, newer
  apps like the Store kept their own grey and blue, older ones lost KDE's
  colors, and dark mode was bluish. The Store's icon in the dock is
  Monet's painted bag.
- **Settings is clearer.** Each page shows its painting and how things
  stand ("Connected to Harbor"), the list glides to the page you're on,
  pages that open KDE's settings are marked ↗, Bluetooth devices show what
  they are, secured networks show a lock, and updates show they're
  working. Everything fits again: "More settings in KDE" had slipped off
  the bottom.
- **Terminal** has a thin cursor, more room around the text, and its menu
  behind a button instead of a menu bar.
- **Window shadows** are softer and wider, in ink instead of black.

Updating from 0.6: Settings → Updates didn't open in 0.6.4, so open
Terminal and run `monet update`, then restart. The new look arrives when
you sign in; your panels stay as they are.

### New in 0.6.4: make the USB stick with one click

- **Monet-0.6.4-Make-USB-Stick.exe.** On Windows, double-click it, choose the
  USB stick, and it does the rest: downloads Monet (picking up where it
  stopped if the connection drops), writes the stick and checks it. Only
  USB sticks are offered, never the disk Windows runs from, and it asks
  before erasing. Nothing else to download or install: no Rufus, no
  Etcher, no Fedora Media Writer.

### New in 0.6.3: Monet's own switches

- **No more blue switches.** Apps that drew the usual blue toggles (Bazaar,
  Flatseal, Bottles and other GTK apps) now use Monet's: a pill that turns
  lily green when on, with a white knob. Checkboxes, radio buttons, sliders
  and progress bars match, in Mist and in Smoke.
- **Store is Bazaar when Bazzite has it**, otherwise Discover, and the dock's
  store button opens it.

### New in 0.6.2: more of Monet, everywhere

- **Apps from Flathub look like Monet.** GTK apps (Flathub's and the
  system's) use Monet's paper and ink, lily for choices and the sun for the
  button that goes ahead, and turn to Smoke after dark with the rest of
  Monet. A gtk.css you wrote yourself is left alone.
- **Store.** Discover is called Store in the dock and the app menu, and no
  longer pops up about updates: those stay in Settings, when you ask.
- **More in Settings:** Mouse & Keyboard, Power & Sleep, Notifications,
  Date & Time, Accounts and Default Apps, each with its swatch from the
  paintings. They open the matching page in KDE's settings.

Updating: sign out and in again after the update.

### Fixed in 0.6.1

- **The download shows itself.** Monet is a 5.7 GB download, and the installer
  only said "Running pre-installation scripts" the whole time, so it looked
  stuck. Now a Monet page covers it: how much is downloaded, how long is
  left, and a note that it picks up again if the connection drops.
- **A download that stops moving starts again by itself** after four minutes,
  keeping what it already has. Before, a stalled connection could hang there
  for hours.
- **Everything fits again.** 0.6 swapped the installer's font for a wider one
  and made its buttons roomier, but its screens are laid out for its own font
  and sizes, so labels and buttons spilled out of their boxes. The installer
  keeps Monet's colors and painting and its own font and sizes.
- **The painted start menu shows** on PCs without Secure Boot (GRUB gave up
  on it because the big title font was too wide for its text layer). With
  Secure Boot on, GRUB doesn't accept fonts from the stick, so the plain
  menu shows; Monet Setup, coming next, skips the menu altogether.

### New in 0.6: Monet's own installer

- **Monet from the first second.** The USB stick is called Monet, and its
  start menu is the harbor at dawn with the choices on smoked glass. The
  installer says "Loading Monet", and its pages are Monet's paper and ink:
  Inter for reading, Fraunces for titles, lily for your choices and the sun
  for the button that goes ahead, with the harbor rising along the bottom of
  the welcome and progress pages. (Before, only the side picture was Monet's;
  the rest of its look never loaded.)
- **Fewer "unknown error"s.** The installer waits for Wi-Fi, checks Monet can
  be downloaded (trying a few times), and downloads it in a way that picks up
  again when the connection drops, instead of failing on the first hiccup.
  It never mistakes the USB stick for the PC's disk, even when the stick
  doesn't say it's USB, and it waits for every disk to show up first.
- **A shorter install.** Windows no longer downloads at the end of the
  install, where 7 GB looked like the installer had stopped. It downloads
  after your first sign-in, with its progress showing, and Monet asks before
  restarting to install it.
- **Monet's name everywhere.** The PC's boot menu, KDE's About page, the
  sign-in screen (with Monet's mark) and the PC's network name say Monet.
- **A personal touch.** The placard on the desktop greets you by name:
  good morning, good evening, and "still up?" after midnight.

### Fixed in 0.5.2

- **Play goes to Windows.** Many PCs keep their old Windows boot entry after
  the disk is wiped, and Monet picked that one, so the PC came straight back
  to Monet. Monet now only starts a Windows entry whose partition is really
  there, and makes one if the PC has none. A Windows that's still finishing
  its own setup goes first for the trip, so its own restarts don't land in
  Monet. Monet checks that the switch was saved before restarting, always
  restarts through the PC's firmware, and the first trip after Windows set
  itself up no longer turns straight back before the game starts.
- **If a trip doesn't reach Windows,** Monet says why at the next sign-in
  (and in Settings → Windows & Games), and tries another way next time.
  Every trip is logged in `/var/lib/monet/switch.log`.
- **Dark mode keeps Monet's look.** KDE's Light and Dark choices now pick
  Monet Mist and the new **Monet Smoke**, instead of Breeze. Choosing a Monet
  theme in KDE's settings no longer resets the glass or the painting. If dark
  mode already broke your desktop, it's mended at the next sign-in.
- **Updates only when you ask.** Monet no longer updates in the background.
  Settings → Updates checks, installs Monet and app updates when you say so,
  then offers a restart.
- **Icons in step.** Settings, System Monitor, Store and Trash are redrawn on
  the same grid as Files and Terminal, so the dock reads evenly.
- **Smoother light changes.** Hours, Mist and Smoke switch once, right after
  the toggle moves, instead of stuttering it.

Sleep works normally on Monet. What Monet can't do is hibernate (Secure
Boot's lockdown blocks it), which is why Windows is the one that hibernates
to switch fast.

### New in 0.5.1: Settings and Files

- **Monet Settings.** One glass sheet with the settings you actually change:
  Light & Wallpaper, Wi-Fi, Bluetooth, Display, Sound, Windows & Games,
  Updates and About. The pages sit on paper so they're easy to read, and each
  is marked with a swatch cut from the paintings. Open it from Settings in the
  dock or the app menu, or All Settings in Quick Settings. Everything else is
  one click away under **More settings in KDE**.
- **Painted folders and icons.** Folders are cut from the paintings (Home and
  Documents in dawn light, Downloads at night, Pictures, Music and Videos at
  dusk), with a small white mark for what's inside. Files, Terminal,
  Settings, Store, System Monitor and Trash are painted marks with nothing
  behind them, instead of icons on tiles.
- **Files** keeps its glass at the edges only: your files sit on paper, with
  a soft Lily selection, bigger icons and previews.
- **New switches** in Settings → Light & Wallpaper: keep one painting all day
  instead of following the hours, hide the placard, or turn glass off for
  solid panels and windows.
- **Window titles** are set in Fraunces, like the clock.
- **Windows & Games** in Settings shows whether Windows is ready, plays a game
  from its cover, and checks that everything is set up.

Updating from 0.5: restart after the update. Your panels stay as they are,
and Settings in the dock opens Monet Settings.

### New in 0.5: Impression

Monet has its own look now, after Claude Monet's *Impression, soleil levant*.

- **The Hours.** The wallpaper is one painted harbor in four lights: dawn,
  midday, dusk and night. It drifts from one to the next as the day goes.
- **Glass.** The bar is three glass islands along the bottom, and panels,
  popovers, title bars, the terminal and app windows like Files are
  see-through, with the painting blurred behind them. Mist while it's light
  out, smoke after dark. Choose Hours, Mist or Smoke in Quick Settings.
- **A placard** on the desktop with the time, the date and the painting's name.
- **Windows Games** is a gallery of covers. Play asks once, then the screen
  fades to night as the sun sets, and the PC restarts in Windows.
- **Quick Settings** in the clock island: Wi-Fi, Bluetooth, Night Light,
  Do Not Disturb, sound, brightness and the light.
- **New icons and fonts:** the sun mark, painted pebbles for Monet's own apps,
  Fraunces for the clock and titles, Inter for reading.
- **A sunrise** when Monet starts, and the night harbor at sign-in.
- **The installer** uses the dawn painting and the sun for its main button.

Also new:

- **`monet update`** gets the newest Monet right away (it also updates by itself).
- **Wi-Fi carries over:** the network you used while installing works in Windows too.
- **For testing:** Slay the Spire is always in Windows Games. The first time,
  Windows installs it from Steam (sign in to Steam once), then starts it.

Updating from 0.4: restart after the update and your desktop changes to the
new look by itself.

### New in 0.4

- **Monet's own installer look.** The installer says Monet instead of Fedora,
  with Monet's sunrise artwork, logo and colors.
- **Monet's start menu on every PC.** The USB stick's menu now shows "Install
  Monet and Windows" (selected) and "Install Monet next to my Windows". Before,
  most PCs still showed Fedora's menu, with "Test this media" selected.
- **One screen less.** No root password screen: the person installing is the
  administrator.

### Fixed in 0.3.1

- "Test this media" on the USB stick works again (the installer's checksum was missing).
- If Monet can't be downloaded during the install, the installer now says why
  (no internet, or the Monet package isn't public) instead of "unknown error".

### New in 0.3

- **Install Monet and Windows.** The default choice on the USB stick. Monet
  splits the disk, installs itself, then downloads Windows 11 from Microsoft
  and installs it by itself. Nothing to prepare in Windows first.
- **Windows sets itself up.** No setup questions, no Microsoft account, no
  BitLocker, no Fast Startup. Monet Bridge and the Game Profile are
  installed automatically, and preinstalled apps games don't need are removed.
- **Matches Monet.** Windows uses your name, language, keyboard and time zone
  from the Monet install.
- **If the download fails,** choosing Windows in Monet tries again, or installs
  from a Windows file you downloaded yourself.
- **Install Monet next to my Windows** is still there for keeping an existing
  Windows.

### Good to know

- **Preview.** Not tested on real hardware yet.
- The installer's wording ("Installation Summary", "Begin Installation") is
  Fedora's own and can't be changed; everything around it is Monet's.
- "Install Monet and Windows" **erases the PC**.
- Windows activates by itself if the PC came with Windows. Otherwise it runs
  unactivated (small watermark).
- One blue screen at the first start can't be skipped: it's how the PC's
  firmware confirms the NVIDIA driver may run with Secure Boot on.
