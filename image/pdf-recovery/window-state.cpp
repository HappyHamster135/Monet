// SPDX-License-Identifier: GPL-2.0-or-later
#include <QDBusMessage>
#include <QDBusMetaType>
#include <QDBusReply>
#include <QDir>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSet>
#include <QUuid>
#include <QWindow>
#include <qpa/qplatformnativeinterface.h>
#include <wayland-client-core.h>

QString Shell::monetDocumentState() const
{
    if (!m_isValid || m_tabs.isEmpty() || m_tabs.size() > 32
        || m_tabWidget->currentIndex() < 0 || m_tabWidget->currentIndex() >= m_tabs.size()) return QStringLiteral("null");
    QJsonArray tabs;
    for (const auto &tab : m_tabs) {
        const auto part = tab.part;
        const auto url = part->url();
        if (url.isEmpty() && m_tabs.size() == 1 && !part->isModified()) {
            return QStringLiteral("{\"tabs\":[],\"active\":-1}");
        }
        const auto path = url.toLocalFile();
        if (!url.isLocalFile() || !QDir::isAbsolutePath(path) || path.size() > 4096
            || path != QDir::cleanPath(path)) return QStringLiteral("null");
        for (const auto character : path) {
            if (character.unicode() < 32 || character.unicode() == 127) return QStringLiteral("null");
        }
        uint page = 0, pages = 0;
        if (!QMetaObject::invokeMethod(part, "currentPage", Q_RETURN_ARG(uint, page))
            || !QMetaObject::invokeMethod(part, "pages", Q_RETURN_ARG(uint, pages))
            || page < 1 || page > pages || pages > 1000000) return QStringLiteral("null");
        tabs.append(QJsonObject{{QStringLiteral("path"), path}, {QStringLiteral("page"), int(page)},
                                {QStringLiteral("modified"), part->isModified()}});
    }
    const auto bytes = QJsonDocument(QJsonObject{{QStringLiteral("tabs"), tabs},
                                                {QStringLiteral("active"), m_tabWidget->currentIndex()}}).toJson(QJsonDocument::Compact);
    return bytes.size() <= 600000 ? QString::fromUtf8(bytes) : QStringLiteral("null");
}

static QList<QPair<Shell *, QString>> monetDocumentIdentities()
{
    if (QGuiApplication::platformName() != QStringLiteral("wayland")) return {};
    QList<Shell *> windows;
    QList<uint> surfaces;
    for (const auto widget : QApplication::topLevelWidgets()) {
        const auto window = qobject_cast<Shell *>(widget);
        if (!window) continue;
        const auto handle = window->windowHandle();
        const auto surface = handle ? static_cast<wl_proxy *>(QGuiApplication::platformNativeInterface()->nativeResourceForWindow(QByteArrayLiteral("surface"), handle)) : nullptr;
        if (!surface || windows.size() >= 16) return {};
        windows.append(window);
        surfaces.append(wl_proxy_get_id(surface));
    }
    if (windows.isEmpty()) return {};
    qDBusRegisterMetaType<QList<uint>>();
    auto request = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin"), QStringLiteral("/MonetWindowIdentity"), QStringLiteral("org.monet.WindowIdentity"), QStringLiteral("resolveWindows"));
    request.setArguments({uint(QCoreApplication::applicationPid()), QVariant::fromValue(surfaces)});
    QDBusReply<QStringList> reply = QDBusConnection::sessionBus().call(request, QDBus::Block, 500);
    const auto ids = reply.value();
    if (!reply.isValid() || ids.size() != windows.size() || QSet<QString>(ids.begin(), ids.end()).size() != ids.size()) return {};
    QList<QPair<Shell *, QString>> result;
    for (int i = 0; i < windows.size(); ++i) {
        if (QUuid(ids[i]).isNull()) return {};
        result.append({windows[i], ids[i]});
    }
    return result;
}

QString Shell::monetDocumentWindows() const
{
    const auto windows = monetDocumentIdentities();
    if (windows.isEmpty()) return QStringLiteral("null");
    QJsonArray states;
    for (const auto &[window, id] : windows) {
        const auto state = QJsonDocument::fromJson(window->monetDocumentState().toUtf8());
        if (!state.isObject()) return QStringLiteral("null");
        states.append(QJsonObject{{QStringLiteral("id"), id}, {QStringLiteral("document"), state.object()}});
    }
    const auto bytes = QJsonDocument(states).toJson(QJsonDocument::Compact);
    return bytes.size() <= 2 * 1024 * 1024 ? QString::fromUtf8(bytes) : QStringLiteral("null");
}
