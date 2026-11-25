/*
 * System: how hard the PC is working, on Monet's glass. A dial each for the
 * processor, the graphics and the memory, a stroke of paint that warms from
 * lily to the sun as the work gets harder, with how hot the chips run (or how
 * much memory is used) beneath, and what's coming in and going out over the
 * network along the foot. From KDE's own sensors, the ones System Monitor
 * reads; a part the PC can't measure (graphics in a virtual machine) leaves.
 */
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtQuick.Shapes
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.sensors as Sensors

PlasmoidItem {
    id: root
    readonly property bool sideBar: Plasmoid.formFactor === PlasmaCore.Types.Vertical
    readonly property bool onBar: sideBar || Plasmoid.formFactor === PlasmaCore.Types.Horizontal
    readonly property var readings: Array.from(Plasmoid.configuration.readings || [])
    readonly property bool dashboardSampling: activity.active && (!onBar || expanded)
    SessionActivity {
        id: activity
        viewVisible: root.visible
        observePower: root.onBar && root.readings.some(key => key.startsWith("battery/"))
    }

    // Degrees the way this PC's region counts them.
    readonly property bool fahrenheit: Qt.locale().measurementSystem === Locale.ImperialUSSystem

    function degrees(celsius) {
        return Math.round(fahrenheit ? celsius * 9 / 5 + 32 : celsius) + "°";
    }

    function ready(sensor) {
        return sensor.status === Sensors.Sensor.Ready && typeof sensor.value === "number"
            && Number.isFinite(sensor.value);
    }

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "utilities-system-monitor"
    TaskManagerAction { id: taskManager; menuApplet: Plasmoid }
    Plasmoid.contextualActions: taskManager.showInAppletMenu ? [taskManager] : []
    toolTipMainText: i18nd("monet", "System")
    toolTipSubText: onBar ? (compactRepresentationItem?.summary || i18nd("monet", "Choose Home Bar readings")) :
        i18nd("monet", "Double-click to open Task Manager")
    preferredRepresentation: onBar ? compactRepresentation : fullRepresentation
    compactRepresentation: ReadingStrip {
        readings: root.readings
        style: Plasmoid.configuration.readingStyle
        vertical: root.sideBar
        power: activity.powerReady ? activity.batteryState : ({})
        sampling: activity.active
        enabled: !Plasmoid.containment?.corona.editMode
        onPressedReading: {
            if (root.readings.length) root.expanded = !root.expanded
            else Plasmoid.internalAction("configure").trigger()
        }
    }

    component Reading: Sensors.Sensor {
        required property bool sampling
        enabled: sampling
        updateRateLimit: 1500
    }

    Reading { sampling: root.dashboardSampling; id: cpu; sensorId: "cpu/all/usage" }
    Reading { sampling: root.dashboardSampling; id: cpuHeat; sensorId: "cpu/all/maximumTemperature" }
    Reading { sampling: root.dashboardSampling; id: memory; sensorId: "memory/physical/usedPercent" }
    Reading { sampling: root.dashboardSampling; id: memoryUsed; sensorId: "memory/physical/used" }
    Reading { sampling: root.dashboardSampling; id: download; sensorId: "network/all/download" }
    Reading { sampling: root.dashboardSampling; id: upload; sensorId: "network/all/upload" }
    // Each graphics chip: the busier one is the one a game runs on (a laptop has two).
    Reading { sampling: root.dashboardSampling; id: gpu0; sensorId: "gpu/gpu0/usage" }
    Reading { sampling: root.dashboardSampling; id: gpu1; sensorId: "gpu/gpu1/usage" }
    Reading { sampling: root.dashboardSampling; id: gpuHeat0; sensorId: "gpu/gpu0/temperature" }
    Reading { sampling: root.dashboardSampling; id: gpuHeat1; sensorId: "gpu/gpu1/temperature" }
    readonly property bool second: ready(gpu1) && (!ready(gpu0) || gpu1.value > gpu0.value)
    readonly property var gpu: second ? gpu1 : gpu0
    readonly property var gpuHeat: second ? gpuHeat1 : gpuHeat0

    // One dial: how busy, from 0 to 100, its name, and a line beneath.
    component Dial: ColumnLayout {
        id: dial
        property real value: 0
        property bool available: false
        property string label
        property string detail
        property color ink
        property color dim
        property color lily
        // Lily while there's room to spare, ochre when it's busy, the sun when it's nearly full.
        readonly property color stroke: shown < 60 ? lily : shown < 85 ? "#D9963A" : "#F2552C"
        property real shown: Math.max(0, Math.min(100, value))
        Behavior on shown {
            NumberAnimation { duration: Kirigami.Units.longDuration * 2; easing.type: Easing.OutCubic }
        }
        spacing: 0

        Item {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: 68
            implicitHeight: 60

            Shape {
                anchors.fill: parent
                preferredRendererType: Shape.CurveRenderer
                // The whole way round, faint, and how far it has come, in paint.
                ShapePath {
                    strokeColor: Qt.rgba(dial.ink.r, dial.ink.g, dial.ink.b, 0.12)
                    strokeWidth: 6
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    PathAngleArc { centerX: 34; centerY: 34; radiusX: 29; radiusY: 29; startAngle: 135; sweepAngle: 270 }
                }
                ShapePath {
                    strokeColor: dial.stroke
                    Behavior on strokeColor {
                        ColorAnimation { duration: Kirigami.Units.longDuration }
                    }
                    strokeWidth: 6
                    fillColor: "transparent"
                    capStyle: ShapePath.RoundCap
                    PathAngleArc {
                        centerX: 34; centerY: 34; radiusX: 29; radiusY: 29; startAngle: 135
                        sweepAngle: Math.max(0.5, 270 * dial.shown / 100)
                    }
                }
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                anchors.horizontalCenter: parent.horizontalCenter
                y: 21
                text: dial.available ? i18nc("a dial's reading, in percent", "%1%", Math.round(dial.value)) : "—"
                Accessible.name: dial.available ? text : i18nd("monet", "Not reported")
                color: dial.ink
                font.family: "Fraunces 72pt SuperSoft"
                font.pixelSize: 17
                font.features: { "tnum": 1 }
            }
        }
        Text {
            horizontalAlignment: Text.AlignLeft
            Layout.alignment: Qt.AlignHCenter
            Layout.maximumWidth: dial.width
            text: dial.label
            color: dial.ink
            elide: Text.ElideRight
            font.family: "Inter"
            font.pixelSize: 12
            font.weight: Font.Medium
        }
        Text {
            horizontalAlignment: Text.AlignLeft
            Layout.alignment: Qt.AlignHCenter
            Layout.maximumWidth: dial.width
            text: dial.detail
            color: dial.dim
            elide: Text.ElideRight
            font.family: "Inter"
            font.pixelSize: 11
            font.features: { "tnum": 1 }
        }
    }

    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 14
        Layout.minimumHeight: Kirigami.Units.gridUnit * 8
        Layout.preferredWidth: Kirigami.Units.gridUnit * 19
        Layout.preferredHeight: Kirigami.Units.gridUnit * (root.onBar ? 12 : 9)

        TapHandler {
            acceptedButtons: Qt.LeftButton
            enabled: !Plasmoid.containment || !Plasmoid.containment.corona.editMode
            onDoubleTapped: taskManager.trigger()
        }

        Glass {
            id: card
            anchors.fill: parent

            readonly property color lily: smoke ? "#4DB4A0" : "#357F72"

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: Kirigami.Units.gridUnit
                anchors.rightMargin: Kirigami.Units.gridUnit
                anchors.topMargin: Math.round(Kirigami.Units.gridUnit * 0.9)
                anchors.bottomMargin: Math.round(Kirigami.Units.gridUnit * 0.7)
                spacing: 0

                // The dials share the width (graphics leaves when there's none to measure).
                Row {
                    id: dials
                    Layout.fillWidth: true
                    readonly property int count: root.ready(root.gpu) ? 3 : 2

                    Dial {
                        width: dials.width / dials.count
                        value: root.ready(cpu) ? cpu.value : 0
                        available: root.ready(cpu)
                        label: i18nc("the computer's main chip", "Processor")
                        detail: root.ready(cpuHeat) && cpuHeat.value > 0 ? root.degrees(cpuHeat.value) : ""
                        ink: card.ink
                        dim: card.dim
                        lily: card.lily
                    }
                    Dial {
                        width: dials.width / dials.count
                        visible: root.ready(root.gpu)
                        value: visible ? root.gpu.value : 0
                        available: root.ready(root.gpu)
                        label: i18nc("the computer's graphics chip", "Graphics")
                        detail: root.ready(root.gpuHeat) && root.gpuHeat.value > 0 ? root.degrees(root.gpuHeat.value) : ""
                        ink: card.ink
                        dim: card.dim
                        lily: card.lily
                    }
                    Dial {
                        width: dials.width / dials.count
                        value: root.ready(memory) ? memory.value : 0
                        available: root.ready(memory)
                        label: i18nc("the computer's working memory (RAM)", "Memory")
                        detail: root.ready(memoryUsed) ? memoryUsed.formattedValue : ""
                        ink: card.ink
                        dim: card.dim
                        lily: card.lily
                    }
                }

                Item { Layout.fillHeight: true }

                // The network, along the foot: down and up, as fast as it goes now.
                Rectangle {
                    Layout.fillWidth: true
                    Layout.bottomMargin: 6
                    implicitHeight: 1
                    color: card.ink
                    opacity: 0.1
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.gridUnit
                    visible: root.ready(download)

                    Text {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        horizontalAlignment: Text.AlignHCenter
                        text: "↓  " + download.formattedValue
                        color: card.dim
                        elide: Text.ElideRight
                        font.family: "Inter"
                        font.pixelSize: 11
                        font.features: { "tnum": 1 }
                        Accessible.name: i18nc("%1 is a speed", "Downloading %1", download.formattedValue)
                    }
                    Text {
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        horizontalAlignment: Text.AlignHCenter
                        text: "↑  " + upload.formattedValue
                        color: card.dim
                        elide: Text.ElideRight
                        font.family: "Inter"
                        font.pixelSize: 11
                        font.features: { "tnum": 1 }
                        Accessible.name: i18nc("%1 is a speed", "Uploading %1", upload.formattedValue)
                    }
                }
                Controls.Button {
                    visible: root.onBar
                    Layout.alignment: Qt.AlignRight
                    text: i18nd("monet", "Choose Home Bar readings")
                    icon.name: "configure"
                    onClicked: Plasmoid.internalAction("configure").trigger()
                }
            }
        }
    }
}
