// Lives with the applet so a pending save survives closing the popup or changing tabs.
import QtQuick
import org.kde.plasma.workspace.dbus as DBus

QtObject {
    id: model
    required property bool shown
    property string ident: ""
    property int revision: 0
    property var choices: []
    property string saved: ""
    property string draft: ""
    property string problem: ""
    property bool dirty: false
    property bool refreshNeeded: false
    property string operation: ""
    readonly property bool switching: operation === "new" || operation === "select" || !!nextAction
    property string sent: ""
    property string nextAction: ""
    property string nextId: ""
    property DBus.DBusPendingReply pending
    readonly property var autosave: Timer { interval: 240; onTriggered: model.flush() }
    readonly property var response: Connections {
        target: model.pending
        function onFinished() { model.finish() }
    }
    readonly property var changes: DBus.SignalWatcher {
        busType: DBus.BusType.Session; service: "org.monet.Utilities"
        path: "/Scratchpad"; iface: "org.monet.Utilities"
        function dbusPadsChanged() {
            if (!model.shown || model.pending || model.dirty) model.refreshNeeded = true
            else model.send("view", model.ident)
        }
    }

    function call(member, payload) {
        return DBus.SessionBus.asyncCall({service: "org.monet.Utilities", path: member === "Pad" ? "/Scratchpad" : "/Utilities",
            iface: "org.monet.Utilities", member: member, signature: "(s)", arguments: [JSON.stringify(payload)]})
    }
    function send(action, id) {
        operation = action
        sent = draft
        pending = call("Pad", {action: action, id: id, revision: revision, value: action === "save" ? sent : ""})
        if (pending.isFinished) finish()
    }
    function finish() {
        if (!pending || !pending.isFinished) return
        let data = {}
        try { if (pending.isValid) data = JSON.parse(String(pending.value)) } catch (e) {}
        const action = operation
        operation = ""
        pending = null
        if (!data.ok) {
            problem = i18n("Could not save or load this pad. Your text is still in the editor.")
            nextAction = ""
            return
        }
        // While reading the current pad another window can update it and a user can start typing.
        // Keep the original revision/draft until their edit has been committed.
        if (action !== "view" || !dirty) {
            choices = data.pads
            ident = data.pad.id
            revision = data.pad.revision
            saved = data.pad.body
            if (action !== "save" || sent === draft) draft = saved
            dirty = draft !== saved
        }
        problem = data.recovered ? i18n("This pad changed in another window. Your edits were saved in a separate pad.") : ""
        if (dirty) { flush(); return }
        if (nextAction) {
            const next = nextAction, id = nextId
            nextAction = ""
            select(next, id)
        } else if (shown && refreshNeeded) {
            refreshNeeded = false
            send("view", ident)
        }
    }
    function edit(text) {
        if (draft === text) return
        draft = text
        dirty = draft !== saved
        problem = ""
        autosave.restart()
    }
    function flush() {
        autosave.stop()
        if (!pending && dirty && ident) send("save", ident)
    }
    function select(action, id) {
        if (pending || dirty) {
            nextAction = action
            nextId = id || ""
            flush()
            return
        }
        if (action === "float") {
            call("Present", ["floating-pad", ident])
            detached()
        } else {
            send(action, id || "")
        }
    }
    function refresh() {
        if (pending || dirty) { refreshNeeded = true; flush() }
        else send("view", ident)
    }
    signal detached()
    Component.onCompleted: refresh()
    onShownChanged: {
        if (shown && ident) refresh()
        if (!shown) flush()
    }
    Component.onDestruction: {
        // The popup may disappear between the last keystroke and its debounce.
        if (dirty && ident && (operation !== "save" || draft !== sent))
            call("Pad", {action: "save", id: ident, revision: revision, value: draft})
    }
}
