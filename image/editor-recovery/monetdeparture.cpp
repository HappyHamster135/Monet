// SPDX-License-Identifier: GPL-3.0-or-later
#include "monetdeparture.h"
#include "monetselection.h"
#include "kateapp.h"
#include "katedocmanager.h"
#include "katesessionmanager.h"
#include "katemainwindow.h"
#include "kateviewmanager.h"
#include "kateviewspace.h"
#include <KConfig>
#include <KConfigGroup>
#include <QCryptographicHash>
#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusMessage>
#include <QDBusMetaType>
#include <QDBusReply>
#include <QDBusServiceWatcher>
#include <QDir>
#include <QEvent>
#include <QFileInfo>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMap>
#include <QPointer>
#include <QRegularExpression>
#include <QSaveFile>
#include <QScrollBar>
#include <QSet>
#include <QStandardPaths>
#include <QTimer>
#include <QUuid>
#include <QWindow>
#include <qpa/qplatformnativeinterface.h>
#include <wayland-client-core.h>
#include <algorithm>
#include <functional>
#include <limits>
#include <sys/stat.h>
#include <unistd.h>

namespace {
bool validFolding(const QJsonValue &value)
{
    if (value.isNull()) return true;
    const auto state = value.toObject();
    static const QRegularExpression checksum(QStringLiteral("\\A[0-9a-f]{40}\\z"));
    if (!value.isObject() || state.keys() != QStringList{QStringLiteral("checksum"), QStringLiteral("ranges")}
        || !checksum.match(state.value(QStringLiteral("checksum")).toString()).hasMatch()
        || !state.value(QStringLiteral("ranges")).isArray() || state.value(QStringLiteral("ranges")).toArray().size() > 1024) return false;
    QList<KTextEditor::Range> parents;
    auto previous = KTextEditor::Cursor::invalid();
    for (const auto &entry : state.value(QStringLiteral("ranges")).toArray()) {
        const auto span = entry.toObject();
        if (!entry.isObject() || span.keys() != QStringList{QStringLiteral("endColumn"), QStringLiteral("endLine"),
            QStringLiteral("flags"), QStringLiteral("startColumn"), QStringLiteral("startLine")}) return false;
        for (auto it = span.begin(); it != span.end(); ++it) {
            if (!it.value().isDouble() || it.value().toInt(-1) < 0 || it.value().toDouble() != it.value().toInt(-1)) return false;
        }
        const KTextEditor::Cursor start(span.value(QStringLiteral("startLine")).toInt(), span.value(QStringLiteral("startColumn")).toInt());
        const KTextEditor::Cursor end(span.value(QStringLiteral("endLine")).toInt(), span.value(QStringLiteral("endColumn")).toInt());
        const KTextEditor::Range range(start, end);
        if (span.value(QStringLiteral("flags")).toInt() > 3 || start >= end || (previous.isValid() && start < previous)) return false;
        while (!parents.isEmpty() && start >= parents.last().end()) parents.removeLast();
        if (!parents.isEmpty() && (end > parents.last().end() || range == parents.last())) return false;
        parents.append(range);
        if (parents.size() > 64) return false;
        previous = start;
    }
    return true;
}

class ScrollRestore final : public QObject
{
public:
    ScrollRestore(KTextEditor::View *view, std::function<void(bool)> finish)
        : QObject(view), m_view(view), m_finish(std::move(finish))
    {
        setObjectName(QStringLiteral("monetScrollRestore"));
        // KTextEditor debounces layout by 16 ms; wait through that resize before scrolling.
        m_timer.setInterval(32);
        m_timer.setSingleShot(true);
        connect(&m_timer, &QTimer::timeout, this, [this] { done(true); });
        connect(view, &KTextEditor::View::cursorPositionChanged, this, [this] { done(false); });
        connect(view, &KTextEditor::View::selectionChanged, this, [this] { done(false); });
        for (auto bar : {view->horizontalScrollBar(), view->verticalScrollBar()}) {
            connect(bar, &QScrollBar::actionTriggered, this, [this] { done(false); });
        }
        qApp->installEventFilter(this);
        m_timer.start();
    }

    bool eventFilter(QObject *object, QEvent *event) override
    {
        auto widget = qobject_cast<QWidget *>(object);
        if (m_finish && widget && (widget == m_view || m_view->isAncestorOf(widget))) {
            if (event->type() == QEvent::Resize) m_timer.start();
            if (event->type() == QEvent::KeyPress || event->type() == QEvent::MouseButtonPress
                || event->type() == QEvent::Wheel || event->type() == QEvent::TouchBegin
                || event->type() == QEvent::InputMethod || event->type() == QEvent::DragEnter) done(false);
        }
        return false;
    }

private:
    void done(bool restore)
    {
        if (!m_finish) return;
        m_timer.stop();
        qApp->removeEventFilter(this);
        auto finish = std::move(m_finish);
        m_finish = {};
        QPointer<ScrollRestore> self = this;
        finish(restore);
        if (self) deleteLater();
    }
    KTextEditor::View *m_view;
    QTimer m_timer;
    std::function<void(bool)> m_finish;
};
}

int KateViewSpace::monetCursor(KTextEditor::Document *doc) const
{
    if (auto view = findViewForDocument(doc)) {
        return qMax(0, doc->cursorToOffset(view->cursorPosition()));
    }
    if (m_monetCursors.contains(doc)) {
        return qMin(m_monetCursors.value(doc), doc->cursorToOffset(doc->documentEnd()));
    }
    const auto session = KateApp::self()->sessionManager()->activeSession();
    if (m_group.isEmpty() || !session || !session->config()) return -1;
    const auto config = session->config();
    QString group = QStringLiteral("%1 %2").arg(m_group, QString::number(KateApp::self()->documentManager()->documentInfo(doc)->sessionConfigId));
    if (!config->hasGroup(group)) group = QStringLiteral("%1 %2").arg(m_group, doc->url().toString());
    if (!config->hasGroup(group)) return -1;
    const KConfigGroup saved(config, group);
    const int line = qBound(0, saved.readEntry("CursorLine", 0), qMax(0, doc->lines() - 1));
    const int column = qBound(0, saved.readEntry("CursorColumn", 0), qMax(0, doc->lineLength(line)));
    return qMax(0, doc->cursorToOffset(KTextEditor::Cursor(line, column)));
}

