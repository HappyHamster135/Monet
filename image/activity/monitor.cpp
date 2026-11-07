// SPDX-License-Identifier: GPL-3.0-or-later
#include "monitor.h"
#include "activity.h"
#include "power.h"
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QWeakPointer>
#include <KWayland/Client/connection_thread.h>
#include <KWayland/Client/dpms.h>
#include <KWayland/Client/output.h>
#include <KWayland/Client/registry.h>

namespace W = KWayland::Client;
static const QString Locker = QStringLiteral("org.freedesktop.ScreenSaver");
static const QString LockerPath = QStringLiteral("/ScreenSaver");

QSharedPointer<DesktopMonitor> DesktopMonitor::shared()
{
    // Shared even when Plasma uses more than one QML engine. The last consumer
    // releases the connections; no process, polling loop or permanent singleton.
    static QWeakPointer<DesktopMonitor> weak;
    auto monitor = weak.toStrongRef();
    if (!monitor) { monitor.reset(new DesktopMonitor); weak = monitor; }
    return monitor;
}
DesktopMonitor::DesktopMonitor() : m_session(QDBusConnection::sessionBus()), m_system(QDBusConnection::systemBus())
{
    m_system.connect(QStringLiteral("org.freedesktop.login1"), QStringLiteral("/org/freedesktop/login1"),
                     QStringLiteral("org.freedesktop.login1.Manager"), QStringLiteral("PrepareForSleep"),
                     this, SLOT(preparingForSleep(bool)));
    auto watcher = new QDBusServiceWatcher(Locker, m_session, QDBusServiceWatcher::WatchForOwnerChange, this);
    connect(watcher, &QDBusServiceWatcher::serviceOwnerChanged, this, [this](const QString &, const QString &, const QString &owner) {
        ++m_ownerRevision; lockerOwner(owner);
    });
    const auto revision = m_ownerRevision;
    auto message = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.DBus"), QStringLiteral("/org/freedesktop/DBus"),
                                                QStringLiteral("org.freedesktop.DBus"), QStringLiteral("GetNameOwner"));
    message << Locker;
    auto pending = new QDBusPendingCallWatcher(m_session.asyncCall(message, 2000), this);
    connect(pending, &QDBusPendingCallWatcher::finished, this, [this, revision](QDBusPendingCallWatcher *call) {
        QDBusPendingReply<QString> reply = *call; call->deleteLater();
        if (revision == m_ownerRevision) lockerOwner(reply.isError() ? QString{} : reply.value());
    });
    if (!qEnvironmentVariableIsEmpty("WAYLAND_DISPLAY") || !qEnvironmentVariableIsEmpty("WAYLAND_SOCKET")) {
        m_connection = new W::ConnectionThread(this);
        connect(m_connection, &W::ConnectionThread::connected, this, &DesktopMonitor::setupWayland);
        connect(m_connection, &W::ConnectionThread::connectionDied, this, [this] { clearWayland(false); });
        connect(m_connection, &W::ConnectionThread::failed, this, [this] { clearWayland(false); });
        m_connection->initConnection();
    }
}
DesktopMonitor::~DesktopMonitor() {
    // Keep QObject::destroyed connected: Qt D-Bus uses that hook to remove its
    // receiver rules. A wildcard disconnect would leave dangling D-Bus targets.
    disconnect(this, &DesktopMonitor::contextChanged, nullptr, nullptr);
    disconnect(this, &DesktopMonitor::powerChanged, nullptr, nullptr);
    m_system.disconnect(QStringLiteral("org.freedesktop.login1"), QStringLiteral("/org/freedesktop/login1"),
                        QStringLiteral("org.freedesktop.login1.Manager"), QStringLiteral("PrepareForSleep"),
                        this, SLOT(preparingForSleep(bool)));
    if (!m_lockerOwner.isEmpty()) m_session.disconnect(m_lockerOwner, LockerPath, Locker, QStringLiteral("ActiveChanged"),
                                                       this, SLOT(lockerSignal(bool,QDBusMessage)));
    clearWayland(m_connection && !m_connection->hasError());
}
void DesktopMonitor::setLock(bool active, bool known, bool pending)
{
    if (m_locked == active && m_lockKnown == known && m_lockPending == pending) return;
    m_locked = active; m_lockKnown = known; m_lockPending = pending; Q_EMIT contextChanged();
}
void DesktopMonitor::lockerOwner(const QString &owner)
{
    if (owner == m_lockerOwner) {
        if (owner.isEmpty()) setLock(false, false);
        return;
    }
    if (!m_lockerOwner.isEmpty()) m_session.disconnect(m_lockerOwner, LockerPath, Locker, QStringLiteral("ActiveChanged"),
                                                       this, SLOT(lockerSignal(bool,QDBusMessage)));
    m_lockerOwner = owner;
    const auto revision = ++m_lockRevision;
    // Do not begin nonessential reads before the initial lock query returns.
    // If that query fails or the locker is absent, remain usable after the
    // bounded async attempt rather than treating an unknown state as locked.
    setLock(false, false, !owner.isEmpty());
    if (owner.isEmpty()) return;
    m_session.connect(owner, LockerPath, Locker, QStringLiteral("ActiveChanged"), this, SLOT(lockerSignal(bool,QDBusMessage)));
    auto message = QDBusMessage::createMethodCall(owner, LockerPath, Locker, QStringLiteral("GetActive"));
    auto pending = new QDBusPendingCallWatcher(m_session.asyncCall(message, 2000), this);
    connect(pending, &QDBusPendingCallWatcher::finished, this, [this, owner, revision](QDBusPendingCallWatcher *call) {
        QDBusPendingReply<bool> reply = *call; call->deleteLater();
        if (owner == m_lockerOwner && revision == m_lockRevision)
            setLock(!reply.isError() && reply.value(), !reply.isError());
    });
}
void DesktopMonitor::lockerSignal(bool active, const QDBusMessage &message)
{
    if (message.service() != m_lockerOwner) return;
    ++m_lockRevision; setLock(active, true);
}
bool DesktopMonitor::activeFor(const QString &name) const
{
    if (m_lockPending || m_locked || m_sleeping) return false;
    bool found = false;
    for (const auto &display : m_outputs) {
        if (display.output->name() != name || !display.dpms || !display.dpms->isSupported()) continue;
        found = true;
        if (display.dpms->mode() == W::Dpms::Mode::On) return true;
    }
    return !found; // Unknown/unavailable state stays usable, without guessing.
}
void DesktopMonitor::preparingForSleep(bool sleeping)
{
    if (m_sleeping == sleeping) return;
    m_sleeping = sleeping; Q_EMIT contextChanged();
}
bool DesktopMonitor::displayKnown(const QString &name) const
{
    for (const auto &display : m_outputs)
        if (display.output->name() == name && display.dpms && display.dpms->isSupported()) return true;
    return false;
}
QVariantMap DesktopMonitor::displays() const
{
    QVariantMap result;
    for (const auto &display : m_outputs) {
        const auto name = display.output->name();
        if (!name.isEmpty() && display.dpms && display.dpms->isSupported())
            result.insert(name, result.value(name).toBool() || display.dpms->mode() == W::Dpms::Mode::On);
    }
    return result;
}
void DesktopMonitor::setupWayland()
{
    clearWayland(true);
    m_registry = new W::Registry(this);
    connect(m_registry, &W::Registry::outputAnnounced, this, [this](quint32 name, quint32 version) {
        auto output = m_registry->createOutput(name, version, m_registry);
        m_outputs.insert(name, {output, nullptr});
        connect(output, &W::Output::changed, this, &DesktopMonitor::contextChanged);
        attachDpms(); Q_EMIT contextChanged();
    });
    connect(m_registry, &W::Registry::outputRemoved, this, [this](quint32 name) {
        const auto display = m_outputs.take(name);
        delete display.dpms; delete display.output; Q_EMIT contextChanged();
    });
    connect(m_registry, &W::Registry::dpmsAnnounced, this, [this](quint32 name, quint32 version) {
        if (m_manager) return;
        m_manager = m_registry->createDpmsManager(name, version, m_registry);
        connect(m_manager, &W::DpmsManager::removed, this, [this] {
            for (auto &display : m_outputs) { delete display.dpms; display.dpms = nullptr; }
            delete m_manager; m_manager = nullptr; Q_EMIT contextChanged();
        });
        attachDpms();
    });
    m_registry->create(m_connection); m_registry->setup();
}
void DesktopMonitor::attachDpms()
{
    if (!m_manager) return;
    for (auto &display : m_outputs) {
        if (display.dpms) continue;
        display.dpms = m_manager->getDpms(display.output, m_registry);
        connect(display.dpms, &W::Dpms::modeChanged, this, &DesktopMonitor::contextChanged);
        connect(display.dpms, &W::Dpms::supportedChanged, this, &DesktopMonitor::contextChanged);
    }
}
void DesktopMonitor::clearWayland(bool alive)
{
    for (auto &display : m_outputs) {
        if (!alive) {
            if (display.dpms) display.dpms->destroy();
            display.output->destroy();
        }
        delete display.dpms; delete display.output;
    }
    m_outputs.clear();
    if (m_manager) { if (!alive) m_manager->destroy(); delete m_manager; m_manager = nullptr; }
    if (m_registry) { if (!alive) m_registry->destroy(); delete m_registry; m_registry = nullptr; }
    Q_EMIT contextChanged();
}
void DesktopMonitor::setPowerConsumer(Activity *consumer, bool active)
{
    if (active) m_powerConsumers.insert(consumer); else m_powerConsumers.remove(consumer);
    if (!m_power && !m_powerConsumers.isEmpty()) {
        m_power = new PowerSnapshot(this);
        connect(m_power, &PowerSnapshot::changed, this, &DesktopMonitor::powerChanged);
    }
    if (m_power) m_power->setActive(!m_powerConsumers.isEmpty());
}
