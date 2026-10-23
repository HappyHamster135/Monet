/*
 * Recently Played: the games played last, on Monet's glass, each its tall
 * cover from Steam's own picture cache (or a painted card with its name), and
 * when it was played. A click starts it the way Steam's Play does; the sun
 * comes up over a cover under the pointer. As many as the card is wide; Monet's
 * helper looks again every minute, so a game just played comes first.
 */
import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Shapes
import QtQuick.Templates as T
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property string helper: "@LIBEXECDIR@/monet-quick"
    // [{ id, name, last (Unix time), art (file URL or "") }], newest first.
    property var games: []
    property bool looked: false

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "applications-games"
    preferredRepresentation: fullRepresentation

    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source);
            if (source === root.helper + " played") {
                try {
                    root.games = JSON.parse(data["stdout"]);
                } catch (e) {
                }
                root.looked = true;
            }
        }
    }

    Timer {
        interval: 60 * 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: runner.connectSource(root.helper + " played")
    }

    function play(id) {
        runner.connectSource(helper + " play " + id);
    }

    // Steam itself, from its menu entry (the helper takes the entry's name as hex).
    function openSteam() {
        let out = "";
        for (const c of "steam.desktop") {
            out += c.charCodeAt(0).toString(16).padStart(2, "0");
        }
        runner.connectSource(helper + " launch " + out);
    }

    // When, in days as the calendar counts them.
    function when(seconds) {
        const played = new Date(seconds * 1000);
        const today = new Date();
        const days = Math.round((new Date(today.getFullYear(), today.getMonth(), today.getDate())
                                 - new Date(played.getFullYear(), played.getMonth(), played.getDate())) / 86400000);
        if (days <= 0) {
            return i18nc("when a game was played", "Today");
        } else if (days === 1) {
            return i18nc("when a game was played", "Yesterday");
        } else if (days < 7) {
            return i18ncp("when a game was played", "%1 day ago", "%1 days ago", days);
        } else if (days < 35) {
            return i18ncp("when a game was played", "%1 week ago", "%1 weeks ago", Math.floor(days / 7));
        }
        return Qt.locale().toString(played, "MMMM yyyy");
    }

    // A game's cover: its picture, or a painted card with its name; the sun on hover.
    component Cover: T.AbstractButton {
        id: cover
        property var game
        property string played
        property color ink
        property color dim
        property color lily
        readonly property bool lit: hovered || visualFocus
        Accessible.name: i18nc("%1 is a game", "Play %1", game.name)
        Accessible.description: played
        hoverEnabled: true

        contentItem: ColumnLayout {
            spacing: 0

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                Item {
                    id: picture
                    anchors.fill: parent
                    scale: cover.down ? 0.98 : cover.lit ? 1.03 : 1
                    Behavior on scale {
                        NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic }
                    }

                    Rectangle {
                        id: card
                        anchors.fill: parent
                        radius: 10
                        // No picture yet: a painted card, lily into the sun, with the game's name.
                        gradient: Gradient {
                            GradientStop { position: 0; color: Qt.lighter(cover.lily, 1.25) }
                            GradientStop { position: 1; color: "#C9643E" }
                        }
                        Text {
                            anchors.fill: parent
                            anchors.margins: 8
                            visible: art.status !== Image.Ready
                            text: cover.game.name
                            color: "#FFFFFF"
                            wrapMode: Text.WordWrap
                            elide: Text.ElideRight
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.family: "Fraunces 72pt SuperSoft"
                            font.pixelSize: 15
                        }
                    }
                    Image {
                        id: art
                        anchors.fill: parent
                        source: cover.game.art
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        smooth: true
                        visible: false
                    }
                    // The picture, with the card's round corners.
                    MultiEffect {
                        anchors.fill: parent
                        source: art
                        visible: art.status === Image.Ready
                        maskEnabled: true
                        maskSource: corners
                        maskThresholdMin: 0.5
                        maskSpreadAtMin: 1
                    }
                    Rectangle {
                        id: corners
                        anchors.fill: parent
                        radius: 10
                        visible: false
                        layer.enabled: true
                    }

                    // Play, on the sun.
                    Rectangle {
                        anchors.centerIn: parent
                        width: 40
                        height: 40
                        radius: 20
                        color: "#F2552C"
                        opacity: cover.lit ? 1 : 0
                        scale: cover.lit ? 1 : 0.8
                        Behavior on opacity {
                            NumberAnimation { duration: Kirigami.Units.shortDuration }
                        }
                        Behavior on scale {
                            NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic }
                        }
                        Shape {
                            anchors.fill: parent
                            preferredRendererType: Shape.CurveRenderer
                            ShapePath {
                                fillColor: "#FFFFFF"
                                strokeColor: "transparent"
                                PathPolyline { path: [Qt.point(16, 12), Qt.point(29, 20), Qt.point(16, 28), Qt.point(16, 12)] }
                            }
                        }
                    }
                }
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                Layout.topMargin: 6
                text: cover.game.name
                textFormat: Text.PlainText
                color: cover.ink
                elide: Text.ElideRight
                font.family: "Inter"
                font.pixelSize: 11
                font.weight: Font.Medium
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: cover.played
                color: cover.dim
                elide: Text.ElideRight
                font.family: "Inter"
                font.pixelSize: 10
            }
        }
    }

    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 12
        Layout.minimumHeight: Kirigami.Units.gridUnit * 9
        Layout.preferredWidth: Kirigami.Units.gridUnit * 19
        Layout.preferredHeight: Kirigami.Units.gridUnit * 11

        Glass {
            id: glass
            anchors.fill: parent

            readonly property color lily: smoke ? "#4DB4A0" : "#357F72"

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: Kirigami.Units.gridUnit
                anchors.rightMargin: Kirigami.Units.gridUnit
                anchors.topMargin: Math.round(Kirigami.Units.gridUnit * 0.8)
                anchors.bottomMargin: Math.round(Kirigami.Units.gridUnit * 0.8)
                spacing: Kirigami.Units.smallSpacing * 2

                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: i18n("Recently played")
                    color: glass.ink
                    elide: Text.ElideRight
                    font.family: "Inter"
                    font.pixelSize: 13
                    font.weight: Font.DemiBold
                }

                // As many covers as fit side by side, each two thirds as wide as it's tall.
                Item {
                    id: shelf
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: root.games.length > 0
                    readonly property int gap: 12
                    // As many as fit at 70 pixels or more, sharing the width (no wider than
                    // a cover is tall, with its name and when it was played under it).
                    readonly property int fits: Math.max(1, Math.min(root.games.length, Math.floor((width + gap) / (70 + gap))))
                    readonly property real coverWidth: Math.min((width - gap * (fits - 1)) / fits, (height - 34) * 0.85)

                    Row {
                        anchors.horizontalCenter: parent.horizontalCenter
                        spacing: shelf.gap
                        Repeater {
                            model: root.games.slice(0, shelf.fits)
                            Cover {
                                required property var modelData
                                width: shelf.coverWidth
                                height: shelf.height
                                game: modelData
                                played: root.when(modelData.last)
                                ink: glass.ink
                                dim: glass.dim
                                lily: glass.lily
                                onClicked: root.play(modelData.id)
                            }
                        }
                    }
                }

                // Nothing played yet.
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    visible: root.looked && root.games.length === 0
                    spacing: Kirigami.Units.smallSpacing * 2

                    Item { Layout.fillHeight: true }
                    Text {
                        Layout.fillWidth: true
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.WordWrap
                        text: i18n("The games you play in Steam show up here.")
                        color: glass.ink
                        font.family: "Fraunces 72pt SuperSoft"
                        font.italic: true
                        font.pixelSize: 17
                    }
                    T.AbstractButton {
                        id: steam
                        Layout.alignment: Qt.AlignHCenter
                        text: i18n("Open Steam")
                        implicitWidth: steamLabel.implicitWidth + 28
                        implicitHeight: 30
                        onClicked: root.openSteam()
                        background: Rectangle {
                            radius: height / 2
                            color: glass.lily
                            opacity: steam.down ? 0.8 : 1
                        }
                        contentItem: Text {
                            id: steamLabel
                            text: steam.text
                            color: "#FFFFFF"
                            horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter
                            font.family: "Inter"
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                        }
                    }
                    Item { Layout.fillHeight: true }
                }
            }
        }
    }
}
