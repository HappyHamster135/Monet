# Monet 0.9.7 — speed, everyday use and small fixes

Approved scope: eight improvements, requested on 5 November 2026. Work stays
local and uncommitted. VERSION and workspace packages identify the 0.9.7
candidate. The laptop runs an earlier 0.9.7 image with a reversible account
preview.
Status below distinguishes implementation from installation and release testing.

The current foundation includes regional clock/weather defaults, Desktop as the
default download destination with a folder-menu override, archive extraction,
Space previews, Keep both, optional Desktop Stacks, Transfers, Files scheduling
changes, desktop menu repair, and screen-lock controls in Power & Sleep. These
have a reversible account installation for laptop testing. Both candidate image
variants pass customized-profile upgrade/rollback in isolated virtual machines;
physical release acceptance remains open.

Physical drive, external-monitor and graphics acceptance remains open. The
candidate before the restart fix included the Security page loading fix from
the account preview. It passed the full desktop suite, encrypted offline Setup
and TPM rollback after an interrupted boot, the Fedora fallback, and signed
update and rollback on both image variants with customized profiles. The
firewall changes and authorization checks for ordinary and Guest sessions also
passed.
The Windows USB maker refused a truncated Setup ISO
before writing, then wrote and verified the complete ISO twice. The written
virtual stick booted Setup with Secure Boot and the expected digest map.
Security and widget Glass also passed additional client rendering checks on
the laptop's GPUs through virtual outputs. A restart from Security reached
virtual UEFI after a document was saved. Canceling kept the draft open.
The NVIDIA VM then exposed a restart dialog failure after Security's firmware
check started Plasma's shutdown service. The passive probe is in the account
preview. With the fix in the VM, canceling Restart kept the signed update
staged, confirming Restart booted it, and an administrator-approved rollback
returned to the original image. Both rebuilt images include the fix. Their
packaged Restart dialog, signed upgrade and profile-preserving rollback passed.
The rebuilt VM installer media pin the exact new image digests. Setup booted
with Secure Boot, and the Fedora fallback installed the pinned AMD/Intel image
after the test registry moved the version tag. The Windows USB maker wrote and
verified the rebuilt Setup ISO twice. The rewritten stick passed independent
read-back and a Secure Boot start in a VM. The exact rebuilt AMD/Intel image
also passed the firmware restart from Security with an unsaved document. The
rebuilt NVIDIA image automatically rolled back when the VM's sign-in screen
failed, and the updater skipped the failed digest on the next check. A fresh
encrypted Setup install of the exact NVIDIA image verified the recovery key,
Secure Boot and TPM unlock after rollback to the retained deployment.
The early boot test exposed a separate GRUB recovery bug. The corrected
helper is in both local image exports and the Linux bundle. The rebuilt
NVIDIA image passed recovery after three interrupted starts. Another
restart kept the recovered signed deployment and the updater skipped the
failed digest. The rebuilt AMD/Intel image passed signature checks and a
manual rollback to the original 0.9.6 deployment. Both VMs preserved the
customized profile. Both VM ISOs were rebuilt with the new pins. Setup
reached Hello with Secure Boot and its network adapter removed. A fresh
Fedora fallback install booted the pinned AMD/Intel digest after the
registry moved the version tag. Its update check used the rolling channel.
The rebuilt Setup ISO installed the pinned NVIDIA digest to a new encrypted
disk. The recovery key and TPM unlock after rollback both passed.
The Windows USB maker refused a truncated copy of the rebuilt Setup ISO,
wrote and verified the full ISO twice, and the rewritten stick reached
Setup with Secure Boot enabled in a VM.
The complete desktop suite passed on the frozen source of this build.
The Windows USB maker follow-up moved disk scans off the window thread.
The rebuilt executable passed slow-discovery, unplug, repeat-write and
Secure Boot checks with the same Setup ISO in a VM.
The local candidate manifest verifies all seven package, image and VM
media files. Its signed AMD/Intel image and packaged Windows Bridge passed
an active-desktop game round trip. The general command and an inactive
switch still required authentication. A pre-first-boot Windows fixture ran
the exact Bridge package at its first automatic sign-in, returned to the
signed Monet image and kept both setup auto-logon values at zero on the next
Windows sign-in.
The current Security page passed its remaining keyboard checks in Mist and
Smoke at 150% and 200%. A signed upgrade from 0.9.6 kept an existing global
firewall rule, restored it after a failed reload and recorded its eventual
administrator removal in Protection history.
The pinned encrypted Setup VM showed Security's pending key state and
confirmed completion across two restarts. That test found an update-status
read blocked by private OSTree directories. The read-only D-Bus fallback
passed on the guest and is in the account preview and both rebuilt images.
The exact signed update and rollback checks passed on both images. Setup
booted with both new pins, and Fedora fallback installed the pinned
AMD/Intel image after the test registry moved its version tag. The final
desktop suite and all seven local artifact checks passed. The Windows USB
maker wrote the rebuilt Setup ISO and verified it in a VM. Independent
read-back matched the ISO payload, and the written stick reached Setup with
Secure Boot and both expected pins. Physical USB, display and GPU checks,
and Steam Remote Play remain open.
The encrypted ZIP failure now has a reproducible fixture. Ark verifies the
read through the end of each ZIP entry and reports the checksum failure.
The rebuilt plugin passed native tests, loaded in the laptop's account
preview, and is in both refreshed local image exports. Both rejected
unsigned and wrong-key offers, booted the locally signed 0.9.7 update, and
rolled back to 0.9.6 with the saved file intact. Setup read both refreshed
pins under Secure Boot. The Windows maker wrote the exact Setup ISO, and
the resulting virtual stick passed read-back and Secure Boot. Fedora
fallback installed the pinned AMD/Intel image after the test tag moved.
The rebuilt Windows writer now sets the protective MBR size from the
validated USB capacity. Setup and Fedora fallback both passed native Windows
write, independent GPT read-back and Secure Boot checks. The full desktop
recheck found a duplicate wallpaper weather request on unlock. A single
refresh now runs through the weather timer. The fix passed 40 focused checks,
is installed in the account preview, and is in both new image exports.
The full desktop rerun passed. The refreshed Setup ISO booted with Secure
Boot and a virtual TPM and read both new pins.
Both refreshed images passed signed upgrade and rollback. The rebuilt Windows
maker wrote both repinned ISOs and passed independent read-back. Fedora
fallback installed the pinned AMD/Intel image from that virtual stick, then
booted with the stick removed.
The current digests and reports
are in [Testing](TESTING.md).
The direct Ethernet Setup kit serves both pinned images from the laptop's
existing archives. The test stick booted with Secure Boot and reached the
isolated registry with a certificate scoped to that registry. The VM finished
an encrypted AMD/Intel install and verified its recovery key. The installed
VM reached the desktop with the stick detached. A second boot used the TPM
and retired Setup's temporary disk key. The physical test still needs a
spare USB stick, a dedicated Ethernet link and a spare installation drive.
The archive actions and power-page restyle are installed in the
account preview and are packaged in both rebuilt images. The frozen v7 OS images
predate these corrections.
Double-click keeps the extraction box; right-click Open is the separate contents
browser. The temporary default-browsing change in batch 31 is reverted in batch 32.
The final v7 images include the native thumbnail loading/Stop control as well as
the cursor, clock and weather-transition fixes. Both pass the complete suite,
actual-image password unlocking and customized-profile VM upgrade/rollback.
The user cannot test an external monitor yet. Eight additional native Store
painting checks pass on the laptop's physical NVIDIA GPU through a private
Intel compositor and virtual output; physical display/hotplug acceptance stays
open.
The Files label fix is built into both images. Desktop/widget right-click menus
and plugged-in stay-awake with idle timers set to Never are user-reported passes,
as are sleep/wake, lid behavior and touchpad scrolling.
Both frozen builds, the complete serial desktop suite and Rust checks pass;
the detailed evidence and limits are below.

| ID | Priority | Work | Status |
| --- | --- | --- | --- |
| 097-01 | High | Measure and improve sign-in and app opening | Store cache and bounded foreground power reads installed; final-image session measurements recorded with all samples retained; no general startup gain demonstrated |
| 097-02 | High | Reduce idle background work | Hidden cursors and prolonged weather-wallpaper transition fixed and installed; native regressions and final-image checks pass; physical power measurements remain separate |
| 097-03 | High | Responsive Files around slow or unavailable drives | Native thumbnail loading/Stop/Escape/Refresh fix installed; matching laptop-runtime cases pass at 100/125/150/200%, both actual image pairs pass at 100/200%; physical drives pending |
| 097-04 | High | Settings search reaches the exact control | Four destinations translated across all 29 catalogs; native multilingual/scaling checks and installed-image lock-control navigation pass; physical review pending |
| 097-05 | High | Explain power state and add temporary Keep awake | Controls/countdown and inhibition recovery implemented; user confirms AC stay-awake, sleep/wake and lid behavior; remaining policy/hardware qualification separate |
| 097-06 | Medium | Immediate launch feedback, duplicate prevention and retry | Matching account preview installed; native/menu/dock/Wayland and final-image checks pass; physical-device qualification separate |
| 097-07 | High | Finish file-operation failure and completion flows | Native failure, cancellable submission and completion flows pass; physical disconnect checks pending |
| 097-08 | High | Keyboard, touchpad and fractional-scaling polish | Native checks, seven clock/password/consent cases and final-image checks pass; user confirms touchpad scrolling; external-monitor checks pending |

## 097-01 — faster sign-in and app opening

Record system and user startup traces plus Files, Settings and Store first-window
and ready-state timings. Compare repeated runs on the same machine, recording
cold/warm state and whether rendering is native or software. Keep firmware,
boot, sign-in, first frame and loaded contents separate. Service blame durations
overlap: they cannot be added or treated as time saved.

Move nonessential work behind desktop readiness, avoid duplicate refresh jobs,
and retain retry after failure. Acceptance: no lost startup choices, Windows
return work or profile migrations; report measured results and limits.

## 097-02 — less background activity

Pause unnecessary widget sampling while locked, while the relevant display is
off, or while a popup is closed. Refresh immediately when it becomes visible.
Share hardware reads where practical; prevent overlapping requests. Do not add
a per-widget daemon or replace missing readings with false zeroes. Acceptance:
native lock/unlock, monitor-off/on, popup and idle CPU/wakeup comparisons.

## 097-03 — Files stays responsive

Audit native KIO loading/cancellation before adding UI. Keep navigation and
Cancel usable with a disconnected share, sleeping USB drive and heavy thumbnail
work; discard stale replies after navigation. Keep existing tabs, selection,
scroll position and file-operation semantics. Acceptance: controlled slow/error
fixtures plus real removable/network-drive checks; no forced unmount or data loss.

## 097-04 — search opens the exact setting

Route “stop screen locking”, “download folder” and “battery limit” to the actual
control, scroll it into view and highlight/focus it. Use one allowlisted catalog
for Settings and the app menu. Search only navigates: it never changes settings.
Acceptance: keyboard activation, translated aliases, slow data, narrow windows
and 125%, 150%, 200% scale; preserve existing search destinations.

## 097-05 — clearer power information and Keep awake

Explain mains connection, charging, a full battery and charging paused by a
configured limit separately. An above-limit battery must not look like a fault.
Add Keep awake for 30 minutes, one hour or until turned off, with a countdown
and explicit cancellation. Use the desktop's inhibition APIs; preserve saved
screen, lock, lid and sleep preferences. Acceptance: expiry, cancellation,
crashed/restarted helpers, lock/sleep policy and AC/battery transitions.

## 097-06 — immediate launch feedback

