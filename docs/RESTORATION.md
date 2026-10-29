# Restoring work after Windows

Editor, Files and Zen restoration are wired into the existing **Open your apps again** setting.
Before a Windows trip, `monet-quick remember-apps` captures running app IDs and KWin window
geometry and desktop assignments. At the next Monet boot, `trip-apps-again` reopens them
and places new windows. Up to 64 eligible apps are retained (previously only twelve).

Kate and KWrite processes now have independent checkpoints and launch receipts, with
per-window document ownership for native window groups. `monet-editor-session` reads saved local tab paths, their order and active tab,
the active pane, and known cursor/scroll positions for active and inactive tabs through a bounded native
metadata query in the image's patched editors. Nested horizontal/vertical splits retain
their hierarchy and relative sizes. Generic unpatched editors retain the bounded two-pane
accessibility adapter.
No document text, window titles, search history or unsaved buffers are read or copied.
The native adapter identifies the active pane directly, including repeated views of the
same document. On unpatched builds, background panes use Qt's current-file D-Bus property: a selected tab's
accessibility "focused" flag does not identify the active pane reliably.

Recovery writes a private 0600 Qt session file and opens each editor process separately.
It verifies the reopened tab grouping/active pane before completing the receipt, restores
cursor positions in new views still at offset zero, and uses the existing KWin
placement code for geometry, desktops and minimized state. Existing windows and cursors
are left alone. Launches carry a boot/PID/session-token receipt, so a slow launch is reused.
Named Kate sessions are not replaced or renamed. The session format follows
[Kate's native restore path](https://github.com/KDE/kate/blob/master/apps/lib/kateapp.cpp)
and [view configuration](https://github.com/KDE/kate/blob/master/apps/lib/kateviewspace.cpp),
verified in Kate/KWrite 26.08.1 under Wayland.

Missing files are excluded from launch arguments/session documents. Their paths stay in
the checkpoint even after the other editor windows have reopened. **Retry documents** in
Settings rechecks the files, uses the original live editor when available, verifies the
opened tabs, and removes only completed paths. It does not replay completed sibling windows
or documents the person has already reopened. If the original editor has closed, only its
remaining documents open in a new window. Late files are retried explicitly, not on another
automatic invocation. Legacy single-window captures also keep missing-file recovery pending.
If one window was manually closed while its process still owns other restored windows,
Retry recreates a window inside that process for its remaining files. Its available panes,
tab grouping and known cursor positions return; documents already open in a sibling reuse the same
objects, including unsaved edits. Existing windows keep their layout and contents.
The helper commits an exact-ID replacement request before calling the editor, so an
interrupted run or uncertain reply reuses that operation. A resumed request does not move
or refocus a window that already exists. For a newly created window, compositor activation
is corrected only if that window took focus and the pointer, desktop and activity are unchanged.
Switching to another window or moving the pointer prevents that correction.

The native automatic recovery path supports up to 16 main windows per process, up to 16 panes
per window and 200 tab entries across the process, including a single pane. The splitter tree is bounded and validated; each pane
must occur exactly once in traversal order. Legacy flat checkpoints remain readable.
Missing-file panes are pruned without flattening the surviving branches. Unsupported
or ambiguous trees use the existing app-owned fallback;
the older single-window native-file parser still respects the open-document count and
excludes stale closed-tab entries. Remaining work includes tab-limit-hidden and
remote/untitled documents.
The unpatched adapter also lacks nested splits and ambiguous background splits showing
the same document. A late file added
to an existing window follows the editor's current pane; recovery does not rearrange the
person's newer layout.
Known inactive-tab positions are saved without selecting tabs or creating extra views.
Recovery keeps them pending until the tab is first opened, separately for each pane and
window even when a document is shared. Capturing another departure before opening the
tab retains that pending position. An optional parallel `cursors` list records bounded
offsets or null for unknown positions; the active tab continues to use `cursor`, and
older checkpoints remain readable. Existing nonzero live cursors are left alone.
Per-tab scroll metadata retains the top line, wrapped row, horizontal pixel offset and
view wrap mode. Lazy views apply it after their initial layout settles; user input takes
priority. Scrolling alone also protects an existing view from repeated restoration, even
when its cursor remains at zero. Pending positions follow Save As and repeated departures.
Ordinary and rectangular text selections also follow Save As and remain pending for hidden
tabs. Coordinate metadata keeps the selection range, cursor direction and rectangular mode;
no selected text is copied. New views restore selections before scrolling. Existing
selections and block mode protect later choices. Normal ranges clamp to shortened files,
while rectangular columns can extend beyond line ends as they do in the native editor.
The image also preserves up to 1,024 cursors per view, including independent selection
ranges and anchors, mixed selected/unselected cursors, and secondary-only selections.
These coordinates use the same pending state for hidden tabs and follow Save As, replacement
and Retry. Native input-mode restrictions remain in effect. Shortened files clamp and
coalesce coincident cursors; repeated requests respect later cleared selections/cursors.
Native folds, including nested ranges and explicitly unfolded views, follow Save As,
hidden tabs, replacement windows and late-file Retry. Only ranges and the editor's file
checksum enter the checkpoint. Changed files and modified buffers do not receive stale
folds. Later unfolding at caret zero survives repeated requests. Metadata is bounded to
1,024 ranges and 64 nested levels per tab. The image's paired KTextEditor fix preserves
persistent folded plugin ranges, so unfolding retains their anchors.
Late-file Retry carries the saved position into the new tab in the current pane. When
the same file had several views, it uses the original active pane's position first,
then the first saved occurrence. Missing old pane membership is not reconstructed in
an already edited window. Shorter files clamp the offset to the end of the document.
Retries can add up to 200 local files at once. Existing and newly added tabs must still fit
the process's 200-entry limit; a request exceeding that budget stays pending. The separate
100-tab pane bottleneck has been removed, so large late-file sets can return without changing
the person's current splits, selected tabs or visible cursors.

When native window identity is available, a missing-file retry now targets that exact
window through `monetReopenDocuments`. It adds tabs to the window's current pane, keeps
its selected tabs and cursors, and reuses shared unsaved document objects. Files already
open in another pane of that window, including aliases, are not duplicated. A rejected
identity or failed targeted request never falls through to the application's active
window. Older single-window adapters retain their existing fallback. Native window groups
retain an explicit old-to-new UUID mapping and per-window pending lists through recovery.
When only one window's files are missing, it opens as a separate empty window; Retry fills
that exact window once its files return. When every saved file is missing, the group waits
without launching blank replacements. Intentionally empty source windows can still reopen.
Window dimensions remain subject to the application's minimum size; in the VM, KWrite
widened a small empty window when adding its first document view.
Native replacement records are bounded to 64 per process and retain closed-window
tombstones. Each explicit Retry persists an attempt ID before dispatch. If its replacement
closes before the helper confirms the UUID, the native closed reply finishes that attempt
without consuming its pending files or reopening it. A later explicit Retry can create a
fresh attempt. Interrupted attempts reuse their ID; new IDs cannot duplicate a replacement
that is still live or being created. Older durable requests remain readable.

The multi-window adapter is wired into automatic departure and recovery.
`monetEditorWindows` obtains exact compositor UUIDs in
one bounded query, then reads each main window's tabs/panes and known cursor positions. It rejects
missing, ambiguous or stale IDs; cursor restoration validates every requested window
before changing any and leaves existing nonzero cursors alone. The Python helper can
write and launch one native session for several windows, sharing document IDs. Live
Kate/KWrite checks cover this path and its single-window compatibility. The new native
group-departure protocol uses Quit to keep all sibling windows and shared buffers alive
until save prompts succeed, then writes one final receipt containing every window's exact
UUID and current paths. Cancel or controller loss invalidates an outstanding close, even
if its save dialog is subsequently accepted. Changed window membership or failed receipt
writes veto the whole exit. The recovery helper validates group membership before arming
and commits the final per-window paths only after the entire process closes. Reopening
uses one native process session and verifies its ordered window layouts before mapping
new compositor IDs to the original frames. It never guesses ownership from window titles
or KWin enumeration order, and leaves pre-existing windows untouched.
The image now builds the [native compositor extension](../image/window-identity/README.md)
against its assembled runtime. Its package/binary guard rejects mismatched builds before
installation, and corresponding source ships with the module. It loads by default unless
the user's KWin settings explicitly disable it. VM checks exercised the packaged module
in an isolated compositor, including disabled preferences. Automatic capture, protected
departure, Save As, first-save, cancelled-switch recovery, exact placement and late-file
retry have been exercised in native Kate/KWrite. A full image and Windows round trip remain untested.

Before Windows preflight, protected departure watches every supported editor window,
including new windows of checkpointed editors while another app blocks the switch. The
image's [native editor integration](../image/editor-recovery/README.md) arms each process
with the departure ID. After the editor's own save prompts succeed, its close/Quit path
writes a private per-process receipt: current saved local paths, tab order, active tabs and
panes, known cursor positions and the nested splitter tree. Save As therefore retains new paths even
when several instances share the anonymous session file. Temporary paths scheduled for
deletion and discarded untitled documents are omitted; a permanent Save As copy remains.
No document text, recent-file history or plugin configuration enters the receipt.

Receipts are atomic, mode 0600, in a mode 0700 runtime directory. Their departure ID, app,
PID, schema and allowlisted fields are validated. Monet reads them only after the process's
windows disappear, then commits the metadata to the durable checkpoint before restart
acceptance or cancelled-switch recovery. A receipt write failure vetoes the native close;
a missing or invalid final receipt cancels switching. Cancel disarms live editors. Runtime
receipts live only in the user's runtime directory; the durable checkpoint supplies later
Windows returns after that directory is cleared on reboot.

The generic Linux tarball also works with unpatched editors. Only an unknown D-Bus method
selects the older fallback: a fresh, stable native session file must belong to one instance.
Repeated polls retain its original timestamp. Separate named sessions can refresh
independently; shared anonymous files remain unconfirmed, and a new writer invalidates
earlier exclusive ownership. The fallback never guesses which process saved a shared file.
It remembers other writers observed while waiting, even if they exit before the final read.
An observed change of the watched editor's session cancels the switch and leaves the editor
open; a new switch can capture the new session. The native receipt path does not depend on
session names. Unpatched session changes that happen entirely between polls remain a limit.

An unsupported final layout retains the earlier capture with an unconfirmed warning.
Editors closed before monitoring remain work. Save/Save As dialogs stay in the departure
wait list but do not count as new editor main windows: on Wayland, Qt transients can have
KWin's normal-window flag. First saves, renamed documents, cancelled choosers and an
observed named-session change have been checked live with the unpatched fallback.

Files captures up to 32 local-folder tabs per Dolphin window, including duplicate tabs,
split folders, their order, and the active tab and side. The image's paired native adapter
also reads current/selected paths, expanded folders, scroll offsets/limits, split widths
and custom tab names, including inactive tabs without activating them. It reads metadata
already held by the views; it does not read document contents, enumerate directory contents
or collect navigation history. Loading, remote, ambiguous or oversized native states are
refused. Each ordinary Dolphin process/window has its own checkpoint and launch receipt,
including windows with identical folder tabs; a stale global session file is never copied.

Older builds use the accessibility tree and validate each folder against Dolphin's D-Bus
API, with two matching reads to reject navigation races. This fallback preserves folders,
tabs and the active side only. It is used only when the native method is absent, never when
the native adapter refuses a state. Unsupported capture retains the existing app-only behavior.

`monet-files-session` runs capture in a separate process with a ten-second timeout, a bounded
native D-Bus call and a 600 KB metadata limit. Native and Python validation bound paths,
tabs, selected items (4,096 per pane), expanded folders (256), coordinates and labels. The
fallback also bounds tree traversal. The Plasma environment hook
`monet-accessibility.sh` keeps Qt's bridge available from the next sign-in. This does not
turn on a screen reader or change the user's accessibility preferences. The image includes
the AT-SPI runtime and PyGObject; an existing session needs a new sign-in for normal app
launches to inherit the hook.

Restoration creates a separate 0600 native session and launches Dolphin with an empty
session key: Qt Wayland discards nonempty keys, otherwise silently opening Home. The adapter
uses Dolphin tab format 2 and view format 1, verified against Dolphin 26.08.1 / Qt 6.11.2.
It does not overwrite Dolphin's usual session or change its startup preference. Tabs and
captured view metadata must match before the launch is marked complete and the private
session is removed. Split ratios allow two logical pixels of rounding. Vanished selected,
current and expanded paths are skipped; dangling selected symlinks remain valid and scroll
offsets clamp to the live range. A launch that is still loading is recorded by PID, boot ID and session token,
then reused on retry. Missing folders leave the checkpoint pending rather than opening
an empty or different folder. Matching existing Files windows are left alone and consumed
one-for-one, so one live window does not suppress a second saved window. Recovery starts only
the missing windows, and an unavailable folder does not replay windows already restored.
Existing windows match by their folder/tab layout; their newer selections, scrolling,
split widths and labels are left alone.

The image builds the Files executable and private library together from its installed
distribution's source RPM, including downstream patches. Original hashes, transitive runtime
package versions, native exports and linked features must match before installation. Build
inputs and corresponding source ship in `/usr/share/doc/monet-files-recovery/source.tar.xz`.

Zen uses its own native session in each original Flatpak profile. `monet-browser-session`
finds the live profile through its process's profile-lock descriptor, rather than guessing
from the default profile. It reads bounded Mozilla JSONLZ4 files using the image's `lz4-libs`
runtime. Monet stores only the profile identity, timestamps, counts and an opaque verification
digest. It never copies or edits browser preferences, cookies, credentials, tab URLs or the
session blob. The browser's private windows are excluded from its normal native checkpoint;
private launches, permanent private browsing and unexpected private payloads are skipped.

The checkpoint allows 16 seconds for Zen's normal 15-second save interval. This is a bounded
wait, not a guarantee that every in-memory change has reached disk: browser idling can delay
saves. A final normal shutdown write is accepted if it belongs to the captured browser session.
Deleted, corrupted or replaced native sessions are not recovered from older backups by Monet.
Zen reopens with `--new-instance --profile` and keeps ownership of its window grouping and
geometry. When **Open previous windows and tabs** is enabled, a fresh native recovery write
must match the expected normal tabs before Monet completes the launch receipt. Slow launches
remain pending and are reused on retry. An already-open profile is left alone; it does not
prevent another captured profile from reopening. Private/unsupported profiles are skipped
independently, and a failed profile does not replay its successfully restored siblings.

For multiple normal windows, Zen 1.23.4b takes synchronized tabs from `zen-sessions.jsonlz4`.
The expected digest follows that native sidebar and its all-tabs/pinned-only/off preference.
Verification still reads the actual reopened windows from a fresh Mozilla recovery write;
it does not treat the unchanged sidebar file as proof that windows reopened. Zen's internal
empty-tab placeholders are excluded, while user-created blank tabs remain part of the check.
Neither native session file is copied or edited. Missing, private or malformed sidebar data
does not fall back to an older backup. A native session with fewer windows than captured is
not reported as full recovery.

Zen's own tab-restore preference is respected. When it is disabled, Monet reopens the original
profile normally; that counts as an app launch, not verified tab restoration. Zen's session
manager removes unpinned tabs when this option is disabled, even though its Firefox base has
other resume flags. No temporary preferences or profile-file replacements are used to bypass it.

Window placement uses KWin's Wayland scripting API. It stores logical coordinates, output
names and work areas, plus minimized/maximized/fullscreen state. A missing monitor falls
back to an available output; window sizes and positions are clamped to its work area.
Only newly opened windows are moved. Existing apps are left alone, which also prevents
duplicate launches when Plasma or the app has already restored itself.

Windows also retain their virtual-desktop memberships, all-desktops flag and above/below
state. Existing desktop IDs are preferred, with an unambiguous name fallback; removed
desktops are not recreated over a person's changed configuration. The first automatic
return restores stacking order, the selected desktop and the active restored window when
the desktop remains untouched. Mouse movement, desktop/activity changes or another visible
window prevent that final focus/order change. Manual Retry does not reshuffle the desktop.
Already-minimized background apps remain untouched. Browser placement is only applied when
a profile has exactly one captured window and one verified normal browser window; ambiguous or
private/multiple-window cases remain owned by the browser.

Recovery launches are started together and verified cooperatively on the Qt thread. A slow
browser checkpoint or failed app no longer postpones launching the remaining apps. Each
adapter retains its deadline and durable completion receipt. Ordinary windows with saved
geometry must show two stable startup observations before placement, allowing their own
initial resize to finish. The departure arrangement is refreshed after the native-save
wait, so a window moved during that wait does not return to its earlier position.

The switch command stops before changing firmware boot state if its recovery helper
cannot run or save the checkpoint. Unsaved-work protection also runs when restoration is off.

## Leaving safely

`monet windows` and `monet play` start `monet-leave` in a single `monet-switch` user service.
That service survives closing the requesting terminal/app and rejects overlapping switches.
It preserves the caller's XDG data/config/state directories. After capturing the checkpoint,
it starts root's guarded preflight. Root checks/prepares Windows, announces readiness and
waits on a pipe; it has not written a launch request, BootNext or trip record at that point.

Before each close pass, the user service asynchronously reads logind's shutdown inhibitors.
Blocking and weak-blocking requests keep the switch waiting, with the app and reason shown
as plain text. Sleep-only and delay inhibitors do not hold this stage. A failed, malformed
or stalled query cancels the switch without approving restart; Cancel stays responsive
during the query. Editor watches continue while background work holds departure.

Store download services acquire a shutdown inhibitor before starting their worker and
release it after the queue finishes, including cancellation or service termination. Closing
the Store window does not release it. Finish or cancel the transaction in Store, or cancel
the switch to keep working. A lost worker still becomes Interrupted and needs Retry.

The user service then sends normal KWin close requests to application windows one at a time.
The app owns Save, Discard and Cancel; Monet never edits its document contents, retries its
close request in a loop or forces it to quit. A veto, an unresponsive window, or a newly
opened window keeps the switch waiting. A failed window inspection cancels it. Desktop
shell/broker windows and the switch window itself are excluded. Unlike Plasma's native
[closeWaylandWindows flow](https://github.com/KDE/kwin/blob/v6.7.5/src/sm.cpp), this path has
no timeout that accepts shutdown while windows remain open. When a browser process has
multiple windows, Monet asks the person to quit it through its own menu instead of closing
windows individually: the browser must preserve them together in its native session.

**Cancel**, Escape or closing the switch window closes root's input pipe. Before acceptance,
worker death also produces EOF and cannot authorize a reboot. Choosing Cancel in an app's own prompt leaves
its window open and the switch waiting; use Monet's Cancel button to finish cancelling.
Once no blocking background work is reported and every relevant window is gone, the worker sends one explicit acceptance and disables
Cancel. Only then does root write the launch request/firmware target and request a firmware
reboot with [`--check-inhibitors=yes`](https://www.freedesktop.org/software/systemd/man/latest/systemctl.html#--check-inhibitors=).
A failed request uses the existing firmware/trip cleanup.

After cancellation or restart failure, supported apps that already closed are reopened from
the checkpoint, without relaunching apps still running or reshuffling focus/desktops. This
exception is bound to the exact checkpoint and departure boot; it does not permit replay
on an unrelated later boot. Pending recovery remains available in Settings on this boot.
Off still prevents reopening. Some windows may have closed before another app vetoed:
recovery retains the existing adapter limits, including private browser sessions and
unsupported window grouping. It is not an undo of every application's close operation.

The checkpoint at `~/.local/state/monet/trip-apps.json` is replaced atomically with mode 0600.
It contains paths, geometry and the browser profile identity, not document contents, window
titles, cookies or browser session contents.
A lock prevents concurrent restores. Confirmed launches get durable receipts, while an app
that fails to create a window stays pending for a later retry. Running
`monet-quick trip-apps-again` retries pending apps without repeating completed entries.
The off switch clears the checkpoint. A checkpoint from this same boot is not replayed
unless the departure worker explicitly marks that exact attempt cancelled.

New version-3 checkpoints have no elapsed-time expiry. `remember-apps` prints the saved
checkpoint ID; the CLI passes it to the privileged switch helper, which records that exact
ID and the departure boot in `/var/lib/monet/trip.json`. On a later boot, `check-switch`
durably writes `/var/lib/monet/trip-return.json` before consuming the trip. That receipt
contains only opaque checkpoint and boot IDs, readable by the signed-in account. It also
permits restoring work when a requested reboot returned to Monet because Windows failed
to start. A same-boot check or a firmware read error never confirms a return.

The matching receipt makes recovery eligible after a long Windows session, days switched
off or a wall-clock correction. Unfinished recovery retains a private copy of its receipt,
so another trip or Monet reboot cannot expire pending apps. A missing or mismatched receipt
keeps the checkpoint unopened and shows an unconfirmed-trip explanation; it does not delete
the work. Once confirmation is available, Settings enables Retry. Off and Dismiss still
clear the private checkpoint. Version-2 and app-ID-only checkpoints remain readable with
their original twelve-hour limit.

If saving the system trip or requesting the restart fails, the helper removes the trip
record before clearing its firmware request/BootNext and restoring Monet as the default.
An unrelated reboot cannot turn that cancelled switch into a confirmed return.

## Reviewing a return

Settings → Play on Windows → **After your last return** keeps the latest return summary,
even after every launch is complete. The **Back in Monet** notification opens that card;
searching for restoring work reaches it too. One notification is queued per trip, and it
follows the person's notification preferences. It does not announce full restoration merely
because an app opened a window.

Each app reports its actual outcome: a confirmed window, verified Files tabs or Zen tabs,
normal browser startup with tab restoration disabled, already-running app left alone,
missing app, unconfirmed launch, unavailable browser session, or missing saved documents.
Partially restored window/profile groups are reported as partial; Retry handles only pending
groups. Private/unsupported browser checkpoints stay closed. Editor outcomes confirm a window and
requests for existing saved files, not the editor's unsaved buffers or every document tab.

**Retry pending** and per-app **Retry** run through one user service, so closing Settings
doesn't stop them. The restore lock, completed receipts and trip identity reject duplicates
and stale buttons. Workers retain the calling account's state directory. **Open app** uses
normal startup, raising an existing window when possible; it does not replay private browser
data. **Dismiss** forgets the list and any remaining recovery checkpoint, never personal files.
Missing documents are listed by filename with a route to Backups; reconnecting a drive does
not yet automatically reopen those individual documents in an already-restored editor.

The private `trip-apps.return.json` survives checkpoint completion. Outcomes are first committed
inside the checkpoint, then copied to that summary; an interrupted summary write cannot lose
a completed launch receipt. Busy state follows the actual lock/service, not a stale boolean.
Same-boot checkpoints stay hidden until explicitly cancelled; expired legacy checkpoints
and unconfirmed new trips explain why work wasn't replayed.
The notification marker `trip-apps.notice.json` stores only the trip identity. Turning restoration
off clears recovery metadata. Pre-switch prompts explain that unsaved changes/private tabs
aren't captured and other downloads may stop during restart. Store transactions hold the
switch until they finish or are cancelled; Store's Downloads remains their recovery route.

## Current limits

- Apps receive normal close requests so they can protect unsaved work, and shutdown
  inhibitors protect background work, including Store's download services. An app that closes
  without warning, or has only background work and no shutdown inhibitor, cannot be checked
  generically. Unsaved buffers, editing history and private browser sessions are not captured.
  Save As during the close prompt uses per-process receipts in the image's patched editors;
  shared anonymous sessions on unpatched editor builds remain unconfirmed. Native receipts
  exclude paths the editor will delete on exit, while retaining permanent Save As copies.
- Editors support up to 16 windows per process, 16 panes per window and 200 tab entries
  across each process in the image's native Wayland adapter. Known inactive-tab cursors
  and scroll positions are retained, along with ordinary/rectangular selections and up to
  1,024 cursors/selection anchors per view in supported native modes. Remote/untitled
  documents are not captured. Native folding
  is retained for unchanged files, including persistent folded plugin ranges in the image's
  paired native engine bundle.
  Unpatched builds retain the two-pane limit. Native files without a supported layout retain local paths; new/ambiguous tab
  arrangements can fall back to one pane and the first tab.
- Files supports ordinary Dolphin windows and up to 16 main windows sharing a process in
  the native Wayland adapter. Exact surface IDs must match the compositor's complete window
  set; missing/ambiguous identity stays unconfirmed. Each window has its own capture and
  launch receipt and may reopen in an independent process. Cancelled switches preserve
  surviving window IDs, including newer selections or changed folders. Pending launches
  reserve their live windows before identical-folder siblings can match them.
  Remote/search/trash locations and more than 32 tabs per window
  remain unsupported and are reported as unconfirmed. Navigation history is not captured.
  Older builds require one window per process and the accessibility bridge, and do not capture view metadata; when
  both split sides show the same folder, that fallback selects the primary side. Localized or
  changed accessibility structures must validate successfully; broader language/RTL testing
  is still required.
- Browser support covers multiple running Zen Flatpak profiles and their normal windows.
  Other browsers retain their normal startup behavior. Private-only launches and save intervals
  above 15 seconds are skipped. Native recovery must be intact; unsaved forms and every last
  navigation are not guaranteed. Browser spaces, custom split/group layouts and monitor changes
  need further live testing. A redirected or changed tab can keep verification
  pending; it will not cause repeated launches while the browser remains open.
- Generic apps launch once. Additional windows are placed only if the app itself reopens
  them in time; this is not full multi-window session restoration. Existing virtual desktops
  are supported, but activities and custom tiling trees are not recreated. Missing document
  paths are skipped, not recreated as empty files.
- The recovery list covers the current adapters; reopening individual missing editor documents,
  friendly names for removed apps captured by older checkpoints, and screen-reader/RTL review
  remain follow-ups. App-only legacy checkpoints retain their older restoration behavior.
- The live test closes/reopens controlled test editors in Monet. A complete Windows round
  trip, hardware sleep/wake and actual multi-monitor scaling are still release checks.
- Trip-confirmed recovery requires the updated CLI and helpers together in the system image.
  Copying only the new helper into an image with the old CLI cannot bind a new checkpoint.

## Verification

`python tools/vm.py tests tests.test_browser_session tests.test_settings_feedback tests.test_resume
tests.test_files_session tests.test_look.GlobalThemes.test_monets_look_can_be_put_back
tests.test_look.YourAppsAgainAfterWindows` exercises private atomic replacement, malformed
state, closed-tab exclusion, duplicate prevention, stale/same-boot behavior, off, concurrent
restores, launch failure/retry, clamping, native browser session verification and repair feedback.

On 2026-10-27 in the Monet Hyper-V VM, two saved test documents reopened as Kate and KWrite tabs
alongside the original saved document. The window returned to x=70, y=100, 820×600 logical
pixels. A failed launch retained its checkpoint, and a successful retry consumed it.
No reboot or Windows return was claimed by this test. The pre-change checkpoint is
`ai-before-painted-resume-1027`.

The Files slice was tested on the same date after checkpoint `ai-before-files-resume-1027`.
A controlled Wayland window with three tabs (including a duplicate folder), a two-folder
split, the second tab active and its right side active was captured, closed and restored.
Folder names containing spaces, a literal percent sign and `å` survived. The restored tree
matched exactly, KWin reported the saved x=70, y=100, 820×600 geometry, and the checkpoint
was consumed only after verification. The 25 targeted editor/Files/setting tests passed,
including timeouts, malformed state, private native streams, pending-launch reuse, duplicate
prevention, off during capture and geometry protection for existing windows.

The Zen slice was tested on the same date after checkpoint `ai-before-browser-resume-1027`,
against Flatpak Zen 1.23.4b. An isolated profile with two normal tabs and a separate private
window was captured, cleanly closed and reopened through Monet's restore adapter. Both normal
tabs returned, the private window stayed closed, and the verified receipt was consumed. With
browser restoration disabled, the original profile reopened normally and the preference
remained disabled. Test-only Marionette access drove native browser actions and flushed the
session checkpoint; the production adapter enables no debugging interface. All isolated test
profiles and their processes were removed. The 44 targeted tests above passed without skips.

The Settings repair was also clicked in the live VM: its completion message and **Put back
again** remained visible. Automated QML tests cover the busy state, ignored duplicate clicks,
completion lasting beyond the old four-second timeout, and failure/retry behavior.

On 2026-10-28, an isolated return checkpoint in the VM reopened a saved KWrite document and
reported a missing second document and an uninstalled test app. The notification's **Review
return** action opened the correct Settings card from notification history. Installing the
controlled test app and pressing **Retry pending** opened exactly one window, left KWrite's
PID unchanged, and kept the results after completing the checkpoint. **Open app** raised the
existing test window without a second process. At 200%, the card remained readable and Tab
reached Dismiss directly; Enter removed the metadata while the saved document stayed intact.
Scale, Settings size and widget positions were restored, test processes/launcher were removed,
and the user's notes checksum stayed unchanged. This was a controlled return simulation,
not a Windows reboot or hardware switching-speed measurement.

Compatibility references: [Dolphin tab serialization](https://github.com/KDE/dolphin/blob/v26.08.1/src/dolphintabpage.cpp),
[view serialization](https://github.com/KDE/dolphin/blob/v26.08.1/src/views/dolphinview.cpp),
[accessible folder descriptions](https://github.com/KDE/dolphin/blob/v26.08.1/src/kitemviews/accessibility/kitemlistviewaccessible.cpp)
and [Qt accessibility](https://doc.qt.io/qt-6/qaccessible.html).

The VM uses a user-level bench installation because its system image is immutable. Visual
changes and helper tests are applied there. The installed `/usr/bin/monet` still locates its
system helper for real switches; the complete flow needs an image containing this checkout.

On 2026-10-28, the workspace-return slice passed 71 targeted recovery/Settings tests. A live
simulation closed and reopened two controlled apps and one isolated KWrite document across
two virtual desktops. Window sizes/positions, minimized state, desktop assignments, stacking
and active window matched; the saved document reopened. The restore portion took 2.07 seconds
in this run, excluding native checkpoint capture, sign-in, boot and any Windows trip. Existing
minimized user windows retained their IDs, geometry and state. The added test desktop and
test processes were removed, and the notes checksum stayed unchanged. `cargo check` passed
for the Linux target; the new switch failure guard still requires an image build/boot check.
The KWin integration uses the documented [workspace/window scripting API](https://develop.kde.org/docs/plasma/kwin/api/).

On 2026-10-28, 78 focused Linux VM checks passed, including `tests.test_trip_lifetime`
and the existing editor/Files/browser/workspace/return-summary regressions. New tests cover
a month-long absence, backward clock changes, exact trip matching, delayed confirmation,
partial recovery across another trip/reboot, off/dismiss and no duplicate completed launches.
All 63 Rust workspace tests passed in the VM, including system receipt persistence,
same-boot rejection, failed Windows startup, failed receipt writes, malformed firmware
and cancellation before an unrelated reboot. Linux-target Clippy also passed. These are
controlled tests; no Windows reboot, installed-image upgrade or real-hardware flow was run.

The unsaved-work slice on 2026-10-28 passed 82 focused checks plus six Qt cases in a separate
process, and all 65 Rust workspace tests. Live Wayland testing used an isolated KWrite profile
and document and a stand-in that implements the privileged pipe protocol without firmware
access. Cancelling the editor's save prompt kept its PID and unsaved text intact for 172 seconds
without an acceptance. Escape in Monet's window sent EOF; the closed terminal reopened once
and the editor stayed running. A second attempt saved the text before sending exactly one
acceptance. A third simulated restart failure reopened the saved document and showed an error.
The original notes checksum was unchanged. The VM was returned to checkpoint
`ai-before-unsaved-switch-1028` after testing. No actual Windows restart is claimed.

A live shutdown-inhibitor probe could not acquire its lock because this VM required interactive
authorization; its dry run is not counted as inhibitor validation. Real root/firmware operation,
other app families, screen-reader and RTL checks remain release work.

The multiple-window/profile slice on 2026-10-28 adds `tests.test_multi_restore`. It checks
independent profile capture, a live profile alongside a missing one, partial failures,
interrupted launches, duplicate Files windows, original window identity after cancellation,
malformed groups, missing/private sidebar data and Zen's window-sync preferences/placeholders.
Legacy single-window/profile checkpoints remain covered by the original suites. All 102
focused recovery/language tests plus seven isolated Qt cases passed; syntax and catalog
consistency checks passed too.

Live tests used three ordinary Dolphin windows, with duplicate folders, duplicate tabs and
a split view whose right side was active. Two windows closed and reopened with their saved
tabs, split state and distinct geometry; the third retained its window ID/PID. A retry did
not create another window. Two isolated Zen 1.23.4b profiles then returned with three normal
windows and twelve real tab entries (including pinned tabs and a user blank tab). Native
Quit closed each profile as a unit; the private window stayed closed. Both actual native
session digests matched, and the fixture preferences were unchanged. A separate partial
return reopened the two-window profile while the other profile's PID remained unchanged.
Test-only Marionette prepared the disposable browser fixtures; production uses no debugging
interface, changes no browser preferences and copies no browser session files.

The tests ran under Wayland without a Windows reboot. The VM was restored to
`ai-before-multi-restore-1028`; its original windows returned, the disposable fixtures were
removed and the user's notes checksum remained unchanged. Multi-monitor scaling, custom
browser spaces/splits, other browser families and editor document-to-window grouping remain
separate release/backlog checks.

The next editor slice on 2026-10-28 passed 111 focused VM tests covering editor, Files,
browser, trip-lifetime, cancellation, workspace placement and the Settings recovery UI.
Live fixtures verified two separate Kate windows plus KWrite; horizontal/vertical splits,
both active-pane choices, tab ordering, visible cursors, distinct geometry, minimized state
and multiple KWrite tabs. Removing a fixture file after capture kept its recovery pending;
returning it and retrying reused the editor, and another retry created no extra window.
A cancelled switch preserved a surviving editor's unsaved buffer, PID, window ID and frame,
while reopening its closed sibling and KWrite. Notes' checksum stayed unchanged.
The VM was restored to `ai-before-editor-recovery-1028` after these controlled Wayland
checks. No firmware/Windows reboot, real removable drive or installed-image upgrade was tested.

The Save As slice on 2026-10-28 passed 132 focused VM tests, including an isolated Qt
departure suite. Live native dialogs verified first-save recovery, renaming while switching,
cancelled Save As, and reopening a renamed document after cancelling the switch with another
unsaved editor still open. Existing files and the unsaved survivor were preserved; retries
created no extra windows. A live D-Bus teardown race was fixed and covered by regression.
The fixture used a guarded-pipe stand-in without firmware/reboot access; this is not a real
Windows return. Shared anonymous sessions remain visibly unconfirmed.

The nested-editor slice on 2026-10-28 passed 159 focused VM regression checks and built
the native Kate/KWrite component against KDE 26.08.1. Live native dialogs and production
recovery helpers verified a four-pane nested layout and a three-pane row: renaming via
Save As, first-save during closing, cancelling the file chooser, cancelled-switch recovery,
tab order, active panes/tabs, visible cursors and relative splitter sizes. A missing pane
left the remaining tree intact and stayed pending; retry reused the returned editor, with
no duplicate windows. Old flat single/two-pane checkpoints, KWrite, repeated same-document
panes, nonzero-cursor protection and an unpatched editor's accessibility fallback also passed.
These are controlled Wayland checks, not a full image build or a Windows firmware round trip.
The VM was restored to `ai-before-nested-editors-1028`; fixtures and the build environment
were removed, and Notes retained its original checksum.
The VM was restored to `ai-before-save-as-1028`; the fixture directories were gone and the
original Notes checksum was unchanged.
