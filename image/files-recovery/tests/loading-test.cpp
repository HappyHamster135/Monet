// SPDX-License-Identifier: GPL-3.0-or-later
#include "mountpointobserver.h"
#include "spaceinfoobserver.h"
#include <QElapsedTimer>
#include <QSignalSpy>
#include <QStorageInfo>
#include <QTemporaryDir>
#include <QTest>
#include <dlfcn.h>

class LoadingTest : public QObject {
    Q_OBJECT
private Q_SLOTS:
    void mountLookupDoesNoSynchronousFilesystemProbe()
    {
        QTemporaryDir folder;
        QVERIFY(folder.isValid());
        auto count = reinterpret_cast<unsigned (*)()>(dlsym(RTLD_DEFAULT, "monet_slow_space_calls"));
        QVERIFY(count);
        const auto before = count();
        qputenv("MONET_TEST_SLOW_SPACE", "1");
        // Establish that this process really intercepts Qt's filesystem probe;
        // otherwise a no-calls assertion could pass with an ineffective shim.
        const QStorageInfo probe(folder.path());
        QVERIFY(probe.isValid());
        QVERIFY(count() > before);
        const auto callsBeforeLookup = count();
        QElapsedTimer elapsed; elapsed.start();
        auto observer = MountPointObserver::observerForUrl(QUrl::fromLocalFile(folder.path()));
        const auto milliseconds = elapsed.elapsed();
        qunsetenv("MONET_TEST_SLOW_SPACE");
        QVERIFY(observer);
        QCOMPARE(count(), callsBeforeLookup);
        QVERIFY2(milliseconds < 500, "The GUI waited for filesystem information");
    }
    void obsoleteJobsCannotPublishResults()
    {
        QTemporaryDir folder;
        auto observer = MountPointObserver::observerForUrl(QUrl::fromLocalFile(folder.path()));
        observer->ref(); observer->update();
        QSignalSpy changes(observer, &MountPointObserver::spaceInfoChanged);
        auto obsolete = KIO::fileSystemFreeSpace(QUrl(QStringLiteral("file:///obsolete-monet-test")));
        QVERIFY(QMetaObject::invokeMethod(observer, "freeSpaceResult", Qt::DirectConnection, Q_ARG(KJob *, obsolete)));
        QCOMPARE(changes.count(), 0);
        obsolete->kill(KJob::Quietly);
        observer->deref(); observer->update();
    }
    void queuedOldLocationCannotReplaceTheCurrentLocation()
    {
        const QUrl oldUrl(QStringLiteral("smb://offline.invalid/old"));
        QTemporaryDir folder;
        auto old = MountPointObserver::observerForUrl(oldUrl);
        SpaceInfoObserver space(oldUrl);
        QObject::connect(old, SIGNAL(spaceInfoChanged(quint64,quint64)), &space,
            SLOT(spaceInfoChanged(quint64,quint64)), Qt::QueuedConnection);
        old->spaceInfoChanged(1000, 500);
        QCOMPARE(space.size(), quint64(1000));
        space.setUrl(QUrl::fromLocalFile(folder.path()));
        QSignalSpy changes(&space, &SpaceInfoObserver::valuesChanged);
        QCoreApplication::sendPostedEvents(&space, QEvent::MetaCall);
        QCOMPARE(space.size(), quint64(0));
        QCOMPARE(changes.count(), 0);
    }
};
QTEST_MAIN(LoadingTest)
#include "loading-test.moc"
