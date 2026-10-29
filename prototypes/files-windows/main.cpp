// SPDX-License-Identifier: GPL-2.0-or-later
// VM fixture: native Files main windows sharing one process and one session.
#include "dolphinmainwindow.h"
#include <KAboutData>
#include <KConfigGui>
#include <KConfig>
#include <KDBusService>
#include <KLocalizedString>
#include <QApplication>
#include <QDebug>
#include <QDir>
#include <QUrl>

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    app.setApplicationName(QStringLiteral("dolphin"));
    KAboutData about(QStringLiteral("dolphin"), QStringLiteral("Files recovery fixture"), QStringLiteral("1"));
    KAboutData::setApplicationData(about);
    KLocalizedString::setApplicationDomain("dolphin");
    app.setDesktopFileName(QStringLiteral("org.kde.dolphin"));
    KDBusService service(KDBusService::Multiple);
    KConfigGui::setSessionConfig(QStringLiteral("monet-shared-fixture"), QString());
    for (int i = 1; i <= 3; ++i) {
        auto window = new DolphinMainWindow;
        window->openDirectories({QUrl::fromLocalFile(QDir::homePath())}, false);
        window->show();
        if (!window->canBeRestored(i)) {
            qWarning() << "Missing fixture session" << app.applicationName() << KConfigGui::sessionConfig()->name() << i;
            return 2;
        }
        window->restore(i);
        window->show();
    }
    return app.exec();
}
