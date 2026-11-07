// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QVariantMap>

class QQuickItem;
class QAbstractItemModel;
class LaunchCoordinator;

class Launcher : public QObject {
    Q_OBJECT
    Q_PROPERTY(QVariantMap states READ states NOTIFY changed)
    Q_PROPERTY(QString activityAgent MEMBER m_activityAgent)
public:
    explicit Launcher(QObject *parent = nullptr);
    QVariantMap states() const;
    Q_INVOKABLE QString key(const QString &id) const;
    Q_INVOKABLE bool open(const QString &id, QQuickItem *source = nullptr, bool newWindow = false);
    Q_INVOKABLE bool retry(const QString &id, QQuickItem *source = nullptr);
    // 0: retain the model's original action; 1: accepted; 2: handled failure.
    Q_INVOKABLE int openModel(QAbstractItemModel *model, int row, QQuickItem *source = nullptr);
    Q_INVOKABLE bool canOpenNewWindow(const QString &id) const;
    Q_INVOKABLE void dismiss(const QString &id);
Q_SIGNALS:
    void changed();
private:
    LaunchCoordinator *m_coordinator;
    QString m_activityAgent = QStringLiteral("org.kde.libtaskmanager");
};
