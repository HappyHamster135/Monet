import QtQuick
import org.kde.plasma.workspace.dbus as DBus

// Observe the existing session by its unique bus name. Only a user action may
// start the service, even if it exits between a registration event and a read.
QtObject {
    id: awake
    readonly property string service: "org.monet.KeepAwake"
    readonly property string path: "/org/monet/KeepAwake"
    property string owner: ""
    property var state: ({})
    property double receivedAt: 0
    readonly property double endTime: state.duration > 0 ? receivedAt + state.remaining * 1000 : 0
    property bool failed: false
    readonly property bool active: state.active === true
    readonly property int minutes: Math.ceil((state.remaining || 0) / 60)
    readonly property string compactText: state.duration > 0 ? i18n("%1 min", minutes) : i18n("Awake")
    readonly property string statusText: failed || state.error ? i18n("Keep awake is unavailable. Choose a duration to try again.")
        : !active ? i18n("Uses your screen, lock and sleep settings")
        : state.duration === 0 ? i18n("An automatic rule is keeping this PC awake")
        : state.indefinite ? i18n("Until turned off or you sign out") : i18n("%1 min remaining", minutes)
    property DBus.DBusPendingReply read
    property DBus.DBusPendingReply write
    readonly property bool busy: !!write

    readonly property DBus.DBusServiceWatcher registration: DBus.DBusServiceWatcher {
        busType: DBus.BusType.Session; watchedService: awake.service
        onRegisteredChanged: {
            awake.read = null
            awake.owner = ""
            awake.state = {}
            minute.stop()
            if (registered) awake.lookup()
        }
    }
    function lookup() {
        read = DBus.SessionBus.asyncCall({service: "org.freedesktop.DBus", path: "/org/freedesktop/DBus",
            iface: "org.freedesktop.DBus", member: "GetNameOwner", signature: "(s)", arguments: [service]})
        finishRead()
    }
    function refresh() {
        if (!owner || read) return
        read = DBus.SessionBus.asyncCall({service: owner, path: path, iface: service, member: "GetStatus"})
        finishRead()
    }
    function finishRead() {
        if (!read?.isFinished) return
        const reply = read
        read = null
        if (!reply.isValid) return
        if (!owner) {
            owner = String(reply.value)
            refresh()
        } else receive(reply.value)
    }
    readonly property Connections readFinished: Connections {
        target: awake.read
        function onFinished() { awake.finishRead() }
    }
    function receive(value) {
        let next
        try { next = JSON.parse(value) } catch (_) { return }
        if (typeof next?.active !== "boolean") return
        failed = false
        receivedAt = Date.now()
        state = next
        minute.stop()
        if (active && next.duration > 0 && next.remaining > 0) {
            minute.interval = ((next.remaining - 1) % 60 + 1) * 1000
            minute.start()
        }
    }
    readonly property Timer minuteTick: Timer {
        id: minute
        onTriggered: awake.refresh()
    }
    readonly property DBus.SignalWatcher changes: DBus.SignalWatcher {
        busType: DBus.BusType.Session; service: awake.service; path: awake.path; iface: awake.service
        function dbusStatusChanged(value) {
            if (awake.owner) awake.read = null
            awake.receive(value)
        }
    }
    function setDuration(seconds) {
        if (busy || (seconds === 0 && !state.duration)) return
        failed = false
        write = DBus.SessionBus.asyncCall({service: service, path: path, iface: service, member: "SetDuration",
            signature: "(i)", arguments: [seconds]})
        finishWrite()
    }
    function finishWrite() {
        if (!write?.isFinished) return
        const reply = write
        write = null
        // StatusChanged reports the ordered session state to every notch.
        // A reply can outlive that state if another client already changed it.
        try { failed = !reply.isValid || !JSON.parse(reply.value).ok } catch (_) { failed = true }
    }
    readonly property Connections writeFinished: Connections {
        target: awake.write
        function onFinished() { awake.finishWrite() }
    }
}
