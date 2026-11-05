# Monet 0.9.6 release qualification

**RC13 includes Electron native integration and per-app Flatpak accessibility
support in both graphics images. Image, fresh-install, upgrade and rollback
checks pass locally. Physical hardware qualification remains deferred.**

Qualified on 5 November 2026 from the checkout based on
`e1fc593512763ba590fa108fb120657642272a54`. The owner subsequently authorized
committing and publishing this tested set as the 0.9.6 preview. The
[release page](https://github.com/HappyHamster135/Monet/releases/tag/v0.9.6)
is the publication record; the sections below preserve the local qualification
history. Physical hardware testing remains deferred at the owner's request.
This preview does not establish that the Razer hard lock or all hardware
compatibility has been resolved.

The release uses the exact RC13 image manifests and existing verified downloads,
without a rebuild against a newer base. The public verification record contains
their SHA-256 digests and the remaining qualification limits. Publication-only
changes add a tested guard against replacing released image tags and make future
installer builds use versioned images. These do not change the qualified runtime.

### Packaged native integration and full-image qualification (RC13)

Both complete graphics images now include all 19 password modules, current
Settings/helpers and the Electron integration source. The Linux install script
also installs that source at `/usr/share/monet/app-integration/electron`; app
authors still bundle its dependencies in their own apps. Each image passes
14 bootc lint checks (one inapplicable skip), native dialog/source checks and
15 real broker/app-support tests against the installed modules with no skips.

A disposable 0.9.5 VM upgrades to the exact RC13 AMD/Intel image and rolls back
successfully under Secure Boot and SELinux. Documents, shortcuts, startup choices
and desktop preferences survive both directions. The second drive receives no
writes. A fresh unencrypted installation also completes, clears its receipt and
download, and releases mounts in every service namespace. After virtual firmware
key enrollment it reaches Monet sign-in and a working desktop. Password settings
opens the native app-support dialog correctly; both were visually checked in the
installed system. The shell stays active with zero restarts and no failed system
or user units. Empty app selection completes offline when its boot timer runs.

The Linux download was rebuilt and its native Qt style test passes. Setup and
fallback ISOs, Windows ZIP and USB writer are reused byte-for-byte from RC12:
all 100 media inputs and 60 Rust/Windows inputs match. These network installers
target the unpublished versioned 0.9.6 registry images. No public release is
implied. The existing full desktop result remains 1,402 passed, 19 documented
skips and zero failed modules; runtime code matches that run. The additional
change here is installation of the developer integration source.

Evidence and downloadable artifacts: `target/release096-rc13-2026-11-05/`.
`source-hashes.json` records the frozen build snapshot; `installed-hashes.json`
records the 30 updated image files verified again inside the installed VM.
The completed disposable VM disks were removed after qualification; original
baseline/upgrade fixtures, screenshots and test results remain available.

### Current laptop update (RC13)

The tested NVIDIA image is now staged for the next restart:
`sha256:40a3714a4f09c4f1f81439b1ae78f5d231b189d6fd4e11229511bee8fb811823`.
The root-owned local source is
`/var/lib/monet/local-images/0.9.6-40a3714a4f09:local`; the staged deployment is
`09a26cf858cb43f140a973f0772cc28471fac10614432d06672dfe3d092c7f59`.
This replaces the pending RC12 update. The running RC8 deployment and retained
0.9.5 deployment remain available. No laptop restart was performed.

The current desktop still has PID 8838 with zero shell restarts. The optional
app-login service stays off/inactive, and the 19-module account preview still
matches the qualified code. Wallet, autologin and startup choices are unchanged.
The root staging receipt is
`/var/lib/monet/local-images/0.9.6-40a3714a4f09.json`; the readable status is
`target/release096-rc13-2026-11-05/laptop-update.json`.

### Electron native integration and sandbox support (after RC12, included in RC13)

The Flatpak/Electron accessibility failure is resolved in the real fixture:
Chromium's native bridge needs `ACCESSIBILITY_ENABLED=1` in this environment,
independently of renderer accessibility. **Settings → Passwords → Review app
support** enables this preference for one selected Flatpak and can undo it while
preserving other app preferences. It adds no sandbox permissions and asks the
user to reopen the app. Browsers, vaults and terminals are excluded. The native
dialog uses Monet light/Smoke styling and was visually checked at 200% scale.

A cooperating Electron app can now use a documented main-process integration
for native save consent and autofill even without an accessibility tree.
`OfferDocumentLogin` and `RequestDocumentLogin` authenticate the real D-Bus caller
and scope accounts to its app identity plus document. The app's trusted main
process supplies and validates the document; the broker cannot independently
verify a hidden page. Flatpak apps bundle the integration and declare only the
named broker permission. No extension or global typing is involved.

Eleven real Electron scenarios run both natively and inside Flatpak, including
direct fill, read-only usernames and refusing navigation, replaced fields,
changed attributes, typed passwords and changed accounts/servers during consent.
The picker leaves Sign in to the user. Four real Flatpak/Electron accessibility
cases now pass with the reversible preference, alongside the existing three
GTK Flatpak scenarios. All use synthetic accounts, private buses and a dummy vault.

Source, tests and documentation are local and uncommitted. Evidence is in
`target/electron-autofill-2026-11-05/`. The final full desktop suite passes
**1,402 checks with 19 documented skips and zero failed modules** (1,421
discovered), plus all JavaScript and 11 signed-connector form checks. The
separately enabled native/sandbox follow-up passes 29 checks with no skips;
the final app-support regression run passes seven, including large-file undo.
The translation catalog now extracts native `self.tr` messages and support errors.

Seven changed files were applied to the laptop's reversible Passwords preview;
all 19 password modules, five helpers and Settings match current sources. The
optional login service remains off/inactive. Plasmashell is still PID 8838 with
zero restarts, and no running app was closed. Receipt:
`~/.local/state/monet/desktop-preview/20261105T001518.650453Z/receipt.json`.
The preview's existing retirement on an image update remains in effect. RC13 now
contains these features, so they remain available from the image after retirement.

The prior RC12 image hashes below remain historical; they do not contain this
follow-up. Chromium still lacks the
accessibility EditableText setter, so unmodified Electron apps need developer
integration for direct autofill. Custom controls, non-Flatpak sandboxes and app
packaging still require compatibility work. See [Passwords](PASSWORDS.md#electron-and-sandboxed-apps)
and the [integration guide](../linux/share/monet/app-integration/electron/README.md).

### Electron, sandboxed apps and regenerated media (RC12)

App login detection now scopes embedded forms to the executable/package or
Flatpak ID and the document origin (exact file for local pages). The original
form and full live URL are rechecked after consent. URL tokens are not saved.
Cross-origin frames, opaque documents and non-loopback HTTP are refused. Consent
and account choice preserve the Monet light/Smoke styling and show the full
saved document scope.

Real Electron 43.8.7 fixtures pass save detection and document/cancellation
boundaries. Its Linux accessibility bridge provides no EditableText setter, so
Monet suppresses unusable fill suggestions. Direct Electron autofill still needs
app cooperation through `RequestLogin`. An installed GTK 3 Flatpak passes real
fill, save and read-only-username scenarios. At RC12 the experimental
Flatpak/Electron fixture exposed no accessibility tree; the follow-up above
resolves that fixture. See [Passwords](PASSWORDS.md#electron-and-sandboxed-apps)
for current limits.

Both complete image flavors include all 17 final password modules and pass the
installed picker/default-off/packaging checks. Bootc lint passes 14 checks with
one inapplicable skip. The new Setup and fallback ISOs boot with Secure Boot
in KVM; their Monet graphical interfaces were inspected. Their network target
is `ghcr.io/happyhamster135/monet:0.9.6`, not `latest`. The versioned registry
images have not been published, so distributing these network installers still
requires the matching release images. VM tests use only a local registry.

Artifacts and VM evidence: `target/release096-rc12-2026-11-05/`.
Desktop/native evidence: `target/app-sandbox-2026-11-04/`.
The Linux package was rebuilt from current sources with its Qt style test;
unchanged Windows/USB binaries retain the previous build and test evidence.
A menu test's fixed debounce wait was replaced with a bounded wait for the
actual request after a heavily loaded full run exposed the timing assumption.

The final full desktop run passes **1,392 checks with 17 documented skips and
zero failed modules** (1,409 discovered). JavaScript and all 11 signed-connector
form checks pass. The separately enabled real GTK Flatpak fixture passes all
three scenarios. RC12 upgrades from published 0.9.5 and rolls back successfully
under Secure Boot and SELinux, preserving documents, shortcuts, startup choices
and desktop preferences. Both image flavors match the final 17 module hashes.
The light and Smoke document-aware pickers were visually checked at 200% scale.
A fresh unencrypted install from the regenerated Setup ISO also completes,
releases its service mount namespaces and clears its receipt/runtime state.
After virtual firmware enrollment and the one-time preparation restart, it
reaches Monet sign-in with the exact final image/modules, Secure Boot enabled,
SELinux enforcing and no failed services.
Rust/Windows sources are unchanged from the prior 99-test/cross-build evidence;
`unchanged-binary-inputs.json` records 60 matching input files.

### Previous laptop update (RC12, replaced by RC13)

The previously staged NVIDIA image was:
`sha256:3891926c30a23b528c2f60eec9eea896d77fa9ae2002673b4702e4595f3e5b24`.
Its root-owned OCI source is
`/var/lib/monet/local-images/0.9.6-3891926c30a2:local`.
The staged deployment is
`54fdc11ee6e3ed1ba4bbbaf8421b7a99540b8952323e5bbd01693297c4ab31ea`.
The currently booted RC8 deployment and the older 0.9.5 deployment remain in
place. This does not reboot the laptop or establish physical hardware acceptance.

The reversible account preview also matches all 17 final password modules.
App-login saving is still off and its listener inactive. Plasmashell remains
active with the same PID and zero restarts. Wallet/autologin preferences and
running applications were left alone. The privileged staging receipt is
`/var/lib/monet/local-images/0.9.6-3891926c30a2.json`; the readable result is
`target/release096-rc12-2026-11-05/laptop-update.json`.
The final software index is that directory's `verification.json`. Newly created
VM disks were removed after qualification, recovering space; all evidence and
the older upgrade/rollback fixture remain available.

### Native app saving and autofill (RC11)

Settings → Passwords → **Save and fill app logins** is off by default. Standard
Qt, GTK 3 and GTK 4 forms can save app logins and offer an explicit account picker
without a browser extension. Read-only usernames, explicit GTK label relations,
common additional language labels and same-window username-first forms are covered.
The Monet light/Smoke picker fills the selected account and leaves Sign in to the
user. Focusing a field never unlocks the vault.

Autofill binds to the executable/script or Flatpak identity, exact server/service,
entered username, original controls and original form actions. Live accessibility
properties are reread after consent; stale caches, changed buttons/fields, typed
passwords, screen locks, disabled permission and expired requests cannot cause a
fill. Native apps can also use the authenticated `RequestLogin` D-Bus interface.
Secrets remain in the encrypted desktop vault; app logins are excluded from the
browser connector. Protected password controls still require manual reentry to
save when their toolkit exposes only masks. See [Passwords](PASSWORDS.md).

The full-image run found that first boot contacted Flathub even for an empty
selection or apps already built into Monet. RC11 resolves the selection first,
so these cases finish offline. Missing apps retain normal install/retry behavior.
RC11 is a local layer containing this helper fix on the fully rebuilt RC10 AMD
and NVIDIA images. Both flavors pass source-hash, native-picker, Settings and
opt-in service packaging checks.

The final isolated desktop suite reports **1,382 passed, 16 environment-specific
skips, zero failures** (1,398 checks). The separately enabled PowerShell suites
pass all 32 checks, native systemd retry tests pass all five checks, and all 99
Rust tests pass. Eight notification cases listed as skipped in the outer suite
run in its successful private-bus subprocess. Native Qt/GTK integration covers
21 real-widget scenarios, including changed servers/actions and closing/cancelling
forms. Light/Smoke picker renders pass at 200% scale. Evidence is under
`target/app-autofill-2026-11-04/`.

RC11 boots after an upgrade from published 0.9.5 with the exact expected image
and app source hashes, Secure Boot enabled, SELinux enforcing, no failed units,
and preserved documents, shortcuts, startup choices and preferences. The earlier
keep-data case also passes interrupted-download recovery without a network,
encrypted boot, TPM reboot, recovery-key verification, temporary-key retirement,
original partition/second-drive checksums and mount/cache cleanup. Final RC11
rollback to 0.9.5 passes the same data checks. The RC11 encrypted clean install
finishes with clean mounts and cleared recovery state. Its first boot verifies
the recovery key, temporary-key retirement, unchanged second drive and successful
empty first-boot app selection with the packaged helper. A second encrypted
boot unlocks through the software TPM and repeats those checks successfully,
with Secure Boot enabled, SELinux enforcing and no failed services. The final
evidence index is `target/app-autofill-2026-11-04/verification.json`.

The earlier RC11 work updated only the reversible account preview. RC12 local
laptop deployment is recorded in the current evidence above/below; the RC8
staging history later in this document is retained as historical evidence.
Wallet/autologin preferences remain unchanged, and app-login saving stays off
until the user enables it.

## Included

- Setup explicitly selects the target drive and shows what will be kept or
  erased. Verified downloads and recovery receipts survive an interrupted
  installation. Gentler scheduling and isolated bootc mounts reduce unnecessary
  contention. Low working space is detected before moving a previous system;
  disk-full errors preserve recovery state and do not trigger network retries.
- Settings → Storage reviews, exports and removes retained unfinished installs
  with administrator authentication and protections for mounted/current roots.
- Task Manager → Startup adds and enables/disables sign-in apps. User overrides
  preserve app arguments, and concurrent changes are rejected without overwriting
  the newer choice. Performance starts drawing with the first available sample.
- Settings → Recovery checks the system on demand, previews a limited diagnostic
  report and supports undo of recorded desktop preference changes.
- Dock hover recovery, English spelling suggestions, keyboard/scaling fixes and
  a bounded single-pass storage scan. New controls follow Monet's native styling.
- Native Monet sign-in: Fraunces clock, glass panel and larger password controls,
  retaining KDE's authentication, keyboard support and emergency fallback page.
- Consistent 0.9.6 executable/plugin metadata, updated release notes, clean
  packaging and corrected image-finalization/container logging.
- Earlier-file restoration selects the snapshot by identity, copies privately
  and publishes without replacing an existing file. Failed copies leave no
  misleading completed file; Settings explains failures and prevents duplicate
  requests. Rollback diagnostics work for ordinary desktop accounts.
- Recorded account previews can be retired with backups and preservation of
  personal edits, so they do not shadow the installed OS after an upgrade.

## Local acceptance

Evidence and reproducible fixtures are under `target/release096-2026-11-04/`.
The source snapshot used for the final Setup ISO is in that directory's `source/`.

| Gate | Result |
| --- | --- |
| Full desktop tests | 1,342 discovered; 1,326 pass; 16 documented skips; zero failed modules. JavaScript and signed browser connector/form checks pass. |
| Rust | 99 workspace tests pass; Clippy passes with warnings denied. |
| Windows delivery | Bridge, setup checker and USB tool cross-compile; Linux/Windows packages built; PowerShell syntax and setup behavior checks pass. Native Windows/physical USB validation remains separate. |
| Complete AMD/Intel and NVIDIA images | Both assembled; packaged image lint passes 14 checks with one inapplicable check skipped and no warnings. |
| Published 0.9.5 → candidate → rollback | Passes in KVM with Secure Boot enabled and SELinux enforcing; documents, shortcut, desktop preference and Startup choice preserved. The second virtual drive has no changed extents. |
| Installed storage recovery | Export includes nested homes and sparse files; excludes private root files; stale tokens and mounted candidates cannot be deleted; active root preserved. |
| Installer working-space boundary | Real disposable Btrfs filesystem rejects insufficient space before changing its existing root. Disk-full and quota failures retain the saved download and receipt. |
| Setup and fallback ISO | Both built. Setup's signed boot files and optical/USB copies verified. Fallback media checksum and embedded EFI menu verified; its branded graphical installer boots with Secure Boot enabled. |
| Fresh encrypted install and offline recovery | Keep-data install resumes after a hard reset with its virtual network disconnected; saved 6 GB download verified and reused. Completion releases all mounts, closes encryption and clears the receipt. First and second boots pass under Secure Boot/SELinux; software TPM unlocks after the bootstrap key is revoked, and the recovery key works. Existing data partition and other drive remain unchanged. |
| Native update retries | All five installed-system success/failure/skip, retry-limit, metered-network and disabled-update checks pass. |
| Native sign-in | Wide, compact, 150% Arabic and software-rendering previews pass password rejection/retry. Deliberately missing Monet QML falls back to the original working sign-in page. Installed VM passes real PAM rejection/login and on-screen keyboard checks. |
| Follow-up recovery and local deployment | RC8 packages match the updated helper and Settings sources. File/folder restoration, collisions, disk-full failures, pruned selections, UI retry and preview retirement pass. The VM boots an OCI-directory installation and its update check stays on that local image. RC6 → RC8 preserves the saved work and preferences under Secure Boot/SELinux, with no failed system services. |

The candidate AMD/Intel OCI manifest is
`sha256:d77a388bc28073476acaaf99ae34174c616d25eaad7237be3a3039f610d46546`.
The baseline is the published 0.9.5 image, not an earlier local build labelled
0.9.6. The NVIDIA image has build/package coverage; no NVIDIA GPU is emulated.

The full interrupted-install/offline-retry trial used the earlier RC2 image.
The RC6 image adds the native sign-in work and its clean source archive;
the Setup worker is unchanged. RC6 is verified on that same encrypted install
and in the separate upgrade/rollback VM. Both final image builds exit zero.
`release-images.json` records the RC6 image IDs; `SHA256SUMS.txt` identifies the
two ISOs and three delivery packages, all rechecked after building.

The subsequent RC8 images add the file-restoration and unprivileged-diagnostics
fixes above; the installer, kernel, native plugins and greeter are unchanged.
Their final test report is `desktop-followup-final.json`; package checks are in
`packaged-followup-{amd,nvidia}.log`. Both builds exit zero with 14 image-lint
checks passed and one inapplicable check skipped. An obsolete test assertion
for row-number snapshot selection failed the first follow-up run; it was updated
and the complete suite rerun successfully. The original ISO/package artifacts
remain the RC6 artifacts; the refreshed OS images are identified separately.

## Local laptop update

**Booted locally; desktop cleanup repaired after the owner's restart.** The
laptop now runs the NVIDIA RC8 image below, with 0.9.5 retained for rollback.
The desktop initially failed because account-preview retirement was deferred
incorrectly. The startup guard compared Fedora's `VERSION_ID=45` with Monet's
`0.9.6` instead of reading `VERSION`. Empty retired package directories also
continued to shadow the installed shell. Both cleanup bugs are fixed locally
and in the retirement tool; only empty recorded directories are removed, and
restoration recreates their parents. The user confirmed that the desktop and
bar returned. The shell then remained active with no further restarts.

The tested NVIDIA RC8 OCI manifest is
`sha256:13f1d13d95f1ab8ae6885a50080bd30ae1c9ca603edcfab1e53d1eb2fcef7545`.
The local staging helper saves the previous deployment and update origin,
copies the image into a root-owned location under `/var/lib/monet/local-images`,
and verifies the staged digest while leaving the running system untouched.
Administrator authentication succeeded. Staging did not reboot the laptop.

This unpublished candidate follows its local OCI image rather than the public
`:latest` tag, so automatic checks cannot replace it with the older published
release. App updates remain available. Once a suitable release is published,
switch the OS back with `sudo bootc switch ghcr.io/happyhamster135/monet:latest`.
Do not switch back while that tag still offers 0.9.5 unless deliberately reverting.
Account-preview retirement has its own reversible receipt and preserves the two
edited Task Manager pages and a subsequently updated Task Manager launcher.
Fourteen launch overrides were retired before reboot. The remaining 574 recorded
files and 177 empty directories were retired during the desktop repair, and the
one-time startup hook was removed. Six retirement regressions pass, including
the Monet/Fedora version distinction, empty package roots, later edits and
restoring removed directories. Native package lookup resolves the installed
shell, menu and Quick Settings; running applications were not closed. The result and backup
receipts are under `~/.local/state/monet/local-update096/` and
`~/.local/state/monet/preview-retirement/`. `laptop-stage.log` records successful
staging, and `followup-summary.json` identifies the tested images and checks.

Repair evidence is in `target/desktop-repair-2026-11-04/`. The KDE Wallet login
prompt was traced to ChatGPT requesting its encrypted sign-in during automatic
login. The owner explicitly chose to leave that behavior unchanged; no wallet
contents, encryption, automatic-login settings or application startup choices
were changed for it.

Redundant intermediate build images/exports and the completed disposable
encrypted-install VM disks were cleaned up to recover laptop storage. Their test
records remain; the RC6/RC8 images and the separate upgrade VM are retained.

The fallback ISO was assembled with the release workflow's steps and a local
mtools adapter for Lorax's EFI-image creation, because rootless containers cannot
use host loop devices. The adapter changes the build mechanism, not the boot
files. Its checks and boot evidence are recorded beside the build log. Setup
uses the normal production builder in a private container.

## USB maker refresh — 5 November 2026

The Windows USB maker is refreshed independently of the frozen RC13 OS images
and installers. Its source is commit `031fdfd`; the release verification record
contains the replacement executable's SHA-256, size, build inputs and hardware
qualification. The original source snapshot remains the provenance of the
unchanged OS images and other release downloads.

The maker clears stale partition tables, initializes cleared removable media,
reopens and validates the physical device after Windows re-enumeration, and
retries busy volume locks for a bounded interval. An unsuccessful lock still
prevents writing. The one-click interface, device protections and full read-back
verification remain in place. All 20 Windows unit tests and two consecutive
production-writer rewrites of the same Kingston DataTraveler 3.0 passed. Booting
the rewritten physical stick and the wider USB hardware matrix remain untested.

## Remaining qualification and scope

- Publication is authorized for the exact qualified RC13 image/media set. The
  release page and its verification record identify the published artifacts.
- Broader real-app login compatibility: unmodified Electron apps need to adopt
  the native integration for direct autofill. The Flatpak/Electron accessibility
  fixture is fixed, but custom controls, other sandboxes and app packaging vary.
  Protected controls can require manual password reentry when saving.
- Physical Razer install completion and temperature investigation; TPM/recovery
  boot, NVIDIA graphics, firmware enrollment, suspend/resume, audio, Bluetooth,
  Wi-Fi, USB writes and external displays on the supported hardware matrix.
- A real Windows game round trip and native Windows package smoke tests.
- Human translation and screen-reader review; consistent spelling/correction
  across app-managed Chromium/Electron and sandboxed dictionaries. The system
  dictionary change does not change ChatGPT's own spelling engine.
- Controlled same-machine comparisons with Windows and other Linux systems.
  Local timing fixtures do not establish better battery life, thermals or gaming
  performance.

Recovery currently handles retained installs on the running Monet filesystem.
Recovery from an unbootable OS, arbitrary disks and custom partition layouts is
not included. Startup currently manages XDG autostart entries, not system
services or per-app startup-duration measurements. These are scope limits, not
features implied by the 0.9.6 test results.

Further OS work beyond this update includes broader office/editor/browser work
restoration; model-specific Windows driver setup and Windows-only game guidance;
automatic Bluetooth enrollment from Monet back into Windows; and password-manager
passkeys, TOTP, global auto-type and Windows integration. The browser connector
also needs broader real-site acceptance and independent security review. None of
these are implied by the system spelling or recovery improvements.
