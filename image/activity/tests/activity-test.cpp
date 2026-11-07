// SPDX-License-Identifier: GPL-3.0-or-later
#include "fake-wayland.h"
#include <QDBusArgument>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusMetaType>
#include <QDBusObjectPath>
#include <QDBusVirtualObject>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>
#include <QVariantMap>
#include <memory>
#include <cstdio>

static const QString Root = QStringLiteral("/org/freedesktop/UPower");
static const QString Battery = Root + QStringLiteral("/devices/battery_BAT0");
static const QString Mouse = Root + QStringLiteral("/devices/mouse_fixture");
static const QString DisplayDevice = Root + QStringLiteral("/devices/DisplayDevice");
static const QString Properties = QStringLiteral("org.freedesktop.DBus.Properties");

struct Deferred {
    QDBusMessage request;
    QDBusConnection connection;
    QVariant value;
};

class Locker : public QDBusVirtualObject {
    Q_OBJECT
public:
    Locker() : bus(QDBusConnection::connectToBus(QDBusConnection::SessionBus, QStringLiteral("fixture-locker"))) {
        if (!bus.registerVirtualObject(QStringLiteral("/ScreenSaver"), this) || !bus.registerService(QStringLiteral("org.freedesktop.ScreenSaver")))
            qFatal("Cannot register private screen-lock fixture");
    }
    ~Locker() override { bus.unregisterService(QStringLiteral("org.freedesktop.ScreenSaver")); bus.unregisterObject(QStringLiteral("/ScreenSaver")); }
    QString introspect(const QString &) const override { return QStringLiteral("<interface name='org.freedesktop.ScreenSaver'><method name='GetActive'><arg type='b' direction='out'/></method><signal name='ActiveChanged'><arg type='b'/></signal></interface>"); }
    bool handleMessage(const QDBusMessage &message, const QDBusConnection &connection) override {
        if (message.member() != QStringLiteral("GetActive")) return false;
        ++reads;
        if (defer) held.append({message, connection, active});
        else connection.send(message.createReply(QVariantList{active}));
        return true;
    }
    void setActive(bool value) {
        active = value;
        auto message = QDBusMessage::createSignal(QStringLiteral("/ScreenSaver"), QStringLiteral("org.freedesktop.ScreenSaver"), QStringLiteral("ActiveChanged"));
        message << value; bus.send(message);
    }
    void release() {
        for (const auto &reply : std::as_const(held)) reply.connection.send(reply.request.createReply(QVariantList{reply.value}));
        held.clear();
    }
    QDBusConnection bus;
    bool active = false, defer = false;
    int reads = 0;
    QList<Deferred> held;
};

