#include <QApplication>
#include <QCheckBox>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QLineEdit>
#include <QPushButton>
#include <QScrollArea>
#include <QScrollBar>
#include <QSettings>
#include <QStackedWidget>
#include <QStyleFactory>
#include <QTabBar>
#include <QTabWidget>
#include <QTemporaryDir>
#include <QTest>
#include <QSignalSpy>
#include <QWheelEvent>
#include <QTextEdit>
#include "backgrounddrag.h"

class ObservedDrag : public BackgroundDrag {
public:
    int moves = 0;
protected:
    bool startMove(QWindow *) override { ++moves; return true; }
};

class LayoutTest : public QObject {
    Q_OBJECT
    QTemporaryDir config;
private slots:
    void initTestCase()
    {
        // Exercise the proxy independently of KDE/Kvantum being installed.
        qputenv("XDG_CONFIG_HOME", config.path().toUtf8());
        QSettings settings(config.filePath("kdeglobals"), QSettings::IniFormat);
        settings.setValue("KDE/widgetStyle", "Fusion");
        settings.sync();
        auto style = QStyleFactory::create("MonetSettings");
        QVERIFY(style);
        qApp->setStyle(style);
    }

    void fullFormAndTabsRemainReachable()
    {
        QScrollArea area;
        area.setWidgetResizable(true);
        auto root = new QWidget;
        auto outer = new QVBoxLayout(root);
        auto form = new QWidget;
        form->setMinimumSize(100, 200); // plasma-nm's explicit minimum
        auto row = new QHBoxLayout(form);
        auto list = new QWidget;
        list->setMinimumWidth(235);
        row->addWidget(list);
        auto tabs = new QTabWidget;
        auto page = new QWidget;
        auto fields = new QVBoxLayout(page);
        auto field = new QPushButton("A wide native settings field");
        field->setMinimumWidth(600);
        fields->addWidget(field);
        tabs->addTab(page, "General");
        tabs->addTab(new QWidget, "Wired");
        row->addWidget(tabs);
        outer->addWidget(form);
        area.setWidget(root);
        area.resize(640, 400);
        area.show();
        QTest::qWait(20);

        QVERIFY(form->minimumWidth() >= row->minimumSize().width());
        QVERIFY(field->mapTo(page, field->rect().bottomRight()).x() < page->width());
        QVERIFY(tabs->tabBar()->y() >= 4);
        auto stack = tabs->findChild<QStackedWidget *>();
        QVERIFY(stack);
        QVERIFY(stack->y() > tabs->tabBar()->geometry().bottom() + 4);

        auto bar = area.horizontalScrollBar();
        QVERIFY(bar->isVisible());
        QVERIFY(bar->maximum() > 0);
        // Shift+wheel over a field pans the whole module.
        bar->setValue(0);
        QWheelEvent wheel(QPointF(5, 5), QPointF(field->mapToGlobal(QPoint(5, 5))),
                          QPoint(), QPoint(0, -120), Qt::NoButton, Qt::ShiftModifier,
                          Qt::NoScrollPhase, false);
        QApplication::sendEvent(field, &wheel);
        QVERIFY(bar->value() > 0);
        // Keyboard users can reach the full right edge too.
        QCOMPARE(bar->focusPolicy(), Qt::StrongFocus);
        bar->setFocus();
        QTest::keyClick(bar, Qt::Key_End);
        QCOMPARE(bar->value(), bar->maximum());
        const int right = field->mapTo(area.viewport(), field->rect().bottomRight()).x();
        QVERIFY(right < area.viewport()->width());

        // Dynamically added pages must update the scroll range, not become clipped.
        const int previous = bar->maximum();
        auto extra = new QWidget;
        auto layout = new QVBoxLayout(extra);
        auto wider = new QLineEdit;
        wider->setMinimumWidth(800);
        layout->addWidget(wider);
        tabs->addTab(extra, "Another page");
        tabs->setCurrentWidget(extra);
        QTest::qWait(20);
        QVERIFY(bar->maximum() > previous);
        bar->setValue(bar->maximum());
        QVERIFY(wider->mapTo(area.viewport(), wider->rect().bottomRight()).x() < area.viewport()->width());
    }

