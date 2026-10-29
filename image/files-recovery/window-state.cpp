// SPDX-License-Identifier: GPL-2.0-or-later
#include "monetfiles.h"
#include <QJsonDocument>
#include <QSplitter>
#include <QSet>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusMetaType>
#include <QDBusReply>
#include <QUuid>
#include <QWindow>
#include <qpa/qplatformnativeinterface.h>
#include <wayland-client-core.h>

QString DolphinMainWindow::monetFilesState() const
{
    if (m_tabWidget->count() < 1 || m_tabWidget->count() > 32 || m_tabWidget->currentIndex() < 0) return QStringLiteral("null");
    QJsonArray tabs;
    for (int i = 0; i < m_tabWidget->count(); ++i) {
        const auto tab = m_tabWidget->tabPageAt(i);
        const auto splitters = tab->findChildren<QSplitter *>(QString(), Qt::FindDirectChildrenOnly);
        const int count = tab->splitViewEnabled() ? 2 : 1;
        if (splitters.size() != 1 || splitters[0]->count() != count || tab->customLabel().size() > 1024) return QStringLiteral("null");
        QJsonArray folders, views, sizes;
        for (const auto size : splitters[0]->sizes()) {
            if (size <= 0) return QStringLiteral("null");
            sizes.append(size);
        }
        for (int side = 0; side < count; ++side) {
            const auto container = side ? tab->secondaryViewContainer() : tab->primaryViewContainer();
            const auto folder = monetLocalPath(container->url());
            const auto view = container->view()->monetViewState();
            if (folder.isEmpty() || view.isEmpty()) return QStringLiteral("null");
            folders.append(folder);
            views.append(view);
        }
        tabs.append(QJsonObject{{QStringLiteral("folders"), folders}, {QStringLiteral("views"), views},
                    {QStringLiteral("active"), tab->primaryViewActive() ? 0 : 1},
                    {QStringLiteral("sizes"), sizes}, {QStringLiteral("label"), tab->customLabel()}});
    }
    const auto bytes = QJsonDocument(QJsonObject{{QStringLiteral("tabs"), tabs},
                                                {QStringLiteral("active"), m_tabWidget->currentIndex()}}).toJson(QJsonDocument::Compact);
    return bytes.size() <= 600000 ? QString::fromUtf8(bytes) : QStringLiteral("null");
}

QString DolphinMainWindow::monetFilesWindows() const
{
    if (QGuiApplication::platformName() != QStringLiteral("wayland")) return QStringLiteral("null");
    QList<DolphinMainWindow *> windows;
    QList<uint> surfaces;
    for (const auto widget : QApplication::topLevelWidgets()) {
        const auto window = qobject_cast<DolphinMainWindow *>(widget);
        if (!window) continue;
        const auto handle = window->windowHandle();
        const auto surface = handle ? static_cast<wl_proxy *>(QGuiApplication::platformNativeInterface()->nativeResourceForWindow(QByteArrayLiteral("surface"), handle)) : nullptr;
        if (!surface || windows.size() >= 16) return QStringLiteral("null");
        windows.append(window);
        surfaces.append(wl_proxy_get_id(surface));
    }
    if (windows.isEmpty()) return QStringLiteral("null");
    qDBusRegisterMetaType<QList<uint>>();
    auto request = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin"), QStringLiteral("/MonetWindowIdentity"), QStringLiteral("org.monet.WindowIdentity"), QStringLiteral("resolveWindows"));
    request.setArguments({uint(QCoreApplication::applicationPid()), QVariant::fromValue(surfaces)});
    QDBusReply<QStringList> reply = QDBusConnection::sessionBus().call(request, QDBus::Block, 500);
    const auto ids = reply.value();
    if (!reply.isValid() || ids.size() != windows.size() || QSet<QString>(ids.begin(), ids.end()).size() != ids.size()) return QStringLiteral("null");
    QJsonArray states;
    for (int i = 0; i < windows.size(); ++i) {
        const auto state = QJsonDocument::fromJson(windows[i]->monetFilesState().toUtf8());
        if (QUuid(ids[i]).isNull() || !state.isObject()) return QStringLiteral("null");
        states.append(QJsonObject{{QStringLiteral("id"), ids[i]}, {QStringLiteral("files"), state.object()}});
    }
    const auto bytes = QJsonDocument(states).toJson(QJsonDocument::Compact);
    return bytes.size() <= 2 * 1024 * 1024 ? QString::fromUtf8(bytes) : QStringLiteral("null");
}
