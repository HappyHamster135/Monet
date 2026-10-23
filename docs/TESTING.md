# Testing Monet on real hardware

Phase 0 of the plan: prove the switch works before building more. Fill in the
tables as you go and commit the results.

Test machines:

| Machine | GPU | Notes |
|---|---|---|
| Laptop | RTX 2080 (Turing) | Hybrid graphics: check games use the NVIDIA GPU |
| Desktop | RTX 5080 (Blackwell) | Needs NVIDIA open kernel modules (driver 570+) |

## 1. Setup

- [ ] Bazzite installed next to Windows 11 ([INSTALL.md](INSTALL.md))
- [ ] Secure Boot **on** in both systems (`monet doctor` in Monet; in Windows, `Confirm-SecureBootUEFI` in an admin PowerShell)
- [ ] `monet doctor` shows no ✗
- [ ] Monet Bridge installed; `monet-bridge status` (admin terminal) lists the Monet entry
- [ ] The right Monet for the graphics: `rpm-ostree status` (or `bootc status`) shows `monet` on the RTX PC and `monet-amd` on a PC with only Intel or AMD graphics (or an NVIDIA card older than the RTX 20 series)

### Making the USB stick

- [ ] Make-USB-Stick.exe lists the plugged-in USB stick (0.8.5 found none) and writes it

### 0.9's smaller things

- [ ] Settings → Updates names Monet's version ("Monet 0.9.0 is ready"), not "44.2026…"
- [ ] Settings' corner and edges drag it bigger and smaller; double-clicking "Settings" fills the screen; the size is kept
- [ ] Popovers, the tray's (Disks & Devices, Audio Volume), the menu and the bars show the painting's strokes, like the desktop widgets
- [ ] The clock's page goes back to its width after the notes close; a note written there shows in the Calendar widget within a second
- [ ] Light & Wallpaper → Through the year hangs the painting of the season
- [ ] A window dragged over the bar makes the island under it slide away; pointing at the bottom edge brings it back; Light & Wallpaper → Bar steps aside off keeps it in view
- [ ] Timer → Focus, then start: notifications stay quiet, the painting goes from dawn to night over the minutes, and both come back after
- [ ] Games & Controllers → Save the last 30 seconds: GPU Screen Recorder installs, KDE asks for the screen once, Windows+Alt+G saves an MP4 in Videos
- [ ] Search in the menu for "printers": Settings' Printers page is found

### Next to Windows, backups and the painting

- [ ] Monet Setup on a PC with a full Windows drive: "Monet next to my Windows" offers to make room (the note says from and to), Bring my files is ticked, and after installing Windows still starts (it checks its drive once)
- [ ] At the first sign-in the files from Windows are in Documents, Pictures and the rest, and a note says so
- [ ] Settings → Backups: after an hour, "An hour ago" opens your files in Files; right-click a file → Earlier versions → Put back puts a copy beside it
- [ ] A USB drive picked in Backups gets "Monet Backup/<you>" the next time it's plugged in
- [ ] The Hours changes light near your sunrise and sunset, not at fixed hours; on a rainy day the painting is softer
- [ ] Display shows HDR and Smoother games on a monitor that can do them, and they change the monitor
- [ ] Games & Controllers lists a game installed here whose anti-cheat needs Windows

### Safety and recovery (0.9.1)

- [ ] Monet Setup on a PC with a TPM 2.0: Encrypt this PC is ticked; after installing, the recovery key page shows eight groups of eight letters, and Continue waits for "I've kept my recovery key"
- [ ] The first start (after the blue screen) asks for no passphrase; afterwards `sudo systemd-cryptenroll /dev/disk/by-uuid/<uuid>` lists a tpm2 slot and a password slot (the recovery key), `/boot/monet-firstboot.key` is gone, and after the next restart `/proc/cmdline` has no `rd.luks.key`
- [ ] Turn Secure Boot off (or clear the TPM): the start asks for the passphrase; the recovery key opens it, and the start after that doesn't ask
- [ ] In a VM: install an update, restart, and within its first minute stop the sign-in screen (`sudo systemctl stop display-manager`): five minutes later the PC restarts into the Monet from before, Settings → Updates says "Monet went back to …", the next sign-in says so too, and `sudo systemctl start monet-update` skips that update
- [ ] An update that starts normally: `/var/lib/monet/trial.json` is gone a minute after the sign-in screen, and `grub2-editenv list` has no `boot_counter`
- [ ] Settings → Updates → Reset this PC asks for the password; after Restart now: Monet's look and welcome come back, Documents, games, apps, Wi-Fi and printers are still there, the settings from before are in `~/.local/share/monet/before-reset`, and a note says Monet is as it came

### Older PCs and laptops

