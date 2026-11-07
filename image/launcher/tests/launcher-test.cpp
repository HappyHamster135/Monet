// SPDX-License-Identifier: GPL-3.0-or-later
#include "coordinator.h"
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <QQmlComponent>
#include <QQmlContext>
#include <QQmlEngine>
#include <QSignalSpy>
#include <QStandardPaths>
#include <QTemporaryDir>
#include <QTest>
#include <QUrl>
#include <abstracttasksmodel.h>
#include <signal.h>
#include <sys/syscall.h>
#include <unistd.h>

using Roles = TaskManager::AbstractTasksModel;
class FixtureTasks : public QAbstractListModel {
public:
    struct Task { QString app, window; bool startup, mapped; };
    QList<Task> tasks;
    QHash<int, QByteArray> roleNames() const override { return {{512, "favoriteId"}}; }
    int rowCount(const QModelIndex &parent = {}) const override { return parent.isValid() ? 0 : tasks.size(); }
    QVariant data(const QModelIndex &index, int role) const override {
        if (!index.isValid() || index.row() >= tasks.size()) return {};
        const auto task = tasks.at(index.row());
        switch (role) {
        case 512: return QStringLiteral("applications:") + task.app;
        case Roles::StorageId: return task.app;
        case Roles::AppId: return task.app.chopped(8);
        case Roles::IsWindow: return !task.startup;
        case Roles::IsStartup: return task.startup;
        case Roles::IsMapped: return task.mapped;
        case Roles::WinIdList: return QVariantList{task.window};
        case Roles::LastActivated: return QDateTime::fromMSecsSinceEpoch(index.row());
        default: return {};
        }
    }
    void add(const QString &app, const QString &window, bool startup = false, bool mapped = true) {
        beginInsertRows({}, tasks.size(), tasks.size()); tasks.append({app, window, startup, mapped}); endInsertRows();
    }
    void map(int row) { tasks[row].mapped = true; Q_EMIT dataChanged(index(row,0), index(row,0), {Roles::IsMapped}); }
    void reset() { beginResetModel(); endResetModel(); }
};

