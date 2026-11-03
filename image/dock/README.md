# Monet dock motion

The native Plasma icons-only task applet gains an upward lift and smooth
magnification under the pointer. Neighbouring icons ease into the effect, giving
a continuous wave as the pointer moves along the dock. Only painting transforms
change: click targets, task grouping, menus, reorder/drag behaviour, panel size
and running-app indicators stay in their native positions.

Motion is limited to a single-row, bottom-edge icons-only dock. It is disabled
for desktop edit mode, dragging, the native hover-effect preference, and the
system's instant/reduced-animation setting. It uses passive HoverHandler events
and finite property transitions; there is no polling, idle animation, shader or
extra process. Icon scale is bounded at 1.28 and lift at nine logical pixels.
The native Trash applet uses the same motion on the bottom dock, with its full
painted icon and a stable click area during dragging and reduced-motion changes.

`image/Containerfile` builds the applet from the exact installed plasma-desktop
version. The patch fails if a source hook moves. The image bundle verifies runtime
packages, the original plugin and delivered binary/source hashes, unresolved
libraries and RPATH before installation. Full corresponding patched source and
build inputs ship under `/usr/share/doc/monet-dock/` with upstream license notices.

With matching development dependencies, rebuild the supplied source using:

```sh
cmake -S monet-build -B build -DUPSTREAM_VERSION=VERSION \
  -DUPSTREAM_SOURCE="$PWD/plasma-desktop-vVERSION" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_SKIP_INSTALL_RPATH=ON
cmake --build build --parallel 2
```

The laptop preview is scoped to plasmashell with a user service override and
checks the runtime before adding its private Qt plugin path. A later OS update
falls back to the stock dock instead of loading an incompatible plugin. The
preview does not modify `/usr` or desktop applet configuration. Restarting
plasmashell activates or removes the override without closing application windows.
