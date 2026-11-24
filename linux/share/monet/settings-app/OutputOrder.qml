import QtQuick
import QtQuick.Layouts

SettingsControls.Card {
    id: card
    objectName: "search-output-order"
    required property var host
    property bool editing: false
    property bool busy: false
    property bool automatic: false
    property string version: ""
    property string issue: ""
    property var ranked: []
    property var connected: []
    property var original: ({})
    readonly property bool dirty: !!version && (automatic !== original.enabled
        || JSON.stringify(ranked) !== JSON.stringify(original.devices))
    readonly property var unranked: connected.filter(d => !ranked.some(r => same(r, d)))
    function same(a, b) { return a.key === b.key && a.port === b.port }
    function entry(d) { return connected.find(c => same(c, d)) }
    function applyState(data) {
        connected = data.connected
        original = {enabled: data.enabled, devices: data.devices}
        automatic = data.enabled
        ranked = data.devices
        version = data.revision
    }
    function load(keepDraft) {
        busy = true
        issue = ""
        host.ask("output-order get", out => {
            busy = false
            const data = host.json(out, {})
            if (data.ok !== true) { issue = i18n("Could not read your output preferences."); return }
            if (keepDraft && version === data.revision) connected = data.connected
            else applyState(data)
        })
    }
    function edit() { editing = true; load(false) }
    Component.onCompleted: if (host.currentAnchor === "output-order") edit()
    Connections {
        target: card.host
        function onCurrentAnchorChanged() {
            if (card.host.currentAnchor === "output-order" && !card.editing) card.edit()
        }
    }
    function add(d) {
        if (ranked.length === 0) automatic = true
        ranked = ranked.concat([d])
    }
    function removeAt(index) {
        ranked = ranked.filter((_, i) => i !== index)
        if (!ranked.length) automatic = false
    }
    function move(index, by) {
        const next = ranked.slice()
        next.splice(index + by, 0, next.splice(index, 1)[0])
        ranked = next
    }
    function save() {
        busy = true
        const devices = ranked.map(d => entry(d) || d)
        const data = host.hex(JSON.stringify({enabled: automatic, devices: devices, revision: version}))
        host.call(["helper", "output-order", "save", data], out => {
            busy = false
            const answer = host.json(out, {})
            if (answer.ok === true) { applyState(answer); editing = false; issue = ""; host.refresh(); return }
            if (answer.problem === "changed") {
                applyState(answer)
                issue = i18n("These preferences changed elsewhere. Review the new order and try again.")
            } else issue = i18n("Could not apply your output order. Check that your audio session is running and try again.")
        })
    }
    SettingsControls.SettingRow {
        tone: card.tone; divider: false
        title: i18n("Preferred output order")
        detail: i18n("Choose which headphones or speakers to use when devices connect or disconnect.")
        SettingsControls.Pill {
            tone: card.tone; visible: !card.editing
            text: i18n("Manage…"); Accessible.name: i18n("Manage preferred sound outputs")
            objectName: "manageOutputOrder"; onClicked: card.edit()
        }
    }
    SettingsControls.SettingRow {
        tone: card.tone; visible: card.editing && !!card.version
        title: i18n("Switch outputs automatically")
        detail: i18n("Your first available choice plays. You can still switch manually until the next device change.")
        tappable: !card.busy && card.ranked.length > 0; checkable: true; checked: card.automatic
        onTapped: card.automatic = !card.automatic
        SettingsControls.Switch { tone: card.tone; active: card.automatic }
    }
    Repeater {
        model: card.editing ? card.ranked : []
        SettingsControls.SettingRow {
            required property var modelData
            required property int index
            tone: card.tone; strong: false
            readonly property var liveDevice: card.entry(modelData)
            readonly property string deviceLabel: liveDevice?.name || modelData.name
            title: i18n("%1. %2", index + 1, deviceLabel)
            detail: liveDevice ? "" : i18n("Disconnected")
            Row {
                spacing: 4
                SettingsControls.Pill {
                    tone: card.tone; text: "↑"; Accessible.name: i18n("Move %1 up", deviceLabel)
                    enabledPill: !card.busy && index > 0; onClicked: card.move(index, -1)
                }
                SettingsControls.Pill {
                    tone: card.tone; text: "↓"; Accessible.name: i18n("Move %1 down", deviceLabel)
                    enabledPill: !card.busy && index + 1 < card.ranked.length; onClicked: card.move(index, 1)
                }
                SettingsControls.Pill {
                    tone: card.tone; text: i18n("Remove"); Accessible.name: i18n("Remove %1 from the order", deviceLabel)
                    enabledPill: !card.busy; onClicked: card.removeAt(index)
                }
            }
        }
    }
    Repeater {
        model: card.editing ? card.unranked : []
        SettingsControls.SettingRow {
            required property var modelData
            tone: card.tone; strong: false; title: modelData.name
            SettingsControls.Pill {
                tone: card.tone; text: i18n("Add"); Accessible.name: i18n("Add %1 to the order", modelData.name)
                enabledPill: !card.busy && card.ranked.length < 48; onClicked: card.add(modelData)
            }
        }
    }
    SettingsControls.SettingRow {
        tone: card.tone; visible: card.editing
        strong: false
        title: card.issue || (card.busy ? i18n("Updating…") : !card.ranked.length && !card.connected.length
            ? i18n("Connect an audio output, then refresh.") : "")
        Flow {
            spacing: 4
            width: Math.min(parent.controlsAvailableWidth, refreshButton.implicitWidth + cancelButton.implicitWidth + applyButton.implicitWidth + 2 * spacing)
            height: childrenRect.height
            SettingsControls.Pill {
                id: refreshButton
                tone: card.tone; text: i18n("Refresh"); enabledPill: !card.busy; onClicked: card.load(true)
            }
            SettingsControls.Pill {
                id: cancelButton
                tone: card.tone; text: card.dirty ? i18n("Cancel") : i18n("Done")
                enabledPill: !card.busy; onClicked: { card.editing = false; card.issue = "" }
            }
            SettingsControls.Pill {
                id: applyButton
                tone: card.tone; kind: "lily"; text: i18n("Apply"); enabledPill: !card.busy && card.dirty; onClicked: card.save()
            }
        }
    }
}
