// Pulse objects stay live while a mixer is open. Stream volumes never rebuild the list.
import QtQuick
import QtCore
import org.kde.plasma.plasma5support as P5
import Qt.labs.folderlistmodel
import org.kde.plasma.private.volume 0.1 as Audio

QtObject {
    id: mixer
    readonly property bool ready: Audio.Context.state === Audio.Context.Ready
    readonly property var output: Audio.PreferredDevice.sink
    readonly property int normal: Audio.PulseAudio.NormalVolume
    property var streams: []
    property var devices: []
    readonly property ListModel rows: ListModel {}
    readonly property Settings prefs: Settings {
        location: StandardPaths.writableLocation(StandardPaths.ConfigLocation) + "/monet/mixer.ini"
    }
    property var layout: ({pins: [], order: []})

    // Closing the mixer also cancels updates queued by the file and stream models.
    readonly property Timer layoutUpdate: Timer { interval: 0; onTriggered: mixer.reload() }
    readonly property Timer streamUpdate: Timer { interval: 0; onTriggered: mixer.reconcile() }

    function readLayout() {
        prefs.sync()
        try {
            const v = JSON.parse(prefs.value("arrangement", "{}"))
            if (Array.isArray(v.pins) && Array.isArray(v.order))
                return {pins: v.pins.filter(p => p && typeof p.key === "string" && typeof p.name === "string"),
                        order: v.order.filter(key => typeof key === "string")}
        } catch (_) {}
        return {pins: [], order: []}
    }
    function reload() {
        layout = readLayout()
        reconcile()
    }
    function reconcile() {
        const found = new Map()
        for (const pin of layout.pins)
            found.set(pin.key, {appKey: pin.key, label: pin.name, pinned: true})
        for (const s of streams) {
            if (!s || !s.eligible || !s.appKey) continue
            const row = found.get(s.appKey)
            if (row) row.label = s.label
            else found.set(s.appKey, {appKey: s.appKey, label: s.label, pinned: false})
        }
        const pinRank = new Map(layout.pins.map((p,i) => [p.key,i]))
        const rank = new Map(layout.order.map((k,i) => [k,i]))
        const sorted = Array.from(found.values()).sort((a,b) => {
            if (a.pinned !== b.pinned) return a.pinned ? -1 : 1
            const positions = a.pinned ? pinRank : rank
            return (positions.get(a.appKey) ?? Infinity) - (positions.get(b.appKey) ?? Infinity)
                || a.label.localeCompare(b.label) || a.appKey.localeCompare(b.appKey)
        })
        for (let i = 0; i < sorted.length; ++i) {
            const row = sorted[i]
            let j = i
            while (j < rows.count && rows.get(j).appKey !== row.appKey) ++j
            if (j === rows.count) rows.insert(i,row)
            else {
                if (j !== i) rows.move(j,i,1)
                if (rows.get(i).label !== row.label || rows.get(i).pinned !== row.pinned) rows.set(i,row)
            }
        }
        if (rows.count > sorted.length) rows.remove(sorted.length, rows.count - sorted.length)
    }
    property string helper: "@LIBEXECDIR@/monet-quick"
    property bool saving: false
    property bool saveFailed: false
    // Loading the mixer only subscribes to changes. Start a helper solely for a layout edit.
    readonly property P5.DataSource writer: P5.DataSource {
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source)
            try { mixer.saveFailed = !JSON.parse(data.stdout).ok } catch (_) { mixer.saveFailed = true }
            mixer.saving = false
            mixer.reload()
        }
    }
    readonly property FolderListModel files: FolderListModel {
        folder: StandardPaths.writableLocation(StandardPaths.ConfigLocation) + "/monet"
        nameFilters: ["mixer.ini"]
        showDirs: false
        onDataChanged: mixer.layoutUpdate?.restart()
        onCountChanged: mixer.layoutUpdate?.restart()
    }
    function save(edit) {
        if (saving) return
        saving = true
        saveFailed = false
        const bytes = unescape(encodeURIComponent(JSON.stringify(edit)))
        const payload = Array.from(bytes, c => c.charCodeAt(0).toString(16).padStart(2, "0")).join("")
        writer.connectSource(helper + " mixer-arrange " + payload)
    }
    function pin(key, name, wanted) {
        if (!key.startsWith("stream:")) save({key: key, name: name, pin: wanted})
    }
    function move(key, target, after) {
        if (key === target) return
        const items = Array.from({length: rows.count}, (_, i) => rows.get(i))
        const row = items.find(r => r.appKey === key)
        if (!row) return
        const visible = items.filter(r => r.pinned === row.pinned && !r.appKey.startsWith("stream:")).map(r => r.appKey)
        if (visible.includes(key) && visible.includes(target))
            save({key: key, target: target, after: after, pinned: row.pinned, visible: visible})
    }
    function step(index, delta) {
        if (index < 0 || index + delta < 0 || index + delta >= rows.count) return
        move(rows.get(index).appKey, rows.get(index+delta).appKey, delta>0)
    }
    function matching(key) { return streams.filter(s => s && s.eligible && s.appKey === key) }
    function level(key, percent) {
        const gain = Math.round(Math.max(0, Math.min(100,percent)) * normal / 100)
        for (const s of matching(key)) if (s.model.VolumeWritable) s.model.Volume = gain
    }
    function mute(key, on) { for (const s of matching(key)) s.model.Muted = on }
    function route(key, device) {
        if (!ready || !device || !devices.includes(device)) return
        for (const s of matching(key)) s.model.DeviceIndex = device.pulseIndex
    }
    readonly property Instantiator inputs: Instantiator {
        model: Audio.SinkInputModel {}
        delegate: QtObject {
            required property var model
            readonly property var meta: model.Properties || ({})
            readonly property var client: model.Client?.properties || ({})
            readonly property string identity: meta["pipewire.access.portal.app_id"] || client["pipewire.access.portal.app_id"]
                || meta["application.id"] || client["application.id"] || ""
            readonly property string binary: meta["application.process.binary"] || client["application.process.binary"] || ""
            readonly property string appName: meta["application.name"] || client["application.name"] || model.Client?.name || ""
            readonly property string appKey: identity ? "id:"+identity : binary ? "binary:"+binary
                : appName ? "name:"+appName : "stream:"+model.Index
            readonly property string label: appName || binary || identity || i18n("Audio stream")
            readonly property bool eligible: !model.VirtualStream && meta["media.role"] !== "event" && model.Name !== "sink-input-by-media-role:event"
            readonly property bool muted: model.Muted
            readonly property int gain: model.Volume
            readonly property int deviceIndex: model.DeviceIndex
            readonly property bool writable: model.VolumeWritable
            onEligibleChanged: mixer.streamUpdate?.restart()
            onAppKeyChanged: mixer.streamUpdate?.restart()
            onLabelChanged: mixer.streamUpdate?.restart()
        }
        onObjectAdded: (i,s) => { mixer.streams = mixer.streams.concat([s]); mixer.streamUpdate?.restart() }
        onObjectRemoved: (i,s) => { mixer.streams = mixer.streams.filter(o => o && o !== s); mixer.streamUpdate?.restart() }
    }
    readonly property Instantiator outputs: Instantiator {
        model: Audio.SinkModel {}
        delegate: QtObject {
            required property var model
            readonly property int pulseIndex: model.Index
            readonly property string node: model.Name
            readonly property string name: model.Description || node
            readonly property bool available: model.Name !== "auto_null"
        }
        onObjectAdded: (i,d) => mixer.devices = mixer.devices.concat([d])
        onObjectRemoved: (i,d) => mixer.devices = mixer.devices.filter(o => o && o !== d)
    }
    Component.onCompleted: {
        if (!prefs.value("format", 0)) {
            prefs.setValue("format", 1)
            prefs.sync()
        }
        reload()
    }
}
