/*
 * Sound, in the clock island beside Quick Settings: how loud at a glance and under the wheel
 * (a middle click mutes), and a glass popover with the volume, where the sound plays and the
 * apps playing. In place of KDE's own item in the tray, whose popover is KDE's (the volume
 * keys and their on-screen level are KDE's audio shortcuts service, which needs no item).
 * wpctl and the `monet-quick` helper do the work; this draws it.
 */
import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Shapes
import QtQuick.Controls as QQC2
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property string helper: "@LIBEXECDIR@/monet-quick"
    readonly property string level: "wpctl get-volume @DEFAULT_AUDIO_SINK@"
    readonly property real speed: Kirigami.Units.longDuration / 200
    // Mist or smoke, the way monet-light set the colors.
    readonly property bool smoke: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    // How loud (0-100; null with no sound at all) and whether it's muted: wpctl, every two seconds.
    property var volume: null
    property bool muted: false
    // Where it can play and the apps playing (monet-quick sound): while open, and now and then.
    property var sound: ({ outputs: [], apps: [], inputs: [], microphone: null })
    readonly property var microphone: sound.microphone || null
    property bool microphoneBusy: false
    property string microphoneMessage: ""
    property bool outputBusy: false
    property string outputMessage: ""
    property bool soundKnown: false
    // While a slider is held, don't let a refresh move it.
    property bool dragging: false
    // Nowhere to play: PipeWire's stand-in only (monet-quick leaves it out).
    readonly property bool silent: soundKnown && sound.outputs.length === 0
    readonly property string playing: (sound.outputs.find(o => o.default) || {}).name || ""

    Plasmoid.icon: silent || muted || !volume ? "audio-volume-muted"
        : volume < 34 ? "audio-volume-low" : volume < 67 ? "audio-volume-medium" : "audio-volume-high"
    Plasmoid.status: PlasmaCore.Types.ActiveStatus
    Plasmoid.contextualActions: [TaskManagerAction {}]
    toolTipMainText: i18n("Sound")
    toolTipSubText: silent ? i18n("No speakers or headphones") : muted ? i18n("Muted")
        : typeof volume === "number" ? i18n("Volume %1%", volume) : ""

    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            const out = data["stdout"] || ""
            if (source === root.level) {
                const found = out.match(/Volume:\s*([0-9.]+)/)
                if (!root.dragging) {
                    root.volume = found ? Math.round(parseFloat(found[1]) * 100) : null
                    root.muted = out.indexOf("[MUTED]") !== -1
                }
            } else if (source === root.helper + " sound") {
                try {
                    const next = JSON.parse(out)
                    if (!root.dragging) {
                        const before = root.microphone || {}
                        const after = next.microphone || {}
                        if (!root.microphoneBusy && (before.id !== after.id || before.muted !== after.muted))
                            root.microphoneMessage = ""
                        root.sound = next
                    }
                    root.soundKnown = true
                } catch (e) {
                }
            } else if (source.startsWith(root.helper + " output ")) {
                root.outputBusy = false
                try {
                    const result = JSON.parse(out)
                    if (Array.isArray(result.outputs)) root.sound = Object.assign({}, root.sound, { outputs: result.outputs })
                    root.outputMessage = result.ok === true && data["exit code"] === 0 ? ""
                        : i18n("The sound output could not be changed. Check its connection and try again.")
                } catch (e) {
                    root.outputMessage = i18n("The sound output could not be changed. Try again.")
                }
                root.refresh()
            } else if (source.startsWith(root.helper + " mic-mute ") || source.startsWith(root.helper + " input ")) {
                root.microphoneBusy = false
                try {
                    const result = JSON.parse(out)
                    if (result.sound) root.sound = result.sound
                    root.microphoneMessage = result.ok
                        ? (root.microphone && root.microphone.muted ? i18n("Microphone muted") : i18n("Microphone ready"))
                        : i18n("The microphone could not be changed. Check its connection and try again.")
                } catch (e) {
                    root.microphoneMessage = i18n("The microphone could not be changed. Try again.")
                }
                root.look()
            } else {
                root.refresh()
                root.look()
            }
        }
    }

    function refresh() {
        runner.connectSource(level)
    }
    function look() {
        runner.connectSource(helper + " sound")
    }
    // Arguments are fixed words or numbers, never anyone's text.
    function run(args) {
        runner.connectSource(helper + " " + args)
    }

    // Sliders send their latest value at most every 120 ms, not every step.
    property var pending: ({})
    function queue(what, value) {
        pending[what] = Math.round(value)
        flush.start()
    }
    Timer {
        id: flush
        interval: 120
        onTriggered: {
            for (const what in root.pending) {
                root.run(what + " " + root.pending[what])
            }
            root.pending = {}
        }
    }

    function setVolume(value) {
        if (volume === null) {
            return
        }
        volume = Math.max(0, Math.min(100, Math.round(value)))
        muted = false
        queue("volume", volume)
    }
    function toggleMute() {
        muted = !muted
        run("mute " + (muted ? "on" : "off"))
    }
    function playThrough(output) {
        if (!Number.isInteger(output.id) || outputBusy) {
            return
        }
        outputBusy = true
        outputMessage = ""
        run("output " + output.id)
    }
    function muteMicrophone() {
        if (!microphone || microphoneBusy) return
        microphoneBusy = true
        microphoneMessage = ""
        run("mic-mute " + microphone.id + " " + (microphone.muted ? "off" : "on"))
    }
    function useMicrophone(input) {
        if (!Number.isInteger(input.id) || microphoneBusy) return
        microphoneBusy = true
        microphoneMessage = ""
        run("input " + input.id)
    }

    Timer {
        interval: 2000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: if (!root.dragging) root.refresh()
    }
    // Open: where it plays and the apps, kept up to date. Closed: now and then, so the icon
    // knows when there's nowhere to play.
    Timer {
        interval: root.expanded ? 3000 : 60000
        repeat: true
        running: true
        triggeredOnStart: true
        onTriggered: if (!root.dragging) root.look()
    }
    onExpandedChanged: if (root.expanded) look()
    // Nothing to set up: no KDE settings window from its menu.
    Component.onCompleted: {
        try {
            Plasmoid.removeInternalAction("configure")
        } catch (e) {
        }
    }

    // The light caught in a pebble's edge, as in Quick Settings.
    component GlassRim: Rectangle {
        required property bool smoke
        anchors.fill: parent
        radius: parent.radius
        color: "transparent"
        border.width: 1
        border.color: smoke ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(1, 1, 1, 0.7)
    }

    // A card of glass on the glass, holding rows.
    component Pane: Rectangle {
        default property alias rows: paneColumn.data
        readonly property bool smoke: Kirigami.Theme.backgroundColor.hslLightness < 0.5
        Layout.fillWidth: true
        implicitHeight: paneColumn.implicitHeight + 20
        radius: 18
        color: smoke ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.34)
        GlassRim {
            smoke: parent.smoke
        }
        ColumnLayout {
            id: paneColumn
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            anchors.leftMargin: 14
            anchors.rightMargin: 14
            spacing: 10
        }
    }

    compactRepresentation: MouseArea {
        id: compact
        property real turned: 0
        // As wide as the bar is high, as Plasma's own icons in it are.
        Layout.minimumWidth: Plasmoid.formFactor === PlasmaCore.Types.Vertical ? 0 : height
        Layout.minimumHeight: Plasmoid.formFactor === PlasmaCore.Types.Vertical ? width : 0
        hoverEnabled: true
        activeFocusOnTab: true
        Accessible.role: Accessible.Button
        Accessible.name: i18n("Sound controls")
        Accessible.onPressAction: root.expanded = !root.expanded
        Keys.onSpacePressed: root.expanded = !root.expanded
        Keys.onReturnPressed: root.expanded = !root.expanded
        acceptedButtons: Qt.LeftButton | Qt.MiddleButton
        onClicked: mouse => {
            if (mouse.button === Qt.MiddleButton) {
                root.toggleMute()
            } else {
                root.expanded = !root.expanded
            }
        }
        // A notch of the wheel is 5%; a touchpad's small turns add up to one.
        onWheel: wheel => {
            turned += wheel.angleDelta.y !== 0 ? wheel.angleDelta.y : -wheel.angleDelta.x
            while (Math.abs(turned) >= 120) {
                root.setVolume((root.volume || 0) + (turned > 0 ? 5 : -5))
                turned += turned > 0 ? -120 : 120
            }
        }
        // The tray's size, beside its icons.
        Kirigami.Icon {
            anchors.centerIn: parent
            width: Kirigami.Units.iconSizes.smallMedium
            height: width
            source: Plasmoid.icon
            active: compact.containsMouse
        }
        Rectangle {
            anchors.fill: parent; anchors.margins: 3
            radius: 10; color: "transparent"
            border.width: compact.activeFocus ? 2 : 0
            border.color: Kirigami.Theme.highlightColor
        }
    }

    fullRepresentation: PlasmaExtras.Representation {
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true
        Layout.preferredWidth: Math.min(Kirigami.Units.gridUnit * 21, Screen.width - 48)
        Layout.preferredHeight: Math.min(column.implicitHeight + Kirigami.Units.largeSpacing * 2, Screen.height - 112)
        Layout.maximumWidth: Layout.preferredWidth
        Layout.minimumHeight: Layout.preferredHeight
        Layout.maximumHeight: Layout.preferredHeight
        collapseMarginsHint: true
        Keys.onEscapePressed: root.expanded = false

        QQC2.ScrollView {
          id: scroll
          anchors.fill: parent
          anchors.margins: Kirigami.Units.largeSpacing
          clip: true
          contentWidth: availableWidth
          QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
          Connections {
              target: scroll.Window.window
              function onActiveFocusItemChanged() {
                  const item = scroll.Window.window.activeFocusItem;
                  let ancestor = item;
                  while (ancestor && ancestor !== scroll) ancestor = ancestor.parent;
                  if (!ancestor || !scroll.contentItem.contentItem) return;
                  const flick = scroll.contentItem;
                  const pos = item.mapToItem(flick.contentItem, 0, 0);
                  if (pos.y < flick.contentY) flick.contentY = Math.max(0, pos.y - 8);
                  else if (pos.y + item.height > flick.contentY + flick.height)
                      flick.contentY = Math.min(Math.max(0, flick.contentHeight - flick.height), pos.y + item.height - flick.height + 8);
              }
          }
        ColumnLayout {
            id: column
            width: scroll.availableWidth - Kirigami.Units.smallSpacing
            spacing: Kirigami.Units.largeSpacing

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    horizontalAlignment: Text.AlignLeft
                    text: i18n("Sound")
                    color: Kirigami.Theme.textColor
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: 20
                    Layout.leftMargin: 2
                }
                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    Layout.leftMargin: 2
                    visible: text !== ""
                    opacity: 0.66
                    font: Kirigami.Theme.smallFont
                    elide: Text.ElideRight
                    text: root.silent ? i18n("No speakers or headphones")
                        : root.playing !== "" ? i18n("Playing through %1", root.playing) : ""
                }
            }

            // How loud, and a round pebble that mutes.
            Pane {
                visible: !root.silent && root.volume !== null
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 10
                    Rectangle {
                        id: muteButton
                        Layout.preferredWidth: 34
                        Layout.preferredHeight: 34
                        radius: 17
                        color: root.muted ? "#357F72"
                            : root.smoke ? Qt.rgba(1, 1, 1, muteHover.hovered ? 0.16 : 0.08) : Qt.rgba(1, 1, 1, muteHover.hovered ? 0.6 : 0.4)
                        scale: muteTap.pressed ? 0.94 : 1
                        Behavior on scale { NumberAnimation { duration: Math.round(160 * root.speed) } }
                        activeFocusOnTab: true
                        Keys.onSpacePressed: root.toggleMute()
                        Keys.onReturnPressed: root.toggleMute()
                        border.width: activeFocus ? 2 : 0
                        border.color: "#357F72"
                        Accessible.role: Accessible.Button
                        Accessible.name: root.muted ? i18n("Unmute") : i18n("Mute")
                        Accessible.onPressAction: root.toggleMute()
                        Kirigami.Icon {
                            anchors.centerIn: parent
                            width: 18
                            height: 18
                            source: Plasmoid.icon
                            isMask: true
                            color: root.muted ? "#FFFFFF" : Kirigami.Theme.textColor
                        }
                        HoverHandler {
                            id: muteHover
                            cursorShape: Qt.PointingHandCursor
                        }
                        TapHandler {
                            id: muteTap
                            onTapped: root.toggleMute()
                        }
                    }
                    PlasmaComponents.Slider {
                        Layout.fillWidth: true
                        from: 0
                        to: 100
                        stepSize: 1
                        value: root.volume || 0
                        opacity: root.muted ? 0.5 : 1
                        Accessible.name: i18n("Volume")
                        onPressedChanged: root.dragging = pressed
                        onMoved: root.setVolume(value)
                    }
                    PlasmaComponents.Label {
                        Layout.preferredWidth: 36
                        horizontalAlignment: Text.AlignRight
                        text: root.muted ? "" : i18n("%1%", root.volume || 0)
                        opacity: 0.7
                        font.features: ({ "tnum": 1 })
                    }
                }
            }

            // Where the sound plays, when it could play in more than one place: a tap moves it.
            PlasmaComponents.Label {
                Layout.fillWidth: true
                visible: root.outputBusy || root.outputMessage !== ""
                wrapMode: Text.Wrap
                text: root.outputBusy ? i18n("Changing sound output…") : root.outputMessage
            }
            PlasmaComponents.Label {
                Layout.leftMargin: 2
                visible: root.sound.outputs.length > 1
                opacity: 0.66
                font: Kirigami.Theme.smallFont
                text: i18n("Play sound through")
            }
            Pane {
                visible: root.sound.outputs.length > 1
                Repeater {
                    model: root.sound.outputs
                    Rectangle {
                        id: place
                        required property var modelData
                        readonly property bool chosen: modelData.default === true
                        Layout.fillWidth: true
                        implicitHeight: 34
                        radius: 12
                        color: chosen ? Qt.rgba(0.208, 0.498, 0.447, root.smoke ? 0.4 : 0.22)
                            : placeHover.hovered ? (root.smoke ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.4)) : "transparent"
                        activeFocusOnTab: true
                        Keys.onSpacePressed: root.playThrough(modelData)
                        Keys.onReturnPressed: root.playThrough(modelData)
                        border.width: activeFocus ? 2 : 0
                        border.color: "#357F72"
                        Accessible.role: Accessible.RadioButton
                        Accessible.name: i18nc("%1 is speakers, headphones or a screen", "Play through %1", modelData.name)
                        Accessible.checked: chosen
                        PlasmaComponents.Label {
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            text: place.modelData.name
                            elide: Text.ElideRight
                            font.weight: place.chosen ? Font.DemiBold : Font.Normal
                        }
                        HoverHandler {
                            id: placeHover
                            cursorShape: Qt.PointingHandCursor
                        }
                        TapHandler {
                            onTapped: root.playThrough(place.modelData)
                        }
                    }
                }
            }

            PlasmaComponents.Label {
                Layout.fillWidth: true
                text: i18n("Microphone")
                font.weight: Font.DemiBold
            }
            Pane {
                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    text: root.microphone ? root.microphone.name : i18n("No microphone connected")
                }
                RowLayout {
                    visible: root.microphone !== null
                    Layout.fillWidth: true
                    PlasmaComponents.Label {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        text: root.microphone && root.microphone.muted ? i18n("Muted") : i18n("Ready for calls and recording")
                    }
                    ActionButton {
                        text: root.microphoneBusy ? i18n("Changing…") : root.microphone && root.microphone.muted ? i18n("Unmute") : i18n("Mute")
                        Accessible.name: root.microphone && root.microphone.muted ? i18n("Unmute microphone") : i18n("Mute microphone")
                        enabled: !root.microphoneBusy && root.microphone !== null
                        onClicked: root.muteMicrophone()
                    }
                }
                Repeater {
                    model: (root.sound.inputs || []).length > 1 ? root.sound.inputs : []
                    ActionButton {
                        required property var modelData
                        Layout.fillWidth: true
                        text: modelData.name
                        checked: modelData.default === true
                        enabled: !root.microphoneBusy
                        Accessible.name: i18n("Use microphone %1", modelData.name)
                        onClicked: root.useMicrophone(modelData)
                    }
                }
                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    visible: root.microphoneMessage !== ""
                    text: root.microphoneMessage
                    wrapMode: Text.WordWrap
                }
            }

            // Each app playing, at its own volume.
            PlasmaComponents.Label {
                Layout.leftMargin: 2
                visible: root.sound.apps.length > 0 && !root.silent
                opacity: 0.66
                font: Kirigami.Theme.smallFont
                text: i18n("Apps playing sound")
            }
            Pane {
                visible: root.sound.apps.length > 0 && !root.silent
                Repeater {
                    model: root.sound.apps
                    RowLayout {
                        required property var modelData
                        Layout.fillWidth: true
                        spacing: 10
                        PlasmaComponents.Label {
                            Layout.preferredWidth: Kirigami.Units.gridUnit * 6
                            text: modelData.name
                            elide: Text.ElideRight
                        }
                        PlasmaComponents.Slider {
                            Layout.fillWidth: true
                            from: 0
                            to: 100
                            stepSize: 1
                            value: modelData.volume
                            Accessible.name: modelData.name
                            onPressedChanged: root.dragging = pressed
                            onMoved: root.queue("app-volume " + modelData.id, value)
                        }
                    }
                }
            }

            // The rest of it in Settings: a pebble of glass like Quick Settings' All Settings.
            Rectangle {
                id: more
                Layout.alignment: Qt.AlignRight
                implicitWidth: moreLabel.implicitWidth + 32
                implicitHeight: 36
                radius: 18
                color: root.smoke ? Qt.rgba(1, 1, 1, moreHover.hovered ? 0.14 : 0.08)
                    : Qt.rgba(1, 1, 1, moreHover.hovered ? 0.48 : 0.34)
                scale: moreTap.pressed ? 0.97 : 1
                Behavior on scale { NumberAnimation { duration: Math.round(160 * root.speed) } }
                activeFocusOnTab: true
                Keys.onSpacePressed: root.openSettings()
                Keys.onReturnPressed: root.openSettings()
                border.width: activeFocus ? 2 : 0
                border.color: "#357F72"
                Accessible.role: Accessible.Button
                Accessible.name: moreLabel.text
                Accessible.onPressAction: root.openSettings()
                GlassRim {
                    smoke: root.smoke
                }
                PlasmaComponents.Label {
                    id: moreLabel
                    anchors.centerIn: parent
                    text: i18n("Sound settings…")
                    font.weight: Font.DemiBold
                }
                HoverHandler {
                    id: moreHover
                    cursorShape: Qt.PointingHandCursor
                }
                TapHandler {
                    id: moreTap
                    onTapped: root.openSettings()
                }
            }
        }
        }
    }

    function openSettings() {
        expanded = false
        run("open sound")
    }
}
