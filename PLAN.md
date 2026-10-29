# Monet: Project Plan

## 0.9.4 replacement build — published — 2026-10-30

At the user's request, the existing [0.9.4 release](https://github.com/HappyHamster135/Monet/releases/tag/v0.9.4)
was replaced from tested commit `555443abe650007a1c38dc27b20fb4b8dd65bb90`.
The release ID is unchanged; its assets, checksums, notes and tag now point to the
replacement. VERSION remains 0.9.4 and no 0.9.5 release was created. This supersedes
the earlier local-only restriction. App/package run 40955620065 and OS/installer
run 40955632028 passed, including both graphics images and a fresh installation
with the image attached as USB and Secure Boot enabled. All set, MOK recovery,
installed-system boot and lock/unlock passed. The five payloads and checksum file
match GitHub's server digests; fresh public USB-maker/checksum downloads also match.

Download the refreshed USB maker and rewrite existing sticks to obtain the new
installer. Its download cache now includes the release checksum so it cannot
resume an older 0.9.4 image into the replacement. Hardware tests, the Razer freeze,
the ThinkPad's firmware trust settings and encrypted NVIDIA installation remain
open. See [Testing](docs/TESTING.md) for evidence and the CI app-tour limitations.
The following records the pre-rebuild component verification.

Setup's custom buttons now show keyboard focus and respond to Enter and keypad
Enter. Tab/Shift+Tab reach Continue and Back; account fields advance with Enter
without bypassing validation. App selections retain focus when toggled, and
built-in app labels no longer take a Tab stop. At 800×600, fixed Qt delegate
padding consumed the entire dropdown text area. Scaling that padding with the
rows restores the language, keyboard, region and city labels in software rendering.

All 61 focused setup tests pass in the VM, including keyboard selection of Swedish,
Europe and Stockholm, app choices, password validation and disabled-install guards.
Dropdown rendering passes at 800×600, 1024×768 and 1440×900; the 800×600 screenshots
were inspected. These are source-level VM checks, not a rebuilt ISO or a physical
laptop retest. See [Testing](docs/TESTING.md) for evidence. The freeze below remains
a separate, unresolved hardware investigation.

Widget editing follow-up: pressing Done now captures the edited arrangement before
the screen-resize guard can restore its old snapshot. Adding, moving, resizing and
removing widgets survive Done and a desktop restart, including removal of the
widget that owns the shared guard. The gallery opened from Settings now targets
the current desktop when D-Bus provides no sender. Monet's desktop-menu defaults
are installed before first sign-in, while explicit account choices still win.
Focused VM suites passed (96 tests, then 19 overlapping follow-up tests); the live
desktop retained a moved calendar and newly added widgets after restarting Plasma.

Secure Boot follow-up: the published 0.9.4 Setup image reached Hello with Secure
Boot on in a separate Hyper-V VM, both as optical media and through its GPT/EFI
disk boot path. The same image was rejected with Windows-only firmware trust.
The ISO build now checks expected signing identities and identical EFI payloads
in both boot paths, and propagates image-creation failures. The release QEMU test
now attaches Setup as a USB disk instead of a CD-ROM; that new QEMU configuration
has a command-construction test but still needs a full run. This does not remove
the firmware requirement to trust Microsoft's third-party UEFI CA, and does not
establish the cause of the user's ThinkPad rejection. No replacement image has
been built or published. Physical USB and laptop Secure Boot checks remain open.

## USB installer freeze investigation — 2026-10-29

The user reports about 30 minutes at Installing Monet after the 6.7 GB download,
then an unresponsive laptop (Razer RZ09 family, reported 32 GB RAM and RTX 2080).
The earlier statement that it booted the installed desktop was corrected: it
returned to the USB installer. A second attempt with basic graphics also froze;
the user now confirms the pointer stopped immediately when the download finished.
This narrows the suspect interval to mounting the target and starting bootc, not
the later completion/restart UI. The freeze's cause is still unknown.

Hardware update: the user reports that installation worked on their ThinkPad
only after disabling Secure Boot. With it enabled, a Secure Boot error appeared
before Setup opened from the USB. Its exact model, graphics, encryption setting
and error wording are not recorded. This gives us a reported successful physical
installation with Secure Boot off, but does not validate the unpublished fixes
or Secure Boot on that laptop, or identify the Razer's failure. The user
suspects overheating; no temperature readings or thermal-shutdown evidence have
been collected, so keep that as a hypothesis and the Razer issue open.

Track the ThinkPad USB boot rejection separately for 0.9.5. The build uses Fedora's
shim, GRUB and kernel; CI booted this chain with Secure Boot enabled in OVMF.
Lenovo documents a third-party UEFI CA trust setting that can block Linux USB
booting when disabled. That is a diagnostic lead, not a confirmed cause here.
The exact error and firmware trust settings are still needed; the installed OS's
later MOK enrollment flow does not explain a failure before USB Setup starts.
The install guide now covers this distinction and links Lenovo's instructions.

Unpublished source fixes avoid waiting for background descendants' output pipes
after an install command exits, drain the final completion message before handling
worker exit, reject nonzero exits, and expose Details during installation. The
progress page explains that the downloaded image still needs installation.
The follow-up audit also fixed hidden bootc output during long-running commands,
lost output on timeout, and child processes surviving their parent's timeout.
The new wrapper reports live bootc output to Details and kills the command's process
group on timeout before allowing retry. All 61 focused VM tests pass, including
live QProcess/QML diagnostics and real subprocess timeout checks. None establishes
the laptop's freeze cause.

The release's successful full-install VM test used the AMD/Intel image and no
encryption; it did not cover the NVIDIA plus LUKS path on this laptop. A complete
NVIDIA/encrypted installation remains a release gate for 0.9.5, along with a laptop
retest. The current development VM has no usable KVM or QEMU installation, so this
audit did not repeat a full isolated installation. Existing logs and the bootc
1.17.1 source were reviewed; OCI downloads and OSTree imports use the destination
disk, not a whole-image RAM buffer. No replacement ISO has been built or published.
Evidence and limits are recorded in [Testing](docs/TESTING.md).

## Release 0.9.4 — 2026-10-29

The user has now authorized committing, pushing and publishing 0.9.4 for a first
physical USB/laptop test, superseding the earlier unpublished-build restriction.
The USB maker is common to supported x86-64 UEFI PCs; both installers choose the
NVIDIA or AMD/Intel image on the destination PC. ARM and BIOS-only PCs remain
unsupported. Both OS image jobs must finish before either installer build starts.

