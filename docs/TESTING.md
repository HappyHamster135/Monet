# Testing Monet on real hardware

Phase 0 of the plan: prove the switch works before building more. Fill in the
tables as you go and commit the results.

Much of it can be tried first in the test VM, by an AI or by hand: docs/TESTBENCH.md.

2026-10-29 integration work is in progress under `ai-before-full-image-1029`. The complete
image build exposed a missing notification-stage `kf6-kitemmodels-devel` dependency; after
adding it, the notification stage compiled and sealed successfully. Full-image installation,
boot, upgrade and rollback have not passed yet. Build inputs and fixes are recorded in
`target/full-image/source-upload.json` and `source-patches.json`.
The second attempt reached the editor runtime guard, which refused development packages
that upgraded util-linux libraries absent from the final runtime. Updating that library family
before native runtime capture fixes the mismatch without weakening the compatibility guards.
The complete build now passes: unpublished image `localhost/monet-vm:1029`, ID
`91639aafadcdacc4e5cf4dcdafb4e139c35f2bc39b9867463eea06e1ee32e3e8`.
The assembled CLI starts and the restoration helpers/native binaries are present. Bootc
container lint passes 12 checks, skips one, and warns about package-manager logs and files
under `/var`. These container checks do not establish that the image boots or upgrades safely.

The PDF capture prototype separately passed five Python checks and one native three-window
scenario using real Okular 26.08.1 PDF parts in a matching nested Wayland compositor. It
checked reordered tabs, active tabs, independent pages for the same file, empty windows,
Save As paths with original files preserved, modified-state reporting, unchanged window
geometry/selection, distinct surface identities, refusal without the identity plugin, and
capture of the last survivor after the original D-Bus window disappears. Source hashes,
native proof and logs are in `target/pdf-recovery/`. Only generated documents were used.
The protected-departure follow-up passes eight focused checks and a second native fixture.
It uses actual annotations, native Save/Discard/Cancel prompts, and independent PDF reads to
verify saved content, final Save As paths, the active tab and an untouched unsaved survivor.
A late Save after switch cancellation/controller loss cannot close the window; failed receipt
writes also veto closing. The capture regression passes with the departure patch installed.
Evidence is in `target/pdf-recovery/departure-evidence.json`. Automatic switching integration,
verified reopen/retry and image packaging remain open.
The later private-session fixture runs the actual patched Okular CLI, preserving duplicate
tabs at different pages, selection and independent windows despite conflicting normal tab
preferences. Empty windows, Unicode/backslash paths, malformed state, missing-file preflight
and launch identity pass. Both native regressions and 73 focused Python checks pass, including
controller capture/final receipts and new-window watch protection. Evidence:
`target/pdf-recovery/restore-evidence.json`. PDF return/retry integration remains unfinished.
The original Notes checksum remains unchanged. Build containers are retained for the next
step, and the checkpoint is not restored while the image build is active.

The PDF late-tab retry follow-up passes 74 focused checks, the native capture/departure/retry
fixtures and the actual CLI/private-session D-Bus scenario. It preserves newer modified
parts, pages, selection and geometry; verifies duplicate-path tabs, stale-state refusal,
late files, repeated requests and manually closed tabs/windows; and distinguishes unavailable
identity support from a closed window. The CLI fixture repeats the same durable request if
a reply is delayed or missing. Final tested source hashes and proof are recorded in
`target/pdf-recovery/retry-evidence.json`; Notes retain their original checksum. Earlier
fixture method capitalization and ambiguous startup identification failures were corrected,
and the whole native batch rerun. Return-controller integration and image packaging remain
unverified; no automatic PDF switching or hardware return is claimed.

The return-controller follow-up passes 124 focused VM checks and a native three-window
scenario. It verifies durable launch ownership, competing launch refusal, duplicate-path
pages, missing-file counts, exact placement and an untouched cancelled-switch survivor.
When the missing PDF returns, automatic recovery leaves newer live work alone; explicit
Retry appends once. The fixture drops that successful reply, reloads the controller and
verifies that the recorded attempt produces no duplicate. Original PDFs, ordinary viewer
preferences and Notes stay unchanged. Evidence and tested source hashes are in
`target/pdf-recovery/return-evidence.json`. Ambiguous disappeared launches require explicit
Retry. Production PDF bundle and installed-image checks remain open.

The production PDF bundle later built and installed into a matching runtime in the VM.
The first attempt rejected a build-only Brotli upgrade; updating the shared runtime before
capture fixed that mismatch. The final install preserves exact hashes of the document part,
core and PDF generator, validates corresponding source and resolves all linked symbols.
The older runtime is rejected. Evidence: `target/pdf-recovery/bundle-evidence.json`.
Native tests of this exact packaged binary and a complete image containing it remain open.

The integration2 replacement passed its real boot trial and installed migration, including
a no-op repeat. Existing preferences, pins, Notes, a saved document and desktop shortcut
survive; all 32 title-button assets match the assembled image. Installed adapters restored
two shared-process editor windows and two Files windows with tabs/splits and placement
within one pixel, without duplicates on repeat. Disk stalls produced metadata misses and
snapshot timeouts in earlier attempts; the same retained windows were inspected afterward,
not relaunched. Startup still reported Plasma initialization/splash timeouts and a base
automount failure. Repeated sign-in, everyday entry points and controlled rollback remain.
Evidence is under `target/full-image/integration2/`.

The follow-up distinguishes failed compositor inspection from an empty desktop. All 244
focused checks pass. A live editor and isolated session bus verify that unavailable inspection
retains the checkpoint without launch; Retry on the real bus reuses the same window with
document state and contents unchanged. The fixture's initial result-list assertion was
corrected: the controller reports completed native recovery even when it reused an owner.
`snapshot-outage-evidence.json` records the final proof and source hashes. These capture fixes
still need inclusion in the next complete image.

The exact packaged PDF shell subsequently passed the real CLI/private-session and
return-controller fixtures in a matching isolated VM runtime. The tested binary hash
matches the sealed bundle. Duplicate-path pages, independent windows, selection/placement,
protected final receipts, cancelled-switch survivors, missing-file retry and interrupted
append recovery pass without duplicates. Synthetic files, viewer preferences and Notes
remain unchanged. The fixtures close their windows normally; the container is stopped.
Evidence is `target/pdf-recovery/production-native/packaged-evidence.json`. A slow rootless
container ownership conversion delayed setup but did not cause a test failure. Complete-image
PDF boot and broader office/editor/browser support remain unverified.

Rollback failure injection found that `monet-boot` ignored a failed scheduling command,
cleared its trial and could reboot while claiming success. Both the failed-desktop and
GRUB-fallback branches now stop on scheduling failure, retain the existing trial/notice
and report a nonzero result to systemd. The new regressions fail against the installed
image; all 11 `GoingBackByItself` checks pass with the source fix. Before/after logs and
hashes are in `target/full-image/integration2/rollback-regression.json` and sibling logs.
The fix remains uninstalled. The user subsequently ran the guarded staging command using
the installed `monet helper rollback`. It queued the expected earlier deployment, followed
by a normal desktop restart. Boot `f77dda8b-8daf-4a6d-812d-5a589c815905` and a repeat normal
boot `02d291e6-81cc-4ea9-8359-1853e32a96a8` both preserve the latest saved document revision,
Notes, preferences, pins and shortcut bindings. KWrite opens the latest saved text; the
test window closes normally. Only the expected desktop shortcut screen mapping differs.
Evidence is `target/full-image/integration2/controlled-rollback.json`; the complete archive
`controlled-rollback-evidence.tar` has SHA-256
`5cdbd2b5c4b1efd30836f8d7491b70836e8d03872697727e96f261b8ee31a171`.

The first rollback desktop exposed missing Sound and broken panel presentation. These were
bench preview packages deliberately removed before full-image acceptance, with backups kept
in `before-upgrade`. Restoring and hash-checking those exact 25 asset directories/launcher
entries repaired the original preview desktop; Sound opens correctly after the repeat boot.
The original deployment/data checks precede this repair and remain separate. This does not
prove automatic compatibility for new widgets across shipped versions. Future image tests
must again exclude these preview overrides before claiming bundled-asset validation.
Base input-remapper and splash startup timeouts remain under substantial VM disk stalls.
After exporting the evidence and synthetic document, the bench returns to
`ai-before-controlled-rollback-1029`; checkpoint cleanup is not a re-upgrade test.
Nothing was published.

The first complete candidate later booted as deployment
`7e2b39e14643802b1ee38175fe51fd925323b3ddee3f63d06a032b797da7575d`. Installed helper/native
manifest hashes match the assembly evidence. Preferences, pins, Notes, saved work and a
desktop shortcut survived. Installed KWrite and Dolphin passed a real four-window capture,
native final editor receipt, cancelled-switch reopen and repeated restore without duplicates.
An initial compositor timeout was preserved as a failed attempt; the same open windows were
then used to finish the check. First boot took 4m29s and Plasma's splash timed out.

This image failed acceptance. Its migration unnecessarily wrote already-matching locked
system defaults; the image installer omitted shared title-button images; and `monet-boot`
treated short SSH sessions as changes to the graphical desktop. The latter forced a false
rollback after six minutes. The original deployment booted again; preferences, Notes, pins,
saved document and shortcut remained intact. The only changed pre-existing shortcut field
was its translated/display label (the Meta+G binding stayed unchanged). The fixes avoid
claiming ownership of inherited matching defaults, install the missing assets, and restrict
boot stability to local X11/Wayland sessions. Both new regressions failed before the fix;
30 focused VM checks pass afterward. A replacement image still needs boot/sign-in/rollback
verification. Evidence is under `target/full-image/`, including `installed-restoration.json`,
`rollback-evidence.json` and the candidate boot journal; these are not hardware tests.
`live-boot-filter.json` records the corrected check accepting the real local Wayland session
after 60 seconds while excluding SSH. `profile-fix-evidence.json` records the successful live
migration and unchanged journal on repetition after rollback. Four-window geometry/flag
comparison has at most 0.5-pixel rounding (`placement-evidence.json`). The replacement
full-checkout build has completed. Replacement assembly checks verify 14 helper/native
entries and 32 title-button assets, with bootc lint passing. The exported archive is
6,069,314,048 bytes, SHA-256 `9f653fc35c3b24dc923ee7999b23c3c33aef81aa6fa412f85ea17dcc5bd89e32`.
Inputs, assembly/lint evidence and the checksum-verifying staging script are under
`target/full-image/integration2/`. The user root staging step and replacement boot checks
remain; export/assembly success does not establish upgrade acceptance.

Test machines:

| Machine | GPU | Notes |
|---|---|---|
| Laptop | RTX 2080 (Turing) | Hybrid graphics: check games use the NVIDIA GPU |
| Desktop | RTX 5080 (Blackwell) | Needs NVIDIA open kernel modules (driver 570+) |

## 1. Setup

- [ ] Bazzite installed next to Windows 11 ([INSTALL.md](INSTALL.md))
- [ ] Secure Boot **on** in both systems (`monet doctor` in Monet; in Windows, `Confirm-SecureBootUEFI` in an admin PowerShell)
- [ ] `monet doctor` shows no âœ—
- [ ] Monet Bridge installed; `monet-bridge status` (admin terminal) lists the Monet entry
- [ ] The right Monet for the graphics: `rpm-ostree status` (or `bootc status`) shows `monet` on the RTX PC and `monet-amd` on a PC with only Intel or AMD graphics (or an NVIDIA card older than the RTX 20 series)

### Making the USB stick

- [ ] The new safety-preview writer lists a plugged-in USB stick, writes and verifies it,
      and the PC boots its installer. Check ordinary 512-byte and supported 4 KiB sectors.
- [ ] Unplug/replace the selected stick while downloading: the replacement receives no writes.
- [ ] Keep a file open on the target: an unsuccessful volume lock stops before any dismount/write.
- [ ] An oversized/corrupt image and a failed device flush never produce a Ready message.

2026-10-28 software evidence: `cargo test -p monet-usb` passes all 18 Windows tests, including
native SHA-256 against a known vector and a temporary source file that cannot be changed or
deleted while held. No Windows test opens a physical drive. Seventeen portable tests also
pass in the Linux VM: wrong device/system disk, capacity including padding, checksum parsing,
invalid ISO headers, simulated lock/write/flush/read failures, corruption and partial writes.
The transfer tests check aligned buffers/offsets, write the header last and preserve bytes
after the image. Clippy passes. The release executable in
`dist/Monet-0.9.3-Make-USB-Stick-safety-preview.exe` is unsigned; Defender found no threats.
These checks do not replace actual Windows disk-driver, controller, hotplug and boot tests.

### Clock format repair — 2026-10-28

Settings' 24-hour toggle updates both the large desktop clock and panel clock in the running
VM. Both directions were observed without signing out. The shared component also feeds the
world clock, lock screen and timed quiet-mode labels. A Qt regression loads two clocks,
changes the preference externally, removes the explicit override to follow the region, and
opens another instance to verify persistence. Sixty-seven focused Python/UI checks pass.
Screenshots are under `target/clock-usb/`. The VM test checkpoint was restored, its notes
checksum stayed unchanged, and the clock-only user overrides were then reapplied for use.

### 0.9's smaller things

- [ ] Upgrade an existing account with `look-0.9.3` and `names` already stamped, and Bazaar/Discover pinned: after sign-in, every Store shortcut opens Monet's gallery. Include a pinned `file:///usr/share/applications/org.kde.discover.desktop`, not just an `applications:` id. Sign out/in again: the result stays, unrelated pins and the desktop layout stay as chosen
- [ ] Settings, Store and Games in Mist and Smoke, with Clear, Frosted, Matte and Solid glass: title and sidebar change opacity together, all outer corners are rounded, and no square blur or pale strip extends outside them. Maximize removes the outer rounding; restore brings it back. Check normal, maximized and snapped windows at 100%, 125% and 150%
- [ ] Drag each app by its title, double-click to maximize/restore, and use all three title buttons with mouse and keyboard. Resize from all four edges and corners, especially above the title. Confirm Windows+Z and shared-edge resizing still work; repeat without compositor blur and with Qt Quick's software renderer
- [ ] Snap Settings beside Store, then beside a client-decorated app: both fill their tiles without an inset. Drag their shared edge in either direction, then stack two windows vertically and drag that shared edge; no gap or overlap. Stretch a window to the bottom: it reaches the work area's bottom
- [ ] Settings â†’ Updates names Monet's version ("Monet 0.9.3 is ready"), not "44.2026â€¦"
- [ ] Settings' four sides and four corners drag it bigger and smaller, taken hold of on the glass edge outside the page too, the edge staying under the pointer; it goes down to the screen's bottom; double-clicking "Settings" fills the screen; the size is kept, and it opens all on the screen
- [ ] Popovers, the tray's (Disks & Devices, Audio Volume), the menu and the bars show the painting's strokes, like the desktop widgets
- [ ] The clock's page goes back to its width after the notes close; a note written there shows in the Calendar widget within a second
- [ ] Light & Wallpaper â†’ Through the year hangs the painting of the season
- [ ] The bar stays in view; with Light & Wallpaper â†’ Bar steps aside on, a window dragged over the bar makes the island under it slide away, and pointing at the bottom edge under it brings it back
- [ ] Timer â†’ Focus, then start: notifications stay quiet, the painting goes from dawn to night over the minutes, and both come back after
- [ ] Games & Controllers â†’ Save the last 30 seconds: GPU Screen Recorder installs, KDE asks for the screen once, Windows+Alt+G saves an MP4 in Videos
- [ ] Search in the menu for "printers": Settings' Printers page is found

### Next to Windows, backups and the painting

- [ ] Monet Setup on a PC with a full Windows drive: "Monet next to my Windows" offers to make room (the note says from and to), Bring my files is ticked, and after installing Windows still starts (it checks its drive once)
- [ ] At the first sign-in the files from Windows are in Documents, Pictures and the rest, and a note says so
- [ ] Settings â†’ Backups: after an hour, "An hour ago" opens your files in Files; right-click a file â†’ Earlier versions â†’ Put back puts a copy beside it
- [ ] A USB drive picked in Backups gets "Monet Backup/<you>" the next time it's plugged in
- [ ] The Hours changes light near your sunrise and sunset, not at fixed hours; on a rainy day the painting is softer
- [ ] Display shows HDR and Smoother games on a monitor that can do them, and they change the monitor
- [ ] Games & Controllers lists a game installed here whose anti-cheat needs Windows

### Safety and recovery (0.9.1)

- [ ] Monet Setup's Hello shows the language's time zone with its time; once online it moves to where the PC is, unless one was chosen; the installed Monet has the zone chosen
- [ ] On the blue screen after installing, choose Continue boot on purpose: Monet doesn't start ("bad shim signature"). Start from the USB stick: Hello says Monet can't start yet and offers Ask again and restart; after it, the blue screen is back, and Enroll MOK lets Monet start
- [ ] All set shows the blue screen's five steps in pictures beside the sheet, in the language chosen (the blue screen's own words in English), and right to left in Arabic and Hebrew
- [ ] Choose Continue boot on purpose with the stick out: "bad shim signature" for about ten seconds, then "Monet needs your OK on a blue screen", and the PC restarts into the blue screen; Enroll MOK, Continue, Yes, monetsetup, Reboot, and Monet starts. The GRUB menu (Esc while starting) lists "Monet: ask again for the blue screen"
- [ ] The password twice: different, Continue waits and says so; both empty, a warning says Monet signs in by itself, and the installed Monet starts straight into the desktop without locking; after Settings â†’ Accounts gives it a password, the next start asks for it
- [ ] Monet Setup on a PC with a TPM 2.0: Encrypt this PC is ticked; after installing, the recovery key page shows eight groups of eight letters, and Continue waits for "I've kept my recovery key"
- [ ] The first start (after the blue screen) asks for no passphrase; afterwards `sudo systemd-cryptenroll /dev/disk/by-uuid/<uuid>` lists a tpm2 slot and a password slot (the recovery key), `/boot/monet-firstboot.key` is gone, and after the next restart `/proc/cmdline` has no `rd.luks.key`
- [ ] Turn Secure Boot off (or clear the TPM): the start asks for the passphrase; the recovery key opens it, and the start after that doesn't ask
- [ ] In a VM: install an update, restart, and within its first minute stop the sign-in screen (`sudo systemctl stop display-manager`): five minutes later the PC restarts into the Monet from before, Settings â†’ Updates says "Monet went back to â€¦", the next sign-in says so too, and `sudo systemctl start monet-update` skips that update
- [ ] An update that starts normally: `/var/lib/monet/trial.json` is gone a minute after the sign-in screen, and `grub2-editenv list` has no `boot_counter`
- [ ] Settings â†’ Updates â†’ Reset this PC asks for the password; after Restart now: Monet's look and welcome come back, Documents, games, apps, Wi-Fi and printers are still there, the settings from before are in `~/.local/share/monet/before-reset`, and a note says Monet is as it came
- [ ] An update that starts normally shows no start menu while the PC starts

### Fixes in 0.9.1

- [ ] The desktop and the lock screen show the painting (0.9.0 showed black)
- [ ] The bar's three islands show on an empty desktop
- [ ] Windows' clock is right after coming from Monet (and Monet's after coming back)
- [ ] Quitting a game in Windows restarts into Monet by itself; the PC doesn't switch off

### Bluetooth in both (0.9.1)

- [ ] Pair a controller (a DualSense: classic Bluetooth) in Monet, then in Windows. Back in Monet it connects without pairing again (`journalctl -u monet-pairings` says "took Windows' pairing for â€¦"), and in Windows it still connects
- [ ] The same with a Low Energy device (an Xbox controller with current firmware, or earbuds)
- [ ] Pair it again in Monet only: Monet keeps its own pairing at the next start (Windows needs pairing once more, then both work)

### Next (after 0.9.1)

