/*
 * The one bright thing: Play.
 */
import QtQuick

Rectangle {
    id: button
    property alias text: label.text
    property real speed: 1
    property real size: 15
    signal clicked()
    implicitWidth: label.implicitWidth + size * 2.6
    implicitHeight: size * 2.6
    radius: height / 2
    color: mouse.containsMouse ? "#FF6A42" : "#F2552C"
    scale: mouse.pressed ? 0.95 : mouse.containsMouse ? 1.04 : 1
    Behavior on scale {
        NumberAnimation { duration: Math.round(160 * button.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] }
    }
    Behavior on color { ColorAnimation { duration: Math.round(140 * button.speed) } }

    Text {
        id: label
        horizontalAlignment: Text.AlignLeft
        anchors.centerIn: parent
        color: "#FFFFFF"
        font.weight: Font.DemiBold
        font.pixelSize: button.size
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: button.clicked()
    }
    // From the keys too (Tab onto it, then Enter or Space), with a ring while it has them.
    activeFocusOnTab: true
    border.width: activeFocus ? 2 : 0
    border.color: "#FFFFFF"
    Keys.onReturnPressed: button.clicked()
    Keys.onEnterPressed: button.clicked()
    Keys.onSpacePressed: button.clicked()
    Accessible.role: Accessible.Button
    Accessible.name: label.text
    Accessible.onPressAction: button.clicked()
}
