import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as K
import org.kde.plasma.private.volume 0.1 as Audio
import org.kde.plasma.plasma5support as P5

ColumnLayout {
    id: desk
    required property var outputNames
    required property string helper
    required property bool presented
    signal refreshOutputs()
    readonly property bool menuOpen: choices.opened
    property var microphones: []
    property bool switching: false
    property string switchError: ""
    property string dropKey: ""
    property bool dropAfter: false
    readonly property var microphone: Audio.PreferredDevice.source
    spacing: 2

    function deviceLabel(node, fallback) {
        if (!node) return fallback
        const bytes = unescape(encodeURIComponent(node))
        const key = Array.from(bytes,c => c.charCodeAt(0).toString(16).padStart(2,"0")).join("")
        return outputNames.find(d => d.key === key)?.name || fallback
    }
    function selectDevice(command, device) {
        if (!device || switching || !Number.isInteger(device.id) || !/^(?:[0-9a-f]{2})+$/.test(device.key || "")) return
        switching = true; switchError = ""
        writer.connectSource(helper + " " + command + " " + device.id + " " + device.key)
    }
    P5.DataSource {
        id: writer
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source)
            if (source === desk.helper + " microphones") {
                try { desk.microphones = JSON.parse(data.stdout) } catch (_) { desk.microphones = [] }
                return
            }
            let ok = false
            try { ok = JSON.parse(data.stdout).ok === true } catch (_) {}
            desk.switchError = ok ? "" : source.startsWith(desk.helper + " input ")
                ? i18n("The microphone could not be changed. Check its connection and try again.")
                : i18n("The sound output could not be changed. Try again.")
            desk.switching = false
            desk.refreshOutputs()
        }
    }
    MixerModel {
        id: sound
        helper: desk.helper
        onDevicesChanged: if (desk.presented) namesDelay?.restart()
    }
    Timer { id: namesDelay; interval: 100; onTriggered: if (desk.presented) desk.refreshOutputs() }
    onPresentedChanged: { if (!presented) choices.close(); else namesDelay.restart() }
    Component.onCompleted: if (presented) namesDelay.restart()
    readonly property Component outputChooser: Component {
        C.AbstractButton {
            id: chooser
            readonly property bool hasOutputs: desk.outputNames.some(d => !d.none && d.key)
            text: desk.deviceLabel(sound.output?.name,sound.output?.description || i18n("Sound output"))
            Accessible.name: i18n("Sound output")
            enabled: chooser.hasOutputs && !desk.switching
            C.ToolTip.visible: hovered; C.ToolTip.text: text
            onClicked: choices.show("outputs",null)
            background: Rectangle {
                radius: height / 2; color: chooser.down || chooser.hovered ? "#343438" : "#242428"
                border.width: chooser.visualFocus ? 1 : 0; border.color: "#adcfff"
            }
            contentItem: RowLayout {
                spacing: 3
                K.Icon { Layout.preferredWidth: 13; Layout.preferredHeight: 13; source: "audio-volume-high"; color: "#dddddf" }
                C.Label { Layout.fillWidth: true; Layout.minimumWidth: 0; text: chooser.text; textFormat: Text.PlainText; elide: Text.ElideRight; font.pixelSize: 11; color: "#dddddf" }
                K.Icon { Layout.preferredWidth: 11; Layout.preferredHeight: 11; source: "arrow-down"; color: "#bdbdc3" }
            }

        }
    }
    C.Popup {
        id: choices
        parent: desk; anchors.centerIn: parent
        popupType: C.Popup.Item; focus: true; modal: true; dim: false; padding: 6; margins: 3
        width: Math.min(232,desk.width - 6)
        height: Math.min(desk.height - 6, 42 + Math.max(1,items.length) * 30)
        property string mode: ""
        property Item app
        function show(section, row) { app = row; mode = section; open(); optionsList.currentIndex = 0; optionsList.forceActiveFocus() }
        function choose(option) {
            if (!option || option.enabled === false) return
            if (option.next) { mode = option.next; optionsList.currentIndex = 0; return }
            option.run(); close()
        }
        onClosed: { mode = ""; app = null }
        onAppChanged: if (!app && (mode === "app" || mode === "routes") && opened) close()
        readonly property var items: {
            if (mode === "outputs" || mode === "inputs") {
                const input = mode === "inputs"
                return (input ? desk.microphones : desk.outputNames).filter(d => !d.none && d.key).map(d => ({
                    label: d.name, checked: d.default, run: () => desk.selectDevice(input ? "input" : "output",d)
                }))
            }
            const row = app
            if (!row) return []
            if (mode === "routes") return sound.devices.filter(d => d && d.available).map(d => ({
                label: desk.deviceLabel(d.node,d.name),
                checked: row.online && row.channels.every(s => s.deviceIndex === d.pulseIndex),
                run: () => sound.route(row.appKey,d)
            }))
            return [
                {label: row.pinned ? i18n("Unpin app") : i18n("Pin app"), icon:"pin", enabled:row.stable && !sound.saving, run: () => sound.pin(row.appKey,row.label,!row.pinned)},
                {label:i18n("Reset volume to 100%"), icon:"edit-undo", enabled:row.writable && row.percent !== 100, run: () => sound.level(row.appKey,100)},
                {label:i18n("Move left"), icon:"go-previous", enabled:row.canStep(-1), run: () => sound.step(row.index,-1)},
                {label:i18n("Move right"), icon:"go-next", enabled:row.canStep(1), run: () => sound.step(row.index,1)},
                {label:i18n("Play through"), icon:"audio-volume-high", enabled:row.online && sound.devices.some(d => d.available), next:"routes"}
            ]
        }
        background: Rectangle { radius: 15; color: "#232327"; border.color: "#4d4d54"; border.width: 1 }
        contentItem: ColumnLayout {
            spacing: 0
            RowLayout {
                Layout.fillWidth: true; Layout.preferredHeight: 28; spacing: 4
                IslandButton { visible: choices.mode === "routes"; plain: true; icon.name: "go-previous"; text: i18n("Back"); onClicked: choices.mode = "app" }
                C.Label {
                    Layout.fillWidth: true; Layout.minimumWidth: 0; leftPadding: 6; elide: Text.ElideRight
                    text: choices.mode === "inputs" ? i18n("Microphones") : choices.mode === "outputs" ? i18n("Sound output") :
                        choices.mode === "routes" ? i18n("Play through") : choices.app?.label ?? ""
                    font.pixelSize: 12; font.weight: Font.DemiBold; color: "#e9e9ed"; textFormat: Text.PlainText
                }
                IslandButton { plain: true; icon.name:"window-close"; text:i18n("Close"); onClicked: choices.close() }
            }
            ListView {
                id: optionsList
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                model: choices.items; boundsBehavior: Flickable.StopAtBounds
                C.ScrollBar.vertical: C.ScrollBar {}
                Keys.onReturnPressed: choices.choose(choices.items[currentIndex])
                Keys.onSpacePressed: choices.choose(choices.items[currentIndex])
                delegate: C.AbstractButton {
                    id: optionButton
                    required property var modelData
                    required property int index
                    width: optionsList.width; height: 30
                    text: modelData.label; enabled: modelData.enabled !== false
                    Accessible.name: text; Accessible.role: Accessible.MenuItem
                    Accessible.description: modelData.checked ? i18n("Selected") : ""
                    onClicked: choices.choose(modelData)
                    background: Rectangle { radius: 7; color: optionButton.hovered || optionButton.visualFocus ||
                        (optionsList.activeFocus && optionButton.ListView.isCurrentItem) ? "#424249" : "transparent" }
                    contentItem: RowLayout {
                        spacing: 5; opacity: optionButton.enabled ? 1 : 0.4
                        K.Icon { Layout.preferredWidth: 16; Layout.preferredHeight: 16; Layout.leftMargin: 6
                            source: optionButton.modelData.icon || (optionButton.modelData.checked ? "checkmark" : ""); color: "#e8e8ed" }
                        C.Label { Layout.fillWidth: true; Layout.minimumWidth: 0; text: optionButton.text; elide: Text.ElideRight
                            textFormat: Text.PlainText; color: "#f6f6f8"; font.pixelSize: 12 }
                        K.Icon { Layout.preferredWidth: 12; Layout.preferredHeight: 12; visible: !!optionButton.modelData.next; source: "go-next"; color: "#aaaaaf" }
                    }
                }
            }
            C.Label { visible: !choices.items.length; Layout.alignment: Qt.AlignHCenter; text: i18n("Unavailable"); color: "#bdbdc3" }
        }
    }
    RowLayout {
        Layout.fillWidth: true; Layout.fillHeight: true
        spacing: 4
        IslandFader {
            Layout.preferredWidth: desk.width < 350 ? 54 : 68; Layout.maximumWidth: Layout.preferredWidth; Layout.minimumWidth: Layout.preferredWidth; Layout.fillHeight: true
            title: i18n("Output"); levelLabel: i18n("Output volume")
            online: sound.ready && !!sound.output && sound.output.name !== "auto_null"
            muted: sound.output?.muted ?? false
            symbol: muted ? "audio-volume-muted" : "audio-volume-high"
            muteLabel: muted ? i18n("Unmute output") : i18n("Mute output")
            percent: Math.round((sound.output?.volume || 0) * 100 / sound.normal)
            onMuteRequested: if (online) sound.output.muted = !muted
            onLevelRequested: value => { if (online) sound.output.volume = Math.round(value * sound.normal / 100) }
        }
        IslandFader {
            Layout.preferredWidth: desk.width < 350 ? 54 : 68; Layout.maximumWidth: Layout.preferredWidth; Layout.minimumWidth: Layout.preferredWidth; Layout.fillHeight: true
            hasOptions: true; onOptionsRequested: { writer.connectSource(desk.helper + " microphones"); choices.show("inputs",null) }
            title: i18n("Microphone"); levelLabel: i18n("Microphone volume")
            online: sound.ready && !!desk.microphone && !desk.microphone.name.endsWith(".monitor")
            visible: online
            muted: desk.microphone?.muted ?? false
            symbol: muted ? "microphone-sensitivity-muted" : "microphone-sensitivity-high-symbolic"
            muteLabel: muted ? i18n("Unmute microphone") : i18n("Mute microphone")
            percent: Math.round((desk.microphone?.volume || 0) * 100 / sound.normal)
            onMuteRequested: if (online) desk.microphone.muted = !muted
            onLevelRequested: value => { if (online) desk.microphone.volume = Math.round(value * sound.normal / 100) }
        }
        Rectangle { Layout.fillHeight: true; Layout.preferredWidth: 1; Layout.topMargin: 8; Layout.bottomMargin: 8; color: "#30ffffff" }
        Item {
            Layout.fillWidth: true; Layout.preferredWidth: 260; Layout.minimumWidth: 0; Layout.fillHeight: true
            C.Label {
                anchors.centerIn: parent; width: Math.max(1,parent.width - 12); visible: !apps.count
                horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap; color: "#a7a7af"
                text: sound.ready ? i18n("Apps appear here when they play sound.") : i18n("Waiting for the audio service…")
            }
            ListView {
                id: apps
                anchors.fill: parent
                orientation: ListView.Horizontal; clip: true; boundsBehavior: Flickable.StopAtBounds
                model: sound.rows
                interactive: contentWidth > width
                C.ScrollBar.horizontal: C.ScrollBar { policy: apps.interactive ? C.ScrollBar.AlwaysOn : C.ScrollBar.AlwaysOff }
                move: Transition { NumberAnimation { property: "x"; duration: K.Units.shortDuration; easing.type: Easing.OutCubic } }
                moveDisplaced: Transition { NumberAnimation { property: "x"; duration: K.Units.shortDuration; easing.type: Easing.OutCubic } }
                delegate: IslandFader {
                    id: app
                    required property int index
                    required property string appKey
                    required property string label
                    required property bool pinned
                    readonly property var channels: sound.matching(appKey)
                    readonly property var first: channels[0]
                    readonly property bool stable: !appKey.startsWith("stream:")
                    width: Math.min(92,apps.width); height: apps.height - (apps.interactive ? 9 : 0)
                    application: true; marked: pinned; title: label
                    symbol: first?.meta["application.icon_name"] || first?.client["application.icon_name"] || first?.identity || "applications-multimedia"
                    levelLabel: i18n("Volume for %1",label)
                    online: channels.length > 0
                    writable: channels.some(s => s.writable)
                    muted: online && channels.every(s => s.muted)
                    percent: Math.round(channels.reduce((gain,s) => Math.max(gain,s.gain),0) * 100 / sound.normal)
                    maximum: sound.maxAppPercent
                    muteLabel: muted ? i18n("Unmute %1",label) : i18n("Mute %1",label)
                    onMuteRequested: sound.mute(appKey,!muted)
                    onLevelRequested: value => sound.level(appKey,value)
                    onOptionsRequested: choices.show("app",app)
                    function canStep(delta) {
                        const n = index + delta
                        const next = n >= 0 && n < sound.rows.count ? sound.rows.get(n) : null
                        return !sound.saving && stable && !!next && next.pinned === pinned && !next.appKey.startsWith("stream:")
                    }
                    TapHandler { acceptedButtons: Qt.RightButton; onTapped: choices.show("app",app) }
                    HoverHandler { parent: app.nameItem; enabled: reorder.enabled; cursorShape: reorder.active ? Qt.ClosedHandCursor : Qt.OpenHandCursor }
                    DragHandler {
                        id: reorder; parent: app.nameItem; target: null
                        enabled: app.canStep(-1) || app.canStep(1)
                        onGrabChanged: transition => {
                            if (transition === PointerDevice.UngrabExclusive) {
                                if (desk.dropKey) sound.move(app.appKey,desk.dropKey,desk.dropAfter)
                                desk.dropKey = ""
                            } else if (transition === PointerDevice.CancelGrabExclusive) desk.dropKey = ""
                        }
                        onTranslationChanged: {
                            if (!active) return
                            const p = apps.contentItem.mapFromItem(null,centroid.scenePosition.x,centroid.scenePosition.y)
                            const other = apps.itemAt(p.x,p.y)
                            desk.dropKey = other && other !== app && other.stable && other.pinned === app.pinned ? other.appKey : ""
                            if (desk.dropKey) desk.dropAfter = p.x >= other.x + other.width / 2
                        }
                    }
                    Rectangle {
                        parent: apps.contentItem
                        x: app.x + (desk.dropAfter ? app.width - width : 0); y: 4
                        width: 2; height: app.height - 8; color: "#adcfff"; z: 2
                        visible: desk.dropKey === app.appKey
                    }

                }
            }
        }
    }
    C.Label {
        Layout.fillWidth: true; wrapMode: Text.Wrap; color: "#ffb469"
        text: desk.switchError || (sound.saveFailed ? i18n("Could not save the mixer layout. Try again.") : "")
        visible: !!text
    }
}
