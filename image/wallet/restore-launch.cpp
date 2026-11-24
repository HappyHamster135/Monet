#include "restore-origin.h"
#include <KIO/ApplicationLauncherJob>
#include <KDesktopFile>
#include <KConfigGroup>
#include <KShell>
#include <QTemporaryDir>
#include <memory>
#include <KService>
#include <QCoreApplication>
#include <QFile>
#include <QGuiApplication>
#include <QProcessEnvironment>

int main(int argc, char **argv)
{
    if (argc >= 3 && QByteArray(argv[1]) == "--exec") {
        MonetRestore::mark(getpid());
        execvp(argv[2], argv + 2);
        return 1;
    }
    QGuiApplication app(argc, argv);
    const auto args = app.arguments();
    if (args.size() != 3 || args[1] != QStringLiteral("--desktop"))
        return 2;
    auto service = KService::serviceByStorageId(args[2]);
    if (!service || !service->isValid() || !service->isApplication())
        return 1;
    // Activation-only entries supply no executable. Bind their newly started
    // D-Bus owner before delivering Activate. An existing instance is user-owned.
    if (service->exec().isEmpty()) {
        const auto bus = QDBusConnection::sessionBus().interface();
        const QString name = service->desktopEntryName();
        const auto alreadyRunning = bus->isServiceRegistered(name);
        if (alreadyRunning.isValid() && !alreadyRunning.value() && bus->startService(name).isValid()) {
            const auto pid = bus->servicePid(name);
            if (pid.isValid())
                MonetRestore::mark(pid.value());
        }
    } else {
        // Keep KDE's field expansion, working directory, GPU, terminal and
        // startup notification handling. Only this launch gets the wrapper.
        QTemporaryDir temp;
        if (!temp.isValid())
            return 1;
        KDesktopFile original(service->entryPath());
        std::unique_ptr<KDesktopFile> copy(original.copyTo(temp.filePath(QStringLiteral("restore.desktop"))));
        auto group = copy->desktopGroup();
        group.writeEntry("Exec", KShell::quoteArg(app.applicationFilePath()) + QStringLiteral(" --exec ") + service->exec());
        group.writeEntry("DBusActivatable", false);
        service = KService::Ptr(new KService(copy.get(), service->entryPath()));
    }
    KIO::ApplicationLauncherJob job(service);
    job.setAutoDelete(false);
    job.setStartupId(qgetenv("XDG_ACTIVATION_TOKEN"));
    return job.exec() ? 0 : 1;
}
