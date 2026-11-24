# Native window identity

This KWin plugin's read-only D-Bus API maps a process ID and Qt Wayland surface ID to the exact
compositor window UUID. `resolveWindows` accepts up to 16 surfaces and rejects the whole
batch if a surface is missing, repeated or ambiguous. It never reads titles, document
paths or contents and exposes no window-control D-Bus methods. The editor adapter uses these IDs
to associate its own document layouts with compositor geometry.

The same runtime-paired module registers the in-process QML type
`org.monet.windowcontrols.WindowControls` for Monet's dropdown title bar. It hands
a held left-button drag directly to KWin's mouse-move operation, retaining the
original press offset and native restore/snapping behavior. It finishes the
bar's Qt press because KWin consumes the later physical release. Missing targets,
released buttons and windows that cannot be moved are rejected. No timer, pointer
warp or external D-Bus control request is used. This path supports both Wayland
and XWayland windows; the surface-identity API remains Wayland-only.

The image builds the module against its fully assembled runtime and records the runtime
packages plus KWin executable/library hashes before adding development packages. A change
after that step fails the build. Installation rechecks those values, both binary/source
hashes and dynamic linking before copying the module. KWin also checks the compiled-in
plugin ABI identifier before loading it. Do not copy this module between KWin versions.

The shipped metadata enables it at compositor startup, unless the user's existing KWin
configuration disables `monet_window_identityEnabled`. Installation does not rewrite that
preference or restart a running desktop. Generic Linux tarballs omit the native module.
Automatic multi-window editor departure and placement still need integration; exposing
window identity alone does not claim complete session restoration. When the module
is absent or disabled, the title script retains its scripting-only fallback.

The complete module source, GPL-3.0-or-later license, build inputs and runtime manifest
ship in `/usr/share/doc/monet-window-identity/source.tar.xz`. With matching development
packages, extract it and run:

```sh
cmake -S monet-window-identity -B build -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_SKIP_INSTALL_RPATH=ON
cmake --build build --parallel 2
```

VM fixtures in `prototypes/window-identity` build this same source and use an isolated
nested compositor. They check identical windows, stale IDs, ambiguous IDs across separate
Wayland connections, native editor capture and cancellation. The VM's system compositor
does not need replacing for those checks.

The same ABI-checked bundle also installs `monet_plain_paste.so`. It handles
the desktop’s Paste as plain text shortcut. Browsers with a native matching-style
command and Konsole receive their own paste shortcut in the focused window.
Other editable controls use an on-demand Utilities helper. The plugin exposes
no D-Bus input method.
