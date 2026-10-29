/*
 * One app in a list of the Store: its picture, name and what it's for, and whether you have
 * it (or `note`, when you don't: when it was updated, say). A click (or Enter) opens its page.
 */
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../games"

Rectangle {
    id: card
    property var app: ({})
    property var tone
    // "windows": an app in your Windows, which opens there.
    property string kind: "flathub"
    property string note: ""
    signal chosen()

    implicitHeight: 92
    radius: 14
    color: mouse.containsMouse ? tone.wash2 : tone.wash
    border.width: activeFocus ? 2 : 1
    border.color: activeFocus ? tone.lily : tone.line
    activeFocusOnTab: true
    Keys.onReturnPressed: card.chosen()
    Keys.onEnterPressed: card.chosen()
    Keys.onSpacePressed: card.chosen()
    Behavior on color { ColorAnimation { duration: Math.round(140 * card.tone.speed) } }

    RowLayout {
        anchors.fill: parent
        anchors.leftMargin: 16
        anchors.rightMargin: 16
        spacing: 14
        Item {
            Layout.preferredWidth: 56
            Layout.preferredHeight: 56
            Image {
                anchors.fill: parent
                visible: card.kind !== "windows" && card.app.icon !== ""
                source: card.kind !== "windows" ? (card.app.icon || "") : ""
                sourceSize: Qt.size(112, 112)
                fillMode: Image.PreserveAspectFit
                smooth: true
                asynchronous: true
            }
            Kirigami.Icon {
                anchors.fill: parent
                visible: card.kind === "windows" || !card.app.icon
                source: card.kind === "windows" ? card.app.icon : "application-x-executable"
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 2
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: card.app.name || ""
                    textFormat: Text.PlainText
                    color: card.tone.ink
                    font.pixelSize: 15
                    font.weight: Font.DemiBold
                    elide: Text.ElideRight
                }
                // Flathub checked who made it.
                Glyph {
                    Layout.preferredWidth: 14
                    Layout.preferredHeight: 14
                    visible: card.app.verified === true
                    path: "M12 3l2.4 1.8 3-.2.9 2.9 2.4 1.8-1 2.8 1 2.8-2.4 1.8-.9 2.9-3-.2L12 21l-2.4-1.8-3 .2-.9-2.9-2.4-1.8 1-2.8-1-2.8 2.4-1.8.9-2.9 3 .2zM8.5 12.2l2.3 2.3 4.7-4.7"
                    color: card.tone.lily
                    stroke: 1.8
                }
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: card.kind === "windows" ? i18n("Opens in Windows") : (card.app.summary || "")
                textFormat: Text.PlainText
                color: card.tone.dim
                font.pixelSize: 13
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                visible: text !== ""
                text: card.app.state === "installed" ? i18n("Installed")
                    : card.app.state === "built-in" ? i18n("Part of Monet")
                    : card.app.state === "working" ? i18n("Working on it…") : card.note
                color: card.app.state === "get" ? card.tone.dim : card.tone.lily
                font.pixelSize: 12
                font.weight: Font.DemiBold
            }
        }
    }
    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: card.chosen()
    }
    Accessible.role: Accessible.Button
    Accessible.name: (app.name || "") + ", " + (app.summary || "")
    Accessible.onPressAction: card.chosen()
}
