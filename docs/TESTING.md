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

## 2. Switching

Time with a stopwatch, from the click to the moment you can play.

| Test | Laptop | Desktop |
|---|---|---|
| Monet → Windows desktop, first time (cold boot) | | |
| Monet → Windows desktop, Windows hibernated | | |
| Play on Windows → game menu | | |
| Quit game → Monet desktop | | |
| Back to Monet shortcut → Monet desktop | | |

Targets: under 30 s into a game, under 20 s back to Monet.

## 3. Anti-cheat after hibernation

For each game: play once after a cold Windows boot, then go back to Monet,
then Play on Windows again (Windows resumes from hibernation).

| Game | Anti-cheat | Cold boot | After resume | Notes |
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