- [ ] Settings â†’ About Monet â†’ Save a report: after a few seconds a notification says it's in Documents; Show opens Files on it; the file has every part (the PC, this start's errors, the start before, sleep, Monet's records), none empty where the PC has the thing
- [ ] Settings â†’ Accessibility â†’ Magnifier on: Windows key and + zooms in around the pointer, Windows key and âˆ’ zooms out; off, the keys do nothing; it stays as set after signing out and in
- [ ] Settings â†’ Phone with no phone yet: the QR code opens KDE Connect's download page on the phone; with the app open on the same Wi-Fi the phone shows up under it, Pair asks on the phone, and once accepted the phone is listed with its battery
- [ ] Ring makes the phone ring; Send a fileâ€¦ sends a file; Texts opens the phone's messages; Files on your phone opens it in Files; Forget unpairs it
- [ ] On a laptop with a fingerprint reader: Lock & Privacy shows Fingerprint; after Set upâ€¦ (Accounts â†’ Configure Fingerprint) the lock screen unlocks with a finger and an administrator question (Reset this PC) accepts one; without a reader the row isn't there
- [ ] Screenshot (Print Screen) â†’ Extract Text on a picture with text in your language (Swedish, say) reads it; Screenshot's settings list your language and English
- [ ] A Windows that Monet installed shows The Hours as its desktop; "Monet next to my Windows" keeps Windows' own wallpaper
- [ ] Monet Bridge updates itself: with an older Bridge in Windows and a newer release out, quit a game: the PC restarts into Monet a few seconds later than usual, and next time in Windows `monet-bridge status` (admin terminal) shows the new version; `C:\ProgramData\Monet\update.log` says so
- [ ] With no internet in Windows, quitting a game still restarts into Monet (at most about 20 seconds later)
- [ ] `powershell -ExecutionPolicy Bypass -File "C:\Program Files\Monet\Update-Monet.ps1" -CheckOnly` says whether a newer Bridge is out, and changes nothing

### Security at a glance (after 0.9.3)

