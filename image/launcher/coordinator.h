// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QAbstractItemModel>
#include <QDBusConnection>
#include <QMap>
#include <QPersistentModelIndex>
#include <QPointer>
#include <QSet>
#include <QTimer>
#include <QVariantMap>
#include <KService>
#include <functional>
#include <memory>

class KNotification;
class QSocketNotifier;
class QWindow;

class LaunchCoordinator : public QObject {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.monet.Launcher1")
public:
    static LaunchCoordinator *shared();
    static QString key(const QString &id);
    // Injecting a task model/activation function is used only by the native
    // tests; the QML type always uses Plasma's real, unfiltered TasksModel.
    explicit LaunchCoordinator(QAbstractItemModel *model = nullptr,
        std::function<void(const QModelIndex &)> activate = {}, bool notifications = true,
        bool endpoint = true, QObject *parent = nullptr);
    ~LaunchCoordinator() override;
    QVariantMap states() const;
    QVariantMap open(const QString &id, QWindow *window = nullptr, bool newWindow = false, const QString &token = {}, const QString &activityAgent = {});
    QVariantMap retry(const QString &id, QWindow *window = nullptr, const QString &token = {});
    void dismiss(const QString &id);
public Q_SLOTS:
    QVariantMap Open(const QString &id, bool newWindow, const QString &activationToken);
Q_SIGNALS:
    void changed();
private:
    struct Attempt {
        quint64 serial = 0;
        QString id, name, icon, state, error, activityAgent;
        KService::Ptr service;
        bool newWindow = false, jobStarted = false, jobFinished = false, processExited = false, observedStartup = false;
        bool hidden = false;
        qint64 pid = 0;
        int pidfd = -1;
        QPointer<QSocketNotifier> exited;
        QPointer<QTimer> deadline;
        QSet<QPersistentModelIndex> originalWindows;
        QSet<QString> originalWindowIds;
    };
    using AttemptPtr = std::shared_ptr<Attempt>;
    QList<QModelIndex> windows(const QString &id, bool mappedOnly = false) const;
    bool startup(const QString &id) const;
    QString taskId(const QModelIndex &index) const;
    QString windowId(const QModelIndex &index) const;
    void scheduleReconcile();
    void reconcile();
    void start(const AttemptPtr &attempt, const QString &token);
    void watchProcess(const AttemptPtr &attempt);
    void processExited(const AttemptPtr &attempt);
    void finish(const AttemptPtr &attempt, const QString &state, const QString &error = {});
    void notify(const AttemptPtr &attempt);
    void clearWatch(const AttemptPtr &attempt);
    bool retained(const AttemptPtr &attempt) const;
    bool processAlive(const AttemptPtr &attempt) const;
    QPointer<QAbstractItemModel> m_tasks;
    std::function<void(const QModelIndex &)> m_activate;
    QMap<quint64, AttemptPtr> m_attempts;
    QMap<QString, QPointer<KNotification>> m_notifications;
    quint64 m_serial = 0;
    bool m_notify = true, m_endpoint = false;
    QTimer m_reconcile;
    QDBusConnection m_bus;
};
