# Install Monet

One USB stick installs everything: Monet, and Windows for the games that need
it. Some PCs need a firmware setting enabled to trust Linux boot media; see below.

You need:

- An x86-64 PC with NVIDIA, AMD or Intel graphics. The installer picks the Monet for your
  PC's graphics by itself. With an NVIDIA card older than the RTX 20 series
  (or GTX 16), Monet draws with an open driver: fine for everyday things,
  while games run best in Windows.
- UEFI firmware: the USB stick only starts that way, so a PC from before
  about 2012 can't run Monet. Every PC that runs Windows 11 has it.
- 4 GB of memory at least, 8 GB to run many apps at once
- A disk of 70 GB or more
- A USB stick of 2 GB or more (it will be erased)
- Internet (Wi-Fi is fine)

**Everything on the PC is erased.** About 20 minutes to install Monet, then
Windows downloads in the background while you use it.

> **Monet is a preview.** Keep a copy of anything you can't lose before you install it.

---

## 1. Make the USB stick

The same USB maker and stick support Intel, AMD and NVIDIA PCs. Graphics are
detected on the PC you boot from the stick; the PC making it does not choose them.
ARM PCs, Apple Silicon Macs and BIOS-only machines are not supported.

On a Windows PC (this one, or any other):

1. Download **Monet-0.9.4-Make-USB-Stick.exe** from the
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
it (**Monet-0.9.4-Setup.iso**), and otherwise Fedora's installer dressed as
Monet (**Monet-0.9.4-Installer.iso**). Monet Setup is in a release only once
it has installed Monet in a test PC.

