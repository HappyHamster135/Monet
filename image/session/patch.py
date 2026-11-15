#!/usr/bin/python3
"""Keep the logout cover and defer firmware restart until Plasma has closed apps."""
from pathlib import Path
import sys
source=Path(sys.argv[1])
root=source/'logout-greeter'
def replace(name,old,new):
 p=root/name;s=p.read_text()
 if new in s:return
 if s.count(old)!=1:raise ValueError('Unsupported logout source: '+name)
 p.write_text(s.replace(old,new))

root = source / 'containmentactions/contextmenu'
replace('menu.h', '    QAction *m_openTerminalAction = nullptr;', '''    QAction *m_monetTaskManagerAction = nullptr;
    QAction *m_openTerminalAction = nullptr;''')
replace('menu.cpp', '    if (!m_runCommandAction) {', '''    if (!m_runCommandAction) {
        m_monetTaskManagerAction = new QAction(i18nd("monet", "Task Manager"), this);
        m_monetTaskManagerAction->setIcon(QIcon::fromTheme(u"utilities-system-monitor"_s));
        connect(m_monetTaskManagerAction, &QAction::triggered, this, [this]() {
            if (auto service = KService::serviceByStorageId(u"org.kde.plasma-systemmonitor.desktop"_s)) {
                auto *job = new KIO::ApplicationLauncherJob(service);
                job->start();
            }
        });
''')
replace('menu.cpp', '    return actions;\n}', '''    const auto hasAvailableAction = [&actions](QLatin1StringView name) {
        return std::any_of(actions.cbegin(), actions.cend(), [name](QAction *action) {
            return action && action->objectName() == name && action->isVisible() && action->isEnabled();
        });
    };
    // Keep Plasma's display shortcut when the wallpaper doesn't provide one.
    if (hasAvailableAction(QLatin1String("monet-display-settings"))) {
        actions.removeAll(m_configureDisplaysAction);
    }
    // The containment also covers empty panel space and desktops that use another wallpaper.
    if (!hasAvailableAction(QLatin1String("monet-task-manager")) && KService::serviceByStorageId(u"org.kde.plasma-systemmonitor.desktop"_s)) {
        // Panel applet menus also include these containment actions. Let applets
        // use their own fallback only when this panel does not supply it.
        const auto type = cont->containmentType();
        if ((type == Plasma::Containment::Panel || type == Plasma::Containment::CustomPanel)
                && cont->containmentActions().value(u"RightButton;NoModifier"_s) == this
                && !cont->internalAction(u"monet-task-manager"_s)) {
            cont->setInternalAction(u"monet-task-manager"_s, m_monetTaskManagerAction);
        }
        const auto first = std::find_if(actions.begin(), actions.end(), [](QAction *action) {
            return action && !action->isSeparator();
        });
        actions.insert(first, m_monetTaskManagerAction);
    }
    return actions;
}''')
replace('menu.cpp', '#include <QAction>', '#include <algorithm>\n#include <QAction>')

root=source/'logout-greeter'
replace('greeter.h','    bool m_running = false;','    bool m_running = false;\n    bool m_leaving = false;')
replace('greeter.h','    void promptAll();','    void promptAll();\n    void updateMonetCover();')
replace('greeter.cpp','#include <QScreen>','#include <QScreen>\n#include <QQuickItem>\n#include <QDBusServiceWatcher>\n#include <LayerShellQt/Window>')
replace('greeter.cpp','            case Qt::ApplicationInactive:\n','            case Qt::ApplicationInactive:\n                if (m_leaving) break;\n')
replace('greeter.cpp','            qCWarning(LOGOUT_GREETER) << "Failed to get focus after 3 seconds, quitting";',
        '            if (m_leaving) return;\n            qCWarning(LOGOUT_GREETER) << "Failed to get focus after 3 seconds, quitting";')
