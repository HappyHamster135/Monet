/*
 * A small work on the wall: an app's picture on a square of paper and its name under it, for
 * the rest of a room on the front page (the first ones are framed). Under the pointer it lifts
 * and says what the app is for; a lily dot when you have it.
 */
import QtQuick
import QtQuick.Layouts

Rectangle {
    id: tile
    property var app: ({})
    property var tone
    signal chosen()

    readonly property bool lit: mouse.containsMouse || activeFocus
    readonly property bool yours: app.state === "installed" || app.state === "built-in"
    implicitWidth: 132
    implicitHeight: 140
    radius: 16
    color: lit ? tone.wash2 : tone.wash
    border.width: activeFocus ? 2 : 1
    border.color: activeFocus ? tone.lily : tone.line
    scale: mouse.pressed ? 0.97 : 1
    Behavior on color { ColorAnimation { duration: Math.round(140 * tile.tone.speed) } }
    Behavior on scale { NumberAnimation { duration: Math.round(160 * tile.tone.speed); easing.type: Easing.OutCubic } }
    activeFocusOnTab: true
    Keys.onReturnPressed: tile.chosen()
    Keys.onEnterPressed: tile.chosen()
    Keys.onSpacePressed: tile.chosen()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8
        Image {
            Layout.alignment: Qt.AlignHCenter
            Layout.topMargin: tile.lit ? 2 : 6
            Layout.preferredWidth: 60
            Layout.preferredHeight: 60
            source: tile.app.icon || ""
            sourceSize: Qt.size(120, 120)
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            Behavior on Layout.topMargin { NumberAnimation { duration: Math.round(180 * tile.tone.speed); easing.type: Easing.OutCubic } }
        }
        Text {
            Layout.fillWidth: true
            Layout.fillHeight: true
            horizontalAlignment: Text.AlignHCenter
            text: tile.lit && !tile.yours && (tile.app.summary || "") !== "" ? tile.app.summary : (tile.app.name || "")
            textFormat: Text.PlainText
            color: tile.lit && !tile.yours ? tile.tone.dim : tile.tone.ink
            font.pixelSize: tile.lit && !tile.yours ? 12 : 13
            font.weight: tile.lit && !tile.yours ? Font.Normal : Font.DemiBold
            wrapMode: Text.Wrap
            maximumLineCount: tile.lit && !tile.yours ? 3 : 2
            elide: Text.ElideRight
        }
    }
    // Yours already: a dot of lily in the corner.
    Rectangle {
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 10
        width: 8
        height: 8
        radius: 4
        visible: tile.yours
        color: tile.tone.lily
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: tile.chosen()
    }
    Accessible.role: Accessible.Button
    Accessible.name: (app.name || "") + ", " + (app.summary || "")
    Accessible.onPressAction: tile.chosen()
}
