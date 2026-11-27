import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as K

Item {
    id: empty
    required property string symbol
    required property string title
    property string detail: ""
    property color tint: "#aaaab4"
    readonly property bool compact: height < 125
    implicitHeight: compact ? 72 : 150
    GridLayout {
        anchors.centerIn: parent
        width: Math.max(0, Math.min(empty.width - 24, 320))
        columns: empty.compact ? 2 : 1
        rowSpacing: 8; columnSpacing: 12
        Rectangle {
            Layout.alignment: Qt.AlignHCenter | Qt.AlignVCenter
            Layout.preferredWidth: empty.compact ? 36 : 48
            Layout.preferredHeight: width
            radius: 15; color: "#12ffffff"
            IslandGlyph { anchors.centerIn: parent; width: empty.compact ? 20 : 24; height: width
                source: empty.symbol; color: empty.tint }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 5
            Text {
                Layout.fillWidth: true; text: empty.title; textFormat: Text.PlainText
                color: "#ededf2"; font.pixelSize: 13; font.weight: Font.Medium
                horizontalAlignment: empty.compact ? Text.AlignLeft : Text.AlignHCenter
                wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight
            }
            Text {
                Layout.fillWidth: true; visible: !!empty.detail; text: empty.detail; textFormat: Text.PlainText
                color: "#aaaab4"; font.pixelSize: 12
                horizontalAlignment: empty.compact ? Text.AlignLeft : Text.AlignHCenter
                wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight
            }
        }
    }
}
