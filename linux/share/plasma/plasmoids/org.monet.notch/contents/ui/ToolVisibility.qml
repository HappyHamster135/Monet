import QtQuick
import QtCore as Core
import org.kde.plasma.workspace.dbus as DBus

// Read the catalogue without starting Utilities, including on a fresh login.
QtObject {
    id: tools
    property var hidden: []
    property var favorites: []
    property var radial: []
    property bool ready: false
    readonly property var desktopApplications: ["files","trash","appimage","apps","homebrew","store","updates","storage","processes","remap","shortcuts","paste-shortcut","rename-shortcut","debounce","quick-panel","empty-trash"]
    function offers(key) { return ready && !hidden.includes(key) && !desktopApplications.includes(key) }
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
        try { saved = JSON.parse(settings.value("favorites", '["screenshot","record","ocr","color","plain","clean","emoji","snippets","compress","mic","output","lock"]')) } catch (_) {}
        if (Array.isArray(saved) && JSON.stringify(favorites) !== JSON.stringify(saved)) favorites = saved
        let ring = ["screenshot","record","color","text-tools","emoji","snippets","mic","awake"]
        try { const value = JSON.parse(settings.value("notchRadial",JSON.stringify(ring))); if (Array.isArray(value)) ring=value.slice(0,8) } catch (_) {}
        while (ring.length<8) ring.push("")
        ring=ring.map(key => typeof key === "string" && !["wheel","wheel-settings","notch-settings","quick-panel"].includes(key) && !hidden.includes(key) && !desktopApplications.includes(key) ? key : "")
        if (JSON.stringify(radial)!==JSON.stringify(ring)) radial=ring
        ready = true
    }
    Component.onCompleted: reload()
}
