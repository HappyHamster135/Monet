// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QObject>
#include <QPointer>
#include <QSet>
#include <QTimer>
#include <QVariantMap>

class Mpris2Model;
class PlayerContainer;

class MediaKeyRules final : public QObject
{
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.monet.MediaKeys1")
public:
    MediaKeyRules();
    PlayerContainer *target(PlayerContainer *active, const QString &action);
public Q_SLOTS:
    Q_SCRIPTABLE QString Players();
    Q_SCRIPTABLE void Reload();
Q_SIGNALS:
    Q_SCRIPTABLE void PlayersChanged();
private:
    void ensureModel();
    QList<PlayerContainer *> players();
    QString appKey(PlayerContainer *player);
    void considerPending();
    void launch();
    Mpris2Model *m_model = nullptr;
    QHash<PlayerContainer *, QString> m_flatpaks;
    QHash<QString, QString> m_desktopIds;
    QSet<QString> m_blocked;
    QString m_fallback;
    QString m_pending;
    QTimer m_deadline;
    QPointer<PlayerContainer> m_last;
};
