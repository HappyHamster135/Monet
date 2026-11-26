import QtQuick
import QtCore as Core
import org.kde.plasma.workspace.dbus as DBus

// Read the catalogue without starting Utilities, including on a fresh login.
QtObject {
    id: tools
    property var hidden: []
    property var favorites: []
    property bool ready: false
    function offers(key) { return ready && !hidden.includes(key) }
    readonly property Core.Settings settings: Core.Settings {
        location: Core.StandardPaths.writableLocation(Core.StandardPaths.GenericConfigLocation) + "/Monet/Utilities.conf"
    }
    readonly property DBus.SignalWatcher changes: DBus.SignalWatcher {
        busType: DBus.BusType.Session; service: "org.monet.Utilities"
        path: "/Utilities"; iface: "org.monet.Utilities"
        function dbusToolVisibilityChanged() { tools.reload() }
    }
    function reload() {
        settings.sync()
        let keys = []
        try {
            const value = JSON.parse(settings.value("hidden", "[]"))
            if (Array.isArray(value)) keys = value.filter(k => typeof k === "string")
        } catch (_) {}
        if (JSON.stringify(keys) !== JSON.stringify(hidden)) hidden = keys
        let saved = []
        try { saved = JSON.parse(settings.value("favorites", '["shelf","notes","screenshot","color","awake","sound"]')) } catch (_) {}
        if (Array.isArray(saved) && JSON.stringify(favorites) !== JSON.stringify(saved)) favorites = saved
        ready = true
    }
    Component.onCompleted: reload()
}
