# Editor departure receipts

Kate and KWrite share libkateprivate. Monet adds a D-Bus method to arm a
departure ID, and hooks the successful native close/Quit paths after save prompts
have finished. A failed private receipt write vetoes closing. No save prompt is
bypassed and no document contents, history or plugin settings are copied.

The receipt contains local paths, tab order, per-tab cursors/scroll positions and the nested splitter
tree (up to 16 panes and 200 tab entries in total, including a single pane). It is bound to the departure ID, app and PID, written atomically
with mode 0600 under the user's private runtime directory. Monet commits it to
the existing private checkpoint before allowing a switch. Cancel disarms live
editors; runtime receipts disappear when that runtime directory is cleared. Unsupported
layouts retain the previous capture with an unconfirmed warning. Automatic departure
supports native window groups when compositor identities are available. A generation check also prevents accepting a native Save
dialog after Cancel from completing the old close request.

`monetEditorState` supplies the same metadata for live capture and verification.
An empty argument is read-only. A cursor restoration request must match all current
pane/tab identities, selections and splitter orientations; it only moves existing
views still at the start, without a selection or later scrolling. Inactive tabs use an optional parallel `cursors` array of
bounded offsets or null for unknown positions; the active entry is null because its
position remains in `cursor`. Older checkpoints remain accepted. Capture reads live
views, pending positions or native saved view positions without selecting tabs.
Recovery stores positions for views that do not exist yet and applies them on first
creation, after shared-view initialization. This preserves separate positions for the
same file in different panes without creating every view eagerly. No document text is returned or changed. Missing files
prune their panes and collapse empty branches without flattening the remaining tree.
Legacy flat checkpoints remain readable; generic unpatched editors retain the bounded
two-pane accessibility adapter.

An optional parallel `scrolls` array includes active and inactive tabs. Each entry is
null for unknown, or `[topLine, wrappedColumn, horizontalPixels, wrapMode]`; coordinates
are bounded nonnegative integers and wrap mode is a boolean or null for unknown. Pending
positions survive another departure before the tab is shown. Native saved view settings
provide only their known line/wrap fields. The first visible layout settles before applying
the position, including KTextEditor's delayed resize, and user input/cursor/selection
changes cancel that pending application. Shorter files and narrower scroll ranges clamp
through the native editor API.

An optional parallel `selections` array preserves ordinary and rectangular selections.
Entries are null for unknown/unselected tabs, or an object with `block` (boolean),
`cursor` (`[line, column]`) and `range` (`[startLine, startColumn, endLine, endColumn]`,
or null when block mode has no selection). Coordinates are bounded nonnegative integers;
range endpoints are ordered. The cursor keeps selection direction and rectangular virtual
columns. Recovery clamps lines and normal columns to the current document while retaining
rectangular columns beyond line ends. It never reads selected text. Lazy selections stay
pending until view creation, after shared-view initialization and before scroll restoration.
Existing selected views and block mode protect later user choices. Native session files
do not supply unknown selections.

Multi-caret selections add an `anchor` (coordinate pair or null) and `secondary`
list to the same per-tab object. Each secondary entry contains its cursor, range and
anchor. Normal mode supports up to 1,024 distinct cursor positions per view; block
mode cannot be combined with extra cursors. Metadata is validated in both helpers
and the native boundary before mutation. The paired engine exposes a private Qt
method to retain anchors and mixed selected/unselected cursors without copying text.
Shortened files clamp coordinates and coalesce positions that now coincide. Native
mode restrictions still apply. A per-view marker prevents later cleared selections
or extra cursors from being recreated by a repeated request.

An optional parallel `foldings` array retains native folding ranges, including nested
folds and explicitly unfolded views. Entries are null for unknown or an object with a
40-character lowercase `checksum` and native `ranges` (`startLine`, `startColumn`,
`endLine`, `endColumn`, `flags`). Coordinates are bounded nonnegative integers; ranges
must be ordered, nonempty, disjoint or nested, with at most 1,024 ranges and 64 levels.
The checksum is the editor's existing file fingerprint. Modified buffers and files whose
checksum changed do not receive stale ranges. View settings round-trip through an in-memory
native config, replacing only `TextFolding`; the checkpoint contains no other view settings
or document text. Folding precedes cursor/selection/scroll restoration. Pending folds stay
with their document through Save As and hidden-view creation. A per-view applied marker
prevents replay from undoing a later unfold at cursor zero. Existing folds protect live views.
The image also builds KTextEditor with a guarded one-line fix that retains both native
persistent/folded flags. Persistent plugin ranges therefore remain available after unfolding,
including nested ranges and repeated recovery. The upstream folding suite includes a
regression that unfolds/refolds those ranges and checks unchanged document contents.

`monetEditorWindows` batches up to 16 Wayland surface
IDs through the [compositor prototype](../../prototypes/window-identity/README.md), then
returns exact window UUIDs and each window's metadata, bounded to 200 tab entries across
the process and 2 MiB. Missing or ambiguous identities fail the whole capture. An empty
argument only reads metadata; a cursor request may name a subset of windows and must
match their complete current layouts. All requests are validated before any cursor moves,
and views that disappear during callbacks are guarded. The returned metadata is captured
again after cursor callbacks.

