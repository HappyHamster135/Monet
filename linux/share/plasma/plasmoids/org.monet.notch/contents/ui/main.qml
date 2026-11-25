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
    readonly property string playingTrack: playing ? (media?.track || " ") : ""
    onPlayingTrackChanged: if (playingTrack) react("music")
    signal react(string kind)
    readonly property var tabNames: ["music", "activity", "time", "calendar", "notes", "camera", "clipboard"]
    readonly property var tabLabels: [i18n("Music"), i18n("Activity"), i18n("Time"), i18n("Calendar"), i18n("Notes"), i18n("Camera"), i18n("Clipboard")]
    ToolVisibility { id: tools }
    readonly property bool offerShelf: tools.offers("shelf")
    readonly property bool offerDownloads: tools.offers("downloads")
    readonly property bool offerAgents: tools.offers("agents")
    readonly property bool offerWatch: tools.offers("watch")
    onOfferShelfChanged: if (!offerShelf) viewingShelf = false
    onOfferDownloadsChanged: {
        if (!offerDownloads) { viewingDownloads = false; downloadAvailable = false }
        if (activityOpen) Qt.callLater(refreshActivity)
    }
    onOfferAgentsChanged: {
        if (!offerAgents) { agentsVisible = false; sessionSelected = false; codexKey = ""; claudeKey = "" }
        if (activityOpen) Qt.callLater(refreshActivity)
    }
    readonly property bool offerAgenda: tools.offers("calendars")
    readonly property bool offerMediaDetails: tools.offers("media")
    readonly property bool offerMixer: tools.offers("mixer")
    onOfferAgendaChanged: if (!offerAgenda) viewingAgenda = false
    onOfferMediaDetailsChanged: if (!offerMediaDetails && (musicView === 1 || musicView === 2)) musicView = 0
    onOfferMixerChanged: if (!offerMixer && musicView === 3) musicView = 0
    readonly property var visibleTabs: {
        const value = Plasmoid.configuration.tabs || ""
        if (value === "none") return []
        const ids = value.split(",").map(key => tabNames.indexOf(key))
        const ordered = ids.every((id, index) => id >= 0 && ids.indexOf(id) === index) ? ids : [0, 1, 2, 3, 4]
        return ordered.filter(id => (id !== 4 || tools.offers("notes")) && (id !== 5 || tools.offers("camera"))
                                    && (id !== 6 || tools.offers("clipboard")))
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
    property bool searching: false
    readonly property bool offerSearch: tools.offers("command-bar")
    onOfferSearchChanged: if (!offerSearch) searching = false
    property bool viewingShelf: false
    readonly property bool displayShelf: offerShelf && (viewingShelf || (!visibleTabs.length && !showingWatch))
    ShelfModel {
        id: fileShelf
        shown: root.expanded && root.displayShelf
        dragging: root.draggingShelf
        onFilesAdded: root.react("shelf")
    }
    function showShelf() {
        if (!offerShelf) return
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
        watchedService: root.offerWatch ? "org.monet.WindowWatch.n" + Plasmoid.id : ""
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
        enabled: root.activityOpen && root.offerAgents
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
        if (!activityOpen || !(offerDownloads || offerAgents)) return
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
        active: root.activityOpen && root.offerDownloads && root.downloadAvailable
        sourceComponent: DownloadFeed {
            directory: root.downloadFolder
            watchCompletions: Plasmoid.configuration.companion && Plasmoid.configuration.companionReactions === "on" && power.active
            onDownloadCompleted: root.react("download")
        }
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
        readonly property bool companionPower: Plasmoid.configuration.companion && Plasmoid.configuration.companionReactions === "on"
        property int previousPlug: -1
        function trackPlug() {
            const value = batteryState?.plugged
            const next = active && companionPower && powerReady && batteryState?.available && typeof value === "boolean" ? Number(value) : -1
            if (previousPlug === 0 && next === 1) root.react("charging")
            previousPlug = next
        }
        onBatteryStateChanged: trackPlug()
        onCompanionPowerChanged: trackPlug()
        onActiveChanged: trackPlug()
        observePower: Plasmoid.configuration.alerts || root.expanded || companionPower
        onBatteriesChanged: if (power.powerReady && Plasmoid.configuration.alerts) root.checkCharge()
        onPowerReadyChanged: {
            trackPlug()
            if (power.powerReady && Plasmoid.configuration.alerts) root.checkCharge()
        }
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
                root.react("battery")
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
        onFinished: message => {
            root.react("finish")
            runner.connectSource(root.helper + " ring " + root.hex(i18n("Monet Notch")) + " " + root.hex(message))
        }
        onActiveChanged: { root.message = ""; if (active) root.react(settings.focus ? "focus" : "timer") }
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
        if (!root.expanded) { searching = false; requestedNotice = 0; viewingDownloads = false; viewingShelf = false; return }
        tools.reload()
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
                    root.sessionSelected = root.offerAgents && !!state.sessionSelected
                    root.agentsVisible = root.offerAgents && state.agentsVisible !== false
                    root.codexKey = state.codexKey || ""
                    root.claudeKey = state.claudeKey || ""
                    root.downloadPath = state.path
                    root.downloadFolder = state.folder
                    root.downloadAvailable = root.offerDownloads && state.available && state.folder.startsWith("file:///")
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
        Accessible.description: companionLoader.item?.showing ? i18n("Notch companion") : ""
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
                visible: !companionLoader.item?.showing
                Layout.preferredHeight: 17; Layout.preferredWidth: 17
                source: shelfDrop.containsDrag ? "folder-add" : preview.item?.noticeId ? "notifications" : countdown.paused ? "media-playback-pause" : countdown.active ? "chronometer" : watch.registered ? "view-visible" : root.media ? "audio-x-generic" : "applications-utilities"
                color: "#9dd9c9"; isMask: true
            }
            Item {
                id: leftCompanion
                visible: companionLoader.parent === this && !!companionLoader.item?.showing
                Layout.preferredWidth: 22; Layout.preferredHeight: 24
            }
            C.Label {
                Layout.fillWidth: true; color: "#f6f3e9"; textFormat: Text.PlainText; elide: Text.ElideRight
                text: shelfDrop.containsDrag ? i18n("Shelf") : preview.item?.title || (countdown.active ? root.timerSummary : watch.registered ? i18n("Watching") : root.media?.track || i18n("Tools"))
            }
            Item {
                id: rightCompanion
                visible: companionLoader.parent === this && !!companionLoader.item?.showing
                Layout.preferredWidth: 22; Layout.preferredHeight: 24
            }
        }
        Loader {
            id: companionLoader
            parent: Plasmoid.configuration.companionSide === "right" ? rightCompanion : leftCompanion
            anchors.fill: parent
            active: Plasmoid.configuration.companion && power.active
            sourceComponent: NotchCompanion {
                presented: power.active && !preview.item?.noticeId && !shelfDrop.containsDrag
                styleName: Plasmoid.configuration.companionStyle
                shapeName: Plasmoid.configuration.companionShape
                paletteName: Plasmoid.configuration.companionColor
                side: Plasmoid.configuration.companionSide
                frequency: Plasmoid.configuration.companionVisits
                visits: frequency !== "off"
                reactions: Plasmoid.configuration.companionReactions === "on"
                hideIdle: Plasmoid.configuration.companionRest === "hide"
                Connections {
                    target: root
                    function onReact(kind) { companionLoader.item?.react(kind) }
                }
            }
        }
        NotchGestureSurface { gestures: notchGestures }
        DropArea {
            id: shelfDrop
            enabled: root.offerShelf
            anchors.fill: parent
            onEntered: drag => { drag.accepted = fileShelf.accepts(drag) }
            onDropped: drop => {
                if (fileShelf.addDrop(drop)) root.showShelf()
            }
        }
    }

    fullRepresentation: ColumnLayout {
        id: pages
        Shortcut {
            sequence: "Ctrl+K"
            enabled: root.expanded && root.offerSearch && !root.searching && !root.draggingShelf
            onActivated: root.searching = true
        }
        C.Popup {
            id: searchPopup
            parent: pages
            width: pages.width; height: pages.height
            padding: Kirigami.Units.smallSpacing
            background: Rectangle {
                radius: Kirigami.Units.cornerRadius
                color: Qt.alpha(Kirigami.Theme.backgroundColor, 0.92)
            }
            popupType: C.Popup.Item
            modal: true; dim: false; focus: true
            closePolicy: C.Popup.CloseOnEscape
            visible: root.expanded && root.searching
            onClosed: {
                root.searching = false
                if (root.expanded && searchButton.visible) searchButton.forceActiveFocus(Qt.BacktabFocusReason)
            }
            readonly property var session: power.nativeState ?? searchLock.item
            readonly property bool unlocked: !!session?.lockKnown && !session.locked
            onUnlockedChanged: if (visible && session?.lockKnown && session.locked) root.expanded = false
            Loader {
                id: searchLock
                active: searchPopup.visible && !power.nativeState
                sourceComponent: Component { CameraLock {} }
            }
            contentItem: Loader {
                id: commandView
                active: searchPopup.visible && searchPopup.unlocked && power.active
                source: "NotchSearch.qml"
                focus: true
                onLoaded: item.focusSearch()
            }
            Connections {
                target: commandView.item
                function onBackRequested() { root.searching = false }
                function onActivated() { root.expanded = false }
            }
            C.Button {
                anchors.centerIn: parent
                visible: commandView.status === Loader.Error || !searchPopup.unlocked
                text: searchPopup.unlocked ? i18n("Open Command Bar") : i18n("Back")
                onClicked: {
                    if (!searchPopup.unlocked) { root.searching = false; return }
                    root.expanded = false
                    DBus.SessionBus.asyncCall({service: "org.kde.krunner", path: "/App",
                        iface: "org.kde.krunner.App", member: "display"})
                }
            }
        }
        // The popup may still lack its own screen while its first layout runs.
        // Use the already-mapped panel so the tab row starts at its final width.
        Layout.preferredWidth: Math.min(422, Math.max(250, (root.Screen.width || 454) - 32))
        Layout.preferredHeight: root.searching || root.visibleTabs.length || root.displayShelf || root.showingWatch
            ? Math.min(370, Math.max(200, Screen.height - 80)) : implicitHeight
        spacing: Kirigami.Units.smallSpacing
        // The overlay is outside the layout. Keep the full reading area while its tabs are hidden.
        Item {
            visible: root.searching
            Layout.fillWidth: true; Layout.fillHeight: true
            Layout.minimumHeight: pages.Layout.preferredHeight
        }
        RowLayout {
            id: navigation
            visible: !root.searching && !root.viewingShelf && root.visibleTabs.length > 0
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            NotchTabs {
                id: strip
                Layout.fillWidth: true
                Layout.minimumWidth: 0
                tabs: root.visibleTabs; labels: root.tabLabels; page: root.tab
                onChosen: tab => { root.viewingWatch = false; root.tab = tab }
            }
            C.ToolButton {
                id: allTabs
                visible: strip.naturalWidth > navigation.width
                text: i18n("All tabs")
                display: C.AbstractButton.IconOnly
                icon.name: "arrow-down"
                onClicked: tabMenu.open()
                C.ToolTip.visible: hovered
                C.ToolTip.text: text
                C.Menu {
                    id: tabMenu
                    y: allTabs.height
                    onOpened: {
                        currentIndex = root.visibleTabs.indexOf(root.tab)
                        itemAt(currentIndex)?.forceActiveFocus(Qt.PopupFocusReason)
                    }
                    Instantiator {
                        model: root.visibleTabs
                        delegate: C.MenuItem {
                            required property int modelData
                            text: root.tabLabels[modelData]
                            checkable: true
                            checked: root.tab === modelData
                            onTriggered: strip.chosen(modelData)
                        }
                        onObjectAdded: (index, item) => tabMenu.insertItem(index, item)
                        onObjectRemoved: (index, item) => tabMenu.removeItem(item)
                    }
                }
            }
        }
        Loader {
            Layout.fillWidth: true; Layout.fillHeight: true
            visible: active && !root.searching
            active: root.expanded && (root.visibleTabs.length > 0 || root.displayShelf || root.showingWatch)
            sourceComponent: root.displayShelf ? shelfPage : root.showingWatch ? watchPage
                : root.tab === 1 && root.viewingDownloads ? downloadsPage
                : root.tab === 3 && root.viewingAgenda ? agendaPage
                : root.tab === 0 && root.musicView === 3 ? mixerPage
                : root.tab === 6 ? clipboardPage
                : root.tab === 5 ? cameraPage
                : root.tab === 4 ? (padController.item ? padPage : null) : [musicPage, activityPage, timerPage, calendarPage][root.tab] ?? null
        }
        RowLayout {
            visible: !root.searching && (!root.viewingShelf || !root.visibleTabs.length)
            Layout.fillWidth: true
            C.Button { visible: root.offerShelf && root.visibleTabs.length > 0; text: i18n("File shelf"); icon.name: "folder-open"; onClicked: root.showShelf() }
            Item { Layout.fillWidth: true }
            C.ToolButton {
                id: searchButton
                visible: root.offerSearch
                icon.name: "system-search"
                text: i18n("Command Bar")
                display: C.AbstractButton.IconOnly
                C.ToolTip.visible: hovered
                C.ToolTip.text: text
                onClicked: root.searching = true
            }
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
    Component {
        id: clipboardPage
        Item {
            id: clipboardView
            readonly property var session: power.nativeState ?? portableLock.item
            readonly property bool unlocked: !!session?.lockKnown && !session.locked
            onUnlockedChanged: if (session?.lockKnown && session.locked) root.expanded = false
            Loader {
                id: portableLock
                active: !power.nativeState
                sourceComponent: Component { CameraLock {} }
            }
            Loader {
                id: history
                anchors.fill: parent
                active: !root.searching && clipboardView.unlocked && power.active
                source: "NotchClipboard.qml"
                focus: true
                onLoaded: item.forceActiveFocus(Qt.OtherFocusReason)
            }
            Connections {
                target: history.item
                function onRequestHidePopup() { root.expanded = false }
            }
            C.Label {
                anchors.centerIn: parent
                width: parent.width
                visible: history.status === Loader.Error || !clipboardView.unlocked
                text: i18n("Clipboard history is unavailable.")
                wrapMode: Text.Wrap
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }
    Component {
        id: cameraPage
        CameraMirror {
            presented: root.expanded && !root.searching && power.active
            session: power.nativeState
        }
    }
    Component { id: padPage; Scratchpad { pads: padController.item } }
    Component {
        id: musicPage
        Music {
            media: root.media; playing: root.playing; view: root.musicView
            gestures: notchGestures
            offerDetails: root.offerMediaDetails; offerMixer: root.offerMixer
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
            offerShelf: root.offerShelf
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
                C.Button { visible: root.offerDownloads; text: i18n("Downloads"); onClicked: root.viewingDownloads = true }
                C.Button { visible: root.agentsVisible && !root.codexKey && !root.claudeKey; text: i18n("Agent usage"); onClicked: root.openTool("agents") }
                C.Button {
                    visible: root.offerWatch
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
                visible: root.offerAgenda
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