QJsonArray KateViewSpace::monetScroll(KTextEditor::Document *doc) const
{
    if (m_monetScrolls.contains(doc)) return m_monetScrolls.value(doc);
    if (auto view = findViewForDocument(doc)) {
        const int line = qMax(0, view->firstDisplayedLine());
        const auto top = view->coordinatesToCursor(view->textAreaRect().topLeft());
        const bool wrapped = view->configValue(QStringLiteral("dynamic-word-wrap")).toBool();
        return {line, wrapped && top.isValid() && top.line() == line ? top.column() : 0, view->horizontalScrollBar()->value(), wrapped};
    }
    const auto session = KateApp::self()->sessionManager()->activeSession();
    if (m_group.isEmpty() || !session || !session->config()) return {};
    const auto config = session->config();
    QString group = QStringLiteral("%1 %2").arg(m_group, QString::number(KateApp::self()->documentManager()->documentInfo(doc)->sessionConfigId));
    if (!config->hasGroup(group)) group = QStringLiteral("%1 %2").arg(m_group, doc->url().toString());
    const KConfigGroup saved(config, group);
    return saved.hasKey("ScrollLine") ? QJsonArray{qBound(0, saved.readEntry("ScrollLine", 0), qMax(0, doc->lines() - 1)), 0, 0,
        saved.hasKey("Dynamic Word Wrap") ? QJsonValue(saved.readEntry("Dynamic Word Wrap", false)) : QJsonValue(QJsonValue::Null)} : QJsonArray{};
}

QJsonObject KateViewSpace::monetSelection(KTextEditor::Document *doc) const
{
    if (m_monetSelections.contains(doc)) return m_monetSelections.value(doc);
    const auto view = findViewForDocument(doc);
    if (!view) return {};
    if (view->cursorPositions().size() > 1) {
        QJsonObject state;
        if (view->metaObject()->indexOfMethod("monetSelectionState(QJsonObject)") >= 0)
            QMetaObject::invokeMethod(view, "monetSelectionState", Qt::DirectConnection, Q_RETURN_ARG(QJsonObject, state), Q_ARG(QJsonObject, QJsonObject{}));
        return monetValidSelection(state) ? state : QJsonObject{};
    }
    if (!view->selection() && !view->blockSelection()) return {};
    const auto cursor = view->cursorPosition();
    const auto range = view->selectionRange();
    return {{QStringLiteral("block"), view->blockSelection()},
            {QStringLiteral("cursor"), QJsonArray{cursor.line(), cursor.column()}},
            {QStringLiteral("range"), range.isValid() ? QJsonValue(QJsonArray{range.start().line(), range.start().column(),
                range.end().line(), range.end().column()}) : QJsonValue(QJsonValue::Null)}};
}

QJsonObject KateViewSpace::monetFolding(KTextEditor::Document *doc) const
{
    if (doc->isModified()) return {};
    if (m_monetFoldings.contains(doc)) {
        const auto folding = m_monetFoldings.value(doc);
        return folding.value(QStringLiteral("checksum")).toString().toLatin1() == doc->checksum().toHex() ? folding : QJsonObject{};
    }
    QJsonObject state;
    if (auto view = findViewForDocument(doc)) {
        KConfig config(QString(), KConfig::SimpleConfig);
        KConfigGroup group(&config, QStringLiteral("View"));
        view->writeSessionConfig(group);
        state = QJsonDocument::fromJson(group.readEntry("TextFolding", QByteArray())).object();
        if (state.isEmpty()) state = {{QStringLiteral("checksum"), QString::fromLatin1(doc->checksum().toHex())},
                                     {QStringLiteral("ranges"), QJsonArray{}}};
    } else if (auto session = KateApp::self()->sessionManager()->activeSession()) {
        const auto config = session->config();
        QString group = QStringLiteral("%1 %2").arg(m_group, QString::number(KateApp::self()->documentManager()->documentInfo(doc)->sessionConfigId));
        if (!config->hasGroup(group)) group = QStringLiteral("%1 %2").arg(m_group, doc->url().toString());
        state = QJsonDocument::fromJson(KConfigGroup(config, group).readEntry("TextFolding", QByteArray())).object();
    }
    return validFolding(state) ? state : QJsonObject{};
}

void KateViewSpace::monetApplyFolding(KTextEditor::View *view, const QJsonObject &folding)
{
    if (folding.isEmpty() || view->property("monetFoldingRestored").toBool() || view->document()->isModified()
        || folding.value(QStringLiteral("checksum")).toString().toLatin1() != view->document()->checksum().toHex()) return;
    view->setProperty("monetFoldingRestored", true);
    // Round-trip current view settings in memory; only the folding entry is replaced.
    KConfig config(QString(), KConfig::SimpleConfig);
    KConfigGroup group(&config, QStringLiteral("View"));
    view->writeSessionConfig(group);
    group.writeEntry("TextFolding", QJsonDocument(folding).toJson(QJsonDocument::Compact));
    view->readSessionConfig(group);
}

void KateViewSpace::monetApplySelection(KTextEditor::View *target, const QJsonObject &selection)
{
    if (selection.isEmpty() || target->property("monetSelectionRestored").toBool()) return;
    QPointer<KTextEditor::View> view = target;
    QPointer<KTextEditor::Document> doc = view->document();
    if (selection.contains(QStringLiteral("secondary"))) {
        QJsonObject restored;
        if (view->metaObject()->indexOfMethod("monetSelectionState(QJsonObject)") >= 0
            && QMetaObject::invokeMethod(view, "monetSelectionState", Qt::DirectConnection,
                                        Q_RETURN_ARG(QJsonObject, restored), Q_ARG(QJsonObject, selection)) && view)
            view->setProperty("monetSelectionRestored", true);
        return;
    }
    view->setProperty("monetSelectionRestored", true);
    const bool block = selection.value(QStringLiteral("block")).toBool();
    auto cursor = [doc, block](const QJsonArray &value, int index) {
        if (!block && value[index].toInt() >= doc->lines()) return doc->documentEnd();
        const int line = qMin(value[index].toInt(), qMax(0, doc->lines() - 1));
        const int column = value[index + 1].toInt();
        return KTextEditor::Cursor(line, block ? column : qMin(column, qMax(0, doc->lineLength(line))));
    };
    view->setBlockSelection(block);
    if (!view || !doc) return;
    view->setCursorPosition(cursor(selection.value(QStringLiteral("cursor")).toArray(), 0));
    if (!view || !doc) return;
    const auto range = selection.value(QStringLiteral("range"));
    if (range.isNull()) view->removeSelection();
    else view->setSelection(KTextEditor::Range(cursor(range.toArray(), 0), cursor(range.toArray(), 2)));
}

