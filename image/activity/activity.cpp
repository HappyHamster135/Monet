// SPDX-License-Identifier: GPL-3.0-or-later
#include "activity.h"
#include "monitor.h"
#include "power.h"

Activity::Activity(QObject *parent) : QObject(parent), m_monitor(DesktopMonitor::shared())
{
    connect(m_monitor.data(), &DesktopMonitor::contextChanged, this, &Activity::update);
    connect(m_monitor.data(), &DesktopMonitor::powerChanged, this, [this] {
        if (m_active && m_observePower) Q_EMIT powerChanged();
    });
    update();
}
Activity::~Activity() {
    disconnect(m_monitor.data(), nullptr, this, nullptr);
    m_monitor->setPowerConsumer(this, false);
}
bool Activity::locked() const { return m_monitor->locked(); }
bool Activity::lockKnown() const { return m_monitor->lockKnown(); }
bool Activity::displayKnown() const { return m_monitor->displayKnown(m_output); }
QVariantMap Activity::displays() const { return m_monitor->displays(); }
bool Activity::powerReady() const { return m_monitor->power() && m_monitor->power()->ready(); }
bool Activity::powerLoading() const { return m_monitor->power() && m_monitor->power()->loading(); }
QVariantList Activity::batteries() const { return m_monitor->power() ? m_monitor->power()->batteries() : QVariantList{}; }
QVariantMap Activity::batteryState() const { return m_monitor->power() ? m_monitor->power()->batteryState() : QVariantMap{}; }
void Activity::setOutputName(const QString &name) {
    if (m_output == name) return;
    m_output = name; Q_EMIT outputNameChanged(); update();
}
void Activity::setEnabled(bool enabled) {
    if (m_enabled == enabled) return;
    m_enabled = enabled; Q_EMIT enabledChanged(); update();
}
void Activity::setObservePower(bool observe) {
    if (m_observePower == observe) return;
    m_observePower = observe; Q_EMIT observePowerChanged(); update();
    if (m_active && m_observePower) Q_EMIT powerChanged();
}
void Activity::update()
{
    const bool next = m_enabled && m_monitor->activeFor(m_output);
    const bool changed = next != m_active;
    m_active = next;
    m_monitor->setPowerConsumer(this, m_active && m_observePower);
    Q_EMIT contextChanged();
    if (changed) {
        Q_EMIT activeChanged();
        if (m_active && m_observePower) Q_EMIT powerChanged();
    }
}
