# Monet Passwords

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
