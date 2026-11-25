# Recording click zooms

Monet builds Fedora's screencast module from the signed source matching the
installed KWin. The upstream screen picker and PipeWire encoder path remain in
use. A Spectacle process launched by the recorder can deliver primary-click
positions relative to its selected source after the first video frame.

The editor listens only when the user enables **Zoom to clicks**. Both ends
verify local peer credentials. The compositor observes button presses during
the stream, skips the lock screen and releases its observer on disconnection,
pause and stream closure. No keyboard input or mouse movement is recorded.
The editor groups nearby clicks and stores zoom edits locally with the
recording's file identity. Exporting renders those edits into the output video.

The source archive includes the original Fedora source RPM, its license files
and the Monet changes. Rebuild with `sh build.sh OUTPUT_DIRECTORY` inside the
matching stock Fedora-based runtime.
