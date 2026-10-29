// SPDX-License-Identifier: GPL-2.0-or-later
#include "shell.h"
#include "core/annotations.h"
#include "core/document.h"
#include "core/page.h"
#include <KAboutData>
#include <KLocalizedString>
#include <QApplication>
#include <QClipboard>
#include <QDialog>
#include <QElapsedTimer>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMimeData>
#include <QMimeDatabase>
#include <QPainter>
#include <QPdfWriter>
#include <QProcess>
#include <QPushButton>
#include <QStandardPaths>
#include <QTemporaryDir>
#include <QTest>
#include <QTimer>
#include <QUuid>
#include <functional>
#include <memory>

class MainShellTest : public QObject
{
    Q_OBJECT
    QJsonObject request(QProcess &process, const QJsonObject &command)
    {
        process.write(QJsonDocument(command).toJson(QJsonDocument::Compact) + '\n');
        QElapsedTimer time;
        time.start();
        while (!process.canReadLine() && time.elapsed() < 8000) QTest::qWait(10);
        const auto response = QJsonDocument::fromJson(process.readLine()).object();
        if (response.contains(QStringLiteral("error")) || response[QStringLiteral("result")] == QJsonValue(false)) qWarning() << response << process.readAllStandardError();
        return response;
    }

    bool arm(QProcess &process, const QString &token, bool armed = true)
    {
        return request(process, {{QStringLiteral("pid"), QCoreApplication::applicationPid()},
            {QStringLiteral("id"), token}, {QStringLiteral("armed"), armed}})[QStringLiteral("result")].toBool();
    }

    QString receiptPath(const QString &token, const QString &window)
    {
        return QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) + QStringLiteral("/monet-pdf/")
            + token + QLatin1Char('-') + QString::number(QCoreApplication::applicationPid()) + QLatin1Char('-')
            + QUuid(window).toString(QUuid::WithoutBraces) + QStringLiteral(".json");
    }

    bool annotate(KParts::ReadWritePart *part, const QString &text)
    {
        Okular::TextAnnotation annotation;
        annotation.setContents(text);
        annotation.setBoundingRectangle(Okular::NormalizedRect(0.2, 0.2, 0.3, 0.3));
        QDomDocument xml;
        auto root = xml.createElement(QStringLiteral("annotations"));
        root.setAttribute(QStringLiteral("version"), 1);
        xml.appendChild(root);
        auto element = xml.createElement(QStringLiteral("annotation"));
        Okular::AnnotationUtils::storeAnnotation(&annotation, element, xml);
        root.appendChild(element);
        auto mime = new QMimeData;
        mime->setData(QStringLiteral("application/x-okular-annotation+xml"), xml.toByteArray());
        QApplication::clipboard()->setMimeData(mime);
        return QMetaObject::invokeMethod(part, "slotPasteAnnotation") && part->isModified();
    }

    QStringList savedAnnotations(const QString &path)
    {
        Okular::Document document(nullptr);
        if (document.openDocument(path, QUrl::fromLocalFile(path), QMimeDatabase().mimeTypeForFile(path)) != Okular::Document::OpenSuccess) return {};
        QStringList texts;
        for (uint i = 0; i < document.pages(); ++i) {
            for (auto annotation : document.page(i)->annotations()) texts.append(annotation->contents());
        }
        return texts;
    }

    QPair<bool, bool> closeWith(Shell *window, const QString &choice, const std::function<void()> &duringPrompt = {})
    {
        bool answered = false;
        QElapsedTimer deadline;
        deadline.start();
        QTimer timer;
        connect(&timer, &QTimer::timeout, this, [&] {
            const auto dialog = qobject_cast<QDialog *>(QApplication::activeModalWidget());
            if (!dialog) return;
            if (deadline.elapsed() > 15000) { dialog->reject(); return; }
            for (auto button : dialog->findChildren<QPushButton *>()) {
                const auto text = button->text().remove(QLatin1Char('&'));
                if (text == QStringLiteral("Close Tabs")) { button->click(); return; }
                if (text == choice) {
                    timer.stop();
                    if (duringPrompt) duringPrompt();
                    answered = true;
                    button->click();
                    return;
                }
            }
        });
        timer.start(20);
        const bool closed = window->close();
        timer.stop();
        return {closed, answered};
    }

