# Laptop keys, monitoring and battery readings

Games & Controllers now has **F1–F12 while playing**. On supported Lenovo
built-in keyboards, the focused game receives function keys; holding Fn uses
the media/brightness keys. Switching to another app restores the normal layout.
Keep Fn Lock off. Detection uses the focused game process, not a background game
or the entire Steam process group. External keyboards and unsupported layouts
are unchanged. A short lease and logind checks restore normal mapping if the
session disappears or locks. The helper never records input. Verified layouts:
ThinkPad P16s/T16 Gen 2 and P14s/T14 Gen 4.

The System widget avoids NVIDIA telemetry on laptops by default, including on
AC. Its persistent monitor can prevent runtime suspend even at zero load.
CPU, integrated graphics, memory and network readings continue. Explicitly
selected dedicated-GPU bar readings say **Paused**, not a fictitious zero.
The widget's settings can enable live dedicated graphics. Task Manager and the
notch's detailed Graphics view retain live monitoring. Static identification
reads sysfs and never invokes a GPU query.

Power & Sleep shows energy remaining (Wh), usable capacity, battery health and
battery power draw (W). Time remaining keeps UPower's estimate, labelled as
dependent on current usage. Invalid/unknown estimates and stale discharge times
after plugging in are suppressed. Physical battery health is aggregated by
energy, excluding peripherals and absent batteries; incomplete data stays
unavailable. See the [UPower device interface](https://upower.freedesktop.org/docs/Device.html).

## Verification on 26 November 2026

- On the ThinkPad P16s Gen 2, a controlled game-window fixture activated the
  mapping through real KWin focus reporting; closing it restored normal mode.
  Physical Fn combinations still need the owner's in-game check.
- An idle NVIDIA RTX A500 reported about 5 W before the change. Stopping
  monitoring allowed it to suspend within nine seconds. After installation,
  it stayed suspended throughout six samples spanning 25 seconds with Plasma
  and its statistics service running. No full discharge comparison is claimed.
- The battery reported 47.36 Wh usable versus 52.5 Wh design (90.2%). It remained
  plugged in at its 80% charge limit, so battery-runtime gains are unmeasured.
- Boot took 37.3 seconds: firmware 14.4, loader 7.8, kernel 1.7, initrd 4.8,
  userspace 8.6. A 3.3-second network wait was on the graphical critical chain.
  The installed guard recognizes these health checks as local. Actual boot
  gains need a subsequent reboot; no reboot was forced.
- Isolated checks cover key mapping, held keys, focus leases, battery data,
  health aggregation, custom boot checks, Settings and the real Plasma widget.
  The widget test verifies GPU subscription creation and removal on opt-in.

Install locally with `tools/install-game-keys.py --apply` and
`tools/install-power-preview.py --apply`. Both keep backups and receipts.
The power installer updates the account's widget and existing Settings preview,
adds a system boot guard and reloads Plasma. It excludes old compiled image QML
so cached bytecode cannot override updated source.

## Wireless regression fixed on 27 November 2026

The initial game-key proxy copied the ThinkPad's hardware wireless switch into
its virtual keyboard. A new virtual switch starts at zero, so registering it
caused Linux to block Bluetooth and Wi-Fi. The proxy now excludes hardware
switches from its virtual keyboard. If the physical wireless switch changes, or its
events are lost, the grab is released so the original kernel handlers can
resynchronize the real state. Other hardware switches are not proxied.

The corrected helper was installed on the P16s. All five virtual input devices
have zero switch capabilities; 39 samples across the installation and restart
found no blocked radios. The previously paired MX Anywhere 3S reconnected.
The game-focus fixture still enabled mapping and returned to normal after
closing. The 38 game-key and priority checks passed, including regression
coverage for switch capabilities and dropped events.

## Unplugged measurement on 27 November 2026

During ten minutes of active desktop use and the wireless repair, the battery
fell from 37.18 to 33.39 Wh: 3.79 Wh used, averaging 22.74 W. The latest reported
draw was 20.83 W. At the final 71% charge, that implies about 88 minutes at the
measured average; UPower estimated 96 minutes from the recent draw. The short
remaining-time estimate is therefore consistent with the measured consumption.

The NVIDIA GPU was suspended in all 21 samples and its runtime-active counter
did not increase. Screen brightness was 100%; a short process sample showed
ChatGPT and the browser consuming most of the measured CPU time. This was not
an idle benchmark or a controlled before/after comparison. No brightness or
power-profile changes were made during the measurement.

## Local fast-boot profile, 27 November 2026

The next physical restart tests an opt-in profile installed with
`python3 tools/install-fast-boot.py --apply`. This profile is limited to the
measured ThinkPad P16s Gen 2; it is not a default BIOS policy for every Monet PC.
`BootMode` was already `Quick`, the boot-time extension disabled, and Monet
first in the EFI boot order. The changes disable the firmware's IPv4 and IPv6
network-boot stacks and change its two-second boot-manager timeout to zero.
These are [UEFI network settings](https://docs.lenovocdrt.com/ref/bios/settings/thinkpad/network/),
not the operating system's networking. PXE/network recovery requires enabling
the stacks again; the firmware's F1/F12 options and USB boot remain available.

GRUB now skips its one-second menu on a previously successful boot with no
update trial or explicit menu request. Failed/unknown boots and trial boots
get ten seconds. The override uses bootupd's `user.cfg` hook, keeps greenboot's
counter and rollback logic, and explicitly saves the incomplete-boot marker.
The kernel, initrd, BLS entries and vendor GRUB configuration are not replaced.
An OS-requested recovery menu remains available:

```sh
python3 tools/install-fast-boot.py --show-menu
```

That requests a 30-second menu on the next start; it does not restart the PC.
To restore this laptop's original settings:

```sh
python3 tools/install-fast-boot.py --restore /var/lib/monet/fast-boot/20261127T124124860069/receipt.json
```

The installer uses an isolated writable mount view of `/boot`, backs up the
previous settings, and records changes before writing. It restores its changes
if verification fails and avoids overwriting subsequent user edits. Fifteen
profile tests and six network-health-check tests passed, including the real
GRUB parser, trial/failure/menu-request branches and simulated install failures.
After installation, both firmware network stacks read `Disable`, the EFI
timeout read zero, the original boot entries and counters matched, and Wi-Fi
and the MX Anywhere 3S remained connected.

The [saved baseline](benchmarks/p16s-fast-boot-20261127.json) records 22.055 seconds
in firmware, 7.763 in GRUB, and 43.474 seconds total systemd startup. That restart
also finalized a pending deployment during shutdown. The owner's next restart
took 42 seconds versus the earlier 51-second stopwatch result. Systemd recorded
32.647 seconds versus 43.474: firmware 14.586, loader 4.345, kernel 1.690,
initrd 3.656 and userspace 8.371 seconds. The login-manager process started
27.868 seconds into boot versus 40.904. These are process-start timestamps,
not visible-screen measurements; later background work explains why the full
systemd total is higher. The update-only trust and linker-cache rebuilds skipped
correctly, and no deployment was pending during shutdown.

This is one before/after pair, not a controlled attribution of the savings to
individual changes. Firmware had also taken about 14.4 seconds on earlier
boots, and the baseline included update finalization. Physical boot reports
continue under `/var/lib/monet/local-boot-test` for comparison.

## Local Intel AMT boot experiment, 27 November 2026

At the owner's request, `AMTControl` was changed from `Enable` to `Disable`
through think-lmi's single-setting interface. This is the reversible option;
the irreversible `PermanentlyDisable` value was not used. AMT was reported as
unprovisioned. The setting read back as `Disable` and `pending_reboot` became
`1`. Its runtime effect and any speed improvement require the next restart.

The original BIOS settings, boot-file hashes, EFI options, GRUB state and timing
were saved in `/var/lib/monet/firmware-tests/20261127T121331Z-amt/receipt.json`.
Comparing all exposed BIOS values confirmed that only `AMTControl` changed;
boot files, EFI options and GRUB state also matched. Wi-Fi and Bluetooth remained
unblocked, the MX Anywhere 3S was connected, and the game-key service was active.
The [experiment record](benchmarks/p16s-amt-20261127.json) retains the 14.585529-second
firmware baseline. No reboot was initiated. Compare the same stopwatch endpoints
and systemd's firmware timing after restart; a second normal restart helps
separate configuration-change work from the steady-state result.

The SMBIOS event-log metadata reports a valid, non-full log, but its access
method is GPNV (4). Reading `raw_event_log` returned EIO and the kernel explicitly
reported `dmi-sysfs: GPNV support missing`. This is a reader limitation, not a
diagnosis of damaged hardware or proof that the log is free of errors. A 68-byte
vendor EFI variable named `EventLog` was saved with the receipt, but no verified
decoder was available; it was not interpreted as event records. The current
kernel journal contains ACPI `_OSI(Linux)` and `_DOD`/`_DOS` firmware warnings,
which do not identify the cause of the pre-OS delay. No persistent crash records
were present in pstore. Logs were not cleared.

The remaining BIOS-log inspection requires the firmware's own viewer:
**F1 at startup → Main → BIOS Event Log**, as documented by
[Lenovo](https://docs.lenovocdrt.com/ref/bios/settings/thinkpad/main/).
Review POST Error and Subcomponent Self-healing events there. Entering setup
adds time, so do that separately from a timed normal restart.

The owner subsequently reported a roughly two-minute restart and requested
reversion. `AMTControl` was restored from `Disable` to its original `Enable`
value; readback and a comparison of all exposed BIOS settings confirmed that
only AMT changed, with `pending_reboot=1`. The rollback takes effect at the
next restart and is recorded in the same receipt. The earlier fast-boot profile
remains a separate change. The corresponding manual setting is **Config →
Intel(R) AMT → Intel(R) AMT Control → Enabled** in BIOS Setup.

The AMT-test boot (`0a944dd6-cfb0-48e0-b9f8-0f901150e383`) recorded 14.674 seconds
in firmware, 4.386 in the loader and 32.023 seconds total startup. That does not
explain the full reported restart interval. The earlier shutdown's journal
ended before the long gap to the next boot, so it cannot establish which
firmware or final shutdown operation consumed the unrecorded time. AMT showed
no measured firmware-speed improvement and the experiment has been reverted.

## Media-helper shutdown stall, 27 November 2026

The same restart exposed an independent, measured shutdown stall. The reboot
request occurred at monotonic 1733.215 seconds. `mpris-proxy.service` began
stopping at 1733.381, timed out at 1748.473 and stopped at 1748.496. KWin had
already exited at 1735.299, leaving 13.197 seconds waiting after the compositor
was gone. This closely matches the reported black screen with a frozen pointer,
although no screen recording establishes the exact visual handoff. Systemd
entered final shutdown at 1749.309: 16.094 seconds after the reboot request.

Monet now supplies a service-specific `mpris-proxy.service.d/monet-shutdown.conf`
with `TimeoutStopSec=3s` and `TimeoutStopFailureMode=kill`. The stateless
Bluetooth media-control proxy still receives SIGTERM and exits normally when
responsive. If stuck, it is terminated after three seconds without Fedora's
SIGABRT/core-dump timeout path. This changes neither application save deadlines
nor Bluetooth's own service or pairing behavior. It applies to both power-off
and restart. It bounds this failure; it is not an upstream BlueZ race fix.

The drop-in was installed at
`/etc/systemd/user/mpris-proxy.service.d/monet-shutdown.conf`, and the user manager
was reloaded. The receipt and any previous file are under
`/var/lib/monet/shutdown/20261127T122402Z/`. The normal installer includes it for
future Monet images, and the uninstaller removes it. The effective live settings
were checked. A disposable user service ignoring SIGTERM, with this exact
service-specific drop-in, was killed with SIGKILL in 3.170 seconds. The actual
media proxy restarted successfully in 0.015 seconds. The MX Anywhere 3S remained
connected, radios unblocked, and the game-key helper active.

At installation, a full shutdown/restart had not yet been tested after this
repair. The first restart would also apply the AMT rollback; a subsequent normal
restart provides a cleaner steady-state comparison. No global service timeouts
were shortened.

### Physical restart after the shutdown fix

Boot `e85e1585-ed97-4d48-8c4a-6d175d58e504` confirmed AMT restored to `Enable`
with no firmware changes pending. The owner reports quicker shutdown but about
50 seconds from the screen going black during restart to their ready endpoint.
The previous reboot request was at monotonic 705.232 seconds, with final
shutdown beginning at 711.027 (5.795 seconds). The media proxy stopped in
0.024 seconds, so its earlier 15-second stall did not recur.

Recorded startup was 31.867 seconds: firmware 14.510, loader 4.360, kernel 1.719,
initrd 4.857 and userspace 6.419. The Plasma workspace target was reached at
kernel-monotonic 13.472 seconds; this is not a first-frame or interactive-desktop
measurement. No deployment was staged, no user units failed, and the successful
boot flag and zero EFI timeout were intact. A later KSplash D-Bus activation
timed out, but the actual splash process had already exited at 14.705 seconds
and the workspace target was active; that background timeout does not establish
a 60-second desktop startup delay. This restart applied the AMT rollback, so
the unaccounted interval cannot yet be attributed to a specific operation.

The owner subsequently located most of the remaining wait at the black screen
before the Lenovo logo. This points investigation toward final kernel shutdown,
hardware reset and early firmware work, rather than desktop startup. The live
kernel reports the `acpi` reset method and `cold` reboot mode. Both persistent
crash-record directories (`/sys/fs/pstore` and `/var/lib/systemd/pstore`) were
empty. None of these observations establishes a faulty reset method, so it was
left unchanged. The next useful comparison is an ordinary restart now that AMT
is restored and no firmware change is pending, recording black-screen-to-logo
and logo-to-desktop separately. No additional runtime changes were applied
during this follow-up diagnosis.

### Cold boot and a smaller startup preview

Boot `4155edfd-096a-4d39-a6e5-de2e09d3ece0` followed a full power-off. The owner
measured about 30 seconds, with the Lenovo logo and a roughly seven-second Monet
screen taking most of the visible time. Recorded startup was 30.810 seconds:
13.565 firmware, 4.355 loader, 1.728 kernel, 4.829 initrd and 6.331 userspace.
The firmware still reports Quick mode, no boot-time extension and disabled
IPv4/IPv6 boot stacks. AMT remains enabled.

Plymouth started at kernel-monotonic 2.524 seconds and quit at 10.022, a 7.499-second
interval that overlaps disk unlock and service startup. Its theme has no timed
hold. TPM disk unlock took 2.619 seconds and Plymouth's root handoff took 1.145
seconds. These overlapping observations do not establish removable idle delays.
The encrypted-disk keyslot already uses the normal inexpensive PBKDF for its
high-entropy TPM secret; the password slot and all encryption settings were left
unchanged. The kernel, initrd, bootloader and BIOS settings were not modified.

Two local preview changes were installed:

- `bootc-update-crypto-policies.service.d/50-monet-deployment.conf` under
  `/etc/systemd/system` now limits backend regeneration to first boot and new
  deployments, ordered before the `/etc/.updated` marker is written. The selected
  `DEFAULT` policy passed `--is-applied` and `--check` before installation and
  `--check` afterward. Restarting this service skipped it as expected on the
  unchanged deployment. The original policy command and boot prerequisites remain.
  The receipt is `/var/lib/monet/startup/20261127T125105Z/receipt.json`. Remove only
  this added drop-in and run `systemctl daemon-reload` to restore the old behavior.
- The user's `ksplashrc` now has `[KSplash] Engine=none`, the native Plasma setting
  that avoids starting the extra desktop splash after login. The boot splash and
  disk-password interface remain. The desktop splash had run from 10.915 to
  14.910 seconds, while the workspace target was active at 13.527. Those are
  service timestamps, not first-frame measurements. Receipt and prior-file state:
  `~/.local/state/monet/startup/20261127T125120Z/receipt.json`. This account had no
  explicit `ksplashrc` before installation; remove the Engine key with
  `kwriteconfig6 --file ksplashrc --group KSplash --key Engine --delete` to restore
  the inherited theme setting.

The policy preparation passed five focused regression tests plus the 18 existing
boot-graphics/preparation tests. Native systemd condition checks confirmed that
a missing marker runs the unit, a current marker skips it, and deleting the
marker as OSTree does on deployment runs it again. Unit verification passed.
The crypto-policy step previously took 306 ms alongside other services; that is
not a promised boot-time saving. The extra splash's four-second lifetime also
overlapped desktop loading. A subsequent cold boot is needed to measure the
actual user-visible reduction. No restart or shutdown was initiated.

### One-boot smaller startup image trial

The same cold boot's ACPI firmware performance table independently reports the
bootloader launching at 13.565275 seconds and ExitBootServices completing at
17.921097 seconds. Loading the bootloader itself began at 13.539692 seconds.
The main firmware interval therefore precedes the bootloader; the logo does not
identify a configurable countdown. UEFI timeout and the healthy GRUB timeout are
already zero, Monet is the first UEFI entry, and no external USB devices or dock
were listed. The legacy device-class list puts USB CD/FDD ahead of NVMe, but
these entries follow Monet in the actual UEFI order. Reordering that list has no
established benefit, so firmware and AMT were left unchanged.

For the bootloader interval, a local dracut host-only image was built in sloppy
mode for this P16s, retaining Intel and NVIDIA graphics, NVMe/Btrfs/composefs,
TPM unlock, password prompts, FIDO2/smartcard support, and keyboard/USB input.
The original kernel command line and kernel are reused, with a harmless
trial identifier added. The image shrank from 187,861,580 to 154,053,111 bytes
(179.16 to 146.92 MiB, 18.0%). One significant reduction is carrying only this
CPU's microcode instead of the entire Intel microcode collection. The selected
microcode was verified byte-for-byte within the original image's payload.

The local build and receipt are under
`/var/lib/monet/startup-image/20261127T125857Z/`. The installed trial image is
`/boot/monet-startup/20261127T125857Z/initramfs.img`. It is not a portable Monet
release image. Its five critical programs/plugins passed dependency resolution
inside the unpacked image, and `systemd-cryptsetup --help` ran there without host
libraries. Required driver dependency checks passed; no account password hashes
were included. TPM enrollment remains bound to PCR 7, with no keyslot changes.

`tools/install-startup-image.py` appended a separate custom GRUB entry and armed
`monet_initrd_trial=20261127T125857Z`. GRUB clears and saves this selector before
selecting the trial; if saving fails, it retains the normal selection. It does
not select the trial during a greenboot deployment trial. A subsequent power-on
uses the original default again. Loader-level failures fall back to entry 0;
a failure after the kernel starts may require manually restarting, after which
the one-time selector has already been cleared. Existing BLS entries, vendor
GRUB configuration, kernel and shared original initrd were hash-verified intact.
The original custom recovery entry was preserved, and `/boot` remains read-only
outside the installer's private mount namespace.

Five focused installer tests and native GRUB syntax validation passed. Actual
TPM unlock, display handoff and bootloader speed still require the physical test.
The 18% image-size reduction is not a measured 18% reduction in bootloader time.
The preceding policy-cache and desktop-splash previews are also pending a boot;
use the separate firmware/loader counters when comparing this trial.

To cancel or remove only this trial, run:

```sh
python3 /var/home/jonte/Documents/ChatGPT/Monet/tools/install-startup-image.py --cancel /var/lib/monet/startup-image/20261127T125857Z/receipt.json
```

The installer refuses to overwrite later custom GRUB edits. A root-owned copy of
the installer is kept with the receipt. No shutdown or restart was initiated.

### Physical trial result and Rust feasibility

Boot `cf313335-43e4-4760-a349-c9f5975f13eb` used the smaller image: its kernel
command line includes `monet.startup_trial=20261127T125857Z`. The one-time GRUB
selector was consumed and `boot_success=1`; the ordinary image remains the next
boot's default. No system or user units were failed when checked. The policy
regeneration was skipped by its condition, the configured policy was applied,
and the extra desktop splash did not start.

The owner reported approximately 33 seconds. Systemd recorded 30.379 seconds:
13.620 firmware, 3.851 loader, 1.738 kernel, 4.649 initrd and 6.518 userspace.
The loader counter is 0.504 seconds lower than the previous cold boot, and total
system startup is 0.431 seconds lower. One comparison with an unspecified boot
type and concurrent policy/splash changes does not prove a repeatable saving.
In particular, it does not establish that the owner's visible wait improved.

The firmware performance table independently places the bootloader launch at
13.620977 seconds. Replacing Monet helpers cannot reduce that preceding firmware
interval. The before-login `monet-ready-boot` helper ran for 63.857 milliseconds
and brightness restoration for 118.282 milliseconds, overlapping other startup
work. Monet's deployment health checker did not run on this boot. Its five-second
poll loop therefore does not explain this delay. `monet-startup` is an on-demand
autostart settings editor, not the boot program.

There is no measured multi-second Monet interpreter bottleneck to justify a Rust
rewrite. A different bootloader or Linux EFI-stub boot could be a separate
architecture experiment; the kernel already supports EFI boot without GRUB
(https://docs.kernel.org/admin-guide/efi-stub.html). Such a change still needs to
load the kernel/initramfs and preserve deployment selection, recovery and TPM
unlock. The 3.851-second loader interval is not an estimate of the achievable
saving. No custom Rust bootloader, firmware replacement, or new persistent boot
configuration was installed in response to this result.

### One-time EFI kernel boot without GRUB

At the owner's request, `tools/install-efi-boot-trial.py` installed and armed
trial `20261127T132847Z`. `BootNext=0001` selects **Monet EFI kernel test** once.
The original **Boot0000 Monet** remains first in the unchanged permanent boot
order. All 30 prior EFI entries, 16 existing ESP files, and six original Monet
boot files were verified unchanged. `/boot` remains read-only and the ESP was
unmounted after installation.

The route is **firmware → existing Fedora shim → Linux EFI stub → Monet**, with
GRUB bypassed. A fully shim-free route would change this laptop's disk-unlock
measurement: the TPM token uses SHA256 PCR 7 and the current event log includes
shim's `SbatLevel` authority event in that PCR. Retaining the exact existing shim
avoids intentionally changing that measurement. No TPM enrollment, encryption,
Secure Boot setting, BIOS setting or original launcher was altered.

The kernel and previously boot-tested smaller initramfs were copied to
`EFI/MonetDirect/20261127T132847Z/` on ESP PARTUUID
`bfd99cf8-a424-41d7-923d-3dae7ab638f9`. The new EFI entry points at the existing
`\\EFI\\fedora\\shimx64.efi`, with its optional data specifying the new kernel
as shim's second stage, an absolute EFI initrd path and the original BLS kernel
options. It replaces the previous trial marker with
`monet.uefi_trial=20261127T132847Z`. The kernel and deployment are unchanged.

The installer uses `efibootmgr --create-only` to avoid modifying `BootOrder`.
It verifies copied files again after unmounting and remounting the ESP, reads
back the full EFI entry including GPT identity and optional data, then arms
`BootNext` as the final selection step. A native check caught efibootmgr 18
omitting the final UTF-16 NUL with `--unicode`; the unarmed attempt was cleaned
up. The successful install uses an explicitly terminated binary payload.
Thirteen focused tests cover payloads, malformed entries, concurrent boot
requests, preserving the existing order, and failed or partial firmware writes.

Receipt, EFI-state snapshot and root-owned installer copy:
`/var/lib/monet/efi-boot-trial/20261127T132847Z/`. To cancel before restarting:

```sh
python3 /var/home/jonte/Documents/ChatGPT/Monet/tools/install-efi-boot-trial.py --cancel /var/lib/monet/efi-boot-trial/20261127T132847Z/receipt.json
```

Cancellation clears only this trial's `BootNext`; it retains the test entry and
files for inspection and does not alter the normal boot order. UEFI consumes
`BootNext` before executing the selected entry. If the test stalls after control
passes to Linux, restarting again should use the ordinary Monet entry; the
owner can also select **Monet** with **F12** at the Lenovo logo. No restart was
initiated. Physical boot, automatic unlock and any speed improvement are still
unverified. This is not a persistent, update-aware replacement for OSTree/GRUB.

References: [Linux EFI stub](https://docs.kernel.org/admin-guide/efi-stub.html),
[shim 16.1 load options](https://github.com/rhboot/shim/blob/16.1/load-options.c),
[UEFI one-time selection](https://uefi.org/specs/UEFI/2.10/03_Boot_Manager.html#load-option-processing).


### EFI trial result, 27 November 2026

The owner reports a cold boot in “20 something seconds”. Boot
`9ad57b19-1f92-408d-b6ba-d022333394f7` contains the expected EFI initrd path and
`monet.uefi_trial=20261127T132847Z`, confirming that the trial route ran.
The loader phase fell from 3.851 to 1.896 seconds. Firmware remains 13.875 seconds;
`systemd-analyze` totals 30.523 seconds including background userspace startup,
while graphical.target was reached 3.943 seconds into userspace. These endpoints
are not the same as the owner's observed desktop-ready time. No further firmware
changes or permanent boot-order changes were made during the editor repair.