    void longRowsWrapAtNarrowWidths()
    {
        QWidget form;
        auto layout = new QFormLayout(&form);
        auto label = new QCheckBox("Connect automatically with priority");
        auto field = new QLineEdit;
        field->setMinimumWidth(180);
        layout->addRow(label, field);
        form.resize(320, 180);
        form.show();
        QTest::qWait(20);
        QCOMPARE(layout->rowWrapPolicy(), QFormLayout::WrapLongRows);
        QVERIFY(field->y() > label->geometry().bottom());
        QVERIFY(field->geometry().right() < form.width());
    }

    void framelessTabsHaveBreathingRoom()
    {
        // KPageWidget's Audio CDs page uses document-mode tabs.
        QTabWidget tabs;
        tabs.setDocumentMode(true);
        tabs.setUsesScrollButtons(false);
        tabs.addTab(new QWidget, "General");
        tabs.addTab(new QWidget, "FLAC Encoder");
        tabs.resize(600, 300);
        tabs.show();
        QTest::qWait(20);
        QVERIFY(tabs.usesScrollButtons());
        QVERIFY(tabs.tabBar()->y() >= 8);
        auto stack = tabs.findChild<QStackedWidget *>();
        QVERIFY(stack);
        QVERIFY(stack->y() >= tabs.tabBar()->geometry().bottom() + 8);
    }

    void fixedWidgetSizesArePreserved()
    {
        QScrollArea area;
        auto fixed = new QWidget;
        fixed->setFixedWidth(240);
        auto row = new QHBoxLayout(fixed);
        row->addWidget(new QPushButton("Fixed width"));
        area.setWidget(fixed);
        area.show();
        QTest::qWait(20);
        QCOMPARE(fixed->width(), 240);
        QCOMPARE(row->sizeConstraint(), QLayout::SetDefaultConstraint);
    }

    void backgroundDragRespectsControlsAndThreshold()
    {
        QWidget window;
        window.resize(400, 300);
        QPushButton button("Button", &window);
        button.setGeometry(20, 20, 100, 40);
        QTextEdit editor(&window);
        editor.setGeometry(20, 80, 200, 100);
        QLineEdit field(&window);
        field.setGeometry(20, 200, 200, 40);
        QLabel label("Selectable", &window);
        label.setTextInteractionFlags(Qt::TextSelectableByMouse);
        window.show();
        QTest::qWait(20);
        QVERIFY(BackgroundDrag::eligible(&window, QPoint(350, 250)));
        QVERIFY(!BackgroundDrag::eligible(&button, QPoint(20, 20)));
        QVERIFY(!BackgroundDrag::eligible(editor.viewport(), QPoint(20, 20)));
        QVERIFY(!BackgroundDrag::eligible(&field, QPoint(20, 20)));
        QVERIFY(!BackgroundDrag::eligible(&label, QPoint(5, 5)));

        ObservedDrag drag;
        qApp->installEventFilter(&drag);
        QTest::mousePress(&window, Qt::LeftButton, Qt::NoModifier, QPoint(350, 250));
        QTest::mouseMove(&window, QPoint(351, 250));
        QCOMPARE(drag.moves, 0);
        QTest::mouseMove(&window, QPoint(380, 250));
        QCOMPARE(drag.moves, 1);
        QTest::mouseRelease(&window, Qt::LeftButton, Qt::NoModifier, QPoint(380, 250));
        QSignalSpy clicked(&button, &QPushButton::clicked);
        QTest::mouseClick(&button, Qt::LeftButton);
        QCOMPARE(clicked.count(), 1);
        QTest::mousePress(&window, Qt::LeftButton, Qt::ShiftModifier, QPoint(350, 250));
        QTest::mouseMove(&window, QPoint(380, 250));
        QTest::mouseRelease(&window, Qt::LeftButton, Qt::ShiftModifier, QPoint(380, 250));
        QCOMPARE(drag.moves, 1);
        qApp->removeEventFilter(&drag);
    }
};
QTEST_MAIN(LayoutTest)
#include "layout-test.moc"
