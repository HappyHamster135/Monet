// SPDX-License-Identifier: GPL-3.0-or-later
#include "power.h"
#include <QDBusMetaType>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusServiceWatcher>
#include <QDBusVariant>
#include <QtMath>
#include <algorithm>

static const QString Service = QStringLiteral("org.freedesktop.UPower");
static const QString Root = QStringLiteral("/org/freedesktop/UPower");
static const QString Device = QStringLiteral("org.freedesktop.UPower.Device");
static const QString DisplayDevice = Root + QStringLiteral("/devices/DisplayDevice");
static const QString Properties = QStringLiteral("org.freedesktop.DBus.Properties");

static QVariantMap plain(QVariantMap values)
{
    for (auto it = values.begin(); it != values.end(); ++it)
        if (it->metaType() == QMetaType::fromType<QDBusVariant>()) it.value() = it->value<QDBusVariant>().variant();
    return values;
}
static bool number(const QVariant &value)
{
    return value.metaType() == QMetaType::fromType<double>() || value.metaType() == QMetaType::fromType<float>()
        || value.metaType() == QMetaType::fromType<int>() || value.metaType() == QMetaType::fromType<uint>()
        || value.metaType() == QMetaType::fromType<qlonglong>() || value.metaType() == QMetaType::fromType<qulonglong>();
}
static bool percentage(const QVariantMap &properties)
{
    const auto value = properties.value(QStringLiteral("Percentage"));
    return number(value) && qIsFinite(value.toDouble()) && value.toDouble() >= 0 && value.toDouble() <= 100;
}
static bool boolean(const QVariant &value) { return value.metaType() == QMetaType::fromType<bool>(); }

