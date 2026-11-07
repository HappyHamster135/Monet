// SPDX-License-Identifier: GPL-3.0-or-later
// Real compiled task applet, private session only. Never launch a user's apps.
#include <QApplication>
#include <QAction>
#include <QDebug>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJSValue>
#include <QProcess>
#include <QQuickWindow>
#include <QMenu>
#include <QStandardPaths>
#include <QTemporaryDir>
#include <QTest>
#include <KConfigGroup>
#include <KLocalizedString>
#include <Plasma/Applet>
#include <Plasma/Containment>
#include <Plasma/Corona>
#include <PlasmaQuick/AppletQuickItem>
#include <algorithm>
#include <functional>
#include <signal.h>
#include <stdexcept>
#include <sys/syscall.h>
#include <unistd.h>

class TestCorona : public Plasma::Corona {
public:
    QRect screenGeometry(uint) const override { return QRect(0, 0, 640, 240); }
};
static void require(bool condition, const char *message) { if (!condition) throw std::runtime_error(message); }
static void until(const std::function<bool()> &predicate, const char *message) {
    for (int i = 0; i < 400; ++i) { if (predicate()) return; QTest::qWait(20); }
    require(false, message);
}
static QList<QQuickItem *> descendants(QQuickItem *root) {
    QList<QQuickItem *> result{root};
    for (auto child : root->childItems()) result.append(descendants(child));
    return result;
}
static QList<QQuickItem *> tasks(QQuickItem *root) {
    QList<QQuickItem *> result;
    for (auto item : descendants(root))
        if (item->property("inPopup").isValid() && !item->property("inPopup").toBool()
                && item->property("index").toInt() >= 0) result.append(item);
    std::sort(result.begin(), result.end(), [](auto a, auto b) { return a->x() < b->x(); });
    return result;
}
class Fixture {
public:
    QTemporaryDir folder;
    QString script = folder.filePath(QStringLiteral("app.py"));
    QString log = folder.filePath(QStringLiteral("calls.jsonl"));
    QList<QJsonObject> calls() const {
        QFile file(log); if (!file.open(QIODevice::ReadOnly)) return {};
        QList<QJsonObject> result;
        for (const auto &line : file.readAll().split('\n')) {
            auto document = QJsonDocument::fromJson(line);
            if (document.isObject()) result.append(document.object());
        }
        return result;
    }
    int count(const QString &name) const {
        const auto all = calls();
        return std::count_if(all.begin(), all.end(), [name](const auto &call) { return call.value("app").toString() == name; });
    }
    ~Fixture() {
        for (const auto &call : calls()) {
            const auto pid = static_cast<pid_t>(call.value("pid").toInteger());
            const int fd = static_cast<int>(syscall(SYS_pidfd_open, pid, 0));
            if (fd < 0) continue;
            QFile command(QStringLiteral("/proc/%1/cmdline").arg(pid));
            if (command.open(QIODevice::ReadOnly) && command.readAll().contains(script.toUtf8()))
                syscall(SYS_pidfd_send_signal, fd, SIGTERM, nullptr, 0);
            close(fd);
        }
    }
    Fixture() {
        require(folder.isValid(), "Private fixture folder unavailable");
        QFile helper(script); require(helper.open(QIODevice::WriteOnly), "Cannot write fixture helper");
        helper.write("import os,sys,time,json\nwith open(sys.argv[1],'a') as f: f.write(json.dumps(dict(app=sys.argv[2],pid=os.getpid()))+'\\n')\ntime.sleep(120)\n"); helper.close();
        const auto applications = QStandardPaths::writableLocation(QStandardPaths::ApplicationsLocation);
        QDir().mkpath(applications);
        for (const QString &name : {QStringLiteral("slow"), QStringLiteral("other"), QStringLiteral("missing")}) {
            QFile entry(applications + QStringLiteral("/monet-dock-") + name + QStringLiteral(".desktop"));
            require(entry.open(QIODevice::WriteOnly), "Cannot write fixture entry");
            const auto exec = name == QStringLiteral("missing") ? QStringLiteral("monet-dock-missing-executable")
                : QStandardPaths::findExecutable(QStringLiteral("python3")) + QLatin1Char(' ') + script + QLatin1Char(' ') + log + QLatin1Char(' ') + name;
            entry.write((QStringLiteral("[Desktop Entry]\nType=Application\nName=Monet dock ") + name + QStringLiteral("\nExec=") + exec
                + QStringLiteral("\nIcon=application-x-executable\nStartupNotify=false\n")).toUtf8());
        }
        QProcess database; database.start(QStringLiteral("kbuildsycoca6"), {QStringLiteral("--noincremental")});
        require(database.waitForFinished(10000) && database.exitCode() == 0, "Cannot index private app entries");
    }
};
int main(int argc, char **argv) {
    QApplication app(argc, argv); KLocalizedString::setApplicationDomain("monet");
    try {
        require(qEnvironmentVariable("HOME").startsWith(QStringLiteral("/tmp/monet-launch-tests.")), "Use launcher/tests/run.sh to isolate this fixture");
        Fixture fixture;
        TestCorona corona;
        auto panel = corona.createContainment(QStringLiteral("org.kde.panel")); require(panel, "Panel missing");
        panel->setFormFactor(Plasma::Types::Horizontal); panel->setLocation(Plasma::Types::BottomEdge);
        auto applet = panel->createApplet(QStringLiteral("org.kde.plasma.icontasks")); require(applet, "Task applet missing");
        auto config = applet->config().group(QStringLiteral("General"));
        config.writeEntry("launchers", QStringList{"applications:monet-dock-slow.desktop", "applications:monet-dock-other.desktop", "applications:monet-dock-missing.desktop"});
        config.writeEntry("taskHoverEffect", true); config.writeEntry("middleClickAction", 2); config.sync();
        auto dock = PlasmaQuick::AppletQuickItem::itemForApplet(applet); require(dock, "Applet did not instantiate");
        QQuickWindow window; window.resize(640, 240);
        dock->setParentItem(window.contentItem()); dock->setPosition({48,100}); dock->setSize({440,64}); window.show();
        until([&] {
            const auto buttons = tasks(dock);
            return buttons.size() == 3 && buttons.first()->property("appId").toString() == QStringLiteral("monet-dock-slow");
        }, "Private fixture launcher delegates missing");
        QTest::qWait(300);
        for (auto task : tasks(dock)) require(task->property("appId").toString().startsWith(QStringLiteral("monet-dock-")), "Unexpected launcher in private fixture");
        auto bridge = dock->property("monetLauncher").value<QObject *>(); require(bridge, "Candidate dock bridge missing");
        until([&] { return bridge->property("client").value<QObject *>(); }, "Candidate native launcher not loaded");
        const auto state = [&](const QString &name) {
            auto value = bridge->property("states");
            const auto all = value.metaType() == QMetaType::fromType<QJSValue>() ? value.value<QJSValue>().toVariant().toMap() : value.toMap();
            return all.value(QStringLiteral("monet-dock-") + name + QStringLiteral(".desktop")).toMap().value("state").toString();
        };
        const auto click = [&](int row, Qt::MouseButton button = Qt::LeftButton, Qt::KeyboardModifiers modifiers = Qt::NoModifier) {
            auto task = tasks(dock).at(row);
            const auto point = task->mapToScene({task->width()/2,task->height()/2}).toPoint();
            QTest::mouseClick(&window,button,modifiers,point); QTest::qWait(30);
        };
        // Read the actual rendered native menu, then retain the launch checks
        // below so the wording change cannot break normal dock input.
        const auto menuAction = [&](const QString &label) -> QAction * {
            for (auto widget : QApplication::topLevelWidgets()) {
                if (auto menu = qobject_cast<QMenu *>(widget); menu && menu->isVisible()) {
                    for (auto action : menu->actions()) if (QString(action->text()).remove(QLatin1Char('&')) == label) return action;
                }
            }
            return nullptr;
        };
        click(0, Qt::RightButton);
        until([&] { return menuAction(QStringLiteral("Unpin from Home Bar")); }, "Home Bar unpin label missing");
        require(menuAction(QStringLiteral("Configure Home Bar…")), "Home Bar configuration label missing");
        for (auto widget : QApplication::topLevelWidgets())
            if (auto menu = qobject_cast<QMenu *>(widget)) menu->close();
        QTest::qWait(50);
        click(0); require(state("slow") == QStringLiteral("starting"), "Immediate start feedback missing");
        require(tasks(dock).first()->property("monetOpening").toBool(), "Native delegate does not show starting state");
        for (int i=0; i<8; ++i) click(0);
        until([&] { return fixture.count("slow")==1; }, "First native launch missing");
        click(1); until([&] { return fixture.count("other")==1; }, "Concurrent app launch missing");
        require(fixture.count("slow")==1, "Repeated pointer clicks opened duplicate apps");
        click(2); until([&] { return state("missing")==QStringLiteral("failed"); }, "Missing executable error not retained");
        click(0,Qt::LeftButton,Qt::ShiftModifier);
        until([&] { return fixture.count("slow")==2; }, "Shift click did not preserve new-window action");
        click(0,Qt::MiddleButton);
        until([&] { return fixture.count("slow")==3; }, "Middle click did not preserve new-window action");
        click(0); QTest::qWait(100); require(fixture.count("slow")==3, "Normal click duplicated a pending explicit launch");
        window.close(); qInfo() << "Compiled native dock: pointer launch, starting feedback, duplicate guard, concurrent apps, errors, Shift and middle-click passed.";
        return 0;
    } catch (const std::exception &error) { qCritical() << error.what(); return 1; }
}
