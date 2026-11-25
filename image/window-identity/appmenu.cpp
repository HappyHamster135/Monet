// SPDX-License-Identifier: GPL-3.0-or-later
#include <plugin.h>
#include <wayland_server.h>
#include <window.h>
#include <workspace.h>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusContext>
#include <QDBusMessage>
#include <QPointer>
#include <QVariantMap>

using namespace KWin;

class AppMenuTarget final : public Plugin, protected QDBusContext
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.monet.AppMenuTarget")
public:
    AppMenuTarget()
    {
        remember(workspace()->activeWindow());
        connect(workspace(), &Workspace::windowActivated, this, &AppMenuTarget::remember);
        registered = QDBusConnection::sessionBus().registerObject(QStringLiteral("/MonetAppMenu"), this, QDBusConnection::ExportScriptableSlots);
    }

    ~AppMenuTarget() override
    {
        if (registered) {
            QDBusConnection::sessionBus().unregisterObject(QStringLiteral("/MonetAppMenu"));
        }
    }

    bool registered = false;

public Q_SLOTS:
    Q_SCRIPTABLE QVariantMap target() const
    {
        auto *w = previous.data();
        if (!w || w->isDeleted() || w->isMinimized() || !w->isOnCurrentDesktop() || !w->isOnCurrentActivity()
            || !waylandServer() || waylandServer()->isScreenLocked() || !calledFromDBus()) {
            return {};
        }
        const auto owner = connection().interface()->serviceOwner(QStringLiteral("org.monet.ToolSearch"));
        if (!owner.isValid() || owner.value() != message().service()) {
            return {};
        }
        return {{QStringLiteral("id"), w->internalId().toString(QUuid::WithoutBraces)},
                {QStringLiteral("pid"), w->pid()}, {QStringLiteral("title"), w->captionNormal()},
                {QStringLiteral("service"), w->applicationMenuServiceName()}, {QStringLiteral("path"), w->applicationMenuObjectPath()}};
    }

private:
    void remember(Window *w)
    {
        // Opening the launcher or a panel temporarily takes focus away from the app.
        if (!w || w->isDock() || w->isAppletPopup() || w->isPopupWindow()
            || w->desktopFileName() == QLatin1String("org.kde.krunner")
            || w->resourceClass() == QLatin1String("krunner")) {
            return;
        }
        previous = ((w->isNormalWindow() || w->isDialog()) && !w->isLockScreen() && w->pid() > 0) ? w : nullptr;
    }

    QPointer<Window> previous;
};

class AppMenuFactory final : public PluginFactory
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID PluginFactory_iid FILE "appmenu.json")
    Q_INTERFACES(KWin::PluginFactory)
public:
    std::unique_ptr<Plugin> create() const override
    {
        auto plugin = std::make_unique<AppMenuTarget>();
        return plugin->registered ? std::move(plugin) : nullptr;
    }
};

#include "appmenu.moc"
