// SPDX-License-Identifier: GPL-3.0-or-later
#include <plugin.h>
#include <workspace.h>
#include <window.h>
#include <wayland/surface.h>
#include <QDBusConnection>
#include <QDBusMetaType>

class WindowIdentity final : public KWin::Plugin
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.monet.WindowIdentity")
public:
    WindowIdentity()
    {
        qDBusRegisterMetaType<QList<uint>>();
        registered = QDBusConnection::sessionBus().registerObject(QStringLiteral("/MonetWindowIdentity"), this, QDBusConnection::ExportScriptableSlots);
    }
    ~WindowIdentity() override
    {
        if (registered) {
            QDBusConnection::sessionBus().unregisterObject(QStringLiteral("/MonetWindowIdentity"));
        }
    }
    bool registered = false;
public Q_SLOTS:
    Q_SCRIPTABLE QStringList resolveWindows(uint pid, const QList<uint> &surfaces) const
    {
        if (surfaces.isEmpty() || surfaces.size() > 16) {
            return {};
        }
        QStringList result;
        for (uint surface : surfaces) {
            const auto id = resolve(pid, surface);
            if (id.isEmpty() || result.contains(id)) {
                return {};
            }
            result.append(id);
        }
        return result;
    }

    Q_SCRIPTABLE QString resolve(uint pid, uint surfaceId) const
    {
        if (!pid || !surfaceId) {
            return {};
        }
        QString result;
        for (auto window : KWin::workspace()->windows()) {
            auto surface = window->surface();
            if (window->isDeleted() || !surface || surface->tearingDown() || uint(window->pid()) != pid || surface->id() != surfaceId) {
                continue;
            }
            // One process can own several Wayland connections; never guess on a collision.
            if (!result.isEmpty()) {
                return {};
            }
            result = window->internalId().toString();
        }
        return result;
    }
};

class WindowIdentityFactory final : public KWin::PluginFactory
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID PluginFactory_iid FILE "metadata.json")
    Q_INTERFACES(KWin::PluginFactory)
public:
    std::unique_ptr<KWin::Plugin> create() const override
    {
        auto plugin = std::make_unique<WindowIdentity>();
        return plugin->registered ? std::move(plugin) : nullptr;
    }
};

#include "identity.moc"
