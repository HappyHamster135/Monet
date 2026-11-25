import QtQuick
import QtQuick.Controls as C
import org.kde.plasma.workspace.dbus as DBus

C.ToolButton {
    id: button
    required property string widgetId
    required property bool active
    property bool subscribed: false
    property bool ready: false
    property string reading: ""

    visible: active
    text: reading ? reading.replace(/\n/g, " · ") : i18n("Session file")
    Accessible.name: text
    C.ToolTip.visible: hovered && !!reading
    C.ToolTip.text: reading
    contentItem: C.Label {
        text: button.text
        textFormat: Text.PlainText
        elide: Text.ElideRight
        verticalAlignment: Text.AlignVCenter
    }

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
            if (!registered) button.reading = ""
            else if (button.subscribed) button.request(true)
        }
    }

    function subscribe(on) {
        if (!ready || on === subscribed) return
        subscribed = on
        reading = ""
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