void KateViewSpace::monetApplyScroll(KTextEditor::Document *doc)
{
    QPointer<KTextEditor::View> view = findViewForDocument(doc);
    if (!view || !view->isVisible() || !m_monetScrolls.contains(doc)) return;
    if (view->findChild<QObject *>(QStringLiteral("monetScrollRestore"), Qt::FindDirectChildrenOnly)) return;
    const auto scroll = m_monetScrolls.value(doc);
    if (scroll[3].isBool()) view->setConfigValue(QStringLiteral("dynamic-word-wrap"), scroll[3].toBool());
    if (!view) return;
    QPointer<KateViewSpace> pane = this;
    QPointer<KTextEditor::Document> document = doc;
    new ScrollRestore(view, [pane, document, view](bool restore) {
        if (!pane || !document) return;
        if (restore && view && !view->isVisible()) return;
        const auto scroll = pane->m_monetScrolls.take(document);
        if (!restore || !view || scroll.isEmpty()) return;
        const int line = qMin(scroll[0].toInt(), qMax(0, document->lines() - 1));
        const int column = qMin(scroll[1].toInt(), qMax(0, document->lineLength(line)));
        view->setScrollPosition(KTextEditor::Cursor(line, column));
        if (view) view->setHorizontalScrollPosition(scroll[2].toInt());
    });
}

void KateViewSpace::monetRestoreCursor(KTextEditor::Document *doc, int offset, const QJsonArray &scroll, const QJsonObject &selection, const QJsonObject &folding, bool newlyCreated)
{
    if (!hasDocument(doc) || (offset < 0 && scroll.isEmpty() && selection.isEmpty() && folding.isEmpty())) return;
    if (auto view = findViewForDocument(doc)) {
        // Scrolling or selecting after reopening belongs to the person too.
        if (newlyCreated || (view->cursorPosition() == KTextEditor::Cursor(0, 0) && view->cursorPositions().size() == 1 && !view->selection() && !view->blockSelection()
            && !view->property("monetSelectionRestored").toBool()
            && view->firstDisplayedLine() == 0 && view->horizontalScrollBar()->value() == 0
            && monetFolding(doc).value(QStringLiteral("ranges")).toArray().isEmpty())) {
            QPointer<KateViewSpace> pane = this;
            QPointer<KTextEditor::Document> document = doc;
            if (!scroll.isEmpty() && !m_monetScrolls.contains(doc)) m_monetScrolls.insert(doc, scroll);
            monetApplyFolding(view, folding);
            if (!pane || !document || pane->findViewForDocument(document) != view) return;
            if (offset >= 0) view->setCursorPosition(doc->offsetToCursor(qMin(offset, doc->cursorToOffset(doc->documentEnd()))));
            if (pane && document && pane->findViewForDocument(document)) monetApplySelection(pane->findViewForDocument(document), selection);
            if (pane && document) monetApplyScroll(document);
        }
    } else {
        if (offset >= 0 && !m_monetCursors.contains(doc)) m_monetCursors.insert(doc, offset);
        if (!scroll.isEmpty() && !m_monetScrolls.contains(doc)) m_monetScrolls.insert(doc, scroll);
        if (!selection.isEmpty() && !m_monetSelections.contains(doc)) m_monetSelections.insert(doc, selection);
        if (!folding.isEmpty() && !m_monetFoldings.contains(doc)) m_monetFoldings.insert(doc, folding);
    }
}

namespace {
struct CursorPane {
    QPointer<KateViewSpace> pane;
    QList<QPointer<KTextEditor::Document>> documents;
};
QString departureToken;
bool complexDeparture = false;
quint64 departureGeneration = 0;
QList<QPointer<KateMainWindow>> departureWindows;
QStringList departureWindowIds;
QString departureOwner;
QPointer<QDBusServiceWatcher> departureWatcher;

void clearDeparture()
{
    departureToken.clear();
    departureWindows.clear();
    departureWindowIds.clear();
    departureOwner.clear();
    if (departureWatcher) {
        departureWatcher->setWatchedServices({});
    }
    ++departureGeneration;
}

QString receiptPath(const QString &token)
{
    const QString runtime = QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation);
    struct stat info;
    auto privateDirectory = [&info](const QString &path) {
        return lstat(QFile::encodeName(path).constData(), &info) == 0 && S_ISDIR(info.st_mode)
            && info.st_uid == getuid() && (info.st_mode & 0777) == 0700;
    };
    if (!privateDirectory(runtime)) {
        return {};
    }
    const QString directory = runtime + QStringLiteral("/monet-editor");
    // mkdir's mode is private from creation; never follow or chmod an existing link.
    mkdir(QFile::encodeName(directory).constData(), 0700);
    if (!privateDirectory(directory)) {
        return {};
    }
    return directory + QLatin1Char('/') + token + QLatin1Char('-') + QCoreApplication::applicationName()
        + QLatin1Char('-') + QString::number(QCoreApplication::applicationPid()) + QStringLiteral(".json");
}

QString localPath(KTextEditor::Document *doc)
{
    if (!doc || !doc->url().isLocalFile()) {
        return {};
    }
    const QString path = doc->url().toLocalFile();
    if (!path.startsWith(QLatin1Char('/')) || path.size() > 8192 || KateApp::self()->monetTemporaryPath(doc, path)) {
        return {};
    }
    for (const auto c : path) {
        if (c.unicode() < 32) {
            return {};
        }
    }
    return path;
}

