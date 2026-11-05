# Monet Passwords

The installed desktop manager is Monet's own native Qt application. Search **passwords** or **wallet**, or use **Settings → Passwords → Open Monet Passwords**. It reads the existing encrypted desktop vault through its supported APIs. Existing Wi-Fi and app credentials remain in place; no migration or new cryptographic format is introduced.

## Optional native app saving and autofill — 5 November 2026

The new native flow is **Settings → Passwords → Save and fill app logins**. It is off by default. Enabling it starts a per-user service and enables that service for later desktop sessions; disabling it stops the service and its pending consent window. Existing saved logins remain encrypted in the desktop vault. No browser extension, pairing, new vault password or browser configuration change is required for this app-login feature. The older Zen connection below remains an independent, optional browser feature.

The Monet dialog identifies the app and its executable, shows the account, and offers **Save login**, **Not now** and **Never for this app**. Enter/Escape initially decline. The vault is opened only after Save; replacing an existing password requires a separate Update confirmation. Unknown or changed records fail without silently overwriting another account. Never is stored per app and can be reset in Settings. Screen/provider lock, turning the feature off, and the prompt deadline cancel pending work. As with other vault operations, a write already accepted by the provider cannot be atomically revoked by a simultaneous lock.

Two input paths are implemented:

- **Native app integration:** an app submits the login it has just used through the session D-Bus interface below. The broker derives the app identity from D-Bus peer credentials, not caller-supplied names. This can provide a one-click Save prompt without retyping.
- **Accessible native forms:** an event listener recognises a focused standard password field alongside one labelled username/email field and a sign-in/register/change-password button. A disappearing form within a still-active window can offer a save. Closing the window, cancelling, changing apps and ambiguous forms do not qualify. Embedded documents require the app/document checks below. Label matching covers common English/Swedish and selected European-language labels. Explicit GTK label relations and read-only usernames are supported. A username/server page can carry its context into the same window’s password page for up to 90 seconds. Custom controls and sign-ins that close their entire window need app integration or manual Add login.

Protected accessibility fields expose mask characters in standard Qt controls. Monet never treats those masks as a password: the native dialog explains that the user needs to enter the password once to save it. Plaintext provided by a supported password control can be offered directly. A recent edit invalidates a cached password before submission, so an incomplete earlier value is never silently saved. Matching new/confirmation fields is checked when readable; masked confirmation fields use the manual fallback. Detecting submission does not establish successful authentication.

App logins live in **Monet App Logins**, appear in the normal **Saved logins** view, and are scoped to the executable/script or Flatpak ID, account and optional service. They are never exposed through the browser connector. Native autofill is available for standard Qt, GTK 3 and GTK 4 forms with a single empty password field. A quiet **Choose account** notification appears only for an app with a previously saved or explicitly opened app login. It does not unlock the vault. Choosing it opens a Monet account picker; selecting **Fill selected account** fills only the original controls and never presses Sign in. Matching requires the same executable/script or Flatpak identity, exact service/server and any already-entered username. The form, identity, permission and screen state are rechecked after consent; changed/replaced fields, typed passwords, hidden forms and expired requests are refused. The picker preserves the Monet light/Smoke styling and supports notification activation on Wayland.

Browser coverage, arbitrary custom controls, passkeys and a broad real-app compatibility matrix remain follow-up work. This is not universal login detection. App integration is the reliable path when a toolkit withholds accessibility information. Older app records are preserved; opening one explicitly in Passwords makes that app eligible for quiet suggestions. New app-record keys include an app hash so listing that app’s accounts does not need to read other apps’ secrets.

There is no keyboard recorder, clipboard watcher, screenshot capture, network service or plaintext credential file. Accessibility work is bounded and event-driven, with at most one pending form and one consent dialog. Candidates expire after 90 seconds; the supervising prompt process has a 100-second bound. Duplicate suppression retains only short-lived salted fingerprints. Python/Qt do not guarantee memory zeroization. The listener does not run while the feature is off, and it never opens the vault merely because the user signed in to the desktop.

### Electron and sandboxed apps

Accessible embedded login forms now bind to both the authenticated app and its document. HTTPS pages use their origin; local app pages use their exact file, and supported app URL schemes retain their host. Query strings and fragments never enter saved identity. During consent, the complete live URL, original form and all containing documents must still match. Cross-origin frames, opaque pages and non-loopback HTTP are refused. The Monet consent dialog displays the document scope in full. Separate apps using the same Electron executable have separate package identities.

