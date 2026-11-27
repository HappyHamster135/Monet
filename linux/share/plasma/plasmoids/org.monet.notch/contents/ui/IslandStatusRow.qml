import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts

C.AbstractButton {
    id: row
    property string heading: ""
    property string subtitle: ""
    property string symbol: "terminal"
    property color accent: "#c6c6d0"
    property bool connected: false
    implicitHeight: 66; implicitWidth: 240
    padding: 12; hoverEnabled: true
    Accessible.name: heading
    Accessible.description: subtitle
    background: Rectangle { radius: 12; color: row.hovered ? "#252529" : "#17171b"; border.width: row.visualFocus ? 1 : 0; border.color: "#aaaab2" }
    contentItem: RowLayout {
        spacing: 10
        Rectangle {
            Layout.preferredWidth: 32; Layout.preferredHeight: 32; radius: 10; color: "#12ffffff"
            IslandGlyph { anchors.centerIn: parent; width: 17; height: 17; source: row.symbol; color: row.accent }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 3
            Text { Layout.fillWidth: true; text: row.heading; textFormat: Text.PlainText; elide: Text.ElideRight; color: "#ededf2"; font.pixelSize: 13; font.weight: Font.Medium }
            Text { Layout.fillWidth: true; text: row.subtitle; textFormat: Text.PlainText; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; color: "#9999a4"; font.pixelSize: 10 }
        }
        Rectangle { visible: row.connected; width: 5; height: 5; radius: 2.5; color: "#9edab7" }
        IslandGlyph { source: "forward"; color: "#777781"; Layout.preferredWidth: 12; Layout.preferredHeight: 12 }
    }
}
