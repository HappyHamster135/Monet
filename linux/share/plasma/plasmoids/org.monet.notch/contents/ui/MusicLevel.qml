import QtQuick
import org.kde.plasma.private.volume as Pulse

Item {
    id: meter
    Pulse.VolumeMonitor { id: monitor; target: Pulse.PreferredDevice.sink }
    Row {
        anchors.fill: parent; spacing: 1
        Repeater {
            model: 3
            Rectangle {
                required property int index
                width: 3; radius: 1; color: "#9dd9c9"; anchors.verticalCenter: parent.verticalCenter
                height: Math.max(2, (meter.height - 2) * Math.max(0, Math.min(1, monitor.volume * (1.65 - 0.37 * index))))
            }
        }
    }
}
