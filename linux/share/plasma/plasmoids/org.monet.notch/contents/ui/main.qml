import QtQuick
import QtQuick.Layouts
import "IslandLayout.js" as IslandLayout
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
    // Plasma instantiates the compact item only for applets with both representations.
    fullRepresentation: Item {}
    preferredRepresentation: compactRepresentation
    property bool islandOpen: false
    property bool folding: false
    property bool pinned: false
    readonly property bool combined: Plasmoid.configuration.combined && timerStrip && !!media && visibleTabs.includes(0)
    property bool overview: true
    property bool prepareSections: false
    onOverviewChanged: if (overview && islandOpen) prepareSections = true
    property string utilityPage: ""
    // Kirigami reports one millisecond when desktop animations are disabled.
    readonly property bool motion: Kirigami.Units.longDuration > 1
    readonly property bool editing: !!Plasmoid.containment?.corona.editMode
    readonly property bool ownEdge: Plasmoid.location === PlasmaCore.Types.TopEdge && Plasmoid.containment?.applets.length === 1
    readonly property int surfaceWidth: Math.min(464, Math.max(1, (root.Screen.width || 648) - 16))
    readonly property bool railSpace: ownEdge && root.Screen.width >= surfaceWidth + 112
    readonly property int restWidth: Plasmoid.configuration.wide ? 244 : 178
    readonly property var panelSurface: pages
    Binding {
        target: Plasmoid.containment
        property: "backgroundHints"
        when: root.ownEdge && !root.editing
        value: PlasmaCore.Types.NoBackground
        restoreMode: Binding.RestoreBindingOrValue
    }
    function collapse() {
        if (folding || !islandOpen) return
        if (!motion) { islandOpen = false; return }
        folding = true
        pages.animateTo(0)
    }
    function preparePage(key) {
        if (islandOpen && (key === "music" || key === "time"))
            body.anticipated = key === "music" ? musicPage : timerPage
    }
    function choose(key) {
        overview = false
        utilityPage = ""
        viewingShelf = false; viewingWatch = false; viewingDownloads = false; viewingAwake = false
        viewingAgenda = false; requestedNotice = 0; musicView = 0
        if (["controls","system","together","captures"].includes(key)) utilityPage = key
        else if (key === "files") viewingShelf = true
        else if (key === "downloads") { tab = 1; viewingDownloads = true }
        else if (key === "mixer") { tab = 0; musicView = 3 }
        else tab = tabNames.indexOf(key)
        body.resolve()
    }
    readonly property var sections: {
        let rows = []
        function add(key, label, icon, color) { rows.push({key, label, icon, color}) }
        if (tools.offers("sound") || tools.offers("display")) add("controls", i18n("Controls"), "configure", "#e0e0e5")
        if (combined) add("together", i18n("Music and timer"), "chronometer", "#ffad54")
        const icons = ["media-playback-start","notifications","chronometer","view-calendar","document-edit","camera-web","edit-paste"]
        const colors = ["#ff6485","#a8b7ff","#ff9f38","#ff716b","#ffcf69","#95d5ff","#c29fff"]
        for (const id of visibleTabs) {
            add(tabNames[id], tabLabels[id], icons[id], colors[id])
            if (id === 0 && offerMixer) add("mixer", i18n("Volume mixer"), "audio-volume-high", "#a1d9ff")
            if (id === 1 && offerDownloads) add("downloads", i18n("Downloads"), "go-down-symbolic", "#79d3aa")
        }
        if (tools.offers("screenshot") || tools.offers("recordings")) add("captures", i18n("Recent captures"), "camera-photo", "#bbdeee")
        if (offerShelf) add("files", i18n("File shelf"), "folder-open", "#75b9ff")
        if (tools.offers("processes")) add("system", i18n("System"), "view-statistics-symbolic", "#aba6ff")
        return rows
    }
    onSectionsChanged: if (utilityPage && !sections.some(item => item.key === utilityPage)) {
        utilityPage = ""; overview = true
    }
    readonly property string pageTitle: overview ? i18n("Sections") : utilityPage === "controls" ? i18n("Controls")
        : utilityPage === "captures" ? i18n("Recent captures") : utilityPage === "system" ? i18n("System") : utilityPage === "together" ? i18n("Music and timer") : displayShelf ? i18n("File shelf") : showingWatch ? i18n("Watch")
        : viewingDownloads ? i18n("Downloads") : tab === 0 && musicView === 3 ? i18n("Volume mixer") : tabLabels[tab] || i18n("Sections")
    // Keep keyboard activation through Plasma on a custom, edge-attached surface.
    onExpandedChanged: if (expanded) { expanded = false; openPill() }

    readonly property string helper: "@LIBEXECDIR@/monet-quick"
    readonly property var media: players.currentPlayer
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
    readonly property bool offerAwake: tools.offers("awake") && visibleTabs.includes(2)
    property bool viewingAwake: false
    readonly property bool timerStrip: visibleTabs.includes(2) && (!!countdown.completion || countdown.waiting
        || (Plasmoid.configuration.countdown && countdown.active))
    readonly property bool timePageVisible: islandOpen && !overview && !utilityPage && !searching && !displayShelf && !showingWatch && !viewingAwake && tab === 2
    readonly property bool awakeStrip: !!(Plasmoid.configuration.awake && awakeModel.item?.active
        && !timerStrip && !watch.registered && (awakeModel.item.state.duration || !playing))
    onCombinedChanged: if (!combined && utilityPage === "together") { utilityPage = ""; overview = true }
    onOfferAwakeChanged: if (!offerAwake) viewingAwake = false
    Loader {
        id: awakeModel
        active: root.offerAwake && power.active && (Plasmoid.configuration.awake || root.viewingAwake)
        source: "NotchAwake.qml"
    }
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
    Loader {
        id: queuePlayback
        active: false
        source: "QueuePlayback.qml"
    }
    onMusicViewChanged: if (musicView === 2) queuePlayback.active = true
    readonly property bool offerMixer: tools.offers("mixer")
    onOfferAgendaChanged: if (!offerAgenda) viewingAgenda = false
    onOfferMediaDetailsChanged: if (!offerMediaDetails) {
        if (musicView === 1 || musicView === 2) musicView = 0
        queuePlayback.active = false
    }
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
        if (!islandOpen || !visibleTabs.includes(tab)) tab = visibleTabs[0] ?? -1
    }
    onVisibleTabsChanged: selectVisibleTab()
    property bool draggingShelf: false
    // Wayland destinations can read the URI list after the pointer leaves the popup.

    property bool searching: false
    readonly property bool offerSearch: tools.offers("command-bar")
    onOfferSearchChanged: if (!offerSearch) searching = false
    property bool viewingShelf: false
    readonly property bool displayShelf: offerShelf && (viewingShelf || (!visibleTabs.length && !showingWatch))
    ShelfModel {
        id: fileShelf
        shown: root.islandOpen && root.displayShelf
        dragging: root.draggingShelf
        onFilesAdded: root.react("shelf")
    }
    function showShelf() {
        if (!offerShelf) return
        islandOpen = true
        choose("files")
    }
    property int requestedNotice: 0
    Loader {
        id: preview
        active: (!root.islandOpen || root.requestedNotice > 0) && root.hasActivity && Plasmoid.configuration.previews && power.active
                && !!power.nativeState?.lockKnown && !power.nativeState.locked && !NM.Server.inhibited
        source: "NoticePreview.qml"
        onLoaded: item.watching = Qt.binding(() => !root.islandOpen)
    }
    function openPill() {
        if (folding) { folding = false; pages.animateTo(1); return }
        if (islandOpen) { collapse(); return }
        const notice = preview.item?.noticeId || 0
        const toAwake = awakeStrip
        if (notice) { choose("activity"); requestedNotice = notice }
        else if (combined) choose("together")
        else if (timerStrip) choose("time")
        else if (watch.registered) { overview = false; viewingWatch = true; if (hasActivity) tab = 1 }
        else if (toAwake) { choose("time"); viewingAwake = true }
        else if (playing && visibleTabs.includes(0)) choose("music")
        islandOpen = true
    }
    property bool padsOpened: false
    readonly property bool padShown: islandOpen && !overview && !utilityPage && !viewingShelf && !showingWatch && tab === 4
    onPadShownChanged: if (padShown) padsOpened = true
    onTabChanged: {
        if (tab !== 1) requestedNotice = 0
        if (tab !== 2) viewingAwake = false
    }
    Loader {
        id: padController
        active: root.padsOpened
        sourceComponent: PadModel {
            shown: root.padShown
            onDetached: root.islandOpen = false
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
    readonly property bool activityOpen: islandOpen && !overview && !utilityPage && !viewingShelf && tab === 1 && !(viewingWatch && watch.registered)
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
    toolTipSubText: preview.item?.title ? [preview.item.sender, preview.item.title].filter(Boolean).join(" · ")
        : timerStrip ? timerSummary : watch.registered ? i18n("Watching a window")
        : awakeStrip ? i18n("Keep awake") + " · " + awakeModel.item.statusText : media?.track || i18n("Music, activity and tools")
    Mpris.Mpris2Model { id: players }
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
        onActiveChanged: { if (!active && root.islandOpen) root.islandOpen = false; trackPlug(); if (active && root.endTime) Qt.callLater(root.refreshTime) }
        observePower: Plasmoid.configuration.alerts || root.islandOpen || companionPower
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
    readonly property string timerSummary: countdown.completion || (countdown.waiting ? (countdown.onBreak ? i18n("Break ready") : i18n("Focus ready"))
        : duration(Math.ceil(countdown.remaining(now) / 1000)))
    function hex(text) {
        return Array.from(unescape(encodeURIComponent(text)), c => c.charCodeAt(0).toString(16).padStart(2, "0")).join("")
    }
    function openTool(page) {
        runner.connectSource(helper + " utilities " + page)
        islandOpen = false
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
    // Draw seconds only when someone can see them. A hidden timer schedules
    // its deadline and checks the wall clock at most once a minute until then.
    readonly property bool showSeconds: power.active && (timePageVisible
        || (timerStrip && !preview.item?.noticeId))
    Timer {
        id: clockTick
        interval: root.showSeconds ? 1000 : Math.max(1, Math.min(60000, root.endTime - root.now))
        repeat: true
        running: !!root.endTime || (root.timePageVisible && power.active && !!root.watchStart)
        onTriggered: root.refreshTime()
    }
    onShowSecondsChanged: if (showSeconds && (endTime || watchStart)) Qt.callLater(refreshTime)
    Component.onCompleted: { selectVisibleTab(); refreshTime() }
    onIslandOpenChanged: {
        if (!islandOpen) {
            folding = false; pinned = false; pages.resetReveal(); overview = true; utilityPage = ""
            viewingAwake = false; searching = false; requestedNotice = 0; viewingDownloads = false; viewingShelf = false
            return
        }
        if (overview) prepareSections = true
        tools.reload()
        agendaDay = new Date()
        refreshTime()

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
        expanded: root.islandOpen
        onExpansionRequested: open => { if (open !== root.islandOpen) root.openPill() }
        onTrackRequested: next => {
            const player = root.media
            if (next && player?.canGoNext) player.Next()
            else if (!next && player?.canGoPrevious) player.Previous()
        }
    }
    compactRepresentation: C.AbstractButton {
        id: pill
        readonly property alias edgeAnchor: edge
        Item {
            id: edge
            width: 1; height: 1
            x: (parent.width - width) / 2
            y: (parent.height - (pill.Window.window?.height ?? parent.height)) / 2
        }
        Item {
            id: leftAnchor
            width: 1; height: parent.height
            x: (parent.width - root.surfaceWidth) / 2 - 23
        }
        Item {
            id: rightAnchor
            width: 1; height: parent.height
            x: (parent.width + root.surfaceWidth) / 2 + 22
        }
        IslandRail {
            id: leftRail
            visualParent: leftAnchor
            presented: popup.visible && root.railSpace && !root.editing
            reveal: pages.revealProgress
            entries: [{key: "sections", label: i18n("Sections"), icon: "view-grid"}].concat(
                root.visibleTabs.includes(2) ? [{key: "time", label: i18n("Time"), icon: "chronometer"}] : [])
            onPreviewRequested: key => root.preparePage(key)
            onSelected: key => { if (key === "sections") pages.showSections(); else root.choose(key) }
        }
        IslandRail {
            id: rightRail
            visualParent: rightAnchor
            presented: popup.visible && root.railSpace && !root.editing
            reveal: pages.revealProgress
            entries: root.sections.filter(item => ["controls", "mixer", "files"].includes(item.key))
            onSelected: key => root.choose(key)
        }
        HoverHandler {
            id: overPill
            blocking: false
            onHoveredChanged: {
                if (hovered && !root.editing) root.prepareSections = true
                else if (!hovered) leavePill.restart()
            }
        }
        Timer { id: leavePill; interval: 160 }
        // On its own panel the compact face stays in place until the new surface actually covers it.
        readonly property bool sharedOpen: root.islandOpen && !root.ownEdge
        readonly property real covered: root.islandOpen && root.ownEdge ? Math.min(1, pages.revealProgress * 4) : 0
        readonly property bool glance: (overPill.hovered || quickButtons.underPointer || leavePill.running || visualFocus) && !root.editing && !sharedOpen && covered < 1
        readonly property bool activeStrip: shelfDrop.containsDrag || preview.item?.noticeId > 0 || root.timerStrip || watch.registered || root.awakeStrip || !!root.media
        readonly property bool titleVisible: sharedOpen || glance || !!preview.item?.noticeId || root.timerStrip || watch.registered || root.awakeStrip || shelfDrop.containsDrag || (Plasmoid.configuration.wide && !!root.media)
        readonly property real stripWidth: glance ? root.restWidth : root.restWidth - 10
        // A stationary panel keeps the compact controls under the pointer throughout the reveal.
        Layout.minimumWidth: root.restWidth
        Layout.maximumWidth: Layout.minimumWidth
        Layout.preferredWidth: Layout.minimumWidth
        readonly property Item compactHost: {
            let ancestor = parent
            while (ancestor && ancestor.objectName !== "org.kde.desktop-CompactApplet") ancestor = ancestor.parent
            return ancestor
        }
        Binding {
            target: pill.compactHost
            property: "active"
            when: !!pill.compactHost
            value: false
            restoreMode: Binding.RestoreBindingOrValue
        }
        hoverEnabled: true
        leftPadding: 13; rightPadding: glance && quickButtons.visible ? 5 : 13; topPadding: 0; bottomPadding: 0
        Accessible.name: root.toolTipMainText + ". " + root.toolTipSubText
        Accessible.description: companionLoader.item?.showing ? i18n("Notch companion") : ""
        onClicked: root.openPill()
        background: Item {
            IslandSurface {
                anchors.horizontalCenter: parent.horizontalCenter
                width: pill.stripWidth
                Behavior on width { enabled: root.motion; NumberAnimation { duration: Kirigami.Units.shortDuration; easing.type: Easing.OutCubic } }
                // The panel theme may inset its applets even on a non-floating panel.
                readonly property real panelHeight: pill.Window.window?.height ?? parent.height
                height: root.ownEdge ? Math.min(panelHeight, 25) : parent.height
                y: root.ownEdge ? (parent.height - panelHeight) / 2 : 0
                transformOrigin: Item.Top
                scale: pill.down && !root.islandOpen && root.motion ? 0.965 : 1
                Behavior on scale { enabled: root.motion; NumberAnimation { duration: Kirigami.Units.veryShortDuration; easing.type: Easing.OutCubic } }
                shoulder: root.ownEdge ? 5 : 0
                chin: 8
                topColor: "#050506"
                bottomColor: shelfDrop.containsDrag ? "#1d4c40" : "#09090b"
            }
        }
        contentItem: RowLayout {
            opacity: 1 - pill.covered
            transform: Translate { y: root.ownEdge ? (Math.min(25, pill.Window.window?.height ?? pill.height) - (pill.Window.window?.height ?? pill.height)) / 2 : 0 }
            spacing: 5
            Image {
                visible: status === Image.Ready && !pill.sharedOpen && !!root.media && (!root.timerStrip || root.combined) && !root.awakeStrip && !watch.registered && !preview.item?.noticeId && !shelfDrop.containsDrag
                Layout.preferredWidth: 20; Layout.preferredHeight: 20
                source: root.media?.artUrl || ""; sourceSize: Qt.size(40, 40)
                asynchronous: true; fillMode: Image.PreserveAspectCrop
            }
            Kirigami.Icon {
                visible: !companionLoader.item?.showing && (pill.titleVisible || pill.activeStrip) && (pill.sharedOpen || !root.media?.artUrl || !pill.activeStrip || root.timerStrip || root.awakeStrip || watch.registered || !!preview.item?.noticeId || shelfDrop.containsDrag)
                Layout.preferredHeight: 17; Layout.preferredWidth: 17
                source: pill.sharedOpen ? "view-grid" : shelfDrop.containsDrag ? "folder-add" : preview.item?.noticeId ? "notifications"
                    : root.timerStrip ? (countdown.paused ? "media-playback-pause" : "chronometer") : watch.registered ? "view-visible"
                    : root.awakeStrip ? "system-suspend-inhibited" : root.media ? "audio-x-generic" : "applications-utilities"
                color: root.timerStrip ? "#ffad54" : "#d8d8df"; isMask: true
            }
            Item {
                id: leftCompanion
                visible: companionLoader.parent === this && !!companionLoader.item?.showing
                Layout.preferredWidth: 22; Layout.preferredHeight: 24
            }
            C.Label {
                Layout.fillWidth: true; color: "#f6f3e9"; textFormat: Text.PlainText; elide: Text.ElideRight
                opacity: pill.titleVisible ? 1 : 0
                Behavior on opacity { NumberAnimation { duration: Kirigami.Units.shortDuration } }
                text: pill.glance && quickButtons.visible && root.media && !Plasmoid.configuration.wide && !root.timerStrip ? "" : pill.sharedOpen ? root.pageTitle : shelfDrop.containsDrag ? i18n("Shelf") : preview.item?.title || (root.timerStrip ? (countdown.completion && !Plasmoid.configuration.wide ? i18n("Done") : root.timerSummary)
                    : watch.registered ? i18n("Watching") : root.awakeStrip ? awakeModel.item.compactText : root.media?.track || i18n("Monet Notch"))
            }
            Loader {
                Layout.preferredWidth: active ? 13 : 0; Layout.preferredHeight: 18
                visible: active; active: Plasmoid.configuration.levels && root.playing && power.active && !root.islandOpen
                source: "MusicLevel.qml"
                onLoaded: {
                    item.sources = players
                    item.player = Qt.binding(() => root.media)
                }
            }
            Kirigami.Icon {
                visible: !!root.media && !pill.glance && !pill.sharedOpen && !root.timerStrip &&
                    !root.awakeStrip && !watch.registered && !preview.item?.noticeId && !shelfDrop.containsDrag &&
                    !(Plasmoid.configuration.levels && root.playing) && !companionLoader.item?.showing
                Layout.preferredWidth: 14; Layout.preferredHeight: 14
                source: root.playing ? "audio-volume-high" : "media-playback-pause"
                color: "#c6c6cb"; isMask: true
            }
            RowLayout {
                id: quickButtons
                readonly property bool underPointer: playQuick.hovered || nextQuick.hovered || timerQuick.hovered || searchQuick.hovered
                visible: pill.glance && Plasmoid.configuration.hoverControls
                enabled: !root.islandOpen
                spacing: 3
                IslandButton {
                    id: playQuick
                    visible: !!root.media
                    implicitWidth: 24; implicitHeight: 24
                    text: root.playing ? i18n("Pause") : i18n("Play"); icon.name: root.playing ? "media-playback-pause" : "media-playback-start"
                    enabled: root.playing ? !!root.media?.canPause : !!root.media?.canPlay
                    onClicked: root.playing ? root.media.Pause() : root.media.Play()
                }
                IslandButton {
                    id: nextQuick
                    visible: !!root.media?.canGoNext && !root.timerStrip
                    implicitWidth: 24; implicitHeight: 24; text: i18n("Next track"); icon.name: "media-skip-forward"
                    onClicked: root.media.Next()
                }
                IslandButton {
                    id: timerQuick
                    visible: root.timerStrip && countdown.active
                    implicitWidth: 24; implicitHeight: 24; text: countdown.paused ? i18n("Resume timer") : i18n("Pause timer")
                    icon.name: countdown.paused ? "media-playback-start" : "media-playback-pause"; tint: "#ffb35b"
                    onClicked: countdown.paused ? countdown.resume(Date.now()) : countdown.pause(Date.now())
                }
                IslandButton {
                    id: searchQuick
                    visible: !root.media && !root.timerStrip && root.offerSearch
                    implicitWidth: 24; implicitHeight: 24; text: i18n("Command Bar"); icon.name: "system-search"
                    onClicked: { root.openPill(); root.searching = true }
                }
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

    PlasmaCore.Dialog {
        id: popup
        visualParent: root.ownEdge ? (root.compactRepresentationItem?.edgeAnchor ?? null) : root.compactRepresentationItem
        location: Plasmoid.location
        type: PlasmaCore.Dialog.AppletPopup
        backgroundHints: PlasmaCore.Dialog.NoBackground
        hideOnWindowDeactivate: false
        property bool receivedFocus: false
        onActiveChanged: {
            if (active) receivedFocus = true
            else if (receivedFocus && visible && !root.draggingShelf && !root.pinned) root.collapse()
        }
        visible: root.islandOpen && !!visualParent
        onVisibleChanged: {
            if (visible) { requestActivate(); pages.reveal() }
            else {
                receivedFocus = false
                if (root.islandOpen) root.islandOpen = false
            }
        }
        mainItem: FocusScope {
        id: pages
        width: root.surfaceWidth
        // Common pages share a native surface. Moving between tiles only changes its contents.
        readonly property int homeHeight: Math.max(272, 52 + IslandLayout.gridHeight(root.sections.length, width - 32))
        readonly property bool detailHeight: root.searching || (!root.overview &&
            (root.displayShelf || root.showingWatch || root.viewingAwake || root.viewingDownloads ||
             (!root.utilityPage && (root.tab === 1 || root.tab >= 3 || root.musicView > 0))))
        readonly property int wantedHeight: Math.min(Math.max(1, (root.Screen.height || 800) - 48),
            Math.max(homeHeight, detailHeight || (root.utilityPage === "together" && width < 370) ? 344 : 0))
        property real visualHeight: 1
        property real reservedHeight: 0
        height: Math.max(wantedHeight, reservedHeight)
        focus: true
        function resizePage() {
            resizeMotion.stop()
            reservedHeight = Math.max(visualHeight, wantedHeight)
            if (!root.motion || !popup.visible || revealProgress < 1 || !visualHeight) {
                visualHeight = wantedHeight
                reservedHeight = 0
                return
            }
            resizeMotion.from = visualHeight
            resizeMotion.to = wantedHeight
            resizeMotion.start()
        }
        onWantedHeightChanged: resizePage()
        NumberAnimation {
            id: resizeMotion; target: pages; property: "visualHeight"
            duration: Kirigami.Units.longDuration; easing.type: Easing.InOutCubic
            onFinished: pages.reservedHeight = 0
        }
        property real revealProgress: 0
        property bool awaitingFrame: false
        function resetReveal() {
            awaitingFrame = false
            morph.stop()
            revealProgress = 0
        }
        function animateTo(goal) {
            awaitingFrame = false
            morph.stop()
            if (!root.motion || revealProgress === goal) {
                revealProgress = goal
                if (goal === 0 && root.folding) root.islandOpen = false
                return
            }
            morph.from = revealProgress
            morph.to = goal
            const distance = Math.abs(goal - revealProgress)
            morph.duration = Math.max(1, Math.round(Kirigami.Units.longDuration * (goal ? 1.55 : 1.15) * Math.sqrt(distance)))
            morph.start()
        }
        function reveal() {
            resetReveal()
            // Let Plasma map the surface before advancing its first animation frame.
            resizePage()
            if (root.motion) awaitingFrame = true
            else revealProgress = 1
            Qt.callLater(() => { if (root.overview) body.item?.focusFirst?.(); else sectionsButton.forceActiveFocus(Qt.OtherFocusReason) })
        }
        Connections {
            target: popup
            enabled: pages.awaitingFrame
            function onFrameSwapped() {
                if (pages.awaitingFrame && root.islandOpen && !root.folding) pages.animateTo(1)
            }
        }
        NumberAnimation {
            id: morph
            target: pages; property: "revealProgress"
            easing.type: Easing.BezierSpline
            easing.bezierCurve: [0.22, 0.02, 0.18, 1, 1, 1]
            onFinished: if (root.folding && to === 0) root.islandOpen = false
        }
        readonly property real closedHeight: root.ownEdge ? 25 : 1
        readonly property real drawnWidth: root.restWidth - 10 + (width - root.restWidth + 10) * revealProgress
        readonly property real drawnHeight: closedHeight + (visualHeight - closedHeight) * revealProgress
        // Scale a settled outline. Its path and the layout beneath the clip stay stable across frames.
        IslandSurface {
            width: pages.width; height: pages.wantedHeight
            opacity: root.ownEdge ? Math.min(1, pages.revealProgress * 4) : 1
            shoulder: root.ownEdge ? 8 : 0; chin: 22
            topColor: "#050506"; bottomColor: "#e1222225"
            transform: Scale {
                origin.x: pages.width / 2
                xScale: pages.drawnWidth / pages.width
                yScale: pages.drawnHeight / pages.wantedHeight
            }
        }
        Item {
            anchors.horizontalCenter: parent.horizontalCenter
            width: pages.drawnWidth; height: pages.drawnHeight
            clip: true
            C.Control {
                id: skin
                anchors.horizontalCenter: parent.horizontalCenter
                width: pages.width - 16; height: pages.wantedHeight
                padding: 0
                background: null
                palette.window: "#151517"; palette.windowText: "#f5f5f7"; palette.text: "#f5f5f7"
                palette.base: "#232325"; palette.button: "#303034"; palette.buttonText: "#f5f5f7"
                palette.highlight: "#527ba6"; palette.highlightedText: "white"
                Kirigami.Theme.inherit: false
                Kirigami.Theme.backgroundColor: "#19191c"; Kirigami.Theme.textColor: "#f5f5f7"
                Kirigami.Theme.alternateBackgroundColor: "#262629"; Kirigami.Theme.highlightColor: "#527ba6"
                contentItem: Item {
                    ColumnLayout {
                        anchors.horizontalCenter: parent.horizontalCenter
                        y: 2; width: parent.width - 16; height: pages.wantedHeight - 12
                        opacity: Math.max(0, (pages.revealProgress - 0.15) / 0.85)
                        transform: Translate { y: -5 * (1 - pages.revealProgress) }
                        spacing: 3
                        RowLayout {
                            Layout.fillWidth: true; Layout.preferredHeight: 32; Layout.maximumHeight: 32
                            IslandButton { id: sectionsButton; plain: true; icon.name: root.overview ? "window-close" : "view-grid"
                                text: root.overview ? i18n("Close") : i18n("Sections")
                                onClicked: { if (root.overview) root.collapse(); else pages.showSections() } }
                            IslandButton { plain: true; visible: !root.overview && pages.canGoBack; icon.name: "go-previous"; text: i18n("Back"); onClicked: pages.back() }
                            C.Label {
                                text: root.pageTitle; textFormat: Text.PlainText; elide: Text.ElideRight
                                font.weight: Font.DemiBold; font.pixelSize: 13; color: "#f7f7fa"
                                Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.fillHeight: true
                                verticalAlignment: Text.AlignVCenter
                                TapHandler { onTapped: root.openPill() }
                            }
                            IslandButton { id: searchButton; plain: true; visible: root.offerSearch; icon.name: "system-search"; text: i18n("Command Bar"); onClicked: root.searching = true }
                            IslandButton { plain: true; icon.name: "pin-symbolic"; text: root.pinned ? i18n("Unpin") : i18n("Keep open"); checked: root.pinned; onClicked: root.pinned = !root.pinned }
                            IslandButton { plain: true; icon.name: "application-menu"; text: i18n("Utilities"); onClicked: root.openTool("tools") }
                        }
                        IslandPages {
                            id: body
                            Layout.fillWidth: true; Layout.fillHeight: true
                            presented: root.islandOpen && !root.searching
                            duration: root.motion && pages.revealProgress === 1 ? Kirigami.Units.shortDuration : 0
                            prewarm: root.prepareSections ? sectionPage : null
                            components: [sectionPage, musicPage, activityPage, timerPage, calendarPage, padPage,
                                clipboardPage, cameraPage, shelfPage, downloadsPage, watchPage, agendaPage,
                                awakePage, mixerPage, controlsPage, systemPage, capturesPage, pairedPage]
                            reusable: [musicPage, timerPage]
                            privatePages: [clipboardPage, cameraPage, padPage, activityPage, watchPage]
                            requested: root.overview ? sectionPage : root.utilityPage === "controls" ? controlsPage
                                : root.utilityPage === "system" ? systemPage : root.utilityPage === "captures" ? capturesPage : root.utilityPage === "together" ? pairedPage :
                                root.displayShelf ? shelfPage : root.showingWatch ? watchPage
                                : root.tab === 2 && root.viewingAwake && awakeModel.item ? awakePage
                                : root.tab === 1 && root.viewingDownloads ? downloadsPage
                                : root.tab === 3 && root.viewingAgenda ? agendaPage
                                : root.tab === 0 && root.musicView === 3 ? mixerPage
                                : root.tab === 6 ? clipboardPage : root.tab === 5 ? cameraPage
                                : root.tab === 4 ? (padController.item ? padPage : null)
                                : [musicPage, activityPage, timerPage, calendarPage][root.tab] ?? null
                            onPageShown: if (root.overview && popup.active) item?.focusFirst?.()
                        }
                    }
                }
            }
        }
        function showSections() {
            root.overview = true
            root.searching = false
            body.resolve()
            Qt.callLater(() => body.item?.focusFirst?.())
        }
        function cycle(direction) {
            if (!root.visibleTabs.length) return
            const at = root.visibleTabs.indexOf(root.tab)
            const next = (at + direction + root.visibleTabs.length) % root.visibleTabs.length
            root.choose(root.tabNames[root.visibleTabs[next]])
        }
        readonly property bool canNavigate: root.islandOpen && !root.searching && !root.draggingShelf
        readonly property bool canGoBack: !root.overview && (root.displayShelf || root.showingWatch ||
            root.viewingAwake || (root.tab === 0 && root.musicView !== 0) || (root.tab === 1 && root.viewingDownloads)
            || (root.tab === 3 && root.viewingAgenda) || !!body.item?.notificationOpen)
        function back() {
            if (body.item?.notificationOpen) { body.item.backFromNotification(); return }
            if (root.viewingAwake) { root.viewingAwake = false; Qt.callLater(() => body.item?.focusAwake?.()); return }
            if (root.tab === 0 && root.musicView !== 0) { root.musicView = 0; return }
            if (root.tab === 3 && root.viewingAgenda) { root.viewingAgenda = false; return }
            showSections()
        }
        Shortcut {
            sequences: ["Escape", "Alt+Left"]
            enabled: pages.canNavigate
            onActivated: { if (pages.canGoBack) pages.back(); else if (!root.overview) pages.showSections(); else root.collapse() }
        }
        Shortcut { sequence: "Ctrl+Tab"; enabled: pages.canNavigate; onActivated: pages.cycle(1) }
        Shortcut { sequence: "Ctrl+Shift+Tab"; enabled: pages.canNavigate; onActivated: pages.cycle(-1) }
        Shortcut { sequence: "Ctrl+K"; enabled: pages.canNavigate && root.offerSearch; onActivated: root.searching = true }
        C.Popup {
            id: searchPopup
            parent: skin
            x: 8; y: 5; width: pages.width - 16; height: pages.height - 16
            padding: Kirigami.Units.smallSpacing
            background: Rectangle {
                radius: Kirigami.Units.cornerRadius
                color: "#19191c"
            }
            popupType: C.Popup.Item
            modal: true; dim: false; focus: true
            closePolicy: C.Popup.CloseOnEscape
            visible: root.islandOpen && root.searching
            onClosed: {
                root.searching = false
                if (root.islandOpen && searchButton.visible) searchButton.forceActiveFocus(Qt.BacktabFocusReason)
            }
            readonly property var session: power.nativeState ?? searchLock.item
            readonly property bool unlocked: !!session?.lockKnown && !session.locked
            onUnlockedChanged: if (visible && session?.lockKnown && session.locked) root.islandOpen = false
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
                function onActivated() { root.islandOpen = false }
            }
            C.Button {
                anchors.centerIn: parent
                visible: commandView.status === Loader.Error || !searchPopup.unlocked
                text: searchPopup.unlocked ? i18n("Open Command Bar") : i18n("Back")
                onClicked: {
                    if (!searchPopup.unlocked) { root.searching = false; return }
                    root.islandOpen = false
                    DBus.SessionBus.asyncCall({service: "org.kde.krunner", path: "/App",
                        iface: "org.kde.krunner.App", member: "display"})
                }
            }
        }
        }
    }
    Component {
        id: sectionPage
        IslandSections {
            entries: root.sections
            onSelected: key => root.choose(key)
            onPreviewRequested: key => root.preparePage(key)
        }
    }
    Component {
        id: capturesPage
        IslandCaptures {
            helper: root.helper
            images: tools.offers("screenshot"); videos: tools.offers("recordings"); shelf: root.offerShelf
            onAddFile: url => fileShelf.change({action: "add", urls: [url]})
        }
    }
    Component { id: controlsPage; IslandControls { soundAvailable: tools.offers("sound"); brightnessAvailable: tools.offers("display") } }
    Component {
        id: pairedPage
        GridLayout {
            columns: width >= 344 ? 2 : 1
            columnSpacing: 8; rowSpacing: 8
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 1
                radius: 15; color: "#232225"
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 11; spacing: 4
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: i18n("Music"); font.weight: Font.Medium; color: "#ff7b97"; Layout.fillWidth: true; elide: Text.ElideRight }
                        IslandButton { text: i18n("Now playing"); icon.name: "go-next-symbolic"; implicitHeight: 25; implicitWidth: 25; onClicked: root.choose("music") }
                    }
                    C.Label { Layout.fillWidth: true; elide: Text.ElideRight; font.bold: true; font.pixelSize: 17; color: "white"
                        textFormat: Text.PlainText; text: root.media?.track || i18n("Now playing") }
                    C.Label { Layout.fillWidth: true; elide: Text.ElideRight; color: "#c2c0c7"; textFormat: Text.PlainText; text: root.media?.artist || root.media?.identity || "" }
                    Item { Layout.fillHeight: true }
                    RowLayout {
                        IslandButton { text: root.playing ? i18n("Pause") : i18n("Play"); icon.name: root.playing ? "media-playback-pause" : "media-playback-start"; prominent: true
                            enabled: root.playing ? !!root.media?.canPause : !!root.media?.canPlay
                            onClicked: root.playing ? root.media.Pause() : root.media.Play() }
                        IslandButton { text: i18n("Next track"); icon.name: "media-skip-forward"; enabled: !!root.media?.canGoNext; onClicked: root.media.Next() }
                    }
                }
            }
            Rectangle {
                Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 1
                radius: 15; color: "#29231f"
                ColumnLayout {
                    anchors.fill: parent; anchors.margins: 11; spacing: 4
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: i18n("Timer"); font.weight: Font.Medium; color: "#ffb35b"; Layout.fillWidth: true; elide: Text.ElideRight }
                        IslandButton { text: i18n("Time"); icon.name: "go-next-symbolic"; implicitHeight: 25; implicitWidth: 25; onClicked: root.choose("time") }
                    }
                    Text {
                        text: root.timerSummary; color: "#ffad53"; font.pixelSize: 43; font.weight: Font.Light
                        font.features: ({"tnum": 1}); fontSizeMode: Text.HorizontalFit; minimumPixelSize: 17
                        Layout.fillWidth: true; Layout.minimumWidth: 0; horizontalAlignment: Text.AlignRight
                    }
                    Item { Layout.fillHeight: true }
                    IslandButton { visible: countdown.active; text: countdown.waiting ? (countdown.onBreak ? i18n("Start break") : i18n("Start next session")) : countdown.paused ? i18n("Resume timer") : i18n("Pause timer")
                        icon.name: countdown.deadline ? "media-playback-pause" : "media-playback-start"; tint: "#ffb35b"; base: "#4a3220"
                        onClicked: !countdown.deadline ? countdown.resume(Date.now()) : countdown.pause(Date.now()) }
                }
            }
        }
    }
    Component { id: systemPage; IslandSystem {} }
    Component {
        id: shelfPage
        FileShelf {
            shelf: fileShelf
            canGoBack: root.visibleTabs.length > 0
            onDraggingChanged: root.draggingShelf = dragging
            Component.onDestruction: root.draggingShelf = false
            onBackRequested: pages.showSections()
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
            onUnlockedChanged: if (session?.lockKnown && session.locked) root.islandOpen = false
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
                function onRequestHidePopup() { root.islandOpen = false }
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
            presented: root.islandOpen && !root.searching && power.active
            session: power.nativeState
        }
    }
    Component { id: padPage; Scratchpad { pads: padController.item } }
    Component {
        id: musicPage
        Music {
            player: visible ? root.media : null; sources: players; playing: visible && root.playing; view: visible ? root.musicView : 0
            playback: queuePlayback.item
            formatDuration: root.duration
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
            onEditing: root.islandOpen = false
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
            readonly property bool notificationOpen: notices.inDetail || notices.toRemove.length > 0
            function backFromNotification() {
                if (notices.toRemove.length) notices.cancelClear()
                else notices.back()
            }

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
                onActivated: root.islandOpen = false
            }
            SessionButton {
                Layout.fillWidth: true
                widgetId: String(Plasmoid.id)
                active: root.agentsVisible && root.sessionSelected && root.activityOpen && power.active
                        && !root.viewingDownloads && !notices.inDetail
                onClicked: {
                    runner.connectSource(root.helper + " utilities agents session")
                    root.islandOpen = false
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
                        root.islandOpen = false
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
                            root.islandOpen = false
                        }
                    }
                }
            }
        }
    }
    Component {
        id: timerPage
        TimePage {
            timer: countdown; now: root.now; message: root.message; formatDuration: root.duration
            offerAwake: root.offerAwake
            onAwakeRequested: root.viewingAwake = true
        }
    }
    Component {
        id: awakePage
        AwakeControls {
            awake: awakeModel.item
            onBackRequested: pages.back()
            Component.onCompleted: focusBack()
        }
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
