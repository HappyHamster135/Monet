# Native PDF restoration

This is an Okular restoration adapter whose production bundle builds and installs in the VM.
The checkout's switching controller captures, protects and restores supported windows.
`patch.py` adds metadata, protected departure and private session
reopening to the distribution's shell, using its PDF/document plugin unchanged.

`monetDocumentState` reports the actual tab order, selected tab, local paths, one-based
page numbers and modified flags. It reads all tabs without selecting them. Empty windows
are explicit; unsupported, loading or remote documents return `null`. The bounded format
contains no document text or annotation contents.

`monetDocumentWindows` associates up to 16 windows with exact KWin Wayland identities,
using the existing Monet window-identity plugin. Each window has a separate D-Bus object
under `/MonetDocuments`, so closing the first window does not hide the survivors.
Missing or ambiguous identities return `null`; single-window capture refuses a shared
process with multiple windows. There are at most 32 documents per window and 2 MiB in
the complete metadata response.

`monetDocumentDeparture` arms the current windows for one switch token owned by the caller's
live D-Bus connection. Each window writes its final paths and pages only after its native
save/discard prompts succeed. A private, bounded, atomic receipt belongs to that token,
process and exact window. Failed receipt writes veto closing. Cancelling or losing the
controller invalidates an in-progress close, including a late Save response. Native prompts
can change the selected tab, so the receipt retains the selection from before the prompts.
Receipt readers reject links, special files, unsafe permissions and mismatched identities.
Windows created during departure veto closing until the same controller registers their
identities. Repeated registration retains already captured closed-window receipts.

Private native sessions retain duplicate tabs, pages and the selected tab in independent
processes, without changing ordinary tab/session preferences. All paths must be readable
before opening any file. The helper can persist its private session identity before launch
and rediscover that exact process after interruption. A private file lock prevents competing
launches. Missing files remain pending for explicit Retry; an ambiguous disappeared launch
also requires Retry rather than automatically reopening a window the person may have closed.

`monetAppendDocument` adds a late saved tab to an exact live window without replacing
its existing parts, selecting a different tab or moving the window. The request carries
the current full metadata, one saved tab and a durable attempt ID. Changed live metadata
refuses a new request; identical repeated attempts return their earlier outcome. A weak
pointer to the appended part prevents replay after the person closes it. Closing the
window never redirects the request into a sibling. Missing identity support is unconfirmed,
not proof that a window closed. Attempts are retained for the window's lifetime (at most
128); tabs retain the existing 32-tab bound. No document text enters this protocol.

The controller persists the exact request before calling the Python helper's `append`,
reuse it after a lost reply, and inspect the returned status. `busy` or no reply can still
mean an in-progress native open dialog; they never authorize a new attempt. `unconfirmed`
can mean a partially opened file and also must not trigger a fresh append.

The VM-only fixtures are in `prototypes/pdf-recovery`. `build.sh` builds the shell from the
installed distribution's source RPM. `bundle.py` requires matching runtime package versions
and exact original shell, part, core and PDF-generator hashes before installing. It checks
dependencies and ships corresponding source; only the shell is replaced. The packaged binary
passes the native CLI and return-controller checks; complete-image checks remain.
Capturing a modified flag does not back up unsaved
annotations or authorize closing them.

On 2026-10-29, eight focused checks, the three-window capture fixture and the protected
departure fixture passed in the VM with Okular 26.08.1 and Qt 6.11.2. The departure fixture
uses real annotations and checks saved PDF contents after Save As, Save and Discard, native
Cancel, untouched unsaved survivors, late Save after cancellation/controller loss and a
receipt-write veto. Evidence is under `target/pdf-recovery/departure-evidence.json`;
this does not establish automatic PDF restoration.

The follow-up passed 73 focused Python checks, both native regression fixtures and a real
CLI private-session scenario. Evidence is `target/pdf-recovery/restore-evidence.json`.
The CLI scenario covers duplicate tabs, independent windows, page/active-tab restoration,
Unicode and backslash paths, unchanged preferences, empty windows, malformed input and
missing-file preflight. It does not establish end-to-end PDF switching or retry.

The native late-tab retry follow-up passes 74 focused checks and all three native fixtures,
plus CLI/private-session reopening and actual D-Bus append/repeat checks. Evidence and the
tested source hashes are in `target/pdf-recovery/retry-evidence.json`. This verifies the
primitive, including newer work and closed-tab protection; durable return-controller
integration and production packaging are still required.

The return-controller follow-up passes 124 focused checks and the native three-window
scenario, including cancelled-switch survivors, missing-file return, exact placement and
a lost append reply followed by a fresh controller. Evidence with matching source hashes
is `target/pdf-recovery/return-evidence.json`. The first two full-image candidates predate
this return implementation; installed-image acceptance remains separate.

Production build/install evidence is `target/pdf-recovery/bundle-evidence.json`. The original
document engines retain their hashes, source checks pass, linked symbols resolve and an
older runtime is refused. A build-only Brotli update was caught and corrected in the shared
runtime before the successful build. Metadata reads may retry within their existing child
timeout; writes, append attempts and native save decisions are not replayed by that retry.

The exact packaged `/usr/bin/okular` subsequently passed both native CLI and return-controller
fixtures in a matching isolated VM runtime. Its hash matches the sealed production bundle.
Duplicate tabs/pages, independent windows, selection and geometry, native final receipts,
cancelled-switch survivors, missing-file retry and a lost append reply followed by a fresh
controller all pass without duplicates. Preferences, synthetic files and Notes stay unchanged.
Evidence is `target/pdf-recovery/production-native/packaged-evidence.json`. This runtime check
does not establish a complete-image PDF boot or the remaining office/browser/editor support.
