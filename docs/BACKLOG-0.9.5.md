# Monet 0.9.5 laptop backlog

The owner authorized pushing and releasing 0.9.5 on 30 October 2026. Candidate `8407f02` is published as the [v0.9.5 preview release](https://github.com/HappyHamster135/Monet/releases/tag/v0.9.5); all ten jobs in its [release workflow](https://github.com/HappyHamster135/Monet/actions/runs/41112429830), including the Setup VM, succeeded. Verified on 3 November: the tag resolves to the exact candidate and all five artifact digests match the published SHA256SUMS. Follow-up commits remain local on `codex/backlog-after-095`. The local-only notes below record earlier development stages; remaining hardware acceptance work stays open and is not implied by publication.

This backlog combines the owner's 30 October 2026 laptop feedback with the [laptop assessment](ASSESSMENT-2026-10-30.md). “Verified” means the stated check passed; it does not imply release acceptance.

Release preparation on 30 October: VERSION, the Rust workspace/lockfile and desktop package metadata now identify 0.9.5. Fresh checks completed with **1,036 Python checks passed, 12 skipped (54 modules, 1,048 discovered), and 75 Rust tests passed**. Clippy with warnings denied, translation freshness, Python/shell syntax and staged whitespace checks passed. Eight notification skips are exercised by their passing isolated parent fixture; three Phone fixtures were checked in the earlier laptop pass; PowerShell is left to Windows CI. The sealed native Task Manager bundle still matches the laptop's runtime and installed preview. Local test credentials and evidence are excluded from Git and image build contexts. Publication and complete OS/installer builds are still pending at this point; the Build workflow on main creates the preview release only after its required jobs pass. Evidence: `target/release095/publish/`.

| ID | Priority | Work | Status and acceptance |
| --- | --- | --- | --- |
| 095-01 | High | Finish encrypted boot cleanup safely | Follow-up implementation on the post-0.9.5 branch; not installed on the laptop or included in the prepared release. Verified read-only mount restoration, checked TPM/argument/slot transitions and interruption retries with disposable fixtures. Legacy cleanup without a receipt and TPM/recovery boot acceptance remain open. Test those boots before changing the laptop's keys. |
| 095-02 | High | Resume interrupted Windows preparation | Local follow-up. Fixed native lsblk discovery: PATH without NAME produced flat JSON and hid the already-created partitions. New preparations use durable GPT/filesystem receipts. Explicit recovery verifies the complete disk layout and filesystem/use probes before recording ownership. Following approved recovery and the owner's restart, the laptop reports Windows ready and has a valid Windows Boot Manager on the recorded EFI partition. Bridge is staged for Windows sign-in. The matched repair bundle is local; the installed system preparation helper and published 0.9.5 still lack these changes. First sign-in, Bridge and physical Windows/game/return acceptance remain open; see 095-56 for the subsequent switch failure. |
| 095-03 | Medium | Task Manager on right-click | Implemented locally. Task Manager appears in the desktop wallpaper, Monet menu, clock, Quick Settings and Sound context menus; Ctrl+Shift+Esc remains. Real QML action loaded and dispatched the expected helper in a private session. |
| 095-04 | Medium | Make Files easier for Windows users | First pass implemented. Tabs stay visible and breadcrumbs show the full path by default. Existing choices survive migration. Native Files preview checked; broader navigation/layout improvements remain open. |
| 095-05 | Medium | Show real free disk space in Files | Implemented in the native Files patch. Original Dolphin observer reports 0 B for Home/Downloads; patched observer matches statvfs on five laptop paths. Enable the full status bar only after the patched image bundle installs successfully. The upgrade now evolves Monet’s owned compact bar to the full bar while preserving an explicitly hidden bar. Full paired Dolphin/image build still required. |
| 095-06 | Medium | Make downloaded applications easy to reopen | First pass implemented: “Add to apps…” for a selected Linux executable creates a menu shortcut without running it. Tested with the extracted ChatGPT wrapper and hostile filename fixtures. Keep the downloaded folder in place. Folder-based discovery is now implemented (095-23). Automatic archive extraction/package installation, icons and optional launch arguments remain open. |
| 095-07 | Medium | Hide disconnected audio outputs and acknowledge selection | Implemented locally. One metadata snapshot filters the three disconnected HDMI ports while preserving unknown/available ports. Selection waits for backend feedback and reports failure. Laptop probe returns only the speaker; unit cases cover removal, failure, fallback and dummy outputs. Real external-device switching still needs hardware. |
| 095-08 | Medium | Natural scrolling by default | Implemented in image and account defaults. Real KConfig migration test confirms NaturalScroll=true for defaults while preserving a touchpad explicitly set false. Physical input check after image upgrade remains. |
| 095-09 | Medium | Mist and Smoke update open windows consistently | Implemented for KDE/Kvantum light transitions. A live Qt window passes Mist → Smoke → Mist → Smoke on the installed KDE runtime. Custom non-Monet styles remain untouched. Broader Qt Quick/GTK/Electron/Flatpak checks and same-mode glass-style changes remain open. |
| 095-10 | Medium | Reduce intermittent lag | Measured improvement: audio enumeration falls from 5 subprocesses to 2 and median 46.57 ms to 16.11 ms across ten samples each (about 65% less time). Settings polling and on-demand storage measurement now remove additional avoidable work (095-24/25); Task Manager pauses hidden sampling (095-26). General compositor/frame timing and clean-session memory profiling remain open. |
| 095-11 | Medium | Deliver existing widget edit persistence fix | Applied and verified locally. Preview installation now updates every Monet widget; the desktop leader previously retained old code. Real pointer move/resize, leaving edit mode and restarting Plasma preserve the edited rectangle. Original test-widget placement restored afterward. Layout tracking is event-driven with no repeating idle timer. |
| 095-12 | Medium | Recover temporary update network failures | Partial follow-up fix. Automatic failures get two 30-minute retries, bounded to three starts in six hours, with network and opt-out checks before every attempt. App check/install failures no longer report success; Settings rejects malformed/failed reports and handles check timeouts. Settings now shows recent automatic results and current running/retry state on demand, including the laptop’s real DNS failure. Skipped attempts remain distinct from completed updates. The Settings changes are applied locally; privileged updater/service changes remain source-only. Real image update acceptance remains open. |
| 095-13 | Low | Make doctor permission warnings accurate | Fixed and verified with a newly built local monet doctor. Unreadable rules now report “could not be checked” rather than claiming a missing rule; a found rule is described as installed without asserting authorization. |
| 095-14 | Medium | Remove misleading full system disk in Files sidebar | First-login timing fix implemented. A path unit reruns the existing idempotent places helper when KDE creates/changes its bookmark file. Native isolated Files preview hides the red system device. Live transient path-unit test verifies delayed creation and preserves explicit unhiding. |
| 095-15 | Low | Investigate NVIDIA settings and Bluetooth wizard failures | NVIDIA startup fix applied locally after the candidate: skip the settings loader when the GPU or saved settings file is absent; retain the native loader/errors otherwise. Real queries succeed, the missing-config loader returns 1, and the same loader with an empty test config returns 0. Bluetooth's exit 1 alone is not evidence of failure: KDE's wizard also returns its Accepted result as 1. Actual Bluetooth pairing and NVIDIA GUI acceptance remain open. |
| 095-16 | Medium | Strengthen automated test coverage | Added audio, downloaded-app, real QML Task Manager and live Kvantum regressions, plus a native Dolphin free-space harness. All run locally. Making required runtimes explicit in CI and adding boot/partition recovery cases remain open. |
| 095-17 | Low | Update deprecated APIs and fixture cleanup | Partial follow-up fix: VM screenshot recognition uses Pillow's new pixel API with compatibility for older images; both existing recognition tests pass with deprecations treated as errors. The GLib warning originates in installed PyGObject's own GLib compatibility exports, not a Monet signal-registration call. Dependency and Qt cleanup warnings remain open. |
| 095-18 | High | Hardware acceptance before release | Open. Encrypted NVIDIA installation, repeated boot/recovery, sleep/resume, sound recording/playback, Bluetooth pairing, external displays, backup restore, Windows game round trip, and Secure Boot trust. |
| 095-19 | Medium | A useful Task Manager Performance page | Implemented locally. Focused CPU, Memory, Graphics, Network, Storage and Sensors tabs, live history and relevant readings. Includes GPU selection, temperature, VRAM, fan RPM and disk free space. Native page verified against the laptop's sensors, NVIDIA tool and filesystem. See 095-22 for the updated layout. |
| 095-20 | Low | Make Task Manager easy to find consistently | Implemented locally. Menu/window title is Task Manager; search also matches graphics, GPU, temperature, fans, performance and network. System widget gains a right-click action and double-click shortcut, disabled during desktop editing. Native widget loads successfully. |
| 095-21 | Medium | Avoid misleading missing hardware readings | Implemented locally. Unavailable temperatures and VRAM say “Not reported”; a valid stopped fan still shows 0 RPM. System-widget dials show a dash while their sensors are unavailable. Real Qt cases cover missing telemetry, idle hardware, invalid numbers and no sensors. |
| 095-22 | Medium | Make Task Manager clearer and task oriented | Implemented locally. Three default sections: Applications, Performance and Processes; Applications opens first. Performance shows one resource at a time, with a readable graph, GPU selector and pause/resume. Page editing moves to the secondary menu. Optional devices are discovered dynamically; readers wait for metadata on cold starts. Custom page choices survive migration. Native Mist/Smoke previews and interaction tests passed. |
| 095-23 | Medium | Find applications inside extracted downloads | Implemented locally. Folder action opens an asynchronous, bounded search. Prefers desktop-declared launchers, hides helpers until requested, supports filtering, reveals the selected file and adds native applications to the menu without executing them. Identifies Windows installers and AppImages lacking execute permission. Tested on the real extracted ChatGPT folder and hostile-name/link fixtures. |
| 095-24 | Medium | Show available drive space immediately | Implemented locally. Folder action shows available/used/capacity/reserved space from the selected filesystem, with refresh and removed-drive handling. Settings shows capacity without scanning Home; the detailed usage breakdown is measured only on request. Native dialog and five-path Dolphin observer comparison passed. |
| 095-25 | Medium | Reduce unnecessary Settings background work | Implemented locally. Poll only the hardware relevant to the visible page; stop the main status timer while minimized and prevent overlapping status requests. Light needs zero subprocesses instead of 15; Sound needs two. Static pages make no repeated hardware requests. The local follow-up also pauses app volumes, phone discovery, Windows return summaries, photo progress, backup progress, clock ticks and busy animations while minimized. Detail reads coalesce; restoring refreshes them immediately. Updates no longer polls unused battery status. A clean-session whole-OS memory baseline remains open. |
| 095-26 | Medium | Avoid hidden Task Manager sampling | Implemented locally. Performance readings/history pause when hidden or minimized, and resume when shown. GPU-name requests run only on Graphics, with dropdown names fetched only while open; Sensors obeys the same visibility rule. Native regressions pass. Short whole-process measurements did not show a meaningful RAM/CPU reduction; further profiling remains open. |
| 095-27 | High | Put installed applications before folders in Menu search | Implemented locally. Applications, Suggestions and Files/settings sections partition one native KRunner query. Enter waits for the current query and prefers an installed app; source-row mapping preserves native launches and pin actions. Linux and Windows menu entries have the same priority. Native ChatGPT search and keyboard/race regressions passed. |
| 095-28 | Medium | Extend painted app-icon coverage | Implemented locally. Add to apps retains nearby packaged PNG/SVG/SVGZ icons under stable theme names; Monet's existing canvas/relief pipeline covers them. Watch native/user application directories as well as Flatpak. Added painted ChatGPT, Inkscape and KeePassXC icons and additional Chrome aliases. Existing custom icons are preserved. |
| 095-29 | Low | Paint app-supplied window icons and existing absolute-path launchers consistently | Open. Native KRunner window results can carry an application-provided bitmap, bypassing the named icon theme (visible in the preview's second ChatGPT result). Existing third-party desktop entries using absolute Icon paths also bypass named frames. Newly registered local apps now import these icons under theme names; existing entries are not rewritten. |
| 095-30 | Medium | Apply the desktop work locally for testing | Applied to this account with a reversible file installer. Search, new icons, frame watcher, Settings, Files actions and Task Manager faces are live. Reloaded Plasma without closing user applications. Verified the real bottom-left search and native windows. Image-level Dolphin/boot fixes remain separate. |
| 095-31 | Medium | Comfortable starting scale without shrinking dense panels | Implemented for new image accounts: start suitable lower-density, unscaled displays at 125%, once. Preserve dense panels, higher scales, unknown physical sizes, small displays and existing accounts. User explicitly chose native 3840×2400 at 200% on this laptop; verified unchanged. |
| 095-32 | Medium | Per-screen scale selection and honest feedback | Applied locally. Display and Accessibility offer 100/125/150/175/200% per screen, show current resolution/scale, prevent overlapping changes and verify the compositor's response. Fixed the old all-monitors setter, optimistic success and disappearing controls on mixed-scale setups. Explanation text wraps in narrow windows. |
| 095-33 | Medium | Automatically copy screenshots | Applied locally and added as a preference-preserving image default. Normal Spectacle capture copied a fresh PNG without a copy flag; clipboard contents survived capture exit. Explicit background CLI output is separate and intentionally follows its command-line options. |
| 095-34 | High | Readable typography and reliable Settings window buttons | Applied locally. Desktop reading/menu/toolbar fonts increase from 10 to 12 pt; small text from 8 to 10 pt. Settings small labels now follow the desktop font with readable minimums, stronger contrast and larger controls. Fixed missing frame artwork in preview packaging and added fallback glyphs. Native 125% and 200% checks, close/minimize/maximize and missing-artwork tests pass. Dense laptop restored to 200%. |
| 095-35 | Medium | System totals above applications and processes | Applied locally. CPU, memory percentage and used/total capacity, graphics, network transfer rates and disk read/write rates appear above native tables. Additive Monet pages preserve KDE's originals and native sorting/search/end-task actions. Uses system sensors rather than summing process memory. |
| 095-36 | Medium | Live Performance tab readings and developer details | Applied locally. CPU/memory/graphics utilisation and network/disk rates remain visible on resource tabs. Details adds per-logical-processor usage, frequency, user/system/wait and temperature; network interfaces/addresses/totals; drives/filesystems with activity/capacity/free space. CPU order is numeric; regex selectors are excluded as fake hardware. Missing telemetry stays explicit. Readers stop while minimized; detail rows sample only in the viewport. |
| 095-37 | Medium | Deploy desktop menu and restore an existing Task Manager | Applied locally. Preview installer now includes the wallpaper action. Actual desktop right-click menu verified; selecting Task Manager restores a minimized instance. Handles app IDs with and without .desktop and retains the temporary model while Wayland activation completes. |
| 095-38 | Low | Follow external display changes safely | Applied locally. Display/Accessibility refresh after scale or logical-screen-geometry changes without periodic polling. Native external 200% → 125% → 200% verified. Invalid screen enumeration results become an empty list instead of producing QML filter/find errors. |
| 095-39 | Low | Broader hardware diagnostics and app identity | Hardware diagnostics implemented and applied (095-40). Extracted-app identity remains open: KDE may still show full paths for apps started before a desktop shortcut/cgroup was registered. Do not restart the user's active apps to rename a process group. |
| 095-40 | Medium | System Details alongside the main Task Manager pages | Applied locally. A fourth sidebar page beside Applications, Performance and Processes owns hardware overview, CPU cores, network interfaces, drives/filesystems and Sensors. Performance now focuses on its five resource graphs and live tab values. Overview includes CPU model/physical cores/logical processors/cache/topology/maximum clock, OS/kernel/firmware, usable RAM/swap, GPU IDs/drivers, network drivers and storage model/firmware/capacity. Identification is on demand and unprivileged. |
| 095-41 | Medium | Actually suspend hidden monitoring on Wayland | Applied locally. Observe KDE's compositor window state because external minimization does not reliably change QWindow visibility. One event-driven model per QML engine, no polling subprocess. Native Applications/Processes content stops sampling while minimized, preserving actions and selection; totals, Performance and System Details share the same activity check. Hardware rows are virtualized and sensor subscriptions follow the viewport. Native minimize/restore model states verified. |
| 095-42 | High | Preserve KDE and personal pages during image installation | Fixed before any image installation. The page install previously used the destructive tree helper; it now installs only monet-*.page additively. Regression verifies native Applications/Processes and a personal page survive. User-level preview installation was already additive. |
| 095-43 | Medium | Reduce desktop background work and memory | Applied locally. Replace each widget’s 500 ms layout poll with lifecycle/geometry signals and coalesced saves. One appearance watcher replaces four per glass widget. Wallpaper unloads its unused full-resolution image between fades; asynchronous transitions still wait for the image. Native measurements and scope are recorded below. Clean-login, longer battery/frame-timing and broader hardware profiling remain open. |
| 095-44 | High | Weather place search rejects Stockholm | Applied locally. Desktop and bottom-right popup use one cancellable search component, retain the active request, ignore stale replies, validate results, time out after 10 seconds and distinguish a failed request from a genuinely empty search. Retry is available. Stockholm checked successfully in both live desktop and panel search; final verification recorded below. |
| 095-45 | Medium | Follow local sunset for Mist / Smoke | Applied locally. Offline solar position uses the shared weather location, with the time-zone city as fallback. Automatic changes follow sunrise/sunset; explicit Mist, Smoke and custom palettes remain respected. Minute timer runs a cheap comparison and only reapplies on a transition; no resident helper or network lookup. |
| 095-46 | Medium | More lightweight desktop widgets | Applied locally. Storage shows account-available capacity on the home filesystem and opens Files. Network shows native download/upload rates and connection totals. Both support Monet's shared layout and glass, and appear in Add Widgets with Mist/Smoke previews. No recurring folder scans; no network history buffer. |
| 095-47 | Medium | Task Manager sidebar and custom page deletion | Applied locally as a matched native build. Hamburger collapses/expands on left click. Right-click empty sidebar opens the full menu, including confirmed Remove Current Page for custom pages. Navigation leaves the deleted controller first and repairs its start-page preference. Built-in Monet pages are protected from direct deletion. Native Edit or Remove Pages remains available. |
| 095-48 | Medium | Newly created Task Manager pages fail to save | Fixed during native testing. KDE 6.7.5 Main.qml called nonexistent savePage(); use its actual save() API. Rebuild patch is anchored against the installed source RPM and fails closed on incompatible source/runtime changes. No replacement process/sensor backend. |
| 095-49 | Low | Refresh races and glass startup errors | Fixed locally. System Details and Storage give each explicit refresh a unique executable source, avoiding immediate replay of the previous cached result. Double refreshes still coalesce. Shared glass gradient binds to a stable ShapePath ID instead of a temporarily null parent. Weather search restores keyboard focus when its panel popup activates. |
| 095-50 | Medium | Stop Sound's closed-panel command polling | Applied locally on the separate follow-up branch after the 0.9.5 candidate was prepared; not part of candidate `8407f02`. Native audio notifications update the level, mute state and default output. The old two-second wpctl polling is retained only as a fallback while the native interface is unavailable. Closed panels no longer repeatedly fetch the full sound snapshot. Fresh request identifiers and coalescing avoid stale replies and overlapping reads. The standalone Sound view also has a readable minimum width. |
| 095-51 | Low | Review native tray heading warnings | Historic reload logs place the observed leftInset warnings around Plasma shutdown. No recurrence appeared in the latest 30-minute journal sample. The new Monet audio components report no such errors. A visible layout defect or ongoing idle work has not been established; native-style investigation remains open. |
| 095-52 | High | Bind Windows deployment to recorded partition identities | Follow-up implementation, 22 native Windows tests and full-image VM acceptance pass. Real DISM/BCDBoot, failed-boot and completed retries, payload locks, fallback/user-file preservation and elevated first-logon handoff are verified. The fixture selects the original Windows EFI loader through private OVMF variables. Consumer editions, other storage drivers, physical power loss, Secure Boot and the real Bridge/game/return-to-Monet round trip remain open. Nothing was installed on the laptop or added to candidate `8407f02`. |
| 095-53 | Medium | Avoid repeated process scans for already allowed listeners | Applied locally after the 0.9.5 candidate. The network-permission watcher checks socket metadata first and resolves processes only for a possible new listener belonging to this account; unknown UID metadata remains eligible. It skips app identity reads for allowed/privileged ports. Ten alternating laptop samples reduce the median poll from 162.36 ms to 19.75 ms. New/closed listeners pass a private native network fixture, and 18 focused security/preview checks pass. This is polling wall time, not a measured whole-OS RAM or battery improvement. |
| 095-54 | Low | Update CI actions and make runner migration explicit | Prepared locally. Checkout 7.0.1, upload-artifact 7.0.2 and download-artifact 8.0.2 use verified full commit pins and Node 24. Linux jobs explicitly use Ubuntu 24.04. Missing release payloads fail their upload step; optional job/error handling stays unchanged. actionlint and a parsed comparison of permissions, gates, commands and artifact contracts pass. Hosted Linux/Windows/reusable-image execution remains pending a future push; the running 0.9.5 workflow is unchanged. |
| 095-55 | Medium | Keep the Windows account distinct from its computer name | Fixed in source after the candidate. A sanitized account name matching MONET-GAMES now keeps its name while the computer becomes MONET-PLAY. A native VM exposed failed administrator-group assignment when both names matched. The corrected full fixture verifies Users/Administrators membership and the elevated first-logon task. Name/case/sanitization regressions pass. Not installed on this laptop. |
| 095-56 | High | Restart into Windows from the desktop | Applied locally. The privileged helper's systemctl check treated the initiating desktop account as another logged-in user. EFI work remains privileged; the restart now runs through runuser as the verified initiating account, retaining inhibitor and other-user checks. Native dry-run succeeds and a real shutdown blocker is still rejected. The departure dialog exposes bounded plain-text helper errors. Installed-helper cancellation leaves EFI unchanged. A real restart and Windows return are still unverified. |
| 095-57 | Medium | Remove stale empty space in the dock | Applied locally. Replace the content snapshot's fixed minimum/maximum width with a centered dynamic range constrained by the two other Monet islands. Native opening/closing of a temporary app changes the dock from 569 to 637 and back to 569 logical pixels. No repeating work was added; the former extra configuration call and 200 ms sleep were removed. |
| 095-58 | Low | Make the game launch destination explicit | Applied locally. Games uses “Play in Monet” or “Play on Windows” on the detail button and context menu. The laptop's Counter-Strike 2 entry routes to Monet, consistent with Valve's native Linux support. Actual gameplay and Windows-only game handoff remain unverified. |




Evidence and development previews belong under `target/release095/` (ignored by Git). Source changes, laptop previews, and release acceptance are recorded separately below.

## Local follow-up after preparing the release candidate

The 0.9.5 candidate is committed as `8407f02` on `work/0.9.5-laptop-polish`. After the initial device sign-in expired, the owner completed authentication and the candidate was pushed to main on 30 October. Further work stays on `codex/backlog-after-095`, so it cannot silently alter that candidate.

Encrypted first-boot cleanup (095-01) now records a private, fsynced receipt before changing anything: disk UUID, exact bootstrap slot metadata fingerprint, original key argument and mount mode, with no secret key material. Cleanup verifies TPM-only unlock, checks a separate bound recovery/passphrase slot, removes and verifies the next boot's key argument, then retires and verifies only the recorded bootstrap slot. Existing TPM enrollments are preserved. A reused slot, mismatched disk, unknown bootstrap slot, failed command or incomplete verification stops cleanup without claiming success. A temporary writable `/boot` is checked and restored to its original read-only state; pending receipts trigger retries even after the bootstrap file is gone. The recovery-relearn service waits for cleanup to finish.

**Verification:** 77 focused seal/setup checks passed, including 20 new failure/retry, receipt, service-condition and native fixture tests. The native LUKS2 test creates only a temporary regular file, substitutes a separate test key for TPM hardware, proves the retired bootstrap key no longer unlocks and proves the recovery key still unlocks before and after retry. The mount test uses a private user/mount namespace with its own tmpfs and fstab; it performs actual remounts and verifies restoration after success and failure. Final seal-only rerun: 24 passed. Rendered systemd units, Python syntax and whitespace checks pass. CI now installs cryptsetup for this fixture. Evidence: `target/backlog-after-095/seal-tests.log` and `seal-final.log`.

This boot helper is **source-only**, not installed or executed against this laptop's encrypted disk. Actual TPM/PCR and recovery boots, rpm-ostree deployment behavior, and full image acceptance remain open. An older partially completed cleanup with no receipt deliberately reports that recovery verification is required instead of guessing which slot to delete. SSD key-file overwriting alone is not claimed as secure erasure; confirmed LUKS slot retirement is essential.

Windows partition recovery (095-02) now creates a private, fsynced receipt before appending GPT entries. It binds the GPT disk ID, original partition layout, logical sector size, intended partition GUIDs/geometry and filesystem transitions. A partial append adds only the missing planned partition; late kernel nodes use six bounded discovery attempts without appending again. Each format is preceded by fresh GPT/kernel identity, mount/use and direct filesystem checks. Successful format results are verified and their filesystem UUIDs saved; a retry preserves already-created filesystems, including a formatter that finished writing before reporting failure. The helper takes an exclusive process lock, preserves unrelated partitions, rejects completed Windows/reused filesystems and no longer forces NTFS formatting over the tool's mounted-device guard.

**Verification:** 18 new recovery/probe tests plus the existing installer suite ran **48 checks: 47 passed, one skipped because PowerShell is unavailable**. Real disposable GPT images prove intended GUIDs and the original partition survive a partial append. Separate temporary NTFS/FAT32 image files prove direct filesystem probing and recovery after a missing post-format receipt without invoking the formatter again. Other cases simulate partial/failed operations, disk/partition changes, stale nodes, mounted devices, conflicting/unreadable probes and concurrent setup. CI explicitly installs the GPT/NTFS/FAT tools. Evidence: `target/backlog-after-095/windows-partition-tests.log`. Python syntax, translation freshness and whitespace checks passed.

This Windows helper remains **source-only**. The laptop's old empty-looking partitions have no receipt; a name or absent filesystem signature is not enough evidence to adopt them automatically. Their recovery remains open. The separate Windows deployment script still needs 095-52 before this flow can be accepted end to end; no real disk formatting, Windows staging, boot-entry changes or reboot was performed.

Windows deployment identity (095-52) now has a separate read-only console checker in `crates/monet-setup-check`, plus a Python manifest producer that reads the preparation receipt, live GPT/kernel mapping and filesystem IDs. Selection requires matching Windows, Setup and shared EFI partitions on the recorded physical disk. It rejects changed serials/geometry/types, duplicate identities/letters, read-only media and malformed records. Hidden EFI partitions are read at their GPT offset without mounting; unrelated EFI partitions are not probed this way. The checker adds no background desktop process. Its cross-built executable is about 374 KiB and imports system console/runtime libraries, without the Bridge's GUI stack.

**Verification:** all **85 Rust workspace tests** pass, including an actual Python-to-Rust manifest handoff and disposable FAT32 images made with both 512-byte and 4096-byte sectors. The focused Python partition/installer suite ran **51 checks: 50 passed and one PowerShell skip**. Linux and Windows-target Clippy pass with warnings denied, along with Python syntax, translation freshness and whitespace checks. CI now runs the new crate's build, native SDK-buffer tests and lint on Windows, and installs native storage fixture tools before Linux Rust tests. Evidence: `target/backlog-after-095/winpe-*.log` and `windows-handoff-tests.log`.

The initial foundation was then connected to the source packaging and deployment flow. Linux now embeds the checker, script and exact job manifest inside `boot.wim`, extracts the manifest again to verify it, and publishes its private staging receipt last. The boot launcher calls only this RAM-image copy, never a script found on another drive. The package and OS builds include the checker; a missing checker fails before partition preparation or replacement of an existing package output.

The explicit WinPE-only `--deploy` operation verifies SHA-256 and sizes, keeps inputs open without write/delete sharing, rejects unlisted split images, and rechecks native identities before mutations. It has **no format operation**. A target must be empty or have the matching job/hash checkpoint. `applying` retries the same WIM; `applied` retries configuration without running DISM again; `complete` does not rewrite Windows. EFI assignment selects the verified disk/partition and checks its new drive letter, with no automatic ESP fallback. The original EFI fallback loader is saved and restored. Linux resumes only the same staging receipt, payload and NTFS checkpoint, without erasing setup files. Monet's Windows detection now distinguishes a partial WIM from a completed installation.

**Integration verification:** **95 Rust workspace tests** pass, including eight transaction failure/preservation cases and a Python/Rust full-job hash check. The Windows executable cross-builds (about 544 KiB), and both Linux and Windows-target Clippy pass with warnings denied. A real disposable two-image WIM verifies embedded bytes and removal of an old embedded script; a real NTFS file image verifies checkpoint reading without mounting or reformatting. The full Python run completed all modules with one stale clock-helper source assertion failing; that assertion was replaced by an actual unprivileged helper call, and the entire **400-test look module passed on rerun**. All ten final focused staging/clock checks pass. The full run logs 19 optional skips: isolated notification/Phone fixtures, PowerShell, JavaScript-only geometry checks and opt-in systemd retry scenarios. Earlier isolated notification and update-service evidence remains recorded above. Translation freshness, shell/Python syntax, Rust formatting for the new crate and whitespace checks pass. Evidence: `target/backlog-after-095/deployment-*.log`.

This integration is **source-only and outside candidate `8407f02`**. Actual WinPE driver/storage behavior, Windows sharing and rename durability, DISM retries, boot-loader restoration and the complete installation/recovery round trip remain unverified. Wine 11.20 stalled during initial environment setup before running the Windows tests; the native SDK-buffer tests compile but still need Windows execution. Cross-compilation and simulated backends do not establish WinPE acceptance. Legacy laptop partitions still have no ownership receipt and are not adopted. No laptop formatting, Windows staging, boot-entry changes or reboot was performed. Temporary compiler containers were removed after the build. See the checker README for its contract and limits.

Update recovery (095-12) now returns failure when Flatpak cannot check or install updates, rather than presenting zero updates or successful completion. Runtime cleanup is skipped after an app-update failure. Settings validates the helper's exit code and complete result and returns a readable error on timeout. Its single helper file was installed with reversible receipt `~/.local/state/monet/desktop-preview/20261030T180223.138722Z/receipt.json`; an injected timeout in that installed helper returned the expected error without starting an update.

The proposed automatic service uses systemd's existing restart scheduling, with at most two retries 30 minutes apart in a six-hour start-limit window. Each attempt checks the opt-out file and NetworkManager's known/guessed unmetered state; missing/unknown/error responses skip automatic work. Native tests exposed that an automatic restart does not recheck the initial unit condition, so opt-out is explicitly checked again in `ExecCondition`. Four temporary user-service scenarios prove recovery, bounded persistent failure, cancellation after switching to metered networking, and cancellation after turning updates off. All temporary services were removed. Seventeen focused Python checks and **76 Rust tests**, including a real CLI fixture with fake updater commands in a private user namespace, passed; Clippy with warnings denied, rendered unit validation, translation freshness and whitespace checks passed. Evidence: `target/backlog-after-095/update-*.log`. The privileged updater and service are not installed locally; no system or app update was started.

**Automatic update history follow-up:** Settings → Updates now shows the ten most recent available automatic attempts, with local dates and Completed / Didn't finish / Skipped results. It reads at most 40 matching manager events from the existing journal, rather than starting a logger, background timer or updater. Reads are coalesced and happen on entering Updates, explicitly refreshing, or finishing a manual check/install. The separate current-service snapshot can show a running update or a scheduled retry. Missing/unreadable/malformed history is reported as unavailable, never as success. Older results depend on normal journal retention; this is not a complete update audit or manual-update history.

The parser uses [systemd's message IDs](https://github.com/systemd/systemd/blob/main/src/systemd/sd-messages.h) and [invocation fields](https://www.freedesktop.org/software/systemd/man/latest/systemd.journal-fields.html), with PID 1 and the exact unit matched at the query. Native disposable user-service tests exposed that a skipped ExecCondition emits both UNIT_SKIPPED and a successful start-job message; the final parser preserves the skip. Success, failure, retry recovery, duplicate events, bounded history, invalid data and unreadable journals are covered. The page also no longer says updates happen only on request while automatic updates are enabled.

All **27 focused Python/Qt checks pass**, including five native systemd scenarios. The ten existing update checks and the final stricter QML response test pass separately; translation freshness, syntax and whitespace checks pass. Mist, Smoke and a 760-pixel-wide window were rendered with the native Qt runtime. The installed helper returns the laptop's real failed attempt at 10:30:38 CET. Five whole-helper read-only calls had a median wall time of 118.7 ms; no whole-OS RAM or CPU saving is claimed for this feature. Settings and its helper were applied through receipt `~/.local/state/monet/desktop-preview/20261030T202544.803444Z/receipt.json`, and Settings was reopened at Updates without runtime QML errors. Evidence: `target/backlog-after-095/update-history-*`. These follow-up changes remain separate from candidate `8407f02`; no real update was invoked.


Sound now follows [KDE's native default-device notifications](https://github.com/KDE/plasma-pa/blob/master/src/preferreddevice.cpp) behind an optional loader. A missing native module or audio-service disconnect falls back to wpctl; reconnection stops polling again. This removes the scheduled 30 volume-reader invocations per minute per healthy closed widget, plus its periodic full sound snapshots. It adds no separate background daemon. This is a command-count reduction, not a measured whole-OS RAM/CPU or battery-life improvement.

Four native acceptance cases use an isolated PipeWire server with virtual outputs, private configuration and a private D-Bus session. They cover immediate volume/mute changes, a changed/removed default output, missing-module fallback, fresh/coalesced reads, failure/retry, late fallback replies, service disconnect/reconnect and the complete rendered Sound widget. The final layout rerun also verifies a minimum usable width; 15 focused desktop/audio regressions, translation freshness, syntax and whitespace checks passed. The apparent full-widget startup failure was a test logging issue: setting `QT_FORCE_STDERR_LOGGING=1` made Qt's successful state changes observable. The fixture now cleans up its whole private process group.

The three Sound QML files were installed with a reversible receipt under `~/.local/state/monet/desktop-preview/20261030T174019.656534Z/receipt.json`, then Plasma was reloaded. Its native audio module is loaded, desktop widget geometry is unchanged, and the real output volume is unchanged. Evidence is under `target/backlog-after-095/audio/`. No push or release has happened yet.

## NVIDIA startup follow-up

The real GPU query succeeds, while `nvidia-settings --load-config-only` exits 1
without a diagnostic when `~/.nvidia-settings-rc` is absent. An empty disposable
config makes the same native command return 0, without applying attributes.
[NVIDIA's config reader](https://github.com/NVIDIA/nvidia-settings/blob/main/src/config-file.c)
returns false for an absent file, and its load-only command propagates that as
failure. This explains the fresh account's failed autostart; it is not a failed
graphics driver.

A systemd user drop-in now requires both `/dev/nvidia0` and the saved settings
file before launching the existing loader. Present settings and real loader
failures remain visible. The account-local preview installed one reversible
file, receipt `~/.local/state/monet/desktop-preview/20261030T195829.524191Z/receipt.json`.
After reload, the native unit reports `ConditionResult=no`, `ActiveState=inactive`,
`Result=success`; no NVIDIA process was launched by that start. The old explained
failure state was cleared. This avoids one unnecessary login process and a false
failure, not a measured whole-OS memory reduction. Shell syntax, the existing
preview-preservation regression and whitespace checks pass. Probe evidence is in
`target/backlog-after-095/nvidia-*-probe*.json`. No GPU settings file was created
in the real home, and no driver or display configuration changed.

## Native Windows follow-up verification

The later native WinPE run closes part of the acceptance gap described above.
Microsoft's amd64 ADK WinPE 10.0.26100.1 was booted under KVM/OVMF with networking
disabled and only disposable file-backed disks. No laptop partitions, keys or
boot entries were passed through or changed. All **22 Windows tests** pass,
including actual Windows sharing violations when another handle tries to write,
rename or delete a verified setup payload.

The VM identified the recorded GPT/NTFS/FAT32 volumes and rejected a changed
filesystem serial. It exposed a real EFI discovery defect: DiskPart's assigned
letter did not appear in volume-GUID enumeration. Read-only DOS volume queries
now check the full extent, GPT identity and filesystem before accepting that
letter. Conflicting observations remain an error. Linux fixture tests and
Linux/Windows-target Clippy with warnings denied pass; the release executable
cross-builds successfully.

[tools/test-winpe.py](../tools/test-winpe.py) reproduces the test using externally
supplied ADK files and a new scratch directory. Native DISM applies a deliberately
non-bootable tiny WIM, then BCDBoot is expected to fail. The `applied` checkpoint,
original EFI fallback and user files survive. A second attempt performs no
second DISM application, and preserves a modified loader file. The automated
runner verifies all of these results from the resulting FAT32/NTFS image files.
Evidence: `target/backlog-after-095/winpe-vm/acceptance/`.

This is not a successful full Windows installation, Secure Boot or power-loss
test. Those remain open. The helper and this fix remain source-only on the local
follow-up branch, outside the 0.9.5 release candidate.

## Full Windows deployment and first-logon acceptance

The new [full-image fixture](../tools/test-windows-install.py) passes from a fresh
file-backed disk through native DISM, successful BCDBoot, completed retry and
Windows first logon. Microsoft’s [evaluation media](https://www.microsoft.com/en-us/evalcenter/download-windows-11-enterprise)
was checked against its published SHA-256:
`bc3f24086ebadc94489066b5ad78089e2cf5c3491e90e790bb81a2b199c10e38`.
No Microsoft image is committed or redistributed.

The guest reports Windows 11 Enterprise Evaluation build **26300**, account
`Monet-Games`, computer `MONET-PLAY`, the correct job and `complete` checkpoint,
and an elevated administrator token. All four production first-logon arguments
arrive. Windows' setup log confirms membership in Users and Administrators. The
fixture script records this evidence and shuts the guest down; it substitutes
for actual Bridge, Game Profile and Steam installation, which remain untested.
Networking is disabled, and only newly created ordinary files are VM disks.

The existing EFI fallback and a user sentinel survive application, retry and
first boot. The retry performs no second DISM application. OVMF's private
variable file selects Microsoft's explicit loader on the target's original ESP;
no host firmware variables or laptop partitions are accessed. This proves the
Windows boot/handoff portion, not Monet's complete BootNext/game/return flow,
Secure Boot, consumer editions, other controllers or physical power loss.

The first prototype reached the desktop but its account and computer names
matched case-insensitively. Windows logged failed group assignments, and the
first-logon task did not run. The production preparation helper now avoids this
collision too: it preserves the account and chooses `MONET-PLAY` if the sanitized
account name matches the usual `MONET-GAMES` computer name. The fresh final VM
exercises this exact case. The helper remains source-only, outside 0.9.5.

Harness defects found during the work were corrected before acceptance: sparse
extraction must not mix buffered reads with descriptor-level seeks, standalone
NTFS image files need explicit partition geometry, the original ESP must be used
instead of a copied BCD USB, and wrapper paths must remain absolute after changing
working directories. Regression tests cover sparse offsets/holes, kernel-copy
fallback and refusing to overwrite prior evidence. A paused disposable QEMU
instance verifies that timeout cleanup also stops a guest behind a killed
container wrapper and retains a screenshot.

Verification: **34 focused installer/harness tests passed, one PowerShell-host
check skipped**; the actual first-logon PowerShell payload ran successfully in
Windows. Translation freshness, Python/shell syntax, preview preservation and
whitespace checks pass. Successful evidence is under
`target/backlog-after-095/windows-full-vm/acceptance-identity/`, with the complete
CLI run in `full-tool-identity.log`. Earlier failed/cancelled fixture logs are
retained separately and are not reported as successful runs.

## Desktop polling follow-up

A 15-second live sample found browser media and ChatGPT work active; it is not a
clean-login idle baseline. The network-permission service itself was roughly
39 MiB RSS, while its periodic `ss -p` subprocess scans were avoidable. A simple
socket-only probe still encountered systemd-resolved's LLMNR listener, so the
final probe uses socket UID metadata to distinguish another account's sockets.
Missing metadata remains eligible for the full owner lookup. The firewall rules,
permission prompts and five-second detection interval are unchanged.

The final complete-helper measurement alternated ten old/new polls on this
laptop: median **162.359 ms → 19.747 ms**. A private user/network namespace with
a real bound TCP socket verifies allowed-port suppression, detection of a newly
opened listener and removal after close. Eighteen focused tests, translation
freshness and whitespace checks pass. The preview installer now includes the
user service so it runs the tested local helper. Its unit/helper receipt is
`20261030T192336.399605Z`; the final helper receipt is
`20261030T192502.840023Z`, both under `~/.local/state/monet/desktop-preview/`.
The service was restarted and is active. Evidence is in
`target/backlog-after-095/listening-*.log` and `listening-final.json`.

## Earlier local desktop checks (before release preparation)

Changes are local and uncommitted on `work/0.9.5-laptop-polish`. VERSION is still 0.9.4. Nothing was pushed, tagged, published or installed as a replacement OS. Preview windows used separate configuration/data folders, were closed afterward, and the temporary test service/container was removed. No encryption keys, disk partitions or boot settings were changed.

| Check | Result |
| --- | --- |
| Full Python suite | 48 modules, 994 discovered tests, 982 passed and 12 skips; no failures. Eight skipped notification cases run inside the passing isolated subprocess wrapper. The three Phone cases pass separately in their required fixture. PowerShell syntax remains unavailable. After the final watcher change, all 400 look-module tests passed again. |
| Rust | 75 workspace tests passed; Clippy passed with warnings denied; local monet binary built and doctor checked on the laptop. |
| Native Task Manager / theme | Both new KDE/Qt tests passed; fake executable records only the expected Task Manager launch, and the same open widget changes palette #f3f1ec → #242321 and back. |
| Native disk space | Compiled Dolphin 26.08.1 observer/cache against Qt 6.11.2 and KDE Frameworks 6.31. Actual KIO results match statvfs for `/var/home/jonte`, `/home/jonte`, Downloads, `/` and `/tmp`. Unpatched source fails four of those five paths. |
| Profile preferences | Explicit Files tab/path/status choices and per-device scrolling survive migration. New default is present. |
| Sidebar startup | Systemd unit syntax verified. Temporary live path unit repairs a file created after it starts, keeps explicit unhiding, and is removed afterward. Separate Files screenshot confirms the nameless system device is hidden. |
| Downloaded app entry | ChatGPT wrapper is recognized and a generated menu entry passes desktop-file-validate, without launching it or changing MIME handlers. KDE service-menu files use KDE's Type=Service extension, outside that validator's Application schema. |
| Source maintenance | Changed shell/Python syntax, translation catalog check and git diff whitespace check passed. Existing translations remain; new untranslated labels fall back to English. |

Evidence is in `target/release095/`: `python-tests.log`, `rust-tests.log`, `clippy.log`, `native-ui-tests.log`, `theme-native.log`, `audio-benchmark.json`, `native/files-space-laptop.log`, `native/files-space-original-laptop.log`, `preferences-test.log`, `final-look-tests.log`, `place-watch.log`, `files-after.png`, `doctor.log`, and `phone-tests.log`. `files-space-preview.png` captures the original incorrect 0 B reading. Free space changed during build/test downloads; equality to the live filesystem measurement is the acceptance criterion, not a fixed GiB value.

The disk-space harness is in `tests/native/files-space`. Build with CMake, setting `DOLPHIN_SOURCE` to the prepared original or patched Dolphin source tree, then run `files-space` on local paths on the Atomic host. The full executable/private-library pair, image/ISO, reboot and real desktop upgrade have not been rebuilt or accepted here. New menu entries and defaults will reach the installed desktop when the local changes are installed in a tested image.

Technical references: Dolphin 26.08.1 uses [Solid storage-device lookup](https://raw.githubusercontent.com/KDE/dolphin/v26.08.1/src/statusbar/mountpointobservercache.cpp) for its cache; this was the failing mapping in the native comparison. [Plasma integration 6.7.5](https://raw.githubusercontent.com/KDE/plasma-integration/v6.7.5/qt6/src/platformtheme/khintssettings.cpp) skips style recreation when the style name stays the same; [Kvantum exposes both kvantum and kvantum-dark](https://raw.githubusercontent.com/tsujan/Kvantum/master/Kvantum/style/KvantumPlugin.cpp), which the transition now uses after its writes finish.

## Task Manager and second laptop pass

The installed KDE System Monitor 6.7.5 already provides Overview, Applications, History and Processes. Monet now adds an independently installed `monet-performance.page` and a small `org.monet.hardware` sensor face. It uses KDE's existing sensor service, with no shell polling or separate hardware daemon. The Performance page loads on demand; it does not add an autostart monitor. Its titles and hardware labels participate in Monet's translation catalogs, with English fallback for untranslated additions.

The native preview displayed live CPU/GPU/RAM/network/disk graphs and hardware readings. In a contemporaneous comparison, KDE and `nvidia-smi` reported the RTX A500 at 51°C, 0% usage and 40 MiB of 4096 MiB VRAM. `/var/home` had about 579 GiB available, matching the disk display. These are observed samples, not fixed expected readings. The CPU and ThinkPad fan also updated. The integrated GPU's backend returns zero temperature and zero dedicated-memory capacity; the new face correctly marks those as unavailable. A zero fan reading alone cannot establish a missing sensor, so it remains a legitimate displayed value.

The initial six-panel layout was checked at 800×600 and 1050×780; it has since been replaced by the focused layout described below. The full System widget loaded in `plasmawindowed` with its installed shared components. The window-title translation was verified using the real session locale; the tool runner's C locale intentionally suppresses gettext translations. Preview setup errors caused by missing copied dependencies were corrected and are not recorded as OS bugs.

Verification for this pass:

- Full Python suite: 48 modules, 995 tests, 980 passed and 15 skipped, no failures. Three JavaScript geometry cases then passed with the bundled Node runtime. Eight notification skips are also exercised inside the passing isolated subprocess wrapper. Three Phone fixture cases were already verified in the first pass; PowerShell remains unavailable.
- All three native KDE/Qt regressions passed, including the new hardware-reading cases. Profile migration preserves an explicit custom page order, start page and hidden pages. All 400 look-module checks passed, including the new sensor-face QML scan.
- Shell syntax, translation freshness and whitespace checks passed. The later widget edit-mode guard was included in the native widget preview and the suite. No Rust source changed in this pass; the earlier 75-test/Clippy result still applies.
- Read-only system checks found no new kernel errors during this pass. The same encryption/update and historical NVIDIA/Bluetooth app failures remain tracked above. This does not establish boot, suspend or Bluetooth acceptance.

Evidence is under `target/release095/polish2/`: `task-manager-final.png`, `task-manager-small.png`, `system-widget.png`, `hardware-comparison.json`, `python-tests.log`, `test-summary.json`, `native-final-tests.log`, `javascript-tests.log`, and `native-profile-tests.log` (the initial fixture conversion error there is superseded by the passing final native run). The final native app logs are empty. No installed image was replaced and no push, tag or release was made.


## Task-oriented Task Manager revision

The default navigation is now **Applications → Performance → Processes**, opening on Applications so stopping a troublesome app is immediate. Overview and History remain available through page management. Existing custom page order, start page and visibility settings are preserved. Page editing is in the secondary menu rather than the main toolbar.

Performance uses a new native `org.monet.performance` face with six resource tabs. It shows one 60-second graph with a compact set of readings underneath. Below 620 logical pixels of content width, the tabs become a resource dropdown so no section is clipped. Graphics has a device selector; Pause freezes the selected graph and readings, and Resume starts a fresh history. The Sensors tab lists supported temperatures and fan speeds. The implementation uses the existing KDE statistics service and samples only the selected resource. Missing telemetry says “Not reported”; unsupported optional devices do not produce a broken-page banner.

Laptop testing caught and fixed a cold-start metadata race: the readers now wait for the sensor catalog before subscribing. A fresh statistics-service start was verified with live CPU usage, frequency, temperature, 20 logical processors and one socket. KDE's coreCount sensor counts logical processors, so it is labelled accordingly; this laptop has 14 physical cores. Optional device discovery also handles removal of the selected GPU. The integrated GPU still exposes limited telemetry and a generic name through the installed backend.

Verification:

- Full Python regression run: **48 modules, 996 tests, 984 passed, 12 skipped, no failures**, with the bundled Node runtime. The notification/Phone fixture qualifications and unavailable PowerShell check above still apply.
- After the device-discovery and cold-start fixes, **31 targeted native, QML and profile-migration tests passed**. The native interaction fixture exercises all six tabs, GPU keyboard selection, pause/resume, device removal, no-GPU state and narrow navigation. Its Basic control style avoids a Python/desktop-style loader deadlock; visual checks use the actual native KDE application.
- Native Mist and Smoke previews confirm the restrained Monet palette, clear sections and readable metrics. NVIDIA readings and unsupported integrated-GPU readings were both checked. An 800×600 Mist preview verifies the resource dropdown and two-column metrics. The Smoke client fits the graphics view at 900×680; the desktop titlebar follows the real user's unchanged theme.
- Translation freshness, shell syntax and whitespace checks pass. No Rust source changed in this revision.

Evidence is under `target/release095/task-manager-redesign/`: `python-tests.log`, `test-summary.json`, `final-targeted-tests.log`, `task-manager-final.png`, `task-manager-small-final.png`, `performance-smoke-final.png`, `applications.png`, `final-native.log` and `small-final.log`. Earlier failed fixture attempts are superseded by the final passing targeted run. The isolated preview is not an installed OS update. VERSION remains 0.9.4; no push, tag or release was made.


## Files and resource-usage pass

Files gains two folder context actions: **Find applications…** and **Drive space…**. They open short-lived native Qt windows and add no resident service or index. The application search runs in a separate process, limits depth/entries/time, refuses directory symlink traversal and file links outside the selected tree, and treats downloaded desktop entries only as naming hints. It never imports their commands or file associations. Native shortcuts use the existing literal-path registration; Windows installers are revealed in Files for the existing Run in Monet action. Archives still need extracting first and application folders must remain in place.

On this laptop, scanning the extracted ChatGPT package visited 372 entries in **12.19 ms** and selected `usr/bin/chatgpt`, the packaged wrapper for `usr/lib/chatgpt/codex-launcher`. Bundled helper executables remain available behind a checkbox. The depth limit is disclosed; this is not a claim to have exhaustively searched every nested dependency.

The drive dialog reports the actual filesystem's available capacity without enumerating files. A sample for Downloads was **578.8 GiB available of 608.0 GiB**, with used and reserved space shown separately. This is the writable Monet filesystem, not the physical disk's capacity or its Windows partitions. Re-running the compiled patched Dolphin observer matched live `statvfs` on Home through both path aliases, Downloads, `/` and `/tmp`. The paired Dolphin/image rebuild is still required for the installed status bar. A newly found migration bug was fixed: the old Monet-owned Small bar now upgrades to FullWidth when the patched-image marker exists, while a user-selected Disabled bar remains unchanged.

Storage settings now returns capacity immediately and uses **Measure folder sizes** for the recursive breakdown. It prevents duplicate scans and shows a retryable error for failed results. Trash and Downloads no longer falsely say “Empty” before their sizes have been measured. This reduces unnecessary disk reads each time Storage is opened.

Settings status requests are scoped to the current page and coalesced while one is pending. They stop while minimized and refresh on return. Five read-only samples on the laptop measured the old full status request at **83.91 ms / 15 subprocesses**, Light at **0.01 ms / zero subprocesses**, and Sound at **14.92 ms / two subprocesses**. These measure helper execution on a warm local system, not total application launch latency. Static pages need no status request.

Task Manager's Performance face now releases sensor subscriptions when hidden/minimized, including the Sensors tab and GPU names. Restoring the window resumes sampling; an unfocused but visible window keeps updating. Eight-second whole-process samples measured **97.4 → 98.1 MiB PSS** active and **4.87 → 5.24% of one CPU core**; minimized CPU was **0.62%** in both runs. This is within run-to-run variation, not evidence of a whole-process memory or CPU improvement. The subscription-state regressions establish the removed work; the native KDE shell still has other monitoring overhead. No system services or desktop features were disabled to manufacture a smaller footprint.

**Full regression suite: 50 modules, 1,010 tests, 998 passed, 12 skipped, no failures.** The eight notification skips are covered by their passing subprocess wrapper; the three Phone fixture cases were verified earlier; PowerShell remains unavailable. The final native/Settings UI checks and changed-source syntax, translation freshness and whitespace checks passed. No Rust source changed in this pass.

The native Storage page preview uses the live capacity snapshot with stubbed unrelated sections for visual inspection.

Native Mist/Smoke Files previews, shortcut creation in an isolated home, file reveal without execution, removed-drive handling, minimized/restored monitor sampling, scoped/coalesced Settings requests and on-demand storage measurement were exercised. Preview logs were empty. Source changes remain uncommitted on `work/0.9.5-laptop-polish`; VERSION is still 0.9.4. No installed OS replacement, push, tag or release occurred.

Evidence is in `target/release095/files-and-performance/`: `find-applications.png`, `find-applications-smoke.png`, `drive-space.png`, `storage-settings.png`, `files-tests.log`, `focused-tests.log`, `settings-ui-tests.log`, `space-upgrade.log`, `native-disk-space.log`, `helper-measurements.json`, `monitor-before.json`, `monitor-after.json`, `monitor-before.log`, `monitor-after.log`, `python-tests.log` and `test-summary.json`.


## Applications-first search and painted icons

Menu search now puts **Applications** first, followed by **Suggestions** and **Files, settings and more**. Two lightweight filter models partition the existing native query; there is no additional search process, executable scan or resident index. Relevance order within each section and native launching/pinning are preserved. Pressing Enter while a query is running waits for current results, avoiding an old application or a folder winning a timing race. Changing the search or closing the menu cancels a pending launch. Arrow navigation crosses all sections and scrolls the selected result into view.

The actual laptop's extracted ChatGPT package had no registered menu shortcut. Added `/var/home/jonte/.local/share/applications/monet-chatgpt.desktop` pointing directly to the package's `usr/bin/chatgpt` wrapper, and a painted `chatgpt.svg` in the user icon theme. The shortcut passes desktop-file-validate and KDE's native services runner returns `applications:monet-chatgpt.desktop`. It is a Linux executable, so the visible name is **ChatGPT**, without a fabricated `.exe` extension. Its downloaded folder must remain in place. No MIME handlers or application commands from an untrusted desktop file were imported.

Add to apps now searches nearby standard package locations for the selected application's icon, with bounded file reads and decompression. Matching desktop metadata is used only to identify the icon; commands are never imported or executed. PNG and SVG/SVGZ icons are copied under a stable theme name, where the existing Monet canvas and paint-relief overlay can cover them. An existing painted theme icon takes precedence. Broken icons fall back to the generic executable icon, and links outside the package are rejected. Native/user application directories now trigger the existing frame service alongside Flatpak directories. No new resident service or shader was added.

New generated paintings cover **ChatGPT, Inkscape and KeePassXC**, with their common icon names; Chrome stable/beta/unstable names reuse its existing painting. The generator remains the source of these SVG assets. This does not establish coverage for every third-party application; the native window-icon/absolute-path exceptions discovered during the preview are tracked in 095-29.

Verification: **50 modules, 1,018 tests, 1,006 passed, 12 skipped, no failures**. The skip qualifications from the preceding pass still apply. The final **32 targeted tests passed**, including the extra compressed-icon corruption check, app/folder ordering, Windows app entries, source-row launches, keyboard section transitions, early Enter, query cancellation, safe icon import and preservation of custom icons. Python/shell syntax, translation freshness, whitespace checks and the substituted systemd units pass. No Rust source changed in this pass.

A native `plasmawindowed` preview uses the real KDE app/file/window results with an inert suggestions helper and isolated configuration. Both Mist and Smoke show ChatGPT first, above the same-name folder and running windows. The real native services runner was also checked separately without launching the app. Preview windows were closed afterward. Only the ChatGPT shortcut and icon were applied to the user's desktop; the broader launcher/frame changes remain local source awaiting installation. VERSION remains 0.9.4; no push, tag, release or image replacement occurred.

Evidence: `target/release095/launcher-icons/` contains `menu-chatgpt.png`, `menu-chatgpt-smoke.png`, `painted-icons.png`, `native-runner.log`, `focused-tests.log`, `python-tests.log`, `test-summary.json` and `units/`. Native preview runs produced no QML warnings. The service source contains installation placeholders; validation uses the substituted copies in `units/`.

The app/file distinction follows KDE's [RunnerMatchesModel implementation](https://raw.githubusercontent.com/KDE/plasma-workspace/master/applets/kicker/runnermatchesmodel.cpp), which exposes `favoriteId` for the services runner. Query handling also accounts for [RunnerModel retaining rows during an in-flight query](https://raw.githubusercontent.com/KDE/plasma-workspace/master/applets/kicker/runnermodel.cpp); behavior was verified against the installed model and native UI.


## Local desktop deployment and display sizing

At the user's request the tested desktop work is now installed in this account. `tools/install-desktop-preview.py` installs user-level overrides, never replacing the Atomic OS image. It routes user-facing helpers to `~/.local/libexec/monet-desktop-preview`, while privileged/image-bound helpers continue to use `/usr/libexec`. The user theme receives the new paintings/aliases, the frame watcher covers native apps, and the menu, clock, Quick Settings, Sound and System widgets use the updated code. Settings and the Files context actions use the current helpers; the Task Manager faces/page and its translation overlay are present. Previously absent Task Manager navigation preferences were set through the existing preference-preserving profile helper.

The installer first ran in an isolated home: install, helper routing, syntax and restoration of an existing personal icon passed. Every changed preview file has a backup and digest receipt under `/var/home/jonte/.local/state/monet/desktop-preview/`. The paths are recorded in `target/release095/local-desktop/receipts.json`. To undo preview files, run `python3 tools/install-desktop-preview.py --restore RECEIPT` for the receipts in reverse order; it preserves files edited since installation. Then reload user systemd, restart the frame path unit and Plasma, and reopen Settings/Task Manager. Task Manager's three preference defaults are separately tracked by the profile helper; the file installer does not restore preferences. No release version or boot/system partition was changed.

The running Plasma panel was reloaded, and a real keyboard search for “chatgpt” verified Applications first with the painted icon, followed by file/window results. The temporary input helper was stopped afterward. The frame service completed successfully in 220 ms of CPU time with a 34.9 MiB peak for that one-shot run; its path watcher remains active. This is not a whole-desktop memory benchmark. The live Task Manager performance page showed CPU activity, frequency and temperature. Files' new actions are installed, but the paired Dolphin binary/free-space patch still requires its separate image build.

The laptop reports a 344×215 mm panel at 3840×2400, about 284 pixels per inch, with scale 200%. The user explicitly chose to retain that sharp, readable setting and make 125% the starting default on lower-density screens. Verified the live compositor still reports 3840×2400 at 200%; resolution was never lowered. Display and Accessibility now show a per-screen selector, current resolution and size, a high-density hint, and wrapping explanatory text. Changes affect only the selected screen, wait for actual backend feedback, and display failures rather than highlighting an unconfirmed choice. An older one-argument request is accepted only when there is one screen, avoiding accidental changes to a mixed-display setup.

For future images, `/etc/skel/.config/monet/display-defaults-pending` marks only newly created accounts. On their first usable display snapshot, the session helper changes an unscaled lower-density screen to 125% only if its physical dimensions are known and at least 800 logical pixels remain on each axis. Dense screens, higher existing scales, unknown EDID dimensions and small displays retain the compositor's selection. The marker is consumed once; upgrades, subsequent logins and user choices are not reset. This image/account-creation policy is implemented and fixture-tested, not installed into this laptop's `/etc/skel` by the user-only preview. Its existing account needs no first-login migration.

Verification: **51 modules, 1,025 tests, 1,013 passed, 12 skipped, no failures**. Previous skip qualifications still apply. Tests cover per-monitor changes, failed/ignored/disconnected outputs, malicious/ambiguous requests, density metadata, one-time defaults and preference preservation. Native QML tests cover pending/failed/successful UI feedback and narrow layouts. Earlier harness attempts combined process-global Qt test modules and aborted; the final repository runner correctly isolates each module. The initial layout-fixture and component-encapsulation failures were fixed before the final passing run. A missing relative Settings component path in the first local installer was caught by opening the actual app and fixed by sharing the installed Games components. Native Settings now opens without QML warnings.

Final Python/shell syntax, translation freshness and whitespace checks passed. No Rust source changed in this pass. Source and preview remain local and uncommitted; VERSION remains 0.9.4. No push, tag, publish or release occurred.

Evidence is under `target/release095/local-desktop/`: `live-chatgpt-search.png`, `display-settings.png`, `live-task-manager.png`, `scale-confirmation.json`, `display-after.json`, `python-tests.log`, `test-summary.json`, `final-search-ui.log`, `live-settings.log`, installation receipts and `receipts.json`. Display settings is left open for user testing; the test Task Manager window is closed.

KDE's [output configuration implementation](https://raw.githubusercontent.com/KDE/kwin/master/src/outputconfigurationstore.cpp) also derives starting scale from physical size and pixel dimensions. Monet's new first-account policy only adjusts eligible unscaled lower-density screens; it does not relabel 200% as 125% or reduce native resolution.


## Screenshot, readability and Task Manager polish — 30 October

All changes in 095-33 through 095-38 are installed as account-level overrides. The preview now includes the wallpaper package, shared frame components and their relative button artwork. The frame has 40×32 logical-pixel hit targets and visible fallback symbols if an asset cannot load. Settings no longer uses tiny fixed text for body labels: default text is larger, follows the desktop font preference, and keeps stronger secondary-label contrast. Native 3840×2400 at 125% was tested temporarily and restored to the user's chosen 200%; the percentages retain their actual meaning and native resolution was preserved.

Task Manager's Applications and Processes pages show actual overall system readings above the native tables. The new pages are additive (`monet-applications.page` and `monet-processes.page`), preserving the packaged KDE pages and existing user configurations. The Performance tab bar has live values; network and storage use transfer rates because throughput is not a utilisation percentage. Details separates logical processors, network interfaces and drives/filesystems. A virtualized list limits detail subscriptions to visible rows; leaving Details destroys its readers, and minimizing releases sampling. No new resident daemon or per-second subprocess was introduced. A broader whole-desktop memory/performance claim is still not established.

Native testing caught and fixed missing totals-face package metadata, duplicate tab labels under KDE's desktop style, lexical CPU ordering and synthetic regex selectors masquerading as hardware. The Task Manager action now recognizes KDE's `.desktop` app IDs and keeps its temporary task model alive for asynchronous Wayland activation; a real minimized window was restored from the desktop menu. Display refresh also follows logical screen geometry: Wayland rounds screen DPR, so fractional scaling alone did not always emit a different DPR.

Spectacle's `General/clipboardGroup=PostScreenshotCopyImage` is now the default and is enabled for this account. The normal desktop D-Bus capture path replaced the previous clipboard image with a fresh 2800×1900 PNG, readable after Spectacle exited. Background `spectacle -b -o …` used for evidence deliberately follows CLI flags and does not exercise that preference. This distinction follows the installed behavior and KDE's [capture export implementation](https://raw.githubusercontent.com/KDE/spectacle/master/src/SpectacleCore.cpp) and [settings schema](https://raw.githubusercontent.com/KDE/spectacle/master/src/Gui/SettingsDialog/spectacle.kcfg).

Verification: final full run **51 modules, 1,026 tests, 1,014 passed, 12 skipped, no failures**. Follow-up native QML tests passed after the final screen-geometry and device-selector corrections. Checks cover missing-artwork close controls, numeric core order, phantom-device rejection, keyboard navigation, device selection, pause and minimized sampling. The prior skip qualifications remain. Translation freshness, shell syntax and whitespace checks pass. No version bump, commit, push, tag, release or OS image replacement was made.

Evidence and backup receipts: `target/release095/desktop-polish/` contains Settings at 125%, Applications totals, Performance, CPU/network/drive details, the desktop menu, restored Task Manager, clipboard validation and preference backup values. File backups remain under `~/.local/state/monet/desktop-preview/`; restore receipts in reverse order using the preview installer's `--restore` option. Preferences are separately journaled by `monet-profile`. The full test log/summary are copied into this evidence folder after completion. Remaining image builds and hardware acceptance stay open in the table above.


## System Details and background resource use — 30 October

System Details is now a **top-level sidebar page**, not a resource tab inside Performance. The hardware overview is selectable text for debugging; CPU cores, network interfaces, drives/filesystems and Sensors occupy the same page's section selector. Performance retains CPU, Memory, Graphics, Network and Storage, including live values without selecting a resource.

The new `monet-system-info` helper reads bounded procfs/sysfs files and the installed PCI names database. It does not invoke probes, require administrator access, open GPU devices, or spawn further processes. It exits after one snapshot; there is no identification timer or resident helper. Refresh requests are coalesced, malformed responses show a retryable error and retain the last successful snapshot. Missing topology and separate driver versions remain explicit. Memory is labeled **usable physical memory** rather than claiming DIMM capacity/type/speed that this interface does not provide.

Native checks matched the laptop's i7-1370P, **14 physical cores / 20 logical processors**, 5.20 GHz reported maximum, 544 KiB L1 data, 704 KiB L1 instruction, 11.5 MiB L2 and 24 MiB L3. Shared caches are deduplicated using their sharing lists. Both Intel and NVIDIA identities/drivers and the KIOXIA drive's firmware/capacity were verified. The topology display retains Linux CPU/core/socket IDs for debugging; these are different from the friendly 1-based logical-processor labels. Identification follows the kernel's [CPU topology interface](https://cdn.kernel.org/doc/html/latest/admin-guide/cputopology.html). Five warm snapshots took a median **31.6 ms**; the short-lived Python measurement process peaked at **24.9 MiB RSS**. This is a helper measurement, not Task Manager's total memory.

The real desktop test found two reasons earlier visibility guards were incomplete: KDE reparents face content separately from its face object, and compositor-initiated minimization did not change the Qt window's reported visibility. The final activity helper observes the displayed item and a shared, event-driven KDE TasksModel. It pauses only when all matching Task Manager windows are minimized; missing metadata keeps monitoring available, and unfocused visible windows continue sampling. The application declares the standard window-management interface and uses a canonical executable path so KWin can match the declaration. No compositor permission checks were disabled. Existing launch arguments, metadata and other declared interfaces are preserved. This uses KDE's [minimized task role](https://api.kde.org/legacy/plasma/plasma-workspace/html/classTaskManager_1_1AbstractTasksModel.html) and [per-application interface lookup](https://raw.githubusercontent.com/KDE/kwin/Plasma/6.4/src/utils/serviceutils.h).

Applications and Processes use thin wrappers around KDE's installed tables. Search, sorting, process actions and column configuration remain native; the content's effective visibility now disables the underlying model while minimized. A temporary native diagnostic observed model enabled **false** on minimization and **true** on restoration. The temporary diagnostic is removed from installed/source files. Sensors uses a virtualized list, with a 500-sensor fixture proving fewer than 50 active visible-row readers, none while minimized, and no remaining readers after returning to the overview. A tab-bar sizing loop discovered by the QML checks was also removed.

Evidence and reversible installation receipts are under `target/release095/system-details/`. Early `after-cold.json` is explicitly invalid because an import URL prevented the table from loading; it must not be used as performance evidence. Final resource measurements and checks are recorded below. Source and all changes remain local; VERSION remains 0.9.4.

The controlled comparison used fresh launches through the same KDE launcher, the same Applications page and 10-second samples per state after settling. CPU percentages below are fractions of **one CPU core**, not percentages of this laptop's entire 20-thread CPU. PSS apportions shared memory; the shared sensor daemon and other desktop applications are outside these process-only figures.

| Task Manager state | Before CPU | After CPU | Before PSS | After PSS |
| --- | ---: | ---: | ---: | ---: |
| Visible | 3.6% | 3.1% | 118.7 MiB | 121.5 MiB |
| Minimized | 1.7% | 0.2% | 118.6 MiB | 121.7 MiB |
| Restored | 3.0% | 3.0% | 118.5 MiB | 121.6 MiB |

This supports a reduction in minimized CPU work, not a RAM reduction: the extra window-state model adds roughly 3 MiB in this short sample. Visible CPU differences are too small to establish a speedup. Whole-desktop RAM/CPU and battery measurements remain open. Files: `controlled-before.json`, `controlled-after.json`; these supersede the earlier cold/warm comparisons.

Final verification: **52 modules, 1,036 tests, 1,024 passed, 12 skipped, no failures**. The existing skip qualifications remain. A later native check caught lexical temperature-row ordering (Core 11 before Core 3); natural numeric ordering was added, installed and visually verified. All **15 focused native/helper tests** passed after that correction. Shell syntax, translation freshness, desktop-entry validation and whitespace checks pass. Native Applications and Processes tables, five Performance tabs, hardware overview/driver details, CPU cores and Sensors were checked. No QML errors appeared in the final running monitor's journal. The display remains 3840×2400 at 200%.

The page installer now preserves native KDE and personal pages in future images; its additive behavior is regression-tested without changing the running OS image. DIMM slot/type/rated-speed information and broader device acceptance are not claimed; unsupported values remain explicit. The remaining whole-desktop profiling, extracted-app identity and image-build work remain open in the backlog. Task Manager is left on System Details for user testing. The temporary virtual-input helper was stopped. No push, tag, release, version change or OS-image replacement occurred.


## Desktop efficiency and widget persistence — 30 October

The user reported that moving/resizing desktop widgets snapped them back. The account preview had updated only Menu, Clock, Quick Settings, Sound and System; Placard, Weather, Calendar and other desktop packages still loaded the old shared LayoutGuard. The lowest-ID desktop widget controls layout restoration, so a fixed panel copy could not fix the desktop. The preview installer now includes **all Monet widget packages**, with a regression ensuring every package receives the same guard and its shared dependencies. The image installer includes the new appearance helper too.

LayoutGuard now discovers its container when representations are created/reparented, elects one coordinator and watches actual geometry/container changes. Dragging coalesces writes; clicking Done captures the new arrangement before screen-area restoration. Startup and scale changes retain the existing saved-layout protections. All repeating 500 ms widget timers were removed. Panel representations without a desktop container stay idle, rather than retrying discovery indefinitely. Native QML tests cover late reparenting, movement without global edit mode, no idle timers, removing the coordinator, move/resize/Done/restart and smaller-screen restoration.

The real laptop test moved Placard from **(80, 64), 320×240** to **(240, 144), 416×304** using pointer dragging and a resize handle. The exact edited rectangle survived leaving edit mode and a Plasma restart. Other widgets retained their rectangles. The test widget was then restored to its original rectangle; the complete widget geometry list matches the pre-test list. Desktop edit mode is off and temporary virtual input is removed. No user application was closed.

Glass appearance previously used four FolderListModels per card, each owning a worker thread. A single filtered watcher now handles glass off/lite/frosted/matte, including same-count renames. It watches only while that card draws its own background. The native regression checks create/rename/delete and disabling/re-enabling the watcher. Appearance and blur levels are preserved.

The wallpaper previously kept both the current and next full-resolution paintings decoded even between transitions and for a pinned light. It now keeps only the displayed image in those states; transitions still use two images, wait for asynchronous loading and reuse the already-loaded next image when swapping. Native image tests cover steady state, partial fades, completion, pinned lights and manual jumps. Native resolution is retained; this does not lower wallpaper quality or turn off desktop effects.

Measurements use 30-second process snapshots with user applications left open. Fresh launches use the same Plasma service and four-second initial settle; PSS apportions shared memory. Baseline `before.json` is a long-running session and is not the comparison baseline, because a restart itself frees retained allocations. The fresh comparison is:

| Desktop shell state | PSS | RSS | Threads | CPU, % of one core |
| --- | ---: | ---: | ---: | ---: |
| Before, fresh | 349.95 MiB | 510.54 MiB | 65 | 1.30% |
| Widget changes, fresh | 339.96 MiB | 500.38 MiB | 57 | 0.93% |
| Plus wallpaper change, fresh | 303.96 MiB | 464.27 MiB | 57 | 1.03% |

The measured shell memory reduction is about **46 MiB (13%)**, with eight fewer threads. The last sample includes the larger test widget; subsequent cleanup restored its original size. Short CPU samples do not establish a whole-OS speedup. Overall CPU remained around 3–4% of the 20-thread laptop while the browser media process and active Codex session dominated work; those applications were left intact. File indexing, audio, accessibility, Bluetooth, security notifications and other OS features were not disabled. A clean-login baseline, longer idle/battery measurements and additional hardware remain open.

Evidence, screenshots, measurement JSON, test logs and reversible preview receipts are under `target/release095/desktop-efficiency/`; effective prior widget files and layout backups are in its `before-files/` folder. Native Plasma logs were checked after deployment with no Monet QML errors. VERSION remains 0.9.4; no push, tag, release or image replacement occurred.

Final verification: **52 modules, 1,039 tests, 1,027 passed, 12 skipped, no failures**. The earlier skip qualifications remain. Translation freshness, shell syntax and whitespace checks passed. The final Plasma journal contains no Monet QML messages. The original widget geometry list is restored exactly, desktop edit mode is off, no test input daemon remains, and the laptop retains 3840×2400 at 200%. All changes are local and uncommitted.


## 30 October: weather, sunset, widgets and native sidebar

Applied account-local previews with receipts under `target/release095/weather-sidebar/`.
The existing account and native desktop remain in place; VERSION is 0.9.4 and
nothing was committed, pushed, tagged or released.

- **Weather:** the owner confirmed the failing query was `stockholm`. Both live
  surfaces now return Stockholm, Stockholm County, Sweden as the first match.
  Selected that existing place again and preserved the shared location/units.
  Before editing, the service and a standalone Qt request both returned results;
  the original transient failure was not reproduced in isolation. The old code
  conflated request/parse failures with an empty search. Native Qt regression
  tests cover Unicode names, empty responses, HTTP/malformed responses, retries,
  stale callbacks, immediate cancellation and timeouts.
- **Light:** the laptop now uses `hours smoke` after Stockholm's sunset. The
  timer runs the local offline helper; a no-change tick measured about **34 ms
  CPU and 8 MiB peak memory**, then exits. These are timer costs, not a whole-OS
  benchmark. Tests cover Stockholm autumn sunrise/sunset, polar day/night,
  leap-year handling through the formula, time zones/date line and invalid
  locations. Manual light choices remain unchanged by the timer. Solar position
  uses [NOAA's published equations](https://gml.noaa.gov/grad/solcalc/solareqns.PDF);
  the calculation is approximate and the timer checks once per minute.
- **Widgets:** native live Storage and Network cards were added temporarily,
  checked against real capacity/sensors, and removed. Storage reports the space
  available to this account on its home filesystem, excluding reserved space.
  Its `statvfs` helper runs once per minute or on explicit refresh. Network uses
  four shared native sensors at a two-second UI update limit; the two rows stay
  instantiated as values change. Both packages and gallery previews are installed.
- **Task Manager:** compiled the matching Fedora **6.7.5-1.fc44 source RPM** in
  a disposable container. Runtime package versions (including Qt/KDE and native
  monitor libraries) and original binary hash matched the laptop. Only the app
  executable was installed locally; its native backend libraries are unchanged.
  Its source archive and build/patch instructions accompany the reversible
  preview. The image build now has the same guarded source-build stage; an image
  build/release has **not** been performed. A runtime upgrade requires rebuilding
  or restoring this local native preview.
- **Native sidebar checks:** left-click collapse/expand, empty-area right-click,
  built-in direct-delete protection, custom-page creation/save, confirmation and
  deletion of the selected page all passed. A test page was written immediately
  after the save API fix. Deletion returned to Applications, removed the page
  from the model/order and disk, and did not recreate it on exit. No personal
  pages were deleted. Final app launch uses Monet's normal search/desktop entry.
- **Additional fixes:** System Details avoids replaying stale executable-source
  results when refreshing quickly. The glass rim no longer reads a null parent
  during construction; System widget sensors reject missing numeric values while
  their metadata arrives. Weather popup activation restores search-field focus.

Verification: full traversal ran **54 modules / 1,048 tests / 12 skips**. It found
one race in the installer timeout test: its already-terminated child disappeared
between `/proc` existence and content checks. The test now accepts an already
reaped child and still rejects a live child; all **53 setup tests passed** on
rerun. Final **32 weather/daylight/widget/native desktop regression tests passed**;
additional gallery/icon/scope checks passed in the earlier 35-test targeted run.
Translation freshness, Python/shell syntax and whitespace checks passed. The
latest native journal has no Monet QML errors. Screenshots and logs retain both
failures and successful retests rather than rewriting failed-run evidence.

Original desktop widget IDs, positions and sizes match the saved before-state
exactly. Temporary pages, widgets, input helper and build container were removed;
the laptop remains at **3840×2400, 200%**. Long-duration idle/battery measurements
and broader OS optimizations remain open under 095-43.

## Settings detail polling follow-up

A native comparison found that Sound Settings still launched app-volume helpers while minimized even though the main status timer was already paused. The same visibility-only condition affected Phone and the Windows return summary; photo and backup progress and Date & Time also kept ticking. These reads and visual timers now follow the actual window visibility, with immediate refresh on restore. Photo progress is read only on Light & Wallpaper. App-volume, photo and backup reads coalesce so a slow reply cannot create overlapping workers. Backup and painting operations themselves continue normally.

Updates no longer requests an unused battery snapshot every four seconds. A real Qt regression exposed a page-switch ordering issue: onPageChanged ran before the derived statusPage binding updated, causing a stray status request on a static page. The read guard now checks the new page directly.

**Verification:** 37 focused Settings/return-summary checks pass, plus all three Phone window checks in a private HOME/XDG/D-Bus fixture. The tests cover minimization through all five detail refresh periods, immediate restore, coalescing, off-page photo work and the page-switch race. Translation freshness and whitespace checks pass. The native Sound fixture uses the installed helper and the real audio session: over 6.5 seconds minimized, the previous QML launched two app-volume helpers and consumed 215.2 ms of child CPU time; the new QML launched none and consumed zero child CPU time. Both refreshed on restore. This measures those helpers only, not a whole-OS CPU or RAM reduction.

The final QML is installed with reversible receipt `~/.local/state/monet/desktop-preview/20261030T203244.313271Z/receipt.json`, and Settings was reopened successfully. No privileged helper or real update was started. Evidence: `target/backlog-after-095/settings-detail-polling-final.log`, `settings-phone-0y2l7ttw/`, `settings-minimized-before.json`, `settings-minimized-after.json` and `settings-final-native.log`. The first probe's in-memory QML loader timed out before creating a window; the passing comparison loads separate temporary QML files. This follow-up remains local, separate from the 0.9.5 candidate.

### External Wayland minimization

The follow-up also checks compositor-initiated minimization, as the earlier Task Manager work required. A native probe shows that KWin leaves QWindow.visibility at Windowed but changes isExposed from true to false. Settings now listens to the window's Expose/visibility events through a small shared Python QObject. A coalesced zero-delay callback updates the QML activity property after the event; there is no repeating timer, subprocess or additional task/window model. Standalone QML fixtures retain their visibility fallback.

With the real Wayland session and installed audio helper, external minimization previously left four probes running in 6.5 seconds (two status and two app-volume reads), consuming 465.9 ms child CPU. The final implementation performed zero probes/zero child CPU and refreshed status and app volumes within half a second of restore. This does not measure total application/OS CPU or RAM. All ten Settings feedback checks pass with the actual exposure QObject, in addition to the earlier 37 + 3 checks. The final Settings launcher, shared helper and QML are applied with receipt `~/.local/state/monet/desktop-preview/20261030T203923.920617Z/receipt.json`. Evidence: `wayland-window-state.json`, `settings-external-minimized-{before,after}.json`, `settings-exposure-tests.log` and `settings-exposure-native.log` under `target/backlog-after-095/`. Temporary probe windows and KWin scripts were closed/unloaded.

The historical unpatched Task Manager crash at 13:55:33 CET occurred on close in PageManager::saveAll → SensorFaceController::forceSaveOnDestroy → KConfigGroup::config. Its session log reports a missing totals-face CompactRepresentation and a null PageContents value. That missing package component was already corrected in 095-35; it is present in the current source and preview. The record alone does not prove causation or establish a crash in the later matched native build. Its evidence is retained as `native-monitor-old-crash.txt`; no speculative crash patch or failure-state clearing was performed.

## Windows preparation recovery — 3 November 2026

The laptop's original 29 October preparation created p4/p5, then reported that the new partitions did not appear. Its 31 October retries reported insufficient free disk space. Native reproduction found that `lsblk -J -b -o PATH,...` produces flat output unless `--tree` is explicit; reading the first item's children therefore hid every partition. The corrected query requests the tree and TYPE, selects the exact disk root, and returns its direct partition children rather than the encrypted mapper.

The disk already reserves **334.85 GiB for Windows and 8 GiB for Setup**. The local repair bundle binds their exact GPT GUIDs and geometry, plus all three original partitions, in a reviewed plan. Explicit recovery verifies that both targets exist, are unmounted and have no holders, then checks direct blkid and read-only wipefs signatures. Only an explicitly invoked recovery can create the ownership receipt; labels or a missing filesystem alone do not trigger automatic adoption. Subsequent preparation uses the existing interruption-safe receipt and verified WinPE handoff.

**Verification:** 73 focused installer/partition/WinPE tests ran: 72 passed, one host PowerShell skip. Coverage includes the native lsblk contract, the real laptop's read-only enumeration, exact legacy reuse, repeat recovery, changed/missing/foreign/in-use partitions, signatures/read failures and the read-only CLI. The privileged read-only inspection passed on the laptop; its GPT metadata dump was saved. No laptop filesystems were formatted, no partitions resized and no boot entry changed. The repair bundle is prepared locally, with a verified published 0.9.5 Bridge executable and the locally tested native setup checker. Applying the disk repair awaits the owner's confirmation; the installed system helper remains unchanged. Evidence and the exact repair command: `target/windows-recovery-2026-11-03/README.md`.

A download preflight then reproduced Microsoft rejecting the helper's automatic ISO request. The official browser flow successfully offered consumer Windows in the laptop's configured English International language. Preparation now obtains the ISO before formatting or adopting legacy partitions, and missing/empty media stops early. Tests cover blocked requests, interrupted downloads and missing/empty local ISOs with zero partition writes or recovery receipt. The official browser download and SHA-256 verification are tracked in the recovery evidence directory.

The consumer ISO download completed into Downloads and matches Microsoft's published SHA-256 (`7e3f373bd3c2321b5d5125dfcf718dfbf1a0abc50a267118669951890df98a5d`). A read-only ISO mount and disposable single-edition export confirm the selected Windows 11 Home x86_64 image fits the existing 8 GiB Setup partition with about 291 MiB remaining for the small Monet payload and filesystem/split overhead (256 MiB minimum checked). The ISO was unmounted and the temporary export removed. Media and the exact local repair command are ready; permission to initialize the two reserved partitions is still pending. No later changes were pushed or released.

### Approved laptop recovery completed

The owner explicitly approved initializing the two reserved partitions and preparing the next boot. The matched local helper completed successfully on 3 November: p4 is NTFS/MONETWIN, p5 is FAT32/MONETSETUP, and the verified Windows 11 Home media is staged with en-GB language, sv-SE keyboard and Stockholm time zone. Root-owned partition and staging receipts are durable under /var/lib/monet. Status is pending with 100% progress.

Independent read-only validation passed: all **21 staged files** and the boot-image hash match the receipt; the GPT dump is byte-for-byte unchanged; the existing EFI, boot and encrypted Monet filesystems retain their types and UUIDs. BootNext 0002 selects Monet Windows Setup on p5's exact GPT GUID and EFI loader. The original boot order is preserved, with Setup appended last. All temporary ISO/Setup mounts were unmounted. The laptop was not restarted.

The owner can save work and restart normally to begin Windows installation. Physical deployment, first boot and return to Monet remain unverified until that happens. The original system helper was not replaced; the matched private recovery bundle is retained for a verified retry. No follow-up changes were pushed or released. Final evidence: `target/windows-recovery-2026-11-03/verified-recovery.json`, `approved-recovery.log`, `verification.log` and before/after GPT and EFI records.

## Windows switch, dock spacing and game destination — 3 November 2026

After the owner's restart, the setup watcher reports Windows ready and Bridge staged for the next Windows sign-in. Boot0003 is a valid Windows Boot Manager on the recorded shared EFI partition. The older foreign Windows entry is ignored. The failed switch attempts armed the correct entry, then cancelled when systemctl rejected the reboot: running its explicit inhibitor check as root caused it to count the initiating desktop user as another logged-in account.

The CLI now resolves the non-root caller supplied by pkexec before closing apps or changing EFI. It performs privileged boot work as before, then uses runuser to request the firmware restart as that desktop account, with its groups and the existing shutdown-inhibitor/other-user checks. It does not bypass inhibitors or force a restart. The original root command fails in a native dry-run; the corrected account command succeeds. A real temporary shutdown inhibitor still prevents it. The departure dialog now shows bounded plain-text helper errors instead of discarding the cause behind a generic failure. An installed-helper cancellation test returned its ready handshake, accepted cancellation and left the complete EFI listing unchanged.

The dock's blank slot came from pinning both width limits to one snapshot of its contents. The helper now sets a centered dynamic range bounded by the other Monet islands, in one configuration call without the former 200 ms sleep. A native temporary window changes the dock from **569 → 637 → 569 logical pixels** as it opens and closes. The window and probe scripts were removed; dodge-windows hiding was restored. No user apps were closed and no persistent polling was added.

Games now labels its main and context-menu play actions with the destination. The real library routes Counter-Strike 2 to Monet, matching [Valve's Linux requirements](https://store.steampowered.com/app/730/CounterStrike_2/). [FACEIT's separate anti-cheat requires Windows](https://support.faceit.com/hc/en-us/articles/9394666828188-What-is-FACEIT-Anti-cheat-and-how-does-it-work). No game or actual restart was launched during these checks; physical Windows sign-in, Bridge and return-to-Monet acceptance remain open.

**Local deployment:** the root-owned, manifest-verified CLI and departure helper are under `/usr/local/lib/monet-switch/20261103/`. The account's Windows shortcut, Games helper and quick helper route to that CLI. The five user-file changes have reversible receipt `~/.local/state/monet/desktop-preview/20261103T104605.446576Z/receipt.json`. The immutable system files remain unchanged. The versioned preview links the existing system preparation helper; it is not a replacement for the separate matched recovery bundle. Preserve these local BINDIR/launcher overrides when applying another generic desktop preview, whose default points back to `/usr/bin`. The unfinished Store observer work was neither deployed nor included in this follow-up.

**Verification:** 25 Monet unit tests and one integration test pass; Clippy with warnings denied and the static release build pass. All 50 departure/document checks, 12 focused dock/routing/departure checks and ten Games/screen checks pass (these groups overlap). The first Games run found an outdated Settings test requiring two valid calls to be adjacent; it now checks both calls independently and passes without changing Settings. Translation freshness and whitespace checks pass. Existing catalog entries and translations are preserved; only the two new helper messages were added. Native measurements, original failures, final retests, installation manifest and cancellation evidence are retained under `target/windows-switch-2026-11-03/`. No new push, tag or release was made.
