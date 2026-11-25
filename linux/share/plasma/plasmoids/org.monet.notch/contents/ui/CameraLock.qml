import QtQuick
import org.kde.plasma.workspace.dbus as DBus

// The portable desktop can use Plasma's screen locker without Monet's native activity module.
QtObject {
    id: gate
    readonly property string service: "org.freedesktop.ScreenSaver"
    readonly property bool active: lockKnown && !locked
    property bool lockKnown: false
    property bool locked: true
    property DBus.DBusPendingReply pending
    readonly property var owner: DBus.DBusServiceWatcher {
        busType: DBus.BusType.Session
        watchedService: gate.service
        onRegisteredChanged: {
            gate.pending = null
            gate.lockKnown = false
            if (!registered) return
            gate.pending = DBus.SessionBus.asyncCall({service: gate.service, path: "/ScreenSaver",
                iface: gate.service, member: "GetActive"})
            gate.finish()
        }
    }
    readonly property var observer: DBus.SignalWatcher {
        busType: DBus.BusType.Session
        service: gate.service; path: "/ScreenSaver"; iface: gate.service
        function dbusActiveChanged(value) {
            if (!gate.owner.registered) return
            gate.pending = null
            gate.locked = value
            gate.lockKnown = true
        }
    }
    function finish() {
        if (!pending?.isFinished) return
        if (pending.isValid && typeof pending.value === "boolean") {
            locked = pending.value
            lockKnown = true
        }
        pending = null
    }
    readonly property Connections completed: Connections {
        target: gate.pending
        function onFinished() { gate.finish() }
    }
}
