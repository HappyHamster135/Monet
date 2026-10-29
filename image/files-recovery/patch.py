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
      '    bool isUrlOpen(const QString &url);\n    QString monetFilesState() const;\n    QString monetFilesWindows() const;')
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
