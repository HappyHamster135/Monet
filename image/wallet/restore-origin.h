// Monet session restore. A record identifies a process lifetime, never just an app name.
#pragma once
#include <QDBusConnectionInterface>
#include <QDBusReply>
#include <QDir>
#include <QRegularExpression>
#include <QFile>
#include <QFileInfo>
#include <QSaveFile>
#include <QStandardPaths>
#include <unistd.h>

namespace MonetRestore {
struct Process {
    qint64 parent = 0;
    QByteArray start;
    QByteArray tty;
};

inline Process process(qint64 pid)
{
    QFile file(QStringLiteral("/proc/%1/stat").arg(pid));
    if (pid <= 1 || !file.open(QIODevice::ReadOnly))
        return {};
    const auto stat = file.readAll();
    // comm may itself contain spaces or parentheses. Fields 4 and 22 follow it.
    const auto fields = stat.mid(stat.lastIndexOf(')') + 2).split(' ');
    return fields.size() > 19 ? Process{fields[1].toLongLong(), fields[19], fields[4]} : Process{};
}

inline QDir records()
{
    return QDir(QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) + QStringLiteral("/monet/restored-processes"));
}

inline bool recorded(const QDir &dir, qint64 pid, const Process &p)
{
    QFile record(dir.filePath(QString::number(pid)));
    return !p.start.isEmpty() && record.open(QIODevice::ReadOnly) && record.read(32) == p.start;
}

inline void mark(qint64 pid)
{
    const auto p = process(pid);
    auto dir = records();
    if (p.start.isEmpty() || !dir.mkpath(QStringLiteral(".")))
        return;
    // Runtime records expire with the user session. Also prune exited instances
    // when launching so repeated sign-ins with a lingering user manager stay bounded.
    for (const auto &name : dir.entryList(QDir::Files)) {
        bool ok;
        const auto old = name.toLongLong(&ok);
        if (ok && !recorded(dir, old, process(old)))
            dir.remove(name);
    }
    QSaveFile out(dir.filePath(QString::number(pid)));
    if (out.open(QIODevice::WriteOnly) && out.write(p.start) == p.start.size())
        out.commit();
}

inline QByteArray group(qint64 pid)
{
    QFile file(QStringLiteral("/proc/%1/cgroup").arg(pid));
    if (!file.open(QIODevice::ReadOnly))
        return {};
    for (const auto &line : file.readAll().split('\n')) {
        if (line.startsWith("0::"))
            return line.mid(3);
    }
    return {};
}

inline bool restored(qint64 pid)
{
    const auto dir = records();
    const auto peerGroup = group(pid);
    // Flatpak's bus proxy is a sibling, reparented to systemd. Its transient
    // scope and runtime pid file identify this launch even with two copies open.
    static const QRegularExpression flatpak(QStringLiteral("/app-flatpak-[^/]+-([0-9]+)\\.scope$"));
    const auto match = flatpak.match(QString::fromUtf8(peerGroup));
    if (match.hasMatch()) {
        QFile owner(QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation)
                    + QStringLiteral("/.flatpak/") + match.captured(1) + QStringLiteral("/pid"));
        if (owner.open(QIODevice::ReadOnly)) {
            const auto root = owner.read(32).trimmed().toLongLong();
            if (root > 1 && group(root) == peerGroup && recorded(dir, root, process(root)))
                return true;
        }
    }
    const auto tty = process(pid).tty;
    for (int depth = 0; pid > 1 && depth < 64; ++depth) {
        const auto p = process(pid);
        // A new app scope or an interactive shell in a restored terminal is
        // a separate launch. Do not let its ancestor's record silence it.
        if (p.tty != tty || group(pid) != peerGroup)
            break;
        if (recorded(dir, pid, p))
            return true;
        pid = p.parent;
    }
    return false;
}

inline bool quiet(const QString &sender)
{
    const QDir config(QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) + QStringLiteral("/monet"));
    if (!records().exists() || config.exists(QStringLiteral("allow-restored-wallet-prompts")))
        return false;
    if (!sender.startsWith(QLatin1Char(':')))
        return false;
    const auto pid = QDBusConnection::sessionBus().interface()->servicePid(sender);
    return pid.isValid() && restored(pid.value());
}
}
