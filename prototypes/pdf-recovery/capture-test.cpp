// SPDX-License-Identifier: GPL-2.0-or-later
#include "shell.h"
#include <KAboutData>
#include <KConfigGroup>
#include <KLocalizedString>
#include <KSharedConfig>
#include <QApplication>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPainter>
#include <QPdfWriter>
#include <QProcess>
#include <QSet>
#include <QTabBar>
#include <QTabWidget>
#include <QTemporaryDir>
#include <QTest>
#include <memory>

class MainShellTest : public QObject
{
    Q_OBJECT
private Q_SLOTS:
    void orderedDocumentsAndWindows()
    {
        QTemporaryDir folder;
        QVERIFY(folder.isValid());
        const auto first = folder.filePath(QStringLiteral("Water lilies % å.pdf"));
        const auto second = folder.filePath(QStringLiteral("Second.pdf"));
        for (const auto &path : {first, second}) {
            QPdfWriter writer(path);
            QPainter paint(&writer);
            for (int page = 1; page <= 4; ++page) {
                if (page > 1) QVERIFY(writer.newPage());
                paint.drawText(100, 100, QStringLiteral("Synthetic PDF page %1").arg(page));
            }
        }
        auto one = std::make_unique<Shell>();
        auto two = std::make_unique<Shell>();
        auto empty = std::make_unique<Shell>();
        QVERIFY(one->isValid() && two->isValid() && empty->isValid());
        for (auto window : {one.get(), two.get(), empty.get()}) window->show();
        QVERIFY(one->openDocument(QUrl::fromLocalFile(first), QString()));
        QVERIFY(one->openDocument(QUrl::fromLocalFile(second), QString()));
        QVERIFY(two->openDocument(QUrl::fromLocalFile(first), QString()));
        QCOMPARE(one->m_tabs.size(), 2);
        QCOMPARE(two->m_tabs.size(), 1);
        auto firstPart = one->m_tabs[0].part;
        auto secondPart = one->m_tabs[1].part;
        QVERIFY(QMetaObject::invokeMethod(firstPart, "goToPage", Q_ARG(uint, 3)));
        QVERIFY(QMetaObject::invokeMethod(secondPart, "goToPage", Q_ARG(uint, 2)));
        QVERIFY(QMetaObject::invokeMethod(two->m_tabs[0].part, "goToPage", Q_ARG(uint, 4)));
        one->m_tabWidget->tabBar()->moveTab(0, 1);
        one->setActiveTab(0);
        one->resize(1100, 760);
        two->resize(1050, 720);
        QTest::qWait(500);
        const auto before = one->geometry();
        const auto focus = QApplication::focusWidget();
        auto state = QJsonDocument::fromJson(one->monetDocumentState().toUtf8()).object();
        QCOMPARE(state[QStringLiteral("active")].toInt(), 0);
        auto tabs = state[QStringLiteral("tabs")].toArray();
        QCOMPARE(tabs.size(), 2);
        QCOMPARE(tabs[0].toObject()[QStringLiteral("path")].toString(), second);
        QCOMPARE(tabs[0].toObject()[QStringLiteral("page")].toInt(), 2);
        QCOMPARE(tabs[1].toObject()[QStringLiteral("path")].toString(), first);
        QCOMPARE(tabs[1].toObject()[QStringLiteral("page")].toInt(), 3);
        QCOMPARE(QJsonDocument::fromJson(two->monetDocumentState().toUtf8()).object()[QStringLiteral("tabs")].toArray()[0].toObject()[QStringLiteral("page")].toInt(), 4);
        QCOMPARE(QJsonDocument::fromJson(empty->monetDocumentState().toUtf8()).object()[QStringLiteral("active")].toInt(), -1);
        QCOMPARE(one->geometry(), before);
        QCOMPARE(QApplication::focusWidget(), focus);

        const auto renamed = folder.filePath(QStringLiteral("Saved as.pdf"));
        QVERIFY(secondPart->saveAs(QUrl::fromLocalFile(renamed)));
        QTRY_COMPARE(QJsonDocument::fromJson(one->monetDocumentState().toUtf8()).object()[QStringLiteral("tabs")].toArray()[0].toObject()[QStringLiteral("path")].toString(), renamed);
        QVERIFY(QFile::exists(second));
        QVERIFY(QFile::exists(renamed));
        secondPart->setModified(true);
        QVERIFY(QJsonDocument::fromJson(one->monetDocumentState().toUtf8()).object()[QStringLiteral("tabs")].toArray()[0].toObject()[QStringLiteral("modified")].toBool());
        secondPart->setModified(false);

        QJsonArray windows;
        QTRY_VERIFY_WITH_TIMEOUT((windows = QJsonDocument::fromJson(one->monetDocumentWindows().toUtf8()).array()).size() == 3, 10000);
        QSet<QString> ids;
        for (const auto &item : windows) ids.insert(item.toObject()[QStringLiteral("id")].toString());
        QCOMPARE(ids.size(), 3);
        QVERIFY(!ids.contains(QString()));
        QCOMPARE(one->geometry(), before);
        QCOMPARE(one->m_tabWidget->currentIndex(), 0);

        const auto helper = qEnvironmentVariable("MONET_PDF_HELPER");
        QVERIFY(!helper.isEmpty());
        auto capture = [&](const QString &mode) {
            auto process = new QProcess(this);
            process->start(QStringLiteral("python3"), {helper, mode, QString::number(QCoreApplication::applicationPid())});
            return process;
        };
        auto all = capture(QStringLiteral("windows"));
        QTRY_COMPARE_WITH_TIMEOUT(all->state(), QProcess::NotRunning, 10000);
        QCOMPARE(all->exitCode(), 0);
        QCOMPARE(QJsonDocument::fromJson(all->readAllStandardOutput()).array().size(), 3);
        auto ambiguous = capture(QStringLiteral("capture"));
        QTRY_COMPARE_WITH_TIMEOUT(ambiguous->state(), QProcess::NotRunning, 10000);
        QCOMPARE(ambiguous->readAllStandardOutput().trimmed(), QByteArray("null"));

        auto pluginRequest = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin"), QStringLiteral("/Plugins"),
                             QStringLiteral("org.kde.KWin.Plugins"), QStringLiteral("UnloadPlugin"));
        pluginRequest.setArguments({QStringLiteral("monet_window_identity")});
        QCOMPARE(QDBusConnection::sessionBus().call(pluginRequest, QDBus::Block, 1000).type(), QDBusMessage::ReplyMessage);
        QCOMPARE(one->monetDocumentWindows(), QStringLiteral("null"));
        pluginRequest = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin"), QStringLiteral("/Plugins"),
                        QStringLiteral("org.kde.KWin.Plugins"), QStringLiteral("LoadPlugin"));
        pluginRequest.setArguments({QStringLiteral("monet_window_identity")});
        const auto loaded = QDBusConnection::sessionBus().call(pluginRequest, QDBus::Block, 1000);
        QVERIFY(loaded.type() == QDBusMessage::ReplyMessage && loaded.arguments().size() == 1 && loaded.arguments()[0].toBool());
        QTRY_COMPARE(QJsonDocument::fromJson(one->monetDocumentWindows().toUtf8()).array().size(), 3);

        one.reset();
        empty.reset();
        auto survivor = capture(QStringLiteral("capture"));
        QTRY_COMPARE_WITH_TIMEOUT(survivor->state(), QProcess::NotRunning, 10000);
        auto last = QJsonDocument::fromJson(survivor->readAllStandardOutput()).object();
        QCOMPARE(last[QStringLiteral("tabs")].toArray().size(), 1);
        QCOMPARE(last[QStringLiteral("tabs")].toArray()[0].toObject()[QStringLiteral("path")].toString(), first);
        QCOMPARE(last[QStringLiteral("tabs")].toArray()[0].toObject()[QStringLiteral("page")].toInt(), 4);

        QFile proof(qEnvironmentVariable("MONET_PDF_EVIDENCE"));
        QVERIFY(proof.open(QIODevice::WriteOnly));
        proof.write(QJsonDocument(QJsonObject{{QStringLiteral("windows"), windows}, {QStringLiteral("survivor"), last},
                    {QStringLiteral("reordered_tabs"), true}, {QStringLiteral("save_as"), true}, {QStringLiteral("original_preserved"), true},
                    {QStringLiteral("read_only_capture"), true}, {QStringLiteral("same_file_independent_pages"), true},
                    {QStringLiteral("ambiguous_single_refused"), true}, {QStringLiteral("missing_identity_refused"), true},
                    {QStringLiteral("first_window_closed"), true}}).toJson());
    }
};

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    app.setQuitOnLastWindowClosed(false);
    KAboutData::setApplicationData(KAboutData(QStringLiteral("okular"), QStringLiteral("PDF capture fixture"), QStringLiteral("1")));
    KLocalizedString::setApplicationDomain("okular");
    app.setDesktopFileName(QStringLiteral("org.kde.okular"));
    MainShellTest test;
    return QTest::qExec(&test, argc, argv);
}

#include "capture-test.moc"
