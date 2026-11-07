# Monet sign-in

The image builds Plasma Login Manager's native greeter from the exact installed
Fedora source RPM. Monet adds its Fraunces clock, quiet glass panel and rounded
password controls. A compact Monet brightness control and brightness keys use
PowerDevil in the separate greeter session. A boot-time helper copies only the
last internal-screen brightness into that account; modes, HDR and scaling are
not imported. Narrow displays keep the compact layout; software rendering
uses opaque glass. There is no extra blur or background polling.

The daemon, PAM, session selection, keyboard/virtual keyboard, screen reader and
password synchronisation remain KDE's. An original, separately compiled QML page
is retained as a fallback if Monet's page fails to load. This is not a second
authentication implementation.

`runtime.json` pins the original executable and its linked RPMs. Installing devel
packages must not change them; both build and image installation fail on a
mismatch. The executable and matching source archive are checksum verified. The
source RPM, Monet patch and build instructions are in `source.tar.xz` beside this
file in `/usr/share/monet/login`.
