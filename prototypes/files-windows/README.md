# Shared-process Files VM fixture

These checks are for the isolated Monet VM only. `main.cpp` creates three real Dolphin main
windows in one process using the patched distribution source tree. Build it alongside that
tree's `dolphinstatic` target, linking `dolphinstatic`, `KF6::DBusAddons` and `KF6::Crash`.
Use exactly the runtime guarded by `image/files-recovery/bundle.py` and install the matching
`image/window-identity` bundle into the test runtime. Do not replace mismatched guest binaries.

The recorded harness uses `/var/home/j/.local/monet-files-build` with `fixture/` as its private
HOME/config and `live/` containing the current recovery helpers and these Python checks.
A matching nested KWin runs on a separate session bus; `live/nested-env.json` records its
`DBUS_SESSION_BUS_ADDRESS`, `WAYLAND_DISPLAY` and `XDG_RUNTIME_DIR`. Keep the same host PID
namespace and UID for the compositor and Files. The fixture executable is `monet_shared_files`
at the harness root. All paths belong to synthetic test data.

Run `verify.py`, then `verify-guards.py` inside that runtime. The first verifies capture,
cancellation, exact placement, missing folders and retry. The second unloads/reloads the
identity plugin and checks refusal without duplicates, plus capture of the last surviving
D-Bus object. JSON proofs are written under `live/`. Restore the VM's own test checkpoint
after exporting evidence. See `docs/TESTING.md` for the completed run and limits.
