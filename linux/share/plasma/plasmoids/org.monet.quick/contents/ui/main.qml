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
import QtQuick.Shapes
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
    // Mist or smoke, the way monet-light set the colors.
    readonly property bool smoke: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    property var info: ({})
    // Speakers, headphones, a screen: where the sound can play.
    property var outputs: []
    // While a slider is held, don't let a status refresh move it.
    property bool dragging: false

    Plasmoid.icon: "monet-quick-symbolic"
    toolTipMainText: i18n("Quick Settings")

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
            } else if (source === root.helper + " outputs") {
                try {
                    root.outputs = JSON.parse(data["stdout"])
                } catch (e) {
                }
            } else {
                refresh()
            }
        }
    }

    function refresh() {
        runner.connectSource(helper + " status")
        runner.connectSource(helper + " outputs")
    }

    function playThrough(output) {
        if (!Number.isInteger(output.id)) {
            return
        }
        outputs = outputs.map(o => Object.assign({}, o, { default: o.id === output.id }))
        run("output " + output.id)
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

    // h:mm, from minutes.
    function span(minutes) {
        return Math.floor(minutes / 60) + ":" + String(minutes % 60).padStart(2, "0")
    }

    // A page of Settings, in place of this popup.
    function openSettings(page) {
        expanded = false
        settings.open(page)
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
        // The screen this panel is on.
        area: Qt.rect(root.Screen.virtualX, root.Screen.virtualY, root.Screen.width, root.Screen.height)
        // The size people gave it, kept for next time.
        chosenWidth: Plasmoid.configuration.SettingsWidth
        chosenHeight: Plasmoid.configuration.SettingsHeight
        onResized: (width, height) => {
            Plasmoid.configuration.SettingsWidth = Math.round(width)
            Plasmoid.configuration.SettingsHeight = Math.round(height)
        }
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

    // The light caught in a pebble's edge.
    component GlassRim: Rectangle {
        required property bool smoke
        anchors.fill: parent
        radius: parent.radius
        color: "transparent"
        border.width: 1
        border.color: smoke ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(1, 1, 1, 0.7)
    }

    component Tile: Rectangle {
        id: tile
        property string title
        property string detail
        property string icon
        property bool active
        property bool available: true
        property real speed: 1
        // The page in Settings with more (networks to join, devices to pair): its chevron opens it.
        property string page
        signal toggled()
        signal opened()

        implicitHeight: Kirigami.Units.gridUnit * 3.4
        radius: 18
        // A pebble of clear glass on the glass, as in Apple's Control Center: lighter, not grey.
        readonly property bool smoke: Kirigami.Theme.backgroundColor.hslLightness < 0.5
        color: smoke ? Qt.rgba(1, 1, 1, hover.hovered ? 0.12 : 0.08) : Qt.rgba(1, 1, 1, hover.hovered ? 0.46 : 0.34)
        opacity: available ? 1 : 0.45
        scale: tap.pressed ? 0.97 : 1
        Behavior on scale { NumberAnimation { duration: Math.round(160 * tile.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
        Behavior on color { ColorAnimation { duration: Math.round(140 * tile.speed) } }
        // From the keyboard too: Tab to it, Space or Enter to switch it.
        activeFocusOnTab: true
        Keys.onSpacePressed: if (available) toggled()
        Keys.onReturnPressed: if (available) toggled()
        border.width: activeFocus ? 2 : 0
        border.color: "#357F72"

        GlassRim {
            smoke: tile.smoke
        }

        RowLayout {
            anchors.fill: parent
            anchors.margins: 12
            anchors.rightMargin: tile.page !== "" ? 4 : 12
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

            // More, in Settings: a chevron of its own, apart from the switch.
            Rectangle {
                id: more
                visible: tile.page !== ""
                Layout.preferredWidth: 28
                Layout.preferredHeight: 40
                radius: 10
                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b,
                               moreArea.containsMouse ? 0.1 : 0)
                Accessible.role: Accessible.Button
                Accessible.name: i18nc("%1 is a quick setting, like Wi-Fi", "%1 settings", tile.title)
                Accessible.onPressAction: tile.opened()

                Shape {
                    anchors.centerIn: parent
                    width: 10
                    height: 14
                    preferredRendererType: Shape.CurveRenderer
                    transform: Scale { origin.x: 5; xScale: more.LayoutMirroring.enabled ? -1 : 1 }
                    ShapePath {
                        strokeColor: Kirigami.Theme.textColor
                        strokeWidth: 1.8
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.RoundJoin
                        PathPolyline { path: [Qt.point(3, 2), Qt.point(8, 7), Qt.point(3, 12)] }
                    }
                }
                MouseArea {
                    id: moreArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: tile.opened()
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
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true
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
                    detail: !available ? i18n("Unavailable") : !active ? i18n("Off") : (root.info.network || i18n("Not connected"))
                    page: "wifi"
                    onToggled: root.flip("wifi", "wifi")
                    onOpened: root.openSettings(page)
                }
                Tile {
                    Layout.fillWidth: true
                    speed: root.speed
                    title: i18n("Bluetooth")
                    icon: "network-bluetooth"
                    active: root.info.bluetooth === true
                    available: root.info.bluetooth !== null && root.info.bluetooth !== undefined
                    detail: !available ? i18n("Unavailable") : active ? i18n("On") : i18n("Off")
                    page: "bluetooth"
                    onToggled: root.flip("bluetooth", "bluetooth")
                    onOpened: root.openSettings(page)
                }
                Tile {
                    Layout.fillWidth: true
                    speed: root.speed
                    title: i18n("Night Light")
                    icon: "weather-clear-night"
                    active: root.info.night === true
                    detail: active ? i18n("Warm after sunset") : i18n("Off")
                    page: "display"
                    onToggled: root.flip("night", "night")
                    onOpened: root.openSettings(page)
                }
                Tile {
                    Layout.fillWidth: true
                    speed: root.speed
                    title: i18n("Do Not Disturb")
                    icon: "notifications-disabled"
                    active: root.info.quiet === true
                    detail: active ? i18n("On") : i18n("Off")
                    page: "notifications"
                    onToggled: root.flip("quiet", "quiet")
                    onOpened: root.openSettings(page)
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: sliders.implicitHeight + 28
                radius: 18
                color: root.smoke ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.34)
                visible: root.info.volume !== null || root.info.brightness !== null

                GlassRim {
                    smoke: root.smoke
                }

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
                            // ?? not ||: at its dimmest the screen reads 0, which is no reason to show 50.
                            value: root.info.brightness ?? 50
                            Accessible.name: i18n("Brightness")
                            onPressedChanged: root.dragging = pressed
                            onMoved: root.queue("brightness", value)
                        }
                    }
                    // The keyboard's light, on laptops that have one: a few steps, off at the left.
                    RowLayout {
                        visible: root.info.keyboard ? true : false
                        spacing: 10
                        Kirigami.Icon { source: "input-keyboard-brightness"; isMask: true; color: Kirigami.Theme.textColor; Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
                        PlasmaComponents.Slider {
                            Layout.fillWidth: true
                            from: 0
                            to: root.info.keyboard ? root.info.keyboard.levels : 1
                            stepSize: 1
                            value: root.info.keyboard ? root.info.keyboard.level : 0
                            Accessible.name: i18n("Keyboard light")
                            onPressedChanged: root.dragging = pressed
                            onMoved: root.queue("keyboard", value)
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
                    // Where the sound plays, when it could play in more than one place: a tap moves it.
                    Flow {
                        Layout.fillWidth: true
                        Layout.leftMargin: 28
                        visible: root.outputs.length > 1 && typeof root.info.volume === "number"
                        spacing: 6
                        Repeater {
                            model: root.outputs
                            Rectangle {
                                id: place
                                required property var modelData
                                readonly property bool chosen: modelData.default === true
                                implicitWidth: Math.min(placeName.implicitWidth, 170) + 22
                                implicitHeight: 26
                                radius: 13
                                color: chosen ? "#357F72"
                                    : root.smoke ? Qt.rgba(1, 1, 1, placeHover.hovered ? 0.14 : 0.08) : Qt.rgba(1, 1, 1, placeHover.hovered ? 0.5 : 0.34)
                                activeFocusOnTab: true
                                Keys.onSpacePressed: root.playThrough(modelData)
                                Keys.onReturnPressed: root.playThrough(modelData)
                                border.width: activeFocus ? 2 : chosen ? 0 : 1
                                border.color: activeFocus ? "#357F72" : root.smoke ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(1, 1, 1, 0.7)
                                Accessible.role: Accessible.RadioButton
                                Accessible.name: i18nc("%1 is speakers, headphones or a screen", "Play through %1", modelData.name)
                                Accessible.checked: chosen
                                Text {
                                    id: placeName
                                    anchors.centerIn: parent
                                    width: Math.min(implicitWidth, 170)
                                    horizontalAlignment: Text.AlignHCenter
                                    text: place.modelData.name
                                    elide: Text.ElideRight
                                    color: place.chosen ? "#FFFFFF" : Kirigami.Theme.textColor
                                    font.family: "Inter"
                                    font.pixelSize: 12
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
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    horizontalAlignment: Text.AlignLeft
                    text: i18n("Light")
                    color: Kirigami.Theme.textColor
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: 18
                    Layout.leftMargin: 2
                }

                // Hours follows the paintings; Mist and Smoke stay put.
                Rectangle {
                    id: lights
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    radius: 14
                    color: root.smoke ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.34)

                    GlassRim {
                        smoke: root.smoke
                    }

                    // The chosen light's pebble glides to it.
                    Rectangle {
                        readonly property int picked: Math.max(0, ["hours", "mist", "smoke"].indexOf(root.info.light || "hours"))
                        readonly property real slot: (lights.width - 16) / 3
                        // From the right in right-to-left languages, as the choices are.
                        x: LayoutMirroring.enabled ? lights.width - 4 - slot - picked * (slot + 4) : 4 + picked * (slot + 4)
                        y: 4
                        width: slot
                        height: lights.height - 8
                        radius: 10
                        color: Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.9)
                        Behavior on x {
                            NumberAnimation { duration: Math.round(320 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] }
                        }
                    }

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 4
                        spacing: 4
                        Repeater {
                            model: [["hours", i18n("Hours")], ["mist", i18n("Mist")], ["smoke", i18n("Smoke")]]
                            Item {
                                id: choice
                                readonly property bool picked: (root.info.light || "hours") === modelData[0]
                                Layout.fillWidth: true
                                Layout.fillHeight: true
                                activeFocusOnTab: true
                                Keys.onSpacePressed: choice.pick()
                                Keys.onReturnPressed: choice.pick()

                                function pick() {
                                    const next = Object.assign({}, root.info)
                                    next.light = modelData[0]
                                    root.info = next
                                    root.run("light " + modelData[0])
                                }

                                Rectangle {
                                    anchors.fill: parent
                                    radius: 10
                                    color: "transparent"
                                    border.width: choice.activeFocus ? 2 : 0
                                    border.color: "#357F72"
                                }
                                PlasmaComponents.Label {
                                    anchors.centerIn: parent
                                    text: modelData[1]
                                    font.weight: Font.DemiBold
                                    opacity: choice.picked ? 1 : choiceHover.hovered ? 0.85 : 0.66
                                    Behavior on opacity { NumberAnimation { duration: Math.round(160 * root.speed) } }
                                }
                                HoverHandler { id: choiceHover }
                                TapHandler {
                                    onTapped: choice.pick()
                                }
                                Accessible.role: Accessible.RadioButton
                                Accessible.name: modelData[1]
                                Accessible.checked: picked
                            }
                        }
                    }
                }
                // What the chosen light does, in Settings' words.
                PlasmaComponents.Label {
                    Layout.leftMargin: 2
                    opacity: 0.66
                    font: Kirigami.Theme.smallFont
                    text: root.info.light === "mist" ? i18n("Always light")
                        : root.info.light === "smoke" ? i18n("Always dark") : i18n("Mist by day, smoke after dark")
                }
            }

            RowLayout {
                Layout.fillWidth: true
                PlasmaComponents.Label {
                    Layout.fillWidth: true
                    visible: typeof root.info.battery === "number"
                    opacity: 0.7
                    text: root.info.charging ? i18n("Battery %1%, charging", root.info.battery)
                        : root.info.plugged ? i18n("Battery %1%, plugged in", root.info.battery)
                        : root.info.minutes ? i18nc("%2 is how long it lasts, like 2:15", "Battery %1%, %2 left", root.info.battery, root.span(root.info.minutes))
                        : i18n("Battery %1%", root.info.battery)
                }
                Item { Layout.fillWidth: typeof root.info.battery !== "number" }
                // All of Settings: a pebble of glass like the tiles, with Settings' own sign.
                Rectangle {
                    id: allSettings
                    implicitWidth: allRow.implicitWidth + 28
                    implicitHeight: 36
                    radius: 18
                    color: root.smoke ? Qt.rgba(1, 1, 1, allHover.hovered ? 0.14 : 0.08)
                        : Qt.rgba(1, 1, 1, allHover.hovered ? 0.48 : 0.34)
                    scale: allTap.pressed ? 0.97 : 1
                    Behavior on scale { NumberAnimation { duration: Math.round(160 * root.speed) } }
                    activeFocusOnTab: true
                    Keys.onSpacePressed: root.openSettings("")
                    Keys.onReturnPressed: root.openSettings("")
                    border.width: activeFocus ? 2 : 0
                    border.color: "#357F72"
                    Accessible.role: Accessible.Button
                    Accessible.name: i18n("All Settings")
                    Accessible.onPressAction: root.openSettings("")
                    GlassRim {
                        smoke: root.smoke
                    }
                    RowLayout {
                        id: allRow
                        anchors.centerIn: parent
                        spacing: 8
                        // Settings' mark: two sliders, as in the app menu.
                        Shape {
                            Layout.preferredWidth: 16
                            Layout.preferredHeight: 16
                            preferredRendererType: Shape.CurveRenderer
                            ShapePath {
                                scale: Qt.size(16 / 24, 16 / 24)
                                strokeColor: Kirigami.Theme.textColor
                                strokeWidth: 2.4
                                fillColor: "transparent"
                                capStyle: ShapePath.RoundCap
                                PathSvg { path: "M4 7h10M18 7h2M4 17h4M12 17h8M16 4v6M10 14v6" }
                            }
                        }
                        PlasmaComponents.Label {
                            text: i18n("All Settings")
                            font.weight: Font.DemiBold
                        }
                    }
                    HoverHandler {
                        id: allHover
                        cursorShape: Qt.PointingHandCursor
                    }
                    TapHandler {
                        id: allTap
                        onTapped: root.openSettings("")
                    }
                }
            }
        }
    }
}
