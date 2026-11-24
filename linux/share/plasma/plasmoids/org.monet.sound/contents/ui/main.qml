/*
 * Sound, in the clock island beside Quick Settings: how loud at a glance and under the wheel
 * (a middle click mutes), and a glass popover with the volume, where the sound plays and the
 * apps playing. In place of KDE's own item in the tray, whose popover is KDE's (the volume
 * keys and their on-screen level are KDE's audio shortcuts service, which needs no item).
 * Native audio events supply the level; wpctl and monet-quick perform changes.
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
    SessionActivity {
        id: activity; viewVisible: root.visible
        onActiveChanged: if (active) Qt.callLater(() => {
            root.refresh();
            if (root.expanded || !audioLevel.nativeReady) root.look();
        })
    }

    readonly property string helper: "@LIBEXECDIR@/monet-quick"
    readonly property real speed: Kirigami.Units.longDuration / 200
    // Mist or smoke, the way monet-light set the colors.
    readonly property bool smoke: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    // Updated immediately by the audio service; the legacy reader is a fallback.
    property var volume: null
    property bool muted: false
    // Where it can play and the apps playing (monet-quick sound): while open, and now and then.
    property var sound: ({ outputs: [], apps: [], inputs: [], microphone: null })
    readonly property var microphone: sound.microphone || null
    // A change underway is its request; one at a time, and the panel's own reading waits for it.
    // What was asked for stays, so Try again asks for the same device even if PipeWire renumbered it.
    property string microphoneRequest: ""
    readonly property bool microphoneBusy: microphoneRequest !== ""
    property var microphoneAsked: null
    property string microphoneMessage: ""
    property bool microphoneFailed: false
    property string outputRequest: ""
    readonly property bool outputBusy: outputRequest !== ""
    property var outputWanted: null
    property string outputMessage: ""
    property bool soundKnown: false
    // While a slider is held, don't let a refresh move it.
    property bool dragging: false
    // Nowhere to play: PipeWire's stand-in only (monet-quick leaves it out).
    readonly property bool silent: audioLevel.nativeReady ? !audioLevel.hasOutput : soundKnown && sound.outputs.length === 0
    readonly property string playing: audioLevel.nativeReady ? audioLevel.description : (sound.outputs.find(o => o.default) || {}).name || ""

    AudioLevel {
        id: audioLevel
        active: activity.active
        onVolumeChanged: if (!root.dragging) root.volume = volume
        onMutedChanged: if (!root.dragging) root.muted = muted
    }
    property int requestSerial: 0
    property string soundRequest: ""
    function request(command) {
        const source = command + " # monet-sound-" + (++requestSerial);
        runner.connectSource(source);
        return source;
    }
    // A change's own source, kept before it's connected: a cached source may reply during connectSource.
    function requestSource(args) {
        return helper + " " + args + " # monet-sound-" + (++requestSerial)
    }

    Plasmoid.icon: silent || muted || !volume ? "audio-volume-muted"
        : volume < 34 ? "audio-volume-low" : volume < 67 ? "audio-volume-medium" : "audio-volume-high"
    Plasmoid.status: PlasmaCore.Types.ActiveStatus
    TaskManagerAction { id: taskManager; menuApplet: Plasmoid }
    Plasmoid.contextualActions: taskManager.showInAppletMenu ? [taskManager] : []
    toolTipMainText: i18n("Sound")
    toolTipSubText: silent ? i18n("No speakers or headphones") : muted ? i18n("Muted")
        : typeof volume === "number" ? i18n("Volume %1%", volume) : ""

    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            const command = source.replace(/ # monet-sound-\d+$/, "")
            const out = data["stdout"] || ""
            if (command === root.helper + " sound" || command === root.helper + " sound devices") {
                if (source !== root.soundRequest) return
                root.soundRequest = ""
                // Read before a change finished; the change answers with the sound after it.
                if (root.outputBusy || root.microphoneBusy) return
                try {
                    const next = JSON.parse(out)
                    if (!root.dragging) {
                        const before = root.microphone || {}
                        const after = next.microphone || {}
                        if ((before.key || before.id) !== (after.key || after.id) || before.muted !== after.muted) {
                            root.microphoneMessage = ""
                            root.microphoneFailed = false
                        }
                        root.sound = next
                    }
                    root.soundKnown = true
                } catch (e) {
                }
            } else if (command.startsWith(root.helper + " output ")) {
                if (source !== root.outputRequest) return
                root.outputRequest = ""
                try {
                    const result = JSON.parse(out)
                    if (Array.isArray(result.outputs))
                        root.sound = Object.assign({}, root.sound, { outputs: result.outputs.filter(o => !o.none) })
                    const name = root.outputWanted ? root.outputWanted.name : ""
                    root.outputMessage = result.ok === true && data["exit code"] === 0 ? ""
                        : result.problem === "gone" ? i18n("%1 isn't connected now. Connect it and try again.", name)
                        : i18nc("%1 is speakers, headphones or a screen", "Sound didn't switch to %1. Try again.", name)
                } catch (e) {
                    root.outputMessage = i18n("The sound output could not be changed. Try again.")
                }
                root.refresh()
            } else if (command.startsWith(root.helper + " mic-mute ") || command.startsWith(root.helper + " input ")) {
                if (source !== root.microphoneRequest) return
                root.microphoneRequest = ""
                const asked = root.microphoneAsked || {}
                try {
                    const result = JSON.parse(out)
                    if (result.sound) root.sound = result.sound
                    root.microphoneFailed = !(result.ok === true && data["exit code"] === 0)
                    root.microphoneMessage = !root.microphoneFailed
                        ? (root.microphone && root.microphone.muted ? i18n("Microphone muted") : i18n("Microphone ready"))
                        : asked.mute || !asked.device ? i18n("The microphone could not be changed. Check its connection and try again.")
                        : result.problem === "gone" ? i18n("%1 isn't connected now. Connect it and try again.", asked.device.name)
                        : i18n("The microphone didn't switch to %1. Try again.", asked.device.name)
                } catch (e) {
                    root.microphoneFailed = true
                    root.microphoneMessage = i18n("The microphone could not be changed. Try again.")
                }
                root.look()
            } else {
                root.refresh()
                if (root.expanded) root.look()
            }
        }
    }

    function refresh() {
        audioLevel.refresh()
        if (!dragging) { volume = audioLevel.volume; muted = audioLevel.muted; }
    }
    function look() {
        if (!activity.active || soundRequest || outputBusy || microphoneBusy) return
        // Keep the identity before connecting: a cached source may reply during
        // connectSource, and activity can change while the widget is created.
        soundRequest = helper + (root.fullRepresentationItem?.nativeMixer ? " sound devices" : " sound") + " # monet-sound-" + (++requestSerial)
        runner.connectSource(soundRequest)
    }
    // Arguments are fixed words or numbers, never anyone's text.
    function run(args) {
        request(helper + " " + args)
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
    // The device's own name, as the helper gave it in hex: it still finds the device after PipeWire
    // has numbered it again (plugged in, unplugged, a new profile). Older answers have none.
    function deviceKey(device) {
        return /^(?:[0-9a-f]{2})+$/.test(device.key || "") ? " " + device.key : ""
    }
    function sameDevice(a, b) {
        return !!a && !!b && (a.key && b.key ? a.key === b.key : a.id === b.id)
    }
    function playThrough(output) {
        if (!output || !Number.isInteger(output.id) || outputBusy || microphoneBusy) {
            return
        }
        outputWanted = output
        outputMessage = ""
        outputRequest = requestSource("output " + output.id + deviceKey(output))
        runner.connectSource(outputRequest)
    }
    function muteMicrophone() {
        if (microphone) askMicrophone({ device: microphone, mute: microphone.muted ? "off" : "on" })
    }
    function useMicrophone(input) {
        askMicrophone({ device: input })
    }
    // { device, mute: "on"|"off" } mutes or unmutes the microphone in use; { device } uses it.
    function askMicrophone(asked) {
        const device = asked && asked.device
        if (!device || !Number.isInteger(device.id) || microphoneBusy || outputBusy) return
        microphoneAsked = asked
        microphoneMessage = ""
        microphoneFailed = false
        microphoneRequest = requestSource((asked.mute ? "mic-mute " + device.id + " " + asked.mute : "input " + device.id)
                                          + deviceKey(device))
        runner.connectSource(microphoneRequest)
    }

    // The native reader keeps the closed icon current. Probe the app/output list
    // while it is open, or occasionally on older hosts using the fallback.
    Timer {
        interval: root.expanded ? 3000 : 60000
        repeat: true
        running: activity.active && (root.expanded || !audioLevel.nativeReady)
        triggeredOnStart: true
        onTriggered: if (!root.dragging) root.look()
    }
    onExpandedChanged: if (root.expanded) Qt.callLater(look)
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
        readonly property bool nativeMixer: mixerLoader.status === Loader.Ready
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true
        Layout.minimumWidth: Math.min(Kirigami.Units.gridUnit * 19, Screen.width - 48)
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
            RowLayout {
                Layout.fillWidth: true
                visible: root.outputBusy || root.outputMessage !== ""
                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    text: root.outputBusy ? i18n("Changing sound output…") : root.outputMessage
                    Accessible.name: text
                }
                // Another go at the same output, found by its name if PipeWire has renumbered it.
                ActionButton {
                    visible: !root.outputBusy && root.outputWanted !== null
                    text: i18n("Try again")
                    enabled: !root.microphoneBusy
                    onClicked: root.playThrough(root.outputWanted)
                }
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
                        // Asked for, and not yet seen playing there.
                        readonly property bool moving: root.outputBusy && root.sameDevice(modelData, root.outputWanted)
                        Layout.fillWidth: true
                        implicitHeight: 34
                        radius: 12
                        color: chosen ? Qt.rgba(0.208, 0.498, 0.447, root.smoke ? 0.4 : 0.22)
                            : moving ? Qt.rgba(0.208, 0.498, 0.447, root.smoke ? 0.2 : 0.11)
                            : placeHover.hovered ? (root.smoke ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.4)) : "transparent"
                        activeFocusOnTab: true
                        Keys.onSpacePressed: root.playThrough(modelData)
                        Keys.onReturnPressed: root.playThrough(modelData)
                        border.width: activeFocus ? 2 : 0
                        border.color: "#357F72"
                        Accessible.role: Accessible.RadioButton
                        Accessible.name: i18nc("%1 is speakers, headphones or a screen", "Play through %1", modelData.name)
                        Accessible.description: moving ? i18n("Changing…") : ""
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
                        enabled: !root.microphoneBusy && !root.outputBusy && root.microphone !== null
                        onClicked: root.muteMicrophone()
                    }
                }
                Repeater {
                    model: (root.sound.inputs || []).length > 1 ? root.sound.inputs : []
                    ActionButton {
                        required property var modelData
                        // Asked for, and not yet seen in use.
                        readonly property bool moving: root.microphoneBusy && !!root.microphoneAsked
                            && !root.microphoneAsked.mute && root.sameDevice(modelData, root.microphoneAsked.device)
                        Layout.fillWidth: true
                        text: moving ? i18n("Changing…") : modelData.name
                        checked: modelData.default === true
                        enabled: !root.microphoneBusy && !root.outputBusy
                        Accessible.name: i18n("Use microphone %1", modelData.name)
                        onClicked: root.useMicrophone(modelData)
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    visible: root.microphoneMessage !== ""
                    PlasmaComponents.Label {
                        Layout.fillWidth: true
                        text: root.microphoneMessage
                        wrapMode: Text.WordWrap
                        Accessible.name: text
                    }
                    // The same change again, to the same microphone.
                    ActionButton {
                        visible: root.microphoneFailed && root.microphoneAsked !== null
                        text: i18n("Try again")
                        enabled: !root.microphoneBusy && !root.outputBusy
                        onClicked: root.askMicrophone(root.microphoneAsked)
                    }
                }
            }

            Loader {
                id: mixerLoader
                active: root.expanded
                visible: !!item && item.appCount > 0 && !root.silent
                Layout.fillWidth: true
                Layout.preferredHeight: item && visible ? Math.min(275, item.contentHeight) : 0
                source: "VolumeMixer.qml"
                onLoaded: {
                    item.showOutput = false
                    item.outputNames = Qt.binding(() => root.sound.outputs)
                }
            }
            // The wpctl mixer remains available on hosts without the native audio controls.
            PlasmaComponents.Label {
                Layout.leftMargin: 2
                visible: mixerLoader.status !== Loader.Ready && root.sound.apps.length > 0 && !root.silent
                opacity: 0.66
                font: Kirigami.Theme.smallFont
                text: i18n("Apps playing sound")
            }
            Pane {
                visible: mixerLoader.status !== Loader.Ready && root.sound.apps.length > 0 && !root.silent
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
                            onMoved: root.queue("app-volume " + (modelData.ids || [modelData.id]).join(","), value)
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
