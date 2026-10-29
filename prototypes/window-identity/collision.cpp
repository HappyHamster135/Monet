// SPDX-License-Identifier: GPL-3.0-or-later
#include "xdg-shell-client-protocol.h"
#include <wayland-client.h>
#include <sys/mman.h>
#include <unistd.h>
#include <cstring>
#include <QCoreApplication>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QTimer>

struct Window {
    wl_display *display = nullptr;
    wl_compositor *compositor = nullptr;
    wl_shm *shm = nullptr;
    xdg_wm_base *shell = nullptr;
    wl_surface *surface = nullptr;
    xdg_surface *xdg = nullptr;
    xdg_toplevel *toplevel = nullptr;
    wl_buffer *buffer = nullptr;
    uint id = 0;

    void open()
    {
        display = wl_display_connect(nullptr);
        if (!display) qFatal("Cannot connect to fixture compositor");
        auto registry = wl_display_get_registry(display);
        static const wl_registry_listener globals = {
            [](void *data, wl_registry *registry, uint32_t name, const char *interface, uint32_t) {
                auto w = static_cast<Window *>(data);
                if (!strcmp(interface, "wl_compositor")) w->compositor = static_cast<wl_compositor *>(wl_registry_bind(registry, name, &wl_compositor_interface, 1));
                if (!strcmp(interface, "wl_shm")) w->shm = static_cast<wl_shm *>(wl_registry_bind(registry, name, &wl_shm_interface, 1));
                if (!strcmp(interface, "xdg_wm_base")) w->shell = static_cast<xdg_wm_base *>(wl_registry_bind(registry, name, &xdg_wm_base_interface, 1));
            },
            [](void *, wl_registry *, uint32_t) {},
        };
        wl_registry_add_listener(registry, &globals, this);
        wl_display_roundtrip(display);
        if (!compositor || !shm || !shell) qFatal("Missing fixture Wayland globals");
        static const xdg_wm_base_listener pings = {
            [](void *, xdg_wm_base *shell, uint32_t serial) { xdg_wm_base_pong(shell, serial); },
        };
        xdg_wm_base_add_listener(shell, &pings, nullptr);
        surface = wl_compositor_create_surface(compositor);
        id = wl_proxy_get_id(reinterpret_cast<wl_proxy *>(surface));
        xdg = xdg_wm_base_get_xdg_surface(shell, surface);
        toplevel = xdg_surface_get_toplevel(xdg);
        xdg_toplevel_set_title(toplevel, "Colliding surface IDs");
        xdg_toplevel_set_app_id(toplevel, "org.monet.WindowIdentityTest");
        static const xdg_toplevel_listener events = {
            [](void *, xdg_toplevel *, int32_t, int32_t, wl_array *) {},
            [](void *, xdg_toplevel *) {},
            nullptr, nullptr,
        };
        xdg_toplevel_add_listener(toplevel, &events, nullptr);
        constexpr int bytes = 200 * 120 * 4;
        int fd = memfd_create("monet-window-fixture", MFD_CLOEXEC);
        if (fd < 0 || ftruncate(fd, bytes)) qFatal("Cannot allocate fixture buffer");
        void *pixels = mmap(nullptr, bytes, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0);
        if (pixels == MAP_FAILED) qFatal("Cannot map fixture buffer");
        memset(pixels, 0xee, bytes);
        auto pool = wl_shm_create_pool(shm, fd, bytes);
        buffer = wl_shm_pool_create_buffer(pool, 0, 200, 120, 800, WL_SHM_FORMAT_XRGB8888);
        wl_shm_pool_destroy(pool);
        munmap(pixels, bytes);
        ::close(fd);
        static const xdg_surface_listener configure = {
            [](void *data, xdg_surface *xdg, uint32_t serial) {
                auto w = static_cast<Window *>(data);
                xdg_surface_ack_configure(xdg, serial);
                wl_surface_attach(w->surface, w->buffer, 0, 0);
                wl_surface_damage(w->surface, 0, 0, 200, 120);
                wl_surface_commit(w->surface);
            },
        };
        xdg_surface_add_listener(xdg, &configure, this);
        wl_surface_commit(surface);
        wl_display_roundtrip(display);
    }

    void close()
    {
        if (!surface) return;
        xdg_toplevel_destroy(toplevel);
        xdg_surface_destroy(xdg);
        wl_surface_destroy(surface);
        surface = nullptr;
        wl_display_roundtrip(display);
    }
};

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    if (argc != 2) return 2;
    Window first, second;
    first.open();
    second.open();
    if (first.id != second.id) qFatal("Fixture did not produce a surface-ID collision");
    const QString outputPath = QString::fromLocal8Bit(argv[1]);
    QTimer timer;
    QObject::connect(&timer, &QTimer::timeout, [&] {
        if (QFile::exists(outputPath + QStringLiteral(".close-first"))) first.close();
        wl_display_roundtrip(first.display);
        wl_display_roundtrip(second.display);
        auto request = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin"), QStringLiteral("/MonetWindowIdentity"), QStringLiteral("org.monet.WindowIdentity"), QStringLiteral("resolve"));
        request.setArguments({uint(app.applicationPid()), first.id});
        auto reply = QDBusConnection::sessionBus().call(request, QDBus::Block, 500);
        QSaveFile output(outputPath);
        if (output.open(QIODevice::WriteOnly)) {
            output.write(QJsonDocument(QJsonObject{{"pid", app.applicationPid()}, {"surface", int(first.id)}, {"uuid", reply.arguments().value(0).toString()}, {"error", reply.errorName()}, {"firstClosed", !first.surface}}).toJson());
            output.commit();
        }
    });
    timer.start(500);
    return app.exec();
}
