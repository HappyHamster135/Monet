// Run only with a disposable home/config and private D-Bus session.
#include <QApplication>
#include <QDebug>
#include <QQuickWindow>
#include <QTest>
#include <KConfigGroup>
#include <KLocalizedString>
#include <Plasma/Applet>
#include <Plasma/Containment>
#include <Plasma/Corona>
#include <PlasmaQuick/AppletQuickItem>
#include <algorithm>
#include <stdexcept>

class TestCorona : public Plasma::Corona
{
public:
    QRect screenGeometry(uint) const override { return QRect(0, 0, 640, 240); }
};

static void require(bool condition, const char *message)
{
    if (!condition) throw std::runtime_error(message);
}

static QList<QQuickItem *> descendants(QQuickItem *root)
{
    QList<QQuickItem *> result{root};
    for (auto child : root->childItems()) result.append(descendants(child));
    return result;
}

static QList<QQuickItem *> tasks(QQuickItem *root)
{
    QList<QQuickItem *> result;
    for (auto item : descendants(root)) {
        if (item->property("inPopup").isValid() && !item->property("inPopup").toBool()
                && item->property("index").toInt() >= 0) result.append(item);
    }
    std::sort(result.begin(), result.end(), [](auto a, auto b) { return a->x() < b->x(); });
    return result;
}

static QQuickItem *motion(QQuickItem *task)
{
    for (auto child : descendants(task)) {
        if (child->property("amount").isValid() && child->property("iconScale").isValid()) return child;
    }
    throw std::runtime_error("Compiled applet did not load Monet's motion component");
}

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    KLocalizedString::setApplicationDomain("monet");
    try {
        TestCorona corona;
        auto panel = corona.createContainment(QStringLiteral("org.kde.panel"));
        require(panel, "Panel containment is unavailable");
        panel->setFormFactor(Plasma::Types::Horizontal);
        panel->setLocation(Plasma::Types::BottomEdge);
        auto applet = panel->createApplet(QStringLiteral("org.kde.plasma.icontasks"));
        require(applet, "Native icons-only applet is unavailable");
        const QStringList launchers{"applications:org.kde.dolphin.desktop", "applications:org.kde.konsole.desktop",
                                    "applications:org.kde.kate.desktop"};
        auto config = applet->config();
        config.writeEntry("launchers", launchers);
        config.writeEntry("taskHoverEffect", true);
        config.writeEntry("showToolTips", true);
        config.writeEntry("maxStripes", 1);
        config.sync();
        auto dock = PlasmaQuick::AppletQuickItem::itemForApplet(applet);
        require(dock, "Native task applet failed to instantiate");
        QQuickWindow window;
        window.resize(640, 240);
        dock->setParentItem(window.contentItem());
        dock->setPosition(QPointF(48, 100));
        dock->setSize(QSizeF(440, 64));
        window.show();
        for (int i = 0; i < 100 && tasks(dock).size() < 3; ++i) QTest::qWait(20);
        auto buttons = tasks(dock);
        require(buttons.size() >= 3, "Native launcher delegates did not appear");
        require(dock->property("monetMotionEnabled").toBool(), "Dock motion unexpectedly disabled");
        QTest::mouseMove(&window, QPoint(10, 10));
        for (int round = 0; round < 2; ++round) {
            for (auto task : buttons) {
                const auto point = task->mapToScene(QPointF(task->width() / 2, task->height() / 2)).toPoint();
                QTest::mouseMove(&window, point);
                QTest::qWait(300);
                require(dock->property("monetHoverActive").toBool(), "Hover tracker missed a native tooltip area");
                require(task->property("containsMouse").toBool(), "Native tooltip hover was blocked");
                require(motion(task)->property("iconScale").toDouble() > 1.25, "Hovered native icon did not enlarge");
            }
        }
        QTest::mouseMove(&window, QPoint(10, 10));
        QTest::qWait(300);
        require(!dock->property("monetHoverActive").toBool(), "Dock stayed hovered after exit");
        for (auto task : buttons) require(qFuzzyCompare(motion(task)->property("iconScale").toDouble(), 1.0), "An icon remained enlarged");
        corona.setEditMode(true);
        QTest::qWait(50);
        require(!dock->property("monetMotionEnabled").toBool(), "Edit mode did not disable motion");
        corona.setEditMode(false);
        const auto point = buttons.first()->mapToScene(QPointF(buttons.first()->width() / 2, 32)).toPoint();
        QTest::mouseMove(&window, point); QTest::qWait(300);
        require(motion(buttons.first())->property("iconScale").toDouble() > 1.25, "Motion did not recover after edit mode");

        auto trashApplet = panel->createApplet(QStringLiteral("org.kde.plasma.trash"));
        auto trash = PlasmaQuick::AppletQuickItem::itemForApplet(trashApplet);
        require(trash, "Native Trash applet failed to instantiate");
        trash->setParentItem(window.contentItem());
        trash->setPosition(QPointF(520, 100)); trash->setSize(QSizeF(64, 64));
        QTest::qWait(300);
        QTest::mouseMove(&window, QPoint(552, 132)); QTest::qWait(300);
        require(motion(trash)->property("iconScale").toDouble() > 1.25, "Native Trash did not enlarge");
        QTest::mouseMove(&window, QPoint(10, 10)); QTest::qWait(300);
        require(qFuzzyCompare(motion(trash)->property("iconScale").toDouble(), 1.0), "Native Trash remained enlarged");
        window.close();
        qInfo() << "Native task and Trash hover, tooltip delivery, exit and edit-mode recovery passed.";
        return 0;
    } catch (const std::exception &error) {
        qCritical() << error.what();
        return 1;
    }
}
