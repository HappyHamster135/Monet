# Monet dock motion

Clicking either the title or thumbnail in a window preview activates that window. Each resizable window has a Snap layouts button that passes its Wayland window ID to Monet Snap. Close keeps its own action.

The native Plasma icons-only task applet gains an upward lift and smooth
magnification under the pointer. Neighbouring icons ease into the effect, giving
a continuous wave as the pointer moves along the dock. Only painting transforms
change: click targets, task grouping, menus, panel size
and running-app indicators stay in their native positions.

Motion is limited to a single-row, bottom-edge icons-only dock. It is disabled
for desktop edit mode, dragging, the native hover-effect preference, and the
system's instant/reduced-animation setting. It uses passive HoverHandler events
and finite property transitions; there is no polling, idle animation, shader or
extra process. Icon scale is bounded at 1.28 and lift at nine logical pixels.
Passive trackers attach to the native tooltip areas, which can consume hover
events before an ancestor handler sees them. They share the current pointer for
neighbour motion without blocking native tooltips or controls. Tracking uses the
untransformed task bounds and follows the native task-reordering transform.
The native Trash applet uses the same motion on the bottom dock, with its full
painted icon and a stable click area during dragging and reduced-motion changes.

Manual single-row icon reordering uses an in-process pointer grab: the held icon
follows the pointer and neighbouring icons slide into their new slots. Input
bursts are coalesced to at most one model move per 16 ms, using slot centres and
a small dead band instead of hit-testing moving pictures. The final launcher
order is saved on release. Leaving the bar hands off to Plasma's normal system
drag, so launchers can still be dropped elsewhere. Neither path polls at idle.
Changing screen edge clears old hover and movement transforms; the list uses
coordinates instead of switching opposing anchors during an orientation change.

Internal manual reordering on that dock uses the delegates' layout slots while
their painted icons slide. It accepts the next pointer movement during an
animation, including an immediate reversal. Initial layout seeds each delegate's
position so its first reorder animates too. Other panel orientations, group
popups and external drops retain upstream handling. Reorder animation still uses
Plasma's duration preference, including instant motion.

The tooltip's volume slider remembers an app's level for its next streams
(`MonetAppVolume.qml`, `~/.config/monet/app-volume.ini`). A player's own level
is put back to the remembered one when it lands on a new stream within a second,
or, on a stream the player keeps between tracks (Spotify), when it returns to a
level the stream had before right after an MPRIS track change or a resume.
Other mixers' changes are kept. When each of a group's streams belongs to one
window, each window that plays sound gets its own slider, and that window's
level holds for its next streams while it is open. A stream belongs to a window
when it comes from that window's own process (or its child) and no other window
shares the process, or, when windows share a process, from the one window whose
title starts with the stream's name (Firefox names a tab's stream after the
page). Chromium-based browsers name every stream "Playback", so they keep one
slider.

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

Regression checks: `tests.test_dock_motion` sends pointer events through real
Plasma tooltip areas and native click/drag controls in a disposable session.
`tests/native/dock-hover/` is a small CMake test host for the compiled task and
Trash plugins. Run that executable only in a disposable home and private D-Bus
session, with `QT_PLUGIN_PATH` pointing to the tested bundle's plugin tree.
With `MONET_DOCK_AUDIO_QML` set to a folder holding the patched `PulseAudio.qml`,
`ToolTipInstance.qml`, `ToolTipDelegate.qml` and `MonetAppVolume.qml` (`build.sh`
leaves them in `tests/audio`), `tests.test_audio_native` checks the volume
memory against a private PipeWire server and against made-up streams and windows.
