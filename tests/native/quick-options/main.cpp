// SPDX-License-Identifier: GPL-3.0-or-later
// Only run in a private home/bus with the fake helper staged by the Python fixture.
#include <QApplication>
#include <QDebug>
#include <QJSValue>
#include <QQmlComponent>
#include <QQmlEngine>
#include <QQuickWindow>
#include <QTest>
#include <KLocalizedString>
#include <Plasma/Applet>
#include <Plasma/Containment>
#include <Plasma/Corona>
#include <PlasmaQuick/AppletQuickItem>
#include <stdexcept>

class TestCorona : public Plasma::Corona {
public:
    QRect screenGeometry(uint) const override { return QRect(0, 0, 1000, 800); }
};
static void require(bool test, const char *message) { if (!test) throw std::runtime_error(message); }
static QQuickItem *find(QQuickItem *root, const QString &name) {
    if (root->objectName() == name) return root;
    for (auto child : root->childItems()) if (auto found = find(child, name)) return found;
    return nullptr;
}
static QVariantMap info(QObject *root) {
    auto value = root->property("info");
    return value.canConvert<QJSValue>() ? value.value<QJSValue>().toVariant().toMap() : value.toMap();
}
int main(int argc, char **argv) {
    QApplication app(argc, argv);
    KLocalizedString::setApplicationDomain("monet");
    try {
        TestCorona corona;
        auto panel = corona.createContainment(QStringLiteral("org.kde.panel"));
        require(panel, "Missing panel containment");
        panel->setFormFactor(Plasma::Types::Horizontal); panel->setLocation(Plasma::Types::BottomEdge);
        auto applet = panel->createApplet(QStringLiteral("org.monet.quick"));
        require(applet, "Missing staged Quick Settings applet");
        auto quick = PlasmaQuick::AppletQuickItem::itemForApplet(applet);
        require(quick, "Quick Settings root failed to instantiate");
        auto component = quick->property("fullRepresentation").value<QQmlComponent *>();
        require(component, "Missing Quick Settings full representation");
        for (int i=0; component->isLoading() && i<200; ++i) QTest::qWait(20);
        if (component->isError()) qWarning() << component->errors();
        auto representation = qobject_cast<QQuickItem *>(component->create(component->creationContext()));
        require(representation, "Quick Settings full representation failed to instantiate");
        QQuickWindow window; window.resize(440, 520);
        representation->setParentItem(window.contentItem()); representation->setSize(QSizeF(440, 520));
        window.show(); QTest::qWait(150);
        quick->setProperty("info", QVariantMap{{"wifi",true},{"bluetooth",true},{"night",false},{"quiet",false},
            {"quietIndefinite",false},{"quietUntil",0},{"lanConnected",false}});
        auto click = [&](const QString &name) {
            auto item = find(representation, name); require(item, "Missing visible action in Quick Settings");
            QTest::mouseClick(&window, Qt::LeftButton, Qt::NoModifier,
                item->mapToScene(QPointF(item->width()/2,item->height()/2)).toPoint());
        };
        const QList<QPair<QString,QString>> pages{{"wifi","wifi"},{"bluetooth","bluetooth"},{"display","night"},{"notifications","quiet"}};
        for (const auto &[tile,page] : pages) {
            const auto before = info(quick);
            click("quickMore-"+tile);
            require(info(quick)==before, "Chevron also toggled the tile");
            require(quick->property("optionsPage").toString()==page, "Chevron opened Settings instead of inline choices");
            for(int i=0; i<200; ++i) {
                auto pane=find(representation,"quickOptionsPane");
                if(pane && !pane->property("busy").toBool()) break;
                QTest::qWait(20);
            }
            require(find(representation,"quickOptionsPane"), "Inline options never appeared");
            require(!find(representation,"quickOptionsPane")->property("busy").toBool(), "Inline choices never finished loading");
            QTest::qWait(60);
            if(argc>1) window.grabWindow().save(QString::fromLocal8Bit(argv[1])+"/quick-"+page+".png");
            click("quickOptionsBack");
            require(quick->property("optionsPage").toString().isEmpty(), "Back did not return to Quick Settings");
            QTest::qWait(60);
        }
        window.close(); delete representation;
        qInfo() << "Actual Quick Settings chevrons opened all four inline panels without toggling their radios.";
        return 0;
    } catch(const std::exception &error) { qCritical() << error.what(); return 1; }
}
