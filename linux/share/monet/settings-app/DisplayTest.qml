import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Window

Window {
    id: test
    objectName: "displayTestWindow"
    title: i18n("Test display colors")
    modality: Qt.WindowModal
    color: "#242424"
    onActiveChanged: if (active) closeButton.forceActiveFocus()

    QQC2.ScrollView {
        id: scroll
        anchors.fill: parent
        anchors.margins: Math.min(48, Math.round(test.width / 20))
        contentWidth: availableWidth
        clip: true
        Keys.onEscapePressed: test.close()

        ColumnLayout {
            width: Math.max(1, Math.min(scroll.availableWidth, 1200))
            x: Math.max(0, (scroll.availableWidth - width) / 2)
            spacing: 22

            RowLayout {
                Layout.fillWidth: true
                spacing: 12
                Text {
                    Layout.fillWidth: true
                    text: test.title
                    font.pixelSize: 26
                    font.weight: Font.DemiBold
                    color: "white"
                    wrapMode: Text.Wrap
                }
                QQC2.Button {
                    id: closeButton
                    objectName: "closeDisplayTest"
                    text: i18n("Close test")
                    onClicked: test.close()
                    Keys.onEscapePressed: test.close()
                    contentItem: Text {
                        text: closeButton.text
                        color: "white"
                        font.pixelSize: 16
                        font.weight: Font.DemiBold
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }
                    background: Rectangle {
                        implicitHeight: 40
                        radius: 10
                        color: closeButton.down ? "#444444" : closeButton.hovered ? "#3a3a3a" : "#303030"
                        border.width: closeButton.activeFocus ? 2 : 1
                        border.color: closeButton.activeFocus ? "#86dcc8" : "#5c5c5c"
                    }
                }
            }
            Text {
                Layout.fillWidth: true
                text: i18n("Look for steps that blend together near black or white. Turn off Night Light before checking the grays for a tint.")
                font.pixelSize: 16
                color: "#dedede"
                wrapMode: Text.Wrap
            }
            Repeater {
                model: [
                    { label: i18n("Shadow detail"), levels: [0, 4, 8, 12, 16, 24, 32] },
                    { label: i18n("Highlight detail"), levels: [223, 231, 239, 243, 247, 251, 255] },
                    { label: i18n("Neutral grays"), levels: [48, 80, 112, 144, 176, 208] }
                ]
                ColumnLayout {
                    id: strip
                    required property var modelData
                    Layout.fillWidth: true
                    spacing: 6
                    Accessible.role: Accessible.Grouping
                    Accessible.name: modelData.label

                    Text {
                        Layout.fillWidth: true
                        text: strip.modelData.label
                        color: "white"
                        font.pixelSize: 18
                        font.weight: Font.DemiBold
                        wrapMode: Text.Wrap
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Repeater {
                            model: strip.modelData.levels
                            ColumnLayout {
                                id: patch
                                required property int modelData
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                Layout.minimumWidth: 0
                                spacing: 4
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: Math.max(60, Math.min(170, Math.round(test.height / 6)))
                                    color: Qt.rgba(patch.modelData / 255, patch.modelData / 255, patch.modelData / 255, 1)
                                }
                                Text {
                                    Layout.fillWidth: true
                                    text: patch.modelData
                                    color: "#dedede"
                                    font.pixelSize: 14
                                    horizontalAlignment: Text.AlignHCenter
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