On Linux or a Mac, download **Monet-0.9.4-Setup.iso** (or, if the release
doesn't have it, **Monet-0.9.4-Installer.iso**) and write it with your disk
tool (GNOME Disks, KDE's ISO Image Writer, or balenaEtcher).

## 2. Install

Monet Setup uses signed boot files and can start with Secure Boot on when the
firmware trusts Microsoft's third-party UEFI CA. Firmware set to trust only
Windows can reject the USB before any installer code runs; Setup cannot change
that firmware setting itself.

If the USB shows a **Secure Boot error before Monet Setup opens**, check the
firmware's Linux boot trust settings. On applicable ThinkPads, Lenovo documents
**Security → Secure Boot → Allow Microsoft 3rd Party UEFI CA**; enabling this
allows signed Linux bootloaders while Secure Boot stays on. See
[Lenovo's instructions](https://download.lenovo.com/pccbbs/mobiles_pdf/Enable_Secure_Boot_for_Linux_Secured-core_PCs.pdf).
The exact error matters: this setting does not fix every signature or revocation
failure. This happens before the installed system's MOK enrollment described in
step 3. If the PC already has an encrypted system, keep its recovery key available
before changing firmware security settings.

1. Restart with the USB stick plugged in, and open the boot menu: **F12**
   (Dell, Lenovo, Acer, Gigabyte), **F9** (HP), **Esc** or **F8** (ASUS),
   **F11** (MSI). Choose the USB stick (it's called **Monet-0.9.4**).
2. Monet Setup opens over the harbor at dawn. Choose your language,
   keyboard and time zone (a region, then a city: Setup guesses it, and once
   online, finds where the PC is), and click **Continue**.
3. Connect to Wi-Fi (with a cable, this step is skipped).
4. Enter your name and a password, twice: your account in Monet, and in
   Windows. Any password will do. Or leave both empty: then Monet signs you
   in by itself and the screen doesn't lock, but anyone who uses the PC can
   open your account. Settings → Accounts gives it a password later.
5. Choose **Monet and Windows** (everything on the PC is erased; about two
   thirds of the disk for Monet, one third for Windows) or **Monet next to my
   Windows** (Windows and your files stay; it needs free space). Check the
   disk, then click **Erase & Install** (or **Install**).
   On a PC with a security chip (TPM 2.0, which every Windows 11 PC has),
   **Encrypt this PC** is ticked: only this PC can read Monet's disk, and
   Monet unlocks it by itself when it starts, as Windows does with BitLocker.

Monet downloads itself while it installs (5.7 GB) and shows how much is down
and how long is left. If the connection drops, it picks up where it stopped.
If something can't go ahead, the page says why in a sentence.

6. Encrypted, Setup shows your **recovery key** once: eight groups of eight
   letters. Take a photo of it or write it down, and keep it somewhere other
   than this PC. Monet asks for it only if it can't unlock the disk by itself
   (after a big firmware update, or with the disk in another PC). Type it
   with the dashes.
7. When it says it's all set, click **Restart** and take out the USB stick.

<details>
<summary>With Fedora's installer (Monet-0.9.4-Installer.iso)</summary>

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

**Once**, a blue screen asks to trust Monet (its kernel and the NVIDIA
driver are signed with Universal Blue's key, which Secure Boot doesn't know
yet). With the arrow keys and Enter:

**Enroll MOK** → **Continue** → **Yes** → type **`monetsetup`** → **Reboot**

Monet Setup's last page shows these steps in pictures: take a photo of them.

It opens on **Continue boot**: don't choose that. It skips this, and then
Secure Boot won't let Monet start. If it happens anyway, the PC says
"bad shim signature" for ten seconds, then Monet asks the firmware again,
says so, and restarts: the blue screen is back. (Starting from the USB stick
works too: Monet Setup notices and offers **Ask again and restart**.)

With Fedora's installer instead:

1. Turn Secure Boot off in the PC's firmware settings, and start Monet.
2. In Terminal, run `sudo mokutil --import /etc/pki/akmods/certs/akmods-ublue.der`
   and type `monetsetup` twice. Then run `sudo mokutil --timeout -1`, so
   the blue screen waits for you.
3. Restart, turn Secure Boot back on, and this time choose **Enroll MOK** on
   the blue screen.

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
- **Play a game:** click **Games** in the panel (the sun as a play button).
  Every game is there, Steam's, Heroic's and Lutris' in Monet and the ones in
  Windows, each saying where it plays. **Play** on a Windows game restarts in
  Windows; while Windows starts the game you see Monet's painting, not Windows.
  When you quit, the PC comes back to Monet.
- **Install a game once:** in Steam, choose **Windows games** when you install
  a game. It goes on Windows' drive, in its Games folder, and Steam in Monet
  and Steam in Windows both play it from there. A game that needs Windows
  downloads while you keep using Monet, and Monet keeps it up to date. Settings
  → Games & Controllers → **Add to Steam** sets it up, if Steam hasn't got it yet.
  In Heroic, choose the same folder for Epic and GOG games: Epic's launcher in
  Windows takes them over, and GOG's games start by themselves.
- **Your own photo, painted:** Settings → Light & Wallpaper → **Your photo**
  paints a photo of yours in Monet's hand, in the same four lights as The
  Hours, and puts it on the wall.
- **A guest:** Settings → Accounts → **Guest** lets someone use the PC without
  a password and without seeing your files, games or Windows; everything they
  do is gone when they sign out.
- **Your apps come back:** the apps you had open before a trip to Windows
  open again when you're back in Monet.
- **Screenshots and clips from Windows** (Windows key + Print Screen, Game
  Bar's clips) move into Monet's Pictures › Screenshots and Videos when you
  come back.
- **Sign in to your game launchers once:** Settings → Play on Windows →
  **Game launchers** → **Sign in…**. Windows opens with your launchers listed;
  sign in to each with *Remember me* ticked, then choose **Back to Monet**.
- **Keep Windows games up to date:** Settings → Play on Windows → **Update
  Windows games** → **Update & switch off**, before you go to bed, say. Windows
  updates itself and your games, then switches the PC off (within an hour and a
  half), so the next Play starts the game, not a download.
- **Windows' language and keyboard** match the ones you picked for Monet.
- **Wi-Fi in both:** a network you join in Monet works in Windows on your
  next trip, and one you join in Windows works in Monet when you're back.
- **A Bluetooth controller or headset:** pair it in Monet, then once in
  Windows. Monet picks up Windows' pairing by itself at the next start, and
  from then on it works in both.

## If something isn't right

Open **Terminal** and run `monet doctor`. It says what's wrong and what to do.

To ask for help, choose **Settings → About Monet → Save a report**. It puts
one file in Documents with what helps find the problem (Monet's records, the
PC's parts, and the errors of this start and the one before), and stays on the
PC until you send it to someone.

**"The Monet package on GitHub isn't public".** The installer can't download
Monet. Make the package public (GitHub → your profile → **Packages** →
**monet** → **Package settings** → **Change visibility** → **Public**), then
start the installer again.

**"Test this media" fails.** Use the first menu entry instead; the test is
optional.

**The start asks for a passphrase.** Monet's disk is encrypted, and this time
the PC's security chip couldn't vouch for the start: after a firmware update,
with Secure Boot turned off or on, or after the chip was cleared. Type your
recovery key, dashes and all. Monet then lets the chip learn the PC again,
so the next start doesn't ask.

**Something's wrong, and going back to the Monet from before didn't help.**
**Settings → Updates → Reset this PC** puts Monet back as it comes at the
next restart: its settings, the desktop's look and the changes made to the
system, for everyone. Files, games and apps stay, and so do accounts, Wi-Fi
and printers. It asks for an administrator's password first. Each person's
settings from before are kept in `~/.local/share/monet/before-reset`, and
the system's in `/var/lib/monet/before-reset`.

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

Monet keeps itself up to date. Once a day, in the background, it updates
your apps and gets the newest Monet ready; the new Monet starts the next
time you restart, never while you work. To update only when you ask, turn
off **Settings → Updates → Update automatically**.

To update right away, open **Settings → Updates** and choose **Check for
updates**. If there's something new, choose **Install** (it updates Monet
and your apps), then **Restart now**.

From a terminal, the same is:

```sh
monet update --check      # only look
monet update              # install, then restart
monet auto-updates off    # only when you ask (on turns it back)
```

A new Monet that doesn't start properly goes back by itself: if it hasn't
brought up the sign-in screen within five minutes, the PC restarts into the
Monet from before, and Settings → Updates says so. The daily update then
waits for the next one. If a new version misbehaves in some other way,
choose **Settings → Updates → Go back**, choose the previous one in the start
menu that appears while the PC starts, or run `sudo bootc rollback` and
restart.

The first time you start a version with a new look, Monet freshens your
desktop (the painting, the colors, the glass) and keeps your panels. Your
files and apps aren't touched.

Monet Bridge, Monet's part in Windows, updates itself on the way back to
Monet, at most once a day: when a newer Monet is out, it installs that
Monet's Bridge, then restarts into Monet as usual. A Bridge from before 0.9.2
needs it once by hand: in Windows, open the release's
**Monet-X-Windows.zip** and double-click **Install Monet**.

### If Play goes back to Monet

Monet writes down every trip to Windows in `/var/lib/monet/switch.log`, and
`monet doctor` lists the PC's Windows boot entries. If a trip comes back
without reaching Windows, Monet says why at the next sign-in and tries
another way the next time.

---

## Keep your current Windows and your files instead

No full reset needed. In Monet Setup, choose **Monet next to my Windows**:
Windows and your files stay, and Monet makes room for itself by shrinking
Windows' drive (it keeps what it uses and half its free space, at least
30 GB). Leave **Bring my files** ticked and your Desktop, Documents,
Pictures, Music, Videos and Downloads are copied into Monet too, into the
same folders (in your language). They stay in Windows as well.

With Fedora's installer instead, choose **Install Monet next to my Windows**
on the stick's start menu, then **Free up space** to shrink Windows, or use
free space you made in Windows' **Disk Management**. It doesn't bring your
files: open them from Windows' drive in Files.

Either way Windows needs to be fully shut down: hold **Shift** while you
choose **Shut down** in Windows (that skips Fast Startup). Windows can't be
shrunk if it's encrypted with BitLocker; turn BitLocker off in Windows
first, or use **Install Monet and Windows** instead. Windows checks its
drive once the next time it starts.

The first time Windows starts from Monet, click **Yes** once to finish.

## Already using Bazzite?

Download **Monet-0.9.4-Linux.tar.gz** and run `./monet-0.9.4-linux/install.sh`,
or switch the whole system: `sudo bootc switch ghcr.io/happyhamster135/monet:latest`
(`monet-amd:latest` with AMD or Intel graphics, or an NVIDIA card older than the RTX 20 series).