Use native startup notification and Wayland activation. A pending launch has
visible feedback and repeated clicks do not accidentally start duplicate copies.
Failures have an actionable retry; a running app comes forward. Acceptance:
slow launch, missing executable, failed launch and two distinct apps in flight.
Keep deliberate new-window actions available.

## 097-07 — file-operation details

Cover encrypted archives/password prompts, full disks, cancelled extraction,
duplicate names and unplugged destinations. Preserve partial work and explain
retry without overwriting existing files. Completion consistently offers Open
folder where the destination is available. Acceptance: real native operations
and controlled failures, including closing and reopening the Transfers view.

## 097-08 — keyboard and scaling

Check Tab/Shift+Tab, Enter, Escape, visible focus and focus restoration across
Settings, Store, menu, extraction and Transfers. Check wheel and touchpad input,
large text, reduced motion and 125%, 150%, 200% scaling. Fix clipping and focus
traps with native render/interaction evidence. Existing shortcuts stay usable.
Settings choice captions now wrap and reflow with available width and font size.
Settings and Store now use the window's own screen's available geometry rather
than the virtual desktop's combined size. Private two-screen X11 and mixed-scale
KWin Wayland fixtures cover moves, restored sizes and window states.
Store now shares Settings' precise scroll input, adapts its podium/sort controls
to narrower outputs, and preserves native grid selection and Enter/Back focus.
Shared glyphs also suppress fully clipped software-rendered paths while keeping
their layout space. Store artwork also has a working software-rendering fallback,
with controlled pixel checks on software and OpenGL clients. Menu keyboard,
scrolling and short-window representation checks also pass. Real Plasma popup
bounds now pass on private mixed-scale Wayland outputs, including live scaling
and moving the panel. Archive preparation keeps its drop target and action
buttons visible while details scroll on a small screen. Transfers now preserves
job-control focus across progress updates, wraps its actions and messages, and
handles precise scrolling and both Enter keys. Physical monitor and input-device
checks remain part of release acceptance.

## Release acceptance

- Repeat laptop sleep/wake, AC changes, lid use and monitor reconnects; record
  graphics hardware and scale. The 0.9.6 physical qualification gap remains open.
- Upgrade an existing customized profile, then roll back, preserving files,
  startup choices, panel layout, shortcuts, region and download destination.
- Run affected native/unit suites and complete desktop/image checks. Update
  translations and release notes from the final frozen sources.
- Record before/after performance with reproducible commands. Do not claim
  whole-OS or battery-life improvements from isolated helper timings.

## Work record

Initial read-only laptop trace: `plasma-workspace.target` at 5.875 seconds in
the user session. Its reported critical chain includes kded (3.043 seconds)
and PowerDevil (662 ms). Monet names, Files-place, frames and Zen jobs also
appear in the service timing list, but are not all on that critical chain.
No sign-in speed improvement is claimed from this baseline.

First implementation batch:

- Reproduced two `power` and two `battery-care` queries from one Settings open.
  Page-change and open requests now share one scheduled load, producing one of
  each query. This reduces duplicate work; it is not a measured launch multiplier.
- Store now paints its first frame before starting the catalog worker. A queued
  native Qt timer and one-shot guard preserve the GUI thread and prevent duplicate
  catalog starts. Download workers remain independent of the Store window.
- Added allowlisted search destinations for the lock timer, Downloads and battery
  limit. Native focus/scrolling plus a temporary highlight reveal each control.
  Unsupported charge-limit hardware has an explanation; an unanswered query
  shows Checking instead of an unsupported result.
- Power status can use the kernel's actual mains/USB charger connection rather
  than infer it from the battery's charging state. The page distinguishes paused
  charging at a configured limit, a full battery and ordinary noncharging state.
- Hidden System sensors stop sampling; hidden Batteries widgets stop their timer
  and overlapping battery requests are prevented. Lock/DPMS-wide coordination
  and shared helper snapshots remain separate work.
- Added `tools/bench-desktop.py` and opt-in `MONET_STARTUP_TIMING=1` events for
  QML loading, window creation and first frame in the native Qt apps. The tool
  isolates HOME, configuration, runtime, D-Bus and local-server socket paths;
  it can measure clean caches or reuse a temporary app cache. It does not close
  or alter the actual desktop's apps. Files UI and data-ready measurements remain
  pending; first-frame results are not presented as app readiness.

The initial three-sample clean-profile software-rendering run measured roughly
1.06 seconds for Settings and 0.36 seconds for Store to their first frames.
A small follow-up varied to 1.10 and 0.30 seconds respectively. These short runs
do not establish a launch-speed gain, especially with Store's unrelated variation.
No boot, firmware, whole-OS speed or battery-life improvement is claimed.

Five later clean-profile samples measured Store's observed first-frame median at
468.5 ms before catalog deferral and 260.1 ms afterward. All five deferred runs
recorded the first-frame event before the catalog worker started. This measures
the first-frame signal under offscreen/software rendering, not full contents,
GPU presentation latency or a general application speedup. Separate cache-reuse
runs and raw timings are retained in `target/polish097-2026-11-05/`.

Validation: 502 passing tests across the affected suites and the real startup
process check; four unrelated checks skip without JavaScript/Xvfb runtimes.
Six additional native checks pass at 125%, 150% and 200%, exercising all three
search destinations, keyboard focus, scrolling and delayed charge-limit data.
The wider scaling audit should also inspect sidebar glyph clipping seen in the
software-rendered narrow-window captures; hardware behavior is not established.

These new changes are source-only. The earlier reversible laptop installation
continues to run the preceding test batch. Full-image packaging, translations,
hardware checks and the remaining backlog items are still pending.


Second implementation batch:

- Keep awake now offers Off, 30 minutes, one hour and until turned off/sign-out.
  A connection-owned session helper holds native PowerDevil and ScreenSaver
  inhibition cookies, without rewriting saved policy. It starts on demand,
  survives closing Settings and exits on expiry/cancellation. Its countdown uses
  boot time, including explicit suspend; wall-clock changes do not extend it.
  Backend replacement reacquires cookies without resetting the deadline, and a
  crashed owner cannot leave an active inhibition or a false active status.
  Indefinite holds do not run a one-second helper timer. Native private-bus tests
  cover expiry, replacement, partial failure, cancellation and abrupt termination;
  A short laptop probe also confirms the real native hold and automatic release
  without any saved policy changes. PowerDevil enforces requests after its native
  delay (observed about 4.8 seconds); the initial immediate-enforcement assertion
  was corrected to observe that transition. Broader policy/hardware interaction
  remains a release check.
- Files no longer resolves mount roots through QStorageInfo/Solid on the GUI
  thread. Exact URLs share asynchronous KIO free-space jobs; obsolete jobs and
  queued notifications from the previous location cannot replace current data.
  Recovery metadata accepts a loaded directory with a harmless trailing slash.
  Native Stop becomes disabled after cancellation. A controlled native WebDAV
  fixture verifies navigation while waiting, Stop and late-reply refusal on a
  private X server. The instrumented filesystem test verifies its blocking shim
  before asserting that observer lookup makes no synchronous capacity probe.
- A real full-disk test reproduced Ark returning zero after its native extraction
  error dialog. The image now rebuilds its matching distribution source so batch
  jobs return zero for success, one for errors and 130 for native cancellation.
  Native password dialogs and installed libraries/plugins remain in use. The
  executable has runtime/dependency/hash guards and preserved corresponding
  source. Encrypted ZIP and header-encrypted 7z, wrong passwords, cancellation,
  actual ENOSPC and retry in a new folder pass in the disposable container.
- Both extraction flows reject a replaced/disconnected destination as completion.
  Partial output stays available; no replacement directory is scanned as an
  extracted app. Archive-folder actions say Open folder. The remaining native
  copy/download completion actions and slow submission work stay on this backlog.
- Settings segments accept Return and keypad Enter as well as Space. Keep awake
  search uses the existing allowlisted route catalog. Catalogs are regenerated,
  with Swedish power/control/search messages added and real-catalog alias tests.
  Other new translations and the wider layout audit still need review.

Evidence for this batch is under `target/097-goal/`. The Fedora 45 desktop test
image now includes the guarded native archive fix, Xvfb, xdotool and JavaScript;
all four checks previously skipped for missing JavaScript/Xvfb runtimes pass.
The first full-suite run found one stale-catalog failure, corrected by regeneration.
The later run covers 1,485 Python checks; its countdown test required replacing a
fixed sleep with a bounded wait for progress. Its 30-test module passes afterward,
giving combined coverage of 1,466 passed and 19 declared skips. JavaScript and
11 browser-form checks pass. `docs/TESTING.md` records the boundaries and original
reports. These additions remain source/build-only; the laptop account preview
has not been refreshed with them. The final candidate still needs a complete
fresh verification run and the remaining release acceptance work above.

Third implementation batch:

- Added an in-process QML activity backend that shares lock, per-output DPMS,
  suspend/resume and UPower observations across widget views. Battery snapshots
  use event subscriptions while needed, without periodic helper launches. Missing
  readings remain unavailable rather than becoming zero; stale replies cannot
  replace newer state after resuming or a service restart.
- Native private-bus/Wayland tests pass in both the release build and an
  AddressSanitizer/UndefinedBehaviorSanitizer build. They cover independent
  outputs, lock races, suspend/resume, shared power reads, subscriber removal,
  invalid readings, service replacement and compositor reconnection. An initial
  lock query also prevents new locked views from starting unnecessary reads.
  Updated logs are `target/097-goal/activity-native-tests-v2.log` and
  `activity-asan-v2.log`.
- Integrated activity state into 15 widgets and the Hours wallpaper. Sampling,
  timers and hidden popup reads pause while inactive; resume obtains current
  data. Real note saves and queued weather preference writes continue. Native
  rendering found and fixed a Sound request initialization race and a Weather
  component-scope binding error. The wallpaper retains a static locked image,
  aborts obsolete requests and stops its animations while inactive.
- The native module now has guarded OS/test-image build stages and preserved
  corresponding source/license. The test image builds and installs it; final OS
  images still need building. The focused run passes 69 checks without skips;
  the later 437-check regression run also passes. Those runs overlap and are not
  a replacement for the final whole-suite run. See `activity-final.json` and
  `activity-regression-final.json`.
- Three alternating baseline/candidate comparisons use actual Quick Settings
  polling intervals and controlled helper responses. Each six-second locked or
  display-off sample drops from four sampling helper launches to zero. Process
  voluntary context-switch medians drop from 19 to 4 while locked and 14 to 0
  while display-off. CPU readings remain near the accounting resolution; these
  are isolated process observations, not hardware wakeup or battery-life gains.
  Commands and raw results are retained in `activity-idle.json` and
  `tools/bench-widget-idle.py`.
- This batch is not installed on the laptop. Its guard correctly refuses the
  test-image bundle because the laptop has an earlier libcurl runtime package.
  A matching laptop build and real lock/display/CPU/wakeup checks remain before
  097-02 acceptance. The previous whole-suite results do not cover this batch.

Fourth implementation batch:

- Added a shared native launch coordinator for the menu, dock and Monet's helper
  launches. Starting indicators appear before process work, repeated pending
  clicks use one job, and different apps can start together. Native task models
  raise existing windows; deliberate new-window actions stay available, including
  dock Shift/middle clicks. Files, URLs and desktop actions keep their original
  native actions. Menu/dock launches retain Plasma's app-usage history.
- Missing executables and native launch errors have a retained menu message and
  notification with Retry. Process spawn does not mean a window is ready. An
  early exit or timeout is described as unconfirmed, and Retry checks existing
  windows/startups and live processes before launching again. Dismiss hides the
  message while keeping its duplicate guard. Native pidfd exit observation needs
  no periodic process polling or separate daemon.