class Power : public QDBusVirtualObject {
    Q_OBJECT
public:
    explicit Power(const QString &connectionName) : bus(QDBusConnection::connectToBus(QDBusConnection::SessionBus, connectionName)) {
        reset();
        if (!bus.registerVirtualObject(Root, this, QDBusConnection::SubPath)) qFatal("Cannot export private UPower fixture");
    }
    ~Power() override { bus.unregisterObject(Root, QDBusConnection::UnregisterTree); }
    void reset() {
        props = {{Root, {{"OnBattery", false}}},
                 {Battery, {{"Type", uint(2)}, {"PowerSupply", true}, {"IsPresent", true}, {"Percentage", 80.0},
                            {"State", uint(5)}, {"Model", "Laptop fixture"}, {"TimeToFull", qlonglong(0)}, {"TimeToEmpty", qlonglong(3600)}}},
                 {Mouse, {{"Type", uint(5)}, {"PowerSupply", false}, {"IsPresent", true}, {"Percentage", 47.0},
                          {"State", uint(2)}, {"Model", "Mouse fixture"}}}};
        props.insert(DisplayDevice, props.value(Battery)); paths = {QDBusObjectPath(Battery), QDBusObjectPath(Mouse)};
        enumerations = 0; reads.clear(); held.clear(); defer.clear();
    }
    void acquire() { if (!bus.registerService(QStringLiteral("org.freedesktop.UPower"))) qFatal("Cannot own private UPower fixture"); }
    void drop() { bus.unregisterService(QStringLiteral("org.freedesktop.UPower")); }
    QString introspect(const QString &) const override {
        return QStringLiteral("<interface name='org.freedesktop.UPower'><method name='EnumerateDevices'><arg type='ao' direction='out'/></method><signal name='DeviceAdded'><arg type='o'/></signal><signal name='DeviceRemoved'><arg type='o'/></signal></interface><interface name='org.freedesktop.DBus.Properties'><method name='GetAll'><arg type='s' direction='in'/><arg type='a{sv}' direction='out'/></method></interface>");
    }
    bool handleMessage(const QDBusMessage &message, const QDBusConnection &connection) override {
        if (message.member() == QStringLiteral("EnumerateDevices")) {
            ++enumerations; connection.send(message.createReply(QVariantList{QVariant::fromValue(paths)})); return true;
        }
        if (message.interface() != Properties || message.member() != QStringLiteral("GetAll")) return false;
        const auto path = message.path(); ++reads[path];
        if (!props.contains(path)) { connection.send(message.createErrorReply(QStringLiteral("org.freedesktop.DBus.Error.UnknownObject"), QStringLiteral("fixture device removed"))); return true; }
        if (defer == path) { held.append({message, connection, props.value(path)}); defer.clear(); }
        else connection.send(message.createReply(QVariantList{props.value(path)}));
        return true;
    }
    void change(const QString &path, const QVariantMap &values, const QStringList &invalidated = {}) {
        for (auto it = values.cbegin(); it != values.cend(); ++it) props[path].insert(it.key(), it.value());
        auto message = QDBusMessage::createSignal(path, Properties, QStringLiteral("PropertiesChanged"));
        message << (path == Root ? QStringLiteral("org.freedesktop.UPower") : QStringLiteral("org.freedesktop.UPower.Device")) << values << invalidated;
        bus.send(message);
    }
    void removeMouse() {
        paths = {QDBusObjectPath(Battery)};
        auto message = QDBusMessage::createSignal(Root, QStringLiteral("org.freedesktop.UPower"), QStringLiteral("DeviceRemoved"));
        message << QDBusObjectPath(Mouse); bus.send(message);
    }
    void release() {
        for (const auto &reply : std::as_const(held)) reply.connection.send(reply.request.createReply(QVariantList{reply.value}));
        held.clear();
    }
    QDBusConnection bus;
    QHash<QString, QVariantMap> props;
    QList<QDBusObjectPath> paths;
    int enumerations = 0;
    QHash<QString, int> reads;
    QString defer;
    QList<Deferred> held;
};

