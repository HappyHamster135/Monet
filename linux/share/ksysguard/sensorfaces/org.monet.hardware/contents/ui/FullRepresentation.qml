import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.faces as Faces

Faces.SensorFace {
    id: root
    Layout.minimumWidth: Kirigami.Units.gridUnit * 16
    Layout.minimumHeight: contentItem.implicitHeight
    contentItem: ColumnLayout {
        spacing: Kirigami.Units.largeSpacing
        Kirigami.Heading {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            level: 2
            text: root.controller.title
            visible: root.controller.showTitle
        }
        HardwareReadings {
            Layout.fillWidth: true
            sensorIds: root.controller.highPrioritySensorIds
            updateRateLimit: root.controller.updateRateLimit
        }
        Item { Layout.fillHeight: true }
    }
}
