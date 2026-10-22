# Install Monet

One USB stick installs everything: Monet, and Windows for the games that need
it. No preparation in Windows, no BitLocker keys, no settings to change.

You need:

- A PC with an NVIDIA RTX 20-series or newer GPU
- A USB stick of 2 GB or more (it will be erased)
- Internet (Wi-Fi is fine)

**Everything on the PC is erased.** About 20 minutes to install Monet, then
Windows downloads in the background while you use it.

> **Monet 0.6 is a preview** and hasn't been tested on real hardware yet.

---

## 1. Make the USB stick

On a Windows PC (this one, or any other):

1. Download **Monet-0.8.0-Make-USB-Stick.exe** from the
   [Monet release](https://github.com/HappyHamster135/Monet/releases) and
   double-click it. Say **Yes** when Windows asks to let it make changes
   (it writes a whole USB stick).

   Windows may first say **"Windows protected your PC"**, because the program
   isn't signed: click **More info**, then **Run anyway**.
2. Plug in a USB stick of 2 GB or more, choose it, and click **Make USB
   stick**. Everything on the stick is erased.
3. It downloads Monet, writes the stick and checks it (about 10-20 minutes),
   then says it's ready.

The stick gets **Monet Setup**, Monet's own installer, when the release has
it (**Monet-0.8.0-Setup.iso**), and otherwise Fedora's installer dressed as
Monet (**Monet-0.8.0-Installer.iso**). Monet Setup is in a release only once
it has installed Monet in a test PC.

On Linux or a Mac, download **Monet-0.8.0-Setup.iso** (or, if the release
doesn't have it, **Monet-0.8.0-Installer.iso**) and write it with your disk
tool (GNOME Disks, KDE's ISO Image Writer, or balenaEtcher).

## 2. Install

1. Restart with the USB stick plugged in, and open the boot menu: **F12**
   (Dell, Lenovo, Acer, Gigabyte), **F9** (HP), **Esc** or **F8** (ASUS),
   **F11** (MSI). Choose the USB stick (it's called **Monet-0.8.0**).
2. Monet Setup opens over the harbor at dawn. Choose your language and
   keyboard, and click **Continue**.
3. Connect to Wi-Fi (with a cable, this step is skipped).
4. Enter your name and a password: your account in Monet, and in Windows.
5. Choose **Monet and Windows** (everything on the PC is erased; about two
   thirds of the disk for Monet, one third for Windows) or **Monet next to my
   Windows** (Windows and your files stay; it needs free space). Check the
   disk, then click **Erase & Install** (or **Install**).

Monet downloads itself while it installs (5.7 GB) and shows how much is down
and how long is left. If the connection drops, it picks up where it stopped.
If something can't go ahead, the page says why in a sentence.

6. When it says it's all set, click **Restart** and take out the USB stick.

<details>
<summary>With Fedora's installer (Monet-0.8.0-Installer.iso)</summary>

1. Open the boot menu and choose the USB stick, as above.
2. Monet's start menu opens (over the harbor at dawn, unless Secure Boot is
   on: then it's plain text). **Install Monet and Windows** is already
   selected. Press **Enter** (or wait ten seconds).
3. Choose your language.
4. Click **Network & Host Name** and connect to Wi-Fi.
5. Click **User Creation** and enter your name and a password.
6. Click **Begin Installation**. The disk is already set up for you: about
   two thirds for Monet, one third for Windows. Monet downloads itself while
   it installs; a Monet page shows how far it is.
7. Click **Reboot** and take out the USB stick.

</details>

## 3. First start

**Once**, a blue screen asks to trust the NVIDIA driver, which anti-cheat
games need:

**Enroll MOK** → **Continue** → **Yes** → type **`monetsetup`** → **Reboot**

Sign in to Monet. It greets you by name.

## 4. Windows gets ready (about 30 minutes, in the background)

Right after you sign in, Monet starts downloading Windows 11 from Microsoft
and shows its progress. Keep using your PC. When it's ready, Monet asks to
restart: Windows then installs itself (about 10 minutes, a few restarts, no
questions), sets up Monet Bridge and the Game Profile, and comes back to
Monet. Done.

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

## Keeping Monet up to date

Monet never updates by itself. When you want to, open **Settings → Updates**
and choose **Check for updates**. If there's something new, choose
**Install** (it updates Monet and your apps), then **Restart now**.

From a terminal, the same is:

```sh
monet update --check   # only look
monet update           # install, then restart
```

If a new version ever misbehaves, choose the previous one in the start menu
that appears while the PC starts, or run `sudo bootc rollback` and restart.

The first time you start a version with a new look, Monet freshens your
desktop (the painting, the colors, the glass) and keeps your panels. Your
files and apps aren't touched.

### If Play goes back to Monet

Monet writes down every trip to Windows in `/var/lib/monet/switch.log`, and
`monet doctor` lists the PC's Windows boot entries. If a trip comes back
without reaching Windows, Monet says why at the next sign-in and tries
another way the next time.

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

Download **Monet-0.8.0-Linux.tar.gz** and run `./monet-0.8.0-linux/install.sh`,
or switch the whole system: `sudo bootc switch ghcr.io/happyhamster135/monet:latest`.
