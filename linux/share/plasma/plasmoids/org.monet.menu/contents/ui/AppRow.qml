/*
 * An app, file or setting in a list: its picture, its name and, for search
 * results, what it is. An ink wash under the pointer, lily on the one the
 * keys are on.
 */
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: row

    property var icon
    property string name
    property string detail
    property bool current: false
    property real speed: 1

    signal activated()
    signal menuRequested()

    implicitHeight: detail !== "" ? 48 : 40

    Accessible.role: Accessible.Button
    Accessible.name: name
    Accessible.description: detail
    Accessible.onPressAction: activated()

    Rectangle {
        anchors.fill: parent
        anchors.topMargin: 1
        anchors.bottomMargin: 1
        radius: 12
        color: row.current ? Kirigami.Theme.highlightColor : Kirigami.Theme.textColor
        opacity: row.current ? 0.16 : hover.hovered ? 0.07 : 0
        Behavior on opacity { NumberAnimation { duration: Math.round(140 * row.speed) } }
    }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 10
        anchors.rightMargin: 10
        spacing: 12

        Kirigami.Icon {
            implicitWidth: 28
            implicitHeight: 28
            source: row.icon
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 1
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: row.name
                color: Kirigami.Theme.textColor
                elide: Text.ElideRight
                textFormat: Text.PlainText
                font.family: "Inter"
                font.pixelSize: 14
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                visible: row.detail !== ""
                text: row.detail
                color: Kirigami.Theme.textColor
                opacity: 0.6
                elide: Text.ElideRight
                textFormat: Text.PlainText
                font.family: "Inter"
                font.pixelSize: 12
            }
        }
    }

    HoverHandler {
        id: hover
        cursorShape: Qt.PointingHandCursor
    }
    TapHandler {
        onTapped: row.activated()
        onLongPressed: row.menuRequested()
    }
    TapHandler {
        acceptedButtons: Qt.RightButton
        onTapped: row.menuRequested()
    }
}
