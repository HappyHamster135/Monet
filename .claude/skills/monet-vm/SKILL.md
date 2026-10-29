---
name: monet-vm
description: Test Monet in its virtual machine (Hyper-V on this Windows PC) the way a person would, through tools/vm.py - its screen, keyboard and mouse, a shell over SSH, and checkpoints to go back to. Use when asked to test Monet in the VM, try a flow end to end (Setup, Settings, Games, a trip to Windows), stress test it, or look for security problems in it.
---

# Testing Monet in its VM

Monet's test VM runs on this Windows PC (Hyper-V). `tools/vm.py` drives it; setting it up is
docs/TESTBENCH.md. Everything here happens **inside the VM only**: never run a stress test, an
attack or anything from inside Monet on this Windows PC itself.

## Before starting

1. `python tools/vm.py state` must say `Running` (`python tools/vm.py start` if it's `Off`).
   A permission error means the person hasn't done docs/TESTBENCH.md's first step: say so and stop.
2. `python tools/vm.py checkpoints` lists where it can go back to. `fresh` is a just-installed
   Monet. Take your own before anything that changes much: `python tools/vm.py checkpoint before-reset`.
3. `python tools/vm.py ssh -- true` says whether SSH works (docs/TESTBENCH.md sets it up).

## Seeing and doing

- `python tools/vm.py screen shot.png`, then read the picture. Its pixels are the VM's: click
  where you see things, at those coordinates. Look again after every action; things take a
  moment (Monet's animations, a window opening): wait a second or two before deciding it failed.
- `python tools/vm.py click X Y` (`--right`, `--double`), `drag X1 Y1 X2 Y2`, `move X Y`,
  `scroll X Y NOTCHES` (the wheel there; negative turns it down).
- `python tools/vm.py type "text"` types one line of plain ASCII key by key, as a US keyboard would
  (the VM's keyboard must be English (US)); about 40 keys a second, so for long text over SSH
  write a file instead. `python tools/vm.py keys enter`, `keys ctrl+u`, `keys meta`,
  `keys esc tab tab enter` for the rest.
- Account `j` is the person's in the current VM (`python tools/vm.py ssh -- whoami`); sudo needs
  their password, which you don't have: for root's side, ask them, or read what users can.
- Prefer what Monet says over what it shows when you can: over SSH,
  `/usr/libexec/monet-quick status`, `... library`, `... security`, `... storage` print JSON;
  `journalctl -b -p warning --no-pager`, `systemctl --failed`, `monet doctor`.
- Screens are slow to draw in a VM (the processor draws them): one action, then a look.
- `python tools/vm.py tests` runs the checkout's whole test suite on Linux in the VM (the tests
  Windows can't run too); `python tools/vm.py tests tests.test_look.Light` runs some.
- To try this checkout's helper, Settings or a widget there before a new image: copy them into
  the account (a plasmoid in `~/.local/share/plasma/plasmoids/` wins over the installed one,
  with `@LIBEXECDIR@` filled in), `systemctl --user restart plasma-plasmashell`, and take them
  out again afterwards, or they hide the next install's. Over SSH, give anything that draws or
  changes the desktop the session's `DBUS_SESSION_BUS_ADDRESS`, `WAYLAND_DISPLAY=wayland-0` and
  `XDG_RUNTIME_DIR` (without them `plasma-apply-desktoptheme` crashes and nothing changes).

## Never

- Type or keep any password but the VM's own test account's, which the person gives you.
- Leave the VM's SSH, firewall or accounts changed in anything that ships: they're for the VM.
- Restore over the person's own checkpoints without saying so; name yours `ai-…`.

## Kinds of tests

**A flow, as a person**: install from the stick, sign in, every page of Settings, Games (play,
favorites, sorting), the Games folder, Windows programs, lock and unlock, the guest account,
another language (Settings → Region; right-to-left in Arabic). Screenshot each step, note
what's cut off, overlapping, untranslated, slow or wrong.

**Stress** (inside the VM, with a checkpoint first):
- Processor: `for i in $(seq $(nproc)); do timeout 600 sha256sum /dev/zero & done` while using
  Settings and Games; does it stay usable, does anything crash (`coredumpctl list`)?
- Memory: `python3 -c "a = bytearray(int(14e9)); import time; time.sleep(300)"` (near the VM's
  16 GB): what's killed, does Monet's session survive?
- Disk: fill it (`fallocate -l 100G ~/fill` in steps) until nearly full; Settings → Storage,
  Updates and Games should say so plainly; then free it.
- Restarts: `sudo systemctl reboot` a few times; each time wait for SSH, then `systemctl --failed`
  and a screenshot of the desktop.
- The session: `systemctl --user restart plasma-plasmashell`, quick logout and login.

**Security** (report, don't fix by hand):
- What listens: `ss -tulpn`; from Windows, `Test-NetConnection ADDRESS -Port N` for each.
  Only what Monet uses should answer (and SSH, which the bench turned on).
- The firewall: `firewall-cmd --get-default-zone` (monet) and `firewall-cmd --list-all`.
- Files anyone can change where they shouldn't: `find /etc /usr/local /var/lib/monet -xdev -perm -0002 ! -type l 2>/dev/null`;
  set-uid programs: `find / -xdev -perm -4000 -type f 2>/dev/null`.
- Administrator prompts: as the guest (Settings → Accounts), try Monet's root helpers through
  `pkexec /usr/libexec/monet-secure`, `monet-guest`, `monet-keep`: each must ask for an
  administrator's password. The guest mustn't read the owner's files (`ls /home/*`).
- Secure Boot and the disk: `mokutil --sb-state`; `/usr/libexec/monet-quick security`.

## Reporting

For each problem: what you did (the commands, the clicks), what you expected, what happened,
the screenshot, and the test that would catch it from now on (tests/test_look.py, or a step for
docs/TESTING.md). Then go back: `python tools/vm.py restore fresh` (or your own checkpoint).
