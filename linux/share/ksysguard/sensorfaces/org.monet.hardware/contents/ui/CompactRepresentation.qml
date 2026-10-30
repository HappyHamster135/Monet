import QtQuick
import QtQuick.Layouts
import org.kde.ksysguard.faces as Faces

Faces.CompactSensorFace {
    id: root
    Layout.minimumWidth: contentItem.implicitWidth
    Layout.minimumHeight: contentItem.implicitHeight
    contentItem: HardwareReadings {
        sensorIds: root.controller.highPrioritySensorIds
        updateRateLimit: root.controller.updateRateLimit
    }
}
