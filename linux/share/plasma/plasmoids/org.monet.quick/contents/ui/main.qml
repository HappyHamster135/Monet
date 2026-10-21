/*
 * Quick Settings: Wi-Fi, Bluetooth, Night Light, Do not disturb, sound,
 * brightness and Monet's light, in the clock island. The `monet-quick`
 * helper does the work; this draws it.
 *
 * It also owns Monet Settings (MonetSettings.qml), which opens from here or
 * from Settings in the app menu (`monet-quick open` rings the doorbell below).
 */
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property string helper: "@LIBEXECDIR@/monet-quick"
    readonly property real speed: Kirigami.Units.longDuration / 200
    property var info: ({})
    // While a slider is held, don't let a status refresh move it.
    property bool dragging: false

    Plasmoid.icon: "monet-quick-symbolic"
    toolTipMainText: i18n("Quick Settings")
    toolTipSubText: info.network ? i18n("Connected to %1", info.network) : ""

    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            if (source === root.helper + " status") {
                try {
                    root.info = JSON.parse(data["stdout"])
                } catch (e) {
                }
            } else {
                refresh()
            }
        }
    }

    function refresh() {
        runner.connectSource(helper + " status")
    }

    // Arguments are fixed words or numbers, never user text.
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

    function flip(key, command) {
        const on = !info[key]
        const next = Object.assign({}, info)
        next[key] = on
        info = next
        run(command + (on ? " on" : " off"))
    }

    MonetSettings {
        id: settings
        helper: root.helper
        speed: root.speed
        area: Qt.rect(Screen.virtualX, Screen.virtualY, Screen.width, Screen.height)
    }

    // Waits for `monet-quick open [PAGE]`, opens Settings, and waits again.
    property double armed: 0
    P5Support.DataSource {
        id: doorbell
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            const asked = (data["stdout"] || "").trim().split(" ")
            if (asked[0] === "open") {
                settings.open(asked[1] || "")
            }
            // If listening fails straight away, don't spin: try again later.
            rearm.interval = asked[0] === "" && Date.now() - root.armed < 5000 ? 30000 : 100
            rearm.start()
        }
    }
    Timer {
        id: rearm
        onTriggered: {
            root.armed = Date.now()
            doorbell.connectSource(root.helper + " listen")
        }
    }
    Component.onCompleted: rearm.start()

    Timer {
        interval: 3000
        repeat: true
        running: root.expanded
        triggeredOnStart: true
        onTriggered: if (!root.dragging) root.refresh()
    }

    component Tile: Rectangle {
        id: tile
        property string title
        property string detail
        property string icon
        property bool active
        property bool available: true
        property real speed: 1
        signal toggled()

        implicitHeight: Kirigami.Units.gridUnit * 3.4
        radius: 18
        color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, hover.hovered ? 0.11 : 0.07)
        opacity: available ? 1 : 0.45
        scale: tap.pressed ? 0.97 : 1
        Behavior on scale { NumberAnimation { duration: Math.round(160 * tile.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
        Behavior on color { ColorAnimation { duration: Math.round(140 * tile.speed) } }

        RowLayout {
            anchors.fill: parent
            anchors.margins: 12
            spacing: 10

            Rectangle {
                Layout.preferredWidth: 34
                Layout.preferredHeight: 34
                radius: 17
                color: tile.active ? "#357F72" : Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.1)
                Behavior on color { ColorAnimation { duration: Math.round(180 * tile.speed) } }
                Kirigami.Icon {
                    anchors.centerIn: parent
                    width: 18
                    height: 18
                    source: tile.icon
                    isMask: true
                    color: tile.active ? "#FFFFFF" : Kirigami.Theme.textColor
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    text: tile.title
                    elide: Text.ElideRight
                    font.weight: Font.DemiBold
                }
                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    text: tile.detail
                    elide: Text.ElideRight
                    opacity: 0.66
                    font: Kirigami.Theme.smallFont
                }
            }
        }

        HoverHandler { id: hover }
        TapHandler {
            id: tap
            enabled: tile.available
            onTapped: tile.toggled()
        }
        Accessible.role: Accessible.CheckBox
        Accessible.name: tile.title
        Accessible.checked: tile.active
        Accessible.onToggleAction: tile.toggled()
    }

    fullRepresentation: PlasmaExtras.Representation {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 23
        Layout.preferredHeight: column.implicitHeight + Kirigami.Units.largeSpacing * 2
        collapseMarginsHint: true

        ColumnLayout {
            id: column
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing
            spacing: Kirigami.Units.largeSpacing

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 8
                rowSpacing: 8

                Tile {
                    Layout.fillWidth: true
                    speed: root.speed
                    title: i18n("Wi-Fi")
                    icon: "network-wireless"
                    active: root.info.wifi === true
                    available: root.info.wifi !== null && root.info.wifi !== undefined
                    detail: !available ? i18n("Unavailable") : !active ? i18n("Off") : (root.info.network || i18n("On"))
                    onToggled: root.flip("wifi", "wifi")
                }
                Tile {
                    Layout.fillWidth: true
                    speed: root.speed
                    title: i18n("Bluetooth")
                    icon: "network-bluetooth"
                    active: root.info.bluetooth === true
                    available: root.info.bluetooth !== null && root.info.bluetooth !== undefined
                    detail: !available ? i18n("Unavailable") : active ? i18n("On") : i18n("Off")
                    onToggled: root.flip("bluetooth", "bluetooth")
                }
                Tile {
                    Layout.fillWidth: true
                    speed: root.speed
                    title: i18n("Night Light")
                    icon: "weather-clear-night"
                    active: root.info.night === true
                    detail: active ? i18n("Warm after sunset") : i18n("Off")
                    onToggled: root.flip("night", "night")
                }
                Tile {
                    Layout.fillWidth: true
                    speed: root.speed
                    title: i18n("Do Not Disturb")
                    icon: "notifications-disabled"
                    active: root.info.quiet === true
                    detail: active ? i18n("On") : i18n("Off")
                    onToggled: root.flip("quiet", "quiet")
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: sliders.implicitHeight + 28
                radius: 18
                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.07)
                visible: root.info.volume !== null || root.info.brightness !== null

                ColumnLayout {
                    id: sliders
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: 14
                    spacing: 10

                    RowLayout {
                        visible: typeof root.info.brightness === "number"
                        spacing: 10
                        Kirigami.Icon { source: "brightness-high"; isMask: true; color: Kirigami.Theme.textColor; Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
                        PlasmaComponents.Slider {
                            Layout.fillWidth: true
                            from: 1
                            to: 100
                            stepSize: 1
                            value: root.info.brightness || 50
                            Accessible.name: i18n("Brightness")
                            onPressedChanged: root.dragging = pressed
                            onMoved: root.queue("brightness", value)
                        }
                    }
                    RowLayout {
                        visible: typeof root.info.volume === "number"
                        spacing: 10
                        Kirigami.Icon { source: "audio-volume-high"; isMask: true; color: Kirigami.Theme.textColor; Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
                        PlasmaComponents.Slider {
                            Layout.fillWidth: true
                            from: 0
                            to: 100
                            stepSize: 1
                            value: root.info.volume || 0
                            Accessible.name: i18n("Volume")
                            onPressedChanged: root.dragging = pressed
                            onMoved: root.queue("volume", value)
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    text: i18n("Light")
                    color: Kirigami.Theme.textColor
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: 18
                    Layout.leftMargin: 2
                }

                // Hours follows the paintings; Mist and Smoke stay put.
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    radius: 14
                    color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.07)

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 4
                        spacing: 4
                        Repeater {
                            model: [["hours", i18n("Hours")], ["mist", i18n("Mist")], ["smoke", i18n("Smoke")]]
                            Rectangle {
                                id: choice
                                readonly property bool picked: (root.info.light || "hours") === modelData[0]
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                radius: 10
                                color: picked ? Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.9) : "transparent"
                                Behavior on color { ColorAnimation { duration: Math.round(160 * root.speed) } }
                                PlasmaComponents.Label {
                                    anchors.centerIn: parent
                                    text: modelData[1]
                                    font.weight: Font.DemiBold
                                    opacity: choice.picked ? 1 : 0.66
                                }
                                TapHandler {
                                    onTapped: {
                                        const next = Object.assign({}, root.info)
                                        next.light = modelData[0]
                                        root.info = next
                                        root.run("light " + modelData[0])
                                    }
                                }
                                Accessible.role: Accessible.RadioButton
                                Accessible.name: modelData[1]
                                Accessible.checked: picked
                            }
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    visible: typeof root.info.battery === "number"
                    opacity: 0.7
                    text: root.info.charging ? i18n("Battery %1%, charging", root.info.battery) : i18n("Battery %1%", root.info.battery)
                }
                Item { Layout.fillWidth: typeof root.info.battery !== "number" }
                PlasmaComponents.Button {
                    icon.name: "configure"
                    text: i18n("All Settings")
                    onClicked: {
                        root.expanded = false
                        settings.open("")
                    }
                }
            }
        }
    }
}
