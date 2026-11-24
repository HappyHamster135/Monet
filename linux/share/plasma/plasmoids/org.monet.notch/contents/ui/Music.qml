import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5
import org.kde.plasma.workspace.dbus as DBus

ColumnLayout {
    id: page
    required property var media
    required property bool playing
    required property int view // 0: now playing, 1: lyrics, 2: upcoming tracks
    signal viewRequested(int index)
    readonly property var player: media?.container || null
    readonly property string selection: player ? JSON.stringify({pid: player.instancePid, identity: player.identity,
        title: player.track, artist: player.artist}) : ""
    readonly property bool detailed: view > 0
    readonly property string watchedService: detailed ? details.service || "" : ""
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
        refreshTimer.restart()
    }
    onSelectionChanged: refresh(true)
    onPlayerChanged: refresh(true)
    onDetailedChanged: if (detailed) refresh(false)
    // Cover changes made after the first snapshot but before the D-Bus subscription.
    onWatchedServiceChanged: if (watchedService) refresh(false)
    onViewChanged: {
        if (view === 1) syncPosition()
        else boundary.stop()
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
        enabled: !!page.watchedService
        busType: DBus.BusType.Session; service: page.watchedService
        path: "/org/mpris/MediaPlayer2"; iface: "org.freedesktop.DBus.Properties"
        function dbusPropertiesChanged(iface, changed, invalidated) {
            const key = iface === "org.mpris.MediaPlayer2.Player" ? "Metadata"
                      : iface === "org.mpris.MediaPlayer2.TrackList" ? "Tracks" : ""
            if (key && (changed[key] !== undefined || invalidated.includes(key))) page.refresh(false)
        }
    }
    onRateChanged: if (view === 1) Qt.callLater(syncPosition)
    Connections {
        target: page.player
        function onPositionChanged() {
            page.anchorPosition = Math.max(0, page.player.position / 1000)
            page.anchorTime = Date.now()
            page.updateLine()
        }
    }
    function syncPosition() {
        if (!player || !lines.length || view !== 1) return
        anchorPosition = Math.max(0, player.position / 1000)
        anchorTime = Date.now()
        player.updatePosition()
        updateLine()
    }
    function updateLine() {
        boundary.stop()
        if (!lines.length || view !== 1) return
        const at = anchorPosition + Math.max(0, Date.now() - anchorTime) * rate
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
            Layout.preferredWidth: page.view ? 36 : 66
            Layout.preferredHeight: Layout.preferredWidth
            Kirigami.Icon { anchors.centerIn: parent; width: parent.width * 0.7; height: width; visible: cover.status !== Image.Ready; source: "audio-headphones" }
            Image {
                id: cover; anchors.fill: parent; asynchronous: true; fillMode: Image.PreserveAspectFit
                sourceSize: Qt.size(width * Screen.devicePixelRatio, height * Screen.devicePixelRatio)
                source: page.media?.artUrl || ""
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 0
            C.Label {
                Layout.fillWidth: true; textFormat: Text.PlainText; elide: Text.ElideRight; font.bold: true
                text: page.media?.track || i18n("Nothing playing")
            }
            C.Label {
                Layout.fillWidth: true; textFormat: Text.PlainText; elide: Text.ElideRight
                text: page.media?.artist || page.media?.identity || i18n("Start a song or video in a media player.")
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
        visible: page.view === 0; Layout.alignment: Qt.AlignHCenter
        C.ToolButton { icon.name: "media-skip-backward"; Accessible.name: i18n("Previous track"); enabled: !!page.player?.canGoPrevious; onClicked: page.player.Previous() }
        C.ToolButton {
            icon.name: page.playing ? "media-playback-pause" : "media-playback-start"
            Accessible.name: page.playing ? i18n("Pause") : i18n("Play")
            enabled: !!(page.playing ? page.player?.canPause : page.player?.canPlay)
            onClicked: page.playing ? page.player.Pause() : page.player.Play()
        }
        C.ToolButton { icon.name: "media-skip-forward"; Accessible.name: i18n("Next track"); enabled: !!page.player?.canGoNext; onClicked: page.player.Next() }
    }
    RowLayout {
        visible: !!page.media || page.view !== 0
        Layout.alignment: Qt.AlignHCenter
        C.ToolButton { visible: page.view !== 0; icon.name: "go-previous"; Accessible.name: i18n("Now playing"); onClicked: page.viewRequested(0) }
        C.Button { text: i18n("Lyrics"); checked: page.view === 1; onClicked: page.viewRequested(1) }
        C.Button { text: i18n("Up next"); checked: page.view === 2; onClicked: page.viewRequested(2) }
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
                onClicked: if (page.player?.canSeek) page.player.position = modelData.at * 1000
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
