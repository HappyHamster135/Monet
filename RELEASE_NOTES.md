One USB stick installs everything: Monet, and a games-only Windows that sets itself up.

**Start here: [Install Monet](https://github.com/HappyHamster135/Monet/blob/HEAD/docs/INSTALL.md)**

### Downloads

| File | What |
|---|---|
| **Monet-0.6.0-Installer.iso** | **Start here.** Write it to a USB stick and boot from it. |
| Monet-0.6.0-Windows.zip | Only for "next to my Windows" when Windows is encrypted |
| Monet-0.6.0-Linux.tar.gz | Only for adding Monet to an existing Bazzite install |

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
