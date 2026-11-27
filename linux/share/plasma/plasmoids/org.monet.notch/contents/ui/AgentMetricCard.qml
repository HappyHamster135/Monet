import QtQuick
import QtQuick.Layouts

Rectangle {
    id: card
    property string heading: ""
    property string value: "—"
    property string detail: ""
    property string footnote: ""
    property string symbol: "activity"
    property color accent: "#ededf2"
    implicitHeight: 112; implicitWidth: 200; radius: 18; color: "#171719"
    ColumnLayout {
        anchors.fill: parent; anchors.margins: 12; spacing: 4
        RowLayout {
            Layout.fillWidth: true; spacing: 6
            IslandGlyph { source: card.symbol; color: card.accent; Layout.preferredWidth: 13; Layout.preferredHeight: 13 }
            Text { Layout.fillWidth: true; Layout.minimumWidth: 0; text: card.heading; color: "#b6b6c0"; font.pixelSize: 10; elide: Text.ElideRight }
        }
        Text {
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.fillHeight: true
            text: card.value; textFormat: Text.PlainText; color: card.accent; font.pixelSize: 24; font.weight: Font.Medium
            fontSizeMode: Text.HorizontalFit; minimumPixelSize: 16; elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
        }
        Text { Layout.fillWidth: true; Layout.minimumWidth: 0; text: card.detail; textFormat: Text.PlainText; color: "#9999a4"; font.pixelSize: 10; elide: Text.ElideRight }
        Text { Layout.fillWidth: true; Layout.minimumWidth: 0; text: card.footnote; textFormat: Text.PlainText; color: "#72727d"; font.pixelSize: 9; elide: Text.ElideRight }
    }
}
