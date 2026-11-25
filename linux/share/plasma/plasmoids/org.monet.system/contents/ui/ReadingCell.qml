import QtQuick
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.sensors as Sensors

Item {
    id: cell
    required property string reading
    required property QtObject names
    required property bool sampling
    required property var power
    required property string style
    property bool inlineLabel: false

    readonly property bool battery: reading.startsWith("battery/")
    readonly property bool percent: names.percentage(reading)
    readonly property bool chargeKnown: power.available === true && Number.isFinite(power.battery) && power.battery >= 0 && power.battery <= 100
    readonly property QtObject sensor: source.item
    readonly property var value: {
        if (battery) {
            if (!chargeKnown) return null
            if (reading === "battery/charge") return power.battery
            return Number.isFinite(power.minutes) && power.minutes >= 0 ? power.minutes : null
        }
        if (!sensor || sensor.status !== Sensors.Sensor.Ready || !Number.isFinite(sensor.value)) return null
        if (percent && (sensor.value < 0 || sensor.value > 100)) return null
        return sensor.value
    }
    readonly property string label: names.name(reading)
    readonly property string display: {
        if (value === null) return "—"
        if (percent) return i18nd("monet", "%1%", Math.round(value))
        if (reading === "battery/time") return Math.floor(value / 60) + ":" + String(value % 60).padStart(2, "0")
        return sensor.formattedValue
    }
    readonly property string shortLabel: reading === "battery/time" && value !== null
        ? (power.charging ? i18nd("monet", "To full") : i18nd("monet", "Time left")) : names.shortName(reading)
    readonly property string captionText: {
        if (width >= metrics.advanceWidth(shortLabel) + 6) return shortLabel
        if (reading === "memory/physical/usedPercent") return i18nd("monet", "RAM")
        if (reading === "battery/time") return i18nd("monet", "Time")
        return shortLabel
    }
    readonly property string description: (reading === "battery/time" && value !== null ? shortLabel : label) + "  " + display
    readonly property bool showValue: style !== "bars" || !percent || value === null
    readonly property bool showBar: style !== "values" && percent && value !== null
    readonly property real textHeight: Math.ceil(metrics.height)
    readonly property real slotWidth: Math.ceil(Math.max(metrics.advanceWidth(shortLabel),
        metrics.advanceWidth(percent ? "100%" : "999 MiB/s")) + 12)
    readonly property real wideSlot: slotWidth + Math.ceil(metrics.advanceWidth(shortLabel)) + 5
    FontMetrics { id: metrics; font: Kirigami.Theme.smallFont }
    Loader {
        id: source
        active: cell.sampling && !cell.battery
        sourceComponent: Component { Sensors.Sensor { sensorId: cell.reading; updateRateLimit: 2000 } }
    }

    Item {
        anchors.centerIn: parent
        width: Math.max(0, parent.width - 4)
        height: Math.min(parent.height, cell.inlineLabel ? cell.textHeight + 3 :
                cell.textHeight * (cell.showValue ? 2 : 1) + (cell.showBar ? 5 : 0))
        Text {
            id: caption
            width: cell.inlineLabel && cell.showValue ? Math.min(metrics.advanceWidth(text) + 2, parent.width * .52) : parent.width
            height: cell.inlineLabel ? parent.height - (cell.showBar ? 3 : 0) : Math.min(cell.textHeight, parent.height)
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            text: cell.captionText
            color: Kirigami.Theme.textColor
            font: Kirigami.Theme.smallFont
            elide: Text.ElideRight
        }
        Text {
            visible: cell.showValue
            x: cell.inlineLabel ? caption.width : 0
            y: cell.inlineLabel ? 0 : caption.height
            width: parent.width - x
            height: Math.max(0, parent.height - y - (cell.showBar ? 3 : 0))
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            text: cell.display
            color: Kirigami.Theme.textColor
            font.family: Kirigami.Theme.defaultFont.family
            font.pixelSize: Math.max(9, cell.textHeight - 1)
            font.weight: Font.DemiBold
            font.features: {"tnum": 1}
            fontSizeMode: Text.HorizontalFit
            minimumPixelSize: 8
            elide: Text.ElideRight
        }
        Rectangle {
            visible: cell.showBar
            anchors.bottom: parent.bottom
            width: parent.width; height: 3; radius: 1.5
            color: Qt.alpha(Kirigami.Theme.textColor, .18)
            Rectangle {
                height: parent.height
                width: parent.width * Math.min(100, Math.max(0, cell.value || 0)) / 100
                radius: parent.radius
                color: Kirigami.Theme.highlightColor
            }
        }
    }
}
