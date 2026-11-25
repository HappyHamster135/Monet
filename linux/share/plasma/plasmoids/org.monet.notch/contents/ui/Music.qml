import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C
import org.kde.kirigami as Kirigami
import org.kde.plasma.private.mpris as Mpris
import org.kde.plasma.plasma5support as P5
import org.kde.plasma.workspace.dbus as DBus

ColumnLayout {
    id: page
    required property var player
    required property var sources
    required property var formatDuration
    property var gestures: null
    property bool offerDetails: true
    property bool offerMixer: true
    required property bool playing
    required property int view // 0: now playing, 1: lyrics, 2: upcoming tracks
    signal viewRequested(int index)
    readonly property string service: player?.objectName ? "org.mpris.MediaPlayer2." + player.objectName : ""
    readonly property string playerInterface: "org.mpris.MediaPlayer2.Player"
    readonly property string playerPath: "/org/mpris/MediaPlayer2"
    property string trackId: ""
    property DBus.DBusPendingReply metadataRead
    function readTrackId() {
        trackId = ""
        metadataRead = service ? DBus.SessionBus.asyncCall({service: service, path: playerPath,
            iface: "org.freedesktop.DBus.Properties", member: "Get", signature: "(ss)",
            arguments: [playerInterface, "Metadata"]}) : null
        finishMetadata()
    }
    function finishMetadata() {
        if (!metadataRead?.isFinished) return
        const reply = metadataRead
        metadataRead = null
        if (reply.isValid) trackId = String(reply.value?.["mpris:trackid"] || "")
    }
    Connections {
        target: page.metadataRead
        function onFinished() { page.finishMetadata() }
    }
    onServiceChanged: readTrackId()
    readonly property string selection: player ? JSON.stringify({service: service, pid: player.instancePid, identity: player.identity,
        title: player.track, artist: player.artist}) : ""
    readonly property bool detailed: view > 0
    readonly property string watchedService: detailed ? service || details.service || "" : ""
    property var details: ({})
    readonly property var lines: details.lyrics?.timed || []
    readonly property var queue: details.queue || []
    property int epoch: 0
    property int requestedEpoch: -1
    property bool busy: false
    property bool follow: true
    property int currentLine: -1
    property double anchorTime: 0
    property double anchorPosition: 0
    readonly property double rate: page.playing ? Math.max(0, player?.rate ?? 1) : 0
    readonly property string reader: "/usr/bin/python3 '@DATADIR@/monet/utilities/player.py' "

    function refresh(clear) {
        ++epoch
        if (clear) {
            details = ({})
            currentLine = -1
            follow = true
        }
        if (detailed && selection) refreshTimer.restart()
    }
    onSelectionChanged: { refresh(true); Qt.callLater(syncPosition) }
    onTrackIdChanged: if (detailed) refresh(true)
    onPlayerChanged: { refresh(true); Qt.callLater(syncPosition) }
    onDetailedChanged: if (detailed) refresh(false)
    // Cover changes made after the first snapshot but before the D-Bus subscription.
    onWatchedServiceChanged: if (watchedService) refresh(false)
    onViewChanged: {
        if (view !== 1) boundary.stop()
        Qt.callLater(syncPosition)
    }
    Component.onCompleted: if (detailed) refresh(false)
    Timer {
        id: refreshTimer; interval: 60
        onTriggered: {
            if (page.busy || !page.selection || !page.view) return
            const bytes = unescape(encodeURIComponent(page.selection))
            const key = Array.from(bytes, c => c.charCodeAt(0).toString(16).padStart(2, "0")).join("")
            page.requestedEpoch = page.epoch
            page.busy = true
            reader.connectSource(page.reader + key)
        }
    }
    P5.DataSource {
        id: reader
        engine: "executable"; connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            page.busy = false
            if (page.requestedEpoch !== page.epoch) {
                refreshTimer.restart()
                return
            }
            let state = {}
            try { state = JSON.parse(data.stdout) } catch (_) {}
            page.details = state
            if (page.view === 1) page.syncPosition()
        }
    }
    DBus.SignalWatcher {
        enabled: !!page.watchedService
        busType: DBus.BusType.Session; service: page.watchedService
        path: "/org/mpris/MediaPlayer2"; iface: "org.mpris.MediaPlayer2.TrackList"
        function dbusTrackListReplaced() { page.refresh(false) }
        function dbusTrackAdded() { page.refresh(false) }
        function dbusTrackRemoved() { page.refresh(false) }
        function dbusTrackMetadataChanged() { page.refresh(false) }
    }
    DBus.SignalWatcher {
        enabled: !!(page.service || page.watchedService)
        busType: DBus.BusType.Session; service: page.service || page.watchedService
        path: "/org/mpris/MediaPlayer2"; iface: "org.freedesktop.DBus.Properties"
        function dbusPropertiesChanged(iface, changed, invalidated) {
            if (String(iface) === page.playerInterface && (changed.Metadata !== undefined || invalidated.includes("Metadata"))) {
                page.metadataRead = null
                if (changed.Metadata !== undefined) page.trackId = String(changed.Metadata["mpris:trackid"] || "")
                else page.readTrackId()
                if (page.detailed) page.refresh(false)
                Qt.callLater(page.syncPosition)
            } else if (page.detailed && String(iface) === "org.mpris.MediaPlayer2.TrackList" && (changed.Tracks !== undefined || invalidated.includes("Tracks"))) {
                page.refresh(false)
            }
        }
    }
    readonly property double lengthMs: Math.max(0, (player?.length ?? 0) / 1000)
    property double clock: 0
    readonly property double elapsed: Math.min(lengthMs, estimatePosition(clock))
    function estimatePosition(now) {
        return anchorPosition + Math.max(0, now - anchorTime) * rate
    }
    Timer {
        interval: 1000; repeat: true
        running: page.visible && page.view === 0 && page.rate > 0 && page.lengthMs > 0
        onTriggered: page.clock = Date.now()
    }
    onRateChanged: Qt.callLater(syncPosition)
    Connections {
        target: page.player
        function onPositionChanged() { page.setPosition(page.player.position / 1000) }
    }
    function seek(ms) {
        ms = Math.round(Math.max(0, lengthMs > 0 ? Math.min(lengthMs, ms) : ms))
        // The track ID belongs to the displayed song, even if the player
        // advances before it processes the asynchronous seek.
        DBus.SessionBus.asyncCall({service: service, path: playerPath,
            iface: playerInterface, member: "SetPosition", signature: "(ox)",
            arguments: [trackId, ms * 1000]})
        setPosition(ms)
    }
    function setPosition(ms) {
        anchorTime = Date.now()
        clock = anchorTime
        anchorPosition = Math.max(0, ms)
        updateLine()
    }
    function syncPosition() {
        if (!player || !visible || (view === 0 ? lengthMs <= 0 : view !== 1 || !lines.length)) return
        setPosition(player.position / 1000)
        player.updatePosition()
    }
    function updateLine() {
        boundary.stop()
        if (!lines.length || view !== 1) return
        const at = estimatePosition(Date.now())
        let low = 0, high = lines.length
        while (low < high) {
            const middle = Math.floor((low + high) / 2)
            if (lines[middle].at <= at) low = middle + 1
            else high = middle
        }
        currentLine = low - 1
        if (rate && low < lines.length) {
            boundary.interval = Math.max(1, Math.min(2147483647, Math.ceil((lines[low].at - at) / rate)))
            boundary.start()
        }
    }
    Timer { id: boundary; onTriggered: page.updateLine() }

    spacing: Kirigami.Units.smallSpacing
    Item { Layout.fillHeight: true; visible: page.view === 0 }
    RowLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.smallSpacing
        Layout.rightMargin: Kirigami.Units.smallSpacing
        spacing: Kirigami.Units.largeSpacing
        Item {
            Layout.fillWidth: true
            implicitHeight: trackInfo.implicitHeight
            RowLayout {
                id: trackInfo
                anchors.fill: parent
                spacing: Kirigami.Units.largeSpacing
                Item {
                    Layout.preferredWidth: page.view ? 36 : 66
                    Layout.preferredHeight: Layout.preferredWidth
                    Kirigami.Icon { anchors.centerIn: parent; width: parent.width * 0.7; height: width; visible: cover.status !== Image.Ready; source: "audio-headphones" }
                    Image {
                        id: cover; anchors.fill: parent; asynchronous: true; fillMode: Image.PreserveAspectFit
                        sourceSize: Qt.size(width * Screen.devicePixelRatio, height * Screen.devicePixelRatio)
                        source: page.player?.artUrl || ""
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 0
                    C.Label {
                        Layout.fillWidth: true; textFormat: Text.PlainText; elide: Text.ElideRight; font.bold: true
                        text: page.player?.track || i18n("Nothing playing")
                    }
                    C.Label {
                        Layout.fillWidth: true; textFormat: Text.PlainText; elide: Text.ElideRight
                        text: page.player?.artist || page.player?.identity || i18n("Start a song or video in a media player.")
                    }
                }
            }
            NotchGestureSurface { gestures: page.gestures }
        }
        C.ToolButton {
            id: sourceButton
            objectName: "notchPlaybackSource"
            visible: sourceRows.count > 2 || page.sources.currentIndex > 0
            Layout.maximumWidth: page.width * 0.36
            text: page.player?.identity || i18n("Playback source")
            contentItem: RowLayout {
                spacing: Kirigami.Units.smallSpacing
                C.Label {
                    Layout.fillWidth: true; Layout.minimumWidth: 0
                    text: sourceButton.text; textFormat: Text.PlainText; elide: Text.ElideRight
                }
                Kirigami.Icon {
                    source: "arrow-down"
                    Layout.preferredWidth: Kirigami.Units.iconSizes.small
                    Layout.preferredHeight: Layout.preferredWidth
                }
            }
            Accessible.name: i18n("Playback source")
            Accessible.description: page.player?.identity || ""
            C.ToolTip.text: i18n("Playback source")
            C.ToolTip.delay: Kirigami.Units.toolTipDelay
            C.ToolTip.visible: hovered
            onClicked: sourceMenu.open()
            C.Menu {
                id: sourceMenu
                popupType: C.Popup.Item
                width: Math.min(page.width, Kirigami.Units.gridUnit * 17)
                x: Math.min(0, page.width - sourceButton.mapToItem(page, 0, 0).x - width)
                y: sourceButton.height
                Instantiator {
                    id: sourceRows
                    model: page.sources
                    delegate: C.MenuItem {
                        required property int index
                        required property var model
                        text: index === 0 ? i18n("Automatic") : [model.identity, model.track].filter(Boolean).join(" — ")
                        icon.name: index === 0 ? "media-playlist-normal" : model.iconName || "multimedia-player"
                        checkable: true; checked: page.sources.currentIndex === index
                        onTriggered: page.sources.currentIndex = index
                    }
                    onObjectAdded: (index, item) => sourceMenu.insertItem(index, item)
                    onObjectRemoved: (index, item) => sourceMenu.removeItem(item)
                }
            }
        }
        C.ToolButton {
            visible: page.view !== 0
            icon.name: page.playing ? "media-playback-pause" : "media-playback-start"
            Accessible.name: page.playing ? i18n("Pause") : i18n("Play")
            enabled: !!(page.playing ? page.player?.canPause : page.player?.canPlay)
            onClicked: page.playing ? page.player.Pause() : page.player.Play()
        }
    }
    RowLayout {
        visible: page.view === 0 && page.lengthMs > 0
        Layout.fillWidth: true
        C.Label {
            text: page.formatDuration((timeline.pressed ? timeline.position * timeline.to : page.elapsed) / 1000)
        }
        C.Slider {
            id: timeline
            objectName: "notchPlaybackPosition"
            Layout.fillWidth: true; Layout.minimumWidth: 1
            from: 0; to: page.lengthMs; value: page.elapsed
            enabled: !!page.player?.canSeek && page.trackId.startsWith("/")
            live: false
            Accessible.name: i18n("Playback position")
            Accessible.description: page.formatDuration(page.elapsed / 1000) + " / " + page.formatDuration(to / 1000)
            Accessible.onIncreaseAction: if (enabled) page.seek(page.elapsed + 5000)
            Accessible.onDecreaseAction: if (enabled) page.seek(page.elapsed - 5000)
            property var pressedPlayer: null
            property string pressedTrack: ""
            Keys.onPressed: event => {
                if (event.key === Qt.Key_Left || event.key === Qt.Key_Right) {
                    page.seek(page.elapsed + ((event.key === Qt.Key_Right) !== mirrored ? 5000 : -5000))
                } else if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                    page.seek(event.key === Qt.Key_Home ? 0 : to)
                } else {
                    return
                }
                event.accepted = true
            }
            onPressedChanged: {
                if (pressed) {
                    forceActiveFocus(Qt.MouseFocusReason)
                    pressedPlayer = page.player
                    pressedTrack = page.trackId
                } else {
                    if (visible && enabled && pressedPlayer && pressedPlayer === page.player && pressedTrack === page.trackId) {
                        page.seek(position * to)
                    }
                    pressedPlayer = null
                }
            }
        }
        C.Label { text: page.formatDuration(page.lengthMs / 1000) }
    }
    RowLayout {
        visible: page.view === 0; Layout.alignment: Qt.AlignHCenter
        Item {
            implicitWidth: shuffleButton.implicitWidth
            implicitHeight: shuffleButton.implicitHeight
            C.ToolButton {
                id: shuffleButton
                anchors.centerIn: parent
                visible: !!page.player && page.player.shuffle !== Mpris.ShuffleStatus.Unknown
                enabled: !!page.player?.canControl
                icon.name: "media-playlist-shuffle"
                checked: page.player?.shuffle === Mpris.ShuffleStatus.On
                Accessible.name: i18n("Shuffle")
                C.ToolTip.text: Accessible.name
                C.ToolTip.delay: Kirigami.Units.toolTipDelay
                C.ToolTip.visible: hovered
                onClicked: page.player.shuffle = page.player.shuffle === Mpris.ShuffleStatus.On ? Mpris.ShuffleStatus.Off : Mpris.ShuffleStatus.On
            }
        }
        C.ToolButton { icon.name: "media-skip-backward"; Accessible.name: i18n("Previous track"); enabled: !!page.player?.canGoPrevious; onClicked: page.player.Previous() }
        C.ToolButton {
            icon.name: page.playing ? "media-playback-pause" : "media-playback-start"
            Accessible.name: page.playing ? i18n("Pause") : i18n("Play")
            enabled: !!(page.playing ? page.player?.canPause : page.player?.canPlay)
            onClicked: page.playing ? page.player.Pause() : page.player.Play()
        }
        C.ToolButton { icon.name: "media-skip-forward"; Accessible.name: i18n("Next track"); enabled: !!page.player?.canGoNext; onClicked: page.player.Next() }
        Item {
            implicitWidth: repeatButton.implicitWidth
            implicitHeight: repeatButton.implicitHeight
            C.ToolButton {
                id: repeatButton
                anchors.centerIn: parent
                readonly property int status: page.player?.loopStatus ?? Mpris.LoopStatus.Unknown
                visible: status !== Mpris.LoopStatus.Unknown
                enabled: !!page.player?.canControl
                icon.name: status === Mpris.LoopStatus.Track ? "media-playlist-repeat-song" : "media-playlist-repeat"
                checked: status === Mpris.LoopStatus.Playlist || status === Mpris.LoopStatus.Track
                Accessible.name: status === Mpris.LoopStatus.Track ? i18n("Repeat track")
                    : status === Mpris.LoopStatus.Playlist ? i18n("Repeat playlist") : i18n("Repeat off")
                C.ToolTip.text: Accessible.name
                C.ToolTip.delay: Kirigami.Units.toolTipDelay
                C.ToolTip.visible: hovered
                onClicked: page.player.loopStatus = status === Mpris.LoopStatus.None ? Mpris.LoopStatus.Playlist
                    : status === Mpris.LoopStatus.Playlist ? Mpris.LoopStatus.Track : Mpris.LoopStatus.None
            }
        }
    }
    RowLayout {
        Layout.alignment: Qt.AlignHCenter
        C.ToolButton { visible: page.view !== 0; icon.name: "go-previous"; Accessible.name: i18n("Now playing"); onClicked: page.viewRequested(0) }
        C.Button { visible: page.offerDetails && (!!page.player || page.view !== 0); text: i18n("Lyrics"); checked: page.view === 1; onClicked: page.viewRequested(1) }
        C.Button { visible: page.offerDetails && (!!page.player || page.view !== 0); text: i18n("Up next"); checked: page.view === 2; onClicked: page.viewRequested(2) }
        C.Button { visible: page.offerMixer && page.view === 0; text: i18n("Mixer"); icon.name: "audio-volume-high"; onClicked: page.viewRequested(3) }
        C.ToolButton {
            visible: page.view === 1 && page.lines.length > 0 && !page.follow
            icon.name: "view-restore"; Accessible.name: i18n("Follow lyrics")
            onClicked: { page.follow = true; lyricsList.centerLine() }
        }
    }
    Item { Layout.fillHeight: true; visible: page.view === 0 }
    Item {
        visible: page.view > 0; Layout.fillWidth: true; Layout.fillHeight: true
        ListView {
            id: lyricsList; objectName: "notchTimedLyrics"
            anchors.fill: parent; visible: page.view === 1 && count > 0; clip: true
            model: page.lines; currentIndex: page.currentLine
            function centerLine() { if (visible && page.follow && currentIndex >= 0) positionViewAtIndex(currentIndex, ListView.Center) }
            onCurrentIndexChanged: Qt.callLater(centerLine)
            onVisibleChanged: Qt.callLater(centerLine)
            onMovementStarted: page.follow = false
            C.ScrollBar.vertical: C.ScrollBar {}
            delegate: C.ItemDelegate {
                id: line
                required property var modelData
                width: ListView.view.width; highlighted: ListView.isCurrentItem
                contentItem: C.Label { textFormat: Text.PlainText; wrapMode: Text.WordWrap; text: modelData.text || "♪"; font.bold: line.highlighted }
                Accessible.role: page.player?.canSeek ? Accessible.Button : Accessible.StaticText
                Accessible.name: modelData.text || i18n("Instrumental")
                onClicked: if (page.player?.canSeek && page.trackId && page.details.trackId === page.trackId) page.seek(modelData.at)
            }
        }
        C.ScrollView {
            id: plainLyrics
            anchors.fill: parent
            visible: page.view === 1 && !page.lines.length && !!page.details.lyrics?.text
            contentWidth: availableWidth
            C.Label { width: plainLyrics.availableWidth; textFormat: Text.PlainText; wrapMode: Text.Wrap; text: page.details.lyrics?.text || "" }
        }
        ListView {
            objectName: "notchQueue"; anchors.fill: parent; clip: true; spacing: Kirigami.Units.smallSpacing
            visible: page.view === 2 && count > 0; model: page.queue
            C.ScrollBar.vertical: C.ScrollBar {}
            delegate: ColumnLayout {
                required property var modelData
                width: ListView.view.width - Kirigami.Units.largeSpacing; spacing: 0
                C.Label { Layout.fillWidth: true; elide: Text.ElideRight; textFormat: Text.PlainText; text: modelData.title || i18n("Untitled") }
                C.Label { Layout.fillWidth: true; elide: Text.ElideRight; textFormat: Text.PlainText; visible: !!text; opacity: 0.75; text: modelData.artist }
            }
        }
        C.Label {
            anchors.centerIn: parent; width: parent.width; horizontalAlignment: Text.AlignHCenter
            visible: page.view === 1 ? !page.lines.length && !page.details.lyrics?.text : !page.queue.length
            wrapMode: Text.WordWrap; text: page.busy ? i18n("Loading…") : page.view === 1
                ? i18n("No lyrics available for this track.") : i18n("No upcoming tracks shared by this player.")
        }
    }
}
