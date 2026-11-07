// SPDX-License-Identifier: GPL-3.0-or-later
#include "../experience.h"
#include <QFile>
#include <QStandardPaths>
#include <QTemporaryDir>
#include <QTest>
#include <QSignalSpy>
#include <QScreen>

class DolphinView : public QWidget { Q_OBJECT public: using QWidget::QWidget; };

class ExperienceTest : public QObject {
    Q_OBJECT
private Q_SLOTS:
    void initTestCase() { QStandardPaths::setTestModeEnabled(true); }
    void keepBothUsesNativeNamingAndPreservesFiles()
    {
        QTemporaryDir folder;
        QVERIFY(folder.isValid());
        const auto source = folder.filePath(QStringLiteral("source.txt"));
        const auto destination = folder.filePath(QStringLiteral("report.txt"));
        for (const auto &path : {source, destination}) {
            QFile file(path); QVERIFY(file.open(QIODevice::WriteOnly)); file.write("original");
        }
        KIO::RenameDialog dialog(nullptr, QStringLiteral("Conflict"), QUrl::fromLocalFile(source),
            QUrl::fromLocalFile(destination), KIO::RenameDialog_Overwrite, 8, 8);
        MonetFilesExperience::improveConflict(&dialog);
        MonetFilesExperience::improveConflict(&dialog);
        const auto buttons = dialog.findChildren<QPushButton *>(QStringLiteral("monetKeepBoth"));
        QCOMPARE(buttons.size(), 1);
        if (!qEnvironmentVariable("MONET_FILES_NATIVE_CAPTURE").isEmpty()) {
            dialog.show(); QTest::qWait(100);
            QVERIFY(dialog.grab().save(qEnvironmentVariable("MONET_FILES_NATIVE_CAPTURE")));
        }
        buttons[0]->click();
        QCOMPARE(dialog.result(), int(KIO::Result_Rename));
        QVERIFY(dialog.newDestUrl().toLocalFile() != destination);
        QVERIFY(!QFile::exists(dialog.newDestUrl().toLocalFile()));
        QFile file(destination); QVERIFY(file.open(QIODevice::ReadOnly)); QCOMPARE(file.readAll(), QByteArray("original"));
    }
    void spacePreviewsViewButDoesNotTakeTextInput()
    {
        int previews = 0;
        MonetFilesExperience filter(this, [&] { ++previews; });
        DolphinView view;
        QVBoxLayout layout(&view);
        QWidget viewport; viewport.setFocusPolicy(Qt::StrongFocus); layout.addWidget(&viewport);
        QLineEdit rename; layout.addWidget(&rename);
        view.show(); view.activateWindow(); viewport.setFocus(); QTest::qWait(50);
        QTest::keyClick(&viewport, Qt::Key_Space);
        QCOMPARE(previews, 1);
        QTest::keyClick(&viewport, Qt::Key_Space, Qt::ControlModifier);
        QCOMPARE(previews, 1);
        rename.setFocus(); QTest::qWait(10); QTest::keyClick(&rename, Qt::Key_Space);
        QCOMPARE(previews, 1); QCOMPARE(rename.text(), QStringLiteral(" "));
    }

    void tabCloseAcceptsPaddingAndRetainsNativeButton()
    {
        MonetFilesExperience filter(this, [] {});
        QTabBar bar; bar.setTabsClosable(true);
        bar.resize(qMin(600, QGuiApplication::primaryScreen()->availableGeometry().width() - 40), 64);
        bar.addTab(QStringLiteral("Downloads")); bar.addTab(QStringLiteral("Monet"));
        bar.show(); QTest::qWait(40);
        QSignalSpy closed(&bar, &QTabBar::tabCloseRequested);
        for (auto direction : {Qt::LeftToRight, Qt::RightToLeft}) {
            bar.setLayoutDirection(direction); bar.moveTab(0, 1); QTest::qWait(20);
            for (int index = 0; index < bar.count(); ++index) {
                auto button = qobject_cast<QAbstractButton *>(bar.tabButton(index, QTabBar::RightSide));
                if (!button) button = qobject_cast<QAbstractButton *>(bar.tabButton(index, QTabBar::LeftSide));
                QVERIFY(button); const auto geometry = button->geometry();
                const QPoint point(geometry.left() - 5, geometry.center().y());
                QVERIFY(bar.tabRect(index).contains(point)); QVERIFY(!geometry.contains(point));
                QTest::mouseMove(&bar, point); QTest::qWait(20);
                QVERIFY(button->underMouse());
                QTest::mousePress(&bar, Qt::LeftButton, {}, point); QVERIFY(button->isDown());
                QTest::mouseRelease(&bar, Qt::LeftButton, {}, point);
                QCOMPARE(closed.takeFirst().at(0).toInt(), index);
                QCOMPARE(button->geometry(), geometry); // icon and painted target did not grow
            }
        }
    }

    void tabCloseDragAwayCancelsAndTabBodyStillSelects()
    {
        MonetFilesExperience filter(this, [] {});
        QTabBar bar; bar.setTabsClosable(true);
        bar.resize(qMin(600, QGuiApplication::primaryScreen()->availableGeometry().width() - 40), 64);
        bar.addTab(QStringLiteral("Downloads")); bar.addTab(QStringLiteral("Monet"));
        bar.show(); QTest::qWait(40);
        auto button = qobject_cast<QAbstractButton *>(bar.tabButton(1, QTabBar::RightSide));
        QVERIFY(button); QSignalSpy closed(&bar, &QTabBar::tabCloseRequested);
        const QPoint point(button->x() - 5, button->geometry().center().y());
        QTest::mousePress(&bar, Qt::LeftButton, {}, point); QVERIFY(button->isDown());
        QTest::mouseMove(&bar, bar.tabRect(0).center());
        QTest::mouseRelease(&bar, Qt::LeftButton, {}, bar.tabRect(0).center());
        QVERIFY(!button->isDown()); QCOMPARE(closed.count(), 0);
        QTest::mouseClick(&bar, Qt::LeftButton, {}, bar.tabRect(1).center());
        QCOMPARE(bar.currentIndex(), 1); QCOMPARE(closed.count(), 0);
    }
};
QTEST_MAIN(ExperienceTest)
#include "experience-test.moc"
