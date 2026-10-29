#!/usr/bin/python3
"""Add native PDF capture, protected departure and private session restoration."""
from pathlib import Path
import sys


def apply(root):
    here = Path(__file__).resolve().parent
    changes = {
        "shell/shell.cpp": [('#include "shell.h"', '#include "shell.h"\nstatic quint64 monetDocumentDepartureGeneration();'),
                            ('void Shell::readProperties(const KConfigGroup &group)\n{',
                             'void Shell::readProperties(const KConfigGroup &group)\n{\n    if (group.hasKey("MonetDocumentState")) {\n        monetRestoreDocumentState(group.readEntry("MonetDocumentState", QString()));\n        return;\n    }'),
                            ('void Shell::openNewTab(const QUrl &url, const QString &serializedOptions)',
                             'void Shell::openNewTab(const QUrl &url, const QString &serializedOptions, bool monetRecovery)'),
                            ('    if (activateTabIfAlreadyOpen) {', '    if (activateTabIfAlreadyOpen && !monetRecovery) {'),
                            ('bool Shell::queryClose()\n{', 'bool Shell::queryClose()\n{\n    const auto monetGeneration = monetDocumentDepartureGeneration();\n    const int monetActiveIndex = m_tabWidget->currentIndex();\n    const QPointer<KParts::ReadWritePart> monetActivePart = monetActiveIndex >= 0 && monetActiveIndex < m_tabs.size() ? m_tabs[monetActiveIndex].part : nullptr;'),
                            ('    for (int i = 0; i < m_tabs.size(); ++i) {\n        KParts::ReadWritePart *const part = m_tabs[i].part;\n\n        // To resolve confusion',
                             '    if (monetGeneration != monetDocumentDepartureGeneration()) return false;\n    for (int i = 0; i < m_tabs.size(); ++i) {\n        KParts::ReadWritePart *const part = m_tabs[i].part;\n\n        // To resolve confusion'),
                            ('        if (!part->queryClose()) {\n            return false;\n        }\n    }\n    return true;',
                             '        if (!part->queryClose() || monetGeneration != monetDocumentDepartureGeneration()) {\n            return false;\n        }\n    }\n    return monetFinishDocumentDeparture(monetGeneration, monetActivePart);'),
                            ('        QDBusConnection::sessionBus().registerObject(QStringLiteral("/okularshell"), this, QDBusConnection::ExportScriptableSlots);',
                             '        QDBusConnection::sessionBus().registerObject(QStringLiteral("/okularshell"), this, QDBusConnection::ExportScriptableSlots);\n'
                             '        static quint64 monetWindowSequence = 0;\n'
                             '        QDBusConnection::sessionBus().registerObject(QStringLiteral("/MonetDocuments/window%1").arg(++monetWindowSequence), this, QDBusConnection::ExportScriptableSlots);')],
        "shell/shell.h": [("    Q_SCRIPTABLE bool canOpenDocs(int numDocs, int desktop);",
                           "    Q_SCRIPTABLE bool canOpenDocs(int numDocs, int desktop);\n"
                           "    Q_SCRIPTABLE QString monetDocumentState() const;\n"
                           "    Q_SCRIPTABLE QString monetDocumentWindows() const;\n"
                           "    Q_SCRIPTABLE QString monetAppendDocument(const QString &text);\n"
                           "    Q_SCRIPTABLE bool monetDocumentDeparture(const QString &token, bool armed, const QDBusMessage &message);"),
                          ('#include <QAction>', '#include <QAction>\n#include <QDBusMessage>'),
                          ('    bool queryClose() override;', '    bool queryClose() override;\n    bool monetFinishDocumentDeparture(quint64 generation, KParts::ReadWritePart *active);\n    bool monetRestoreDocumentState(const QString &text);'),
                          ('    void openNewTab(const QUrl &url, const QString &serializedOptions);',
                           '    void openNewTab(const QUrl &url, const QString &serializedOptions, bool monetRecovery = false);')],
        "shell/CMakeLists.txt": [("add_executable(okular ${okular_SRCS})",
                                 "find_package(Qt6 REQUIRED COMPONENTS GuiPrivate)\n"
                                 "find_package(PkgConfig REQUIRED)\n"
                                 "pkg_check_modules(MonetWayland REQUIRED IMPORTED_TARGET wayland-client)\n"
                                 "add_executable(okular ${okular_SRCS})\n"
                                 "target_link_libraries(okular Qt6::GuiPrivate PkgConfig::MonetWayland)")],
    }
    pending = {}
    for name, edits in changes.items():
        text = (root / name).read_text()
        if "monetDocumentState" in text:
            raise ValueError("Okular source already patched: " + name)
        for before, after in edits:
            if text.count(before) != 1:
                raise ValueError("Okular source changed or already patched: " + name)
            text = text.replace(before, after)
        pending[name] = text
    shell = pending["shell/shell.cpp"]
    if "monetDocumentState" in shell:
        raise ValueError("Okular shell already patched")
    pending["shell/shell.cpp"] = shell + "\n" + "\n".join((here / name).read_text() for name in ("window-state.cpp", "departure.cpp", "restore.cpp", "retry.cpp"))
    for name, text in pending.items():
        (root / name).write_text(text)


if __name__ == "__main__":
    apply(Path(sys.argv[1]))
