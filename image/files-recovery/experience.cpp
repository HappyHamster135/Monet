// SPDX-License-Identifier: GPL-3.0-or-later
#include "experience.h"
#include <QProcess>
#include <QStandardPaths>

void DolphinMainWindow::setupMonetFiles()
{
    auto preview = [this] {
        if (!m_activeViewContainer) return;
        const auto state = m_activeViewContainer->view()->monetViewState();
        const auto selected = state.value(QStringLiteral("selected")).toArray();
        const auto path = selected.isEmpty() ? state.value(QStringLiteral("current")).toString() : selected.first().toString();
        const auto helper = QStandardPaths::findExecutable(QStringLiteral("monet-files"));
        if (!path.isEmpty() && !helper.isEmpty()) {
            // KIO carries the user's Wayland activation token to the preview.
            auto job = new KIO::CommandLauncherJob(helper, {QStringLiteral("preview"), path}, this);
            KJobWidgets::setWindow(job, this);
            job->start();
        }
    };
    // One filter suffices when several main windows share a process. Use the
    // active main window rather than a captured first window that may close.
    static bool installed = false;
    if (!installed) {
        installed = true;
        new MonetFilesExperience(qApp, [] {
            if (auto window = qobject_cast<DolphinMainWindow *>(QApplication::activeWindow())) {
                if (auto action = window->actionCollection()->action(QStringLiteral("monet_preview"))) action->trigger();
            }
        });
    }
    auto action = actionCollection()->addAction(QStringLiteral("monet_preview"));
    action->setText(i18nd("monet", "Quick preview"));
    action->setIcon(QIcon::fromTheme(QStringLiteral("document-preview")));
    connect(action, &QAction::triggered, this, preview);
    auto transfers = actionCollection()->addAction(QStringLiteral("monet_transfers"));
    transfers->setText(i18nd("monet", "Transfers"));
    transfers->setIcon(QIcon::fromTheme(QStringLiteral("folder-download")));
    connect(transfers, &QAction::triggered, this, [] {
        const auto helper = QStandardPaths::findExecutable(QStringLiteral("monet-files"));
        if (!helper.isEmpty()) QProcess::startDetached(helper, {QStringLiteral("transfers")});
    });
}
