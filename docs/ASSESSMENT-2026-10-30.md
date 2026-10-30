# Monet laptop assessment 30 October 2026

Monet builds successfully and its existing automated tests pass, but this laptop has two confirmed setup failures and an older widget component that loses edits. Prioritize encryption cleanup and Windows setup recovery, then deliver the widget fix already present in this checkout.

The project was cloned into `/var/home/jonte/Monet` from `https://github.com/HappyHamster135/Monet.git`. The assessed `main` commit is `16bc34a57acd12c937183d6d531d7d4e4d1217aa`, version 0.9.4. Tests ran on 30 October 2026, Europe/Stockholm time.

## Test results

| Check | Result | Local evidence under `target/assessment/` |
| --- | --- | --- |
| Rust workspace tests with the locked dependencies | 75 passed, zero failures: Monet 23, Bridge 15, core 19, USB 18 | `rust-tests.log` |
| Rust Clippy for the workspace and all Linux test targets | Passed with warnings treated as errors | `clippy.log` |
| Optimized Linux musl build | Passed; the resulting static executable also runs `doctor` | `linux-build.log`, `built-doctor.log` |
| Python and Qt suite | 45 modules, 983 discovered checks: 968 passed, 15 skipped, zero failures | `python-tests.log` |
| Phone Settings fixture | All three initially skipped tests passed with a private home and D-Bus session | `phone-tests.log`, `phone/artifacts/` |
| Window geometry and shortcut JavaScript checks | All three initially skipped tests passed using the bundled Node runtime | `geometry-tests.log` |
| Native More Settings style | Compiled with Fedora 44 and Qt 6.11.2 in a disposable rootless container; CTest passed 1/1 | `native-build.log`, `native/build/Testing/Temporary/LastTest.log` |
| Python syntax | 126 files passed | `syntax.json` |
| Shell syntax | 26 files passed | `syntax.json` |
| Installed widget regression | Failed against the installed component; the same test passes against this checkout | `installed-widget-regression.log`, `installed-widget.diff` |

Eight of the 15 top-level Python skips are notification tests that the passing parent fixture runs in its own isolated process. Six more passed in the follow-up Phone and JavaScript runs. The remaining skipped check is PowerShell syntax because PowerShell is unavailable here. Linux Rust tests exercise portable Bridge/USB logic; they do not establish that Windows APIs or physical USB writing work.

The Python suite used a separate HOME, XDG directories, session bus and offscreen Qt rendering. It covers widget editing, search, Settings interactions, installer screens, notifications, translations, download error handling, and editor/Files/PDF/browser restoration logic. Some recovery and installer scenarios use mocks; passing them does not certify a complete hardware installation or Windows round trip.

## Confirmed work needed

### High priority encryption cleanup fails on the installed boot mount

`monet-seal.service` failed at 21:14:58 on 29 October. Its traceback ends in `OSError: [Errno 30] Read-only file system: '/boot/monet-firstboot.key'`. `/boot` is mounted read-only, and `/etc/fstab` explicitly requests that mode. The 64-byte bootstrap key file still exists with root-only permissions; its contents were not read.

In `linux/libexec/monet-seal`, `wipe()` catches an overwrite error but then calls `unlink()` outside that handler (lines 66–76). `first_start()` performs enrollment and attempts key-slot retirement before this failing cleanup, so it never reaches kernel-argument cleanup (lines 79–93). The installed helper is byte-identical to the checkout. A mock of a read-only key reproduces the exception without touching a disk.

Update this sequence to handle the OS's read-only boot mount explicitly, verify every cleanup command's result, and support safe retries after partial completion. Add failure cases for read-only boot, failed slot removal, and failed kernel-argument updates. Actual TPM enrollment and remaining valid key slots need privileged inspection before repair; this assessment does not establish whether the leftover key still unlocks the disk. Do not treat deleting the file alone as a complete repair.

Evidence: `seal-journal.log`, `boot-mount.log`, `regression-reproductions.json`, and `installed-source-hashes.json`.

### High priority Windows setup cannot resume from its interrupted partition step

The installed setup log ends at 21:16:06 on 29 October with “the new partitions didn't show up.” The disk now contains `Monet Windows` at approximately 334.9 GiB and `Monet Setup` at 8 GiB; neither has a detected filesystem. `monet doctor` reports no usable Windows boot entry and failed Windows preparation. The original reason partition discovery failed is unresolved.

A separate recovery defect is reproducible in the current source: `make_partitions()` in `linux/libexec/monet-prepare-windows` returns immediately when both named partitions exist (lines 157–163). It neither validates nor initializes their filesystems, and ignores a failed `ntfslabel`. The formatting commands at lines 187–188 only run after creating new partitions. Later staging tries to mount the setup partition. The installed helper is byte-identical to this checkout.

Make recovery distinguish newly created empty partitions from existing user data and a completed Windows installation. Verify filesystem state before continuing, handle partial partition creation, and replace the single delayed lookup with bounded retries and useful diagnostics. Add a regression for “partitions created, discovery failed, rerun.” A recovery path must not indiscriminately format partitions identified only by their labels.

Evidence: `windows-log.log`, `disk-layout.log`, `doctor.log`, and `regression-reproductions.json`. The reproduction mocks every disk command.

### Medium priority install the existing widget edit fix

