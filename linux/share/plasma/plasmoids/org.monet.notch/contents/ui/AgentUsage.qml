import QtQuick
import QtCore as Core
import org.kde.plasma.plasma5support as P5
import org.kde.plasma.workspace.dbus as DBus

// Cache usage values for one opted-in account; credentials remain with its CLI.
QtObject {
    id: usage
    required property string provider
    required property bool presented
    property string reader: "/usr/bin/python3 '@DATADIR@/monet/utilities/notch_agents.py'"
    property string generation: ""
    readonly property bool enabled: generation.length > 0
    property var result: ({})
    property string problem: ""
    property string pending: ""
    property string pendingAction: ""
    property real lastAttempt: 0
    property bool ready: false
    signal settingsChanged()
    readonly property Core.Settings preferences: Core.Settings {
        location: Core.StandardPaths.writableLocation(Core.StandardPaths.GenericConfigLocation) + "/Monet/Utilities.conf"
    }
    readonly property Core.Settings cache: Core.Settings {
        location: Core.StandardPaths.writableLocation(Core.StandardPaths.GenericCacheLocation) + "/monet/notch-agent-usage.conf"
        category: usage.provider
    }
    function reloadConfiguration() {
        preferences.sync()
        let hidden = []
        try { const value = JSON.parse(preferences.value("hidden", "[]")); if (Array.isArray(value)) hidden = value } catch (_) {}
        const saved = String(preferences.value(provider + "Limits", ""))
        const key = !hidden.includes("agents") && /^[a-f0-9]{32}$/.test(saved) ? saved : ""
        if (!ready || key !== generation) {
            generation = key; result = ({}); problem = ""; lastAttempt = 0
            let savedReading = null
            try { savedReading = JSON.parse(cache.value("reading", "{}")) } catch (_) {}
            if (key && savedReading?.generation === key && savedReading?.result?.state === "ready") {
                result = savedReading.result
                lastAttempt = Math.min(Date.now(), Number(savedReading.savedAt) || 0)
            } else { cache.setValue("reading", "{}"); cache.sync() }
        }
        ready = true
    }
    function refreshIfNeeded() {
        if (!presented) return
        reloadConfiguration()
        if (enabled && Date.now() - lastAttempt >= 60000) read("read")
    }
    function read(action, extra = "") {
        if (!presented || pending) return
        pendingAction = action
        pending = reader + " " + provider + " " + action + (extra ? " " + extra : "")
        source.connectSource(pending)
    }
    function accept(command, output) {
        if (pending !== command) return
        const action = pendingAction
        pending = ""; pendingAction = ""
        reloadConfiguration()
        let next = null
        try { next = JSON.parse(output) } catch (_) {}
        lastAttempt = Date.now()
        if (!next?.ok) problem = i18n("Could not update. Showing the last known usage.")
        else if (!enabled || next.generation !== generation) {
            if (enabled) { lastAttempt = 0; Qt.callLater(refreshIfNeeded) }
        } else if (next.state === "ready") {
            result = next; problem = ""
            cache.setValue("reading", JSON.stringify({generation:generation, result:next, savedAt:Date.now()}))
            cache.sync()
        } else if (result.state === "ready" && ["unavailable", "missing", "outdated"].includes(next.state)) {
            problem = next.details || i18n("Could not update. Showing the last known usage.")
        } else {
            result = next; problem = ""
            cache.setValue("reading", "{}"); cache.sync()
        }
        if (action !== "read") settingsChanged()
    }
    Component.onCompleted: { reloadConfiguration(); refreshIfNeeded() }
    onPresentedChanged: if (presented && ready) Qt.callLater(refreshIfNeeded)
    readonly property Timer refreshTimer: Timer {
        interval: 60000; repeat: true; running: usage.presented && usage.enabled
        onTriggered: usage.refreshIfNeeded()
    }
    readonly property P5.DataSource source: P5.DataSource {
        engine: "executable"; connectedSources: []
        onNewData: (command, data) => { disconnectSource(command); usage.accept(command, data.stdout) }
    }
    readonly property DBus.SignalWatcher changes: DBus.SignalWatcher {
        busType: DBus.BusType.Session; service: "org.monet.Utilities"
        path: "/Utilities"; iface: "org.monet.Utilities"
        function dbusCodexLimitsChanged() { if (usage.provider === "codex") { usage.reloadConfiguration(); usage.refreshIfNeeded() } }
        function dbusClaudeLimitsChanged() { if (usage.provider === "claude") { usage.reloadConfiguration(); usage.refreshIfNeeded() } }
        function dbusAgentVisibilityChanged() { usage.reloadConfiguration(); usage.refreshIfNeeded() }
    }
}
