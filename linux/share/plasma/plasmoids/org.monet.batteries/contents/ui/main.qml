/*
 * Batteries: everything with a battery, on Monet's glass, as Apple's widget
 * has it: this laptop first, then the mouse, the keyboard, controllers and
 * headphones, each a ring of paint round its sign, lily while there's plenty,
 * ochre when it runs low, the sun when it's nearly out, and a dab of the sun
 * beside the number while it charges. From UPower (what KDE reads too), through
 * Monet's helper, every minute.
 */
import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property string helper: "@LIBEXECDIR@/monet-quick"
    // [{ kind, name, level, charging }], this laptop first.
    property var batteries: []
    property bool looked: false

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "preferences-system-power-management"
    preferredRepresentation: fullRepresentation
    toolTipMainText: i18n("Batteries")
    toolTipSubText: batteries.map(b => root.label(b, 0) + " " + i18nc("a battery's charge, in percent", "%1%", b.level)).join(" · ")

    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source);
            try {
                root.batteries = JSON.parse(data["stdout"]);
            } catch (e) {
            }
            root.looked = true;
        }
    }

    Timer {
        interval: 60 * 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: runner.connectSource(root.helper + " batteries")
    }

    // The device's own name when it has one ("MX Master 3"), else what it is.
    function label(battery, index) {
        if (battery.kind === "laptop") {
            return index > 0 ? i18n("Second battery") : i18n("This laptop");
        }
        if (battery.name !== "") {
            return battery.name;
        }
        return {
            mouse: i18nc("a device with a battery", "Mouse"),
            keyboard: i18nc("a device with a battery", "Keyboard"),
            controller: i18nc("a device with a battery", "Controller"),
            headset: i18nc("a device with a battery", "Headset"),
            headphones: i18nc("a device with a battery", "Headphones"),
            speaker: i18nc("a device with a battery", "Speaker"),
            phone: i18nc("a device with a battery", "Phone"),
            tablet: i18nc("a device with a battery", "Tablet"),
            pen: i18nc("a device with a battery", "Pen"),
            touchpad: i18nc("a device with a battery", "Touchpad"),
            watch: i18nc("a device with a battery", "Watch")
        }[battery.kind] || i18nc("a device with a battery", "Battery");
    }

    // Each kind's sign, drawn as Monet Settings draws devices (24 x 24, a line of ink).
    readonly property var signs: ({
        laptop: "M4 5h16v10H4zM2 19h20",
        mouse: "M12 3a6 6 0 0 1 6 6v6a6 6 0 0 1-12 0V9a6 6 0 0 1 6-6zM12 7v3",
        keyboard: "M3 7h18v10H3zM7 10.5h.01M11 10.5h.01M15 10.5h.01M8 14h8",
        controller: "M7.5 8.5h9a4 4 0 0 1 3.9 4.9l-.8 3.3a2 2 0 0 1-3.4.9L14.8 16H9.2l-1.4 1.6a2 2 0 0 1-3.4-.9l-.8-3.3a4 4 0 0 1 3.9-4.9zM8.5 11.5v3M7 13h3M15.5 12h.01M17 14h.01",
        headset: "M4 15v-3a8 8 0 0 1 16 0v3M4 14h3v6H4zM17 14h3v6h-3z",
        headphones: "M4 15v-3a8 8 0 0 1 16 0v3M4 14h3v6H4zM17 14h3v6h-3z",
        speaker: "M5 10h3l5-4v12l-5-4H5zM17 9a4.5 4.5 0 0 1 0 6",
        phone: "M8 3h8v18H8zM11 18h2",
        tablet: "M5 3h14v18H5zM11 18h2",
        pen: "M4 20l4-1 11-11-3-3L5 16zM14 6l3 3",
        touchpad: "M4 6h16v12H4zM12 14v4",
        watch: "M8 7h8v10H8zM9 7l1-4h4l1 4M9 17l1 4h4l1-4",
        other: "M4 8h14v8H4zM20 11v2"
    })

    // One battery: a ring of paint round its sign, its charge and its name beneath.
    component Ring: ColumnLayout {
        id: ring
        property var battery
        // What it is and its sign, from the widget (a component can't see the widget's own names).
        property string title
        property string sign
        property color ink
        property color dim
        property color lily
        readonly property real shown: Math.max(0, Math.min(100, battery.level))
        // Lily while there's plenty, ochre when it runs low, the sun when it's nearly out.
        readonly property color stroke: shown > 20 ? lily : shown > 10 ? "#D9963A" : "#F2552C"
        spacing: 2
        Accessible.role: Accessible.StaticText
        Accessible.name: title + ", " + i18nc("a battery's charge, in percent", "%1%", battery.level)
                         + (battery.charging ? ", " + i18n("charging") : "")

        Item {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: 58
            implicitHeight: 58

            Shape {
                anchors.fill: parent
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    strokeColor: Qt.rgba(ring.ink.r, ring.ink.g, ring.ink.b, 0.12)
                    strokeWidth: 5
                    fillColor: "transparent"
                    PathAngleArc { centerX: 29; centerY: 29; radiusX: 25; radiusY: 25; startAngle: 0; sweepAngle: 360 }
                }
                ShapePath {
                    strokeColor: ring.stroke
                    strokeWidth: 5
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    PathAngleArc {
                        centerX: 29; centerY: 29; radiusX: 25; radiusY: 25; startAngle: -90
                        sweepAngle: Math.max(0.5, 360 * ring.shown / 100)
                    }
                }
            }
            Shape {
                anchors.centerIn: parent
                width: 22
                height: 22
                preferredRendererType: Shape.CurveRenderer
                ShapePath {
                    scale: Qt.size(22 / 24, 22 / 24)
                    strokeColor: ring.ink
                    strokeWidth: 2
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    joinStyle: ShapePath.RoundJoin
                    PathSvg { path: ring.sign }
                }
            }
        }
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            spacing: 4
            // Charging: a dab of the sun.
            Rectangle {
                visible: ring.battery.charging
                Layout.preferredWidth: 6
                Layout.preferredHeight: 6
                radius: 3
                color: "#F2552C"
            }
            Text {
                horizontalAlignment: Text.AlignHCenter
                text: i18nc("a battery's charge, in percent", "%1%", ring.battery.level)
                color: ring.ink
                font.family: "Fraunces 72pt SuperSoft"
                font.pixelSize: 16
                font.features: { "tnum": 1 }
            }
        }
        Text {
            Layout.alignment: Qt.AlignHCenter
            Layout.maximumWidth: ring.width
            horizontalAlignment: Text.AlignHCenter
            text: ring.title
            color: ring.dim
            // Two lines before it's cut short ("Tämä kannettava").
            wrapMode: Text.Wrap
            maximumLineCount: 2
            elide: Text.ElideRight
            font.family: "Inter"
            font.pixelSize: 11
        }
    }

    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 9
        Layout.minimumHeight: Kirigami.Units.gridUnit * 7
        Layout.preferredWidth: Kirigami.Units.gridUnit * 16
        Layout.preferredHeight: Kirigami.Units.gridUnit * 8

        Glass {
            id: card
            anchors.fill: parent

            readonly property color lily: smoke ? "#4DB4A0" : "#357F72"
            // As many as fit, side by side.
            readonly property int fits: Math.max(1, Math.floor((width - 2 * Kirigami.Units.gridUnit) / (Kirigami.Units.gridUnit * 4.4)))

            Row {
                id: rings
                anchors.centerIn: parent
                width: parent.width - 2 * Kirigami.Units.gridUnit
                visible: root.batteries.length > 0
                Repeater {
                    model: root.batteries.slice(0, card.fits)
                    Ring {
                        required property var modelData
                        required property int index
                        width: rings.width / Math.min(root.batteries.length, card.fits)
                        battery: modelData
                        title: root.label(modelData, index)
                        sign: root.signs[modelData.kind] || root.signs.other
                        ink: card.ink
                        dim: card.dim
                        lily: card.lily
                    }
                }
            }

            // Nothing with a battery yet (a desktop PC with wired things).
            Text {
                anchors.centerIn: parent
                width: parent.width - 2 * Kirigami.Units.gridUnit
                visible: root.looked && root.batteries.length === 0
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: i18n("Wireless mice, headphones and controllers show here with their battery.")
                color: card.dim
                font.family: "Fraunces 72pt SuperSoft"
                font.italic: true
                font.pixelSize: 15
            }
        }
    }
}
