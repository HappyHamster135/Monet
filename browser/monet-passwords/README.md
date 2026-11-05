# Monet Passwords browser connector

Small GPL-3.0-only derivative of KeePassXC-Browser 1.10.4.1. The existing upstream protocol implementation is retained; this work has not had an independent security audit.

Monet advertises native consent through its authenticated database-hash response. When this capability is present, form submission sends the detected login directly to the native host. The host asks before saving or updating, verifies origin and pairing, and retains the existing vault encryption. The upstream New/Update banner is suppressed for this path. Other compatible hosts retain the original flow.

The background submission gate rejects mismatched tab origins and public HTTP, suppresses duplicate prompts for two minutes, limits concurrent requests, and keeps only salted fingerprints/timestamps in memory. Declining does not write a login. Locked/disconnected requests can be retried; unchanged passwords do not prompt. This adds no polling or persistent background service. Detecting a form submission does not prove the website accepted the login. Unusual forms still require site-specific compatibility testing.

## Reproduce the unsigned candidate

Use Python 3 (standard library only):

```sh
python3 browser/monet-passwords/build.py keepassxc-browser.xpi monet-passwords.xpi
```

The required official upstream archive is:
https://addons.mozilla.org/firefox/downloads/file/5078406/keepassxc_browser-1.10.4.1.xpi

Its SHA-256 must be `ae41157a3f017b0773abba2097d5b0056241631d0a38ad36d68d0b24b1a409c1`. The build refuses another archive or changed hooks, strips upstream signatures, preserves attribution and adds the Monet source. It does not upload, sign or install. The upstream tag source is https://github.com/keepassxreboot/keepassxc-browser/tree/1.10.4.1. Inherited minified third-party libraries are unchanged; all Monet JavaScript is unminified.

Permanent identity: `{d6b46926-af45-4fa5-b746-bd36f68af460}`. It must receive its own Mozilla signature before permanent installation. The optional `--temporary-preview` keeps the upstream ID solely for a local developer-mode replacement; NEVER submit that output for signing. A test-profile restart verified restoration of the original signed connector. `--fixture` uses a separate native-host name and is never a signing candidate.

No extension signature preference is changed. Normal-profile remote debugging is neither required nor enabled. The signed permanent connector needs a new explicit vault pairing because it has its own extension storage. Disable the upstream connector before enabling the Monet connector to avoid duplicate prompts. Keep its stored pairing/settings in place for rollback.

## OS packaging — 4 November 2026

The source tree now includes the previously approved signed 0.1.1 artifact at
`linux/share/monet/passwords/connector.xpi`. `release.json` records its identity,
SHA-256, signing record and hashes of the build inputs. `package.py` verifies
the artifact and refuses changed source before release packaging. The desktop
test job also rebuilds from the pinned upstream input and compares every payload
file with the signed archive (allowing only Mozilla's manifest formatting and
signature records).

Linux release packages, the OS installer and the reversible account-preview plan
include the artifact. The OS also carries this README, license, build recipe and
Monet JavaScript under `share/doc/monet/passwords-connector`. The installer checks
the artifact before changing the system. This is pinning of a reviewed signed
file, not a replacement for the browser's signature verification.

Zen autofill offers **Update Zen connector** when a valid bundled release is
newer than the installed numeric version. Updates retain the extension identity,
pairing and settings, and require Zen's normal approval. Missing, corrupt, newer
or unrecognized versions never cause an automatic reinstall or downgrade. No
background updater or network feed was added. Future connector releases need a
new build, owner-authorized signing, updated receipt and OS package. This pass
has not published a release or installed the new source into the live desktop.

## Data handling

The connector sends website URLs and credentials to the on-device Monet native host for matching, autofill and approval. Mozilla counts native messaging as data transmission, so the manifest declares authentication information and browsing activity, and requires Firefox/Gecko 140 or newer for built-in consent. Monet adds no cloud storage, telemetry or remote credential destination. Existing upstream links/features remain identifiable as upstream; the native host does not support passkeys or TOTP. The local host and desktop UI source is in `linux/share/monet/passwords/`. Never place test credentials or profiles in a review/source package.

Synthetic checks: `node tests/test_browser_autosave.cjs`, plus `tests.test_passwords_browser` and `tests.test_passwords_consent`. Live fixtures use an isolated vault bus and a disposable Zen profile.


## Local signing record — 3 November 2026

With explicit owner approval, candidate 0.1.0 was privately submitted to Mozilla with source and reproduction notes. It was approved and signed, then installed in normal Zen. Signed SHA-256: `8fcd6250f4e0adc27eb07c7a685889b201cfc7db228e957511596848e8b85882`. Mozilla only added signature records and reformatted the manifest; all other bytes and parsed manifest contents match. The owner’s [private version page](https://addons.mozilla.org/en-US/developers/addon/63215ddcb8374935a449/versions/6659407) retains the submission. The upstream extension is disabled, the new identity is paired, and persistence/save/autofill passed after normal browser restart. No public listing, GitHub push or OS release was made. Packaging this signed artifact and an update feed for future OS images remains separate work.

## Multi-step and password-change fixes — connector 0.1.1

Username-first forms carry the submitted username to the password page on the same tab and exact origin. This context is kept only in memory, expires after two minutes and is bounded to 128 tabs, contains no passwords, and is cleared on lock, native disconnect, tab close or origin change. A different entered username never receives the sole saved account’s password. Multiple matches require selection.

Current/new-password field roles are retained even when upstream menus change `autocomplete` to `off`. Autofill leaves new-password and confirmation fields empty. Matching confirmation fields can propose a save/update; invalid forms and mismatched confirmations do not. A password-change form without a username uses an explicit selection or a unique current-password match. Ambiguous accounts require selection. All writes still require native Save/Update approval; declining preserves the saved password.

Validation: 17 live scenarios passed in a disposable Zen profile with a private synthetic vault, plus 27 JavaScript checks and 27 Python browser/consent/fixture checks. These cover two-page and dynamic sign-ins, multiple accounts, current/new/confirm fields, denied updates and lock/origin boundaries. No real passwords were used. The repeatable flow checker is `prototypes/passwords/check_flows.py`; it refuses the desktop bus and normal Zen profile. It requires the isolated fixture setup, loopback server and a temporary `--fixture` connector with single-account autofill enabled. Run `node tests/test_browser_forms.cjs EXTRACTED_CONNECTOR_DIRECTORY` for form regressions.

Private signing update: Mozilla approved [0.1.1](https://addons.mozilla.org/en-US/developers/addon/63215ddcb8374935a449/versions/6659730), zero errors/six inherited warnings. Signed SHA-256: `72ffb607b98999e1e0b680ce347425b2d1cd1e4e7d6629c28c4b079a5cd97d47`. Scripts/assets and parsed manifest exactly match the tested build. The signed local setup artifact is updated with a reversible receipt. After the owner accepted Zen’s update prompt, normal Zen reports 0.1.1 active, signedState 2, enabled and non-temporary. Its installed archive hash matches the verified signed build; native-host setup remains configured. No public listing, push or OS release.