QJsonValue windowState(KateMainWindow *window, bool &supported, QList<CursorPane> *visible = nullptr, QSet<QString> *allPaths = nullptr)
{
    supported = false;
    QJsonArray views;
    QSet<QString> captured;
    int active = 0, tabs = 0, nodes = 0;
    bool complete = true;
    std::function<QJsonValue(QWidget *, int)> collect = [&](QWidget *widget, int depth) -> QJsonValue {
        if (depth > 16 || ++nodes > 64) {
            complete = false;
            return QJsonValue::Null;
        }
        if (auto splitter = qobject_cast<QSplitter *>(widget)) {
            QJsonArray children, sizes;
            if (splitter->count() < 1 || splitter->count() > 16) {
                complete = false;
                return QJsonValue::Null;
            }
            const auto lengths = splitter->sizes();
            for (int i = 0; i < splitter->count(); ++i) {
                auto child = collect(splitter->widget(i), depth + 1);
                if (!child.isNull()) {
                    children.append(child);
                    sizes.append(qBound(1, lengths.at(i), 100000));
                }
            }
            if (children.isEmpty()) {
                return QJsonValue::Null;
            }
            if (children.size() == 1) {
                return children.at(0);
            }
            return QJsonObject{{QStringLiteral("children"), children}, {QStringLiteral("sizes"), sizes},
                               {QStringLiteral("orientation"), int(splitter->orientation())}};
        }
        auto pane = qobject_cast<KateViewSpace *>(widget);
        if (!pane || pane->documentList().size() > 200 || views.size() >= 16) {
            complete = false;
            return QJsonValue::Null;
        }
        auto current = pane->currentView();
        const QString selected = current ? localPath(current->document()) : QString();
        QJsonArray documents;
        QJsonArray cursors, scrolls, selections, foldings;
        CursorPane target{pane, {}};
        int selectedIndex = 0;
        for (const auto &item : pane->documentList()) {
            const auto path = localPath(item.doc());
            if (path.isEmpty() || documents.contains(path)) {
                continue;
            }
            if (path == selected) {
                selectedIndex = documents.size();
            }
            documents.append(path);
            const int offset = path == selected ? -1 : pane->monetCursor(item.doc());
            cursors.append(offset < 0 ? QJsonValue(QJsonValue::Null) : QJsonValue(offset));
            const auto scroll = pane->monetScroll(item.doc());
            scrolls.append(scroll.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(scroll));
            const auto selection = pane->monetSelection(item.doc());
            selections.append(selection.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(selection));
            const auto folding = pane->monetFolding(item.doc());
            foldings.append(folding.isEmpty() ? QJsonValue(QJsonValue::Null) : QJsonValue(folding));
            target.documents.append(item.doc());
            captured.insert(path);
        }
        if (documents.isEmpty()) {
            return QJsonValue::Null;
        }
        if (pane->isActiveSpace()) {
            active = views.size();
        }
        const int cursor = current && !selected.isEmpty() ? qMax(0, current->document()->cursorToOffset(current->cursorPosition()))
                                                        : cursors.at(selectedIndex).toInt(0);
        const int index = views.size();
        cursors[selectedIndex] = QJsonValue::Null;
        QJsonObject state{{QStringLiteral("documents"), documents}, {QStringLiteral("active"), selectedIndex},
                          {QStringLiteral("cursor"), cursor}, {QStringLiteral("cursors"), cursors}, {QStringLiteral("scrolls"), scrolls}};
        if (std::any_of(selections.begin(), selections.end(), [](const QJsonValue &v) { return !v.isNull(); })) state.insert(QStringLiteral("selections"), selections);
        if (std::any_of(foldings.begin(), foldings.end(), [](const QJsonValue &v) { return !v.isNull(); })) state.insert(QStringLiteral("foldings"), foldings);
        views.append(state);
        if (visible) {
            visible->append(target);
        }
        tabs += documents.size();
        return index;
    };
    const auto layout = collect(window->viewManager(), 0);
    if (!complete || tabs > 200) {
        return QJsonValue::Null;
    }
    if (allPaths) {
        allPaths->unite(captured);
    }
    supported = true;
    if (views.isEmpty()) {
        return QJsonValue::Null; // Discarded untitled tabs have no saved file to reopen.
    }
    return QJsonObject{{QStringLiteral("views"), views}, {QStringLiteral("active"), active}, {QStringLiteral("layout"), layout}};
}

bool coversDocuments(const QSet<QString> &captured)
{
    for (auto doc : KateApp::self()->documents()) {
        const auto path = localPath(doc);
        if (!path.isEmpty() && !captured.contains(path)) {
            return false;
        }
    }
    return true;
}

QJsonValue finalState(bool &supported, QList<CursorPane> *visible = nullptr)
{
    supported = false;
    auto app = KateApp::self();
    if (app->mainWindowsCount() != 1) {
        return QJsonValue::Null;
    }
    QSet<QString> paths;
    const auto state = windowState(app->mainWindow(0), supported, visible, &paths);
    supported = supported && coversDocuments(paths);
    return supported ? state : QJsonValue::Null;
}

QJsonValue shape(QJsonValue node)
{
    if (!node.isObject()) {
        return node;
    }
    auto object = node.toObject();
    object.remove(QStringLiteral("sizes"));
    QJsonArray children;
    for (auto child : object.value(QStringLiteral("children")).toArray()) {
        children.append(shape(child));
    }
    object.insert(QStringLiteral("children"), children);
    return object;
}

bool cursorOffsets(QJsonValue value, int count, QJsonArray &offsets)
{
    if (value.isUndefined()) {
        for (int i = 0; i < count; ++i) offsets.append(QJsonValue::Null);
        return true;
    }
    if (!value.isArray() || value.toArray().size() != count) return false;
    offsets = value.toArray();
    for (const auto &offset : offsets) {
        if (!offset.isNull() && (!offset.isDouble() || offset.toInt(-1) < 0 || offset.toDouble() != offset.toInt(-1))) return false;
    }
    return true;
}

bool scrollPositions(QJsonValue value, int count, QJsonArray &positions)
{
    if (value.isUndefined()) return cursorOffsets(value, count, positions);
    if (!value.isArray() || value.toArray().size() != count) return false;
    positions = value.toArray();
    for (const auto &position : positions) {
        if (position.isNull()) continue;
        if (!position.isArray() || position.toArray().size() != 4) return false;
        const auto coordinates = position.toArray();
        if (!coordinates[3].isNull() && !coordinates[3].isBool()) return false;
        for (int i = 0; i < 3; ++i) {
            const auto coordinate = coordinates[i];
            if (!coordinate.isDouble() || coordinate.toInt(-1) < 0 || coordinate.toDouble() != coordinate.toInt(-1)) return false;
        }
    }
    return true;
}

bool selectionStates(QJsonValue value, int count, QJsonArray &selections)
{
    if (value.isUndefined()) return cursorOffsets(value, count, selections);
    if (!value.isArray() || value.toArray().size() != count) return false;
    selections = value.toArray();
    return std::all_of(selections.begin(), selections.end(), [](const QJsonValue &v) { return monetValidSelection(v); });
}

bool foldingStates(QJsonValue value, int count, QJsonArray &foldings)
{
    if (value.isUndefined()) return cursorOffsets(value, count, foldings);
    if (!value.isArray() || value.toArray().size() != count) return false;
    foldings = value.toArray();
    return std::all_of(foldings.begin(), foldings.end(), [](const QJsonValue &v) { return validFolding(v); });
}

