/*
 * Now Playing: what's playing, with its cover, on Monet's glass. Back, play
 * or pause (on the sun) and next, for whichever player is going, and how far
 * along it is (click or drag the line to go there); the cover brings the
 * player forward. With nothing playing, it offers the music apps there are,
 * the PC's own first, or the Store to find one.
 */
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Shapes
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.plasma.private.mpris as Mpris
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property string helper: "@LIBEXECDIR@/monet-quick"
    // What there is to play with: { apps: [{ id, name, icon }], store: "" }.
    property var music: ({ apps: [], store: "" })

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "applications-multimedia"
    preferredRepresentation: fullRepresentation

    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source);
            if (source === root.helper + " music") {
                try {
                    root.music = JSON.parse(data["stdout"]);
                } catch (e) {
                }
            }
        }
    }

    function lookForMusic() {
        runner.connectSource(helper + " music");
    }

    // An app's entry name goes to the helper as the hex of its UTF-8, so the shell never reads it.
    function launch(id) {
        const bytes = unescape(encodeURIComponent(id));
        let out = "";
        for (let i = 0; i < bytes.length; i++) {
            out += bytes.charCodeAt(i).toString(16).padStart(2, "0");
        }
        runner.connectSource(helper + " launch " + out);
    }

    // m:ss, or h:mm:ss, from microseconds.
    function clock(us) {
        const s = Math.max(0, Math.floor(us / 1000000));
        const h = Math.floor(s / 3600), m = Math.floor(s / 60) % 60, rest = String(s % 60).padStart(2, "0");
        return h > 0 ? h + ":" + String(m).padStart(2, "0") + ":" + rest : m + ":" + rest;
    }

    fullRepresentation: Item {
        Layout.minimumWidth: Kirigami.Units.gridUnit * 15
        Layout.minimumHeight: Kirigami.Units.gridUnit * 7
        Layout.preferredWidth: Kirigami.Units.gridUnit * 19
        Layout.preferredHeight: Kirigami.Units.gridUnit * 8

        Glass {
            id: card
            anchors.fill: parent

            readonly property color lily: smoke ? "#4DB4A0" : "#357F72"

            // The player that's going (the same one KDE's media controls show).
            Repeater {
                id: players
                model: Mpris.MultiplexerModel { }

                RowLayout {
                    id: row
                    required property var model
                    readonly property var player: model.container || null
                    readonly property bool playing: model.playbackStatus === Mpris.PlaybackStatus.Playing
                    readonly property real length: player ? player.length : (model.length || 0)
                    readonly property bool canSeek: player ? player.canSeek : !!model.canSeek
                    // Where it is, in microseconds: from the player, moved on here between its reports.
                    property real at: player ? player.position : (model.position || 0)
                    anchors.fill: parent
                    anchors.margins: Kirigami.Units.gridUnit * 0.8
                    spacing: Kirigami.Units.gridUnit * 0.8

                    Connections {
                        target: row.player
                        function onPositionChanged() {
                            row.at = row.player.position;
                        }
                        function onLengthChanged() {
                            row.player.updatePosition();
                        }
                    }
                    Timer {
                        interval: 1000
                        repeat: true
                        running: row.playing && row.length > 0 && !seekArea.pressed
                        onTriggered: {
                            if (row.at + 1000000 >= row.length) {
                                if (row.player) {
                                    row.player.updatePosition();
                                }
                            } else {
                                row.at += 1000000;
                            }
                        }
                    }
                    Component.onCompleted: if (player) player.updatePosition()

                    // The cover, or a painted stage when there's none. It brings the player forward.
                    Item {
                        Layout.fillHeight: true
                        Layout.preferredWidth: height
                        Accessible.role: Accessible.Button
                        Accessible.name: i18nc("%1 is a music app", "Show %1", row.model.identity || "")
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
                        MouseArea {
                            anchors.fill: parent
                            enabled: !!row.model.canRaise && row.player !== null
                            cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                            onClicked: row.player.Raise()
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

                        // How far along: a line to click or drag, with the time gone and the time left.
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.topMargin: 4
                            visible: row.length > 0
                            spacing: 6

                            Text {
                                text: root.clock(row.at)
                                color: card.dim
                                font.family: "Inter"
                                font.pixelSize: 10
                                font.features: { "tnum": 1 }
                            }
                            Item {
                                Layout.fillWidth: true
                                implicitHeight: 12
                                Accessible.role: Accessible.ProgressBar
                                Accessible.name: i18n("Position")

                                Rectangle {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width
                                    height: 3
                                    radius: 1.5
                                    color: card.ink
                                    opacity: 0.14
                                }
                                Rectangle {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: parent.width * Math.min(1, row.at / Math.max(1, row.length))
                                    height: 3
                                    radius: 1.5
                                    color: card.ink
                                    opacity: 0.7
                                }
                                // The knob, while it can be moved.
                                Rectangle {
                                    visible: row.canSeek && (seekArea.containsMouse || seekArea.pressed)
                                    x: parent.width * Math.min(1, row.at / Math.max(1, row.length)) - width / 2
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 10
                                    height: 10
                                    radius: 5
                                    color: "#E2471F"
                                }
                                MouseArea {
                                    id: seekArea
                                    anchors.fill: parent
                                    anchors.margins: -4
                                    enabled: row.canSeek && row.player !== null
                                    hoverEnabled: true
                                    cursorShape: enabled ? Qt.PointingHandCursor : Qt.ArrowCursor
                                    function placed(x) {
                                        return Math.max(0, Math.min(1, (x - 4) / Math.max(1, width - 8))) * row.length;
                                    }
                                    onPressed: mouse => row.at = placed(mouse.x)
                                    onPositionChanged: mouse => {
                                        if (pressed) {
                                            row.at = placed(mouse.x);
                                        }
                                    }
                                    onReleased: mouse => row.player.position = placed(mouse.x)
                                }
                            }
                            Text {
                                text: "-" + root.clock(row.length - row.at)
                                color: card.dim
                                font.family: "Inter"
                                font.pixelSize: 10
                                font.features: { "tnum": 1 }
                            }
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

            // Nothing playing anywhere: the empty stage, and something to start.
            RowLayout {
                anchors.fill: parent
                anchors.margins: Kirigami.Units.gridUnit * 0.8
                spacing: Kirigami.Units.gridUnit * 0.8
                visible: players.count === 0

                onVisibleChanged: if (visible) root.lookForMusic()
                Component.onCompleted: if (visible) root.lookForMusic()

                Rectangle {
                    Layout.fillHeight: true
                    Layout.preferredWidth: height
                    radius: 14
                    opacity: 0.85
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

                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
                    spacing: 4

                    Text {
                        Layout.fillWidth: true
                        text: i18n("Nothing playing")
                        color: card.ink
                        elide: Text.ElideRight
                        font.family: "Fraunces 72pt SuperSoft"
                        font.italic: true
                        font.pixelSize: 18
                    }
                    Text {
                        Layout.fillWidth: true
                        text: root.music.apps.length > 0 ? i18n("Play something with")
                            : root.music.store !== "" ? i18n("No music app yet.") : i18n("Music and videos show here while they play.")
                        color: card.dim
                        elide: Text.ElideRight
                        font.family: "Inter"
                        font.pixelSize: 12
                    }
                    Flow {
                        Layout.fillWidth: true
                        Layout.topMargin: 4
                        spacing: 6

                        Repeater {
                            model: root.music.apps.length > 0 ? root.music.apps.slice(0, 3)
                                : root.music.store !== "" ? [{ id: root.music.store, name: i18n("Find a music app"), icon: "" }] : []
                            QQC2.AbstractButton {
                                id: chip
                                required property var modelData
                                implicitWidth: chipRow.implicitWidth + 20
                                implicitHeight: 30
                                Accessible.name: modelData.name
                                onClicked: root.launch(modelData.id)
                                scale: down ? 0.96 : 1
                                Behavior on scale { NumberAnimation { duration: 120 } }
                                background: Rectangle {
                                    radius: height / 2
                                    color: card.ink
                                    opacity: chip.hovered ? 0.13 : 0.07
                                    Behavior on opacity { NumberAnimation { duration: 120 } }
                                }
                                contentItem: Item {
                                    RowLayout {
                                        id: chipRow
                                        anchors.centerIn: parent
                                        spacing: 6
                                        Kirigami.Icon {
                                            visible: chip.modelData.icon !== ""
                                            source: chip.modelData.icon
                                            Layout.preferredWidth: 18
                                            Layout.preferredHeight: 18
                                        }
                                        Text {
                                            text: chip.modelData.name
                                            color: card.ink
                                            font.family: "Inter"
                                            font.pixelSize: 12
                                            font.weight: Font.Medium
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
