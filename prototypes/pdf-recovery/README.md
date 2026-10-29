# PDF restoration fixture

Run only in Monet's disposable Linux VM, after taking an `ai-` checkpoint.
`build.sh` builds the shell patch from the installed distribution's source RPM,
retaining its patches and compiler flags. The installed document plugin stays unchanged.
This prototype is not the production image bundle.

`capture-test.cpp` uses real Okular shell windows and its installed PDF plugin with
generated four-page PDFs. Build it alongside the shell's sources, substituting it for
`main.cpp` and linking Qt Test. Run in an isolated, matching Wayland compositor with
Monet's window-identity plugin, private HOME/configuration, and the same UID/PID namespace.

Set `MONET_PDF_HELPER` to `linux/libexec/monet-pdf-session` and `MONET_PDF_EVIDENCE` to a
private output JSON path. The fixture verifies tab reordering, independent pages for a
shared file, empty windows, Save As paths with the original preserved, modified-state
capture, unchanged selection/geometry, exact distinct window identities, refusal of
ambiguous single-window capture and querying survivors after the first window closes.
It also unloads the identity plugin to check refusal, then reloads it and verifies recovery.
The helper checks use real D-Bus requests, not mocked capture results.

`departure-test.cpp` substitutes for `main.cpp` in a second test executable. Link Qt Test,
Xml, PrintSupport and the installed matching Okular core library as well as the shell's
normal dependencies. Set `MONET_PDF_CONTROLLER` to `controller.py` and
`MONET_PDF_DEPARTURE_EVIDENCE` to its output JSON path. The controller keeps a real Qt
D-Bus connection alive across arm/disarm/receipt commands. Use a compositor socket name
other than `monet-pdf`, which is the adapter's private runtime directory.

The departure test pastes actual annotations through Okular's native annotation interface,
answers its real Save/Discard/Cancel dialogs, and independently reads the resulting PDFs.
It checks final Save As paths, active-tab preservation, an unsaved surviving window,
cancellation/controller loss during a save prompt and failed receipt writes. Cancellation
leaves the window open even if the user subsequently chooses Save; the saved content stays.
It also checks a window created after arming: close is vetoed until the controller adds
its exact identity to the watch.

`build-fixtures.py` adds the three Qt test targets to the prepared source tree. `restore-test.py`
uses the helper and real patched `okular --session` entry point. With ordinary tab preferences
set to separate windows and collapse duplicate files, it still opens two independent private
windows containing duplicate tabs at different pages. It verifies the selected tab, unusual
local filenames, unchanged preferences, empty sessions, malformed-state refusal, missing-file
preflight and exact launch identity. It also calls the real append D-Bus method, repeats its
request and verifies that another process cannot receive that window's tab. Run it with the
patched executable on PATH in the same isolated compositor.

`retry-test.cpp` exercises a missing file becoming available, exact window routing, changed
live-state rejection, duplicate-path tabs, repeated requests after a lost reply, and manual
tab/window closure. The original modified part, page, selection, geometry and sibling stay
unchanged. Unloading the identity plugin returns an unconfirmed result without modifying
the window. Set `MONET_PDF_RETRY_EVIDENCE` to its output JSON path.

`return-test.py` runs the real return controller against three native windows. It covers
protected departure, an untouched cancelled-switch survivor, duplicate tabs, missing-file
retry, page/selection/placement and interruption after a successful append but before its
reply is recorded. A fresh controller and repeated return must produce no duplicates.
It uses AT-SPI only to answer Close Tabs on its owned synthetic windows. Set
`MONET_PDF_RETURN_EVIDENCE` to a private output JSON path. Production image acceptance
remains separate from this fixture.

All files are synthetic. Export evidence and restore the test checkpoint after the broader
integration work finishes; do not restore over an active complete-image build.
