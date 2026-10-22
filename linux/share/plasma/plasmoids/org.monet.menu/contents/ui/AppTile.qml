/*
 * A pinned app in the menu: its painting over its name, with an ink wash
 * under the pointer and lily on the one the keys are on.
 */
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: tile

    property var icon
    property string name
    property bool current: false
    property real speed: 1

    signal activated()
    signal menuRequested()

    Accessible.role: Accessible.Button
    Accessible.name: name
    Accessible.onPressAction: activated()

    Rectangle {
        anchors.fill: parent
        anchors.margins: 3
        radius: 14
        color: tile.current ? Kirigami.Theme.highlightColor : Kirigami.Theme.textColor
        opacity: tile.current ? 0.16 : hover.hovered ? 0.07 : 0
        Behavior on opacity { NumberAnimation { duration: Math.round(140 * tile.speed) } }
    }

    ColumnLayout {
        anchors.centerIn: parent
        width: parent.width - 12
        spacing: 6
        scale: tap.pressed ? 0.94 : 1
        Behavior on scale { NumberAnimation { duration: Math.round(160 * tile.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }

        Kirigami.Icon {
            Layout.alignment: Qt.AlignHCenter
            implicitWidth: 44
            implicitHeight: 44
            source: tile.icon
        }
        Text {
            Layout.fillWidth: true
            horizontalAlignment: Text.AlignHCenter
            text: tile.name
            color: Kirigami.Theme.textColor
            elide: Text.ElideRight
            wrapMode: Text.Wrap
            maximumLineCount: 2
            textFormat: Text.PlainText
            font.family: "Inter"
            font.pixelSize: 12
        }
    }

    HoverHandler {
        id: hover
        cursorShape: Qt.PointingHandCursor
    }
    TapHandler {
        id: tap
        onTapped: tile.activated()
        onLongPressed: tile.menuRequested()
    }
    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: tile.menuRequested()
    }
}
