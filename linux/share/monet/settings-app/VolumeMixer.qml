import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: page
    property bool showOutput: true
    property var outputNames: []
    // The parent already knows the friendly names shown in Monet Sound.
    function deviceLabel(node, fallback) {
        if (!node || !outputNames.length) return fallback
        const bytes = unescape(encodeURIComponent(node))
        const key = Array.from(bytes, c => c.charCodeAt(0).toString(16).padStart(2, "0")).join("")
        return outputNames.find(d => d.key === key)?.name || fallback
    }
    signal outputsChangedWhileOpen()
    readonly property int appCount: apps.count
    property string dropKey: ""
    property bool dropAfter: false
    readonly property real contentHeight: (master.visible ? master.implicitHeight + spacing : 0)
        + (apps.count ? apps.contentHeight : empty.implicitHeight)
    spacing: Kirigami.Units.smallSpacing
    MixerModel {
        id: sound
        objectName: "appMixerModel"
        onDevicesChanged: Qt.callLater(page.outputsChangedWhileOpen)
    }
    // A second mixer can be open in Settings or on another screen.
    Connections {
        target: page.Window.window
        function onActiveChanged() { if (page.Window.window?.active) sound.reload() }
    }

    component SoundButton: C.ToolButton {
        display: C.AbstractButton.IconOnly
        Accessible.name: text
        C.ToolTip.visible: hovered
        C.ToolTip.text: text
    }
    RowLayout {
        id: master
        Layout.fillWidth: true
        visible: page.showOutput && sound.ready && sound.output && sound.output.name !== "auto_null"
        readonly property int percent: Math.round((sound.output?.volume || 0) * 100 / sound.normal)
        SoundButton {
            text: sound.output?.muted ? i18n("Unmute output") : i18n("Mute output")
            icon.name: sound.output?.muted ? "audio-volume-muted" : "audio-volume-high"
            onClicked: if (sound.output) sound.output.muted = !sound.output.muted
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 0
            C.Label {
                Layout.fillWidth: true; text: page.deviceLabel(sound.output?.name, sound.output?.description || i18n("Output volume"))
                textFormat: Text.PlainText; elide: Text.ElideRight; font.bold: true
            }
            C.Slider {
                Layout.fillWidth: true
                Accessible.name: i18n("Output volume")
                from: 0; to: 100; stepSize: 1; value: master.percent
                onMoved: if (sound.output) sound.output.volume = Math.round(value * sound.normal / 100)
            }
        }
        C.Label { text: i18n("%1%", master.percent) }
    }
    C.Label {
        id: empty
        visible: !apps.count
        Layout.fillWidth: true; wrapMode: Text.Wrap
        text: sound.ready ? i18n("Apps appear here when they play sound.") : i18n("Waiting for the audio service…")
    }
    C.Label {
        visible: sound.saveFailed
        Layout.fillWidth: true
        wrapMode: Text.Wrap
        text: i18n("Could not save the mixer layout. Try again.")
    }
    ListView {
        id: apps
        objectName: "mixerAppList"
        Layout.fillWidth: true; Layout.fillHeight: true
        interactive: contentHeight > height + 1
        model: sound.rows; clip: true; boundsBehavior: Flickable.StopAtBounds
        spacing: Kirigami.Units.smallSpacing
        C.ScrollBar.vertical: C.ScrollBar {}
        move: Transition { NumberAnimation { property: "y"; duration: Kirigami.Units.shortDuration } }
        moveDisplaced: Transition { NumberAnimation { property: "y"; duration: Kirigami.Units.shortDuration } }
        delegate: ColumnLayout {
            id: row
            required property int index
            required property string appKey
            required property string label
            required property bool pinned
            readonly property var channels: sound.matching(appKey)
            readonly property bool online: channels.length > 0
            readonly property bool muted: online && channels.every(s => s.muted)
            readonly property int gain: channels.reduce((max,s) => Math.max(max,s.gain),0)
            readonly property int percent: Math.round(gain * 100 / sound.normal)
            readonly property bool stable: !appKey.startsWith("stream:")
            width: apps.width - (apps.contentHeight > apps.height ? Kirigami.Units.smallSpacing * 2 : 0)
            spacing: 0
            function canStep(by) {
                const n = index + by
                const neighbor = n >= 0 && n < sound.rows.count ? sound.rows.get(n) : null
                return !sound.saving && stable && !!neighbor && neighbor.pinned === pinned && !neighbor.appKey.startsWith("stream:")
            }
            RowLayout {
                Layout.fillWidth: true
                SoundButton {
                    text: row.muted ? i18n("Unmute %1", row.label) : i18n("Mute %1", row.label)
                    icon.name: row.muted ? "audio-volume-muted" : "audio-volume-medium"
                    enabled: row.online
                    onClicked: sound.mute(row.appKey,!row.muted)
                }
                C.Label {
                    Layout.fillWidth: true; elide: Text.ElideRight; textFormat: Text.PlainText
                    text: row.label; font.bold: true
                    HoverHandler { cursorShape: reorder.active ? Qt.ClosedHandCursor : enabled ? Qt.OpenHandCursor : Qt.ArrowCursor; enabled: reorder.enabled }
                    DragHandler {
                        id: reorder
                        enabled: row.stable && (row.canStep(-1) || row.canStep(1))
                        target: null
                        onGrabChanged: transition => {
                            if (transition === PointerDevice.UngrabExclusive) {
                                if (page.dropKey) sound.move(row.appKey, page.dropKey, page.dropAfter)
                                page.dropKey = ""
                            } else if (transition === PointerDevice.CancelGrabExclusive) page.dropKey = ""
                        }
                        onTranslationChanged: {
                            if (!active) return
                            const pos = apps.contentItem.mapFromItem(null,centroid.scenePosition.x,centroid.scenePosition.y)
                            const other = apps.itemAt(pos.x,pos.y)
                            page.dropKey = other && other !== row && other.pinned === row.pinned && other.stable ? other.appKey : ""
                            if (page.dropKey) page.dropAfter = pos.y >= other.y + other.height / 2
                        }
                    }
                }
                Kirigami.Icon { visible: row.pinned; source: "pin"; implicitWidth: 14; implicitHeight: 14; Accessible.name: i18n("Pinned") }
                C.Label { text: row.online ? i18n("%1%",row.percent) : i18n("Not playing"); opacity: 0.8 }
                SoundButton {
                    id: more
                    text: i18n("Options for %1",row.label); icon.name: "overflow-menu"
                    onClicked: options.popup()
                    C.Menu {
                        id: options
                        C.MenuItem {
                            text: row.pinned ? i18n("Unpin app") : i18n("Pin app")
                            enabled: row.stable && !sound.saving
                            onTriggered: sound.pin(row.appKey,row.label,!row.pinned)
                        }
                        C.MenuItem { text: i18n("Move up"); enabled: row.canStep(-1); onTriggered: sound.step(row.index,-1) }
                        C.MenuItem { text: i18n("Move down"); enabled: row.canStep(1); onTriggered: sound.step(row.index,1) }
                        C.Menu {
                            id: routes
                            title: i18n("Play through")
                            enabled: row.online && count > 0
                            Instantiator {
                                model: sound.devices.filter(d => d && d.available)
                                delegate: C.MenuItem {
                                    required property var modelData
                                    text: page.deviceLabel(modelData.node, modelData.name); checkable: true
                                    checked: row.online && row.channels.every(s => s.deviceIndex === modelData.pulseIndex)
                                    onTriggered: sound.route(row.appKey,modelData)
                                }
                                onObjectAdded: (i,item) => routes.insertItem(i,item)
                                onObjectRemoved: (i,item) => routes.removeItem(item)
                            }
                        }
                    }
                }
            }
            Rectangle {
                // An overlay takes no layout space and keeps the pointer's drop target still.
                parent: row.parent
                x: row.x; y: row.y + (page.dropAfter ? row.height : 0)
                width: row.width; height: 2; z: 2
                color: Kirigami.Theme.highlightColor
                visible: page.dropKey === row.appKey
            }
            C.Slider {
                Layout.fillWidth: true; visible: row.online
                enabled: row.channels.some(s => s.writable)
                Accessible.name: i18n("Volume for %1",row.label)
                from: 0; to: 100; stepSize: 1; value: row.percent
                onMoved: sound.level(row.appKey,value)
            }
        }
    }
}
