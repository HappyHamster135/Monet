/*
 * Photo frame: your pictures in a gilt frame, as in a museum, a new one
 * every ten minutes (a click shows the next). With none in Pictures yet,
 * the painting hangs there instead.
 */
import QtCore
import QtQuick
import QtQuick.Layouts
import Qt.labs.folderlistmodel
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property string painting: "file://@DATADIR@/wallpapers/Monet/contents/hours/dusk.jpg"
    property int index: 0

    FolderListModel {
        id: pictures
        folder: StandardPaths.writableLocation(StandardPaths.PicturesLocation)
        nameFilters: ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.JPG", "*.JPEG", "*.PNG"]
        showDirs: false
        sortField: FolderListModel.Time
    }

    function nextPicture() {
        if (pictures.count > 1) {
            index = (index + 1 + Math.floor(Math.random() * (pictures.count - 1))) % pictures.count;
        }
    }

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "org.kde.gwenview"
    preferredRepresentation: fullRepresentation

    Timer {
        interval: 10 * 60 * 1000
        running: true
        repeat: true
        onTriggered: root.nextPicture()
    }

    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 9
        Layout.minimumHeight: Kirigami.Units.gridUnit * 7
        Layout.preferredWidth: Kirigami.Units.gridUnit * 16
        Layout.preferredHeight: Kirigami.Units.gridUnit * 12

        // The gilt frame, with light along its top.
        Rectangle {
            id: gilt
            anchors.fill: parent
            radius: 10
            gradient: Gradient {
                GradientStop { position: 0; color: "#F2D27E" }
                GradientStop { position: 0.45; color: "#C9973E" }
                GradientStop { position: 1; color: "#8A5A24" }
            }
            border.width: 1
            border.color: "#6A4218"

            // The mat, then the picture.
            Rectangle {
                id: mat
                anchors.fill: parent
                anchors.margins: Kirigami.Units.gridUnit * 0.7
                color: "#F6F1E4"
                border.width: 1
                border.color: "#5A3A14"

                Image {
                    id: picture
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.gridUnit * 0.7
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    sourceSize: Qt.size(width * 2, height * 2)
                    source: pictures.count > 0 ? pictures.get(Math.min(root.index, pictures.count - 1), "fileUrl") : root.painting
                    opacity: status === Image.Ready ? 1 : 0
                    Behavior on opacity { NumberAnimation { duration: 600 } }
                }
            }
        }

        MouseArea {
            anchors.fill: parent
            onClicked: root.nextPicture()
        }
    }
}