- Corrected a compile error in the notification Retry callback, preserved
  explicit new-window intent through Retry, and covered windows arriving while
  activation-token work is pending. The native suite passes in release and
  AddressSanitizer/UndefinedBehaviorSanitizer builds. It also checks shared state
  across recreated views/QML engines, wrappers exiting before child windows,
  late mapping, service validation and confirmation timeout.
- A real private KWin Wayland session with Intel rendering confirms mapped
  windows, distinct native activation tokens, duplicate suppression, concurrent
  apps, restoring/activating a minimized window and deliberate second windows.
  It exposes only the render node to the container, without the host display,
  session bus or physical display-control devices. This does not qualify actual
  laptop panels, monitor hotplug or suspend/resume.
- The desktop test image now builds/installs guarded launcher and candidate dock
  modules. The compiled dock test uses pointer clicks on its actual delegates;
  menu tests use actual Kicker models/native jobs and exercise notification and
  menu Retry. Bundle checks refuse changed private task-model/runtime libraries,
  damaged notification configuration, unresolved dependencies and build RPATH.
  Source/license archives are included. Swedish launch messages are added;
  wider translation and accessibility/scaling review remain.

Evidence for this batch is retained under `target/097-goal/`; detailed commands
and test boundaries are in `docs/TESTING.md`. The final focused regression run
passes 459 Python checks without skips or failed modules, including the native
fixture wrappers. It remains source/build-only: a
matching laptop installation, final whole-suite/image run and the other release
acceptance items above are still required. VERSION remains 0.9.6; no commit or
push was made.

Fifth implementation batch:

- Archive inspection, destination validation/reservation, foreground extraction
  and durable-job submission now run outside the dialog's GUI thread. A loading
  state appears while checking a slow source/folder; Cancel and Escape do not
  wait for filesystem checks or synchronously remove output. Dropped local URLs
  are checked asynchronously, with file/remote/multiple-item rejection retained
  before extraction. Existing folders and partial output are not overwritten.
- Background submissions have preassigned job IDs. Cancelling after reservation
  stops the submitter and cancels its exact queue entry afterward, preventing a
  late detached extraction. The queue rejects reused IDs and its reserved global
  lock ID. Accepted jobs continue independently after the dialog disappears.
- An actual Enter/keypad Enter check found an extraction/Cancel default-button
  race. Qt's default Extract button now handles those keys once. Controlled slow
  metadata and paused-submission fixtures verify a live GUI event loop, prompt
  Escape and no late launch. These inject delays inside the worker; they do not
  establish physical-drive behavior or general performance figures.
- The 59-check affected run passes without skips or failed modules, including
  actual native encrypted/password/cancellation dialogs through the new worker,
  native ZIP/tar/7z handling, full-disk recovery, partial-output preservation,
  duplicate destinations, existing Transfers/widgets and translation checks.
  Evidence is `target/097-goal/archive-async-final-v2.json` and its log; inspected
  dialog captures and controlled latency observations are in `archive-async-ui-v2`.

This batch remains source-only and is not installed in the laptop preview. The
consistent native copy/download completion action, real destination disconnects,
wider keyboard/scaling audit and final release gates remain open.

Sixth implementation batch:

- Transfers now offers Open folder for native copies/downloads and local
  extractions. Its native action checks the destination asynchronously through
  KIO: directories open directly; files are selected in their parent folder.
  Downloaded files, including desktop launchers, are never opened as content by
  that action. Missing/changed destinations have a dismissible explanation;
  slow checks have cancellation and a deadline. Obsolete replies cannot open a
  window after cancellation or view removal. No metadata is queried while idle.
- The actual copy/download/extraction workflow survives closing/reopening the
  panel. Destination comparisons now handle KIO display URLs versus Python's
  encoded spaces/Unicode, preventing duplicate archive rows. Native descriptions
  are converted to plain text rather than displaying HTML link markup. Error
  details are bounded visually while remaining available to accessibility.
- The workflow uncovered a state-watcher defect: Qt's StateLocation includes the
  app name, whereas the workers use the shared state directory. Transfers now
  uses GenericStateLocation and enables watchers after the helper creates the
  directories. An open panel also refreshes when another open request arrives.
  The missing-destination test observes a real queue update without manually
  refreshing, then dismisses its error and verifies extracted files remain.
- The guarded native module includes the folder action and corresponding source.
  Its fixture passes 14 QtTest cases, including setup/cleanup, with memory and
  undefined-behavior sanitizers. Real KIO copy/download jobs, their standard
  progress tracker, native Ark and a rendered Transfers view verify the complete
  action path. A private KWin/Intel run also verifies a distinct activation token,
  correct directory argument and focused window for a controlled folder handler.
- The earlier broad regression run passes 510 Python checks. After the text,
  error and watcher fixes, a focused 14-check run passes without skips/failures,
  covering the affected workflows, widgets, activity gating and catalogs. These
  runs overlap and are not the final complete suite. Current evidence is
  `folder-final-checks.json`, `folder-wayland-text-final/`, `folder-asan-text.log`
  and `transfers-completion-verified/` under `target/097-goal/`.

The newest test image is built locally; these changes are not installed on the
laptop. Physical drive disconnection, wider keyboard/touchpad/scaling work,
matching laptop installation and all final release acceptance checks remain.

Seventh implementation batch:

- Settings' More settings link now participates in Tab/Shift+Tab, has a visible
  focus outline and accepts Space, Return and keypad Enter. Page tabs, tappable
  rows, action pills and appearance/power choices also accept both Enter keys.
  Busy action pills are disabled and omitted from Tab traversal. A search jump
  into a grouping now hands the next Tab to its first usable control. Regression
  testing caught a duplicate special-case handler in the return-summary card;
  that card now uses the same handoff and its existing keyboard checks pass.
- Settings handles native wheel detents and precise touchpad pixel gestures in
  both scroll panels, including zero-delta gesture boundaries. Scrolling stays
  inside the panel under the pointer; page keys, modified wheel steps, background
  window dragging and ordinary control clicks are preserved. The controlled
  negative case without the new input handler reproduces the ignored pixel
  scrolling. This is input-event evidence, not a physical touchpad qualification.
- Fully clipped sidebar marks could paint above the list with Qt's software
  Shape renderer. Software-only visibility checks suppress those offscreen
  marks using each mark's own bounds; normal GPU rendering keeps its existing
  path. A pixel check covers both list edges and a range of scroll positions. It catches
  599 stray white pixels without the fix and passes with it. The clipped edge of
  a partially visible, unfocused row is normal scrolling and remains unchanged.
- The isolated scale fixture uses a private 1920×1080 X server, the packaged
  Inter reading font and Monet's Fraunces headings. It checks 125%, 150% and
  200%, with normal English text and larger Swedish text in separate Qt
  processes. A separate native KDE-style run verifies reduced motion. Evidence
  and current regression results are described in docs/TESTING.md.

This Settings pass remains source-only. Appearance-card caption layout, the
other apps' keyboard/scaling pass, physical input/hardware checks, matching
laptop installation and final release acceptance remain open. No commit or push
was made, and VERSION remains 0.9.6.

Eighth implementation batch:

- Light, wallpaper and power choices keep their full captions. The grids retain
  three columns where text has room and reflow to fewer columns for larger text
  or narrower windows. Labels wrap, cards grow to fit and photo placeholders stay
  inside their frames. Resizing preserves the focused choice and sends no
  preference changes. Existing power-choice focus also survives replies/refreshes;
  its model behavior was verified rather than unnecessarily replaced.
- Store section tabs, sorting/filter controls, featured/ranked apps and screenshot galleries
  accept keypad Enter. Its screenshot viewer uses a native Qt modal popup, with a
  visible Close button, Tab containment, Escape and native focus return. Find
  cannot move focus behind the viewer; closing a screenshot keeps the app page.
  The gallery itself has a visible keyboard focus outline.
- Back restores the original app-card focus, or Search when that card has been
  removed. A queued restoration cannot override a new navigation choice. The
  focused control is scrolled into view again after visible content finishes
  laying out, using change signals and no polling. Store also handles an absent
  featured app without binding errors and avoids a hidden shelf's invalid banner
  read after going home.
- Oversized saved Store dimensions are constrained on the tested single display.
  A source review identified the remaining per-monitor geometry issue described
  under 097-08; the single-screen results do not qualify multiple outputs.
- Real-font Settings checks pass at 125%, 150% and 200% with English and larger
  Swedish text: 78 executions of 13 checks, plus 13 in native reduced motion.
  Store's eight navigation cases pass in all six combinations (48 executions),
  plus eight in reduced motion. The affected regression run passes 588 checks
  without skips or failed modules. These are local, scoped checks; final whole
  suite/image, hardware, installation and upgrade/rollback gates remain open.

Evidence is recorded in docs/TESTING.md and `target/097-goal/`. These additions
remain source-only; the account preview is not refreshed. No commit, push or
version bump was made.

Ninth implementation batch:

- Settings and Store follow the usable geometry of their current screen, using
  a shared signal-driven Qt controller. It follows screen changes, available-area
  changes and output destruction without polling. A temporarily invalid screen
  rectangle keeps the last valid size. Disconnects remove only this controller's
  connections, leaving other screen/window observers intact.
- Oversized saved windows fit the current output, including smaller fractional-
  scale outputs. Returning to a larger output preserves a chosen smaller size
  within that output's minimum size. Moving does not rebuild the app or reset its
  page. Normal windows also recover from a late Wayland configure carrying their
  old, oversized dimensions; maximized and fullscreen states remain intact.
- Two real QScreens on a private X server cover both apps at 125%, 150% and 200%.
  The private KWin Wayland fixture uses mixed 125%/200% outputs and a live 175%
  change. It checks actual compositor window bounds/state, minimized moves and
  restore, maximized/fullscreen moves, and virtual output disable/re-enable.
  Removing the late-size correction reproduces the old oversized-height failure.
- These are isolated native desktop checks, with software-rendered Qt clients
  and an Intel OpenGL KWin compositor for Wayland. They do not qualify physical
  monitor hotplug, physical touchpads, other graphics drivers or the final OS
  image. Current reports, source hashes and test commands are in docs/TESTING.md
  and `target/097-goal/window-area-validation.json`.

The account preview is unchanged by this batch. Matching laptop installation,
the remaining UI/input audit and all final release acceptance gates remain open.
Everything stays local and uncommitted; VERSION remains 0.9.6.

Tenth implementation batch:

- Store's home, shelf, search, app details, Downloads and sidebar accept precise
  touchpad pixel gestures, mouse detents and bounded page steps. Settings uses
  the same shared input component. Zero-delta gesture boundaries preserve the
  scroll position, and each panel handles only its own input. Blank areas still
  request window dragging; cards/buttons still click normally.
- Shelf Home/Page/End includes the header; arrows retain native GridView item
  selection. Each grid card now receives keyboard focus so Enter opens the
  selected app. Tab focus synchronizes the current index, and Back returns to
  the card. A manual scroll cancels that panel's pending focus reveal, preventing
  a delayed reveal from undoing Home or a wheel gesture. Later genuine focus or
  layout changes still reveal the control.
- The podium reflows from three columns to two or one, preserving usable app
  labels and existing control objects/focus. Sort choices wrap inside their group
  and grow to fit their captions. A normal search with no compatibility suggestion
  no longer attempts to bind an absent value to a Boolean.
- Shared glyph painting now handles entirely clipped paths in Qt's software
  renderer. Native pixel tests cover nested clipping and geometry changes, and
  controlled negatives reproduce 827 white sidebar pixels and 368 colored pixels
  over the title without the correction. Culling the Shape retains the glyph's
  layout slot. Settings uses that same glyph component; its old per-sidebar
  workarounds are removed. GPU rendering retains its existing path.

