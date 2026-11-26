import QtQuick
import QtQuick.Layouts
import org.kde.ksysguard.sensors as Sensors

ColumnLayout {
    spacing: 8
    Repeater {
        model: [
            { title: i18n("CPU"), sensor: "cpu/all/usage", color: "#74b5ff" },
            { title: i18n("Memory"), sensor: "memory/physical/usedPercent", color: "#b69bff" },
            { title: i18n("Graphics"), sensor: "gpu/gpu0/usage", color: "#7cdba4" }
        ]
        Rectangle {
            id: row
            required property var modelData
            Layout.fillWidth: true; implicitHeight: 57; radius: 13; color: "#252528"
            Sensors.Sensor { id: reading; sensorId: row.modelData.sensor; updateRateLimit: 1500 }
            Sensors.Sensor { id: second; sensorId: row.modelData.sensor === "gpu/gpu0/usage" ? "gpu/gpu1/usage" : ""; enabled: sensorId !== ""; updateRateLimit: 1500 }
            readonly property var current: second.enabled && second.status === Sensors.Sensor.Ready && typeof second.value === "number" && (reading.status !== Sensors.Sensor.Ready || second.value > reading.value) ? second : reading
            readonly property bool available: current.status === Sensors.Sensor.Ready && typeof current.value === "number" && Number.isFinite(current.value)
            Accessible.role: Accessible.StaticText
            Accessible.name: title.text + " " + value.text
            Text { id: title; x: 14; y: 9; text: row.modelData.title; color: "white"; font.weight: Font.Medium }
            Text { id: value; anchors.right: parent.right; anchors.rightMargin: 14; y: 9; color: "#cfcfd4"; text: row.available ? row.current.formattedValue : i18n("Unavailable") }
            Rectangle { x: 14; y: 40; height: 4; width: parent.width - 28; radius: 2; color: "#444449"
                Rectangle { width: parent.width * (row.available ? Math.max(0, Math.min(1, row.current.value / 100)) : 0); height: 4; radius: 2; color: row.modelData.color }
            }
        }
    }
    Item { Layout.fillHeight: true }
}
