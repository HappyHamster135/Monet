import QtQuick
import org.kde.ksysguard.sensors as Sensors

// Shared by the totals strip and resource tabs. No subprocesses or history
// buffers: the daemon coalesces these subscriptions with the selected graph.
QtObject {
    id: readings
    property bool sampling: true
    property string gpu: "gpu/all"
    function value(sensor) {
        return sensor.status === Sensors.Sensor.Ready && typeof sensor.value === "number"
            && Number.isFinite(sensor.value) && sensor.value >= 0 ? sensor.formattedValue : "—"
    }
    readonly property var values: [value(cpu), value(memory), value(graphics),
        "↓ " + value(download) + "  ↑ " + value(upload),
        i18nd("monet", "Read") + " " + value(read) + " · " + i18nd("monet", "Write") + " " + value(write)]
    readonly property string memoryDetail: value(used) + " / " + value(total)
    property Sensors.Sensor cpu: Sensors.Sensor { sensorId: "cpu/all/usage"; enabled: readings.sampling; updateRateLimit: 1000 }
    property Sensors.Sensor memory: Sensors.Sensor { sensorId: "memory/physical/usedPercent"; enabled: readings.sampling; updateRateLimit: 1000 }
    property Sensors.Sensor graphics: Sensors.Sensor { sensorId: readings.gpu ? readings.gpu + "/usage" : ""; enabled: readings.sampling && readings.gpu !== ""; updateRateLimit: 1000 }
    property Sensors.Sensor download: Sensors.Sensor { sensorId: "network/all/download"; enabled: readings.sampling; updateRateLimit: 1000 }
    property Sensors.Sensor upload: Sensors.Sensor { sensorId: "network/all/upload"; enabled: readings.sampling; updateRateLimit: 1000 }
    property Sensors.Sensor read: Sensors.Sensor { sensorId: "disk/all/read"; enabled: readings.sampling; updateRateLimit: 1000 }
    property Sensors.Sensor write: Sensors.Sensor { sensorId: "disk/all/write"; enabled: readings.sampling; updateRateLimit: 1000 }
    property Sensors.Sensor used: Sensors.Sensor { sensorId: "memory/physical/used"; enabled: readings.sampling; updateRateLimit: 1000 }
    property Sensors.Sensor total: Sensors.Sensor { sensorId: "memory/physical/total"; enabled: readings.sampling; updateRateLimit: 1000 }
}
