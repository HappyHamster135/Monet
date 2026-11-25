// Run only with a disposable home/config and private D-Bus session.
#include <QApplication>
#include <QDebug>
#include <QImage>
#include <QIcon>
#include <QQuickWindow>
#include <QQmlEngine>
#include <QQmlExpression>
#include <QTest>
#include <QTimer>
#include <KConfigGroup>
#include <KConfigPropertyMap>
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

static QString launcher(QQuickItem *task)
{
    QQmlExpression expression(QQmlEngine::contextForObject(task), task,
                             QStringLiteral("String(model.LauncherUrlWithoutIcon)"));
    const auto value = expression.evaluate();
    require(!expression.hasError(), "Cannot read the launcher's stable URL");
    return value.toString();
}

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    QIcon::setThemeName(QStringLiteral("breeze"));
    if (app.arguments().contains(QStringLiteral("--rtl"))) app.setLayoutDirection(Qt::RightToLeft);
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
        config.writeEntry("sortingStrategy", 1);
        config.writeEntry("monetIconAlignment", QStringLiteral("center"));
        config.sync();
        auto dock = PlasmaQuick::AppletQuickItem::itemForApplet(applet);
        require(dock, "Native task applet failed to instantiate");
        QQuickWindow window;
        window.resize(640, 240);
        dock->setParentItem(window.contentItem());
        dock->setPosition(QPointF(48, 100));
        dock->setSize(QSizeF(440, 64));
        dock->setVisible(true);
        window.show();
        for (int i = 0; i < 100 && tasks(dock).size() < 3; ++i) QTest::qWait(20);
        QTest::qWait(350); // Initial mirrored/centered layout must settle before pointer targeting.
        // The applet can load the distribution's pins before the fixture writes
        // its KConfig group. Update the live map just as its configuration UI does.
        applet->configuration()->setProperty("launchers", launchers);
        auto expectedPins = launchers;
        expectedPins.sort();
        require(QTest::qWaitFor([&] {
            QStringList current;
            for (auto item : tasks(dock)) current.append(launcher(item));
            current.sort();
            return current == expectedPins;
        }, 2000), "Native applet did not load the fixture launchers");
        auto buttons = tasks(dock);
        require(buttons.first()->isVisible(), "Native launcher delegates are not visible");
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

        QQuickItem *handler = nullptr;
        for (auto item : descendants(dock)) {
            if (item->metaObject()->indexOfMethod("monetReorder(QVariant)") >= 0) handler = item;
        }
        require(handler, "Compiled reorder handler is unavailable");
        auto source = buttons.first();
        const int original = source->property("index").toInt();
        dock->setProperty("dragSource", QVariant::fromValue(source));
        require(dock->property("monetReordering").toBool(), "Manual bottom-dock reorder is unavailable");
        auto reorder = [&](int slot) {
            const auto ordered = tasks(dock);
            auto destination = *std::find_if(ordered.begin(), ordered.end(), [slot](auto task) {
                return task->property("index").toInt() == slot;
            });
            // Drop events are in the full applet's coordinates, including the
            // space beside a centered or mirrored task list. Ignore translations.
            const auto position = destination->parentItem()->mapToItem(handler,
                QPointF(destination->x() + destination->width() / 2 + (destination->x() > source->x() ? 6 : -6),
                        destination->y() + destination->height() / 2));
            QVariant result;
            require(QMetaObject::invokeMethod(handler, "monetReorder", Q_RETURN_ARG(QVariant, result),
                    Q_ARG(QVariant, position)), "Reorder call failed");
            require(result.toBool(), "Internal drag fell through to visual hit testing");
            QTest::qWait(20);
            require(source->property("index").toInt() == slot, "Reorder did not reach the requested slot");
        };
        reorder(1);
        // The first delegate starts at x=0. Its very first move must slide too.
        const auto painted = source->mapToItem(source->parentItem(), QPointF(0, 0));
        require(qAbs(painted.x() - source->x()) > 1, "First reorder jumped without an animation");
        require(source->parentItem()->property("animating").toBool(), "Reorder did not animate");
        reorder(original == 0 ? 2 : 0); // Must accept the next slot before the first animation finishes.
        reorder(original); // Reversing direction must not wait for a timer either.
        dock->setProperty("dragSource", QVariant::fromValue<QQuickItem *>(nullptr));
        QTest::qWait(400);
        require(!source->parentItem()->property("animating").toBool(), "Reorder animation never settled");
        require(qAbs(source->mapToItem(source->parentItem(), QPointF()).x() - source->x()) < 0.5,
                "Reorder retained an obsolete translation");

        dock->setWidth(64); QTest::qWait(350);
        auto viewport = dock->findChild<QQuickItem *>(QStringLiteral("monetTaskViewport"));
        require(viewport && viewport->clip(), "Crowded task icons can paint over the neighbouring tray");
        require(viewport->property("contentWidth").toDouble() > viewport->width(), "Crowded taskbar has no accessible overflow");
        auto nextTasks = dock->findChild<QQuickItem *>(QStringLiteral("monetNextTasks"));
        require(nextTasks && nextTasks->isVisible(), "Taskbar overflow cannot be reached");
        QTest::mouseClick(&window, Qt::LeftButton, Qt::NoModifier, nextTasks->mapToScene(QPointF(nextTasks->width()/2, nextTasks->height()/2)).toPoint());
        QTest::qWait(100);
        require(viewport->property("contentX").toDouble() > 0, "More apps button did not scroll the taskbar");
        dock->setWidth(520); QTest::qWait(350);
        require(!viewport->clip() && viewport->property("contentX").toDouble() == 0, "Widening the taskbar retained stale overflow geometry");

        // Exercise the real press/hold/move/release path. Calling monetReorder
        // alone cannot catch platform QDrag freezes or lost handler grabs.
        for (int round = 0; round < 3; ++round) {
            buttons = tasks(dock);
            source = buttons.first();
            const auto sourceId = launcher(source);
            require(!sourceId.isEmpty(), "Fixture launcher has no stable identity");
            auto neighbour = buttons[1];
            const int destinationIndex = neighbour->property("index").toInt();
            const auto press = source->mapToScene(QPointF(source->width()/2, source->height()/2)).toPoint();
            const auto destination = neighbour->mapToScene(QPointF(neighbour->width()/2 + 8, neighbour->height()/2)).toPoint();
            QTest::mouseMove(&window, press); QTest::qWait(180);
            QTest::mousePress(&window, Qt::LeftButton, Qt::NoModifier, press);
            QTest::mouseMove(&window, press + QPoint(18, 0)); QTest::qWait(20);
            require(dock->property("monetInternalDragging").toBool(), "Real icon drag entered the platform drag loop or failed to grab");
            require(viewport->clip(), "Held icon can paint over neighbouring tray widgets");
            int ticks = 0;
            QTimer heartbeat;
            QObject::connect(&heartbeat, &QTimer::timeout, [&] { ++ticks; });
            heartbeat.start(10);
            QTest::mouseMove(&window, destination); QTest::qWait(35);
            require(source->property("index").toInt() == destinationIndex, "Held icon did not reorder through actual pointer input");
            require(source->parentItem()->property("animating").toBool(), "Neighbour did not slide aside during a real drag");
            const auto moving = neighbour->mapToItem(neighbour->parentItem(), QPointF());
            require(qAbs(moving.x() - neighbour->x()) > 1, "Neighbour jumped instead of sliding");
            const auto followed = source->mapToScene(QPointF(source->width()/2, source->height()/2));
            require(qAbs(followed.x() - destination.x()) < 22, "Held icon did not follow the pointer");
            const auto during = window.grabWindow();
            QTest::qWait(320);
            require(ticks >= 15, "Holding an icon starved the UI event loop");
            require(source->property("index").toInt() == destinationIndex, "Stationary held pointer made the order oscillate");
            require(!source->parentItem()->property("animating").toBool(), "Stationary drag kept restarting animations");
            const auto after = window.grabWindow();
            if (qEnvironmentVariableIsSet("MONET_DOCK_CAPTURE")) {
                const auto prefix = qEnvironmentVariable("MONET_DOCK_CAPTURE") + QString::number(round);
                during.save(prefix + QStringLiteral("-during.png"));
                after.save(prefix + QStringLiteral("-after.png"));
            }
            require(!during.isNull() && during != after, "Reordering did not animate rendered pixels");
            QTest::mouseRelease(&window, Qt::LeftButton, Qt::NoModifier, destination);
            QTest::qWait(350);
            require(!dock->property("monetInternalDragging").toBool() && dock->property("dragSource").isNull(),
                    "Releasing a real drag left the taskbar stuck");
            const auto saved = tasks(dock);
            const auto released = std::find_if(saved.begin(), saved.end(), [&](auto item) {
                return launcher(item) == sourceId;
            });
            // syncLaunchers may replace delegates. Check the saved app's
            // identity rather than dereferencing the old pointer after release.
            require(released != saved.end() && (*released)->property("index").toInt() == destinationIndex,
                    "Releasing a real drag restored the previous order");
        }

        // Leaving the bar keeps Plasma's system drag available. Cancelling it
        // must not save launchers early and destroy the exporting delegate.
        source = tasks(dock).first();
        const auto exportPress = source->mapToScene(QPointF(source->width()/2, source->height()/2)).toPoint();
        QTest::mousePress(&window, Qt::LeftButton, Qt::NoModifier, exportPress);
        QTest::mouseMove(&window, exportPress + QPoint(18, 0)); QTest::qWait(30);
        require(dock->property("monetInternalDragging").toBool(), "Export fixture did not start an internal drag");
        QTimer::singleShot(200, &window, [&] { QTest::keyClick(&window, Qt::Key_Escape); });
        const auto outside = exportPress - QPoint(0, 95);
        QTest::mouseMove(&window, outside); QTest::qWait(260);
        QTest::mouseRelease(&window, Qt::LeftButton, Qt::NoModifier, outside); QTest::qWait(350);
        require(!dock->property("monetInternalDragging").toBool() && dock->property("dragSource").isNull(),
                "Cancelled external drag left the bar stuck");
        require(tasks(dock).size() == 3, "Exporting a launcher lost a pinned app");
        for (int round = 0; round < 3; ++round) {
            source = tasks(dock).first();
            const auto press = source->mapToScene(QPointF(source->width()/2, source->height()/2)).toPoint();
            QTest::mousePress(&window, Qt::LeftButton, Qt::NoModifier, press);
            QTest::mouseMove(&window, press + QPoint(18, 0)); QTest::qWait(20);
            QTimer::singleShot(100, &window, [&] { QTest::keyClick(&window, Qt::Key_Escape); });
            const auto outside = press - QPoint(0, 95);
            QTest::mouseMove(&window, outside);
            QTest::mouseRelease(&window, Qt::LeftButton, Qt::NoModifier, outside);
            QTest::qWait(250);
            require(!dock->property("monetInternalDragging").toBool() && dock->property("dragSource").isNull(),
                    "Quick release during export left a stale drag source");
        }

        // Rapid edge changes interrupt in-flight layout/hover animations. No
        // old horizontal translation or overflow offset may survive the swap.
        for (int round = 0; round < 16; ++round) {
            panel->setLocation(Plasma::Types::LeftEdge);
            panel->setFormFactor(Plasma::Types::Vertical);
            dock->setSize(QSizeF(64, 200));
            QTest::qWait(round % 2 ? 20 : 220);
            panel->setLocation(Plasma::Types::BottomEdge);
            panel->setFormFactor(Plasma::Types::Horizontal);
            dock->setSize(QSizeF(round % 2 ? 64 : 520, 64));
            QTest::qWait(round % 2 ? 20 : 220);
        }
        dock->setSize(QSizeF(520, 64)); QTest::qWait(350);
        buttons = tasks(dock);
        require(buttons.size() == 3, "Edge switching recreated or lost pinned apps");
        for (int i = 0; i < buttons.size(); ++i) {
            auto item = buttons[i];
            const auto bounds = item->mapRectToItem(dock, item->boundingRect());
            require(bounds.left() >= -1 && bounds.right() <= dock->width()+1
                    && bounds.top() >= -1 && bounds.bottom() <= dock->height()+1,
                    "Edge switching left an icon outside the taskbar");
            require(qAbs(item->mapToItem(item->parentItem(), QPointF()).x() - item->x()) < .5,
                    "Edge switching retained an obsolete reorder translation");
            if (i) require(item->x() >= buttons[i-1]->x() + buttons[i-1]->width() - 1,
                           "Edge switching left overlapping task icons");
        }
        require(!viewport->clip() && viewport->property("contentX").toDouble() == 0,
                "Edge switching retained the previous orientation's overflow");
        require(!buttons.first()->parentItem()->property("animating").toBool(), "Edge switching left animation permanently active");

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
        QQuickItem *dropFeedback = nullptr;
        for (auto item : descendants(trash)) if (item->objectName() == QStringLiteral("monetTrashDropFeedback")) dropFeedback = item;
        require(dropFeedback, "Trash drop feedback is missing");
        const auto dropBounds = QRectF(trash->position(), trash->size());
        const auto beforeDrop = window.grabWindow().copy(dropBounds.toRect());
        trash->setProperty("containsAcceptableDrag", true); QTest::qWait(300);
        require(dropFeedback->property("opacity").toDouble() > .4, "Accepted file drag has no Trash highlight");
        const auto duringDrop = window.grabWindow().copy(dropBounds.toRect());
        require(!beforeDrop.isNull() && !duringDrop.isNull() && beforeDrop != duringDrop,
                "Trash accepted a drag without changing any rendered pixels");
        require(QRectF(trash->position(), trash->size()) == dropBounds, "Trash drop feedback moved the drop target");
        trash->setProperty("containsAcceptableDrag", false); QTest::qWait(300);
        require(dropFeedback->property("opacity").toDouble() == 0, "Cancelled file drag left Trash highlighted");
        window.close();
        qInfo() << "Native hover, real animated pointer drags, event-loop responsiveness and repeated edge switching passed.";
        return 0;
    } catch (const std::exception &error) {
        qCritical() << error.what();
        return 1;
    }
}