PowerSnapshot::PowerSnapshot(QObject *parent) : QObject(parent), m_system(QDBusConnection::systemBus())
{
    qDBusRegisterMetaType<QList<QDBusObjectPath>>();
    m_refresh.setSingleShot(true); m_refresh.setInterval(0);
    m_publish.setSingleShot(true); m_publish.setInterval(0);
    connect(&m_refresh, &QTimer::timeout, this, &PowerSnapshot::refresh);
    connect(&m_publish, &QTimer::timeout, this, &PowerSnapshot::publish);
    auto watcher = new QDBusServiceWatcher(Service, m_system, QDBusServiceWatcher::WatchForOwnerChange, this);
    connect(watcher, &QDBusServiceWatcher::serviceOwnerChanged, this, [this](const QString &, const QString &, const QString &owner) {
        ++m_ownerRevision; m_lookupPending = false; ownerChanged(owner);
    });
    const auto revision = m_ownerRevision;
    auto message = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.DBus"), QStringLiteral("/org/freedesktop/DBus"),
                                                QStringLiteral("org.freedesktop.DBus"), QStringLiteral("GetNameOwner"));
    message << Service;
    auto pending = new QDBusPendingCallWatcher(m_system.asyncCall(message, 2000), this);
    connect(pending, &QDBusPendingCallWatcher::finished, this, [this, revision](QDBusPendingCallWatcher *call) {
        QDBusPendingReply<QString> reply = *call; call->deleteLater();
        if (revision == m_ownerRevision) {
            m_lookupPending = false;
            ownerChanged(reply.isError() ? QString{} : reply.value());
            if (m_active) Q_EMIT changed();
        }
    });
}
PowerSnapshot::~PowerSnapshot() { subscribe(false); }
void PowerSnapshot::setActive(bool active)
{
    if (active == m_active) return;
    m_active = active; ++m_revision;
    m_loading = false; m_pending = 0; m_dirty = false; m_ready = false;
    m_state.insert(QStringLiteral("available"), false);
    m_refresh.stop(); m_publish.stop();
    subscribe(active);
    if (active && !m_owner.isEmpty()) m_refresh.start();
    Q_EMIT changed();
}
void PowerSnapshot::ownerChanged(const QString &owner)
{
    if (owner == m_owner) return;
    subscribe(false);
    m_owner = owner; ++m_revision;
    m_loading = false; m_pending = 0; m_dirty = false; m_ready = false;
    m_state.insert(QStringLiteral("available"), false);
    m_refresh.stop(); m_publish.stop();
    if (m_active) {
        subscribe(true);
        if (!owner.isEmpty()) m_refresh.start();
        Q_EMIT changed();
    }
}
void PowerSnapshot::subscribe(bool active)
{
    if (m_owner.isEmpty()) return;
    // Always remove the old rules first, so repeated activations cannot create
    // duplicate subscriptions. No device polling is left running while hidden.
    m_system.disconnect(m_owner, Root, Service, QStringLiteral("DeviceAdded"), this, SLOT(deviceAdded(QDBusObjectPath)));
    m_system.disconnect(m_owner, Root, Service, QStringLiteral("DeviceRemoved"), this, SLOT(deviceRemoved(QDBusObjectPath)));
    m_system.disconnect(m_owner, QString{}, Properties, QStringLiteral("PropertiesChanged"), this,
                        SLOT(propertiesChanged(QString,QVariantMap,QStringList,QDBusMessage)));
    if (!active) return;
    m_system.connect(m_owner, Root, Service, QStringLiteral("DeviceAdded"), this, SLOT(deviceAdded(QDBusObjectPath)));
    m_system.connect(m_owner, Root, Service, QStringLiteral("DeviceRemoved"), this, SLOT(deviceRemoved(QDBusObjectPath)));
    m_system.connect(m_owner, QString{}, Properties, QStringLiteral("PropertiesChanged"), this,
                     SLOT(propertiesChanged(QString,QVariantMap,QStringList,QDBusMessage)));
}
void PowerSnapshot::readProperties(const QString &path, const QString &interface, quint64 revision,
                                   std::function<void(QVariantMap, bool)> done)
{
    auto message = QDBusMessage::createMethodCall(m_owner, path, Properties, QStringLiteral("GetAll"));
    message << interface;
    auto pending = new QDBusPendingCallWatcher(m_system.asyncCall(message, 2000), this);
    connect(pending, &QDBusPendingCallWatcher::finished, this,
            [this, revision, done = std::move(done)](QDBusPendingCallWatcher *call) {
        QDBusPendingReply<QVariantMap> reply = *call; call->deleteLater();
        if (revision != m_revision || !m_active) return;
        done(reply.isError() ? QVariantMap{} : plain(reply.value()), !reply.isError());
        readComplete();
    });
}
void PowerSnapshot::refresh()
{
    if (!m_active || m_owner.isEmpty()) return;
    if (m_loading) { m_dirty = true; return; }
    const auto revision = ++m_revision;
    m_loading = true; m_failed = false; m_dirty = false; m_pending = 3;
    m_nextRoot.clear(); m_nextDisplay.clear(); m_nextPaths.clear(); m_nextDevices.clear();
    Q_EMIT changed();
    readProperties(Root, Service, revision, [this](QVariantMap values, bool) { m_nextRoot = values; });
    readProperties(DisplayDevice, Device, revision, [this](QVariantMap values, bool) { m_nextDisplay = values; });
    auto message = QDBusMessage::createMethodCall(m_owner, Root, Service, QStringLiteral("EnumerateDevices"));
    auto pending = new QDBusPendingCallWatcher(m_system.asyncCall(message, 2000), this);
    connect(pending, &QDBusPendingCallWatcher::finished, this, [this, revision](QDBusPendingCallWatcher *call) {
        QDBusPendingReply<QList<QDBusObjectPath>> reply = *call; call->deleteLater();
        if (revision != m_revision || !m_active) return;
        if (reply.isError() || reply.value().size() > 256) {
            m_failed = true;
        } else {
            for (const auto &path : reply.value()) {
                if (!path.path().startsWith(Root + QStringLiteral("/devices/"))) { m_failed = true; continue; }
                if (path.path() != DisplayDevice) m_nextPaths.insert(path.path());
            }
            m_pending += m_nextPaths.size();
            for (const auto &path : std::as_const(m_nextPaths))
                readProperties(path, Device, revision, [this, path](QVariantMap values, bool ok) {
                    m_failed |= !ok; m_nextDevices.insert(path, values);
                });
        }
        readComplete();
    });
}
void PowerSnapshot::readComplete()
{
    if (--m_pending != 0) return;
    m_loading = false;
    if (!m_failed) {
        m_paths = m_nextPaths; m_root = m_nextRoot; m_display = m_nextDisplay; m_devices = m_nextDevices;
    }
    publish();
    if (m_dirty) m_refresh.start();
}
void PowerSnapshot::deviceAdded(const QDBusObjectPath &) { if (m_active) m_refresh.start(); }
void PowerSnapshot::deviceRemoved(const QDBusObjectPath &) { if (m_active) m_refresh.start(); }
void PowerSnapshot::propertiesChanged(const QString &interface, const QVariantMap &raw,
                                       const QStringList &invalidated, const QDBusMessage &message)
{
    if (!m_active || message.service() != m_owner) return;
    const auto path = message.path();
    if (!((path == Root && interface == Service) ||
          ((path == DisplayDevice || m_paths.contains(path)) && interface == Device))) return;
    if (m_loading) { m_dirty = true; return; }
    if (!invalidated.isEmpty()) { m_refresh.start(); return; }
    const auto values = plain(raw);
    auto &target = path == Root ? m_root : path == DisplayDevice ? m_display : m_devices[path];
    for (auto it = values.cbegin(); it != values.cend(); ++it) target.insert(it.key(), it.value());
    m_publish.start();
}
void PowerSnapshot::publish()
{
    if (!m_active) return;
    bool valid = !m_failed;
    QVariantList batteries;
    const QHash<int, QString> kinds{{5,"mouse"},{6,"keyboard"},{8,"phone"},{10,"tablet"},{12,"controller"},
                                  {13,"pen"},{14,"touchpad"},{17,"headset"},{18,"speaker"},{19,"headphones"},{26,"watch"}};
    auto paths = m_paths.values(); std::sort(paths.begin(), paths.end());
    for (const auto &path : std::as_const(paths)) {
        const auto props = m_devices.value(path);
        const auto type = props.value(QStringLiteral("Type")).toInt();
        QString kind;
        if (type == 2 && props.value(QStringLiteral("PowerSupply")).toBool()) {
            if (!props.value(QStringLiteral("IsPresent")).toBool()) continue;
            kind = QStringLiteral("laptop");
        } else if (type == 2) kind = QStringLiteral("other");
        else if (kinds.contains(type)) kind = kinds.value(type);
        else continue;
        if (!percentage(props)) { valid = false; continue; }
        batteries.append(QVariantMap{{"kind", kind}, {"name", props.value(QStringLiteral("Model")).toString()},
                         {"level", qRound(props.value(QStringLiteral("Percentage")).toDouble())},
                         {"charging", props.value(QStringLiteral("State")).toInt() == 1}});
    }
    std::stable_sort(batteries.begin(), batteries.end(), [](const QVariant &a, const QVariant &b) {
        return a.toMap().value(QStringLiteral("kind")) == QStringLiteral("laptop")
            && b.toMap().value(QStringLiteral("kind")) != QStringLiteral("laptop");
    });
    // An unavailable device never turns into a fictitious 0% reading. Preserve
    // the last complete snapshot and expose its unavailability separately.
    m_ready = valid;
    if (valid) m_batteries = batteries;
    auto aggregate = m_display;
    if (aggregate.value(QStringLiteral("Type")).toInt() != 2 || !aggregate.value(QStringLiteral("IsPresent")).toBool()) {
        for (const auto &path : std::as_const(paths)) {
            const auto props = m_devices.value(path);
            if (props.value(QStringLiteral("Type")).toInt() == 2 && props.value(QStringLiteral("PowerSupply")).toBool()
                    && props.value(QStringLiteral("IsPresent")).toBool()) { aggregate = props; break; }
        }
    }
    const bool present = aggregate.value(QStringLiteral("Type")).toInt() == 2 && aggregate.value(QStringLiteral("IsPresent")).toBool();
    const bool known = !m_failed && (!present || percentage(aggregate));
    if (known) {
        const int state = aggregate.value(QStringLiteral("State")).toInt();
        const auto seconds = aggregate.value(state == 1 ? QStringLiteral("TimeToFull") : QStringLiteral("TimeToEmpty"));
        QVariant minutes;
        if (present && (state == 1 || state == 2) && number(seconds) && qIsFinite(seconds.toDouble()) && seconds.toDouble() > 0)
            minutes = qRound64(seconds.toDouble() / 60);
        m_state = {{"available", true}, {"battery", present ? QVariant(qRound(aggregate.value(QStringLiteral("Percentage")).toDouble())) : QVariant{}},
                   {"charging", present && state == 1}, {"minutes", minutes},
                   {"plugged", boolean(m_root.value(QStringLiteral("OnBattery"))) ? QVariant(!m_root.value(QStringLiteral("OnBattery")).toBool()) : QVariant{}}};
    } else m_state.insert(QStringLiteral("available"), false);
    Q_EMIT changed();
}
