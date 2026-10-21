# Install Monet

About 45 minutes. You need a USB stick (16 GB or larger) and a Windows 11 PC.

Written for a laptop with an NVIDIA RTX 2080. It works the same way on a desktop
with an RTX 5080.

> **Monet 0.1 is a preview.** It hasn't been tested on real hardware yet.
> Back up anything important first.

---

## 1. Get Windows ready

1. **Back up** your files.
2. **Save your BitLocker recovery key.** Go to
   [aka.ms/myrecoverykey](https://aka.ms/myrecoverykey) and write it down.
   Windows may ask for it once after Linux is installed.
3. **Make room for Monet.** Right-click Start → **Disk Management** →
   right-click **C:** → **Shrink Volume**. Shrink by at least **150 GB**
   (153600 MB).
4. **Turn off Fast Startup.** Open **Control Panel** → **Power Options** →
   **Choose what the power buttons do** → **Change settings that are currently
   unavailable** → untick **Turn on fast startup**.

## 2. Install Bazzite

Monet 0.1 runs on top of [Bazzite](https://bazzite.gg), a gaming version of
Linux with the NVIDIA drivers built in.

1. On [bazzite.gg](https://bazzite.gg), pick **Laptop** (or Desktop) →
   **NVIDIA** → **RTX 16xx series and newer** → **KDE Plasma**. Download the ISO.
2. Write it to the USB stick with
   [Fedora Media Writer](https://fedoraproject.org/workstation/download) or
   [balenaEtcher](https://etcher.balena.io).
3. Restart with the USB stick plugged in and open the boot menu. The key
   depends on the brand: **F12** (Dell, Lenovo, Acer, Gigabyte), **F9** (HP),
   **Esc** or **F8** (ASUS), **F11** (MSI). Choose the USB stick.
4. In the installer, choose the **free space** for Bazzite.
   **Don't erase the Windows partitions.**
5. After the first restart, you'll see a blue screen called **MOK management**.
   This lets Bazzite start with Secure Boot on, which Windows anti-cheat needs:
   **Enroll MOK** → **Continue** → **Yes** → type the password
   **`universalblue`** → **Reboot**.

## 3. Install Monet

1. In Bazzite, open the latest
   [Monet release](https://github.com/HappyHamster135/Monet/releases)
   (sign in to GitHub first) and download **Monet-0.1.0-Linux.tar.gz**.
2. Open **Konsole** and run:

   ```sh
   cd ~/Downloads
   tar xzf Monet-0.1.0-Linux.tar.gz
   ./monet-0.1.0-linux/install.sh
   ```

3. Type your password when asked. The Monet wallpaper and a **Windows Games**
   button in the panel appear.

## 4. Set up Windows

1. Open the app menu and choose **Windows**, then **Restart**.
2. In Windows, download **Monet-0.1.0-Windows.zip** from the same release page
   and extract it.
3. Open the **Monet for Windows** folder and double-click **Install Monet**.
   Click **Yes** when Windows asks for permission.
4. Optional: right-click **GameProfile.ps1** → **Run with PowerShell** for
   faster, quieter gaming. It doesn't remove anything unless you ask it to.
5. Double-click **Back to Monet** on the desktop.

## 5. Play

Click **Windows Games** in the panel and press **Play**. Your PC restarts in
Windows and starts the game. When you quit, it comes back to Monet.

Windows games also show up in the app menu, so you can search for them.

---

## If something isn't right

Run this in Konsole. It checks everything and says what to fix:

```sh
monet doctor
```

**The PC starts Windows instead of Monet.** Run `monet make-default`.
Monet Bridge also fixes this automatically each time Windows starts.

**The clock is wrong in Windows.** Windows and Linux read the PC's clock
differently. Fix it once, in Windows, in an administrator terminal:

```powershell
reg add "HKLM\SYSTEM\CurrentControlSet\Control\TimeZoneInformation" /v RealTimeIsUniversal /t REG_QWORD /d 1 /f
```

**A Linux game runs slowly on the laptop.** It may be using the built-in
graphics instead of the RTX 2080. In Steam, right-click the game →
**Properties** → **Launch Options**:

```
__NV_PRIME_RENDER_OFFLOAD=1 __VK_LAYER_NV_optimus=NVIDIA_only __GLX_VENDOR_LIBRARY_NAME=nvidia %command%
```

**A game is missing from the list.** Monet finds Steam, Epic, and Riot games.
For others (Battle.net, EA, Ubisoft), add them in
`C:\ProgramData\Monet\custom-games.json` in Windows:

```json
[
  { "name": "Overwatch 2", "uri": "battlenet://Pro", "dir": "C:\\Program Files (x86)\\Overwatch" },
  { "name": "My Game", "exe": "D:\\Games\\My Game\\game.exe" }
]
```

**Don't open the Windows drive from Monet.** Between games, Windows is
hibernated, not shut down. Changing its files from Linux can damage them.

---

## Remove Monet

- In Windows: run **Uninstall Monet** from the Monet for Windows folder.
- In Monet: run `./monet-0.1.0-linux/uninstall.sh`.
