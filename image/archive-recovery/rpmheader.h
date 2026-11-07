// SPDX-License-Identifier: GPL-3.0-or-later
// Read RPM's file index without decompressing its cpio payload. Query only:
// no package install, scriptlets, database changes or shell interpretation.
#pragma once
#include <QElapsedTimer>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QProcess>
#include <QThread>
#include <optional>

namespace MonetRpm {
struct Entry {
    QString path, owner, group, link;
    qint64 size, time;
    int mode;
};

inline std::optional<QList<Entry>> read(const QString &filename)
{
    QFile file(filename);
    if (!file.open(QIODevice::ReadOnly) || file.read(4) != QByteArray::fromHex("edabeedb")) return std::nullopt;
    file.close();
    QProcess process;
    // JSON-escape strings: filenames can contain spaces, quotes and newlines.
    const QString format = QStringLiteral("[%{FILENAMES:json},%{LONGFILESIZES},%{FILEMODES},%{FILEMTIMES},"
                                           "%{FILEUSERNAME:json},%{FILEGROUPNAME:json},%{FILELINKTOS:json},%{FILEFLAGS}\\n]");
    process.start(QStringLiteral("/usr/bin/rpm"),
        {QStringLiteral("-qp"), QStringLiteral("--nosignature"), QStringLiteral("--nodigest"),
         QStringLiteral("--qf"), format, QStringLiteral("--"), filename});
    if (!process.waitForStarted(1000)) return std::nullopt;
    QByteArray output;
    QElapsedTimer timer; timer.start();
    do {
        process.waitForFinished(25);
        output += process.readAllStandardOutput();
        process.readAllStandardError();
        if (QThread::currentThread()->isInterruptionRequested() || timer.elapsed() > 10000 || output.size() > 32 * 1024 * 1024) {
            process.kill(); process.waitForFinished(1000);
            return std::nullopt;
        }
    } while (process.state() != QProcess::NotRunning);
    if (process.exitStatus() != QProcess::NormalExit || process.exitCode() != 0) return std::nullopt;

    QList<Entry> entries;
    for (const auto &line : output.split('\n')) {
        if (QThread::currentThread()->isInterruptionRequested()) return std::nullopt;
        if (line.isEmpty()) continue;
        QJsonParseError error;
        const auto document = QJsonDocument::fromJson('[' + line + ']', &error);
        const auto fields = document.array();
        if (error.error != QJsonParseError::NoError || fields.size() != 8 || entries.size() >= 100000) return std::nullopt;
        for (int index : {0, 4, 5, 6})
            if (!fields[index].isString() || fields[index].toString().contains(QChar::Null)) return std::nullopt;
        for (int index : {1, 2, 3, 7})
            if (!fields[index].isDouble() || fields[index].toInteger(-1) < 0) return std::nullopt;
        const auto path = fields[0].toString();
        if (!path.startsWith(QLatin1Char('/')) || fields[2].toInteger() > 65535) return std::nullopt;
        // Ghost entries have no file in the payload and must not appear as
        // extractable archive members (RPMFILE_GHOST == 1 << 6).
        if (fields[7].toInteger() & 64) continue;
        entries.append({QLatin1Char('.') + path, fields[4].toString(), fields[5].toString(), fields[6].toString(),
                        fields[1].toInteger(), fields[3].toInteger(), int(fields[2].toInteger())});
    }
    return entries;
}
}
