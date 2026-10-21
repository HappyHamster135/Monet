One USB stick installs everything: Monet, and a games-only Windows that sets itself up.

**Start here: [Install Monet](https://github.com/HappyHamster135/Monet/blob/HEAD/docs/INSTALL.md)**

### Downloads

| File | What |
|---|---|
| **Monet-0.4.0-Installer.iso** | **Start here.** Write it to a USB stick and boot from it. |
| Monet-0.4.0-Windows.zip | Only for "next to my Windows" when Windows is encrypted |
| Monet-0.4.0-Linux.tar.gz | Only for adding Monet to an existing Bazzite install |

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
