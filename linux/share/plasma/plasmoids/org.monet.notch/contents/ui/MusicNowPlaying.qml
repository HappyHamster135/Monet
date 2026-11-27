import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Controls as C
import org.kde.plasma.private.mpris as Mpris
import org.kde.plasma.private.volume 0.1 as Audio

Item {
    id: nowPlaying
    required property var page
    property var output: Audio.PreferredDevice.sink
    readonly property bool narrow: width < 370
    readonly property bool menuOpen: options.visible
    readonly property alias sourceAnchor: sourceButton
    signal sourceRequested()
    implicitHeight: narrow ? 244 : 216

    GridLayout {
        id: layout
        anchors.left: parent.left; anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        columns: 2; columnSpacing: nowPlaying.narrow ? 12 : 16; rowSpacing: 8

        Rectangle {
            id: artwork
            objectName: "notchMusicArtwork"
            Layout.row: 0; Layout.column: 0; Layout.rowSpan: nowPlaying.narrow ? 1 : 3
            Layout.alignment: Qt.AlignTop
            Layout.preferredWidth: nowPlaying.narrow ? 76 : Math.min(148, Math.round(nowPlaying.width * 0.28))
            Layout.preferredHeight: Layout.preferredWidth
            radius: nowPlaying.narrow ? 16 : 22; color: "#202a28"
            IslandGlyph {
                anchors.centerIn: parent; width: parent.width * 0.35; height: width
                source: "music"; color: "#9cbbb2"; visible: cover.status !== Image.Ready
            }
            Rectangle { id: mask; anchors.fill: parent; radius: parent.radius; visible: false; layer.enabled: cover.layer.enabled }
            Image {
                id: cover; anchors.fill: parent; asynchronous: true; fillMode: Image.PreserveAspectCrop
                source: page.player?.artUrl || ""
                sourceSize: Qt.size(width * Screen.devicePixelRatio, height * Screen.devicePixelRatio)
                layer.enabled: status === Image.Ready && GraphicsInfo.api !== GraphicsInfo.Software && GraphicsInfo.api !== GraphicsInfo.Unknown
                layer.effect: MultiEffect { maskEnabled: true; maskSource: mask }
            }
            C.AbstractButton {
                anchors.fill: parent; enabled: !!page.service
                Accessible.name: i18n("Open player")
                onClicked: page.raisePlayer()
                background: Rectangle { radius: artwork.radius; color: "transparent"; border.width: parent.visualFocus ? 2 : 0; border.color: "#9ed3c1" }
            }
            NotchGestureSurface { gestures: page.gestures }
        }

        GridLayout {
            Layout.row: 0; Layout.column: 1; Layout.fillWidth: true; Layout.minimumWidth: 0
            Layout.alignment: Qt.AlignVCenter
            columns: nowPlaying.narrow ? 1 : 2; columnSpacing: 8; rowSpacing: 4
            C.Label {
                objectName: "notchMusicTitle"
                Layout.row: 0; Layout.column: 0
                Layout.fillWidth: true; Layout.minimumWidth: 0
                text: page.player?.track || i18n("Nothing playing"); textFormat: Text.PlainText
                font.pixelSize: nowPlaying.narrow ? 15 : 17; font.weight: Font.DemiBold
                color: "#f7f8f8"; elide: Text.ElideRight
            }
            C.Label {
                Layout.fillWidth: true; Layout.minimumWidth: 0
                Layout.row: 1; Layout.column: 0
                text: page.knownCredit(page.player?.artist) || page.knownCredit(page.player?.identity)
                    || (page.player ? i18n("Now playing") : i18n("Start a song or video."))
                textFormat: Text.PlainText; color: "#949c99"; font.pixelSize: 12; elide: Text.ElideRight
            }
            RowLayout {
                Layout.row: nowPlaying.narrow ? 2 : 0; Layout.column: nowPlaying.narrow ? 0 : 1
                Layout.rowSpan: nowPlaying.narrow ? 1 : 2
                Layout.maximumWidth: nowPlaying.narrow ? 180 : Math.min(90, nowPlaying.width * 0.18)
                Layout.fillWidth: nowPlaying.narrow; spacing: 5
                C.AbstractButton {
                    id: sourceButton
                    objectName: "notchPlaybackSource"
                    Layout.maximumWidth: nowPlaying.narrow ? 150 : Math.max(35, nowPlaying.width * 0.18 - 20)
                    implicitWidth: sourceText.implicitWidth + 16; implicitHeight: 22
                    visible: !!page.player
                    Accessible.name: i18n("Playback source"); Accessible.description: text
                    text: page.player?.identity || i18n("Playback source")
                    onClicked: nowPlaying.sourceRequested()
                    contentItem: RowLayout {
                        spacing: 4
                        Text { id: sourceText; Layout.fillWidth: true; Layout.minimumWidth: 0; text: sourceButton.text; textFormat: Text.PlainText; elide: Text.ElideRight; font.pixelSize: 10; color: "#959e9a" }
                        IslandGlyph { Layout.preferredWidth: 10; Layout.preferredHeight: 10; source: "arrow-down"; color: "#959e9a" }
                    }
                    background: Rectangle { radius: 6; color: sourceButton.hovered ? "#202724" : "transparent"; border.width: sourceButton.visualFocus ? 1 : 0; border.color: "#9ed3c1" }
                }
                Loader {
                    visible: !!page.player; active: visible && nowPlaying.visible
                    Layout.preferredWidth: 15; Layout.preferredHeight: 13
                    sourceComponent: MusicLevel { player: page.player; sources: page.sources; bars: 4; playing: page.playing; monitoring: page.liveLevels; tint: "#8bd1b9" }
                }
                Item { visible: nowPlaying.narrow; Layout.fillWidth: true }
            }
        }

        ColumnLayout {
            Layout.row: 1; Layout.column: nowPlaying.narrow ? 0 : 1; Layout.columnSpan: nowPlaying.narrow ? 2 : 1
            Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 0
            visible: page.lengthMs > 0
            MusicTimeline { id: timeline; page: nowPlaying.page; Layout.fillWidth: true; implicitHeight: 18; leftPadding: 0; rightPadding: 0 }
            RowLayout {
                Layout.fillWidth: true
                Text { font.pixelSize: 10; color: "#949c99"; text: page.formatDuration((timeline.pressed ? timeline.position * timeline.to : page.elapsed) / 1000) }
                Item { Layout.fillWidth: true }
                Text { objectName: "notchMusicRemaining"; font.pixelSize: 10; color: "#949c99"; text: "−" + page.formatDuration(Math.max(0, page.lengthMs - (timeline.pressed ? timeline.position * timeline.to : page.elapsed)) / 1000) }
            }
        }

        RowLayout {
            Layout.row: 2; Layout.column: nowPlaying.narrow ? 0 : 1; Layout.columnSpan: nowPlaying.narrow ? 2 : 1
            Layout.fillWidth: true; spacing: 12
            Item { Layout.fillWidth: true }
            IslandButton {
                objectName: "notchMusicPrevious"; plain: true; implicitWidth: 34; implicitHeight: 36; glyphSize: 21; solidGlyph: true
                icon.name: "media-skip-backward"; text: i18n("Previous track")
                enabled: !!page.player?.canGoPrevious; onClicked: page.player.Previous()
            }
            IslandButton {
                objectName: "notchMusicPlay"; prominent: true; implicitWidth: 42; implicitHeight: 42; glyphSize: 20; solidGlyph: true
                icon.name: page.playing ? "media-playback-pause" : "media-playback-start"
                text: page.playing ? i18n("Pause") : i18n("Play")
                enabled: !!(page.playing ? page.player?.canPause : page.player?.canPlay)
                onClicked: page.playing ? page.player.Pause() : page.player.Play()
            }
            IslandButton {
                objectName: "notchMusicNext"; plain: true; implicitWidth: 34; implicitHeight: 36; glyphSize: 21; solidGlyph: true
                icon.name: "media-skip-forward"; text: i18n("Next track")
                enabled: !!page.player?.canGoNext; onClicked: page.player.Next()
            }
            Item { Layout.fillWidth: true }
        }

        RowLayout {
            Layout.row: 3; Layout.column: 0; Layout.columnSpan: nowPlaying.narrow ? 2 : 1
            Layout.fillWidth: true; Layout.minimumWidth: 0
            Layout.preferredWidth: nowPlaying.narrow ? 0 : artwork.width
            Layout.maximumWidth: nowPlaying.narrow ? nowPlaying.width : artwork.width
            spacing: 3
            IslandButton {
                objectName: "notchMusicMute"; plain: true; implicitWidth: 22; implicitHeight: 26; glyphSize: 15
                enabled: !!nowPlaying.output
                icon.name: nowPlaying.output?.muted ? "audio-volume-muted" : "audio-volume-high"
                text: nowPlaying.output?.muted ? i18n("Unmute") : i18n("Mute")
                onClicked: nowPlaying.output.muted = !nowPlaying.output.muted
            }
            C.Slider {
                id: volume; objectName: "notchMusicVolume"
                Layout.fillWidth: true; Layout.minimumWidth: 24; implicitHeight: 26
                enabled: !!nowPlaying.output; from: 0; to: 100; stepSize: 1
                value: nowPlaying.output && !nowPlaying.output.muted ? Math.round(nowPlaying.output.volume * 100 / Audio.PulseAudio.NormalVolume) : 0
                Accessible.name: i18n("Output volume"); wheelEnabled: false
                leftPadding: 0; rightPadding: 0
                onMoved: {
                    if (!nowPlaying.output) return
                    nowPlaying.output.volume = Math.round(value * Audio.PulseAudio.NormalVolume / 100)
                    if (value > 0) nowPlaying.output.muted = false
                }
                background: Rectangle {
                    x: volume.leftPadding; y: (volume.height - height) / 2
                    width: volume.availableWidth; height: 6; radius: 3; color: "#29332f"
                    Rectangle { width: volume.visualPosition * parent.width; height: parent.height; radius: parent.radius; color: "#deebe6" }
                }
                handle: Rectangle {
                    x: volume.leftPadding + volume.visualPosition * (volume.availableWidth - width); y: (volume.height - height) / 2
                    width: 9; height: 9; radius: 4.5; color: "white"; visible: volume.pressed || volume.visualFocus
                }
            }
            IslandButton {
                objectName: "notchMusicMixer"; plain: true; implicitWidth: 25; implicitHeight: 26; glyphSize: 16
                visible: page.offerMixer; icon.name: "headphones"; text: i18n("Sound output and mixer")
                onClicked: page.viewRequested(3)
            }
        }

        RowLayout {
            Layout.row: nowPlaying.narrow ? 4 : 3; Layout.column: nowPlaying.narrow ? 0 : 1; Layout.columnSpan: nowPlaying.narrow ? 2 : 1
            Layout.fillWidth: true; spacing: 6
            Item { Layout.fillWidth: true }
            component DetailButton: C.AbstractButton {
                id: button
                property string symbol
                implicitWidth: label.implicitWidth + 39; implicitHeight: 29
                Accessible.name: text
                background: Rectangle { radius: height / 2; color: button.down ? "#343c38" : button.hovered ? "#242b27" : "#171b19"; border.width: button.visualFocus ? 1 : 0; border.color: "#9ed3c1" }
                contentItem: RowLayout {
                    spacing: 5
                    Item { Layout.preferredWidth: 6 }
                    IslandGlyph { Layout.preferredWidth: 13; Layout.preferredHeight: 13; source: button.symbol; color: "#ebefed" }
                    Text { id: label; text: button.text; color: "#ebefed"; font.pixelSize: 11 }
                    Item { Layout.preferredWidth: 6 }
                }
            }
            DetailButton { objectName: "notchMusicLyrics"; visible: page.offerDetails; enabled: !!page.player; text: i18n("Lyrics"); symbol: "lyrics"; onClicked: page.viewRequested(1) }
            DetailButton { objectName: "notchMusicQueue"; visible: page.offerDetails; enabled: !!page.player; text: i18n("Up next"); symbol: "view-media-playlist"; onClicked: page.viewRequested(2) }
            IslandButton {
                id: more; plain: true; implicitWidth: 26; implicitHeight: 29
                icon.name: "view-more-symbolic"; text: i18n("Playback options")
                onClicked: options.open()
            }
        }
    }
    IslandMenu {
        id: options; bounds: nowPlaying; anchorItem: more
        C.MenuItem {
            text: i18n("Shuffle"); checkable: true; checked: page.player?.shuffle === Mpris.ShuffleStatus.On
            enabled: !!page.player?.canControl && page.player?.shuffle !== Mpris.ShuffleStatus.Unknown
            onTriggered: page.player.shuffle = checked ? Mpris.ShuffleStatus.On : Mpris.ShuffleStatus.Off
        }
        C.MenuItem {
            readonly property int status: page.player?.loopStatus ?? Mpris.LoopStatus.Unknown
            text: status === Mpris.LoopStatus.Track ? i18n("Repeat track") : status === Mpris.LoopStatus.Playlist ? i18n("Repeat playlist") : i18n("Repeat off")
            enabled: !!page.player?.canControl && status !== Mpris.LoopStatus.Unknown
            onTriggered: page.player.loopStatus = status === Mpris.LoopStatus.None ? Mpris.LoopStatus.Playlist : status === Mpris.LoopStatus.Playlist ? Mpris.LoopStatus.Track : Mpris.LoopStatus.None
        }
        C.MenuSeparator {}
        C.MenuItem { text: i18n("Open player"); enabled: !!page.service; onTriggered: page.raisePlayer() }
    }
}
