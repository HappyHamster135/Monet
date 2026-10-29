/*
 * Timer: a few minutes on the sun's path, on Monet's glass. The sun goes
 * round the ring as the time runs out; when it's home, a notification and
 * the sound theme's alarm say so. A length to pick (or the wheel over the
 * time, a minute a click), start and pause on the sun. It keeps going if
 * Plasma starts again: the end is kept, not the count.
 */
import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import QtQuick.Templates as T
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property string helper: "@LIBEXECDIR@/monet-quick"
    readonly property int minutes: Plasmoid.configuration.minutes
    readonly property real length: minutes * 60000
    readonly property bool running: Plasmoid.configuration.ends > 0
    readonly property bool paused: !running && Plasmoid.configuration.left > 0
    // Plein-air focus: while it runs, notifications are quiet and the painting goes from
    // dawn to night (monet-quick focus), so the light shows the time passing.
    readonly property bool focusSession: Plasmoid.configuration.focus === true
    property string focusPending: ""
    property string focusActive: ""
    property real now: Date.now()
    // What's left, in milliseconds: counting down, held, or all of it.
    readonly property real remaining: running ? Math.max(0, Plasmoid.configuration.ends - now)
                               : paused ? Plasmoid.configuration.left : length
    property bool done: false

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "monet-timer"
    preferredRepresentation: fullRepresentation
    toolTipMainText: i18n("Timer")
    toolTipSubText: running ? i18nc("%1 is a time like 4:59", "%1 left", clock(remaining)) : ""

    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: source => {
            disconnectSource(source)
            if (source === root.focusActive) {
                root.focusActive = ""
                root.sendFocus()
            }
        }
    }

    // Start/pause/resume can happen faster than a helper finishes. Send the latest
    // intent in order, so an older pause cannot turn off a newly resumed timer.
    function requestFocus(command) {
        focusPending = helper + " focus " + command + " " + Plasmoid.id
        sendFocus()
    }
    function sendFocus() {
        if (focusActive !== "" || focusPending === "") return
        focusActive = focusPending
        focusPending = ""
        runner.connectSource(focusActive)
    }

    Timer {
        interval: 250
        repeat: true
        running: root.running
        onTriggered: {
            root.now = Date.now();
            if (root.remaining <= 0) {
                root.finish(true);
            }
        }
    }

    // A timer that ended while Plasma was away has ended: no alarm late.
    Component.onCompleted: {
        if (running && Plasmoid.configuration.ends <= Date.now()) {
            finish(false);
        }
    }

    // m:ss, or h:mm:ss, rounding up so it shows 0:00 only at the end.
    function clock(ms) {
        const s = Math.ceil(ms / 1000);
        const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, rest = String(s % 60).padStart(2, "0");
        return h > 0 ? h + ":" + String(m).padStart(2, "0") + ":" + rest : m + ":" + rest;
    }

    function hex(text) {
        const bytes = unescape(encodeURIComponent(text));
        let out = "";
        for (let i = 0; i < bytes.length; i++) {
            out += bytes.charCodeAt(i).toString(16).padStart(2, "0");
        }
        return out;
    }

    function start() {
        now = Date.now();
        Plasmoid.configuration.ends = now + (paused ? Plasmoid.configuration.left : length);
        Plasmoid.configuration.left = 0;
        done = false;
        if (focusSession) {
            requestFocus(String(Math.round(Plasmoid.configuration.ends / 1000)));
        }
    }

    // The painting and the notifications back as they were.
    function unfocus() {
        if (focusSession) {
            requestFocus("off");
        }
    }

    function pause() {
        Plasmoid.configuration.left = Math.max(1, Plasmoid.configuration.ends - Date.now());
        Plasmoid.configuration.ends = 0;
        unfocus();
    }

    function reset() {
        Plasmoid.configuration.ends = 0;
        Plasmoid.configuration.left = 0;
        done = false;
        unfocus();
    }

    function finish(ring) {
        Plasmoid.configuration.ends = 0;
        Plasmoid.configuration.left = 0;
        done = true;
        unfocus();
        if (ring) {
            runner.connectSource(helper + " ring " + hex(i18n("Time's up"))
                                 + " " + hex(i18np("%1 minute has passed.", "%1 minutes have passed.", minutes)));
        }
    }

    function setMinutes(value) {
        Plasmoid.configuration.minutes = Math.max(1, Math.min(180, value));
        done = false;
    }

    // A length to pick, below the ring.
    component Length: T.AbstractButton {
        id: pill
        property int value
        property bool chosen
        property color ink
        property color dim
        text: i18nc("a timer's length, short", "%1 min", value)
        implicitWidth: Math.max(implicitHeight, label.implicitWidth + 14)
        implicitHeight: 24
        background: Rectangle {
            radius: height / 2
            color: pill.ink
            opacity: pill.chosen ? 0.12 : pill.hovered || pill.visualFocus ? 0.07 : 0
        }
        contentItem: Text {
            id: label
            text: pill.text
            color: pill.chosen ? pill.ink : pill.dim
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.family: "Inter"
            font.pixelSize: 11
            font.weight: pill.chosen ? Font.DemiBold : Font.Normal
        }
    }

    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 10
        Layout.minimumHeight: Kirigami.Units.gridUnit * 10
        Layout.preferredWidth: Kirigami.Units.gridUnit * 12
        Layout.preferredHeight: Kirigami.Units.gridUnit * 12

        Glass {
            id: card
            anchors.fill: parent

            readonly property color sun: "#F2552C"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Math.round(Kirigami.Units.gridUnit * 0.8)
                spacing: Kirigami.Units.smallSpacing

                // The ring: the sun goes round it as the time runs out.
                Item {
                    id: dial
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    readonly property real size: Math.min(width, height)
                    readonly property real r: size / 2 - 10
                    readonly property real share: root.done ? 0 : root.remaining / Math.max(1, root.length)

                    Shape {
                        anchors.fill: parent
                        preferredRendererType: Shape.CurveRenderer
                        ShapePath {
                            strokeColor: Qt.rgba(card.ink.r, card.ink.g, card.ink.b, 0.1)
                            strokeWidth: 7
                            fillColor: "transparent"
                            PathAngleArc {
                                centerX: dial.width / 2; centerY: dial.height / 2; radiusX: dial.r; radiusY: dial.r
                                startAngle: -90; sweepAngle: 360
                            }
                        }
                        ShapePath {
                            strokeColor: card.sun
                            strokeWidth: 7
                            fillColor: "transparent"
                            capStyle: ShapePath.RoundCap
                            PathAngleArc {
                                centerX: dial.width / 2; centerY: dial.height / 2; radiusX: dial.r; radiusY: dial.r
                                startAngle: -90; sweepAngle: Math.max(0.01, 360 * dial.share)
                            }
                        }
                    }
                    // The sun, where the time has got to.
                    Rectangle {
                        readonly property real angle: (-90 + 360 * dial.share) * Math.PI / 180
                        x: dial.width / 2 + dial.r * Math.cos(angle) - width / 2
                        y: dial.height / 2 + dial.r * Math.sin(angle) - height / 2
                        width: 15
                        height: 15
                        radius: 7.5
                        visible: !root.done
                        gradient: Gradient {
                            GradientStop { position: 0; color: "#FF8A4C" }
                            GradientStop { position: 1; color: "#E0441C" }
                        }
                    }

                    ColumnLayout {
                        anchors.centerIn: parent
                        width: dial.r * 1.5
                        spacing: 0

                        Text {
                            Layout.fillWidth: true
                            horizontalAlignment: Text.AlignHCenter
                            text: root.done ? i18n("Time's up") : root.clock(root.remaining)
                            color: card.ink
                            elide: Text.ElideRight
                            font.family: "Fraunces 72pt SuperSoft"
                            font.italic: root.done
                            font.pixelSize: root.done ? 19 : Math.round(Math.min(34, dial.r * 0.48))
                            font.features: { "tnum": 1 }

                            // A minute more or less, a click of the wheel, while it isn't running.
                            WheelHandler {
                                enabled: !root.running && !root.paused
                                acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
                                onWheel: event => root.setMinutes(root.minutes + (event.angleDelta.y > 0 ? 1 : -1))
                            }
                            PlasmaCore.ToolTipArea {
                                anchors.fill: parent
                                active: !root.running && !root.paused && !root.done
                                mainText: i18n("Scroll to change the minutes")
                            }
                        }

                        // Start, pause, again: on the sun.
                        T.AbstractButton {
                            id: go
                            Layout.alignment: Qt.AlignHCenter
                            Layout.topMargin: 6
                            implicitWidth: 36
                            implicitHeight: 36
                            Accessible.name: root.running ? i18n("Pause") : i18n("Start")
                            onClicked: root.running ? root.pause() : root.start()
                            background: Rectangle {
                                radius: width / 2
                                color: card.sun
                                scale: go.down ? 0.94 : go.hovered ? 1.05 : 1
                                Behavior on scale {
                                    NumberAnimation { duration: Kirigami.Units.shortDuration }
                                }
                            }
                            contentItem: Shape {
                                preferredRendererType: Shape.CurveRenderer
                                ShapePath {
                                    fillColor: "#FFFFFF"
                                    strokeColor: "transparent"
                                    PathPolyline {
                                        path: root.running ? [Qt.point(12, 11), Qt.point(16, 11), Qt.point(16, 25), Qt.point(12, 25), Qt.point(12, 11)]
                                                           : [Qt.point(14, 10), Qt.point(26, 18), Qt.point(14, 26), Qt.point(14, 10)]
                                    }
                                }
                                ShapePath {
                                    fillColor: root.running ? "#FFFFFF" : "transparent"
                                    strokeColor: "transparent"
                                    PathPolyline { path: [Qt.point(20, 11), Qt.point(24, 11), Qt.point(24, 25), Qt.point(20, 25), Qt.point(20, 11)] }
                                }
                            }
                        }
                    }
                }

                // How long: four lengths, or back to the start while it runs or rests.
                RowLayout {
                    Layout.alignment: Qt.AlignHCenter
                    spacing: 2
                    visible: !root.running && !root.paused

                    Repeater {
                        model: [3, 5, 10, 25]
                        Length {
                            required property int modelData
                            value: modelData
                            chosen: root.minutes === modelData
                            ink: card.ink
                            dim: card.dim
                            onClicked: root.setMinutes(modelData)
                        }
                    }
                }
                // Plein-air focus, on or off for the next run.
                Length {
                    Layout.alignment: Qt.AlignHCenter
                    visible: !root.running && !root.paused
                    text: i18nc("a timer: quiet notifications, a day on the painting", "Focus")
                    chosen: root.focusSession
                    ink: card.ink
                    dim: card.dim
                    onClicked: Plasmoid.configuration.focus = !root.focusSession
                    Accessible.role: Accessible.CheckBox
                    Accessible.checked: root.focusSession
                    PlasmaCore.ToolTipArea {
                        anchors.fill: parent
                        mainText: i18nc("a timer: quiet notifications, a day on the painting", "Focus")
                        subText: i18n("Notifications stay quiet, and the painting goes from dawn to night while the timer runs.")
                    }
                }
                T.AbstractButton {
                    id: again
                    Layout.alignment: Qt.AlignHCenter
                    visible: root.running || root.paused
                    text: i18nc("a timer: back to its full length", "Reset")
                    implicitWidth: againLabel.implicitWidth + 18
                    implicitHeight: 24
                    onClicked: root.reset()
                    background: Rectangle {
                        radius: height / 2
                        color: card.ink
                        opacity: again.hovered || again.visualFocus ? 0.08 : 0
                    }
                    contentItem: Text {
                        id: againLabel
                        text: again.text
                        color: card.dim
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        font.family: "Inter"
                        font.pixelSize: 11
                    }
                }
            }
        }
    }
}
