# Native window identity proof

These fixtures test the image's native window identity module, the prerequisite for
restoring multiple Kate windows without matching document titles, positions or focus.
Its production source and guarded build are in `image/window-identity`.

Qt supplies the Wayland surface object ID. This read-only KWin extension resolves
the pair of process ID and surface ID to the compositor's window UUID. No match or
an ambiguous match returns an empty string. It exposes no titles, paths, document
contents or window controls. The existing restoration code does not use this proof yet.

Build against the exact installed KWin/Qt development packages; KWin's plugin ABI
is release-specific. The shipped module is enabled by default. The fixture creates two identical
windows and reports their surface IDs and resolved UUIDs for VM verification. A second
fixture uses two Wayland connections in one process to force an object-ID collision.

## Reproduce inside the VM

Take a VM checkpoint first. Copy this directory to `~/.local/monet-window-build/src`,
`image/window-identity` to `~/.local/monet-window-build/production`, and
`linux/libexec/monet-resume` to `~/.local/monet-window-build/monet-resume`.
Use the VM's rootless Podman; no host install or administrative changes are needed.

```sh
root="$HOME/.local/monet-window-build"
podman run -d --name monet-window-build --network=host -v "$root:/work:Z" \
  registry.fedoraproject.org/fedora:44 sleep infinity
podman exec monet-window-build dnf5 -y install --setopt=install_weak_deps=False \
  cmake gcc-c++ make extra-cmake-modules kwin kwin-devel qt6-qtbase-private-devel \
  wayland-devel wayland-protocols-devel libepoxy-devel libdrm-devel vulkan-loader-devel
podman exec monet-window-build cmake -S /work/src -B /work/build \
  -DMONET_IDENTITY_SOURCE=/work/production \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_SKIP_INSTALL_RPATH=ON
podman exec monet-window-build cmake --build /work/build --parallel 4
python3 "$root/src/start-nested.py" "$root" monet-window-build
# Wait for identity.json to contain two nonempty UUIDs, then:
python3 "$root/src/verify.py" "$root"
python3 "$root/src/verify-collision.py" "$root"
```

The start script leaves KWin's plugin preference unset to test default loading. It
compares the installed and build-container package versions and
KWin/Qt/Wayland binary hashes, checks dynamic linking, then starts an isolated nested compositor
with a fresh D-Bus session. The plugin never loads in the VM's main compositor.
The tests write `verified.json` and `collision-verified.json`; restore the checkpoint
after saving those results. The VM supplies Python's existing PySide6/PyGObject packages.

To check an explicit disabled preference, stop this disposable fixture process first
(the nested compositor exits with it). Create a fresh fixture root with the same `build`
and `monet-resume`, and pre-create `config/kwinrc` containing
`[Plugins]` and `monet_window_identityEnabled=false` on separate lines. Run `start-nested.py`
for that root, wait for `identity.json`, then run `verify-disabled.py ROOT`. It checks that
the installed plugin is available but unloaded, exports no object, and leaves both windows
open. The start script preserves existing configuration and refuses to reuse an earlier
fixture root. Do not run two fixtures simultaneously: they use the same nested socket name.

The bounded `resolveWindows` method resolves a batch in one IPC call. Invalid, repeated
or ambiguous surfaces reject the whole batch. `verify.py` checks its input bounds,
ordering, stale surfaces and lack of partial matches.

With the patched editor built as well, `verify-editor.py BUILD_ROOT` exercises real
Kate/KWrite windows, shared document IDs, cursor targeting, stale windows, missing-plugin
behavior and legacy departure receipts. The build root must contain the patched library
in `build/bin`, this compositor session and its sources in `identity`, and the current
`monet-resume`/`monet-editor-session` helpers in `identity`. Check the editor's private
Qt/KDE runtime before running; never install a bundle whose full runtime guard rejects it.

## Automatic editor recovery

The native editor exposes per-window capture and targeted cursors. Automatic recovery
now uses those APIs to reopen a native process session with several windows, shared
document IDs, and explicit compositor-ID mappings for placement. The image includes
the guarded compositor bundle. X11 still needs its own native-handle mapping.