Current scale, reduced-motion, regression and Wayland results are recorded in
docs/TESTING.md and `target/097-goal/store-scroll-validation.json`. They qualify
the tested paths, not all Store artwork, physical devices or a release image.
The software Store capture still has blank framed artwork to investigate. The
remaining app/input audit, matching laptop installation and final release gates
remain open. No commit, push or version bump was made; the account preview has
not been refreshed.

Eleventh implementation batch:

- Store screenshots, fallback paintings/icons and section banners now appear in
  the software renderer. Shader-only mask layers are bypassed in that renderer,
  and raster sources provide the paper mats behind images. Unavailable shader
  shadows are hidden. The normal OpenGL path keeps its masks and shadows.
- Native pixel checks cover a ready screenshot, no screenshot, an image-load
  failure returning to the painting/icon, and a section banner. The scale fixture
  moves to the smaller actual X screen, including a 608-pixel window at 200%.
  Restoring the shader-only mask layers reproduces all four blank-image failures.
- Private Wayland checks also exercise both client renderers. OpenGL pixels pass
  in the basic and threaded render loops; render-thread driver data from the
  basic-loop run identifies Intel Iris Xe/Mesa. These are virtual-output checks,
  not physical-display or other-GPU qualification. The software fallback uses
  rectangular image clipping rather than unsupported rounded shader masks.
- A missing `pgrep` in the test image was exposed by the regression log. Both
  image definitions now explicitly require procps-ng, and the desktop runtime
  checker requires the command. The refreshed local test image adds procps-ng
  without updating existing packages; the guarded native bundles retain their
  matching dependencies.

The former blank-artwork gap is resolved for these paths. Current results and
source hashes are in docs/TESTING.md and `target/097-goal/store-artwork-validation.json`.
The remaining app/input audit, real devices, matching laptop installation and
final release gates remain open. These changes are still local and uncommitted;
the account preview is unchanged and VERSION remains 0.9.6.

Twelfth implementation batch (focused menu checks):

- Tab reaches pinned apps, recent files and all apps with a selected item.
  Native arrow selection and both Enter keys remain usable; Escape clears
  search, returns from All apps and then closes. Menu and Shift+F10 request the
  selected app's context menu.
- All four menu lists accept mouse detents and touchpad pixel gestures. Apps
  and menu use one shared input component, included in both installation paths.
  Compact representation layouts reduce pinned rows and adapt their columns so
  recent files retain usable space in the tested short windows.
- Six focused cases pass in all six scale/font combinations (36 executions),
  plus six with native reduced motion. These load the actual representation and
  delegates with inert external models. A separate native Plasma/Kicker launch
  fixture passes, as do the affected search/profile checks (60 Python checks in
  total). The original focused baseline reproduced seven assertions failing in
  six cases without runtime errors.
- The shared input move also passes 431 affected Settings, Store and appearance
  checks with no skips or failed modules. These scoped runs do not replace the
  final full-suite/image run. Reports and source hashes are recorded in
  `target/097-goal/menu-navigation-validation.json` and docs/TESTING.md.

The menu popup's actual size limits still need qualification; these short-window
representation results do not close that item. Extraction/Transfers input,
physical devices, measured loaded-app readiness and laptop idle activity,
matching laptop installation, full-image upgrade/rollback and final release
checks remain open. The read-only preview plan includes the new shared handler;
it has not been applied. No commit, push or version bump was made.

Thirteenth implementation batch (actual menu popup bounds):

- A real Plasma panel reproduced an oversized menu after a live change to 200%.
  Its requested position was above the output; KWin placed the 604-pixel-tall
  frame at y=0, still overflowing the 494-pixel usable area. Representation-only
  window checks had not covered the outer popup.
- Menu size hints now use its own containment's available screen rectangle,
  leaving room for the native frame. An event-driven correction also handles a
  late Wayland configure restoring the old dimensions. Size hints alone did not
  resolve that case. The correction preserves native frame padding and only
  reduces oversized content; there is no polling.
- The actual Plasma/Kicker menu passes 12 compositor-observed checkpoints with
  10pt and 14pt native fonts: 125%, 150%, 200%, moving the panel between mixed-
  scale outputs, a live 175% change and moving the panel to the top edge. Search,
  pinned apps and recent-file regions stay inside the popup. Disabling only the
  correction, with bounded size hints retained, reproduces the overflow at 200%.
- The representation input matrix still passes all 36 executions. These are
  private virtual-output checks with software-rendered Plasma and an Intel
  OpenGL compositor; physical display/input qualification remains open.
- Six current reduced-motion checks and 445 affected menu/search/launch/dock/
  appearance regression checks also pass, without skips or failed modules.
  Reports and source/artifact hashes are in
  `target/097-goal/menu-popup-validation.json`.

Extraction/Transfers input and layout, real devices, measured app readiness and
laptop idle activity, matching laptop installation and final release acceptance
remain open. Nothing from this batch has been installed in the account preview;
no commit, push or version bump was made. Evidence is recorded in docs/TESTING.md.

Fourteenth implementation batch (extraction and Transfers input/layout):

- The extraction preparation dialog reproduced a 417-pixel minimum height on
  a 360-pixel logical screen. It now fits its current screen, keeps the drop
  target and native action buttons visible, and scrolls details separately.
  Narrow layouts stack full button captions. Focus reveals the destination and
  location chooser, precise touchpad pixels scroll, and Escape remains usable.
  Native extraction/password/cancellation and background-queue behavior remain
  covered by the operation suites.
- Transfers uses a native Flickable/scrollbar with the shared input handler.
  Enter/keypad Enter activate the focused native button once; held Enter does
  not repeat a transfer action. Long titles, states and errors wrap; action
  groups flow to more rows. Messages and explanatory text belong to the scrolling
  content so they cannot crowd the usable list out of a short window.
- Keyed local rows survive progress updates and reordering without recreating
  the focused control. Completing a job hands focus to its Open folder action.
  Geometry-driven focus reveal follows row movement; manual Home and checked
  wheel gestures are not undone by later progress updates. Loading cancellation
  and error dismissal remain keyboard accessible. Indeterminate animation stops
  while the full view is closed or inactive.
- Menu and Transfers sizing handle an early window resize whose anchored
  content has not caught up: temporary negative padding cannot shrink the window
  twice. Static Transfers popups also request a frame after position changes.
  Without that frame, Qt requested the new position but KWin retained the old
  one for more than five seconds after a scale change. A controlled current-source
  negative reproduces that failure with only the frame request disabled.
- Extraction passes 18 scale/font executions, three native-style reduced-motion
  checks and three private Wayland checks. Transfers passes 60 scale/font
  executions and ten native-style reduced-motion checks. Actual Plasma menu and
  Transfers popups each pass 12 compositor-observed checkpoints; the Transfers
  run displays three completed real Ark queue jobs. The affected regression run
  passes 513 Python checks without skips or failed modules. These are scoped
  checks, not final image or physical-device qualification.

Current reports, source hashes and captures are recorded in docs/TESTING.md and
`target/097-goal/extraction-transfers-validation.json`. Catalogs are regenerated
and checked. Matching laptop installation, real hardware/drives, measured app
readiness and laptop idle activity, customized-profile image upgrade/rollback
and final release checks remain open. The account preview is unchanged; all work
stays local and uncommitted, and VERSION remains 0.9.6.

Fifteenth implementation batch (matching laptop preview and launch overhead):

- Built activity, launcher, dock, Files and Archives against the laptop's actual
  package revisions and original Monet binaries. The SDK's differing libcurl
  revision was replaced only inside disposable containers; its library bytes
  match the laptop. Package/original-file/ABI/bundle guards remain enabled.
- The account installer now includes regional helpers, file tools, layout
  instructions, catalogs and the complete native set. Startup guards isolate
  each QML module and remove stale inherited preview paths. Changed runtimes
  fall back to system code. Existing Files desktop/service metadata is retained.
- Native preparation checks only code that the process can load. Files and Ark
  validate themselves when launched, rather than being hashed by every Settings
  or widget helper. Installed app-guard preparation measures a 1.393 ms median
  in seven warm-cache samples, versus 76.29 ms for the earlier all-component
  guard. This measures the guard, not app readiness or sign-in.
- Removed unused debug sections from shipped Files/Archives binaries while
  retaining unstripped local build trees. Files' executable/library pair shrank
  from 83.02 MiB to 4.22 MiB. Compared `.text` sections are unchanged, matching ABI
  checks pass, and corresponding source archives include the packaging step.
- The isolated preview loads its own QML modules and paired executables and
  reverses installation without replacing later personal edits. A 123-check
  affected run passes; after the packaging/guard optimization, 40 affected
  checks and a real delayed-network Files GUI run pass. Focused installer/bundle
  checks pass 43 tests. A completion-fixture failure was traced to an existing
  file manager owning its shared test bus; that fixture now owns a private bus
  and verifies its endpoint's readiness and ownership.
- Installed 264 changed account files, then the nine-file packaging/guard
  optimization. All 852 planned payloads match, all five native guards pass,
  and the twelve checked preference files are unchanged by both applications.
  Plasma restarted with no active transfers and maps the account activity,
  launcher and dock modules. Already-open Files/Settings windows must be reopened
  to use the newly installed code. Local undo receipts are retained.
- Preview retirement understands both installer receipt histories, includes
  account binary wrappers, and preserves preferences seeded by the first preview.
  Updated native test dependencies include the actual Files runtime.

Current evidence is in `target/097-goal/laptop-preview-validation.json` and
docs/TESTING.md. Matching account installation is complete; measured app readiness
and laptop idle activity, physical hardware/drives/input, customized-profile
whole-image upgrade/rollback, and final release preparation remain open. No
commit or push was made, and VERSION remains 0.9.6.

Sixteenth implementation batch (app measurements and parsed Store cache):

- Added a common Settings/Store observation probe for first frames and the frame
  following initial data settlement. Both revisions use the same probe, private
  profiles/buses and alternating run order. Native Wayland runs use a private
  KWin/OpenGL output. A separate Files bench records mapped windows and completed
  local listings, distinguishing the installed OS binary, account wrapper and
  verified native pair. These do not measure remote artwork or physical drives.
- The Store can reuse parsed catalog metadata when its source identity, parser
  schema, language and blocklist match. It still queries installed apps afresh.
  Invalid, stale, oversized, nonregular or unwritable cache files fall back to
  the catalog. Writes are atomic/private and run on the existing catalog worker
  after a real data frame; explicit Refresh reparses. The real 51 MB catalog's
  3,323 permitted app records compare exactly across fresh, saved and cached reads.
- On the laptop, five interleaved native runs give a Store data-frame median of
  473.652 ms for the installed preview versus 1,335.230 ms for the baseline.
  Its process peak-RSS median at that frame is 280.03 MiB versus 562.66 MiB.
  This is a cached-catalog/private-profile result. Five separate empty-cache
  runs show a faster first frame (413.852 versus 489.167 ms), but later catalog
  data (1,479.558 versus 1,380.813 ms). No universal cold-start gain is claimed.
- Settings' measured data frame is 549.166 versus 531.686 ms in that native run;
  ordinary local Files opening is comparable for the native pair (301.505 versus
  295.930 ms). The account wrapper measures 326.521 ms. These results do not prove
  those apps open faster. The existing slow-drive responsiveness checks remain
  separate evidence. More Settings/sign-in/idle work remains.
- Actual installed-app measurement caught a preview packaging omission: the
  private games URL could not resolve its relative shared-widget import. Added
  that sibling link and a regression that starts the actual installed Settings,
  Store and Games helpers. Their first frames and paired native executables now
  pass the reversible account fixture. This was missed by the earlier plugin-
  only installation check; failing reports and diagnostics are retained. Removing
  only the link reproduces the failure in the controlled negative check.
