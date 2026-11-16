/*
 * Monet Titles: title bars that appear when you point at the top, as Zen's compact mode has its
 * toolbar.
 *
 * While it's on, the windows KWin frames get Monet's bare frame (monet-light picks MonetBare,
 * tools/make-decoration.py): its shadow alone, no title bar, so the app has the whole window.
 * Bring the pointer to the top of a window, or to the top of the screen over one that fills it,
 * and after a moment a title bar of Monet's glass slides down over the window's top: the app's
 * icon and title, minimize, maximize and close. Drag it to move the window, double-click it to
 * fill the screen, right-click it for the window's menu. It slides away again a moment after
 * the pointer leaves it. The window never moves or changes size for it: the bar lies over it.
 *
 * Never for a window that draws its own title bar (GTK, Chromium, Zen, Monet's own apps), one
 * that's full screen (games), Plasma's or KWin's own, or under a menu, a panel or another window.
 * The keys stay KWin's: Alt+F3 and Alt+Space open the window's menu as before.
 * Settings → Light & Wallpaper turns it off (monet-quick pref titles: kwinrc [Script-monet-titles]
 * Hover, and monet-light gives the windows their glass title bars back).
 */
import QtQuick
import org.kde.kwin
import org.kde.kirigami as Kirigami
import "hover.js" as Hover

Item {
    id: root

    property bool hovering: KWin.readConfig("Hover", true)
    Connections {
        target: Options
        function onConfigChanged() {
            root.hovering = KWin.readConfig("Hover", true)
            if (!root.hovering) {
                root.pending = null
                reveal.stop()
                bar.close()
            }
        }
    }
    // Monet's motion (DESIGN.md); none, with animations turned off.
    readonly property real speed: Kirigami.Units.longDuration / 200
    // Mist or smoke, the way monet-light set the colors (Kirigami has no colors in KWin).
    readonly property bool smoke: palette.window.hslLightness < 0.5
    SystemPalette {
        id: palette
    }

    // The window the pointer waits at the top of, before its bar comes.
    property var pending: null

    // The bar's own window, which KWin lists with the rest.
    function ours(o) {
        return o.popupWindow && o.caption === bar.title
    }

    // KWin's full-screen views (the overview, the windows side by side, the tile editor) take
    // the pointer and the screen while they're up.
    function busy() {
        return Workspace.isEffectActive("overview") || Workspace.isEffectActive("windowview")
            || Workspace.isEffectActive("tileseditor")
    }

    function coveredNow(w) {
        return Hover.covered(w, Hover.barRect(w.clientGeometry, w.output.geometry), Workspace.stackingOrder,
                             Workspace.currentDesktop, ours)
    }

    // The window whose top the pointer is at, if its bar may come there now.
    function aimedAt(p) {
        if (busy()) {
            return null
        }
        const under = Workspace.windowAt(p, 2)
        let w = null
        for (let i = 0; i < under.length && !w; i++) {
            w = ours(under[i]) ? null : under[i]
        }
        if (!w || !Hover.titleless(w) || w.move || w.resize || !w.output) {
            return null
        }
        if (!Hover.atTop(w.clientGeometry, w.output.geometry, p)) {
            return null
        }
        return coveredNow(w) ? null : w
    }

    // As the pointer moves (once a frame at most): the bar stays while the pointer's on it or
    // holds it, comes a moment after the pointer reaches a window's top (passing by isn't enough),
    // and goes a moment after the pointer leaves it.
    function evaluate() {
        if (!hovering) {
            return
        }
        const p = Workspace.cursorPos
        const w = bar.window
        if (bar.open && w && (bar.held || w.move || w.resize || Hover.onBar(bar.area, p))) {
            pending = null
            reveal.stop()
            away.stop()
            return
        }
        const aimed = aimedAt(p)
        if (bar.open && aimed === w) {
            away.stop()
            return
        }
        if (aimed !== pending) {
            pending = aimed
            if (aimed) {
                reveal.restart()
            } else {
                reveal.stop()
            }
        }
        if (bar.open && !away.running) {
            away.start()
        }
    }

    Timer {
        id: look
        interval: 16
        onTriggered: root.evaluate()
    }
    Connections {
        target: Workspace
        function onCursorPosChanged() {
            if (root.hovering && !look.running) {
                look.start()
            }
        }
    }
    Timer {
        id: reveal
        interval: 150
        onTriggered: {
            const w = root.aimedAt(Workspace.cursorPos)
            if (w && w === root.pending) {
                bar.openFor(w)
            }
            root.pending = null
        }
    }
    Timer {
        id: away
        interval: 400
        onTriggered: {
            const w = bar.window
            const p = Workspace.cursorPos
            if (!w || bar.held || w.move || w.resize || Hover.onBar(bar.area, p) || root.aimedAt(p) === w) {
                return
            }
            bar.close()
        }
    }
    // Gone, minimized, full screen, on another desktop or covered meanwhile (its menu opened over
    // it, another window raised): the bar goes too. Never while it's held or its window moves.
    Timer {
        interval: 150
        repeat: true
        running: bar.open
        onTriggered: {
            const w = bar.window
            if (w && (bar.held || w.move || w.resize)) {
                return
            }
            if (!w || !root.hovering || root.busy() || !Hover.titleless(w) || !w.output
                    || !(w.onAllDesktops || w.desktops.indexOf(Workspace.currentDesktop) >= 0) || root.coveredNow(w)) {
                bar.close()
            }
        }
    }
    Connections {
        target: bar.window
        ignoreUnknownSignals: true
        function onClosed() {
            bar.close()
        }
        // Let go where the bar is, it stays until the pointer leaves it, as after any press.
        function onInteractiveMoveResizeFinished() {
            look.restart()
        }
    }

    // KWin moves, and shows the menu of, only the active window; an X11 app's turns active a
    // moment after it's asked to. Asked: {window, what: "move" or "menu", tries}.
    property var asked: null
    function whenActive(w, what) {
        if (!w) {
            return
        }
        if (Workspace.activeWindow !== w) {
            Workspace.activeWindow = w
        }
        asked = { window: w, what: what, tries: 0 }
        act()
    }
    function act() {
        const a = asked
        if (!a) {
            return
        }
        // Let go already: a move now would stick to the pointer until the next click.
        if (a.window.deleted || (a.what === "move" && !bar.held)) {
            asked = null
            return
        }
        if (Workspace.activeWindow !== a.window) {
            a.tries += 1
            if (a.tries < 10) {
                soon.restart()
            } else {
                asked = null
            }
            return
        }
        asked = null
        if (a.what === "move") {
            Workspace.slotWindowMove()
            bar.letGo()
        } else {
            Workspace.slotWindowOperations()
        }
    }
    Timer {
        id: soon
        interval: 20
        onTriggered: root.act()
    }

    TitleBar {
        id: bar
        speed: root.speed
        smoke: root.smoke
        onActivateAsked: {
            if (bar.window && Workspace.activeWindow !== bar.window) {
                Workspace.activeWindow = bar.window
            }
        }
        onMoveAsked: root.whenActive(bar.window, "move")
        onMenuAsked: root.whenActive(bar.window, "menu")
    }
}
