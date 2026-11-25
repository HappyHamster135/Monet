import QtQuick
import org.kde.plasma.workspace.dbus as DBus

QtObject {
    id: shelf
    required property bool shown
    required property bool dragging
    property var rows: []
    property string message: ""
    signal filesAdded()
    property var pendingRequest: null
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
        if (!(event.supportedActions & Qt.CopyAction) || dragging
                || event.formats.includes("application/x-monet-shelf-drag")) return false
        if (!event.hasUrls) return event.hasText
        return event.urls.length > 0 && event.urls.length <= 100 && event.urls.every(u =>
            String(u).startsWith("file:///") || /^https?:\/\//i.test(String(u)))
    }
    function addDrop(event) {
        if (!accepts(event)) return false
        if (event.hasUrls) change({action: "add", urls: Array.from(event.urls, u => String(u))})
        else {
            const text = event.text
            if (!text.trim() || text.includes("\0")) return false
            change({action: "add", text: text})
        }
        event.accept(Qt.CopyAction)
        return true
    }
    function change(request) {
        queue.push(request)
        message = ""
        dispatch()
    }
    function refresh() { needsView = true; dispatch() }
    function dispatch() {
        if (pending || !(queue.length || (needsView && shown && !dragging))) return
        const request = queue.shift() || {action: "view"}
        needsView = false
        request.version = 2
        pendingRequest = request
        pending = DBus.SessionBus.asyncCall({service: "org.monet.Utilities", path: "/FileShelf",
            iface: "org.monet.Utilities", member: "Shelf", signature: "(s)", arguments: [JSON.stringify(request)]})
        if (pending.isFinished) finish()
    }
    function finish() {
        if (!pending || !pending.isFinished) return
        let data = {}
        try { if (pending.isValid) data = JSON.parse(String(pending.value)) } catch (_) {}
        // The shell and an already-open Utilities window can update at different times.
        // Older receivers understand file URLs and omit version, kind and key.
        const richAdd = pendingRequest.action === "add" && (pendingRequest.text !== undefined
            || (pendingRequest.urls || []).some(url => !url.startsWith("file:///")))
        const unsupported = richAdd && Array.isArray(data.rows) && data.version !== 2
        if (Array.isArray(data.rows) && data.version !== 2) {
            for (const row of data.rows) { row.key = row.url; row.kind = "file" }
        }
        if (unsupported) {
            message = i18n("Reopen Utilities to use text and links on the shelf.")
        } else if (!Array.isArray(data.rows)) {
            message = i18n("Could not update the file shelf.")
        } else if (shown) {
            // Keep the source delegate alive until the other app finishes reading its drag.
            if (dragging) needsView = true
            else if (data.rows.length !== rows.length || data.rows.some((row, i) =>
                    row.key !== rows[i].key || row.icon !== rows[i].icon || row.name !== rows[i].name)) rows = data.rows
            if (data.missing) message = i18n("Some files are no longer available.")
        }
        if (pendingRequest.action === "add" && !unsupported && Array.isArray(data.rows) && !data.missing) filesAdded()
        pendingRequest = null
        pending = null
        dispatch()
    }
    onDraggingChanged: if (!dragging) dispatch()
    onShownChanged: {
        if (shown) { message = ""; refresh() }
        else { rows = []; needsView = false }
    }
}
