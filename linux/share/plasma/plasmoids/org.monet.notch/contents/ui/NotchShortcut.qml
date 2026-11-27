import QtQuick
import org.kde.plasma.workspace.dbus as DBus

QtObject {
    id: shortcut
    required property string ownerId
    signal requested(string command)
    readonly property DBus.SignalWatcher watcher: DBus.SignalWatcher {
        busType: DBus.BusType.Session; service: "org.monet.Utilities"
        path: "/NotchShortcuts"; iface: "org.monet.Utilities"
        function dbusNotchShortcut(widgetId, action) {
            // The desktop watcher delivers boxed QVariant strings.
            const command = String(action)
            if (String(widgetId) === shortcut.ownerId && command === "toggle")
                shortcut.requested(command)
        }
    }
}
