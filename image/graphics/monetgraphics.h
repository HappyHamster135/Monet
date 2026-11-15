// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once

#include <QHash>
#include <QProcess>

#include <processcore/process_data_provider.h>

namespace KSysGuard
{
class ProcessAttribute;
}

// The Graphics column of Task Manager's Applications and Processes: each program's share
// of the graphics card, read from monet-graphics-use --watch while the column is in view
// (KDE adds a program's processes up for its application row).
class MonetGraphics : public KSysGuard::ProcessDataProvider
{
    Q_OBJECT

public:
    MonetGraphics(QObject *parent, const QVariantList &args);
    ~MonetGraphics() override;

    void handleEnabledChanged(bool enabled) override;
    void update() override;

    // One line from the helper, {"version": 1, "pids": {"123": 4.5}}, into use. False if it isn't one.
    static bool parse(const QByteArray &line, QHash<qlonglong, double> &use);

private:
    void read();
    void stop();

    KSysGuard::ProcessAttribute *m_use;
    QProcess *m_watch = nullptr;
    QHash<qlonglong, double> m_latest;
};