class LauncherTest : public QObject {
    Q_OBJECT
    QTemporaryDir folder;
    QString log, script;
    QString app(const QString &name) const { return QStringLiteral("monet-fixture-") + name + QStringLiteral(".desktop"); }
    QList<QJsonObject> calls() const {
        QFile file(log); if (!file.open(QIODevice::ReadOnly)) return {};
        QList<QJsonObject> result;
        for (const auto &line : file.readAll().split('\n')) {
            const auto doc = QJsonDocument::fromJson(line);
            if (doc.isObject()) result.append(doc.object());
        }
        return result;
    }
    int count(const QString &name) const {
        const auto values = calls();
        return std::count_if(values.begin(), values.end(), [name](const QJsonObject &value) { return value.value(QStringLiteral("app")).toString() == name; });
    }
    QString state(LaunchCoordinator &coordinator, const QString &name) const {
        return coordinator.states().value(app(name)).toMap().value(QStringLiteral("state")).toString();
    }
    void entry(const QString &name, const QString &command, const QString &extra = {}) {
        QFile file(QStandardPaths::writableLocation(QStandardPaths::ApplicationsLocation) + QLatin1Char('/') + app(name));
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.write((QStringLiteral("[Desktop Entry]\nType=Application\nName=Fixture ") + name
            + QStringLiteral("\nExec=") + command + QStringLiteral("\nStartupNotify=false\n") + extra).toUtf8());
    }
private Q_SLOTS:
    void initTestCase() {
        QVERIFY(folder.isValid());
        QVERIFY(qEnvironmentVariable("HOME").startsWith(QStringLiteral("/tmp/monet-launch-tests.")));
        log = folder.filePath(QStringLiteral("calls.jsonl")); script = folder.filePath(QStringLiteral("app.py"));
        QFile helper(script); QVERIFY(helper.open(QIODevice::WriteOnly));
        helper.write("import json,os,sys,time\nfrom pathlib import Path\n"
            "with open(sys.argv[1], 'a') as f: f.write(json.dumps(dict(app=sys.argv[2],pid=os.getpid()))+'\\n')\n"
            "if sys.argv[2] == 'exit': time.sleep(.3); sys.exit(7)\n"
            "time.sleep(120)\n"); helper.close();
        QDir().mkpath(QStandardPaths::writableLocation(QStandardPaths::ApplicationsLocation));
        const auto python = QStandardPaths::findExecutable(QStringLiteral("python3")); QVERIFY(!python.isEmpty());
        for (const auto &name : {QStringLiteral("slow"), QStringLiteral("other"), QStringLiteral("exit"), QStringLiteral("single"), QStringLiteral("deadline")})
            entry(name, python + QLatin1Char(' ') + script + QLatin1Char(' ') + log + QLatin1Char(' ') + name,
                  name == QStringLiteral("single") ? QStringLiteral("SingleMainWindow=true\n") : QString{});
        entry(QStringLiteral("missing"), QStringLiteral("monet-no-such-executable-fixture"));
        entry(QStringLiteral("hidden"), python + QLatin1Char(' ') + script, QStringLiteral("Hidden=true\n"));
        QProcess database;
        database.start(QStringLiteral("kbuildsycoca6"), {QStringLiteral("--noincremental")});
        QVERIFY(database.waitForFinished(10000)); QCOMPARE(database.exitCode(), 0);
        QVERIFY(KService::serviceByStorageId(app(QStringLiteral("slow"))));
    }
    void cleanup() {
        // Only children running this unique disposable fixture script are sent
        // a signal, through pidfds so an exited/reused PID cannot be targeted.
        for (const auto &call : calls()) {
            const auto pid = static_cast<pid_t>(call.value(QStringLiteral("pid")).toInteger());
            const int fd = static_cast<int>(syscall(SYS_pidfd_open, pid, 0));
            if (fd < 0) continue;
            QFile command(QStringLiteral("/proc/%1/cmdline").arg(pid));
            if (command.open(QIODevice::ReadOnly) && command.readAll().contains(script.toUtf8()))
                syscall(SYS_pidfd_send_signal, fd, SIGTERM, nullptr, 0);
            close(fd);
        }
        QTest::qWait(80); QFile::remove(log);
    }
    void validatesApplicationIdsAndDoesNotExecuteArbitraryFiles() {
        FixtureTasks tasks; LaunchCoordinator coordinator(&tasks, {}, false, false);
        for (const auto &value : {QStringLiteral("../outside.desktop"), QStringLiteral("bad.desktop;touch"), QStringLiteral("/tmp/rogue.desktop"),
                                 QStringLiteral("applications:foo.desktop?action=delete"), QStringLiteral("file:///tmp/rogue.desktop")}) {
            QVERIFY(LaunchCoordinator::key(value).isEmpty()); QVERIFY(!coordinator.open(value).value(QStringLiteral("accepted")).toBool());
        }
        QVERIFY(!coordinator.open(app(QStringLiteral("hidden"))).value(QStringLiteral("accepted")).toBool());
        QVERIFY(!coordinator.open(app(QStringLiteral("removed"))).value(QStringLiteral("accepted")).toBool());
        QCOMPARE(calls().size(), 0);
        QCOMPARE(LaunchCoordinator::key(QStringLiteral("applications:") + app(QStringLiteral("slow"))), app(QStringLiteral("slow")));
        const auto entry = KService::serviceByStorageId(app(QStringLiteral("slow")));
        QCOMPARE(LaunchCoordinator::key(QUrl::fromLocalFile(entry->entryPath()).toString()), app(QStringLiteral("slow")));
    }
    void immediateFeedbackAndRepeatedClicksShareOneNativeJob() {
        FixtureTasks tasks; LaunchCoordinator coordinator(&tasks, {}, false, false);
        QSignalSpy changes(&coordinator, &LaunchCoordinator::changed);
        QVERIFY(coordinator.open(app(QStringLiteral("slow"))).value(QStringLiteral("accepted")).toBool());
        QCOMPARE(state(coordinator, QStringLiteral("slow")), QStringLiteral("starting")); QVERIFY(changes.count() > 0);
        QCOMPARE(calls().size(), 0);
        for (int i = 0; i < 10; ++i) QVERIFY(coordinator.open(app(QStringLiteral("slow"))).value(QStringLiteral("accepted")).toBool());
        QTRY_COMPARE(count(QStringLiteral("slow")), 1); QTest::qWait(100); QCOMPARE(count(QStringLiteral("slow")), 1);
        QTRY_VERIFY(coordinator.states().value(app(QStringLiteral("slow"))).toMap().value(QStringLiteral("spawned")).toBool());
        QCOMPARE(state(coordinator, QStringLiteral("slow")), QStringLiteral("starting"));
        tasks.add(app(QStringLiteral("slow")), QStringLiteral("window-one"));
        QTRY_COMPARE(state(coordinator, QStringLiteral("slow")), QStringLiteral("running"));
    }
    void raisesTheMostRecentWindowInsteadOfLaunchingAgain() {
        FixtureTasks tasks; tasks.add(app(QStringLiteral("slow")), QStringLiteral("older")); tasks.add(app(QStringLiteral("slow")), QStringLiteral("newer"));
        int activated = -1;
        LaunchCoordinator coordinator(&tasks, [&activated](const QModelIndex &index) { activated = index.row(); }, false, false);
        QVERIFY(coordinator.open(app(QStringLiteral("slow"))).value(QStringLiteral("accepted")).toBool());
        QCOMPARE(activated, 1); QTest::qWait(80); QCOMPARE(calls().size(), 0);
    }
    void anUnmappedSurfaceDoesNotConfirmAUsableWindow() {
        FixtureTasks tasks; LaunchCoordinator coordinator(&tasks, {}, false, false);
        coordinator.open(app(QStringLiteral("slow"))); QTRY_COMPARE(count(QStringLiteral("slow")), 1);
        tasks.add(app(QStringLiteral("slow")), QStringLiteral("not-mapped-yet"), false, false);
        QTest::qWait(80); QCOMPARE(state(coordinator, QStringLiteral("slow")), QStringLiteral("starting"));
        QCOMPARE(coordinator.open(app(QStringLiteral("slow"))).value(QStringLiteral("state")).toString(), QStringLiteral("activating"));
        QTest::qWait(80); QCOMPARE(count(QStringLiteral("slow")), 1);
        tasks.map(0); QTRY_COMPARE(state(coordinator, QStringLiteral("slow")), QStringLiteral("running"));
    }
    void aWindowDiscoveredBeforeDispatchPreventsAnotherProcess() {
        FixtureTasks tasks; int activated = 0;
        LaunchCoordinator coordinator(&tasks, [&activated](const QModelIndex &) { ++activated; }, false, false);
        coordinator.open(app(QStringLiteral("slow")));
        tasks.add(app(QStringLiteral("slow")), QStringLiteral("external-window"), false, false);
        QTRY_COMPARE(activated, 1); QTest::qWait(80); QCOMPARE(count(QStringLiteral("slow")), 0);
        QCOMPARE(state(coordinator, QStringLiteral("slow")), QStringLiteral("starting"));
        tasks.map(0); QTRY_COMPARE(state(coordinator, QStringLiteral("slow")), QStringLiteral("running"));
    }
    void missingExecutableIsFailedAndRetryUsesANewNativeJob() {
        FixtureTasks tasks; LaunchCoordinator coordinator(&tasks, {}, false, false);
        coordinator.retry(app(QStringLiteral("missing")));
        QTRY_COMPARE(state(coordinator, QStringLiteral("missing")), QStringLiteral("failed"));
        QVERIFY(!coordinator.states().value(app(QStringLiteral("missing"))).toMap().value(QStringLiteral("error")).toString().isEmpty());
        coordinator.open(app(QStringLiteral("missing")));
        QCOMPARE(state(coordinator, QStringLiteral("missing")), QStringLiteral("starting"));
        QTRY_COMPARE(state(coordinator, QStringLiteral("missing")), QStringLiteral("failed"));
        coordinator.dismiss(app(QStringLiteral("missing"))); QVERIFY(coordinator.states().isEmpty());
    }
    void retryPreservesAnExplicitNewWindowRequest() {
        FixtureTasks tasks; tasks.add(app(QStringLiteral("missing")), QStringLiteral("existing")); int activated = 0;
        LaunchCoordinator coordinator(&tasks, [&activated](const QModelIndex &) { ++activated; }, false, false);
        coordinator.open(app(QStringLiteral("missing")), nullptr, true);
        QTRY_COMPARE(state(coordinator, QStringLiteral("missing")), QStringLiteral("failed"));
        coordinator.retry(app(QStringLiteral("missing")));
        QCOMPARE(state(coordinator, QStringLiteral("missing")), QStringLiteral("starting"));
        QTRY_COMPARE(state(coordinator, QStringLiteral("missing")), QStringLiteral("failed")); QCOMPARE(activated, 0);
    }
    void twoDifferentAppsCanStartTogether() {
        FixtureTasks tasks; LaunchCoordinator coordinator(&tasks, {}, false, false);
        coordinator.open(app(QStringLiteral("slow"))); coordinator.open(app(QStringLiteral("other")));
        QTRY_COMPARE(count(QStringLiteral("slow")), 1); QTRY_COMPARE(count(QStringLiteral("other")), 1);
        tasks.add(app(QStringLiteral("slow")), QStringLiteral("window-one"));
        QTRY_COMPARE(state(coordinator, QStringLiteral("slow")), QStringLiteral("running"));
        QCOMPARE(state(coordinator, QStringLiteral("other")), QStringLiteral("starting"));
        tasks.add(app(QStringLiteral("other")), QStringLiteral("window-two"));
        QTRY_COMPARE(state(coordinator, QStringLiteral("other")), QStringLiteral("running"));
    }
    void nativeStartupFromAnotherLauncherIsNotDuplicated() {
        FixtureTasks tasks; tasks.add(app(QStringLiteral("slow")), {}, true);
        LaunchCoordinator coordinator(&tasks, {}, false, false);
        QCOMPARE(coordinator.open(app(QStringLiteral("slow"))).value(QStringLiteral("state")).toString(), QStringLiteral("starting"));
        QTest::qWait(100); QCOMPARE(calls().size(), 0);
    }
    void deliberateNewWindowWaitsForADifferentWindowIncludingAfterModelReset() {
        FixtureTasks tasks; tasks.add(app(QStringLiteral("slow")), QStringLiteral("original"));
        LaunchCoordinator coordinator(&tasks, {}, false, false);
        coordinator.open(app(QStringLiteral("slow")), nullptr, true);
        QTRY_COMPARE(count(QStringLiteral("slow")), 1); tasks.reset(); QTest::qWait(80);
        QCOMPARE(state(coordinator, QStringLiteral("slow")), QStringLiteral("starting"));
        tasks.add(app(QStringLiteral("slow")), QStringLiteral("additional"));
        QTRY_COMPARE(state(coordinator, QStringLiteral("slow")), QStringLiteral("running"));
    }
    void newWindowIntentSurvivesATaskAppearingBeforeDispatch() {
        FixtureTasks tasks; LaunchCoordinator coordinator(&tasks, {}, false, false);
        coordinator.open(app(QStringLiteral("slow")), nullptr, true);
        tasks.add(app(QStringLiteral("slow")), QStringLiteral("external-window"));
        QTRY_COMPARE(count(QStringLiteral("slow")), 1);
        QCOMPARE(state(coordinator, QStringLiteral("slow")), QStringLiteral("starting"));
        tasks.add(app(QStringLiteral("slow")), QStringLiteral("requested-window"));
        QTRY_COMPARE(state(coordinator, QStringLiteral("slow")), QStringLiteral("running"));
    }
    void singleWindowAppsAreRaisedEvenForNewWindowRequests() {
        FixtureTasks tasks; tasks.add(app(QStringLiteral("single")), QStringLiteral("only")); int activated = 0;
        LaunchCoordinator coordinator(&tasks, [&activated](const QModelIndex &) { ++activated; }, false, false);
        coordinator.open(app(QStringLiteral("single")), nullptr, true);
        QCOMPARE(activated, 1); QTest::qWait(80); QCOMPARE(calls().size(), 0);
    }
    void anEarlyExitIsNotReportedAsAReadyWindow() {
        FixtureTasks tasks; LaunchCoordinator coordinator(&tasks, {}, false, false);
        coordinator.open(app(QStringLiteral("exit")));
        QTRY_COMPARE(count(QStringLiteral("exit")), 1);
        QTRY_COMPARE_WITH_TIMEOUT(state(coordinator, QStringLiteral("exit")), QStringLiteral("unconfirmed"), 5000);
        QVERIFY(!coordinator.states().value(app(QStringLiteral("exit"))).toMap().value(QStringLiteral("error")).toString().isEmpty());
        coordinator.dismiss(app(QStringLiteral("exit"))); QVERIFY(coordinator.states().isEmpty());
        for (int i = 0; i < 5; ++i) coordinator.open(app(QStringLiteral("exit")));
        QTest::qWait(80); QCOMPARE(count(QStringLiteral("exit")), 1);
        QCOMPARE(state(coordinator, QStringLiteral("exit")), QStringLiteral("unconfirmed"));
        coordinator.retry(app(QStringLiteral("exit"))); QTRY_COMPARE(count(QStringLiteral("exit")), 2);
        tasks.add(app(QStringLiteral("exit")), QStringLiteral("late-child-window"));
        QTRY_COMPARE(state(coordinator, QStringLiteral("exit")), QStringLiteral("running"));
    }
    void endpointAndLocalCallsShareTheSamePendingLaunch() {
        FixtureTasks tasks; LaunchCoordinator coordinator(&tasks, {}, false, true);
        auto request = QDBusMessage::createMethodCall(QStringLiteral("org.monet.Launcher"), QStringLiteral("/Launcher"),
            QStringLiteral("org.monet.Launcher1"), QStringLiteral("Open"));
        request << app(QStringLiteral("slow")) << false << QString{};
        QDBusPendingCallWatcher call(QDBusConnection::sessionBus().asyncCall(request));
        QTRY_VERIFY(call.isFinished()); QDBusPendingReply<QVariantMap> reply = call; QVERIFY(!reply.isError());
        QVERIFY(reply.value().value(QStringLiteral("accepted")).toBool());
        coordinator.open(app(QStringLiteral("slow"))); QTRY_COMPARE(count(QStringLiteral("slow")), 1);
        QTest::qWait(80); QCOMPARE(count(QStringLiteral("slow")), 1);
    }
    void multipleQmlEnginesAndRecreatedViewsShareTheNativeCoordinator() {
        FixtureTasks tasks; tasks.add(app(QStringLiteral("slow")), {});
        const QByteArray qml = "import QtQuick\nimport org.monet.launcher 1.0\nItem {\n"
            "Launcher { id: launch }\nproperty var states: launch.states\n"
            "function go() { return launch.openModel(fixtureModel, 0, null); }\n}";
        const auto create = [&tasks, &qml](QQmlEngine &engine) {
            engine.rootContext()->setContextProperty(QStringLiteral("fixtureModel"), &tasks);
            QQmlComponent component(&engine); component.setData(qml, QUrl(QStringLiteral("fixture.qml")));
            return component.create();
        };
        QQmlEngine first, second;
        std::unique_ptr<QObject> a(create(first)), b(create(second)); QVERIFY(a); QVERIFY(b);
        QVariant accepted;
        QVERIFY(QMetaObject::invokeMethod(a.get(), "go", Q_RETURN_ARG(QVariant, accepted))); QCOMPARE(accepted.toInt(), 1);
        QVERIFY(QMetaObject::invokeMethod(b.get(), "go", Q_RETURN_ARG(QVariant, accepted))); QCOMPARE(accepted.toInt(), 1);
        QTRY_COMPARE(count(QStringLiteral("slow")), 1);
        const auto snapshot = [](QObject *object) {
            const auto value = object->property("states");
            return value.metaType() == QMetaType::fromType<QJSValue>() ? value.value<QJSValue>().toVariant().toMap() : value.toMap();
        };
        const auto firstState = snapshot(a.get());
        QCOMPARE(firstState.value(app(QStringLiteral("slow"))).toMap().value(QStringLiteral("state")).toString(), QStringLiteral("starting"));
        QCOMPARE(firstState, snapshot(b.get()));
        a.reset(); b.reset();
        QQmlEngine third; std::unique_ptr<QObject> c(create(third)); QVERIFY(c);
        QVERIFY(QMetaObject::invokeMethod(c.get(), "go", Q_RETURN_ARG(QVariant, accepted))); QCOMPARE(accepted.toInt(), 1);
        QTest::qWait(80); QCOMPARE(count(QStringLiteral("slow")), 1);
    }
    void confirmationTimeoutDoesNotPermitAnAccidentalDuplicate() {
        FixtureTasks tasks; LaunchCoordinator coordinator(&tasks, {}, false, false);
        coordinator.open(app(QStringLiteral("deadline"))); QTRY_COMPARE(count(QStringLiteral("deadline")), 1);
        QTRY_COMPARE_WITH_TIMEOUT(state(coordinator, QStringLiteral("deadline")), QStringLiteral("unconfirmed"), 33000);
        coordinator.dismiss(app(QStringLiteral("deadline"))); QVERIFY(coordinator.states().isEmpty());
        for (int i = 0; i < 5; ++i) coordinator.open(app(QStringLiteral("deadline")));
        QCOMPARE(state(coordinator, QStringLiteral("deadline")), QStringLiteral("unconfirmed"));
        coordinator.retry(app(QStringLiteral("deadline")));
        QTest::qWait(100); QCOMPARE(count(QStringLiteral("deadline")), 1);
        coordinator.open(app(QStringLiteral("deadline")), nullptr, true);
        QTRY_COMPARE(count(QStringLiteral("deadline")), 2);
    }
};

int main(int argc, char **argv) { QGuiApplication app(argc, argv); LauncherTest tests; return QTest::qExec(&tests, argc, argv); }
#include "launcher-test.moc"
