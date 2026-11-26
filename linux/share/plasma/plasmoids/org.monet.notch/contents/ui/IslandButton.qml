import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as K

C.AbstractButton {
    id: button
    property bool tile: false
    property bool caption: false
    property color tint: "#f5f5f7"
    property color base: tile ? "#252528" : "#29292c"
    property bool prominent: false
    implicitWidth: tile ? 95 : caption ? tag.implicitWidth + 25 : 32
    implicitHeight: tile ? 65 : 32
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
        radius: button.tile ? 13 : height / 2
        color: button.down ? "#525258" : button.checked || button.prominent ? "#f3f3f5" : button.hovered ? "#3c3c41" : button.base
        border.width: button.visualFocus ? 2 : 0
        border.color: "#81bfff"
    }
    contentItem: ColumnLayout {
        spacing: 3
        Item { Layout.fillHeight: true }
        K.Icon {
            Layout.alignment: Qt.AlignHCenter; Layout.preferredWidth: button.tile ? 20 : 15; Layout.preferredHeight: Layout.preferredWidth
            visible: !button.caption
            source: button.icon.name; isMask: true
            color: !button.enabled ? "#77777e" : button.checked || button.prominent ? "#161618" : button.tint
        }
        Text {
            id: tag
            visible: button.tile || button.caption; text: button.text; color: button.checked ? "#161618" : "#f5f5f7"
            textFormat: Text.PlainText; font.pixelSize: 12; font.weight: Font.Medium
            Layout.fillWidth: true; Layout.leftMargin: 3; Layout.rightMargin: 3
            horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight
            wrapMode: button.tile ? Text.Wrap : Text.NoWrap; maximumLineCount: button.tile ? 2 : 1
        }
        Item { Layout.fillHeight: true }
    }
}
