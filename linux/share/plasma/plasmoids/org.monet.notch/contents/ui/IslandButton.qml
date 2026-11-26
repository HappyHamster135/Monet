import QtQuick
import QtQuick.Controls as C
import "IslandLayout.js" as IslandLayout
import org.kde.kirigami as K

C.AbstractButton {
    id: button
    property bool tile: false
    property bool plain: false
    property bool caption: false
    property color tint: "#f5f5f7"
    property color base: plain ? "transparent" : tile ? "#12ffffff" : "#29292c"
    property bool prominent: false
    implicitWidth: tile ? 95 : caption ? tag.implicitWidth + 25 : 32
    implicitHeight: tile ? IslandLayout.tileHeight : plain ? 29 : 32
    padding: 0
    hoverEnabled: true
    Accessible.name: text
    Accessible.onPressAction: click()
    Keys.onReturnPressed: click()
    Keys.onEnterPressed: click()
    C.ToolTip.text: text
    C.ToolTip.visible: hovered && !tile && !caption
    C.ToolTip.delay: K.Units.toolTipDelay
    scale: down ? 0.95 : 1
    Behavior on scale { NumberAnimation { duration: K.Units.shortDuration; easing.type: Easing.OutCubic } }
    background: Rectangle {
        radius: button.tile ? 10 : height / 2
        color: button.down ? "#525258" : button.checked || button.prominent ? "#f3f3f5" : button.hovered ? "#3c3c41" : button.base
        border.width: button.visualFocus ? 1.5 : button.tile ? 1 : 0
        border.color: button.visualFocus ? "#a3ccff" : "#0cffffff"
    }
    contentItem: Item {
        Column {
            width: parent.width - 6
            anchors.centerIn: parent
            spacing: button.tile ? 4 : 2
            K.Icon {
                anchors.horizontalCenter: parent.horizontalCenter
                width: button.tile ? 21 : 15; height: width
                visible: !button.caption
                source: button.icon.name; isMask: true
                color: !button.enabled ? "#77777e" : button.checked || button.prominent ? "#161618" : button.tint
            }
            Text {
                id: tag
                width: parent.width
                visible: button.tile || button.caption; text: button.text; color: button.checked || button.prominent ? "#161618" : button.tile ? "#f5f5f7" : button.tint
                textFormat: Text.PlainText; font.pixelSize: 12; font.weight: Font.Medium
                horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
                wrapMode: button.tile ? Text.Wrap : Text.NoWrap; maximumLineCount: button.tile ? 2 : 1
            }
        }
    }
}
