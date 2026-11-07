#!/usr/bin/python3
"""Add read-only, bounded Files metadata; never alter Dolphin's normal session files."""
from pathlib import Path
import sys

root=Path(sys.argv[1])
here=Path(__file__).resolve().parent

def patch(name, before, after):
    path=root/name
    text=path.read_text()
    if text.count(before) != 1:
        raise SystemExit('Dolphin source changed: '+name)
    path.write_text(text.replace(before,after))

patch('src/dolphinmainwindow.h','    bool isUrlOpen(const QString &url);',
      '    bool isUrlOpen(const QString &url);\n    QString monetFilesState() const;\n    QString monetFilesWindows() const;\n    void setupMonetFiles();')
patch('src/dolphinmainwindow.cpp', '    setupActions();', '    setupActions();\n    setupMonetFiles();')
patch('src/dolphinui.rc', '<Action name="manage_disk_space" />',
      '<Action name="monet_preview" />\n            <Action name="monet_transfers" />\n            <Action name="manage_disk_space" />')
patch('src/CMakeLists.txt', 'add_library(dolphinstatic STATIC)',
      'add_library(dolphinstatic STATIC)\nfind_package(Qt6 REQUIRED COMPONENTS GuiPrivate)\n'
      'find_package(PkgConfig REQUIRED)\npkg_check_modules(MonetWayland REQUIRED IMPORTED_TARGET wayland-client)\n'
      'target_link_libraries(dolphinstatic Qt6::GuiPrivate PkgConfig::MonetWayland)')
patch('src/views/dolphinview.h','#include <QWidget>', '#include <QWidget>\n#include <QJsonObject>')
patch('src/views/dolphinview.h','    int selectedItemsCount() const;',
      '    int selectedItemsCount() const;\n    QJsonObject monetViewState() const;')
for target, source in [('src/dolphinmainwindow.cpp','window-state.cpp'), ('src/views/dolphinview.cpp','view-state.cpp')]:
    path=root/target
    text=path.read_text()
    if 'monetfiles.h' in text:
        raise SystemExit('Dolphin source already patched: '+target)
    path.write_text(text+'\n'+(here/source).read_text())
for folder in ('src','src/views'):
    (root/folder/'monetfiles.h').write_bytes((here/'monetfiles.h').read_bytes())
(root/'src/experience.h').write_bytes((here/'experience.h').read_bytes())
with (root/'src/dolphinmainwindow.cpp').open('a') as stream:
    stream.write('\n' + (here/'experience.cpp').read_text())

# Keep two pages warm on either side, rather than decoding five pages each
# way. Visible items retain priority; large photo folders do less speculative
# thumbnail and metadata work while the user is navigating.
patch('src/kitemviews/kfileitemmodelrolesupdater.cpp', 'const int ReadAheadPages = 5;', 'const int ReadAheadPages = 2;')
patch('src/kitemviews/kfileitemmodelrolesupdater.cpp', 'const int MaxBlockTimeout = 200;', 'const int MaxBlockTimeout = 32;')

# Determining a filesystem root with Solid/QStorageInfo can block on a sleeping
# or disconnected mounted drive. Pool exact URLs and let the existing native
# KIO job resolve the real filesystem in its worker, including Atomic /var/home.
patch('src/statusbar/mountpointobservercache.cpp', """    QUrl cachedObserverUrl;
    // If the url is a local path we can extract the root dir by checking the mount points.
    if (url.isLocalFile()) {
        // Try to share the observer with other paths that have the same mount point.
        // Use Solid (rather than KMountPoint) which will likely already have the info from KFilePlacesModel.
        const auto device = Solid::Device::storageAccessFromPath(url.toLocalFile());
        const auto *deviceAccess = device.as<Solid::StorageAccess>();
        if (deviceAccess) {
            cachedObserverUrl = QUrl::fromLocalFile(deviceAccess->filePath());
        } else {
            // Even if determining the mount point failed, the observer might still
            // be able to retrieve information about the url.
            cachedObserverUrl = url;
        }
    } else {
        cachedObserverUrl = url;
    }""", """    // Never stat a mount or resolve symlinks on the GUI thread. KIO performs
    // that work asynchronously; identical URLs still share an observer.
    const QUrl cachedObserverUrl = url;""")
patch('src/statusbar/mountpointobserver.cpp', 'void MountPointObserver::freeSpaceResult(KJob *job)\n{',
      'void MountPointObserver::freeSpaceResult(KJob *job)\n{\n'
      '    if (job != m_pendingJob.data()) return;\n    m_pendingJob.clear();')
patch('src/statusbar/spaceinfoobserver.cpp', '    if (newObserver != m_mountPointObserver) {',
      '    if (newObserver != m_mountPointObserver) {\n'
      '        m_hasData = false;\n        m_dataSize = 0;\n        m_dataAvailable = 0;')
patch('src/statusbar/spaceinfoobserver.cpp', '        // so update the observer now.\n        m_mountPointObserver->update();',
      '        // so update the observer now.\n        m_mountPointObserver->update();\n        Q_EMIT valuesChanged();')
patch('src/statusbar/spaceinfoobserver.cpp', 'void SpaceInfoObserver::spaceInfoChanged(quint64 size, quint64 available)\n{',
      'void SpaceInfoObserver::spaceInfoChanged(quint64 size, quint64 available)\n{\n'
      '    if (sender() != m_mountPointObserver) return;')

# The status bar already fixes this row's height. Inheriting the style's outer
# layout margins leaves too little room for the free-space button's text.
patch('src/statusbar/statusbarspaceinfo.cpp',
      '    layout->setContentsMargins(2, -1, 0, -1); // "-1" makes it so the fixed height won\'t be ignored.',
      '    layout->setContentsMargins(2, 0, 0, 0); // Keep the fixed-height row available for the button text.')

# Stop should cease to offer cancellation once the native load was cancelled,
# just as it already does on successful completion.
patch('src/dolphinmainwindow.cpp',
      '    connect(view, &DolphinView::directoryLoadingCompleted, this, &DolphinMainWindow::disableStopAction);',
      '    connect(view, &DolphinView::directoryLoadingCompleted, this, &DolphinMainWindow::disableStopAction);\n'
      '    connect(view, &DolphinView::directoryLoadingCanceled, this, &DolphinMainWindow::disableStopAction);')

import runpy
runpy.run_path(str(here / 'thumbnail-jobs.py'))['apply'](root)
