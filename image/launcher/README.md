# Native application launching

`org.monet.launcher` shares installed-app launch state across menu/dock views in
each Plasma process, including recreated views and multiple QML engines. The
session-bus endpoint `org.monet.Launcher` lets Monet helpers use that coordinator.
It accepts indexed application IDs, not arbitrary executables or shell commands.
Files, URLs and desktop actions retain their original native model actions.

Launching uses KDE's ApplicationLauncherJob and native startup notifications.
Wayland tokens come from the source window or notification action. The native
TasksModel raises an existing window and tracks startup/window confirmation.
A successful process spawn is not treated as a ready window. Pending repeated
clicks share one launch; explicit new-window actions remain available. Distinct
applications can start concurrently. SingleMainWindow applications are raised.

Missing executables and native launch errors keep an actionable message in the
menu and a notification with Retry. Early exit or a confirmation timeout is
described as unconfirmed rather than a proven crash. Retry first checks native
windows/startups; a live pending process remains protected from accidental
duplicates. pidfds observe exits without polling or signalling applications.
The read-only fallback on older kernels can only keep a duplicate blocked.
There is no separate launcher daemon or persistent launch-state file.

The same native module also provides `FolderOpener` for explicit transfer-folder
actions. It asynchronously checks the actual destination type through KIO. A
directory opens directly in the default file manager; a file uses the native
file-manager interface to show its parent and select it, never opening downloaded
content. There are no idle metadata reads. Slow checks have cancellation and a
deadline; cancelled/obsolete replies cannot open a later window. Missing or
changed destinations keep a retryable explanation in Transfers. Native dispatch
does not establish that the file-manager window has painted.

The build guards Qt, KDE and the private task-model library against the exact
runtime captured before headers are installed. It checks packages, library and
bundle hashes, dependencies, relocations and RPATH. Matching source, this build
recipe and the license ship in `/usr/share/doc/monet-launcher/source.tar.xz`.
Notification defaults do not overwrite a person's notification preferences.

With matching development packages:

```sh
cmake -S monet-launcher -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_SKIP_RPATH=ON
cmake --build build --parallel 2
ctest --test-dir build --output-on-failure
```

The private-bus native tests exercise actual KIO launches against disposable
desktop entries. A supplied task model controls window/startup events for these
tests; separate rendered menu/dock and real window-system checks are required
before release. The fixture executable is included only in the test image.
The test image also includes the folder-action checks and a real KIO copy/download
driver using the standard KUiServerV2 progress tracker. Production images exclude
all fixture executables.

Primary API references: [ApplicationLauncherJob](https://api.kde.org/kio-applicationlauncherjob.html),
[TasksModel](https://invent.kde.org/plasma/plasma-workspace/-/blob/v6.8.2/libtaskmanager/tasksmodel.h)
and [KWaylandExtras](https://api.kde.org/kwindowsystem-kwaylandextras.html).
