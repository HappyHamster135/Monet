One USB stick installs everything: Monet, and a games-only Windows that sets itself up.

**Start here: [Install Monet](https://github.com/HappyHamster135/Monet/blob/HEAD/docs/INSTALL.md)**

### Downloads

| File | What |
|---|---|
| **Monet-0.5.0-Installer.iso** | **Start here.** Write it to a USB stick and boot from it. |
| Monet-0.5.0-Windows.zip | Only for "next to my Windows" when Windows is encrypted |
| Monet-0.5.0-Linux.tar.gz | Only for adding Monet to an existing Bazzite install |

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
- "Install Monet and Windows" **erases the PC**.
- Windows activates by itself if the PC came with Windows. Otherwise it runs
  unactivated (small watermark).
- One blue screen at the first start can't be skipped: it's how the PC's
  firmware confirms the NVIDIA driver may run with Secure Boot on.
