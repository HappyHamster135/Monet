# Native Files recovery metadata

The paired build also supplies Monet's everyday Files actions: Space previews
the selected/current local item, without taking spaces away from inline rename;
Tools offers Quick preview and Transfers. The preview launches through KIO so
Wayland activation is preserved. A process-level filter adds **Keep both** to
KIO's existing conflict dialog, retaining its previews, sizes, dates and native
unused-name/copy checks. Resume-only dialogs remain unchanged.

The roles updater limits speculative work to two pages before/after the view
and yields at a 32 ms budget. Visible items keep their existing priority. This
reduces background thumbnail/metadata work and long event-loop stalls without
turning off normal previews or changing saved view state.

Native thumbnail jobs share the existing delayed loading indicator and Stop
control. Stop or Escape pauses new preview work for that listing, retains
completed thumbnails and leaves the saved preview setting unchanged. Refresh,
navigation or an explicit preview toggle resumes work. The action follows the
active tab; cancelling only previews does not mark its completed listing as
cancelled. State uses QObject properties without adding class data members,
and the original exported no-argument cancellation helper remains available.

In a disposable matching build/test runtime, verify the pair with
`python3 image/files-recovery/bundle.py verify OUTPUT/runtime.json`, then run
`python3 tests/fixtures/files-thumbnail-native.py OUTPUT ARTIFACTS` from Monet's
repository. The fixture supplies its own home, cache, bus, Xvfb display and 2,000
synthetic photo paths. It verifies real native previews, responsiveness,
Stop/Escape, refresh, tab state, saved preview choice and graceful teardown.
Set `QT_SCALE_FACTOR=1.25`, `1.5` or `2` for the fractional-scale checks.

`tests/` builds native Qt/KIO checks for Keep both and Space-versus-text-input.
The image build runs these after compiling Dolphin. The package preserves
these test sources along with the experience adapter in its source archive.

Free-space lookup never discovers a filesystem root on the GUI thread. Exact
URLs share observers; native KIO workers resolve local and remote filesystem
capacity asynchronously. This also avoids Solid associating `/var/home` with
the read-only Atomic overlay. Different folders on one filesystem may use
separate jobs, bounded by active/recent views; this avoids synchronous mount
queries while navigating sleeping or disconnected drives. Old job results and
queued notifications from the previously selected location are discarded.

The image's Dolphin exposes a read-only `monetFilesState` method on its existing
`org.kde.dolphin.MainWindow` interface. It captures local folders, active tab/split side,
selected and current paths, expanded directories, scroll offsets/limits, splitter sizes
and custom tab labels. It does not read file contents or enumerate all directory items.
`monetFilesWindows` maps up to 16 main windows in one process to their exact KWin UUIDs
through the existing Wayland surface identity plugin. The helper discovers surviving
D-Bus objects when the first window has closed. Missing/ambiguous identity refuses the
multiwindow capture; the ordinary single-window path does not require the plugin.
Loaded local URLs may differ by a trailing slash; they still identify the same directory.
Loading, remote, ambiguous and oversized states are refused. The existing private native
session remains the restoration path; normal Dolphin session files are untouched.

Build with `sh build.sh OUTPUT` in the final image runtime. The build prepares the matching
distribution source RPM before patching, preserving downstream fixes. Development packages
must leave the captured runtime unchanged. The executable and private library form a pair;
runtime package identities, original hashes, shared-library exports and linked features are
checked before sealing/installing. The executable may directly link the already captured
transitive Wayland client runtime for surface IDs; no other linked-feature changes are accepted.
Corresponding source, build inputs and the source RPM are preserved in `source.tar.xz`.
Install with `python3 bundle.py install OUTPUT` only into
the matching runtime. A mismatch fails the image build.

The image builds and installs this pair against its assembled runtime. Monet validates the
metadata again before writing its private native session and verifies restored view state
before completing a launch. Missing selected/current items and expanded folders are skipped;
scroll offsets clamp to the live range. Matching existing windows retain their newer choices.
Older Dolphin builds retain folder-only accessibility capture when this method is absent;
a native refusal never silently downgrades to that fallback.

Live VM checks cover inactive tabs, unequal split widths, Unicode custom labels, selections,
expanded folders, dangling symlinks, bottom-of-folder scrolling, separate window placement,
missing items/folders, three windows in one process, first-object closure, disabled identity
and repeated recovery. The guest's different system runtime is refused;
the paired build runs in a matching container on the VM's Wayland display. Remote/search
locations, navigation history and broader display/RTL
coverage remain outside this adapter. See docs/RESTORATION.md and docs/TESTING.md in Monet's
source tree for the contract and verification record.
