/*
 * Photo frame: your pictures in a gilt frame, as in a museum, a new one
 * every ten minutes, fading from one to the next. Pointing at it shows
 * ‹ › for the one before or after; a click opens the picture in Photos.
 * With none in Pictures yet, the painting hangs there instead.
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
    LayoutGuard {}

    readonly property string painting: "file://@DATADIR@/wallpapers/Monet/contents/hours/dusk.jpg"
    property int index: 0
    readonly property url current: pictures.count > 0 ? pictures.get(Math.min(index, pictures.count - 1), "fileUrl") : painting

    FolderListModel {
        id: pictures
        folder: StandardPaths.writableLocation(StandardPaths.PicturesLocation)
        nameFilters: ["*.jpg", "*.jpeg", "*.png", "*.webp", "*.JPG", "*.JPEG", "*.PNG"]
        showDirs: false
        sortField: FolderListModel.Time
    }

    // Every ten minutes, one it didn't just show.
    function nextPicture() {
        if (pictures.count > 1) {
            index = (index + 1 + Math.floor(Math.random() * (pictures.count - 1))) % pictures.count;
        }
    }

    function step(by) {
        if (pictures.count > 1) {
            index = (index + by + pictures.count) % pictures.count;
            changer.restart();
        }
    }

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "org.kde.gwenview"
    preferredRepresentation: fullRepresentation

    Timer {
        id: changer
        interval: 10 * 60 * 1000
        running: true
        repeat: true
        onTriggered: root.nextPicture()
    }

    fullRepresentation: Item {
        id: face
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

            // The mat, then the picture: two, so one fades into the next.
            Rectangle {
                id: mat
                anchors.fill: parent
                anchors.margins: Kirigami.Units.gridUnit * 0.7
                color: "#F6F1E4"
                border.width: 1
                border.color: "#5A3A14"

                Item {
                    id: hang
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.gridUnit * 0.7
                    clip: true

                    // Which of the two is in front.
                    property bool flip: false
                    readonly property Image front: flip ? second : first
                    readonly property bool arrived: front.status === Image.Ready

                    function hangUp(url) {
                        if (front.source == url) {
                            return;
                        }
                        flip = !flip;
                        front.source = url;
                    }
                    Component.onCompleted: first.source = root.current

                    Connections {
                        target: root
                        function onCurrentChanged() {
                            hang.hangUp(root.current);
                        }
                    }

                    Image {
                        id: first
                        anchors.fill: parent
                        z: hang.flip ? 0 : 1
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        sourceSize: Qt.size(width * 2, height * 2)
                        opacity: hang.front === first ? (hang.arrived ? 1 : 0) : (hang.arrived ? 0 : 1)
                        Behavior on opacity { NumberAnimation { duration: 700; easing.type: Easing.InOutQuad } }
                    }
                    Image {
                        id: second
                        anchors.fill: parent
                        z: hang.flip ? 1 : 0
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        sourceSize: Qt.size(width * 2, height * 2)
                        opacity: hang.front === second ? (hang.arrived ? 1 : 0) : (hang.arrived ? 0 : 1)
                        Behavior on opacity { NumberAnimation { duration: 700; easing.type: Easing.InOutQuad } }
                    }

                    // The one before and the one after, on pebbles of glass while pointed at.
                    Repeater {
                        model: [-1, 1]
                        Rectangle {
                            required property int modelData
                            z: 2
                            anchors.verticalCenter: parent.verticalCenter
                            x: modelData < 0 ? 8 : parent.width - width - 8
                            width: 30
                            height: 30
                            radius: 15
                            color: Qt.rgba(0.11, 0.106, 0.098, stepArea.containsMouse ? 0.62 : 0.42)
                            opacity: pointing.hovered && pictures.count > 1 ? 1 : 0
                            visible: opacity > 0
                            Behavior on opacity { NumberAnimation { duration: 160 } }
                            Accessible.role: Accessible.Button
                            Accessible.name: modelData < 0 ? i18n("The picture before") : i18n("The next picture")
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                anchors.centerIn: parent
                                anchors.horizontalCenterOffset: parent.modelData < 0 ? -1 : 1
                                text: parent.modelData < 0 ? "‹" : "›"
                                color: "#FBF7EE"
                                font.family: "Inter"
                                font.pixelSize: 20
                            }
                            MouseArea {
                                id: stepArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.step(parent.modelData)
                            }
                        }
                    }

                    // With no photos yet, where they come from, while pointed at.
                    Rectangle {
                        z: 2
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.bottom: parent.bottom
                        anchors.bottomMargin: 8
                        width: Math.min(parent.width - 16, hint.implicitWidth + 20)
                        height: hint.implicitHeight + 10
                        radius: Math.min(height / 2, 14)
                        color: Qt.rgba(0.11, 0.106, 0.098, 0.55)
                        opacity: pointing.hovered && pictures.count === 0 ? 1 : 0
                        visible: opacity > 0
                        Behavior on opacity { NumberAnimation { duration: 160 } }
                        Text {
                            id: hint
                            anchors.fill: parent
                            anchors.leftMargin: 10
                            anchors.rightMargin: 10
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            wrapMode: Text.WordWrap
                            text: i18n("Put photos in your Pictures folder and they hang here.")
                            color: "#FBF7EE"
                            font.family: "Inter"
                            font.pixelSize: 12
                        }
                    }
                }
            }
        }

        // Pointing at the frame shows the pebbles (seen even over them); a click opens the picture in Photos.
        HoverHandler {
            id: pointing
            cursorShape: pictures.count > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
        }
        PlasmaCore.ToolTipArea {
            anchors.fill: parent
            z: -1
            active: pictures.count > 0
            mainText: i18n("Open in Photos")
            MouseArea {
                anchors.fill: parent
                onClicked: if (pictures.count > 0) Qt.openUrlExternally(root.current)
            }
        }
    }
}