bool cursorRequest(const QJsonObject &state, const QJsonObject &request, QJsonArray &positions)
{
    auto expected = request;
    auto metadata = state;
    expected.insert(QStringLiteral("layout"), shape(expected.value(QStringLiteral("layout"))));
    metadata.insert(QStringLiteral("layout"), shape(metadata.value(QStringLiteral("layout"))));
    const auto actualViews = metadata.value(QStringLiteral("views")).toArray();
    const auto expectedViews = expected.value(QStringLiteral("views")).toArray();
    if (expectedViews.size() != actualViews.size()) {
        return false;
    }
    for (int i = 0; i < expectedViews.size(); ++i) {
        auto item = expectedViews.at(i).toObject();
        const auto cursor = item.value(QStringLiteral("cursor"));
        if (!cursor.isDouble() || cursor.toInt(-1) < 0 || cursor.toDouble() != cursor.toInt(-1)) {
            return false;
        }
        auto actual = actualViews.at(i).toObject();
        QJsonArray offsets, scrolls, selections, foldings;
        const int active = actual.value(QStringLiteral("active")).toInt();
        if (!cursorOffsets(item.value(QStringLiteral("cursors")), actual.value(QStringLiteral("documents")).toArray().size(), offsets)
            || !scrollPositions(item.value(QStringLiteral("scrolls")), offsets.size(), scrolls)
            || !selectionStates(item.value(QStringLiteral("selections")), offsets.size(), selections)
            || !foldingStates(item.value(QStringLiteral("foldings")), offsets.size(), foldings)
            || !offsets.at(active).isNull()) return false;
        offsets[active] = cursor;
        positions.append(QJsonObject{{QStringLiteral("cursors"), offsets}, {QStringLiteral("scrolls"), scrolls},
                                     {QStringLiteral("selections"), selections}, {QStringLiteral("foldings"), foldings}});
        item.remove(QStringLiteral("cursor"));
        item.remove(QStringLiteral("cursors"));
        item.remove(QStringLiteral("scrolls"));
        item.remove(QStringLiteral("selections"));
        item.remove(QStringLiteral("foldings"));
        actual.remove(QStringLiteral("cursor"));
        actual.remove(QStringLiteral("cursors"));
        actual.remove(QStringLiteral("scrolls"));
        actual.remove(QStringLiteral("selections"));
        actual.remove(QStringLiteral("foldings"));
        if (item != actual) {
            return false;
        }
    }
    expected.insert(QStringLiteral("views"), actualViews);
    if (expected != metadata) {
        return false;
    }
    return true;
}

void restoreCursors(const QList<CursorPane> &visible, const QJsonArray &positions, bool newlyCreated = false)
{
    for (int i = 0; i < visible.size(); ++i) {
        const auto &target = visible.at(i);
        const auto offsets = positions.at(i).toObject().value(QStringLiteral("cursors")).toArray();
        const auto scrolls = positions.at(i).toObject().value(QStringLiteral("scrolls")).toArray();
        const auto selections = positions.at(i).toObject().value(QStringLiteral("selections")).toArray();
        const auto foldings = positions.at(i).toObject().value(QStringLiteral("foldings")).toArray();
        for (int j = 0; j < target.documents.size(); ++j) {
            if (target.pane && target.documents[j] && (!offsets[j].isNull() || !scrolls[j].isNull() || !selections[j].isNull() || !foldings[j].isNull())) {
                target.pane->monetRestoreCursor(target.documents[j], offsets[j].isNull() ? -1 : offsets[j].toInt(), scrolls[j].toArray(), selections[j].toObject(), foldings[j].toObject(), newlyCreated);
            }
        }
    }
}
}

QString monetEditorState(const QString &restore)
{
    bool supported;
    QList<CursorPane> visible;
    auto state = finalState(supported, &visible);
    if (!supported || !state.isObject()) {
        return QStringLiteral("null");
    }
    if (!restore.isEmpty()) {
        QJsonArray positions;
        if (restore.size() > 2 * 1024 * 1024 || !cursorRequest(state.toObject(), QJsonDocument::fromJson(restore.toUtf8()).object(), positions)) {
            return QStringLiteral("null");
        }
        restoreCursors(visible, positions);
        state = finalState(supported);
    }
    return QString::fromUtf8(QJsonDocument(state.toObject()).toJson(QJsonDocument::Compact));
}

QString monetEditorWindows(const QString &restore)
{
    auto app = KateApp::self();
    const int count = app->mainWindowsCount();
    if (count < 1 || count > 16 || QGuiApplication::platformName() != QStringLiteral("wayland") || restore.size() > 2 * 1024 * 1024) {
        return QStringLiteral("null");
    }
    QList<uint> surfaces;
    for (int i = 0; i < count; ++i) {
        auto handle = app->mainWindow(i)->windowHandle();
        auto surface = handle ? static_cast<wl_proxy *>(QGuiApplication::platformNativeInterface()->nativeResourceForWindow(QByteArrayLiteral("surface"), handle)) : nullptr;
        if (!surface) {
            return QStringLiteral("null");
        }
        surfaces.append(wl_proxy_get_id(surface));
    }
    qDBusRegisterMetaType<QList<uint>>();
    auto request = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin"), QStringLiteral("/MonetWindowIdentity"), QStringLiteral("org.monet.WindowIdentity"), QStringLiteral("resolveWindows"));
    request.setArguments({uint(QCoreApplication::applicationPid()), QVariant::fromValue(surfaces)});
    QDBusReply<QStringList> reply = QDBusConnection::sessionBus().call(request, QDBus::Block, 500);
    const auto ids = reply.value();
    if (!reply.isValid() || ids.size() != count || QSet<QString>(ids.begin(), ids.end()).size() != count) {
        return QStringLiteral("null");
    }
    QJsonArray states;
    QList<QList<CursorPane>> visible(count);
    QSet<QString> paths;
    int tabs = 0;
    for (int i = 0; i < count; ++i) {
        bool supported;
        const auto state = windowState(app->mainWindow(i), supported, &visible[i], &paths);
        if (!supported || QUuid(ids[i]).isNull()) {
            return QStringLiteral("null");
        }
        for (const auto &view : state.toObject().value(QStringLiteral("views")).toArray()) {
            tabs += view.toObject().value(QStringLiteral("documents")).toArray().size();
        }
        if (tabs > 200) {
            return QStringLiteral("null");
        }
        states.append(QJsonObject{{QStringLiteral("id"), ids[i]}, {QStringLiteral("editor"), state}});
    }
    const auto bytes = QJsonDocument(states).toJson(QJsonDocument::Compact);
    if (!coversDocuments(paths) || bytes.size() > 2 * 1024 * 1024) {
        return QStringLiteral("null");
    }
    if (!restore.isEmpty()) {
        const auto parsed = QJsonDocument::fromJson(restore.toUtf8());
        const auto expected = parsed.array();
        if (!parsed.isArray() || expected.isEmpty() || expected.size() > count) {
            return QStringLiteral("null");
        }
        QMap<int, QJsonArray> positions;
        for (const auto &value : expected) {
            const auto item = value.toObject();
            const int index = ids.indexOf(item.value(QStringLiteral("id")).toString());
            QJsonArray cursors;
            if (item.keys() != QStringList{QStringLiteral("editor"), QStringLiteral("id")} || index < 0 || positions.contains(index)
                || !states[index].toObject().value(QStringLiteral("editor")).isObject() || !item.value(QStringLiteral("editor")).isObject()
                || !cursorRequest(states[index].toObject().value(QStringLiteral("editor")).toObject(), item.value(QStringLiteral("editor")).toObject(), cursors)) {
                return QStringLiteral("null");
            }
            positions.insert(index, cursors);
        }
        // Validate the whole request before touching any window.
        for (auto it = positions.cbegin(); it != positions.cend(); ++it) {
            restoreCursors(visible[it.key()], it.value());
        }
        return monetEditorWindows({});
    }
    return QString::fromUtf8(bytes);
}

