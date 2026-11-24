/*
 * Monet Settings: one window with the settings people actually change, an app of its own
 * (monet-settings) with Monet's frame, as Games is. The list sits on glass, the pages on solid
 * paper (or smoke) so text is always easy to read. Anything rarer is one click away in KDE's
 * System Settings ("More settings").
 *
 * The `monet-quick` helper does the work; this only draws it. monet-settings gives it `helper`
 * (which runs monet-quick and monet), its i18n calls, where its pictures are, and the page to
 * open at; opened again, it comes forward at the page asked for (helper.wanted).
 */
import QtCore
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Templates as T
import QtQuick.Window
import org.kde.kirigami as Kirigami
import "../games" as Shared
import "FocusNavigation.js" as FocusNavigation

Shared.MonetWindow {
    id: sheet

    readonly property real speed: Kirigami.Units.longDuration / 200
    readonly property real availableWidth: typeof windowArea !== "undefined" && windowArea.width > 0
        ? windowArea.width : Math.min(Screen.width, Screen.desktopAvailableWidth)
    readonly property real availableHeight: typeof windowArea !== "undefined" && windowArea.height > 0
        ? windowArea.height : Math.min(Screen.height, Screen.desktopAvailableHeight)
    width: Math.max(1, Math.min(1000, availableWidth - 64))
    height: Math.max(1, Math.min(780, availableHeight - 96))
    minimumWidth: Math.max(1, Math.min(760, availableWidth - 32))
    minimumHeight: Math.max(1, Math.min(520, availableHeight - 48))
    function fitAvailableScreen() {
        if (availableWidth <= 0 || availableHeight <= 0
                || visibility === Window.Maximized || visibility === Window.FullScreen || visibility === Window.Minimized) return
        // Wayland can briefly report Windowed while minimizing a maximized
        // window. Keep a fitting size instead of shrinking it to the margins.
        if (width > availableWidth || width < minimumWidth)
            width = Math.max(minimumWidth, Math.min(width, availableWidth - 32))
        if (height > availableHeight || height < minimumHeight)
            height = Math.max(minimumHeight, Math.min(height, availableHeight - 48))
    }
    onAvailableWidthChanged: Qt.callLater(fitAvailableScreen)
    onAvailableHeightChanged: Qt.callLater(fitAvailableScreen)
    // Wayland can deliver a configure for the old size after a screen change.
    onWidthChanged: if (width > availableWidth || width < minimumWidth) Qt.callLater(fitAvailableScreen)
    onHeightChanged: if (height > availableHeight || height < minimumHeight) Qt.callLater(fitAvailableScreen)
    onVisibleChanged: if (visible) Qt.callLater(fitAvailableScreen)
    onVisibilityChanged: state => { if (state === Window.Windowed) Qt.callLater(fitAvailableScreen) }
    // See-through: the glass column's glass is WindowGlass (Games' and the Store's too).
    color: "transparent"
    // The size people gave it, kept for next time (~/.config/monet/settings.conf).
    Settings {
        category: "Window"
        property alias windowWidth: sheet.width
        property alias windowHeight: sheet.height
    }
    // Updates → Show beta versions, kept the same way: this person's choice, not the PC's.
    Settings {
        category: "Updates"
        property alias showBetas: sheet.showBetas
    }
    property string page: "light"
    readonly property bool pageReady: pageLoader.status === Loader.Ready
    property var searchResults: []
    property int searchRevision: 0
    property bool searchBusy: false
    property string searchReady: ""
    property string searchProblem: ""
    property string pendingAnchor: ""
    property string currentAnchor: ""
    property int anchorAttempts: 0
    property Item highlightedItem: null
    property rect highlightedRect: Qt.rect(0, 0, 0, 0)
    property bool loadScheduled: false
    property var windowsFiles: ({})
    property bool outputBusy: false
    property string outputProblem: ""
    // The output last asked for (and microphoneWanted, the microphone), for Try again: by its
    // name, it's found again even if PipeWire has given it another number since.
    property var outputWanted: null
    // Microphones to choose from (an interface's inputs each by name), and a change underway.
    property var microphones: []
    property bool microphoneBusy: false
    property string microphoneProblem: ""
    property var microphoneWanted: null
    property bool statusBusy: false
    readonly property bool pollingActive: visible && visibility !== Window.Minimized
        && (typeof windowActivity === "undefined" || windowActivity.active)
    readonly property var statusPages: ["light", "wifi", "bluetooth", "display", "sound", "power"]
    readonly property bool statusPage: statusPages.includes(page)
    onPollingActiveChanged: { if (pollingActive) { refresh(); if (page === "power") loadKeepAwake() } }
    onActiveChanged: if (active && page === "display") scheduleLoad()
    // Also acknowledge changes made in another display settings window.
    Screen.onDevicePixelRatioChanged: if (sheet.pollingActive && ["display", "accessibility"].includes(sheet.page)) displayChanged.restart()
    // Wayland's screen DPR is rounded to an integer; fractional changes also
    // change the logical screen geometry even when that rounded DPR stays 2.
    Screen.onDesktopAvailableWidthChanged: if (sheet.pollingActive && ["display", "accessibility"].includes(sheet.page)) displayChanged.restart()
    Screen.onDesktopAvailableHeightChanged: if (sheet.pollingActive && ["display", "accessibility"].includes(sheet.page)) displayChanged.restart()
    Timer {
        id: displayChanged
        interval: 300
        onTriggered: {
            if (sheet.scaleBusy) return
            if (sheet.page === "display") sheet.loadDisplay()
            else if (sheet.page === "accessibility") sheet.ask("display-sizes", out => {
                const sizes = sheet.json(out, [])
                sheet.displaySizes = Array.isArray(sizes) ? sizes : []
            })
        }
    }

    Timer {
        id: searchDelay
        interval: 140
        onTriggered: sheet.findSettings(false)
    }
    Timer {
        id: anchorDelay
        interval: 50
        repeat: true
        running: sheet.pageReady && sheet.pendingAnchor !== "" && sheet.anchorAttempts < 20
            && !(sheet.page === "apps" && sheet.loadingDefaults)
        onTriggered: { sheet.anchorAttempts++; sheet.revealSearchTarget() }
    }

    function findSettings(activate) {
        searchDelay.stop()
        const query = search.text.trim()
        const revision = ++searchRevision
        searchProblem = ""
        if (query === "") { searchResults = []; searchReady = ""; searchBusy = false; return }
        searchBusy = true
        ask("search " + hex(query), (out, code) => {
            if (revision !== sheet.searchRevision || query !== search.text.trim()) return
            const result = sheet.json(out, {})
            const ok = code === 0 && Array.isArray(result.results)
            sheet.searchBusy = false
            sheet.searchReady = ok ? query : ""
            sheet.searchResults = ok ? result.results : []
            sheet.searchProblem = ok ? "" : i18n("Search couldn't finish. Try again.")
            if (activate && ok) sheet.activateSearch()
        })
    }
    function activateSearch() {
        if (searchReady !== search.text.trim()) { findSettings(true); return }
        if (searchResults.length > 0) { openSearchResult(searchResults[0]); return }
        const typed = side.fold(search.text.trim())
        const shown = pages.filter(p => side.matches(p))
        const first = shown.find(p => side.fold(p.name) === typed)
            || shown.find(p => side.fold(p.name).startsWith(typed)) || shown[0]
        if (first) { search.text = ""; open(first.id) }
    }
    function openSearchResult(result) {
        if (result.target === "calendar" || result.target.endsWith(".desktop")) {
            ask("search-open " + result.id, (out, code) => {
                if (code !== 0 || sheet.json(out, {}).ok !== true)
                    sheet.searchProblem = i18n("Couldn't open this result. Try again.")
                else sheet.searchProblem = ""
            })
        } else {
            search.text = ""
            open(result.target)
        }
    }
    function findNamedItem(item, name) {
        if (!item) return null
        if (item.objectName === name) return item
        for (let child of item.children || []) {
            const found = findNamedItem(child, name)
            if (found) return found
        }
        return null
    }
    function findSearchTarget(item, name) {
        return findNamedItem(item, "search-" + name)
    }
    function focusControl(name) {
        const item = findNamedItem(pageLoader.item, name)
        if (item && item.visible && item.enabled) item.forceActiveFocus(Qt.OtherFocusReason)
    }
    function revealSearchTarget() {
        const target = findSearchTarget(pageLoader.item, pendingAnchor)
        if (!target || !target.visible || target.height <= 0) return
        const top = target.mapToItem(scroller.contentItem, 0, 0).y
        const margin = Math.min(40, Math.max(0, (scroller.height - target.height) / 2))
        scroller.contentY = Math.max(0, Math.min(top - margin, scroller.contentHeight - scroller.height))
        target.forceActiveFocus(Qt.ShortcutFocusReason)
        highlightedItem = target
        updateSearchHighlight()
        searchHighlight.restart()
        pendingAnchor = ""
    }

    Timer {
        id: searchHighlight
        interval: 1800
        onTriggered: sheet.highlightedItem = null
    }
    function updateSearchHighlight() {
        if (!highlightedItem) return
        const point = highlightedItem.mapToItem(scroller.contentItem, 0, 0)
        highlightedRect = Qt.rect(point.x - 2, point.y - 2, highlightedItem.width + 4, highlightedItem.height + 4)
    }
    Connections {
        target: sheet.highlightedItem
        function onXChanged() { sheet.updateSearchHighlight() }
        function onYChanged() { sheet.updateSearchHighlight() }
        function onWidthChanged() { sheet.updateSearchHighlight() }
        function onHeightChanged() { sheet.updateSearchHighlight() }
    }
    Rectangle {
        objectName: "searchHighlightOutline"
        parent: scroller.contentItem
        x: sheet.highlightedRect.x
        y: sheet.highlightedRect.y
        width: sheet.highlightedRect.width
        height: sheet.highlightedRect.height
        z: 1000
        visible: sheet.highlightedItem !== null
        color: Qt.rgba(look.lily.r, look.lily.g, look.lily.b, 0.09)
        radius: 14
    }

    readonly property string art: pictures
    // Each page's search words are said in your language too: what people might type to find
    // it, with the English ones people use anyway (wifi, bluetooth) kept in.
    readonly property var pages: [
        { id: "light", name: i18n("Light & Wallpaper"), glyph: "M5 15a7 7 0 0 1 14 0M3 19h18",
          words: i18nc("Settings search words, space-separated",
                      "light wallpaper painting hours mist smoke dark mode glass placard clock theme appearance colors")
              + " " + i18nc("Settings search words, space-separated", "photo picture own painted")
              + " " + i18nc("Settings search words, space-separated", "transparent transparency see-through frosted matte solid blur")
              + " " + i18nc("Settings search words, space-separated", "snap layouts assist windows side by side halves tiling")
              + " " + i18nc("Settings search words, space-separated", "title bar titlebar borderless window frame buttons") },
        { id: "wifi", name: i18n("Internet"), glyph: "M12 2a10 10 0 1 0 0 20a10 10 0 0 0 0-20M2 12h20M12 2c-5 5-5 15 0 20M12 2c5 5 5 15 0 20",
          words: i18nc("Settings search words, space-separated",
                      "wifi wi-fi wireless network internet password") },
        { id: "bluetooth", name: i18n("Bluetooth"), glyph: "M7 7l10 10-5 5V2l5 5L7 17",
          words: i18nc("Settings search words, space-separated",
                      "bluetooth headphones controller gamepad mouse keyboard pair") },
        { id: "phone", name: i18n("Phone"), glyph: "M8 3h8v18H8zM11 18h2",
          words: i18nc("Settings search words, space-separated",
                      "phone mobile android iphone kde connect texts messages sms notifications send files pair ring find") },
        { id: "printers", name: i18n("Printers"), glyph: "M7 9V4h10v5M7 17H5a1 1 0 0 1-1-1v-5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v5a1 1 0 0 1-1 1h-2M7 14h10v6H7z",
          words: i18nc("Settings search words, space-separated",
                      "printers printer print scanner paper queue default add") },
        { id: "display", name: i18n("Display"), glyph: "M4 5h16v11H4zM10 20h4",
          words: i18nc("Settings search words, space-separated",
                      "display screen brightness night light monitor resolution scale size hdr vrr freesync g-sync refresh tearing") },
        { id: "sound", name: i18n("Sound"), glyph: "M5 10h3l5-4v12l-5-4H5zM17 9a4.5 4.5 0 0 1 0 6",
          words: i18nc("Settings search words, space-separated",
                      "sound volume speakers headphones microphone mic audio output") },
        { id: "datetime", name: i18n("Date & Time"), glyph: "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 7v5l3 2",
          words: i18nc("Settings search words, space-separated",
                      "date time clock time zone 24-hour format automatic") },
        { id: "users", name: i18n("Accounts"), glyph: "M8 8a4 4 0 1 0 8 0a4 4 0 1 0-8 0M4 21a8 8 0 0 1 16 0",
          words: i18nc("Settings search words, space-separated",
                      "accounts users password picture people name login sign in")
              + " " + i18nc("Settings search words, space-separated", "guest visitor") },
        { id: "input", name: i18n("Mouse & Keyboard"), gap: true,
          glyph: "M9 3h6a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3H9a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3zM12 3v5",
          words: i18nc("Settings search words, space-separated",
                      "mouse keyboard touchpad trackpad pointer speed scrolling natural tap click left-handed layout language typing") },
        { id: "power", name: i18n("Power & Sleep"),
          glyph: "M12 3v8M7 6.5a7 7 0 1 0 10 0",
          words: i18nc("Settings search words, space-separated",
                      "power sleep suspend screen off energy battery lid button shutdown performance saver mode lock locker wake away password")
              + " " + i18nc("Settings search words, space-separated", "restart reboot reopen apps again windows remember session") },
        { id: "privacy", name: i18n("Privacy"), glyph: "M6.5 11h11v9h-11zM9 11V8a3 3 0 0 1 6 0v3",
          words: i18nc("Settings search words, space-separated",
                      "privacy recent files history forget remember fingerprint finger") },
        { id: "passwords", name: i18n("Passwords"), swatch: "privacy", glyph: "M8 14a5 5 0 1 1 4-8M12 10l9 9M17 15l3-3",
          words: i18nc("Settings search words, space-separated", "password passwords wallet vault autofill saved logins app access unlock password manager") },
        { id: "security", name: i18n("Security"), glyph: "M12 3l7.5 3v5.5c0 4.6-3.1 8.4-7.5 9.5-4.4-1.1-7.5-4.9-7.5-9.5V6zM9 12l2.2 2.2L15.5 10",
          words: i18nc("Settings search words, space-separated",
                      "security safe safety protection protected secure boot encryption encrypted firewall updates firmware backups selinux") },
        { id: "notifications", name: i18n("Notifications"),
          glyph: "M6 16v-5a6 6 0 0 1 12 0v5l2 2H4zM10 20h4",
          words: i18nc("Settings search words, space-separated",
                      "notifications alerts do not disturb quiet popups sounds apps") },
        { id: "accessibility", name: i18n("Accessibility"),
          glyph: "M12 5h.01M5 8.5l7 1.5 7-1.5M12 10v4.5M8.5 20.5l3.5-6 3.5 6",
          words: i18nc("Settings search words, space-separated",
                      "accessibility bigger larger text size scale zoom pointer cursor motion animation screen reader orca see read magnifier magnify") },
        { id: "apps", name: i18n("Default Apps"),
          glyph: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
          words: i18nc("Settings search words, space-separated",
                      "default apps browser web email mail files music video photos pdf text open with")
              + " " + i18nc("Settings search words, space-separated", "bookmarks favorites passwords import windows edge chrome firefox zen") },
        { id: "storage", name: i18n("Storage"),
          glyph: "M4 7.5h16v9H4zM7.5 12h.01M11 12h5.5",
          words: i18nc("Settings search words, space-separated",
                      "storage disk space room full free trash downloads clean games apps onedrive cloud microsoft") },
        { id: "backups", name: i18n("Backups"), glyph: "M4.5 12a7.5 7.5 0 1 0 2.2-5.3M4.5 4.5v3h3M12 8.5V12l2.5 1.5",
          words: i18nc("Settings search words, space-separated",
                      "backups backup copy restore earlier versions history snapshot undo lost deleted usb drive time machine") },
        { id: "games", name: i18n("Games & Controllers"), gap: true,
          glyph: "M7.5 8h9a4.5 4.5 0 0 1 4.5 4.5v1a3.5 3.5 0 0 1-6.4 2L14 14.5h-4l-.6 1A3.5 3.5 0 0 1 3 13.5v-1A4.5 4.5 0 0 1 7.5 8zM8 10.5v3M6.5 12h3M15.5 11.5h.01M17.5 13h.01",
          words: i18nc("Settings search words, space-separated",
                      "games controller gamepad joystick xbox playstation dualsense battery pair test buttons overlay fps mangohud performance steam library installed heroic lutris")
              + " " + i18nc("Settings search words, space-separated", "shared both install once folder epic gog") },
        { id: "windows", name: i18n("Play on Windows"), glyph: "M9 6.5L18 12l-9 5.5z", filled: true,
          words: i18nc("Settings search words, space-separated",
                      "windows games play anti-cheat steam restart boot doctor check")
              + " " + i18nc("Settings search words, space-separated", "apps reopen again session") },
        { id: "updates", name: i18n("Updates"), glyph: "M12 4v11M7 10l5 5 5-5M5 20h14",
          words: i18nc("Settings search words, space-separated",
                      "updates update version upgrade new reset restore rollback") },
        { id: "recovery", name: i18n("Recovery"), swatch: "backups", glyph: "M4.5 12a7.5 7.5 0 1 0 2.2-5.3M4.5 4.5v3h3",
          words: i18nc("Settings search words, space-separated", "recovery undo desktop settings preferences shortcuts update restore repair") },
        { id: "about", name: i18n("About Monet"), glyph: "M12 7.5h.01M12 11v6",
          words: i18nc("Settings search words, space-separated",
                      "about pc computer specs graphics gpu processor cpu memory ram storage disk version report logs problem")
              + " " + i18nc("Settings search words, space-separated", "terminal command line tools container distrobox toolbox developer") }
    ]

    // What the helper reported.
    property var info: ({})
    property var prefs: ({ hours: true, placard: true, glass: "clear", weather: true, dodge: true })
    // Your photo, painted (monet-paint): {state: "" | "painting" | "ready", percent, preview, failed}.
    property var photoInfo: ({ state: "" })
    property bool photoLoading: false
    property var nets: []
    // The cables (monet-quick lan): {available, devices: [{device, profile, state, ipv4, ipv6, gateways, dns}]}.
    property var wiredNetwork: null
    property bool wiredNetworkLoading: false
    // Whether a look for networks has come back yet (until then: looking).
    property bool netsLoaded: false
    property var devices: []
    property var outputs: []
    property var audioRename: null
    property bool audioRenameBusy: false
    property string audioRenameProblem: ""
    // The apps playing sound, each with its own volume.
    property var appsSound: []
    property bool appsSoundLoading: false
    property var notificationAudio: ({})
    property string notificationAudioProblem: ""
    property bool notificationAudioSaving: false
    // Battery care: whether the battery can stop at 80%, and where it stops.
    property var batteryCare: ({})
    property var keepAwakeInfo: ({ active: false, duration: 0, end: 0, remaining: 0, error: "" })
    property bool keepAwakeBusy: false
    property bool keepAwakeReading: false
    property int keepAwakeRevision: 0
    property int keepAwakeTick: 0
    property string keepAwakeProblem: ""
    readonly property int keepAwakeLeft: {
        const tick = keepAwakeTick
        if (!keepAwakeInfo.active || keepAwakeInfo.indefinite) return 0
        const now = typeof bootClock !== "undefined" ? bootClock.now() : Date.now() / 1000
        return Math.max(0, Math.ceil((keepAwakeInfo.end || 0) - now))
    }
    Timer {
        interval: 1000
        repeat: true
        running: sheet.pollingActive && sheet.page === "power" && sheet.keepAwakeInfo.active === true
            && sheet.keepAwakeInfo.indefinite !== true
        onTriggered: sheet.keepAwakeTick++
    }
    Timer {
        interval: 10000
        repeat: true
        running: sheet.pollingActive && sheet.page === "power"
        onTriggered: sheet.loadKeepAwake()
    }
    // This PC's own Wi-Fi network for phones and tablets.
    property var hotspot: ({ on: false, possible: false })
    // Ready when you come back: after Windows, the desktop starts behind the lock screen.
    property var ready: ({ on: false })
    // How long the last start took: { pc, monet, desktop, total } in seconds.
    property var startup: ({})
    property string hotspotState: ""
    property var games: []
    property var pc: ({})
    property var clock: ({})
    property var zones: []
    // You first, then everyone else on this PC.
    property var people: []
    // The Guest account (monet-guest): {on}; busy while an administrator's password is asked for.
    property var guestInfo: ({ on: false })
    property bool guestBusy: false
    // Power & Sleep, Mouse & Keyboard, Notifications and Default Apps, as the helper reports them.
    property var powerInfo: ({})
    property bool powerBusy: false
    property string powerProblem: ""
    readonly property string batteryPowerZone: typeof info.battery !== "number" ? "unknown"
        : info.plugged === true ? "ac" : info.battery <= (powerInfo.batterySaverThreshold || 20) ? "low" : "battery"
    onBatteryPowerZoneChanged: Qt.callLater(() => { if (pollingActive && page === "power") powerStateRefresh.restart() })
    Timer { id: powerStateRefresh; interval: 150; onTriggered: if (sheet.pollingActive && sheet.page === "power" && !sheet.powerBusy) sheet.reloadPower() }
    property var inputInfo: ({})
    property var knownLayouts: []
    property var notifyInfo: ({})
    property string notifyBusy: ""
    property string notifyMessage: ""
    property bool notifyFailed: false
    property string notifyRetry: ""
    property int notifyRevision: 0
    property var appDefaults: []
    property bool loadingDefaults: false
    // Default Apps' From Windows: the bookmarks kept from Windows' browsers (monet-quick windows-browsers).
    property var browserInfo: ({})
    property var storageInfo: ({})
    // Each storage answer carries its request's number: an older one coming back late is ignored.
    property int storageRequest: 0
    property bool storageLoaded: false
    property bool storageBusy: false
    property var disks: []
    property bool disksLoading: false
    property bool diskBusy: false
    property bool disksLoaded: false
    property string diskProblem: ""
    property var retained: []
    property var retainedReview: null
    property bool retainedBusy: false
    property bool retainedLoaded: false
    property string retainedMessage: ""
    property string retainedArchive: ""
    property bool retainedConsent: false
    property var retainedExport: null
    property var health: ({})
    property bool healthBusy: false
    property string healthError: ""

    function recoverStorage(action, item, destination) {
        if (retainedBusy) return
        if (action === "delete" && (!retainedConsent || !retainedReview || !item
                || item.id !== retainedReview.id || item.token !== retainedReview.token)) return
        retainedBusy = true
        retainedMessage = action === "export" ? i18n("Saving your files. Keep Settings open until this finishes…") : i18n("Checking the saved installation…")
        ask("storage-recovery " + action + (item ? " " + item.id + " " + item.token : "")
            + (destination ? " " + hex(destination) : ""), (out, code) => {
            sheet.retainedBusy = false
            const result = sheet.json(out, {ok: false})
            if (!result.ok || code !== 0) {
                sheet.retainedReview = null
                sheet.retainedMessage = result.state === "unsupported" ? i18n("This disk layout does not support unfinished-install recovery.")
                    : result.state === "busy" ? i18n("Another recovery operation is running. Wait, then try again.")
                    : result.state === "changed" || result.state === "in-use" ? i18n("The saved installation changed or is in use. Refresh before trying again.")
                    : i18n("The operation did not finish or permission was cancelled. Refresh to check what remains before trying again.")
                return
            }
            sheet.retainedMessage = ""
            if (action === "list") {
                sheet.retained = result.items || []
                sheet.retainedLoaded = true
                sheet.retainedReview = null
                if (result.limited) sheet.retainedMessage = i18n("Showing the first 64 saved installations. Refresh after cleanup to see more.")
            } else if (action === "review") {
                sheet.retainedReview = result.item
                sheet.retainedConsent = false
            } else if (action === "export") {
                sheet.retainedArchive = result.path
                sheet.retainedMessage = i18n("Your files were saved in an archive. Open it and check the files before removing the saved installation.")
            } else if (action === "delete") {
                sheet.retained = sheet.retained.filter(entry => entry.id !== item.id)
                sheet.retainedReview = null
                sheet.retainedMessage = i18n("Saved installation removed. Freed space may take a moment to appear.")
                sheet.loadStorage()
            }
        })
    }
    FolderDialog {
        id: recoveryFolder
        title: i18n("Choose where to save your recovered files")
        onAccepted: {
            const url = selectedFolder.toString()
            if (url.startsWith("file:///")) sheet.recoverStorage("export", sheet.retainedExport, decodeURIComponent(url.slice(7)))
            sheet.retainedExport = null
        }
        onRejected: sheet.retainedExport = null
    }
    function checkHealth() {
        if (healthBusy) return
        healthBusy = true
        healthError = ""
        ask("troubleshooting", (out, code) => {
            sheet.healthBusy = false
            const result = sheet.json(out, {ok: false})
            if (result.ok && code === 0) sheet.health = result
            else sheet.healthError = i18n("The recovery check could not finish. Try again.")
        })
    }
    property string storageProblem: ""
    // Storage → OneDrive (monet-quick onedrive): its state, what's being done, and a sign-in that didn't finish.
    property var oneDrive: ({})
    property string oneDriveBusy: ""
    property bool oneDriveProblem: false
    property bool oneDriveCancelled: false
    // Which games play here and which need Windows (anti-cheat), by Steam id.
    property var gameMarks: ({ marks: {}, blocked: [] })
    // The screens that can show HDR or keep pace with games: [{name, hdr, vrr}].
    property var screenInfo: []
    // Backups: earlier versions, and the copy on a drive.
    property var backup: ({ versions: true, drives: [], lookBack: {} })
    property bool backupLoading: false
    // The earlier versions of one file, when Files asked for them.
    property var earlier: ({})
    property bool earlierBusy: false
    property string earlierMessage: ""
    function useEarlier(action, item) {
        if (earlierBusy) return
        earlierBusy = true
        earlierMessage = action === "put-back" ? i18n("Restoring a copy…") : ""
        ask(action + " " + hex(earlier.file) + " " + hex(item.name), out => {
            sheet.earlierBusy = false
            const result = sheet.json(out, {})
            sheet.earlierMessage = result.ok ? (action === "put-back" ? i18n("The restored copy is beside your file.") : "")
                : result.state === "changed" ? i18n("The list of earlier versions changed. Open it again and choose a version.")
                : i18n("The copy could not be restored. Check free space and folder permissions, then try again.")
        })
    }
    // Games & Controllers: { controllers, overlay, pair, libraries }.
    property var gameInfo: ({})
    // What's new in this Monet: { version, headline, items: [{ title, text }] }.
    property var whatsNew: ({})
    // Privacy: { remember, fingerprint }; Printers: { printers, cups }.
    property var privacyInfo: ({})
    property var walletInfo: ({})
    property bool walletBusy: false
    property string walletProblem: ""
    property bool walletChanged: false
    property var printerInfo: ({})
    // The Monet before the last update: { version, date, pending }, or {}.
    property var previous: ({})
    property var profileHistory: []
    property var profileReview: null
    property bool profileLoading: false
    property bool profileRestoring: false
    property string profileState: ""
    property string profileMessage: ""
    // An update that didn't start here, so Monet went back by itself: { version, to }, or {}.
    property var wentBack: ({})
    // Reset this PC: { pending } once it waits for the next restart.
    property var resetState: ({})
    property var accessInfo: ({})
    property var displaySizes: []
    property bool scaleBusy: false
    property string scaleProblem: ""
    // Phone: the phones KDE Connect knows ([{id, name, paired, near, battery, charging}]),
    // whether it's here at all, and the one asked to pair (its answer is on the phone).
    property var phoneList: []
    property bool phoneApp: true
    property string phoneAsked: ""
    property bool phoneChecking: false
    property bool phoneFailed: false
    property bool phoneSending: false
    property string phoneFileState: ""
    // About → Save a report: being written, and the name of the one saved.
    property bool reporting: false
    // About → Command-line tools: BoxBuddy on its way from Flathub.
    property bool gettingTools: false
    property string reportSaved: ""
    property bool dragging: false

    // Wi-Fi: the network being joined, and how it went.
    property string joining: ""
    property string joinState: ""
    // Bluetooth: the device that's connecting or disconnecting.
    property string busyDevice: ""
    // Windows: the game (or {} for Windows itself) waiting for a yes.
    property var asking: null
    property var windowsSetup: ({})
    property bool windowsSetupStarting: false
    property string windowsSetupProblem: ""
    property url windowsIso: ""

    function refreshWindowsSetup() {
        ask("windows-setup-status", (out, code) => {
            if (code === 0) sheet.windowsSetup = sheet.json(out, sheet.windowsSetup)
        })
    }

    function startWindowsSetup(iso, retry) {
        windowsSetupStarting = true
        windowsSetupProblem = ""
        const argument = iso ? " " + hex(String(iso)) : (retry ? " --retry" : "")
        ask("windows-setup-start" + argument, (out, code) => {
            if (code !== 0) sheet.windowsSetupProblem = sheet.json(out, {}).message
                || i18n("Windows setup couldn't start. Wait for any current setup to finish, then try again.")
            else if (iso) sheet.windowsIso = ""
            sheet.refreshWindowsSetup()
            sheet.windowsSetupStarting = false
        })
    }
    // When Windows games were last updated (an update trip), as Unix time; 0 if never.
    property real gamesUpdated: 0
    property bool switching: false
    property string switchProblem: ""
    property string doctorReport: ""
    property bool checkingDoctor: false
    property var returnInfo: ({available: false, busy: false, items: []})
    property bool returnLoading: false
    property bool returnBusy: false
    property int returnRevision: 0
    property string returnProblem: ""
    property string returnReadProblem: ""
    function returnFocusTarget(item, name) {
        if (!item) return null
        if (item.objectName === name) return item
        for (let child of item.children || []) {
            const found = returnFocusTarget(child, name)
            if (found) return found
        }
        return null
    }
    function applyReturnState(state) {
        // Identical polling results must not rebuild the focused delegate.
        if (JSON.stringify(state) === JSON.stringify(returnInfo)) return
        const focused = activeFocusItem ? activeFocusItem.objectName : ""
        returnInfo = state
        if (focused.indexOf("return") === 0) Qt.callLater(() => {
            const same = sheet.returnFocusTarget(pageLoader.item, focused)
            const target = same && same.visible && same.enabledPill !== false ? same
                : sheet.findSearchTarget(pageLoader.item, "return")
            if (target) target.forceActiveFocus(Qt.ShortcutFocusReason)
        })
    }
    function loadReturn() {
        if (returnLoading || returnBusy) return
        returnLoading = true
        const revision = ++returnRevision
        ask("return-status", (out, code) => {
            if (revision !== sheet.returnRevision) return
            sheet.returnLoading = false
            const state = sheet.json(out, {})
            if (code === 0 && Array.isArray(state.items) && typeof state.busy === "boolean") {
                sheet.applyReturnState(state)
                sheet.returnReadProblem = ""
            } else sheet.returnReadProblem = i18n("The return summary couldn't load. Try again.")
        })
    }
    function returnAction(action, app) {
        if (returnBusy || returnInfo.busy || !returnInfo.id) return
        returnBusy = true
        returnLoading = false
        const revision = ++returnRevision
        returnProblem = ""
        ask("return-" + action + " " + returnInfo.id + (app ? " " + app : ""), (out, code) => {
            if (revision !== sheet.returnRevision) return
            sheet.returnBusy = false
            const result = sheet.json(out, {})
            if (code === 0 && result.ok === true && result.state && Array.isArray(result.state.items)) {
                sheet.applyReturnState(result.state)
                if (action === "dismiss") {
                    const card = sheet.findSearchTarget(pageLoader.item, "return")
                    if (card) card.forceActiveFocus(Qt.ShortcutFocusReason)
                }
            } else sheet.returnProblem = i18n("That action couldn't finish. Try again; your saved recovery list is still here.")
            sheet.loadReturn()
        })
    }
    Timer {
        interval: 1800
        repeat: true
        triggeredOnStart: true
        running: sheet.pollingActive && sheet.page === "windows"
        onTriggered: {
            sheet.loadReturn()
            sheet.refreshWindowsSetup()
        }
    }
    // While a restart's apps are still reopening, its summary on Power & Sleep keeps up.
    Timer {
        interval: 1800
        repeat: true
        running: sheet.pollingActive && sheet.page === "power" && sheet.returnInfo.busy === true
        onTriggered: sheet.loadReturn()
    }
    function setReopenWork(on) {
        sheet.ready = sheet.changed(sheet.ready, ["apps"], on)
        sheet.ask("trip-apps " + (on ? "on" : "off"), out => sheet.ready = sheet.json(out, sheet.ready))
    }
    // Updates: "", "checking", "none", "available", "installing", "done" or
    // "failed"; what the check found; and what Monet said.
    property string updateState: ""
    property bool updateStaged: false
    property int updateInstallRevision: 0
    readonly property bool updateRestartReady: updateStaged && ["done", "failed"].includes(updateState)
        && betaState !== "installing" && !betaRestartReady
    property var updateFound: ({})
    property string updateMessage: ""
    property var updateHistory: ({ ok: false, items: [], state: "unknown" })
    property bool updateHistoryBusy: false
    // Betas, for whoever turns on Show beta versions: what the last check offered ({ version,
    // number, tag, notes }, or null), why it couldn't look, and installing it: "", "installing",
    // "done" or "failed". Only Install beta installs one; the release replaces it by itself.
    property bool showBetas: false
    property var betaFound: null
    property bool betaChecked: false
    property string betaMessage: ""
    property string betaState: ""
    property bool betaStaged: false
    readonly property bool betaRestartReady: showBetas && betaState === "done" && betaStaged && updateStaged
    // Firmware for the PC's own parts (fwupd): the same states, and the updates.
    // Security: what keeps the PC safe (monet-quick security), the fix that's running, asking
    // before the restart into the firmware settings, and Monet's key asked for.
    property var safety: ({})
    property string securityFixing: ""
    property bool securityChecking: false
    property bool securityChecked: false
    property int securityCheckId: 0
    property string securityProblem: ""
    property string securityConfirmation: ""
    property bool keyAsked: false
    property string firmwareState: ""
    property var firmware: []
    property string firmwareMessage: ""
    readonly property bool firmwareRestart: firmware.some(f => f.restart)
    // Accounts: changing your name, and your password: "", "open", "changing", "done" or
    // "failed", with what went wrong.
    property bool renaming: false
    // Games & Controllers: Windows' BitLocker drive being opened, and what went wrong.
    property bool unlocking: false
    property string unlockProblem: ""
    property string nameProblem: ""
    property string passwordState: ""
    property string passwordMessage: ""
    // Each language's locale with a 12-hour clock, and its nearest with a 24-hour one.
    readonly property var clocks: ({ en: ["en_US.UTF-8", "en_GB.UTF-8"] })

    title: i18n("Settings")
    visible: false
    Component.onCompleted: open(firstPage)

    function open(which) {
        fitAvailableScreen()
        const destination = (which === "privacy#passwords" ? "passwords" : (which || "")).split("#")
        if (destination[0] && (destination[0] === "welcome" || pages.some(p => p.id === destination[0]))) {
            pendingAnchor = /^[a-z-]+$/.test(destination[1] || "") ? destination[1] : ""
            anchorAttempts = 0
            page = destination[0]
            currentAnchor = pendingAnchor
        }
        bringForward()
        scheduleLoad()
    }

    function scheduleLoad() {
        if (loadScheduled) return
        loadScheduled = true
        Qt.callLater(() => {
            sheet.loadScheduled = false
            if (sheet.visible) sheet.load()
        })
    }

    onPageChanged: {
        highlightedItem = null
        currentAnchor = ""
        joining = ""
        asking = null
        renaming = false
        if (passwordState !== "changing") {
            passwordState = ""
        }
        if (visible) {
            scheduleLoad()
        }
    }

    // Running the helper ----------------------------------------------------

    property var waiting: ({})

    // ["helper" (monet-quick) or "monet", the words it's given...]
    function call(command, then) {
        waiting[helper.run(command)] = then || null
    }
    // Arguments are fixed words, numbers, or hex; never raw text from people.
    function ask(args, then) {
        call(["helper"].concat(args.split(" ").filter(word => word !== "")), then)
    }
    Connections {
        target: helper
        function onDone(ticket, out, code, err) {
            const then = sheet.waiting[ticket]
            delete sheet.waiting[ticket]
            if (then) {
                then(out, code, err)
            }
        }
        // Opened again (the menu, a link, Windows+I): here, at the page asked for.
        function onWanted(which) {
            sheet.open(which)
        }
    }
    function tell(args) {
        ask(args, () => refresh())
    }
    function json(text, fallback) {
        try {
            const found = JSON.parse(text)
            if (Array.isArray(fallback)) return Array.isArray(found) ? found : fallback
            if (fallback !== null && typeof fallback === "object")
                return found !== null && typeof found === "object" && !Array.isArray(found) ? found : fallback
            return found === null ? fallback : found
        } catch (e) {
            return fallback
        }
    }

    function refresh() {
        // onPageChanged can run before the statusPage binding re-evaluates.
        if (!pollingActive || !statusPages.includes(page) || statusBusy) return
        statusBusy = true
        const requestedPage = page
        ask("status " + requestedPage, out => {
            sheet.statusBusy = false
            if (sheet.page !== requestedPage) { sheet.refresh(); return }
            if (!sheet.dragging) sheet.info = Object.assign({}, sheet.info, sheet.json(out, {}))
        })
    }

    function loadDisplay() {
        ask("display-state", out => {
            if (sheet.page !== "display") return
            const state = sheet.json(out, {}) || {}
            sheet.screenInfo = Array.isArray(state.features) ? state.features : []
            sheet.displaySizes = Array.isArray(state.sizes) ? state.sizes : []
        })
    }

    function load() {
        refresh()
        if (page === "light") {
            ask("prefs", out => sheet.prefs = sheet.json(out, sheet.prefs))
            loadPhotoState()
        } else if (page === "wifi") {
            loadWiredNetwork()
            ask("wifi-list", out => { sheet.nets = sheet.json(out, []); sheet.netsLoaded = true })
            ask("hotspot", out => sheet.hotspot = sheet.json(out, sheet.hotspot))
        } else if (page === "bluetooth") {
            ask("bt-list", out => sheet.devices = sheet.json(out, []))
        } else if (page === "sound") {
            ask("outputs", out => { if (!sheet.outputBusy) sheet.outputs = sheet.json(out, []) })
            loadMicrophones()
            loadAppsSound()
        } else if (page === "about") {
            ask("startup", out => sheet.startup = sheet.json(out, {}))
        } else if (page === "security") {
            securityConfirmation = ""
            loadSecurity()
            if (firmwareState !== "installing" && firmwareState !== "done") {
                checkFirmware()
            }
        } else if (page === "windows") {
            loadReturn()
            ask("ready", out => sheet.ready = sheet.json(out, sheet.ready))
            ask("game-marks", out => sheet.gameMarks = sheet.json(out, sheet.gameMarks))
            // The games Windows plays, from the one library the Games gallery shows too.
            ask("library", out => sheet.games = sheet.json(out, []).filter(g => g.windows !== "")
                .map(g => ({ id: g.windows, name: g.name, art: g.art, here: g.plays === "monet" })))
            call(["monet", "games", "--updated"], out => sheet.gamesUpdated = parseInt(out) || 0)
        } else if (page === "datetime") {
            ask("time", out => sheet.clock = sheet.json(out, sheet.clock))
            if (zones.length === 0) {
                ask("zones", out => sheet.zones = sheet.json(out, []))
            }
        } else if (page === "users") {
            ask("accounts", out => sheet.people = sheet.json(out, sheet.people))
            ask("guest", out => sheet.guestInfo = sheet.json(out, sheet.guestInfo))
        } else if (page === "power") {
            loadKeepAwake()
            ask("power", out => sheet.powerInfo = sheet.json(out, sheet.powerInfo))
            ask("battery-care", out => sheet.batteryCare = sheet.json(out, sheet.batteryCare))
            // Reopen your work, and what didn't reopen after the last restart.
            ask("ready", out => sheet.ready = sheet.json(out, sheet.ready))
            loadReturn()
        } else if (page === "input") {
            ask("input", out => sheet.inputInfo = sheet.json(out, sheet.inputInfo))
            ask("prefs", out => sheet.prefs = sheet.json(out, sheet.prefs))  // Windows+Z goes with Snap layouts
            if (knownLayouts.length === 0) {
                ask("layouts-known", out => sheet.knownLayouts = sheet.json(out, []))
            }
        } else if (page === "notifications") {
            loadNotifications()
        } else if (page === "apps") {
            loadingDefaults = true
            ask("defaults", out => {
                sheet.appDefaults = sheet.json(out, sheet.appDefaults)
                sheet.loadingDefaults = false
            })
            ask("windows-browsers", out => sheet.browserInfo = sheet.json(out, sheet.browserInfo))
        } else if (page === "display") {
            loadDisplay()
        } else if (page === "storage") {
            loadDisks()
            if (!storageBusy) loadStorage()
            ask("onedrive", out => sheet.oneDrive = sheet.json(out, sheet.oneDrive))
            ask("shared-files", out => sheet.windowsFiles = sheet.json(out, {}))
        } else if (page === "backups") {
            loadBackup()
            ask("versions", out => sheet.earlier = sheet.json(out, {}))
        } else if (page === "phone") {
            phoneAsked = ""
            loadPhones()
        } else if (page === "accessibility") {
            ask("access", out => sheet.accessInfo = sheet.json(out, sheet.accessInfo))
            ask("display-sizes", out => {
                const sizes = sheet.json(out, [])
                sheet.displaySizes = Array.isArray(sizes) ? sizes : []
            })
        } else if (page === "games") {
            ask("gaming", out => sheet.gameInfo = sheet.json(out, sheet.gameInfo))
            ask("game-marks", out => sheet.gameMarks = sheet.json(out, sheet.gameMarks))
        } else if (page === "privacy") {
            ask("privacy", out => sheet.privacyInfo = sheet.json(out, sheet.privacyInfo))
        } else if (page === "passwords") {
            walletAction("status")
        } else if (page === "printers") {
            ask("printers", out => sheet.printerInfo = sheet.json(out, sheet.printerInfo))
        }
        if (page === "recovery") loadProfileHistory()
        if (page === "updates") {
            loadUpdateHistory()
            ask("previous", out => sheet.previous = sheet.json(out, {}))
            ask("whats-new", out => sheet.whatsNew = sheet.json(out, {}))
            ask("went-back", out => sheet.wentBack = sheet.json(out, {}))
            ask("reset-state", out => sheet.resetState = sheet.json(out, {}))
        }
        if (page === "windows" || page === "updates" || page === "about") {
            ask("about", out => sheet.pc = sheet.json(out, sheet.pc))
        }
    }

    function loadWiredNetwork() {
        if (wiredNetworkLoading) return
        wiredNetworkLoading = true
        ask("lan", (out, code) => {
            sheet.wiredNetworkLoading = false
            const next = sheet.json(out, {})
            sheet.wiredNetwork = code === 0 && Array.isArray(next.devices) ? next : { available: false, devices: [] }
        })
    }

    function loadAppsSound() {
        if (appsSoundLoading || dragging) return
        appsSoundLoading = true
        ask("apps-sound", out => {
            sheet.appsSoundLoading = false
            if (!sheet.dragging) sheet.appsSound = sheet.json(out, sheet.appsSound)
        })
    }

    function loadNotificationAudio() {
        sheet.notificationAudio = {}
        sheet.notificationAudioProblem = ""
        ask("notification-audio", out => {
            const result = sheet.json(out, {})
            sheet.notificationAudio = result.ok === true ? result : {ok: false}
        })
    }

    function setNotificationAudio(level) {
        sheet.notificationAudioSaving = true
        ask("notification-audio " + level, out => {
            const result = sheet.json(out, {})
            sheet.notificationAudioSaving = false
            if (result.ok) sheet.notificationAudio = result
            sheet.notificationAudioProblem = result.ok ? "" : i18n("Couldn't change the notification volume.")
        })
    }

    function loadBackup() {
        if (backupLoading) return
        backupLoading = true
        ask("backup", out => {
            sheet.backupLoading = false
            sheet.backup = sheet.json(out, sheet.backup)
        })
    }

    function loadPhotoState() {
        if (photoLoading) return
        photoLoading = true
        ask("paint-state", out => {
            sheet.photoLoading = false
            const was = sheet.photoInfo.state
            sheet.photoInfo = sheet.json(out, sheet.photoInfo)
            if (was === "painting" && sheet.photoInfo.state === "ready")
                sheet.ask("prefs", more => sheet.prefs = sheet.json(more, sheet.prefs))
        })
    }

    function flip(key, command) {
        const on = info[key] !== true
        const next = Object.assign({}, info)
        next[key] = on
        info = next
        tell(command + (on ? " on" : " off"))
        if (key === "wifi" && on) {
            rescan.restart()
        }
    }

    // The last 30 seconds: GPU Screen Recorder comes from Flathub the first time (a minute or two).
    property bool replaying: false
    property bool replayFailed: false
    // Windows' Games folder going into Steam here (Steam closes for a moment).
    property bool sharing: false
    // Keep the result visible. A short-lived Done looked like the action never happened.
    property bool restoring: false
    property bool restored: false
    property bool restoreFailed: false
    function restoreLook() {
        if (restoring) return
        restoring = true
        restored = false
        restoreFailed = false
        sheet.ask("look-reset", (out, code) => {
            sheet.restoring = false
            sheet.restored = code === 0 && sheet.json(out, {}).done === true
            sheet.restoreFailed = !sheet.restored
            sheet.refresh()
        })
    }
    property bool gettingHeroic: false
    // Battle.net's or Ubisoft Connect's key while Lutris starts to get it ("" otherwise).
    property string gettingLauncher: ""
    function replay(on) {
        gameInfo = changed(gameInfo, ["replay"], on)
        replaying = on
        replayFailed = false
        ask("replay " + (on ? "on" : "off"), out => {
            sheet.replaying = false
            sheet.gameInfo = sheet.json(out, sheet.gameInfo)
            sheet.replayFailed = on && sheet.gameInfo.replay !== true
        })
    }

    function screenFeature(name, what, on) {
        screenInfo = screenInfo.map(s => s.name === name ? Object.assign({}, s, { [what]: on }) : s)
        ask("screen-" + what + " " + name + (on ? " on" : " off"), out => sheet.screenInfo = sheet.json(out, sheet.screenInfo))
    }

    function pref(key) {
        const on = prefs[key] === false
        const next = Object.assign({}, prefs)
        next[key] = on
        prefs = next
        tell("pref " + key + (on ? " on" : " off"))
    }

    // Settings' Glass slider: monet-light dresses the desktop in it, once the slider is let go.
    function chooseGlass(level) {
        if (prefs.glass === level) {
            return
        }
        prefs = changed(prefs, ["glass"], level)
        tell("glass " + level)
    }

    function chooseSeries(name) {
        if (name === "photo" && photoInfo.state !== "ready") {
            photoPicker.open()
            return
        }
        prefs = changed(prefs, ["series"], name)
        ask("series " + name)
    }

    // A photo of yours, painted in Monet's hand in the four lights: it takes a minute or so,
    // then the wall changes to it by itself (monet-quick paint-run).
    function paintPhoto(url) {
        const path = decodeURIComponent(url.toString().replace(/^file:\/\//, ""))
        photoInfo = { state: "painting", percent: 0 }
        ask("paint-photo " + hex(path), out => sheet.photoInfo = sheet.json(out, { state: "", failed: true }))
    }

    function chooseLight(mode) {
        const next = Object.assign({}, info)
        next.light = mode
        info = next
        tell("light " + mode)
    }

    // Sliders send their latest value at most every 120 ms.
    property var pending: ({})
    function queue(what, value) {
        pending[what] = Math.round(value)
        flush.start()
    }

    // Text from people (network names, passwords) goes to the helper as the
    // hex of its UTF-8 bytes, so the shell never sees it.
    function hex(text) {
        const bytes = unescape(encodeURIComponent(text))
        let out = ""
        for (let i = 0; i < bytes.length; i++) {
            out += bytes.charCodeAt(i).toString(16).padStart(2, "0")
        }
        return out
    }

    function join(name, key) {
        joinState = "joining"
        ask("wifi-join " + hex(name) + (key ? " " + hex(key) : ""), out => {
            const result = sheet.json(out, { ok: false })
            if (result.ok) {
                sheet.joining = ""
                sheet.joinState = ""
            } else {
                sheet.joinState = "failed"
            }
            sheet.load()
        })
    }

    function connectDevice(device) {
        if (!/^[0-9A-Fa-f:]{17}$/.test(device.address)) {
            return
        }
        busyDevice = device.address
        ask((device.connected ? "bt-disconnect " : "bt-connect ") + device.address, () => {
            sheet.busyDevice = ""
            sheet.ask("bt-list", out => sheet.devices = sheet.json(out, sheet.devices))
        })
    }

    function loadMicrophones() {
        if (microphoneBusy) return
        ask("microphones", out => {
            if (sheet.microphoneBusy) return
            const found = sheet.json(out, sheet.microphones)
            sheet.microphones = Array.isArray(found) ? found : []
            // In use after all (chosen elsewhere, or it came back): nothing left to try again.
            if (sheet.microphones.some(m => m.default && sheet.sameDevice(m, sheet.microphoneWanted))) sheet.microphoneProblem = ""
        })
    }
    // A device's own name, as the helper gave it in hex: the helper finds the device by it however
    // PipeWire numbers it by then (plugged in, unplugged, a new profile). Older answers have none.
    function deviceKey(device) {
        return /^(?:[0-9a-f]{2})+$/.test(device.key || "") ? " " + device.key : ""
    }
    function sameDevice(a, b) {
        return !!a && !!b && (a.key && b.key ? a.key === b.key : a.id === b.id)
    }
    // Said done only once the helper has seen the change; else why not, beside Try again.
    function pickMicrophone(input) {
        if (!input || !Number.isInteger(input.id) || microphoneBusy || input.default === true) return
        microphoneBusy = true
        microphoneProblem = ""
        microphoneWanted = input
        ask("input " + input.id + deviceKey(input), (out, code) => {
            const result = sheet.json(out, {})
            if (result.sound && Array.isArray(result.sound.inputs)) sheet.microphones = result.sound.inputs
            sheet.microphoneBusy = false
            sheet.microphoneProblem = code === 0 && result.ok === true ? ""
                : result.problem === "gone" ? i18n("%1 isn't connected now. Connect it and try again.", input.name)
                : i18n("The microphone didn't switch to %1. Try again.", input.name)
            sheet.refresh()  // the volume slider is the chosen microphone's
        })
    }

    function pickOutput(output) {
        if (!output || !Number.isInteger(output.id) || outputBusy) {
            return
        }
        outputBusy = true
        outputProblem = ""
        outputWanted = output
        ask("output " + output.id + deviceKey(output), (out, code) => {
            const result = sheet.json(out, {})
            if (Array.isArray(result.outputs)) sheet.outputs = result.outputs
            sheet.outputBusy = false
            sheet.outputProblem = code === 0 && result.ok === true ? ""
                : result.problem === "gone" ? i18n("%1 isn't connected now. Connect it and try again.", output.name)
                : i18nc("%1 is speakers, headphones or a screen", "Sound didn't switch to %1. Try again.", output.name)
            sheet.refresh()  // the volume slider is the chosen output's
        })
    }

    // Game ids only contain letters, digits, ":", ".", "_" and "-"; tasks are fixed words.
    function restart() {
        const game = asking && asking.id && /^[A-Za-z0-9:._-]+$/.test(asking.id) ? asking : null
        const task = asking && (asking.task === "launchers" || asking.task === "update") ? asking.task : ""
        switchProblem = ""
        asking = null
        switching = true
        call(game ? ["monet", "play", game.id] : task ? ["monet", "windows", "--" + task] : ["monet", "windows"], (out, code, err) => {
            sheet.switching = false
            if (code !== 0) {
                sheet.switchProblem = err.trim() || i18n("Monet couldn't switch to Windows.")
            }
        })
    }

    function checkMonet() {
        checkingDoctor = true
        ask("doctor", out => {
            sheet.checkingDoctor = false
            sheet.doctorReport = (sheet.json(out, { message: "" }).message || "").trim()
        })
    }

    // `monet doctor`'s lines, with ✓ in lily, ! in amber and ✗ in red.
    function report(text) {
        const marks = { "✓": look.lily, "!": "#D9892E", "✗": "#E0603A" }
        return text.split("\n").map(l => l.trim()).filter(l => marks[l[0]] !== undefined).map(l => {
            const words = l.slice(1).trim().replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
            return "<font color=\"" + marks[l[0]] + "\">" + l[0] + "</font>&nbsp;&nbsp;" + words
        }).join("<br>")
    }

    // When asked: first look, then install. By itself (once a day, unless that's off) the helper does both.
    function loadUpdateHistory() {
        if (updateHistoryBusy) return
        updateHistoryBusy = true
        const revision = updateInstallRevision
        ask("update-history", (out, code) => {
            const found = sheet.json(out, {}) || {}
            sheet.updateHistoryBusy = false
            // A local status read can finish after an install has reported a newer state.
            if (revision === sheet.updateInstallRevision && code === 0 && typeof found.staged === "boolean") {
                sheet.updateStaged = found.staged
            }
            sheet.updateHistory = code === 0 && typeof found.ok === "boolean" && Array.isArray(found.items)
                && found.items.length <= 10 && found.items.every(item => item
                    && ["done", "failed", "skipped"].includes(item.result)
                    && typeof item.time === "number" && Number.isFinite(item.time) && item.time > 0
                    && item.time <= 8640000000000000)
                && ["unknown", "idle", "running", "retry"].includes(found.state)
                ? found : { ok: false, items: [], state: "unknown" }
            if (revision !== sheet.updateInstallRevision) sheet.loadUpdateHistory()
        })
    }

    function updateHistoryDetail() {
        if (updateHistoryBusy && updateHistory.items.length === 0) return i18n("Loading…")
        if (updateHistory.state === "running") return i18n("An automatic update is in progress.")
        if (updateHistory.state === "retry") return i18n("Waiting to retry an automatic update.")
        if (!updateHistory.ok) return i18n("Recent update results couldn't load. Try refreshing.")
        const latest = updateHistory.items[0]
        if (!latest) return i18n("No recent automatic update results are available.")
        if (latest.result === "failed") return i18n("The last automatic update didn't finish. Check your connection, then choose Check for updates.")
        if (latest.result === "skipped") return i18n("The last automatic update was skipped because its conditions weren't met.")
        return i18n("Recent attempts saved by this PC. Older results may no longer be available.")
    }

    function checkUpdates() {
        updateState = "checking"
        const betas = showBetas
        ask("update-check" + (betas ? " beta" : ""), (out, code) => {
            const found = sheet.json(out, {}) || {}
            const valid = code === 0 && found.ok === true && typeof found.system === "boolean"
                && (found.apps === undefined || Number.isInteger(found.apps) && found.apps >= 0)
            sheet.updateFound = valid ? found : {}
            sheet.updateMessage = typeof found.message === "string" ? found.message : ""
            sheet.updateState = !valid ? "failed" : found.system || found.apps > 0 ? "available" : "none"
            if (betas && sheet.showBetas && valid) {
                sheet.betaFound = found.beta || null
                sheet.betaMessage = found.betaMessage || ""
                sheet.betaChecked = true
            }
            sheet.loadUpdateHistory()
        })
        checkFirmware()
    }

    // Show beta versions: turned on, it looks for one at once.
    function flipBetas() {
        showBetas = !showBetas
        if (!showBetas) {
            betaFound = null
            betaChecked = false
            betaMessage = ""
            if (betaState !== "installing") betaState = ""
        } else if (updateState !== "checking" && updateState !== "installing" && betaState !== "installing") {
            checkUpdates()
        }
    }

    // Install beta: the one shown, and only from its own button.
    function installBeta() {
        const beta = betaFound
        if (!beta || !/^\d{1,6}\.\d{1,6}\.\d{1,6}(-\d{1,6})?-beta\.[1-9]\d{0,5}$/.test(beta.tag || "")) return
        betaState = "installing"
        ask("install-beta " + beta.tag, (out, code) => {
            const result = sheet.json(out, {}) || {}
            const success = code === 0 && result.ok === true
            const lines = typeof result.message === "string" ? result.message.trim().split("\n") : []
            sheet.betaMessage = success ? "" : lines.length > 0 ? lines[lines.length - 1] : ""
            sheet.updateInstallRevision++
            if (code === 0 && typeof result.staged === "boolean") sheet.updateStaged = result.staged
            sheet.betaStaged = code === 0 && result.staged === true
            sheet.betaState = success ? "done" : "failed"
            sheet.loadUpdateHistory()
        })
    }

    function loadProfileHistory() {
        if (profileLoading || profileRestoring) return
        profileLoading = true
        profileReview = null
        ask("profile-recovery", (out, code) => {
            const result = sheet.json(out, {})
            sheet.profileLoading = false
            sheet.profileState = code === 0 && result.ok === true && Array.isArray(result.items) ? "ready"
                : result.state === "busy" ? "busy" : "unavailable"
            sheet.profileHistory = sheet.profileState === "ready" ? result.items : []
        })
    }
    function profileAreas(item) {
        const names = {appearance: i18n("Appearance"), windows: i18n("Windows and workspace"),
            input: i18n("Keyboard and pointer"), lock: i18n("Screen locking"), desktop: i18n("Desktop layout"),
            shortcuts: i18n("Application shortcuts"), preferences: i18n("Other desktop preferences")}
        return (item.areas || []).map(area => names[area] || names.preferences).join(" · ")
    }
    function profileStatus(item) {
        return item.status === "rolled-back" ? i18n("Undone")
            : item.status === "conflicts" ? i18n("Some newer choices were kept")
            : item.status === "interrupted" ? i18n("Interrupted")
            : item.status === "failed" ? i18n("Didn't finish") : i18n("Completed")
    }
    function reviewProfile(item) {
        if (profileLoading || profileRestoring || !item || !(item.remaining > 0)) return
        profileReview = item
        profileMessage = ""
    }
    function undoProfile() {
        if (profileLoading || profileRestoring || !profileReview) return
        const item = profileReview
        profileRestoring = true
        ask("profile-recovery " + item.id + " " + item.fingerprint, (out, code) => {
            const result = sheet.json(out, {})
            sheet.profileRestoring = false
            sheet.profileReview = null
            sheet.profileMessage = code === 0 && result.ok === true && result.state === "done"
                ? i18n("Desktop changes undone. Sign out and back in when you are ready to apply them everywhere.")
                : code === 0 && result.state === "conflicts"
                    ? i18n("Newer choices and changes that could not be restored were kept. Review what remains.")
                : result.state === "busy" ? i18n("Desktop settings are being updated. Wait for that to finish, then refresh.")
                : result.state === "changed" ? i18n("The saved changes have changed. Refresh and review them again before undoing.")
                : i18n("Recovery could not finish. Some changes may already have been undone; refresh to check what remains.")
            sheet.loadProfileHistory()
        })
    }

    function goBack() {
        previous = changed(previous, ["pending"], true)
        ask("rollback", () => ask("previous", out => sheet.previous = sheet.json(out, {})))
    }
    function previousName() {
        return previous.version ? i18n("Monet %1", previous.version) : i18n("the Monet from before")
    }

    function flipAutoUpdates() {
        const on = pc.autoUpdates === false
        pc = changed(pc, ["autoUpdates"], on)
        ask("auto-updates " + (on ? "on" : "off"), () => ask("about", out => sheet.pc = sheet.json(out, sheet.pc)))
    }

    function checkFirmware() {
        if (firmwareState === "installing" || (firmwareState === "done" && firmwareRestart)) return
        firmwareState = "checking"
        ask("firmware-check", out => {
            const found = sheet.json(out, { ok: false })
            sheet.firmware = found.updates || []
            sheet.firmwareMessage = found.message || ""
            sheet.firmwareState = found.unavailable === true ? "unavailable"
                : !found.ok ? "failed" : sheet.firmware.length > 0 ? "available" : "none"
        })
    }

    function loadSecurity(afterChange) {
        if (securityChecking && afterChange !== true) return
        const checkId = ++securityCheckId
        securityChecking = true
        ask("security", (out, code) => {
            if (checkId !== sheet.securityCheckId) return
            const found = code === 0 ? sheet.json(out, null) : null
            sheet.safety = found && typeof found.secureBoot === "string" ? found : ({})
            if (sheet.securityConfirmation === "firmware" && sheet.safety.firmwareRestartAvailable !== true)
                sheet.securityConfirmation = ""
            sheet.securityChecked = true
            sheet.securityChecking = false
            if (afterChange === true) sheet.securityFixing = ""
        })
    }

    function fixSecurity(command) {
        if (securityFixing !== "") return
        securityFixing = command
        securityProblem = ""
        ask(command, (out, code) => {
            const result = sheet.json(out, { ok: false })
            if (code !== 0 || !result || result.ok !== true) {
                sheet.securityProblem = command === "restart" ? i18n("Couldn’t open the restart confirmation. Try again.")
                    : i18n("The change didn’t go through. Check the setting below and try again.")
            } else if (command === "trust-key") {
                sheet.keyAsked = true
            }
            if (command === "restart") sheet.securityFixing = ""
            else sheet.loadSecurity(true)
        })
    }

    function securityOverview() {
        const s = safety
        if (securityChecking || !securityChecked)
            return { title: i18n("Checking this PC…") }
        if (s.firewall === "off")
            return { title: i18n("The firewall is off."), detail: i18n("Turn it on to limit connections from other devices."), action: i18n("Turn on"), command: "firewall-on" }
        if (s.encryptionSetup === "pending")
            return { title: i18n("Finishing disk encryption."), detail: i18n("Keep your recovery key somewhere safe. Check again after restarting."), anchor: "security-device" }
        if (s.secureBoot === "off" || s.encrypted === false || ["permissive", "disabled"].includes(s.selinux))
            return { title: i18n("Device security needs a look."), detail: i18n("Check how this PC starts and protects its files."), anchor: "security-device" }
        if (s.network && s.network.sharingAsDefault)
            return { title: i18n("The sharing zone is the default."), detail: i18n("Shared ports may be open on other connections."), anchor: "security-network" }
        if (s.network && s.network.legacy)
            return { title: i18n("Review older firewall rules."), detail: i18n("Some ports are open across firewall zones."), anchor: "security-network" }
        if (s.updateWaiting === true)
            return { title: i18n("An update is ready."), detail: i18n("Restart to finish installing it."), action: i18n("Restart"), command: "restart" }
        if (s.autoUpdates === "off" || s.lastUpdateFailed === true || firmwareState === "available" || (firmwareState === "done" && firmwareRestart))
            return { title: i18n("Updates need a look."), anchor: "security-updates" }
        if (s.secureBoot !== "on" || s.encrypted !== true || s.encryptionSetup !== "complete"
                || s.firewall !== "on" || !s.network || s.network.complete !== true
                || s.selinux !== "enforcing" || s.autoUpdates !== "on" || s.updateWaiting !== false
                || ["failed", "unavailable"].includes(firmwareState))
            return { title: i18n("Some checks couldn’t be completed."), detail: i18n("See the details below for what Monet could verify."), action: i18n("Check again"), command: "check" }
        if (firmwareState === "" || firmwareState === "checking") return { title: i18n("Checking for firmware updates…") }
        if (firmwareState === "installing") return { title: firmwareTitle(), detail: firmwareDetail() }
        return { title: i18n("The main checks look good."), detail: i18n("See what Monet checked below.") }
    }

    function securityEvent(event) {
        switch (event) {
        case "firewall-on": return i18n("Firewall turned on")
        case "firewall-strict": return i18n("Default firewall rules changed")
        case "firewall-network": return i18n("Network sharing changed")
        case "firewall-sharing":
        case "firewall-sharing-port": return i18n("Shared ports changed")
        case "firewall-clear-legacy": return i18n("Older firewall rules removed")
        case "update-failed": return i18n("Automatic update failed")
        default: return ""
        }
    }

    function installFirmware() {
        firmwareState = "installing"
        ask("firmware-update", out => {
            const result = sheet.json(out, { ok: false, message: "" })
            sheet.firmwareMessage = result.message || ""
            sheet.firmwareState = result.ok ? "done" : "failed"
        })
    }

    function firmwareTitle() {
        switch (firmwareState) {
        case "installing": return i18n("Updating firmware…")
        case "done": return firmwareRestart ? i18n("Restart to finish the firmware") : i18n("Firmware is up to date")
        case "failed": return i18n("The firmware didn't update")
        default: return i18np("%1 firmware update", "%1 firmware updates", firmware.length)
        }
    }

    function firmwareDetail() {
        switch (firmwareState) {
        case "installing": return i18n("Keep the PC plugged in and switched on.")
        case "done": return firmwareRestart ? i18n("It installs while the PC restarts. Keep it plugged in until it's back.") : i18n("Everything is installed.")
        case "failed": return firmwareMessage || i18n("Try again in a moment.")
        default: return i18n("For this PC's own parts, from their makers. Install when you're ready.")
        }
    }

    // "1.20 \u2192 1.32 · installs when the PC restarts", or what's in the way.
    function firmwareLine(update) {
        if (update.blocked) {
            return update.blocked
        }
        const versions = update.current ? update.current + " \u2192 " + update.version : update.version
        return update.restart ? i18n("%1 · installs when the PC restarts", versions) : versions
    }

    function installUpdates() {
        updateState = "installing"
        ask("update", (out, code) => {
            const result = sheet.json(out, {}) || {}
            const lines = typeof result.message === "string" ? result.message.trim().split("\n") : []
            sheet.updateMessage = lines.length > 0 ? lines[lines.length - 1] : ""
            sheet.updateInstallRevision++
            if (code === 0 && typeof result.staged === "boolean") sheet.updateStaged = result.staged
            sheet.updateState = code === 0 && result.ok === true ? "done" : "failed"
            sheet.loadUpdateHistory()
        })
    }

    function updateTitle() {
        const found = updateFound
        if (updateState === "available" && found.system) {
            // The same Monet built again on a fixed base: fixes, not a new version. Older images
            // carry their base's version ("44.20261012.1"), which isn't Monet's to show. On a
            // beta, the same version is its release.
            if (found.version && found.version === pc.monet && !(pc.beta > 0)) {
                return i18n("Fixes for Monet %1 are ready", found.version)
            }
            return /^\d{1,2}\.\d{1,2}(\.\d{1,2})?(-\d+)?$/.test(found.version || "") ? i18n("Monet %1 is ready", found.version)
                : i18n("A new Monet is ready")
        }
        if (updateState === "available") {
            return i18np("%1 app update is ready", "%1 app updates are ready", found.apps || 0)
        }
        if (updateRestartReady) return i18n("Restart to finish")
        if (updateState === "done") return i18n("Monet and your apps are up to date.")
        if (pc.monet && pc.beta > 0) return i18n("Monet %1", i18n("%1 beta %2", pc.monet, pc.beta))
        return pc.monet ? i18n("Monet %1", pc.monet) : i18n("Monet")
    }

    function updateDetail() {
        const found = updateFound
        if (updateRestartReady && updateState !== "failed") return i18n("The new Monet starts the next time you restart.")
        switch (updateState) {
        case "checking": return i18n("Looking for updates…")
        case "none": return updateStaged ? "" : i18n("Monet and your apps are up to date.")
        case "available":
            if (found.message) return found.message
            return found.system && found.apps > 0 ? i18np("And %1 app update. Install when you're ready.", "And %1 app updates. Install when you're ready.", found.apps || 0)
                : i18n("Install when you're ready.")
        case "installing": return i18n("Downloading and installing. You can keep using your PC.")
        case "done": return ""
        case "failed": return updateMessage || i18n("Monet couldn't finish the update. Try again.")
        default: return pc.autoUpdates === false ? i18n("Monet only updates when you ask it to.")
            : i18n("Automatic updates are on. You can also check now.")
        }
    }

    // Date & Time -----------------------------------------------------------

    function reloadClock() {
        ask("time", out => sheet.clock = sheet.json(out, sheet.clock))
    }

    function flipNtp() {
        const on = clock.ntp !== true
        clock = Object.assign({}, clock, { ntp: on })
        ask("ntp " + (on ? "on" : "off"), () => sheet.reloadClock())
    }

    // The saved locale followed by the clocks.
    function timeLocale() {
        return clock.locale ? Qt.locale(clock.locale) : Qt.locale()
    }

    // Whether a locale's clock runs to 24 hours, as Qt (and so every clock in Monet) shows it.
    function hours24(locale) {
        return !/a/i.test(locale.timeFormat(Locale.ShortFormat).replace(/'[^']*'/g, ""))
    }

    // The locale with the other clock: the region's own, or its language's other one ("" if none).
    function otherClock() {
        const region = clock.region || ""
        const want = !hours24(timeLocale())
        const twins = clocks[region.split("_")[0]]
        return region !== "" && hours24(Qt.locale(region)) === want ? region : twins ? twins[want ? 1 : 0] : ""
    }

    function flipClock() {
        const next = otherClock()
        if (next !== "") {
            ask("time-locale " + (next === clock.region ? "region" : next), () => sheet.reloadClock())
            clock = Object.assign({}, clock, { locale: next })
        }
    }

    // Zone names are letters, digits and "/_+-" (timedatectl's list).
    function chooseZone(zone) {
        if (!/^[A-Za-z0-9\/_+-]+$/.test(zone)) {
            return
        }
        clock = Object.assign({}, clock, { zone: zone })
        ask("zone " + zone, () => {
            Date.timeZoneUpdated()
            sheet.reloadClock()
        })
    }

    // Time zones where each word typed starts a word of the name ("new y": New York), up to six.
    function findZones(text) {
        const words = text.toLowerCase().split(/\s+/).filter(w => w !== "")
        return zones.filter(z => {
            const parts = z.toLowerCase().split(/[\/_]/)
            return words.every(w => parts.some(p => p.startsWith(w)))
        }).slice(0, 6)
    }

    // "America/Argentina/Buenos_Aires" is Buenos Aires, in America · Argentina.
    function zoneCity(zone) {
        return zone.split("/").pop().replace(/_/g, " ")
    }

    function zoneRegion(zone) {
        return zone.split("/").slice(0, -1).join(" · ").replace(/_/g, " ")
    }

    // Accounts --------------------------------------------------------------

    function rename(name) {
        name = name.trim()
        nameProblem = name === "" ? i18n("Type your name.") : /[:,]/.test(name) ? i18n("A name can't have : or , in it.") : ""
        if (nameProblem !== "") {
            return
        }
        ask("name " + hex(name), out => {
            const done = sheet.json(out, { ok: false }).ok
            sheet.renaming = !done
            sheet.nameProblem = done ? "" : i18n("Monet couldn't change your name.")
            sheet.ask("accounts", found => sheet.people = sheet.json(found, sheet.people))
        })
    }

    // A password goes to the helper sealed with a one-time pad the helper hands back first (as
    // hex), because anyone on the PC can read a command line.
    function seal(text, pad) {
        const bytes = unescape(encodeURIComponent(text))
        let out = ""
        for (let i = 0; i < bytes.length && i * 2 < pad.length; i++) {
            out += (bytes.charCodeAt(i) ^ parseInt(pad.substr(i * 2, 2), 16)).toString(16).padStart(2, "0")
        }
        return out.length === bytes.length * 2 ? out : ""
    }

    // Windows' BitLocker drive, opened with its recovery key (sealed with the pad on its way).
    function unlockWindows(key) {
        if (unlocking || key.trim() === "") {
            return
        }
        unlocking = true
        unlockProblem = ""
        ask("pad", pad => {
            const sealed = sheet.seal(key.trim(), pad.trim())
            if (sealed === "") {
                sheet.unlocking = false
                sheet.unlockProblem = i18n("A recovery key is 48 digits, in eight groups of six.")
                return
            }
            sheet.ask("bitlocker " + sealed, out => {
                const done = sheet.json(out, { result: "failed" })
                sheet.unlocking = false
                sheet.unlockProblem = done.result === "open" ? ""
                    : done.result === "bad-key" ? i18n("A recovery key is 48 digits, in eight groups of six.")
                    : done.result === "wrong-key" ? i18n("That key doesn't open Windows' drive. Check the digits and try again.")
                    : i18n("Windows' drive couldn't be opened. Try again.")
                sheet.ask("gaming", info => sheet.gameInfo = sheet.json(info, sheet.gameInfo))
            })
        })
    }

    function changePassword(old, fresh, again) {
        passwordMessage = fresh === "" ? i18n("Type a new password.") : fresh !== again ? i18n("The new passwords don't match.") : ""
        passwordState = passwordMessage !== "" ? "failed" : "changing"
        if (passwordState === "failed") {
            return
        }
        ask("pad", pad => {
            pad = pad.trim()
            // 128 bytes of pad for each.
            const sealed = [old === "" ? "-" : sheet.seal(old, pad.slice(0, 256)), sheet.seal(fresh, pad.slice(256))]
            const problem = pad.length !== 512 ? i18n("Monet couldn't change your password.")
                : sealed.includes("") ? i18n("That password is too long.") : ""
            if (problem !== "") {
                sheet.passwordMessage = problem
                sheet.passwordState = "failed"
                return
            }
            sheet.ask("password " + sealed.join(" "), out => {
                const result = sheet.json(out, { ok: false })
                sheet.passwordMessage = result.ok ? "" : result.message || i18n("Monet couldn't change your password.")
                sheet.passwordState = result.ok ? "done" : "failed"
            })
        })
    }

    function glaze(name) {
        const glazes = [["#E2603A", "#5B2350"], ["#3F9A89", "#1C3556"], ["#9C7BC0", "#2B2547"],
                        ["#5C88D0", "#1B2546"], ["#F0A048", "#7A3326"], ["#D46A8C", "#2E2A55"]]
        let h = 0
        for (let i = 0; i < name.length; i++) {
            h = (Math.imul(h, 31) + name.charCodeAt(i)) >>> 0
        }
        return glazes[h % glazes.length]
    }

    // Power & Sleep, Mouse & Keyboard, Notifications, Default Apps -----------
    // Each change shows at once, then the helper does it and the page reloads.

    function changed(object, path, value) {
        const next = JSON.parse(JSON.stringify(object))
        let at = next
        for (let i = 0; i < path.length - 1; i++) {
            at = at[path[i]] = at[path[i]] || {}
        }
        at[path[path.length - 1]] = value
        return next
    }

    function loadKeepAwake() {
        if (keepAwakeBusy || keepAwakeReading || page !== "power" || !pollingActive) return
        keepAwakeReading = true
        const revision = keepAwakeRevision
        ask("keep-awake-status", (out, code) => {
            sheet.keepAwakeReading = false
            if (revision !== sheet.keepAwakeRevision) return
            const state = sheet.json(out, {})
            if (code === 0 && typeof state.active === "boolean") {
                sheet.keepAwakeInfo = state
                sheet.keepAwakeTick++
            }
        })
    }
    function changeKeepAwake(seconds) {
        if (keepAwakeBusy || ![-1, 0, 1800, 3600].includes(seconds)) return
        keepAwakeBusy = true
        keepAwakeProblem = ""
        keepAwakeRevision++
        const mode = seconds === -1 ? "on" : seconds === 0 ? "off" : seconds === 1800 ? "30" : "60"
        ask("keep-awake " + mode, (out, code) => {
            sheet.keepAwakeBusy = false
            const result = sheet.json(out, {})
            if (result.state && typeof result.state.active === "boolean") sheet.keepAwakeInfo = result.state
            sheet.keepAwakeTick++
            sheet.keepAwakeProblem = (code === 0 && result.ok === true)
                || (result.state && typeof result.state.active === "boolean" && result.state.error) ? ""
                : i18n("Keep awake couldn't be changed. Try again.")
        })
    }
    function keepAwakeDescription() {
        if (keepAwakeBusy) return i18n("Changing…")
        if (keepAwakeProblem) return keepAwakeProblem
        if (keepAwakeInfo.error === "interrupted") return i18n("Keep awake stopped unexpectedly. Choose a duration to start it again.")
        if (keepAwakeInfo.error) return i18n("Keep awake is unavailable. Choose a duration to try again.")
        if (!keepAwakeInfo.active) return i18n("Uses your screen, lock and sleep settings")
        if (keepAwakeInfo.indefinite) return i18n("Until turned off or you sign out")
        if (keepAwakeLeft === 0) return i18n("Finishing…")
        const minutes = Math.floor(keepAwakeLeft / 60)
        const seconds = String(keepAwakeLeft % 60).padStart(2, "0")
        return i18nc("%1 is a countdown such as 29:59", "%1 remaining", minutes + ":" + seconds)
    }

    function batteryDescription() {
        if (info.charging) return info.minutes
            ? i18nc("%1 is a time like 1:20", "Charging, full in %1", hm(info.minutes)) : i18n("Charging")
        if (!info.plugged) return info.minutes
            ? i18nc("%1 is a time like 2:15", "About %1 left", hm(info.minutes)) : i18n("On battery")
        if (batteryCare.supported === true && batteryCare.limit < 100 && info.battery >= batteryCare.limit)
            return i18n("Plugged in · charging paused · %1% limit", batteryCare.limit)
        if (info.battery >= 100) return i18n("Plugged in · fully charged")
        return i18n("Plugged in · not charging")
    }

    function powerTime(state, what, seconds) {
        powerInfo = changed(powerInfo, [state, what], seconds)
        ask("power-time " + state + " " + what + " " + seconds, () => sheet.reloadPower())
    }
    function powerAction(key, action) {
        powerInfo = changed(powerInfo, [key === "button" ? "button" : "lidAction"], action)
        ask((key === "button" ? "power-button " : "power-lid ") + action, () => sheet.reloadPower())
    }
    function powerLock(what, value) {
        powerInfo = changed(powerInfo, [what], value)
        ask(what === "lockAfter" ? "lock-after " + value
            : "lock-resume " + (value ? "on" : "off"), () => sheet.reloadPower())
    }
    function powerMode(mode) {
        changePower("power-mode " + mode)
    }
    function changePower(command) {
        if (powerBusy) return
        powerBusy = true; powerProblem = ""
        ask(command, out => {
            const result = sheet.json(out, {})
            if (result.state && typeof result.state.mode === "string") sheet.powerInfo = result.state
            sheet.powerBusy = false
            if (result.ok !== true) sheet.powerProblem = result.problem === "critical-level"
                ? i18n("Choose a battery saver level above the critical battery level.")
                : i18n("The power setting couldn't be changed. Try again.")
            sheet.reloadPower()
        })
    }
    function reloadPower() {
        ask("power", out => sheet.powerInfo = sheet.json(out, sheet.powerInfo))
    }

    function pointer(kind, name, on) {
        inputInfo = changed(inputInfo, [kind, name], on)
        ask("pointer " + kind + " " + name + (on ? " on" : " off"))
    }
    function setLayouts(codes) {
        if (codes.length === 0) {
            return
        }
        const names = {}
        knownLayouts.forEach(l => names[l.code] = l.name)
        inputInfo = changed(inputInfo, ["layouts"], codes.map(c => ({ code: c, name: names[c] || c })))
        ask("layouts " + codes.join(","), () => ask("input", out => sheet.inputInfo = sheet.json(out, sheet.inputInfo)))
    }
    function findLayouts(text) {
        const word = text.trim().toLowerCase()
        const used = (inputInfo.layouts || []).map(l => l.code)
        return word === "" ? [] : knownLayouts.filter(l => used.indexOf(l.code) === -1
            && (l.name.toLowerCase().indexOf(word) !== -1 || l.code === word)).slice(0, 6)
    }

    function loadNotifications() {
        if (notifyBusy !== "") return
        const revision = ++notifyRevision
        ask("notify", out => {
            if (revision !== sheet.notifyRevision || sheet.notifyBusy !== "") return
            const state = sheet.json(out, null)
            if (state && Array.isArray(state.apps) && typeof state.quiet === "boolean") sheet.notifyInfo = state
        })
    }
    function changeNotification(command) {
        if (notifyBusy !== "") return
        ++notifyRevision
        notifyBusy = command
        notifyRetry = command
        notifyFailed = false
        notifyMessage = ""
        ask(command, (out, code) => {
            const result = sheet.json(out, {})
            const valid = result.state && Array.isArray(result.state.apps) && typeof result.state.quiet === "boolean"
            if (valid) sheet.notifyInfo = result.state
            sheet.notifyBusy = ""
            sheet.notifyFailed = code !== 0 || result.ok !== true || !valid
            sheet.notifyMessage = sheet.notifyFailed
                ? i18n("That change could not be saved. Try again.") : i18n("Saved")
            sheet.refresh()
        })
    }
    function quietDescription() {
        if (!notifyInfo.quiet) return i18n("Notifications pop up as they come")
        if (notifyInfo.quietIndefinite) return i18n("Quiet until you turn it off")
        return i18n("Quiet until %1", Qt.formatDateTime(new Date(notifyInfo.quietUntil * 1000), Qt.locale().dateTimeFormat(Locale.ShortFormat)))
    }
    function notifyRule(name, on) {
        changeNotification("notify-rule " + name + (on ? " on" : " off"))
    }
    function notifyPopups(what, value) {
        changeNotification((what === "place" ? "notify-place " : "notify-time ") + value)
    }
    function notifyApp(app, on) {
        changeNotification("notify-app " + hex(app.id) + (on ? " on" : " off"))
    }

    function setDefault(kind, app) {
        appDefaults = appDefaults.map(k => k.id === kind ? Object.assign({}, k, { current: app.id }) : k)
        ask("default " + kind + " " + hex(app.id), () => ask("defaults", out => sheet.appDefaults = sheet.json(out, sheet.appDefaults)))
    }

    function emptyTrash() {
        storageInfo = changed(storageInfo, ["trash"], 0)
        ask("empty-trash", () => loadStorage())
    }
    function loadStorage() {
        const request = ++storageRequest
        ask("storage-capacity", (out, code) => {
            if (request !== sheet.storageRequest) return
            sheet.storageLoaded = true
            if (code === 0) sheet.storageInfo = sheet.json(out, sheet.storageInfo)
        })
    }
    function measureStorage() {
        if (storageBusy) return
        const request = ++storageRequest
        storageBusy = true
        storageProblem = ""
        ask("storage", (out, code) => {
            sheet.storageBusy = false
            if (request !== sheet.storageRequest) return
            const result = sheet.json(out, {})
            if (code === 0 && result.measured === true) {
                sheet.storageInfo = result
                sheet.storageLoaded = true
            } else {
                sheet.storageProblem = i18n("Folder sizes couldn't be measured. Try again.")
                if (!sheet.storageLoaded) sheet.loadStorage()
            }
        })
    }
    function loadDisks() {
        if (disksLoading || diskBusy) return
        disksLoading = true
        ask("storage-disks", (out, code) => {
            const result = sheet.json(out, {})
            sheet.disksLoading = false
            sheet.disksLoaded = code === 0 && result.ok === true
            sheet.disks = sheet.disksLoaded && Array.isArray(result.disks) ? result.disks : []
            if (!sheet.disksLoaded && sheet.diskProblem === "")
                sheet.diskProblem = i18n("Couldn't read the drives. Try refreshing.")
        })
    }
    function changeDisk(action, disk, target, format, size, name) {
        if (diskBusy || disksLoading) return
        diskBusy = true
        diskProblem = ""
        ask("storage-disks " + [action, disk.token, target, format, size, name ? hex(name) : "-"].join(" "), (out, code) => {
            const result = sheet.json(out, {})
            sheet.diskBusy = false
            if (code !== 0 || result.ok !== true)
                sheet.diskProblem = result.message || i18n("The disk operation couldn't finish.")
            sheet.loadDisks()
        })
    }
    function rememberFiles(value) {
        privacyInfo = changed(privacyInfo, ["remember"], value)
        ask("remember " + (value ? "on" : "off"))
    }

    function walletAction(action, value) {
        if (walletBusy) return
        walletBusy = true
        walletProblem = ""
        ask("wallet-" + action + (value ? " " + value : ""), (out, code) => {
            walletBusy = false
            const result = sheet.json(out, {})
            if (result.state && typeof result.state.enabled === "boolean") walletInfo = result.state
            if (code !== 0 || (action === "status" ? typeof result.enabled !== "boolean" : result.ok !== true)) {
                walletProblem = i18n("Password settings couldn't finish. Try again.")
                return
            }
            if (action === "status") walletInfo = result
            if (action === "policy") walletChanged = true
        })
    }

    function printerDefault(name) {
        printerInfo = changed(printerInfo, ["printers"], (printerInfo.printers || []).map(
            p => Object.assign({}, p, { default: p.name === name })))
        ask("printer-default " + hex(name))
    }

    function overlay(on) {
        gameInfo = changed(gameInfo, ["overlay"], on)
        ask("overlay " + (on ? "on" : "off"))
    }

    // "3 games · 120 GB · 410 GB free": a game library in words.
    function library(found) {
        const parts = [i18np("%1 game", "%1 games", found.games || 0)]
        if (found.size > 0)
            parts.push(bytes(found.size))
        if (typeof found.free === "number")
            parts.push(i18n("%1 free", bytes(found.free)))
        return parts.join(" · ")
    }

    function loadPhones() {
        if (sheet.phoneChecking) return
        sheet.phoneChecking = true
        ask("phones", (out, code) => {
            const found = sheet.json(out, false)
            const valid = found === null || (Array.isArray(found) && found.every(p => p
                && typeof p.id === "string" && p.id !== "" && typeof p.name === "string"
                && typeof p.paired === "boolean" && typeof p.near === "boolean"
                && (p.battery === null || (Number.isInteger(p.battery) && p.battery >= 0 && p.battery <= 100))
                && (p.charging === null || typeof p.charging === "boolean")))
            sheet.phoneChecking = false
            sheet.phoneFailed = code !== 0 || !valid
            if (sheet.phoneFailed) {
                sheet.phoneList = []
                sheet.phoneAsked = ""
                return
            }
            sheet.phoneApp = found !== null
            sheet.phoneList = found || []
            if (sheet.phoneList.some(p => p.id === sheet.phoneAsked && p.paired))
                sheet.phoneAsked = ""
        })
    }

    function sendPhoneFile(ident) {
        if (sheet.phoneSending) return
        sheet.phoneSending = true
        sheet.phoneFileState = ""
        ask("phone-send " + ident, (out, code) => {
            const result = sheet.json(out, {})
            sheet.phoneSending = false
            sheet.phoneFileState = code === 0 && result && ["canceled", "dispatched"].includes(result.state) ? result.state : "failed"
        })
    }

    function access(what, value) {
        accessInfo = changed(accessInfo, [what], value)
        const said = what === "reduced" ? (value ? "reduced" : "normal") : (what === "reader" || what === "zoom") ? (value ? "on" : "off") : value
        ask("access-" + ({ scale: "scale", cursor: "cursor", reduced: "motion", reader: "reader", zoom: "zoom" })[what] + " " + said)
    }

    function changeScreenSize(name, value) {
        if (scaleBusy) return
        scaleBusy = true
        scaleProblem = ""
        ask("access-scale " + value + " " + hex(name), (out, code) => {
            scaleBusy = false
            const result = sheet.json(out, {})
            if (Array.isArray(result.displays)) displaySizes = result.displays
            if (code !== 0 || result.ok !== true)
                scaleProblem = result.error || i18n("The screen size couldn't be changed. Try again.")
        })
    }

    // A size on disk in words: 840 MB, 6.2 GB, 412 GB, 1.8 TB.
    function bytes(n) {
        n = n || 0
        return n >= 1e12 ? i18n("%1 TB", (n / 1e12).toFixed(1)) : n >= 1e10 ? i18n("%1 GB", Math.round(n / 1e9))
            : n >= 1e9 ? i18n("%1 GB", (n / 1e9).toFixed(1)) : n >= 1e6 ? i18n("%1 MB", Math.round(n / 1e6))
            : i18n("%1 KB", Math.round(n / 1e3))
    }

    // When it was, said plainly: "Today, 14:00", "Yesterday, 09:00", or the date and time.
    function moment(seconds) {
        const then = new Date(seconds * 1000)
        const time = then.toLocaleTimeString(timeLocale(), Locale.ShortFormat)
        const days = Math.round((new Date().setHours(0, 0, 0, 0) - new Date(then).setHours(0, 0, 0, 0)) / 86400000)
        return days === 0 ? i18n("Today, %1", time) : days === 1 ? i18n("Yesterday, %1", time)
            : i18n("%1, %2", then.toLocaleDateString(timeLocale(), Locale.ShortFormat), time)
    }

    // h:mm, from minutes: how long the battery lasts.
    function hm(minutes) {
        return Math.floor(minutes / 60) + ":" + String(minutes % 60).padStart(2, "0")
    }

    // How long, in words: 300 is "5 min", 3600 "1 hour", 0 "Never".
    function span(seconds) {
        return seconds === 0 ? i18n("Never") : seconds < 3600 ? i18n("%1 min", seconds / 60)
            : i18np("%1 hour", "%1 hours", seconds / 3600)
    }

    // The sheet -------------------------------------------------------------

    Item {
        id: frame
        anchors.fill: parent
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true
        // Mist or smoke, from the colors Monet's light chose.
        readonly property bool dark: Kirigami.Theme.backgroundColor.hslLightness < 0.5

        // A canvas under the glass, as faint as paper's grain (as in Games).
        Image {
            anchors.fill: parent
            anchors.margins: 14
            source: brush
            fillMode: Image.Tile
            opacity: frame.dark ? 0.05 : 0.07
        }

        Shortcut {
            sequences: ["Escape"]
            onActivated: {
                if (typeof pageLoader.item?.cancelConfirmation === "function" && pageLoader.item.cancelConfirmation()) return
                if (search.text !== "") { search.text = ""; search.forceActiveFocus() }
                else sheet.close()
            }
        }
        Shortcut {
            sequences: [StandardKey.Find]
            onActivated: search.forceActiveFocus()
        }

        // The glass column: the name, search and the pages.
        Item {
            id: side
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 250

            ColumnLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 12
                anchors.topMargin: 14
                anchors.bottomMargin: 6
                spacing: 4

                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.leftMargin: 10
                    Layout.bottomMargin: 12
                    text: i18n("Settings")
                    color: look.ink
                    font.family: "Fraunces 72pt SuperSoft"
                    font.weight: Font.Light
                    font.pixelSize: 34
                    font.letterSpacing: -0.6
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    Layout.bottomMargin: 10
                    radius: 12
                    color: look.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.4)
                    border.width: search.activeFocus ? 2 : 1
                    border.color: search.activeFocus ? look.lily : look.dark ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(1, 1, 1, 0.7)
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 8
                        spacing: 8
                        SettingsControls.Glyph {
                            Layout.preferredWidth: 15
                            Layout.preferredHeight: 15
                            path: "M10.5 5.5a5 5 0 1 0 0.01 0M14.2 14.2L19 19"
                            color: look.dim
                        }
                        TextInput {
                            id: search
                            objectName: "settingsSearch"
                            Layout.fillWidth: true
                            activeFocusOnTab: true
                            maximumLength: 256
                            color: look.ink
                            font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
                            clip: true
                            selectByMouse: true
                            selectionColor: look.lily
                            Accessible.role: Accessible.EditableText
                            Accessible.name: i18n("Search settings")
                            onTextChanged: {
                                // Typing a new query cancels a delayed jump from the
                                // previous result, so it cannot steal keyboard focus.
                                sheet.pendingAnchor = ""
                                sheet.searchRevision++
                                sheet.searchReady = ""
                                sheet.searchResults = []
                                sheet.searchProblem = ""
                                sheet.searchBusy = text.trim() !== ""
                                searchDelay.restart()
                            }
                            onAccepted: sheet.activateSearch()
                            Keys.onEscapePressed: event => { search.text = ""; event.accepted = true }
                            Keys.onDownPressed: {
                                const first = searchRepeater.itemAt(0)
                                if (first) first.forceActiveFocus(Qt.TabFocusReason)
                            }
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                anchors.fill: parent
                                verticalAlignment: Text.AlignVCenter
                                visible: search.text === "" && !search.activeFocus
                                text: i18n("Search")
                                color: look.dim
                                font: search.font
                            }
                        }
                    }
                }

                // The pages, scrolling when the screen is short. The current
                // page's pebble of glass glides from one to the next.
                Flickable {
                    id: navList
                    objectName: "settingsNavigation"
                    Shared.MouseScroll { view: navList }
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentHeight: navColumn.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    interactive: contentHeight > height
                    Shared.ScrollInput { id: navInput; view: navList }
                    Keys.priority: Keys.AfterItem
                    Keys.onPressed: event => navInput.key(event)
                    // On a laptop's screen not every page fits: a scrollbar says there are more,
                    // and the page that opens (from a notification, say) is scrolled into view.
                    T.ScrollBar.vertical: SettingsControls.Rail { id: navScroll; tone: look }

                    function reveal() {
                        const shown = pebble.target
                        if (shown && (shown.y < contentY || shown.y + shown.height > contentY + height)) {
                            contentY = Math.max(0, Math.min(shown.y - (height - shown.height) / 2, contentHeight - height))
                        }
                    }
                    onHeightChanged: Qt.callLater(reveal)

                    Connections {
                        target: sheet
                        function onPageChanged() { Qt.callLater(navList.reveal) }
                        function onActiveFocusItemChanged() {
                            const focused = sheet.activeFocusItem
                            let ancestor = focused
                            while (ancestor && ancestor !== navColumn) ancestor = ancestor.parent
                            if (!focused || !ancestor) return
                            const top = focused.mapToItem(navList.contentItem, 0, 0).y
                            if (top < navList.contentY) navList.contentY = top
                            else if (top + focused.height > navList.contentY + navList.height)
                                navList.contentY = top + focused.height - navList.height
                        }
                        function onVisibleChanged() {
                            if (sheet.visible) {
                                Qt.callLater(navList.reveal)
                            }
                        }
                    }

                    Rectangle {
                        id: pebble
                        readonly property Item target: navRepeater.count > 0
                            ? navRepeater.itemAt(sheet.pages.findIndex(p => p.id === sheet.page)) : null
                        width: navColumn.width
                        height: target ? target.height : 0
                        y: target ? target.y : 0
                        visible: target !== null && target.visible
                        radius: 12
                        color: look.dark ? Qt.rgba(1, 1, 1, 0.15) : Qt.rgba(1, 1, 1, 0.6)
                        border.width: 1
                        border.color: look.dark ? Qt.rgba(1, 1, 1, 0.2) : Qt.rgba(1, 1, 1, 0.85)
                        Behavior on y {
                            enabled: sheet.visible
                            NumberAnimation { duration: Math.round(320 * sheet.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] }
                        }
                    }

                    ColumnLayout {
                        id: navColumn
                        // Clear of the scrollbar, when there is one, so the pebble never runs under it.
                        width: navList.width - (navList.interactive ? navScroll.width + 4 : 0)
                        spacing: 2

                        Repeater {
                            id: searchRepeater
                            model: sheet.searchResults
                            Rectangle {
                                id: suggestion
                                required property var modelData
                                required property int index
                                objectName: "searchResult-" + modelData.id
                                Layout.fillWidth: true
                                implicitHeight: resultWords.implicitHeight + 20
                                radius: 12
                                color: suggestion.activeFocus || suggestionHover.hovered ? look.wash : "transparent"
                                border.width: activeFocus ? 2 : 0
                                border.color: look.lily
                                activeFocusOnTab: true
                                Accessible.role: Accessible.Button
                                Accessible.name: modelData.name
                                Accessible.description: modelData.detail
                                Accessible.onPressAction: sheet.openSearchResult(modelData)
                                Keys.onReturnPressed: sheet.openSearchResult(modelData)
                                Keys.onEnterPressed: sheet.openSearchResult(modelData)
                                Keys.onSpacePressed: sheet.openSearchResult(modelData)
                                Keys.onUpPressed: {
                                    if (index === 0) search.forceActiveFocus(Qt.BacktabFocusReason)
                                    else searchRepeater.itemAt(index - 1).forceActiveFocus(Qt.BacktabFocusReason)
                                }
                                Keys.onDownPressed: {
                                    const next = searchRepeater.itemAt(index + 1)
                                    if (next) next.forceActiveFocus(Qt.TabFocusReason)
                                }
                                Column {
                                    id: resultWords
                                    anchors.left: parent.left; anchors.right: parent.right
                                    anchors.margins: 10; anchors.verticalCenter: parent.verticalCenter
                                    spacing: 3
                                    Text {
                                        width: parent.width; text: suggestion.modelData.name
                                        color: look.ink; font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1); font.weight: Font.DemiBold
                                        wrapMode: Text.Wrap; textFormat: Text.PlainText
                                    }
                                    Text {
                                        width: parent.width; text: suggestion.modelData.detail
                                        color: look.dim; font.pixelSize: Math.max(13, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 3)
                                        wrapMode: Text.Wrap; textFormat: Text.PlainText
                                    }
                                }
                                HoverHandler { id: suggestionHover }
                                TapHandler { onTapped: sheet.openSearchResult(suggestion.modelData) }
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            Layout.margins: 8
                            visible: sheet.searchBusy || sheet.searchProblem !== ""
                            text: sheet.searchBusy ? i18n("Searching…") : sheet.searchProblem
                            color: look.dim; font.pixelSize: Math.max(14, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 2); wrapMode: Text.Wrap
                            Accessible.role: Accessible.StaticText
                        }
                        SettingsControls.Pill {
                            objectName: "settingsSearchRetry"
                            tone: look
                            visible: sheet.searchProblem !== ""
                            text: i18n("Try again")
                            onClicked: sheet.findSettings(false)
                        }
                        Repeater {
                            id: navRepeater
                            model: sheet.pages
                            Rectangle {
                                id: navItem
                                objectName: "settingsPage-" + modelData.id
                                readonly property bool current: sheet.page === modelData.id
                                Layout.fillWidth: true
                                Layout.preferredHeight: visible ? Math.max(38, Kirigami.Theme.defaultFont.pointSize * 4 / 3 + 18) : 0
                                // A little air between Monet's pages, KDE's, and Windows'.
                                Layout.topMargin: modelData.gap ? 10 : 0
                                visible: side.matches(modelData)
                                radius: 12
                                // Clear the old hover as soon as the pointer reaches another row.
                                color: navHover.hovered && !current ? (look.dark ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.3)) : "transparent"
                                border.width: activeFocus ? 2 : 0
                                border.color: look.lily
                                activeFocusOnTab: true
                                Keys.onSpacePressed: sheet.go(modelData)
                                Keys.onReturnPressed: sheet.go(modelData)
                                Keys.onEnterPressed: sheet.go(modelData)

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 10
                                    spacing: 12
                                    // A swatch cut from the paintings, with a white mark.
                                    Item {
                                        Layout.preferredWidth: 26
                                        Layout.preferredHeight: 26
                                        Image {
                                            anchors.fill: parent
                                            source: sheet.art + "swatch-" + (modelData.swatch || modelData.id) + ".png"
                                            sourceSize: Qt.size(56, 56)
                                            smooth: true
                                        }
                                        SettingsControls.Glyph {
                                            anchors.centerIn: parent
                                            anchors.verticalCenterOffset: 1
                                            width: 15
                                            height: 15
                                            path: modelData.glyph
                                            filled: modelData.filled === true
                                            color: Qt.rgba(0, 0, 0, 0.3)
                                        }
                                        SettingsControls.Glyph {
                                            anchors.centerIn: parent
                                            width: 15
                                            height: 15
                                            path: modelData.glyph
                                            filled: modelData.filled === true
                                        }
                                    }
                                    Text {
                                        horizontalAlignment: Text.AlignLeft
                                        Layout.fillWidth: true
                                        text: modelData.name
                                        color: look.ink
                                        opacity: navItem.current ? 1 : 0.88
                                        font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
                                        font.weight: navItem.current ? Font.DemiBold : Font.Normal
                                        elide: Text.ElideRight
                                    }
                                    // Opens in KDE's settings, not here.
                                    SettingsControls.Glyph {
                                        visible: modelData.kde !== undefined
                                        Layout.preferredWidth: 11
                                        Layout.preferredHeight: 11
                                        path: "M7 17L17 7M9 7h8v8"
                                        color: look.ink
                                        opacity: navHover.hovered ? 0.6 : 0.32
                                    }
                                }
                                HoverHandler { id: navHover }
                                TapHandler { onTapped: sheet.go(modelData) }
                                Accessible.role: Accessible.PageTab
                                Accessible.name: modelData.name
                                Accessible.description: modelData.kde !== undefined ? i18n("Opens in a separate window") : ""
                                Accessible.selected: current
                                Accessible.onPressAction: sheet.go(modelData)
                            }
                        }

                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            Layout.leftMargin: 10
                            Layout.topMargin: 8
                            visible: !sheet.searchBusy && sheet.searchResults.length === 0 && sheet.searchProblem === ""
                                     && !sheet.pages.some(p => side.matches(p))
                            text: i18n("Nothing here by that name. Try More settings.")
                            color: look.dim
                            font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                            wrapMode: Text.Wrap
                        }
                    }
                }

                Rectangle {
                    id: moreSettings
                    objectName: "settingsMore"
                    Layout.fillWidth: true
                    Layout.preferredHeight: Math.max(34, Kirigami.Theme.defaultFont.pointSize * 4 / 3 + 16)
                    radius: 10
                    color: kdeHover.hovered ? (look.dark ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.3)) : "transparent"
                    border.width: activeFocus ? 2 : 0
                    border.color: look.lily
                    activeFocusOnTab: true
                    Keys.onSpacePressed: sheet.ask("kde " + sheet.kdePage())
                    Keys.onReturnPressed: sheet.ask("kde " + sheet.kdePage())
                    Keys.onEnterPressed: sheet.ask("kde " + sheet.kdePage())
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        text: i18n("More settings ›")
                        color: look.ink
                        opacity: 0.78
                        font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                        font.weight: Font.Medium
                        elide: Text.ElideRight
                    }
                    HoverHandler { id: kdeHover }
                    TapHandler { onTapped: sheet.ask("kde " + sheet.kdePage()) }
                    Accessible.role: Accessible.Link
                    Accessible.name: i18n("More settings")
                    Accessible.onPressAction: sheet.ask("kde " + sheet.kdePage())
                }
            }

            // Without accents or capitals on either side: "ecran" finds "Écran".
            function fold(text) {
                return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
            }
            function matches(entry) {
                const words = fold(search.text.trim()).split(/\s+/).filter(word => word !== "")
                const all = fold(entry.name + " " + entry.words)
                return words.every(word => all.indexOf(word) !== -1)
            }
        }

        // The page: solid paper, so reading never fights the painting.
        Rectangle {
            id: pageArea
            anchors.left: side.right
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            radius: 14
            // All paper: the window under it is glass now.
            color: Qt.rgba(look.paper.r, look.paper.g, look.paper.b, 1)
            border.width: 1
            border.color: look.dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(1, 1, 1, 0.7)

            Flickable {
                id: scroller
                objectName: "settingsScroller"
                Shared.MouseScroll { view: scroller }
                Shared.ScrollInput { id: pageInput; view: scroller; onScrollRequested: scroller.leaveFocus() }
                Keys.priority: Keys.AfterItem
                Keys.onPressed: event => pageInput.key(event)
                anchors.fill: parent
                anchors.topMargin: 2
                anchors.bottomMargin: sheet.page === "notifications" ? notificationFeedback.height + 12 : 2
                clip: true
                contentWidth: width
                contentHeight: pageLoader.height + 60
                boundsBehavior: Flickable.StopAtBounds
                property bool followFocus: true
                // The control that had focus when the page was scrolled away from it (the wheel,
                // touchpad, keys, a drag or the scroll bar): a page that grows or shrinks later, as
                // Wi-Fi's networks come and go, doesn't pull it back into view, which stopped the
                // scroll. Moving the focus on follows again.
                property Item leftBehind: null
                function leaveFocus() { leftBehind = sheet.activeFocusItem }
                onMovementStarted: leaveFocus()
                function resumeFocusTracking() { followFocus = sheet.active }
                function revealFocus() {
                    const item = sheet.activeFocusItem
                    let ancestor = item
                    while (ancestor && ancestor !== scroller.contentItem) ancestor = ancestor.parent
                    if (!followFocus || !sheet.active || !item || !ancestor || item === leftBehind) return
                    const top = item.mapToItem(scroller.contentItem, 0, 0).y
                    if (top < contentY + 12) contentY = Math.max(0, top - 12)
                    else if (top + item.height > contentY + height - 12)
                        contentY = Math.min(Math.max(0, contentHeight - height), top + item.height - height + 12)
                }
                onHeightChanged: Qt.callLater(revealFocus)
                onContentHeightChanged: {
                    if (followFocus && sheet.active) Qt.callLater(revealFocus)
                    Qt.callLater(sheet.updateSearchHighlight)
                }
                Connections {
                    target: sheet
                    function onActiveChanged() {
                        // The window restores focus during activation. Reveal only later moves.
                        scroller.followFocus = false
                        if (sheet.active) Qt.callLater(scroller.resumeFocusTracking)
                    }
                    function onActiveFocusItemChanged() {
                        // Not when the window gives back the same focus as it's activated again.
                        if (sheet.active && sheet.activeFocusItem && sheet.activeFocusItem !== scroller.leftBehind)
                            scroller.leftBehind = null
                        if (sheet.active && scroller.followFocus) Qt.callLater(scroller.revealFocus)
                    }
                }
                T.ScrollBar.vertical: SettingsControls.Rail { tone: look; onPressedChanged: if (pressed) scroller.leaveFocus() }

                Loader {
                    id: pageLoader
                    objectName: "settingsPageLoader"
                    x: 34
                    y: 28
                    width: scroller.width - 68
                    property real shift: 0
                    transform: Translate { y: pageLoader.shift }
                    // Compile only the selected page, without blocking window input.
                    asynchronous: true
                    source: ({
                        light: "SettingsLight.qml", wifi: "SettingsWifi.qml", bluetooth: "SettingsBluetooth.qml", phone: "SettingsPhone.qml", display: "SettingsDisplay.qml",
                        sound: "SettingsSound.qml", datetime: "SettingsDatetime.qml", users: "SettingsUsers.qml", input: "SettingsInput.qml",
                        power: "SettingsPower.qml", notifications: "SettingsNotifications.qml", accessibility: "SettingsAccessibility.qml", apps: "SettingsApps.qml",
                        storage: "SettingsStorage.qml", backups: "SettingsBackups.qml", recovery: "SettingsRecovery.qml", games: "SettingsGames.qml", windows: "SettingsWindows.qml", privacy: "SettingsPrivacy.qml",
                        security: "SettingsSecurity.qml", passwords: "SettingsPasswords.qml",
                        printers: "SettingsPrinters.qml", welcome: "SettingsWelcome.qml",
                        updates: "SettingsUpdates.qml", about: "SettingsAbout.qml"
                    })[sheet.page]
                    onLoaded: {
                        pageInput.stopWheelAnimation()
                        scroller.contentY = 0
                        enter.restart()
                    }
                }

                ParallelAnimation {
                    id: enter
                    NumberAnimation { target: pageLoader; property: "opacity"; from: 0; to: 1; duration: Math.round(280 * sheet.speed); easing.type: Easing.OutCubic }
                    NumberAnimation { target: pageLoader; property: "shift"; from: 8; to: 0; duration: Math.round(280 * sheet.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] }
                }
            }

            Rectangle {
                id: notificationFeedback
                objectName: "notificationFeedback"
                visible: sheet.page === "notifications" && (sheet.notifyBusy !== "" || sheet.notifyMessage !== "")
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.margins: 12
                height: Math.max(56, feedbackRow.implicitHeight + 20)
                radius: 12
                color: look.wash2
                RowLayout {
                    id: feedbackRow
                    anchors.fill: parent
                    anchors.margins: 10
                    Text {
                        Layout.fillWidth: true
                        color: look.ink
                        text: sheet.notifyBusy !== "" ? i18n("Changing…") : sheet.notifyMessage
                        font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                        wrapMode: Text.Wrap
                        Accessible.role: sheet.notifyFailed ? Accessible.AlertMessage : Accessible.StaticText
                        Accessible.name: text
                    }
                    SettingsControls.Pill {
                        objectName: "notificationRetry"
                        tone: look
                        visible: sheet.notifyFailed && sheet.notifyBusy === ""
                        text: i18n("Try again")
                        onClicked: sheet.changeNotification(sheet.notifyRetry)
                    }
                }
            }

        }

        // Not drawn: timers, colors and the pages.

        // Your photo: the chooser, and how far the painting is while it's on its way.
        FileDialog {
            id: photoPicker
            title: i18n("Choose a photo to paint")
            nameFilters: [i18n("Photos") + " (*.jpg *.jpeg *.png *.webp *.tif *.tiff *.bmp)"]
            onAccepted: sheet.paintPhoto(selectedFile)
        }
        Timer {
            interval: 1500
            repeat: true
            triggeredOnStart: true
            running: sheet.pollingActive && sheet.page === "light" && sheet.photoInfo.state === "painting"
            onTriggered: sheet.loadPhotoState()
        }

        Timer {
            interval: 4000
            repeat: true
            running: sheet.pollingActive && (sheet.statusPage || sheet.page === "notifications")
            onTriggered: {
                sheet.refresh()
                if (sheet.page === "bluetooth" && sheet.busyDevice === "") {
                    sheet.ask("bt-list", out => sheet.devices = sheet.json(out, sheet.devices))
                }
                if (sheet.page === "notifications") sheet.loadNotifications()
                // Networks come and go (and are slow to show after waking): look again, but never
                // while a password is being typed, which a new list would wipe. A cable, too.
                if (sheet.page === "wifi") {
                    sheet.loadWiredNetwork()
                    if (sheet.joining === "")
                        sheet.ask("wifi-list", out => { sheet.nets = sheet.json(out, sheet.nets); sheet.netsLoaded = true })
                }
            }
        }

        Timer {
            id: rescan
            interval: 4000
            onTriggered: sheet.ask("wifi-list", out => sheet.nets = sheet.json(out, []))
        }

        Timer {
            id: flush
            interval: 120
            onTriggered: {
                for (const what in sheet.pending) {
                    sheet.ask(what + " " + sheet.pending[what])
                }
                sheet.pending = {}
            }
        }

        // Colors ----------------------------------------------------------------
        QtObject {
            id: look
            readonly property bool dark: frame.dark
            readonly property color ink: dark ? "#F1EEE8" : "#1C1B19"
            readonly property color dim: dark ? Qt.rgba(0.945, 0.933, 0.91, 0.76) : Qt.rgba(0.11, 0.106, 0.098, 0.74)
            readonly property color wash: dark ? Qt.rgba(1, 1, 1, 0.05) : Qt.rgba(0.11, 0.106, 0.098, 0.035)
            readonly property color wash2: dark ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(0.11, 0.106, 0.098, 0.07)
            readonly property color press: dark ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(0.11, 0.106, 0.098, 0.11)
            readonly property color line: dark ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(0.11, 0.106, 0.098, 0.08)
            readonly property color paper: dark ? Qt.rgba(0.122, 0.118, 0.11, 0.94) : Qt.rgba(0.984, 0.98, 0.969, 0.95)
            readonly property color lily: dark ? "#4DB4A0" : "#357F72"
            readonly property color sun: dark ? "#F0AD86" : "#A34727"
            readonly property real speed: sheet.speed
        }

        // What reopened after the last trip or restart, and what to retry: on Play on Windows,
        // and on Power & Sleep after a restart.
        Component {
            id: returnSummary
            SettingsControls.Card {
                id: summary
                readonly property string returnTitle: sheet.returnInfo.kind === "restart"
                    ? i18n("After your last restart") : i18n("After your last return")
                objectName: "search-return"
                tone: look
                Accessible.role: Accessible.Grouping
                Accessible.name: returnTitle
                SettingsControls.SettingRow {
                    tone: look
                    divider: false
                    title: summary.returnTitle
                    detail: sheet.returnInfo.busy ? i18n("Reopening your work…")
                        : sheet.returnInfo.available ? i18n("What opened, and what still needs attention. Open app uses its normal startup settings.")
                        : i18n("After a trip to Windows, your recovery summary appears here. Save your work before leaving; unsaved changes and private tabs aren't captured.")
                    Row {
                        spacing: 8
                        SettingsControls.Pill {
                            objectName: "returnRetryAll"
                            tone: look
                            visible: sheet.returnInfo.retry === true
                            text: i18n("Retry pending")
                            enabledPill: !sheet.returnBusy && !sheet.returnInfo.busy
                            onClicked: sheet.returnAction("retry", "")
                        }
                        SettingsControls.Pill {
                            objectName: "returnDismiss"
                            tone: look
                            visible: sheet.returnInfo.available === true
                            text: i18n("Dismiss")
                            enabledPill: !sheet.returnBusy && !sheet.returnInfo.busy
                            onClicked: sheet.returnAction("dismiss", "")
                        }
                    }
                }
                Repeater {
                    model: sheet.returnInfo.items || []
                    SettingsControls.SettingRow {
                        required property var modelData
                        tone: look
                        title: modelData.name
                        detail: modelData.detail + ((modelData.missing || []).length > 0
                            ? "\n" + i18n("Unavailable: %1", modelData.missing.join(", ")) : "")
                        Row {
                            spacing: 8
                            SettingsControls.Pill {
                                objectName: "returnRetry-" + modelData.app
                                tone: look
                                visible: modelData.retry === true
                                text: modelData.missingCount > 0 ? i18n("Retry documents") : i18n("Retry")
                                enabledPill: !sheet.returnBusy && !sheet.returnInfo.busy
                                onClicked: sheet.returnAction("retry", modelData.app)
                            }
                            SettingsControls.Pill {
                                objectName: "returnOpen-" + modelData.app
                                tone: look
                                visible: modelData.canOpen === true
                                text: i18n("Open app")
                                enabledPill: !sheet.returnBusy && !sheet.returnInfo.busy
                                onClicked: sheet.returnAction("open", modelData.app)
                            }
                            SettingsControls.Pill {
                                tone: look
                                visible: modelData.missingCount > 0
                                text: i18n("Backups")
                                onClicked: sheet.open("backups")
                            }
                        }
                    }
                }
                Text {
                    Layout.fillWidth: true
                    Layout.margins: 18
                    visible: sheet.returnInfo.available === true
                    text: i18n("Dismiss forgets this recovery list, not your files. Apps already running are left alone.")
                    color: look.dim
                    font.pixelSize: Math.max(14, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 2)
                    wrapMode: Text.Wrap
                }
                SettingsControls.SettingRow {
                    tone: look
                    visible: sheet.returnProblem !== "" || sheet.returnReadProblem !== ""
                    title: sheet.returnProblem || sheet.returnReadProblem
                    strong: false
                    SettingsControls.Pill {
                        objectName: "returnRefresh"
                        tone: look
                        text: i18n("Refresh")
                        enabledPill: !sheet.returnLoading && !sheet.returnBusy
                        onClicked: sheet.loadReturn()
                    }
                }
            }
        }

    }

    // Seconds with one decimal, the way this PC's region writes them.
    function secs(value) {
        return Number(value).toLocaleString(Qt.locale(), "f", 1)
    }

    // A page of Monet's own, or one KDE's settings show (then this stays put).
    function go(entry) {
        currentAnchor = ""
        pendingAnchor = ""
        if (entry.kde)
            ask("kde " + entry.kde)
        else
            page = entry.id
    }

    // More settings at KDE's page for the one open here (KDE's own first page is out of sight).
    function kdePage() {
        return ({ wifi: "wifi", bluetooth: "bluetooth", phone: "phone", printers: "printers", display: "display",
                  sound: "sound", datetime: "datetime", users: "users", input: "input", power: "power",
                  privacy: "screenlocker", notifications: "notifications", apps: "apps", accessibility: "access",
                  games: "gamecontroller", light: "fonts" })[page] || "all"
    }

    function entry(id) {
        return pages.find(p => p.id === id) || ({})
    }

    // What Bluetooth says a device is (its icon name), as a glyph.
    function deviceGlyph(kind) {
        if (kind.indexOf("audio") === 0)
            return "M4 15v-3a8 8 0 0 1 16 0v3M4 14h3v6H4zM17 14h3v6h-3z"
        if (kind === "input-gaming")
            return "M7.5 8.5h9a4 4 0 0 1 3.9 4.9l-.8 3.3a2 2 0 0 1-3.4.9L14.8 16H9.2l-1.4 1.6a2 2 0 0 1-3.4-.9l-.8-3.3a4 4 0 0 1 3.9-4.9zM8.5 11.5v3M7 13h3M15.5 12h.01M17 14h.01"
        if (kind === "input-mouse")
            return "M12 3a6 6 0 0 1 6 6v6a6 6 0 0 1-12 0V9a6 6 0 0 1 6-6zM12 7v3"
        if (kind === "input-keyboard")
            return "M3 7h18v10H3zM7 10.5h.01M11 10.5h.01M15 10.5h.01M8 14h8"
        if (kind === "phone")
            return "M8 3h8v18H8zM11 18h2"
        if (kind === "computer")
            return "M4 5h16v10H4zM2 19h20"
        return entry("bluetooth").glyph
    }

    // Speakers, headphones or a screen, from the output's name.
    function outputGlyph(name) {
        if (/head|ear|buds/i.test(name))
            return deviceGlyph("audio")
        if (/hdmi|displayport|monitor|tv/i.test(name))
            return entry("display").glyph
        return entry("sound").glyph
    }
}