- Backend/startup/Store UI checks pass 73 tests without skips. Cache tests cover
  locale/filter/schema changes, atomic replacement, malformed files, cancellation
  of stale deferred saves and full-disk-style write failure. A deliberately slow
  save proves the catalog frame precedes serialization. The raw production entry
  point is also tested without the probe's extra Qt bindings.
- Installed the cache helper and shared-import repair with separate local undo
  receipts. All 853 current payloads match; five native guards pass and the twelve
  checked preference files are unchanged by both updates. The desktop remains
  running; reopen Store to use the new cache. No OS image was replaced.

Evidence and limits are recorded in docs/TESTING.md and
`target/097-goal/readiness-cache-validation.json`. Remaining release gates include
sign-in/Settings/idle improvements and comparisons, physical power/drive/input
qualification, customized-profile whole-image upgrade/rollback and final release
preparation. A physical menu/screen-behavior question is pending; no answer or
physical pass is assumed. Everything remains local, uncommitted and unpushed.

Seventeenth implementation batch (foreground power reads and repeat sign-in work):

- Power & Sleep's thirteen independent native KConfig reads now use at most four
  foreground workers, preserving request order and native inherited/locked
  policy. The workers finish with the request; no preference cache, daemon or
  polling is added. Standalone privacy reads retain their existing behavior.
- Sign-in preparation checks the existing region/download setup receipts before
  launching their already-completed helpers. Missing receipts and failed setup
  still retry; desktop-menu repair still runs. Explicit empty/custom bindings
  and later region/download choices remain intact.
- Seven interleaved native runs compare this batch with its frozen input using
  the same Settings UI and private profiles. The Power & Sleep data-frame median
  is 509.712 ms versus 563.173 ms; first frames are comparable. The foreground
  power helper measures 145.411 ms versus 180.034 ms, but combined helper/child
  CPU is 193.892 ms versus 179.733 ms. This trades a small amount of foreground
  CPU for latency; it is not an idle-power or battery-life improvement.
- The completed-setup sign-in helper measures 81.863 ms versus 211.276 ms, with
  CPU 81.210 ms versus 209.853 ms. This is the helper's time, not a measured
  sign-in/boot saving. The before/after profiles keep the same preferences.
- Affected backend/policy/profile checks pass 42 tests and broader appearance,
  Settings, region, downloads and startup checks pass 457 tests, without skips.
  The reversible account fixture passes 21 checks plus actual app/native launch
  and undo checks. Native tests include inherited locked groups, fresh reads
  after edits, malformed values, bounded work and missing/failed receipt retries.
- Installed the two helpers with a separate undo receipt. All 853 planned
  payloads match and all five native guards pass; the twelve checked preference
  files are unchanged. Read-only actual-account power results match the frozen
  preceding helper exactly. Reopen Settings to load the new helper.

Evidence is in docs/TESTING.md and
`target/097-goal/power-startup-validation.json`. A fresh desktop test image build
has started for final whole-suite verification; it is not yet a passing release
result. Complete sign-in/idle comparisons, physical power/drives/input,
customized-profile full-image upgrade/rollback, broader language review and final
release preparation remain open. No commit, push, OS image replacement or
version bump was made.

Eighteenth implementation batch (complete desktop/Rust verification and OS integration):

- Rebuilt the required Fedora 45 desktop runtime, including the guarded native
  activity, launcher, dock and archive components. On this SELinux host, the
  documented private-socket build option is required; with it, compositor
  reconnection and both launcher native suites pass without changed assertions.
- The complete desktop run covers all 115 Python test modules: 1,595 tests pass
  and 19 declared environment-specific cases skip. All selected JavaScript tests
  and eleven browser-form checks pass. All 2,252 recorded input files match
  before/after the run. This closes the complete desktop-suite run for this code
  snapshot; it does not qualify a full OS deployment or physical hardware.
- The image's Rust builder matches that same source snapshot. Its Linux
  workspace tests pass 99 checks, and Clippy passes for all targets with warnings
  denied. Syntax checks also pass for 27 shell and 107 Python source files.
- A full local Mesa integration image is building from the digest-pinned
  Bazzite base. It retains VERSION 0.9.6 while integration is checked; release
  version/notes preparation remains separate. Nothing is published or installed
  over the laptop's OS.
- Prepared a rootless KVM toolbox and a checksum-verified Fedora Cloud installer
  guest. The guest boots with Secure Boot enabled and accepts its task-specific
  SSH key. The published Monet 0.9.6 Mesa baseline is installing to its newly
  created 128 GiB virtual disk after checking the guest hostname, disk serial,
  size, absence of partitions/mounts and the separate installer/other-drive
  serials. This is setup for customized-profile upgrade/rollback, not a passing
  Monet boot or upgrade result.

Completed desktop/Rust evidence is in
`target/097-goal/release-desktop-validation.json`. The active full-image build
and guest installation have separate logs and process handles; neither is
treated as finished based on its state file alone. These two progress documents
were updated after the recorded test inputs; product and test sources are
unchanged. Full-image acceptance, complete sign-in/idle comparisons, physical
power/drives/input, broader language review and final release preparation remain
open. No commit or push was made.

Nineteenth implementation batch (localized search, wrapping controls and candidate preparation):

- Filled 336 search names, descriptions and alias entries across the 28 catalogs
  that still used English; existing Swedish translations are retained. Real
  compiled-catalog checks cover four independent native phrases in every one of
  the 29 supported languages, exact read-only navigation and English fallback.
- Actual Arabic/large-font rendering reproduced timer controls extending beyond
  their Settings card. Choices now measure their labels, wrap within the card
  and keep centered captions, keyboard activation and focus. Final native runs
  pass 104 checks across German, Arabic, Japanese and Thai at 150%/200%, plus
  78 English/Swedish checks at 125%/150%/200%. These use private Xvfb/software
  rendering and real KDE controls; physical input/display checks remain open.
- Refreshed the laptop account preview with 57 changed payloads (the two catalog
  locations and Settings QML). All 853 planned payloads match, five native guards
  pass and twelve checked preference files are unchanged. Reopen Settings to use
  the layout/catalog update; its independent undo receipt is retained.
- Prepared VERSION, workspace package versions and release notes for a local
  0.9.7 candidate. No downloads or OS images have been published. The preceding
  complete desktop/Rust run predates these changes and must be repeated against
  the final sources.
- The earlier Mesa integration build completed with 14 bootc lint checks passing
  and one skipped. It retains 0.9.6 and predates this batch, so it is integration
  evidence rather than the final 0.9.7 candidate. The published baseline installed
  successfully to the isolated virtual disk; another virtual drive is unchanged.
  Secure Boot enrollment in the VM is not yet complete, so neither a successful
  baseline boot nor customized-profile upgrade/rollback is claimed.

Final image/source verification, customized-profile upgrade/rollback, complete
sign-in/idle comparisons and physical power/drives/input remain open. Evidence
and precise scopes are recorded in docs/TESTING.md. All work remains local,
uncommitted and unpushed; the laptop OS image has not been replaced.

Twentieth implementation batch (release checks and customized VM baseline):

- Built the first local 0.9.7 Mesa candidate. The complete desktop run then found
  a missed 0.9.6 sign-in stamp; corrected it to 0.9.7 without changing the
  content-based profile migration. The revised Mesa image builds successfully
  with 14 bootc checks passing and one skipped. Neither is a release acceptance
  result for the later runtime-package fix described below.
- The revised full desktop run exposes four fixture failures under concurrent
  image compilation. A controlled delayed observer reproduces the native
  form-test race: its timed mutation precedes target capture. The fixture now
  captures, mutates and verifies through private pipes. Its delayed positive
  control passes, retaining all credential-rejection/native-value assertions.
  Archive tests verify that a dialog actually vanished before skipping its old
  X11 ID. Settings/recovery checks wait for bounded asynchronous completion.
  All four affected modules now pass their combined 64 checks, without skips;
  a final complete run after these changes remains required.
- Rust's final-version builder passes 99 workspace tests and warnings-denied
  Clippy, with its recorded 2,253 copied inputs verified before the run. Later
  changes are outside Rust inputs. Test-harness failures and original complete
  test reports are retained rather than relabeled as passing runs.
- The NVIDIA build stops at the strict PDF runtime guard: development headers
  upgrade ICU 78.3-8 to 78.3-9 after runtime capture. Added ICU to the runtime's
  existing matching-library update, retaining all package/binary/ABI guards.
  Both corrected OS image variants still need successful final builds.
- The isolated published 0.9.6 baseline boots to its graphical desktop and
  accepts the private SSH key. Secure Boot is enabled, Universal Blue's key is
  enrolled, SELinux is enforcing and no system units are failed. A normal test
  account has signed in, customized its panel, region/units, weather, download
  folder and startup choices, then signed out. Its file/permission/link/config
  proof and clean-shutdown disk/firmware checkpoint are saved for the actual
  upgrade/rollback test. The separate sentinel drive is byte-for-byte unchanged.

The VM baseline is preparation, not a successful upgrade/rollback. Final image/
desktop verification, full sign-in/idle comparisons and physical power/menu/
drive/input checks remain open. Source version is an unpublished 0.9.7 candidate;
the laptop keeps its existing OS and reversible account preview. No Git commit
or push was made.

Twenty-first implementation batch (complete candidate verification and canonical VM):

- Both corrected local 0.9.7 image variants build successfully from the same
  frozen 2,253 inputs. Each passes 14 bootc checks with one skipped. The actual
  binaries in both images report 0.9.7. Local OCI exports include verified
  archive/config/manifest identities and checksums; nothing is published.
- The final full desktop run passes all 116 modules: 1,597 Python tests pass,
  with the same 19 declared environment skips; selected Node checks and eleven
  browser-form checks pass. Rust/Cargo inputs still match the verified 99-test
  and warnings-denied Clippy run. No product/test source changed during builds
  or the complete desktop run.
- Refreshed the final sign-in helper in the reversible laptop preview. All 853
  payloads match, all five native guards pass and twelve checked preference
  files are unchanged. Read-only laptop power data confirms AC screen/sleep and
  automatic locking are disabled; lock on resume remains enabled. This is
  configuration evidence, not a physical screen/lid pass.
- The first VM layout was unsuitable for release qualification: its root-bound
  /boot collided with a GPT-generated automount. It stopped the shutdown-trial
  service during import and failed to finalize a staged update. Those negative
  reports remain; no successful upgrade is claimed from that fixture.
- Rebuilt the baseline with a separate 1 GiB EFI partition, 2 GiB ext4 boot
  partition and Btrfs root subvolume. Its saved account is mirrored exactly,
  without adding fresh-account defaults. The new baseline boots, preserves all
  checked files/preferences, uses the expected ext4 /boot with no conflicting
  automount, and keeps the trial service active. Secure Boot and SELinux remain
  enabled. A clean-shutdown checkpoint and independent NVIDIA copy are saved;
  the unrelated virtual drive remains byte-for-byte unchanged.

Completed source/build evidence is `target/097-goal/candidate097-v3-validation.json`.
Actual candidate upgrade/rollback, complete sign-in/idle comparisons and physical
power/menu/drives/monitor/input checks remain open. The laptop OS image is
unchanged; everything remains local, uncommitted and unpushed.

Twenty-second implementation batch (both image round trips and installed-app checks):

- Both exact v3 candidate images boot with Secure Boot enabled and SELinux
  enforcing, accept a graphical sign-in, preserve the customized profile, and
  roll back to their pinned published 0.9.6 image. Checks pass before sign-in,
  in the actual desktop and after clean sign-out, including live panel geometry.
- The original fixture's missing preferred-browser pin is also pruned by the
  0.9.6 desktop. KDE moves its Files shortcut to the native services group while
  retaining the key; the actual custom key opens Files. Original diagnostic
  reports remain, and the final comparisons use stable 0.9.6 captures.