Release [0.9.4](https://github.com/HappyHamster135/Monet/releases/tag/v0.9.4)
is published from `9ffbf84ac36618c724c1684c46459eaa1b1ff811` on `main`.
Release run 40895588120 passed, including both graphics images, both installers,
fresh installation, Secure Boot enrollment recovery, first boot and lock/unlock.
The full VM suite and Windows safety checks passed; the complete local image and
its installed PDF recovery helpers also passed the isolated native scenarios.
The downloaded release USB executable matches both its published checksum and
the exact binary scanned by Defender, which found no threats.
See [Testing](docs/TESTING.md) for evidence and limits. Physical USB writing,
laptop driver behavior and a real Windows round trip remain unverified.
The CI desktop tour also needs stronger app checks: its Settings screenshot shows
Steam instead, so that portion is inconclusive despite the successful boot test.

## Active integration and app-restoration goal — 2026-10-29

1. Build this checkout as a complete Monet image, install and boot it in the VM, then
   exercise upgrade and rollback with existing preferences and work preserved. Verify the
   integrated CLI/helpers, native adapters and everyday entry points after restarting;
   isolated component tests do not complete this item. Keep local candidates unpublished.
2. Extend restoration to everyday office documents, PDFs, additional editors and browsers.
   Check actual saved documents/tabs and their windows, save/discard/cancel behavior,
   missing files, interrupted restoration and duplicate prevention. Preserve newer live work
   and native sign-in ownership; generic app launching does not complete this item.

The source snapshot for the first full-image VM build is recorded in
`target/full-image/source-upload.json`; its build runs under the checkpoint
`ai-before-full-image-1029`. Both items remain open until the corresponding live checks pass.

Integration progress — 2026-10-29: the complete image build now succeeds. It exposed a
missing notification-stage `kf6-kitemmodels-devel` dependency and an editor-header transaction
that upgraded util-linux libraries only in the build stage. The fixes add the dependency
and update the shipped runtime libraries before native components capture their compatibility
requirements; all unchanged native compatibility guards then pass. The unpublished candidate
is `localhost/monet-vm:1029`, image ID `91639aafadcdacc4e5cf4dcdafb4e139c35f2bc39b9867463eea06e1ee32e3e8`.
Its installed CLI/helpers are present and bootc's container lint passes 12 checks (one skipped),
with warnings about package-manager logs and files under `/var`. The candidate subsequently
booted in the VM. Existing preferences, pins, Notes, a saved document and its desktop shortcut
survived; the installed native adapters reopened two shared-process editor windows and two
Files windows with tabs/splits, final departure receipts and duplicate-free repeat recovery.
The image is not accepted yet: its profile migration tried to rewrite matching locked system
defaults, shared title-button assets were omitted, and the boot trial wrongly counted SSH
session churn as desktop instability. That last bug triggered an automatic rollback despite
a working desktop. The original deployment returned with saved work and choices intact.
Source fixes and 30 focused regression checks pass; a replacement image, repeated sign-in
and healthy upgrade/rollback verification remain. Inputs and evidence are under `target/full-image/`.
The corrected boot filter also passed its full 60-second read-only check against the live
VM while SSH sessions changed. The corrected migration completed and its repeat after
rollback was a no-op. The replacement full-checkout build under `target/full-image/integration2/`
has finished. Assembly checks verify 14 helper/native entries and all 32 title-button
assets; bootc lint passes. The exported 6,069,314,048-byte archive has SHA-256
`9f653fc35c3b24dc923ee7999b23c3c33aef81aa6fa412f85ea17dcc5bd89e32`.
The user staged that archive, and the replacement booted as deployment
`927a3b093367e0ec58815cd228b2884dc3cc36771fbc1bdfb4ef13794a615b14`.
The corrected boot trial passed and remained healthy beyond six minutes. The installed
profile migration completed and repeating it changed nothing; all 32 title-button assets,
saved work, Notes, pins and existing preferences passed checks. Two shared-process editor
windows and two Files windows reopened with tabs/splits and positions within one pixel;
repeat recovery created no duplicates. Heavy VM disk stalls caused metadata misses and
snapshot timeouts during earlier attempts; retained windows were verified without relaunch.
Startup still reported Plasma initialization/splash timeouts and a base automount failure.
Evidence is in `target/full-image/integration2/`. Repeated sign-in, everyday entry points
and a controlled rollback still require verification; image acceptance remains open.

PDF restoration progress — 2026-10-29: a bounded native Okular capture interface and Python
reader now retain actual local tab order, active tab, page numbers, modified flags and exact
Wayland window identities. Five focused VM tests and the native three-window fixture pass,
including reordered tabs, separate pages for a shared PDF, Save As with the original preserved,
empty windows, missing-identity refusal and capture after the first window closes. Evidence:
`target/pdf-recovery/evidence.json`. That first fixture covers capture; protected departure
is checked separately below. Automatic switching integration, verified reopening/missing-file
retry and image packaging remain. The isolated containers and VM checkpoint are retained
while the broader image integration continues. The original Notes checksum is unchanged.

PDF protected departure — 2026-10-29: per-window final receipts and controller-owned
cancellation guards now pass eight focused checks and a native annotation scenario in the VM.
Real Save As/Save/Discard/Cancel preserve the expected PDF contents and an unsaved survivor;
late Save after switch cancellation or controller loss cannot complete the close. Receipt
write failures veto closing, and final records retain the original active tab. The capture
regression still passes. Evidence: `target/pdf-recovery/departure-evidence.json`.
The prototype is not installed or enabled: switching-controller integration, verified
reopening/missing-file retry and image packaging are still required for PDF restoration.

PDF private reopening — 2026-10-29: the checkout controller now captures per-window PDF
metadata and consumes final departure receipts, including new windows and cancelled switches.
Seventy-three focused VM checks pass. The native CLI restores duplicate tabs, independent
windows, pages and selection through private sessions while preserving ordinary preferences;
both native capture/departure regressions still pass. Malformed input and missing files are
refused before opening. Evidence: `target/pdf-recovery/restore-evidence.json`. Return-controller
reopening, late-file retry, duplicate prevention and production image packaging remain open;
the first complete-image candidate does not include this PDF prototype.

PDF late-tab retry primitive — 2026-10-29: native retry now binds each request to an exact
window and a durable attempt ID. A file that becomes available can be appended without
replacing newer modified tabs, their pages, selection or window geometry. Repeated requests
do not append again; manually closed recovered tabs stay closed, and closed windows never
redirect into siblings. Stale metadata and missing identity support refuse mutation.
All 74 focused VM checks, three native fixtures and the real CLI/D-Bus reopening scenario
pass. Evidence and matching source hashes: `target/pdf-recovery/retry-evidence.json`.
Fixture method-case and startup-identity failures were corrected before the final run.
Notes remained unchanged. The return controller still needs durable retry/launch integration,
counts/summary and placement; production PDF packaging and broader office/editor/browser
support remain open. These primitives do not yet establish automatic PDF switching.

PDF return controller — 2026-10-29: 124 focused VM checks and the native three-window
return scenario pass. Durable private launches and exact retry requests survive controller
loss without duplicate tabs/windows; missing files remain available for explicit Retry.
Duplicate-path tabs, pages, selection and placement return, while an unsaved cancelled-switch
survivor and newer live work remain untouched. The native fixture answers only its synthetic
windows' real Close Tabs confirmation. Original PDFs and Notes retain their checksums.
Evidence and tested source hashes: `target/pdf-recovery/return-evidence.json`. Ambiguous
unconfirmed launches require explicit Retry if their process has disappeared. Production PDF
packaging is being built and checked separately; the staged integration2 image predates this
controller. Broader office/editor/browser support and installed PDF switching remain open.

PDF production bundle — 2026-10-29: the native shell now builds from the installed source
RPM, seals and installs into its matching runtime. Its original part, core and PDF generator
remain byte-for-byte unchanged; corresponding source and all linked dependencies verify.
An older runtime is refused. The first build correctly rejected a Brotli upgrade confined
to development dependencies; the shared image runtime now updates that library first.
Evidence: `target/pdf-recovery/bundle-evidence.json`. The packaged binary still needs the
native fixture and complete-image boot checks. Metadata-only capture retries were added
inside the existing bounded child processes; cursor writes are never replayed. Sustained
unresponsive apps remain unconfirmed. Failed compositor snapshots now raise an explicit
capture error instead of looking like an empty desktop. Departure preserves its previous
checkpoint, and recovery keeps pending work available for Retry without launching anything.
All 244 focused VM checks pass. A real editor/private-bus outage fixture confirms that Retry
reuses the original window with document state/content unchanged; evidence is in
`target/full-image/integration2/snapshot-outage-evidence.json`. These follow-up fixes are not
in the currently booted integration2 image yet.

Packaged PDF and rollback follow-up — 2026-10-29: the exact production PDF binary passed
both live CLI and return-controller scenarios in the matching isolated VM runtime, including
cancelled switching, missing-file retry, placement and controller interruption without
duplicate tabs/windows. Files, preferences and Notes retain their contents. Evidence is
`target/pdf-recovery/production-native/packaged-evidence.json`; complete-image PDF boot
remains open. Rollback failure testing exposed an unchecked `bootc rollback` result: the
boot checker could erase its trial, record success and reboot after scheduling failed.
The source now retains the trial, reports failure to systemd and does not reboot. Both
regressions fail against the installed image; all 11 boot-recovery checks pass with the fix.
Evidence is `target/full-image/integration2/rollback-regression.json`. The fix is not yet in
the booted image. The user then queued rollback through the installed helper. The earlier
deployment booted and passed data-preservation checks twice, across a second normal restart:
latest saved document contents, Notes, preferences, pins and shortcut bindings survive.
The document also opens with its latest text. Evidence is
`target/full-image/integration2/controlled-rollback.json`. The older image could not load
newer preview widgets whose user overrides had deliberately been removed for image testing;
restoring the exact saved bench assets/launchers repaired Sound and the panel. This is test
cleanup, not proof of shipped cross-version widget compatibility. Base input-remapper and
splash timeouts under VM disk stalls remain. Evidence and test documents were exported before
returning to checkpoint `ai-before-controlled-rollback-1029`; that cleanup is not a re-upgrade
test. Full-image PDF/newest-fix validation and broader app support remain open. Nothing is published.

## Current delivery backlog — 2026-10-27

These are implementation priorities; completion requires the stated checks, not just code.
The supporting usability review is in [docs/ANNOYANCES.md](docs/ANNOYANCES.md).

Clock format repair — 2026-10-28: a shared read-only preference watcher updates the panel,
desktop, world clock, lock screen and Quick Settings time labels without a new sign-in.
Live VM toggles and a two-clock regression test cover 12/24-hour changes, region fallback
and reopening. The test checkpoint was restored, then only the clock repair was reapplied
to the VM's user overrides; those overrides must be removed when testing a matching image.

USB writer safety — 2026-10-28: selection retains Windows' device GUID, capacity and sector
size, all rechecked on the opened device before writing; an unknown system disk blocks the
operation. Volume discovery/lock/dismount errors stop the operation, all locks precede any
dismount, and another raw writer is excluded. Image validation and capacity checks precede
writing; release downloads require their published SHA-256, and one source handle denies
changes/deletion until verification ends. Sector-aligned uncached writes/read-back check
the flush result and final padding. Failure messages no longer claim the hardware is sound.
The safety preview builds and passes Defender, 18 Windows tests using memory/temporary files,
and 17 portable tests in the Linux VM. Actual Windows volume locks, hotplug, USB writes and
booting still require physical-device validation; no USB disk was written during this work.
The local build for that later check is `dist/Monet-0.9.3-Make-USB-Stick-safety-preview.exe`.

### Everyday polish backlog — 2026-10-27

Keep the existing wallpapers unchanged throughout this work. These follow-ups are
authorized in order; a VM check does not replace real-hardware release validation.

| Order | Work | Status | Acceptance checks |
|---|---|---|---|
| A | Shared weather details | Implemented and VM-checked; 28 focused weather/widget checks pass | Clicking the desktop card or bar weather opens the same hourly and seven-day forecast, with rain probability, feels-like temperature, wind and sunrise/sunset. Day selection, units, place changes, keyboard navigation, offline recovery and small/scaled screens work in both entry points. Preserve Monet's painted sky and glass. |
| B | Useful network, Bluetooth, sound and battery controls | Microphone selection/mute implemented and VM-tested with virtual devices; existing native network/Bluetooth/battery controls to audit | Show connection/internet status and available networks; connected Bluetooth devices and supported battery levels; output device, volume and microphone mute; charge, charging state and power mode. Reuse working system controls; verify real radios and batteries on hardware. |
| C | Clear action feedback | Notification settings now verify changes, show pending/saved/error states and keep Retry visible; keyboard focus reveals off-screen controls. Wider settings/download/update audit remains | Audit everyday settings, downloads and update actions. Show pending, success and actionable failure states; prevent duplicate requests; keep failures and recovery actions visible. |
| D | Calmer notifications | Timed Do Not Disturb, per-app muting and focus-timer preferences VM-checked. Native important-popup retention and prevention of old popups after unmuting now built and VM-tested, including actions, grouping and Clear History at 100/200%. Image integration added; full image build/boot and first-notification app discovery during quiet time remain open | Group repeat notifications, provide timed Do Not Disturb and per-app muting, and retain dismissed important messages in accessible history. Respect existing notification preferences. |
| E | Keyboard and scaling consistency | Widget arrangements now persist across Plasma restarts at another scale; nine desktop UI checks and live 200% restart/100% return pass. Wider app/accessibility audit remains | Audit Settings, Store, Games, menu and popups with visible keyboard focus, Escape, large text and all supported scaling steps. Every action stays reachable on small screens without accidental horizontal scrolling. Preserve the original widget arrangement even after restarting Plasma at another scale. Include screen-reader and RTL validation. |
| F | Everyday-language search | Implemented in Settings and the menu; 16 search checks plus eight feedback checks pass. Live destinations, keyboard handoff and 100/200% layout checked. Translation catalogs updated; language coverage and screen-reader review remain release work | Queries such as "make text bigger", "headphones", "birthday" and "Windows files" reach the relevant setting or app. Search terms are translatable and results open the correct destination. |
| G | Clear return after restart or switching systems | Return summary, per-app/pending retry, normal app opening and dismissal implemented; notification-to-Settings flow and 100/200% keyboard/layout VM-checked. Pre-switch explanations added. Real Windows return, missing-document reopening and wider accessibility validation remain | Show what was restored and provide retry/reopen for missing work. Explain unsaved work and interrupted operations before leaving. Validate restoration and switching speed on real hardware. |

### Existing delivery and release work

| Priority | Work | Status | Acceptance checks |
|---|---|---|---|
| 1 | Restore work after a Windows trip: documents, browser tabs and window positions | Editor, Files and Zen slices implemented and VM-tested: saved Kate/KWrite documents, Files tabs/splits, geometry and Zen's native normal session in its original profile. Zen's startup preference is preserved; private windows stay closed. | Reopen real saved documents/tabs, restore multiple windows on their available screens, avoid duplicates, respect the off switch and handle an interrupted restore. State limits for unsaved/private work explicitly; test a real Windows round trip before release. |
| 2 | Reliable upgrades that preserve shortcuts and preferences | Profile migration implemented and VM-tested: ownership records, field-by-field launcher updates, failure retry and conflict-safe undo. Two live migration runs preserve existing choices and pins. Full image upgrade/reboot/rollback remains a release check. | Upgrade an existing profile with old pins and custom preferences; restart and sign in twice; preserve unrelated choices and verify rollback. |
| 3 | Store downloads with cancel, retry and recovery | Implemented and VM-tested: saved queue, independent workers, cooperative cancel, retry, interrupted-job recovery, network/space errors and catalog retry. Release checks remain for power loss and actual disk exhaustion. | Persistent queue; cancel/retry; recovery after network loss, app close or reboot; useful errors for unavailable catalogs and full disks. |
| 4 | Sleep/wake, display scaling and hardware support | Desktop scaling slice implemented and VM-tested at 100/125/150/175/200%; hardware validation remains | Keep widgets on screen and separate the bottom bars; return to the previous arrangement when scaling back. Record results for hybrid graphics, multiple monitors, docks, Bluetooth, controllers, battery drain and Secure Boot. |
| 5 | Clear recovery tools and complete keyboard/accessibility support | Calendar keyboard slice implemented; wider audit and recovery UI remain | Calendar day selection, note editing, repeat choice and close work by keyboard with visible focus. Recover from a failed boot/update and restore real files; finish screen-reader, large-text, reduced-motion and right-to-left flows across everyday apps. |

Visual follow-up: reuse Monet's painted window controls across its own apps, system
decorations, compatible GTK title bars and Zen. Apps that draw private, unthemeable controls
need individual integration rather than forced replacement of their window chrome.

Accessibility next: audit Settings, Store, the app menu and Games with keyboard only;
check focus order, dialog escape/return, announced labels and errors with Orca, then
large text, high contrast and reduced motion. Validate mixed-scale monitors on hardware.
The two calendars now open notes inward without shifting the month. Notes can repeat
every year; changes apply to the series, and 29 February repeats only in leap years.

Restoration follow-up, in order:

- Workspace return — delivered 2026-10-28: start apps together, preserve virtual-desktop
  memberships and above/below state, restore stacking/active window on an untouched automatic
  return, and wait for startup resizing before placement. Up to 64 eligible apps survive the
  checkpoint instead of twelve. Seventy-one focused checks and a live three-window/two-desktop
  return pass. The CLI stops on checkpoint-save failure; this part needs a new image to test.
- The product target is one continuous desktop around a Windows game: unchanged work before
  and after, native sign-ins preserved, and no routine recovery decisions. Remaining work
  includes complete per-app multi-window capture, broader app-specific recovery and hardware
  timing. Do not describe the current reopen adapters as preserving a running
  memory session.
- Trip-confirmed recovery lifetime — implemented 2026-10-28: new checkpoints bind to the
  exact switch and departure boot. A durable system return receipt replaces the twelve-hour
  cutoff, including long Windows sessions and clock changes. Partial recovery retains its
  confirmation across later trips/reboots. Failed restart commands cancel the pending trip
  and firmware target; unrelated checkpoints stay closed and available for review. Seventy-eight
  focused Linux VM checks and all 63 Rust workspace tests pass. Requires a matching CLI/helpers
  in a rebuilt image and a real Windows round trip; older checkpoints keep their old expiry.
- Unsaved-work protection — implemented and VM-checked 2026-10-28: a separate switch service
  sends normal window-close requests, waits for app save/discard/cancel decisions and never
  forces an unclosed window after a timeout. Cancel/Escape keeps the switch unarmed and uses
  the existing adapters to reopen already-closed supported work on this boot only. The root
  helper waits for explicit acceptance before arming the Windows boot and checks shutdown inhibitors.
  A live KWrite veto remained blocked for almost three minutes with its unsaved text intact;
  cancellation reopened the closed terminal once. Save-and-continue and simulated restart
  failure/reopening passed. 82 focused checks (plus six isolated Qt cases), all 65 Rust tests,
  Clippy and catalog checks pass. Real firmware/reboot and privileged inhibitor validation
  still require a matching image. Apps that don't expose unsaved work through close/inhibition
  remain an adapter limit. Save As recovery during these prompts is described below.

- Files — delivered: read current local-folder tabs and split views, restore duplicate tabs
  in order and the active tab/side, and verify the actual result. The native image adapter
  also retains selected/current items, expanded folders, scrolling, split widths and custom
  tab names. Older builds keep folder-only accessibility capture.
  A private native session avoids Dolphin's stale global checkpoint and handles Qt Wayland's
  empty session key. Multiple ordinary windows now have independent capture/launch receipts;
  matching live windows and completed receipts prevent duplicates even with identical folders.
  Native Wayland capture also maps up to 16 same-process windows by exact surface identity;
  each window has its own recovery receipt. Surviving windows retain their newer choices.
  Follow-up: remote/search tabs, navigation history,
  changed monitor/scaling combinations and broader language/RTL validation.
- Zen — delivered: reopen the original profile using its native normal-session recovery,
  verify the saved tabs before completing the receipt, and preserve the startup preference.
  Multiple profiles now recover independently, including multiple normal windows and pinned
  tabs. Verification follows Zen's native synchronized sidebar without changing its files or
  preferences. A multi-window browser is asked to quit through its menu to preserve the group.
  Private sessions are excluded independently; partial recovery retains per-profile receipts.
  Follow-up: other browsers, browser spaces/splits, monitor changes and broader preference
  combinations in live tests. Reduce the bounded 16-second checkpoint wait.
- Multiple-window/profile verification — 2026-10-28: three Files windows retained their tabs,
  splits and separate positions, with the surviving window untouched. Two Zen profiles returned
  with three normal windows; private windows stayed closed. A partial return preserved the
  other profile's PID. All 102 focused tests plus seven Qt cases passed, and the VM checkpoint
  was restored. These were controlled Wayland returns, not a Windows firmware/reboot test.
- Editors — delivered for ordinary Kate/KWrite windows: independent process/window receipts,
  local tab grouping/order, active tabs/panes, visible cursor positions, two-pane Kate splits
  and KWin placement/minimized state. Private native sessions are verified against live tabs.
  Missing documents remain pending; Settings' Retry documents reuses the original editor or
  opens only the remaining files if it has closed. Completed windows and manually reopened
  documents are not duplicated. Legacy captures also retain missing-file recovery.
  111 focused VM checks passed, plus live multi-editor, missing-file/retry and cancelled-switch
  checks with an unsaved survivor. The VM checkpoint was restored afterwards.
  Follow-up: multiple windows within one process, inactive-tab cursors,
  tab-limit-hidden/remote/untitled documents, ambiguous same-document background splits on unpatched editors,
  and returning late files to their original pane without disturbing newer work.
- Save As during protected departure — implemented for uniquely owned Kate/KWrite native
  sessions: refresh local document references from the editor's final write before allowing
  restart or reopening closed editors after cancellation. First saves and renamed paths
  replace the earlier references; discarded untitled documents are excluded. A failed final
  read cancels the switch and keeps the last good recovery data. The VM verified first-save,
  rename, cancelled Save As and cancellation after a renamed document had already closed;
  original files/unsaved survivors stayed intact and retries made no duplicate windows.
  All 132 focused VM tests passed; the VM checkpoint was restored and Notes stayed unchanged.
  The unpatched-editor fallback leaves shared anonymous sessions explicitly unconfirmed.
  Image integration for those sessions is described below. Follow-up: multiple windows per
  process, live validation of named-session changes during departure, and richer layouts.
- Independently closed editors — implemented and VM-checked 2026-10-28: watch all supported
  editor windows before Windows preflight and before any normal close requests. Continue
  watching new windows of checkpointed editors while another app blocks the switch. Preserve
  each original native-file stamp across polls; a later shared writer invalidates earlier
  exclusive ownership. Cancellation during setup cannot arm a late watch or start preflight.
  The live VM saved/closed Kate manually while KWrite remained open, then cancelled Monet:
  the latest filename reopened once, the unsaved survivor stayed running and no restart was
  accepted. All 136 focused tests passed, including twelve isolated Qt cases.
  The VM checkpoint was restored; temporary fixtures were removed and Notes stayed unchanged.
- Shared editor sessions — implemented and VM-checked 2026-10-28: the image's Kate/KWrite
  library writes private per-process final receipts after native save prompts succeed.
  Simultaneous anonymous instances retain separate Save As/first-save paths, tab order,
  selected panes/tabs and visible cursors. Cancel disarms live editors; failed receipt writes
  veto closing. Temporary paths scheduled for deletion are excluded, but permanent Save As
  copies remain recoverable. Unpatched builds keep the conservative fallback above.
  Live checks covered two KWrite instances, two Kate instances with both split orientations,
  cancelled Save As, cancelled switching, retry without duplicates, a receipt-write veto,
  and warnings for newly added main windows/third panes. 151 broad VM checks and 41 final
  focused checks passed. The native component built, sealed and installed in its matching
  container; a different runtime was correctly rejected. Full-image/Windows validation,
  same-process multi-window restoration remain open. Nested layouts are covered below.
  Restored `ai-before-shared-editors-1028`; the VM is Running, fixtures/build environment
  are gone and the original Notes checksum is unchanged.
- Nested editor layouts — implemented and VM-checked 2026-10-28: the native adapter keeps
  the splitter tree, tab order, active panes/tabs and visible cursors for up to 16 panes
  (100 tabs per pane, 200 tab entries total). Missing-file panes prune only their branch;
  old flat checkpoints and the unpatched two-pane accessibility fallback still work.
  A bounded metadata query verifies the actual tree and restores only matching visible
  cursors still at zero. Repeated views of the same document retain the correct active pane.
  All 159 focused VM regression checks passed. The native component compiled; live tests
  covered four nested panes and a three-pane row, Save As/first saves, a cancelled chooser,
  cancelled-switch recovery, relative sizes/cursors, missing-file retry without duplicates,
  legacy single/two-pane checkpoints, KWrite and the unpatched editor fallback.
  Full-image/Windows testing, same-process multiple windows, inactive-tab cursors and
  returning late files to their original pane without disturbing newer work remain open.
  Restored `ai-before-nested-editors-1028`; the VM is Running, fixtures/build environment
  are gone and Notes retained its original checksum.
- Same-process window identity — prototype VM-checked 2026-10-28; image packaging is covered
  below, while automatic editor restoration still needs integration. A read-only native KWin extension maps a Qt Wayland surface
  and process ID to the exact window UUID. Identical titles/positions, minimization, closing
  one sibling, invalid IDs and same-process collisions across Wayland connections passed
  live checks in an isolated nested compositor. Lookup left focus, stacking and geometry
  unchanged; ambiguous matches returned no identity. Exact runtime versions/library hash
  and dynamic linking were checked before loading. Reproducible fixtures are in
  [prototypes/window-identity](prototypes/window-identity/README.md).
  Next: per-window close receipts and same-process cancellation recovery that preserve shared
  document objects, including a later Save As in a surviving window. The native capture/launch
  interfaces are described below; automatic placement still needs integration. Full-image and
  Windows/USB testing remain open; this prototype does not change current recovery behavior.
  Restored `ai-before-window-identity-1028`; the VM is Running, both fixture directories
  and the build container are gone, and Notes retained its original checksum.
- Native multi-window editor interfaces — implemented and VM-checked 2026-10-28; automatic
  departure is still gated to one main window per process. The new metadata query resolves
  up to 16 windows in one compositor call, bounds the process to 200 tab entries, and validates
  exact identities and layouts before applying targeted cursors. The Python helper can reopen
  several windows in one process with shared document IDs. Live Kate tests kept a shared
  document's Save As path in both windows, preserved a cancelled chooser, and reopened tabs,
  splits and visible cursors. Final native tests passed for Kate and KWrite, including stale
  IDs, missing compositor support, nonzero cursors and unchanged single-window close receipts.
  All 163 focused regression tests and eight final bundle tests passed. The native library
  built, sealed with corresponding source, and installed in its matching container. The full
  bundle guard rejected the differing guest runtime; disposable VM fixtures separately checked
  matching Qt/KDE/editor binaries and dynamic linking.
  Remaining: per-window final receipts, shared unsaved-buffer recovery inside a surviving
  editor on Cancel, compositor image packaging, automatic window placement and Windows/USB
  testing. This does not yet enable automatic multi-window restoration.
  Restored `ai-before-editor-window-map-1028`; the VM is Running, build/editor/compositor
  fixtures and the container are gone, and Notes retained its original checksum.
- Native editor group departure — implemented and VM-checked 2026-10-28; automatic switching
  is still limited to one main window per editor process. The group protocol uses native Quit
  so sibling windows and their shared document objects remain alive through save prompts.
  Final receipts bind each window's layout and post-Save-As paths to its compositor UUID.
  Cancel, controller loss, changed window membership, missing identity support and receipt
  failures cannot partially close the group. Accepting an old save dialog after cancellation
  no longer completes its close request, including the existing single-window path.
  All 165 focused VM tests passed. Live Kate/KWrite checks covered shared unsaved buffers,
  Save As, first saves during close, cancelled choosers, late Save after Cancel, write vetoes,
  missing resolver support and reopening both windows together. Controller loss, rearming,
  stale-token cancellation and a changed window group were also checked in native Kate.
  This replaces the proposed destroy-and-recreate strategy for closed sibling windows.
  Remaining: automatic group capture/departure/recovery and
  exact placement, inactive-tab cursors, full-image and Windows/USB testing.
  Restored `ai-before-editor-group-exit-1028`; the VM is Running, disposable editor/compositor
  fixtures and the build container are gone, and Notes retained its original checksum.
  Evidence and cleanup checks are in `target/editor-window-cancel/`.
- Native window identity image bundle — implemented and VM-checked 2026-10-28. The image
  builds the read-only KWin module against its assembled runtime, checks runtime package
  versions and compositor binary hashes before/after adding development packages, then
  verifies source/module hashes and linked symbols before installation. Corresponding source
  and the runtime manifest ship with it. Existing disabled preferences remain respected.
  All 153 focused VM tests passed. The production build and matching-container installation
  succeeded; the guard rejected the guest's differing transitive runtime. The exact packaged
  module passed the isolated compositor's default-loading, identical-window, stale-ID and
  ambiguous Wayland-connection checks. A separate session kept an explicit disabled setting.
  Automatic group capture/departure/recovery and exact placement remain open, as do full-image
  and Windows/USB testing. Evidence is in `target/window-identity-image/evidence.json`.
  Restored `ai-before-window-identity-image-1028`; the VM is Running, fixtures/build/container
  are gone, and Notes retained its original checksum (`target/window-identity-image/cleanup-results.json`).
- Targeted missing-file retries — implemented and VM-checked 2026-10-29. The native editor accepts
  a bounded list of existing local files for an exact window UUID. New tabs use that window's
  current pane, preserving its selection, cursor and split layout; shared unsaved buffers and
  existing aliases are reused. Invalid requests and unavailable identities cannot fall through
  to another active window. The existing single-window recovery caller now uses this operation
  when available. Automatic multi-window capture/departure/recovery and placement still need
  integration, including windows whose documents are all temporarily missing.
  All 152 focused VM tests passed across the runs. Final native checks covered Kate/KWrite
  retries, actual reopened contents, preserved shared unsaved buffers, Save As and cancellation.
  The guarded source patch matched the compiled tree; its source bundle installed in the
  matching container and rejected the guest's differing runtime. Evidence is recorded in
  `target/editor-targeted-retry/evidence.json`.
  Restored `ai-before-editor-retry-guards-1028`; the VM is Running, fixtures/build/container
  are gone, and Notes retained its original checksum (`target/editor-targeted-retry/cleanup-results.json`).
- Automatic editor window groups — implemented and VM-checked 2026-10-29. Capture and
  protected departure now retain each native Kate/KWrite window's exact identity and final
  Save As/first-save paths. Recovery opens one process with shared document IDs, verifies
  the ordered layouts and maps the new window IDs to the original frames. Existing windows
  remain untouched. Per-window owners/pending lists keep late files in their correct window;
  an unavailable window can remain empty while its siblings return. All files missing waits
  without launching replacements; intentionally empty source windows can still reopen.
  The 170 focused VM tests passed. Native Kate/KWrite tests covered the full automatic helper
  path, shared unsaved buffers on Cancel, Save As, first saves, exact placement, missing and
  empty windows, targeted Retry and repeated requests without duplicate windows.
  KWrite may widen a small empty window to fit its first document view's minimum size.
  Remaining: creating a replacement for a manually closed window while its siblings still
  run (its files stay pending), late-file sets that exceed the current pane's tab limit,
  inactive-tab cursors, X11 identity, full-image and Windows/USB
  testing. Evidence is in `target/editor-auto-groups/evidence.json`; the reusable native
  fixture is `prototypes/window-identity/verify-auto-groups.py`.
  Restored `ai-before-auto-editor-groups-1029`; the VM is Running, temporary fixtures and
  the build container are gone, and Notes retained its original checksum. Cleanup evidence
  is in `target/editor-auto-groups/cleanup-results.json`.
- Closed editor replacement — implemented and VM-checked 2026-10-29. Explicit Retry can now
  recreate a manually closed window inside its surviving Kate/KWrite process. It restores
  available tabs, nested splits and visible cursors, reuses shared unsaved buffers, and maps
  the replacement to the original frame. Surviving windows retain their state and focus;
  focus correction stops when the desktop choice or pointer position changes. A durable
  request and native duplicate protection make lost replies and interrupted recovery safe
  to retry. Oversized checkpoints cannot replace the last readable recovery record.
  All 179 focused VM tests passed, followed by native replacement, automatic group and
  protected-departure regressions in both editors. Those regressions include Save As,
  first saves, cancelled choosers, shared unsaved text and exact window placement.
  The guarded patch matched all ten compiled source files; the sealed source/binary bundle
  installed in its matching container and rejected the guest's different full runtime.
  Evidence is in `target/editor-replacement/evidence.json`; the reusable native fixture is
  `prototypes/window-identity/verify-replacement.py`.
  Remaining: a replacement closed before its UUID is confirmed stays pending; native closed
  receipts are needed to advance that interrupted request safely. Replacement records are
  bounded to 64 per editor process. Late-file sets exceeding the current pane's tab limit,
  inactive-tab cursors, X11 identity, full-image and Windows/USB testing remain open.
  Restored `ai-before-editor-replacement-1029`; Hyper-V reports Running, the temporary build,
  fixtures and container are gone, and Notes retained its original checksum. Cleanup evidence
  is in `target/editor-replacement/cleanup-results.json`.
- Interrupted replacement receipts — implemented and VM-checked 2026-10-29. The editor now
  distinguishes a replacement that closed from an unconfirmed request. Recovery retains its
  pending files and leaves the window closed until a later explicit Retry. Durable attempt IDs
  let that Retry proceed without duplicating a still-live or in-progress replacement; older
  requests remain accepted. A failed checkpoint write retains the original request for replay.
  All 181 focused VM tests passed. The live replacement fixture passed in Kate and KWrite,
  including closing before confirmation, a later successful Retry, cross-attempt duplicate
  refusal, old requests, shared unsaved buffers, nested panes/cursors and survivor focus/frame.
  The guarded source patch matched the build, and its sealed bundle installed in the matching
  container. Evidence is in `target/editor-closed-receipts/evidence.json`.
  This resolves the close-before-confirmation follow-up above. The 64-record process limit,
  late-file pane limits, inactive-tab cursors and full-image/Windows/hardware checks remain.
  Restored `ai-before-editor-closed-receipts-1029`; Hyper-V reports Running, the temporary
  build/fixtures/container are gone, and Notes retained its original checksum. Cleanup
  evidence is in `target/editor-closed-receipts/cleanup-results.json`.
- Large missing-document retries — implemented and VM-checked 2026-10-29. Native capture,
  replacement, saved-session parsing and Retry now allow a pane to use the existing
  200-entry process budget. The separate 100-tab pane/request bottleneck is removed.
  Returning files still enter the current pane without rearranging the person's newer layout;
  requests exceeding the remaining process capacity are refused before opening files.
  All 183 focused tests passed, with the updated legacy-parser boundary check rerun separately.
  Live Kate/KWrite tests captured and recovered a 200-entry group, returned 197 missing files
  in one Retry, retained sibling state/shared unsaved text/frame/focus/visible cursor, refused
  an extra file and recreated the large window after it closed. Save As, cancellation,
  placeholders, empty windows and repeated-Retry checks also passed in that fixture.
  The guarded source patch matched the compiled tree; the sealed bundle installed in its
  matching container. Evidence is in `target/editor-large-retry/evidence.json`.
  The 200-entry process budget remains; inactive-tab cursors, X11 identity, full-image and
  Windows/USB/hardware checks are still open.
  Restored `ai-before-editor-large-retry-1029`; Hyper-V reports Running, the temporary
  build/fixtures/container are gone, and Notes retained its original checksum. Cleanup
  evidence is in `target/editor-large-retry/cleanup-results.json`.
- Inactive-tab cursor recovery — implemented and VM-checked 2026-10-29. Native Kate/KWrite
  capture now keeps known positions for every saved tab without selecting hidden tabs or
  creating their views. Pending positions survive another departure and first selection,
  with independent positions for shared files in different panes/windows. Save As keeps
  those positions with the new paths. Late-file Retry carries the original active pane's
  position into the current pane; closed-window replacement restores all known positions.
  Live nonzero cursors stay untouched, shortened files clamp offsets, and malformed cursor
  requests are rejected before mutation. Older checkpoints remain readable. Single-window
  recovery now keeps its launch pending when cursor restoration cannot be confirmed.
  All 188 focused VM tests passed. The expanded native group fixture passed for Kate and
  KWrite, covering Save As/first-save, cancellation, three shared-document carets, repeated
  lazy recovery, replacement, late files, malformed requests, truncation and the existing
  200-entry/197-file Retry cases. A fresh guarded patch matched all twelve compiled source
  files, and the sealed source/binary bundle installed in the matching container.
  Evidence is in `target/editor-hidden-cursors/evidence.json`. Unknown positions, selections,
  scroll state, X11 identity, full-image and Windows/USB/hardware checks remain open.
  Restored `ai-before-editor-hidden-cursors-1029`; Hyper-V reports Running, the temporary
  build/fixtures/container are gone, and Notes retained its original checksum. Cleanup
  evidence is in `target/editor-hidden-cursors/cleanup-results.json`.
- Editor scroll recovery — implemented and VM-checked 2026-10-29. Kate/KWrite now retain
  per-tab vertical/horizontal scroll positions, wrapped top columns and view wrap mode.
  Pending positions follow Save As, survive repeated departures and apply when hidden
  tabs first open. Recovery waits through the editor's initial resize; later user input
  takes priority, and scrolling protects a live view even when its caret remains at zero.
  Late-file Retry carries the original pane's position into the new tab. A newly recreated
  window restores its own positions rather than keeping a cursor inherited from a shared
  sibling. Shorter documents clamp safely; malformed metadata is refused before mutation.
  All 191 focused VM tests and the expanded native Kate/KWrite group fixture passed,
  including Save As/first saves, cancellation, hidden/shared tabs, replacement, late files,
  wrapped lines and the existing 200-entry/197-file Retry checks. A fresh patch matched all
  twelve compiled source files; the sealed source/binary bundle installed in its matching
  container. Evidence is in `target/editor-view-state/evidence.json`.
  Unknown positions, selections/folding, X11 identity, full-image and Windows/USB/hardware
  checks remain open. Restored `ai-before-editor-view-state-1029`; the VM is Running,
  temporary fixtures/build/container are gone and Notes retained its original checksum
  (`target/editor-view-state/cleanup-results.json`).

- Editor selection recovery — implemented and VM-checked 2026-10-29. Ordinary and
  rectangular selections now follow their documents through Save As, repeated departures,
  hidden-tab creation, closed-window replacement and late-file Retry. Coordinate-only
  metadata keeps the range, cursor direction and rectangular mode without copying selected
  text. Later selections remain untouched, shortened normal ranges clamp to the document,
  and rectangular columns can retain their native position beyond line ends.
  All 194 focused VM tests and the expanded native Kate/KWrite group fixture passed.
  Checks include actual selected text in generated fixtures, continuing a backwards
  selection through the native editor action, independent shared-file selections, malformed
  request rejection and unchanged file contents. Existing scroll, cancellation, placement
  and 200-entry/197-file Retry checks also pass. A fresh patch matched all twelve compiled
  files, and the sealed source/binary bundle installed in its matching container.
  Evidence is in `target/editor-selections/evidence.json`. Multi-caret selections/anchors,
  folding, unknown positions, X11 identity and full-image/Windows/USB/hardware checks remain.
  Restored `ai-before-editor-selections-1029`; the VM is Running, the temporary build and
  container are gone, and Notes retained its original checksum
  (`target/editor-selections/cleanup-results.json`).

- Editor folding recovery — implemented and VM-checked 2026-10-29. Native Kate/KWrite
  folds, including nested ranges and explicitly unfolded views, follow edited Save As
  documents, repeated departures, lazy shared tabs, recreated windows and late-file Retry.
  Only bounded ranges and the editor's file checksum enter the checkpoint. Changed files
  and modified buffers do not receive stale folds; replay preserves later unfolding even
  with the caret at zero. Existing per-pane cursors, selections and scroll state still apply.
  All 197 focused VM tests and the full native Kate/KWrite group fixture passed. Native
  actions verified parent/child unfolding, independent shared-file folds and later choices;
  malformed, crossing, duplicate and excessively deep ranges were refused. The full run
  also retained cancellation, Save As/first-save, selection, scroll, placement, 200-entry
  capture and 197-file Retry checks. A fixture comparison now uses the post-Save All state
  because saving makes folding metadata available for a previously modified buffer.
  A fresh guarded patch matched twelve compiled files; the sealed source/binary bundle
  installed in its matching container. Evidence: `target/editor-folding/evidence.json`.
  Persistent folded plugin ranges were still open at this checkpoint; the native importer
  dropped that combination's persistent bit. The next entry records the fix. Multi-caret
  anchors, unknown positions, X11 identity, full-image and real Windows/USB/hardware checks
  remain open too.
  Restored `ai-before-editor-folding-1029`; Hyper-V reports Running, the temporary build,
  fixtures and container are gone, and Notes retained its original checksum
  (`target/editor-folding/cleanup-results.json`).

- Persistent editor folding — implemented and VM-checked 2026-10-29. A guarded one-line
  KTextEditor fix retains both persistent/folded flags when native ranges are imported.
  Unfolding now retains plugin-created anchors, including nested ranges. The image builds
  and verifies the engine alongside Kate/KWrite's shared library against the installed
  runtime, preserving source, hashes, dependencies, editor functions/vtables and owned data.
  The engine uses its installed RPM's optimization/hardening flags and Fedora linker flags;
  incidental Qt/std template data is not treated as the engine's public data contract.
  The runtime explicitly includes the binary-inspection tools used by the install guard.
  All 201 focused VM tests passed; the 12 bundle tests passed again after refining the
  symbol guard. The original engine failed the new native regression; the patched engine
  passed all seven native folding tests, including unfolding/refolding without text changes.
  The full Kate/KWrite fixture passed persistent and ordinary folds through edited Save As,
  repeated hidden-tab recovery, independent shared views, window replacement and late Retry,
  alongside cancellation, first-save, selections, scrolling, placement and capacity checks.
  Fresh patches matched twelve Kate files and three engine files. Both sealed libraries
  installed in the matching container; the different guest runtime was rejected by the
  full bundle guard. Evidence: `target/editor-persistent-folds/evidence.json`.
  Restored `ai-before-persistent-folds-1029`; the VM is Running, temporary build/container
  state is gone and Notes retained its original checksum
  (`target/editor-persistent-folds/cleanup-results.json`). Multi-caret state, unknown
  positions, X11 identity and full-image/real Windows/USB/hardware checks remain open.

- Multi-caret editor recovery — implemented and VM-checked 2026-10-29. Kate/KWrite retain
  extra cursors, selection direction and anchors, including mixed selected/unselected
  cursors and selections only on secondary cursors. The same metadata follows Save As,
  hidden tabs, repeated departures, window replacement and missing-file Retry. Shared files
  keep separate state in each pane/window. No document contents enter the checkpoint.
  A bounded extension to selection metadata supports up to 1,024 distinct carets per view;
  old selection/checkpoint formats remain readable. Helpers and the paired engine validate
  complete requests before mutation. Shortened files clamp/coalesce positions, and a
  per-view marker prevents replay from undoing later cleared selections or cursors.
  The three-pane test caught a shortened-file bug: normal and multi-caret positions on
  removed lines now clamp to the document end instead of resetting to column zero.
  All 204 focused VM tests, 32 native multicursor tests and seven native folding tests
  passed. Native Shift+Right/Delete tests verified restored anchors and actual editing;
  the full Kate/KWrite fixture passed the new cases and previous cancellation, Save As,
  missing-file, placement, selection, scroll, folding and capacity checks. Three panes
  retained different extra-cursor sets for the same document after replacement.
  Fresh guarded patches matched thirteen Kate files and eight engine/test files; both
  sealed libraries installed in the matching container with verified corresponding source.
  Evidence: `target/editor-multicaret/evidence.json`. Restored `ai-before-multicaret-1029`;
  the VM is Running, temporary build/container state is gone, and Notes is unchanged
  (`target/editor-multicaret/cleanup-results.json`). Native input-mode restrictions,
  unknown positions, X11 identity and full-image/real Windows/USB/hardware checks remain.


- Background-work departure protection — implemented and VM-checked 2026-10-29.
  Store services now acquire a shutdown inhibitor before their worker starts and retain it
  until the queue finishes, even after the Store window closes. The switch dialog reads
  inhibitors asynchronously before each close pass, shows the blocking apps/reasons as
  plain text, and waits without closing other windows. Cancel remains responsive; failed,
  malformed or stalled queries cancel safely. Sleep-only/delay inhibitors do not block
  this stage. Editor watches and the final privileged restart inhibitor check remain active.
  All 95 focused VM tests plus 18 isolated Qt checks passed. Live real-service checks at
  100% and 200% verified untouched windows while work runs, one acceptance after completion,
  Escape preserving the worker, queue cancellation releasing the veto, and service loss
  releasing it while retaining an Interrupted job. The restart helper was a controlled pipe
  stub; no firmware or reboot request was issued. Catalog checks passed.
  Evidence and dialog screenshots: `target/background-work/evidence.json`. Restored
  `ai-before-background-work-1029`; the VM is Running, fixture/services are gone and Notes
  is unchanged (`target/background-work/cleanup-results.json`). Full-image/privileged reboot
  and physical Windows/USB checks remain. Background apps without any veto/inhibitor still
  need app-specific integration.


- Save As departure follow-up — implemented and VM-checked 2026-10-29. Qt Save/Save As
  dialogs can be normal transient Wayland windows. Departure now keeps them in its wait
  list without mistaking them for extra editor main windows and cancelling the switch.
  Unpatched editors also retain observed shared-writer ambiguity after the other writer
  exits; an observed session-name change cancels before reading the old session's paths.
  Native per-process receipts remain independent of named/shared session files.
  All 179 focused VM tests and 19 isolated Qt checks passed. Real Kate/KWrite 26.08.1
  verified first saves, a renamed document after vetoing Close, cancelled Save As/switching,
  and safe cancellation after Save Session As. Recovered documents opened once with their
  new paths and contents; original files and the unsaved survivor remained intact.
  Evidence: `target/save-as-session/evidence.json`. The privileged restart was simulated;
  full-image/Windows/USB tests and unobserved changes between fallback polls remain open.
  Restored `ai-before-save-as-session-1029`; the VM is Running, temporary fixtures are gone,
  and Notes is unchanged (`target/save-as-session/cleanup-results.json`).

- Files view-state recovery — implemented and VM-checked 2026-10-29. The image now builds
  a paired Dolphin executable/private library from the matching distribution source RPM,
  preserving downstream fixes and refusing mismatched runtimes. Read-only native metadata
  adds current/selected paths, expanded folders, scroll offsets, split widths and custom
  tab names without activating hidden tabs or reading document contents. Private native
  sessions restore that state; launch completion requires verified live metadata. Missing
  items are skipped, offsets clamp to the available range, and existing windows keep their
  newer choices. Older builds retain folder-only accessibility capture.
  All 210 focused restoration tests passed, including native Qt stream/splitter checks.
  Live Dolphin 26.08.1 on the VM's Wayland display verified hidden tabs, Unicode labels,
  separate window sizes/positions, bottom scrolling, same-folder split selections, vanished
  current/selected/expanded items, dangling symlinks, unavailable folders and repeated Retry.
  The final bundle's executable/library hashes and corresponding source were checked;
  the mismatched guest runtime was refused and its system binaries remained unchanged.
  Evidence: `target/files-view-state/evidence.json`. Full-image, Windows/USB, remote/search,
  same-process multiwindow, navigation history and broader monitor/RTL checks remain open.
  Restored `ai-before-files-view-state-1029b`; temporary fixtures, containers and image are
  gone, and Notes is unchanged (`target/files-view-state/cleanup-results.json`).

- Files shared-process windows — implemented and VM-checked 2026-10-29. Native capture
  maps up to 16 main windows to KWin UUIDs using the existing surface identity plugin.
  Each window keeps its own state, frame and recovery receipt. Object discovery survives
  closing the first window; cancellation preserves live IDs and their newer choices.
  Pending launches reserve their windows before identical-folder siblings can match them.
  All 216 focused regression tests passed. A matching Dolphin 26.08.1/KWin runtime in the
  VM verified three main windows in one process, first-object closure, changed surviving
  selections, exact placement, missing-folder retry and repeated retry without duplicates.
  Unloading the identity plugin left shared captures unconfirmed without launching copies;
  the last surviving object still captured through the ordinary single-window method.
  The unpatched guest's accessibility fallback passed. Native bundle/source hashes match
  the checkout, and guest system binaries remain unchanged. Evidence:
  `target/files-windows/evidence.json`. Full-image, physical Windows/USB, remote/search,
  navigation history and broader monitor/scaling/RTL checks remain open.
  Restored `ai-before-files-windows-1029`; the VM is Running, fixtures/containers/image are
  gone, and Notes is unchanged (`target/files-windows/cleanup-results.json`).

- Extend protected departure to background-only apps that expose neither a window veto nor
  a shutdown inhibitor.
- Run the complete Monet → Windows → Monet flow and unplug/scale displays on real hardware.

Implementation and current limits: [docs/RESTORATION.md](docs/RESTORATION.md).

### Passwords — development preview, 2026-10-28

Build an in-house Monet experience around an established local vault implementation.
The first prototype in `prototypes/passwords/` adapts KeePassXC 2.8.0's native UI while
retaining its KDBX writer, locking, recovery and browser authorization. It is outside the
normal image/installer and is for synthetic logins. It includes an isolated preview launcher,
checksum-pinned build, source preservation, guarded patching, and native Qt checks.

The VM proof uses the standard native-messaging proxy with a disposable Zen profile and
the official browser extension. Pairing and site access require the existing approval
dialogs. Real extension filling passed; denied access, an unrelated hostname and a locked
vault left the fields empty. This is not yet automated browser setup for users.
Three patch checks, eight compiled suites and eight GUI scenarios passed. The encrypted
backup recovered independently and a corrupted copy was rejected. Reconnecting after a
running-app replacement needed the extension's Reload button. Evidence was saved on the
host and the VM's starting checkpoint restored.

Next: complete the Monet flows and translations, surface browser permission requests,
package reversible multi-profile setup, review security, and design/test optional Windows
access with encrypted backup and conflict recovery. Session tokens remain app-owned;
vault secrets must never enter restoration checkpoints. [Details](docs/PASSWORDS.md).

Save/update follow-up — VM-checked 2026-10-28: the real Zen extension prompts before
saving a new account or changing a password. Cancellation leaves the vault unchanged;
an approved update retains the previous password in history without making a duplicate.
The test server now discards submitted values and cannot serve fixture files. Five
patch/fixture checks pass. Real-site detection, multi-step forms and clearer cancelled-update
feedback remain open; this is still an isolated preview, not part of the installed OS.

Further VM checks — 2026-10-28: same-origin frame filling and a two-step username/password
login pass. Cross-origin child frames and a saved site embedded by an unrelated parent
remain empty with the vault unlocked. Six patch/fixture checks pass. Multi-step saving,
real-site detection, additional frame attacks and multiple vault associations remain open.

### People moving from Windows, macOS or another Linux desktop — 2026-10-28

- Delivered and VM-checked: familiar names in Settings and menu search reach installed
  Monet tools. Finder/File Explorer/Nautilus reach Files, Task Manager/Activity Monitor
  reach System Monitor, and Notepad/TextEdit, Snipping Tool, archive/PDF tools and software
  stores have matching destinations. Hidden or removed launchers are excluded. Late-arriving
  suggestions no longer scroll above the menu's visible area while typing.
- Store suggests available apps for Pages/Numbers/Keynote, iMovie/Final Cut, GarageBand/Logic
  and nearby sharing as well as its existing Windows-app suggestions. It explains that
  features and formats differ and gives an honest fallback when no suggestion exists.
  These are task alternatives, not native-format or protocol compatibility promises;
  LocalSend requires its app on the other device and does not implement AirDrop.
- Verification: 44 focused checks pass. Live Settings-to-Files and menu-to-System-Monitor
  launches, Store suggestions/detail navigation, and menu/Store layouts at 100/200% pass.
  Screen-reader, RTL and translated new text remain release checks. Evidence is recorded
  in [docs/TESTING.md](docs/TESTING.md).

Migration progress — 2026-10-28: Settings now reviews an HTML export for an explicitly
selected Zen profile, skips existing/repeated URLs, reports unsupported links and refuses
corrupt exports or busy profiles. It prepares a private file containing a separate import
folder; Zen performs the native import. Checking the result reads the selected profile,
and the latest import remains checkable after Settings restarts. The VM confirms that
existing bookmark IDs and the other profile's database are unchanged. Re-review finds no
new links after import; manually importing the same prepared file twice still adds duplicates,
which verification detects. Undo is deleting that imported folder in Zen, not an automatic
database rollback. Custom profiles outside Zen's Flatpak directory and broader source-browser
exports remain validation work. The native file picker showed mixed light/dark styling in
this VM; check the portal theme in the complete image. Synthetic DOCX/XLSX/PPTX round trips and
PDF exports pass in LibreOffice; live Writer/Calc edits save, and the spreadsheet recalculates.
PDF/PNG default-app opening passes. These are basic format checks, not full Office/iWork fidelity.

The earlier seven failing checks are resolved: five stale interaction/dispatch assertions
now cover the current contracts; weather's inline component scope is corrected; microphone
and notification Retry actions use a shared painted button with keyboard coverage.
The full VM suite passes: 746 tests, including the previously unavailable PowerShell, NumPy
and Node checks; the eight reported notification skips run in their passing isolated wrapper.
Import and navigation regression checks have also been added. Detailed results
and release limits are in [docs/TESTING.md](docs/TESTING.md).

Next, in order:

1. Walk through a first day from each source OS using disposable copies of real-format
   documents and browser exports. Expand the checked Zen import to real exports from each
   source browser and custom profile locations; retain profile isolation, duplicate filtering,
   explicit verification and the native undo path. Build safe,
   explicit password migration on the reviewed vault integration; never silently copy secrets.
2. Verify opening, editing and saving common office/PDF/photo files, default-app choices,
   removable drives, phone file transfer and nearby sharing. Say which features and formats
   are unsupported before a person risks their only copy. Test actual file interchange,
   not just whether the suggested app opens.
3. Complete continuity and recovery: broader editor/window layouts and unpatched-editor Save As fallback,
   additional browsers and vault profiles, then actual sleep/wake and Windows return on hardware.
   Keep the existing restoration acceptance checks; search aliases are not session migration.

Store downloads now live in `~/.local/state/monet/store/downloads.json`, atomically saved
with mode 0600 before work begins. A separate user service serializes Flatpak transactions,
so closing Store leaves downloads running. Cancel waits for Flatpak's cancellation cleanup;
Retry keeps the exact app reference and installation, reusing cached downloads where possible.
A lost worker or reboot leaves an interrupted request for explicit retry. Successful commits
are checked against the installed app before completion; a late cancel cannot undo a completed
install. Downloads stays available even when the catalog is unavailable. See the Store checks
in [docs/TESTING.md](docs/TESTING.md) for live evidence and remaining release validation.

## 1. Vision

A desktop OS that is as easy to set up as Windows, as calm to use as macOS, and
plays every PC game:

- **Linux (Monet)** for everything: browsing, work, media, and every game that runs
  through Proton.
- **A hidden, minimal Windows** used only for games Linux can't run, mostly
  games with kernel-level anti-cheat.
- **Switching takes seconds and one click.** The user thinks in terms of games,
  not operating systems.

### What makes Monet different

Existing gaming distros (SteamOS, Bazzite, ChimeraOS, Nobara, CachyOS) are
good at running games *on Linux*, but they leave anti-cheat games unsolved.
Monet's unique parts are:

1. **"Play on Windows"**: anti-cheat games get a button that switches to
   Windows, starts the game, and returns to Monet when you quit.
2. **Windows as a game console**: Monet installs and strips Windows itself, so
   the user never has to deal with Windows setup, ads, or clutter.
3. **Fast switching**: one click restarts into the game in Windows, and
   quitting it restarts into Monet. Windows always shuts down fully, so Monet
   can safely use its drive.
4. **A simple, opinionated design** inspired by Apple's simplicity, with its
   own visual identity.

### Non-goals

- ❌ Bypassing, spoofing, or emulating anti-cheat. We use real Windows.
- ❌ Running Windows in a VM for anti-cheat games. Vanguard and Ricochet block VMs.
- ❌ Distributing Windows or a modified Windows ISO.
- ❌ Writing our own kernel, Wine, or drivers.

---

## 2. Name check: "Monet"

- No existing operating system called "Monet" turned up in a search.
- "MONET" is a trademark in a few unrelated software areas (contact-center
  scheduling, content rating). Trademarks are tied to a field, so an OS is
  probably fine, but **run a proper search** (USPTO, EUIPO, class 9 and 42)
  before a public launch.
- Android 12's color system was codenamed "Monet". That was an internal
  codename, not a product, so it isn't a conflict.
- Bonus: Claude Monet's paintings are in the public domain. Museums such as the
  Art Institute of Chicago publish CC0 images of them, so they can serve as
  default wallpapers, and releases can be named after paintings ("Water
  Lilies", "Impression", "Haystacks").

**Decision: keep "Monet."**

---

## 3. How it works

### 3.1 Disk layout

```
┌──────┬──────────────────────────┬─────┬────────────────────────┐
│ EFI  │ Monet (Linux, btrfs)     │ MSR │ Windows (NTFS)         │
│ 1 GB │ rest of the disk         │16 MB│ user picks, ≥ 64 GB    │
└──────┴──────────────────────────┴─────┴────────────────────────┘
```

- One shared EFI partition holds Monet's bootloader (shim + GRUB, signed for
  Secure Boot) and Windows Boot Manager.
- **Monet is the default boot entry.** Turning the PC on always lands in Monet.
  Windows boots only when asked to.
- Monet **writes to Windows' drive only when Windows has shut down fully**
  (writing to a hibernated Windows disk corrupts it): never hibernated or
  asleep with Fast Startup, never encrypted, its file system clean. Then it
  shares the drive's Games folder, so a game installs once for both.
- Setup asks one question about space: *"How much space for Windows games?"*
  (a slider).

### 3.2 The switch: "Play on Windows"

```
Monet                                   Windows (game mode)
─────                                   ───────────────────
User clicks "Play on Windows: Valorant"
 │
 ├─ write launch request to an EFI variable
 │    MonetLaunch = { store: "riot", game: "valorant" }
 ├─ set one-time boot: BootNext = Windows
 └─ reboot ─────────────────────────────▶ Windows starts (~10–15 s)
                                          │
                                          ├─ Monet Bridge reads + clears MonetLaunch
                                          ├─ launches the game
                                          ├─ waits for the game to exit
                                          ├─ "Back to Monet in 10 s"  [Stay] [Go now]
                                          ├─ set one-time boot: Monet
                                          └─ restart ─────────────────┐
 Monet cold-boots (~10 s) ◀────────────────────────────────────────────┘
```

**Why an EFI variable for the handoff?** It's a few bytes in firmware memory
that both systems can read and write: Linux through `efivarfs`, Windows through
`GetFirmwareEnvironmentVariable`. No shared disk means no risk of corruption.
It's written only once per switch, so wear on the firmware chip is negligible.

**Why doesn't anything hibernate?** Secure Boot must stay on for Windows
anti-cheat, and on Linux it turns on kernel "lockdown", which blocks
hibernation. Windows could hibernate, but a hibernated PC stays off until
someone presses the power button, writing its memory to disk slows the way
back, and Monet can't write to its drive while it's asleep. So both start
fresh: Monet with a fast cold boot and "Ready when you come back".

**Target times**

| Switch | Target |
|---|---|
| Click "Play on Windows" → game launching | < 30 s |
| Quit game → Monet desktop | < 20 s |

### 3.3 Windows Game Profile (the stripped-down Windows)

Applied during an unattended install of the **official** Windows ISO. Every
item is a reviewed entry in a list, not an ad-hoc script.

| Remove / disable | Keep (never remove) |
|---|---|
| Preinstalled apps, ads, "suggestions" | Windows Update |
| OneDrive, Copilot, Widgets, Teams | Defender / Windows Security |
| Search indexing, most startup items | TPM, Secure Boot, VBS components (Memory Integrity off by default, see 4.1) |
| Fast Startup (it leaves Windows' drive half asleep) | WebView2 (launchers need it) |
| Lock screen, login screen (auto-login to a local account) | DirectX and VC++ runtimes |
| Telemetry, as far as official settings allow | Gaming Services / Xbox app (for Game Pass) |

Goals: **< 25 GB disk use**, fast resume, nothing on screen except the game.
Performance settings for Windows are listed in section 4.1.

Every profile change must pass the anti-cheat test list (section 6) before it ships.

### 3.4 Setup flow

The approach: **install Monet first, then let Monet install Windows.** This
avoids writing a whole installer from scratch, makes Windows optional, and
keeps Windows from taking over the bootloader.

1. **Monet installer** (USB): language, disk, account, Windows-games space. Done.
2. **First boot**: a short welcome, then *"Set up Windows for anti-cheat
   games?"* [Set up] [Skip, I can do this later]
3. If the user chooses Set up, Monet:
   1. downloads the official Windows 11 ISO from Microsoft,
   2. creates the Windows partitions in the space set aside for them,
   3. copies Windows Setup to a temporary partition along with an
      `autounattend.xml` answer file (local account, Game Profile, Monet Bridge),
   4. reboots into Windows Setup, which runs with **no screens to click through**,
   5. on Windows' first login, Monet Bridge puts Monet back as the default
      boot entry and restarts into Monet,
   6. Monet deletes the temporary partition.
4. The user sees one progress screen: *"Setting up Windows for games… (about
   20 minutes)"*.

**License:** Windows runs unactivated, with a watermark and limited
personalization, which matters little for a games-only system. Setup offers to
enter a key and explains this plainly.

### 3.5 Monet Games (the game hub)

- One library for **Steam**, **Epic / GOG** (through Heroic or Legendary), and
  other launchers.
- Each game gets a badge: **Plays on Monet** · **Plays on Windows** · **Not supported**.
- Compatibility data comes from public sources: AreWeAntiCheatYet (anti-cheat
  status) and ProtonDB (how well each game runs).
- **Installing a Windows-only game:** Steam (or Heroic, for Epic and GOG) in
  Monet downloads it into Windows' Games folder (`C:\Games`, shared by both
  sides), so it's ready when Windows starts; other launchers still install in
  Windows.

