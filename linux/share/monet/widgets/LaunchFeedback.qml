/* Failed launches remain reviewable when the menu is reopened. */
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PC

ColumnLayout {
    id: feedback
    required property Item controller
    required property Item source
    signal dismissed()
    readonly property var problems: Object.values(controller.states).filter(item => ["failed", "unconfirmed"].includes(item.state))
        .sort((a,b) => a.sequence - b.sequence).slice(-1)
    visible: problems.length > 0
    spacing: 6
    Repeater {
        model: feedback.problems
        Rectangle {
            required property var modelData
            objectName: "launchFeedback-" + modelData.id
            Layout.fillWidth: true
            implicitHeight: body.implicitHeight + 16
            radius: 12
            color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.06)
            ColumnLayout {
                id: body
                anchors.fill: parent; anchors.margins: 8
                spacing: 4
                RowLayout {
                    Layout.fillWidth: true
                    PC.Label {
                        text: modelData.name
                        textFormat: Text.PlainText
                        font.bold: true
                        Layout.fillWidth: true
                        elide: Text.ElideRight
                    }
                    PC.ToolButton {
                        icon.name: "window-close"
                        Accessible.name: i18nd("monet", "Dismiss launch message")
                        onClicked: { feedback.controller.dismiss(modelData.id); feedback.dismissed(); }
                    }
                    PC.Button { text: i18nd("monet", "Retry"); onClicked: feedback.controller.retry(modelData.id, feedback.source) }
                }
                PC.Label {
                    Layout.fillWidth: true
                    text: modelData.error
                    textFormat: Text.PlainText
                    wrapMode: Text.WordWrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                    Accessible.description: modelData.error
                }
                RowLayout {
                    visible: modelData.state === "unconfirmed" && feedback.controller.canOpenNewWindow(modelData.id)
                    PC.Button {
                        text: i18nd("monet", "Open another window")
                        onClicked: feedback.controller.open(modelData.id, feedback.source, true)
                    }
                }
            }
        }
    }
}
