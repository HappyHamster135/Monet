// SPDX-License-Identifier: GPL-3.0-or-later
#include <QApplication>
#include <QWidget>
#include <QTimer>
#include <QJsonDocument>
#include <QJsonArray>
#include <QJsonObject>
#include <QSaveFile>
#include <QWindow>
#include <QDBusConnection>
#include <QDBusMessage>
#include <qpa/qplatformnativeinterface.h>
#include <wayland-client-core.h>

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    app.setQuitOnLastWindowClosed(false);
    app.setDesktopFileName(QStringLiteral("org.monet.WindowIdentityTest"));
    if (argc != 2 || app.platformName() != QStringLiteral("wayland")) {
        return 2;
    }
    QWidget first, second;
    for (auto window : {&first, &second}) {
        window->setWindowTitle(QStringLiteral("Identical fixture"));
        window->resize(500, 350);
        window->show();
    }
    QTimer timer;
    QObject::connect(&timer, &QTimer::timeout, [&] {
        QJsonArray windows;
        for (auto window : {&first, &second}) {
            auto handle = window->windowHandle();
            auto surface = handle ? static_cast<wl_proxy *>(QGuiApplication::platformNativeInterface()->nativeResourceForWindow(QByteArrayLiteral("surface"), handle)) : nullptr;
            const uint surfaceId = surface ? wl_proxy_get_id(surface) : 0;
            auto request = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin"), QStringLiteral("/MonetWindowIdentity"), QStringLiteral("org.monet.WindowIdentity"), QStringLiteral("resolve"));
            request.setArguments({uint(app.applicationPid()), surfaceId});
            auto reply = QDBusConnection::sessionBus().call(request, QDBus::Block, 500);
            windows.append(QJsonObject{{QStringLiteral("surface"), int(surfaceId)}, {QStringLiteral("uuid"), reply.arguments().value(0).toString()}, {QStringLiteral("error"), reply.errorName()}, {QStringLiteral("visible"), window->isVisible()}});
        }
        QSaveFile output(QString::fromLocal8Bit(argv[1]));
        if (output.open(QIODevice::WriteOnly)) {
            output.write(QJsonDocument(QJsonObject{{QStringLiteral("pid"), app.applicationPid()}, {QStringLiteral("windows"), windows}}).toJson());
            output.commit();
        }
    });
    timer.start(500);
    return app.exec();
}
