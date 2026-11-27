pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Effects
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
    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: i18n("Notch & Tools settings…")
            icon.name: "configure"
            onTriggered: root.openNotchSettings()
        },
        PlasmaCore.Action {
            text: i18n("Edit notch…")
            icon.name: "configure"
            onTriggered: {
                root.collapse()
                runner.connectSource("@LIBEXECDIR@/monet-quick panel-configure " + Plasmoid.containment.id)
            }
        }
    ]
    property bool islandOpen: false
    property bool rememberRoute: true
    readonly property string shortcutOwner: String(Plasmoid.id)
    NotchShortcut {
        ownerId: root.shortcutOwner
        onRequested: command => {
            if (command === "toggle") root.openPill()
        }
    }
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
    readonly property int surfaceWidth: Math.min(Math.max(340, Math.min(640, Plasmoid.configuration.expandedWidth || 464)), Math.max(1, (root.Screen.width || 648) - 16))
    readonly property bool railSpace: ownEdge && root.Screen.width >= surfaceWidth + 112
    readonly property int restWidth: Plasmoid.configuration.wide ? 244 : 178
    readonly property var panelSurface: pages
    Binding {
        target: Plasmoid.containment
        property: "backgroundHints"
        when: root.ownEdge
        value: PlasmaCore.Types.NoBackground
        restoreMode: Binding.RestoreBindingOrValue
    }
    NotchHoverPreview {
        id: hoverPreview
        allowed: Plasmoid.configuration.hoverControls && !root.editing && power.active
        opened: root.islandOpen
        overPill: root.compactRepresentationItem?.hoveredForPreview ?? false
        overPreview: popupPointer.hovered || (root.compactRepresentationItem?.railHovered ?? false)
        held: root.pinned || root.draggingShelf || root.searching || !!body.item?.menuOpen
            || !!body.item?.choosingFile || !!body.item?.ownsSurface
        onRequested: root.showPill()
        onDismissed: root.collapse()
        onAdopted: { root.rememberRoute = true; Qt.callLater(() => { popup.requestActivate(); pages.focusPage() }) }
    }
    function collapse() {
        hoverPreview.cancel()
        if (folding || !islandOpen) return
        if (body.current?.modelData === toolDetails && body.item?.ownsSurface) {
            body.item.releaseForNavigation(() => root.finishCollapse())
            return
        }
        finishCollapse()
    }
    function finishCollapse() {
        if (folding || !islandOpen) return
        if (!motion) { islandOpen = false; return }
        folding = true
        pages.animateTo(0)
    }
    NotchNavigation {
        id: navigation
        route: root.currentRoute
        sections: root.sections
        available: root.availableRoute
        onRequested: (key, backwards) => root.displayRoute(key, backwards)
    }
    property int slideDirection: 1
    readonly property string currentRoute: overview ? "sections" : utilityPage || (displayShelf ? "files"
        : showingWatch ? "watch" : viewingDownloads ? "downloads" : viewingAgenda ? "agenda"
        : viewingAwake ? "awake" : tab === 0 ? ["music", "lyrics", "queue", "mixer"][musicView] : tabNames[tab]) || "sections"
    function availableRoute(key) {
        const inlineTool = ({camera:"camera", clipboard:"clipboard", notes:"notes", queue:"media", mixer:"mixer", agents:"agents", files:"shelf", agenda:"calendars"})[key]
        if (inlineTool && visibleTabs.includes(7) && tools.offers(inlineTool)) return true
        if (key === "radial") return false
        if (key.startsWith("agent-")) return (visibleTabs.includes(8) || visibleTabs.includes(1)) && offerAgents
        if (key.startsWith("tool-")) {
            const tool = key.slice(5)
            return tools.offers(tool) && (visibleTabs.includes(7) || (tool === "calendars" && offerAgenda) || (tool === "downloads" && offerDownloads))
        }
        if (key === "sections") return true
        if (key === "agenda") return offerAgenda && visibleTabs.includes(3)
        if (key === "awake") return offerAwake
        if (key === "watch") return watch.registered
        if (key === "lyrics" || key === "queue") return offerMediaDetails && visibleTabs.includes(0)
        return sections.some(section => section.key === key)
    }
    function preparePage(key) {
        if (!islandOpen) return
        if (key === "tools" && !toolRows.length) body.anticipated = toolPage
        else if (["music","time","mixer"].includes(key))
            body.anticipated = key === "music" ? musicPage : key === "time" ? timerPage : mixerPage
    }
    function displayRoute(key, backwards) {
        if (key === currentRoute && !body.item?.releasing) return
        if (body.current?.modelData === toolDetails && body.item?.ownsSurface) {
            body.item.releaseForNavigation(() => {
                root.finishDisplayRoute(key, backwards)
                popup.requestActivate()
            })
            return
        }
        finishDisplayRoute(key, backwards)
    }
    function finishDisplayRoute(key, backwards) {
        slideDirection = backwards ? -1 : 1
        overview = key === "sections"
        utilityPage = key.startsWith("agent-") || key.startsWith("tool-") || ["controls","system","together","captures"].includes(key) ? key : ""
        viewingShelf = key === "files"
        viewingWatch = key === "watch"
        viewingDownloads = key === "downloads"
        viewingAgenda = key === "agenda"
        requestedNotice = 0
        const music = ["music", "lyrics", "queue", "mixer"].indexOf(key)
        if (music >= 0) tab = 0
        else if (viewingDownloads || viewingWatch) tab = 1
        else if (key === "awake") tab = 2
        else if (viewingAgenda) tab = 3
        else if (tabNames.includes(key)) tab = tabNames.indexOf(key)
        viewingAwake = key === "awake"
        musicView = Math.max(0, music)
        Qt.callLater(body.resolve)
    }
    readonly property var sections: {
        let rows = []
        function add(key, label, icon, color) { rows.push({key, label, icon, color}) }
        if (tools.offers("sound") || tools.offers("display")) add("controls", i18n("Controls"), "configure", "#e0e0e5")
        if (combined) add("together", i18n("Music and timer"), "chronometer", "#ffad54")
        const icons = ["media-playback-start","view-history","chronometer","view-calendar","document-edit","camera-web","edit-paste","applications-utilities","dialog-scripts","notifications"]
        const colors = ["#ff6485","#a8b7ff","#ff9f38","#ff716b","#ffcf69","#95d5ff","#c29fff","#8ed1d3","#d2adff","#ffb681"]
        for (const id of visibleTabs) {
            add(tabNames[id], tabLabels[id], icons[id], colors[id])
            if (id === 0 && offerMixer) add("mixer", i18n("Volume mixer"), "audio-volume-high", "#a1d9ff")
            if (id === 1 && offerDownloads) add("downloads", i18n("Downloads"), "go-down-symbolic", "#79d3aa")
        }
        if (tools.offers("screenshot") || tools.offers("recordings") || tools.offers("clipboard")) add("captures", i18n("Recent captures"), "camera-photo", "#bbdeee")
        if (offerShelf) add("files", i18n("File shelf"), "folder-open", "#75b9ff")
        if (tools.offers("processes")) add("system", i18n("System"), "view-statistics-symbolic", "#aba6ff")
        return rows
    }
    onSectionsChanged: if (utilityPage && !availableRoute(utilityPage)) {
        utilityPage = ""; overview = true
    }
    readonly property string pageTitle: overview ? i18n("Sections") : utilityPage === "controls" ? i18n("Controls")
        : utilityPage.startsWith("agent-") ? (utilityPage === "agent-claude" ? "Claude Code" : utilityPage === "agent-codex" ? "Codex" : i18n("Session file"))
        : utilityPage.startsWith("tool-") ? (toolRows.find(entry => entry.key === utilityPage.slice(5))?.label || (utilityPage === "tool-calendars" ? i18n("Link a calendar…") : utilityPage === "tool-downloads" ? i18n("Watch downloads") : i18n("Tools")))
        : utilityPage === "captures" ? i18n("Recent captures") : utilityPage === "system" ? i18n("System") : utilityPage === "together" ? i18n("Music and timer") : displayShelf ? i18n("File shelf") : showingWatch ? i18n("Watch")
        : viewingDownloads ? i18n("Downloads") : tab === 0 ? [i18n("Now Playing"), i18n("Lyrics"), i18n("Up next"), i18n("Volume mixer")][musicView] : tabLabels[tab] || i18n("Sections")
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
    readonly property var tabNames: ["music", "activity", "time", "calendar", "notes", "camera", "clipboard", "tools", "agents", "notifications"]
    readonly property var tabLabels: [i18n("Music"), i18n("Activity"), i18n("Time"), i18n("Calendar"), i18n("Notes"), i18n("Camera"), i18n("Clipboard"), i18n("Tools"), i18n("AI agents"), i18n("Notifications")]
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
        if (readingActivity) Qt.callLater(refreshActivity)
    }
    onOfferAgentsChanged: {
        if (!offerAgents) { agentsVisible = false; sessionSelected = false; lastSessionReading = "" }
        if (readingActivity) Qt.callLater(refreshActivity)
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
        const ordered = ids.every((id, index) => id >= 0 && ids.indexOf(id) === index) ? ids : [0, 1, 2, 3, 4, 6, 7, 8, 9]
        return ordered.filter(id => (id !== 4 || tools.offers("notes")) && (id !== 5 || tools.offers("camera"))
                                    && (id !== 6 || tools.offers("clipboard")) && (id !== 8 || offerAgents))
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
        shown: root.islandOpen && !root.searching && ((!root.overview && !root.utilityPage && root.displayShelf) || body.current?.modelData === shelfPage || body.outgoing?.modelData === shelfPage)
        dragging: root.draggingShelf
        onFilesAdded: root.react("shelf")
    }
    function showShelf() {
        if (!offerShelf) return
        islandOpen = true
        navigation.openTab("files")
    }
    property int requestedNotice: 0
    Loader {
        id: preview
        active: (!root.islandOpen || root.requestedNotice > 0) && (root.hasActivity || root.visibleTabs.includes(9)) && Plasmoid.configuration.previews && power.active
                && !!power.nativeState?.lockKnown && !power.nativeState.locked && !NM.Server.inhibited
        source: "NoticePreview.qml"
        onLoaded: item.watching = Qt.binding(() => !root.islandOpen)
    }
    property string lastRoute: "sections"
    function railEntries(side) {
        const saved = side === "left" ? Plasmoid.configuration.leftRail : Plasmoid.configuration.rightRail
        const keys = String(saved || (side === "left" ? "time" : "controls,mixer,files")).split(",")
        return keys.map(key => sections.find(item => item.key === key)).filter(item => !!item).slice(0,4)
    }
    function openPill() {
        if (hoverPreview.previewing) { hoverPreview.adopt(); return }
        if (folding) { folding = false; pages.animateTo(1); return }
        if (islandOpen) { collapse(); return }
        showPill()
    }
    function showPill() {
        rememberRoute = !hoverPreview.previewing
        const notice = preview.item?.noticeId || 0
        const toAwake = awakeStrip
        if (!(Plasmoid.configuration.openActivity ?? true)) {
            navigation.openTab(Plasmoid.configuration.reopen === "last" && availableRoute(lastRoute) ? lastRoute : "sections")
        }
        else if (notice) { navigation.openTab(visibleTabs.includes(9) ? "notifications" : "activity"); requestedNotice = notice }
        else if (combined) navigation.openTab("together")
        else if (timerStrip) navigation.openTab("time")
        else if (watch.registered) navigation.openTab("watch")
        else if (toAwake) navigation.openTab("awake")
        else if (media && visibleTabs.includes(0)) navigation.openTab("music")
        else navigation.openTab(Plasmoid.configuration.reopen === "last" && availableRoute(lastRoute) ? lastRoute : "sections")
        islandOpen = true
    }
    property bool padsOpened: false
    readonly property bool padShown: islandOpen && !overview && !utilityPage && !viewingShelf && !showingWatch && tab === 4
    onPadShownChanged: if (padShown) padsOpened = true
    onTabChanged: {
        if (tab !== 1 && tab !== 9) requestedNotice = 0
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
    property bool agentsVisible: false
    property string lastSessionReading: ""
    AgentHistory {
        id: agentHistory
        presented: root.offerAgents && root.agentPageOpen && power.active
    }
    AgentUsage {
        id: codexUsage; provider: "codex"
        presented: root.offerAgents && power.active && (root.readingActivity || (root.islandOpen && root.currentRoute === "agent-codex"))
        onSettingsChanged: root.refreshActivity()
    }
    AgentUsage {
        id: claudeUsage; provider: "claude"
        presented: root.offerAgents && power.active && (root.readingActivity || (root.islandOpen && root.currentRoute === "agent-claude"))
        onSettingsChanged: root.refreshActivity()
    }
    DBus.SignalWatcher {
        enabled: root.offerAgents
        busType: DBus.BusType.Session; service: "org.monet.Utilities"
        path: "/Utilities"; iface: "org.monet.Utilities"
        function dbusAgentFileChanged(selected) {
            root.lastSessionReading = ""
            root.sessionSelected = selected
            if (root.checkingDownloads) root.refreshPending = true
        }
        function dbusAgentVisibilityChanged() {
            root.sessionSelected = false; root.agentsVisible = false; root.lastSessionReading = ""
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
    readonly property bool agentPageOpen: islandOpen && currentRoute === "agents"
    readonly property bool readingActivity: activityOpen || agentPageOpen
    function refreshActivity() {
        if (!readingActivity || !(offerDownloads || offerAgents)) return
        if (checkingDownloads) { refreshPending = true; return }
        checkingDownloads = true
        runner.connectSource(helper + " notch-activity")
    }
    onReadingActivityChanged: {
        if (readingActivity) refreshActivity()
        else {
            downloadAvailable = false; downloadPath = ""; downloadFolder = ""
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
    toolTipMainText: ""
    toolTipSubText: ""
    readonly property string accessibleStatus: preview.item?.title ? [preview.item.sender, preview.item.title].filter(Boolean).join(" · ")
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
    property var toolRows: []
    property var toolGroups: []
    property string toolGroup: "favorites"
    property string toolQuery: ""
    function catalogReady(rows, groups) { toolRows = rows; toolGroups = groups }
    function runDesktopTool(key) {
        if (!tools.offers(key)) return
        DBus.SessionBus.asyncCall({service:"org.monet.Utilities", path:"/NotchTools", iface:"org.monet.Utilities",
            member:"Tool", signature:"(s)", arguments:[JSON.stringify({action:"run", key:key})]})
        if (!["mic","output","keyboard-light","automatic-appearance","switch-appearance","clean","plain"].includes(key)) collapse()
    }
    function selectTool(key) {
        if (!tools.offers(key)) return
        if (key === "wheel") { openRadialMenu(); return }
        if (key === "notch-settings") { openNotchSettings(); return }
        const route = ({shelf:"files", notes:"notes", downloads:"downloads", calendars:"agenda", agents:"agents",
            media:"queue", mixer:"mixer", camera:"camera",watch:"watch", clipboard:"clipboard", awake:"awake"})[key]
        if (route && availableRoute(route)) { navigation.openDetail(route); return }
        if (key === "command-bar" && offerSearch) { searching = true; return }
        if (toolRows.find(item => item.key === key)?.immediate) {
            // The catalogue is already visible. Issue actions once, directly to their owner.
            runDesktopTool(key)
            return
        }
        navigation.openDetail("tool-" + key)
    }
    function openTool(page) {
        runner.connectSource(helper + " utilities " + page)
        islandOpen = false
    }
    function openNotchSettings(page = "overview") {
        root.collapse()
        DBus.SessionBus.asyncCall({service:"org.monet.Utilities",path:"/Utilities",iface:"org.monet.Utilities",
            member:"Present",signature:"(s)",arguments:[JSON.stringify(["notch-settings",page])]})
    }
    function openRadialMenu() {
        root.collapse()
        DBus.SessionBus.asyncCall({service:"org.monet.Utilities",path:"/Utilities",iface:"org.monet.Utilities",
            member:"Present",signature:"(s)",arguments:[JSON.stringify(["radial"])]})
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
            if (rememberRoute) lastRoute = currentRoute
            folding = false; pinned = false; navigation.dismiss(); pages.resetReveal(); overview = true; utilityPage = ""
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
                    if (root.readingActivity) Qt.callLater(root.refreshActivity)
                    return
                }
                if (!root.readingActivity) return
                try {
                    const state = JSON.parse(data.stdout)
                    root.sessionSelected = root.offerAgents && !!state.sessionSelected
                    root.agentsVisible = root.offerAgents && state.agentsVisible !== false
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
        readonly property bool hoveredForPreview: conceal.hovered
        readonly property bool railHovered: leftRail.hovered || rightRail.hovered
        readonly property bool revealed: conceal.shown
        property real faceOpacity: conceal.shown ? 1 : 0
        Behavior on faceOpacity { NumberAnimation { duration: root.motion && !conceal.shown ? 160 : 0 } }
        NotchAutoHide {
            id: conceal
            // Plasma insets and clips applets. Observe the standalone panel's
            // full input area, independently of the translated compact face.
            parent: root.ownEdge ? (pill.Window.window?.contentItem ?? pill) : pill
            anchors.fill: parent
            z: 1000
            automatic: Plasmoid.configuration.autoHide
            occupied: root.islandOpen || root.editing || pill.visualFocus || shelfDrop.containsDrag
            onHoveredChanged: {
                if (hovered && !root.editing) {
                    root.prepareSections = true
                    if (companionLoader.item?.visits && !companionLoader.item.moment) companionLoader.item.greet()
                }
                else if (!hovered) leavePill.restart()
            }
        }
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
            leadingButton: IslandNavigationButton {
                objectName: "island-rail-back"
                width: 33; height: 33; base: "#141416"
                enabled: navigation.canGoBack; opacity: enabled ? 1 : 0.4
                showsSections: pages.backShowsSections
                onClicked: { hoverPreview.adopt(); pages.back() }
            }
            entries: root.railEntries("left")
            onPreviewRequested: key => root.preparePage(key)
            onSelected: key => { hoverPreview.adopt(); navigation.openTab(key) }
        }
        IslandRail {
            id: rightRail
            visualParent: rightAnchor
            presented: popup.visible && root.railSpace && !root.editing
            reveal: pages.revealProgress
            entries: root.railEntries("right")
            onPreviewRequested: key => root.preparePage(key)
            onSelected: key => { hoverPreview.adopt(); navigation.openTab(key) }
        }
        Timer { id: leavePill; interval: 160 }
        // On its own panel the compact face stays in place until the new surface actually covers it.
        readonly property bool sharedOpen: root.islandOpen && !root.ownEdge
        readonly property real covered: root.islandOpen && root.ownEdge ? Math.min(1, pages.revealProgress * 4) : 0
        readonly property bool glance: (conceal.hovered || leavePill.running || visualFocus) && !root.editing && !sharedOpen && covered < 1
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
        Accessible.name: i18n("Monet Notch") + ". " + root.accessibleStatus
        Accessible.description: companionLoader.item?.showing ? i18n("Notch companion") : ""
        onClicked: root.openPill()
        background: Item {
            opacity: pill.faceOpacity
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
                NotchEditHighlight {
                    anchors.fill: parent
                    applet: root
                    active: root.editing
                    standalone: root.ownEdge
                    shoulder: parent.shoulder
                    chin: parent.chin
                }
            }
        }
        contentItem: RowLayout {
            opacity: (1 - pill.covered) * pill.faceOpacity
            transform: Translate { y: root.ownEdge ? (Math.min(25, pill.Window.window?.height ?? pill.height) - (pill.Window.window?.height ?? pill.height)) / 2 : 0 }
            spacing: 5
            Image {
                id: compactCover
                visible: status === Image.Ready && !pill.sharedOpen && !!root.media && (!root.timerStrip || root.combined) && !root.awakeStrip && !watch.registered && !preview.item?.noticeId && !shelfDrop.containsDrag
                Layout.preferredWidth: 20; Layout.preferredHeight: 20
                source: root.media?.artUrl || ""; sourceSize: Qt.size(40, 40)
                asynchronous: true; fillMode: Image.PreserveAspectCrop
                layer.enabled: status === Image.Ready && GraphicsInfo.api !== GraphicsInfo.Software && GraphicsInfo.api !== GraphicsInfo.Unknown
                layer.effect: MultiEffect { maskEnabled: true; maskSource: compactCoverMask }
                Rectangle { id: compactCoverMask; anchors.fill: parent; radius: 4; visible: false; layer.enabled: compactCover.layer.enabled }
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
                objectName: "notchCompactWave"
                Layout.preferredWidth: active ? 35 : 0; Layout.preferredHeight: 16
                visible: active
                active: conceal.shown && !!root.media && power.active && !root.islandOpen && !pill.sharedOpen &&
                    !root.timerStrip && !root.awakeStrip && !watch.registered && !preview.item?.noticeId && !shelfDrop.containsDrag
                source: "MusicLevel.qml"
                onLoaded: {
                    item.sources = players
                    item.player = Qt.binding(() => root.media)
                    item.playing = Qt.binding(() => root.playing)
                    item.monitoring = Qt.binding(() => Plasmoid.configuration.levels)
                    item.motion = Qt.binding(() => root.motion)
                }
            }
            RowLayout {
                id: quickButtons
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
        readonly property var companion: companionLoader.item
        Loader {
            id: companionLoader
            parent: root.islandOpen ? pages.companionSeat
                    : Plasmoid.configuration.companionSide === "right" ? rightCompanion : leftCompanion
            anchors.fill: parent
            active: Plasmoid.configuration.companion && power.active
            sourceComponent: NotchCompanion {
                presented: conceal.shown && power.active && (root.islandOpen || (!preview.item?.noticeId && !shelfDrop.containsDrag))
                motionAllowed: root.motion
                styleName: Plasmoid.configuration.companionStyle
                shapeName: Plasmoid.configuration.companionShape
                paletteName: Plasmoid.configuration.companionColor
                side: Plasmoid.configuration.companionSide
                frequency: Plasmoid.configuration.companionVisits
                visits: frequency !== "off"
                reactions: Plasmoid.configuration.companionReactions === "on"
                hideIdle: Plasmoid.configuration.companionRest === "hide"
                // Only a new request from the editor plays. Restoring settings on login stays quiet.
                property string greetingRequest: Plasmoid.configuration.companionGreeting || ""
                property bool listeningForHello: false
                Component.onCompleted: listeningForHello = true
                onGreetingRequestChanged: if (listeningForHello && greetingRequest) greet()
                Connections {
                    target: root
                    function onReact(kind) { companionLoader.item?.react(kind) }
                }
            }
        }
        NotchGestureSurface { gestures: notchGestures; enabled: conceal.shown }
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
        flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | (hoverPreview.previewing ? Qt.WindowDoesNotAcceptFocus : 0)
        backgroundHints: PlasmaCore.Dialog.NoBackground
        hideOnWindowDeactivate: false
        property bool receivedFocus: false
        onActiveChanged: {
            if (active) receivedFocus = true
            else if (receivedFocus && visible && !root.draggingShelf && !root.pinned && !body.item?.choosingFile && !body.item?.ownsSurface) root.collapse()
        }
        visible: root.islandOpen && !!visualParent
        onVisibleChanged: {
            if (visible) { if (!hoverPreview.previewing) requestActivate(); pages.reveal() }
            else {
                receivedFocus = false
                if (root.islandOpen) root.islandOpen = false
            }
        }
        mainItem: FocusScope {
        id: pages
        HoverHandler { id: popupPointer; blocking: false }
        // Observe presses without taking them away from sliders, buttons, or editors.
        Item {
            anchors.fill: parent; z: 10000
            PointHandler {
                onActiveChanged: if (active) hoverPreview.adopt()
            }
        }
        IslandPopupOverlay {}
        readonly property Item companionSeat: Plasmoid.configuration.companionSide === "right" ? headerRight : headerLeft
        component CompanionSeat: Item {
            readonly property var buddy: root.compactRepresentationItem?.companion
            visible: pages.companionSeat === this && !!buddy?.showing
            Layout.preferredWidth: 30; Layout.preferredHeight: 28
            activeFocusOnTab: visible
            Accessible.role: Accessible.Button
            Accessible.name: i18n("Say hello")
            Accessible.description: i18n("Notch companion")
            Accessible.onPressAction: buddy.greet()
            Keys.onReturnPressed: buddy.greet()
            Keys.onSpacePressed: buddy.greet()
            TapHandler { onTapped: parent.buddy.greet() }
            Rectangle { anchors.fill: parent; radius: 8; color: "transparent"; border.width: parent.activeFocus ? 1 : 0; border.color: "#a3ccff" }
        }
        width: root.surfaceWidth
        // Common pages share a native surface. Moving between tiles only changes its contents.
        readonly property int wantedHeight: Math.min(Math.max(1, (root.Screen.height || 800) - 48), root.currentRoute === "music" ? (root.surfaceWidth < 402 ? 316 : 252) : root.currentRoute === "agents" ? 512 : root.currentRoute.startsWith("tool-") ? Math.max(316, Math.min(640, Plasmoid.configuration.toolHeight || 420)) : ["tools"].includes(root.currentRoute) ? 372 : 316)
        property real visualHeight: 1
        property real reservedHeight: 0
        height: Math.max(wantedHeight, reservedHeight)
        focus: true
        function resizePage() {
            resizeMotion.stop()
            reservedHeight = Math.max(visualHeight, wantedHeight)
            if (!root.motion || !popup.visible || revealProgress < 1 || !visualHeight
                    || root.currentRoute.startsWith("tool-") || body.current?.modelData === toolDetails) {
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
        function focusPage() {
            Qt.callLater(() => { if (root.overview) body.item?.focusFirst?.(); else sectionsButton.forceActiveFocus(Qt.OtherFocusReason) })
        }
        function reveal() {
            resetReveal()
            // Let Plasma map the surface before advancing its first animation frame.
            resizePage()
            if (root.motion) awaitingFrame = true
            else revealProgress = 1
            if (!hoverPreview.previewing) focusPage()
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
            topColor: "#050506"; bottomColor: "#121214"
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
                        y: 2; width: parent.width - 16; height: pages.wantedHeight - 24
                        opacity: Math.max(0, (pages.revealProgress - 0.15) / 0.85)
                        transform: Translate { y: -5 * (1 - pages.revealProgress) }
                        spacing: 3
                        RowLayout {
                            Layout.fillWidth: true; Layout.preferredHeight: 32; Layout.maximumHeight: 32
                            CompanionSeat { id: headerLeft }
                            IslandNavigationButton { id: sectionsButton; plain: true
                                closes: !navigation.canGoBack
                                showsSections: pages.backShowsSections
                                onClicked: { if (closes) root.collapse(); else pages.back() } }
                            IslandNavigationButton { plain: true; visible: navigation.inDetail
                                showsSections: true; onClicked: navigation.showSections() }
                            C.Label {
                                id: heading
                                property string presentedTitle: root.pageTitle
                                function sync() { if (!body.current || body.current.modelData === body.requested) presentedTitle = root.pageTitle }
                                Connections { target: root; function onPageTitleChanged() { Qt.callLater(heading.sync) } }
                                text: presentedTitle; textFormat: Text.PlainText; elide: Text.ElideRight
                                font.weight: Font.DemiBold; font.pixelSize: 13; color: "#f7f7fa"
                                Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.fillHeight: true
                                verticalAlignment: Text.AlignVCenter
                                TapHandler { onTapped: root.openPill() }
                            }
                            CompanionSeat { id: headerRight }
                            IslandButton { id: searchButton; plain: true; visible: root.offerSearch; icon.name: "system-search"; text: i18n("Command Bar"); onClicked: root.searching = true }
                            IslandButton { plain: true; icon.name: "pin-symbolic"; text: root.pinned ? i18n("Unpin") : i18n("Keep open"); checked: root.pinned; onClicked: root.pinned = !root.pinned }
                            IslandButton { plain: true; icon.name: "application-menu"; text: i18n("Tools"); visible: root.visibleTabs.includes(7); onClicked: navigation.openTab("tools") }
                            IslandButton { plain: true; icon.name: "configure"; text: i18n("Notch settings"); visible: root.overview; onClicked: root.openNotchSettings() }
                            IslandButton { plain: true; visible: root.overview && navigation.canGoBack
                                icon.name: "window-close"; text: i18n("Close"); onClicked: root.collapse() }
                        }
                        IslandPages {
                            id: body
                            Layout.fillWidth: true; Layout.fillHeight: true
                            presented: root.islandOpen && !root.searching
                            duration: root.motion && pages.revealProgress === 1 ? IslandLayout.slideDuration(Kirigami.Units.longDuration) : 0
                            prewarm: root.prepareSections ? sectionPage : null
                            components: [sectionPage, musicPage, activityPage, timerPage, calendarPage, padPage,
                                clipboardPage, cameraPage, shelfPage, downloadsPage, watchPage, agendaPage,
                                awakePage, mixerPage, controlsPage, systemPage, capturesPage, pairedPage, toolPage, agentsPage, notificationsPage, sessionDetails, codexDetails, claudeDetails, toolDetails]
                            reusable: [musicPage, timerPage, mixerPage, toolPage, controlsPage, systemPage]
                            privatePages: [clipboardPage, cameraPage, activityPage, watchPage, notificationsPage, toolDetails]
                            externalPages: [toolDetails]
                            navigationDirection: root.slideDirection
                            requested: root.overview ? sectionPage : root.utilityPage === "agent-session" ? sessionDetails
                                : root.utilityPage === "agent-codex" ? codexDetails : root.utilityPage === "agent-claude" ? claudeDetails
                                : root.utilityPage.startsWith("tool-") ? toolDetails : root.utilityPage === "controls" ? controlsPage
                                : root.utilityPage === "system" ? systemPage : root.utilityPage === "captures" ? capturesPage : root.utilityPage === "together" ? pairedPage :
                                root.displayShelf ? shelfPage : root.showingWatch ? watchPage
                                : root.tab === 2 && root.viewingAwake && awakeModel.item ? awakePage
                                : root.tab === 1 && root.viewingDownloads ? downloadsPage
                                : root.tab === 3 && root.viewingAgenda ? agendaPage
                                : root.tab === 0 && root.musicView === 3 ? mixerPage
                                : root.tab === 9 ? notificationsPage : root.tab === 8 ? agentsPage : root.tab === 7 ? toolPage
                                : root.tab === 6 ? clipboardPage : root.tab === 5 ? cameraPage
                                : root.tab === 4 ? (padController.item ? padPage : null)
                                : [musicPage, activityPage, timerPage, calendarPage][root.tab] ?? null
                            onPageShown: {
                                heading.sync()
                                if (root.overview && popup.active) item?.focusFirst?.()
                            }
                        }
                    }
                }
            }
        }
        function cycle(direction) {
            if (!root.visibleTabs.length) return
            const at = root.visibleTabs.indexOf(root.tab)
            const next = (at + direction + root.visibleTabs.length) % root.visibleTabs.length
            navigation.openTab(root.tabNames[root.visibleTabs[next]])
        }
        readonly property bool canNavigate: root.islandOpen && !root.searching && !root.draggingShelf && !body.item?.menuOpen
        readonly property bool editingEvent: body.current?.modelData === body.requested && !!body.item?.editingEvent
        readonly property bool notificationOpen: body.current?.modelData === body.requested && !!body.item?.notificationOpen
        readonly property bool backShowsSections: !root.overview && !navigation.inDetail && !editingEvent && !notificationOpen
        function back(escape = false) {
            if (editingEvent) { body.item.closeEditor(); return }
            if (notificationOpen) { body.item.backFromNotification(); return }
            if (escape && !navigation.inDetail) root.collapse()
            else navigation.back()
        }
        Shortcut { sequence: "Escape"; enabled: pages.canNavigate; onActivated: pages.back(true) }
        Shortcut { sequence: "Alt+Left"; enabled: pages.canNavigate && navigation.canGoBack; onActivated: pages.back() }
        Shortcut { sequence: "Ctrl+Tab"; enabled: pages.canNavigate; onActivated: pages.cycle(1) }
        Shortcut { sequence: "Ctrl+Shift+Tab"; enabled: pages.canNavigate; onActivated: pages.cycle(-1) }
        Shortcut { sequence: "Ctrl+K"; enabled: pages.canNavigate && root.offerSearch; onActivated: root.searching = true }
        C.Popup {
            id: searchPopup
            parent: skin
            x: 8; y: 5; width: skin.width - 16; height: skin.height - 16
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
            motion: root.motion && pages.revealProgress === 1 && !body.outgoing
            entries: root.sections
            lastSection: navigation.lastSection
            detailFor: key => {
                if (key === "music") return root.media?.track || ""
                if (key === "time" && countdown.active) return root.timerSummary
                if (key === "calendar") return Qt.formatDate(root.agendaDay, "ddd d MMM")
                return ""
            }
            onSelected: key => { hoverPreview.adopt(); navigation.openTab(key) }
            onPreviewRequested: key => root.preparePage(key)
        }
    }
    Component {
        id: capturesPage
        IslandCaptures {
            helper: root.helper
            showCopied: tools.offers("clipboard") && root.islandOpen && root.currentRoute === "captures" && !root.searching && power.active
                        && !!(power.nativeState ?? capturesLock.item)?.lockKnown && !(power.nativeState ?? capturesLock.item)?.locked
            Loader { id: capturesLock; active: !power.nativeState; sourceComponent: Component { CameraLock {} } }
            images: tools.offers("screenshot"); videos: tools.offers("recordings"); shelf: root.offerShelf
            onAddFile: url => fileShelf.change({action: "add", urls: [url]})
        }
    }
    Component {
        id: controlsPage
        IslandControls {
            soundAvailable: tools.offers("sound"); brightnessAvailable: tools.offers("display")
            shortcuts: root.sections.filter(item => ["time", "calendar", "notes", "mixer"].includes(item.key)).concat(
                root.offerAwake ? [{key: "awake", label: i18n("Keep awake"), icon: "system-suspend-inhibited", color: "#ffd477"}] : [],
                tools.offers("screenshot") ? [{key: "tool-screenshot", label: i18n("Screenshot"), icon: "spectacle", color: "#a1d9ff"}] : [],
                tools.offers("record") ? [{key: "tool-record", label: i18n("Record screen"), icon: "media-record", color: "#ff8797"}] : [])
            onSelected: key => {
                // These two actions also work before the Tools catalogue has loaded.
                if (key === "tool-screenshot" || key === "tool-record") root.selectTool(key.slice(5))
                else navigation.openDetail(key)
            }
        }
    }
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
                        IslandButton { text: i18n("Now playing"); icon.name: "go-next-symbolic"; implicitHeight: 25; implicitWidth: 25; onClicked: navigation.openDetail("music") }
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
                        IslandButton { text: i18n("Time"); icon.name: "go-next-symbolic"; implicitHeight: 25; implicitWidth: 25; onClicked: navigation.openDetail("time") }
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
            onDraggingChanged: root.draggingShelf = dragging
            Component.onDestruction: root.draggingShelf = false
            onDetachRequested: root.openTool("shelf")
        }
    }
    Component {
        id: mixerPage
        IslandMixer {
            presented: body.presented && body.requested === mixerPage
            outputNames: root.outputNames
            helper: root.helper
            onRefreshOutputs: runner.connectSource(root.helper + " outputs")
        }
    }
    Component {
        id: clipboardPage
        Item {
            id: clipboardView
            readonly property bool notificationOpen: !!history.item?.inDetail
            function backFromNotification() { history.item?.back() }
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
            id: playerPage
            player: visible ? root.media : null; sources: players; playing: visible && root.playing
            liveLevels: Plasmoid.configuration.levels
            view: 0
            Binding {
                target: playerPage; property: "view"; value: root.musicView
                when: body.requested === musicPage && root.musicView < 3
                restoreMode: Binding.RestoreNone
            }
            playback: queuePlayback.item
            formatDuration: root.duration
            gestures: notchGestures
            offerDetails: root.offerMediaDetails; offerMixer: root.offerMixer
            onViewRequested: index => navigation.openDetail(["music","lyrics","queue","mixer"][index])
        }
    }
    Component {
        id: watchPage
        Watch {
            service: watch.watchedService; path: root.watchPath
            onBackRequested: pages.back()
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
            onBackRequested: pages.back()
            onRefreshRequested: { root.downloadAvailable = false; root.refreshActivity() }
            onManageRequested: navigation.openDetail("tool-downloads")
        }
    }
    Component {
        id: toolPage
        ToolDirectory {
            motion: root.motion
            rows: root.toolRows; groups: root.toolGroups; hidden: tools.hidden; favorites: tools.favorites
            group: root.toolGroup; query: root.toolQuery
            onFilterChanged: (group, query) => { root.toolGroup = group; root.toolQuery = query }
            onLoaded: (rows, groups) => root.catalogReady(rows, groups)
            onSelected: key => root.selectTool(key)
            onManageRequested: root.openNotchSettings("tools")
            onRadialRequested: root.openRadialMenu()
        }
    }
    Component {
        id: toolDetails
        NotchTool {
            tool: root.utilityPage.startsWith("tool-") ? root.utilityPage.slice(5) : ""
            ownerId: String(Plasmoid.id)
            active: root.islandOpen && !root.folding && !root.searching && power.active && !!tool && tools.offers(tool)
                && pages.revealProgress === 1 && !resizeMotion.running && body.progress === 1 && body.current?.item === this
            screenName: Screen.name
            property point popupPosition: Qt.point(popup.x, popup.y)
            onPopupPositionChanged: Qt.callLater(reposition)
            onDismissRequested: root.collapse()
            onBackRequested: pages.back()
        }
    }
    component ProviderDetail: AgentDetail {
        usage: provider === "codex" ? codexUsage : provider === "claude" ? claudeUsage : null
        presented: power.active && root.islandOpen && root.utilityPage === "agent-" + provider
        onSettingsChanged: root.refreshActivity()
    }
    Component { id: sessionDetails; ProviderDetail { provider: "session" } }
    Component { id: codexDetails; ProviderDetail { provider: "codex" } }
    Component { id: claudeDetails; ProviderDetail { provider: "claude" } }
    Component {
        id: agentsPage
        TimeScrollView {
            id: agentScroll
            C.ScrollBar.vertical.policy: C.ScrollBar.AlwaysOn
            C.ScrollBar.vertical.active: true
            AgentOverview {
                width: agentScroll.availableWidth
                codex: codexUsage; claude: claudeUsage
                history: agentHistory
                presented: root.agentPageOpen && power.active
                sessionSelected: root.agentsVisible && root.sessionSelected
                widgetId: String(Plasmoid.id)
                sessionReading: root.lastSessionReading
                onSessionReadingChanged: root.lastSessionReading = sessionReading
                onSelected: provider => navigation.openDetail("agent-" + provider)
            }
        }
    }

    Component {
        id: notificationsPage
        NoticeInbox {
            standalone: true
            readonly property bool notificationOpen: inDetail || toRemove.length > 0
            function backFromNotification() { if (toRemove.length) cancelClear(); else back() }
            requestedNotice: root.requestedNotice
            liveSource: root.requestedNotice ? preview.item : null
            onPreviewFinished: root.requestedNotice = 0
            onActivated: root.islandOpen = false
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

            ListView {
                visible: !notices.inDetail && count > 0
                Layout.fillWidth: true; Layout.preferredHeight: 40
                orientation: ListView.Horizontal; spacing: 6; clip: true
                model: power.batteries
                delegate: Rectangle {
                    required property var modelData
                    width: Math.min(180,batteryRow.implicitWidth + 20); height: 36; radius: 10; color: "#17171b"
                    RowLayout {
                        id: batteryRow; anchors.fill: parent; anchors.margins: 8; spacing: 7
                        IslandGlyph { source: "battery"; color: modelData.level < 20 ? "#ffad53" : "#b8cbbb"; Layout.preferredWidth: 18; Layout.preferredHeight: 18 }
                        Text { Layout.fillWidth: true; text: modelData.name || modelData.kind; textFormat: Text.PlainText; elide: Text.ElideRight; font.pixelSize: 10; color: "#aaaab2" }
                        Text { text: modelData.level + "%"; font.pixelSize: 12; color: "white" }
                    }
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
            C.Label {
                readonly property string latestName: downloadFeed.item?.latestFinished ?? ""
                font.pixelSize: 10; color: "#9999a4"; Layout.fillWidth: true; visible: !notices.inDetail && !!latestName; elide: Text.ElideMiddle
                textFormat: Text.PlainText
                text: latestName ? i18n("Latest download · %1", latestName) : ""
            }
            RowLayout {
                visible: !notices.inDetail
                IslandButton { caption: true; visible: root.offerDownloads; text: i18n("Downloads"); onClicked: navigation.openDetail("downloads") }
                IslandButton { caption: true; visible: root.agentsVisible; text: i18n("Agent usage"); onClicked: navigation.openDetail("agents") }
                IslandButton {
                    caption: true; visible: root.offerWatch
                    text: i18n("Watch")
                    onClicked: {
                        if (watch.registered) navigation.openDetail("watch")
                        else {
                            root.selectTool("watch")
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
            onAwakeRequested: navigation.openDetail("awake")
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
            editorParent: pages
            day: root.agendaDay
            onChoose: date => root.agendaDay = date
            onMonthRequested: pages.back()
            onCalendarsRequested: navigation.openDetail("tool-calendars")
        }
    }
    Component {
        id: calendarPage
        ColumnLayout {
            id: calendar
            readonly property bool editingEvent: edit.visible || !!dailyAgenda.item?.editingEvent
            function closeEditor() { if (edit.visible) edit.close(); else dailyAgenda.item?.closeEditor() }
            onEnabledChanged: if (!enabled) edit.close()
            readonly property bool split: width >= 410 && height >= 235 && root.offerAgenda
            spacing: 5
            NoteStore { id: notes; helper: root.helper; Component.onCompleted: refresh() }
            RowLayout {
                Layout.fillWidth: true; Layout.fillHeight: true
                spacing: 14
                Month {
                    id: month
                    Layout.fillWidth: true; Layout.fillHeight: true
                    Layout.preferredWidth: 225; Layout.minimumWidth: 0
                    island: true; titleSize: 16
                    ink: "#f5f5f7"; dim: "#aaaab1"; lily: "#ff6974"
                    notesButton: false; store: notes
                    property bool ready: false
                    Component.onCompleted: { choose(root.agendaDay); ready = true }
                    onChosenChanged: if (ready) root.agendaDay = chosen
                    onOpened: day => { edit.day = day; edit.text = notes.noteFor(day); edit.open() }
                }
                Rectangle {
                    visible: calendar.split
                    Layout.preferredWidth: 1; Layout.fillHeight: true
                    color: "#24ffffff"
                }
                Loader {
                    id: dailyAgenda
                    visible: active; active: calendar.split
                    Layout.fillWidth: true; Layout.fillHeight: true
                    Layout.preferredWidth: 174; Layout.minimumWidth: 0
                    sourceComponent: Agenda {
                        editorParent: pages
                        embedded: true; day: month.chosen
                        onUpcomingRequested: navigation.openDetail("agenda")
                        onCalendarsRequested: navigation.openDetail("tool-calendars")
                    }
                }
            }
            IslandButton {
                Layout.alignment: Qt.AlignHCenter
                visible: root.offerAgenda && !calendar.split; caption: true
                text: i18n("Upcoming events")
                onClicked: { root.agendaDay = month.chosen; navigation.openDetail("agenda") }
            }
            DayNoteDialog {
                id: edit
                parent: pages
                onSaved: (day, text) => notes.write(day, text)
            }
        }
    }
}