bool monetReopenDocuments(const QString &request)
{
    if (request.size() > 2 * 1024 * 1024) {
        return false;
    }
    const auto parsed = QJsonDocument::fromJson(request.toUtf8());
    const auto object = parsed.object();
    const auto documents = object.value(QStringLiteral("documents")).toArray();
    auto keys = object.keys();
    keys.removeAll(QStringLiteral("cursors"));
    keys.removeAll(QStringLiteral("scrolls"));
    keys.removeAll(QStringLiteral("selections"));
    keys.removeAll(QStringLiteral("foldings"));
    QJsonArray offsets, scrolls, selections, foldings;
    if (!parsed.isObject() || keys != QStringList{QStringLiteral("documents"), QStringLiteral("id")}
        || !object.value(QStringLiteral("id")).isString() || documents.isEmpty() || documents.size() > 200
        || !cursorOffsets(object.value(QStringLiteral("cursors")), documents.size(), offsets)
        || !scrollPositions(object.value(QStringLiteral("scrolls")), documents.size(), scrolls)
        || !selectionStates(object.value(QStringLiteral("selections")), documents.size(), selections)
        || !foldingStates(object.value(QStringLiteral("foldings")), documents.size(), foldings)) {
        return false;
    }
    QStringList paths;
    for (const auto &value : documents) {
        const auto path = value.toString();
        if (!value.isString() || !path.startsWith(QLatin1Char('/')) || path.size() > 8192 || paths.contains(path)
            || !QFileInfo(path).isFile() || std::any_of(path.begin(), path.end(), [](QChar c) { return c.unicode() < 32; })) {
            return false;
        }
        paths.append(path);
    }
    const auto captured = QJsonDocument::fromJson(monetEditorWindows({}).toUtf8());
    if (!captured.isArray()) {
        return false;
    }
    const auto states = captured.array();
    int index = -1, tabs = 0;
    QSet<QString> present;
    for (int i = 0; i < states.size(); ++i) {
        const auto state = states[i].toObject();
        const bool target = state.value(QStringLiteral("id")) == object.value(QStringLiteral("id"));
        if (target) {
            index = i;
        }
        for (const auto &view : state.value(QStringLiteral("editor")).toObject().value(QStringLiteral("views")).toArray()) {
            for (const auto &path : view.toObject().value(QStringLiteral("documents")).toArray()) {
                ++tabs;
                if (target) {
                    present.insert(path.toString());
                }
            }
        }
    }
    if (index < 0) {
        return false;
    }
    QPointer<KateMainWindow> window = KateApp::self()->mainWindow(index);
    QPointer<KateViewSpace> pane = window->viewManager()->activeViewSpace();
    auto manager = KateApp::self()->documentManager();
    const auto panes = window->viewManager()->findChildren<KateViewSpace *>();
    const auto requestedPaths = paths;
    paths.removeIf([&](const QString &path) {
        const auto doc = manager->findDocument(QUrl::fromLocalFile(path));
        return present.contains(path) || (doc && std::any_of(panes.begin(), panes.end(),
            [doc](KateViewSpace *view) { return view->hasDocument(doc); }));
    });
    if (!pane || tabs + paths.size() > 200 || pane->numberOfRegisteredDocuments() + paths.size() > 200) {
        return false;
    }
    for (const auto &path : paths) {
        if (!window || !pane || !QFileInfo(path).isFile()) {
            return false;
        }
        const auto url = QUrl::fromLocalFile(path);
        QPointer<KTextEditor::Document> doc = manager->findDocument(url);
        if (!doc) {
            doc = manager->createDoc();
            if (!doc->openUrl(url) || !QFileInfo(path).isFile()) {
                if (doc) {
                    manager->closeDocument(doc);
                }
                return false;
            }
        }
        if (!window || !pane || !doc) {
            return false;
        }
        // Add the tab to this pane without replacing a shared buffer or selecting a different window.
        QPointer<KTextEditor::View> selected = pane->currentView();
        pane->registerDocument(doc);
        if (!window || !pane || !doc) {
            return false;
        }
        const auto offset = offsets[requestedPaths.indexOf(path)];
        const auto scroll = scrolls[requestedPaths.indexOf(path)];
        pane->monetRestoreCursor(doc, offset.isNull() ? -1 : offset.toInt(), scroll.toArray(), selections[requestedPaths.indexOf(path)].toObject(), foldings[requestedPaths.indexOf(path)].toObject());
        if (!window || !pane || !doc) return false;
        QObject::connect(doc, &KTextEditor::Document::documentSavedOrUploaded,
                         window->viewManager(), &KateViewManager::documentSavedOrUploaded, Qt::UniqueConnection);
        if (selected && pane->currentView() == selected) {
            pane->showView(selected);
        } else if (!pane->currentView()) {
            window->viewManager()->activateView(doc.data(), pane.data());
        }
    }
    return true;
}

