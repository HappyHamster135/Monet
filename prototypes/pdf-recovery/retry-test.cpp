// SPDX-License-Identifier: GPL-2.0-or-later
#include "shell.h"
#include <KAboutData>
#include <KLocalizedString>
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
#include <QTemporaryDir>
#include <QTabWidget>
#include <QTest>
#include <QUuid>
#include <qscopeguard.h>
#include <memory>

class MainShellTest : public QObject
{
    Q_OBJECT
    QJsonObject state(Shell *window) { return QJsonDocument::fromJson(window->monetDocumentState().toUtf8()).object(); }
    QString call(Shell *window, const QJsonObject &request) { return window->monetAppendDocument(QString::fromUtf8(QJsonDocument(request).toJson(QJsonDocument::Compact))); }
private Q_SLOTS:
    void lateFileAndLostReplies()
    {
        QTemporaryDir folder;
        QVERIFY(folder.isValid());
        const auto first = folder.filePath(QStringLiteral("Existing.pdf"));
        const auto missing = folder.filePath(QStringLiteral("Late å %.pdf"));
        const auto siblingFile = folder.filePath(QStringLiteral("Sibling.pdf"));
        {
            QPdfWriter writer(first);
            QPainter paint(&writer);
            for (int page = 1; page <= 4; ++page) {
                if (page > 1) QVERIFY(writer.newPage());
                paint.drawText(100, 100, QStringLiteral("Synthetic retry page %1").arg(page));
            }
        }
        QVERIFY(QFile::copy(first, siblingFile));
        auto one = std::make_unique<Shell>();
        auto two = std::make_unique<Shell>();
        const auto cleanup = qScopeGuard([&] {
            for (auto window : {one.get(), two.get()}) {
                if (window) for (const auto &tab : window->m_tabs) tab.part->setModified(false);
            }
        });
        QVERIFY(one->isValid() && two->isValid());
        for (auto window : {one.get(), two.get()}) {
            window->show();
            QVERIFY(window->openDocument(QUrl::fromLocalFile(window == one.get() ? first : siblingFile), QString()));
        }
        QJsonArray windows;
        QTRY_VERIFY_WITH_TIMEOUT((windows = QJsonDocument::fromJson(one->monetDocumentWindows().toUtf8()).array()).size() == 2, 10000);
        const auto oneId = [&] {
            for (const auto &value : QJsonDocument::fromJson(one->monetDocumentWindows().toUtf8()).array()) {
                if (value.toObject()[QStringLiteral("document")].toObject()[QStringLiteral("tabs")].toArray()[0].toObject()[QStringLiteral("path")] == first)
                    return value.toObject()[QStringLiteral("id")].toString();
            }
            return QString();
        }();
        QVERIFY(!oneId.isEmpty());
        QVERIFY(QMetaObject::invokeMethod(one->m_tabs[0].part, "goToPage", Q_ARG(uint, 3)));
        QTRY_COMPARE(state(one.get())[QStringLiteral("tabs")].toArray()[0].toObject()[QStringLiteral("page")].toInt(), 3);
        const auto sibling = state(two.get());
        const auto frame = one->geometry();
        auto originalPart = one->m_tabs[0].part;
        originalPart->setModified(true);
        const auto before = state(one.get());
        const QJsonObject tab{{QStringLiteral("path"), missing}, {QStringLiteral("page"), 4}, {QStringLiteral("modified"), false}};
        QJsonObject request{{QStringLiteral("window"), oneId}, {QStringLiteral("attempt"), QUuid::createUuid().toString(QUuid::Id128)},
                            {QStringLiteral("before"), before}, {QStringLiteral("tab"), tab}};
        QCOMPARE(call(two.get(), request), QStringLiteral("unavailable"));
        QCOMPARE(state(one.get()), before);
        QVERIFY(QFile::copy(first, missing));
        auto plugin = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin"), QStringLiteral("/Plugins"),
            QStringLiteral("org.kde.KWin.Plugins"), QStringLiteral("UnloadPlugin"));
        plugin.setArguments({QStringLiteral("monet_window_identity")});
        const auto unloaded = QDBusConnection::sessionBus().call(plugin, QDBus::Block, 1000);
        QCOMPARE(unloaded.type(), QDBusMessage::ReplyMessage);
        QCOMPARE(call(two.get(), request), QStringLiteral("unconfirmed"));
        QCOMPARE(state(one.get()), before);
        plugin = QDBusMessage::createMethodCall(QStringLiteral("org.kde.KWin"), QStringLiteral("/Plugins"),
            QStringLiteral("org.kde.KWin.Plugins"), QStringLiteral("LoadPlugin"));
        plugin.setArguments({QStringLiteral("monet_window_identity")});
        const auto loaded = QDBusConnection::sessionBus().call(plugin, QDBus::Block, 1000);
        QVERIFY(loaded.type() == QDBusMessage::ReplyMessage && loaded.arguments() == QVariantList{true});
        QCOMPARE(call(two.get(), request), QStringLiteral("opened"));
        QCOMPARE(one->m_tabs.size(), 2);
        QCOMPARE(one->m_tabs[0].part, originalPart);
        QVERIFY(originalPart->isModified());
        QCOMPARE(one->m_tabWidget->currentIndex(), 0);
        QCOMPARE(state(one.get())[QStringLiteral("tabs")].toArray()[1].toObject()[QStringLiteral("page")].toInt(), 4);
        QCOMPARE(one->geometry(), frame);
        QCOMPARE(state(two.get()), sibling);
        const auto opened = state(one.get());
        // The reply was lost. Reusing the same request must not append again.
        QCOMPARE(call(two.get(), request), QStringLiteral("opened"));
        QCOMPARE(state(one.get()), opened);
        auto conflict = request;
        conflict.insert(QStringLiteral("tab"), QJsonObject{{QStringLiteral("path"), first}, {QStringLiteral("page"), 2}, {QStringLiteral("modified"), false}});
        QCOMPARE(call(two.get(), conflict), QStringLiteral("conflict"));
        conflict.insert(QStringLiteral("attempt"), QUuid::createUuid().toString(QUuid::Id128));
        QCOMPARE(call(two.get(), conflict), QStringLiteral("conflict"));
        QCOMPARE(state(one.get()), opened);

