import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5
import org.kde.plasma.private.mpris as Mpris
import org.kde.notificationmanager as NM
import org.kde.plasma.workspace.dbus as DBus

PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    preferredRepresentation: compactRepresentation
    readonly property string helper: "@LIBEXECDIR@/monet-quick"
    readonly property var media: players.count ? players.itemAt(0)?.model ?? null : null
    readonly property bool playing: media?.playbackStatus === Mpris.PlaybackStatus.Playing
    readonly property double endTime: countdown.deadline
    readonly property double watchStart: Number(Plasmoid.configuration.watchStart) || 0
    property double now: Date.now()
    readonly property var tabNames: ["music", "activity", "time", "calendar", "notes"]
    readonly property var tabLabels: [i18n("Music"), i18n("Activity"), i18n("Time"), i18n("Calendar"), i18n("Notes")]
    readonly property var visibleTabs: {
        const value = Plasmoid.configuration.tabs || ""
        if (value === "none") return []
        const ids = value.split(",").map(key => tabNames.indexOf(key))
        return ids.every((id, index) => id >= 0 && ids.indexOf(id) === index) ? ids : [0, 1, 2, 3, 4]
    }
    readonly property bool hasActivity: visibleTabs.includes(1)
    property int tab: 0
    function selectVisibleTab() {
        if (!expanded || !visibleTabs.includes(tab)) tab = visibleTabs[0] ?? -1
    }
    onVisibleTabsChanged: selectVisibleTab()
    property bool draggingShelf: false
    // Wayland destinations can read the URI list after the pointer leaves the popup.
    hideOnWindowDeactivate: !draggingShelf
    property bool viewingShelf: false
    readonly property bool displayShelf: viewingShelf || (!visibleTabs.length && !showingWatch)
    ShelfModel {
        id: fileShelf
        shown: root.expanded && root.displayShelf
        dragging: root.draggingShelf
    }
    function showShelf() {
        viewingShelf = true
        expanded = true
    }
    property int requestedNotice: 0
    Loader {
        id: preview
        active: (!root.expanded || root.requestedNotice > 0) && root.hasActivity && Plasmoid.configuration.previews && power.active
                && !!power.nativeState?.lockKnown && !power.nativeState.locked && !NM.Server.inhibited
        source: "NoticePreview.qml"
        onLoaded: item.watching = Qt.binding(() => !root.expanded)
    }
    function openPill() {
        if (!expanded && preview.item?.noticeId) {
            requestedNotice = preview.item.noticeId
            viewingWatch = false
            viewingDownloads = false
            tab = 1
        }
        expanded = !expanded
    }
    property bool padsOpened: false
    readonly property bool padShown: expanded && !viewingShelf && !showingWatch && tab === 4
    onPadShownChanged: if (padShown) padsOpened = true
    onTabChanged: if (tab !== 1) requestedNotice = 0
    Loader {
        id: padController
        active: root.padsOpened
        sourceComponent: PadModel {
            shown: root.padShown
            onDetached: root.expanded = false
        }
    }
    property int musicView: 0
    property var outputNames: []
    property bool viewingAgenda: false
    property date agendaDay: new Date()
    property bool viewingWatch: false
    readonly property bool showingWatch: !viewingShelf && viewingWatch && watch.registered && (tab === 1 || !hasActivity)
    readonly property string watchPath: "/WindowWatch/n" + Plasmoid.id
    DBus.DBusServiceWatcher {
        id: watch
        busType: DBus.BusType.Session
        watchedService: "org.monet.WindowWatch.n" + Plasmoid.id
        onRegisteredChanged: {
            root.viewingWatch = registered
            if (registered && root.hasActivity) root.tab = 1
        }
    }
    Component.onDestruction: {
        if (watch.registered)
            DBus.SessionBus.asyncCall({service: watch.watchedService, path: root.watchPath,
                iface: "org.monet.WindowWatch", member: "Stop"})
    }
    property string message: ""
    property bool sessionSelected: false
    property string codexKey: ""
    property string claudeKey: ""
    property bool agentsVisible: false
    DBus.SignalWatcher {
        enabled: root.activityOpen
        busType: DBus.BusType.Session; service: "org.monet.Utilities"
        path: "/Utilities"; iface: "org.monet.Utilities"
        function dbusCodexLimitsChanged(key) { root.codexKey = key; if (root.checkingDownloads) root.refreshPending = true }
        function dbusClaudeLimitsChanged(key) { root.claudeKey = key; if (root.checkingDownloads) root.refreshPending = true }
        function dbusAgentFileChanged(selected) {
            root.sessionSelected = selected
            if (root.checkingDownloads) root.refreshPending = true
        }
        function dbusAgentVisibilityChanged() {
            root.sessionSelected = false; root.agentsVisible = false
            root.refreshActivity()
        }
    }
    property bool viewingDownloads: false
    property bool checkingDownloads: false
    property bool refreshPending: false
    property string downloadPath: ""
    property url downloadFolder: ""
    property bool downloadAvailable: false
    readonly property bool activityOpen: expanded && !viewingShelf && tab === 1 && !(viewingWatch && watch.registered)
    function refreshActivity() {
        if (checkingDownloads) { refreshPending = true; return }
        checkingDownloads = true
        runner.connectSource(helper + " notch-activity")
    }
    onActivityOpenChanged: {
        if (activityOpen) refreshActivity()
        else {
            downloadAvailable = false; downloadPath = ""; downloadFolder = ""
            codexKey = ""; claudeKey = ""; agentsVisible = false; sessionSelected = false
        }
    }
    Loader {
        id: downloadFeed
        active: root.activityOpen && root.downloadAvailable
        sourceComponent: DownloadFeed { directory: root.downloadFolder }
    }
    toolTipMainText: i18n("Monet Notch")
    toolTipSubText: preview.item?.title ? [preview.item.sender, preview.item.title].filter(Boolean).join(" · ") : countdown.active ? timerSummary : watch.registered ? i18n("Watching a window") : media?.track || i18n("Music, activity and tools")
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
    readonly property string timerSummary: countdown.waiting ? (countdown.onBreak ? i18n("Break ready") : i18n("Focus ready"))
        : duration(Math.ceil(countdown.remaining(now) / 1000))
    function hex(text) {
        return Array.from(unescape(encodeURIComponent(text)), c => c.charCodeAt(0).toString(16).padStart(2, "0")).join("")
    }
    function openTool(page) {
        runner.connectSource(helper + " utilities " + page)
        expanded = false
    }
    NotchTimer {
        id: countdown
        settings: Plasmoid.configuration
        onDeadlineChanged: if (deadline) root.now = Date.now()
        onQuietRequested: until => {
            root.desiredQuiet = until
            if (!root.quietCommand) root.applyQuiet()
        }
        onFinished: message => runner.connectSource(root.helper + " ring " + root.hex(i18n("Monet Notch")) + " " + root.hex(message))
        onActiveChanged: root.message = ""
    }
    // Apply only the latest request after an in-flight helper returns. A quick
    // pause followed by Resume must never leave the newer session unmuted.
    property double desiredQuiet: 0
    property double sentQuiet: 0
    property string quietCommand: ""
    function applyQuiet() {
        sentQuiet = desiredQuiet
        quietCommand = helper + " notch-focus " + (sentQuiet || "off") + " " + Plasmoid.id
        runner.connectSource(quietCommand)
    }
    function refreshTime() {
        now = Date.now()
        countdown.finishIfDue(now)
    }
    Timer {
        interval: 1000; repeat: true
        running: !!root.endTime || (root.expanded && !root.displayShelf && !root.showingWatch && root.tab === 2 && !!root.watchStart)
        onTriggered: root.refreshTime()
    }
    Component.onCompleted: { selectVisibleTab(); refreshTime() }
    onExpandedChanged: {
        if (!root.expanded) { requestedNotice = 0; viewingDownloads = false; viewingShelf = false; return }
        agendaDay = new Date()
        refreshTime()
        if (requestedNotice || viewingShelf) return
        if (countdown.active && visibleTabs.includes(2)) tab = 2
        else if (watch.registered) {
            viewingWatch = true
            if (hasActivity) tab = 1
        }
    }
    P5.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            if (source === root.helper + " outputs") {
                try { root.outputNames = JSON.parse(data.stdout) } catch (_) {}
            }
            if (source.endsWith(" notch-activity")) {
                root.checkingDownloads = false
                if (root.refreshPending) {
                    root.refreshPending = false
                    if (root.activityOpen) Qt.callLater(root.refreshActivity)
                    return
                }
                if (!root.activityOpen) return
                try {
                    const state = JSON.parse(data.stdout)
                    root.sessionSelected = !!state.sessionSelected
                    root.agentsVisible = state.agentsVisible !== false
                    root.codexKey = state.codexKey || ""
                    root.claudeKey = state.claudeKey || ""
                    root.downloadPath = state.path
                    root.downloadFolder = state.folder
                    root.downloadAvailable = state.available && state.folder.startsWith("file:///")
                } catch (_) { root.downloadAvailable = false }
            }
            if (source === root.quietCommand) {
                root.quietCommand = ""
                if (root.sentQuiet !== root.desiredQuiet) {
                    root.applyQuiet()
                } else {
                    let ok = false
                    try { ok = JSON.parse(data.stdout).ok } catch (_) {}
                    root.message = ok ? "" : root.sentQuiet ? i18n("Quiet mode was unavailable. Your timer is running.")
                        : i18n("Could not restore the previous notification setting.")
                }
            }
        }
    }
    NotchGestures {
        id: notchGestures
        enabled: Plasmoid.configuration.gestures
        expanded: root.expanded
        onExpansionRequested: open => { if (open !== root.expanded) root.openPill() }
        onTrackRequested: next => {
            const player = root.media?.container
            if (next && player?.canGoNext) player.Next()
            else if (!next && player?.canGoPrevious) player.Previous()
        }
    }
    compactRepresentation: C.AbstractButton {
        id: pill
        Layout.minimumWidth: Plasmoid.configuration.wide ? 176 : 96
        Layout.maximumWidth: Layout.minimumWidth
        Layout.preferredWidth: Layout.minimumWidth
        Accessible.name: root.toolTipMainText + ". " + root.toolTipSubText
        onClicked: root.openPill()
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
                visible: !Plasmoid.configuration.companion || !!preview.item?.noticeId
                Layout.preferredHeight: 17; Layout.preferredWidth: 17
                source: shelfDrop.containsDrag ? "folder-add" : preview.item?.noticeId ? "notifications" : countdown.paused ? "media-playback-pause" : countdown.active ? "chronometer" : watch.registered ? "view-visible" : root.media ? "audio-x-generic" : "applications-utilities"
                color: "#9dd9c9"; isMask: true
            }
            C.Label {
                visible: Plasmoid.configuration.companion && !preview.item?.noticeId
                text: shelfDrop.containsDrag ? "✿" : root.playing ? "♫" : "◕‿◕"
                color: "#a8ddc8"
                Accessible.name: i18n("Notch companion")
            }
            C.Label {
                Layout.fillWidth: true; color: "#f6f3e9"; textFormat: Text.PlainText; elide: Text.ElideRight
                text: shelfDrop.containsDrag ? i18n("Shelf") : preview.item?.title || (countdown.active ? root.timerSummary : watch.registered ? i18n("Watching") : root.media?.track || i18n("Tools"))
            }
        }
        NotchGestureSurface { gestures: notchGestures }
        DropArea {
            id: shelfDrop
            anchors.fill: parent
            onEntered: drag => { drag.accepted = fileShelf.accepts(drag) }
            onDropped: drop => {
                if (fileShelf.accepts(drop)) {
                    fileShelf.change("add", Array.from(drop.urls))
                    root.showShelf()
                    drop.accept(Qt.CopyAction)
                }
            }
        }
    }

    fullRepresentation: ColumnLayout {
        Layout.preferredWidth: Math.min(422, Math.max(250, Screen.width - 32))
        Layout.preferredHeight: Math.min(370, Math.max(200, Screen.height - 80))
        spacing: Kirigami.Units.smallSpacing
        NotchTabs {
            visible: !root.viewingShelf && tabs.length > 0
            Layout.fillWidth: true
            tabs: root.visibleTabs; labels: root.tabLabels; page: root.tab
            onChosen: tab => { root.viewingWatch = false; root.tab = tab }
        }
        Loader {
            Layout.fillWidth: true; Layout.fillHeight: true
            active: root.expanded
            sourceComponent: root.displayShelf ? shelfPage : root.showingWatch ? watchPage
                : root.tab === 1 && root.viewingDownloads ? downloadsPage
                : root.tab === 3 && root.viewingAgenda ? agendaPage
                : root.tab === 0 && root.musicView === 3 ? mixerPage
                : root.tab === 4 ? (padController.item ? padPage : null) : [musicPage, activityPage, timerPage, calendarPage][root.tab] ?? null
        }
        RowLayout {
            visible: !root.viewingShelf || !root.visibleTabs.length
            Layout.fillWidth: true
            C.Button { visible: root.visibleTabs.length > 0; text: i18n("File shelf"); icon.name: "folder-open"; onClicked: root.showShelf() }
            Item { Layout.fillWidth: true }
            C.Button { text: i18n("Utilities"); icon.name: "applications-utilities"; onClicked: root.openTool("tools") }
        }
    }
    Component {
        id: shelfPage
        FileShelf {
            shelf: fileShelf
            canGoBack: root.visibleTabs.length > 0
            onDraggingChanged: root.draggingShelf = dragging
            Component.onDestruction: root.draggingShelf = false
            onBackRequested: root.viewingShelf = false
            onDetachRequested: root.openTool("shelf")
        }
    }
    Component {
        id: mixerPage
        ColumnLayout {
            RowLayout {
                C.ToolButton { icon.name: "go-previous"; Accessible.name: i18n("Now playing"); onClicked: root.musicView = 0 }
                C.Label { text: i18n("Volume mixer"); font.bold: true }
            }
            Loader {
                id: mixerLoader
                Layout.fillWidth: true; Layout.fillHeight: true
                source: "VolumeMixer.qml"
                onLoaded: {
                    item.outputNames = Qt.binding(() => root.outputNames)
                    namesDelay.restart()
                }
                Connections {
                    target: mixerLoader.item
                    function onOutputsChangedWhileOpen() { namesDelay.restart() }
                }
                Timer {
                    id: namesDelay
                    interval: 80
                    onTriggered: runner.connectSource(root.helper + " outputs")
                }
            }
            C.Label { visible: mixerLoader.status === Loader.Error; Layout.fillWidth: true; wrapMode: Text.Wrap; text: i18n("The volume mixer could not open.") }
        }
    }
    Component { id: padPage; Scratchpad { pads: padController.item } }
    Component {
        id: musicPage
        Music {
            media: root.media; playing: root.playing; view: root.musicView
            gestures: notchGestures
            onViewRequested: index => root.musicView = index
        }
    }
    Component {
        id: watchPage
        Watch {
            service: watch.watchedService; path: root.watchPath
            onBackRequested: root.viewingWatch = false
            onEditing: root.expanded = false
        }
    }
    Component {
        id: downloadsPage
        Downloads {
            feed: downloadFeed.item
            localPath: root.downloadPath
            directory: root.downloadFolder
            checking: root.checkingDownloads
            opener: FolderOpenController {}
            onBackRequested: root.viewingDownloads = false
            onRefreshRequested: { root.downloadAvailable = false; root.refreshActivity() }
            onManageRequested: root.openTool("downloads")
        }
    }
    Component {
        id: activityPage
        ColumnLayout {

            Repeater {
                model: notices.inDetail ? [] : power.batteries
                C.Label {
                    required property var modelData
                    Layout.fillWidth: true; elide: Text.ElideRight; textFormat: Text.PlainText
                    text: i18n("%1 · %2%", modelData.name || modelData.kind, modelData.level)
                }
            }
            NoticeInbox {
                id: notices
                Layout.fillWidth: true; Layout.fillHeight: true
                requestedNotice: root.requestedNotice
                liveSource: root.requestedNotice ? preview.item : null
                onPreviewFinished: root.requestedNotice = 0
                onActivated: root.expanded = false
            }
            SessionButton {
                Layout.fillWidth: true
                widgetId: String(Plasmoid.id)
                active: root.agentsVisible && root.sessionSelected && root.activityOpen && power.active
                        && !root.viewingDownloads && !notices.inDetail
                onClicked: {
                    runner.connectSource(root.helper + " utilities agents session")
                    root.expanded = false
                }
            }
            Repeater {
                model: ["codex", "claude"]
                delegate: AccountLimitButton {
                    required property string modelData
                    Layout.fillWidth: true
                    active: root.agentsVisible && root.activityOpen && !root.viewingDownloads && !notices.inDetail
                    generation: modelData === "claude" ? root.claudeKey : root.codexKey
                    command: root.helper + " notch-" + modelData + "-limits"
                    pendingLabel: modelData === "claude" ? i18n("Checking Claude Code limits…") : i18n("Checking Codex limits…")
                    onPreferencesChanged: root.refreshActivity()
                    onClicked: {
                        runner.connectSource(root.helper + " utilities agents " + modelData)
                        root.expanded = false
                    }
                }
            }
            C.Label {
                readonly property string latestName: downloadFeed.item?.latestFinished ?? ""
                Layout.fillWidth: true; visible: !notices.inDetail && !!latestName; elide: Text.ElideMiddle
                textFormat: Text.PlainText
                text: latestName ? i18n("Latest download · %1", latestName) : ""
            }
            RowLayout {
                visible: !notices.inDetail
                C.Button { text: i18n("Downloads"); onClicked: root.viewingDownloads = true }
                C.Button { visible: root.agentsVisible && !root.codexKey && !root.claudeKey; text: i18n("Agent usage"); onClicked: root.openTool("agents") }
                C.Button {
                    text: i18n("Watch")
                    onClicked: {
                        if (watch.registered) root.viewingWatch = true
                        else {
                            runner.connectSource(root.helper + " utilities watch " + Plasmoid.id)
                            root.expanded = false
                        }
                    }
                }
            }
        }
    }
    Component {
        id: timerPage
        TimePage { timer: countdown; now: root.now; message: root.message; formatDuration: root.duration }
    }
    Component {
        id: agendaPage
        Agenda {
            day: root.agendaDay
            onChoose: date => root.agendaDay = date
            onMonthRequested: root.viewingAgenda = false
            onCalendarsRequested: root.openTool("calendars")
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
                Component.onCompleted: choose(root.agendaDay)
                onOpened: day => { edit.day = day; entry.text = notes.noteFor(day); edit.open() }
            }
            C.Button {
                Layout.alignment: Qt.AlignHCenter
                text: i18n("Upcoming appointments")
                icon.name: "view-calendar-agenda"
                onClicked: { root.agendaDay = month.chosen; root.viewingAgenda = true }
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
