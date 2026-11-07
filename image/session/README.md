# Monet native session backdrop

The native logout greeter keeps Monet's transition page over applications
while they close. Its exclusive keyboard grab is released. The real task model
watches new windows (including ones skipped by the taskbar) and attention requests;
these lower the cover to reveal native save/inhibitor prompts until they close.
A Show applications fallback appears after four seconds for prompts inside an
existing window. Cancellation or a failed request closes the cover.
The normal session, update, authorization and shutdown paths stay in
KDE; no power action is run by the theme or a new privileged helper.

Build from the exact Fedora source/runtime and retain source and ABI guards.
A stock/fallback theme retains KDE's original accept/close behavior.
