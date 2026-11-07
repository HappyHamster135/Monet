# Shared desktop activity

The `org.monet.activity` QML extension shares one native observer across widget
views in each Plasma process. It observes the screen locker, login1 suspend
signals and KWin's per-output DPMS protocol. It never requests locking, sleep or
a display power change. Unsupported display state stays usable rather than
guessing that the screen is off.

Power consumers share UPower snapshots and property-change subscriptions. No
timer polls hardware; subscriptions stop when no active view needs them. Resume
reads a fresh snapshot. Generations and unique bus owners reject stale replies.
Unavailable readings retain the previous complete battery list with a separate
availability flag; they do not become zero percent. Widget timers, sensors and
nonessential reads use this state; user writes and active file jobs continue.

The image captures Qt, KWayland and transitive runtime package identities before
adding build headers, then verifies them before building and installing. It
rejects missing dependencies, unresolved symbols, build-directory RPATHs and
damaged bundles. The module, QML metadata, corresponding source and license ship
together. The build does not replace upstream binaries or restart Plasma.

With matching development packages, extract
`/usr/share/doc/monet-activity/source.tar.xz` and run:

```sh
cmake -S monet-activity -B build -DCMAKE_BUILD_TYPE=Release -DCMAKE_SKIP_RPATH=ON
cmake --build build --parallel 2
ctest --test-dir build --output-on-failure
```

Tests run on private D-Bus and Wayland servers, including multiple QML engines,
per-display modes, lock races, suspend/resume, cached reads and service/compositor
replacement. `MONET_ACTIVITY_TESTING=1` additionally builds a fixture executable
for rendered widget tests in the disposable test image. That executable and its
test-only controls are not installed in the OS image. Isolated checks do not
replace real laptop lock/display testing or CPU/wakeup comparisons.
