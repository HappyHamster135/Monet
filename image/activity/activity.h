// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QSharedPointer>
#include <QVariantList>
#include <QVariantMap>

class DesktopMonitor;

class Activity : public QObject {
    Q_OBJECT
    Q_PROPERTY(QString outputName READ outputName WRITE setOutputName NOTIFY outputNameChanged)
    Q_PROPERTY(bool enabled READ enabled WRITE setEnabled NOTIFY enabledChanged)
    Q_PROPERTY(bool observePower READ observePower WRITE setObservePower NOTIFY observePowerChanged)
    Q_PROPERTY(bool active READ active NOTIFY activeChanged)
    Q_PROPERTY(bool locked READ locked NOTIFY contextChanged)
    Q_PROPERTY(bool lockKnown READ lockKnown NOTIFY contextChanged)
    Q_PROPERTY(bool displayKnown READ displayKnown NOTIFY contextChanged)
    Q_PROPERTY(QVariantMap displays READ displays NOTIFY contextChanged)
    Q_PROPERTY(bool powerReady READ powerReady NOTIFY powerChanged)
    Q_PROPERTY(bool powerLoading READ powerLoading NOTIFY powerChanged)
    Q_PROPERTY(QVariantList batteries READ batteries NOTIFY powerChanged)
    Q_PROPERTY(QVariantMap batteryState READ batteryState NOTIFY powerChanged)
public:
    explicit Activity(QObject *parent = nullptr);
    ~Activity() override;
    QString outputName() const { return m_output; }
    bool enabled() const { return m_enabled; }
    bool observePower() const { return m_observePower; }
    bool active() const { return m_active; }
    bool locked() const;
    bool lockKnown() const;
    bool displayKnown() const;
    QVariantMap displays() const;
    bool powerReady() const;
    bool powerLoading() const;
    QVariantList batteries() const;
    QVariantMap batteryState() const;
    void setOutputName(const QString &name);
    void setEnabled(bool enabled);
    void setObservePower(bool observe);
Q_SIGNALS:
    void outputNameChanged();
    void enabledChanged();
    void observePowerChanged();
    void activeChanged();
    void contextChanged();
    void powerChanged();
private:
    void update();
    QSharedPointer<DesktopMonitor> m_monitor;
    QString m_output;
    bool m_enabled = true;
    bool m_observePower = false;
    bool m_active = true;
};