---

## 4. Technology choices

Rule: **when performance and convenience conflict, performance wins.** The
simple design is built on top through theming and locked-down settings.

| Area | Choice | Why |
|---|---|---|
| Base OS | **Fedora Atomic** via **Universal Blue** (bootc images) | Same base as Bazzite. Image-based updates with rollback. Builds on GitHub Actions. Speed comes from the kernel and gaming stack, not the base (see 4.1). |
| Desktop | **KDE Plasma 6** | Best gaming desktop on Linux: low-latency tearing in fullscreen, mature VRR and HDR, solid NVIDIA support. Its *Kiosk* system can hide advanced settings, which gives us the simple design. |
| Game Mode session | **Gamescope** (SteamOS-style fullscreen session) | Lowest overhead for controller and TV play, built-in frame limiting and FSR upscaling. Switch between Desktop and Game Mode with one click. |
| Monet apps (Linux) | **Rust core + Qt 6 / QML (Kirigami) UI** via CXX-Qt | Fast, native on KDE, easy to style |
| Monet Bridge (Windows) | **Rust** program run by scheduled tasks at sign-in | Tiny and fast, and it shares the handoff code with the Linux side. Not a Windows service: services can't start games on the user's desktop. |
| Gaming stack | Proton + Proton-GE/CachyOS builds, DXVK, VKD3D-Proton, latest Mesa, NVIDIA open kernel modules | Proven, maintained by others, always the latest versions |
| Windows install | Official ISO + `autounattend.xml` | No redistribution, fully supported by Microsoft |
| License | **GPL-3.0-or-later** | Anyone can use Monet, including other distros, but modified versions must stay open |

