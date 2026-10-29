/*
 * A game's picture: `source` filling it (its tall cover, or its banner on a wide card). Without
 * one, a glaze from the paintings with brushstrokes of light, its `banner` laid on it when
 * there's that, and its name: every game has a cover worth looking at.
 */
import QtQuick
import QtQuick.Effects

Item {
    id: cover
    property string name
    property string source
    property string banner
    property var glaze: ["#5C88D0", "#1B2546"]
    property string texture
    property real radius: 12
    // How far a download is (0 to 100), drawn along the bottom; -1 when there's none.
    property real progress: -1
    readonly property bool painted: picture.status !== Image.Ready
    readonly property bool tall: height > width

    Item {
        anchors.fill: parent
        layer.enabled: true
        layer.effect: MultiEffect {
            maskEnabled: true
            maskSource: shape
            maskThresholdMin: 0.5
            maskSpreadAtMin: 1.0
        }

        Rectangle {
            anchors.fill: parent
            visible: cover.painted
            gradient: Gradient {
                orientation: cover.tall ? Gradient.Vertical : Gradient.Horizontal
                GradientStop { position: 0; color: cover.glaze[0] }
                GradientStop { position: 1; color: cover.glaze[1] }
            }
            Image {
                anchors.fill: parent
                source: cover.texture
                fillMode: Image.PreserveAspectCrop
                opacity: 0.9
            }
            // The game's banner, hung on the glaze like a small painting.
            Rectangle {
                id: frame
                visible: cover.tall && hung.status === Image.Ready
                x: Math.round(parent.width * 0.09)
                y: Math.round(parent.height * 0.22)
                width: parent.width - 2 * x
                height: Math.round(width * 215 / 460) + 6
                radius: 6
                color: Qt.rgba(1, 1, 1, 0.85)
                Image {
                    id: hung
                    anchors.fill: parent
                    anchors.margins: 3
                    source: cover.painted && cover.tall ? cover.banner : ""
                    fillMode: Image.PreserveAspectCrop
                    asynchronous: true
                    sourceSize.width: 460
                }
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: Math.round(Math.min(parent.width, parent.height) * 0.1)
                text: cover.name
                color: "#FFFFFF"
                wrapMode: Text.Wrap
                maximumLineCount: 3
                elide: Text.ElideRight
                font.family: "Fraunces 72pt SuperSoft"
                font.pixelSize: Math.max(13, Math.round(Math.min(parent.width * 0.12, parent.height * 0.17)))
            }
        }

        Image {
            id: picture
            anchors.fill: parent
            source: cover.source
            fillMode: Image.PreserveAspectCrop
            asynchronous: true
            // Sharp on a big window and a sharp screen, without holding every cover full size.
            sourceSize.width: cover.tall ? 400 : 920
            visible: status === Image.Ready
        }

        // A download on its way: a lily line along the bottom, over a faint track.
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 5
            visible: cover.progress >= 0
            color: Qt.rgba(0, 0, 0, 0.35)
            Rectangle {
                anchors.left: parent.left
                width: parent.width * Math.max(0.02, cover.progress / 100)
                height: parent.height
                color: "#4DB4A0"
            }
        }
    }

    Rectangle {
        id: shape
        anchors.fill: parent
        radius: cover.radius
        visible: false
        layer.enabled: true
    }
}
