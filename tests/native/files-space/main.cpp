// Exercise Dolphin's actual observer/cache against the host mount table and KIO worker.
// Build against either original or Monet-patched sources; no filesystem writes.
#include "mountpointobserver.h"
#include <QCoreApplication>
#include <QEventLoop>
#include <QTimer>
#include <iostream>
#include <sys/statvfs.h>

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    if (argc < 2) return 2;
    bool passed = true;
    for (int i = 1; i < argc; ++i) {
        struct statvfs expected {};
        if (statvfs(argv[i], &expected)) return 2;
        const auto size = quint64(expected.f_blocks) * expected.f_frsize;
        const auto free = quint64(expected.f_bavail) * expected.f_frsize;
        auto *observer = MountPointObserver::observerForUrl(QUrl::fromLocalFile(QString::fromLocal8Bit(argv[i])));
        observer->ref();
        QEventLoop wait;
        bool received = false;
        const auto connection = QObject::connect(observer, &MountPointObserver::spaceInfoChanged, &wait,
            [&](quint64 actualSize, quint64 actualFree) {
                const auto delta = actualFree > free ? actualFree - free : free - actualFree;
                const bool ok = actualSize == size && delta < 16 * 1024 * 1024;
                std::cout << argv[i] << ": size=" << actualSize << " available=" << actualFree
                          << " statvfs=" << free << (ok ? " PASS" : " FAIL") << std::endl;
                received = true;
                passed = passed && ok;
                wait.quit();
            });
        QTimer timeout;
        timeout.setSingleShot(true);
        QObject::connect(&timeout, &QTimer::timeout, &wait, &QEventLoop::quit);
        timeout.start(10000);
        observer->update();
        wait.exec();
        QObject::disconnect(connection);
        observer->deref();
        if (!received) {
            std::cerr << argv[i] << ": timed out" << std::endl;
            passed = false;
        }
    }
    return passed ? 0 : 1;
}
