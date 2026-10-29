// SPDX-License-Identifier: GPL-3.0-or-later
#include <QAction>
#include <QLabel>
#include <QMenu>
#include <QMenuBar>
#include <QTemporaryDir>
#include <QTest>
#include <QToolBar>
#include <QToolButton>
#include "core/Config.h"
#include "crypto/Crypto.h"
#include "gui/Application.h"
#include "gui/MainWindow.h"

class TestMonetPasswords : public QObject
{
    Q_OBJECT
private slots:
    void defaultsAndActions()
    {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        Config::createConfigFromFile(directory.filePath("settings.ini"), directory.filePath("local.ini"));
        QVERIFY(Crypto::init());
        Application::bootstrap();
        QVERIFY(config()->get(Config::BackupBeforeSave).toBool());
        QVERIFY(config()->get(Config::AutoSaveAfterEveryChange).toBool());
        QVERIFY(config()->get(Config::Security_LockDatabaseScreenLock).toBool());
        QVERIFY(config()->get(Config::Security_ClearClipboard).toBool());
        QVERIFY(!config()->get(Config::Security_QuickUnlock).toBool());
        QCOMPARE(config()->get(Config::Security_LockDatabaseIdleSeconds).toInt(), 300);
        MainWindow window;
        window.show();
        auto* toolbar = window.findChild<QToolBar*>("toolBar");
        auto* more = window.findChild<QToolButton*>("monetPasswordsMore");
        QVERIFY(toolbar);
        QVERIFY(more && more->menu());
        QCOMPARE(window.menuBar()->maximumHeight(), 0);
        QVERIFY(window.findChild<QLabel*>("monetPasswordsPreview"));
        for (const auto* name : {"actionEntryNew", "actionEntryEdit", "actionEntryDelete",
                                "actionEntryCopyPassword", "actionLockDatabaseToolbar"}) {
            auto* action = window.findChild<QAction*>(name);
            QVERIFY(action);
            QVERIFY(toolbar->actions().contains(action));
            QVERIFY(!action->isEnabled()); // No unlocked vault: the facade cannot bypass the engine.
        }
        QCOMPARE(more->menu()->actions(), window.menuBar()->actions());
        QVERIFY(window.findChild<QAction*>("actionDatabaseSaveBackup"));
    }
};

int main(int argc, char** argv)
{
    Application app(argc, argv);
    app.setApplicationName("Monet Passwords test");
    TestMonetPasswords test;
    return QTest::qExec(&test, argc, argv);
}
#include "TestMonetPasswords.moc"
