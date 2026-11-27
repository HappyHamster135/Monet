// Static PCI/power-supply inventory. Reading it never opens a GPU device.
import QtQuick
import org.kde.plasma.plasma5support as P5Support

Item {
    id: policy
    visible: false
    property bool monitorDedicatedGraphics: false
    property string helper: "@LIBEXECDIR@/monet-graphics-use"
    property bool ready: false
    property var sleepingDevices: []
    function allows(sensorId) {
        if (!sensorId.startsWith("gpu/")) return true
        if (!ready) return false
        return monitorDedicatedGraphics || !sleepingDevices.includes(sensorId.split("/")[1])
    }
    Component.onCompleted: reader.connectSource("'" + helper.replace(/'/g, "'\\''") + "' --policy")
    P5Support.DataSource {
        id: reader
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            try {
                const result = JSON.parse(data.stdout)
                if (data["exit code"] === 0 && result.version === 1 && Array.isArray(result.sleepingDevices)) {
                    policy.sleepingDevices = result.sleepingDevices
                    policy.ready = true
                }
            } catch (_) {}
        }
    }
}
