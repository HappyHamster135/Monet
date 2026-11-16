Monet Task Manager sidebar
=========================

A small patch to Main.qml in the distribution's matching plasma-systemmonitor
source RPM. The native process/sensor backends remain installed unchanged.
The hamburger toggles the sidebar, its empty space accepts the page menu,
and custom pages can be removed with confirmation and a safe navigation fallback.
Monet's built-in pages are excluded from the direct Remove Current Page action.

Build with `sh build.sh /out` in an image build stage with the native runtime.
The build refuses changed source anchors or runtime packages. `bundle.py install`
verifies the runtime and checksums before installing. The source RPM and Monet
build/patch scripts are retained in source.tar.xz (upstream GPL licenses apply).
The user preview installer accepts `--task-manager-bundle /path/to/out`; that
installs to this account only with reversible backups. Restore/rebuild the local
preview after an OS runtime upgrade.

Monet's Applications and Processes faces (`linux/share/ksysguard/sensorfaces`)
add to KDE's tables at run time: their first cells, text cells, overrides and
rows under the apps. `patch.py` also checks the same source RPM's table faces
for what they use (`FACE_ANCHORS`) and stops the build when KDE changed them.

Native tests: one-click collapse/expand, empty-space right-click, create/remove
custom page, deleting a selected/start page, restart, native sensor updates, and
minimized sampling. For the table faces: a Steam game's row by its name and icon
(also one started before its entry existed), a Flatpak app's row, a browser's
second line following its tab and a web app window, the Processes page's app
names in list and tree, Quit and Kill on a renamed row, and Other and System
next to the cards (with a `java` loop from an SSH login, an app's terminal tab
in a scope of its own, and `systemd-run --user`). Never deploy an executable
built for a different runtime.
