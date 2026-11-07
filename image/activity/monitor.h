// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QDBusConnection>
#include <QDBusMessage>
#include <QHash>
#include <QObject>
#include <QSet>
#include <QSharedPointer>
#include <QVariantMap>

namespace KWayland::Client { class ConnectionThread; class Registry; class Output; class DpmsManager; class Dpms; }
class Activity;
class PowerSnapshot;

class DesktopMonitor : public QObject {
    Q_OBJECT
public:
    static QSharedPointer<DesktopMonitor> shared();
    explicit DesktopMonitor();
    ~DesktopMonitor() override;
    bool activeFor(const QString &output) const;
    bool locked() const { return m_locked; }
    bool lockKnown() const { return m_lockKnown; }
    bool displayKnown(const QString &output) const;
    QVariantMap displays() const;
    void setPowerConsumer(Activity *consumer, bool active);
    PowerSnapshot *power() const { return m_power; }
Q_SIGNALS:
    void contextChanged();
    void powerChanged();
private Q_SLOTS:
    void lockerSignal(bool active, const QDBusMessage &message);
    void preparingForSleep(bool sleeping);
private:
    void lockerOwner(const QString &owner);
    void setLock(bool active, bool known, bool pending = false);
    void setupWayland();
    void clearWayland(bool alive);
    void attachDpms();
    QDBusConnection m_session;
    QDBusConnection m_system;
    QString m_lockerOwner;
    quint64 m_ownerRevision = 0;
    quint64 m_lockRevision = 0;
    bool m_locked = false;
    bool m_lockKnown = false;
    bool m_lockPending = true;
    bool m_sleeping = false;
    KWayland::Client::ConnectionThread *m_connection = nullptr;
    KWayland::Client::Registry *m_registry = nullptr;
    KWayland::Client::DpmsManager *m_manager = nullptr;
    struct Display { KWayland::Client::Output *output; KWayland::Client::Dpms *dpms; };
    QHash<quint32, Display> m_outputs;
    QSet<Activity *> m_powerConsumers;
    PowerSnapshot *m_power = nullptr;
};
