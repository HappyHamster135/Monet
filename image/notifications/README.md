# Monet notification policy

This builds Plasma's existing notification applet with two small QML changes:

- Dismissing a non-transient critical popup keeps it in native history, including
  its available actions. The close button says **Dismiss to history**. Removing
  an item from history or using Clear History still removes it normally.
- Messages from apps/services whose popups are muted go straight to history.
  Unmuting does not replay those messages. Transient messages are discarded.

The native applet identity, C++ code, notification daemon, grouping, replies,
jobs and history filters are retained. No second notification database is made.
Actions remain dependent on the sending app; history does not survive a restart
of Plasma. Existing native privacy/history exclusions still apply.

## Build and compatibility

`image/Containerfile` builds this after installing the image's runtime packages.
`sh build.sh /out` obtains the exact upstream Plasma version, patches only known
hooks, and builds the applet against that runtime. The build fails if installing
development dependencies changes the recorded runtime packages. The final image
checks their versions, the original plugin digest, the new binary/source digests,
missing libraries and unwanted build-time library paths before replacement.
An upstream QML hook change requires review; it must not silently omit the fix.

The image includes `source.tar.xz` under `/usr/share/doc/monet-notifications/`:
the full patched upstream tree (including its licenses) and the Monet build
files. With matching development packages installed, rebuild the extracted
sources using:

```sh
cmake -S monet-build -B build -DUPSTREAM_VERSION=VERSION \
  -DUPSTREAM_SOURCE="$PWD/plasma-workspace-vVERSION" \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_SKIP_INSTALL_RPATH=ON
cmake --build build --parallel 2
DESTDIR="$PWD/installed" cmake --install build
```

Replace `VERSION` with the version in the extracted source directory name.
Upstream files retain their original license notices; Monet's policy is
GPL-3.0-or-later. The original release archive comes from KDE Invent over HTTPS.
The bundle manifest records the exact runtime and delivered source digests.

These image-specific binaries are not installed by the generic Linux tarball.
Do not copy a plugin between Plasma versions. Live VM tests use a temporary
`QT_PLUGIN_PATH` override and remove it afterwards.