replace('greeter.cpp','    connect(w, &KSMShutdownDlg::accepted, this, &Greeter::quit);','''    connect(w, &KSMShutdownDlg::accepted, this, [this, w] {
        if (!w->rootObject() || !w->rootObject()->property("monetHandoff").toBool()) {
            quit(); return;
        }
        m_leaving = true;
        const auto message = w->rootObject()->property("transitionMessage").toString();
        for (auto dialog : std::as_const(m_dialogs)) {
            QMetaObject::invokeMethod(dialog->rootObject(), "showLeaving", Q_ARG(QVariant, message));
            // Cover normal applications, without retaining an exclusive grab.
            // QML watches native window metadata and reveals save prompts.
            dialog->setKeyboardGrabEnabled(false);
            if (KWindowSystem::isPlatformWayland() && !m_windowed) {
                if (auto layer = LayerShellQt::Window::get(dialog)) {
                    layer->setKeyboardInteractivity(LayerShellQt::Window::KeyboardInteractivityNone);
                    layer->setLayer(LayerShellQt::Window::LayerOverlay);
                }
            } else dialog->raise();
        }
        updateMonetCover();
        auto watcher = new QDBusServiceWatcher(QStringLiteral("org.kde.Shutdown"), QDBusConnection::sessionBus(),
            QDBusServiceWatcher::WatchForUnregistration, this);
        connect(watcher, &QDBusServiceWatcher::serviceUnregistered, this, &Greeter::quit);
        // Failed/denied requests never leave an orphaned backdrop. Actual
        // cancellation also ends Shutdown's connection and reaches the watcher.
        QTimer::singleShot(3000, this, [this] {
            if (!QDBusConnection::sessionBus().interface()->isServiceRegistered(QStringLiteral("org.kde.Shutdown"))) quit();
        });
    });''')
# KWindowSystem is already linked by the native target.
replace('greeter.cpp','#include <KLocalizedQmlContext>','#include <KLocalizedQmlContext>\n#include <KWindowSystem>\n#include <QQmlContext>\n#include <windowtasksmodel.h>')
replace('greeter.cpp', '    new LogoutPromptAdaptor(this);', '''    m_engine->rootContext()->setContextProperty(QStringLiteral("monetSessionWindows"), new TaskManager::WindowTasksModel(this));
    new LogoutPromptAdaptor(this);''')
replace('greeter.cpp', '    w->init(m_package);', '''    w->init(m_package);
    if (w->rootObject() && w->rootObject()->metaObject()->indexOfSignal("monetInteractionRequiredChanged()") >= 0) {
        connect(w->rootObject(), SIGNAL(monetInteractionRequiredChanged()), this, SLOT(updateMonetCover()));
    }''')
replace('greeter.cpp', 'void Greeter::quit()\n{', '''void Greeter::updateMonetCover()
{
    if (!m_leaving) return;
    // Any display can request access to a native prompt. Apply the same layer
    // to every output so a dialog cannot be stranded behind another screen.
    const bool interactive = std::ranges::any_of(m_dialogs, [](KSMShutdownDlg *dialog) {
        return dialog->rootObject() && dialog->rootObject()->property("monetInteractionRequired").toBool();
    });
    for (auto dialog : std::as_const(m_dialogs)) {
        if (KWindowSystem::isPlatformWayland() && !m_windowed) {
            if (auto layer = LayerShellQt::Window::get(dialog)) {
                layer->setLayer(interactive ? LayerShellQt::Window::LayerBottom : LayerShellQt::Window::LayerOverlay);
            }
        } else if (interactive) dialog->lower();
        else dialog->raise();
    }
}

void Greeter::quit()
{''')

root=source/'startkde/plasma-shutdown'
replace('org.kde.Shutdown.xml', '    <method name="logoutAndReboot"/>', '''    <method name="logoutAndReboot"/>
    <method name="logoutAndRebootToFirmware">
      <arg name="started" type="b" direction="out"/>
    </method>''')
replace('shutdown.h', '    void logoutAndReboot();', '''    void logoutAndReboot();
    bool logoutAndRebootToFirmware();''')
replace('shutdown.h', '    void startLogout(KWorkSpace::ShutdownType shutdownType);', '''    bool startLogout(KWorkSpace::ShutdownType shutdownType, bool rebootToFirmware = false);
    bool requestFirmwareReboot();
    bool m_rebootToFirmware = false;''')
