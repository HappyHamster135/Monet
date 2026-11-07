#!/usr/bin/python3
"""Retain Monet's native logout surface as the session closes; no power override."""
from pathlib import Path
import sys
root=Path(sys.argv[1])/'logout-greeter'
def replace(name,old,new):
 p=root/name;s=p.read_text()
 if new in s:return
 if s.count(old)!=1:raise ValueError('Unsupported logout source: '+name)
 p.write_text(s.replace(old,new))
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
