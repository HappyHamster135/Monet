# Install Monet

One USB stick installs everything: Monet, and Windows for the games that need
it. Some PCs need a firmware setting enabled to trust Linux boot media; see below.

These instructions are for the **0.9.8-5 preview**. Use the USB maker or an
installer ISO from the same release. [Monet downloads](https://github.com/HappyHamster135/Monet/releases)

You need:

- An x86-64 PC with NVIDIA, AMD or Intel graphics. The installer picks the Monet for your
  PC's graphics by itself. With an NVIDIA card older than the RTX 20 series
  (or GTX 16), Monet draws with an open driver: fine for everyday things,
  while games run best in Windows.
- UEFI firmware: the USB stick only starts that way, so a PC from before
  about 2012 can't run Monet. Every PC that runs Windows 11 has it.
- 4 GB of memory at least, 8 GB to run many apps at once
- A disk of 70 GB or more
- A USB stick of 2 GB or more with 512-byte logical sectors (it will be erased)
- Internet (Wi-Fi is fine)

Setup installs onto the drive you select. **Erasing that drive deletes all of
its partitions and files; other drives are kept.** Installation time depends on
the connection and PC. On a large enough erased drive, space is also reserved
for Windows, which downloads after you sign in to Monet.

> **Monet is a preview.** Keep a copy of anything you can't lose before you install it.

---

## 1. Make the USB stick

The same USB maker and stick support Intel, AMD and NVIDIA PCs. Graphics are
detected on the PC you boot from the stick; the PC making it does not choose them.
ARM PCs, Apple Silicon Macs and BIOS-only machines are not supported.
512e drives meet the sector requirement. They report 512-byte logical sectors
and use 4 KiB physical sectors.

On a Windows PC (this one, or any other):

1. Download **Monet-0.9.8-5-Make-USB-Stick.exe** from the release page and
   double-click it. Say **Yes** when Windows asks to let it make changes
   (it writes a whole USB stick).

   Windows may first say **"Windows protected your PC"**, because the program
   isn't signed: click **More info**, then **Run anyway**.
2. Plug in a USB stick of 2 GB or more, choose it, and click **Make USB
   stick**. Everything on the stick is erased.
3. It downloads Monet, writes the stick and checks it (about 10-20 minutes),
   then says it's ready.

The USB maker prefers **Monet-0.9.8-5-Setup.iso**. It checks the downloaded
installer against the release checksum before writing the stick. If Monet
Setup is unavailable, it uses **Monet-0.9.8-5-Installer.iso**, the Fedora fallback.

On Linux or a Mac, download **Monet-0.9.8-5-Setup.iso** and write it with your
disk tool (GNOME Disks, KDE's ISO Image Writer, or balenaEtcher).

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
   **F11** (MSI). Choose the USB stick. Its volume label is **Monet-0.9.8-5**.
2. Monet Setup opens over the harbor at dawn. Choose your language,
   keyboard and time zone (a region, then a city: Setup guesses it, and once
   online, finds where the PC is), and click **Continue**.
3. Connect to Wi-Fi (with a cable, this step is skipped).
4. Enter your name and type your Monet password twice. Leave both password
   fields empty and Monet signs you in by itself. Anyone who uses the PC
   can then open your account. On a passwordless administrator account,
   firewall changes can go through without a password dialog.
   Settings → Accounts gives the account a password later.
5. Choose your apps, then choose an **Installation drive** by its model,
   capacity and device path. Review its existing partitions and the list of
   other drives that will be kept. No drive is selected automatically.
   Choose **Keep existing data and add Monet** to use free space (or check
   whether Windows can safely shrink), or **Erase this drive and install
   Monet** to delete everything on that drive. Keeping data currently requires
   an existing EFI system partition on the same drive; this is not a manual
   partition editor. **Bring my files** is optional and scans Windows only
   when requested. Review the summary, tick its confirmation, and install.
   On a PC with TPM 2.0, **Encrypt Monet** is selected by default. Keep the
   recovery key shown at completion; it also unlocks the disk if the TPM cannot.

Resume needs the recovery information saved by the Setup stick that started
the installation.

Setup downloads the system, then unpacks and writes it. A finished download is
not a finished installation: leave the PC and USB connected until **All set**.
Progress includes elapsed time, available memory and the highest temperature
reported by available sensors. **Gentler installation** limits the installation
worker and its children to at most two logical CPUs with lower priority. It can
take longer and is not a fix for a thermal, kernel, firmware or graphics fault.

If installation is interrupted after disk preparation, boot the updated USB
again. If the download completed and no network is available, choose **Continue
offline** on the connection page. Enter your account choices, select the same drive and choose **Resume
interrupted installation**. Setup verifies the drive, partition identities and
saved download before reusing them. It keeps the existing partitions. The local
installer update also checks the downloaded image against the exact digest
recorded for that graphics variant on the Setup stick. Account and Wi-Fi
passwords are not saved in the recovery record. Offline mode only resumes an
existing installation. A corrupted or missing download asks you to reconnect.
Setup refuses to resume if the drive identity, device numbering or layout changed.

An unfinished system is retained as a `previous-install-*` subvolume at the
Monet filesystem's top level when rebuilding it. Those files are not automatically
merged into the new account. Repeated late retries can consume space; inspect
and recover anything needed before removing old subvolumes. Cleanup is never
automatic. When retrying a late failure, Setup also preserves the former boot
files in a `saved-boot-*`
folder inside a retained subvolume before rebuilding the boot entries. The
installation receipt and other systems' EFI files stay in place.

Open Settings → Storage → Unfinished installations to review saved systems. After
successfully booting Monet, use Find saved installations, then Review files and
cleanup. Save your files to an archive on a folder/drive you choose and check it
before confirming permanent removal. Only the matching account's home is
exported; removal also removes other accounts' files in that retained system.
The running OS and its rollback are protected. This tool needs a working Monet
desktop and works on retained installations on the current disk.

For an encrypted installation, a temporary bootstrap key is retained on the
unencrypted boot partition until Setup finishes, alongside the existing first-boot
key mechanism. The recovery copy is removed on success; the installed first-boot
service retires its LUKS slot after verified TPM enrollment. Until that succeeds,
disk encryption does not protect against someone with physical access to this key.

6. Encrypted, Setup shows your **recovery key** once: eight groups of eight
   letters. Take a photo of it or write it down, and keep it somewhere other
   than this PC. Monet asks for it only if it can't unlock the disk by itself
   (after a big firmware update, or with the disk in another PC). Type it
   with the dashes.
7. When it says it's all set, click **Restart** and take out the USB stick.

<details>
<summary>With Fedora's fallback installer</summary>

The fallback offers erase only when it can identify the boot media and one
eligible internal drive. If either check fails, use Monet Setup to choose
the drive. The fallback waits at its summary before writing to the drive.

1. Open the boot menu and choose the USB stick, as above.
2. Monet's start menu opens (over the harbor at dawn, unless Secure Boot is
   on: then it's plain text). **Install Monet and Windows** is already
   selected. Press **Enter** (or wait ten seconds).
3. Choose your language.
4. Click **Network & Host Name** and connect to Wi-Fi.
5. Click **User Creation**, enter your name and a password, and leave
   **Add administrative privileges to this user account** selected.
6. Open **Installation Destination** and check the selected drive and partition
   changes before clicking **Begin Installation**. If the summary says
   **Kickstart insufficient**, select only the drive you intend to use and
   confirm its layout there. Monet shows download progress while it installs.
7. Click **Reboot System**. Remove the USB stick once the PC starts restarting.

</details>

## 3. First start

When Secure Boot is on, a blue screen asks once to trust Monet. Its kernel
and NVIDIA driver are signed with Universal Blue's key. Use the arrow keys
and Enter:

**Enroll MOK** → **Continue** → **Yes** → type **`monetsetup`** → **Reboot**

Monet Setup's last page shows these steps in pictures. The Fedora fallback
shows the same instructions before **Reboot System**.

It opens on **Continue boot**: don't choose that. It skips this, and then
Secure Boot won't let Monet start. If it happens anyway, the PC says
"bad shim signature" for ten seconds, then Monet asks the firmware again,
says so, and restarts: the blue screen is back. (Starting from the USB stick
works too: Monet Setup notices and offers **Ask again and restart**.)

Sign in to Monet. It greets you by name.

## 4. Windows gets ready (about 30 minutes, in the background)

If Setup reserved space for a new Windows install, Monet starts downloading
Windows 11 from Microsoft after you sign in and shows its progress. Keep using
your PC. When it's ready, Monet asks to restart. Windows installs itself, sets
up Monet Bridge and the Game Profile, then comes back to Monet.

On a new dual-boot install, Setup leaves room for a Windows partition of
100 to 128 GiB plus 8 GiB for setup files. This includes room for Windows
updates. Check the sizes of any games you plan to install on that partition.

---

## Good to know

- **A new games-only Windows** has a separate local administrator account
  with your name and no password. Its first automatic sign-in finishes setup,
  then setup clears its sign-in settings. Windows can still open the desktop
  automatically when the account has no password. Automatic device encryption
  is turned off during installation. Windows Security and Windows Update can be
  managed in Windows. If the PC came with Windows, Windows activates by itself.
  Otherwise it runs unactivated, with a small watermark.
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

**"Test this media" fails.** Windows can move GPT metadata after writing the
stick, which can cause Fedora's embedded ISO checksum to fail. Verify the
downloaded ISO against `SHA256SUMS`. If it matches, use the first menu entry.

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
then choose **Windows** again. Monet opens the ISO read-only and checks the
setup and install images before creating or formatting Windows partitions.

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

### Set up signed system updates

Monet 0.9.8 and later configure signature verification when installed from
Monet Setup or the Fedora fallback. Add the release key before switching
from Monet 0.9.7 or Bazzite.

Download the 0.9.8-5 source archive from the Monet GitHub release and extract it.
From its top-level directory, run these commands:

```sh
sudo python3 image/install-update-trust.py image/monet-update.pub
sudo bootc status
```

On Monet 0.9.7, use the same repository shown in the current image. On
Bazzite, use `monet` for an NVIDIA RTX 20-series or later card or a GTX 16-series
card, and `monet-amd` for AMD, Intel or older NVIDIA graphics. For `monet`, run:

```sh
sudo bootc switch --enforce-container-sigpolicy ghcr.io/happyhamster135/monet:latest
```

For `monet-amd`, substitute `ghcr.io/happyhamster135/monet-amd:latest`.
Restart after the switch succeeds. The previous deployment remains available
in the boot menu.

### Going back after an update

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

**Settings → Recovery** links to Backups
and Updates and lists recent changes Monet recorded to this account's desktop
settings and application shortcuts. Choose **Review changes**, then **Undo these
changes** to restore matching entries. Later personal edits are kept; failures
and unreadable history remain visible. Save your work and sign out when ready
if restored settings have not appeared in running apps. Recovery never signs
you out automatically. This does not restore documents, reinstall Monet or undo
arbitrary unrecorded changes. A recent journal must exist, and this page requires
a working desktop.

To update an existing Windows Bridge to 0.9.8-5, extract
**Monet-0.9.8-5-Windows.zip** in Windows and double-click **Install Monet**.
Approve the administrator prompt. Older Bridge versions skip release numbers
with a suffix like `0.9.8-5`, so they need this one-time install.

Starting with 0.9.8-5, Bridge checks for updates after you sign in to Windows.
**Back to Monet** applies an update that has already downloaded and passed
its checksum check. If no verified package is ready, it requests the restart
without waiting for a download.

### If Play goes back to Monet

Monet writes down every trip to Windows in `/var/lib/monet/switch.log`, and
`monet doctor` lists the PC's Windows boot entries. If a trip comes back
without reaching Windows, Monet says why at the next sign-in and tries
another way the next time.

---

## Keep your current Windows and your files instead

No full reset needed. In the updated Monet Setup, select the Windows drive and
choose **Keep existing data and add Monet** (older Setup calls this **Monet next
to my Windows**):
Windows and your files stay, and Monet makes room for itself by shrinking
Windows' drive (it keeps what it uses and half its free space, at least
30 GB). Leave **Bring my files** ticked and your Desktop, Documents,
Pictures, Music, Videos and Downloads are copied into Monet too, into the
same folders (in your language). They stay in Windows as well.

With Fedora's installer instead, choose **Install Monet next to my Windows**
on the stick's start menu, then **Free up space** to shrink Windows, or use
free space you made in Windows' **Disk Management**. It doesn't bring your
files: open them from Windows' drive in Files.

Either way, fully shut down Windows. Hold **Shift** while choosing **Shut down**
to skip Fast Startup. If BitLocker is on, use existing unallocated space or a
separate drive to keep the encrypted partition intact. To let Setup shrink it,
first turn BitLocker off from Windows. **Install Monet and Windows** erases the
target drive. Windows checks its drive the next time it starts after a shrink.

The first time Windows starts from Monet, click **Yes** once to finish.

## Already using Bazzite?

Extract **Monet-0.9.8-5-Linux.tar.gz** to a folder and run `./install.sh` from
that folder. To switch the whole system to the Monet image, use the
[signed update steps](#set-up-signed-system-updates) to install the trust key
and choose the channel for your graphics hardware.
