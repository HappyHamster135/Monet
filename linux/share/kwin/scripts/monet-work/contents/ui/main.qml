/*
 * Monet Work: says when the windows change, so Monet keeps a recent picture of your work (which
 * apps, on which screen and desktop, where, how big) to open again after a restart, a sign-out,
 * a crash or a power cut. monet-work.service does the looking (monet-resume's KWin snapshot);
 * this only says "something changed", at most once a second, and which window closed, by
 * KWin's id for it. Never a title or anything a window shows.
 */
import QtQuick
import org.kde.kwin

Item {
    id: root

    // The windows Monet reopens: an app's own, in the taskbar, with a menu entry.
    function tracked(w) {
        return w && w.normalWindow && !w.skipTaskbar && !w.transient && String(w.desktopFileName || "") !== ""
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
        root.watch(w)
        if (root.tracked(w)) root.changed()
    }
    // Right away, so a window closed just before a restart stays closed: monet-work stops
    // listening to closes the moment a restart, shutdown or sign-out begins.
    function removed(w) {
        if (!root.tracked(w)) return
        closed.arguments = [String(w.internalId)]
        closed.call()
    }

    Component.onCompleted: {
        Workspace.stackingOrder.forEach(root.watch)
        Workspace.windowAdded.connect(root.added)
        Workspace.windowRemoved.connect(root.removed)
        Workspace.windowActivated.connect(root.changed)
        Workspace.currentDesktopChanged.connect(root.changed)
        Workspace.screensChanged.connect(root.changed)
        root.changed()
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
}