replace('shutdown.cpp', '#include <QDBusConnection>', '''#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusReply>
#include <QDBusVariant>''')
replace('shutdown.cpp', 'void Shutdown::startLogout(KWorkSpace::ShutdownType shutdownType)', '''static QDBusMessage login1Call(const QString &method, const QVariantList &arguments = {},
                               const QString &interface = QStringLiteral("org.freedesktop.login1.Manager"))
{
    auto call = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.login1"),
                                               QStringLiteral("/org/freedesktop/login1"), interface, method);
    call.setArguments(arguments);
    call.setInteractiveAuthorizationAllowed(true);
    return QDBusConnection::systemBus().call(call, QDBus::Block, INT32_MAX);
}

bool Shutdown::logoutAndRebootToFirmware()
{
    const QDBusReply<QString> allowed = login1Call(QStringLiteral("CanRebootToFirmwareSetup"));
    if (!allowed.isValid() || (allowed.value() != QStringLiteral("yes") && allowed.value() != QStringLiteral("challenge"))) {
        return false;
    }
    return startLogout(KWorkSpace::ShutdownTypeReboot, true);
}

bool Shutdown::startLogout(KWorkSpace::ShutdownType shutdownType, bool rebootToFirmware)''')
replace('shutdown.cpp', '''        qCWarning(PLASMA_SESSION) << "Logout already in progress, ignoring duplicate request";
        return;
    }

    m_shutdownType = shutdownType;''', '''        qCWarning(PLASMA_SESSION) << "Logout already in progress, ignoring duplicate request";
        return false;
    }

    m_shutdownType = shutdownType;
    m_rebootToFirmware = rebootToFirmware;''')
replace('shutdown.cpp', '''        if (closeSessionReply.isError()) {
            qCInfo(PLASMA_SESSION)''', '''        if (closeSessionReply.isError()) {
            if (m_rebootToFirmware) {
                logoutCancelled();
                return;
            }
            qCInfo(PLASMA_SESSION)''')
replace('shutdown.cpp', '''    });
}

void Shutdown::saveSession()''', '''    });
    return true;
}

void Shutdown::saveSession()''')
replace('shutdown.cpp', '''void Shutdown::logoutComplete()
{
    runShutdownScripts();
''', '''bool Shutdown::requestFirmwareReboot()
{
    const auto manager = QStringLiteral("org.freedesktop.login1.Manager");
    const auto property = QStringLiteral("RebootToFirmwareSetup");
    const auto setFirmware = QStringLiteral("SetRebootToFirmwareSetup");
    const QDBusReply<QDBusVariant> previous = login1Call(QStringLiteral("Get"), {manager, property},
                                                       QStringLiteral("org.freedesktop.DBus.Properties"));
    if (!previous.isValid()) {
        qCWarning(PLASMA_SESSION) << "Could not read the firmware boot target" << previous.error().message();
        return false;
    }
    const bool arm = !previous.value().variant().toBool();
    if (arm) {
        const QDBusReply<void> prepared = login1Call(setFirmware, {true});
        if (!prepared.isValid()) {
            qCWarning(PLASMA_SESSION) << "Could not set the firmware boot target" << prepared.error().message();
            return false;
        }
    }

    const QDBusReply<void> reboot = login1Call(QStringLiteral("Reboot"), {true});
    if (reboot.isValid()) {
        return true;
    }
    if (arm) {
        const QDBusReply<void> cleared = login1Call(setFirmware, {false});
        if (!cleared.isValid()) {
            qCWarning(PLASMA_SESSION) << "Could not clear the firmware boot target" << cleared.error().message();
        }
    }
    qCWarning(PLASMA_SESSION) << "Could not restart into firmware" << reboot.error().message();
    return false;
}

void Shutdown::logoutComplete()
{
    runShutdownScripts();

    if (m_rebootToFirmware) {
        // Both application close requests have succeeded. Keep the active session
        // available to logind for authorization until it accepts the reboot.
        if (requestFirmwareReboot()) {
            qApp->quit();
        } else {
            OrgKdeKSMServerInterfaceInterface ksmserverIface(QStringLiteral("org.kde.ksmserver"), QStringLiteral("/KSMServer"), QDBusConnection::sessionBus());
            ksmserverIface.resetLogout();
            logoutCancelled();
        }
        return;
    }
''')
