import QtQuick
import QtQuick.Controls as C
import org.kde.kirigami as K
import "IslandSymbols.js" as Symbols

// A launcher glyph and its two-line label share one generous hit target.
C.AbstractButton {
    id: tile
    property real diameter: 32
    property bool favorite: false
    property string symbol: ""
    property string fullName: text
    property color accent: "#ededf2"
    readonly property string symbolPath: Symbols.path(symbol)
    implicitWidth: 72; implicitHeight: diameter + 38
    padding: 0; hoverEnabled: true
    opacity: enabled ? 1 : 0.4
    Accessible.name: fullName
    Accessible.onPressAction: click()



    Keys.onReturnPressed: click()
    Keys.onEnterPressed: click()
    background: Rectangle {
        radius: 12; color: tile.down ? "#18ffffff" : "transparent"
        border.width: tile.visualFocus ? 1 : 0; border.color: "#88ffffff"
    }
    contentItem: Item {
        Rectangle {
            id: disc
            anchors.horizontalCenter: parent.horizontalCenter; y: 4
            width: tile.diameter; height: width; radius: width / 2
            color: tile.checked ? "#eeeeef" : tile.hovered || tile.visualFocus ? "#26ffffff" : "#14ffffff"
            K.Icon {
                visible: !tile.symbolPath
                anchors.centerIn: parent
                width: tile.diameter >= 40 ? 18 : 16; height: width
                source: visible ? tile.icon.name : ""; isMask: true
                color: tile.checked ? "#171719" : tile.accent
            }
            Image {
                anchors.centerIn: parent
                width: tile.diameter >= 40 ? 18 : 16; height: width
                visible: !!tile.symbolPath
                sourceSize: Qt.size(72, 72)
                source: visible ? "data:image/svg+xml," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="none" stroke="' + (tile.checked ? '#171719' : tile.accent) + '" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" d="' + tile.symbolPath + '"/></svg>') : ""
            }
            K.Icon {
                visible: tile.favorite
                anchors.top: parent.top; anchors.right: parent.right
                width: 9; height: 9; source: visible ? "rating" : ""; isMask: true; color: "#cbb886"
            }
        }
        Text {
            anchors.top: disc.bottom; anchors.topMargin: 6
            anchors.left: parent.left; anchors.right: parent.right; anchors.margins: 3
            height: 28
            text: tile.text; textFormat: Text.PlainText
            color: "#eeeeef"; font.pixelSize: tile.diameter >= 40 ? 11 : 10; font.weight: Font.Medium
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignTop
            wrapMode: Text.WordWrap; maximumLineCount: 2; elide: Text.ElideRight
        }
    }
}