### 4.1 Performance tuning

**Linux side**

| Tuning | What it does |
|---|---|
| **Performance kernel** (CachyOS-patched, signed for Secure Boot) | Lower latency and better CPU scheduling under gaming load |
| **sched_ext scheduler** (`scx_lavd`, developed with Valve's funding for gaming) | Prioritizes the game's threads, so fewer stutters when other apps run |
| **NTSYNC** (kernel 6.14+) | Native Windows-style thread syncing for Wine/Proton. Faster and more accurate than esync/fsync. |
| **GameMode** + automatic performance power profile while gaming | Full CPU/GPU clocks during games, power saving otherwise |
| **Shader pre-caching** (Steam) + Mesa shader cache kept across updates | Less stutter the first time you play |
| **zram** swap, tuned `vm` settings | Smooth even when RAM is full, without slow disk swapping |
| Lean startup: only needed services, fast firmware boot | Faster cold boot, which matters because Monet cold-boots on every switch back |

**Considered and rejected:** basing Monet on CachyOS (Arch packages compiled for
newer CPUs). Its extra gains mostly show up in CPU-heavy tasks, not GPU-bound
games, and it gives up Fedora Atomic's rollback updates. We take CachyOS's
kernel instead, which is where most of the gaming benefit comes from.

**Windows side** (part of the Game Profile)

| Tuning | What it does |
|---|---|
| High-performance power plan | No CPU downclocking while gaming |
| Hardware-accelerated GPU scheduling + Windows Game Mode on | Lower latency |
| **Memory Integrity (HVCI) off by default** | Recovers a few percent of FPS (Microsoft itself says gamers can turn it off). Turned on automatically for any game that requires it. |
| No background apps, indexing, or startup items | All CPU and RAM go to the game |

### 4.2 First supported hardware

| Part | Supported in the first beta | Why |
|---|---|---|
| GPU | **AMD Radeon RX 6000 and newer** (best experience), **NVIDIA RTX 20-series and newer** | AMD's open Mesa drivers are the fastest on Linux. NVIDIA RTX 20+ supports the open kernel modules. Intel Arc comes later. |
| CPU / board | Any x86-64 PC that meets Windows 11 requirements (TPM 2.0, Secure Boot) | Needed for Windows anti-cheat anyway |
| Storage | NVMe SSD | Fast boot and switching. HDDs not supported for the system. |

**Development machines**

| Machine | GPU | What it means for Monet |
|---|---|---|
| Laptop | NVIDIA RTX 2080 (Turing) | Oldest supported generation. Hybrid graphics: games must run on the NVIDIA GPU, not the built-in one. Battery and lid behavior matter. |
| Desktop | NVIDIA RTX 5080 (Blackwell) | Only works with NVIDIA's open kernel modules (driver 570+). Bazzite's `nvidia-open` image covers both machines. |

---

## 5. Roadmap

Each phase ends with something that works on its own. The riskiest ideas are
tested first.

### Status: v0.1 (preview)

v0.1 delivers Phase 1 as an add-on for **Bazzite** (`bazzite-nvidia-open`), so
it works on both development machines with Secure Boot right away:

- `monet` (Rust, Linux): Play on Windows, open Windows, `doctor`, games list,
  app-menu shortcuts. Elevates through a polkit rule, so no password prompts.
- `monet-bridge` (Rust, Windows): starts the game as the normal user, waits
  for it to close, offers to return, restarts into Monet, and repairs the boot order.
- The handoff is a UEFI variable (`MonetLaunch`). The games list travels on the
  EFI partition, which Windows mounts only while writing it.
- A Plasma panel widget (QML) and the Monet look (wallpaper, accent color).
- `image/Containerfile`: the first Monet OS image, Bazzite with Monet built in.

Built and unit-tested, **not yet tested on real hardware**. That is Phase 0
below, with the checklist in [docs/TESTING.md](docs/TESTING.md).

The CachyOS kernel (section 4.1) is not in v0.1. Bazzite's kernel already
carries most gaming patches and is signed for Secure Boot. Switching kernels
waits for the Phase 2 benchmarks.

### Status: v0.5 (preview)

v0.5 gives Monet its own look, "Impression" (see [docs/DESIGN.md](docs/DESIGN.md)):

- **The Hours**: a generated impressionist harbor in four lights, as a Plasma
  wallpaper plugin that drifts between them through the day
- three glass islands instead of a panel; a placard with the time
- glass everywhere: a generated Plasma style, Kvantum themes for app windows,
  see-through title bars, glass Konsole; mist by day, smoke after dark
- the Monet icon theme, Fraunces and Inter, a sunrise splash, the night
  painting at sign-in and on the lock screen
- Windows Games as a gallery with covers and a sunset when you play; Quick
  Settings with Wi-Fi, Bluetooth, Night Light, sound, brightness and the light
- `monet update`, and Wi-Fi from the installer carried into Windows
- Slay the Spire is always listed, for testing: Windows installs it from Steam
  the first time and then starts it

v0.5.1 adds Monet Settings (one glass sheet in front of KDE's System
Settings), painted folders and app icons, Files on paper with glass edges,
and switches for the Hours, the placard and glass.

v0.6.1 shows the download (a Monet page over the installer, restarted when
it stalls), puts Anaconda's own font and sizes back so everything fits, and
fixes the start menu's theme on PCs without Secure Boot.

v0.6 gives the installer Monet's look from the USB stick's start menu on
(a GRUB theme, Anaconda's stylesheet loaded from conf.d), makes it sturdier (Wi-Fi wait, retried checks, Monet
downloaded ahead with retries, a fixed USB-stick guard), and moves the
Windows download to after the first sign-in.

v0.5.2 makes the switch reliable on PCs with leftover boot entries (choose a
Windows entry that can start, add one if missing, verify, log, and check the
result at the next start), makes updates manual, adds the Monet Smoke global
theme for KDE's Dark mode, and evens out the icons.

### Status: v0.3 (preview)

v0.3 makes the installer do everything. The USB stick's default choice,
**Install Monet and Windows**, erases the PC and:

- plans the disk itself (the internal disk, about one third for Windows)
- installs Monet, then downloads Windows 11 from Microsoft (same API as a
  browser) in Monet's language, and stages it on a temporary setup partition
- boots that partition once, where Monet's own script replaces the Setup
  wizard: DISM applies Windows, `bcdboot` adds it to the shared EFI partition
- answers every first-start question with an answer file: local account
  with the user's name and no password, no Microsoft account, no BitLocker
  (`PreventDeviceEncryption`), UTC hardware clock, Monet Bridge and the Game
  Profile installed on first sign-in
- removes the setup partition and gives its space to Windows, makes Monet the
  default again, and returns to Monet

**Install Monet next to my Windows** keeps the v0.2 behavior.

Known limits: PCs with Intel VMD/RST storage may need a driver Windows
Setup's environment lacks; Microsoft can block automatic downloads (Monet
then asks for a downloaded ISO); the MOK confirmation screen can't be skipped.

