// SPDX-License-Identifier: GPL-3.0-or-later
import QtQuick
import QtCore
import org.kde.kwin

Item {
    id: root
    Settings {
        id: config
        location: StandardPaths.writableLocation(StandardPaths.ConfigLocation) + "/monet/quit-on-close.conf"
    }
    function id(value) {
        return String(value || "").split("/").pop().replace(/\.desktop$/i, "").toLowerCase()
    }
    function rules() {
        config.sync()
        try {
            const result = JSON.parse(config.value("applications", "{}"))
            return result && typeof result === "object" && !Array.isArray(result) ? result : {}
        } catch (_) { return {} }
    }
    function matches(w, desktop, aliases) {
        const reported = id(w.desktopFileName)
        if (reported) return reported === id(desktop) || aliases.includes(reported)
        const klass = id(w.resourceClass)
        return klass === id(desktop) || aliases.includes(klass)
    }
    function remaining(desktop, aliases, pid) {
        return Workspace.stackingOrder.filter(w => !w.deleted && w.managed && (w.normalWindow || w.dialog)
            && (w.pid === pid || matches(w, desktop, aliases)))
    }
    // Minimized windows and windows on another desktop still count. A closing
    // dialog, splash or utility window cannot initiate an application quit.
    function removed(w) {
        if (!w || !w.managed) return
        if (w.transient || w.dialog) {
            for (const req of Object.values(pending)) {
                if (req.waitingForDialog) req.restart()
            }
            return
        }
        if (!w.normalWindow || w.skipTaskbar || w.pid <= 1) return
        const selected = rules()
        const keys = Object.keys(selected).filter(k => Array.isArray(selected[k]) && matches(w, k, selected[k]))
        if (keys.length !== 1) return
        const desktop = keys[0], pid = w.pid
        if (remaining(desktop, selected[desktop], pid).some(other => other !== w && !other.dialog && !other.transient)) return
        const key = JSON.stringify([desktop, pid])
        if (pending[key]) pending[key].finish()
        const request = decision.createObject(root, { desktop, pid, key, closedAt: Date.now() })
        pending[key] = request
        request.start()
    }
    property var pending: Object.create(null)
    Connections { target: Workspace; function onWindowRemoved(window) { root.removed(window) } }
    Component {
        id: decision
        Timer {
            id: candidate
            required property string desktop
            required property int pid
            required property string key
            required property double closedAt
            property bool waitingForDialog: false
            function ready() {
                const aliases = root.rules()[desktop]
                const windows = Array.isArray(aliases) ? root.remaining(desktop, aliases, pid) : []
                if (root.pending[key] !== candidate || !Array.isArray(aliases) || windows.some(w => !w.dialog && !w.transient)) {
                    finish()
                    return false
                }
                // A save dialog can outlive the main window. Resume only when
                // a dialog closes, then re-check every window on every desktop.
                waitingForDialog = windows.length > 0
                return !waitingForDialog
            }
            function finish() {
                if (root.pending[key] === candidate) delete root.pending[key]
                stop()
                destroy()
            }
            interval: 400
            onTriggered: if (ready()) prepare.call()
            property DBusCall prepare: DBusCall {
                service: "org.monet.QuitOnClose"
                path: "/org/monet/QuitOnClose"
                dbusInterface: "org.monet.QuitOnClose"
                method: "Prepare"
                arguments: [candidate.desktop, String(candidate.pid), String(candidate.closedAt)]
                onFinished: values => {
                    if (!values[0]) candidate.finish()
                    else if (candidate.ready()) {
                        confirm.arguments = [values[0]]
                        confirm.call()
                    }
                }
                onFailed: candidate.finish()
            }
            property DBusCall confirm: DBusCall {
                service: "org.monet.QuitOnClose"
                path: "/org/monet/QuitOnClose"
                dbusInterface: "org.monet.QuitOnClose"
                method: "Confirm"
                onFinished: candidate.finish()
                onFailed: candidate.finish()
            }
        }
    }
}
