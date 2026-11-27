import QtQuick
import QtQuick.Controls as C
import org.kde.plasma.workspace.dbus as DBus

IslandStatusRow {
    id: button
    required property string widgetId
    required property bool active
    property bool subscribed: false
    property bool ready: false
    property string reading: ""

    visible: active
    text: reading ? reading.replace(/\n/g, " · ") : i18n("Session file")
    Accessible.name: text


    heading: i18n("Local session")
    subtitle: text
    symbol: "code"; accent: "#c5b7e6"
    connected: !!reading

    DBus.SignalWatcher {
        enabled: button.active
        busType: DBus.BusType.Session
        service: "org.monet.Utilities"; path: "/AgentSession"; iface: "org.monet.Utilities"
        function dbusSessionChanged(value) { if (button.active) button.reading = value }
    }

    DBus.DBusServiceWatcher {
        busType: DBus.BusType.Session
        watchedService: button.active ? "org.monet.Utilities" : ""
        onRegisteredChanged: {
            if (registered && button.subscribed) button.request(true)
        }
    }

    function subscribe(on) {
        if (!ready || on === subscribed) return
        subscribed = on
        request(on)
    }
    function request(on) {
        DBus.SessionBus.asyncCall({service: "org.monet.Utilities", path: "/AgentSession",
            iface: "org.monet.Utilities", member: "Watch", signature: "(sb)", arguments: [widgetId, on]})
    }
    onActiveChanged: subscribe(active)
    Component.onCompleted: { ready = true; subscribe(active) }
    Component.onDestruction: subscribe(false)
}