### Status: v0.2 (preview)

v0.2 brings Phase 3's core early: **one download, one USB stick.**

- `Monet-Installer.iso` (about 1 GB) is Fedora's network installer with a
  Monet kickstart. It installs the Monet OS image from GitHub Packages, so it
  stays under GitHub's 2 GB release limit. A full offline ISO would be about 7 GB.
- Monet prepares Windows by itself: at startup it copies Monet Bridge into
  `C:\ProgramData\Monet\Setup` and adds a one-time Startup script. The
  first time Windows starts, one UAC "Yes" installs Bridge, and the PC goes
  back to Monet. It never writes to a hibernated or BitLocker-encrypted Windows.
- The Monet OS image is rebuilt weekly to pick up Bazzite updates.

Still to do for a fully Windows-like setup: Monet branding in the installer
(it still says Fedora), a Windows app that makes the USB stick (or installs
without one), and BitLocker support for the automatic Windows setup.

### Phase 0: Prove it (research and prototypes)
Goal: show that the core ideas work on real hardware before building anything polished.

- [ ] Test PC: Fedora Atomic + Windows 11 dual boot, **Secure Boot on**
- [ ] Manual switch with `efibootmgr --bootnext` (Linux) and
      `bcdedit /set {fwbootmgr} bootsequence` (Windows); measure the time
