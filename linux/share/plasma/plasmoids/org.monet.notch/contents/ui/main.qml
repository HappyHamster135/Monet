import QtQuick
import QtCore
import Qt.labs.folderlistmodel
import QtQuick.Layouts
import QtQuick.Controls as C
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5
import org.kde.plasma.private.mpris as Mpris
import org.kde.notificationmanager as NM

PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: compactRepresentation
    readonly property string helper: "@LIBEXECDIR@/monet-quick"
    readonly property var media: players.count ? players.itemAt(0)?.model ?? null : null
    readonly property bool playing: media?.playbackStatus === Mpris.PlaybackStatus.Playing
    readonly property double endTime: Number(Plasmoid.configuration.deadline) || 0
    readonly property double watchStart: Number(Plasmoid.configuration.watchStart) || 0
    property double now: Date.now()
    property int tab: 0
    property string message: ""
    property string agentSummary: ""
    property url downloadFolder: StandardPaths.writableLocation(StandardPaths.DownloadLocation)
    toolTipMainText: i18n("Monet Notch")
    toolTipSubText: endTime ? remaining() : media?.track || i18n("Music, activity and tools")
    Repeater {
        id: players
        model: Mpris.MultiplexerModel {}
        delegate: Item { required property var model; visible: false }
    }
    SessionActivity {
        id: power
        observePower: Plasmoid.configuration.alerts || root.expanded
        onBatteriesChanged: if (power.powerReady && Plasmoid.configuration.alerts) root.checkCharge()
        onPowerReadyChanged: if (power.powerReady && Plasmoid.configuration.alerts) root.checkCharge()
    }
    function checkCharge() {
        let warned = {}
        try { warned = JSON.parse(Plasmoid.configuration.warnedDevices || "{}") } catch (_) {}
        for (const device of power.batteries) {
            if (device.kind === "laptop" || device.kind === "other") continue
            const key = JSON.stringify([device.kind, device.name])
            if (device.level > 25) delete warned[key]
            if (device.level <= 20 && !device.charging && !warned[key]) {
                warned[key] = true
                runner.connectSource(helper + " accessory-alert " + hex(device.name || device.kind) + " " + device.level)
            }
        }
        const saved = JSON.stringify(warned)
        if (saved !== Plasmoid.configuration.warnedDevices) Plasmoid.configuration.warnedDevices = saved
    }
    function duration(seconds) {
        const s = Math.max(0, Math.floor(seconds))
        return (s >= 3600 ? Math.floor(s / 3600) + ":" : "") +
            String(Math.floor(s / 60) % 60).padStart(s >= 3600 ? 2 : 1, "0") + ":" + String(s % 60).padStart(2, "0")
    }
    function remaining() { return duration(Math.ceil((endTime - now) / 1000)) }
    function hex(text) {
        return Array.from(unescape(encodeURIComponent(text)), c => c.charCodeAt(0).toString(16).padStart(2, "0")).join("")
    }
    function openTool(page, urls) {
        const args = urls ? " " + hex(JSON.stringify(urls.map(u => u.toString()))) : ""
        runner.connectSource(helper + " utilities " + page + args)
        expanded = false
    }
    function start(minutes, focus) {
        now = Date.now()
        Plasmoid.configuration.deadline = String(now + minutes * 60000)
        Plasmoid.configuration.focus = focus
        if (focus) runner.connectSource(helper + " focus " + Math.ceil(endTime / 1000) + " " + Plasmoid.id)
    }
    function stop(ring) {
        const focused = Plasmoid.configuration.focus
        Plasmoid.configuration.deadline = ""
        Plasmoid.configuration.focus = false
        if (focused) runner.connectSource(helper + " focus off " + Plasmoid.id)
        if (ring) runner.connectSource(helper + " ring " + hex(i18n("Monet Notch")) + " " +
            hex(focused ? i18n("Focus session finished") : i18n("Timer finished")))
    }
    function refreshTime() {
        now = Date.now()
        if (endTime && now >= endTime) stop(true)
    }
    Timer {
        interval: 1000; repeat: true
        running: !!root.endTime || (root.expanded && root.tab === 2 && !!root.watchStart)
        onTriggered: root.refreshTime()
    }
    Component.onCompleted: refreshTime()
    onExpandedChanged: expanded => { if (expanded) refreshTime() }
    P5.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            if (source.endsWith(" notch-activity")) {
                try {
                    const state = JSON.parse(data.stdout)
                    root.agentSummary = state.agent
                    if (state.folder.startsWith("file:///")) root.downloadFolder = state.folder
                } catch (_) {}
            }
            if (source.startsWith(root.helper + " focus ") && !source.includes(" focus off ")) {
                try { if (JSON.parse(data.stdout).ok) return } catch (e) {}
                Plasmoid.configuration.focus = false
                root.message = i18n("Quiet mode was unavailable. Your timer is running.")
            }
        }
    }
    function wheelAction(wheel) {
        if (Math.abs(wheel.angleDelta.x) > Math.abs(wheel.angleDelta.y)) {
            if (gesture.running) return
            if (wheel.angleDelta.x < 0 && media?.canGoNext) media.container.Next()
            if (wheel.angleDelta.x > 0 && media?.canGoPrevious) media.container.Previous()
            gesture.restart()
        } else if (wheel.angleDelta.y) {
            expanded = wheel.angleDelta.y < 0
        }
    }
    Timer { id: gesture; interval: 450 }
    compactRepresentation: C.AbstractButton {
        id: pill
        Layout.minimumWidth: Plasmoid.configuration.wide ? 176 : 96
        Layout.maximumWidth: Layout.minimumWidth
        Layout.preferredWidth: Layout.minimumWidth
        Accessible.name: root.toolTipMainText + ". " + root.toolTipSubText
        onClicked: root.expanded = !root.expanded
        background: Rectangle {
            radius: height / 2
            color: shelfDrop.containsDrag || pill.activeFocus ? "#30695e" : "#202323"
            border.color: shelfDrop.containsDrag || pill.hovered ? "#7ec9b5" : "#494c4a"
        }
        contentItem: RowLayout {
            spacing: 5
            Loader {
                Layout.preferredWidth: active ? 13 : 0; Layout.preferredHeight: 18
                visible: active; active: Plasmoid.configuration.levels && root.playing && power.active
                source: "MusicLevel.qml"
            }
            Kirigami.Icon {
                visible: !Plasmoid.configuration.companion
                Layout.preferredHeight: 17; Layout.preferredWidth: 17
                source: shelfDrop.containsDrag ? "folder-add" : root.endTime ? "chronometer" : root.media ? "audio-x-generic" : "applications-utilities"
                color: "#9dd9c9"; isMask: true
            }
            C.Label {
                visible: Plasmoid.configuration.companion
                text: shelfDrop.containsDrag ? "✿" : root.playing ? "♫" : "◕‿◕"
                color: "#a8ddc8"
                Accessible.name: i18n("Notch companion")
            }
            C.Label {
                Layout.fillWidth: true; color: "#f6f3e9"; textFormat: Text.PlainText; elide: Text.ElideRight
                text: shelfDrop.containsDrag ? i18n("Shelf") : root.endTime ? root.remaining() : root.media?.track || i18n("Tools")
            }
        }
        WheelHandler { onWheel: event => root.wheelAction(event) }
        DropArea {
            id: shelfDrop
            anchors.fill: parent
            onEntered: drag => { drag.accepted = drag.hasUrls && drag.urls.length <= 100 && drag.urls.every(u => u.toString().startsWith("file:///")) }
            onDropped: drop => {
                if (drop.hasUrls) {
                    root.openTool("shelf", Array.from(drop.urls))
                    drop.accept(Qt.CopyAction)
                }
            }
        }
    }

    fullRepresentation: ColumnLayout {
        Layout.preferredWidth: Math.min(422, Math.max(250, Screen.width - 32))
        Layout.preferredHeight: Math.min(370, Math.max(200, Screen.height - 80))
        spacing: Kirigami.Units.smallSpacing
        C.TabBar {
            Layout.fillWidth: true
            currentIndex: root.tab
            onCurrentIndexChanged: root.tab = currentIndex
            Repeater {
                model: [i18n("Music"), i18n("Activity"), i18n("Time"), i18n("Calendar")]
                C.TabButton { required property string modelData; text: modelData }
            }
        }
        Loader {
            Layout.fillWidth: true; Layout.fillHeight: true
            active: root.expanded
            sourceComponent: [musicPage, activityPage, timerPage, calendarPage][root.tab]
        }
        RowLayout {
            Layout.fillWidth: true
            C.Button { text: i18n("File shelf"); icon.name: "folder-open"; onClicked: root.openTool("shelf") }
            Item { Layout.fillWidth: true }
            C.Button { text: i18n("Utilities"); icon.name: "applications-utilities"; onClicked: root.openTool("tools") }
        }
    }
    Component {
        id: musicPage
        ColumnLayout {
            Item { Layout.fillHeight: true }
            Image {
                Layout.alignment: Qt.AlignHCenter; Layout.preferredHeight: 82; Layout.preferredWidth: 82
                visible: status === Image.Ready; asynchronous: true; sourceSize: Qt.size(164,164)
                source: root.media?.artUrl || ""; fillMode: Image.PreserveAspectFit
            }
            C.Label {
                Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; textFormat: Text.PlainText
                elide: Text.ElideRight; font.bold: true; text: root.media?.track || i18n("Nothing playing")
            }
            C.Label {
                Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; elide: Text.ElideRight; textFormat: Text.PlainText
                text: root.media?.artist || root.media?.identity || i18n("Start a song or video in a media player.")
            }
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                C.ToolButton { icon.name: "media-skip-backward"; Accessible.name: i18n("Previous track"); enabled: !!root.media?.canGoPrevious; onClicked: root.media.container.Previous() }
                C.ToolButton {
                    icon.name: root.playing ? "media-playback-pause" : "media-playback-start"
                    Accessible.name: root.playing ? i18n("Pause") : i18n("Play")
                    enabled: !!(root.playing ? root.media?.canPause : root.media?.canPlay)
                    onClicked: root.playing ? root.media.container.Pause() : root.media.container.Play()
                }
                C.ToolButton { icon.name: "media-skip-forward"; Accessible.name: i18n("Next track"); enabled: !!root.media?.canGoNext; onClicked: root.media.container.Next() }
            }
            C.Button {
                Layout.alignment: Qt.AlignHCenter; visible: !!root.media
                text: i18n("Queue and lyrics"); onClicked: root.openTool("media")
            }
            Item { Layout.fillHeight: true }
        }
    }
    Component {
        id: activityPage
        ColumnLayout {

            Repeater {
                model: power.batteries
                C.Label {
                    required property var modelData
                    Layout.fillWidth: true; elide: Text.ElideRight; textFormat: Text.PlainText
                    text: i18n("%1 · %2%", modelData.name || modelData.kind, modelData.level)
                }
            }
            ListView {
                id: alerts
                Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                model: NM.Notifications {
                    showNotifications: true; showJobs: true; showExpired: true; showDismissed: false; limit: 20
                    groupMode: NM.Notifications.GroupDisabled
                }
                delegate: C.ItemDelegate {
                    required property var model
                    width: ListView.view.width
                    contentItem: C.Label { textFormat: Text.PlainText; elide: Text.ElideRight; text: model.summary || model.applicationName }
                    onClicked: root.openTool("notifications")
                }
                C.Label { anchors.centerIn: parent; visible: alerts.count === 0; text: i18n("No recent notifications") }
            }
            Component.onCompleted: {
                runner.connectSource(root.helper + " notch-activity")
            }
            C.Label {
                Layout.fillWidth: true; visible: text.length > 0; textFormat: Text.PlainText
                elide: Text.ElideRight; text: root.agentSummary; Accessible.name: root.agentSummary
            }
            FolderListModel {
                id: arriving
                folder: root.downloadFolder
                showDirs: false; showDotAndDotDot: false; sortField: FolderListModel.Time; sortReversed: false
            }
            C.Label {
                Layout.fillWidth: true; visible: arriving.count > 0; elide: Text.ElideMiddle
                textFormat: Text.PlainText
                text: arriving.count ? i18n("Latest download · %1", arriving.get(0, "fileName")) : ""
            }
            RowLayout {
                C.Button { text: i18n("Downloads"); onClicked: root.openTool("downloads") }
                C.Button { text: i18n("Agent usage"); onClicked: root.openTool("agents") }
                C.Button { text: i18n("Watch"); onClicked: root.openTool("watch") }
            }
        }
    }
    Component {
        id: timerPage
        ColumnLayout {
            Item { Layout.fillHeight: true }
            C.Label {
                Layout.alignment: Qt.AlignHCenter; font.pointSize: 23
                text: root.endTime ? root.remaining() : i18n("Timer")
            }
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                C.SpinBox { id: minutes; visible: !root.endTime; from: 1; to: 1440; value: 25; editable: true; Accessible.name: i18n("Minutes") }
                C.Button { text: root.endTime ? i18n("Cancel") : i18n("Start"); onClicked: root.endTime ? root.stop(false) : root.start(minutes.value, false) }
                C.Button { visible: !root.endTime; text: i18n("Focus"); onClicked: root.start(minutes.value, true) }
            }
            C.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; visible: text.length > 0; text: root.message }
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                C.Label { text: root.duration((Plasmoid.configuration.watchElapsed + (root.watchStart ? root.now - root.watchStart : 0)) / 1000) }
                C.Button {
                    text: root.watchStart ? i18n("Pause") : i18n("Stopwatch")
                    onClicked: {
                        root.now = Date.now()
                        if (root.watchStart) {
                            Plasmoid.configuration.watchElapsed += Math.max(0, root.now - root.watchStart)
                            Plasmoid.configuration.watchStart = ""
                        } else Plasmoid.configuration.watchStart = String(root.now)
                    }
                }
                C.ToolButton { icon.name: "edit-reset"; Accessible.name: i18n("Reset stopwatch"); onClicked: { Plasmoid.configuration.watchStart = ""; Plasmoid.configuration.watchElapsed = 0 } }
            }
            Item { Layout.fillHeight: true }
        }
    }
    Component {
        id: calendarPage
        ColumnLayout {
            NoteStore { id: notes; helper: root.helper; Component.onCompleted: refresh() }
            Month {
                id: month
                Layout.fillWidth: true; Layout.fillHeight: true
                ink: Kirigami.Theme.textColor; dim: Kirigami.Theme.disabledTextColor; lily: Kirigami.Theme.highlightColor
                notesButton: false; store: notes
                onOpened: day => { edit.day = day; entry.text = notes.noteFor(day); edit.open() }
            }
            C.Dialog {
                id: edit
                property date day
                anchors.centerIn: parent
                width: Math.max(180, parent.width - 26)
                title: Qt.formatDate(day, Qt.locale().dateFormat(Locale.ShortFormat))
                standardButtons: C.Dialog.Save | C.Dialog.Cancel
                C.TextArea { id: entry; width: parent.width; wrapMode: TextEdit.Wrap; placeholderText: i18n("Day note") }
                onAccepted: notes.write(day, entry.text)
            }
        }
    }
}
