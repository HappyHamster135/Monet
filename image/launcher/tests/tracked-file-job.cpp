// SPDX-License-Identifier: GPL-3.0-or-later
// Native operation and its standard progress tracker, disposable test session only.
#include <KIO/CopyJob>
#include <KIO/FileCopyJob>
#include <KUiServerV2JobTracker>
#include <QGuiApplication>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTextStream>
#include <QTimer>
#include <QUrl>
int main(int argc, char **argv)
{
    QGuiApplication app(argc, argv); app.setDesktopFileName(QStringLiteral("monet-transfer-operation-fixture"));
    QCoreApplication::setQuitLockEnabled(false); app.setQuitOnLastWindowClosed(false);
    if (argc != 4 || !qEnvironmentVariable("HOME").startsWith(QStringLiteral("/tmp/monet-tests-"))) return 2;
    const auto source = QUrl::fromUserInput(QString::fromLocal8Bit(argv[2]));
    const auto destination = QUrl::fromUserInput(QString::fromLocal8Bit(argv[3]));
    KUiServerV2JobTracker tracker;
    KJob *job;
    if (QByteArray(argv[1]) == "copy") job = KIO::copy(source, destination, KIO::HideProgressInfo);
    else if (QByteArray(argv[1]) == "download") job = KIO::file_copy(source, destination, -1, KIO::HideProgressInfo);
    else return 2;
    job->setProperty("immediateProgressReporting", true);
    tracker.registerJob(job);
    int result = 1;
    QObject::connect(job, &KJob::result, &app, [&app, &result](KJob *finished) {
        result = finished->error() ? 1 : 0;
        QTextStream(stdout) << QJsonDocument(QJsonObject{{"error", finished->error()}, {"message", finished->errorText()}}).toJson(QJsonDocument::Compact) << Qt::endl;
        // Flush the tracker's asynchronous final JobView update/termination too.
        if (!qEnvironmentVariableIsSet("MONET_TRACKED_JOB_HOLD")) QTimer::singleShot(200, &app, &QCoreApplication::quit);
    });
    QTimer::singleShot(30000, &app, &QCoreApplication::quit);
    app.exec(); return result;
}