        // A new request may append a duplicate path, even with ordinary duplicate collapsing enabled.
        conflict.insert(QStringLiteral("before"), opened);
        QCOMPARE(call(two.get(), conflict), QStringLiteral("opened"));
        QCOMPARE(one->m_tabs.size(), 3);
        QCOMPARE(state(one.get())[QStringLiteral("tabs")].toArray()[2].toObject()[QStringLiteral("page")].toInt(), 2);
        QCOMPARE(one->m_tabWidget->currentIndex(), 0);
        QVERIFY(originalPart->isModified());
        // Closing the recovered tab is a user decision, including after another controller starts.
        one->closeTab(1);
        QTest::qWait(50);
        QCOMPARE(one->m_tabs.size(), 2);
        QCOMPARE(call(two.get(), request), QStringLiteral("closed"));
        QCOMPARE(one->m_tabs.size(), 2);
        originalPart->setModified(false);
        one.reset();
        QCOMPARE(call(two.get(), conflict), QStringLiteral("closed"));
        QCOMPARE(state(two.get()), sibling);

        QFile proof(qEnvironmentVariable("MONET_PDF_RETRY_EVIDENCE"));
        QVERIFY(proof.open(QIODevice::WriteOnly));
        proof.write(QJsonDocument(QJsonObject{{QStringLiteral("exact_window"), true}, {QStringLiteral("late_file"), true},
            {QStringLiteral("lost_reply"), true}, {QStringLiteral("newer_modified_tab_preserved"), true},
            {QStringLiteral("page_selection_geometry_preserved"), true}, {QStringLiteral("duplicate_path"), true},
            {QStringLiteral("stale_request_refused"), true}, {QStringLiteral("closed_tab_not_replayed"), true},
            {QStringLiteral("missing_identity_not_closed"), true},
            {QStringLiteral("closed_window_not_redirected"), true}}).toJson());
    }
};

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    app.setQuitOnLastWindowClosed(false);
    KAboutData::setApplicationData(KAboutData(QStringLiteral("okular"), QStringLiteral("PDF retry fixture"), QStringLiteral("1")));
    KLocalizedString::setApplicationDomain("okular");
    app.setDesktopFileName(QStringLiteral("org.kde.okular"));
    MainShellTest test;
    return QTest::qExec(&test, argc, argv);
}
#include "retry-test.moc"