class ActivityTest : public QObject {
    Q_OBJECT
private:
    QTemporaryDir runtime;
    std::unique_ptr<FakeWayland> server;
    std::unique_ptr<Locker> locker;
    std::unique_ptr<Power> power;
    QList<QObject *> roots;
    QList<QQmlEngine *> engines;
    QObject *create(const QString &output, bool observe = false, bool enabled = true) {
        auto engine = new QQmlEngine; engines.append(engine);
        QQmlComponent component(engine);
        component.setData("import org.monet.activity 1.0\nActivity {}", QUrl(QStringLiteral("fixture.qml")));
        auto object = component.create();
        if (!object) qFatal("Cannot load native activity plugin: %s", qPrintable(component.errorString()));
        roots.append(object);
        object->setProperty("outputName", output); object->setProperty("enabled", enabled); object->setProperty("observePower", observe);
        return object;
    }
    static bool active(QObject *object) { return object->property("active").toBool(); }
    static bool ready(QObject *object) { return object->property("powerReady").toBool(); }
    static QVariantMap state(QObject *object) { return object->property("batteryState").toMap(); }
private Q_SLOTS:
    void initTestCase() {
        QVERIFY(runtime.isValid()); qputenv("XDG_RUNTIME_DIR", runtime.path().toUtf8()); qputenv("WAYLAND_DISPLAY", "monet-activity-test");
        qDBusRegisterMetaType<QList<QDBusObjectPath>>();
        server = std::make_unique<FakeWayland>(); locker = std::make_unique<Locker>();
        power = std::make_unique<Power>(QStringLiteral("fixture-power")); power->acquire();
        QVERIFY(power->bus.registerService(QStringLiteral("org.freedesktop.login1")));
    }
    void init() {
        locker->active = false; locker->defer = false; locker->reads = 0; locker->held.clear(); power->reset();
        server->setMode(QStringLiteral("eDP-1"), 0); server->setMode(QStringLiteral("HDMI-A-1"), 0);
        server->setSupported(QStringLiteral("eDP-1"), true);
    }
    void cleanup() {
        qDeleteAll(roots); roots.clear(); qDeleteAll(engines); engines.clear();
        locker->held.clear(); power->held.clear(); QTest::qWait(20);
    }
    void lockAndIndependentDisplayPowerFollowNativeEvents() {
        auto laptop = create(QStringLiteral("eDP-1")); auto external = create(QStringLiteral("HDMI-A-1"));
        QTRY_VERIFY(laptop->property("lockKnown").toBool()); QTRY_VERIFY(laptop->property("displayKnown").toBool());
        QTRY_VERIFY(external->property("displayKnown").toBool()); QVERIFY(active(laptop)); QVERIFY(active(external));
        server->setMode(QStringLiteral("eDP-1"), 3);
        QTRY_VERIFY(!active(laptop)); QVERIFY(active(external));
        locker->setActive(true); QTRY_VERIFY(!active(external)); QVERIFY(laptop->property("locked").toBool());
        QVERIFY(external->property("displays").toMap().value(QStringLiteral("HDMI-A-1")).toBool());
        locker->setActive(false); QTRY_VERIFY(active(external)); QVERIFY(!active(laptop));
        server->setMode(QStringLiteral("eDP-1"), 0); QTRY_VERIFY(active(laptop));
        QCOMPARE(server->modeRequests, 0); QCOMPARE(power->enumerations, 0);
    }
    void staleLockQueryCannotUndoANewerLockSignal() {
        locker->defer = true;
        auto object = create(QStringLiteral("eDP-1")); QTRY_VERIFY(!locker->held.isEmpty());
        locker->setActive(true); QTRY_VERIFY(!active(object));
        locker->release(); QTest::qWait(40); QVERIFY(!active(object)); QVERIFY(object->property("lockKnown").toBool());
        locker->setActive(false); QTRY_VERIFY(active(object));
    }
    void openingWhileAlreadyLockedDoesNotStartPowerReads() {
        locker->active = true; locker->defer = true;
        auto object = create(QStringLiteral("eDP-1"), true);
        QSignalSpy changes(object, SIGNAL(activeChanged()));
        QTRY_VERIFY(!locker->held.isEmpty());
        QTest::qWait(40); QVERIFY(!active(object)); QCOMPARE(power->enumerations, 0);
        locker->release(); QTRY_VERIFY(object->property("lockKnown").toBool());
        QVERIFY(!active(object)); QCOMPARE(changes.count(), 0); QCOMPARE(power->enumerations, 0);
        locker->setActive(false); QTRY_VERIFY(ready(object)); QCOMPARE(power->enumerations, 1);
    }
    void missingLockerRemainsUsableAndReplacementIsQueriedBeforeReads() {
        QVERIFY(locker->bus.unregisterService(QStringLiteral("org.freedesktop.ScreenSaver")));
        auto object = create(QStringLiteral("eDP-1"), true);
        QTRY_VERIFY(active(object)); QTRY_VERIFY(ready(object));
        QVERIFY(!object->property("lockKnown").toBool());
        locker->active = true; locker->defer = true;
        QVERIFY(locker->bus.registerService(QStringLiteral("org.freedesktop.ScreenSaver")));
        QTRY_VERIFY(!locker->held.isEmpty()); QTRY_VERIFY(!active(object));
        const auto reads = power->enumerations;
        QTest::qWait(40); QCOMPARE(power->enumerations, reads);
        locker->release(); QTRY_VERIFY(object->property("lockKnown").toBool()); QVERIFY(!active(object));
        locker->setActive(false); QTRY_VERIFY(active(object));
    }
    void differentQmlEnginesSharePowerReadsAndPauseWithoutSubscribers() {
        auto a = create(QStringLiteral("eDP-1"), true); auto b = create(QStringLiteral("HDMI-A-1"), true);
        QTRY_VERIFY(ready(a)); QVERIFY(ready(b)); QCOMPARE(power->enumerations, 1);
        QCOMPARE(power->reads.value(Root), 1); QCOMPARE(power->reads.value(DisplayDevice), 1);
        QCOMPARE(power->reads.value(Battery), 1); QCOMPARE(power->reads.value(Mouse), 1);
        QCOMPARE(a->property("batteries").toList().size(), 2);
        QCOMPARE(a->property("batteries").toList().first().toMap().value(QStringLiteral("kind")).toString(), QStringLiteral("laptop"));
        QCOMPARE(state(a).value(QStringLiteral("battery")).toInt(), 80);
        QVERIFY(state(a).value(QStringLiteral("plugged")).toBool());
        power->change(DisplayDevice, {{"Percentage", 82.0}});
        QTRY_COMPARE(state(a).value(QStringLiteral("battery")).toInt(), 82);
        QCOMPARE(state(b).value(QStringLiteral("battery")).toInt(), 82); QCOMPARE(power->enumerations, 1);
        power->change(Root, {{"OnBattery", true}});
        QTRY_VERIFY(!state(a).value(QStringLiteral("plugged")).toBool());
        server->setMode(QStringLiteral("eDP-1"), 3); QTRY_VERIFY(!active(a)); QVERIFY(active(b));
        b->setProperty("enabled", false); QTRY_VERIFY(!active(b));
        const auto reads = power->reads;
        power->change(Battery, {{"Percentage", 72.0}}, {QStringLiteral("State")});
        QTest::qWait(100); QCOMPARE(power->reads, reads); QCOMPARE(power->enumerations, 1);
        b->setProperty("enabled", true); QTRY_VERIFY(ready(b)); QCOMPARE(power->enumerations, 2);
        QCOMPARE(b->property("batteries").toList().first().toMap().value(QStringLiteral("level")).toInt(), 72);
        locker->setActive(true); QTRY_VERIFY(!active(b));
        const auto lockedReads = power->reads;
        power->change(Battery, {{"Percentage", 71.0}}, {QStringLiteral("State")});
        QTest::qWait(100); QCOMPARE(power->reads, lockedReads); QCOMPARE(power->enumerations, 2);
        locker->setActive(false); QTRY_VERIFY(ready(b)); QCOMPARE(power->enumerations, 3);
        QCOMPARE(b->property("batteries").toList().first().toMap().value(QStringLiteral("level")).toInt(), 71);
    }
    void obsoletePowerRepliesCannotReplaceAResumedSnapshot() {
        power->defer = DisplayDevice; power->props[DisplayDevice].insert(QStringLiteral("Percentage"), 25.0);
        auto object = create(QStringLiteral("eDP-1"), true); QTRY_VERIFY(!power->held.isEmpty());
        object->setProperty("enabled", false);
        power->props[DisplayDevice].insert(QStringLiteral("Percentage"), 90.0);
        object->setProperty("enabled", true); QTRY_VERIFY(ready(object));
        QCOMPARE(state(object).value(QStringLiteral("battery")).toInt(), 90);
        power->release(); QTest::qWait(40); QCOMPARE(state(object).value(QStringLiteral("battery")).toInt(), 90);
    }
    void suspendAndResumeRefreshWithoutChangingPowerPolicy() {
        auto object = create(QStringLiteral("eDP-1"), true); QTRY_VERIFY(ready(object));
        const auto signal = [](bool sleeping) {
            auto message = QDBusMessage::createSignal(QStringLiteral("/org/freedesktop/login1"),
                QStringLiteral("org.freedesktop.login1.Manager"), QStringLiteral("PrepareForSleep"));
            message << sleeping; return message;
        };
        power->bus.send(signal(true)); QTRY_VERIFY(!active(object));
        power->change(DisplayDevice, {{"Percentage", 60.0}});
        QTest::qWait(60); QCOMPARE(power->enumerations, 1);
        power->bus.send(signal(false)); QTRY_VERIFY(active(object)); QTRY_VERIFY(ready(object));
        QCOMPARE(power->enumerations, 2); QCOMPARE(state(object).value(QStringLiteral("battery")).toInt(), 60);
    }
    void unavailableReadingsKeepTheLastSnapshotInsteadOfZero() {
        auto object = create(QStringLiteral("eDP-1"), true); QTRY_VERIFY(ready(object));
        const auto before = object->property("batteries");
        power->change(Battery, {{"Percentage", QStringLiteral("unknown")}});
        power->change(DisplayDevice, {{"Percentage", QStringLiteral("unknown")}});
        QTRY_VERIFY(!ready(object)); QCOMPARE(object->property("batteries"), before);
        QVERIFY(!state(object).value(QStringLiteral("available")).toBool());
        power->change(Battery, {{"Percentage", 79.0}}); power->change(DisplayDevice, {{"Percentage", 79.0}});
        QTRY_VERIFY(ready(object)); QCOMPARE(state(object).value(QStringLiteral("battery")).toInt(), 79);
        power->removeMouse(); QTRY_COMPARE(object->property("batteries").toList().size(), 1);
    }
    void ownerReplacementCannotAcceptOldPowerReplies() {
        power->defer = DisplayDevice;
        auto object = create(QStringLiteral("eDP-1"), true); QTRY_VERIFY(!power->held.isEmpty());
        power->drop(); QTRY_VERIFY(!object->property("powerLoading").toBool());
        Power replacement(QStringLiteral("fixture-power-replacement"));
        replacement.props[DisplayDevice].insert(QStringLiteral("Percentage"), 33.0); replacement.acquire();
        QTRY_VERIFY(ready(object)); QCOMPARE(state(object).value(QStringLiteral("battery")).toInt(), 33);
        power->release(); QTest::qWait(40); QCOMPARE(state(object).value(QStringLiteral("battery")).toInt(), 33);
        replacement.drop(); power->acquire(); QTRY_COMPARE(state(object).value(QStringLiteral("battery")).toInt(), 80);
    }
    void unsupportedOrRemovedProtocolsStayUsableAndRecover() {
        auto object = create(QStringLiteral("eDP-1")); QTRY_VERIFY(object->property("displayKnown").toBool());
        server->setMode(QStringLiteral("eDP-1"), 3); QTRY_VERIFY(!active(object));
        server->setSupported(QStringLiteral("eDP-1"), false); QTRY_VERIFY(active(object)); QVERIFY(!object->property("displayKnown").toBool());
        server->setSupported(QStringLiteral("eDP-1"), true); QTRY_VERIFY(!active(object));
        server->removeManager(); QTRY_VERIFY(active(object)); QVERIFY(!object->property("displayKnown").toBool());
        server->addManager(); QTRY_VERIFY(!active(object));
        server->removeOutput(QStringLiteral("eDP-1")); QTRY_VERIFY(active(object)); QVERIFY(!object->property("displayKnown").toBool());
        server->addOutput(QStringLiteral("eDP-1"), 3); QTRY_VERIFY(!active(object));
        QCOMPARE(server->modeRequests, 0);
    }
    void compositorReconnectDropsOldDisplayState() {
        auto object = create(QStringLiteral("eDP-1")); QTRY_VERIFY(object->property("displayKnown").toBool());
        server->setMode(QStringLiteral("eDP-1"), 3); QTRY_VERIFY(!active(object));
        server.reset(); QTRY_VERIFY(!object->property("displayKnown").toBool()); QVERIFY(active(object));
        server = std::make_unique<FakeWayland>();
        server->setMode(QStringLiteral("eDP-1"), 3);
        QTRY_VERIFY(object->property("displayKnown").toBool()); QVERIFY(!active(object));
        server->setMode(QStringLiteral("eDP-1"), 0); QTRY_VERIFY(active(object));
    }
};

