# Monet native session backdrop

The native logout greeter keeps Monet's transition page over applications
while they close. Its exclusive keyboard grab is released. The real task model
watches new windows (including ones skipped by the taskbar) and attention requests;
these lower the cover to reveal native save/inhibitor prompts until they close.
A Show applications fallback appears after four seconds for prompts inside an
existing window. Cancellation or a failed request closes the cover.
The firmware restart from Settings uses Plasma's shutdown service. The
service waits for X11 and Wayland applications to finish closing before it
sets the firmware boot target and calls logind. A refused reboot clears the
target set by that request. Ordinary logout, reboot and update actions use
Plasma's existing paths.

The Plasma containment menu opens Task Manager from empty desktop and panel
space. It keeps the existing menu entries and uses the wallpaper's action when
Monet's wallpaper has already provided one.

Build from the exact Fedora source/runtime and retain source and ABI guards.
A stock/fallback theme retains KDE's original accept/close behavior.
