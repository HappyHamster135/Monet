import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.sensors as Sensors

ColumnLayout {
    id: readings
    property var sensorIds: []
    property int updateRateLimit: 1000
    property bool sampling: visible
    spacing: Kirigami.Units.smallSpacing

    // Some drivers expose a temperature sensor that always returns zero. A
    // zero fan speed is legitimate; GPU memory with no reported capacity is not.
    function reported(status, value, sensorId, capacity) {
        if (status !== Sensors.Sensor.Ready || typeof value !== "number" || !Number.isFinite(value)) return false
        if (sensorId.endsWith("Temperature") || sensorId.endsWith("/temperature")) return value > 0
        if (sensorId.endsWith("/usedVram")) return typeof capacity === "number" && capacity > 0 && value >= 0
        return value >= 0
    }

    Repeater {
        model: readings.sensorIds
        RowLayout {
            id: row
            required property string modelData
            readonly property bool gpu: modelData.startsWith("gpu/")
            readonly property string gpuPath: gpu ? modelData.substring(0, modelData.lastIndexOf("/")) : ""
            readonly property bool available: readings.reported(sensor.status, sensor.value, modelData, capacity.value)
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing

            Sensors.Sensor { id: sensor; sensorId: row.modelData; updateRateLimit: readings.updateRateLimit; enabled: readings.sampling }
            Sensors.Sensor { id: gpuName; sensorId: row.gpu ? row.gpuPath + "/name" : ""; enabled: readings.sampling && row.gpu }
            Sensors.Sensor { id: capacity; sensorId: row.modelData.endsWith("/usedVram") ? row.gpuPath + "/totalVram" : ""; enabled: readings.sampling && sensorId !== "" }

            QQC2.Label {
                Layout.fillWidth: true
                wrapMode: Text.Wrap
                text: {
                    if (row.gpu) {
                        const name = gpuName.value || sensor.name || i18nd("monet", "Graphics")
                        return row.modelData.endsWith("/usedVram")
                            ? i18nd("monet", "%1 video memory", name) : i18nd("monet", "%1 temperature", name)
                    }
                    if (row.modelData === "cpu/all/maximumTemperature") return i18nd("monet", "CPU temperature (hottest core)")
                    if (row.modelData.startsWith("lmsensors/")) return row.modelData.split("/")[1].split("-")[0] + " · " + sensor.name
                    return sensor.name || row.modelData
                }
            }
            QQC2.Label {
                Layout.alignment: Qt.AlignRight | Qt.AlignVCenter
                text: !row.available ? i18nd("monet", "Not reported")
                    : row.modelData.endsWith("/usedVram")
                        ? i18nd("monet", "%1 / %2", sensor.formattedValue, capacity.formattedValue)
                        : sensor.formattedValue
                opacity: row.available ? 1 : 0.65
                Accessible.description: row.available ? text : i18nd("monet", "The hardware or driver does not provide this reading.")
            }
        }
    }
    QQC2.Label {
        Layout.fillWidth: true
        visible: readings.sensorIds.length === 0
        wrapMode: Text.Wrap
        text: i18nd("monet", "No supported hardware sensors were found.")
    }
}