- Both variants open installed Settings, Store and Games to their first frames.
  Settings opens the precise lock control. Actual archive dialogs extract a
  fixture to Desktop through the installed Ark backend; completed queue records
  and file contents match. Transfers offers Open folder, which opens the actual
  result in Files. New files remain accessible after rollback.
- The NVIDIA VM uses a virtual GPU. Its two NVIDIA CDI no-device failures are
  independently recorded on both baseline and candidate; no additional failed
  units appear. Physical NVIDIA qualification remains open. Mesa has no failed
  system units. All original preference/file comparisons remain enabled.
- Extraction creates a Transfers widget through the normal product flow. After
  checking completion, the smoke test removes only its newly created widget,
  then verifies the original panel configuration before the rollback comparison.
- Actual image rendering exposes clipped disk-space text in Files at the VM's
  scale. The published 0.9.6 image reproduces it too. Investigation/fix remains
  in 097-08; no product/theme source is changed in this batch.

The completed image round trips are additional integration evidence for the
frozen v3 sources. Complete sign-in/idle comparisons, the Files label issue and
physical power/menu/drives/monitor/input acceptance remain open. No Git commit,
push, publication or laptop OS replacement was made.

Twenty-third implementation batch (Files disk-space label):

- Reproduced the clipped text in a native button/layout probe and the actual
  unmodified Files pair. The fixed-height disk-space section inherited nine
  pixels of top and bottom layout margin, leaving twelve pixels for its button.
- The source patch removes only those vertical margins. Horizontal spacing,
  text, the capacity bar and disk-usage actions are retained. The rebuilt native
  pair passes the existing experience and delayed-space suites. Ten real Files
  runs cover all six themes and 125%/150%/200% scaling, including large text;
  delayed-drive navigation and stale-reply checks pass. Actual before/after
  captures show the vertical clipping fixed. Tight widths still elide long text.
- Installed five changed native-preview payloads with a new undo receipt. All
  853 payloads match, all five guards pass and twelve preference files are
  unchanged. Close and reopen Files to load the new native pair.
- The laptop-specific pair correctly refuses a different base binary in the VM.
  Its guard is retained. Both OS image variants need rebuilding with the source
  patch, followed by installed-image verification. Earlier v3 round trips remain
  evidence for their recorded source snapshot.

Full sign-in/idle comparisons and physical acceptance remain open. No commit,
push, publication or laptop OS replacement was made.

Twenty-fourth implementation batch (current images and session measurements):

- Both v4 image builds include the Files label fix. The actual installed Mesa
  and NVIDIA images show readable text, preserve the customized account through
  graphical sign-in/sign-out, and roll back to their pinned 0.9.6 images. Secure
  Boot and SELinux remain enabled. NVIDIA remains a virtual-GPU check with the
  previously recorded no-device CDI exceptions.
- The full serial desktop run passes all 116 modules: 1,597 passed checks and
  19 declared skips, plus the Node and 11 browser-form checks. The original
  concurrent-run fixture failures remain recorded; no assertions were changed.
  Current Cargo/Rust inputs still match the 99-test and Clippy pass.
- Three complete graphical sign-ins per image measure the user manager to
  settled, responsive saved panels. Median times are 3.646 s initially on
  0.9.6, 5.510 s on the candidate and 5.178 s after returning to 0.9.6. No
  startup gain is demonstrated; the return run also shows that the full initial
  gap cannot be attributed to candidate code.
- Three 30-second samples per visible/locked phase include the whole user
  cgroup and normal helper bursts. Pooled CPU use, as a percentage of one core,
  is 0.887%/0.855% on the original baseline and 10.403%/10.293% on the candidate.
  A separate 30-second visible sample after rollback is 0.857%. Most candidate
  CPU is in Plasma and KWin. This is an open performance issue, not acceptance
  evidence for reduced idle work or battery savings. The upstream KWin package
  also differs between images; the cause is not yet isolated.
- User confirms that Desktop/widget context menus and AC stay-awake with all
  idle timers Never work on the laptop. Other physical checks remain separate.
  The lock-screen question is explanatory; no lock controls are removed.

Raw measurements and qualifications are in
`target/097-goal/vm/session-benchmark-comparison.json`. Live external weather was
not frozen, startup/page caches differ across boots, and candidate samples may
include deferred sign-in work. Authentication, complete remote widget contents,
physical graphics/input, hardware wakeups and battery life are outside this
measurement. Performance investigation and remaining physical acceptance are
still open. All work remains local, uncommitted and unpushed.

Twenty-fifth implementation batch (hidden cursors and the clock screen):

- Traced repeated desktop frames to Weather's hidden city-search input retaining
  active focus and a blinking cursor. It now releases focus when hidden, guards
  deferred focus requests and pauses cursor/search work while inactive. The
  native regression reproduces the old hidden/focused/blinking state on the v4
  source and passes with the fix.
- Current Plasma no longer supplies VirtualKeyboardLoader. Its missing type
  prevented Monet's lock screen from loading. The current keyboard API restores
  Monet's design; the large clock stays, with responsive sizing and an Unlock
  button. Enter opens the form, pointer movement preserves typing and Escape
  returns to the clock. Hidden password fields release focus and stop blinking.
- Seven cases in the actual KDE greeter cover desktop, smaller and portrait
  layouts, native keyboard/pointer input, hidden-cursor checks and the consent
  UI for an account without a password. Actual VM password authentication also
  passes. The native authentication backend and fallback are preserved.
- Updated the account preview with receipts 20261106T121511.287239Z and
  20261106T123052.119950Z. All 853 payloads and five native guards verify; twelve
  checked preferences are unchanged. The clock loads on the next lock, and the
  Weather component on the next sign-in. The undo guide lists both receipts.
- Repeat VM observations with private QML overrides include all normal periodic
  helper bursts. Pooled CPU is 1.375% visible / 0.605% locked, versus the original
  candidate's 10.403% / 10.293%, as percentages of one virtual core. Baseline
  0.9.6 was 0.887% / 0.855%; these short runs do not establish battery savings
  or a general improvement over 0.9.6. Startup remains variable with no general
  gain claimed. Current full-image qualification must use the final sources.
- User confirms sleep/wake, lid and touchpad checks. External-monitor testing
  remains untried. Physical drive and GPU qualification were not included in
  that question and remain separate.

Both final images and the complete suite need rerunning for these source changes.
Diagnostic account overrides will be retired before actual image checks. No
commit, push, publication or laptop OS replacement is made.

Twenty-sixth implementation batch (final-image checks and weather settling):

- Both v5 images build from the frozen 2,255 inputs. The serial suite passes
  117 modules: 1,598 checks passed and the same 19 declared skips, plus Node and
  11 browser-form checks. The 46 Cargo/Rust inputs still match the earlier
  99-test and Clippy pass.
- Both actual v5 images load the shipped clock and Weather sources without
  diagnostic account overrides. Native password unlocking and customized
  profile checks before sign-in, on the desktop and after sign-out pass.
- Three serial v5 sign-ins have a 5.586 s median to settled, responsive panels.
  Startup remains variable; no general gain is demonstrated. The subsequent
  visible idle samples reveal sustained wallpaper rendering while its weather
  effect fades for three minutes. A controlled static-wallpaper comparison
  drops the load, and restoring The Hours brings it back.
- The weather effect now settles in 1.5 seconds, matching the other wallpaper
  transitions. Its final appearance and lock/display-off pauses are preserved.
  A native regression fails with the exact old source and passes with the fix.
  One 30-second VM observation with only that wallpaper override uses 0.874%
  of one virtual core; this is targeted evidence, not final-image or battery
  qualification. The override is retired before final image checks.
- Installed the account preview with receipt 20261106T132004.687755Z: one
  changed payload, all 853 verified, five native guards valid and twelve checked
  preferences unchanged. It loads at the next sign-in; the undo guide is updated.

The v6 images and complete suite must include this last wallpaper fix. Physical
drive, graphics and external-monitor checks remain separate. Everything stays
local, uncommitted and unpushed.

Twenty-seventh verification batch (final v6 candidate):

- Both v6 images build from the unchanged 2,255-input snapshot. The full serial
  suite passes all 117 modules: 1,598 checks passed, the same 19 declared skips,
  Node and 11 browser-form checks. Installed image sources match the clock,
  Weather and shortened wallpaper transition, and the native Files pair/source.
- Both actual images pass customized-profile prelogin, graphical desktop and
  post-sign-out checks, native password unlocking and rollback to the pinned
  0.9.6 image. Files, startup choices, panels, shortcuts, region, weather,
  downloads and power settings persist. Secure Boot and SELinux remain enabled;
  both unrelated virtual sentinel disks remain unchanged. No account QML
  overrides are present. NVIDIA qualification uses a virtual GPU and only its
  recorded baseline no-device CDI exceptions.
- Final serial sign-in samples are 5.077 / 5.710 / 5.634 s to settled, responsive
  panels. No general startup improvement is demonstrated. Three 30-second
  visible intervals use 0.933 / 0.319 / 16.856% of one virtual core; locked
  intervals use 1.150 / 0.321 / 1.144%. Pooled values are 6.0362% visible and
  0.8718% locked. The higher visible interval is retained; its Plasma/KWin CPU
  accounting does not establish the exact cause or timing within that interval.
  These short, live-weather VM runs do not establish uniform CPU or battery
  savings. They no longer show the sustained three-minute rendering cost;
  the native controlled regression independently verifies prompt settling.

Evidence is in `target/097-goal/candidate097-v6-validation.json`,
`target/097-goal/vm/candidate097-v6-image-roundtrips.json` and
`target/097-goal/vm/session-benchmark-v6-comparison.json`. Both VMs are cleanly
stopped on 0.9.6. Only progress documentation changes after the frozen checks;
product and test sources remain unchanged. The latest laptop preview receipt
remains 20261106T132004.687755Z. No commit, push, publication or laptop OS
replacement is made. Physical acceptance remains open.

Twenty-eighth implementation batch (thumbnail cancellation acceptance audit):

- Exercised the actual v6 Files pair against 2,000 distinct photo paths with
  4,800×3,200 JPEGs, an empty thumbnail cache and native previews. Four image
  payloads are shared by hardlink; this isolates list/decoding/UI pressure and
  does not model physical drive throughput. Native thumbnail URI metadata is
  verified, and cache entries grow from 5 to 84 during responsiveness sampling.
- The slowest of sixty state queries is 2.048 ms. Navigation away takes 131.110
  ms including native keyboard typing, and the original tab's selection/scroll
  is preserved. However, Stop remains disabled during active preview generation.
  The stronger regression fails on that missing control in the actual v6 pair.
- Added native preview-work signals to the existing Files progress/Stop path.
  The proposed cancellation leaves completed previews and saved preview choices
  intact; a new listing/Refresh resumes work. Verification covers Stop, Escape,
  refresh, active-tab state and normal window teardown. Native builds and tests
  remain in progress; the installed laptop preview has not been replaced yet.

This reopens the software part of 097-03. The v6 validation remains historical
evidence; it does not qualify the new code. No commit, push or publication is
made.

Batch 28 native verification and account installation:

- Preserved the original exported helper and class data layouts; the native
  pair passes its complete package/ABI seal in the matching build runtime.
  A mismatched generic test runtime is refused rather than used for evidence.
- The stronger 2,000-photo native case passes at 100%, 125%, 150% and 200%.
  Stop/Escape halt new previews, Refresh resumes them, completed cache entries
  remain, the saved preview preference is unchanged, and Stop follows the
  active tab. Prior selection/scroll and late-result navigation checks pass;
  Files closes normally. Loading and the native Stop control are visible.
