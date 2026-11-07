/*
 * One choice of a few, as Settings' and Games' choices are: the chosen one on a pebble of
 * paper. `plain` for one standing alone (a kind of app), with how many there are (`count`).
 */
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: pebble
    property var tone
    property alias text: label.text
    property bool chosen: false
    property bool plain: false
    property int count: -1
    signal clicked()

    implicitWidth: row.implicitWidth + 24
    implicitHeight: Math.max(plain ? 32 : 30, row.implicitHeight + 12)
    width: Math.min(implicitWidth, parent.width)
    height: implicitHeight
    radius: height / 2
    color: chosen ? (tone.dark ? Qt.rgba(1, 1, 1, 0.16) : "#FFFFFF")
        : mouse.containsMouse ? tone.press : plain ? tone.wash2 : "transparent"
    border.width: activeFocus ? 2 : plain && chosen ? 1 : 0
    border.color: activeFocus ? tone.lily : tone.line
    activeFocusOnTab: true
    Keys.onReturnPressed: pebble.clicked()
    Keys.onEnterPressed: pebble.clicked()
    Keys.onSpacePressed: pebble.clicked()
    Behavior on color { ColorAnimation { duration: Math.round(140 * pebble.tone.speed) } }

    RowLayout {
        id: row
        anchors.centerIn: parent
        width: parent.width - 24
        spacing: 6
        Text {
            id: label
            horizontalAlignment: Text.AlignLeft
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            color: pebble.tone.ink
            opacity: pebble.chosen ? 1 : 0.75
            font.pixelSize: 13
            font.weight: pebble.chosen ? Font.DemiBold : Font.Normal
        }
        Text {
            horizontalAlignment: Text.AlignLeft
            Layout.alignment: Qt.AlignVCenter
            visible: pebble.count >= 0
            text: pebble.count.toLocaleString(Qt.locale(), "f", 0)
            color: pebble.tone.dim
            font.pixelSize: 12
            font.features: ({ "tnum": 1 })
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: pebble.clicked()
    }
    Accessible.role: Accessible.RadioButton
    Accessible.name: label.text
    Accessible.checked: chosen
    Accessible.onPressAction: pebble.clicked()
}
