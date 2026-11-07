// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusObjectPath>
#include <QHash>
#include <QObject>
#include <QSet>
#include <QTimer>
#include <QVariantList>
#include <QVariantMap>
#include <functional>

class PowerSnapshot : public QObject {
    Q_OBJECT
public:
    explicit PowerSnapshot(QObject *parent = nullptr);
    ~PowerSnapshot() override;
    void setActive(bool active);
    bool ready() const { return m_ready; }
    bool loading() const { return m_loading || (m_active && (m_lookupPending || m_refresh.isActive())); }
    QVariantList batteries() const { return m_batteries; }
    QVariantMap batteryState() const { return m_state; }
Q_SIGNALS:
    void changed();
private Q_SLOTS:
    void deviceAdded(const QDBusObjectPath &path);
    void deviceRemoved(const QDBusObjectPath &path);
    void propertiesChanged(const QString &interface, const QVariantMap &values,
                           const QStringList &invalidated, const QDBusMessage &message);
private:
    void ownerChanged(const QString &owner);
    void subscribe(bool active);
    void refresh();
    void readProperties(const QString &path, const QString &interface, quint64 revision,
                        std::function<void(QVariantMap, bool)> done);
    void readComplete();
    void publish();
    QDBusConnection m_system;
    QString m_owner;
    quint64 m_ownerRevision = 0;
    quint64 m_revision = 0;
    bool m_active = false;
    bool m_lookupPending = true;
    bool m_ready = false;
    bool m_loading = false;
    bool m_failed = false;
    bool m_dirty = false;
    int m_pending = 0;
    QTimer m_refresh;
    QTimer m_publish;
    QSet<QString> m_paths, m_nextPaths;
    QVariantMap m_root, m_nextRoot, m_display, m_nextDisplay;
    QHash<QString, QVariantMap> m_devices, m_nextDevices;
    QVariantList m_batteries;
    QVariantMap m_state;
};
