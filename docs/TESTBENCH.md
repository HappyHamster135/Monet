# The test bench

Monet's test VM on a Windows PC, which an AI (Claude Code, Codex) or a person drives from the
command line with `tools/vm.py`: it sees the VM's screen, types and clicks in it, runs commands
inside it over SSH, and goes back to a checkpoint in seconds after something destructive. The
VM is a PC like a real one (UEFI, Secure Boot with Microsoft's keys, a TPM), so it tests Setup,
the blue driver-key screen, restarts and Reset this PC too, and nothing it does can reach the
PC it runs on.

## Once, as administrator

In PowerShell **as administrator** (right-click Start → Terminal (Admin)):

```powershell
# Let your own account drive Hyper-V, so Claude Code needn't run as administrator.
Add-LocalGroupMember -Group "Hyper-V Administrators" -Member "$env:USERDOMAIN\$env:USERNAME"
```

Then sign out of Windows and back in (a new group counts from the next sign-in).

Then make the VM (with Setup's image, `Monet-…-Setup.iso` from a release):

```powershell
.\tools\hyperv-vm.ps1 -Iso D:\VMs\Monet-0.9.4-Setup.iso
```

A VM made before (it was slow: 4 processors and 8 GB) gets the new size instead, switched off:

```powershell
Stop-VM -Name Monet
.\tools\hyperv-vm.ps1 -Tune
```

## Why it was slow, and what changed

Hyper-V has no graphics card for a Linux VM: the processor draws every frame of Monet's
desktop. With 4 processors that's choppy. The VM now gets all but four of this PC's
processors (12 of 16 here) and 16 GB, and a fixed 1920×1080 screen. For smoother still,
`-Tune -Width 1600 -Height 900`. Watching it in Hyper-V Manager's window (Connect) is itself
slow for Linux VMs; the bench doesn't need that window, so leave it closed while an AI tests.
Monet notices it's drawn by the processor and switches its glass off by itself.

## Once, in the VM

1. Start it (`python tools/vm.py start`, or Hyper-V Manager) and install Monet from the stick as
   anyone would. Choose **English (US)** as the keyboard: the bench types as a US keyboard.
2. In Monet, open Terminal (the app menu).
3. On Windows, in the repository:

   ```powershell
   python tools/vm.py ssh-setup --user YOUR-ACCOUNT-IN-THE-VM
   ```

   It types a line into the VM's Terminal that gives the bench's own key (made in
   `%LOCALAPPDATA%\Monet\testbench`) to that account, starts SSH and lets it through the
   firewall. Type the VM account's password where sudo asks, in the VM's window or with
   `python tools/vm.py type "password"` and `python tools/vm.py keys enter`.
4. `python tools/vm.py ip` should print the VM's address. If it doesn't, the Terminal shows it
   (`ip -4 -br addr`): `python tools/vm.py ip --set 172.x.x.x`.
5. `python tools/vm.py ssh -- uname -a` should answer from the VM.
6. `python tools/vm.py checkpoint fresh`: a just-installed Monet to go back to.

SSH is only ever turned on in this VM; Monet itself keeps it off.

## Testing with Claude Code

In Claude Code, in this repository, ask in plain words: "use the monet-vm skill and test the
Games app in the VM", "stress test Monet in the VM for half an hour", "look for security
problems in the VM's Monet". The skill (`.claude/skills/monet-vm`) tells it how to look, click,
type, check over SSH, take a checkpoint before anything destructive and go back after, what to
try, and how to report what it found.

By hand, the same commands:

```
python tools/vm.py screen shot.png        python tools/vm.py click 640 400
python tools/vm.py keys meta              python tools/vm.py type "Settings"
python tools/vm.py keys enter             python tools/vm.py ssh -- systemctl --failed
python tools/vm.py checkpoint before-x    python tools/vm.py restore fresh
python tools/vm.py scroll 900 600 -5      (the wheel, five notches down)
```

## What it can't test

A real graphics card (games run in the VM, slowly, without one), controllers and sound, a
real PC's firmware and its Secure Boot quirks, and Windows itself (install Windows in the VM
through Monet for the Play on Windows trips). Those need a real PC: docs/TESTING.md.

`python tools/vm.py tests` runs this checkout's whole test suite inside the VM, on Linux,
where the tests Windows can't run (bash, GTK, monet-light against a pretend KDE) run too;
`python tools/vm.py tests tests.test_look.Light` runs some. It copies the checkout to the VM's
/tmp each time and touches nothing else there.

### Keep a test installation consistent

When testing helpers under `~/.local/monet-bench`, copying just an app and its desktop entry
is not enough. The system's older `monet-session` and `monet-names.service` can still run
`monet-look --names` from the installed image and turn Store back into Bazaar. The bench's
`monet-look` must use a data directory that includes `applications/monet-store.desktop`.
Its session helper must call the bench helpers too. Override the existing
`~/.config/autostart/monet-session.desktop` and add a user service drop-in for
`monet-names.service` that clears `ExecStart` before selecting the bench's `monet-look --names`.
Keep installed assets available in the bench data directory and back up existing overrides.
Run both the sign-in helper and app-name refresh, then open Store from an old shortcut and
the dock. Remove these bench overrides when moving to an image containing the changes.

The profile-upgrade test also installs the bench's `monet-profile`, `monet-fresh`,
`monet-look`, `monet-light` and `monet-session` together. Its pre-desktop overrides are
`~/.config/systemd/user/monet-fresh.service.d/90-profile-preservation.conf` and
`~/.config/systemd/user/monet-keys.service` (enabled for the next sign-in). Remove these
alongside the other bench overrides when validating a shipped image. Private before/after
snapshots and helper backups are in `~/.local/state/monet/profile-upgrade-backup-*`;
the recovery journal is separate at `~/.local/state/monet/profile/state.json`.

KWin can retain QML and decoration configuration after a reconfigure. Switch away from and
back to a decoration to load its changed padding. A snap-script reload is not verified just
because `isScriptLoaded` says true: check the journal for QML load errors and exercise
Windows+Z, Snap Assist and a fast shared-edge resize. Keep sibling QML components beside the
entry point. A fresh session is the final release check.

Preserve current modification times when copying edited QML. A tar entry with its default
epoch timestamp can leave Qt using stale compiled QML even after restarting the app. Use
the source timestamp (as `checkout()` does), or touch the changed files before restarting.
Confirm the visible result and check the app's journal, not only the file contents.

Painted window controls are generated by `make-decoration.py` and shared with QML, GTK
and Zen through `make-gtk.py`. Copy `share/monet/window-buttons`, both GTK versions and
Zen's `window-buttons.css` along with the QML frame. The bench's `monet-light` must use
the bench data directory or its timer will copy older installed GTK styles over them.
An SVG can be valid XML and still fail Qt image sniffing: keep an unprefixed `<svg>` root
and check actual decoding, hover/pressed states, keyboard focus and dark mode.

The first work-restoration adapter and its precise test limits are in
[RESTORATION.md](RESTORATION.md). Keep live fixtures separate from the person's documents;
Kate/KWrite intentionally omit documents under `/tmp` from their session checkpoints.

`tests.test_window_frame` loads the shared app frame offscreen with PySide6/Kirigami and
checks content sizing, all eight resize grips, title buttons, maximize/restore rounding,
the blur region and transparent corners with the software renderer. It uses a temporary
QML file and does not write the account's settings. Live KWin input and blur still need
the mouse/keyboard checks above.

To see a Windows game in Games without a Windows, list one in the VM's
`~/.config/monet/windows-games.json`:
`{"v": 1, "games": [{"id": "steam:646570", "name": "Slay the Spire"}]}`.