QString monetReplaceWindow(const QString &request)
{
    if (request.size() > 2 * 1024 * 1024) {
        return {};
    }
    const auto parsed = QJsonDocument::fromJson(request.toUtf8());
    const auto object = parsed.object();
    const auto oldId = object.value(QStringLiteral("id")).toString();
    const auto anchor = object.value(QStringLiteral("anchor")).toString();
    const auto editor = object.value(QStringLiteral("editor")).toObject();
    const auto views = editor.value(QStringLiteral("views")).toArray();
    const auto integer = [](QJsonValue value, int low, int high) {
        return value.isDouble() && value.toDouble() == value.toInt(-1) && value.toInt(-1) >= low && value.toInt(-1) <= high;
    };
    const auto uuid = [](const QString &id) { return !QUuid(id).isNull() && QUuid(id).toString() == id; };
    const auto attempt = object.value(QStringLiteral("attempt")).toString();
    const auto keys = object.contains(QStringLiteral("attempt"))
        ? QStringList{QStringLiteral("anchor"), QStringLiteral("attempt"), QStringLiteral("editor"), QStringLiteral("id")}
        : QStringList{QStringLiteral("anchor"), QStringLiteral("editor"), QStringLiteral("id")};
    static const QRegularExpression validAttempt(QStringLiteral("\\A[0-9a-f]{32}\\z"));
    if (!parsed.isObject() || object.keys() != keys
        || (object.contains(QStringLiteral("attempt")) && !validAttempt.match(attempt).hasMatch())
        || !uuid(oldId) || !uuid(anchor) || oldId == anchor
        || editor.keys() != QStringList{QStringLiteral("active"), QStringLiteral("layout"), QStringLiteral("views")}
        || views.isEmpty() || views.size() > 16 || !integer(editor.value(QStringLiteral("active")), 0, views.size() - 1)) {
        return {};
    }
    // An empty SimpleConfig stays in memory; never replace the person's named session.
    KConfig config(QString(), KConfig::SimpleConfig);
    const QString groupName = QStringLiteral("MonetRecovery");
    KConfigGroup(&config, groupName).writeEntry("Active ViewSpace", editor.value(QStringLiteral("active")).toInt());
    KConfigGroup(&config, groupName).writeEntry("Monet Recovery", true);
    QStringList paths;
    int tabs = 0;
    for (int i = 0; i < views.size(); ++i) {
        const auto view = views[i].toObject();
        const auto documents = view.value(QStringLiteral("documents")).toArray();
        auto keys = view.keys();
        keys.removeAll(QStringLiteral("cursors"));
        keys.removeAll(QStringLiteral("scrolls"));
        keys.removeAll(QStringLiteral("selections"));
        keys.removeAll(QStringLiteral("foldings"));
        QJsonArray offsets, scrolls, selections, foldings;
        if (keys != QStringList{QStringLiteral("active"), QStringLiteral("cursor"), QStringLiteral("documents")}
            || documents.isEmpty() || documents.size() > 200 || !integer(view.value(QStringLiteral("active")), 0, documents.size() - 1)
            || !integer(view.value(QStringLiteral("cursor")), 0, std::numeric_limits<int>::max()) || (tabs += documents.size()) > 200
            || !cursorOffsets(view.value(QStringLiteral("cursors")), documents.size(), offsets)
            || !scrollPositions(view.value(QStringLiteral("scrolls")), documents.size(), scrolls)
            || !selectionStates(view.value(QStringLiteral("selections")), documents.size(), selections)
            || !foldingStates(view.value(QStringLiteral("foldings")), documents.size(), foldings)
            || !offsets.at(view.value(QStringLiteral("active")).toInt()).isNull()) {
            return {};
        }
        QStringList urls;
        for (const auto &value : documents) {
            const auto path = value.toString();
            if (!value.isString() || !path.startsWith(QLatin1Char('/')) || path.size() > 8192
                || std::any_of(path.begin(), path.end(), [](QChar c) { return c.unicode() < 32; })) {
                return {};
            }
            const auto url = QUrl::fromLocalFile(path).toString(QUrl::FullyEncoded);
            if (urls.contains(url)) {
                return {};
            }
            urls.append(url);
            if (!paths.contains(path)) paths.append(path);
        }
        KConfigGroup pane(&config, groupName + QStringLiteral("-ViewSpace %1").arg(i));
        pane.writeEntry("Documents", urls);
        pane.writeEntry("Active View", urls[view.value(QStringLiteral("active")).toInt()]);
    }
    int leaves = 0, splitters = 0, nodes = 0;
    bool valid = true;
    std::function<QString(QJsonValue, int)> tree = [&](QJsonValue node, int depth) -> QString {
        if (depth > 16 || ++nodes > 64) { valid = false; return {}; }
        if (integer(node, 0, views.size() - 1)) {
            if (node.toInt() != leaves++) valid = false;
            return groupName + QStringLiteral("-ViewSpace %1").arg(node.toInt());
        }
        const auto branch = node.toObject();
        const auto children = branch.value(QStringLiteral("children")).toArray();
        const auto sizes = branch.value(QStringLiteral("sizes")).toArray();
        if (!node.isObject() || branch.keys() != QStringList{QStringLiteral("children"), QStringLiteral("orientation"), QStringLiteral("sizes")}
            || !integer(branch.value(QStringLiteral("orientation")), 1, 2) || children.isEmpty() || children.size() > 16 || children.size() != sizes.size()) {
            valid = false; return {};
        }
        const auto name = groupName + QStringLiteral("-Splitter %1").arg(splitters++);
        QStringList names;
        QList<int> lengths;
        for (int i = 0; i < children.size(); ++i) {
            if (!integer(sizes[i], 1, 100000)) valid = false;
            lengths.append(sizes[i].toInt());
            names.append(tree(children[i], depth + 1));
        }
        KConfigGroup group(&config, name);
        group.writeEntry("Children", names);
        group.writeEntry("Sizes", lengths);
        group.writeEntry("Orientation", branch.value(QStringLiteral("orientation")).toInt());
        return name;
    };
    auto layout = editor.value(QStringLiteral("layout"));
    if (layout.isDouble()) {
        layout = QJsonObject{{QStringLiteral("orientation"), 1}, {QStringLiteral("sizes"), QJsonArray{800}}, {QStringLiteral("children"), QJsonArray{layout}}};
    }
    tree(layout, 0);
    if (!valid || leaves != views.size()) return {};

    struct Replacement { QByteArray digest; QString oldId; QPointer<KateMainWindow> window; bool created; };
    static QMap<QString, Replacement> replacements;
    const auto key = attempt.isEmpty() ? oldId : attempt; // Old durable requests remain readable.
    const auto digest = QCryptographicHash::hash(parsed.toJson(QJsonDocument::Compact), QCryptographicHash::Sha256);
    auto app = KateApp::self();
    const auto identify = [app](KateMainWindow *window) {
        const auto current = QJsonDocument::fromJson(monetEditorWindows({}).toUtf8()).array();
        for (int i = 0; window && i < app->mainWindowsCount() && i < current.size(); ++i) {
            if (app->mainWindow(i) == window) return current[i].toObject().value(QStringLiteral("id")).toString();
        }
        return QString();
    };
    if (replacements.contains(key)) {
        const auto &previous = replacements[key];
        if (previous.digest != digest) return {};
        return previous.created && !previous.window ? QStringLiteral("closed") : identify(previous.window);
    }
    for (const auto &previous : replacements) {
        if (previous.oldId == oldId && (!previous.created || previous.window)) return {};
    }
    const auto captured = QJsonDocument::fromJson(monetEditorWindows({}).toUtf8());
    bool anchored = false;
    for (const auto &value : captured.array()) {
        const auto state = value.toObject();
        const auto id = state.value(QStringLiteral("id")).toString();
        if (id == oldId) return {};
        anchored = anchored || id == anchor;
        for (const auto &view : state.value(QStringLiteral("editor")).toObject().value(QStringLiteral("views")).toArray()) {
            tabs += view.toObject().value(QStringLiteral("documents")).toArray().size();
        }
    }
    if (!captured.isArray() || !anchored || tabs > 200 || app->mainWindowsCount() >= 16 || replacements.size() >= 64 || !departureToken.isEmpty()
        || std::any_of(paths.begin(), paths.end(), [](const QString &path) { return !QFileInfo(path).isFile(); })) {
        return {};
    }
    auto manager = app->documentManager();
    QList<QPointer<KateMainWindow>> original;
    for (int i = 0; i < app->mainWindowsCount(); ++i) original.append(app->mainWindow(i));
    QList<QPointer<KTextEditor::Document>> created;
    const auto clean = [&] {
        for (const auto &doc : created) {
            if (doc && !doc->isModified() && doc->views().isEmpty()) manager->closeDocument(doc);
        }
    };
    replacements.insert(key, {digest, oldId, nullptr, false});
    for (const auto &path : paths) {
        const auto url = QUrl::fromLocalFile(path);
        if (!manager->findDocument(url)) {
            QPointer<KTextEditor::Document> doc = manager->createDoc();
            created.append(doc);
            if (!doc || !doc->openUrl(url) || !QFileInfo(path).isFile()) { clean(); replacements.remove(key); return {}; }
        }
    }
    bool unchanged = departureToken.isEmpty() && app->mainWindowsCount() == original.size();
    for (int i = 0; unchanged && i < original.size(); ++i) unchanged = original[i] && original[i] == app->mainWindow(i);
    if (!unchanged) { clean(); replacements.remove(key); return {}; }
    QPointer<KateMainWindow> window = new KateMainWindow(&config, groupName, false);
    // Keep a tombstone after close: an uncertain/repeated request must not create another window.
    replacements.insert(key, {digest, oldId, window, true});
    if (!window) { clean(); return QStringLiteral("closed"); }
    window->show();
    if (!window) { clean(); return QStringLiteral("closed"); }
    bool supported;
    QList<CursorPane> visible;
    const auto current = windowState(window, supported, &visible);
    QJsonArray positions;
    // These views were just constructed; a copied sibling cursor is not a later user move.
    if (supported && current.isObject() && cursorRequest(current.toObject(), editor, positions)) restoreCursors(visible, positions, true);
    return window ? identify(window) : QStringLiteral("closed");
}

