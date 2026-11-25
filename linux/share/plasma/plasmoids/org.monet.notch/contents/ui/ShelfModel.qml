import QtQuick
import org.kde.plasma.workspace.dbus as DBus

QtObject {
    id: shelf
    required property bool shown
    required property bool dragging
    property var rows: []
    property string message: ""
    signal filesAdded()
    property string pendingAction: ""
    property var queue: []
    property bool needsView: false
    property DBus.DBusPendingReply pending
    readonly property var finished: Connections {
        target: shelf.pending
        function onFinished() { shelf.finish() }
    }
    readonly property var changes: DBus.SignalWatcher {
        enabled: shelf.shown
        busType: DBus.BusType.Session; service: "org.monet.Utilities"
        path: "/FileShelf"; iface: "org.monet.Utilities"
        function dbusShelfChanged() { shelf.refresh() }
    }

    // Utilities exits when idle. Rejoin a new instance if the shelf is still on screen.
    readonly property var service: DBus.DBusServiceWatcher {
        busType: DBus.BusType.Session
        watchedService: shelf.shown ? "org.monet.Utilities" : ""
        onRegisteredChanged: if (registered && shelf.shown) shelf.refresh()
    }

    function accepts(event) {
        return (event.supportedActions & Qt.CopyAction) && event.hasUrls && event.urls.length > 0
            && event.urls.length <= 100 && event.urls.every(u => String(u).startsWith("file:///"))
    }
    function change(action, urls) {
        queue.push({action: action, urls: urls.map(u => String(u))})
        message = ""
        dispatch()
    }
    function refresh() { needsView = true; dispatch() }
    function dispatch() {
        if (pending || !(queue.length || (needsView && shown && !dragging))) return
        const request = queue.shift() || {action: "view"}
        needsView = false
        pendingAction = request.action
        pending = DBus.SessionBus.asyncCall({service: "org.monet.Utilities", path: "/FileShelf",
            iface: "org.monet.Utilities", member: "Shelf", signature: "(s)", arguments: [JSON.stringify(request)]})
        if (pending.isFinished) finish()
    }
    function finish() {
        if (!pending || !pending.isFinished) return
        let data = {}
        try { if (pending.isValid) data = JSON.parse(String(pending.value)) } catch (_) {}
        if (!Array.isArray(data.rows)) {
            message = i18n("Could not update the file shelf.")
        } else if (shown) {
            // Keep the source delegate alive until the other app finishes reading its drag.
            if (dragging) needsView = true
            else if (JSON.stringify(data.rows) !== JSON.stringify(rows)) rows = data.rows
            if (data.missing) message = i18n("Some files are no longer available.")
        }
        if (pendingAction === "add" && Array.isArray(data.rows) && !data.missing) filesAdded()
        pendingAction = ""
        pending = null
        dispatch()
    }
    onDraggingChanged: if (!dragging) dispatch()
    onShownChanged: {
        if (shown) { message = ""; refresh() }
        else { rows = []; needsView = false }
    }
}
