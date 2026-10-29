// SPDX-License-Identifier: GPL-2.0-or-later
#include <QDBusConnectionInterface>
#include <QDBusServiceWatcher>
#include <QFile>
#include <QHash>
#include <QRegularExpression>
#include <QSaveFile>
#include <QStandardPaths>
#include <sys/stat.h>
#include <unistd.h>

namespace {
QString monetPdfToken;
QString monetPdfOwner;
quint64 monetPdfGeneration = 0;
QHash<Shell *, QString> monetPdfWindows;
QPointer<QDBusServiceWatcher> monetPdfWatcher;

void monetPdfDisarm()
{
    monetPdfToken.clear();
    monetPdfOwner.clear();
    monetPdfWindows.clear();
    if (monetPdfWatcher) monetPdfWatcher->setWatchedServices({});
    ++monetPdfGeneration;
}

QString monetPdfReceiptPath(const QString &token, const QString &id)
{
    const auto runtime = QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation);
    auto privateDirectory = [](const QString &path) {
        struct stat info;
        return lstat(QFile::encodeName(path).constData(), &info) == 0 && S_ISDIR(info.st_mode)
            && info.st_uid == getuid() && (info.st_mode & 0777) == 0700;
    };
    if (!privateDirectory(runtime)) return {};
    const auto directory = runtime + QStringLiteral("/monet-pdf");
    mkdir(QFile::encodeName(directory).constData(), 0700);
    if (!privateDirectory(directory) || QUuid(id).isNull()) return {};
    return directory + QLatin1Char('/') + token + QLatin1Char('-') + QString::number(QCoreApplication::applicationPid())
        + QLatin1Char('-') + QUuid(id).toString(QUuid::WithoutBraces) + QStringLiteral(".json");
}
}

static quint64 monetDocumentDepartureGeneration()
{
    return monetPdfGeneration;
}

bool Shell::monetDocumentDeparture(const QString &token, bool armed, const QDBusMessage &message)
{
    static const QRegularExpression valid(QStringLiteral("\\A[0-9a-f]{32}\\z"));
    if (!valid.match(token).hasMatch()) return false;
    const auto owner = message.service();
    if (!armed) {
        if (monetPdfToken == token && monetPdfOwner == owner) monetPdfDisarm();
        return monetPdfToken != token;
    }
    auto bus = QDBusConnection::sessionBus();
    if (!owner.startsWith(QLatin1Char(':')) || !bus.interface() || !bus.interface()->isServiceRegistered(owner).value()) return false;
    const auto generation = monetPdfGeneration;
    const auto windows = monetDocumentIdentities();
    if (generation != monetPdfGeneration || windows.isEmpty()) return false;
    if (!monetPdfToken.isEmpty()) {
        if (monetPdfToken != token || monetPdfOwner != owner) return false;
        for (const auto &[window, id] : windows) {
            if ((monetPdfWindows.contains(window) && monetPdfWindows.value(window) != id)
                || monetPdfReceiptPath(token, id).isEmpty()) return false;
        }
        for (const auto &[window, id] : windows) {
            if (monetPdfWindows.contains(window)) continue;
            monetPdfWindows.insert(window, id);
            connect(window, &QObject::destroyed, qApp, [window] { monetPdfWindows.remove(window); });
        }
        return true;
    }
    for (const auto &[window, id] : windows) {
        if (monetPdfReceiptPath(token, id).isEmpty()) return false;
    }
    if (!monetPdfWatcher) {
        monetPdfWatcher = new QDBusServiceWatcher(qApp);
        monetPdfWatcher->setConnection(bus);
        monetPdfWatcher->setWatchMode(QDBusServiceWatcher::WatchForUnregistration);
        connect(monetPdfWatcher, &QDBusServiceWatcher::serviceUnregistered, qApp, [](const QString &service) {
            if (service == monetPdfOwner) monetPdfDisarm();
        });
    }
    monetPdfToken = token;
    monetPdfOwner = owner;
    monetPdfWatcher->setWatchedServices({owner});
    for (const auto &[window, id] : windows) {
        monetPdfWindows.insert(window, id);
        connect(window, &QObject::destroyed, qApp, [window] { monetPdfWindows.remove(window); });
    }
    ++monetPdfGeneration;
    if (!bus.interface()->isServiceRegistered(owner).value()) {
        monetPdfDisarm();
        return false;
    }
    return true;
}

bool Shell::monetFinishDocumentDeparture(quint64 generation, KParts::ReadWritePart *active)
{
    if (generation != monetPdfGeneration) return false;
    if (monetPdfToken.isEmpty()) return true;
    const auto id = monetPdfWindows.value(this);
    const auto windows = monetDocumentIdentities();
    if (id.isEmpty() || windows.isEmpty()) return false;
    for (const auto &[window, currentId] : windows) {
        if (monetPdfWindows.value(window) != currentId) return false;
    }
    const auto path = monetPdfReceiptPath(monetPdfToken, id);
    if (path.isEmpty()) return false;
    const auto parsed = QJsonDocument::fromJson(monetDocumentState().toUtf8());
    auto state = parsed.object();
    // Native save prompts select modified tabs; keep the tab selected before those prompts.
    if (parsed.isObject() && !state.value(QStringLiteral("tabs")).toArray().isEmpty()) {
        for (int i = 0; i < m_tabs.size(); ++i) {
            if (m_tabs[i].part == active) state.insert(QStringLiteral("active"), i);
        }
    }
    const QJsonObject receipt{{QStringLiteral("version"), 1}, {QStringLiteral("id"), monetPdfToken},
        {QStringLiteral("pid"), QCoreApplication::applicationPid()}, {QStringLiteral("window"), id},
        {QStringLiteral("app"), QStringLiteral("org.kde.okular.desktop")}, {QStringLiteral("supported"), parsed.isObject()},
        {QStringLiteral("document"), parsed.isObject() ? QJsonValue(state) : QJsonValue(QJsonValue::Null)}};
    const auto bytes = QJsonDocument(receipt).toJson(QJsonDocument::Compact);
    QSaveFile file(path);
    if (generation != monetPdfGeneration || bytes.size() > 600000 || !file.open(QIODevice::WriteOnly)
        || !file.setPermissions(QFile::ReadOwner | QFile::WriteOwner) || file.write(bytes) != bytes.size()
        || !file.flush() || fsync(file.handle()) != 0 || !file.commit()) return false;
    return true;
}
