# Install Monet

One USB stick installs everything: Monet, and Windows for the games that need
it. No preparation in Windows, no BitLocker keys, no settings to change.

You need:

- A PC with an NVIDIA RTX 20-series or newer GPU
- A USB stick of 2 GB or more (it will be erased)
- Internet (Wi-Fi is fine)

**Everything on the PC is erased.** About an hour, mostly downloading.

> **Monet 0.3 is a preview** and hasn't been tested on real hardware yet.

---

## 1. Make the USB stick

1. Download **Monet-0.3.1-Installer.iso** from the
   [Monet release](https://github.com/HappyHamster135/Monet/releases).
2. Open [Fedora Media Writer](https://fedoraproject.org/workstation/download),
   choose **Select .iso file**, pick the Monet installer and your USB stick,
   and click **Write**.

## 2. Install

1. Restart with the USB stick plugged in, and open the boot menu: **F12**
   (Dell, Lenovo, Acer, Gigabyte), **F9** (HP), **Esc** or **F8** (ASUS),
   **F11** (MSI). Choose the USB stick.
2. **Install Monet and Windows** is already selected. Press **Enter**.
3. Choose your language.
4. Click **Network & Host Name** and connect to Wi-Fi.
5. Click **User Creation** and enter your name and a password.
6. Click **Begin Installation**.

The disk is already set up for you: about two thirds for Monet, one third
for Windows.

At the end, Monet downloads Windows 11 from Microsoft. The progress bar
stands still for a while. That's normal.

7. Click **Reboot** and take out the USB stick.

## 3. Let it finish (about 15 minutes)

Windows now installs itself, with a few restarts. No need to touch anything.
Monet answers all of Windows' setup questions, and sets up Monet Bridge and
the Game Profile.

Then Monet starts. **Once**, a blue screen asks to trust the NVIDIA driver,
which anti-cheat games need:

**Enroll MOK** → **Continue** → **Yes** → type **`monetsetup`** → **Reboot**

Sign in to Monet. Done.

---

## Good to know

- **Windows** has an account with your name and no password, so it starts
  straight into your games. If the PC came with Windows, Windows activates by
  itself. If not, it runs unactivated, with a small watermark.
- **Play a Windows game:** click **Windows Games** in the panel and press
  **Play**. When you quit, the PC comes back to Monet.
- **Windows' language and keyboard** match the ones you picked for Monet.

## If something isn't right

Open **Konsole** and run `monet doctor`. It says what's wrong and what to do.

**"The Monet package on GitHub isn't public".** The installer can't download
Monet. Make the package public (GitHub → your profile → **Packages** →
**monet** → **Package settings** → **Change visibility** → **Public**), then
start the installer again.

**"Test this media" fails.** Use the first menu entry instead; the test is
optional.

**Windows didn't install.** Choose **Windows** in the app menu. Monet
offers to try again.

**Microsoft blocked the download.** Choosing **Windows** opens Microsoft's
download page. Download **Windows 11 Disk Image (ISO)** into **Downloads**,
then choose **Windows** again. Monet installs it from there.

**A Linux game runs slowly on a laptop.** It may be using the built-in
graphics. In Steam: right-click the game → **Properties** → **Launch Options**:

```
__NV_PRIME_RENDER_OFFLOAD=1 __VK_LAYER_NV_optimus=NVIDIA_only __GLX_VENDOR_LIBRARY_NAME=nvidia %command%
```

**A game is missing.** Monet finds Steam, Epic, and Riot games. Add others in
`C:\ProgramData\Monet\custom-games.json` in Windows:

```json
[
  { "name": "Overwatch 2", "uri": "battlenet://Pro", "dir": "C:\\Program Files (x86)\\Overwatch" }
]
```

---

## Keep your current Windows instead

On the USB stick's start menu, choose **Install Monet next to my Windows**.
Windows and your files stay. The installer then asks where to put Monet:
choose **Free up space** to shrink Windows, or use free space you made in
Windows' **Disk Management**.

This needs Windows to be fully shut down (Fast Startup off), and Windows
can't be shrunk if it's encrypted with BitLocker. If that's the case, use
**Install Monet and Windows** instead.

The first time Windows starts from Monet, click **Yes** once to finish.

## Already using Bazzite?

Download **Monet-0.3.1-Linux.tar.gz** and run `./monet-0.3.1-linux/install.sh`,
or switch the whole system: `sudo bootc switch ghcr.io/happyhamster135/monet:latest`.
