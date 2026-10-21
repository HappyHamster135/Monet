# Install Monet

One download, one USB stick, about 30 minutes. Monet installs next to
Windows, and Windows stays as it is.

You need:

- A Windows 11 PC with an NVIDIA RTX 20-series or newer GPU
- A USB stick of 2 GB or more (it will be erased)
- Internet (Wi-Fi is fine). Monet downloads while it installs.

> **Monet 0.2 is a preview.** It hasn't been tested on real hardware yet.
> Back up anything important first.

---

## 1. Get Windows ready (5 minutes)

1. **Back up** your files.
2. **Save your BitLocker recovery key.** Go to
   [aka.ms/myrecoverykey](https://aka.ms/myrecoverykey) and write it down.
   Windows may ask for it once.
3. **Make room for Monet.** Right-click Start → **Disk Management** →
   right-click **C:** → **Shrink Volume** → shrink by at least **150 GB**
   (153600 MB).
4. **Turn off Fast Startup.** Control Panel → **Power Options** → **Choose
   what the power buttons do** → **Change settings that are currently
   unavailable** → untick **Turn on fast startup**.

## 2. Make the USB stick (5 minutes)

1. Download **Monet-0.2.0-Installer.iso** from the
   [Monet release](https://github.com/HappyHamster135/Monet/releases).
2. Download and open [Fedora Media Writer](https://fedoraproject.org/workstation/download).
   Choose **Select .iso file**, pick the Monet installer, choose your USB
   stick, and click **Write**.

## 3. Install Monet (20 minutes)

1. Restart with the USB stick plugged in and open the boot menu. The key
   depends on the brand: **F12** (Dell, Lenovo, Acer, Gigabyte), **F9** (HP),
   **Esc** or **F8** (ASUS), **F11** (MSI). Choose the USB stick.
2. Choose **Install** and your language.
3. **Network:** on a laptop, open **Network & Host Name** and connect to
   Wi-Fi.
4. **Installation Destination:** choose your disk and keep **Automatic**.
   Monet uses the free space from step 1. **Windows isn't touched.**
5. **User Creation:** your name and password.
6. Click **Begin Installation**, then **Reboot** when it's done.

## 4. First start (2 minutes)

1. A blue screen appears once, called **MOK management**. It lets the NVIDIA
   driver run with Secure Boot on, which anti-cheat needs:
   **Enroll MOK** → **Continue** → **Yes** → type **`monetsetup`** → **Reboot**.
2. Monet starts. Sign in.

## 5. Connect Windows (1 click)

1. Open the app menu and choose **Windows**, then **Restart**.
2. When Windows has signed in, click **Yes** once, then wait a few seconds.
3. Your PC goes back to Monet by itself, and your Windows games appear in the
   **Windows Games** button in the panel.

That's it. Press **Play** on any Windows game to start it. When you quit,
your PC comes back to Monet.

---

## If something isn't right

Open **Konsole** and run:

```sh
monet doctor
```

It checks everything and says what to fix.

**Windows is encrypted with BitLocker.** Monet can't set up an encrypted
Windows by itself. In Windows, download **Monet-0.2.0-Windows.zip** from the
release page, extract it, and double-click **Install Monet**.

**"Windows is asleep".** Open Windows from Monet, choose **Restart** in
Windows, and Monet finishes the setup the next time it starts.

**The PC starts Windows instead of Monet.** Run `monet make-default`. Monet
Bridge also fixes this automatically each time Windows starts.

**The clock is wrong in Windows.** Run this once in Windows, in an
administrator terminal:

```powershell
reg add "HKLM\SYSTEM\CurrentControlSet\Control\TimeZoneInformation" /v RealTimeIsUniversal /t REG_QWORD /d 1 /f
```

**A Linux game runs slowly on a laptop.** It may be using the built-in
graphics. In Steam, right-click the game → **Properties** → **Launch
Options**:

```
__NV_PRIME_RENDER_OFFLOAD=1 __VK_LAYER_NV_optimus=NVIDIA_only __GLX_VENDOR_LIBRARY_NAME=nvidia %command%
```

**A game is missing.** Monet finds Steam, Epic, and Riot games. Add others
(Battle.net, EA, Ubisoft) in `C:\ProgramData\Monet\custom-games.json`:

```json
[
  { "name": "Overwatch 2", "uri": "battlenet://Pro", "dir": "C:\\Program Files (x86)\\Overwatch" },
  { "name": "My Game", "exe": "D:\\Games\\My Game\\game.exe" }
]
```

**Don't open the Windows drive from Monet.** Between games, Windows is
hibernated. Changing its files from Linux can damage them.

---

## Already using Bazzite?

You don't need the USB stick. Download **Monet-0.2.0-Linux.tar.gz** and run:

```sh
tar xzf Monet-0.2.0-Linux.tar.gz
./monet-0.2.0-linux/install.sh
```

Or switch the whole system to Monet OS:

```sh
sudo bootc switch ghcr.io/happyhamster135/monet:latest
```

## Remove Monet

- In Windows: **Settings** → **Apps** → **Installed apps** → **Monet Bridge**
  → **Uninstall**.
- In Monet: run `./monet-0.2.0-linux/uninstall.sh`, or remove the Monet
  partitions from Windows' Disk Management.
