/*
 * Monet Snap: Windows 11's snap layouts, in Monet's glass.
 *
 * Drag a window and a pebble of glass waits at the top of the screen; bring the window up to
 * it and it opens into layouts (halves, two thirds and a third, thirds, a half and two
 * quarters, quarters): let go over a part and the window takes that part. The left and right
 * edges take halves, the corners quarters, the top the whole screen. A preview shows where it
 * goes before you let go, and the window glides there (Monet Motion, the effect beside this).
 * Afterwards the rest of the layout offers the other windows (Snap Assist): pick one for each
 * part, or click anywhere else; so does a half or a quarter from Windows+arrows. Windows+Z shows
 * the layouts for the window you're in. Both take the arrows, Tab, Enter, Space and Esc while
 * they're up, as in Windows. Dragged away again, a window gets its own size back.
 * And a window stretched to the top or bottom of the screen by its edge takes the whole height.
 * The bar's islands stay on one row while widgets are being edited.
 *
 * KWin's own edge tiling and top-edge maximizing are off (monet-look): this does both.
 */
import QtQuick
import QtQuick.Window
import org.kde.kwin
import org.kde.kirigami as Kirigami

Item {
    id: root

    // The layouts at the top, each part as fractions of the screen: x, y, width, height.
    readonly property var layouts: [
        [[0, 0, 1 / 2, 1], [1 / 2, 0, 1 / 2, 1]],
        [[0, 0, 2 / 3, 1], [2 / 3, 0, 1 / 3, 1]],
        [[0, 0, 1 / 3, 1], [1 / 3, 0, 1 / 3, 1], [2 / 3, 0, 1 / 3, 1]],
        [[0, 0, 1 / 2, 1], [1 / 2, 0, 1 / 2, 1 / 2], [1 / 2, 1 / 2, 1 / 2, 1 / 2]],
        [[0, 0, 1 / 2, 1 / 2], [1 / 2, 0, 1 / 2, 1 / 2], [0, 1 / 2, 1 / 2, 1 / 2], [1 / 2, 1 / 2, 1 / 2, 1 / 2]]
    ]
    // The edges are the halves (layout 0) and the corners the quarters (layout 4).
    readonly property int halves: 0
    readonly property int quarters: 4
    // Between windows, and at the screen's edges: none, as in Windows, so snapped windows meet
    // each other and the screen's edges (the user saw the painting around them).
    readonly property int gap: 0
    readonly property int edge: 4       // how near the edge the pointer has to come
    readonly property int corner: 140   // how far from a corner still counts as the corner
    // Monet's motion (DESIGN.md): rise for what arrives, glide for what moves to a choice.
    readonly property real speed: Kirigami.Units.longDuration / 200
    // Mist or smoke, the way monet-light set the colors (Kirigami has no colors in KWin).
    readonly property bool smoke: palette.window.hslLightness < 0.5
    SystemPalette {
        id: palette
    }
    readonly property color lily: "#357F72"

    property var dragged: null
    property bool moving: false
    property rect start: Qt.rect(0, 0, 0, 0)
    property rect area: Qt.rect(0, 0, 0, 0)     // the work area of the screen under the pointer
    property rect screen: Qt.rect(0, 0, 0, 0)   // that screen
    property bool travelled: false              // moved far enough to be a drag, not a click
    property bool barNear: false                // the pointer close enough for the layouts
    // What letting go would do: {rect, layout, zone} or {rect, maximize}, or null.
    property var target: null
    // Windows Monet Snap put somewhere: their internalId -> the size they had before.
    property var sizes: ({})
    // Putting a window somewhere ourselves: not a tile KWin chose for it.
    property bool placing: false
    // Windows snapped into a layout, by internalId: they share their edges until dragged away.
    property var together: ({})
    // Moving a neighbor's edge ourselves, so its change doesn't move the next one again.
    property bool sharing: false
    // Wayland clients acknowledge a resize later. Use the last requested edge while waiting,
    // or the next pointer step can lose a neighbour whose window has not caught up yet.
    property var pendingGeometry: ({})
    // Settings → Light & Wallpaper → Snap layouts (monet-quick, kwinrc [Script-monet-snap]): off,
    // none of the snapping here, and KWin's own edges and top take a window instead. The bar's
    // islands stay on one row either way.
    property bool snapping: KWin.readConfig("Snapping", true)
    Connections {
        target: Options
        function onConfigChanged() {
            root.snapping = KWin.readConfig("Snapping", true)
            if (!root.snapping) {
                assist.close()
                picker.close()
                root.together = {}
                root.sizes = {}
                root.pendingGeometry = {}
            }
        }
    }

    function key(w) {
        return String(w.internalId)
    }

    // A part of a layout on the screen under the pointer, with Monet's gaps.
    function partRect(layout, zone, a) {
        const z = layouts[layout][zone]
        const x0 = a.x + gap, y0 = a.y + gap, w0 = a.width - 2 * gap, h0 = a.height - 2 * gap
        const left = x0 + z[0] * w0 + (z[0] > 0.001 ? gap / 2 : 0)
        const top = y0 + z[1] * h0 + (z[1] > 0.001 ? gap / 2 : 0)
        const right = x0 + (z[0] + z[2]) * w0 - (z[0] + z[2] < 0.999 ? gap / 2 : 0)
        const bottom = y0 + (z[1] + z[3]) * h0 - (z[1] + z[3] < 0.999 ? gap / 2 : 0)
        return Qt.rect(Math.round(left), Math.round(top), Math.round(right - left), Math.round(bottom - top))
    }

    // Each window's three handlers, to let go of them if this script is stopped.
    property var hooks: []
    function watch(w) {
        // Notifications: Plasma places them by their content's width, and Monet's glass frame is
        // wider than that, so they stuck out past the screen's edge. Kept inside it, they end
        // where the islands do.
        if (w && (w.notification || w.criticalNotification)) {
            const hook = { window: w, inside: () => root && root.keepInside(w) }
            w.frameGeometryChanged.connect(hook.inside)
            noteHooks.push(hook)
            w.closed.connect(() => root && root.noteHooks && (root.noteHooks = root.noteHooks.filter(h => h.window !== w)))
            keepInside(w)
            return
        }
        if (w && w.dock) {
            const hook = { window: w, line: () => root && root.lineUp() }
            w.frameGeometryChanged.connect(hook.line)
            barHooks.push(hook)
            w.closed.connect(() => root && root.barHooks && (root.barHooks = root.barHooks.filter(h => h.window !== w)))
            lineUp()
            return
        }
        if (!w || !w.normalWindow) {
            return
        }
        // Settings and Games ask to come forward only when they're opened again (from the bar, a
        // link, the menu): with no token of the desktop's to show for it, KWin would only flash
        // them in the taskbar (found by the test bench), so Monet lets its own apps through.
        if (w.resourceClass === "monet-settings" || w.resourceClass === "monet-games") {
            w.demandsAttentionChanged.connect(() => root && w.demandsAttention && (Workspace.activeWindow = w))
        }
        // Nothing, once this script is gone (KWin may keep the window's end of it).
        const hook = { window: w, start: () => root && root.started(w), step: () => root && root.stepped(w),
                       finish: () => root && root.finished(w) }
        hook.tile = () => root && root.tiled(w)
        hook.reshape = (old) => root && root.reshaped(w, old)
        w.interactiveMoveResizeStarted.connect(hook.start)
        w.interactiveMoveResizeStepped.connect(hook.step)
        w.interactiveMoveResizeFinished.connect(hook.finish)
        w.tileChanged.connect(hook.tile)
        w.frameGeometryChanged.connect(hook.reshape)
        hooks.push(hook)
        const id = key(w)
        w.closed.connect(() => {
            if (!root || !root.hooks) return
            root.hooks = root.hooks.filter(h => h.window !== w)
            delete root.pendingGeometry[id]
        })
    }
    Component.onDestruction: {
        for (const h of hooks || []) {
            if (!h.window) continue
            h.window.interactiveMoveResizeStarted.disconnect(h.start)
            h.window.interactiveMoveResizeStepped.disconnect(h.step)
            h.window.interactiveMoveResizeFinished.disconnect(h.finish)
            h.window.tileChanged.disconnect(h.tile)
            h.window.frameGeometryChanged.disconnect(h.reshape)
        }
        for (const h of noteHooks || []) {
            if (!h.window) continue
            h.window.frameGeometryChanged.disconnect(h.inside)
        }
        for (const h of barHooks || []) {
            if (!h.window) continue
            h.window.frameGeometryChanged.disconnect(h.line)
        }
    }

    // Plasma's edit mode gives each of the bar's three islands room of its own, and KWin piles
    // them up a bar's height apart: each goes back down, to the bottom of the screen or onto a
    // panel under it (one stacked there on purpose stays). Never lower: a bar sliding away is its own.
    property var barHooks: []
    property var noteHooks: []
    function keepInside(w) {
        const screen = w.output.geometry
        const g = w.frameGeometry
        const x = Math.max(screen.x, Math.min(g.x, screen.x + screen.width - g.width))
        if (Math.abs(x - g.x) >= 1) {
            w.frameGeometry = Qt.rect(x, g.y, g.width, g.height)
        }
    }
    property bool liningUp: false
    // Each island's side of the screen (left, right or middle), seen while its size has settled.
    property var barSides: ({})
    function lineUp() {
        if (liningUp) {
            return
        }
        liningUp = true
        const near = (a, b) => Math.abs(a - b) <= 1
        const lower = w => {
            const g = w.frameGeometry, o = w.output.geometry
            return g.width > g.height && g.y + g.height / 2 > o.y + o.height / 2
        }
        const bars = Workspace.stackingOrder.filter(w => w.dock && !w.deleted && w.output && lower(w))
        bars.sort((a, b) => (b.frameGeometry.y + b.frameGeometry.height) - (a.frameGeometry.y + a.frameGeometry.height))
        const below = []
        for (const w of bars) {
            const g = w.frameGeometry, o = w.output.geometry
            const right = o.x + o.width, middle = o.x + o.width / 2
            const side = near(g.x, o.x) ? "left" : near(g.x + g.width, right) ? "right"
                       : near(g.x + g.width / 2, middle) ? "middle" : ""
            if (side) {
                barSides[key(w)] = side
            }
            let floor = o.y + o.height
            for (const b of below) {
                if (b.output === w.output && Math.min(b.x + b.width, g.x + g.width) - Math.max(b.x, g.x) > 0.5) {
                    floor = Math.min(floor, b.y)
                }
            }
            // KWin puts an island where its next size goes before that size arrives, so the move
            // names that size (from its side): the size it has would be sent back to Plasma.
            // shortcut: a left island's next width doesn't show in where KWin puts it; Monet's left
            // island is the one KWin leaves at the bottom, so it never moves. Matters if that changes.
            const sideNow = barSides[key(w)]
            const width = sideNow === "middle" ? 2 * (middle - g.x) : sideNow === "right" ? right - g.x : g.width
            const y = Math.max(g.y, floor - g.height)
            if (g.y + g.height < floor - 0.5) {
                w.frameGeometry = Qt.rect(g.x, y, width, g.height)
            }
            below.push({ output: w.output, x: g.x, y: y, width: width })
        }
        liningUp = false
    }
    Component.onCompleted: {
        Workspace.stackingOrder.forEach(watch)
        Workspace.windowAdded.connect(watch)
    }

    function started(w) {
        if (!snapping || !w.resizeable || w.fullScreen || w.specialWindow) {
            return
        }
        assist.close()
        dragged = w
        moving = w.move
        if (moving) {
            delete together[key(w)]
        }
        travelled = false
        barNear = false
        target = null
        const p = Workspace.cursorPos
        const out = Workspace.screenAt(p)
        area = Workspace.clientArea(KWin.MaximizeArea, out, Workspace.currentDesktop)
        screen = out.geometry
        const was = sizes[key(w)]
        if (moving && was) {
            // As in Windows: dragged away, it's its own size again, held where it was held.
            delete sizes[key(w)]
            const g = w.frameGeometry
            const along = (p.x - g.x) / Math.max(g.width, 1)
            w.frameGeometry = Qt.rect(Math.round(p.x - along * was.width), g.y, was.width, was.height)
        }
        const g = w.frameGeometry
        start = Qt.rect(g.x, g.y, g.width, g.height)
    }

    function stepped(w) {
        if (w !== dragged || !moving) {
            return
        }
        const p = Workspace.cursorPos
        const out = Workspace.screenAt(p)
        area = Workspace.clientArea(KWin.MaximizeArea, out, Workspace.currentDesktop)
        screen = out.geometry
        const g = w.frameGeometry
        travelled = travelled || Math.abs(g.x - start.x) + Math.abs(g.y - start.y) > 16
        target = travelled ? aim(p) : null
    }

    // Where letting go here would put the window.
    function aim(p) {
        const a = area
        const nearTop = p.y <= a.y + edge
        const nearLeft = p.x <= a.x + edge
        const nearRight = p.x >= a.x + a.width - 1 - edge
        // Near the bar as it is when open, so it opens wherever its layouts will be.
        const middle = screen.x + screen.width / 2
        barNear = p.y < a.y + layoutRow.implicitHeight + 110 && Math.abs(p.x - middle) < layoutRow.implicitWidth / 2 + 90
        if (barNear) {
            const hit = overlay.partAt(p)
            if (hit) {
                return { rect: partRect(hit.layout, hit.zone, a), layout: hit.layout, zone: hit.zone }
            }
        }
        if (nearLeft || nearRight) {
            const side = nearLeft ? 0 : 1
            if (p.y < a.y + corner) {
                return { rect: partRect(quarters, side, a), layout: quarters, zone: side }
            }
            if (p.y > a.y + a.height - corner) {
                return { rect: partRect(quarters, 2 + side, a), layout: quarters, zone: 2 + side }
            }
            return { rect: partRect(halves, side, a), layout: halves, zone: side }
        }
        if (nearTop && !barNear) {
            if (p.x < a.x + corner) {
                return { rect: partRect(quarters, 0, a), layout: quarters, zone: 0 }
            }
            if (p.x > a.x + a.width - corner) {
                return { rect: partRect(quarters, 1, a), layout: quarters, zone: 1 }
            }
            return { rect: Qt.rect(a.x, a.y, a.width, a.height), maximize: true }
        }
        return null
    }

    function finished(w) {
        if (w !== dragged) {
            return
        }
        const t = target
        const wasMoving = moving
        dragged = null
        target = null
        barNear = false
        travelled = false
        if (wasMoving) {
            if (!t) {
                return
            }
            if (t.maximize) {
                w.setMaximize(true, true)
                return
            }
            place(w, t.rect, start)
            assist.offer(w, t.layout, t.zone, area)
            return
        }
        // Stretched by its top or bottom edge to the screen's: the whole height, as in Windows.
        const g = w.frameGeometry
        const a = Workspace.clientArea(KWin.MaximizeArea, w)
        const topMoved = Math.abs(g.y - start.y) > 1
        const bottomMoved = Math.abs(g.y + g.height - start.y - start.height) > 1
        if ((bottomMoved && !topMoved && g.y + g.height >= a.y + a.height - edge)
                || (topMoved && !bottomMoved && g.y <= a.y + edge)) {
            sizes[key(w)] = sizes[key(w)] || { width: start.width, height: start.height }
            w.frameGeometry = Qt.rect(g.x, a.y, g.width, a.height)
        }
    }

    // A window into a part, keeping the size it had (before) to go back to.
    function place(w, part, before) {
        delete pendingGeometry[key(w)]
        if (!sizes[key(w)]) {
            sizes[key(w)] = { width: before.width, height: before.height }
        }
        placing = true
        w.frameGeometry = part
        placing = false
        together[key(w)] = true
    }

    // As in Windows, snapped windows share their edges: one made bigger or smaller by an edge
    // (KWin's, or Settings' own grips) moves the edge of each snapped window beside it with it,
    // so neither goes over the other (Settings, made wider, went under the store beside it).
    function reshaped(w, old) {
        const pending = pendingGeometry[key(w)]
        if (pending) {
            const actual = w.frameGeometry
            if (Math.abs(actual.x - pending.x) < 1 && Math.abs(actual.y - pending.y) < 1
                    && Math.abs(actual.width - pending.width) < 1 && Math.abs(actual.height - pending.height) < 1)
                delete pendingGeometry[key(w)]
            // An acknowledgement is not another user resize to propagate back.
            if (!w.resize && !w.move) return
            delete pendingGeometry[key(w)]
        }
        if (!snapping || placing || sharing || !old || !together[key(w)] || w.move || w.fullScreen) {
            return
        }
        const g = w.frameGeometry
        const moved = (a, b) => Math.abs(a - b) > 0.5
        const left = moved(g.x, old.x), right = moved(g.x + g.width, old.x + old.width)
        const top = moved(g.y, old.y), bottom = moved(g.y + g.height, old.y + old.height)
        if ((left && right) || (top && bottom) || !(left || right || top || bottom)) {
            return  // moved or put somewhere new, not an edge pulled
        }
        // Their frame geometries meet: the theme paints no rim outside either window.
        const beside = (a0, a1, b0, b1) => Math.min(a1, b1) - Math.max(a0, b0) > 8
        sharing = true
        for (const o of Workspace.stackingOrder) {
            if (o === w || !together[key(o)] || o.output !== w.output || o.minimized) {
                continue
            }
            const f = pendingGeometry[key(o)] || o.frameGeometry
            const minW = Math.max(o.minSize.width, 160), minH = Math.max(o.minSize.height, 120)
            const rows = beside(old.y, old.y + old.height, f.y, f.y + f.height)
            const columns = beside(old.x, old.x + old.width, f.x, f.x + f.width)
            let next = null
            if (right && rows && Math.abs(f.x - (old.x + old.width)) <= 2) {
                const x = Math.min(g.x + g.width, f.x + f.width - minW)
                next = Qt.rect(x, f.y, f.x + f.width - x, f.height)
            } else if (left && rows && Math.abs(f.x + f.width - old.x) <= 2) {
                next = Qt.rect(f.x, f.y, Math.max(minW, g.x - f.x), f.height)
            } else if (bottom && columns && Math.abs(f.y - (old.y + old.height)) <= 2) {
                const y = Math.min(g.y + g.height, f.y + f.height - minH)
                next = Qt.rect(f.x, y, f.width, f.y + f.height - y)
            } else if (top && columns && Math.abs(f.y + f.height - old.y) <= 2) {
                next = Qt.rect(f.x, f.y, f.width, Math.max(minH, g.y - f.y))
            }
            if (next) {
                pendingGeometry[key(o)] = next
                o.frameGeometry = next
            }
        }
        sharing = false
    }

    // Windows+Left, Right, Up or Down put the window in a half or a quarter (KWin's tiles): the
    // rest of the screen offers the other windows, as after a drag.
    function tiled(w) {
        const tile = w.tile
        if (!snapping || !tile || placing || dragged || Workspace.activeWindow !== w || w.move || w.resize) {
            return
        }
        const g = tile.absoluteGeometry
        const a = Workspace.clientArea(KWin.MaximizeArea, w)
        const near = (r) => Math.abs(r.x - g.x) < 24 && Math.abs(r.y - g.y) < 24
            && Math.abs(r.width - g.width) < 48 && Math.abs(r.height - g.height) < 48
        for (const layout of [halves, quarters]) {
            for (let zone = 0; zone < layouts[layout].length; zone++) {
                const part = partRect(layout, zone, a)
                if (near(part)) {
                    // Keep KWin's tiles edge to edge, just like a dragged layout.
                    placing = true
                    w.frameGeometry = part
                    placing = false
                    together[key(w)] = true
                    assist.offer(w, layout, zone, a)
                    return
                }
            }
        }
    }

    // Windows+Z: the layouts for the window you're in.
    ShortcutHandler {
        name: "Monet Snap Layouts"
        text: "Snap layouts"
        sequence: "Meta+Z"
        onActivated: {
            const w = Workspace.activeWindow
            if (picker.shown) {
                picker.close()
            } else if (w && w.normalWindow && root.snapping) {
                assist.close()
                picker.open(w, w.output.geometry, Workspace.clientArea(KWin.MaximizeArea, w))
            }
        }
    }
    // While Snap Assist or the layouts are up, the keys Windows gives them: the arrows and Tab to
    // walk, Enter or Space to choose, Esc to put them away. KWin never gives a script's window the
    // keyboard, so these are KWin shortcuts that exist only meanwhile, giving the keys back after.
    // They go a moment after: the layouts handing over to Snap Assist keep the same ones (gone and
    // made again at once, the old ones' going switched the new ones off).
    readonly property bool keysWanted: assist.shown || picker.shown
    onKeysWantedChanged: {
        if (keysWanted) {
            keysOff.stop()
            keys.active = true
        } else {
            keysOff.restart()
        }
    }
    Timer {
        id: keysOff
        interval: 200
        onTriggered: keys.active = false
    }
    Loader {
        id: keys
        active: false
        sourceComponent: Item {
            Repeater {
                // And Windows' numbers in Windows+Z: a layout's, then a part's.
                model: [["Left", "left"], ["Right", "right"], ["Up", "up"], ["Down", "down"], ["Tab", "next"],
                        ["Return", "choose"], ["Enter", "choose"], ["Space", "choose"], ["Escape", "close"]]
                    .concat(["1", "2", "3", "4", "5", "6", "7", "8", "9"].map(n => [n, n]))
                Item {
                    required property var modelData
                    ShortcutHandler {
                        name: "Monet Snap Assist " + modelData[0]
                        // As KDE's shortcut list shows it, which keeps it with the key (taken only meanwhile).
                        text: "While Snap Assist or the snap layouts are open: " + modelData[0]
                        sequence: modelData[0]
                        // After the key's own signal: choosing closes them, which takes this away.
                        onActivated: Qt.callLater(root.pressed, modelData[1])
                    }
                }
            }
        }
    }
    function pressed(k) {
        if (picker.shown) {
            picker.press(k)
        } else if (assist.shown && !/^[1-9]$/.test(k)) {
            assist.press(k)
        }
    }
    Picker {
        id: picker
        layouts: root.layouts
        smoke: root.smoke
        lily: root.lily
        speed: root.speed
        onChosen: (w, layout, zone) => {
            const a = Workspace.clientArea(KWin.MaximizeArea, w)
            root.place(w, root.partRect(layout, zone, a), w.frameGeometry)
            assist.offer(w, layout, zone, a)
        }
    }

    // The bar and the preview, over the screen being dragged on; nothing here takes the pointer.
    Window {
        id: overlay
        readonly property bool dragging: root.dragged !== null && root.moving && root.travelled
        flags: Qt.BypassWindowManagerHint | Qt.FramelessWindowHint | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus
        color: "transparent"
        x: root.screen.x
        y: root.screen.y
        width: Math.max(root.screen.width, 1)
        height: Math.max(root.screen.height, 1)
        // Shown and hidden by hand: KWin doesn't show a script's window for a visible it's given.
        onDraggingChanged: {
            if (dragging) {
                hideOverlay.stop()
                show()
            } else {
                hideOverlay.restart()
            }
        }
        // While the bar opens or the pointer rests, what's under it changes all the same.
        Timer {
            interval: 40
            repeat: true
            running: overlay.dragging
            onTriggered: if (root.dragged) root.target = root.aim(Workspace.cursorPos)
        }
        Timer {
            id: hideOverlay
            interval: Math.round(260 * root.speed) + 40
            onTriggered: if (!overlay.dragging) overlay.hide()
        }

        function partAt(p) {
            return layoutRow.partAt(overlay.contentItem, p.x - overlay.x, p.y - overlay.y)
        }

        // Where the window goes, as a pane of lily-tinted glass.
        Rectangle {
            id: preview
            readonly property bool aimed: root.target !== null && overlay.dragging
            // Seen and moving between parts: glide; first seen: rise where it is.
            property bool settled: false
            property rect at: Qt.rect(0, 0, 0, 0)
            x: at.x - root.screen.x
            y: at.y - root.screen.y
            width: at.width
            height: at.height
            radius: 16
            color: Qt.rgba(0.208, 0.498, 0.447, root.smoke ? 0.30 : 0.20)
            border.width: 2
            border.color: Qt.rgba(1, 1, 1, root.smoke ? 0.35 : 0.75)
            opacity: aimed ? 1 : 0
            scale: aimed ? 1 : 0.96
            onAimedChanged: {
                if (aimed && opacity < 0.01) {
                    settled = false
                    at = root.target.rect
                }
            }
            Connections {
                target: root
                function onTargetChanged() {
                    if (root.target !== null) {
                        preview.at = root.target.rect
                        preview.settled = preview.opacity > 0.5
                    }
                }
            }
            Behavior on x { enabled: preview.settled; NumberAnimation { duration: Math.round(320 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] } }
            Behavior on y { enabled: preview.settled; NumberAnimation { duration: Math.round(320 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] } }
            Behavior on width { enabled: preview.settled; NumberAnimation { duration: Math.round(320 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] } }
            Behavior on height { enabled: preview.settled; NumberAnimation { duration: Math.round(320 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] } }
            Behavior on opacity { NumberAnimation { duration: Math.round((preview.aimed ? 200 : 160) * root.speed) } }
            Behavior on scale { NumberAnimation { duration: Math.round(380 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] } }
            // Light along its top, as on all of Monet's glass.
            Rectangle {
                anchors.fill: parent
                anchors.margins: 2
                radius: parent.radius - 2
                gradient: Gradient {
                    GradientStop { position: 0; color: Qt.rgba(1, 1, 1, root.smoke ? 0.10 : 0.30) }
                    GradientStop { position: 0.35; color: Qt.rgba(1, 1, 1, 0) }
                }
            }
        }

        // The pebble at the top: a sliver while a window is dragged, the layouts when it comes near.
        Item {
            id: bar
            readonly property bool open: root.barNear && overlay.dragging
            readonly property int closedWidth: 120
            readonly property int closedHeight: 10
            width: open ? layoutRow.implicitWidth + 28 : closedWidth
            height: open ? layoutRow.implicitHeight + 28 : closedHeight
            x: Math.round((overlay.width - width) / 2)
            y: overlay.dragging ? root.area.y - root.screen.y + 12 : -height - 12
            opacity: overlay.dragging ? 1 : 0
            Behavior on width { NumberAnimation { duration: Math.round(320 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] } }
            Behavior on height { NumberAnimation { duration: Math.round(320 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] } }
            Behavior on y { NumberAnimation { duration: Math.round((overlay.dragging ? 380 : 200) * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: overlay.dragging ? [0.2, 0.9, 0.25, 1.08, 1, 1] : [0.4, 0, 1, 1, 1, 1] } }
            Behavior on opacity { NumberAnimation { duration: Math.round(200 * root.speed) } }

            Pebble {
                anchors.fill: parent
                smoke: root.smoke
            }

            Layouts {
                id: layoutRow
                anchors.centerIn: parent
                layouts: root.layouts
                smoke: root.smoke
                lily: root.lily
                speed: root.speed
                litLayout: root.target !== null && root.barNear && !root.target.maximize ? root.target.layout : -1
                litZone: root.target !== null && root.barNear && !root.target.maximize ? root.target.zone : -1
                opacity: bar.open ? 1 : 0
                visible: opacity > 0
                Behavior on opacity { NumberAnimation { duration: Math.round(180 * root.speed) } }
            }
        }
    }

    Assist {
        id: assist
        speed: root.speed
        smoke: root.smoke
        lily: root.lily
        // Picked, it takes its part and comes to the front, as in Windows.
        onPicked: (w, rect) => {
            root.place(w, rect, w.frameGeometry)
            Workspace.activeWindow = w
        }
        partRect: (layout, zone, a) => root.partRect(layout, zone, a)
        layouts: root.layouts
    }
}