private Q_SLOTS:
    void protectedDeparture()
    {
        QTemporaryDir folder;
        QVERIFY(folder.isValid());
        const auto first = folder.filePath(QStringLiteral("Original å.pdf"));
        const auto second = folder.filePath(QStringLiteral("Active.pdf"));
        const auto third = folder.filePath(QStringLiteral("Survivor.pdf"));
        for (const auto &path : {first, second, third}) {
            QPdfWriter writer(path);
            QPainter painter(&writer);
            painter.drawText(100, 100, QStringLiteral("Synthetic annotation test"));
        }
        auto one = std::make_unique<Shell>();
        auto two = std::make_unique<Shell>();
        for (auto window : {one.get(), two.get()}) {
            window->setAttribute(Qt::WA_DeleteOnClose, false);
            window->show();
        }
        QVERIFY(one->openDocument(QUrl::fromLocalFile(first), QString()));
        QVERIFY(one->openDocument(QUrl::fromLocalFile(second), QString()));
        QVERIFY(two->openDocument(QUrl::fromLocalFile(third), QString()));
        one->setActiveTab(1);
        QJsonArray windows;
        QTRY_COMPARE_WITH_TIMEOUT((windows = QJsonDocument::fromJson(one->monetDocumentWindows().toUtf8()).array()).size(), 2, 10000);
        QString firstId, secondId;
        for (const auto &value : windows) {
            const auto item = value.toObject();
            if (item[QStringLiteral("document")].toObject()[QStringLiteral("tabs")].toArray().size() == 2) firstId = item[QStringLiteral("id")].toString();
            else secondId = item[QStringLiteral("id")].toString();
        }
        QVERIFY(!firstId.isEmpty() && !secondId.isEmpty());
        QProcess controller;
        controller.start(QStringLiteral("python3"), {qEnvironmentVariable("MONET_PDF_CONTROLLER")});
        QVERIFY(controller.waitForStarted());
        const QString token(32, QLatin1Char('a'));
        QVERIFY(arm(controller, token));
        auto added = std::make_unique<Shell>();
        added->setAttribute(Qt::WA_DeleteOnClose, false);
        added->show();
        QTRY_COMPARE(QJsonDocument::fromJson(one->monetDocumentWindows().toUtf8()).array().size(), 3);
        QVERIFY(!added->close());
        QVERIFY(arm(controller, token));
        QVERIFY(added->close());
        added.reset();
        auto part = one->m_tabs[0].part;
        QVERIFY(annotate(part, QStringLiteral("Saved annotation")));
        QCOMPARE(closeWith(one.get(), QStringLiteral("Cancel")), qMakePair(false, true));
        QVERIFY(one->isVisible() && part->isModified());
        QVERIFY(!QFile::exists(receiptPath(token, firstId)));
        const auto renamed = folder.filePath(QStringLiteral("Renamed å.pdf"));
        QVERIFY(part->saveAs(QUrl::fromLocalFile(renamed)));
        QVERIFY(savedAnnotations(renamed).contains(QStringLiteral("Saved annotation")));
        QVERIFY(savedAnnotations(first).isEmpty());
        QVERIFY(annotate(part, QStringLiteral("Saved during close")));
        auto survivor = two->m_tabs[0].part;
        QVERIFY(annotate(survivor, QStringLiteral("Surviving unsaved annotation")));
        one->setActiveTab(1);
        const auto before = two->monetDocumentState();
        QCOMPARE(closeWith(one.get(), QStringLiteral("Save")), qMakePair(true, true));
        one.reset();
        const auto receipt = request(controller, {{QStringLiteral("pid"), QCoreApplication::applicationPid()},
            {QStringLiteral("id"), token}, {QStringLiteral("window"), firstId}})[QStringLiteral("result")].toObject();
        QVERIFY(receipt[QStringLiteral("supported")].toBool());
        const auto state = receipt[QStringLiteral("document")].toObject();
        QCOMPARE(state[QStringLiteral("active")].toInt(), 1);
        QCOMPARE(state[QStringLiteral("tabs")].toArray()[0].toObject()[QStringLiteral("path")].toString(), renamed);
        QVERIFY(savedAnnotations(renamed).contains(QStringLiteral("Saved during close")));
        QCOMPARE(two->monetDocumentState(), before);
        QVERIFY(survivor->isModified());

        bool cancelled = false;
        QCOMPARE(closeWith(two.get(), QStringLiteral("Save"), [&] { cancelled = arm(controller, token, false); }), qMakePair(false, true));
        QVERIFY(cancelled && two->isVisible());
        QVERIFY(!QFile::exists(receiptPath(token, secondId)));
        QVERIFY(savedAnnotations(third).contains(QStringLiteral("Surviving unsaved annotation")));

        const QString retryToken(32, QLatin1Char('b'));
        QVERIFY(arm(controller, retryToken));
        QVERIFY(annotate(survivor, QStringLiteral("Discarded annotation")));
        QCOMPARE(closeWith(two.get(), QStringLiteral("Discard")), qMakePair(true, true));
        const auto discarded = request(controller, {{QStringLiteral("pid"), QCoreApplication::applicationPid()},
            {QStringLiteral("id"), retryToken}, {QStringLiteral("window"), secondId}})[QStringLiteral("result")].toObject();
        QVERIFY(discarded[QStringLiteral("supported")].toBool());
        QVERIFY(!savedAnnotations(third).contains(QStringLiteral("Discarded annotation")));
        QVERIFY(arm(controller, retryToken, false));
        two.reset();

        auto last = std::make_unique<Shell>();
        last->setAttribute(Qt::WA_DeleteOnClose, false);
        last->show();
        QVERIFY(last->openDocument(QUrl::fromLocalFile(second), QString()));
        QTRY_COMPARE(QJsonDocument::fromJson(last->monetDocumentWindows().toUtf8()).array().size(), 1);
        const QString finalToken(32, QLatin1Char('c'));
        QVERIFY(arm(controller, finalToken));
        const auto directory = QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) + QStringLiteral("/monet-pdf");
        QVERIFY(QFile::setPermissions(directory, QFile::ReadOwner | QFile::ExeOwner));
        QVERIFY(!last->close());
        QVERIFY(last->isVisible());
        QVERIFY(QFile::setPermissions(directory, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner));
        QVERIFY(annotate(last->m_tabs[0].part, QStringLiteral("Saved after controller loss")));
        QCOMPARE(closeWith(last.get(), QStringLiteral("Save"), [&] {
            controller.terminate();
            QTRY_COMPARE(controller.state(), QProcess::NotRunning);
            QTest::qWait(100);
        }), qMakePair(false, true));
        QVERIFY(last->isVisible());
        QVERIFY(savedAnnotations(second).contains(QStringLiteral("Saved after controller loss")));
        QVERIFY(last->close());

        QFile proof(qEnvironmentVariable("MONET_PDF_DEPARTURE_EVIDENCE"));
        QVERIFY(proof.open(QIODevice::WriteOnly));
        proof.write(QJsonDocument(QJsonObject{{QStringLiteral("final_receipt"), receipt},
            {QStringLiteral("native_cancel"), true}, {QStringLiteral("annotation_save_as"), true},
            {QStringLiteral("native_save"), true}, {QStringLiteral("native_discard"), true},
            {QStringLiteral("original_preserved"), true}, {QStringLiteral("survivor_untouched"), true},
            {QStringLiteral("cancelled_switch_veto"), true}, {QStringLiteral("controller_loss_veto"), true},
            {QStringLiteral("new_window_watch"), true},
            {QStringLiteral("receipt_failure_veto"), true}}).toJson());
    }
};

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    app.setQuitOnLastWindowClosed(false);
    KAboutData::setApplicationData(KAboutData(QStringLiteral("okular"), QStringLiteral("PDF departure fixture"), QStringLiteral("1")));
    KLocalizedString::setApplicationDomain("okular");
    app.setDesktopFileName(QStringLiteral("org.kde.okular"));
    MainShellTest test;
    return QTest::qExec(&test, argc, argv);
}

#include "departure-test.moc"