- Maximum state-query latency is 4.560 ms across all four cases. The complete
  run includes actual JPEG decoding and thumbnail URI verification; shared
  payloads/caches mean these are not physical disk-throughput measurements.
- Installed five changed account payloads with receipt 20261106T144417.965361Z.
  All 853 payloads, five native guards and twelve checked preference files
  verify. After file copies finish, close all Files windows and reopen Files
  to use the new pair. The undo guide lists this receipt first.

Evidence: `target/097-goal/files-thumbnail-native-matrix.json`. The new v7
snapshot still needs complete build/test and installed-image qualification.

The final native regression strengthens the original-tab case to 401 text files,
a selected item and nonzero scroll, and checks current/selected items through
Refresh. All four scales pass. At 200%, native layout settles to a six-pixel
smaller scroll range; the saved bottom position correctly clamps to the new
maximum, with selection/current item unchanged. Raw before/after diagnostics
are retained rather than treating derived range equality as the preservation
contract. `target/097-goal/files-thumbnail-native-strong-matrix.json` records
the final fixture/helper hashes and each complete native case.

Twenty-ninth verification batch (final v7 images):

- Both images build from the frozen 2,257-input snapshot with native package/ABI
  seals and two native CTest checks. The complete serial suite passes all 117
  modules: 1,598 checks passed, the same 19 declared skips, Node and 11 browser
  form checks. The 46 Cargo/Rust inputs still match the earlier 99-test and
  warnings-denied Clippy pass.
- Files pairs extracted from both actual production images pass the final
  2,000-photo regression at 100% and 200%. Stop/Escape, Refresh, active-tab
  state, saved preview choice, current/selected items, nonzero scroll, stale
  replies and clean window closure pass. Maximum state-query latency is
  4.603 ms; these synthetic shared-payload cases do not measure drive throughput.
- Both actual images pass profile checks before sign-in, on the desktop and
  after sign-out, then the same three phases after rollback to pinned 0.9.6.
  Saved files, startup choices, panels, shortcuts, region, weather, downloads and
  power settings persist. Password unlocking uses the shipped Monet clock;
  all five checked QML files and the native Files pair match the final images.
  No diagnostic account overrides are present. Secure Boot and SELinux remain
  enabled. NVIDIA uses a virtual GPU with only its recorded baseline no-device
  CDI exceptions; physical graphics qualification remains open.
- Both VMs are cleanly stopped on 0.9.6 and unrelated virtual sentinel disks
  are unchanged. Exported archives pass independent full verification in each
  guest before staging. All 2,257 frozen inputs still match after the roundtrips.
  Subsequent edits only update this backlog and the testing record.

Evidence: `target/097-goal/candidate097-v7-validation.json`,
`target/097-goal/files-thumbnail-v7-production-matrix.json`,
`target/097-goal/candidate097-v7-exports-verified.json` and
`target/097-goal/vm/candidate097-v7-image-roundtrips.json`.
Concurrent VM sign-ins here are functional checks, not new performance samples;
the earlier v6 session measurements and their limits remain recorded separately.
The latest laptop preview receipt is 20261106T144417.965361Z. Close Files after
copies finish and reopen it to load the new pair. The clock appears on the next
lock; sign out and back in to load the desktop Weather/wallpaper changes.
Physical acceptance remains open. No commit, push, publication or laptop OS
replacement is made.

Thirtieth verification batch (available laptop renderer):

- Recorded the user's external-monitor answer, “Cannot test yet”, as unverified.
  Read-only inventory confirms only the built-in display is connected and no
  removable drive is attached. Neither check is treated as a pass.
- The four Store screenshot/fallback/banner pixel cases pass at 150% with the
  physical RTX A500 GPU identified by QRhi, excluding a software renderer. The
  same four cases also pass with Qt's threaded OpenGL loop and the same exclusive
  NVIDIA client environment. A private Intel KWin compositor uses a virtual
  output; no active laptop display configuration or session is changed.
- The first setup attempt applies the NVIDIA environment to the compositor too
  and stops at the active-compositing guard before app tests. That failure is
  retained. The client-only adapter changes environment placement and leaves
  the fixture and pixel assertions unchanged.

Evidence: `target/097-goal/candidate097-v7-physical-renderer-check.json`.
This adds client-renderer coverage; it does not establish physical monitor,
drive disconnect, suspend, power or full graphics acceptance. Product/test
sources and the installed preview remain unchanged. Physical acceptance still
needs connected hardware; no monitor question is repeated.

Thirty-first implementation batch (archive inspection):

- User reports slow ZIP opening and requests a right-click Open action for
  inspecting contents. The managed archive MIME handler was entering extraction
  preparation. It now launches native Archives directly, without a Python
  extraction dialog or destination lookup. Existing explicit alternative MIME
  choices are preserved because the managed handler ID stays the same.
- A top-level Open service action uses the same browser. Extract archive… is
  separate and retains the destination-folder drop box and durable transfer
  workflow. Installation, uninstallation and account-preview wiring include
  the new service; the preview uses the existing guarded native Ark binary.
- All 32 affected checks pass without skips. Four native cases use actual KDE
  MIME/default and service-menu dispatch, rather than directly launching the
  browser. Both routes show an unchanged 8-entry ZIP in 207–209 ms and an
  unchanged 12,000-entry ZIP in 1.356–1.528 s, without extraction. Literal Unicode,
  field-code and shell-metacharacter filenames survive dispatch; each native
  browser exits 0. These synthetic warm local cases do not establish timings for
  the user's particular ZIP, cold starts or unavailable drives.
- Installed two desktop-entry payloads with receipt 20261106T162311.847163Z,
  rebuilt the application/menu caches, verified all five native guards and
  preserved twelve checked preference files. No active laptop window or session
  is terminated. The latest undo receipt is listed first in the local guide.

Evidence: `target/097-goal/archive-open-affected-tests.json`,
`target/097-goal/archive-open-native-v4/result.json` and
`target/097-goal/archive-open-preview-installed.json`. The earlier v7 images
remain historical qualification for their frozen source; this metadata change
needs inclusion in the next final image build. Nothing is committed or pushed.

Thirty-second correction (preserve double-click extraction):

- The user's request was for a separate right-click Open action; changing the
  double-click default to browsing was a misinterpretation. Restored the exact
  previous extraction desktop entry. Double-click opens the destination-folder
  drop box; Open browses contents directly in native Archives. The separate
  Extract archive… service action remains available.
- Installed only the restored application entry with receipt
  20261106T163255.663760Z. The Open service bytes and six checked preference files
  stay unchanged; the default MIME handler ID is preserved and caches refreshed.
  The undo guide lists this correction before batch 31's installation.
- The native regression now verifies the two different behaviors through actual
  KDE default/action dispatch for both small and 12,000-entry ZIPs. Extraction
  boxes appear in 176 / 202 ms and cancel with the expected exit 1. Open shows
  contents in 193 / 1,342 ms and browsers exit 0. No files are extracted without
  an explicit extraction action. Archive bytes remain unchanged. Four native
  cases and fourteen affected preference/preview checks pass; timings remain
  bounded synthetic warm-local observations, not a general speed claim.

Evidence: `target/097-goal/archive-default-extract-native-v2/result.json`,
`target/097-goal/archive-default-extract-checks.json` and
`target/097-goal/archive-double-click-restored.json`. No commit or push is made.

Thirty-third implementation batch (Monet power page):

- The user's screenshot shows the stock shell power page with oversized painted
  theme icons. The existing Monet page was installed only under global themes;
  the current Plasma greeter loads the desktop shell's logout page instead.
  Wired the new page into that shell and retained its original page behind a
  loader fallback. Both legacy Monet global themes receive the same design.
- Replaced the icon row with a centered Mist/Smoke panel, Fraunces heading,
  Inter labels, compact drawn line icons and responsive action cards. Cancel
  stays separate and visible. Short views scroll the content and reveal keyboard
  focus; labels wrap and follow larger text, fractional scaling and RTL layout.
- Native action signals, permissions, update/plain choices, countdowns, boot
  notes and other-session warnings remain. Countdown cancellation is shared
  across screens; destroyed custom pages unregister their callback. One shared
  action claim prevents two screens choosing different actions during the fade,
  and is released if its owning page is removed. Sign-out does not warn about
  other users losing work. No helper process or power action is added by the UI.
- Thirteen focused cases pass at 100%, 125%, 150% and 200%. Eleven packaging/preview
  checks pass. The OpenGL basic-loop layout case identifies the physical NVIDIA
  GPU for all four rendered layouts; all thirteen cases also pass on the threaded
  OpenGL path. These use private virtual outputs, not monitor qualification.
  The real Plasma greeter loads the generated preview shell and cancels with
  Escape. Intentionally breaking Monet's component loads the preserved native
  fallback, which also cancels. Neither native case emits a power action.
- The initial thirteen-file installation and subsequent shared-action fix are
  retained in the receipt history. Latest receipt 20261106T174648.821127Z updates
  three page copies, verifies sixteen power-page payloads/five native guards and leaves
  fourteen checked preferences unchanged. No live session is restarted. The
  next opening loads the page; cancel an already-open prompt first. The undo
  guide lists the new receipt before the archive correction.

Evidence: `target/097-goal/power-screen-controls-verified.json`,
`power-screen-scale{125,150,200}-verified.json`, `power-screen-packaging.json`,
`power-screen-gpu-{basic,threaded}-final/result.json`,
`power-greeter-native-positive-verified/result.json`,
`power-greeter-native-fallback-final/result.json` and
`power-screen-preview-installed.json` under the same directory. The full image
and physical acceptance limits above remain open. Everything stays local,
uncommitted and unpushed.

Thirty-fourth correction (power hover and actual Files archive activation):

- Prevent the transient power-page scrollbar from intercepting card hover when
  content fits. Reserve its space when scrolling is needed, explicitly enable
  hover, and use immediate opaque tinted fills without colour-animation churn.
- Make Files' default archive policy explicitly follow the extraction MIME
  handler. Existing deliberate archive-as-folder preferences remain preserved
  by the default-only migration; this requested laptop preview sets it to false.
  Right-click Open still browses contents in Archives.
- Fourteen power cases pass at 100% and 150%; hover and short/large-text checks
  pass at 200%, and hover passes on the isolated threaded OpenGL GPU path.
  Eleven migration/preview checks pass. Two actual Dolphin GUI activations
  (double-click and Enter) open the extraction box and cancel without extracting.
  Four native single-file/service dispatch cases retain separate extraction
  and inspection. Earlier archive tests covered multi-file preferred dispatch;
  the fixture now covers Dolphin's single-file OpenUrlJob too.
- Local receipt 20261106T183554.489130Z changes five files: three power-page
  copies, the look helper and only the requested archive preference in dolphinrc.
  Launch caches are refreshed, seven selected payloads and five native guards
  verify. Reopen Files once for its in-memory settings/launch data; no laptop
  restart is required. Active laptop windows are not closed automatically.

Evidence: `target/097-goal/power-hover-*.json`, `power-hover-gpu/result.json`,
`files-archive-activation-v3/result.json`,
`archive-real-single-activation-final/result.json` and
`hover-archive-preview-installed.json`. No commit, push or new full-image claim.

Thirty-fifth correction (tab closing, app priority and package prompts):

- Files accepts a square of at least 32 logical pixels around its native tab
  close button (36 with the current 20-pixel icon), clipped to the owning tab.
  Native icon geometry, style and hover/press events remain; moving away cancels
  a press. Reordered/RTL tabs retain their original native close signal.
- Search includes matching running application identities and executable file
  results in its app section. Running Files/Archives windows whose document name
  matches the query stay with other results. Late task metadata refreshes priority.
  Native source-row activation and query-change guards remain. The actual laptop
  Kicker query now puts ChatGPT ahead of its RPM and Archives window.
