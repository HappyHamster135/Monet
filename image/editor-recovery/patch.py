#!/usr/bin/python3
"""Guard each native close hook so upstream changes fail the image build."""
from pathlib import Path
import shutil
import sys


def patch(root):
    lib = root / "apps/lib"
    changes = {
        "kateviewspace.h": [("#include <QWidget>", "#include <QWidget>\n#include <QHash>\n#include <QJsonArray>\n#include <QJsonObject>"),
                            ("    KTextEditor::View *findViewForDocument(KTextEditor::Document *doc) const",
                             "    int monetCursor(KTextEditor::Document *doc) const;\n    QJsonArray monetScroll(KTextEditor::Document *doc) const;\n    QJsonObject monetSelection(KTextEditor::Document *doc) const;\n    QJsonObject monetFolding(KTextEditor::Document *doc) const;\n    void monetApplyFolding(KTextEditor::View *view, const QJsonObject &folding);\n    void monetApplySelection(KTextEditor::View *view, const QJsonObject &selection);\n    void monetApplyScroll(KTextEditor::Document *doc);\n    void monetRestoreCursor(KTextEditor::Document *doc, int offset, const QJsonArray &scroll = {}, const QJsonObject &selection = {}, const QJsonObject &folding = {}, bool newlyCreated = false);\n\n    KTextEditor::View *findViewForDocument(KTextEditor::Document *doc) const"),
                            ("    std::unordered_map<KTextEditor::Document *, KTextEditor::View *> m_docToView;",
                             "    QHash<KTextEditor::Document *, int> m_monetCursors;\n    QHash<KTextEditor::Document *, QJsonArray> m_monetScrolls;\n    QHash<KTextEditor::Document *, QJsonObject> m_monetSelections;\n    QHash<KTextEditor::Document *, QJsonObject> m_monetFoldings;\n    std::unordered_map<KTextEditor::Document *, KTextEditor::View *> m_docToView;")],
        "kateviewspace.cpp": [("    connect(v, &KTextEditor::View::cursorPositionChanged, this, [this](KTextEditor::View *view, const KTextEditor::Cursor &newPosition) {",
                               "    // Restore this pane's pending position after the normal shared-view initialization.\n    if (m_monetFoldings.contains(doc)) monetApplyFolding(v, m_monetFoldings.take(doc));\n    if (m_monetCursors.contains(doc)) {\n        const int offset = qMin(m_monetCursors.take(doc), doc->cursorToOffset(doc->documentEnd()));\n        v->setCursorPosition(doc->offsetToCursor(offset));\n    }\n    if (m_monetSelections.contains(doc)) monetApplySelection(v, m_monetSelections.take(doc));\n\n    connect(v, &KTextEditor::View::cursorPositionChanged, this, [this](KTextEditor::View *view, const KTextEditor::Cursor &newPosition) {"),
                              ("    auto *invalidDoc = static_cast<KTextEditor::Document *>(doc);",
                               "    auto *invalidDoc = static_cast<KTextEditor::Document *>(doc);\n    m_monetCursors.remove(invalidDoc);\n    m_monetScrolls.remove(invalidDoc);\n    m_monetSelections.remove(invalidDoc);\n    m_monetFoldings.remove(invalidDoc);"),
                              ("        kv->show();", "        kv->show();\n        monetApplyScroll(kv->document());")],
        "kateviewmanager.cpp": [("    QTimer::singleShot(0, this, [this] {",
                                 '    QTimer::singleShot(0, this, [this, recovery = config.readEntry("Monet Recovery", false)] {\n        if (recovery) return;')],
        "kateviewmanager.h": [("    void documentSavedOrUploaded(KTextEditor::Document *document, bool saveAs);",
                               "    friend bool monetReopenDocuments(const QString &request);\n\n    void documentSavedOrUploaded(KTextEditor::Document *document, bool saveAs);")],
        "kateapp.h": [("    static KateApp *self();", "    static KateApp *self();\n\n    bool monetTemporaryPath(QObject *document, const QString &path) const\n    {\n        return m_tempFilesToDelete.value(document).contains(path);\n    }")],
        "CMakeLists.txt": [("    kateapp.cpp\n", "    kateapp.cpp\n    monetdeparture.cpp\n"),
                           ('add_library(kateprivate SHARED "")', 'add_library(kateprivate SHARED "")\nfind_package(Qt6 REQUIRED COMPONENTS GuiPrivate)\nfind_package(PkgConfig REQUIRED)\npkg_check_modules(MonetWayland REQUIRED IMPORTED_TARGET wayland-client)\ntarget_link_libraries(kateprivate PRIVATE Qt6::GuiPrivate PkgConfig::MonetWayland)')],
        "kateappadaptor.h": [("#include <QDBusAbstractAdaptor>", "#include <QDBusAbstractAdaptor>\n#include <QDBusMessage>"), ("public Q_SLOTS:\n", "public Q_SLOTS:\n    bool monetDeparture(const QString &token, bool armed);\n    bool monetDepartureWindows(const QString &token, bool armed, const QDBusMessage &message);\n    QString monetEditorState(const QString &restore);\n    QString monetEditorWindows(const QString &restore);\n    bool monetReopenDocuments(const QString &request);\n    QString monetReplaceWindow(const QString &request);\n")],
        "kateappadaptor.cpp": [("#include \"kateappadaptor.h\"", '#include "kateappadaptor.h"\n#include "monetdeparture.h"'),
                               ("KateAppAdaptor::KateAppAdaptor()", "bool KateAppAdaptor::monetDeparture(const QString &token, bool armed)\n{\n    return monetArmDeparture(token, armed);\n}\n\nbool KateAppAdaptor::monetDepartureWindows(const QString &token, bool armed, const QDBusMessage &message)\n{\n    return monetArmDeparture(token, armed, true, message.service());\n}\n\nQString KateAppAdaptor::monetEditorState(const QString &restore)\n{\n    return ::monetEditorState(restore);\n}\n\nQString KateAppAdaptor::monetEditorWindows(const QString &restore)\n{\n    return ::monetEditorWindows(restore);\n}\n\nbool KateAppAdaptor::monetReopenDocuments(const QString &request)\n{\n    return ::monetReopenDocuments(request);\n}\n\nQString KateAppAdaptor::monetReplaceWindow(const QString &request)\n{\n    return ::monetReplaceWindow(request);\n}\n\nKateAppAdaptor::KateAppAdaptor()")],
        "kateapp.cpp": [("#include \"kateapp.h\"", '#include "kateapp.h"\n#include "monetdeparture.h"'),
                        ("    if (win && !win->queryClose_internal()) {", "    const auto monetGeneration = monetDepartureGeneration();\n    if (win && !win->queryClose_internal()) {"),
                        ("    //  we are ready to quit, ignore any unix signals now", "    if (monetGeneration != monetDepartureGeneration() || !monetFinishDeparture()) {\n        return;\n    }\n\n    //  we are ready to quit, ignore any unix signals now")],
        "katemainwindow.cpp": [("    KateUpdateDisabler disableUpdates(this);", '    KateUpdateDisabler disableUpdates(this);\n    const bool monetRecovery = KConfigGroup(sconfig, sgroup).readEntry("Monet Recovery", false);\n    if (monetRecovery) setAttribute(Qt::WA_ShowWithoutActivating);'),
                               ("    // trigger proper focus restore\n    m_viewManager->triggerActiveViewFocus();", "    // Recovery windows must not steal the surviving window's focus.\n    if (!monetRecovery) m_viewManager->triggerActiveViewFocus();"),
                               ("#include \"katemainwindow.h\"", '#include "katemainwindow.h"\n#include "monetdeparture.h"'),
                               ("    if (KateApp::self()->mainWindowsCount() > 1) {\n        return winClosesDocuments() ? queryClose_internal(nullptr, this) : true;\n    }", "    if (monetGroupDeparture()) {\n        // Keep shared buffers and all sibling windows alive until native Quit succeeds.\n        KateApp::self()->shutdownKate(this);\n        return false;\n    }\n    if (KateApp::self()->mainWindowsCount() > 1) {\n        monetComplexDeparture();\n        const auto monetGeneration = monetDepartureGeneration();\n        const bool accepted = winClosesDocuments() ? queryClose_internal(nullptr, this) : true;\n        return accepted && monetGeneration == monetDepartureGeneration();\n    }"),
                               ("    if (queryClose_internal()) {\n        // We are ready to quit", "    const auto monetGeneration = monetDepartureGeneration();\n    if (queryClose_internal()) {\n        if (monetGeneration != monetDepartureGeneration() || !monetFinishDeparture()) {\n            return false;\n        }\n        // We are ready to quit")],
    }
    for name, replacements in changes.items():
        path = lib / name
        text = path.read_text(encoding="utf-8")
        for before, after in replacements:
            if text.count(before) != 1:
                raise ValueError(f"Upstream editor close hook changed: {name}")
            text = text.replace(before, after)
        path.write_text(text, encoding="utf-8")
    for name in ("monetdeparture.h", "monetdeparture.cpp", "monetselection.h"):
        shutil.copyfile(Path(__file__).with_name(name), lib / name)


if __name__ == "__main__":
    patch(Path(sys.argv[1]))