Kate shares document objects between its windows. The new `monetDepartureWindows` protocol
keeps the group together using native Quit: a save veto leaves every original window and
buffer alive. Its final receipt captures Save As URLs for the whole group. This avoids
destroying a sibling and then trying to recreate its shared unsaved buffers on Cancel.
`verify-group-exit.py BUILD_ROOT` exercises this protocol in disposable Kate/KWrite sessions.
`verify-auto-groups.py BUILD_ROOT` exercises the production capture, protected departure,
final receipt, cancellation and recovery functions in native Kate and KWrite. It checks
shared unsaved buffers on Cancel, Save As and first-save paths, native window placement,
missing-file placeholders and exact-window Retry, all files missing, intentionally empty
windows and repeated requests. Its controlled same-boot recovery does not reboot into Windows.
Window dimensions remain subject to the application's minimum size.
The group fixture also captures a full 200-entry process, retries 197 returning files
into one pane, and replaces the resulting large window after it closes. It checks
unchanged sibling state, shared unsaved text, pane selection/cursor and frame/focus,
and refuses another file once the process budget is full.
It also exercises inactive-tab offsets in three panes across two windows, including
separate positions for a shared file, Save As during protected departure, repeated
recovery before hidden tabs are opened, closed-window replacement, late-file Retry,
live-cursor protection, truncated files and malformed cursor requests. Accessibility
checks verify the actual carets and that recovery creates only the visible editor views.
The scroll cases cover vertical/horizontal offsets, per-view wrap mode and wrapped top
columns through Save As, repeated recovery, first selection of hidden shared tabs,
closed-window replacement and late-file Retry. They check actual scrollbar values,
scroll-only user changes, malformed requests and shorter-file clamping.
Selection checks cover ordinary and rectangular ranges, continuing a backwards selection
with the native Shift+Right action, virtual columns beyond line ends, lazy shared views,
Save As, repeated recovery, replacement and late-file Retry. Accessibility confirms an
actual selected range; malformed requests and shorter files cannot modify document contents.
The selection flow also runs with multiple cursors: backwards anchors, mixed selection
states and secondary-only selections survive Save As, lazy recovery, replacement and Retry.
Native Select All followed by clearing the selection verifies that a repeated request
cannot recreate removed cursors. The three-pane shared-file case retains separate extra
cursor sets in each view. Native engine tests additionally verify Shift+Right/Delete behavior,
bare cursors, invalid requests and shortened-file coalescing.
Folding checks cover nested ranges, different shared-file folds, an edit followed by Save As,
two departures before lazy tabs are opened, replacement and late-file Retry. Native actions
unfold the parent while retaining its child, then unfold everything; replay respects that
later choice at caret zero. Changed files skip stale folds, and malformed, overlapping or
overly deep metadata is refused before mutation.
The same folding flow also runs with persistent parent/child ranges. Unfolding retains
their native anchors and flags through repeated recovery, replacement and Retry. The
paired engine's upstream regression separately unfolds and refolds those imported ranges.

`verify-retry.py BUILD_ROOT` tests targeted late-file reopening in Kate and KWrite,
including an inactive split window, shared unsaved buffers, existing file aliases,
malformed requests and a missing identity resolver. It also drives the production
single-window recovery generator through a missing file, automatic recheck, explicit
Retry and repeated Retry. All files and editor instances belong to the disposable fixture.

`verify-replacement.py BUILD_ROOT` checks closed-window Retry in the surviving native process.
It restores nested panes/cursors, reuses a shared unsaved buffer without changing its saved
file, and verifies the surviving window's frame, focus and metadata. It drops the first
reply, repeats the request, closes the replacement and recovers another pending file in a
second generation. A second lost reply closes its replacement before confirmation: the
native closed receipt leaves its files pending, automatic recovery leaves the window
closed, and the next explicit Retry succeeds. It also checks duplicate prevention across
attempt IDs and older requests without an attempt ID. Malformed requests, unavailable identity support and armed departure
must reject creation. The focus guard also leaves another active window and a changed
pointer position alone. All text inspection is confined to these generated fixtures.
