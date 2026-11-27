import QtQuick
import QtCore as Core
import org.kde.plasma.plasma5support as P5

QtObject {
    id: history
    required property bool presented
    property string reader: "/usr/bin/python3 '@DATADIR@/monet/utilities/agent_history.py'"
    property var result: ({})
    property string period: "today"
    property bool pending: false
    property bool failed: false
    property real lastAttempt: 0
    readonly property var reading: result.periods?.[period] || ({})
    readonly property var total: reading.total || ({})
    readonly property Core.Settings cache: Core.Settings {
        location: Core.StandardPaths.writableLocation(Core.StandardPaths.GenericCacheLocation) + "/monet/notch-agent-history.conf"
    }
    function tokens(value) {
        if (!Number.isFinite(value)) return "—"
        const units = value >= 1e9 ? [1e9,"B"] : value >= 1e6 ? [1e6,"M"] : value >= 1e3 ? [1e3,"K"] : [1,""]
        return (value/units[0]).toLocaleString(Qt.locale(), "f", units[0] === 1 ? 0 : 1) + units[1]
    }
    function money(value) { return Number.isFinite(value) ? "$" + value.toLocaleString(Qt.locale(), "f", 2) : "—" }
    function cost(row) {
        return !row || !Number.isFinite(row.cost) || (row.requests > 0 && row.unpriced === row.requests) ? "—" : money(row.cost) + (row.unpriced ? "+" : "")
    }
    function refresh(force = false) {
        if (!presented || pending || (!force && Date.now()-lastAttempt < 30000)) return
        pending = true
        source.connectSource(reader)
    }
    function accept(output) {
        pending = false; lastAttempt = Date.now()
        let next = null
        try { next = JSON.parse(output) } catch (_) {}
        failed = !next?.ok || !next.periods
        if (failed) return // Keep the last complete snapshot visible.
        result = next
        cache.setValue("reading", JSON.stringify(next)); cache.sync()
    }
    Component.onCompleted: {
        try { const saved = JSON.parse(cache.value("reading", "{}")); if (saved.ok && saved.periods) result = saved } catch (_) {}
        const savedPeriod = cache.value("period", "today")
        if (["today","week","month"].includes(savedPeriod)) period = savedPeriod
        Qt.callLater(refresh)
    }
    onPeriodChanged: { cache.setValue("period", period); cache.sync() }
    onPresentedChanged: if (presented) Qt.callLater(refresh)
    readonly property Timer updates: Timer { interval: 30000; repeat: true; running: history.presented; onTriggered: history.refresh() }
    readonly property P5.DataSource source: P5.DataSource {
        engine: "executable"; connectedSources: []
        onNewData: (command, data) => { disconnectSource(command); history.accept(data.stdout) }
    }
}
