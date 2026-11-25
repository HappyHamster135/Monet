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

On an image with the plugin installed, run `python3 tests/fixtures/plain-paste-wayland.py`
from the checkout. It changes fields during clipboard transfer, pastes twice in quick
succession, and checks that the original HTML remains available, all in a private session.

The bundle also includes `monet_quit_guard.so`. Its input filter is installed
only while quit or close protection is enabled, or while draining a key release.
The settings are in Monet Utilities. Confirmed shortcuts go to the focused
application so it can show its usual unsaved-document prompt. Run
`python3 tests/fixtures/quit-protection-wayland.py` and repeat with
`--platform xcb` to check both window systems in an isolated session.

The wheel scrolling module reads its settings when KWin starts and when the
preferences page changes them. The input filter runs only when a wheel option
is enabled. A smooth scroll schedules frames while the wheel is moving and stops
when focus changes or a mouse button is pressed. For the integration check, build
`tests/fixtures/wheel-input.c` with `pkg-config --cflags --libs libei-1.0`, then
run `python3 tests/fixtures/wheel-scrolling-wayland.py --driver /path/to/wheel-input`.
Repeat with `--platform xcb` for XWayland.

The extra-click filter suppresses a complete repeated press and release from a
selected mouse button at the same position and window. It forwards the first
press immediately. The filter starts off and installs no idle timer. A settings
change or focus switch clears the click history. An outstanding suppressed
press still owns its release. Test with the same libei driver using
`python3 tests/fixtures/extra-click-wayland.py --driver /path/to/wheel-input`.
Repeat with `--platform xcb` and with `--saved` to check saved preferences.

Utilities loads `monet_cleaning.so` on demand for **Darken displays** and
**Keep desktop visible**. The compositor draws the countdown and finish button
on each output. A bounded timer, five deliberate Esc presses, the finish
button, session lock or loss of the Utilities owner releases the input filter.
The standard Plasma locker handles **Lock the session** independently.
Exercise the two-output flow with
`python3 tests/fixtures/visible-cleaning-wayland.py --plugin /path/to/monet_cleaning.so`.

The Command Bar uses `monet_app_menu.so` to identify the window that was active
before desktop search opened. When the search provider asks, KWin supplies that
window's ID, process, title and exported menu address. The provider reads the
menu on demand and checks the window again before invoking a selection.
Test duplicate actions, focus changes and disabled commands with
`python3 tests/fixtures/app-menu-wayland.py --plugin /path/to/monet_app_menu.so`.
