import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.ksysguard.faces as Faces
import "../../../org.monet.performance/contents/ui" as Performance

Faces.SensorFace {
    id: face
    Layout.minimumWidth: 440
    Performance.WindowActivity { id: activity; item: face.contentItem }
    readonly property bool sampling: activity.active
    Performance.SensorCatalog { id: catalog }
    Performance.SummaryReadings { id: totals; sampling: face.sampling && catalog.ready }
    contentItem: GridLayout {
        Layout.minimumHeight: implicitHeight
        columns: width >= 850 ? 5 : 3
        columnSpacing: 8
        rowSpacing: 8
        Repeater {
            model: [i18nd("monet", "CPU"), i18nd("monet", "Memory"), i18nd("monet", "Graphics"),
                i18nd("monet", "Network"), i18nd("monet", "Storage")]
            Rectangle {
                required property int index
                required property string modelData
                objectName: "systemTotal" + index
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                implicitHeight: words.implicitHeight + 24
                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.035)
                radius: 8
                ColumnLayout {
                    id: words
                    anchors { left: parent.left; right: parent.right; verticalCenter: parent.verticalCenter; margins: 12 }
                    spacing: 4
                    QQC2.Label { text: modelData; font.weight: Font.DemiBold }
                    QQC2.Label {
                        Layout.fillWidth: true
                        text: totals.values[index]
                        font.pointSize: Kirigami.Theme.defaultFont.pointSize * (index < 3 ? 1.4 : 1)
                        font.weight: Font.DemiBold
                        wrapMode: Text.Wrap
                        Accessible.name: modelData + ": " + text
                    }
                    QQC2.Label {
                        Layout.fillWidth: true
                        visible: index === 1
                        text: totals.memoryDetail
                        wrapMode: Text.Wrap
                        color: Kirigami.Theme.disabledTextColor
                    }
                }
            }
        }
    }
}