- [ ] Hibernate Windows → boot Linux → resume Windows: does **Valorant,
      Call of Duty, Fortnite, or a FACEIT game** still work after resuming?
- [ ] Hand off data with an EFI variable, written from Linux and read from Windows
- [ ] Unattended Windows install from an `autounattend.xml` with a local account
      (check this against the current Windows 11 build)
- [ ] First draft of the Game Profile, followed by the anti-cheat test list
- [ ] Check BitLocker / device encryption behavior with BootNext switching

**Exit:** the switch works by hand, the anti-cheat games run, and the times are measured.

### Phase 1: Monet Switch MVP
Goal: one-click switching on any existing Fedora/Bazzite + Windows dual boot.

- [x] `monet` CLI + games sync service (Linux), v0.1
- [x] Monet Bridge: read the request, launch, wait, return, hibernate, v0.1
- [x] Launch support for Steam, Epic, and Riot, v0.1; GOG, Battle.net, Ubisoft Connect, Rockstar and EA after 0.9.3
- [x] Panel widget (Linux) and "Back to Monet" shortcut (Windows), v0.1
- [x] Safety: a normal power-on always starts Monet; a failed switch leaves the boot order untouched
- [ ] All of the above confirmed on the laptop (RTX 2080) and desktop (RTX 5080)

