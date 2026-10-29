# Phone page native verification

29 October 2026. This verifies the Settings Phone page from commit `1709790`
against synthetic helper replies in the existing Monet test VM. It does not
establish phone pairing, file delivery or an installed desktop update.

## Inputs and runtime

| Input | Observed identity |
| --- | --- |
| Hyper-V VM | `Monet`, `35518937-adaf-4997-99c9-5ecb6758a0d1` |
| Guest | Monet 0.9.3 / Fedora 44; boot `b8611dfb-e836-44f6-90d2-b1dd355b1320` |
| Qt / PySide6 | 6.11.2 / 6.11.2 |
| Kirigami / Plasma | 6.31.0 / 6.7.5 |
| Existing transport package | `kde-connect-26.08.1-1.fc44.x86_64` |
| Existing CLI SHA-256 | `43281a0b621f2f5c4ce31e92c32ad2ccb3ecbada47476c7e825d40c63505b762` |
| Existing daemon SHA-256 | `9148171438f7ba9898ea5c14e87fed59f7c6e5a81f14a048b8b6118841f3d9cf` |
| Tested Settings QML SHA-256 | `940d8de2d38fa007e4a95c07682a99600e607f19d90d816bbfa6cb01039fdce3` |
| New test SHA-256 | `c4274b341ff9a1f9c995f053cd413d4f0bfa2c4c4161996be3e79782eb8ccfd5` |

The test loads the actual QML and shared window components. Its helper is an
in-process fake: no KDE command, pairing request, file picker or transport runs.
Fresh HOME, XDG configuration/data/cache/state/runtime directories and a private
Unix D-Bus session keep existing user settings and pairing data outside the
fixture. The final bus configuration contains no activation service directories.
Software rendering and the offscreen platform avoid the running desktop session.

## Results

All three [Phone window tests](../tests/test_phone_window.py) pass at each scale:

| Scale | Native cases | Runtime | PNG dimensions |
| --- | --- | --- | --- |
| 1 | 3 passed, no QML warnings | 3.484 seconds | 760 x 600 |
| 2 | 3 passed, no QML warnings | 3.643 seconds | 1520 x 1200 |

The cases verify:

- Two device rows retain their own Files and sharing recipients. Keyboard
  activation reaches the intended helper command, and controls fit inside each row.
- Delayed sharing disables repeated requests. Cancellation, a nonzero command
  result and malformed output remain retryable without reporting delivery.
- Failed discovery clears stale device actions. Activating the visible Retry
  button restores both devices after a successful response.

Both selected-device renders were visually inspected. These are scale-factor
checks at a 760 x 600 logical window, not a large-font, screen-reader or live
KWin/input acceptance result. There are three cases repeated at two scales,
not six different interoperability cases.

## Preserved evidence and isolation observations

Each successful workspace retains 80 source files with a checksum inventory,
the exact command/environment, logs, three PNGs and `receipt.json`:

| Workspace under `/tmp/` | Receipt SHA-256 |
| --- | --- |
| `monet-phone-window-20261029-owned-e088v2xx` | `690fa2cbf9387fee7478dd8fca29397751e17bf4bd7f68412c86fac872a14287` |
| `monet-phone-window-20261029-owned-g1wflcdt` | `cfb0234ebc2324cfc526c043e240f58f71fd02bf3bbc7cfa7606c1bde32eb314` |

The guest boot and existing `kdeconnectd` PID 3161/start ticks 18649 remain
identical. Routes and TCP/UDP listeners match exactly before/after each run;
source bytes remain unchanged. No fixture Unix sockets remain afterward.
No existing account configuration or pairing files were read or modified.

The receipts deliberately retain `sameNetwork: false`: raw address JSON includes
the dynamic IPv4 lease countdown. On `eth0`, `172.25.9.86`, both `valid_life_time`
and `preferred_life_time` changed from 64782 to 64778 in the scale-1 run and
64744 to 64740 in the scale-2 run. An independent comparison removing only those
lifetime fields finds the remaining address configuration equal. The raw results
were not rewritten or described as literally identical.

The first native attempt is separately preserved at
`/tmp/monet-phone-window-20261029-owned-5osdxoz9`, receipt SHA-256
`35dfbe191c83d46824fb1401cf17d6ddedf5de011b3374b5040a4d9d5d393b8b`.
It loaded QML but failed because the fixture omitted the QtQuick import needed
for the proper Python window wrapper. Its default private bus also activated
portal helpers. The import and activation-disabled bus fixed the fixture;
all recorded first-attempt bus/test/portal processes were independently gone
before subsequent work. This failed attempt is not counted as passing evidence.

## Re-running the native cases

Use a configured Linux Monet runtime with Qt/PySide/Kirigami already installed.
Create a new private fixture for every run; the tests refuse to replace existing
PNG output. From a complete source checkout:

```sh
umask 077
fixture="$(mktemp -d /tmp/monet-phone-window-owned.XXXXXXXX)"
mkdir "$fixture"/home "$fixture"/config "$fixture"/data "$fixture"/cache \
  "$fixture"/state "$fixture"/runtime "$fixture"/artifacts
cat > "$fixture/bus.conf" <<EOF
<busconfig>
  <type>session</type>
  <listen>unix:tmpdir=$fixture/runtime</listen>
  <auth>EXTERNAL</auth>
  <policy context="default">
    <allow user="$(id -u)"/><allow own="*"/>
    <allow send_destination="*" eavesdrop="true"/>
    <allow receive_sender="*" eavesdrop="true"/>
  </policy>
</busconfig>
EOF
env -i PATH=/usr/bin:/bin LANG=C.UTF-8 LANGUAGE=C \
  HOME="$fixture/home" XDG_CONFIG_HOME="$fixture/config" \
  XDG_DATA_HOME="$fixture/data" XDG_CACHE_HOME="$fixture/cache" \
  XDG_STATE_HOME="$fixture/state" XDG_RUNTIME_DIR="$fixture/runtime" \
  MONET_PHONE_WINDOW_ROOT="$fixture" PYTHONDONTWRITEBYTECODE=1 \
  QT_QPA_PLATFORM=offscreen QT_QUICK_BACKEND=software QSG_RENDER_LOOP=basic \
  QT_SCALE_FACTOR=1 dbus-run-session --config-file="$fixture/bus.conf" -- \
  python3 -B -m unittest -v tests.test_phone_window
```

Repeat with a new fixture and scale 2 for the second matrix entry. Ordinary
test discovery skips these native cases unless the explicit isolated fixture
and Qt runtime are supplied. Preserve the failed output before diagnosing a run;
do not reuse an existing desktop profile or activate its KDE transport to make
this synthetic UI test pass.

Actual source-built Monet Phone pairing, bidirectional picture hashes,
disconnect/reconnect and revocation remain separate runtime gates.
