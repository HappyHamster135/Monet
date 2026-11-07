// SPDX-License-Identifier: GPL-3.0-or-later
#include "folderopener.h"
#include <KIO/OpenFileManagerWindowJob>
#include <KIO/OpenUrlJob>
#include <KIO/StatJob>
#include <KIO/UDSEntry>
#include <KLocalizedString>
#include <KProtocolInfo>
#include <KProtocolManager>
#include <KWaylandExtras>
#include <KWindowSystem>
#include <QFuture>
#include <QQuickItem>
#include <QQuickWindow>
#include <QTextDocumentFragment>

static QString unavailable(const QString &detail)
{
    const auto message = i18nd("monet", "Couldn't open the folder. Check that its drive or connection is available, then try again.");
    return detail.isEmpty() ? message : message + QLatin1Char('\n') + QTextDocumentFragment::fromHtml(detail).toPlainText();
}
FolderOpener::FolderOpener(QObject *parent, int timeoutMs) : QObject(parent)
{
    m_deadline.setSingleShot(true); m_deadline.setInterval(timeoutMs);
    connect(&m_deadline, &QTimer::timeout, this, [this] {
        ++m_revision;
        if (m_job) { m_job->kill(KJob::Quietly); m_job = nullptr; }
        // Publish one complete transition. A changed handler can immediately
        // retry without the old timeout overwriting that newer action's state.
        finish(i18nd("monet", "The folder is taking too long to respond. Reconnect its drive or network, then try again."));
    });
}
FolderOpener::~FolderOpener()
{
    ++m_revision; m_deadline.stop();
    if (m_job) m_job->kill(KJob::Quietly);
}
QString FolderOpener::plainText(const QString &formatted) const
{
    return QTextDocumentFragment::fromHtml(formatted).toPlainText();
}
bool FolderOpener::open(const QUrl &url, bool mustBeDirectory, QQuickItem *source)
{
    if (m_busy) return false;
    m_error.clear();
    // KProtocolManager reads installed worker metadata, not the destination.
    // Stream/helper URLs (including web pages and application handlers) cannot
    // become an Open folder action. Filesystem inspection itself is async KIO.
    if (!url.isValid() || url.isRelative() || url.path().isEmpty() || url.path().contains(QChar::Null) || url.toEncoded().size() > 32768
            || url.scheme() == QStringLiteral("trash") || url.scheme() == QStringLiteral("applications")
            || KProtocolInfo::isHelperProtocol(url) || KProtocolManager::outputType(url) != KProtocolInfo::T_FILESYSTEM
            || !KProtocolManager::supportsListing(url)) {
        m_error = i18nd("monet", "This transfer has no folder to open."); Q_EMIT changed(); return false;
    }
    m_busy = true; m_dispatched = false;
    const auto revision = ++m_revision;
    QPointer<QQuickWindow> window = source ? source->window() : nullptr;
    m_deadline.start(); Q_EMIT changed();
    QTimer::singleShot(0, this, [this, url, mustBeDirectory, window, revision] {
        if (!m_busy || revision != m_revision) return;
        auto job = KIO::stat(url, KIO::StatJob::SourceSide,
            KIO::StatBasic | KIO::StatResolveSymlink, KIO::HideProgressInfo);
        m_job = job;
        connect(job, &KJob::result, this, [this, url, mustBeDirectory, window, revision, job] {
            if (!m_busy || revision != m_revision) return;
            m_job = nullptr;
            if (job->error()) { finish(unavailable(job->errorText())); return; }
            const bool directory = job->statResult().isDir();
            if (mustBeDirectory && !directory) {
                finish(i18nd("monet", "This destination is no longer a folder. Choose it again in Files.")); return;
            }
            const auto begin = [this, url, directory, revision](const QString &token) {
                dispatch(url, directory, token.toUtf8(), revision);
            };
            if (window && KWindowSystem::isPlatformWayland()) {
                KWaylandExtras::xdgActivationToken(window, {}).then(this, begin);
                QTimer::singleShot(2000, this, [begin] { begin({}); });
            } else begin({});
        });
    });
    return true;
}
void FolderOpener::dispatch(const QUrl &url, bool directory, const QByteArray &token, quint64 revision)
{
    if (!m_busy || revision != m_revision || m_dispatched) return;
    m_dispatched = true;
    KJob *job;
    if (directory) {
        auto open = new KIO::OpenUrlJob(url, QStringLiteral("inode/directory"), this);
        open->setRunExecutables(false); open->setEnableExternalBrowser(false); open->setStartupId(token);
        job = open;
    } else {
        // Native ShowItems opens the containing folder and selects the output;
        // it never opens or executes a downloaded file (including .desktop).
        auto reveal = new KIO::OpenFileManagerWindowJob(this);
        reveal->setHighlightUrls({url}); reveal->setStartupId(token); job = reveal;
    }
    m_job = job;
    connect(job, &KJob::result, this, [this, url, directory, revision, job] {
        if (!m_busy || revision != m_revision) return;
        if (job->error()) finish(unavailable(job->errorText()));
        else { finish(); Q_EMIT opened(url, !directory); }
    });
    job->start();
}
void FolderOpener::finish(const QString &error)
{
    m_deadline.stop(); m_job = nullptr; m_busy = false; m_error = error; Q_EMIT changed();
}
void FolderOpener::cancel()
{
    ++m_revision;
    if (m_job) { m_job->kill(KJob::Quietly); m_job = nullptr; }
    finish();
}
