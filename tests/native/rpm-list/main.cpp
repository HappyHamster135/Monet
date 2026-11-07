// SPDX-License-Identifier: GPL-3.0-or-later
// Probe the actual installed/candidate Ark plugin; no package installation.
#include <QCoreApplication>
#include <QElapsedTimer>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QThread>
#include <KPluginFactory>
#include <KPluginMetaData>
#include "archiveinterface.h"
#include "archiveentry.h"
#include "options.h"
int main(int argc, char **argv)
{
    QCoreApplication app(argc,argv);
    if (argc != 4 && argc != 5 && argc != 6) return 2;
    const KPluginMetaData metadata(QString::fromLocal8Bit(argv[1]));
    const auto plugin = KPluginFactory::instantiatePlugin<Kerfuffle::ReadOnlyArchiveInterface>(metadata, nullptr,
        {QString::fromLocal8Bit(argv[2]), QVariant::fromValue(metadata)});
    if (!plugin.plugin) return 3;
    auto interface = plugin.plugin;
    QJsonArray entries;
    QList<Kerfuffle::Archive::Entry *> selected;
    bool error = false;
    QObject::connect(interface, &Kerfuffle::ReadOnlyArchiveInterface::error, &app, [&] { error=true; });
    QObject::connect(interface, &Kerfuffle::ReadOnlyArchiveInterface::entry, &app, [&](auto item) {
        QJsonObject row;
        for (const auto name : {"fullPath","size","permissions","owner","group","link","isDirectory","isExecutable"})
            row.insert(QLatin1String(name), QJsonValue::fromVariant(item->property(name)));
        entries.append(row);
        if (argc==6 && item->property("fullPath").toString()==QString::fromLocal8Bit(argv[4])) selected.append(item);
    });
    QElapsedTimer timer; timer.start();
    bool ok = false;
    if (argc==5) {
        if (QString::fromLocal8Bit(argv[4])!=QStringLiteral("cancel")) return 2;
        auto thread = QThread::create([&] {
            QThread::currentThread()->requestInterruption();
            ok = interface->list();
            interface->moveToThread(app.thread());
        });
        interface->moveToThread(thread);
        thread->start(); thread->wait(); delete thread;
    } else ok = interface->list();
    const auto elapsed = timer.elapsed();
    QJsonObject report{{"ok",ok},{"error",error},{"milliseconds",elapsed},{"entries",entries},{"count",entries.size()}};
    if (argc==6) {
        if (selected.size()!=1) return 5;
        // ArchiveModel strips the cpio ./ prefix before passing selections to
        // the native extraction backend. Reproduce that model boundary here.
        for (auto item : selected) {
            auto path = item->property("fullPath").toString();
            if (path.startsWith(QStringLiteral("./"))) item->setFullPath(path.mid(2));
        }
        Kerfuffle::ExtractionOptions options;
        report.insert(QStringLiteral("extracted"), interface->extractFiles(selected, QString::fromLocal8Bit(argv[5]), options));
    }
    QFile file(QString::fromLocal8Bit(argv[3]));
    if (!file.open(QIODevice::WriteOnly)) return 4;
    file.write(QJsonDocument(report).toJson());
    delete interface;
    return ok && !error ? 0 : 1;
}