The Python adapter's `windows=True` capture/start/session helpers preserve one process
and shared document IDs across its windows. Live VM checks cover shared-document Save As,
native reopening, stale identities, targeted cursors and the old single-window receipt.
`monetDepartureWindows` arms a whole native window group. While armed, closing a window
uses native Quit, so all shared buffers and windows survive until the app's save prompts
succeed. A version-2 receipt records final paths and layouts for every original compositor
UUID. A changed window group, missing resolver or receipt failure vetoes the entire exit.
Cancel, or loss of the arming D-Bus connection, disarms the group; accepting an outstanding
save prompt afterwards cannot finish the cancelled close. The Python receipt reader must
explicitly request `windows=True`, so the legacy path cannot mistake a group for one window.
Automatic departure uses these interfaces for process groups and commits their final
per-window paths before switching. Recovery starts one native session, verifies its window
layouts, then maps new compositor IDs to captured frames for exact placement.

`monetReopenDocuments` adds previously missing local files to an exact window UUID.
Requests can include up to 200 paths; existing and newly added tabs must still fit the
200-entry process limit. A request exceeding the remaining capacity is refused before
opening files, leaving them pending for a later Retry.
It validates the complete bounded request before opening anything, reuses existing
document objects (including shared unsaved buffers), and skips tabs already present
anywhere in that window, including file aliases. New tabs go into its current pane;
existing selections, cursors, splits and other windows remain intact. Optional per-file
cursor offsets, scroll positions, selections and folding are applied only to newly added tabs. For a file that had multiple views,
Retry chooses its original active pane's position first, then the first saved occurrence;
it does not reconstruct old pane membership inside a window the person has since changed. It returns no
document text. Missing files, stale IDs and unavailable compositor identity are rejected.
The recovery caller uses this method when native identity is
available. Only an unknown method permits its older application-wide fallback; refusal
or a timeout never does. Group recovery keeps separate owners and pending-file lists.
A window with only missing files gets an empty placeholder if its siblings can reopen;
when all saved files are missing, recovery waits. Retry never redirects a closed sibling's
files into a surviving window.

`monetReplaceWindow` recreates a closed window inside its surviving process. Its request
names the absent window UUID, a live sibling UUID and a bounded editor layout. The whole
request and existing group are validated before files open. An
[in-memory KConfig](https://api.kde.org/kconfig.html) restores native panes using existing
document objects where available; named sessions and surviving views are not rewritten.
The replacement omits unrelated pinned-tab injection and the constructor's delayed focus
request. The Python caller corrects compositor activation only while the previous desktop
choice is unchanged, and never refocuses a resumed request.
New replacement views receive their own saved positions even when shared-document
initialization inherited another window's cursor. Repeated requests do not reapply them.

Requests include an `attempt` ID (32 lowercase hexadecimal characters) persisted before
dispatch. The native cache retains the request digest, absent UUID and guarded window
pointer. Identical retries return the live window UUID, or `closed` once that attempt's
window has gone. Empty replies remain unconfirmed. Changed requests are refused, and a
different attempt cannot duplicate a live or in-progress replacement of the same window.
After a closed reply, pending files remain available for a later explicit Retry with a
fresh attempt ID; automatic recovery never resurrects that window. Older durable requests
without an attempt ID use their absent UUID as the duplicate key and remain accepted.
The cache is bounded to 64 records per process.

`image/Containerfile` builds both libraries against the final runtime. The build
records installed packages (including the direct Wayland client dependency) and the original library hash, checks they remain
unchanged after installing development packages, and patches guarded upstream
hooks. A source or runtime mismatch fails the build. The final image verifies
runtime and binary/source hashes before installing. The engine's direct dependencies and
exported functions, vtables and KTextEditor-owned data are checked against the installed
library; incidental Qt/std template data can vary with development headers. EditorConfig and
KAuth are required in its build. Schema-2 manifests retain both original library hashes;
older single-library bundles remain readable. Every file is verified before either library
is copied. Installation is part of the image build, so a failed copy rejects that image layer.
Generic Linux tarballs keep
the conservative native-session-file fallback for unpatched editors.

The image ships the full patched upstream source, original licenses, Monet build
inputs and runtime manifest under `/usr/share/doc/monet-editor-recovery/`. With
matching development packages, rebuild the extracted `kate-vVERSION` tree using:

```sh
cmake -S kate-vVERSION -B build -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_SKIP_INSTALL_RPATH=ON \
  -DBUILD_addons=OFF -DBUILD_doc=OFF -DBUILD_TESTING=OFF -DENABLE_PCH=OFF
cmake --build build --target kateprivate --parallel 2
```

Rebuild the included `ktexteditor-VERSION` tree first with the same runtime development
packages, EditorConfig and KAuth, `-DCMAKE_SKIP_RPATH=ON`, the installed engine RPM's
optimization flags and Fedora's linker flags, `-DBUILD_TESTING=ON` and
`-DENABLE_PCH=OFF`. Build targets `KF6TextEditor`, `katefoldingtest` and `multicursortest`; run the tests
with `QT_QPA_PLATFORM=offscreen` and `LD_LIBRARY_PATH` pointing at that build's `bin/`.
The full production commands are preserved in `monet-build/build.sh`.

Monet's Kate additions are GPL-3.0-or-later; the KTextEditor fix and regression are
LGPL-2.0-or-later. Upstream files retain their license notices.
Do not copy these libraries between editor/runtime versions. VM tests use
`LD_LIBRARY_PATH` only for disposable editor processes and restore their checkpoint.
