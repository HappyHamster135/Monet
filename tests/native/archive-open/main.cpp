// SPDX-License-Identifier: GPL-3.0-or-later
// Drive the same MIME and service-action machinery used by Files.
#include <QApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMenu>
#include <QTimer>
#include <QFile>
#include <KApplicationTrader>
#include <KFileItem>
#include <KFileItemActions>
#include <KFileItemListProperties>
#include <KIO/OpenUrlJob>
#include <KIO/JobUiDelegateFactory>
#include <KAuthorized>
#include <KDesktopFile>
#include <QStandardPaths>

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    app.setQuitOnLastWindowClosed(false);
    if (argc != 4) return 2;
    const QString mode = QString::fromLocal8Bit(argv[1]);
    const QUrl url = QUrl::fromLocalFile(QString::fromLocal8Bit(argv[2]));
    KFileItemList items{KFileItem(url, QStringLiteral("application/zip"), 0)};
    KFileItemActions actions;
    actions.setItemListProperties(KFileItemListProperties(items));
    QMenu menu;
    actions.addActionsTo(&menu, KFileItemActions::MenuActionSource::Services);
    QJsonArray labels;
    QAction *open = nullptr;
    bool extract = false;
    for (auto action : menu.actions()) {
        labels.append(action->text());
        if (action->text() == QStringLiteral("Open")) open = action;
        if (action->text() == QStringLiteral("Extract archive…")) extract = true;
    }
    auto preferred = KApplicationTrader::preferredService(QStringLiteral("application/zip"));
    QJsonObject result{{"top_level_labels", labels}, {"open", bool(open)}, {"extract", extract},
                       {"preferred", preferred ? preferred->desktopEntryName() : QString()},
                       {"preferred_exec", preferred ? preferred->exec() : QString()}};
    const auto menuPath = QStandardPaths::locate(QStandardPaths::GenericDataLocation,
        QStringLiteral("kio/servicemenus/monet-archive-open.desktop"));
    result.insert("preferred_path", preferred ? preferred->entryPath() : QString());
    result.insert("preferred_authorized", preferred && KDesktopFile::isAuthorizedDesktopFile(preferred->entryPath()));
    result.insert("menu_path", menuPath);
    result.insert("menu_authorized", KDesktopFile::isAuthorizedDesktopFile(menuPath));
    result.insert("desktop_launch_allowed", KAuthorized::authorize(QStringLiteral("run_desktop_files")));
    QFile report(QString::fromLocal8Bit(argv[3]));
    if (!report.open(QIODevice::WriteOnly)) return 3;
    report.write(QJsonDocument(result).toJson());
    report.close();
    if (mode == QStringLiteral("query")) return 0;
    if (!open || !extract || !preferred || preferred->desktopEntryName() != QStringLiteral("monet-archive")) return 4;
    QObject::connect(&actions, &KFileItemActions::error, &app, [](const QString &) { QCoreApplication::exit(5); });
    QTimer::singleShot(0, &app, [&] {
        if (mode == QStringLiteral("context")) open->trigger();
        else {
            // A single activated file in Dolphin uses OpenUrlJob. Multi-file
            // runPreferredApplications does not cover this route.
            auto job = new KIO::OpenUrlJob(url, QStringLiteral("application/zip"));
            job->setUiDelegate(KIO::createDefaultJobUiDelegate(KJobUiDelegate::AutoWarningHandlingEnabled, nullptr));
            job->setShowOpenOrExecuteDialog(true);
            QObject::connect(job, &KIO::OpenUrlJob::finished, &app, [&app, job] { app.exit(job->error() ? 5 : 0); });
            job->start();
        }
    });
    QTimer::singleShot(30000, &app, [] { QCoreApplication::exit(6); });
    return app.exec();
}
