# Background-work departure fixture

Run only inside the Monet test VM under an `ai-…` checkpoint, with the desktop session's
`DBUS_SESSION_BUS_ADDRESS`, `XDG_RUNTIME_DIR` and `WAYLAND_DISPLAY`. Set `XDG_STATE_HOME`
to `OUTPUT/state`, then run `python3 verify-background.py OUTPUT` with a new output directory.
Repeat with `QT_SCALE_FACTOR=2` and another output directory.

The fixture uses the production Store service launcher, queue and switch dialog, a synthetic
transaction and a normal Qt companion window. The privileged restart helper is replaced
by a pipe handshake that records acceptance; it cannot write firmware or reboot.

It checks real logind inhibitors, untouched windows while work runs, exactly one acceptance
after completion, Escape preserving the running worker, queue cancellation, and interrupted
worker recovery. It captures the waiting dialog and checks that its frame fits the screen.
Output includes `proof.json` and screenshots. Restore the checkpoint after saving evidence.
