import QtQuick
import QtCore
import org.kde.kwin

Item {
    id: placement

    // This is separate from the restart checkpoint. It contains only the last
    // main window's geometry per app, in logical pixels relative to its screen.
    Settings {
        id: history
        location: StandardPaths.writableLocation(StandardPaths.ConfigLocation) + "/monet/window-placements.conf"
    }
    property var entries: Object.create(null)
    // KWin's MaximizeMode flags: both directions set.
    readonly property int maximized: 3

    function key(w) {
        if (!w || !w.normalWindow || w.skipTaskbar || w.transient || w.dialog || !w.managed)
            return ""
        const id = String(w.desktopFileName || "").split("/").pop().replace(/\.desktop$/, "")
        return /^[\w.+-]{1,255}$/.test(id) ? "apps/" + id : ""
    }

    function saved(app) {
        try {
            const record = JSON.parse(history.value(app, "null"))
            if (record && [record.x, record.y, record.width, record.height].every(Number.isFinite)
                    && record.width > 0 && record.height > 0 && record.screen)
                return record
        } catch (error) {
            // A damaged preference is treated as a first launch.
        }
        return null
    }

    function screenOf(output) {
        return {name: String(output.name || ""), maker: String(output.manufacturer || ""),
                model: String(output.model || ""), serial: String(output.serialNumber || "")}
    }

    function matchingScreen(screen) {
        const sameModel = Workspace.screens.filter(o => screen.model
            && o.manufacturer === screen.maker && o.model === screen.model)
        const exact = screen.serial
            ? sameModel.filter(o => o.serialNumber === screen.serial) : []
        if (exact.length === 1) return exact[0]
        if (sameModel.length === 1 && !screen.serial) return sameModel[0]
        return Workspace.screens.find(o => o.name === screen.name && (!screen.model || !o.model
            || (o.model === screen.model && (!screen.serial || !o.serialNumber || o.serialNumber === screen.serial))))
    }

    function snapshot(w) {
        if (w.fullScreen || w.tile || Number(w.maximizeMode) !== 0 || !w.output || !w.moveable)
            return null
        const g = w.frameGeometry
        const area = Workspace.clientArea(KWin.MaximizeArea, w)
        if (area.width <= 0 || area.height <= 0 || g.width <= 0 || g.height <= 0) return null
        return {x: g.x - area.x, y: g.y - area.y, width: g.width, height: g.height,
                screen: screenOf(w.output), maximized: false}
    }

    function hasSibling(w, app) {
        return Workspace.stackingOrder.some(other => other !== w && !other.deleted && key(other) === app)
    }

    function restore(entry) {
        const w = entry.window
        const app = key(w)
        if (!app || w.deleted || w.move || w.resize || w.fullScreen || w.tile
                || Number(w.maximizeMode) !== 0 || !w.moveable || !w.output || hasSibling(w, app))
            return
        const record = saved(app)
        if (!record) return
        const output = matchingScreen(record.screen) || w.output
        const area = Workspace.clientArea(KWin.MaximizeArea, output, Workspace.currentDesktop)
        if (area.width <= 0 || area.height <= 0) return
        const g = w.frameGeometry
        const border = Qt.size(g.width - w.clientGeometry.width, g.height - w.clientGeometry.height)
        const width = w.resizeable
            ? Math.max(w.minSize.width + border.width, Math.min(record.width, area.width, w.maxSize.width + border.width))
            : g.width
        const height = w.resizeable
            ? Math.max(w.minSize.height + border.height, Math.min(record.height, area.height, w.maxSize.height + border.height))
            : g.height
        const x = area.x + Math.max(0, Math.min(record.x, area.width - width))
        const y = area.y + Math.max(0, Math.min(record.y, area.height - height))
        const target = Qt.rect(x, y, width, height)
        w.frameGeometry = target
        if (record.maximized && w.maximizable) {
            w.setMaximize(true, true, target)
            entry.normal = record
        }
    }

    function add(w, newlyOpened) {
        if (!w || !w.normalWindow || w.deleted || !w.managed) return
        const id = String(w.internalId)
        if (!entries[id]) entries[id] = watcher.createObject(placement, {window: w, pending: newlyOpened})
    }

    function remove(w) {
        const id = String(w.internalId)
        const entry = entries[id]
        if (!entry) return
        const app = key(w)
        if (app && !entry.pending && !hasSibling(w, app)) {
            const previous = saved(app)
            // A monitor disappearing can move every window to the laptop's
            // screen. Keep the preferred monitor unless the person moved it.
            if (!previous || matchingScreen(previous.screen) || entry.moved) {
                const record = snapshot(w) || (!w.fullScreen && Number(w.maximizeMode) === maximized
                    && entry.normal ? Object.assign({}, entry.normal, {maximized: true}) : null)
                if (record) {
                    const value = JSON.stringify(record)
                    if (value !== history.value(app, "")) {
                        history.setValue(app, value)
                        history.sync()
                    }
                }
            }
        }
        delete entries[id]
        entry.destroy()
    }

    Component {
        id: watcher
        Item {
            id: entry
            required property var window
            property bool pending: false
            property bool moved: false
            property var normal: null

            function applyOnce(deadline = false) {
                if (!pending || (!deadline && !placement.key(window))) return
                pending = false
                placement.restore(entry)
            }

            // Apps can update their size/identity just after mapping. Give the
            // initial configure a moment, with a deadline for animated starts.
            Timer { id: settle; interval: 220; onTriggered: entry.applyOnce() }
            Timer { interval: 1100; running: entry.pending; onTriggered: entry.applyOnce(true) }
            Connections {
                target: entry.window
                function onFrameGeometryChanged() { if (entry.pending) settle.restart() }
                function onDesktopFileNameChanged() { if (entry.pending) settle.restart() }
                function onInteractiveMoveResizeStarted() {
                    entry.pending = false
                    entry.moved = true
                }
                function onMaximizedAboutToChange() {
                    entry.pending = false
                    const frame = placement.snapshot(entry.window)
                    if (frame) entry.normal = frame
                }
            }
            Component.onCompleted: if (pending) settle.start()
        }
    }
}
