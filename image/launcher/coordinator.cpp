// SPDX-License-Identifier: GPL-3.0-or-later
#include "coordinator.h"
#include <KIO/ApplicationLauncherJob>
#include <KLocalizedString>
#include <KNotification>
#include <KWaylandExtras>
#include <KWindowSystem>
#include <PlasmaActivities/ResourceInstance>
#include <QCoreApplication>
#include <QDateTime>
#include <QFuture>
#include <QRegularExpression>
#include <QSocketNotifier>
#include <QTextDocumentFragment>
#include <QUrl>
#include <QWindow>
#include <abstracttasksmodel.h>
#include <tasksmodel.h>
#include <algorithm>
#include <cerrno>
#include <poll.h>
#include <signal.h>
#include <sys/syscall.h>
#include <unistd.h>

static const QString BusName = QStringLiteral("org.monet.Launcher");
static const QString BusPath = QStringLiteral("/Launcher");
using Roles = TaskManager::AbstractTasksModel;

LaunchCoordinator *LaunchCoordinator::shared()
{
    // One coordinator per process, including multiple QML engines. It owns
    // pending native jobs even if the menu closes or its view is recreated.
    static QPointer<LaunchCoordinator> instance;
    if (!instance) instance = new LaunchCoordinator(nullptr, {}, true, true, QCoreApplication::instance());
    return instance;
}
QString LaunchCoordinator::key(const QString &value)
{
    if (value.size() > 4096) return {};
    QString id = value;
    const QUrl url(value);
    if (url.isLocalFile() && !url.hasQuery() && !url.hasFragment()) {
        // Resolve only applications already indexed by KService; this does not
        // execute arbitrary .desktop files supplied as filesystem paths.
        const auto service = KService::serviceByDesktopPath(url.toLocalFile());
        if (!service) return {};
        id = service->storageId();
    }
    if (id.startsWith(QStringLiteral("applications:"))) id.remove(0, 13);
    static const QRegularExpression allowed(QStringLiteral("\\A[\\p{L}\\p{N}_][\\p{L}\\p{N}_.+-]{0,255}\\.desktop\\z"));
    return allowed.match(id).hasMatch() ? id : QString{};
}
LaunchCoordinator::LaunchCoordinator(QAbstractItemModel *model, std::function<void(const QModelIndex &)> activate,
    bool notifications, bool endpoint, QObject *parent)
    : QObject(parent), m_tasks(model), m_activate(std::move(activate)), m_notify(notifications), m_bus(QDBusConnection::sessionBus())
{
    if (!m_tasks) {
        auto tasks = new TaskManager::TasksModel(this);
        tasks->setGroupMode(TaskManager::TasksModel::GroupDisabled);
        m_tasks = tasks;
        m_activate = [tasks](const QModelIndex &index) { tasks->requestActivate(index); };
    }
    m_reconcile.setSingleShot(true); m_reconcile.setInterval(0);
    connect(&m_reconcile, &QTimer::timeout, this, &LaunchCoordinator::reconcile);
    connect(m_tasks, &QAbstractItemModel::dataChanged, this, &LaunchCoordinator::scheduleReconcile);
    connect(m_tasks, &QAbstractItemModel::rowsInserted, this, &LaunchCoordinator::scheduleReconcile);
    connect(m_tasks, &QAbstractItemModel::rowsRemoved, this, &LaunchCoordinator::scheduleReconcile);
    connect(m_tasks, &QAbstractItemModel::modelReset, this, &LaunchCoordinator::scheduleReconcile);
    connect(m_tasks, &QAbstractItemModel::layoutChanged, this, &LaunchCoordinator::scheduleReconcile);
    if (endpoint && m_bus.registerService(BusName)) {
        m_endpoint = m_bus.registerObject(BusPath, this, QDBusConnection::ExportAllSlots);
        if (!m_endpoint) m_bus.unregisterService(BusName);
    }
}
LaunchCoordinator::~LaunchCoordinator()
{
    for (const auto &attempt : std::as_const(m_attempts)) clearWatch(attempt);
    if (m_endpoint) { m_bus.unregisterObject(BusPath); m_bus.unregisterService(BusName); }
}
QString LaunchCoordinator::taskId(const QModelIndex &index) const
{
    auto id = key(index.data(Roles::StorageId).toString());
    if (!id.isEmpty()) return id;
    const auto url = index.data(Roles::LauncherUrlWithoutIcon).toUrl();
    if (url.scheme() == QStringLiteral("applications")) id = key(url.toString());
    if (!id.isEmpty()) return id;
    // AppId is Plasma's resolved desktop entry name, not a title or PID.
    const auto app = index.data(Roles::AppId).toString();
    return key(app.endsWith(QStringLiteral(".desktop")) ? app : app + QStringLiteral(".desktop"));
}
QString LaunchCoordinator::windowId(const QModelIndex &index) const
{
    QStringList ids;
    for (const auto &id : index.data(Roles::WinIdList).toList()) ids.append(id.toString());
    std::sort(ids.begin(), ids.end());
    return ids.join(QChar(0x1f));
}
QList<QModelIndex> LaunchCoordinator::windows(const QString &id, bool mappedOnly) const
{
    QList<QModelIndex> result;
    if (!m_tasks) return result;
    for (int row = 0; row < m_tasks->rowCount(); ++row) {
        const auto index = m_tasks->index(row, 0);
        const auto mapped = index.data(Roles::IsMapped);
        if (mappedOnly && mapped.isValid() && !mapped.toBool() && !index.data(Roles::IsMinimized).toBool()) continue;
        if (index.data(Roles::IsWindow).toBool() && taskId(index) == id) result.append(index);
    }
    std::stable_sort(result.begin(), result.end(), [](const QModelIndex &a, const QModelIndex &b) {
        return a.data(Roles::LastActivated).toDateTime() > b.data(Roles::LastActivated).toDateTime();
    });
    return result;
}
bool LaunchCoordinator::startup(const QString &id) const
{
    if (!m_tasks) return false;
    for (int row = 0; row < m_tasks->rowCount(); ++row) {
        const auto index = m_tasks->index(row, 0);
        if (index.data(Roles::IsStartup).toBool() && taskId(index) == id) return true;
    }
    return false;
}
QVariantMap LaunchCoordinator::states() const
{
    QVariantMap result;
    for (const auto &attempt : m_attempts) {
        if (attempt->hidden) continue;
        const auto old = result.value(attempt->id).toMap();
        const bool pending = attempt->state == QStringLiteral("starting") || attempt->state == QStringLiteral("unconfirmed");
        if (!pending && old.value(QStringLiteral("pending")).toBool()) continue;
        result.insert(attempt->id, QVariantMap{{"id", attempt->id}, {"name", attempt->name}, {"icon", attempt->icon},
            {"state", attempt->state}, {"error", attempt->error}, {"pending", pending},
            {"spawned", attempt->jobFinished && attempt->pid > 0}, {"sequence", QVariant::fromValue(attempt->serial)}});
    }
    return result;
}
QVariantMap LaunchCoordinator::Open(const QString &id, bool newWindow, const QString &activationToken)
{
    return open(id, nullptr, newWindow, activationToken);
}
QVariantMap LaunchCoordinator::open(const QString &value, QWindow *window, bool newWindow, const QString &token, const QString &activityAgent)
{
    const auto id = key(value);
    if (id.isEmpty() || token.size() > 4096 || token.contains(QChar::Null)) return {{"accepted", false}};
    const auto running = windows(id);
    if (!newWindow && !running.isEmpty()) {
        if (m_activate) m_activate(running.first());
        reconcile();
        dismiss(id);
        return {{"accepted", true}, {"state", windows(id, true).isEmpty() ? "activating" : "running"}};
    }
    if (!newWindow) {
        const auto attempts = m_attempts.values();
        for (const auto &attempt : attempts) {
            if (attempt->id != id) continue;
            if (attempt->state == QStringLiteral("starting") || attempt->state == QStringLiteral("unconfirmed")) {
                if (attempt->hidden) {
                    attempt->hidden = false;
                    Q_EMIT changed();
                    notify(attempt);
                }
                return {{"accepted", true}, {"state", attempt->state}};
            }
        }
        if (startup(id)) return {{"accepted", true}, {"state", "starting"}};
    }
    // Keep failed history bounded without forgetting in-flight launches.
    for (auto it = m_attempts.begin(); it != m_attempts.end();) {
        if ((*it)->id == id && ((*it)->state == QStringLiteral("failed") || (*it)->state == QStringLiteral("running")
                || ((*it)->state == QStringLiteral("unconfirmed") && (*it)->jobFinished && !processAlive(*it) && !startup(id)))) {
            clearWatch(*it); it = m_attempts.erase(it);
        } else ++it;
    }
    if (m_attempts.size() >= 64) {
        for (auto it = m_attempts.begin(); it != m_attempts.end() && m_attempts.size() >= 64;) {
            if ((*it)->state == QStringLiteral("failed") || (*it)->state == QStringLiteral("running")) {
                clearWatch(*it); it = m_attempts.erase(it);
            } else ++it;
        }
        if (m_attempts.size() >= 64) return {{"accepted", false}};
    }
    if (m_notifications.value(id)) m_notifications.value(id)->close();
    const auto attempt = std::make_shared<Attempt>();
    attempt->serial = ++m_serial; attempt->id = id; attempt->name = id;
    attempt->newWindow = newWindow; attempt->state = QStringLiteral("starting");
    if (activityAgent == QStringLiteral("org.kde.plasma.kicker") || activityAgent == QStringLiteral("org.kde.libtaskmanager"))
        attempt->activityAgent = activityAgent;
    for (const auto &index : running) {
        attempt->originalWindows.insert(index);
        const auto identity = windowId(index);
        if (!identity.isEmpty()) attempt->originalWindowIds.insert(identity);
    }
    m_attempts.insert(attempt->serial, attempt);
    Q_EMIT changed(); // Visible feedback precedes token acquisition/process work.
    attempt->service = KService::serviceByStorageId(id);
    if (!attempt->service || !attempt->service->isValid() || !attempt->service->isApplication()
            || attempt->service->isDeleted() || attempt->service->property<bool>(QStringLiteral("Hidden"))) {
        finish(attempt, QStringLiteral("failed"), i18nd("monet", "This app is no longer available. Install it again, then retry."));
        return {{"accepted", false}, {"state", "failed"}};
    }
    attempt->name = attempt->service->name(); attempt->icon = attempt->service->icon();
    if (newWindow && !running.isEmpty() && attempt->service->property<bool>(QStringLiteral("SingleMainWindow"))) {
        if (m_activate) m_activate(running.first());
        finish(attempt, QStringLiteral("running"));
        return {{"accepted", true}, {"state", "running"}};
    }
    Q_EMIT changed();
    auto deadline = new QTimer(this); attempt->deadline = deadline; deadline->setSingleShot(true);
    connect(deadline, &QTimer::timeout, this, [this, attempt] {
        reconcile();
        if (retained(attempt) && attempt->state == QStringLiteral("starting"))
            finish(attempt, QStringLiteral("unconfirmed"), i18nd("monet", "No window was confirmed. The app may still be opening. Retry checks for an existing window first."));
    });
    deadline->start(30000);
    const auto begin = [this, attempt](const QString &activation) { start(attempt, activation); };
    if (!token.isEmpty()) QTimer::singleShot(0, this, [begin, token] { begin(token); });
    else if (window && KWindowSystem::isPlatformWayland()) {
        const auto appId = attempt->service->desktopEntryName();
        KWaylandExtras::xdgActivationToken(window, appId).then(this, begin);
        // A missing compositor token must not leave the application stuck.
        QTimer::singleShot(2000, this, [begin] { begin({}); });
    } else QTimer::singleShot(0, this, [begin] { begin({}); });
    return {{"accepted", true}, {"state", "starting"}};
}
QVariantMap LaunchCoordinator::retry(const QString &value, QWindow *window, const QString &token)
{
    const auto id = key(value);
    AttemptPtr problem;
    for (const auto &attempt : std::as_const(m_attempts))
        if (attempt->id == id && (attempt->state == QStringLiteral("failed") || attempt->state == QStringLiteral("unconfirmed"))) problem = attempt;
    if (!problem) return open(value, window, false, token);
    const auto ready = windows(id, true);
    for (const auto &index : ready) {
        if (problem->newWindow && (problem->originalWindows.contains(index) || problem->originalWindowIds.contains(windowId(index)))) continue;
        if (m_activate) m_activate(index);
        finish(problem, QStringLiteral("running"));
        return {{"accepted", true}, {"state", "running"}};
    }
    if (problem->state == QStringLiteral("unconfirmed") && (!problem->jobFinished || processAlive(problem) || startup(id)))
        return {{"accepted", true}, {"state", "unconfirmed"}};
    const bool newWindow = problem->newWindow;
    const auto activityAgent = problem->activityAgent;
    clearWatch(problem); m_attempts.remove(problem->serial);
    return open(value, window, newWindow, token, activityAgent);
}
bool LaunchCoordinator::retained(const AttemptPtr &attempt) const { return m_attempts.value(attempt->serial) == attempt; }
void LaunchCoordinator::start(const AttemptPtr &attempt, const QString &token)
{
    if (!retained(attempt) || attempt->jobStarted || attempt->state != QStringLiteral("starting")) return;
    const auto existing = windows(attempt->id);
    if (!attempt->newWindow && !existing.isEmpty()) {
        attempt->jobStarted = true; attempt->jobFinished = true;
        if (m_activate) m_activate(existing.first());
        reconcile(); return;
    }
    if (attempt->newWindow) for (const auto &index : existing) {
        attempt->originalWindows.insert(index);
        const auto identity = windowId(index);
        if (!identity.isEmpty()) attempt->originalWindowIds.insert(identity);
    }
    attempt->jobStarted = true;
    auto job = new KIO::ApplicationLauncherJob(attempt->service, this);
    if (!token.isEmpty()) job->setStartupId(token.toUtf8());
    connect(job, &KJob::result, this, [this, attempt, job] {
        if (!retained(attempt)) return;
        attempt->jobFinished = true;
        if (attempt->state != QStringLiteral("starting") && attempt->state != QStringLiteral("unconfirmed")) return;
        if (job->error()) { finish(attempt, QStringLiteral("failed"), QTextDocumentFragment::fromHtml(job->errorText()).toPlainText()); return; }
        // Native job completion confirms spawning, not a usable window.
        attempt->pid = job->pid(); watchProcess(attempt); scheduleReconcile();
        Q_EMIT changed();
    });
    job->start();
    // Preserve the native menu/task-manager usage history, once per actual job.
    // Repeated pending clicks and raising a window never record extra launches.
    if (!attempt->activityAgent.isEmpty())
        KActivities::ResourceInstance::notifyAccessed(QUrl(QStringLiteral("applications:") + attempt->id), attempt->activityAgent);
}
void LaunchCoordinator::watchProcess(const AttemptPtr &attempt)
{
    if (attempt->pid <= 0) return; // D-Bus activation can succeed without a PID.
    attempt->pidfd = static_cast<int>(syscall(SYS_pidfd_open, attempt->pid, 0));
    if (attempt->pidfd < 0) { if (errno == ESRCH) processExited(attempt); return; }
    auto watcher = new QSocketNotifier(attempt->pidfd, QSocketNotifier::Read, this); attempt->exited = watcher;
    connect(watcher, &QSocketNotifier::activated, this, [this, attempt] { processExited(attempt); });
}
bool LaunchCoordinator::processAlive(const AttemptPtr &attempt) const
{
    if (attempt->processExited || attempt->pid <= 0) return false;
    if (attempt->pidfd >= 0) { pollfd fd{attempt->pidfd, POLLIN, 0}; return poll(&fd, 1, 0) == 0; }
    // Read-only fallback on kernels that refuse pidfd. A reused PID can only
    // keep a duplicate launch blocked; it is never signalled or terminated.
    return kill(static_cast<pid_t>(attempt->pid), 0) == 0 || errno == EPERM;
}
void LaunchCoordinator::processExited(const AttemptPtr &attempt)
{
    attempt->processExited = true;
    if (attempt->exited) attempt->exited->setEnabled(false);
    // Wrapper processes may exit before a child window appears. Give native
    // startup/window events time to arrive, and describe uncertainty accurately.
    QTimer::singleShot(750, this, [this, attempt] {
        reconcile();
        if (retained(attempt) && attempt->state == QStringLiteral("starting") && !startup(attempt->id))
            finish(attempt, QStringLiteral("unconfirmed"), i18nd("monet", "No window was confirmed yet. The app may still be opening. Retry checks for an existing window first."));
    });
}
void LaunchCoordinator::scheduleReconcile() { if (!m_attempts.isEmpty()) m_reconcile.start(); }
void LaunchCoordinator::reconcile()
{
    const auto attempts = m_attempts.values();
    for (const auto &attempt : attempts) {
        if (!retained(attempt)) continue;
        if (attempt->state != QStringLiteral("starting") && attempt->state != QStringLiteral("unconfirmed")) continue;
        if (attempt->newWindow && !attempt->jobStarted) continue;
        auto ready = windows(attempt->id, true);
        ready.erase(std::remove_if(ready.begin(), ready.end(), [this, attempt](const QModelIndex &index) {
            return attempt->newWindow && (attempt->originalWindows.contains(index)
                || attempt->originalWindowIds.contains(windowId(index)));
        }), ready.end());
        if (!ready.isEmpty()) { finish(attempt, QStringLiteral("running")); continue; }
        const bool opening = startup(attempt->id);
        if (opening) attempt->observedStartup = true;
        else if (attempt->observedStartup && attempt->processExited && attempt->state == QStringLiteral("starting"))
            finish(attempt, QStringLiteral("unconfirmed"), i18nd("monet", "No window was confirmed yet. The app may still be opening. Retry checks for an existing window first."));
    }
}
void LaunchCoordinator::clearWatch(const AttemptPtr &attempt)
{
    if (attempt->deadline) { attempt->deadline->stop(); attempt->deadline->deleteLater(); attempt->deadline = nullptr; }
    if (attempt->exited) { attempt->exited->setEnabled(false); attempt->exited->deleteLater(); attempt->exited = nullptr; }
    if (attempt->pidfd >= 0) { close(attempt->pidfd); attempt->pidfd = -1; }
}
void LaunchCoordinator::finish(const AttemptPtr &attempt, const QString &state, const QString &error)
{
    if (!retained(attempt)) return;
    attempt->state = state; attempt->error = error;
    if (state == QStringLiteral("failed")) attempt->hidden = false;
    if (state != QStringLiteral("unconfirmed")) clearWatch(attempt);
    else if (attempt->deadline) { attempt->deadline->stop(); attempt->deadline->deleteLater(); attempt->deadline = nullptr; }
    Q_EMIT changed();
    if (state == QStringLiteral("failed") || state == QStringLiteral("unconfirmed")) notify(attempt);
    if (state == QStringLiteral("running") && m_notifications.value(attempt->id)) {
        const bool otherProblem = std::any_of(m_attempts.cbegin(), m_attempts.cend(), [attempt](const AttemptPtr &other) {
            return other->id == attempt->id && other->serial != attempt->serial
                && (other->state == QStringLiteral("failed") || other->state == QStringLiteral("unconfirmed"));
        });
        if (!otherProblem) m_notifications.value(attempt->id)->close();
    }
    if (state == QStringLiteral("running")) QTimer::singleShot(1500, this, [this, attempt] {
        if (retained(attempt) && attempt->state == QStringLiteral("running")) { m_attempts.remove(attempt->serial); Q_EMIT changed(); }
    });
}
void LaunchCoordinator::notify(const AttemptPtr &attempt)
{
    if (!m_notify) return;
    if (m_notifications.value(attempt->id)) m_notifications.value(attempt->id)->close();
    auto notification = new KNotification(QStringLiteral("launch-failed"), KNotification::Persistent, this);
    notification->setComponentName(QStringLiteral("monet-launcher"));
    notification->setTitle(attempt->state == QStringLiteral("unconfirmed")
        ? i18nd("monet", "Opening %1 wasn't confirmed", attempt->name) : i18nd("monet", "Couldn't open %1", attempt->name));
    notification->setText(attempt->error.toHtmlEscaped());
    notification->setIconName(attempt->icon.isEmpty() ? QStringLiteral("application-x-executable") : attempt->icon);
    auto retry = notification->addAction(i18nd("monet", "Retry"));
    connect(retry, &KNotificationAction::activated, this, [this, id = attempt->id, notification] {
        this->retry(id, nullptr, notification->xdgActivationToken());
    });
    m_notifications.insert(attempt->id, notification); notification->sendEvent();
}
void LaunchCoordinator::dismiss(const QString &value)
{
    const auto id = key(value);
    for (auto it = m_attempts.begin(); it != m_attempts.end();) {
        if ((*it)->id == id && (*it)->state == QStringLiteral("failed")) {
            clearWatch(*it); it = m_attempts.erase(it);
        } else {
            // Dismiss hides the message, not the duplicate guard. A wrapper may
            // have exited while its child is still preparing a window.
            if ((*it)->id == id && (*it)->state == QStringLiteral("unconfirmed")) (*it)->hidden = true;
            ++it;
        }
    }
    if (m_notifications.value(id)) m_notifications.value(id)->close();
    Q_EMIT changed();
}