Real Electron 43.8.7 fixtures pass save detection and reject changed documents, cancellation and unavailable fill methods. Chromium's Linux accessibility bridge exposes Text but no EditableText setter, so unmodified Electron apps still cannot be filled through accessibility. Monet suppresses unusable fill suggestions. Protected fields still require entering the password once in the save dialog. See the [Electron accessibility documentation](https://www.electronjs.org/docs/latest/tutorial/accessibility) and [Chromium ATK implementation](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/ui/accessibility/platform/ax_platform_node_auralinux.cc).

**Settings → Passwords → Review app support** now offers a reversible setting for individual installed Flatpaks. Choose an app, select **Enable support**, then reopen it. This sets only its `ACCESSIBILITY_ENABLED=1` environment preference; it grants no new sandbox permissions. **Undo change** restores the earlier value and preserves unrelated later edits. Browsers, password managers and terminals are excluded. This preference does not turn on app-login saving or unlock the vault. Some apps still require developer integration.

The previously failing Flatpak/Electron fixture now exposes its accessibility tree with this setting. Chromium checks its native [accessibility startup gate](https://chromium.googlesource.com/chromium/src/+/refs/heads/main/ui/accessibility/platform/atk_util_auralinux.cc) separately from renderer accessibility. Four real save/document-boundary scenarios pass using the actual reversible setting. Flatpak identity recognises the filtered D-Bus proxy using its kernel-visible `.flatpak-info`; an actually installed GTK 3 Flatpak also passes direct fill, save and read-only-username scenarios. These tests use private installations and restore their overrides.

The new [Electron main-process integration](../linux/share/monet/app-integration/electron/README.md) provides native autofill without an accessibility tree. It calls the authenticated document API, opens Monet's existing light/Smoke picker and fills only the original standard form through a private isolated world. It refuses changed URLs, nodes, field attributes, accounts, servers or typed passwords during consent and never submits the form. Eleven scenarios pass in both native Electron and an actually installed Flatpak with accessibility disabled. Flatpak apps must bundle the integration and declare only `--talk-name=org.monet.PasswordOffers1`. The main process must own the document allowlist, selectors and user action; no renderer-facing integration API is exposed. This is app-developer support, not automatic compatibility with all installed Electron apps.

Evidence: `target/electron-autofill-2026-11-05/final-followup.json`, `full-desktop.json`, `support-final.json` and light/Smoke 200% renders. RC13 image and VM qualification is in `target/release096-rc13-2026-11-05/`; earlier RC12 evidence remains in `target/app-sandbox-2026-11-04/`. Tests use synthetic accounts and a dummy vault, never this laptop's saved credentials. The reversible account preview and both RC13 graphics images include these changes, so the image retains the features after preview retirement.

### Native app interface

Session bus name/interface: `org.monet.PasswordOffers1`; object: `/org/monet/PasswordOffers1`.

- `OfferLogin(username: s, password: s, service: s, kind: s) → status: s`. Call asynchronously after the app's own successful password sign-in, registration or password change. `kind` is `login`, `register` or `change`; `service` is an optional account/server label, not an asserted website origin. Limits are 320 username characters, 4,096 password characters and 200 service characters. No app identity, PID, file path or arbitrary URL argument is accepted.
- Use the D-Bus **no auto start** flag. An absent service means offers are off or unavailable; the app continues normally. Do not retry continuously, block sign-in on consent, pass passwords through command-line arguments, or log requests.
- Save replies are `saved`, `updated`, `unchanged`, `declined`, `ignored`, `disabled`, `busy`, `recent`, `invalid`, `unavailable` or `cancelled`.
- `RequestLogin(username: s, service: s) → a{ss}` opens a native chooser. Empty username allows account selection; service matching is exact. The caller cannot supply an app identity. Vault access requires **Open saved logins**, followed by **Fill selected account**. A `filled` reply includes `username`, `password` and `service`; other statuses contain no credential. Call asynchronously, permit up to 100 seconds for consent, do not log the response, and apply it only if the initiating form is still current. The broker rechecks the unique D-Bus caller before returning anything. Apps must not auto-submit or retry declined requests.
- `OfferDocumentLogin(document: s, username: s, password: s, service: s, kind: s) → status: s` and `RequestDocumentLogin(document: s, username: s, service: s) → a{ss}` add an app-owned document scope to those operations. They use the same identity as accessibility detection for that app/document. The broker authenticates the app, but trusts its main process to supply the document; it cannot independently prove a hidden page's URL. Main-process clients must enforce an explicit document allowlist and revalidate the original form after consent. No caller-supplied PID, app ID or record key is accepted. Losing the requesting connection closes pending fill consent.
- `GetStatus() → a{sv}` returns only `enabled`, `busy` and `screenLocked` for session health checks.

Sources: `app_logins.py`, `app_documents.py`, `app_detector.py`, `app_offers.py`, `app_prompt.py`, `app_fill.py`, `app_suggestions.py` under `linux/share/monet/passwords/`. The service is packaged but not globally enabled. Existing auto-login, wallet encryption and unlock preferences are unchanged.

Validation uses isolated session buses, a dummy KWallet/Secret Service, and a separate Xvfb display. It covers actual app → broker → native consent → provider calls, save/decline/never, lock/disable cancellation, duplicate/conflicting updates, and real Qt login/register/password-change/cancel/window-close accessibility events. No existing user credential is read by these tests. Light and Smoke consent renders are checked at 200% scale. The broader native-widget and full-image results are recorded in [the release notes](RELEASE-0.9.6.md). Both RC13 graphics images contain all 19 current password modules and pass native consent/support checks against their installed files. Fresh install, upgrade, rollback and the actual Settings → Review app support route pass in the VM. RC8 predates native saving and autofill.

The laptop now has a reversible **account-local preview** of Passwords and its Settings page. The switch is off and the listener is inactive. Installed module hashes and Settings loading were verified; the desktop shell was not restarted and no app was closed. The earlier 144 saving checks remain recorded in `target/app-logins-2026-11-04/verified.json`. Broader saving/autofill and full-suite evidence is under `target/app-autofill-2026-11-04/`; original failure logs are retained alongside the passing follow-ups. Local deployment receipts use the existing `~/.local/state/monet/desktop-preview/` history so the next image update can retire these overrides safely.

## Desktop manager

- Saved logins is the default view. Wi-Fi & VPN, App data, Connected apps and Preferences have separate sections. Repeated folder/key metadata appears once without changing stored entries. Known portal/browser encryption keys are explained in App data; their secret values are never read or offered for editing.
- A selected entry shows readable usernames/websites and labelled secret fields with Show/Hide and Copy. Passwords are concealed initially, revealed for 15 seconds, and concealed when the window loses focus. Copies carry KDE's password-manager MIME hint and clear after 30 seconds only if the clipboard still contains that copy.
- Add logins, generate random passwords, edit supported password/map entries and delete with confirmation. Another app's intervening change is checked before editing/deleting; the API does not offer an atomic compare-and-swap transaction.
- Known QDataStream string maps, UTF-8 and text JSON fields are decoded for display. Unknown binary records are explained as app-managed data and cannot be edited or deleted here. Multiline existing fields are preserved during edits of other fields.
- Network profile names replace matching UUIDs without requesting network secrets. Ordinary listings contain metadata; only the selected credential is read. An explicitly confirmed CSV import also reads Monet-owned login records to skip identical accounts.
- Close view releases Monet's connection and clears displayed values. Lock vault calls the encrypted storage provider and verifies its Locked property. Screen-lock and provider-lock notifications clear the view. Settings uses the same verified lock/status path.
- Connected apps can be disconnected from the current vault session. This is not a permanent deny policy, nor a universal website autofill controller. Browser password/autofill controls are linked from Preferences. Zen can now connect to Monet logins as described below. Saved browser connections can be revoked separately; this keeps the logins but prevents that browser from retrieving them again.
- Session/idle preferences preserve separate login and vault passwords. Automatic desktop sign-in still requires the initial encrypted-vault unlock. The optional app-offer service above is event-driven; there is no secret file export, external network request or password command-line argument. Python/Qt retain transient values in process memory; guaranteed zeroization is not claimed.

Source: `linux/libexec/monet-passwords`, `linux/share/monet/passwords/app.py` and `vault.py`. Installer/uninstaller and account preview include the app and its desktop entry; the image explicitly carries python3-dbus.

### Guided Zen setup — 3 November 2026

Open **Zen autofill** in Passwords, or **Settings → Passwords → Set up Zen autofill**. The page checks the default profile, signed extension registration, local host registration and native-messaging permission on demand. It reads bounded installation metadata only, never browser login databases or extension storage. Missing profiles, missing connectors, disabled connectors and configuration problems have separate next actions. An already installed connector opens directly; it is not reinstalled. Browser pages open in a separate Zen window, including when the existing browser window is minimized, without replacing a login form.

Enabling the connection still backs up configuration and rolls back failed permission changes. Zen must approve installation and Monet must approve pairing. The page distinguishes **installed** from a live connection; saved pairing metadata alone is not proof that a particular profile is connected. The connector's own page shows the live status.

The local source now packages the reviewed signed 0.1.1 connector with Linux/OS builds and the account-preview plan. Packaging pins the archive and matching build inputs; installation verifies the archive before any system changes. Zen still verifies its signature and requests approval. An older installed connector offers **Update Zen connector**; an equal, newer or unrecognized version is never automatically reinstalled or downgraded. Updates keep the existing identity, pairing and settings. There is no background update feed: future signed connectors are delivered through Monet releases. Publishing and full-image acceptance remain pending; this source has not been installed in the live account. See [the connector packaging instructions](../browser/monet-passwords/README.md#os-packaging--4-november-2026).

Closed views show **Open vault** instead of an incorrect connection prompt. Connected apps can open the vault directly. Closing the view clears its data without claiming to lock every app; **Lock vault** remains the explicit provider-lock action. Setup checks run on the worker only when requested or when returning to its page, with no background polling. Existing login and vault passwords, consent prompts, autofill permissions and encryption are unchanged.

### Multi-step sign-ins and changing passwords — connector 0.1.1

Username-first sign-ins retain the chosen account across the two pages on the same tab and exact website origin. Username context is memory-only, expires after two minutes and is discarded on lock, disconnect, tab close or origin change. A different entered username never autofills another account’s password.

Password-change forms fill the current password and leave new/confirmation fields for the user. Monet asks before updating the matching saved account. Mismatched confirmations and invalid forms do not propose writes. Where the site omits a username, an explicit account choice or unique current-password match identifies the record; ambiguous matches require selection from the field’s menu. Declining an update preserves the old password. Form submission does not prove that a website accepted a login or change.

Seventeen scenarios passed in a disposable Zen profile and isolated synthetic vault, including dynamic forms, multiple accounts, declined updates and lock/origin boundaries. Additional JavaScript form/gate checks and Python protocol/consent checks passed. Mozilla approved and signed connector 0.1.1 privately. The verified signed file is installed as Monet’s local setup artifact and is active in normal Zen as version 0.1.1. Zen reports it enabled, signed and non-temporary; the installed archive hash and native-host configuration were verified after the owner accepted the update. No real login was read or changed in these tests.

### Importing actual website logins

Choose **Import…**, select a CSV exported by Zen/Firefox or Chromium, then confirm the count. The importer accepts UTF-8/BOM and quoted CSV, limits the file to 4 MB and 2,000 rows, skips empty-password/repeated rows and exact existing logins, and never overwrites another record. Changed passwords for the same account are kept as separately named entries. Verified partial imports can be retried safely. Screen lock cancels remaining writes and clears the review. Values stay on the worker; the review shows counts only. No export or temporary plaintext file is created by Monet. The original user-selected CSV remains where the user placed it; the review reminds them to delete this unencrypted export when finished.

CSV import remains optional. The Zen connection below saves and fills directly from Monet; an import is not required. Existing browser-only entries are not silently extracted: they can be saved to Monet when used and approved. **Open browser passwords** still opens Zen's own account management page. [Mozilla documents CSV export](https://support.mozilla.org/en-US/kb/export-login-data-firefox).

The duplicate Zen entries in the reported screenshot were app metadata, not two website accounts. KWallet's compatibility folder enumeration can contain repeated folders, so Monet deduplicates `(folder, key)` display identities. The [Secret portal provides per-application keys](https://flatpak.github.io/xdg-desktop-portal/docs/doc-org.freedesktop.portal.Secret.html); [Chromium Safe Storage is an encryption key](https://chromium.googlesource.com/chromium/src/+/3f85aea3bf92db168ea7d3f8a286d77651d751b1/components/os_crypt/sync/key_storage_linux.cc). No attempt is made to interpret these values as user logins or to delete duplicates in storage.

The native UI uses Fusion controls with Monet's Mist/Smoke colors, opaque surfaces, compact account rows and explicit type sizes. This avoids Kvantum's translucent child-widget backgrounds seen in the report. Native Wayland renders were checked at the laptop's 200% scale using synthetic accounts only.

### Compatibility details and validation — 3 November 2026

KWallet 6.31's compatibility `close()`/`closeAllWallets()` drop app handles without locking the underlying Secret Service collection. Monet therefore uses [Secret Service Lock](https://specifications.freedesktop.org/secret-service/latest/unlocking.html) and verifies the collection's actual Locked property. Its compatibility disconnect method also returns false after successfully dropping a connection; Monet checks the resulting connected-app list instead. The source was checked against [KDE 6.31](https://github.com/KDE/kwallet/blob/v6.31.0/src/runtime/kwalletd/kwalletd.cpp). An unrelated app disconnect no longer clears a still-valid Monet view.

The [KWallet map API](https://github.com/KDE/kwallet/blob/v6.31.0/src/api/KWallet/kwallet.cpp), [NetworkManager's non-secret GetSettings API](https://networkmanager.dev/docs/api/latest/gdbus-org.freedesktop.NetworkManager.Settings.Connection.html) and [Klipper's clipboard filtering](https://github.com/KDE/plasma-workspace/blob/Plasma/6.5/klipper/historymodel.cpp) were checked. Generated maps match native Qt serialization. Typed D-Bus tests use an isolated bus and synthetic providers, including actual Qt lock-signal delivery, verified collection locking and misleading compatibility return values.

On the laptop, an explicitly scoped temporary synthetic login was created, read back, edited, read back and deleted through the real encrypted vault. The test refused reads or changes to any other entry. Existing credentials were not opened or modified. The real user's vault was not locked by the tests. Light/Smoke rendering, clipboard expiry, stale read rejection, editor cancellation, lossless field preservation and a slow-provider UI responsiveness fixture pass. Current evidence and local deployment receipts are recorded in the 0.9.5 backlog and under `target/monet-passwords-2026-11-03/`.

The earlier KeePassXC/KDBX experiment below remains separate. The current connection uses the signed browser connector with Monet's existing desktop vault, without running that prototype or creating a KDBX database.

## Automatic native approval — installed locally, 3 November 2026

The laptop uses the permanent signed Monet connector 0.1.0: submitting a login automatically opens Monet’s Save login or Update password dialog. No New/Update banner click is needed. Cancel preserves existing values; unchanged passwords do not prompt. Repeated submissions are suppressed briefly, and locked/disconnected attempts can retry after recovery. Saving still requires approval, and form auto-submit stays off.

The connector has its own add-on identity and received **private, unlisted Mozilla approval/signing** with owner authorization. Normal browser restart, saved pairing, automatic approval and autofill are verified. The old signed KeePassXC connector is disabled with its settings retained for rollback. Signing and normal browser protections remain enabled. Build source, privacy/data categories and preview limitations are in [the connector README](../browser/monet-passwords/README.md). No CSV export/import is required. Connect Zen prefers the installed local signed Monet package. The older instructions below describe the upstream fallback on installations without this package; distributing the connector in an OS image is separate release work.

## Zen save and autofill — 3 November 2026

**Applied locally, not released.** Open **Preferences → Connect Zen for save and autofill** (also available from the Saved logins empty view). This registers the Monet native host for the default Zen Flatpak profile and opens the official [KeePassXC-Browser extension](https://addons.mozilla.org/firefox/addon/keepassxc-browser/). Install it, restart Zen, then choose Connect in the connector and approve Monet's connection dialog. The laptop's normal profile is already installed and paired. The connector retains its upstream name and branding; the full KeePassXC desktop app is not required.

After submitting a login, the connector offers **New** or **Update**. Monet then shows the exact website and username and requires approval before writing. Cancel, timeout, screen lock, a changed record or a revoked browser connection prevents the write. A repeated request for an identical password does not create a duplicate. Enable **Automatically fill in single-credential entries** in the connector's General settings; it is enabled on this laptop. Multiple accounts use the connector's chooser. Automatic form submission is off. The connector is the default password-saving manager here, so Zen's built-in saver does not show a competing save prompt; its existing logins are retained.

Only entries in **Monet Logins** can be shared. Matching uses the exact HTTPS scheme, normalized host and port, and rejects a form submission address on another origin. HTTP is limited to local development addresses. Manually added/imported accounts require a first-use website permission; approved browser saves grant that exact site to the connected browser. **Connected apps → Saved browser connections → Revoke selected browser** invalidates its saved authorization without deleting logins. The desktop list refreshes when returning to the app, without polling or replacing an open editor. Revocation cannot retract a password already filled into a web page.

The host implements the documented [KeePassXC-Browser protocol](https://github.com/keepassxreboot/keepassxc-browser/blob/develop/keepassxc-protocol.md) with PyNaCl/libsodium authenticated encryption, bounded native messages, per-connection keys and replay rejection. Authorization records stay encrypted in a separate vault folder and never appear as logins. Native framing carries no secret command-line arguments or credential files; dialog input contains metadata only. Screen/provider locks clear the connector cache and block replies; unrelated vault collections do not lock this connection. Browser credentials remain in memory while in use; Python does not guarantee zeroization. No independent security audit or compatibility with every website is claimed.

Account-local setup backs up the native manifest, `user.js` and Flatpak override. It adds only the native-messaging proxy preference and permission, preserves other settings, refuses another manager's native host and rolls back a failed permission change. It does not disable extension signing or enable debugging in the normal profile. The image includes `python3-pynacl`; this laptop uses a reversible private PyNaCl 1.6.2 dependency bundle. The host runs on demand with the browser, with no new login service or polling timer. The signed extension tested is 1.10.4.1 (SHA-256 `ae41157a3f017b0773abba2097d5b0056241631d0a38ad36d68d0b24b1a409c1`). Passkeys, TOTP, global auto-type and arbitrary group creation are not implemented by this host; unsupported requests fail explicitly.

Validation includes encrypted signed-extension pairing, save, update, declined update, different-origin and cross-frame blocking, screen lock/unlock, revocation and restart/reconnect against a disposable Zen profile and isolated synthetic vault. The normal profile also passed a real keyboard → browser save banner → native approval → autofill test with one temporary loopback account. The stored password matched the actual Swedish-layout input; the test account, its site permission, test tabs and test services were removed afterward. No existing login was modified. Automated tests cover tampering/replay, consent, concurrent edits, exact origins, rollback and actual D-Bus lock signals; the native dialog's Enter key defaults to cancellation. Evidence and local receipts are in the laptop backlog.

# Earlier browser-integration prototype

Passwords is a development preview of a local vault with Monet's native interface.
The first prototype adapts KeePassXC 2.8.0, using its existing Qt application,
KDBX storage, cryptography, file locking, atomic saves, recovery, clipboard clearing
and browser authorization. Monet supplies a smaller toolbar, welcome/unlock wording
and defaults. It does not implement a second vault writer or a new cryptographic format.

The source lives in `prototypes/passwords/`. It is deliberately outside the normal
installer and OS image while the integration is being evaluated. Use made-up logins.
Advanced dialogs still use KeePassXC's interface; this is the start of Monet's product,
not a claim that its complete design, Windows integration or security review is finished.

## Current behavior

- A native Qt window uses Monet's system style, with search, Add login, Edit, Copy password,
  Delete, Lock vault and More. More retains the engine's full menus, including backups and
  recovery. Existing keyboard shortcuts and permission checks remain in charge.
- A vault requires an explicit unlock. Passwordless desktop sign-in does not unlock it.
  Quick unlock is off by default; idle locking defaults to five minutes. The upstream
  screen-lock/user-switch locking and ten-second clipboard clearing remain enabled.
- Saving makes an encrypted previous-version backup using KeePassXC's own backup path.
  This is one previous version beside the vault, not an off-device disaster backup.
- Preview settings live in `~/.config/monet/passwords-preview/`; vault locations are
  chosen by the person. The native messaging identity stays upstream-compatible.
  Do not run the preview alongside another KeePassXC instance: they intentionally
  share the engine's single-instance and browser-service identity.
- The archive includes the exact modified upstream source and its license notices.
  KeePassXC is credited in the preview. Monet must keep tracking upstream security fixes.

The presentation patch checks every source anchor before writing any file. An upstream
change or an already-patched tree fails the build. The source archive is pinned by SHA-256;
updating the pin requires reviewing the changes, building and repeating the tests.

## Build and test

In a disposable Fedora 44 container, mount this repository's `prototypes/passwords`
at `/src` read-only and a writable build directory at `/build`, then run:

```sh
sh /src/build.sh /build/work /build/out
```

`work` must be new. The script installs build dependencies in the container, verifies
the upstream archive, applies the patch, compiles the app and tests, runs eight focused
test suites and eight GUI scenarios, and installs to `out`. Run
`out/bin/monet-passwords-preview` in a compatible
Linux desktop. Runtime dependencies include Qt 6 and Botan 3; the output is a development
prefix, not a self-contained portable package. The Qt platform style belongs to the OS.

Run the source-patch checks with:

```sh
python3 -m unittest tests.test_passwords_preview
```

For the VM fixture, follow `.claude/skills/monet-vm/SKILL.md` and take an `ai-` checkpoint
first. The fixture helpers expect the build at `~/monet-passwords-build/out`; the bench
supplied the matching Botan and jitterentropy libraries under `runtime/` without changing
the installed image. `test_zen.py setup` creates a new disposable Zen profile, downloads
the checksum-pinned KeePassXC-Browser 1.10.4.1 extension, and starts a loopback-only page.
`test_zen.py install` installs the extension through Firefox's add-on manager.
`test_vault.py setup` creates a synthetic KDBX and its native-host manifest, refusing to
replace an existing vault or manifest. `test_vault.py launch` opens the preview.

Pair the browser in its actual extension UI and approve the request in Passwords. The
helpers never grant vault access or fill fields themselves. `test_zen.py verify` checks
that the real extension filled the two expected synthetic values without printing them.
`test_zen.py empty` checks refusal paths. Restore the VM checkpoint when finished.

For save/update checks, use `test_zen.py signup` or `test_zen.py change`, type only
the synthetic account through the real UI, and submit the form. The loopback server
discards submissions and serves only the fixed test pages, never a directory or vault.
`test_vault.py verify-unsaved`, `verify-saved` and `verify-updated` inspect the encrypted
fixture through the native CLI, keeping the decrypted export in memory. They check
consent, persistence, duplicate prevention and retention of the previous password.

The test profile enables Marionette for inspection. It is a test fixture, never a product
profile; no remote debugging, test credentials or loopback server belong in the OS image.

For bounded frame checks, `test_zen.py same-frame` embeds the sign-in page on its own
origin; `cross-frame` embeds `localhost` under `127.0.0.1`; `trusted-frame` embeds the
saved `127.0.0.1` site under an unrelated `localhost` parent. Unlock first and request
filling through the actual extension. Inspect the child fields without writing them.
`multi-user` starts a username-only page, followed by a password-only page; use the real
extension at both steps. These fixtures do not establish real-site save detection.

## Flatpak Zen integration

The VM has Zen 1.23.4b / Gecko 158.0.1 and Fedora's
`xdg-native-messaging-proxy` 0.1.0. They support a standard route:

```text
KeePassXC-Browser → Zen → system native-messaging proxy
                         → keepassxc-proxy → unlocked vault + approval
```

The disposable launch grants only `org.freedesktop.NativeMessagingProxy` D-Bus access
and enables `widget.use-xdg-desktop-portal.native-messaging-proxy` in that test profile.
It does not grant host-command execution or change Zen's persistent Flatpak overrides.
The native manifest permits the official KeePassXC-Browser extension ID. The normal
pairing dialog and per-site access decision are still required.

This D-Bus permission exposes registered native messaging hosts; it is not a claim that
every native host is sandbox-safe. Before making it a default, audit host registration,
extension permissions, consent, profile association/revocation and the supported browser
versions. Requests can appear behind Zen under Wayland; presenting those requests clearly
is part of the remaining integration work.

Primary references: [KeePassXC source](https://github.com/keepassxreboot/keepassxc/tree/2.8.0),
[Firefox native-messaging support](https://bugzilla.mozilla.org/show_bug.cgi?id=1955255),
[proxy scope and security boundary](https://github.com/flatpak/xdg-native-messaging-proxy).

## VM evidence — 2026-10-28

- Three Python patch checks passed. The source build passed eight CTest suites:
  Monet defaults/actions, KDBX 2/3/4, keys, entries, password generation and browser protocol.
- Eight unchanged upstream GUI scenarios passed: creating a vault, adding/editing entries,
  searching, saving, backup saving, locking and menu action state. Qt reports ten passes
  including setup/cleanup, with no failures or skips.
- Live Wayland checks covered wrong-password rejection, explicit unlock after restarting,
  native browser pairing and per-site approval, actual extension filling, denial, a different
  hostname and filling while locked. The last three left both expected fields empty.
- The synthetic vault and native backup had private permissions and no literal fixture
  credentials. An independent copy of the encrypted backup opened successfully. A corrupted
  copy was rejected without modifying the original.
- After replacing/restarting the running preview, the extension needed its **Reload** button
  to reconnect. The association survived and filling worked again. Seamless reconnect still
  needs work; a successful first connection is not proof of robust session recovery.
- Follow-up save/update check: submitting a new login showed the extension's save prompt.
  No entry existed before approval or after cancelling. Approving New saved one account.
  Submitting a changed password preserved the old value until the matching account and
  native update prompt were approved. Cancelling that prompt preserved the old password;
  approving it updated the same account and retained the previous password in history.
  All checks used the real extension and native UI on the loopback fixture. This does not
  establish detection on arbitrary websites. Later bounded frame and two-step filling
  checks are recorded below.
- The extension shows a generic failure message after cancelling the native update prompt.
  The vault remains unchanged, but this wording needs to distinguish cancellation from failure.
  The follow-up's five patch/fixture tests passed; the native app binary was unchanged.

Host evidence is under `target/passwords-preview/` (ignored): `final.log`, `final-open.png`,
`final-locked.png`, `final-browser.png`, `wrong.png`, `browser-access.png`, and
`monet-passwords-linux-preview.tar`. The tar contains the Linux development prefix, exact
patched source with upstream license notices, and bench runtime libraries; it contains no
fixture vault, browser profile or settings. Its SHA-256 is
`343232c29056f1216ad3b1aff3ded21b64d5955f16efa6ebbd8549802a861885`.

Restored `ai-before-passwords-1028` after saving evidence. The VM is running, the fixture
build and browser profile are absent, and the original notes checksum is unchanged.
The save/update follow-up evidence is under `target/passwords-preview/save-update-20261028/`.
Its checkpoint, `ai-before-passwords-switchers-1028`, was also restored and checked:
the preview build/profile are absent and the original notes remain unchanged.

The migration follow-up used the same verified binary and extension in a new disposable
profile, with native pairing and site approval. Same-origin frame filling passed.
With the vault explicitly unlocked, a different-origin child remained empty, and a saved
site embedded under an unrelated parent remained empty with the extension's
"Credential fill blocked in untrusted iframe" message. The five-minute idle lock also
required a new explicit unlock. A two-step login filled its username-only page, then
its password-only page through the real extension. No credentials were supplied through
debugging APIs. Six patch/fixture tests pass; this covers these synthetic forms and frame
relationships, not arbitrary embedded content, real-site detection or a security audit.
Evidence and remaining failures are in [TESTING.md](TESTING.md), under the migration
regression check, and `target/vm-migration-checks/` on the host.

## Next delivery work

1. Complete the Monet welcome, vault creation, account editing and browser-connection flows;
   retain existing validation and recovery. Translate the new text and check keyboard use,
   screen readers, RTL, small screens and large text. The preview's new strings are English.
2. Make browser setup explicit and reversible, with one association per profile, clear site
   permissions, visible requests and revocation. Improve cancelled-update feedback. Extend
   save/update testing to real sites and multi-step forms; test private browsing, hostile
   frames and origins, multiple profiles, lock/suspend/restart and failure recovery.
3. Design optional Windows access. Decide the encrypted vault location and conflict rules;
   test full shutdown, interrupted writes, unavailable/encrypted drives and restoring backups.
   Keep unlocking explicit on each OS. Do not use the EFI trip note for credentials or keys.
4. Add off-device encrypted backup and recovery guidance, import/export checks, and a
   maintenance/update policy. Review the complete integration before enabling real passwords.

Credentials help a person sign in again. Browser cookies, launcher tokens and running
sessions remain owned by their apps; neither passwords nor vault keys enter restoration
checkpoints. A vault does not bypass MFA, account policy or expired sessions.