**Exit:** a non-technical tester can play Valorant from Linux with one click.

### Phase 2: Monet OS image
- [ ] Universal Blue custom image (Fedora Atomic + KDE Plasma) with the CachyOS-patched kernel, built by GitHub Actions
- [ ] AMD/Intel image + NVIDIA image variant
- [ ] Monet Switch included
- [ ] Performance tuning from section 4.1, each one benchmarked against stock Bazzite
- [ ] Gamescope "Game Mode" session at login
- [ ] Design layer: Plasma theme, icons, fonts, Monet wallpapers, simplified settings
- [ ] Secure Boot works out of the box (signed kernel, enrolled MOK key)

**Exit:** a bootable Monet image that people can rebase to or install.

### Phase 3: Monet Setup
- [x] One-download installer ISO (network install of the Monet OS image), v0.2
- [x] Windows half set up from Monet automatically (one UAC click), v0.2
- [x] "Install Monet and Windows": fresh, unattended, games-only Windows, v0.3
- [ ] "Monet Setup" for Windows: makes the USB stick, or installs without one
- [x] Branded installer (Monet name, artwork, start menu, fewer screens), v0.4
- [ ] Monet Setup: our own installer app (Wi-Fi, your name, Install)
- [ ] First-boot wizard
- [ ] Windows ISO download, partitioning, temporary setup partition, unattended install
- [ ] Final Game Profile applied and verified automatically
- [ ] Recovery: "Repair Windows game mode" and "Remove Windows" options

