/*
 * Monet Titles: title bars that appear when you point at the top, as Zen's compact mode has its
 * toolbar.
 *
 * While it's on, the windows KWin frames get Monet's bare frame (monet-light picks MonetBare,
 * tools/make-decoration.py): its shadow alone, no title bar, so the app has the whole window.
 * Bring the pointer to the top of a window, or to the top of the screen over one that fills it,
 * and after a moment a title bar of Monet's glass appears over the window's top: the app's
 * icon and title, minimize, maximize and close. Drag it to move the window, double-click it to
 * fill the screen, right-click it for the window's menu. It fades away a moment after
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
                root.newWindow = null
                introduce.stop()
                reveal.stop()
                away.stop()
                bar.close(true)
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
    property var newWindow: null
    property var preview: null
    property var lastClient: null
    property QtObject mouseMove: null
    Component.onCompleted: {
        bar.updatePanels(Workspace.stackingOrder)
        // The image supplies a bridge built against its exact KWin runtime.
        // Generic tarballs can still use KWin's scripting-only move action.
        try {
            mouseMove = Qt.createQmlObject('import org.monet.windowcontrols 1.0; WindowControls {}', root, "MonetTitleMove")
        } catch (error) { mouseMove = null }
    }

    function startMove() {
        if (!bar.window || !bar.dragHeld) return
        if (mouseMove) {
            if (mouseMove.beginMove(bar.window, bar.dragOrigin, bar.dragSurface)) bar.letGo()
        } else {
            whenActive(bar.window, "move")
        }
    }

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
        const stack = Workspace.stackingOrder
        const layout = Hover.barLayout(w.clientGeometry, w.output.geometry, stack)
        return Hover.covered(w, layout.main, stack, Workspace.currentDesktop, ours)
            || (layout.side !== null && Hover.covered(w, layout.side, stack, Workspace.currentDesktop, ours))
    }

    function aroundBar(p) {
        if (Hover.onBar(bar.area, p) || (bar.layout.side && Hover.onBar(bar.layout.side, p))) return true
        // A narrow window can only fit its controls below the notch. Keep them
        // open while the pointer crosses the intervening part of this window.
        const w = bar.window
        return w && p.y < bar.area.y && p.y >= Hover.visibleTop(w.clientGeometry, w.output.geometry)
            && p.x >= bar.area.x && p.x < bar.area.x + bar.area.width && topWindow(p) === w
    }

    function canShow(w) {
        return Hover.titleless(w) && w.output
            && (w.onAllDesktops || w.desktops.indexOf(Workspace.currentDesktop) >= 0) && !coveredNow(w)
    }

    function topWindow(p) {
        return Workspace.windowAt(Qt.point(p.x, p.y), 2).find(w => !ours(w))
    }

    // The window whose top the pointer is at, if its bar may come there now.
    function aimedAt(p) {
        if (busy()) {
            return null
        }
        return Hover.aimedAt(p, root.topWindow, root.canShow, bar.panels)
    }

    function atClientEdge(w, p) {
        return w && !w.deleted && w.managed && (w.normalWindow || w.dialog || w.utility)
            && w.output && Hover.atTop(w.clientGeometry, w.output.geometry, p, bar.panels)
    }

    function nearEdge(p) {
        // A snap outline or closing menu can be the top hit until KWin removes it.
        return atClientEdge(Workspace.activeWindow, p) || atClientEdge(root.topWindow(p), p)
    }

    function edgeChanged() {
        if (root.hovering && !bar.held && nearEdge(Workspace.cursorPos)) root.queueEvaluation()
    }

    // As the pointer moves (once a frame at most): the bar stays while the pointer's on it or
    // holds it, comes a moment after the pointer reaches a window's top (passing by isn't enough),
    // and goes a moment after the pointer leaves it.
    function evaluate(retry = true) {
        if (!hovering) {
            return
        }
        const p = Workspace.cursorPos
        const w = bar.window
        if (bar.visible && !bar.open && w && !root.busy() && root.canShow(w) && aroundBar(p)) {
            bar.keepOpen()
        }
        if (bar.open && w && (bar.held || w.move || w.resize || aroundBar(p))) {
            pending = null
            reveal.stop()
            away.stop()
            return
        }
        const aimed = aimedAt(p)
        if (!aimed && retry && !bar.held && !root.busy() && nearEdge(p)) settleEdge.restart()
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
        if (bar.open && preview !== w && !away.running) {
            away.start()
        }
    }

    Timer {
        id: look
        interval: 16
        onTriggered: root.evaluate()
    }
    Timer {
        id: settleEdge
        interval: Math.max(200, Math.round(300 * root.speed))
        onTriggered: root.evaluate(false)
    }
    function queueEvaluation() {
        if (root.hovering && !look.running) look.start()
    }
    Connections {
        target: Workspace
        function onCursorPosChanged() {
            settleEdge.stop()
            root.queueEvaluation()
        }
        function onWindowAdded(w) {
            if (w && w.dock) bar.updatePanels(Workspace.stackingOrder)
            if (root.hovering && w && w.normalWindow && w.managed && !w.popupWindow && !w.transient) {
                root.newWindow = w
                introduce.restart()
            }
        }
        function onWindowRemoved(w) {
            if (w && w.dock) bar.updatePanels(Workspace.stackingOrder)
            if (w && !root.ours(w)) root.edgeChanged()
        }
        function onWindowActivated(w) {
            if (root.asked && root.asked.window === w) root.act()
            // KWin may announce the same client again as an internal popup maps.
            // A deliberate hover on an inactive window must survive that announcement.
            if (!w || !(w.normalWindow || w.dialog || w.utility) || w.popupWindow || w === root.lastClient) return
            const previous = root.lastClient
            root.lastClient = w
            if (bar.visible && bar.window && bar.window !== w && !bar.held
                    && (bar.window === previous || root.preview === bar.window || root.coveredNow(bar.window))) {
                root.pending = null
                reveal.stop()
                bar.close(true)
            }
            root.queueEvaluation()
        }
    }

    Connections {
        target: Workspace.activeWindow
        ignoreUnknownSignals: true
        function onClientGeometryChanged() {
            if (target && !target.move && !target.resize && root.atClientEdge(target, Workspace.cursorPos))
                root.queueEvaluation()
        }
        function onInteractiveMoveResizeFinished() { root.edgeChanged() }
    }

    // Give a new foreground window a brief introduction after its first map.
    // Keep it open if the pointer is already on the controls when time is up.
    Timer {
        id: introduce
        interval: 220
        onTriggered: {
            const w = root.newWindow
            root.newWindow = null
            if (!w || w !== Workspace.activeWindow || !root.hovering || bar.held
                    || w.move || w.resize || root.busy() || !root.canShow(w)) return
            root.pending = null
            reveal.stop()
            away.stop()
            bar.openFor(w, Workspace.stackingOrder)
            root.preview = w
            previewTime.restart()
        }
    }
    Timer {
        id: previewTime
        interval: 2200
        onTriggered: {
            const w = root.preview
            root.preview = null
            if (bar.open && w && bar.window === w && !bar.held && !w.move && !w.resize
                    && !root.aroundBar(Workspace.cursorPos)) bar.close()
        }
    }
    Timer {
        id: reveal
        interval: 125
        onTriggered: {
            const w = root.aimedAt(Workspace.cursorPos)
            if (w && w === root.pending && !bar.held) {
                bar.openFor(w, Workspace.stackingOrder)
            } else if (root.pending && !bar.held && root.nearEdge(Workspace.cursorPos)) {
                // The outline may appear during the hover delay itself.
                settleEdge.restart()
            }
            root.pending = null
        }
    }
    Timer {
        id: away
        interval: 320
        onTriggered: {
            const w = bar.window
            const p = Workspace.cursorPos
            if (!w || bar.held || w.move || w.resize || aroundBar(p) || root.aimedAt(p) === w) {
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
            if (!root.hovering || root.busy() || !root.canShow(w)) {
                bar.close(true)
            }
        }
    }
    Connections {
        target: bar.window
        ignoreUnknownSignals: true
        function onClosed() {
            bar.close(true)
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
        asked = { window: w, what: what, tries: 0 }
        if (Workspace.activeWindow !== w) {
            Workspace.activeWindow = w
        }
        act()
    }
    function act() {
        const a = asked
        if (!a) {
            return
        }
        // Let go already: a move now would stick to the pointer until the next click.
        if (a.window.deleted || bar.window !== a.window || !bar.open || (a.what === "move" && !bar.dragHeld)) {
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
        soon.stop()
        if (a.what === "move") {
            Workspace.slotWindowMove()
            bar.letGo()
        } else {
            bar.close(true)
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
        onOpenChanged: {
            if (!bar.open) {
                previewTime.stop()
                root.preview = null
            }
        }
        onWindowChanged: {
            if (root.preview && root.preview !== bar.window) {
                previewTime.stop()
                root.preview = null
            }
        }
        onAreaChanged: if (bar.open) root.queueEvaluation()
        onHeldChanged: {
            if (bar.held && root.preview) {
                previewTime.stop()
                root.preview = null
            }
            if (bar.open) root.queueEvaluation()
        }
        onActivateAsked: {
            if (bar.window && Workspace.activeWindow !== bar.window) {
                Workspace.activeWindow = bar.window
            }
        }
        onMoveAsked: root.startMove()
        onMenuAsked: root.whenActive(bar.window, "menu")
    }
}
