// SPDX-License-Identifier: GPL-2.0-or-later
#include "rules.h"
#include "mpris2model.h"
#include "mpris2sourcemodel.h"
#include "playercontainer.h"

#include <KIO/ApplicationLauncherJob>
#include <KService>
#include <KApplicationTrader>
#include <QDBusConnection>
#include <QFileInfo>
#include <QSettings>
#include <QJsonDocument>
#include <QJsonObject>

MediaKeyRules::MediaKeyRules()
{
    m_deadline.setSingleShot(true);
    m_deadline.setInterval(10000);
    connect(&m_deadline, &QTimer::timeout, this, [this] { m_pending.clear(); });
    Reload();
    QDBusConnection::sessionBus().registerObject(QStringLiteral("/org/monet/MediaKeys"), this,
        QDBusConnection::ExportScriptableSlots | QDBusConnection::ExportScriptableSignals);
}

void MediaKeyRules::Reload()
{
    QSettings settings(QStringLiteral("Monet"), QStringLiteral("MediaKeys"));
    const QStringList blocked = settings.value(QStringLiteral("blocked")).toStringList();
    m_blocked = QSet<QString>(blocked.cbegin(), blocked.cend());
    m_fallback = settings.value(QStringLiteral("fallback")).toString();
    m_pending.clear();
    m_deadline.stop();
    m_last.clear();
    m_desktopIds.clear();
}

void MediaKeyRules::ensureModel()
{
    if (m_model) return;
    m_model = new Mpris2Model(this);
    connect(m_model, &QAbstractItemModel::rowsInserted, this, [this] {
        Q_EMIT PlayersChanged();
        if (!m_pending.isEmpty()) QTimer::singleShot(0, this, &MediaKeyRules::considerPending);
    });
    connect(m_model, &QAbstractItemModel::rowsRemoved, this, &MediaKeyRules::PlayersChanged);
    connect(m_model, &QAbstractItemModel::dataChanged, this, [this](const QModelIndex &, const QModelIndex &, const QList<int> &roles) {
        if (roles.isEmpty() || roles.contains(Mpris2SourceModel::IdentityRole) || roles.contains(Mpris2SourceModel::DesktopEntryRole)) {
            Q_EMIT PlayersChanged();
        }
        if (!m_pending.isEmpty()) QTimer::singleShot(0, this, &MediaKeyRules::considerPending);
    });
}

QList<PlayerContainer *> MediaKeyRules::players()
{
    ensureModel();
    QList<PlayerContainer *> list;
    for (int i = 0; i < m_model->rowCount(); ++i) {
        const auto index = m_model->index(i, 0);
        if (index.data(Mpris2SourceModel::IsMultiplexerRole).toBool()) continue;
        if (auto *p = index.data(Mpris2SourceModel::ContainerRole).value<PlayerContainer *>()) list.append(p);
    }
    return list;
}

QString MediaKeyRules::appKey(PlayerContainer *p)
{
    if (!m_flatpaks.contains(p)) {
        QString flatpak;
        // MPRIS gives Plasma the connection owner's PID. Some sandboxes
        // advertise a short internal desktop name, different from their launcher.
        const QString path = QStringLiteral("/proc/%1/root/.flatpak-info").arg(p->instancePid());
        if (QFileInfo::exists(path)) flatpak = QSettings(path, QSettings::IniFormat).value(QStringLiteral("Application/name")).toString();
        m_flatpaks.insert(p, flatpak);
        connect(p, &QObject::destroyed, this, [this, p] { m_flatpaks.remove(p); });
    }
    QString id = m_flatpaks.value(p);
    if (id.isEmpty()) id = p->desktopEntry();
    if (id.endsWith(QLatin1String(".desktop"))) id.chop(8);
    if (!id.isEmpty()) {
        // Sandboxed and native players can advertise an internal launcher
        // name. Respect a unique, explicit StartupWMClass alias.
        if (!m_desktopIds.contains(id)) {
            QString resolved = id;
            if (!id.contains(QLatin1Char('/')) && !KService::serviceByStorageId(id + QStringLiteral(".desktop"))) {
                const auto matches = KApplicationTrader::query([&id](const KService::Ptr &s) {
                    return s->property<QString>(QStringLiteral("StartupWMClass")).compare(id, Qt::CaseInsensitive) == 0;
                });
                if (matches.size() == 1 && matches.first()->storageId().endsWith(QLatin1String(".desktop"))) {
                    resolved = matches.first()->storageId().chopped(8);
                }
            }
            m_desktopIds.insert(id, resolved);
        }
        return QStringLiteral("app:") + m_desktopIds.value(id);
    }
    return QStringLiteral("player:") + (p->identity().isEmpty() ? p->dbusAddress() : p->identity());
}

QString MediaKeyRules::Players()
{
    QJsonObject result;
    for (auto *p : players()) result.insert(appKey(p), p->identity());
    return QString::fromUtf8(QJsonDocument(result).toJson(QJsonDocument::Compact));
}

void MediaKeyRules::considerPending()
{
    if (m_pending.isEmpty()) return;
    for (auto *p : players()) {
        if (appKey(p) != m_pending || !p->canControl()) continue;
        const bool playing = p->playbackStatus() == PlaybackStatus::Playing;
        if (!playing && !p->canPlay()) continue;
        m_pending.clear();
        m_deadline.stop();
        m_last = p;
        if (!playing) p->Play();
        return;
    }
}

void MediaKeyRules::launch()
{
    if (m_fallback.isEmpty() || !m_pending.isEmpty() || m_fallback.contains(QLatin1Char('/'))) return;
    const QString key = QStringLiteral("app:") + m_fallback;
    if (m_blocked.contains(key)) return;
    const QString id = m_fallback + QStringLiteral(".desktop");
    auto service = KService::serviceByStorageId(id);
    if (!service || !service->isApplication() || service->storageId() != id) return;
    ensureModel();
    m_pending = key;
    m_deadline.start();
    auto *job = new KIO::ApplicationLauncherJob(service, this);
    connect(job, &KJob::result, this, [this, key](KJob *job) {
        if (job->error() && m_pending == key) {
            m_pending.clear();
            m_deadline.stop();
        }
    });
    job->start();
}

PlayerContainer *MediaKeyRules::target(PlayerContainer *active, const QString &action)
{
    if (m_blocked.isEmpty() && m_fallback.isEmpty()) return active;
    const bool play = action == QStringLiteral("playpausemedia") || action == QStringLiteral("playmedia");
    if (!m_pending.isEmpty() && play) {
        considerPending();
        return nullptr;
    }
    if (!play && (action == QStringLiteral("stopmedia") || action == QStringLiteral("pausemedia"))) {
        m_pending.clear();
        m_deadline.stop();
    }
    if (active && active->canControl() && !m_blocked.contains(appKey(active))) {
        m_last = active;
        return active;
    }
    PlayerContainer *candidate = nullptr;
    for (auto *p : players()) {
        if (!p->canControl() || m_blocked.contains(appKey(p))) continue;
        if (!candidate || p == m_last) candidate = p;
        if (p->playbackStatus() == PlaybackStatus::Playing) {
            candidate = p;
            break;
        }
    }
    m_last = candidate;
    if (!candidate && play) launch();
    return candidate;
}
