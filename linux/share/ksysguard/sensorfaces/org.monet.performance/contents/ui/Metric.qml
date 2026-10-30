import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.sensors as Sensors

ColumnLayout {
    id: metric
    property string label
    property string sensorId
    property bool paused: false
    property bool positiveOnly: false
    property bool allowText: false
    property bool compact: false
    property string capacityId: ""
    readonly property bool reported: sensor.status === Sensors.Sensor.Ready
        && ((allowText && typeof sensor.value === "string" && sensor.value.length > 0)
            || (typeof sensor.value === "number" && Number.isFinite(sensor.value)
                && (positiveOnly ? sensor.value > 0 : sensor.value >= 0)))
        && (!capacityId || (capacity.status === Sensors.Sensor.Ready && capacity.value > 0))
    spacing: 3

    Sensors.Sensor { id: sensor; sensorId: metric.sensorId; updateRateLimit: 1000; enabled: !metric.paused }
    Sensors.Sensor { id: capacity; sensorId: metric.capacityId; updateRateLimit: 1000; enabled: !metric.paused }
    QQC2.Label {
        Layout.fillWidth: true
        text: metric.label
        color: Kirigami.Theme.disabledTextColor
        wrapMode: Text.Wrap
    }
    QQC2.Label {
        Layout.fillWidth: true
        text: metric.reported ? (metric.allowText ? sensor.value : sensor.formattedValue) : i18nd("monet", "Not reported")
        font.pointSize: Kirigami.Theme.defaultFont.pointSize * (metric.reported && !metric.compact ? 1.4 : 1)
        font.weight: Font.Medium
        wrapMode: Text.Wrap
        Accessible.name: metric.label + ": " + text
    }
}
