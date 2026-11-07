// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QPointer>
#include <QTimer>
#include <QUrl>
class KJob;
class QQuickItem;

// Explicit user actions only: no directory polling, listing or startup probing.
class FolderOpener : public QObject {
    Q_OBJECT
    Q_PROPERTY(bool busy READ busy NOTIFY changed)
    Q_PROPERTY(QString error READ error NOTIFY changed)
public:
    explicit FolderOpener(QObject *parent = nullptr, int timeoutMs = 30000);
    ~FolderOpener() override;
    bool busy() const { return m_busy; }
    QString error() const { return m_error; }
    Q_INVOKABLE bool open(const QUrl &url, bool mustBeDirectory = false, QQuickItem *source = nullptr);
    Q_INVOKABLE void cancel();
    Q_INVOKABLE QString plainText(const QString &formatted) const;
Q_SIGNALS:
    void changed();
    // Confirms native dispatch, not that a file-manager window has painted.
    void opened(const QUrl &url, bool highlighted);
private:
    void dispatch(const QUrl &url, bool directory, const QByteArray &token, quint64 revision);
    void finish(const QString &error = {});
    QPointer<KJob> m_job;
    QTimer m_deadline;
    QString m_error;
    quint64 m_revision = 0;
    bool m_busy = false, m_dispatched = false;
};