bool monetArmDeparture(const QString &token, bool armed, bool windows, const QString &owner)
{
    static const QRegularExpression valid(QStringLiteral("\\A[0-9a-f]{32}\\z"));
    if (!valid.match(token).hasMatch()) {
        return false;
    }
    if (!armed) {
        if (departureToken == token) {
            clearDeparture();
        }
        return true;
    }
    if (!departureToken.isEmpty()) {
        if (windows || monetGroupDeparture()) {
            return departureToken == token && monetGroupDeparture() == windows && departureOwner == owner;
        }
        if (departureToken == token) {
            return true;
        }
        // Legacy callers have no owner watch; a new attempt may replace their stale token.
    }
    auto app = KateApp::self();
    if ((!windows && app->mainWindowsCount() != 1) || receiptPath(token).isEmpty()) {
        return false;
    }
    if (windows) {
        const auto generation = departureGeneration;
        auto bus = QDBusConnection::sessionBus();
        if (!owner.startsWith(QLatin1Char(':')) || !bus.interface() || !bus.interface()->isServiceRegistered(owner).value()) {
            return false;
        }
        const auto states = QJsonDocument::fromJson(monetEditorWindows({}).toUtf8());
        if (generation != departureGeneration || !states.isArray() || states.array().size() != app->mainWindowsCount()) {
            return false;
        }
        for (int i = 0; i < app->mainWindowsCount(); ++i) {
            departureWindows.append(app->mainWindow(i));
            departureWindowIds.append(states.array()[i].toObject().value(QStringLiteral("id")).toString());
        }
        if (!departureWatcher) {
            departureWatcher = new QDBusServiceWatcher(qApp);
            departureWatcher->setConnection(bus);
            departureWatcher->setWatchMode(QDBusServiceWatcher::WatchForUnregistration);
            QObject::connect(departureWatcher, &QDBusServiceWatcher::serviceUnregistered, qApp, [](const QString &service) {
                if (service == departureOwner) {
                    clearDeparture(); // A crashed switch controller must not leave group-close mode armed.
                }
            });
        }
        departureOwner = owner;
        departureWatcher->setWatchedServices({owner});
        if (!bus.interface()->isServiceRegistered(owner).value()) {
            clearDeparture();
            return false;
        }
    }
    complexDeparture = false;
    departureToken = token;
    ++departureGeneration;
    return true;
}

bool monetGroupDeparture()
{
    return !departureWindows.isEmpty();
}

quint64 monetDepartureGeneration()
{
    return departureGeneration;
}

void monetComplexDeparture()
{
    complexDeparture = true;
}

bool monetFinishDeparture()
{
    if (departureToken.isEmpty()) {
        return true;
    }
    const auto generation = departureGeneration;
    const auto path = receiptPath(departureToken);
    if (path.isEmpty()) {
        return false;
    }
    const QString appId = QStringLiteral("org.kde.") + QCoreApplication::applicationName() + QStringLiteral(".desktop");
    QJsonObject receipt{{QStringLiteral("version"), 1}, {QStringLiteral("id"), departureToken}, {QStringLiteral("pid"), QCoreApplication::applicationPid()},
                        {QStringLiteral("app"), appId}};
    if (monetGroupDeparture()) {
        auto app = KateApp::self();
        if (app->mainWindowsCount() != departureWindows.size()) {
            return false;
        }
        const auto states = QJsonDocument::fromJson(monetEditorWindows({}).toUtf8());
        if (!states.isArray() || states.array().size() != departureWindows.size()) {
            return false;
        }
        for (int i = 0; i < departureWindows.size(); ++i) {
            if (!departureWindows[i] || departureWindows[i] != app->mainWindow(i)
                || states.array()[i].toObject().value(QStringLiteral("id")).toString() != departureWindowIds[i]) {
                return false; // A different group needs a new checkpoint before any window can close.
            }
        }
        receipt.insert(QStringLiteral("version"), 2);
        receipt.insert(QStringLiteral("supported"), true);
        receipt.insert(QStringLiteral("windows"), states.array());
    } else {
        bool supported;
        auto state = finalState(supported);
        if (complexDeparture) {
            supported = false;
            state = QJsonValue::Null;
        }
        receipt.insert(QStringLiteral("supported"), supported);
        receipt.insert(QStringLiteral("editor"), state);
    }
    QSaveFile file(path);
    const auto bytes = QJsonDocument(receipt).toJson(QJsonDocument::Compact);
    if (generation != departureGeneration || bytes.size() > 2 * 1024 * 1024 || !file.open(QIODevice::WriteOnly) || !file.setPermissions(QFile::ReadOwner | QFile::WriteOwner)
        || file.write(bytes) != bytes.size() || !file.flush() || fsync(file.handle()) != 0 || !file.commit()) {
        return false; // A failed recovery write vetoes this close, just like a failed save.
    }
    clearDeparture();
    return true;
}