class FixtureControl : public QObject {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.monet.ActivityFixture")
public:
    FixtureControl(FakeWayland &server, Locker &locker, Power &power) : server(server), locker(locker), power(power) {}
public Q_SLOTS:
    void SetLocked(bool locked) { locker.setActive(locked); }
    bool SetMode(const QString &output, uint mode) {
        if ((output != QStringLiteral("eDP-1") && output != QStringLiteral("HDMI-A-1")) || mode > 3) return false;
        server.setMode(output, mode); return true;
    }
    void SetBattery(double level, bool plugged) {
        power.change(Battery, {{"Percentage", level}}); power.change(DisplayDevice, {{"Percentage", level}});
        power.change(Root, {{"OnBattery", !plugged}});
    }
    QString Metrics() {
        QVariantMap reads;
        for (auto it = power.reads.cbegin(); it != power.reads.cend(); ++it) reads.insert(it.key(), it.value());
        return QString::fromUtf8(QJsonDocument::fromVariant(QVariantMap{{"enumerations", power.enumerations},
            {"reads", reads}, {"lockerReads", locker.reads}, {"modeRequests", server.modeRequests}}).toJson(QJsonDocument::Compact));
    }
private:
    FakeWayland &server;
    Locker &locker;
    Power &power;
};

int main(int argc, char **argv)
{
    QGuiApplication app(argc, argv);
    if (app.arguments().contains(QStringLiteral("--fixture"))) {
        if (qEnvironmentVariableIsEmpty("DBUS_SESSION_BUS_ADDRESS") || qgetenv("DBUS_SYSTEM_BUS_ADDRESS") != qgetenv("DBUS_SESSION_BUS_ADDRESS"))
            qFatal("Activity fixtures require an isolated bus shared by the two test connections");
        FakeWayland server; Locker locker; Power power(QStringLiteral("fixture-power")); power.acquire();
        FixtureControl control(server, locker, power);
        auto bus = QDBusConnection::sessionBus();
        if (!bus.registerObject(QStringLiteral("/Fixture"), &control, QDBusConnection::ExportAllSlots)
                || !bus.registerService(QStringLiteral("org.monet.ActivityFixture"))) qFatal("Cannot register activity fixture controls");
        std::puts("READY"); std::fflush(stdout);
        return app.exec();
    }
    ActivityTest tests;
    return QTest::qExec(&tests, argc, argv);
}
#include "activity-test.moc"
