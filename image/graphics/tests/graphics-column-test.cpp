// SPDX-License-Identifier: GPL-3.0-or-later
// Task Manager's Graphics column end to end, through KDE's own process model: the plugin
// loads and names its column, each process shows the share the helper reports for it, and
// the helper stops once the column is no longer shown.
#include <QCoreApplication>
#include <QElapsedTimer>
#include <QFile>
#include <QThread>

#include <processcore/process_data_model.h>

#include <cmath>
#include <cstdio>
#include <functional>
#include <signal.h>

static bool waitFor(const std::function<bool()> &test, int milliseconds)
{
    QElapsedTimer timer;
    timer.start();
    while (timer.elapsed() < milliseconds) {
        if (test()) {
            return true;
        }
        QCoreApplication::processEvents(QEventLoop::AllEvents, 50);
        QThread::msleep(20);
    }
    return test();
}

static int fail(const char *what)
{
    std::fprintf(stderr, "FAIL: %s\n", what);
    return 1;
}

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    const QString column = QStringLiteral("monetGraphics");
    KSysGuard::ProcessDataModel model;
    model.setFlatList(true);
    if (!model.availableAttributes().contains(column)) {
        return fail("the plugin didn't load: no monetGraphics attribute");
    }
    model.setEnabledAttributes({QStringLiteral("pid"), column});
    model.setEnabled(true);
    const QString title = model.headerData(1, Qt::Horizontal, Qt::DisplayRole).toString();
    if (title != QStringLiteral("Graphics")) {
        std::fprintf(stderr, "title: %s\n", qPrintable(title));
        return fail("the column's title");
    }
    const qlonglong self = QCoreApplication::applicationPid();
    const auto share = [&](qlonglong pid) {
        for (int row = 0; row < model.rowCount(); ++row) {
            if (model.data(model.index(row, 0), KSysGuard::ProcessDataModel::Value).toLongLong() == pid) {
                return model.data(model.index(row, 1), KSysGuard::ProcessDataModel::Value).toDouble();
            }
        }
        return -1.0;
    };
    if (!waitFor([&] { return std::abs(share(self) - 42.5) < 0.01; }, 15000)) {
        std::fprintf(stderr, "this process: %f\n", share(self));
        return fail("this process's share, as the helper reports it");
    }
    // A process the helper doesn't name has none.
    if (std::abs(share(1)) > 0.0001 && share(1) != -1.0) {
        std::fprintf(stderr, "pid 1: %f\n", share(1));
        return fail("a process the helper doesn't name");
    }
    // The column taken away: the helper stops.
    QFile said(qEnvironmentVariable("MONET_GRAPHICS_PIDFILE"));
    if (!said.open(QIODevice::ReadOnly)) {
        return fail("the stand-in helper didn't say who it is");
    }
    const pid_t helper = said.readAll().trimmed().toInt();
    model.setEnabledAttributes({QStringLiteral("pid")});
    if (helper <= 0 || !waitFor([&] { return kill(helper, 0) != 0; }, 5000)) {
        return fail("the helper still runs with the column gone");
    }
    std::printf("Graphics column: plugin, title, each process's share and stopping all work\n");
    return 0;
}
