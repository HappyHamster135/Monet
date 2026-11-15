// SPDX-License-Identifier: GPL-3.0-or-later
#include "monetgraphics.h"

#include <KLocalizedString>
#include <KPluginFactory>
#include <QJsonDocument>
#include <QJsonObject>

#include <processcore/process.h>
#include <processcore/process_attribute.h>
#include <processcore/processes.h>

#include <algorithm>

using namespace KSysGuard;

static QString helper()
{
    // A test's stand-in; otherwise the one installed with Monet.
    const QByteArray chosen = qgetenv("MONET_GRAPHICS_USE");
    return chosen.isEmpty() ? QStringLiteral(MONET_GRAPHICS_USE) : QString::fromLocal8Bit(chosen);
}

MonetGraphics::MonetGraphics(QObject *parent, const QVariantList &args)
    : ProcessDataProvider(parent, args)
    , m_use(new ProcessAttribute(QStringLiteral("monetGraphics"), i18nd("monet", "Graphics"), this))
{
    m_use->setShortName(i18nd("monet", "Graphics"));
    m_use->setUnit(UnitPercent);
    m_use->setMin(0);
    m_use->setMax(100);
    addProcessAttribute(m_use);
}

MonetGraphics::~MonetGraphics()
{
    stop();
}

void MonetGraphics::handleEnabledChanged(bool enabled)
{
    // Measured only while the column is shown: reading NVIDIA's report can wake a sleeping card.
    if (!enabled) {
        stop();
        return;
    }
    if (m_watch) {
        return;
    }
    m_watch = new QProcess(this);
    m_watch->setProgram(helper());
    m_watch->setArguments({QStringLiteral("--watch")});
    m_watch->setStandardErrorFile(QProcess::nullDevice());
    connect(m_watch, &QProcess::readyReadStandardOutput, this, &MonetGraphics::read);
    m_watch->start();
}

void MonetGraphics::stop()
{
    if (!m_watch) {
        return;
    }
    m_watch->disconnect(this);
    m_watch->kill();
    m_watch->waitForFinished(1000);
    delete m_watch;
    m_watch = nullptr;
    m_latest.clear();
}

void MonetGraphics::read()
{
    while (m_watch && m_watch->canReadLine()) {
        QHash<qlonglong, double> use;
        if (parse(m_watch->readLine(), use)) {
            m_latest = use;
        }
    }
}

bool MonetGraphics::parse(const QByteArray &line, QHash<qlonglong, double> &use)
{
    const QJsonObject result = QJsonDocument::fromJson(line).object();
    if (result.value(QStringLiteral("version")).toInt() != 1) {
        return false;
    }
    const QJsonObject pids = result.value(QStringLiteral("pids")).toObject();
    for (auto it = pids.begin(); it != pids.end(); ++it) {
        bool number = false;
        const qlonglong pid = it.key().toLongLong(&number);
        const double share = it.value().toDouble(-1);
        if (number && pid > 0 && share >= 0) {
            use.insert(pid, std::min(share, 100.0));
        }
    }
    return true;
}

void MonetGraphics::update()
{
    if (!m_watch) {
        return;
    }
    const auto all = processes()->getAllProcesses();
    for (Process *process : all) {
        m_use->setData(process, m_latest.value(process->pid(), 0.0));
    }
}

K_PLUGIN_CLASS_WITH_JSON(MonetGraphics, "monetgraphics.json")

#include "monetgraphics.moc"
