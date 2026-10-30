# Native Files recovery metadata

The same paired build fixes local free-space lookup on Atomic systems: the
status bar shares observers using `QStorageInfo`'s actual mount root. Solid's
storage-device lookup can associate `/var/home` with the read-only overlay and
report 0 B free. Remote locations retain Dolphin's existing KIO handling.

The image's Dolphin exposes a read-only `monetFilesState` method on its existing
`org.kde.dolphin.MainWindow` interface. It captures local folders, active tab/split side,
selected and current paths, expanded directories, scroll offsets/limits, splitter sizes
and custom tab labels. It does not read file contents or enumerate all directory items.
`monetFilesWindows` maps up to 16 main windows in one process to their exact KWin UUIDs
through the existing Wayland surface identity plugin. The helper discovers surviving
D-Bus objects when the first window has closed. Missing/ambiguous identity refuses the
multiwindow capture; the ordinary single-window path does not require the plugin.
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