- [ ] Settings â†’ Security on a PC with Secure Boot on, an encrypted disk, the firewall on and updates by themselves: every row has a lily tick, and the title says Your PC is protected
- [ ] Secure Boot off (turned off in the firmware, Monet's key trusted): Firmware settingsâ€¦ explains, Restart asks KDE's restart question, and the PC opens its firmware settings
- [ ] Secure Boot off on a PC where Monet's key isn't trusted (`sudo mokutil --delete` it first, in a VM): the row says so and offers Trust Monetâ€¦, which asks for the password; the next restart shows the blue screen; after Enroll MOK the row offers Firmware settingsâ€¦
- [ ] `sudo systemctl disable --now firewalld`: the Firewall row says Off; Turn on asks for the password, and the row says On afterwards
- [ ] Updates â†’ auto updates off: the Updates row says so; Turn on brings the tick back. With an update downloaded, the row says it's ready and Restart restarts
- [ ] Firmware: the row looks for updates as the page opens; with one available, Install installs it (fwupd asks for the password)
- [ ] Backups â†’ earlier versions off: Turn on brings them back; without a backup drive the row offers Add a driveâ€¦, which opens Backups
- [ ] An unencrypted Monet (Fedora's installer): the Encryption row says Off, with no button
- [ ] `firewall-cmd --get-default-zone` says `monet`; the Firewall row says only what Monet uses comes in, and the switch under it is on
- [ ] With the switch on: the phone pairs and rings (Settings â†’ Phone), Steam on another PC on the network finds this one for Remote Play and a local game transfer, a network printer shows up; from another PC, `nc -zv <this PC> 22` (or any other port) is refused
- [ ] The switch off asks for the password; `firewall-cmd --get-default-zone` is Bazzite's zone again (`cat /usr/share/monet/firewall-zone-before`), and on turns Monet's back on
- [ ] With Monet's zone on, `python3 -m http.server 8765` in Konsole: within seconds a notification asks "python3 wants to accept connections" and stays; Allow asks for the password, then another device on the network opens http://this-pc:8765, and Security â†’ Apps that can accept connections lists python3 with its switch on. Off again: the other device can't. Run it again after Keep blocked: no question
- [ ] Apps that can accept connections â†’ Games you host (the password once): a Minecraft LAN world on this PC shows up for a friend on the same Wi-Fi; `firewall-cmd --list-all-policies` shows monet-allowed with 25565; off again, the policy is gone. LocalSend on with the app open: a phone nearby finds this PC

### A smoother trip to Windows (0.9.3)

- [ ] Play a Windows game: from Windows' sign-in until the game is up, Monet's painting covers the screen with the game's name and Back to Monet now; a launcher that opens (Riot Client, say) comes up over it; a Windows that Monet installed shows no taskbar until the pointer touches the bottom edge
- [ ] Quit the game: the cover says Back to Monet and counts down; Go now (or Enter) restarts into Monet at once, Stay in Windows (or Esc) leaves you in Windows
- [ ] Back to Monet now while the game is still starting restarts into Monet at once; a game that doesn't start within 30 minutes leaves you in Windows, the cover gone
- [ ] With Discord (or Vesktop) installed in Monet and the shared Games folder open: `ls "/run/media/Windows games/.monet/installers"` shows DiscordSetup.exe after sign-in; Game launchers â†’ Sign inâ€¦ shows Getting Discord ready, then Discord is in the list; after signing in once, a later trip to Windows has Discord running at sign-in
- [ ] Settings â†’ Play on Windows â†’ Game launchers â†’ Sign inâ€¦: Windows lists the launchers it has; Sign in opens one (not as administrator: Task Manager's Details shows it under your name, not elevated); after signing in to Steam with Remember me, its card says Signed in within a few seconds; Back to Monet goes back
- [ ] Settings â†’ Update Windows games â†’ Update & switch off: the cover says Updating your games with Windows Update's and Steam's progress; Steam and Epic open in the background; the PC switches itself off when the downloads are quiet, and Settings then says when it was last done
- [ ] With a Windows update that needs a restart: Windows restarts once (back to the cover, Windows Update finishing), then switches off; the next Play starts the game without "Working on updates"
- [ ] Switch off now on the update cover switches the PC off at once, even when Windows wanted a restart
- [ ] The cover in Arabic or Hebrew Windows: words on the right, buttons in reverse order; in Japanese or Chinese the title is in Windows' own font
- [ ] `monet-bridge cover-preview launchers %TEMP%\cover.png` (in `C:\Program Files\Monet`) paints the launchers scene into a PNG

### One game library (after 0.9.3)

- [ ] Games in the panel (the sun as a play button) lists Steam's games installed here, Heroic's (an Epic and a GOG game at least, Heroic from the Store, so the Flatpak) and the Windows games, each once, by name, with covers
- [ ] Each says Steam Â· Plays on Monet, Epic Â· Plays on Windows and so on; a game with anti-cheat that doesn't allow Linux (Apex Legends, Fortnite) says Plays on Windows even when it's installed here too
- [ ] Play on a Plays on Monet game starts it at once (Steam's or Heroic's game window), no restart; on a Plays on Windows game it asks, then restarts in Windows with it, as before
- [ ] A game installed here that needs Windows but isn't installed there says it needs Windows, and Restart opens Windows (no game) to install it
- [ ] `/usr/libexec/monet-quick library` prints the list as JSON, each with `plays`, `here` and `windows`
- [ ] In Windows, with a Battle.net game (Call of Duty, Overwatch) a Ubisoft Connect game and GTA V from the Rockstar Games Launcher installed: `monet-bridge scan` lists them as `battlenet:AUKS`, `ubisoft:ID`, `rockstar:gta5`; back in Monet they're in Games as Battle.net Â· Plays on Windows, and Play starts them in Windows (Battle.net opens and launches the game)
- [ ] Recently played (the desktop widget) shows a Heroic game and a Lutris game after playing them, and a game played in Windows (VALORANT) after the trip, with its time; clicking that one asks before restarting in Windows
- [ ] Lutris' games (installed, not its Steam ones) are there too, with Lutris' banner as the cover; Play starts them through Lutris
- [ ] Typing in Find a game filters by name (without accents: "etretat" finds Ã‰tretat), Enter plays the one game left, Esc clears it
- [ ] With games on both sides, Plays on Monet and Plays on Windows in the side show each side; a game installed on both sides says Monet Â· Windows on its cover
- [ ] Open Games with the keyboard (Windows+G): Ctrl+F or typing on the covers goes into the search; Down moves onto the games with a ring around the one you're on, the arrows move it, Enter or Space opens its page (where Enter plays), the Menu key opens its menu, Up from the top row goes back to the search
- [ ] Right-click a game in Windows games that plays on Monet too: Play on Windows asks, then restarts there with it; Show in Steam opens its page; Uninstallâ€¦ opens Steam's own uninstall question
- [ ] A game Steam is downloading shows Downloading with a percent and a green line along its cover that grows while the gallery is open
- [ ] A game that needs Windows, installed in Monet's own Steam folder, with Windows games added to Steam: Play explains moving it, and Show in Steam opens its page in Steam
- [ ] A native Linux game ProtonDB rates Borked for Proton still says Plays on Monet
- [ ] A Steam game ProtonDB rates Borked (installed here, no anti-cheat): a minute after the gallery first opens, it says Plays on Windows, and Play explains that players report it doesn't run in Monet; right-click â†’ Play in Monet starts it here anyway; `~/.cache/monet/protondb.json` has each installed game once
- [ ] With Windows games shared but not yet in Steam here, the gallery shows a green note with Add to Steam: it says Addingâ€¦ while Steam restarts, then the note goes; Ã— puts it away for good (`~/.config/monet/shared-hint-off`)

### Games, the app (after 0.9.3)

- [ ] The Games button in the bar, Windows+G and Games in the menu each open the Games window (with its own taskbar entry and the sun icon, titled Games); doing it again while it's open brings that window forward instead of a second one
- [ ] The side lists All games, Favorites, Recently played, Plays on Monet / Plays on Windows (with games on both sides) and each store under Stores, with counts; picking one shows its covers, and a store far down the list on a small window scrolls into view
- [ ] Covers are Steam's tall library pictures (also for Steam games only Windows has); a game without one shows a painted cover with its banner and name
- [ ] Recent / Name / Play time / Size sort the covers; the choice and the window's size are there again after closing and opening Games
- [ ] Continue playing shows the four games played last (Today, Yesterday, 3 days agoâ€¦); its sun plays straight away
- [ ] Hovering a cover shows its star and sun: the star makes it a favorite (it stays on the cover, and the game is in Favorites, also after a restart), the sun plays it
- [ ] Clicking a cover opens its page: the wide picture with the name, Play, Plays on, Last played, Play time and Size on disk; Esc or the arrow goes back; a Windows game's Play on Windows asks before restarting
- [ ] Play time matches Steam's for a Steam game; after playing a Windows-only game on a trip (VALORANT), its play time grows by about as long as it ran
- [ ] Right-click a cover: Play, Open its page, Add to / Remove from favorites, and for Steam's Show in Steam and Uninstallâ€¦
- [ ] In Arabic or Hebrew the window is mirrored: the side on the right, covers from the right

### Wi-Fi in both (after 0.9.3)

- [ ] Join a new Wi-Fi network in Monet (a phone's hotspot), then play a Windows game: Windows is online on it without asking; `C:\ProgramData\Monet\wifi` is empty afterwards
- [ ] Join another network in Windows (the taskbar's Wi-Fi), then Back to Monet: Monet knows it at once (Wi-Fi page lists it as saved), and `C:\ProgramData\Monet\wifi-out` is gone or empty after Monet started
- [ ] A work or school network (802.1X) in either stays where it was joined
- [ ] In Windows, as an administrator: `icacls C:\ProgramData\Monet\wifi` lists only Administrators and SYSTEM, and a file Monet left there before Bridge started (Settings â†’ Wi-Fi, join one, then restart into Windows with Bridge's tasks stopped) has the same
- [ ] Change Monet's time zone (Settings â†’ Date & Time, another city), then play a Windows game: Windows' clock shows the same time as Monet's did

### Your apps again (after 0.9.3)

- [ ] With Files, Zen and Discord open, Play a Windows game and quit it: back in Monet, a few seconds after the desktop shows, Files, Zen (with its tabs) and Discord open again; Steam isn't opened twice
- [ ] Settings â†’ Play on Windows â†’ Open your apps again off: after the next trip nothing reopens; on again, it does
- [ ] With Ready when you come back on too: the apps are open behind the lock screen when you unlock

### A guest (after 0.9.3)

- [ ] Settings â†’ Accounts â†’ Guest asks for an administrator's password, then the sign-in screen lists Guest with Monet's parasol painting; Guest signs in with no password and gets Monet's look
- [ ] As Guest, save a file in Documents and change the wallpaper, then sign out and in as Guest again: the file is gone and the look is new; Backups shows no earlier versions
- [ ] As Guest, Play on Windows asks for an administrator's password; your files (`ls /var/home/<you>`) are refused
- [ ] As Guest, Games lists no Windows games and the app menu has none either
- [ ] Power off while Guest is signed in: at the next start Guest's home is new again
- [ ] Guest off removes the account (no Guest on the sign-in screen), after the password
- [ ] As Guest, `loginctl enable-linger` is refused, and `btrfs subvolume create ~/keep` then signing out still leaves a new home
- [ ] As Guest, start `setsid sleep 1d &` in Konsole and leave a file in /tmp, then sign out: `pgrep -u guest` finds nothing, the file is gone, and Guest's next sign-in has a new home
- [ ] As another account (not an administrator), `su guest` is refused; as root it still works
- [ ] Guest off right after a guest signed out removes the account (`id guest` fails) and Settings says it's off
- [ ] On a PC where someone's own account is called `guest`, Guest doesn't turn on and their home is untouched

### Your photo, painted (after 0.9.3)

- [ ] Settings â†’ Light & Wallpaper â†’ Your photo: the file dialog opens; pick a JPEG from your phone: the tile says Paintingâ€¦ with a percent, and within about a minute (two on a 4K screen) the desktop and the lock screen show it painted, in the light of the hour; the placard says Your photo, and the light
- [ ] Choose The Hours and back to Your photo: it comes back at once, no painting again; Another photoâ€¦ paints a new one, the old one stays on the wall until it's done
- [ ] A picture Monet can't open (a .heic renamed .jpg): the card says it couldn't be painted, the wall stays as it was
- [ ] With Through the day on, the painting drifts dawn â†’ midday â†’ dusk â†’ night like The Hours
- [ ] Sideways phone photos come out the right way up

### Downloading once (after 0.9.3)

- [ ] Files lists Shared with Windows with your places; a file saved there is in Windows' Explorer under Quick Access (Shared with Monet), and one saved there in Windows is in Monet after the next start
- [ ] With Windows hibernated, the place isn't in Files (and is back after a trip that ended with Back to Monet)
- [ ] In Windows, Steam installs a game into the Games folder Monet made (no "disk write error"), and `icacls C:\Games` lists Authenticated Users with Modify
- [ ] Install an Epic game in Heroic into Windows games on a Windows without Epic's launcher: at the next sign-in `Windows games/.monet/installers` gets Epic's installer; the next trip installs the launcher without downloading it (Bridge's log says so), and the installer is gone the start after
- [ ] Battle.net in Lutris: drive W: is Windows games; install Overwatch there; Monet's Games lists it as Battle.net Â· Plays on Windows; Play: Windows' Battle.net (installed from the fetched installer, its own window) asks to install it, Locate the game â†’ C:\Games\Overwatch, and it starts with nothing downloaded; next time it starts straight away
- [ ] Ubisoft Connect in Lutris: install a game on W:; at the next start Windows' Ubisoft Connect lists it as installed (or, asked to install it, Locate installed game finds it)
- [ ] An installer that isn't signed by its maker (a renamed file in .monet/installers) isn't run: Windows downloads the real one
- [ ] Settings â†’ Games & Controllers â†’ Get Battle.net: Lutris (from Flathub if it wasn't here) installs Battle.net; W: is there in its install dialog right away; the button then says Open Battle.net
- [ ] A Battle.net game installed on W: is in Monet's Games before any trip, as Battle.net Â· Plays on Windows, and its Play sheet says where to locate it
- [ ] On a trip that installs a launcher, Windows shows Monet's painting with "Getting Battle.net ready" (or Epic Games, Ubisoft Connect) until the game starts

### Windows' keys (after 0.9.3)

- [ ] On a new account's first sign-in: Ctrl+Shift+Esc opens System Monitor, Windows+I Settings, Windows+A Quick Settings, Windows+G Games, Windows+R the run box, Windows+E Files, Windows+Shift+S a region screenshot; Windows+Up maximizes a window and Windows+Down minimizes it
- [ ] The old keys still work too (Ctrl+Esc, Alt+Space, Meta+Shift+Print, Meta+PgUp)
- [ ] An account from 0.9.3 gets them at its next sign-in; a key changed in Change shortcutsâ€¦ stays changed after another sign-in
- [ ] Settings â†’ Mouse & Keyboard lists them

### Windows programs (after 0.9.3)

- [ ] Download a small Windows program (7-Zip's or Notepad++'s installer) and double-click it in Files: Monet's sheet asks, with its name; Run in Monet installs it (the first time a note says Monet is getting ready, then the installer opens), and afterwards the program is in the app menu and opens from there
- [ ] A portable `.exe` (a single program, no installer) runs from Run in Monet, and a second one starts quicker (no getting ready)
- [ ] Open in Windows on the same file: the PC restarts in Windows and the program opens there, Windows stays (no countdown); `C:\Shared with Monet` has it, and Back to Monet goes back; a program saved in Shared with Windows opens without being copied
- [ ] With Windows' drive not open (Windows hibernated, say), the sheet says Windows can't get it this time and Open in Windows is greyed
- [ ] Right-click an `.exe` in Files: Run in Monet starts it at once; Open in Windowsâ€¦ shows the sheet
- [ ] With Office, Photoshop or another app installed in Windows: after a start of Monet with Windows' drive open, the app menu has it with its own icon on Monet's canvas, "Opens in Windows" under its name; searching "word" or "windows" finds it. Windows' own tools (Notepad, Command Prompt), Steam and its games, Edge and Chrome, uninstallers and help aren't there, and an app Monet has too (Discord) is there once, Monet's
- [ ] With iCloud or WhatsApp from the Microsoft Store in Windows: after a trip to Windows and back (and the next start of Monet), the app menu has it with its own logo; choosing it opens it in Windows. Calculator, Photos and Xbox aren't listed
- [ ] Choose one: Monet's sheet shows it with Open in Windows (no taskbar button meanwhile); Open in Windows restarts in Windows and the app opens there as you (with its own arguments: Office opens to its start page), Windows stays; Back to Monet goes back. Uninstall it in Windows: after the next trip, its entry and icon are gone
- [ ] An `.msi` installer works both ways too

### The Store (after 0.9.3)

- [ ] The bar's Store (the bouquet) and the menu's open Monet's Store, not Bazaar: today's pick hung on a painting with Install on its placard, then Monet's picks as rooms (a strip of The Hours with its placard, three framed apps, a wall of tiles), Most installed this month after the first and Fresh paint after the third; Mist by day, Smoke by night; sections down the side with counts, the window in Monet's glass. An account from 0.9.3 with Bazaar pinned in the menu or the bar opens the Store from there too, and no "Bazaar" shows anywhere
- [ ] In another language (Svenska, say) the names, summaries and descriptions are in it where Flathub has them, and the window's own words are too
- [ ] The mouse wheel and a touchpad glide through the front page, a section and an app's page, also with the pointer over the screenshots; Page Down and arrows scroll too; Settings' pages, Games' covers and a game's page glide the same way
- [ ] Settings', Games' and the Store's side is glass: the painting (or a window behind) shows through, blurred. Settings â†’ Light & Wallpaper â†’ Glass: Solid makes all three paper at once, Matte nearly paper with the painting's color, Frosted and Clear see-through again, without closing them; their pages stay paper all along
- [ ] Monet's look â†’ Put back: the card says Putting it backâ€¦ for a few seconds, then the pill says Done in lily, then Put back again
- [ ] Games: its own painting (the haystacks), a placard with how many, the top three framed and numbered. Recently updated puts the newest first with their dates, Name sorts by name (and is still chosen after the Store is opened again), Strategy narrows to strategy games (the placard says how many), Checked by Flathub to the checked ones, and the page starts from its painting each time
- [ ] Search "krita": Krita first. Search "photoshop": a note says Photoshop is made for Windows and lists GIMP, Krita and Pinta; with Photoshop in your Windows, it's under On your Windows and choosing it opens Monet's sheet for Windows. Search "zzqx": the Store says nothing goes by it, with examples
- [ ] An app's page: under its section's painting; the screenshots as a gallery (the arrows, the small ones under it and the arrow keys change the big one, a click shows it whole), the description, What it can reach in plain words, the sizes, version and website, and More like this (choosing one opens its page at the top). Install shows progress, then Open and Remove; it's in the app menu and under Installed; Remove takes it away again. A built-in app (Photos) says Part of Monet
- [ ] As a standard account (not an administrator), Install says only an administrator can. With the network off, it says the Store can't reach Flathub
- [ ] A link to `appstream://org.gimp.GIMP` (from a web page or `xdg-open`) opens the Store on GIMP's page; a second click on the bar's Store brings the open window forward

### EA's games, and launchers out of sight (after 0.9.3)

- [ ] In Windows, with EA SPORTS FC 26 installed by the EA app: back in Monet it's in Games as EA Â· Plays on Windows; Play restarts in Windows and Monet's painting says Starting until the game itself is on screen; the EA app is never seen (it's minimized in the taskbar while the game runs)
- [ ] The same with the EA app signed out: after about a minute the painting steps aside and the EA app's sign-in is there; once signed in, the game starts
- [ ] Quit the game and press Stay in Windows on the countdown: within a minute the EA app is gone from Task Manager (EABackgroundService, a Windows service, may stay); Battle.net, Ubisoft Connect and Epic's launcher close the same way after their games; Steam stays
- [ ] A Ubisoft game in Ubisoft Connect's own games folder: while it runs it isn't minimized (only Ubisoft Connect's windows are)
- [ ] Settings â†’ Games & Controllers â†’ Get EA app: Lutris installs the EA app; set its download folder to W:\ and install a game; it's in Games as Plays on Windows before any trip, and Play's sheet says to choose Download with C:\Games; in Windows the EA app checks it instead of downloading it
- [ ] In Monet, with Steam closed: Play on a Steam game starts it with Steam only in the tray; Play on a Heroic game starts it without Heroic's window

### Monet's names everywhere (after 0.9.3)

- [ ] Sign in, open Files, Terminal, Photos and Documents: their title bars end in Files, Terminal, Photos and Documents (never Dolphin, Konsole, Gwenview, Okular); in Swedish, Filer; Alt+Tab and the bar's previews say the same
- [ ] `cat /etc/os-release`: NAME and PRETTY_NAME say Monet, VERSION is Monet's, BOOTLOADER_NAME says Monet; ID still bazzite; KDE's About this System says Monet
- [ ] Files' Devices doesn't list "boot" (or EFI); a USB stick still shows, even one with a partition called boot
- [ ] Files' status bar doesn't say "0 B free"; Settings â†’ Storage shows the room left
- [ ] Input Remapper isn't in the menu and `systemctl status input-remapper` says disabled; the start isn't held up by it
- [ ] Light or Dark picked several times quickly: Monet's look follows each time, and `systemctl --user --failed` stays empty

### Settings tells the truth (after 0.9.3, found by the test bench)

- [ ] Settings â†’ Security: Secure Boot says on when the PC's firmware has it on (`mokutil --sb-state`), and the firewall says on (`systemctl is-active firewalld`)
- [ ] Settings â†’ Default Apps lists Documents for PDFs
- [ ] Zen's first start (a new account) opens one Monet new tab: no Zen welcome or what's-new page
- [ ] A PC without Wi-Fi or Bluetooth (on a cable): Quick Settings says Unavailable on both and opens at once with its sliders (no empty bar first); Settings â†’ Wi-Fi says This PC has no Wi-Fi
- [ ] A PC without speakers (or the VM): Sound says No speakers or headphones, with no Play sound through list
- [ ] Settings' search: type Games and press Enter, it opens Games (not Storage); Updates opens Updates
- [ ] Games lists no Windows game that Windows doesn't have (Slay the Spire is no longer always there); on a Monet without Windows, Games has no Open Windows
- [ ] Settings from the app menu (or any of its pages, like Sound) opens Monet Settings on that page; double-clicking a Windows program in Files asks where to open it
- [ ] Games & Controllers counts only controllers: a drawing tablet or a VM's mouse isn't one

### The bar, the glass and the sound (after 0.9.3)

- [ ] A new account: the bar's islands slide down out of the way when a window comes over them (maximize Files), and slide back up as the pointer touches the bottom of the screen, with a pen or touchscreen too; Settings â†’ Light & Wallpaper â†’ Bar steps aside is on
- [ ] An account from 0.9.3 that never turned Bar steps aside off: it's on after the update; one that turned it off keeps it off
- [ ] Bar steps aside off and on again, several times: the middle island stays in line with the other two (it stood a bar's height higher)
- [ ] In a VM, or on a PC without its graphics driver (6 or more processor threads): windows and the bar still animate (`KWIN_EFFECTS_FORCE_ANIMATIONS=1` in `cat /proc/$(pidof kwin_wayland)/environ | tr '\0' '\n'`)
- [ ] Settings â†’ Light & Wallpaper â†’ Glass is a slider: Solid, Matte, Frosted, Clear. Each step changes the bar, popovers, window frames, Files' window and the desktop widgets together: Clear shows the painting's strokes, Frosted only its light and color, Matte a light veil with a faint grain, Solid is paper; the words under the slider say what each is
- [ ] Glass right after the first sign-in (KWin may not have loaded its blur yet): Clear is frosted glass, never a sharp see-through window (`busctl --user get-property org.kde.KWin /Effects org.kde.kwin.Effects loadedEffects` lists blur)
- [ ] An account from 0.9.3 with glass off stays solid; with glass on stays clear
- [ ] Sound sits beside Quick Settings (KDE's volume item is gone from the tray): its icon follows the volume, the wheel over it changes it 5% a notch, a middle click mutes; its popover has the volume with a mute pebble, Play sound through (with two or more outputs) and Apps playing sound, and Sound settingsâ€¦ opens Settings â†’ Sound
- [ ] The volume keys still change the volume and show the level on screen
- [ ] On a PC without Windows: Settings â†’ Play on Windows says No Windows on this PC, with no Restart in Windows, games or launchers there; Games has no Open Windows

### Windows, snapped as in Windows (after 0.9.3)

- [ ] Drag a window by its title: a sliver of glass comes down at the top of the screen; bring the window up to it and it opens into five layouts; the part under the pointer lights up and a lily pane shows where the window goes; let go and the window glides there
- [ ] Drag to the left or right edge: a half; to a corner: a quarter; to the top elsewhere: the whole screen; each with the preview first, and gliding into place
- [ ] After a snap, Snap Assist offers the other windows in the rest of the layout: click one and it takes its part and comes to the front, then the next part is offered; click anywhere else, the pane's empty glass too, and it goes; Windows+Left and Windows+Right do the same for the other half
- [ ] Windows+Z: the layouts come down for the window you're in; click a part; Windows+Z again or a click elsewhere puts them away
- [ ] Settings â†’ Light & Wallpaper â†’ Snap layouts off: dragging a window to the left edge gives it the left half with no Snap Assist, the top fills the screen, Windows+Z does nothing and Mouse & Keyboard's list leaves it out; on again, the layouts and Snap Assist are back at once (no sign-out). Install an update of Monet: still off
- [ ] Keys, as in Windows: Windows+Left, then the arrows or Tab light a window's picture in Snap Assist, Enter or Space picks it, Esc closes it. Windows+Z, then the arrows walk the parts (up and down: the layouts), Enter puts the window there and Snap Assist comes; Esc closes that too. Afterwards Esc, Enter and the arrows work in apps again (the Calculator's Esc clears it)
- [ ] The left island shows the sun and the Games button (the sun as a play button); clicking it, or Windows+G, opens Games, and again brings it forward
- [ ] A notification (a screenshot taken, say) shows whole, its close button inside the screen and its right edge in line with the right island's, at 100%, 125% and 150%
- [ ] Windows+Z shows a number under each layout; 4 lights that layout's first part, numbers its parts and turns its own number lily; 3 puts the window in its third part. A number with no layout (9) does nothing; afterwards typing numbers in an app works again
- [ ] Drag a snapped window away: it's its own size again, still under the pointer where you held it
- [ ] Stretch a window's bottom edge to the bottom of the screen (or its top edge to the top): it takes the whole height, gliding there
- [ ] Snapped windows (a drag, Snap Assist, Windows+arrows) meet each other and the screen's edges: no painting shows around them
- [ ] Snap Settings to one half and another window to the other; make Settings wider by its glass edge: the other window gets narrower, and neither goes over the other. The same the other way round, from the other window's edge
- [ ] Settings is a window like the others: Monet's title bar with its three dabs, it resizes from every side, double-clicking the title fills the screen, Windows+arrows and a drag snap it, the taskbar shows it, and it keeps its size after closing. Restart the bar (or let it crash): Settings stays open. Open it from the menu, Windows+I, Quick Settings' All Settings and a tile's arrow, and the desktop's Personalize: always one window, at the page asked for, coming to the front even from behind another window. Typing in its search works; Esc closes it
- [ ] Close Settings after it was snapped and open it again: its own size, in the middle, not the snapped one
- [ ] Turn Bar steps aside off and on a few times: the three islands stay at the same height every time and look alike; off, a maximized window goes below all three of them
- [ ] Right-click the desktop â†’ Add or Manage Widgets, then Done: the three islands stay on one row the whole time (they piled up a bar's height apart), the middle one centered; add a widget to the middle island while editing and it stays centered; with Bar steps aside on, a maximized window still makes them slide away afterwards
- [ ] Glass at Solid, then back to Matte, Frosted and Clear: each one comes back
- [ ] KDE apps (Files, Terminal, Calculator, Photos, Documents, Video, Music, Archives, Text Editor) and More settings wear Monet's glass app style: rounded fields, lily selection, glass at the edges; Files' status bar shows "9 folders" whole; the desktop's right-click menu is glass with rounded corners
- [ ] In More settings' first page, press Light, then Dark: the windows and menus keep Monet's style (they turned plain), and the title says "More settings"
- [ ] More settings â†’ Keyboard: hover Back and the menu button at 100% and 125% scaling, in Mist and Smoke. Their highlights stay above the header divider with a visible gap. Use the keyboard to return to the category list too. Repeat with matte glass and no glass.
- [ ] After a fresh install, open More settings from Settings â†’ Display: it opens at Display, and from Light & Wallpaper at Fonts. Its list has no Quick Settings, Wallpaper, Activities, Colors, Global Theme, Window Decorations, Icons, KDE Wallet or Software Update, and its groups say Display, Sound, Default Apps and Desktop (in your language too). From a Settings page with no KDE page of its own (Updates, say) it opens at General Behavior, never a page saying Plasma
- [ ] Change the wallpaper in KDE's dialog, the pointer and a font, then Settings â†’ Light & Wallpaper â†’ Monet's look â†’ Put back: in a few seconds the painting, Monet's pointer, fonts and glass are back, panels and files as they were
- [ ] On a desktop PC, Num Lock is on after signing in (not changed on a laptop); Windows+Tab shows all the windows
- [ ] Right-click the desktop: Create New, Paste, Undo, Icons, Open Terminal, Add or Manage Widgets, Display settings, Personalize, and nothing of KDE's dialogs. Display settings opens Settings on Display, Personalize on Light & Wallpaper (in your language too). The lock screen still shows the painting
- [ ] Mist to Smoke and back: the colors, frames and app style change together in about a second, and the bar and Settings don't stop
- [ ] Mist with Through the day on: the painting goes through the day into the night with the colors staying light; with Through the year, the season's painting. The Mist and Smoke cards say "Light colors all day" and "Dark colors all day"
- [ ] Files: under Devices, no nameless drive with a red bar, no "boot" and no "monet"; a USB stick and Windows' drive still show; no "0 B free" at the bottom
- [ ] Pick another font (More settings), then install an update of Monet: the font is still yours
- [ ] With two keyboard layouts, Windows+Space switches between them (from the next sign-in); Settings â†’ Mouse & Keyboard lists it, and Windows+Z
- [ ] A Word file written in Calibri opens in the office apps with the same lines and pages as in Word
- [ ] The resize arrows appear on a window's glass edge and a few pixels outside it, all along the sides and bottom, and the edge follows the pointer; windows look as before
- [ ] With Bar steps aside on, maximize a window: the islands slide away in the same glass they had (Clear, Frosted, Matte), never turning white first
- [ ] Maximize and restore (double-click the title): the window grows and shrinks smoothly, once (no double animation)
- [ ] A game in full screen, dragged windows on a second screen, and a window an app resizes itself (a video player's native size): nothing snaps or glides that shouldn't

### Install a game once (after 0.9.3)

- [ ] On a PC with Monet's Windows (or a kept one with Monet Bridge, no BitLocker): `findmnt "/run/media/Windows games"` shows Windows' `Games` folder, `ls /run/monet/windows-drive/c` is refused to the person and to a second account (root's only), and `findmnt -o OPTIONS /run/monet/windows-drive/c` says `rw`; Files' Devices doesn't list Windows' drive (a USB stick still shows), and `cat /run/monet/windows-drive.json` says `"state": "open"`
- [ ] After a trip to Windows that ended with Back to Monet, the next start opens it again; after Windows crashed or lost power, the state is `unclean` and Settings â†’ Games & Controllers says Windows wants to check its drive (Windows does at its next start, and the folder is back the start after)
- [ ] Settings â†’ Games & Controllers shows Windows games with Add to Steam (Steam closes for a moment and opens again); in Steam, Settings â†’ Storage lists `/run/media/Windows games`; signing out and in adds it by itself when Steam was closed
- [ ] Install a game that needs Windows (Apex Legends) in Steam here, choosing Windows games: it downloads while you keep using Monet; Games says Plays on Windows; Play restarts in Windows and Steam there starts it without downloading it again (a quick check of its files is fine)
- [ ] The first such trip: Steam in Windows lists `C:\Games` under Storage (it closed and opened by itself once); `C:\Users\<you>\AppData\Local\Monet\bridge.log` says it added C:\Games
- [ ] Install a game in Windows' Steam into C:\Games: back in Monet, Steam here lists it as installed and keeps it up to date; one that plays here (no anti-cheat) starts in Monet from there with Proton (its Properties â†’ Compatibility says Proton Experimental), and in Windows again afterwards without a download
- [ ] In Heroic, install an Epic game that needs Windows (Fortnite) into `/run/media/Windows games`: Games says Plays on Windows; at the next sign-in `Windows games/.monet/epic/Fortnite.json` and the game's `.egstore` appear; Play restarts in Windows, Epic's launcher checks the files once and starts it, with no download
- [ ] An Epic game installed in Epic's launcher in Windows elsewhere (C:\Program Files\Epic Games) keeps its own entry; uninstalling the Heroic one in Monet makes Epic's launcher forget it at the next trip
- [ ] Without Heroic, Settings â†’ Games & Controllers â†’ Shared with Windows has Epic and GOG games with Get Heroic: it says Getting Heroicâ€¦ and then Heroic opens to sign in; the row then says how to install into Windows games
- [ ] A GOG game installed by Heroic into Windows games plays on Windows (Play on Windowsâ€¦ from Settings) straight from its folder, with no launcher; `monet-bridge status` lists it as gog:<id>
- [ ] Windows' screenshots (Windows key + Print Screen) and Game Bar clips (Windows key + Alt + R) are in Monet's Pictures â€º Screenshots and Videos after the trip, gone from Windows, and a notification says so once with Show; a screenshot taken with F12 in Windows' Steam is there too, and still in Windows' Steam
- [ ] With bookmarks in Edge (and Chrome or Firefox) in Windows, and Zen not started yet in Monet: after a trip to Windows and back (or the first sign-in after Setup), Zen's first start has them, Edge's bar on Zen's toolbar (several browsers: a folder each). Settings â†’ Default Apps â†’ From Windows says how many, from which browsers
- [ ] A GTK 4 app from Flathub (Mission Center, say) in Monet's paper or smoke, the button that goes ahead in the sun, switches lily; the window buttons are signs with a dab of paint under the pointer (lily, ochre, the sun), page titles in Fraunces. `head -3 ~/.config/gtk-4.0/gtk.css` starts with `/* Monet:` and imports `colors.css` and `kde_window_geometry.css`; changing KDE's colors in More settings doesn't take it away
- [ ] Settings â†’ Storage â†’ OneDrive â†’ Connect: Microsoft's sign-in opens in the browser; after it, the card says how full OneDrive is, Files lists OneDrive among its places, and a Word file there opens (coming down as it's opened). After a restart it's there again without asking. A file Windows keeps online-only in OneDrive opens from here too. Disconnect: the place is gone, `~/OneDrive` is gone, and the files are still in OneDrive on the web
- [ ] Connect, then close the browser without signing in and press Cancel: the card shows Connect again with no complaint, and `rclone listremotes` lists nothing
- [ ] With Zen already used: Add to Zen leaves Bookmarks from Windows in Downloads and opens Zen's bookmarks; Import and Backup â†’ Import Bookmarks from HTML adds them beside Zen's own. The Passwords row's Show the folder opens Shared with Windows; a CSV exported there from Edge imports in about:logins
- [ ] On a Windows with a second account (another person's), their screenshots stay in Windows, and F12 screenshots of a Steam account you don't use in Monet don't come over; `ls -ld /run/monet/windows-drive/c` and the shared folder's files are the person's alone (another account here can't read them)
- [ ] Settings â†’ Games & Controllers â†’ Needs Windows: a game in Windows games says it's ready there, with Play on Windowsâ€¦

### Older PCs and laptops

- [ ] `/usr/libexec/monet-quick older-pc` says `yes` with 8 GB of memory or less (or a hard disk), `no` otherwise
- [ ] On an older PC: `~/.config/monet/glass-lite` is there, Steam opens about 45 s after the desktop, and `kreadconfig6 --file baloofilerc --group General --key "only basic indexing"` says `true`
- [ ] Sign-in: `systemctl --user list-timers` shows `monet-after-sign-in` for a minute only after something changed (the first sign-in after an update, or an app installed while signed out); signing out and in again with nothing new shows none
- [ ] A normal start: `systemctl status monet-ready-boot monet-keep-prepare` say "condition unmet", and Settings â†’ About Monet â†’ Last start shows where the start's time went
- [ ] On a laptop with an NVIDIA chip beside the built-in graphics: a game from the Store's Play row (Prism Launcher, RetroArch) runs on the NVIDIA chip (`nvidia-smi` lists it), while the desktop and Steam's window don't

## 2. Switching

Time with a stopwatch, from the click to the moment you can play.

| Test | Laptop | Desktop |
|---|---|---|
| Monet â†’ Windows desktop | | |
| Play on Windows â†’ game menu | | |
| Quit game â†’ Monet desktop | | |
| Back to Monet shortcut â†’ Monet desktop | | |

Targets: under 30 s into a game, under 20 s back to Monet.

Settings â†’ About â†’ **Last start** shows where the time went on the way back:
the PC's own start (firmware), Monet's (loader, kernel, system), and your
desktop (from signing in until it's there). Note them for both PCs:

| Last start | Laptop | Desktop |
|---|---|---|
| The PC | | |
| Monet | | |
| Your desktop | | |

### Ready when you come back

Turn it on in Settings â†’ Play on Windows, then Play on Windows and come back.

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
- [ ] Settings â†’ About Monet â†’ Get BoxBuddy installs and opens it (an administrator's yes for Flathub); it makes a container with a terminal, where `dnf install` works
- [ ] BitLocker turned on in a Windows that has Monet Bridge (Settings â†’ Privacy & security â†’ Device encryption on, or BitLocker on a Pro): after encryption finishes and Windows restarts once, the next start of Monet opens Windows' drive by itself, Settings shows no key to type, and `ls /boot/efi/EFI/Monet` (or the EFI partition) has no `bitlocker.json` left. Also on Windows 11 Home
- [ ] BitLocker (device encryption on a Windows 11 laptop): Settings â†’ Games & Controllers â†’ Shared with Windows asks for the recovery key. A wrong one says so; the right one (from aka.ms/myrecoverykey) opens it: Monet Bridge is staged and installs at Windows' next start, then games, files and Wi-Fi work in both. After a restart it opens without asking (`ls /var/lib/monet/bitlocker` as root shows one `.cred`). Windows still starts normally afterwards, without asking for its recovery key
- [ ] Unplug the charger while switching (laptop): does everything still work?
- [ ] Start Windows from the firmware boot menu instead of Monet: does it behave normally?
- [ ] Uninstall a game in Windows, then press Play on it in Monet: is the message clear?
- [ ] Clock: is the time right in both systems after switching a few times?

## Store downloads and recovery

Implemented 2026-10-27; pre-change VM checkpoint: `ai-before-store-downloads-1027`.
The Store saves each request before starting a separate user-service worker. A file lock
allows one transaction at a time; repeated clicks/workers cannot install the same job twice.
Flatpak keeps its partial downloads and owns deployment safety. Cancellation uses
[Gio.Cancellable](https://docs.gtk.org/gio/method.Cancellable.cancel.html) with
[Flatpak transactions](https://docs.flatpak.org/en/latest/libflatpak-api-reference.html);
the UI waits for cleanup and checks success against the exact installed app reference.
Closing Store keeps work running. A lost worker becomes **Interrupted** with **Retry**;
reopening or signing in does not automatically repeat removals. Completed requests offer
Open/Dismiss; failed/cancelled requests keep their app reference and installation for retry.

Automated: `python tools/vm.py tests tests.test_store_downloads tests.test_look.OurOwnStore
tests.test_store_frame_regressions tests.test_settings_feedback`. The 41 selected tests pass
with three Node-dependent skips; those three pass separately on Windows. Checks cover private
atomic state, duplicate workers/clicks, cancellation races, exact removal retries, lost workers,
reboot-style stale requests, malformed data, startup failure, injected ENOSPC writes, catalog
independence and Return/Space on queue controls. The existing catalog/shortcut/Settings checks
remain green. Unreadable state is kept rather than silently overwritten.

Live in the Monet VM, Firefox was initially absent. Its real Flathub download was cancelled
from the app page. Retry continued after Store closed, and reopening Store recovered its state.
Killing only that test worker produced an Interrupted request. A worker-only unreachable proxy
produced the connection error without changing the VM's network settings. Retry from Downloads
then installed Firefox successfully; Flatpak confirmed the reference. Remove through Store
completed successfully, returning the installed-app list to Zen alone. Test requests were dismissed.

Still required before release:

- [ ] Full reboot/power-loss testing during download and commit on a disposable installation.
- [ ] Real disk exhaustion during download, deployment and queue write; clear space and retry.
- [ ] Standard/administrator accounts, denied authorization and alternate Flatpak installations.
- [ ] Screen-reader, large-text, RTL and fractional-scale checks for the queue and app controls.

Current bounds: 100 requests, one job per app, one active transaction, explicit retry after
failure/reboot, and Flathub app install/remove only. This is not a pause/resume-by-byte API;
Flatpak decides which cached objects it can reuse. A cancellation can remain pending during
native cleanup. Updates and Windows game downloads use their existing flows.

## Upgrade preservation and profile recovery

`monet-profile` owns only the values Monet has written. `monet-look --keep` no longer
applies the global theme first. Existing unknown values, explicitly empty values, disabled
bindings and deleted owned values stay untouched. The former `look-written` ledger is
imported only when it matches the current value. Generated launchers use a three-way merge:
custom names, icons, commands, localized fields and removed shortcuts survive later updates.
Removed launchers stay removed. Known obsolete Store commands are repaired, but customized
commands and arbitrary file URLs are not redirected by dock repair. Panel order is retained.
Pre-desktop menu/tray defaults and maintenance jobs follow the same preservation policy.

Sign-in records a migration by its helper contents and arguments, rather than only the
marketing version. It records success only after successful writes. Failed/interrupted runs
remain inspectable and retryable; a previously applied revision is not replayed after a newer
one. This protection applies to releases that include the new updater, not older binaries.
An explicit **Put back** still restores Monet's appearance by request.

The private, atomic journal is `$XDG_STATE_HOME/monet/profile/state.json` (normally
`~/.local/state/monet/profile/state.json`, mode 0600). On an updated image, run these as the
affected account, without sudo:

```sh
/usr/libexec/monet-profile status
/usr/libexec/monet-profile rollback RUN_ID
```

Use a run ID from `status`. Undo restores managed keys/files only when they still match the
migration's output; later edits and symlinks are reported as conflicts and left untouched.
Undo is repeatable and blocks that revision from immediately reapplying at sign-in. The four
previous completed histories are retained alongside the newest run; failed/interrupted and
conflicted histories are retained. The record is bounded to 8 MiB and fails without discarding
its contents when full or corrupt. This is not a document backup or full desktop snapshot:
live compositor operations, light synchronization, third-party application state and system
deployment rollback have their own mechanisms. Recovery has a command-line interface for now.

Automated checks use KDE's real configuration tools in isolated profiles:
`python tools/vm.py tests tests.test_profile_upgrades tests.test_store_frame_regressions
tests.test_look`. They exercise customized and disabled settings, legacy records, launchers,
two repeated runs, separate command arguments, an older applied revision, failed writes,
a process killed just after a write, private journal permissions, corrupt state and undo
conflicts. JavaScript checks skipped without Node in the VM run separately on Windows with
`python -m unittest tests.test_store_frame_regressions.WindowGeometry`.

Validation on 2026-10-27: 409 checks passed in the broad upgrade/look suite with four
dependency skips. Four Settings feedback checks passed in a separate Qt process, and the
three JavaScript checks passed on Windows. The final shortcut-preservation adjustment also
passed all 21 Linux checks in the profile/Store regression suite.

Live check on 2026-10-27: checkpoint `ai-before-upgrade-preservation-1027`; updated helpers
installed in the VM's existing user test bench. The first migration completed, and the second
used its receipt. All pre-existing values in eight desktop configuration files, launcher
names/icons/commands/shortcuts, Monet preferences and panel configuration matched their before
snapshot. Open apps were kept running. The prepared recovery record had mode 0600.

Release gates still open:

- [ ] Install a new system image over a customized existing installation; restart and sign in twice.
- [ ] Boot the previous system deployment and return to the newer one; compare preferences and pins.
- [ ] Test actual power loss and disk exhaustion while updating the image and profile.
- [ ] Verify normal/administrator accounts and the graphical recovery route.

### Desktop scaling and calendar accessibility

The desktop coordinator uses Plasma's logical work area, preserves the arrangement for
each size during the session, and saves positions through Plasma's normal layout store.
It respects widget minimum sizes and fits the middle bar between the two side bars.
The calendar and clock share an inward-opening notes panel; opening it does not resize
or reposition the month. Notes retain the legacy date-to-text format for one-off entries;
repeating entries store text and `repeat: daily`, `weekly`, `monthly` or `yearly`. Writes are
serialized and atomically replaced. A failed save retains the pending edit and exposes Retry.
Editing or deleting an occurrence changes the series; changing the interval starts it on
the selected date. Monthly notes skip months without that date; 29 February yearly notes
appear only in leap years. Weekly notes follow calendar days across daylight-saving changes.

Automated checks: `python tools/vm.py tests tests.test_accessible_desktop tests.test_look`.
On 2026-10-27, 399 checks completed successfully (one dependency skip), including real QML
keyboard input, native-position animation handling, returning to the earlier layout, yearly
occurrences, leap days, legacy notes, empty-note deletion and failed-write preservation.
Translation extraction/check also passes; new untranslated strings fall back to English.
The final 11 focused checks also pass, including reopening/dismissing the shared notes
dialog without breaking the calendar's visibility binding.
The repeat-options extension passes 17 focused checks, covering all four intervals,
short months, century leap-day gaps, chronological Coming up entries, existing-note
precedence, interval changes, persistence, and keyboard selection of every option.

Live VM checks (checkpoint `ai-before-accessible-layout-1027`):

- [x] 1920Ã—1080 at 100%, 125%, 150%, 175%, 200%, then back to 100%: all four desktop
  widgets stay inside the work area without overlap; bottom bars have separate intervals.
- [x] Reopening Plasma preserves the layout; weather forecasts remain inside their card.
- [x] Both notes panels open toward the screen centre and keep their month stationary,
  including at 200%; panel placement calculations also cover negative monitor origins.
- [x] Type a temporary note, Tab to repetition, select Every year with the keyboard,
  see it in both calendars and Coming up, then clear it. Existing notes remain intact.
- [x] Add a weekly note in the desktop calendar and open its next Tuesday occurrence.
  Open the same note from the clock, use the keyboard to change it to daily and monthly,
  and verify both calendars and Coming up update. Reopen the monthly note: its interval
  persists. Remove the test series; the existing note remains intact.
- [x] Escape returns from a note to the clock's month; Enter reopens it, and clicking
  outside dismisses both. The decorative clock fits its width as the time changes.
- [ ] Mixed-scale physical monitors, changed font metrics, hotplug and docking.
- [ ] Complete Orca, large-text, high-contrast, reduced-motion and RTL audits through
  Settings, Store, Games and the app menu. Calendar keyboard support is the first slice.

An arbitrarily crowded desktop can exceed the space available: fallback keeps its widgets
reachable but cannot guarantee separation in that case. Screen-reader announcement quality
and real hardware behavior are release checks, not established by the VM results.

### More Settings and Store paintings (2026-10-27)

More Settings loads a private Qt proxy style, preserving the chosen base style.
Its native module containers report their layout minimum instead of allowing
explicit undersized minima to clip fields. Forms may wrap long rows, top tabs
have padding above and below, and Shift+wheel pans a wide module from its fields.
Kvantum's scrollbars reserve space and stay visible whenever content overflows.

Validation: 26 focused Python checks (`tests.test_more_settings`,
`tests.test_look.AppStyle`, `tests.test_look.OurOwnStore`) pass. The CMake/Qt
layout suite also passes: complete scroll range including dynamically added
pages, keyboard End, Shift+wheel over a field, wrapping rows, frameless tab
spacing and preservation of intentionally fixed widget widths. Linux packaging
builds and runs this suite before including the private plugin.

Live VM checks (checkpoint `ai-before-settings-layout-1027`):

- [x] Network â†’ General at 100% and 125%: scroll to the right with mouse and
  keyboard; every control's right edge and dropdown arrow is reachable.
- [x] Audio CDs: clear space between header, tabs and form; the last encoder
  tab remains reachable, with visible horizontal and vertical scrollbars.
- [x] At 200%, maximize More Settings: both scrollbars and Apply/Reset remain
  reachable. Restore the original 100% scale after checking.
- [x] Store category paintings at 960px and maximized 1920px: the selected banner
  details remain uncropped by the UI and have rounded corners.
- [x] Close the test instance and use Monet Settings â†’ More settings: the
  process loads the installed private plugin through the normal launcher.

The Store art was subsequently replaced at the user's request with actual Claude
Monet paintings: The Bridge at Argenteuil (1874), The Japanese Footbridge (1899),
The Seine at Giverny (1897), The Artist's Garden in Argenteuil (1873), and Jerusalem
Artichoke Flowers (1880). Five additional works give the remaining categories their
own art: Palazzo da Mula, Venice (1908), Waterloo Bridge, Gray Day (1903),
The Houses of Parliament, Sunset (1903), Rouen Cathedral, West FaÃ§ade (1894),
and The Artist's Garden at VÃ©theuil (1881). All ten museum reproductions come from the National
Gallery of Art's CC0 open-access collection. `branding/store/sources.json` records
their titles, accession numbers, source URLs and 2400Ã—800 crop coordinates;
uncropped reproductions are kept in `branding/store/sources`. The category
associations are curatorial choices for Monet OS, not historical claims about
the paintings. `tools/make-store.py` preserves source pixels and embedded sRGB
profiles, exports the same art for both appearance modes, and bundles
`ARTWORK-CREDITS.txt` with the installed Store. No generated additions or color
filters are used. All ten PNG details match their source crops exactly; all
30 JPEG banners decode at the expected size and have matching light/dark bytes.
The existing front-page asset check passes. Games and Music & video have also
been visually checked in the running Wayland VM with the new paintings, followed
by Writing & office after the category expansion. Generated alternatives were
rejected by the user and are not included in the source or installed Store.

### Everyday bar and shared weather (2026-10-27)

The bar uses the same Monet weather widget as the desktop, with a compact painted
sky and temperature button. Its popup uses the panel's glass without a second
opaque card, and has bounded width and height. `monet-weather` stores one private
location list and unit preference in `~/.config/monet/weather.json`, seeded once
from the existing Monet widget. Both views watch those preferences and the cached
Open-Meteo forecast. Cache keys include the coordinates and temperature unit;
requests are serialized, and a location change during a request cannot show the
old place's forecast. Failed requests keep the last forecast, show its age, and
can be retried. The wallpaper's location also reads the shared preference first.

Fresh layouts and a one-time explicit adoption of Monet's look enable network
and Bluetooth status in the bar, keep notifications, battery, removable devices
and clipboard access, and remove duplicate weather/sound/brightness widgets,
Input Method, Display Configuration, lock-key indicators and Vaults from the
default tray. Keyboard-layout switching and camera/privacy indicators remain.
Only the Xwayland Video Bridge status icon is disabled; its compatibility service
continues running. Display and input-method controls remain in Settings/More
settings, and all tray entries can be enabled in Configure System Tray. Existing
custom app entries are retained; `monet-look --keep` does not reapply this policy.

Validation: eight focused weather/tray tests pass, plus 34 existing widget,
sound, tray and profile-preservation checks. Live checks cover migration of
Stockholm, changing Celsius to Fahrenheit from the bar and seeing both views
update, and the configuration dialog's Cancel and OK behavior. Celsius was
restored afterward. The cleaned overflow menu and panel bounds were checked at
100%, 125% and 200% scaling; weather popup bounds were checked at 100% and 200%
on the 1920 by 1080 VM display. The test leaves scaling at 100%.
The VM has wired networking and no Bluetooth adapter; Wi-Fi radio control,
Bluetooth pairing and laptop battery behavior still require real hardware.

### Hourly and weekly weather details (2026-10-27)

The desktop card and bar now open the same `WeatherDetails` component. It shows
24 hours ahead, all seven days, and the hours for a selected day, using the existing
painted sky and themed popup glass. It includes precipitation probabilities,
feels-like temperature, wind, update time and sunrise/sunset. Hour pages have
explicit buttons; the week scrolls vertically with a visible scrollbar. Tab focus
reveals off-screen controls, Page Up/Down scroll and Escape closes the view.
Reopening resets to current weather. Forecast times stay local to the chosen city.

The cache upgrades from five-day summaries to a versioned seven-day/hourly response.
Incomplete responses cannot replace the previous complete forecast. Offline refresh
keeps the cached result with an error and retry; an old summary remains usable while
hourly details are unavailable. Missing values display an em dash rather than zero.

Validation: 13 shared-weather/tray/presentation tests and 15 existing desktop-widget
tests pass. Live VM checks cover both entry points at 100% and 200%, selecting a day,
the complete seven-day list and sunrise/sunset, keyboard focus scrolling, choosing
Oslo through the bar, and Fahrenheit with matching hourly temperatures/wind units.
Stockholm and Celsius were restored. Wallpapers were not edited. Restarting Plasma
at high scale exposed a separate widget-position persistence regression, tracked
under everyday polish item E in PLAN.md; ordinary scale changes alone had passed.

### Workspace return and overlapping app launches (2026-10-28)

Seventy-one targeted recovery and return-Settings tests pass. They include launching a fast
app while another is unresponsive, starting the editor before browser verification, sixteen
apps surviving capture/receipts, waiting for startup resizing, real Qt JavaScript evaluation
of desktop assignment and stacking/focus, and avoiding focus changes after user interaction.
Existing Files/browser retry, privacy, cancellation and durable-receipt checks remain green.

In the Monet VM, a controlled return reopened two test apps and a real saved KWrite document
across two virtual desktops. Geometry, minimized state, virtual desktop, stacking and active
window matched the captured values. The measured restoration phase was 2.07 seconds; this
does not include boot or a real Windows switch. An initial run exposed a Wayland startup
resize race; waiting for two stable observations fixed it and the repeated live run passed.
The test desktop/apps were removed afterward; existing minimized user windows and calendar
notes were preserved. Evidence is in `/tmp/monet-workspace-live-return.log` and
`/tmp/monet-workspace-tests.log` in the VM. Checkpoint: `ai-before-workspace-return-1028`.

The Linux-target Rust check passes for stopping the switch if checkpoint saving fails.
Translation catalog generation/check pass (1669 texts). This CLI guard needs a rebuilt
system image for an actual switch test; the live bench tests exercise the recovery helpers.

### Recovery after long Windows sessions (2026-10-28)

`python tools/vm.py tests tests.test_trip_lifetime tests.test_resume tests.test_return_summary
tests.test_files_session tests.test_browser_session tests.test_workspace_return
tests.test_look.YourAppsAgainAfterWindows` passes 78 checks without skips. In the same Linux VM,
`cargo test --workspace --locked` passes all 63 Rust tests. Linux-target Clippy and translation
catalog checks pass. Tests use isolated checkpoints and fake firmware, without restarting
the VM or changing its installed helpers.

Version-3 recovery matches the checkpoint and departure boot to a durable system return
receipt. Tests cover a month in Windows, a backward clock adjustment, same-boot rejection,
wrong/missing receipts, interrupted receipt writes, failed restart cleanup and partial
recovery across later trips/reboots. Off, Dismiss, legacy expiry and completed-launch
deduplication remain covered. System receipt failures retain retry evidence and put Monet
first again even when Windows had been placed first.

Release checks still required with a rebuilt image containing both CLI and helpers:

- [ ] Complete Monet → Windows → Monet after more than twelve hours, including Windows updates
  and a period powered off; confirm documents/tabs and window state, without duplicate apps.
- [ ] Interrupt recovery, restart Monet, and retry only pending work.
- [ ] Block/cancel a restart and then perform an unrelated reboot; do not replay that checkpoint
  or leave Windows selected.

### Unsaved work and cancelled switches (2026-10-28)

The recovery command above plus `tests.test_departure` passes 82 checks without skips and
six additional Qt cases in an isolated process. All 65 Rust workspace tests, Linux-target
Clippy and translation catalog checks pass. Tests cover veto/wait without a forced timeout,
only one close request per window, a new window before acceptance, failed inspection,
Cancel during a nested Qt event loop, Escape, exact checkpoint recovery on the same boot,
root EOF/malformed replies and the no-boot-target-before-acceptance ordering.

Live VM evidence, from checkpoint `ai-before-unsaved-switch-1028`:

- An isolated saved KWrite document was modified without saving. Its native close prompt
  appeared; pressing Cancel left the process and unsaved text intact. The worker stayed
  blocked for 172 seconds and did not send an acceptance.
- Escape in Monet's switch window sent EOF. The terminal that had already closed reopened
  once; the original editor PID stayed unchanged. The visible status said the switch was cancelled.
- Retrying and choosing Save persisted the changed text before the worker sent one acceptance.
- A simulated restart failure reopened the saved document and kept the error visible.
  The original notes checksum remained `f977db373d159cf87d95b94c5745fa5418fe237c57dca0415dc606064cb50d95`.

The root endpoint was a stand-in recording the production pipe protocol; it could not touch
firmware or reboot. The VM was restored afterward. A separate inhibitor probe was denied
interactive authorization, so its dry run does not validate actual inhibitor handling.

- [ ] Repeat with a rebuilt image and real privileged helper, including failed firmware/reboot
  requests, active logind shutdown inhibitors and another signed-in user's work.
- [ ] Test browser form/download warnings, office documents, native X11 apps and unresponsive apps.
- [ ] Verify screen readers, RTL and small/scaled screens with save dialogs and the Cancel button.
- [x] Extend document recovery to paths first saved with Save As during close prompts for
  uniquely owned Kate/KWrite native sessions (2026-10-28); shared anonymous sessions remain.

### Multiple windows and browser profiles (2026-10-28)

Run the existing recovery modules plus `tests.test_multi_restore`, `tests.test_departure`
and `tests.test_words`. For headless Qt tests over SSH, set `QT_QPA_PLATFORM=offscreen`.
This slice passed 102 tests plus seven isolated Qt cases, syntax and catalog consistency checks.
The new cases cover per-group receipts, partial return/retry, duplicate folder windows,
source-window identity during cancellation, independent browser profiles and Zen's native
sidebar synchronization without weakening actual-tab verification.

Live VM checks from `ai-before-multi-restore-1028`:

- [x] Three Files windows, with identical folders in two windows, duplicate tabs and split
  folders: close two, retain one, restore the missing pair and verify their distinct positions.
- [x] Leave the surviving Files window's original ID/PID unchanged; Retry creates no duplicates.
- [x] Two isolated Zen profiles with three normal windows, pinned tabs and a private window:
  use native Quit, reopen both profiles, verify normal window counts and native tab digests.
- [x] The private window stays closed and browser preferences remain unchanged.
- [x] Restore a missing two-window profile while the other profile keeps its original PID.
- [ ] Repeat the whole installed-image Monet → Windows → Monet flow on hardware.
- [ ] More browser families, browser spaces/splits, display changes and unusual same-process
  Files windows; editor document-to-window grouping remains separate work.

Disposable fixtures live under `~/.local/state/monet-multi-test-1028` and browser profiles
named `monet-multi-*-1028`. Marionette is confined to those test profiles. The user-facing
browser Quit path was exercised through the VM keyboard; production enables no debug access.
Host screenshots use `%TEMP%/monet-multi-*.png`. Restore the checkpoint after collecting evidence.
The checkpoint was restored after this run; the original session returned and the notes
checksum was unchanged. Host evidence is `%TEMP%/monet-multi-evidence.log`.

### Weather button highlight (2026-10-28)

The compact weather button now centers a natural-sized icon/temperature row inside
its padded control area. Its hover background follows the themed active area's
horizontal inset; Plasma alone paints the expanded highlight, avoiding two
overlapping backgrounds. Extra horizontal padding keeps both the cloud and the
temperature comfortably inside that highlight.

Live checks in the Monet VM cover hover, opening/closing the forecast, and the
expanded button at 100% and 200%. No weather QML errors appeared in the Plasma
journal. The VM was returned to 100%; calendar notes and wallpapers were unchanged.

### Microphone controls in the bar (2026-10-27)

Sound now shows the selected microphone, verified mute state, an explicit mute/unmute
button and input choices when more than one source exists. Audio capture filters
(such as a noise-reduced microphone) are included; video sources and capture streams
are not. The helper validates the displayed microphone ID before muting/unmuting,
reads the actual result back, and returns an error instead of optimistic success.
The popup has bounded height, vertical scrolling and focus-following scroll behavior.

Six focused helper/bar checks pass, covering source parsing, unplugging, denied
changes, changed defaults and rejection of non-input IDs. In the VM, temporary
null-speaker/remapped microphone nodes verified selection between two sources,
mute and keyboard unmute against `wpctl get-volume`, no-device presentation,
and layout at 100% and 200%. All three test modules were unloaded and the original
default-source setting restored. Physical microphones and Bluetooth headsets remain
hardware checks. The VM was returned to 100% and its original widget arrangement.

### Widget arrangements after a scaled restart (2026-10-27)

The layout guard now persists bounded, validated arrangements per desktop and logical
screen size in `monet/widget-layouts.conf`. It loads them before capturing startup
geometry, so restarting Plasma at a larger scale cannot replace the original layout
with temporarily resized widget positions. Plasma's `isUiReady` flag remained false
in the live VM and is not used as a startup gate; the layout's relayout lock and
settling timer protect restoration instead.

Nine desktop UI tests pass, including a fresh QML-engine restart at 200% followed by
return to 100%, animation-safe placement, all supported scale steps, recurring notes
and keyboard calendar operation. Live VM checks confirm that all four widgets stay
on screen without overlap after restarting Plasma at 200%; their complete 100%
geometry records then match the saved baseline exactly. The settings file contains
both arrangements. All local widget copies use the updated guard, and the desktop
was left at 100%. Wallpapers were not edited. Mixed monitors, hotplug and a complete
sign-out/reboot remain hardware/release checks.

### Notification controls and focus-timer preferences (2026-10-27–28)

Notifications offers one hour, four hours and tomorrow at 08:00 local time, with
the actual deadline shown in Settings and a compact caption in Quick Settings.
Expired settings read as off. Hour durations align with Plasma's minute clock;
tomorrow remains 08:00 across daylight-saving changes. Settings serializes requests,
verifies the actual value, keeps failure/Retry visible and reserves feedback space
so the controls do not move when a change completes. Tab focus scrolls controls into
view. Per-app muting changes popup permission without changing history preferences.
Sound configuration opens the native per-app controls: Plasma's temporary
`NotificationSoundsMuted` marker is no longer exposed as a global sound preference.

Focus timers now keep an existing longer quiet period and restore the previous
value only while they still own the setting. A later manual choice wins, including
changes outside Monet Settings. A private, atomic record survives helper/Plasma
restarts, distinguishes overlapping timer widgets and preserves the first timer
if a second timer's write fails. Rapid start/pause/resume requests are serialized
and coalesced to the latest intent.

Validation: focused helper and QML tests cover deadlines, time zones, failed or
immutable writes, expiry, real Settings buttons and keyboard scrolling, overlapping
timers, restart recovery, newer manual choices and request ordering. Live VM checks
cover notification controls at 100% and 200%, native inhibition and expiry, per-app
muting and grouped history, plus the compact "Until tomorrow" bar caption. Real
KConfig writes confirm that focus preserves pre-existing and newer manual choices
and the remaining timer. Starting and resetting the actual Timer widget preserves
the previously selected one-hour deadline. The VM is left at 100%, with manual
quiet off and test timers closed; wallpaper artwork and appearance choices remain
unchanged.

The native popup/history findings from this pass are addressed by the next slice
below. Native app discovery still records an app when its first popup is shown,
not merely when a notification arrives during quiet time. Further accessibility
and real-hardware checks remain release work.

### Native notification retention and muted messages (2026-10-28)

`image/notifications` builds the existing Plasma notification applet with minimal
QML policy changes. Dismissing a non-transient critical popup marks it expired in
the native model without closing the sender's notification, preserving available
actions in history. The tooltip says **Dismiss to history**. Messages from muted
apps/services are placed in history immediately; unmuting cannot replay them.
Muted transient messages are closed, and native history exclusions still apply.
The native applet identity, daemon, C++ implementation, grouping, replies and job
UI are retained. History remains session-local and actions depend on the sender.

Validation on Plasma 6.7.5 / Qt 6.11.2 in the Monet VM:

- [x] Built the exact-version applet with the new QML and loaded it through a
  temporary `QT_PLUGIN_PATH` service override; confirmed the loaded binary.
- [x] Dismissed a critical popup, reopened Notifications and activated its Open
  button. The still-running sender received `open` after dismissal.
- [x] Sent normal and critical messages while the app was muted. Unmuting showed
  no old popups; grouped history retained both, and the critical action worked.
  A new message after unmuting appeared normally.
- [x] Popup/history stayed inside the screen at 200%. Clear History removed the
  two remaining test messages; reopening history at 100% showed it empty.
- [x] `tests.test_notification_bundle`,
  `tests.test_notification_policy.NotificationPolicyProcess`,
  `tests.test_notifications` and `tests.test_settings_feedback` pass: 28 outer
  tests, including a subprocess running eight checks against Plasma's real model
  on an isolated D-Bus session. These cover muted actions, service muting,
  transient messages, history filters and native ClearExpired. They also cover
  muting several active messages at once and replacing an existing message:
  its body/actions update in history without reappearing as a popup, matching
  Plasma's native replacement semantics. Seven delivery
  checks reject mismatched runtimes/plugins, damaged files, missing libraries
  and unsafe destinations, and preserve an existing file after a failed copy.
- [x] CMake install stripped the temporary sysroot library path. Captured and
  verified the real VM's runtime manifest, sealed the binary/source bundle, and
  exercised installation with its final writes redirected to a private staging
  directory. The complete patched upstream source and licenses are bundled.
- [x] Removed the temporary plugin override and test notification preferences;
  `plasmanotifyrc` matches its original empty backup. Plasma again loads the
  system applet. Scale is 100%, the four original widget positions are intact,
  and wallpaper artwork/preferences were not changed by this work.
- [ ] Build and boot the complete Monet image on both supported image variants.
  The new Containerfile stage derives from the final runtime, rejects dependency
  drift and verifies the bundle before replacing the native plugin. Its full
  package-install/image pipeline has not yet been exercised.
- [ ] Review distributor patches when moving to another Plasma release, and
  validate native replies, jobs, screen-reader navigation and real hardware.

The native fix is integrated into image sources, not permanently installed over
the VM's immutable system plugin. Its test build is in
`/tmp/monet-notifications-build`; logs are `build-install.log`, `install.log` and
`/tmp/monet-native-delivery-tests.log`. The general Linux tarball deliberately
does not carry a binary tied to one image's Plasma version.

### Everyday-language search (2026-10-28)

Settings and the app menu use `monet-quick search` with a shared catalog of 14
navigation destinations. English and translated aliases are matched together,
ignoring accents/case and optional question words. Result IDs are allowlisted;
queries cannot become commands. Settings supports `PAGE#CONTROL` links, scrolls
the destination into view and gives it visible keyboard focus. Calendar results
open the existing Monet calendar with its shared notes through `plasmawindowed`.
The Windows-files destination explains unavailable/locked/asleep states and only
offers Open folder when the current account can access the actual shared folder.

Validation:

- [x] `tests.test_everyday_search`, `tests.test_notifications.NotificationUI`
  and `tests.test_settings_feedback`: 24 checks pass in the VM. Sixteen are search
  checks, including the real Settings UI and the real menu representation with
  inert native app models. They cover immediate Enter, stale responses, failure
  and same-query retry, safe routes, translated aliases, missing audio hardware,
  narrow/wide row transitions and focus returning from a long native result list.
- [x] The menu's ListView focus-scope handoff now focuses the native delegate:
  focusing only the view could return focus to its last active suggestion.
  Returning to suggestions uses their content coordinates, so they remain visible
  after scrolling. A failed suggestion lookup cannot auto-launch a native result.
- [x] In the live VM, "make text bigger" opened and focused Size of everything;
  "headphones" opened Sound; "birthday" opened the shared calendar and showed
  the existing note. Settings Ctrl+F, "Windows files", Enter opened the actual
  Storage explanation for a VM without Windows configured.
- [x] At 200%, Settings results and destination controls fit, including Windows
  files and the no-audio-device explanation. Arrow keys moved from the menu's two
  headphone suggestions into native results and back; Enter opened the selected
  Monet result. Scale returned to 100%, all four original widget positions remained,
  the original Settings window-size file was restored, and the calendar host config
  and note-file checksum were unchanged. No wallpaper artwork/preferences changed.
- [x] Translation extraction/build and `tools/make-translations.py --check` pass.
  New messages/aliases are available for translators; this is not a claim that
  every new phrase has been translated into every supported language.
- [ ] Validate a real Windows shared folder and locked/sleeping drive states on
  dual-boot hardware; backend tests cover these states without mounting drives.
- [ ] Review real screen-reader navigation, translated phrases and RTL layouts.
  Native KRunner ranking is unchanged and can still include weak suggestions.
  The standalone calendar retains Plasma's host window; this slice does not
  introduce a separate calendar application.

The existing VM bench helper, Settings and menu copies were updated for the live
check; this is not an image/release installation. Their prior copies are at
`~/.local/state/monet/search-polish-backup-20261028`. Test logs are
`/tmp/monet-search-tests.log`; screenshots on the host include
`%TEMP%/monet-size-ready.png`, `monet-settings-files-200.png`,
`monet-menu-headphones-return-200.png` and `monet-sound-200-ready.png`.

### Return summary and recovery actions (2026-10-28)

The focused run passed **90 checks** without skips:
`tests.test_return_summary`, `tests.test_resume`, `tests.test_files_session`,
`tests.test_browser_session`, `tests.test_everyday_search`, `tests.test_settings_feedback`,
`tests.test_look.YourAppsAgainAfterWindows` and `tests.test_look.GamesTheApp`.

- [x] Durable outcome tests cover completion, missing-app reinstall/retry, stale trip buttons,
  expired/same-boot checkpoints, malformed summaries, interrupted summary writes, actual-lock
  busy state, dismissal and partially missing editor files. Browser tests distinguish verified
  tabs from normal startup and private-session exclusion.
- [x] Actual Settings QML tests cover repeated keyboard actions, persistent failure/retry,
  stale refreshes after dismissal, polling focus preservation, direct Tab entry into the card,
  narrow rows and literal filenames. The Games restart explanation and buttons fit a
  760×520 window without invoking any switch.
- [x] Live VM: saved test document reopened; missing document/app were reported honestly.
  Review return in notification history opened Settings at the card. After installing a
  controlled test app, Retry pending opened it once without reopening the existing editor.
  Open app raised its existing window. Dismiss by keyboard at 200% forgot recovery metadata
  while preserving the saved test document. Both 100/200% layouts were inspected.
- [x] Returned to 100%; original widget positions and notes checksum were unchanged.
  Restored Settings' previous size file and removed the controlled launcher/processes.
  No wallpaper artwork or preferences changed.
- [x] `cargo check -p monet --bin monet --target x86_64-unknown-linux-gnu` and translation
  extraction/build/check pass. The Linux binary cannot be tested with a Windows-native
  `cargo test`; that attempt fails on its existing Unix-specific APIs. Cross-checking is
  compilation evidence, not a Linux runtime or reboot test.
- [ ] Real Monet → Windows → Monet round trip, real interruption during reboot, measured
  switching time, other user accounts, screen readers and translated/RTL presentation.
- [ ] Explicitly reopen missing editor documents after reconnecting a drive, preserving
  existing tabs; the current recovery UI directs the person to the app and Backups.

Bench backup: `~/.local/state/monet/return-polish-backup-20261028`. The live fixture uses
`/tmp/monet-return-live-20261028/state`, separate from the user's real recovery state.
Logs: `/tmp/monet-return-suite.log`. Host screenshots include
`%TEMP%/monet-return-card.png`, `monet-return-result.png`,
`monet-return-reloaded-ready.png`, `monet-return-tab-fixed.png` and
`monet-return-dismissed.png`. The installed image/boot binary was not replaced.

### Dragging empty app backgrounds (2026-10-27)

Settings, Store and Games share a background drag surface behind their controls.
An unmodified left-button drag starts the compositor's normal window move after
the platform drag threshold. WheelHandler and Flickable leave blank mouse presses
to that surface; wheel, touchpad and touchscreen scrolling remain available.
Qt versions before 6.9 retain their previous mouse behavior inside scroll views.
More Settings' private style also supports dragging blank native widget forms,
excluding buttons, fields, sliders, editors, item views and selectable text.
This does not impose blank-area dragging on unrelated third-party applications.

Validation: the QML frame suite covers blank surfaces, nested scrolling pages,
button clicks, text selection, sliders, drag thresholds, modified drags, wheel
and synthesized touchscreen scrolling. Native Qt tests cover blank form movement
and exclusion of interactive controls. Existing frame and layout checks still pass.

Live Wayland VM checks:

- [x] Drag the Store from its blank sidebar and the gap between home-page sections.
- [x] Drag Settings from space between its wallpaper choices; drag it out of a
  half-screen tile and retain the normal compositor placement behavior.
- [x] Drag More Settings from the blank network form background.
- [ ] Physical touchpad and touchscreen checks on real hardware.

### Passwords development preview (2026-10-28)

See [PASSWORDS.md](PASSWORDS.md) for the pinned source, build and disposable VM fixtures.
This preview is outside the normal image and installer; all credentials used were synthetic.

- [x] Three source-patch checks, eight compiled vault/browser/default suites, and eight
  upstream GUI scenarios (ten Qt passes including setup/cleanup), with no failures or skips.
- [x] Live native UI: wrong password rejected, explicit unlock, lock action, and locked
  startup after restarting. The toolbar fits at the tested 800-pixel window width.
- [x] Real Flatpak Zen extension: pair and approve in the native UI, fill the local form;
  denied access, another hostname and a locked vault leave both fixture fields empty.
- [x] Native encrypted backup, private file permissions, recovery from an independent
  backup copy, and rejection of corrupted ciphertext without changing the original.
- [x] Reconnect after replacing the running app by using the extension's Reload button;
  the existing association survived. Automatic reconnect remains unfinished.
- [ ] Windows access, multiple profiles, real-site save/update, hostile frames, suspend,
  accessibility/RTL, package upgrades, and a complete integration security review.

Screenshots, logs and the development build with corresponding upstream source are saved
on the host under `target/passwords-preview/`. See the detailed record for known permission
dialog visibility and reconnect limitations. No real credentials were imported.
Restored `ai-before-passwords-1028`; the VM is running, the fixtures are absent, and the
original notes checksum is unchanged.

### Password consent and familiar app discovery (2026-10-28)

Follow-up in the Monet VM, using the isolated password preview and user-local copies of
the current Settings, menu and Store. No real credentials or documents were imported.

- [x] Real Zen extension: submit a new login, cancel without saving, then approve New and
  verify the encrypted vault contains one new account. Submit a changed password, cancel
  the native update prompt and verify the original value remains; approve the next update
  and verify the same account changed with its previous password retained in history.
- [x] The loopback fixture serves only its fixed pages, rejects file/directory requests and
  oversized submissions, and discards submitted values. Five patch/fixture tests pass.
- [x] Familiar names resolve to installed apps; user-hidden, missing and unusable TryExec
  launchers stay out of suggestions. Settings opens external results, retains a retryable
  error when the launch helper cannot start, and clears it after a successful retry.
- [x] Reproduced the menu's delayed-header clipping in the real QML test (`y = -96`);
  the fix keeps new suggestions visible without taking keyboard focus from the search.
  Existing keyboard movement between suggestions and native results still passes.
- [x] Live desktop: Settings Finder → Files and menu Task Manager → System Monitor.
  At 200%, Nautilus → Files works by keyboard and the suggestion is fully visible.
  System Monitor reports missing VM sensors; only discovery/launch was verified here.
- [x] Store: AirDrop shows LocalSend; Pages shows LibreOffice/ONLYOFFICE and opens the
  LibreOffice details page. iCloud gives the no-suggestion fallback. The new explanation
  wraps correctly at 100/200%; no install or removal was started.
- [x] **44 checks, no skips:** `tests.test_passwords_preview`, `tests.test_everyday_search`,
  `tests.test_look.OurOwnStore` and `tests.test_store_downloads.DownloadUI`.
  Translation extraction/build/check and scoped whitespace checks pass. New text has English
  fallback pending translation. No native vault rebuild was needed for fixture-only changes.
- [ ] Real-site and multi-step password detection, hostile frames, multi-profile setup,
  cancelled-update wording, accessibility/RTL and the complete integration security review.
- [ ] Actual browser/document migration, native-format round trips, nearby file transfer,
  new OS image build/boot, physical hardware and a complete Windows return.

Host screenshots and check records: `target/passwords-preview/save-update-20261028/`
and `target/switcher-preview/`. Store suggestions were checked against the official
[LocalSend](https://localsend.org/), [Kdenlive](https://kdenlive.org/),
[Ardour](https://ardour.org/requirements.html) and
[LibreOffice](https://books.libreoffice.org/en/index2.html) documentation.
LocalSend needs its app on both devices; no AirDrop protocol support is claimed.

Restored `ai-before-passwords-switchers-1028`. The VM is running, the temporary preview
build/profile and switcher overrides are absent, and the original notes checksum is
unchanged (`f977db373d159cf87d95b94c5745fa5418fe237c57dca0415dc606064cb50d95`).

### Migration and regression check (2026-10-28)

Started from checkpoint `ai-before-migration-checks-1028`. Tests used the checkout uploaded
to `/tmp/monet-tests`, a disposable Zen profile, the existing checksum-verified Passwords
preview and synthetic documents/bookmarks. LibreOffice 26.8.1.1 was installed temporarily
from the user Flathub remote. No real logins or documents were imported.

- [x] Real extension: same-origin frame fill, foreign child refusal, and refusal when the
  saved site is embedded by an unrelated parent. The negative checks were repeated with
  the vault explicitly unlocked; the last showed the untrusted-iframe warning. A username-only
  first step and password-only second step both filled through the actual UI. Idle locking
  required a fresh unlock. See [PASSWORDS.md](PASSWORDS.md) for the reusable fixture commands.
- [x] Actual Zen **Library → Import and Backup → Import Bookmarks from HTML**: import the
  Windows adapter's HTML into an existing disposable profile. Three bookmarks appeared;
  preexisting bookmark GUIDs, a nested Work folder, Swedish characters and a URL containing
  `?a=1&b=2` survived. The source export's checksum remained unchanged.
- [ ] Repeat import: the same three bookmarks are added again. Existing records are preserved,
  but duplicate handling is unfinished. Repeat the same native import to reproduce.
- [ ] Corrupt import: a file containing non-bookmark bytes adds nothing and preserves all
  bookmark GUIDs, but no visible error or zero-import explanation appears. Profile selection
  and a clear result/retry flow remain required; no real browser profile was modified.
- [x] LibreOffice reads and writes synthetic DOCX, XLSX and PPTX copies and exports each to
  PDF. Inspection of the resulting files confirms Swedish text, DOCX bold text/table/image,
  the spreadsheet's `SUM(B2:B3)` formula and cached value 20, and the presentation's slide/text.
  Each PDF has one page with the expected text.
- [x] Live default-app launch: Writer opens DOCX, saves an added sentence after the format
  warning; Calc opens XLSX, changes 12.5 to 22.5 and saves the formula and recalculated value
  30 after its format warning. Saved files were inspected independently. Impress displays
  the PPTX, Okular opens the exported PDF and Gwenview opens the PNG. Original fixture
  checksums remain unchanged.
- [ ] Complex Office documents, macros, Microsoft Office/iWork comparison, native Apple
  formats, font/layout fidelity, PDF/photo editing, removable media and phone/nearby sharing.

The broad suite exposed an actual `monet-quick` regression: assigning a local search result
to `ok` made Python treat the shared command helper as an uninitialized local in timezone,
NTP and security branches. Renamed the result to `opened`. The new regression check exercises
the affected clock/security dispatch with command execution mocked; the timezone check also
mocks the shared executor, so tests cannot change the VM's clock or security settings.
Two source scanners now ignore generated `__pycache__` directories. The native Settings
launch check mocks `execvpe`, matching the implementation; its old `execvp` mock let the
test process replace itself and crash before the suite could finish.

Validation after these fixes:

```text
python tools/vm.py tests
Ran 730 tests in 70.964s
FAILED (failures=7, skipped=13)

python tools/vm.py tests tests.test_passwords_preview tests.test_everyday_search \
  tests.test_look.Scripts.test_quick_takes_only_zones_and_locales_it_knows \
  tests.test_look.FirmwareIds tests.test_look.OneOfEachName tests.test_more_settings
Ran 39 tests in 10.352s
OK
```

That baseline was **not green**. The seven failures below were resolved in the subsequent
safe-import pass recorded below; this table preserves the original diagnosis:

| Test | Observed mismatch / next action |
|---|---|
| `ASmootherTripToWindows.test_settings_ask_bridge_for_a_task` | Old `args.extend` assertion; protected departure now passes the task through `command.args`. Update the contract check around the current route. |
| `MonetSettings.test_settings_search_speaks_every_language` | Old single-string search assertion; current search matches individual words. Update coverage without losing translated/accent-folded behavior. |
| `SnapLikeWindows.test_settings_is_a_window_like_the_others` | Old direct Escape-close assertion; Escape now clears search first. Match the current interaction. |
| `WhatOtherSystemsHave.test_a_new_account_is_welcomed_once` | Old `which` route assertion; Settings now validates the parsed destination. Retain welcome-once coverage. |
| `Scripts.test_quick_settings_commands_take_only_their_own_values` | Rejects read-only `kreadconfig6` calls used for notification error feedback; no writes occurred. Distinguish reads from mutation. |
| `PlasmaPackages.test_inline_components_do_not_reach_outside` | WeatherDetails inline components refer to their outer `details` context. Resolve the existing component-scope rule. |
| `OneGamesFolderForBoth.test_widgets_buttons_are_monets_pills` | Sound's two microphone controls use `PlasmaComponents.Button`. Bring them into the established Monet control style. |

Thirteen reported skips comprise eight notification cases deliberately delegated to an
isolated D-Bus subprocess (its wrapper passed), plus five unavailable-runtime checks:
PowerShell parsing, NumPy photo painting, and three Node-based geometry/migration checks.
No Rust rebuild, new OS image, privileged firmware/inhibitor check or real Windows return
was performed in this pass. Preexisting failed units were input-remapper, its user autostart
and plasma-ksplash; they were already failed before testing.

Host evidence: `target/vm-migration-checks/final-suite.log`, `final-focused.log`, per-group
diagnostic logs in `suites/`, document originals/results in `documents/`, bookmark snapshots
in `bookmarks/`, and live screenshots in `screenshots/`. These are ignored test artifacts.

Restored `ai-before-migration-checks-1028`. The VM is running; temporary vault build/profile,
document/bookmark fixtures and the user LibreOffice installation are absent. Zen is again
the only installed Flatpak app. The original notes checksum is unchanged:
`f977db373d159cf87d95b94c5745fa5418fe237c57dca0415dc606064cb50d95`.

### Safe bookmark import and test-baseline repair — 2026-10-28

Checkpoint: `ai-before-import-recovery-1028`. Synthetic bookmarks only, two disposable
Zen profiles, a local HTTP fixture, and an account-local Settings preview; no production
bookmark database was written by Monet. The existing wallpaper was unchanged.

Settings → Default Apps → Browser bookmarks now lets the person choose an HTML export
and a specific Zen profile. Review counts new, already bookmarked/repeated, and unsupported
links; it displays a small sample before preparing a private HTML file. Source or destination
changes require a fresh review. Existing bookmarks are read through a read-only transaction;
an open profile is refused. Zen's native Library performs the import into its own named folder.
Checking reads that folder from the chosen profile, rather than equating launch with success.
The latest import for a profile can be checked after restarting Settings. Undo remains the
native action of removing the imported folder; manually importing a prepared file twice can
still create duplicates, which the check reports.

- [x] Live review: four exported links became one new link, two duplicates and one unsupported
  `javascript:` link. The existing bookmark was made through Zen's normal Add bookmark UI.
- [x] Native Library import: the selected profile received the new link and nested folder;
  all five preexisting bookmark GUID/title/URL tuples remained unchanged. A fresh review
  reported zero new links. The other disposable profile still reported two new links, and
  the original profile's database checksum was unchanged.
- [x] Review with the target profile open returned `busy`; no empty-profile fallback.
  Verification after closing the profile reported exactly one imported link.
- [x] Deliberately importing the prepared file twice through Zen reported one duplicate.
  Removing both test import folders through Zen preserved the preexisting bookmarks;
  verification then reported no imported links, and a new review offered the missing link again.
- [x] Restart Settings, choose the same profile, and check the previous import: its receipt
  survived and the result reflected the current bookmark database. Profile selection has a
  visible label and radio-button accessibility semantics. Live layout and result controls
  remained reachable at 100% and 200% app scale.
- [x] A slow default-app query initially pushed the bookmark section below the visible area
  after following a direct link. Anchor navigation now waits for that query before scrolling.
  A delayed-helper UI regression covers the actual geometry, alongside keyboard profile
  selection, disabled/pending controls, errors, and preparation versus verified success.
- [x] Backend regressions cover corrupt and oversized exports, excessive link counts,
  unsupported URLs, non-regular input files, corrupt profile lists/databases/receipts,
  external profile paths, changed previews, private output permissions, failed export or
  receipt writes, failed launches, and exact profile selection. Failed writes clean up only
  their newly created incomplete files.

The previous seven baseline failures are fixed without dropping their contracts: five
assertions follow the current search/navigation/departure/read-only settings behavior;
weather's inline components now pass focus requests through their own signal; microphone
and notification Retry buttons share a painted control with Space/Enter and disabled-state
coverage. Installer/uninstaller and CI include the bookmark helper and shared button.
The translation catalog was regenerated; untranslated new text uses the English fallback.

The VM temporarily received Node 24.22.1, PowerShell 7.6.9 (official release checksums
verified), and NumPy 2.5.4 so the five formerly unavailable checks could run. They are test
tools only, not new dependencies of the shipped OS.

```text
python tools/vm.py tests
Ran 746 tests in 77.026s
OK (skipped=8)
```

The eight reported skips are notification cases delegated to the passing isolated D-Bus
runner. Non-fatal fork/Pillow deprecation and Qt lifetime warnings remain in the log.
Evidence: `target/import-recovery/final-suite3.log`, `live-before.json`, `live-verified.json`,
`live-duplicate.json`, `live-undo.json`, and the live PNG screenshots in that folder.

Still open: exports from real installations of each source browser, custom Zen profiles
outside its Flatpak directory, screen-reader/RTL review, translations, and a full image
build/boot. This pass does not complete password migration, missing-document reopening,
editor cursor/split recovery, USB installation, firmware/Windows return, or real hardware
sleep/wake/peripheral tests. The native portal file picker also showed a mixed light/dark
theme in this VM and needs a separate theme integration check.

Restored `ai-before-import-recovery-1028`; the VM is running and SSH responds. The temporary
Settings preview, browser profiles/import receipts, Node/PowerShell runtimes and NumPy
installation are absent. The original notes checksum is unchanged:
`f977db373d159cf87d95b94c5745fa5418fe237c57dca0415dc606064cb50d95`.
The cleanup assertion is saved as `target/import-recovery/restored.json`.

## Editor windows and missing documents — 2026-10-28

Checkpoint: `ai-before-editor-recovery-1028`. Run the focused checks inside the VM:

```text
python tools/vm.py tests tests.test_editor_session tests.test_resume tests.test_return_summary tests.test_multi_restore tests.test_departure tests.test_trip_lifetime tests.test_workspace_return tests.test_files_session tests.test_browser_session
Ran 111 tests
OK
```

The live Wayland fixtures in `target/editor-recovery/` covered two independent Kate
windows and one KWrite window. Verified horizontal and vertical two-pane Kate layouts,
active tabs and either active pane, visible cursor offsets, separate window positions,
minimized capture/restoration and multiple KWrite tabs. A file renamed out of the way
after checkpointing stayed pending without creating a blank file. Returning it and
retrying reused the existing editor; another retry left the same three window IDs.
A separate cancellation kept an editor's unsaved buffer, PID, window ID and geometry
intact while reopening the closed sibling and KWrite. Native session receipts were
private, and Notes retained its original checksum.

Regression tests include all-files-missing, a closed original editor, manually reopened
files, slow launches, duplicate saved windows, stale requests, malformed pending lists,
PID reuse and legacy checkpoint recovery. Settings' Retry documents uses the existing
serialized worker and passes keyboard and narrow-window layout checks.

The VM was returned to the checkpoint after testing; the temporary editor helper,
fixture documents/windows and recovery records were removed by rollback. Existing clock
preview changes from the preceding task remain in that checkpoint. Real USB disconnects,
Windows firmware/reboots, a rebuilt image, nested splits, same-process multi-window editors,
inactive-tab cursors remain unverified or unfinished. Save As during departure is covered below.

## Save As during protected departure — 2026-10-28

Checkpoint: `ai-before-save-as-1028`. The focused VM run passed 132 tests, including
the parent check that runs ten isolated Qt departure cases:

```powershell
python tools/vm.py tests tests.test_departure_documents tests.test_editor_session tests.test_resume tests.test_return_summary tests.test_multi_restore tests.test_departure tests.test_trip_lifetime tests.test_workspace_return tests.test_files_session tests.test_browser_session
```

Real Kate/KWrite dialogs under Wayland covered these synthetic-document flows:

- Untitled KWrite → native Save prompt → first filename → close → controlled return.
  The final checkpoint and reopened tab used the newly saved path; retry created no duplicate.
- Modified Kate → cancel its close prompt → Save As → close while Monet waited.
  Recovery opened the new name; the old file's contents were unchanged.
- Cancel KWrite's Save As chooser → switch still waiting → cancel Monet.
  No restart acceptance was sent; the same editor PID retained its modified document.
- Rename and close Kate, then cancel Monet while an unsaved KWrite still blocked departure.
  Kate reopened its latest path once; KWrite retained its PID and modified state, and the
  previous saved filename was unchanged. Retrying added no windows.

The privileged helper was replaced only in the fixture by a pipe-protocol stand-in; it
recorded acceptance/EOF without reboot or firmware access. Evidence is in
`target/save-as/live-results.json` and the screenshots/scripts alongside it. The initial live
run caught D-Bus teardown removing an editor object before its bus name; closed watched PIDs
are now excluded from that query. Regression tests also cover stale/corrupt native files,
changed files during reads, shared anonymous sessions, distinct named sessions, discarded
untitled documents, cancellation during IPC, and retention of KWrite tab order/cursors.

Source compilation and translation-catalog consistency are checked separately. Shared
anonymous editor sessions, independent exits before Monet's close request, richer layouts,
installed-image behavior and real Windows/USB round trips remain limited or untested.

Restored `ai-before-save-as-1028` after testing. Hyper-V took several minutes, then reported
the VM Running; SSH confirmed both fixture directories were absent and the original Notes
SHA-256 was unchanged (`target/save-as/cleanup-results.json`).

## Independent editor exits during switching — 2026-10-28

Checkpoint: `ai-before-independent-exit-1028`. The same focused restoration command above
passed 136 tests, including the parent run of twelve isolated Qt departure cases. Added
coverage proves all editors are watched before any app closes and before privileged
preflight, repeated polls retain the baseline, cancellation during capture cannot install
a late watch, new windows get separate watches, and a newly shared native file invalidates
the older exclusive watch.

In the live Wayland fixture, Monet requested only KWrite's close and continued waiting for
that window. Kate was then edited, saved under a new name and closed manually. Its final
path updated without a Monet close request. Cancelling Monet reopened the latest file once,
retained KWrite's PID and modified state, left the original file unchanged, and sent EOF
without any restart acceptance. Retry created no extra windows. Native dialogs and helpers
were real; only the privileged pipe endpoint was a stand-in without firmware access.
Evidence: `target/independent-exit/verified.json`, fixture scripts and screenshots.

This does not validate switching named Kate sessions mid-departure, a completely new app
family opened after capture, shared anonymous instances, or a real Windows/image round trip.

Restored `ai-before-independent-exit-1028`; the VM returned to Running, SSH confirmed all
fixture files were gone and Notes retained its original SHA-256. Cleanup evidence is in
`target/independent-exit/cleanup-results.json`. Syntax and catalog checks also passed.

## Shared editor sessions and final receipts — 2026-10-28

Checkpoint: `ai-before-shared-editors-1028`. The focused restoration suite passed 151
tests, including the parent run of twelve isolated Qt departure cases. After the final
receipt/cancellation/build guards, 41 focused tests passed (`tests.test_departure_documents`
and `tests.test_editor_bundle`). These cover identity/schema/permission checks, shared
writers, missing receipts, late cancellation, unsupported layouts, atomic-copy failure,
runtime drift and loader-path aliases.

The actual Kate/KWrite 26.08.1 shared library was built in rootless Podman inside the VM.
Disposable editors used a temporary `LD_LIBRARY_PATH`; the VM's installed library was not
replaced. Live checks verified:

- Two anonymous KWrite instances: rename one document and save an untitled document in
  the other. The close button and Quit both produce separate final receipts. Cancelling
  the Save As chooser produces none and keeps switching blocked. Cancelling Monet then
  reopens both final paths with their visible cursors, preserves an unsaved Kate survivor,
  sends no restart acceptance and creates no duplicates on retry.
- Two anonymous Kate instances: horizontal and vertical split layouts retain tab order,
  selected tabs/panes, sizes and visible cursors in their receipts and reopened windows.
- Making the private receipt directory unusable vetoes closing. Disarming permits normal
  close. Malformed tokens are rejected. Adding another main window or a third pane leaves
  the previous capture intact with an unconfirmed warning.
- Native `--tempfile` paths scheduled for deletion stay out of recovery. Saving a permanent
  copy with Save As retains that new path after the temporary original is deleted.

The production component script built and sealed the binary/full-source bundle, and its
installer succeeded in the matching container. It correctly rejected the VM's different
runtime package set (including `libcurl-minimal` versus `libcurl`); this does not validate a
complete Monet image build. Evidence is in `target/shared-editors/`, including `verified.json`,
`kate-verified.json`, `veto.json`, `unsupported-verified.json`, `temporary-verified.json`,
`bundle-verified.json`, build logs and screenshots. Original fixture files and Notes remained
unchanged in the cancellation test.

Real Windows/USB round trips, a full rebuilt image, named-session changes mid-departure,
same-process multi-window restoration and richer layouts remain open. The privileged
endpoint in the live cancellation fixture was a pipe stand-in without firmware access.

Restored `ai-before-shared-editors-1028`. Hyper-V reported Running; SSH confirmed the
fixture directories and build environment were gone, and Notes retained its original
SHA-256 (`target/shared-editors/cleanup-results.json`).

## Nested editor panes and Save As — 2026-10-28

Checkpoint: `ai-before-nested-editors-1028`. All 159 focused restoration tests passed,
including nested-session serialization, bounds/identity/schema checks, missing-pane
pruning, legacy checkpoints, per-process final receipts, D-Bus fallback and Qt departure
tests. The native Kate/KWrite 26.08.1 component compiled in the VM's rootless build
container; only disposable editors used its temporary `LD_LIBRARY_PATH`.

Live native dialogs and production recovery helpers verified:

- Four nested Kate panes (horizontal, vertical, then horizontal) and a three-pane row.
  Save As kept a renamed document in its pane; a first-save during closing kept the new
  document in the middle pane. Cancelling the chooser left the editor open with no final
  receipt and kept its departure watch pending.
- After final receipts and cancellation, both editors reopened with the final filenames,
  tab order, active tabs/panes, visible cursors and relative split sizes. A repeated restore
  made no extra windows. The original file remained intact after Save As.
- Removing a fixture file before return removed only its pane. The remaining nested
  branch retained its layout; the absent path stayed pending. Returning the file and
  retrying reused the editor, and a second retry made no duplicate window.
- Legacy one/two-pane checkpoints, KWrite, repeated views of one document with different
  visible cursors, active-pane identification in the background and refusing to overwrite
  nonzero cursors. Invalid/stale cursor requests left the editor unchanged. A real unpatched
  editor continued using its existing accessibility adapter.

Evidence: `target/nested-editors/evidence.json`, fixture scripts and screenshots. Notes'
SHA-256 stayed unchanged. This slice did not build a full Monet image or perform a Windows
or USB round trip. Same-process multiple windows, inactive-tab cursors and returning late
files to their former pane without disturbing newer work remain backlog items.

Restored `ai-before-nested-editors-1028`. Hyper-V reported Running; SSH confirmed the
fixture directories and build environment were removed and Notes retained its original
SHA-256 (`target/nested-editors/cleanup-results.json`).

## Same-process window identity prerequisite — 2026-10-28

Checkpoint: `ai-before-window-identity-1028`. Built the native prototype in rootless
Podman inside Monet, against KWin 6.7.5, Qt 6.11.2 and Wayland 1.26. The start script
verified matching x86_64 package versions, the exact KWin library hash and resolved
dynamic symbols before loading it in a nested KWin session with its own D-Bus bus.
The VM's main compositor was not modified.

Live fixture checks, repeated with the final scripts in a fresh nested session:

- Two Qt windows in one process resolved to their exact, distinct KWin UUIDs, even
  with identical titles and frame geometry. Minimized windows kept their identities.
- Repeated lookups left focus, stacking, geometry and minimized state unchanged.
- Closing one window removed its identity without assigning it to the surviving sibling.
- Zero/invalid process and surface IDs returned no match. D-Bus exposed only the
  read-only resolver, with no inherited QObject control slots.
- Two raw Wayland connections in one process deliberately reused the same surface ID.
  The resolver refused the ambiguous match; closing one let the remaining connection
  resolve to its original compositor UUID.

The native build and both live test scripts passed. The final nested-compositor log
was empty, and Notes retained its original SHA-256. Evidence is in
`target/window-identity/evidence.json` and `identity-vm.png`; reproducible code and
commands are in [the prototype](../prototypes/window-identity/README.md).

This is a prerequisite, not shipped multi-window editor restoration. Per-window
capture/close receipts, shared unsaved-buffer recovery on cancellation, cross-window
Save As, production image guards and Windows/USB validation still need implementation
or testing. Existing single-window/nested-pane restoration was not changed by this slice.

Restored `ai-before-window-identity-1028`. Hyper-V reported Running; SSH confirmed both
fixture directories and the build container were removed and Notes retained its original
SHA-256 (`target/window-identity/cleanup-results.json`).

## Native multi-window editor interfaces — 2026-10-28

Checkpoint: `ai-before-editor-window-map-1028`. All 163 focused restoration tests passed;
the eight bundle tests passed again after adding the direct Wayland dependency to the
runtime manifest. The final native library and compositor extension compiled in the VM.

Real editor checks in an isolated nested compositor:

- Kate reopened two windows in one process, including a split window, using shared
  native document IDs. Each window mapped to its exact compositor UUID.
- An invalid second cursor request left the first window untouched. A request for one
  window left the other alone; subsequent requests preserved nonzero cursors.
- Save As on a document shown in both Kate windows updated both views to the new path.
  The original file remained intact. Cancelling the native chooser preserved both states.
- Closing and reopening the process retained the two windows' tabs, splitter tree and
  visible cursors. This exercised the adapter directly, not the automatic departure flow.
- Final native checks covered Kate and KWrite: a closed window's ID could not target its
  sibling; unloading the nested compositor extension made multi-window capture return no
  result while ordinary capture still worked; reloading restored exact identity. After one
  sibling closed, the existing single-window departure receipt remained valid.
- The batch resolver rejected invalid/duplicate/over-limit/stale surfaces and real
  same-process Wayland connection collisions without returning partial matches.

The corresponding-source bundle sealed and installed into its matching Fedora container.
The full bundle guard rejected the guest's different transitive packages. Disposable live
fixtures used the separate build after checking matching editor/Qt/KDE versions, exact
Qt and TextEditor library hashes, and all linked symbols. No system editor library or
main compositor was replaced in the VM.

Reproducible final native checks: `prototypes/window-identity/verify-editor.py`, alongside
the resolver fixtures. Evidence: `target/editor-window-map/evidence.json` and screenshots.
Notes retained its original SHA-256. Per-window close receipts, shared unsaved-buffer
recovery after cancellation, compositor image packaging, automatic placement and full
Windows/USB testing remain unfinished; the automatic path still uses one window per process.

Restored `ai-before-editor-window-map-1028`. Hyper-V reported Running; SSH confirmed the
build directory (including compositor/editor fixtures) and container were removed, and
Notes retained its original SHA-256 (`target/editor-window-map/cleanup-results.json`).

## Native editor group departure — 2026-10-28

Checkpoint: `ai-before-editor-group-exit-1028`. All 165 focused restoration tests passed.
The patched editor and compositor prototype compiled in the VM. The reproducible native
fixture is `prototypes/window-identity/verify-group-exit.py BUILD_ROOT`, using the same
isolated nested compositor and runtime checks as `verify-editor.py`.

- Kate and KWrite retained both original window IDs and the same unsaved shared buffer
  when the native close prompt was cancelled.
- Cancelling Monet while a save dialog remained open, then accepting Save, saved the
  document without completing the old close. The single-window path was checked too.
- Save As changed a shared document's path in both windows. Its original file survived;
  cancelling the chooser preserved the previous paths. First-save during group exit kept
  the new document in the correct window, including cancellation and retry of its chooser.
- A failed private receipt write and an unavailable identity resolver left the whole
  group open. A successful receipt reopened both windows in one process with their final
  paths and layout.
- Controller loss invalidated a pending native close. A new controller could arm a new
  token; a stale cancellation could not disarm it. Adding a window after arming vetoed
  closing until the whole new group was captured again.

The tests exercise the native group protocol directly. Automatic multi-window switching,
exact placement, compositor image packaging and a full Windows/USB trip remain open.
The final library passed the existing native multi-window/legacy compatibility fixture too.
Its source bundle sealed and installed in the matching build container. The full runtime
guard rejected the guest's missing/different transitive packages; system editor libraries
and the main compositor were not replaced. Source/binary hashes and native results are in
`target/editor-window-cancel/evidence.json`.

Restored `ai-before-editor-group-exit-1028`. The VM is Running; SSH confirmed the disposable
build, fixtures and container are gone, and Notes retained its original SHA-256
(`target/editor-window-cancel/cleanup-results.json`).

## Native window identity image bundle — 2026-10-28

Checkpoint: `ai-before-window-identity-image-1028`. All 153 focused VM tests passed,
including nine new bundle tests. They cover changed runtime packages/compositor binaries,
invalid destinations, damaged binary/source bundles, missing symbols, build-time library
paths and failed copies preserving the previously installed module.

The production `image/window-identity/build.sh` built and sealed the module in rootless
Podman; installation into that matching container passed. The full guard rejected the
guest's differing transitive runtime. The live fixture used the exact packaged module
after separately checking KWin/Qt/Wayland binary hashes and dynamic linking; nothing was
installed into the VM's main compositor.

- A fresh nested compositor loaded the module with no plugin preference override.
- Exact identities survived identical titles/geometry and minimization; lookups left
  focus, stacking and layout unchanged. Invalid, stale, duplicate and ambiguous identities
  returned no match, including real collisions across Wayland connections in one process.
- A second nested session found the installed plugin but kept it unloaded when
  `monet_window_identityEnabled=false`. No identity object was exported; both windows
  stayed open and the preference remained disabled.

The fixtures now compile the production source, with reproducible checks in
`prototypes/window-identity/verify.py`, `verify-collision.py` and `verify-disabled.py`.
Source/binary hashes and results are in `target/window-identity-image/evidence.json`.
The module's SHA-256 is `04205d992d28a38b6d105d86232d56cb0a1339dfc593bce0014c1de2b00cc463`.

The production build ran in an already provisioned development container, so its
before/after runtime check observed no package changes. The full image build and boot
remain untested. Automatic group capture/departure/recovery, exact window placement and
Windows/USB switching still need integration or validation.

Restored `ai-before-window-identity-image-1028`. The VM is Running; SSH confirmed the
temporary build, fixtures and container are gone, and Notes retained its original SHA-256
(`target/window-identity-image/cleanup-results.json`).

## Targeted missing-file retries — 2026-10-29

Checkpoints: `ai-before-editor-group-recovery-1028` and
`ai-before-editor-retry-guards-1028`. All 152 focused VM tests passed across the runs,
with the 34 affected editor tests rerun after adding delayed-reply coverage. These include
target validation, refusal/timeout handling and the production recovery caller.

The native check is `prototypes/window-identity/verify-retry.py BUILD_ROOT`. In disposable
Kate and KWrite processes inside the isolated compositor it verifies:

- Reopening into an inactive split window adds tabs to that window's current pane.
  Its other pane, selections, cursors, geometry and desktop focus stay unchanged.
- A document modified in the other window is reused as the same unsaved buffer; its
  saved file stays unchanged until the fixture explicitly saves it.
- Duplicate retries and a file alias already open in another pane add no extra tabs.
- Missing files, directories, invalid identities, duplicate/oversized requests and extra
  fields are rejected before mutation. Missing compositor support rejects the operation.
- The production recovery generator opens available files first and retains the missing
  file as pending. An automatic recheck leaves it alone; explicit Retry uses the exact
  owned window, preserves its cursor, and completes without another process or window.
  The reopened tab's displayed text matches the saved file, rather than an empty replacement.

Existing native multi-window capture/cursor checks and group departure tests also cover
Save As, first-save, cancelled choosers, late Save after Cancel, receipt failures and
controller loss. The fixture processes can emit a GLib main-context diagnostic during
Python teardown after their assertions and JSON results; those runs exited successfully.

A fresh guarded source patch matched the compiled editor tree. The corresponding-source
bundle sealed and installed in its matching container; the full guard rejected the guest's
different transitive runtime. Live editor fixtures separately checked matching Qt/KDE/editor
versions, binary hashes and dynamic linking. The main desktop's libraries were not replaced.
Results and source/binary hashes are in `target/editor-targeted-retry/evidence.json`.
The final native library SHA-256 is
`e10fbb00f485f5e3f51ff31f704964c8545abfb62ae3dfa3bef9e33b61df2058`.

Automatic multi-window capture/departure/recovery, windows with no currently available
documents, exact return placement, a full image build and Windows/USB testing remain open.

Restored `ai-before-editor-retry-guards-1028`. Hyper-V reported Running; SSH confirmed
the temporary build, fixtures and container are gone, and Notes retained its original
SHA-256 (`target/editor-targeted-retry/cleanup-results.json`).

### Automatic editor window groups (2026-10-29)

Under `ai-before-auto-editor-groups-1029`, rebuilt the existing guarded editor library and
production compositor module in the VM. The disposable nested compositor used matching
Qt/KDE/editor versions, verified binary hashes and resolved dynamic symbols. The VM's
main desktop libraries were not replaced.

All 170 focused tests passed: editor session/retry/group recovery, final departure receipts,
protected departure, return summaries, workspace placement, trip lifetime and bundle guards.
The group tests cover exact-ID validation, changed membership, cancellation while arming,
final Save As paths, dialogs, interrupted launches, same-boot survivors, malformed receipts,
existing-process matching, missing-file retries and disabled recovery.

`prototypes/window-identity/verify-auto-groups.py BUILD_ROOT` drives the production
checkpoint, departure, final receipt, cancellation and restore helpers with real Kate and
KWrite in an isolated Wayland compositor. It checks:

- Shared unsaved buffers, window IDs and processes survive Cancel.
- Save As and a first save during closing reopen in the correct windows, with their actual
  saved text, tab grouping and distinct geometry. Native window order supplies the mapping;
  KWin enumeration order is deliberately different.
- One missing window remains an empty placeholder. Automatic rechecks leave late files
  pending; explicit Retry opens them in that exact window without replacing its sibling.
- All saved files missing launches nothing. Intentionally empty source windows reopen.
- Repeated recovery/Retry requests create no extra windows or tabs.

A small empty KWrite window widened from 490 to 504 pixels when its first document view
appeared. Retesting at 620 pixels preserved its frame, sibling frame, focus and state.
Application minimum sizes still constrain restoration. A native accessibility cache warning
occurred during an earlier fixture run; all final assertions must pass before evidence is saved.

This is controlled same-boot recovery after a cancelled switch, not a Windows reboot.
Full-image, Windows/USB and physical multi-monitor tests remain open. A manually closed
window whose siblings still run keeps its remaining files pending until a safe native
window-creation operation is available. Evidence and source hashes are saved in
`target/editor-auto-groups/evidence.json`.

Restored `ai-before-auto-editor-groups-1029`. Hyper-V reports Running; SSH verified the
temporary fixtures/build and container are gone, and Notes retained its original SHA-256.
The cleanup result is saved in `target/editor-auto-groups/cleanup-results.json`.

### Replacing a closed editor window (2026-10-29)

Under `ai-before-editor-replacement-1029`, built the updated native editor library in the
VM's matching container and tested it in the disposable nested Wayland compositor.
The main desktop's editor library remained unchanged. All 179 focused tests passed,
including durable request handling, interrupted replies, disabled recovery, malformed
identities and preservation of the previous checkpoint when a write would exceed its limit.

The final native regression run passed `verify-replacement.py`, `verify-auto-groups.py`
and `verify-group-exit.py` sequentially. For both Kate and KWrite it confirmed:

- Explicit Retry recreates a closed missing-file window in its surviving process, with
  the available nested panes, visible cursors and original frame.
- Existing windows retain their metadata, frame and focus. A shared document reuses its
  unsaved buffer; its on-disk file is not overwritten by recovery.
- A lost reply creates only one replacement. Identical native retries return that window;
  changed requests are refused and a stale retry cannot resurrect a closed replacement.
  A later Retry can recover another generation once the preceding result was confirmed.
- Focus correction leaves another active window alone and does not run after the pointer
  moves. Resumed recovery does not reposition or refocus an existing replacement.
- Invalid layouts, missing paths, unavailable identity support and an armed departure
  refuse replacement. The automatic recovery and protected-close regressions still pass
  Save As, first-save, cancelled-dialog, shared-buffer and final-receipt checks.

The first live run exposed compositor activation despite the editor's activation suppression.
The final caller corrects focus only while its captured desktop choice remains unchanged;
both positive and negative focus checks passed. Application minimum sizes still constrain
window geometry. Successful fixture teardown can emit a GLib main-context diagnostic.

A fresh guarded upstream patch matched all ten compiled source files. The sealed bundle's
source archive and binary hashes matched the tested build and installed container copies.
The full runtime guard rejected the guest's differing transitive packages; isolated editor
processes separately used verified matching Qt/KDE/editor versions, hashes and dynamic symbols.
Evidence, final hashes and native results are in `target/editor-replacement/evidence.json`.

This remains controlled same-boot cancelled-switch recovery. A replacement closed before
Monet confirms its UUID stays pending; native closed-result receipts are still needed.
The per-process replacement cache holds at most 64 records. Inactive-tab cursors, late-file
sets exceeding a pane's tab limit, full-image, Windows/USB and physical multi-monitor tests
remain open.

Restored `ai-before-editor-replacement-1029`. Hyper-V reports Running; SSH verified the
temporary build, fixtures and container are gone, and Notes retained its original SHA-256.
The cleanup result is saved in `target/editor-replacement/cleanup-results.json`.

### Closed results during interrupted editor recovery (2026-10-29)

Under `ai-before-editor-closed-receipts-1029`, all 181 focused VM tests passed. The new
cases retain pending files after an unconfirmed replacement closes, require another
explicit Retry, reuse the original durable request after a failed checkpoint write, and
reject malformed attempt IDs and replies.

The final native `verify-replacement.py` passed for both Kate and KWrite. It deliberately
drops a successful replacement reply, closes the window before Monet confirms it, then
checks that the native closed receipt clears only the attempt. The pending document remains
available for Retry, automatic recovery leaves it closed, and the next explicit Retry
reopens it once. A new attempt cannot duplicate a live replacement of the same window.
Requests written before attempt IDs were added also reopen and report their eventual closure.
Existing shared-unsaved-buffer, nested-pane/cursor, frame/focus and malformed-request checks
passed in the same fixture.

The fixture first assumed that Wayland identity was available on the first native reply;
it now waits for that identity before dropping the reply. Its return-summary check also
uses the existing `partly-restored` status when a document is pending but present on disk,
with Retry available and no missing-file warning. These test corrections did not change
the product code or weaken the pending-document and duplicate-window assertions.

The fresh guarded patch matched all ten compiled files. The sealed source/binary bundle
installed in its matching container. Evidence and final source/binary hashes are in
`target/editor-closed-receipts/evidence.json`. The guest's normal desktop libraries were
not replaced. This is a controlled same-boot VM test; full-image, Windows/USB and physical
multi-monitor checks remain open, alongside the documented 64-record per-process limit,
late-file pane limits and inactive-tab cursors.

Restored `ai-before-editor-closed-receipts-1029`. Hyper-V reports Running; SSH confirmed
the temporary build, fixtures and container are gone, and Notes retained its original
SHA-256 (`target/editor-closed-receipts/cleanup-results.json`).

### Large batches of returning documents (2026-10-29)

Under `ai-before-editor-large-retry-1029`, the 183 focused VM tests passed. Boundary cases
accept a 200-document pane/request, reject 201 documents and reject a combined window
group above 200 entries. The updated legacy final-session parser check was rerun separately
and preserved all 200 paths, their order, selection and visible cursor.

The expanded native `verify-auto-groups.py` passed for Kate and KWrite. It starts with
200 tab entries across two windows, closes through protected departure, temporarily
removes 197 files, and restores the available documents. Automatic rechecks leave the
returned files pending; explicit Retry adds all 197 to the original window's current pane.
Its existing tab selection, cursor, layout, frame and focus stay unchanged, as does the
sibling window. A shared unsaved document retains its text and original on-disk contents.
Another file is refused at the full process budget without changing either window.
Repeated Retry adds nothing. After saving the fixture text, closing and recreating the
large window restores its 199-tab layout alongside the sibling's shared tab.

The same live fixture passed Save As/first-save, cancelled-switch, missing-window
placeholder, all-files-missing, intentionally empty window and exact-placement checks.
A fresh guarded patch matched all ten compiled source files. The sealed source/binary
bundle installed in the matching container; the normal guest desktop libraries were
not replaced. Evidence and hashes are in `target/editor-large-retry/evidence.json`.

The process remains bounded to 200 tab entries. This is controlled same-boot VM recovery;
inactive-tab cursors, full-image installation, Windows/USB and physical multi-monitor
checks remain open.

Restored `ai-before-editor-large-retry-1029`. Hyper-V reports Running; SSH verified that
the temporary build, fixtures and container are gone, and Notes retained its original
SHA-256 (`target/editor-large-retry/cleanup-results.json`).

### Inactive-tab positions through Save As and recovery (2026-10-29)

Under `ai-before-editor-hidden-cursors-1029`, all 188 focused VM tests passed. The new cases
cover optional bounded per-tab metadata, malformed offsets, pruning/promoting tabs when
files are missing, shared-file position selection, late-file requests and retaining an
unconfirmed cursor-restoration launch for Retry. Legacy checkpoints remain readable.

The expanded `verify-auto-groups.py` passed for Kate and KWrite. Three panes across two
windows share one file at offsets 37, 81 and 119. Save As during protected departure and
two successive recoveries preserve those positions before any hidden tab is selected;
accessibility checks show only the three visible editor views exist. Recreating the split
window retains its own offsets, and selecting the shared tabs exposes all three actual
carets. A cursor moved to 155 survives repeated requests both while visible and hidden.
A returning missing file gets its saved position in the current pane without changing
selections. Invalid cursor arrays reject the entire native request; truncated files clamp
the pending caret to the new end. Native Save As/first-save, cancel/veto, empty placeholders,
full 200-entry groups, 197-file Retry, shared unsaved buffers and placement checks also pass.
The VM occasionally refused transient captures; the fixture now waits for complete initial
window metadata, while production retains its conservative refusal and Retry behavior.

A fresh guarded patch matched all twelve compiled source files, including the view-space
hooks. The sealed library and source archive installed in the matching container. The
full bundle guard refused the differing guest runtime; normal desktop libraries were not
replaced. Evidence and hashes are in `target/editor-hidden-cursors/evidence.json`.

These are controlled same-boot tests. Scroll/selection state, unknown cursor positions,
full-image installation, Windows/USB and physical multi-monitor checks remain open.

Restored `ai-before-editor-hidden-cursors-1029`. Hyper-V reports Running; SSH verified
the temporary build, fixtures and container are gone, and Notes retained its original
SHA-256 (`target/editor-hidden-cursors/cleanup-results.json`).

### Scroll positions through Save As and recovery (2026-10-29)

Under `ai-before-editor-view-state-1029`, all 191 focused VM tests passed. The added cases
cover optional bounded per-tab scroll metadata, pruning/promoting tabs, shared-file pane
precedence and exact-file Retry requests. Older checkpoints remain readable.

The expanded `verify-auto-groups.py` passed in native Kate and KWrite. Active tabs at
vertical positions 50/90 and horizontal 120, plus hidden shared tabs at 160/200 and
horizontal 70, survive Save As and two protected departures/recoveries. Actual scrollbar
values and lazy view creation are checked. First activation exposed KTextEditor's delayed
resize resetting the horizontal offset; restoration now waits for the initial layout.
Repeated requests preserve a scrolled view even when its caret is still zero. A closed
window sharing a document with a sibling restores its own caret/scroll state, and late-file
Retry retains the saved viewport. Wrapped top columns and per-view wrapping survive another
departure. Invalid metadata is rejected atomically; shortened files clamp to the new range.
The existing first-save, shared-unsaved-buffer cancellation, placement, missing placeholders,
200-entry group and 197-file Retry checks also passed.

A fresh guarded patch matched all twelve compiled source files. The sealed source/binary
bundle installed in the matching container, and the full guard refused the differing guest
runtime. The main desktop libraries and nested compositor plugin stayed unchanged.
Evidence and hashes are in `target/editor-view-state/evidence.json`.

These are controlled same-boot VM tests. Selections/folding, unknown positions, full-image
installation, real Windows/USB switching and physical multi-monitor behavior remain open.
Restored `ai-before-editor-view-state-1029`; Hyper-V reports Running. SSH verified the
temporary build, fixtures and container are gone and Notes retained its original checksum
(`target/editor-view-state/cleanup-results.json`).


### Text selections through Save As and recovery (2026-10-29)

Under `ai-before-editor-selections-1029`, all 194 focused VM tests passed. New checks cover
bounded selection coordinates and mode, malformed/extra fields, missing-file pruning,
original-pane precedence and exact-file Retry requests. Older checkpoints remain readable.

The expanded native group fixture passed for Kate and KWrite. Ordinary and rectangular
selections survive Save As and two recoveries before hidden shared tabs are instantiated.
Accessibility verifies an actual selected range. The fixture exposes the native selection
action in its disposable toolbar and checks that Select Character Right continues a backwards range
from the correct end; replaying the old request leaves that later selection untouched.
Rectangular mode, reversed columns and columns beyond line ends survive first activation,
replacement in a surviving process and late-file Retry. Normal selections clamp when the
files become shorter, rectangular virtual columns remain valid, and document contents are
unchanged. Invalid native requests reject the entire operation. Existing shared-unsaved-
buffer cancellation, scroll, placement, missing placeholders and 197-file Retry checks pass.

An initial broad run refused a transient identity query before arming departure, leaving
both windows open. The same identities were subsequently available; the full rerun passed.
The safety refusal remains unchanged. Test-only fixes use the embedded editor's actual
selection action and wait for its toolbar button to be visible rather than assuming that
KMainWindow's action interface includes the editor component.

A fresh guarded patch matched all twelve compiled source files. The sealed source/binary
bundle installed in its matching container; its full runtime guard refused the differing
guest runtime. Main desktop libraries and the nested identity plugin stayed unchanged.
Evidence and hashes are in `target/editor-selections/evidence.json`.

Multi-caret selection anchors, folding and unknown positions remain open, as do full-image,
real Windows/USB switching and physical multi-monitor tests. Restored
`ai-before-editor-selections-1029`; Hyper-V reports Running. SSH verified the temporary
build, fixtures and container are gone and Notes retained its original checksum
(`target/editor-selections/cleanup-results.json`).


### Folding through edited Save As and recovery (2026-10-29)

Under `ai-before-editor-folding-1029`, all 197 focused VM tests passed. New tests cover
bounded native folding metadata, checksum shape, range order/nesting, missing-file pruning,
original-pane precedence and exact-file Retry. Invalid or extra fields cannot enter native
requests. The bounds allow 1,024 ranges and 64 nested levels per tab.

The full native group fixture passed in Kate and KWrite. A generated Unicode Python file
was edited while folded, then saved under a new name during protected departure. Its final
checksum and folds survived two recoveries before hidden shared views were instantiated.
Different windows retained independent folds for the same file. Native toolbar actions
unfolded an outer range while retaining its child, then unfolded the child; replay did not
undo that later choice at caret zero. Recreating a closed window left its sibling unchanged,
and temporarily missing files regained their original folds through production Retry.
Changed files rejected stale checksums, including lazy views. Invalid native requests were
refused before mutation; all generated file contents matched their expected values.

The broad run initially caught a stale fixture comparison taken before Save All. Saving
makes folding metadata available for a previously modified buffer. The fixture now verifies
that all other metadata stays unchanged across Save All, checks the new checksum, and then
compares the replacement's surviving sibling with that post-save state. The corrected full
run passed, including previous cancellation, Save As, cursor, selection, scroll, placement,
200-entry capture and 197-file Retry checks.

A fresh guarded patch matched all twelve compiled files. The sealed source/binary bundle
installed in the matching container; its full runtime guard rejected the different guest
runtime. Desktop libraries and the nested identity plugin stayed unchanged. Evidence and
hashes: `target/editor-folding/evidence.json`.

At this checkpoint the native importer still dropped the persistent bit on plugin ranges
marked both persistent and folded; the next entry records the dedicated native fix. Multi-caret anchors,
unknown positions, full-image and real Windows/USB/multi-monitor checks remain open.
Restored `ai-before-editor-folding-1029`; Hyper-V reports Running. SSH verified the temporary
build, fixtures and container are gone and Notes retained its original checksum
(`target/editor-folding/cleanup-results.json`).


### Persistent editor folding — VM checked 2026-10-29

Under `ai-before-persistent-folds-1029`, all 201 focused VM tests passed. The engine bundle
tests cover both original hashes, valid destinations, damaged binary/source refusal before
copy, dependency and engine-symbol preservation, and guarded patch/regression application.
All twelve bundle tests passed again after distinguishing incidental Qt/std template data
from the engine's functions, vtables and owned data.

The actual production build script compiled the installed KTextEditor version with its
RPM's optimization/hardening flags and Fedora linker flags, then built Kate's library and
sealed both with their source. Earlier builds caught missing development packages, a wrong
test executable path and mismatched linker/compiler settings; the final clean build passed.
The symbol check was scoped to the engine's contract after inspecting header-generated Qt
template data differences. These checks reduce compatibility risk; they are not a full ABI
analysis or a full-image boot test.
The runtime now explicitly installs binutils for the installation-time dependency/symbol
checks; the complete image build/boot remains untested.

The added native regression failed against the original engine and passed against the
patched engine. All seven upstream-suite cases passed with the addition: persistent folded
parent/child ranges survived repeated import, unfolding retained their anchors, refolding
worked, and document contents stayed unchanged. The production fix is one flag-assignment
change in KTextEditor's importer, guarded against upstream source changes.

The complete native Kate/KWrite group fixture passed both ordinary and persistent ranges.
It covered an edit followed by Save As, two departures before hidden tabs were shown,
independent folds in shared-document views, native parent/child unfolding, later choices
at caret zero, closed-window replacement and missing-file Retry. Changed files skipped stale
folds; malformed requests were refused. The broader cancellation, first-save, cursor,
selection, scroll, window-placement, 200-entry capture and 197-file Retry checks also passed.
The two fold variants use distinct file names so the test never accidentally overwrites
the other variant's saved document.

Fresh guarded patches matched all twelve Kate files and three engine/test files. Both
sealed libraries installed in the matching container, and the source archive matched the
compiled trees and build inputs. The full runtime guard rejected the different guest
runtime. Guest desktop libraries, nested identity plugin and Notes stayed unchanged.
Evidence and hashes: `target/editor-persistent-folds/evidence.json`.

Restored `ai-before-persistent-folds-1029`; Hyper-V reports Running. SSH verified the build,
fixtures and container are gone and Notes retained its original checksum
(`target/editor-persistent-folds/cleanup-results.json`). These remain controlled same-boot
tests; multi-caret state, unknown positions, X11 identity, full-image and real
Windows/USB/multi-monitor validation remain open.


### Multi-caret editor recovery — VM checked 2026-10-29

Under `ai-before-multicaret-1029`, all 204 focused VM tests passed. Three new format tests
cover extended selection metadata through missing-file pruning, document ownership,
invalid/duplicate coordinates, missing anchors, bounds and older ordinary/rectangular
selections. The native and helper boundaries reject unknown fields and malformed requests
before changing views; only coordinates and native selection anchors are retained.

The production build compiled and sealed both editor libraries. The added native tests
round-trip backward selections twice, continue them with Shift+Right, and delete the
selected text to verify the correct anchors are active. Bare cursors, malformed requests
and shortened-file coalescing are checked too. All 32 multicursor-suite tests and seven
folding-suite tests passed. The first build caught strict Qt string-literal errors in the
new test; after correction, the clean build passed. The original engine still fails the
persistent-fold regression while the paired engine passes it.

The first broad live run caught a shortened-file clamp problem: a saved cursor on a removed
line at column zero moved to the start of the last surviving line instead of document end.
Both normal selection and multi-caret restoration now clamp such positions to document end;
rectangular virtual columns retain their existing behavior. A native zero-column regression
and live normal/multi-caret shortened-file checks cover the repair. The complete corrected
run passed.

The complete Kate/KWrite live fixture passed multiple cursors through Save As, two
departures before hidden tabs are opened, independent shared-document views, closed-window
replacement and missing-file Retry. It includes mixed selections and secondary-only
selections. The native Shift+Right action continues the restored selections. Select All,
clearing the selection and resetting the caret to zero verifies that repeated recovery
does not recreate removed cursors. The shared-file case additionally retains different
extra-cursor sets in three panes across two windows after replacement. Changed file lengths
clamp coordinates without changing file contents. The broader cancellation, first-save,
placement, ordinary/rectangular selections, scrolling, folding, 200-entry capture and
197-file Retry cases passed as well.

Fresh guarded patches matched thirteen Kate files and eight engine/test files. Both
libraries installed into the matching container; archive sources and build inputs matched
the compiled trees. The full runtime guard rejected the different guest runtime. Desktop
libraries, nested identity plugin and Notes remained unchanged. Evidence and hashes:
`target/editor-multicaret/evidence.json`.

Restored `ai-before-multicaret-1029`; Hyper-V reports Running. SSH verified temporary build,
fixtures and container state is gone and Notes retains its original checksum
(`target/editor-multicaret/cleanup-results.json`). Native mode restrictions and the bounds
of 1,024 cursors per view/200 tab entries per process remain. Unknown positions, X11 identity,
full-image, real Windows reboot and physical USB/multi-monitor checks remain open.


### Background-work departure protection — VM checked 2026-10-29

Under `ai-before-background-work-1029`, 95 focused tests passed across departure, Store
downloads, final document receipts, return summaries, workspace return and trip lifetime.
The departure suite also passed 18 isolated Qt checks: shutdown versus sleep/delay
inhibitors, malformed replies, plain-text app names, no early close/acceptance, responsive
Cancel with a late reply, and an actual stalled child process killed by the query timeout.
Translation catalog consistency passed.

The reusable `prototypes/departure/verify-background.py` fixture used the production Store
service launcher/queue and switch dialog, real systemd services and logind inhibitors,
synthetic transactions and a normal Qt companion window. A pipe stub replaced only the
privileged restart helper. At 100% and 200% application scale it verified that windows
remain open while work runs; completion authorizes exactly once; Escape leaves the worker
and app running; queue cancellation releases the veto; and stopping the fixture service
releases it while retaining an Interrupted job for Retry. Both complete runs exited zero.
Captured dialogs fit their screens with visible Cancel buttons and readable app/reason text.

Source hashes, live proof and screenshots are in `target/background-work/`. Restored
`ai-before-background-work-1029`; Hyper-V reports Running and SSH confirms fixture/service
cleanup and the unchanged Notes checksum. The tests did not install/remove real apps,
invoke the privileged restart, change firmware or perform a Windows/physical USB trip.
Apps with neither a window veto nor a shutdown inhibitor remain an integration limit.


### Save As dialogs and fallback session ownership — VM checked 2026-10-29

Under `ai-before-save-as-session-1029`, two new regression cases reproduced the fallback
accepting a changed session and forgetting an observed shared writer. After the fix, all
179 focused restoration/departure tests and 19 isolated Qt checks passed. The Qt test
executes the actual KWin script with a normal transient save dialog, checking that it stays
pending without being classified as an editor main window. Native receipts are also tested
to remain independent of fallback session discovery.

Live unpatched Kate/KWrite 26.08.1 checks used isolated config/data directories and real
native save dialogs, production Python departure/recovery helpers, and a pipe stub for the
privileged restart acceptance. No firmware/reboot request was issued. The first run exposed
that Wayland Save prompts were counted as extra main windows and cancelled departure;
excluding transients from the main-window flag fixes that while retaining the save veto.

- KWrite's first save through the close prompt captured `First saved [1].txt`, reopened
  it with its synthetic contents, and did not duplicate it on Retry.
- Kate vetoed Close, used Save As while departure waited, then closed normally. Recovery
  reopened `Renamed [1].txt` with the edited contents; `Original.txt` remained unchanged.
- Cancelling the first-save chooser and then switching left the original KWrite process
  and unsaved text alive, with no restart acceptance.
- Kate's Save Session As changed the monitored named session. Departure cancelled safely,
  kept the same editor/document open, and did not accept the old session's saved list.

Evidence, source hash and screenshots are in `target/save-as-session/`. Tests did not rebuild
the image/native libraries or cover actual Windows/USB switching. A session change and exit
entirely between fallback polls cannot be proven by this adapter; native per-process
receipts remain the supported path for exact ownership. Restored
`ai-before-save-as-session-1029`; Hyper-V reports Running, fixture directories are gone,
and the Notes checksum is unchanged (`target/save-as-session/cleanup-results.json`).


### Files view-state recovery — VM checked 2026-10-29

Under checkpoint `ai-before-files-view-state-1029b`, built the production paired Dolphin
executable/private library from Fedora's 26.08.1 source RPM. The build retained downstream
patches and validated runtime packages, original hashes, linked features and exported APIs.
The final source archive matched the compiled tree and current build inputs. Both matching
containers accepted the final bundle; the guest's different runtime was refused and its
installed Files binaries stayed unchanged. Live apps ran in a matching container on the
VM's Wayland display, using the production Python helpers and KWin placement.

- Captured/restored hidden tabs, Unicode labels, unequal split widths, current/selected
  paths, expanded folders and scrolling. Two windows returned to their exact rectangles.
- Repeated the return at the bottom of a folder with different window heights; verified
  the actual metadata after placement, not only before resizing.
- Verified two panes showing the same folder retain different selections and the secondary
  active side. A selected dangling symlink remains selected.
- Removed a current/selected file and moved an expanded folder while its window was closed.
  Recovery skipped those missing items. A surviving window's later select-all/scroll choices
  and rectangle remained unchanged, and Retry created no duplicate windows.
- An unavailable folder kept its window pending. Returning the folder opened only that
  window, preserving the other processes and views. Repeated Retry did nothing.
- The installed, unpatched guest Dolphin still passed folder-only AT-SPI capture/restore;
  native refusals are separately tested not to downgrade silently.

All 210 focused tests passed across Files sessions/bundles, multiple windows, departure,
editors, browsers, workspace placement and return UI. Run Qt tests with
`QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software` over SSH. An initial combined run without
that environment aborted while initializing the XCB plugin; the configured run passed.
The new stream decoder's backing QByteArray must outlive QDataStream; its initial temporary
was fixed before the successful runs. Bundle tests also cover malformed destinations,
changed runtime/binaries, lost exports/features, corrupted source/binaries and failed copies.

Evidence and screenshots: `target/files-view-state/`. The final native pair was installed
again and exercised with the live two-window return and same-folder split checks. Native
sources were identical across both builds. These checks do not cover the full image build,
Windows firmware/reboots, physical USB media, remote/search locations, navigation history,
same-process multiwindow or broader monitor/scaling/RTL combinations.
Restored `ai-before-files-view-state-1029b`; SSH confirms the fixture/build directories,
both containers and the temporary image are gone, with the Notes checksum unchanged.
Cleanup evidence is in `target/files-view-state/cleanup-results.json`.

### Files windows sharing one process — 2026-10-29

Built the production Files pair from Dolphin 26.08.1's distribution source RPM in the VM,
including the guarded Wayland client dependency. The existing identity plugin and a native
three-window fixture ran in a matching rootless runtime with an isolated nested KWin.
The guest's mismatched runtime was refused, and its installed binaries were unchanged.
The nested compositor used an identical unprivileged executable copy because Fedora's
file capability cannot execute in the test user namespace. This does not alter the image.

Live checks passed for three main windows in one process, exact UUID/frame association,
closing the first D-Bus object, preserving changed selections and surviving window geometry,
reopening only the closed sibling at its saved position, unavailable-folder recovery and
repeated Retry without duplicates. Unloading the identity plugin left shared captures
unconfirmed and launched nothing. After two siblings closed, the remaining `Dolphin_3`
object still captured without the plugin. The unpatched guest's folder-only fallback passed.
Recovery can reopen saved Files windows in independent processes; shared process topology
is not part of the preserved workspace state.

All 216 focused restoration tests passed with `QT_QPA_PLATFORM=offscreen` and
`QT_QUICK_BACKEND=software`, including malformed/duplicate identity rejection, mismatched
window sets, cancelled switches with changed tabs, and pending launch ownership when
multiple windows show identical folders. The live fixture initially exited/crashed before
capture: it must use Dolphin's application name, initialize a folder before restoring,
and not interpret KMainWindow's always-false restore return as failure. Those fixture issues
were corrected before the successful checks. The build's initial CMake signature mismatch
was fixed before sealing and installing the production pair.

Evidence and screenshot: `target/files-windows/evidence.json` and
`target/files-windows/shared-windows.png`; reusable native checks are in
`prototypes/files-windows/`. Packaged native sources and installed binary hashes were checked
against the checkout. Full-image boot, physical Windows/USB switching, remote/search folders,
navigation history and broader monitor/scaling/RTL combinations remain untested here.
Restored `ai-before-files-windows-1029`; the VM is Running, temporary fixture/build files,
containers and image are gone, and Notes is unchanged. Cleanup evidence is in
`target/files-windows/cleanup-results.json`.

## 5. Logs

- Monet: Settings â†’ About Monet â†’ **Save a report** (one file in Documents), or `journalctl -u monet-sync` and `monet doctor`
- Windows' drive, its Games folder, Wi-Fi in both and what came over: `journalctl -b -u monet-windows-drive -u monet-windows-files`, and `cat /run/monet/windows-drive.json`
- A guest: `journalctl -b -u monet-guest-wipe` and `journalctl -b -u 'user@*'`
- Your photo, painted: `journalctl --user -u monet-paint`
- Windows: `C:\ProgramData\Monet\bridge.log` (and `%LOCALAPPDATA%\Monet\bridge.log` for what runs as you: adding the Games folder to Steam)

## Before real hardware: a virtual machine

On a Windows 11 Pro PC, Hyper-V runs Monet the way a real PC does: UEFI
with Secure Boot on (Microsoft's keys for Linux), so it starts through its
signed shim and shows the blue driver-key screen once. There's no graphics
card in it, so everything is drawn by the processor, and Monet starts
without glass there (blurring makes everything lag). To see the glass
anyway, turn on **Glass** in Settings â†’ Light & Wallpaper: right, but slow.

1. Turn Hyper-V on, once, in PowerShell as administrator, then restart:
   `Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V-All`
2. Download the USB stick's image (Monet-X-Setup.iso, or Monet-X-Installer.iso)
   from the release, or a build's `setup-candidate` artifact.
3. In PowerShell as administrator, from the repository:
   `.\tools\hyperv-vm.ps1 -Iso D:\VMs\Monet-X-Setup.iso`
4. Hyper-V Manager: select Monet, **Connect**, **Start**. Install as on a PC
   ([INSTALL.md](INSTALL.md)). Where it says to take out the USB stick, use
   **Media â†’ DVD Drive â†’ Eject** in the VM's window. At the blue screen, the
   password is `monetsetup`.
5. Once Monet is installed, take a checkpoint (**Action â†’ Checkpoint**), so a
   fresh Monet is a click away.

The screen size is set in Monet (Settings â†’ Display) once it's installed.


### 0.9.4 release preflight — 2026-10-29

The full checkout suite ran in the Monet VM with `tools/test.py`: 957 tests,
945 passed and 12 skipped in the outer runner. Eight of those are intentionally
run again on a private D-Bus by the passing notification subprocess test; the
remaining four require Node or Windows PowerShell. The Windows
PowerShell syntax check passed separately, as did 18 Windows USB safety tests,
15 Bridge tests and Windows Clippy with warnings denied. No physical disk was written.

The installer hardware matrix exercises both Setup's detector and the fallback
kickstart detector against Intel, AMD, modern NVIDIA, hybrid graphics, older NVIDIA
and no-display-controller fixtures. It confirms driver selection happens on the
destination, independent of the PC making the USB stick. Both OS image builds must
finish before either installer build starts. The USB binary remains common to all
supported x86-64 UEFI machines. This is not a physical-hardware compatibility test.

The combined Python process exposed a PySide assertion when unrelated QML fixtures
were loaded in succession. Running each module in a separate process keeps the
complete suite usable without disabling the affected UI tests. A JS-only test now
uses QCoreApplication, and a Qt-optional fixture no longer evaluates Qt constants
when Qt is unavailable. Full-image build and installation results are recorded
separately; these preflight results alone do not establish a bootable release.
