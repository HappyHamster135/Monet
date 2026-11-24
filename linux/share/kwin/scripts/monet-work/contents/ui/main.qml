/*
 * Monet Work: says when the windows change, so Monet keeps a recent picture of your work (which
 * apps, on which screen and desktop, where, how big) to open again after a restart, a sign-out,
 * a crash or a power cut. monet-work.service does the looking (monet-resume's KWin snapshot);
 * this only says "something changed", at most once a second, and which window closed, by
 * KWin's id for it. Never a title or anything a window shows.
 *
 * And for games first (monet-priority.service), which windows are in front, by their process:
 * the active one, and any full screen on another screen, said as it changes, so the service
 * never has to ask KWin.
 */
import QtQuick
import org.kde.kwin

Item {
    id: root
    WindowPlacement { id: placement }

    // The windows Monet reopens: an app's own, in the taskbar, with a menu entry.
    function tracked(w) {
        return w && w.normalWindow && !w.skipTaskbar && !w.transient && (w.desktopFileName || /^[\w.+-]{1,255}$/.test(String(w.resourceClass || "")))
    }
    // Moves and resizes arrive in a stream while a window is dragged: one word a second at most.
    function changed() {
        if (!settle.running) settle.start()
    }
    function watch(w) {
        if (!tracked(w) || w.deleted) return
        for (const signal of [w.frameGeometryChanged, w.desktopsChanged, w.minimizedChanged, w.maximizedChanged,
                              w.fullScreenChanged, w.outputChanged, w.keepAboveChanged, w.keepBelowChanged])
            signal.connect(root.changed)
    }
    function added(w) {
        placement.add(w, true)
        root.watch(w)
        if (root.tracked(w)) root.changed()
    }
    // Right away, so a window closed just before a restart stays closed: monet-work stops
    // listening to closes the moment a restart, shutdown or sign-out begins.
    function removed(w) {
        if (root.tracked(w)) {
            closed.arguments = [String(w.internalId)]
            closed.call()
        }
        placement.remove(w)
    }

    // What's in front, a moment after it changes, and only when it has: {active, full}, process ids.
    property string front: ""
    function inFront() {
        if (!frontSettle.running) frontSettle.start()
    }
    function shown(w) {
        return w && w.normalWindow && !w.deleted && !w.minimized
            && (w.onAllDesktops || w.desktops.indexOf(Workspace.currentDesktop) >= 0)
    }
    function sayFront() {
        const active = root.shown(Workspace.activeWindow) ? Workspace.activeWindow : null
        const full = []
        for (const w of Workspace.stackingOrder) {
            // Full screen behind the active window on the same screen isn't in front.
            if (w !== active && w.fullScreen && root.shown(w) && (!active || w.output !== active.output))
                full.push(w.pid)
        }
        const said = JSON.stringify({active: active ? active.pid : 0, full: full})
        if (said === root.front) return
        root.front = said
        frontCall.arguments = [said]
        frontCall.call()
    }
    function watchFront(w) {
        if (!w || !w.normalWindow || w.deleted) return
        for (const signal of [w.fullScreenChanged, w.minimizedChanged, w.outputChanged, w.desktopsChanged])
            signal.connect(root.inFront)
    }

    Component.onCompleted: {
        Workspace.stackingOrder.forEach(w => placement.add(w, false))
        Workspace.stackingOrder.forEach(root.watch)
        Workspace.windowAdded.connect(root.added)
        Workspace.windowRemoved.connect(root.removed)
        Workspace.windowActivated.connect(root.changed)
        Workspace.currentDesktopChanged.connect(root.changed)
        Workspace.screensChanged.connect(root.changed)
        root.changed()
        Workspace.stackingOrder.forEach(root.watchFront)
        for (const signal of [Workspace.windowAdded, Workspace.windowRemoved, Workspace.windowActivated,
                              Workspace.currentDesktopChanged, Workspace.screensChanged])
            signal.connect(root.inFront)
        Workspace.windowAdded.connect(root.watchFront)
        root.inFront()
    }

    Timer {
        id: settle
        interval: 1000
        onTriggered: notify.call()
    }
    DBusCall {
        id: notify
        service: "org.monet.Work"
        path: "/org/monet/Work"
        dbusInterface: "org.monet.Work"
        method: "Changed"
    }
    DBusCall {
        id: closed
        service: "org.monet.Work"
        path: "/org/monet/Work"
        dbusInterface: "org.monet.Work"
        method: "Closed"
    }
    Timer {
        id: frontSettle
        interval: 250
        onTriggered: root.sayFront()
    }
    DBusCall {
        id: frontCall
        service: "org.monet.Priority"
        path: "/org/monet/Priority"
        dbusInterface: "org.monet.Priority"
        method: "Front"
        // Not listening yet (or any more): said again at the next change.
        onFailed: root.front = ""
    }
}