**Exit:** USB to working Monet and Windows game mode with only a few questions answered.

### Phase 4: Monet Games
- [x] Unified library (Steam, Heroic for Epic/GOG/Amazon, Windows' games), after 0.9.3
- [x] Compatibility from AreWeAntiCheatYet and ProtonDB (a game players report borked plays on Windows, with Play in Monet to try anyway), after 0.9.3
- [x] "Play" vs "Play on Windows" chosen automatically, after 0.9.3
- [x] Installing Windows-only games from Monet: Steam's, into the Games folder both sides share
- [x] The same for Epic (handed to Epic's launcher as legendary's EGL sync does) and GOG (DRM-free, started directly)
- [x] The same for Ubisoft, Battle.net and EA (their launchers in Monet through Lutris install on drive W:, the Games folder), after 0.9.3
- [x] A folder for files on both sides (Shared with Monet), and launchers fetched in Monet before a trip needs them, after 0.9.3
- [x] Windows programs opened in Files run in Monet (Proton) or open in Windows (through the shared folder), after 0.9.3
- [x] Launchers out of sight: Monet's painting in front while a launcher starts its game in Windows, the launcher closed after when you stay; Steam and Heroic start quietly in Monet, after 0.9.3
- [x] Games as an app: a library window like Steam's (sections, stores, favorites, sorting by recent, name, play time or size, a page per game, play time from both sides), after 0.9.3

### Phase 5: Beta
- [ ] Hardware test matrix (AMD, Intel, and NVIDIA GPUs; several motherboard vendors)
- [ ] Public beta, feedback, bug fixing
- [ ] Documentation and website

---

## 6. Anti-cheat test list

Every release of Monet Switch and the Game Profile must pass on Windows game mode:

| Game | Anti-cheat | Why it's on the list |
|---|---|---|
| Valorant / League of Legends | Riot Vanguard | Strictest: needs TPM 2.0, Secure Boot, and a driver loaded at boot |
| Call of Duty | Ricochet | Kernel-level, blocks VMs |
| Fortnite | EasyAntiCheat (Windows-only setup) | Very popular |
| Counter-Strike 2 via FACEIT | FACEIT AC | Kernel-level, strict |
| Apex Legends | EasyAntiCheat | Linux support was removed in 2024 |

---

## 7. Risks

| Risk | Impact | Plan |
|---|---|---|
| Windows Update overwrites the boot order or bootloader | User lands in Windows | Monet Bridge checks and repairs the boot order on every Windows boot |
| BitLocker asks for a recovery key | Scary for users | Test in Phase 0. Save the recovery key in Monet, or turn off device encryption in the profile |
| Microsoft changes how unattended installs or local accounts work | Setup breaks | Pin a tested Windows build. Re-test the setup on every new Windows release |
| Stripping Windows breaks a game | Game won't run | Conservative profile + anti-cheat test list + per-game "restore component" fixes |
| Wide hardware variety | Bugs on unusual PCs | Start with a small supported-hardware list and grow it |
| Too much work for a small team | Project stalls | Reuse Universal Blue/Bazzite work. Ship Monet Switch alone first (Phase 1) |
| Anti-cheat vendors flag Monet Bridge | Bans or blocks | Bridge only launches games and never touches game processes. Talk to vendors before the beta |

---

## 8. Decisions

| Decision | Choice | Why |
|---|---|---|
| Desktop | **KDE Plasma 6 (Wayland)** | Best gaming performance and features (see section 4) |
| Base | **Bazzite** for v0.1; **Fedora Atomic** (Universal Blue) + **CachyOS-patched kernel** to be benchmarked in Phase 2 | Bazzite works today on NVIDIA with Secure Boot. The CachyOS kernel only goes in if it measurably helps (see 4.1) |
| Language | **Rust** everywhere | Native speed like C/C++, memory-safe, one codebase for Linux and Windows |
| UI | **Qt 6 / QML (Kirigami)**. v0.1 is a QML panel widget that calls the Rust CLI; a full app via CXX-Qt comes with Monet Games | Fast, GPU-rendered, native on KDE |
| License | **GPL-3.0-or-later** | Keeps Monet and its forks open source. Same family as Linux and KDE |
| First beta hardware | See section 4.2 | Best-supported GPUs on Linux. TPM 2.0 is required by Windows 11 and Vanguard |
| Leaving Windows | **Restart, not hibernate** (since 0.9.1) | A hibernated PC stays off until the power button is pressed. Restarting comes back to Monet by itself and sooner, every game starts from a cold boot as its anti-cheat expects, and Windows' drive stays safe to write from Monet |

| Branding | Sun-over-water logo, Monet Blue accent, impressionist wallpaper. See [docs/DESIGN.md](docs/DESIGN.md) | Apple's simplicity, our own look |

### Still open

- [x] **Typeface:** Inter for the desktop and apps (`monet-look`), Fraunces for titles