- [ ] `/usr/libexec/monet-quick older-pc` says `yes` with 8 GB of memory or less (or a hard disk), `no` otherwise
- [ ] On an older PC: `~/.config/monet/glass-lite` is there, Steam opens about 45 s after the desktop, and `kreadconfig6 --file baloofilerc --group General --key "only basic indexing"` says `true`
- [ ] Sign-in: `systemctl --user list-timers` shows `monet-after-sign-in` for a minute only after something changed (the first sign-in after an update, or an app installed while signed out); signing out and in again with nothing new shows none
- [ ] A normal start: `systemctl status monet-ready-boot monet-keep-prepare` say "condition unmet", and Settings → About Monet → Last start shows where the start's time went
- [ ] On a laptop with an NVIDIA chip beside the built-in graphics: a game from the Store's Play row (Prism Launcher, RetroArch) runs on the NVIDIA chip (`nvidia-smi` lists it), while the desktop and Steam's window don't

## 2. Switching

Time with a stopwatch, from the click to the moment you can play.

| Test | Laptop | Desktop |
|---|---|---|
| Monet → Windows desktop | | |
| Play on Windows → game menu | | |
| Quit game → Monet desktop | | |
| Back to Monet shortcut → Monet desktop | | |

Targets: under 30 s into a game, under 20 s back to Monet.

Settings → About → **Last start** shows where the time went on the way back:
the PC's own start (firmware), Monet's (loader, kernel, system), and your
desktop (from signing in until it's there). Note them for both PCs:

| Last start | Laptop | Desktop |
|---|---|---|
| The PC | | |
| Monet | | |
| Your desktop | | |

### Ready when you come back

Turn it on in Settings → Play on Windows, then Play on Windows and come back.

- [ ] Coming back, Monet signs in by itself and the **lock screen** shows first, not the desktop
- [ ] After the password, the desktop is already there (compare the time with it off)
- [ ] The start after that asks for the password at the sign-in screen as usual
- [ ] Shut down from Windows instead of coming back, start the PC the next day: the sign-in screen asks as usual
- [ ] Turned off again: coming back from Windows shows the sign-in screen
- [ ] If the desktop ever shows before the lock screen, turn it off and note it in Logs below

## 3. Anti-cheat

For each game: Play on Windows, quit (the PC restarts into Monet by itself,
not off), then Play on Windows again.

| Game | Anti-cheat | First play | Second play | Notes |
|---|---|---|---|---|
| Valorant | Riot Vanguard | | | |
| League of Legends | Riot Vanguard | | | |
| Call of Duty | Ricochet | | | |
| Fortnite | EasyAntiCheat | | | |
| Counter-Strike 2 (FACEIT) | FACEIT AC | | | |
| Apex Legends | EasyAntiCheat | | | |

## 4. Things that can go wrong

- [ ] A Windows update restarts the PC: does it come back to Monet by default?
- [ ] BitLocker: does Windows ask for the recovery key after switching?
- [ ] Unplug the charger while switching (laptop): does everything still work?
- [ ] Start Windows from the firmware boot menu instead of Monet: does it behave normally?
- [ ] Uninstall a game in Windows, then press Play on it in Monet: is the message clear?
- [ ] Clock: is the time right in both systems after switching a few times?

## 5. Logs

- Monet: `journalctl -u monet-sync` and `monet doctor`
- Windows: `C:\ProgramData\Monet\bridge.log`

## Before real hardware: a virtual machine

On a Windows 11 Pro PC, Hyper-V runs Monet the way a real PC does: UEFI
with Secure Boot on (Microsoft's keys for Linux), so it starts through its
signed shim and shows the blue driver-key screen once. There's no graphics
card in it, so everything is drawn by the processor, and Monet starts
without glass there (blurring makes everything lag). To see the glass
anyway, turn on **Glass** in Settings → Light & Wallpaper: right, but slow.

1. Turn Hyper-V on, once, in PowerShell as administrator, then restart:
   `Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All`
2. Download the USB stick's image (Monet-X-Setup.iso, or Monet-X-Installer.iso)
   from the release, or a build's `setup-candidate` artifact.
3. In PowerShell as administrator, from the repository:
   `.\tools\hyperv-vm.ps1 -Iso D:\VMs\Monet-X-Setup.iso`
4. Hyper-V Manager: select Monet, **Connect**, **Start**. Install as on a PC
   ([INSTALL.md](INSTALL.md)). Where it says to take out the USB stick, use
   **Media → DVD Drive → Eject** in the VM's window. At the blue screen, the
   password is `monetsetup`.
5. Once Monet is installed, take a checkpoint (**Action → Checkpoint**), so a
   fresh Monet is a click away.

The screen size is set in Monet (Settings → Display) once it's installed.
