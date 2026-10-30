/* Four native shared sensors; no subprocess, history buffer or animation loop. */
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.sensors as Sensors

PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "preferences-system-network"
    Plasmoid.contextualActions: [TaskManagerAction { id: taskManager }]
    preferredRepresentation: fullRepresentation
    toolTipMainText: i18nd("monet", "Network")
    Sensors.Sensor { enabled: root.visible; updateRateLimit: 2000; id: download; sensorId: "network/all/download" }
    Sensors.Sensor { enabled: root.visible; updateRateLimit: 2000; id: upload; sensorId: "network/all/upload" }
    Sensors.Sensor { enabled: root.visible; updateRateLimit: 2000; id: downloaded; sensorId: "network/all/totalDownload" }
    Sensors.Sensor { enabled: root.visible; updateRateLimit: 2000; id: uploaded; sensorId: "network/all/totalUpload" }
    function value(sensor) { return sensor.status === Sensors.Sensor.Ready && Number.isFinite(sensor.value) && sensor.value >= 0 ? sensor.formattedValue : "—"; }
    fullRepresentation: Glass {
        id: card
        Layout.minimumWidth: Kirigami.Units.gridUnit * 15
        Layout.minimumHeight: Kirigami.Units.gridUnit * 12
        Layout.preferredWidth: Kirigami.Units.gridUnit * 19
        Layout.preferredHeight: Kirigami.Units.gridUnit * 14
        ColumnLayout {
            anchors.fill: parent; anchors.margins: Kirigami.Units.gridUnit
            spacing: Kirigami.Units.smallSpacing
            Text { text: i18nd("monet", "Network"); color: card.ink; font.family: "Fraunces 72pt SuperSoft"; font.pixelSize: 22 }
            Text { text: i18nd("monet", "All network interfaces"); color: card.dim; font.family: "Inter"; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight }
            Item { Layout.fillHeight: true }
            Repeater {
                model: [
                    {label: i18nd("monet", "Download"), speed: download, total: downloaded, arrow: "↓"},
                    {label: i18nd("monet", "Upload"), speed: upload, total: uploaded, arrow: "↑"}]
                ColumnLayout {
                    required property var modelData
                    Layout.fillWidth: true
                    RowLayout {
                        Text { text: modelData.arrow + " " + modelData.label; color: card.dim; font.family: "Inter"; font.pixelSize: 13 }
                        Item { Layout.fillWidth: true }
                        Text { text: root.value(modelData.speed); color: card.ink; font.family: "Inter"; font.pixelSize: 18; font.weight: Font.DemiBold; Layout.fillWidth: true; horizontalAlignment: Text.AlignRight; fontSizeMode: Text.Fit; minimumPixelSize: 12 }
                    }
                    Text { text: i18nd("monet", "%1 since connection started", root.value(modelData.total)); color: card.dim; font.family: "Inter"; font.pixelSize: 11; Layout.fillWidth: true; elide: Text.ElideRight }
                }
            }
            Item { Layout.fillHeight: true }
            QQC2.Button { text: i18nd("monet", "Task Manager"); icon.name: "utilities-system-monitor"; onClicked: taskManager.trigger(); enabled: !Plasmoid.containment.corona.editMode }
        }
    }
}