All 16 installed Monet `LayoutGuard.qml` copies differ from the checkout and lack its edit-completion capture logic. Running `test_layout_guard_keeps_edits_on_done_and_after_restart` against an installed copy reproduces a reset: the edited rectangle `(320, 320, 320, 256)` returns to `(48, 48, 224, 224)` after Done. This uses an offscreen fixture and does not move the user's actual widgets.

The same test passes against `linux/share/monet/widgets/LayoutGuard.qml`. Deliver that existing fix through an updated image and verify persistence after sign-in/restart. Both the installed OS and checkout identify themselves as 0.9.4, so version text alone does not identify the contents. Most sampled helpers match after installation path substitution, but the widget assets do not.

Evidence: `installed-widget-regression.log`, `installed-widget.diff`, `installed-widgets.json`, and `python-tests.log`.

### Medium priority distinguish a failed diagnostic read from missing permissions

`doctor()` at `crates/monet/src/main.rs:458` converts any failure to list `/etc/polkit-1/rules.d` into “Switching will ask for your password. Run the Monet installer again to fix it.” On this laptop the directory is mode 0750, owned by root and polkitd, and cannot be listed by the current user. The warning therefore does not establish that Monet's rule is absent or that switching would prompt.

Report an unknown/unreadable state separately from a verified missing rule. The authorization-only probe was also refused by PolicyKit because an untrusted caller supplied details; no privileged command was executed. Password-free switching remains unverified.

### Medium priority recover the failed update attempt

`monet-update.service` failed at 10:30:38 on 30 October while resolving `ghcr.io`. Later DNS lookup succeeded and NetworkManager reported full connectivity. This is a confirmed failed attempt, not proof of a persistent registry outage. The current connection is reported as metered, so automatic update retry must continue to respect that setting.

Check the updater again when an update download is appropriate, and ensure temporary network failures remain visible and retryable. An OS update was not staged during this assessment.

Evidence: `update-journal.log`, `network.log`, and `deployment.log`.

## Installed hardware and desktop observations

The laptop runs Monet 0.9.4 on the Bazzite/Fedora 44 NVIDIA image, kernel `7.2.11-ogc4.1.fc44.x86_64`. The installed image digest is `sha256:b9d031d2c515a650e5c6779bf6c2d88bea409f605648a0714d1591b3b3924c46`.

| Area | Observed result |
| --- | --- |
| Startup | UEFI detected; Monet is the default boot entry and the desktop is running |
| Graphics | Intel Iris Xe and NVIDIA RTX A500 Laptop GPU are both enumerated by Vulkan; NVIDIA driver 615.78.08 responds successfully |
| Network | NetworkManager reports connected with full connectivity; repository and build dependency downloads succeeded |
| Audio | PipeWire and WirePlumber are running; speaker, HDMI and microphone endpoints are present |
| Bluetooth | Bluetooth service is running; a prior Add Bluetooth Device wizard exited with status 1 |
| Background tasks | Monet's light and backup timers are active; this does not establish successful backup or restore |
| Secure Boot | Off; firmware trust and game compatibility still need hardware validation |

The failed NVIDIA settings autostart is separate from the working NVIDIA driver and Vulkan enumeration. Its exit status and the prior Bluetooth wizard failure warrant follow-up if the corresponding features misbehave; neither alone establishes a broken GPU or Bluetooth stack. Audio endpoint detection does not replace listening/recording tests.

## Remaining acceptance checks

After the setup fixes, test an encrypted NVIDIA installation in a disposable machine or VM with TPM support, then exercise repeated boots and recovery after interrupted setup. A real Windows installation and game launch/return are still required. Sleep/resume, physical Bluetooth pairing, audible sound/microphone recording, external displays, gaming performance, and backup restoration also need direct hardware checks. The complete OS image and installer ISO were not rebuilt in this assessment.

Strengthen CI so critical Qt tests cannot silently disappear when PySide6, KDE modules or a JavaScript runtime are missing. The general Ubuntu test job currently installs GTK bindings but does not explicitly provision those Qt/KDE dependencies. Add the two newly reproduced setup failures to the suite. Existing warnings also identify future maintenance in GLib signal registration, Pillow `getdata()`, and Qt fixture cleanup.

## Evidence and rerunning

Logs, the mock reproduction script, screenshots and build output are retained locally under `/var/home/jonte/Monet/target/assessment/`; this directory is ignored by Git. Run `python3 target/assessment/reproduce-findings.py` from the checkout to reproduce the two setup defects without hardware writes. The script reports current behavior; it is not a passing regression test for the desired fixed behavior.

Rust 1.97.0, Clippy and the musl target are installed only under `target/assessment/toolchain/`. For subsequent Rust commands, set `RUSTUP_HOME` to that directory's `rustup`, `CARGO_HOME` to its `cargo`, and prepend `$CARGO_HOME/bin` to PATH. The Python entry point is `python3 tools/test.py`; use a disposable HOME/XDG and D-Bus session as in this assessment when testing on a daily-use desktop.

This records the initial assessment before the owner requested 0.9.5 fixes. At that point production source files and the installed system were unchanged. Subsequent local implementation and verification are tracked in [the 0.9.5 backlog](BACKLOG-0.9.5.md). No disk formatting, encryption repair, reboot, update staging, commit, push or release occurred during the assessment.
