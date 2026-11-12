// SPDX-License-Identifier: GPL-3.0-or-later
#include "folderopener.h"
#include <KApplicationTrader>
#include <KService>
#include <QDateTime>
#include <QDBusConnection>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <QSignalSpy>
#include <QStandardPaths>
#include <QTcpServer>
#include <QTcpSocket>
#include <QTemporaryDir>
#include <QTest>
#include <QTimer>

class FileManager : public QObject {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.freedesktop.FileManager1")
public:
    QList<QStringList> items, folders;
public Q_SLOTS:
    void ShowItems(const QStringList &urls, const QString &) { items.append(urls); }
    void ShowFolders(const QStringList &urls, const QString &) { folders.append(urls); }
};
class SlowDav : public QTcpServer {
public:
    QList<QPointer<QTcpSocket>> pending;
    int stats = 0;
    SlowDav() {
        connect(this, &QTcpServer::newConnection, this, [this] {
            while (hasPendingConnections()) {
                auto socket = nextPendingConnection();
                connect(socket, &QTcpSocket::readyRead, this, [this, socket] {
                    auto data = socket->property("request").toByteArray() + socket->readAll();
                    socket->setProperty("request", data);
                    if (socket->property("handled").toBool() || !data.contains("\r\n\r\n")) return;
                    socket->setProperty("handled", true);
                    if (data.startsWith("PROPFIND ")) { ++stats; pending.append(socket); }
                    else { socket->write("HTTP/1.1 200 OK\r\nDAV: 1, 2\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"); socket->disconnectFromHost(); }
                });
                connect(socket, &QTcpSocket::disconnected, socket, &QObject::deleteLater);
            }
        });
        if (!listen(QHostAddress::LocalHost, 0)) qFatal("Private WebDAV server could not listen");
    }
    QUrl url() const { return QUrl(QStringLiteral("webdav://127.0.0.1:%1/slow/").arg(serverPort())); }
    void release() {
        for (auto socket : std::as_const(pending)) if (socket && socket->state() == QAbstractSocket::ConnectedState) {
            const QByteArray body = "<?xml version=\"1.0\"?><d:multistatus xmlns:d=\"DAV:\"><d:response><d:href>/slow/</d:href>"
                "<d:propstat><d:prop><d:resourcetype><d:collection/></d:resourcetype><d:displayname>slow</d:displayname>"
                "</d:prop><d:status>HTTP/1.1 200 OK</d:status></d:propstat></d:response></d:multistatus>";
            socket->write("HTTP/1.1 207 Multi-Status\r\nContent-Type: application/xml\r\nContent-Length: "
                + QByteArray::number(body.size()) + "\r\nConnection: close\r\n\r\n" + body);
            socket->disconnectFromHost();
        }
        pending.clear();
    }
};
class FolderTest : public QObject {
    Q_OBJECT
    QTemporaryDir folder;
    FileManager manager;
    QString log, script;
    QList<QStringList> directoryCalls() const {
        QFile file(log); if (!file.open(QIODevice::ReadOnly)) return {};
        QList<QStringList> result;
        for (auto line : file.readAll().split('\n')) {
            const auto array = QJsonDocument::fromJson(line);
            if (array.isArray()) { QStringList values; for (auto value : array.array()) values.append(value.toString()); result.append(values); }
        }
        return result;
    }
    QUrl path(const QString &name) const { return QUrl::fromLocalFile(folder.filePath(name)); }
    void touch(const QString &name) { QFile file(folder.filePath(name)); QVERIFY(file.open(QIODevice::WriteOnly)); file.write("fixture"); }
private Q_SLOTS:
    void initTestCase() {
        QVERIFY(folder.isValid());
        QVERIFY(qEnvironmentVariable("HOME").startsWith(QStringLiteral("/tmp/monet-launch-tests.")));
        auto bus = QDBusConnection::sessionBus();
        QVERIFY(bus.registerService(QStringLiteral("org.freedesktop.FileManager1")));
        QVERIFY(bus.registerObject(QStringLiteral("/org/freedesktop/FileManager1"), &manager, QDBusConnection::ExportAllSlots));
        log = folder.filePath(QStringLiteral("directories.jsonl")); script = folder.filePath(QStringLiteral("directory.py"));
        QFile helper(script); QVERIFY(helper.open(QIODevice::WriteOnly));
        helper.write("import json,sys\nwith open(sys.argv[1],'a') as f:f.write(json.dumps(sys.argv[2:])+'\\n')\n"); helper.close();
        const auto applications = QStandardPaths::writableLocation(QStandardPaths::ApplicationsLocation);
        QDir().mkpath(applications);
        QFile entry(applications + QStringLiteral("/monet-folder-fixture.desktop")); QVERIFY(entry.open(QIODevice::WriteOnly));
        entry.write((QStringLiteral("[Desktop Entry]\nType=Application\nName=Monet private folder fixture\nNoDisplay=true\nExec=")
            + QStandardPaths::findExecutable(QStringLiteral("python3")) + QLatin1Char(' ') + script + QLatin1Char(' ') + log
            + QStringLiteral(" %U\nMimeType=inode/directory;\nX-KDE-Protocols=file,webdav,webdavs\nStartupNotify=false\n")).toUtf8()); entry.close();
        QFile mime(QStandardPaths::writableLocation(QStandardPaths::ConfigLocation) + QStringLiteral("/mimeapps.list"));
        QVERIFY(mime.open(QIODevice::WriteOnly)); mime.write("[Default Applications]\ninode/directory=monet-folder-fixture.desktop;\n"); mime.close();
        QProcess database; database.start(QStringLiteral("kbuildsycoca6"), {QStringLiteral("--noincremental")});
        QVERIFY(database.waitForFinished(10000)); QCOMPARE(database.exitCode(), 0);
        const auto preferred = KApplicationTrader::preferredService(QStringLiteral("inode/directory"));
        QVERIFY(preferred); QCOMPARE(preferred->storageId(), QStringLiteral("monet-folder-fixture.desktop"));
    }
    void cleanup() { manager.items.clear(); manager.folders.clear(); QFile::remove(log); QTest::qWait(20); }
    void filesAreSelectedInTheirFolderAndNeverOpened() {
        const auto name = QStringLiteral("Downloaded $(touch NO); # å.desktop");
        QFile file(folder.filePath(name)); QVERIFY(file.open(QIODevice::WriteOnly));
        file.write((QStringLiteral("[Desktop Entry]\nType=Application\nName=Downloaded fixture\nExec=touch ")
            + folder.filePath(QStringLiteral("SHOULD_NOT_EXECUTE")) + QLatin1Char('\n')).toUtf8()); file.close();
        FolderOpener opener; QSignalSpy opened(&opener, &FolderOpener::opened);
        QVERIFY(opener.open(path(name))); QVERIFY(opener.busy());
        QVERIFY(!opener.open(path(name))); // Repeated pending action stays one job.
        QTRY_COMPARE(opened.count(), 1); QVERIFY(!opener.busy()); QVERIFY(opener.error().isEmpty());
        QCOMPARE(manager.items.size(), 1); QCOMPARE(manager.items.first().size(), 1); QCOMPARE(QUrl(manager.items.first().first()), path(name));
        QVERIFY(opened.first().at(1).toBool()); QCOMPARE(directoryCalls().size(), 0);
        QVERIFY(!QFile::exists(folder.filePath(QStringLiteral("SHOULD_NOT_EXECUTE"))));
    }
    void descriptionsKeepLiteralNamesWithoutShowingHtmlMarkup() {
        FolderOpener opener;
        QCOMPARE(opener.plainText(QStringLiteral("2 files to <a href=\"file:///tmp/saved\">Saved &lt;download&gt; &amp; å</a>")),
                 QStringLiteral("2 files to Saved <download> & å"));
    }
    void aDirectoryOpensItselfInsteadOfItsParent() {
        const auto name = QStringLiteral("Copied folder # å"); QVERIFY(QDir().mkdir(folder.filePath(name)));
        FolderOpener opener; QSignalSpy opened(&opener, &FolderOpener::opened);
        QVERIFY(opener.open(path(name))); QTRY_COMPARE(opened.count(), 1);
        QTRY_COMPARE(directoryCalls().size(), 1);
        QCOMPARE(manager.items.size(), 0); QVERIFY(!opened.first().at(1).toBool());
        const auto argument = directoryCalls().first().first();
        QCOMPARE(argument.startsWith(QStringLiteral("file:")) ? QUrl(argument) : QUrl::fromLocalFile(argument), path(name));
    }
    void anExtractionFolderReplacedByAFileIsRejected() {
        touch(QStringLiteral("replaced")); FolderOpener opener; QSignalSpy opened(&opener, &FolderOpener::opened);
        QVERIFY(opener.open(path(QStringLiteral("replaced")), true)); QTRY_VERIFY(!opener.busy());
        QVERIFY(opener.error().contains(QStringLiteral("no longer a folder"))); QCOMPARE(opened.count(), 0);
        QCOMPARE(manager.items.size(), 0); QCOMPARE(directoryCalls().size(), 0);
    }
    void missingDestinationExplainsFailureAndCanBeRetried() {
        FolderOpener opener; QSignalSpy opened(&opener, &FolderOpener::opened);
        QVERIFY(opener.open(path(QStringLiteral("returned-drive")), true)); QTRY_VERIFY(!opener.busy());
        QVERIFY(!opener.error().isEmpty()); QCOMPARE(opened.count(), 0);
        QVERIFY(QDir().mkdir(folder.filePath(QStringLiteral("returned-drive"))));
        QVERIFY(opener.open(path(QStringLiteral("returned-drive")), true)); QVERIFY(opener.error().isEmpty());
        QTRY_COMPARE(opened.count(), 1); QTRY_COMPARE(directoryCalls().size(), 1);
    }
    void streamAndApplicationUrisCannotBecomeFolderActions() {
        FolderOpener opener;
        for (const auto &value : {QStringLiteral("relative"), QStringLiteral("https://example.com/download"),
                QStringLiteral("applications:org.kde.dolphin.desktop"), QStringLiteral("javascript:alert(1)"),
                QStringLiteral("trash:/deleted"), QStringLiteral("data:text/plain,no")}) {
            QVERIFY2(!opener.open(QUrl(value)), qPrintable(value)); QVERIFY(!opener.busy()); QVERIFY(!opener.error().isEmpty());
        }
        QCOMPARE(manager.items.size(), 0); QCOMPARE(directoryCalls().size(), 0);
    }
    void cancellingBeforeDispatchDoesNotOpenALateWindow() {
        touch(QStringLiteral("queued.txt")); FolderOpener opener; QSignalSpy opened(&opener, &FolderOpener::opened);
        QVERIFY(opener.open(path(QStringLiteral("queued.txt")))); opener.cancel();
        QTest::qWait(100); QVERIFY(!opener.busy()); QCOMPARE(opened.count(), 0); QCOMPARE(manager.items.size(), 0);
    }
    void aSlowNetworkFolderRemainsCancellableAndLateRepliesAreIgnored() {
        SlowDav server; FolderOpener opener; QSignalSpy opened(&opener, &FolderOpener::opened);
        QVERIFY(opener.open(server.url())); QTRY_VERIFY(server.stats > 0);
        int ticks = 0; QTimer heartbeat; heartbeat.setInterval(10); connect(&heartbeat, &QTimer::timeout, this, [&ticks] { ++ticks; }); heartbeat.start();
        QTRY_VERIFY(ticks >= 5); QVERIFY(opener.busy());
        QElapsedTimer elapsed; elapsed.start(); opener.cancel(); QVERIFY(elapsed.elapsed() < 100);
        touch(QStringLiteral("after-cancel.txt")); QVERIFY(opener.open(path(QStringLiteral("after-cancel.txt"))));
        server.release(); QTRY_COMPARE(opened.count(), 1); QTest::qWait(150);
        QCOMPARE(opened.count(), 1); QCOMPARE(manager.items.first(), QStringList{path(QStringLiteral("after-cancel.txt")).toString()});
        QCOMPARE(directoryCalls().size(), 0);
    }
    void aResponsiveWebDavFolderUsesItsNativeDirectoryHandler() {
        SlowDav server; FolderOpener opener; QSignalSpy opened(&opener, &FolderOpener::opened);
        QVERIFY(opener.open(server.url())); QTRY_VERIFY(server.stats > 0); server.release();
        QTRY_COMPARE(opened.count(), 1); QTRY_COMPARE(directoryCalls().size(), 1);
        QCOMPARE(directoryCalls().first(), QStringList{server.url().toString()}); QVERIFY(!opened.first().at(1).toBool());
    }
    void anUnavailableNetworkFolderTimesOutWithoutOpeningAnything() {
        // The private KIO worker must start before we observe the stalled request.
        SlowDav server; FolderOpener opener(nullptr, 2000); QSignalSpy opened(&opener, &FolderOpener::opened);
        QVERIFY(opener.open(server.url())); QTRY_VERIFY(server.stats > 0); QTRY_VERIFY(!opener.busy());
        QVERIFY(opener.error().contains(QStringLiteral("taking too long"))); server.release(); QTest::qWait(100);
        QCOMPARE(opened.count(), 0); QCOMPARE(manager.items.size(), 0); QCOMPARE(directoryCalls().size(), 0);
    }
    void destroyingAViewWithAPendingLookupCannotOpenLater() {
        SlowDav server; auto opener = new FolderOpener;
        QVERIFY(opener->open(server.url())); QTRY_VERIFY(server.stats > 0); delete opener;
        server.release(); QTest::qWait(150); QCOMPARE(manager.items.size(), 0); QCOMPARE(directoryCalls().size(), 0);
    }
    void aTimeoutCannotOverwriteAnImmediateRetry() {
        SlowDav server; FolderOpener opener(nullptr, 2000); QSignalSpy opened(&opener, &FolderOpener::opened);
        touch(QStringLiteral("timeout-retry.txt")); bool retried = false, stale = false;
        connect(&opener, &FolderOpener::changed, this, [&] {
            if (retried && opener.busy() && !opener.error().isEmpty()) stale = true;
            if (!opener.busy() && !retried) {
                retried = true; opener.open(path(QStringLiteral("timeout-retry.txt")));
            }
        });
        QVERIFY(opener.open(server.url())); QTRY_VERIFY(server.stats > 0); QTRY_COMPARE(opened.count(), 1);
        QVERIFY(retried); QVERIFY(!stale); QVERIFY(opener.error().isEmpty()); QCOMPARE(manager.items.size(), 1);
    }
};
int main(int argc, char **argv) { QGuiApplication app(argc, argv); FolderTest tests; return QTest::qExec(&tests, argc, argv); }
#include "folder-test.moc"
