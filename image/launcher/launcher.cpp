// SPDX-License-Identifier: GPL-3.0-or-later
#include "launcher.h"
#include "coordinator.h"
#include <QQuickItem>
#include <QQuickWindow>
#include <KService>

Launcher::Launcher(QObject *parent) : QObject(parent), m_coordinator(LaunchCoordinator::shared())
{
    connect(m_coordinator, &LaunchCoordinator::changed, this, &Launcher::changed);
}
QVariantMap Launcher::states() const { return m_coordinator->states(); }
QString Launcher::key(const QString &id) const { return LaunchCoordinator::key(id); }
bool Launcher::open(const QString &id, QQuickItem *source, bool newWindow)
{
    return m_coordinator->open(id, source ? source->window() : nullptr, newWindow, {}, m_activityAgent).value(QStringLiteral("accepted")).toBool();
}
bool Launcher::retry(const QString &id, QQuickItem *source)
{
    return m_coordinator->retry(id, source ? source->window() : nullptr).value(QStringLiteral("accepted")).toBool();
}
int Launcher::openModel(QAbstractItemModel *model, int row, QQuickItem *source)
{
    if (!model || row < 0 || row >= model->rowCount()) return 0;
    const auto roles = model->roleNames();
    int favorite = -1;
    for (auto it = roles.cbegin(); it != roles.cend(); ++it)
        if (it.value() == QByteArrayLiteral("favoriteId")) { favorite = it.key(); break; }
    if (favorite < 0) return 0;
    const auto id = model->data(model->index(row, 0), favorite).toString();
    if (key(id).isEmpty()) return 0; // Files, URLs and desktop actions stay native.
    return m_coordinator->open(id, source ? source->window() : nullptr, false, {}, QStringLiteral("org.kde.plasma.kicker"))
        .value(QStringLiteral("accepted")).toBool() ? 1 : 2;
}
bool Launcher::canOpenNewWindow(const QString &id) const
{
    const auto normalized = key(id);
    if (normalized.isEmpty()) return false;
    const auto service = KService::serviceByStorageId(normalized);
    return service && !service->property<bool>(QStringLiteral("SingleMainWindow"));
}
void Launcher::dismiss(const QString &id) { m_coordinator->dismiss(id); }