- The screenshot's archive is an RPM, not ZIP. Added its MIME type to the
  extraction/default/Open routes; it now prompts without listing its 622 MB
  payload first. Opening the box neither extracts nor installs the package.
  Actual small/12,000-entry ZIP and large RPM prompts appear in 519/384/487 ms
  in private warm-local checks, then cancel without changing archive bytes.
- Native tab behavior passes with MonetDark/Kvantum at 100%, 150% and 200%.
  Search/navigation, archive controls, MIME defaults and the matching native
  encrypted extractor checks pass. The rebuilt Files executable retains the
  identical private library; native preview install/load/undo also passes.
- Receipt 20261106T201754.718157Z changes ten account-preview files, verifies
  thirteen payloads and five native guards. Only the requested RPM association
  changes among checked preferences. The desktop menu was refreshed; existing
  applications remain open. Reopen Files once for its new executable.

Evidence: `target/097-goal/tab-search-archive-preview-installed.json`,
`tab-target-native-style-final.log`, `search-app-priority-installed-source.json`,
`search-live-priority.json`, `archive-zip-rpm-activation-final/result.json`,
`archive-rpm-defaults-final.json` and `tab-target-preview-private.json`.
Everything remains local, uncommitted and unpushed; no full-image qualification
or physical monitor acceptance is claimed for this correction.

Thirty-sixth correction (archive action authorization and calendar repeat picker):

- KDE rejected the user-owned service menu installed at mode 0644. Install the
  four Monet service menus at 0755, including generic Linux installs. Archive
  file modes and global execution policy stay unchanged. The preview installer
  now detects mode-only changes, records/restores permissions, and preserves
  later personal permission edits during restore/retirement.
- Replace the repeat dropdown with a Monet picker. Options match the green
  button, wrap, scroll in limited space, and support arrows/Home/End/Enter/Space
  and Escape. Placement measures the button and real notes window, then maps
  into the actual Controls overlay; it accounts for Plasma Dialog's offset
  overlay without Qt ComboBox's unwanted automatic flipping.
- The real laptop authorization query changes from rejected to accepted. Four
  KIO default/Open cases and two actual Files activations pass as UID 1000,
  including 12,000-entry ZIPs; root ownership no longer masks service trust.
  Thirty-four installer/desktop/notes checks pass, plus three repeat-control
  cases at each of 150%/200%, and actual notes-window placement on private
  Wayland at 150%. No extraction occurs in the cancelled native checks.
- Receipt 20261106T205033.991070Z updates four service-menu modes and twenty
  shared DayNotes copies. All 24 payloads/five native guards verify; fifteen
  checked preference/notes files stay unchanged. The desktop refresh loads the
  picker without a laptop restart. Everything remains local and uncommitted.

Evidence: `target/097-goal/archive-authorization-{before,after}.json`,
`archive-authorization-nonroot/result.json`,
`files-archive-authorization-nonroot/result.json`,
`archive-trust-calendar-final-checks.json`, `calendar-repeat-scale{150,200}.json`,
`calendar-repeat-wayland/result.json` and `archive-trust-calendar-preview-installed.json`.

### Thirty-seventh correction: brightness memory and Home Bar wording

- Added a session-owned brightness service. It records PowerDevil's logical,
  undimmed built-in-panel level on signals from brightness keys and sliders,
  atomically saves it with private permissions, and restores it once when the
  service/panel becomes available. It also handles late startup and service
  restarts without tying the panel to a temporary display number. External
  monitors remain independent. No idle polling or repeated helper launches.
- HDR can leave the kernel backlight at 100% while the chosen logical level is
  lower: the laptop reported 400/400 in sysfs but 2000/10000 through PowerDevil.
  The latter is the value remembered. Temporary profile changes and this
  helper's own restore events do not replace the saved choice.
- Native dock context menus now say Pin to Home Bar, Unpin from Home Bar and
  Configure Home Bar. The actual Task Manager app retains its name. Native
  pin/launch actions, activity handling and dock effects remain in place.
- Sixteen focused Python checks pass without skips, including real private
  D-Bus round trips for late startup, keys, slider changes, changed display
  numbers and a new session. The rebuilt compiled dock passes actual menu-label
  and pointer-launch/duplicate/new-window checks. Catalog and service validation
  pass. Receipt 20261106T210319.762180Z installs ten changed files, verifies
  twelve payloads and all five native guards, and preserves fourteen checked
  preference files. The brightness service is enabled and active locally; the
  desktop refresh loads the new menu. A physical laptop reboot is not performed
  and remains the final startup check. Nothing is committed or pushed.

Evidence: `target/097-goal/brightness-homebar-checks.json`,
`homebar-dock-native.log`, `brightness-homebar-preview-installed.json` and
`brightness-homebar-local-validation.json`.


### Thirty-eighth correction: fast RPM contents inspection

- Archives reads the existing RPM header file index instead of decompressing
  its sequential cpio payload simply to list contents. The reported ChatGPT
  package is 621,826,837 bytes with 4,185 entries and roughly 1.8 GB unpacked.
  Native listing falls from 14,820 ms to 67 ms. Actual usable Archives contents
  fall from 17,906 ms to 219 ms; the packaged runtime-guarded preview, tested as
  a normal user, takes 272 ms. These are warm local-file measurements.
- Names, sizes, permissions, symlinks and types match every member of the actual
  package; owner/group names come from the RPM header. Ghost files are omitted.
  JSON escaping preserves quotes, Unicode and shell metacharacters. The query
  is read-only, bounded and cancellable. Unsupported headers fall back to the
  native reader. Native payload extraction and double-click's extraction box
  stay in place; listing neither installs packages nor executes scriptlets.
- A native synthetic RPM checks selected extraction, hard links, symlinks,
  directories, special names and ghost entries, plus cancellation, ZIP fallback
  and malformed RPM errors. Twenty-two focused tests pass with no skips,
  including actual ZIP/7-Zip password/cancel/error dialogs and preview guards.
- Schema 2 bundles deliver the guarded read-only plugin alongside Ark, retain
  corresponding sources and guard the RPM query runtime. Older schema 1
  bundles remain accepted. Private plugin paths apply only to a validated
  Archives launch; a changed runtime uses the system application.
- Local receipt 20261106T212007.948436Z changes 7 files and verifies
  eight payloads/all five native guards. Fifteen checked preference/state files
  and the original ChatGPT RPM remain unchanged. Close and reopen Archives to
  load the update; no desktop/laptop restart, commit or push is performed.

Evidence: `target/097-goal/rpm-inspection-comparison.json`,
`rpm-inspection-guarded-user/window/result.json`,
`rpm-inspection-native-edges-verified/result.json`,
`rpm-inspection-focused-checks.json`, `rpm-inspection-preview-installed.json`
and `rpm-inspection-local-validation.json`.


### Thirty-ninth correction: leaving, pre-login brightness and cold app search

- The native logout greeter keeps a Monet transition backdrop while the normal
  KDE session shutdown closes apps. It releases its keyboard grab and lowers
  the surface so unsaved-work dialogs stay accessible. Cancellation/failure
  removes the backdrop. Restart/update/logout authorization and actions remain
  native. The theme uses a bundled Monet mark instead of depending on an icon
  theme lookup; the final native render was visually inspected.
- The separate sign-in greeter gains a brightness slider and brightness keys,
  including when a password field has focus. Its existing native event filter
  forwards only these special keys and popup Escape handling; authentication
  stays in KDE. A boot-time helper transfers only the last logical internal
  brightness into the system greeter account. Modes, HDR, scaling and external
  monitors keep their independent settings. The greeter power profile avoids
  introducing new automatic screen/suspend timers or profile brightness resets.
- Cold app search refreshes priority when native runner metadata arrives, rather
  than relying on a running-app change. Installed applications stay ahead of
  matching folders before launch. The extracted ChatGPT binary had no installed
  menu launcher: a safe persistent launcher now points to that existing binary,
  without importing its package's commands or MIME defaults. A fresh isolated
  runner finds both Zen and ChatGPT before launching either. The real cold
  All apps model also contains both applications without a running-window bus.
- Sixteen focused search/brightness checks, fourteen power-page checks,
  twenty-two support/guard checks and four final render/policy checks pass
  without skips (some suites overlap). Native mock-authentication greeter tests
  exercise brightness keys and slider. A native logout test retains the actual
  surface, permits a separate unsaved-work prompt to take focus, and removes
  it when the fake shutdown service cancels. All native checks use private
  profiles/displays/buses and cannot power off the laptop.
- Account preview receipt 20261106T222008.032587Z is the latest
  refinement in this batch. All 76 selected payloads and six native guards
  verify; fourteen checked preferences remain unchanged. The complete account
  batch starts at receipt 20261106T221057.706016Z; undo newest receipts first.
- The administrator-approved system-login preview is installed under receipt
  20261106T225609.063998Z. Fifteen receipt entries and the root-owned native
  runtime guard verify; the greeter's internal brightness is seeded to 20%.
  Unit validation caught a duplicate brightness D-Bus owner during installation;
  the corrected login target reuses the native plasma-powerdevil service, and
  both system and user unit checks pass. The correction retains the original
  undo receipt. The desktop has refreshed; no login restart or sign-out was
  performed. A physical reboot/login check remains necessary.

Evidence: `target/097-goal/session-login-search-qml-checks.json`,
`session-backdrop-qml-checks.json`, `session-login-support-checks.json`,
`session-login-final-render-checks.json`, `login-brightness-native-final/result.json`,
`session-backdrop-native-complete/result.json`, `cold-app-results-after.txt`,
`cold-all-apps-after.json`, `session-login-search-preview-installed.json`,
`login-system-preview-verified.json` and `session-login-search-local-validation.json`.

### Fortieth correction: search stalls and a covering restart/shutdown screen

- Search ranking no longer reads Kicker's URL role, which synchronously checks
  local paths and resolves symlinks. Pure match metadata classifies apps,
  executables, packages and running windows. Proxy refreshes are deferred and
  coalesced after native model changes. A 90 ms typing delay combines runner
  requests, Enter waits for the latest query, and closing the menu stops searches.
  A regression model proves ranking never requests file URLs, including a burst
  of 100 metadata updates. The real native runner accepts repeated ChatGPT,
  Zen and Settings queries without hanging in the private reproduction.
- The prior transition was behind ordinary apps, exposing the chat while they
  closed. The retained native layer-shell surface now covers them with Monet's
  progress screen. An unfiltered native window model reveals new save/inhibitor
  windows and attention requests; the cover returns when those windows close.
  A Show applications fallback appears after four seconds for prompts inside an
  existing window. Native power/update actions, save handling and cancellation
  remain KDE's; no force-close or force-restart behavior is added.
- The single additional library is Plasma's native task manager library. Its
  full package runtime and ABI are pinned alongside the existing guard. Actual
  private Wayland screenshots prove an existing fullscreen app is covered,
  revealed for a new native save prompt, and covered again afterward. Both
  restart and shutdown routes pass, with cancellation removing the surface.
  No physical laptop power/session action is used by these tests.

Evidence: `target/097-goal/search-freeze-before/run.log`,
`search-freeze-after/result.json`, `search-optimized-native/result.json`,
`session-cover-rendered/result.json`, `session-cover-shutdown-rendered/result.json`,
`session-cover-x11-native/result.json` and `session-cover-final-checks.json`.

Installed locally under account receipt 20261106T232552.998480Z: 69 selected
payloads and all six native runtime guards verify, with fourteen checked
preferences unchanged. The desktop shell was refreshed. All 41 focused checks
pass without skips. Undo instructions are in the account's TESTING-AND-UNDO.txt;
physical restart/shutdown testing remains with the user. Nothing was committed
or pushed.
