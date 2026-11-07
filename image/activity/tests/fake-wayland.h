// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
#include <QObject>
#include <QHash>
#include <QList>
#include <QString>
#include <memory>
#include <wayland-server-core.h>

class QSocketNotifier;
class FakeWayland : public QObject {
    Q_OBJECT
public:
    explicit FakeWayland(QObject *parent = nullptr);
    ~FakeWayland() override;
    void addOutput(const QString &name, uint32_t mode = 0);
    void removeOutput(const QString &name);
    void setMode(const QString &name, uint32_t mode);
    void setSupported(const QString &name, bool supported);
    void removeManager();
    void addManager();
    int modeRequests = 0;
private:
    struct Output {
        FakeWayland *server;
        QString name;
        uint32_t mode;
        bool supported = true;
        wl_global *global = nullptr;
        QList<wl_resource *> outputs;
        QList<wl_resource *> dpms;
    };
    static void bindOutput(wl_client *client, void *data, uint32_t version, uint32_t id);
    static void bindManager(wl_client *client, void *data, uint32_t version, uint32_t id);
    static void getDpms(wl_client *client, wl_resource *manager, uint32_t id, wl_resource *output);
    static void requestMode(wl_client *, wl_resource *resource, uint32_t mode);
    static void release(wl_client *, wl_resource *resource);
    static void outputDestroyed(wl_resource *resource);
    static void dpmsDestroyed(wl_resource *resource);
    void send(Output *output);
    wl_display *m_display = nullptr;
    wl_global *m_manager = nullptr;
    std::unique_ptr<QSocketNotifier> m_notifier;
    QHash<QString, Output *> m_outputs;
};
