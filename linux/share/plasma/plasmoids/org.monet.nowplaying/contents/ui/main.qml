/*
 * Now Playing: what's playing, with its cover, on Monet's glass. Back, play
 * or pause (on the sun) and next, for whichever player is going.
 */
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Shapes
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.private.mpris as Mpris
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "applications-multimedia"
    preferredRepresentation: fullRepresentation

    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 15
        Layout.minimumHeight: Kirigami.Units.gridUnit * 7
        Layout.preferredWidth: Kirigami.Units.gridUnit * 19
        Layout.preferredHeight: Kirigami.Units.gridUnit * 8

        Glass {
            id: card
            anchors.fill: parent

            // The player that's going (the same one KDE's media controls show).
            Repeater {
                id: players
                model: Mpris.MultiplexerModel { }

                RowLayout {
                    id: row
                    required property var model
                    readonly property bool playing: model.playbackStatus === Mpris.PlaybackStatus.Playing
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.gridUnit * 0.8
                    spacing: Kirigami.Units.gridUnit * 0.8

                    // The cover, or a painted stage when there's none.
                    Item {
                        Layout.fillHeight: true
                        Layout.preferredWidth: height
                        Rectangle {
                            anchors.fill: parent
                            radius: 14
                            visible: cover.status !== Image.Ready
                            gradient: Gradient {
                                GradientStop { position: 0; color: "#8A6FA8" }
                                GradientStop { position: 1; color: "#F09A6A" }
                            }
                            Text {
                                anchors.centerIn: parent
                                text: "♪"
                                color: "#FBF7EE"
                                font.pixelSize: 34
                            }
                        }
                        Image {
                            id: cover
                            anchors.fill: parent
                            visible: false
                            asynchronous: true
                            fillMode: Image.PreserveAspectCrop
                            source: row.model.artUrl || ""
                            sourceSize: Qt.size(width * 2, height * 2)
                        }
                        Item {
                            id: coverMask
                            anchors.fill: parent
                            visible: false
                            layer.enabled: true
                            Rectangle { anchors.fill: parent; radius: 14 }
                        }
                        MultiEffect {
                            anchors.fill: parent
                            source: cover
                            visible: cover.status === Image.Ready
                            maskEnabled: true
                            maskSource: coverMask
                            maskThresholdMin: 0.5
                            maskSpreadAtMin: 1
                        }
                    }

                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        spacing: 2

                        Item { Layout.fillHeight: true }
                        Text {
                            Layout.fillWidth: true
                            text: row.model.track || i18n("Nothing playing")
                            color: card.ink
                            elide: Text.ElideRight
                            font.family: "Fraunces 72pt SuperSoft"
                            font.pixelSize: 18
                        }
                        Text {
                            Layout.fillWidth: true
                            text: row.model.artist || row.model.identity || ""
                            color: card.dim
                            elide: Text.ElideRight
                            font.family: "Inter"
                            font.pixelSize: 12
                        }
                        Item { Layout.fillHeight: true }

                        RowLayout {
                            spacing: Kirigami.Units.gridUnit * 0.6
                            enabled: row.model.canControl

                            QQC2.AbstractButton {
                                id: back
                                implicitWidth: 28
                                implicitHeight: 28
                                enabled: row.model.canGoPrevious
                                opacity: enabled ? 1 : 0.4
                                Accessible.name: i18n("Previous track")
                                onClicked: row.model.container.Previous()
                                contentItem: Shape {
                                    preferredRendererType: Shape.CurveRenderer
                                    ShapePath {
                                        fillColor: card.ink
                                        strokeColor: "transparent"
                                        PathPolyline { path: [Qt.point(22, 7), Qt.point(11, 14), Qt.point(22, 21), Qt.point(22, 7)] }
                                    }
                                    ShapePath {
                                        fillColor: card.ink
                                        strokeColor: "transparent"
                                        PathPolyline { path: [Qt.point(7, 7), Qt.point(10, 7), Qt.point(10, 21), Qt.point(7, 21), Qt.point(7, 7)] }
                                    }
                                }
                            }

                            // Play or pause, on the sun.
                            QQC2.AbstractButton {
                                id: play
                                implicitWidth: 38
                                implicitHeight: 38
                                Accessible.name: row.playing ? i18n("Pause") : i18n("Play")
                                onClicked: row.model.container.PlayPause()
                                scale: down ? 0.92 : hovered ? 1.06 : 1
                                Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
                                background: Rectangle {
                                    radius: height / 2
                                    gradient: Gradient {
                                        GradientStop { position: 0; color: "#FF7A45" }
                                        GradientStop { position: 1; color: "#E2471F" }
                                    }
                                }
                                contentItem: Shape {
                                    preferredRendererType: Shape.CurveRenderer
                                    ShapePath {
                                        fillColor: "#FBF7EE"
                                        strokeColor: "transparent"
                                        PathPolyline {
                                            path: row.playing
                                                ? [Qt.point(13, 11), Qt.point(17, 11), Qt.point(17, 27), Qt.point(13, 27), Qt.point(13, 11)]
                                                : [Qt.point(15, 10), Qt.point(28, 19), Qt.point(15, 28), Qt.point(15, 10)]
                                        }
                                    }
                                    ShapePath {
                                        fillColor: row.playing ? "#FBF7EE" : "transparent"
                                        strokeColor: "transparent"
                                        PathPolyline { path: [Qt.point(21, 11), Qt.point(25, 11), Qt.point(25, 27), Qt.point(21, 27), Qt.point(21, 11)] }
                                    }
                                }
                            }

                            QQC2.AbstractButton {
                                id: next
                                implicitWidth: 28
                                implicitHeight: 28
                                enabled: row.model.canGoNext
                                opacity: enabled ? 1 : 0.4
                                Accessible.name: i18n("Next track")
                                onClicked: row.model.container.Next()
                                contentItem: Shape {
                                    preferredRendererType: Shape.CurveRenderer
                                    ShapePath {
                                        fillColor: card.ink
                                        strokeColor: "transparent"
                                        PathPolyline { path: [Qt.point(6, 7), Qt.point(17, 14), Qt.point(6, 21), Qt.point(6, 7)] }
                                    }
                                    ShapePath {
                                        fillColor: card.ink
                                        strokeColor: "transparent"
                                        PathPolyline { path: [Qt.point(18, 7), Qt.point(21, 7), Qt.point(21, 21), Qt.point(18, 21), Qt.point(18, 7)] }
                                    }
                                }
                            }
                        }
                    }
                }
            }

            // Nothing playing anywhere.
            ColumnLayout {
                anchors.centerIn: parent
                visible: players.count === 0
                spacing: 2
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: i18n("Nothing playing")
                    color: card.ink
                    font.family: "Fraunces 72pt SuperSoft"
                    font.italic: true
                    font.pixelSize: 18
                }
                Text {
                    Layout.alignment: Qt.AlignHCenter
                    text: i18n("Music and videos show here while they play.")
                    color: card.dim
                    font.family: "Inter"
                    font.pixelSize: 12
                }
            }
        }
    }
}
