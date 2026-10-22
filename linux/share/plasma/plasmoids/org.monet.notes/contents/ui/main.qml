/*
 * Note: a sheet of paper on the desktop, pinned with a dab of lily. What's
 * written stays, the moment you stop typing.
 */
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "accessories-text-editor"
    preferredRepresentation: fullRepresentation

    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 10
        Layout.minimumHeight: Kirigami.Units.gridUnit * 8
        Layout.preferredWidth: Kirigami.Units.gridUnit * 12
        Layout.preferredHeight: Kirigami.Units.gridUnit * 12

        Glass {
            id: card
            anchors.fill: parent
            radius: 18
            wash: 0.82  // paper you can write on, with the painting faint behind

            // The pin.
            Rectangle {
                x: Kirigami.Units.gridUnit * 0.8
                y: Kirigami.Units.gridUnit * 0.7
                width: 12
                height: 12
                radius: 6
                gradient: Gradient {
                    GradientStop { position: 0; color: "#4DB4A0" }
                    GradientStop { position: 1; color: "#245A50" }
                }
            }

            QQC2.ScrollView {
                anchors.fill: parent
                anchors.margins: Kirigami.Units.gridUnit * 0.8
                anchors.topMargin: Kirigami.Units.gridUnit * 1.6

                QQC2.TextArea {
                    id: page
                    text: Plasmoid.configuration.text
                    placeholderText: i18n("Write something…")
                    placeholderTextColor: card.dim
                    color: card.ink
                    wrapMode: TextEdit.Wrap
                    font.family: "Inter"
                    font.pixelSize: 14
                    selectionColor: "#9FD3C4"
                    selectedTextColor: "#1C1B19"
                    background: null
                    onTextChanged: keep.restart()
                }
            }

            Timer {
                id: keep
                interval: 600
                onTriggered: Plasmoid.configuration.text = page.text
            }
        }
    }
}
