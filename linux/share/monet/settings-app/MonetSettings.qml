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
import QtQuick.Shapes
import QtQuick.Templates as T
import QtQuick.Window
import org.kde.kirigami as Kirigami
import "../games" as Shared

Shared.MonetWindow {
    id: sheet

    readonly property real speed: Kirigami.Units.longDuration / 200
    width: Math.min(1000, Screen.desktopAvailableWidth - 64)
    height: Math.min(780, Screen.desktopAvailableHeight - 96)
    minimumWidth: Math.min(760, Screen.desktopAvailableWidth - 32)
    minimumHeight: Math.min(520, Screen.desktopAvailableHeight - 48)
    // See-through: the glass column's glass is WindowGlass (Games' and the Store's too).
    color: "transparent"
    // The size people gave it, kept for next time (~/.config/monet/settings.conf).
    Settings {
        category: "Window"
        property alias windowWidth: sheet.width
        property alias windowHeight: sheet.height
    }
    property string page: "light"
    property var searchResults: []
    property int searchRevision: 0
    property bool searchBusy: false
    property string searchReady: ""
    property string searchProblem: ""
    property string pendingAnchor: ""
    property int anchorAttempts: 0
    property var windowsFiles: ({})

    Timer {
        id: searchDelay
        interval: 140
        onTriggered: sheet.findSettings(false)
    }
    Timer {
        id: anchorDelay
        interval: 50
        repeat: true
        running: sheet.pendingAnchor !== "" && sheet.anchorAttempts < 20
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
    function findSearchTarget(item, name) {
        if (!item) return null
        if (item.objectName === "search-" + name) return item
        for (let child of item.children || []) {
            const found = findSearchTarget(child, name)
            if (found) return found
        }
        return null
    }
    function revealSearchTarget() {
        const target = findSearchTarget(pageLoader.item, pendingAnchor)
        if (!target || !target.visible || target.height <= 0) return
        const top = target.mapToItem(scroller.contentItem, 0, 0).y
        scroller.contentY = Math.max(0, Math.min(top - 20, scroller.contentHeight - scroller.height))
        target.forceActiveFocus(Qt.ShortcutFocusReason)
        pendingAnchor = ""
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
              + " " + i18nc("Settings search words, space-separated", "snap layouts assist windows side by side halves tiling") },
        { id: "wifi", name: i18n("Wi-Fi"), glyph: "M4 10a12 12 0 0 1 16 0M7 13.5a7.5 7.5 0 0 1 10 0M10 17a3 3 0 0 1 4 0",
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
                      "power sleep suspend screen off energy battery lid button shutdown performance saver mode") },
        { id: "privacy", name: i18n("Lock & Privacy"), glyph: "M6.5 11h11v9h-11zM9 11V8a3 3 0 0 1 6 0v3",
          words: i18nc("Settings search words, space-separated",
                      "lock screen locker password wake sleep privacy recent files history forget remember away fingerprint finger") },
        { id: "security", name: i18n("Security"), glyph: "M12 3l7.5 3v5.5c0 4.6-3.1 8.4-7.5 9.5-4.4-1.1-7.5-4.9-7.5-9.5V6zM9 12l2.2 2.2L15.5 10",
          words: i18nc("Settings search words, space-separated",
                      "security safe safety protection protected secure boot encryption encrypted firewall updates firmware backups virus antivirus malware") },
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
    property var nets: []
    // Whether a look for networks has come back yet (until then: looking).
    property bool netsLoaded: false
    property var devices: []
    property var outputs: []
    // The apps playing sound, each with its own volume.
    property var appsSound: []
    // Battery care: whether the battery can stop at 80%, and where it stops.
    property var batteryCare: ({ supported: false, limit: 100 })
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
    // The earlier versions of one file, when Files asked for them.
    property var earlier: ({})
    // Games & Controllers: { controllers, overlay, pair, libraries }.
    property var gameInfo: ({})
    // What's new in this Monet: { version, headline, items: [{ title, text }] }.
    property var whatsNew: ({})
    // Lock & Privacy: { lockAfter, lockOnResume, remember }; Printers: { printers, cups }.
    property var privacyInfo: ({})
    property var printerInfo: ({})
    // The Monet before the last update: { version, date, pending }, or {}.
    property var previous: ({})
    // An update that didn't start here, so Monet went back by itself: { version, to }, or {}.
    property var wentBack: ({})
    // Reset this PC: { pending } once it waits for the next restart.
    property var resetState: ({})
    property var accessInfo: ({})
    // Phone: the phones KDE Connect knows ([{id, name, paired, near, battery, charging}]),
    // whether it's here at all, and the one asked to pair (its answer is on the phone).
    property var phoneList: []
    property bool phoneApp: true
    property string phoneAsked: ""
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
        running: sheet.visible && sheet.page === "windows"
        onTriggered: sheet.loadReturn()
    }
    // Updates: "", "checking", "none", "available", "installing", "done" or
    // "failed"; what the check found; and what Monet said.
    property string updateState: ""
    property var updateFound: ({})
    property string updateMessage: ""
    // Firmware for the PC's own parts (fwupd): the same states, and the updates.
    // Security: what keeps the PC safe (monet-quick security), the fix that's running, asking
    // before the restart into the firmware settings, and Monet's key asked for.
    property var safety: ({})
    property string securityFixing: ""
    property bool askingFirmwareSetup: false
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
        const destination = (which || "").split("#")
        if (destination[0] && (destination[0] === "welcome" || pages.some(p => p.id === destination[0]))) {
            pendingAnchor = /^[a-z-]+$/.test(destination[1] || "") ? destination[1] : ""
            anchorAttempts = 0
            page = destination[0]
        }
        if (visibility === Window.Minimized) {
            showNormal()
        } else {
            show()
        }
        raise()
        requestActivate()
        load()
    }

    onPageChanged: {
        joining = ""
        asking = null
        renaming = false
        if (passwordState !== "changing") {
            passwordState = ""
        }
        if (visible) {
            load()
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
            return JSON.parse(text)
        } catch (e) {
            return fallback
        }
    }

    function refresh() {
        ask("status", out => { if (!sheet.dragging) sheet.info = sheet.json(out, sheet.info) })
    }

    function load() {
        refresh()
        if (page === "light") {
            ask("prefs", out => sheet.prefs = sheet.json(out, sheet.prefs))
            ask("paint-state", out => sheet.photoInfo = sheet.json(out, sheet.photoInfo))
        } else if (page === "wifi") {
            ask("wifi-list", out => { sheet.nets = sheet.json(out, []); sheet.netsLoaded = true })
            ask("hotspot", out => sheet.hotspot = sheet.json(out, sheet.hotspot))
        } else if (page === "bluetooth") {
            ask("bt-list", out => sheet.devices = sheet.json(out, []))
        } else if (page === "sound") {
            ask("outputs", out => sheet.outputs = sheet.json(out, []))
            ask("apps-sound", out => { if (!sheet.dragging) sheet.appsSound = sheet.json(out, []) })
        } else if (page === "about") {
            ask("startup", out => sheet.startup = sheet.json(out, {}))
        } else if (page === "security") {
            askingFirmwareSetup = false
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
            ask("power", out => sheet.powerInfo = sheet.json(out, sheet.powerInfo))
            ask("battery-care", out => sheet.batteryCare = sheet.json(out, sheet.batteryCare))
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
            ask("screens", out => sheet.screenInfo = sheet.json(out, []))
        } else if (page === "storage") {
            ask("storage", out => sheet.storageInfo = sheet.json(out, sheet.storageInfo))
            ask("onedrive", out => sheet.oneDrive = sheet.json(out, sheet.oneDrive))
            ask("shared-files", out => sheet.windowsFiles = sheet.json(out, {}))
        } else if (page === "backups") {
            ask("backup", out => sheet.backup = sheet.json(out, sheet.backup))
            ask("versions", out => sheet.earlier = sheet.json(out, {}))
        } else if (page === "phone") {
            phoneAsked = ""
            loadPhones()
        } else if (page === "accessibility") {
            ask("access", out => sheet.accessInfo = sheet.json(out, sheet.accessInfo))
        } else if (page === "games") {
            ask("gaming", out => sheet.gameInfo = sheet.json(out, sheet.gameInfo))
            ask("game-marks", out => sheet.gameMarks = sheet.json(out, sheet.gameMarks))
        } else if (page === "privacy") {
            ask("privacy", out => sheet.privacyInfo = sheet.json(out, sheet.privacyInfo))
        } else if (page === "printers") {
            ask("printers", out => sheet.printerInfo = sheet.json(out, sheet.printerInfo))
        }
        if (page === "updates") {
            ask("previous", out => sheet.previous = sheet.json(out, {}))
            ask("whats-new", out => sheet.whatsNew = sheet.json(out, {}))
            ask("went-back", out => sheet.wentBack = sheet.json(out, {}))
            ask("reset-state", out => sheet.resetState = sheet.json(out, {}))
        }
        if (page === "windows" || page === "updates" || page === "about") {
            ask("about", out => sheet.pc = sheet.json(out, sheet.pc))
        }
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

    function pickOutput(output) {
        if (!Number.isInteger(output.id)) {
            return
        }
        outputs = outputs.map(o => Object.assign({}, o, { default: o.id === output.id }))
        ask("output " + output.id, () => sheet.ask("outputs", out => sheet.outputs = sheet.json(out, sheet.outputs)))
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
    function checkUpdates() {
        updateState = "checking"
        ask("update-check", out => {
            const found = sheet.json(out, { ok: false })
            sheet.updateFound = found
            sheet.updateMessage = found.message || ""
            sheet.updateState = !found.ok ? "failed" : found.system || found.apps > 0 ? "available" : "none"
        })
        checkFirmware()
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
        firmwareState = "checking"
        ask("firmware-check", out => {
            const found = sheet.json(out, { ok: false })
            sheet.firmware = found.updates || []
            sheet.firmwareMessage = found.message || ""
            sheet.firmwareState = !found.ok ? "failed" : sheet.firmware.length > 0 ? "available" : "none"
        })
    }

    function loadSecurity() {
        ask("security", out => sheet.safety = sheet.json(out, sheet.safety))
    }

    // A fix from the Security page; the ones that need an administrator ask for the password.
    function fixSecurity(command) {
        securityFixing = command
        ask(command, out => {
            const result = sheet.json(out, { ok: true })
            sheet.securityFixing = ""
            if (command === "trust-key" && result.ok) {
                sheet.keyAsked = true
            }
            sheet.loadSecurity()
        })
    }

    // How many things on the Security page want a look.
    function securityProblems() {
        const s = safety
        return [s.secureBoot === "off", s.encrypted === false, s.firewall === "off",
                s.autoUpdates === false || s.updateWaiting === true,
                firmwareState === "available" || (firmwareState === "done" && firmwareRestart),
                s.versions === false].filter(x => x).length
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
        ask("update", out => {
            const result = sheet.json(out, { ok: false, message: "" })
            const lines = (result.message || "").split("\n").map(l => l.trim()).filter(l => l !== "")
            sheet.updateMessage = lines.length > 0 ? lines[lines.length - 1] : ""
            sheet.updateState = result.ok ? "done" : "failed"
        })
    }

    function updateTitle() {
        const found = updateFound
        if (updateState === "available" && found.system) {
            // The same Monet built again on a fixed base: fixes, not a new version. Older images
            // carry their base's version ("44.20261012.1"), which isn't Monet's to show.
            if (found.version && found.version === pc.monet) {
                return i18n("Fixes for Monet %1 are ready", found.version)
            }
            return /^\d{1,2}\.\d{1,2}(\.\d{1,2})?$/.test(found.version || "") ? i18n("Monet %1 is ready", found.version)
                : i18n("A new Monet is ready")
        }
        if (updateState === "available") {
            return i18np("%1 app update is ready", "%1 app updates are ready", found.apps || 0)
        }
        if (updateState === "done") {
            return updateFound.system ? i18n("Restart to finish") : i18n("Your apps are up to date")
        }
        return pc.monet ? i18n("Monet %1", pc.monet) : i18n("Monet")
    }

    function updateDetail() {
        const found = updateFound
        switch (updateState) {
        case "checking": return i18n("Looking for updates…")
        case "none": return i18n("Monet and your apps are up to date.")
        case "available":
            return found.system && found.apps > 0 ? i18np("And %1 app update. Install when you're ready.", "And %1 app updates. Install when you're ready.", found.apps || 0)
                : i18n("Install when you're ready.")
        case "installing": return i18n("Downloading and installing. You can keep using your PC.")
        case "done": return updateFound.system ? i18n("The new Monet starts the next time you restart.") : i18n("Everything is installed.")
        case "failed": return updateMessage || i18n("Monet couldn't look for updates. Check your internet connection and try again.")
        default: return i18n("Monet only updates when you ask it to.")
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

    function powerTime(state, what, seconds) {
        powerInfo = changed(powerInfo, [state, what], seconds)
        ask("power-time " + state + " " + what + " " + seconds, () => sheet.reloadPower())
    }
    function powerAction(key, action) {
        powerInfo = changed(powerInfo, [key === "button" ? "button" : "lidAction"], action)
        ask((key === "button" ? "power-button " : "power-lid ") + action, () => sheet.reloadPower())
    }
    function powerMode(mode) {
        powerInfo = changed(powerInfo, ["mode"], mode)
        ask("power-mode " + mode, () => sheet.reloadPower())
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
        ask("empty-trash", () => ask("storage", out => sheet.storageInfo = sheet.json(out, sheet.storageInfo)))
    }
    function privacy(what, value) {
        privacyInfo = changed(privacyInfo, [what], value)
        ask(what === "lockAfter" ? "lock-after " + value
            : (what === "lockOnResume" ? "lock-resume " : "remember ") + (value ? "on" : "off"))
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
        ask("phones", out => {
            const found = sheet.json(out, [])
            sheet.phoneApp = found !== null
            sheet.phoneList = found || []
            if (sheet.phoneList.some(p => p.id === sheet.phoneAsked && p.paired))
                sheet.phoneAsked = ""
        })
    }

    function access(what, value) {
        accessInfo = changed(accessInfo, [what], value)
        const said = what === "reduced" ? (value ? "reduced" : "normal") : (what === "reader" || what === "zoom") ? (value ? "on" : "off") : value
        ask("access-" + ({ scale: "scale", cursor: "cursor", reduced: "motion", reader: "reader", zoom: "zoom" })[what] + " " + said)
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

    // Pieces ----------------------------------------------------------------
    // Inline components can't see this file's ids, so everything they need
    // comes in through properties.

    component Glyph: Item {
        id: glyph
        property string path
        property bool filled
        property color color: "#FFFFFF"
        implicitWidth: 16
        implicitHeight: 16
        Shape {
            anchors.fill: parent
            // Smooth edges without a multisampled layer for every glyph.
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                scale: Qt.size(glyph.width / 24, glyph.height / 24)
                strokeColor: glyph.color
                strokeWidth: 2.4
                fillColor: glyph.filled ? glyph.color : "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: glyph.path }
            }
        }
    }

    component Rounded: Item {
        id: rounded
        property real radius: 12
        default property alias content: inside.data
        Item {
            id: inside
            anchors.fill: parent
            layer.enabled: true
            layer.effect: MultiEffect {
                maskEnabled: true
                maskSource: shape
                maskThresholdMin: 0.5
                maskSpreadAtMin: 1.0
            }
        }
        Rectangle {
            id: shape
            anchors.fill: parent
            radius: rounded.radius
            visible: false
            layer.enabled: true
        }
    }

    // A page's title next to its swatch, as large as the one in the list.
    component PageTitle: RowLayout {
        id: heading
        property var tone
        property string text
        property string detail
        property var entry: ({})
        property string art
        Layout.fillWidth: true
        spacing: 16
        Item {
            visible: heading.entry.glyph !== undefined
            Layout.preferredWidth: 46
            Layout.preferredHeight: 46
            Layout.alignment: Qt.AlignTop
            Image {
                anchors.fill: parent
                source: heading.art + "swatch-" + (heading.entry.swatch || heading.entry.id) + ".png"
                sourceSize: Qt.size(92, 92)
                smooth: true
            }
            Glyph {
                anchors.centerIn: parent
                anchors.verticalCenterOffset: 1
                width: 24
                height: 24
                path: heading.entry.glyph || ""
                filled: heading.entry.filled === true
                color: Qt.rgba(0, 0, 0, 0.3)
            }
            Glyph {
                anchors.centerIn: parent
                width: 24
                height: 24
                path: heading.entry.glyph || ""
                filled: heading.entry.filled === true
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: heading.text
                color: heading.tone.ink
                font.family: "Fraunces 72pt SuperSoft"
                font.weight: Font.Light
                font.pixelSize: 30
                elide: Text.ElideRight
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                visible: heading.detail !== ""
                text: heading.detail
                color: heading.tone.dim
                font.pixelSize: 14
                wrapMode: Text.Wrap
            }
        }
    }

    component Caption: Text {
        property var tone
        Layout.fillWidth: true
        Layout.bottomMargin: -10
        color: tone.dim
        font.pixelSize: 12
        font.weight: Font.DemiBold
        font.letterSpacing: 0.7
        font.capitalization: Font.AllUppercase
    }

    component Card: Rectangle {
        id: card
        property var tone
        default property alias rows: list.data
        Layout.fillWidth: true
        implicitHeight: list.implicitHeight
        radius: 16
        color: tone.wash
        border.width: activeFocus ? 2 : 1
        border.color: activeFocus ? tone.lily : tone.line
        ColumnLayout {
            id: list
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            spacing: 0
        }
    }

    component SettingRow: Item {
        id: row
        property var tone
        property string title
        property string detail
        property bool divider: true
        property bool tappable: false
        property bool checkable: false
        property bool checked: false
        property bool strong: true
        default property alias trailing: slot.data
        property alias lead: leadSlot.data
        signal tapped()
        readonly property bool stacked: slot.childrenRect.width > 0
            && width - slot.childrenRect.width - leadSlot.width - 52 < 180
        Layout.fillWidth: true
        implicitHeight: stacked ? Math.max(texts.implicitHeight, leadSlot.childrenRect.height) + slot.childrenRect.height + 40
            : Math.max(texts.implicitHeight, slot.childrenRect.height, leadSlot.childrenRect.height) + 28
        activeFocusOnTab: tappable
        Keys.onSpacePressed: if (tappable) row.tapped()
        Keys.onReturnPressed: if (tappable) row.tapped()

        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: 14
            color: row.tone.wash
            opacity: hover.hovered && row.tappable ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: Math.round(140 * row.tone.speed) } }
        }
        Rectangle {
            visible: row.divider
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 18
            anchors.rightMargin: 18
            height: 1
            color: row.tone.line
        }
        Rectangle {
            anchors.fill: parent
            anchors.margins: 2
            radius: 14
            color: "transparent"
            border.width: 2
            border.color: row.tone.lily
            visible: row.activeFocus
        }
        Item {
            id: leadSlot
            anchors.left: parent.left
            anchors.leftMargin: 18
            y: row.stacked ? texts.y + (texts.height - height) / 2 : (row.height - height) / 2
            width: childrenRect.width
            height: childrenRect.height
        }
        ColumnLayout {
            id: texts
            objectName: "settingRowText"
            anchors.left: leadSlot.right
            anchors.leftMargin: leadSlot.width > 0 ? 12 : 0
            anchors.right: row.stacked ? parent.right : slot.left
            anchors.rightMargin: row.stacked ? 18 : 16
            y: row.stacked ? 14 : (row.height - height) / 2
            spacing: 3
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: row.title
                textFormat: Text.PlainText
                color: row.tone.ink
                font.pixelSize: 14
                font.weight: row.strong ? Font.DemiBold : Font.Medium
                wrapMode: row.stacked ? Text.Wrap : Text.NoWrap
                elide: row.stacked ? Text.ElideNone : Text.ElideRight
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                visible: row.detail !== ""
                text: row.detail
                textFormat: Text.PlainText
                color: row.tone.dim
                font.pixelSize: 13
                wrapMode: Text.Wrap
            }
        }
        Item {
            id: slot
            objectName: "settingRowControls"
            anchors.right: parent.right
            anchors.rightMargin: 18
            y: row.stacked ? Math.max(texts.y + texts.height, leadSlot.y + leadSlot.height) + 12
                : (row.height - height) / 2
            width: childrenRect.width
            height: childrenRect.height
        }
        HoverHandler { id: hover }
        TapHandler {
            enabled: row.tappable
            onTapped: row.tapped()
        }
        Accessible.role: checkable ? Accessible.CheckBox : tappable ? Accessible.Button : Accessible.StaticText
        Accessible.checked: checked
        Accessible.name: title
        Accessible.description: detail
        Accessible.onPressAction: if (tappable) row.tapped()
        Accessible.onToggleAction: if (tappable) row.tapped()
    }

    component Switch: Rectangle {
        id: toggle
        property var tone
        property bool active
        implicitWidth: 44
        implicitHeight: 26
        radius: 13
        color: active ? "#357F72" : (tone.dark ? Qt.rgba(1, 1, 1, 0.18) : Qt.rgba(0.11, 0.106, 0.098, 0.16))
        Behavior on color { ColorAnimation { duration: Math.round(200 * toggle.tone.speed) } }
        Rectangle {
            x: toggle.active ? 21 : 3
            y: 3
            width: 20
            height: 20
            radius: 10
            color: "#FFFFFF"
            Behavior on x { NumberAnimation { duration: Math.round(220 * toggle.tone.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.2, 1, 1] } }
        }
        Accessible.role: Accessible.CheckBox
        Accessible.checked: active
    }

    component Check: Rectangle {
        id: tick
        property var tone
        property bool active
        implicitWidth: 22
        implicitHeight: 22
        radius: 11
        color: active ? "#357F72" : "transparent"
        border.width: active ? 0 : 1.5
        border.color: tone.dark ? Qt.rgba(1, 1, 1, 0.3) : Qt.rgba(0.11, 0.106, 0.098, 0.28)
        Glyph {
            anchors.centerIn: parent
            width: 12
            height: 12
            visible: tick.active
            path: "M5 12.4l4.8 4.6 9.2-10"
            color: "#FFFFFF"
        }
    }

    // Security's mark for each row: lily with a tick when it's as it should be, amber with "!"
    // when it wants a look, an empty ring when Monet can't tell.
    component Mark: Rectangle {
        id: mark
        property var tone
        property bool good
        property bool known: true
        implicitWidth: 22
        implicitHeight: 22
        radius: 11
        color: !known ? "transparent" : good ? "#357F72" : "#D9892E"
        border.width: known ? 0 : 1.5
        border.color: tone.dark ? Qt.rgba(1, 1, 1, 0.3) : Qt.rgba(0.11, 0.106, 0.098, 0.28)
        Glyph {
            anchors.centerIn: parent
            width: 12
            height: 12
            visible: mark.known
            path: mark.good ? "M5 12.4l4.8 4.6 9.2-10" : "M12 5v8M12 18.5v.5"
            color: "#FFFFFF"
        }
    }

    component Bars: Row {
        id: bars
        property var tone
        property int level: 3
        spacing: 2
        Repeater {
            model: [5, 9, 14]
            Rectangle {
                anchors.bottom: parent.bottom
                width: 3
                height: modelData
                radius: 1
                color: index < bars.level ? bars.tone.ink : (bars.tone.dark ? Qt.rgba(1, 1, 1, 0.25) : Qt.rgba(0.11, 0.106, 0.098, 0.22))
            }
        }
        height: 14
    }

    component Pill: Rectangle {
        id: pill
        property var tone
        property string text
        // "plain", "lily", or "sun" (the one bright thing: Play and Restart in Windows).
        property string kind: "plain"
        property bool enabledPill: true
        signal clicked()
        implicitWidth: label.implicitWidth + (kind === "sun" ? 40 : 32)
        implicitHeight: kind === "sun" ? 40 : 36
        radius: kind === "sun" ? 20 : 12
        opacity: enabledPill ? 1 : 0.5
        color: kind === "sun" ? (hover.hovered ? "#FF6A42" : "#F2552C")
            : kind === "lily" ? (hover.hovered ? "#3F9483" : "#357F72")
            : (hover.hovered ? tone.press : tone.wash2)
        scale: tap.pressed ? 0.96 : hover.hovered && kind === "sun" ? 1.04 : 1
        border.width: activeFocus ? 2 : 0
        border.color: kind === "plain" ? tone.lily : "#FFFFFF"
        activeFocusOnTab: true
        Keys.onSpacePressed: if (enabledPill) pill.clicked()
        Keys.onReturnPressed: if (enabledPill) pill.clicked()
        Behavior on scale { NumberAnimation { duration: Math.round(160 * pill.tone.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
        Behavior on color { ColorAnimation { duration: Math.round(140 * pill.tone.speed) } }
        Text {
            horizontalAlignment: Text.AlignLeft
            id: label
            anchors.centerIn: parent
            text: pill.text
            color: pill.kind === "plain" ? pill.tone.ink : "#FFFFFF"
            font.pixelSize: pill.kind === "sun" ? 15 : 14
            font.weight: Font.DemiBold
        }
        HoverHandler { id: hover }
        TapHandler {
            id: tap
            enabled: pill.enabledPill
            onTapped: pill.clicked()
        }
        Accessible.role: Accessible.Button
        Accessible.name: text
        Accessible.onPressAction: if (enabledPill) pill.clicked()
    }

    // A few choices side by side, the chosen one on a pebble: [[value, label], …].
    // A key on the keyboard, as a small pebble; the Windows key ("Meta" to KDE) as its four panes.
    component Key: Rectangle {
        id: keyCap
        property var tone
        property string keyName
        implicitWidth: keyName === "Meta" ? 28 : Math.max(26, keyWord.implicitWidth + 14)
        implicitHeight: 24
        radius: 6
        color: tone.wash2
        border.width: 1
        border.color: tone.line
        Text {
            horizontalAlignment: Text.AlignLeft
            id: keyWord
            anchors.centerIn: parent
            visible: keyCap.keyName !== "Meta"
            text: keyCap.keyName
            color: keyCap.tone.ink
            font.pixelSize: 12
            font.weight: Font.DemiBold
        }
        Grid {
            anchors.centerIn: parent
            visible: keyCap.keyName === "Meta"
            columns: 2
            spacing: 2
            Repeater {
                model: 4
                Rectangle {
                    width: 5
                    height: 5
                    radius: 1
                    color: keyCap.tone.ink
                }
            }
        }
    }

    component Segments: Rectangle {
        id: segments
        property var tone
        property var options: []
        property var current
        signal picked(var value)
        implicitWidth: segmentRow.implicitWidth + 6
        implicitHeight: 34
        radius: 11
        color: tone.wash2
        Row {
            id: segmentRow
            anchors.centerIn: parent
            spacing: 2
            Repeater {
                model: segments.options
                Rectangle {
                    id: segment
                    required property var modelData
                    readonly property bool chosen: segments.current === modelData[0]
                    width: segmentLabel.implicitWidth + 22
                    height: 28
                    radius: 9
                    color: chosen ? (segments.tone.dark ? Qt.rgba(1, 1, 1, 0.17) : "#FFFFFF")
                        : segmentHover.hovered ? segments.tone.press : "transparent"
                    border.width: segment.activeFocus ? 2 : 0
                    border.color: segments.tone.lily
                    activeFocusOnTab: true
                    Keys.onSpacePressed: segments.picked(modelData[0])
                    Behavior on color { ColorAnimation { duration: Math.round(140 * segments.tone.speed) } }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        id: segmentLabel
                        anchors.centerIn: parent
                        text: segment.modelData[1]
                        color: segments.tone.ink
                        font.pixelSize: 13
                        font.weight: segment.chosen ? Font.DemiBold : Font.Medium
                    }
                    HoverHandler { id: segmentHover }
                    TapHandler { onTapped: segments.picked(segment.modelData[0]) }
                    Accessible.role: Accessible.RadioButton
                    Accessible.name: modelData[1]
                    Accessible.checked: chosen
                    Accessible.onPressAction: segments.picked(modelData[0])
                }
            }
        }
    }

    component SliderRow: Item {
        id: sliderRow
        property var tone
        property string title
        property real from: 0
        property real to: 100
        property real value: 0
        property bool divider: true
        signal moved(real value)
        signal held(bool down)
        Layout.fillWidth: true
        implicitHeight: 54
        Rectangle {
            visible: sliderRow.divider
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.leftMargin: 18
            anchors.rightMargin: 18
            height: 1
            color: sliderRow.tone.line
        }
        RowLayout {
            anchors.fill: parent
            anchors.leftMargin: 18
            anchors.rightMargin: 18
            spacing: 16
            // Room for the longer words other languages use ("Zeigergeschwindigkeit"), up to a point.
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.preferredWidth: Math.min(Math.max(120, implicitWidth), 190)
                elide: Text.ElideRight
                text: sliderRow.title
                color: sliderRow.tone.ink
                font.pixelSize: 14
                font.weight: Font.DemiBold
            }
            Slide {
                tone: sliderRow.tone
                Layout.fillWidth: true
                from: sliderRow.from
                to: sliderRow.to
                stepSize: 1
                value: sliderRow.value
                Accessible.name: sliderRow.title
                onPressedChanged: sliderRow.held(pressed)
                onMoved: sliderRow.moved(value)
            }
        }
    }

    // A slider: a lily track and a white stone.
    component Slide: T.Slider {
        id: slide
        property var tone
        implicitWidth: 200
        implicitHeight: 28
        background: Rectangle {
            x: slide.leftPadding
            y: slide.topPadding + (slide.availableHeight - height) / 2
            width: slide.availableWidth
            height: 4
            radius: 2
            color: slide.tone.wash2
            Rectangle {
                width: slide.visualPosition * parent.width
                height: parent.height
                radius: 2
                color: slide.tone.lily
            }
        }
        handle: Rectangle {
            x: slide.leftPadding + slide.visualPosition * (slide.availableWidth - width)
            y: slide.topPadding + (slide.availableHeight - height) / 2
            width: 20
            height: 20
            radius: 10
            color: "#FFFFFF"
            border.width: slide.visualFocus ? 2 : 1
            border.color: slide.visualFocus ? slide.tone.lily : Qt.rgba(0, 0, 0, 0.18)
            scale: slide.pressed ? 1.1 : 1
            Behavior on scale { NumberAnimation { duration: Math.round(120 * slide.tone.speed) } }
        }
    }

    // A list's scroll bar: a thin stroke that shows while it's used.
    component Rail: T.ScrollBar {
        id: rail
        property var tone
        implicitWidth: 10
        padding: 2
        contentItem: Rectangle {
            implicitWidth: 6
            radius: 3
            color: rail.tone.dim
            opacity: rail.policy === T.ScrollBar.AlwaysOn || rail.active ? 0.55 : 0
            Behavior on opacity { NumberAnimation { duration: Math.round(200 * rail.tone.speed) } }
        }
    }

    // Still working, with no number to show: a short lily stroke going along.
    component Busy: T.ProgressBar {
        id: meter
        property var tone
        implicitWidth: 200
        implicitHeight: 4
        background: Rectangle {
            radius: 2
            color: meter.tone.wash2
        }
        contentItem: Item {
            clip: true
            Rectangle {
                id: stroke
                width: parent.width * 0.3
                height: parent.height
                radius: 2
                color: meter.tone.lily
                NumberAnimation on x {
                    running: meter.visible
                    loops: Animation.Infinite
                    from: -stroke.width
                    to: meter.width
                    duration: 1400
                }
            }
        }
    }

    // A well to type in, like Wi-Fi's password.
    component Field: Rectangle {
        id: field
        property var tone
        property alias text: input.text
        property string hint
        property bool secret
        signal accepted()
        function focusInput() {
            input.forceActiveFocus()
        }
        Layout.fillWidth: true
        Layout.preferredHeight: 38
        radius: 12
        color: tone.dark ? Qt.rgba(0, 0, 0, 0.28) : Qt.rgba(1, 1, 1, 0.9)
        border.width: input.activeFocus ? 2 : 1
        border.color: input.activeFocus ? tone.lily : tone.line
        TextInput {
            id: input
            anchors.fill: parent
            anchors.leftMargin: 12
            anchors.rightMargin: 12
            verticalAlignment: TextInput.AlignVCenter
            echoMode: field.secret ? TextInput.Password : TextInput.Normal
            color: field.tone.ink
            font.pixelSize: 14
            clip: true
            selectByMouse: true
            selectionColor: field.tone.lily
            Accessible.role: Accessible.EditableText
            Accessible.name: field.hint
            onAccepted: field.accepted()
            Text {
                horizontalAlignment: Text.AlignLeft
                anchors.fill: parent
                verticalAlignment: Text.AlignVCenter
                visible: input.text === ""
                text: field.hint
                color: field.tone.dim
                font.pixelSize: 14
            }
        }
    }

    // Someone's picture, or their initial on a glaze.
    component Face: Item {
        id: face
        property string name
        property string picture
        property var glaze: ["#4DB4A0", "#245A50"]
        Rounded {
            anchors.fill: parent
            radius: width / 2
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0; color: face.glaze[0] }
                    GradientStop { position: 1; color: face.glaze[1] }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: -1
                    text: face.name.charAt(0).toUpperCase()
                    color: "#FBF7EE"
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: Math.round(face.height * 0.46)
                }
            }
            Image {
                anchors.fill: parent
                source: face.picture !== "" ? "file://" + encodeURI(face.picture) : ""
                sourceSize: Qt.size(face.width * 2, face.height * 2)
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                cache: false
                visible: status === Image.Ready
            }
        }
        Accessible.role: Accessible.Graphic
        Accessible.name: name
    }

    // The game covers on Play on Windows.
    component Cover: Item {
        id: cover
        property string name
        property string artwork
        property var glaze: ["#5C88D0", "#1B2546"]
        property bool here: false
        signal picked()
        implicitHeight: width * 215 / 460
        scale: tap.pressed ? 0.97 : hover.hovered ? 1.03 : 1
        Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
        Rounded {
            anchors.fill: parent
            radius: 10
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    orientation: Gradient.Horizontal
                    GradientStop { position: 0; color: cover.glaze[0] }
                    GradientStop { position: 1; color: cover.glaze[1] }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    anchors.fill: parent
                    anchors.margins: 10
                    verticalAlignment: Text.AlignBottom
                    text: cover.name
                    color: "#FFFFFF"
                    elide: Text.ElideRight
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: Math.max(12, Math.round(parent.height * 0.17))
                }
            }
            Image {
                anchors.fill: parent
                source: cover.artwork
                fillMode: Image.PreserveAspectCrop
                asynchronous: true
                visible: status === Image.Ready
            }
            // A pebble on the corner: this one plays in Monet too.
            Rectangle {
                visible: cover.here
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.margins: 6
                width: hereText.implicitWidth + 14
                height: 20
                radius: 10
                color: Qt.rgba(0.11, 0.106, 0.098, 0.72)
                Text {
                    id: hereText
                    anchors.centerIn: parent
                    text: i18n("Plays here too")
                    color: "#FFFFFF"
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                }
            }
        }
        HoverHandler { id: hover }
        TapHandler {
            id: tap
            onTapped: cover.picked()
        }
        Accessible.role: Accessible.Button
        Accessible.name: i18n("Play %1", name)
        Accessible.onPressAction: cover.picked()
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
                        Glyph {
                            Layout.preferredWidth: 15
                            Layout.preferredHeight: 15
                            path: "M10.5 5.5a5 5 0 1 0 0.01 0M14.2 14.2L19 19"
                            color: look.dim
                        }
                        TextInput {
                            id: search
                            objectName: "settingsSearch"
                            Layout.fillWidth: true
                            maximumLength: 256
                            color: look.ink
                            font.pixelSize: 14
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
                    Shared.MouseScroll { view: navList }
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentHeight: navColumn.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    interactive: contentHeight > height
                    // On a laptop's screen not every page fits: a scrollbar says there are more,
                    // and the page that opens (from a notification, say) is scrolled into view.
                    T.ScrollBar.vertical: Rail { id: navScroll; tone: look }

                    function reveal() {
                        const shown = pebble.target
                        if (shown && (shown.y < contentY || shown.y + shown.height > contentY + height)) {
                            contentY = Math.max(0, Math.min(shown.y - (height - shown.height) / 2, contentHeight - height))
                        }
                    }

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
                                        color: look.ink; font.pixelSize: 13; font.weight: Font.DemiBold
                                        wrapMode: Text.Wrap; textFormat: Text.PlainText
                                    }
                                    Text {
                                        width: parent.width; text: suggestion.modelData.detail
                                        color: look.dim; font.pixelSize: 11
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
                            color: look.dim; font.pixelSize: 12; wrapMode: Text.Wrap
                            Accessible.role: Accessible.StaticText
                        }
                        Pill {
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
                                readonly property bool current: sheet.page === modelData.id
                                Layout.fillWidth: true
                                Layout.preferredHeight: visible ? 32 : 0
                                // A little air between Monet's pages, KDE's, and Windows'.
                                Layout.topMargin: modelData.gap ? 10 : 0
                                visible: side.matches(modelData)
                                radius: 12
                                color: navHover.hovered && !current ? (look.dark ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.3)) : "transparent"
                                Behavior on color { ColorAnimation { duration: Math.round(140 * sheet.speed) } }
                                border.width: activeFocus ? 2 : 0
                                border.color: look.lily
                                activeFocusOnTab: true
                                Keys.onSpacePressed: sheet.go(modelData)
                                Keys.onReturnPressed: sheet.go(modelData)

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
                                        Glyph {
                                            anchors.centerIn: parent
                                            anchors.verticalCenterOffset: 1
                                            width: 15
                                            height: 15
                                            path: modelData.glyph
                                            filled: modelData.filled === true
                                            color: Qt.rgba(0, 0, 0, 0.3)
                                        }
                                        Glyph {
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
                                        font.pixelSize: 14
                                        font.weight: navItem.current ? Font.DemiBold : Font.Normal
                                        elide: Text.ElideRight
                                    }
                                    // Opens in KDE's settings, not here.
                                    Glyph {
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
                            font.pixelSize: 13
                            wrapMode: Text.Wrap
                        }
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 34
                    radius: 10
                    color: kdeHover.hovered ? (look.dark ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.3)) : "transparent"
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        anchors.left: parent.left
                        anchors.leftMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        text: i18n("More settings ›")
                        color: look.ink
                        opacity: 0.78
                        font.pixelSize: 13
                        font.weight: Font.Medium
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
                anchors.fill: parent
                anchors.topMargin: 2
                anchors.bottomMargin: sheet.page === "notifications" ? notificationFeedback.height + 12 : 2
                clip: true
                contentWidth: width
                contentHeight: pageLoader.height + 60
                boundsBehavior: Flickable.StopAtBounds
                function revealFocus() {
                    const item = sheet.activeFocusItem
                    let ancestor = item
                    while (ancestor && ancestor !== scroller.contentItem) ancestor = ancestor.parent
                    if (!item || !ancestor) return
                    const top = item.mapToItem(scroller.contentItem, 0, 0).y
                    if (top < contentY + 12) contentY = Math.max(0, top - 12)
                    else if (top + item.height > contentY + height - 12)
                        contentY = Math.min(Math.max(0, contentHeight - height), top + item.height - height + 12)
                }
                onHeightChanged: Qt.callLater(revealFocus)
                Connections {
                    target: sheet
                    function onActiveFocusItemChanged() { Qt.callLater(scroller.revealFocus) }
                }
                // A wheel's turn glides, as in the Store and Games.
                Kirigami.WheelHandler {
                    target: scroller
                    filterMouseEvents: !("acceptedButtons" in scroller)
                    keyNavigationEnabled: true
                    verticalStepSize: 96
                }
                T.ScrollBar.vertical: Rail { tone: look }

                Loader {
                    id: pageLoader
                    x: 34
                    y: 28
                    width: scroller.width - 68
                    property real shift: 0
                    transform: Translate { y: pageLoader.shift }
                    sourceComponent: ({
                        light: lightPage, wifi: wifiPage, bluetooth: bluetoothPage, phone: phonePage, display: displayPage,
                        sound: soundPage, datetime: datetimePage, users: usersPage, input: inputPage,
                        power: powerPage, notifications: notificationsPage, accessibility: accessibilityPage, apps: appsPage,
                        storage: storagePage, backups: backupsPage, games: gamesPage, windows: windowsPage, privacy: privacyPage,
                        security: securityPage,
                        printers: printersPage, welcome: welcomePage,
                        updates: updatesPage, about: aboutPage
                    })[sheet.page]
                    onLoaded: {
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
                        font.pixelSize: 13
                        wrapMode: Text.Wrap
                        Accessible.role: sheet.notifyFailed ? Accessible.AlertMessage : Accessible.StaticText
                        Accessible.name: text
                    }
                    Pill {
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
            running: sheet.visible && sheet.photoInfo.state === "painting"
            onTriggered: sheet.ask("paint-state", out => {
                const was = sheet.photoInfo.state
                sheet.photoInfo = sheet.json(out, sheet.photoInfo)
                if (was === "painting" && sheet.photoInfo.state === "ready")
                    sheet.ask("prefs", more => sheet.prefs = sheet.json(more, sheet.prefs))
            })
        }

        Timer {
            interval: 4000
            repeat: true
            running: sheet.visible
            onTriggered: {
                sheet.refresh()
                if (sheet.page === "bluetooth" && sheet.busyDevice === "") {
                    sheet.ask("bt-list", out => sheet.devices = sheet.json(out, sheet.devices))
                }
                if (sheet.page === "notifications") sheet.loadNotifications()
                // Networks come and go (and are slow to show after waking): look again, but never
                // while a password is being typed, which a new list would wipe.
                if (sheet.page === "wifi" && sheet.joining === "") {
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
            readonly property color dim: dark ? Qt.rgba(0.945, 0.933, 0.91, 0.62) : Qt.rgba(0.11, 0.106, 0.098, 0.6)
            readonly property color wash: dark ? Qt.rgba(1, 1, 1, 0.05) : Qt.rgba(0.11, 0.106, 0.098, 0.035)
            readonly property color wash2: dark ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(0.11, 0.106, 0.098, 0.07)
            readonly property color press: dark ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(0.11, 0.106, 0.098, 0.11)
            readonly property color line: dark ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(0.11, 0.106, 0.098, 0.08)
            readonly property color paper: dark ? Qt.rgba(0.122, 0.118, 0.11, 0.94) : Qt.rgba(0.984, 0.98, 0.969, 0.95)
            readonly property color lily: dark ? "#4DB4A0" : "#357F72"
            readonly property real speed: sheet.speed
        }

        // Pages -----------------------------------------------------------------
        // The first sign-in: what's worth knowing, each with the way there. Not in the list of
        // pages; monet-session opens it once, for a new account.
        Component {
            id: welcomePage
            ColumnLayout {
                spacing: 20
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        text: i18n("Welcome to Monet")
                        color: look.ink
                        font.family: "Fraunces 72pt SuperSoft"
                        font.weight: Font.Light
                        font.pixelSize: 36
                        elide: Text.ElideRight
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        text: i18n("A few things worth knowing, then it's yours.")
                        color: look.dim
                        font.pixelSize: 15
                        wrapMode: Text.Wrap
                    }
                }
                Card {
                    tone: look
                    Repeater {
                        // glyph, title, what it is, the way there (a page, or the widget gallery), its button
                        model: [
                            ["M4 7h10M18 7h2M4 17h4M12 17h8M16 4v6M10 14v6", i18n("Quick Settings, at the right of the bar"),
                             i18n("Wi-Fi, sound, brightness and the light, a click away. The arrow on a tile opens its page here."), "", ""],
                            ["M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z", i18n("Widgets on your desktop"),
                             i18n("Weather, a calendar with notes, your batteries, clocks around the world and more."), "widgets",
                             i18n("Edit widgets")],
                            ["M9 6.5L18 12l-9 5.5z", i18n("Play on Windows"),
                             i18n("Games that need Windows are a restart away, and you come back here after."), "windows",
                             i18n("See your games")],
                            [sheet.entry("light").glyph || "", i18n("Make it yours"),
                             i18n("Choose the light and the painting, and how big things are on the screen."), "light",
                             i18n("Light & Wallpaper")],
                            ["M10 4a6 6 0 1 0 0 12a6 6 0 1 0 0-12M15 15l5 5", i18n("Find any setting"),
                             i18n("Type what you're looking for in the search at the top left, in your own words."), "", ""]
                        ]
                        SettingRow {
                            required property var modelData
                            required property int index
                            tone: look
                            divider: index > 0
                            title: modelData[1]
                            detail: modelData[2]
                            lead: Glyph {
                                width: 20
                                height: 20
                                path: modelData[0]
                                filled: modelData[3] === "windows"
                                color: look.ink
                            }
                            Pill {
                                tone: look
                                visible: modelData[4] !== ""
                                text: modelData[4]
                                onClicked: modelData[3] === "widgets" ? sheet.ask("widgets") : sheet.page = modelData[3]
                            }
                        }
                    }
                }
                Pill {
                    tone: look
                    kind: "lily"
                    Layout.alignment: Qt.AlignRight
                    text: i18n("Start using Monet")
                    onClicked: sheet.close()
                }
            }
        }

        Component {
            id: lightPage
            ColumnLayout {
                spacing: 20
                PageTitle {
                    tone: look
                    entry: sheet.entry("light")
                    art: sheet.art
                    text: i18n("Light & Wallpaper")
                    detail: i18n("How Monet looks, and when it changes.")
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    Repeater {
                        model: [
                            ["hours", i18n("Follow the hours"), i18n("Mist by day, smoke after dark")],
                            // The colors stay; the painting can still follow the day (Through the day).
                            ["mist", i18n("Mist"), i18n("Light colors all day")],
                            ["smoke", i18n("Smoke"), i18n("Dark colors all day")]
                        ]
                        Rectangle {
                            id: choice
                            readonly property bool picked: (sheet.info.light || "hours") === modelData[0]
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            implicitHeight: choiceColumn.implicitHeight + 20
                            radius: 18
                            color: picked ? Qt.rgba(0.302, 0.706, 0.627, 0.1) : choiceHover.hovered ? look.wash2 : look.wash
                            border.width: picked || activeFocus ? 2 : 1
                            border.color: picked || activeFocus ? look.lily : look.line
                            scale: choiceTap.pressed ? 0.98 : 1
                            activeFocusOnTab: true
                            Keys.onSpacePressed: sheet.chooseLight(modelData[0])
                            Behavior on scale { NumberAnimation { duration: Math.round(160 * sheet.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
                            Behavior on color { ColorAnimation { duration: Math.round(160 * sheet.speed) } }
                            ColumnLayout {
                                id: choiceColumn
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 10
                                spacing: 3
                                Image {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: Math.round(width * 236 / 480)
                                    Layout.bottomMargin: 7
                                    source: sheet.art + "light-" + modelData[0] + ".png"
                                    smooth: true
                                    mipmap: true
                                }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    Layout.leftMargin: 4
                                    text: modelData[1]
                                    color: look.ink
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    Layout.leftMargin: 4
                                    text: modelData[2]
                                    color: look.dim
                                    font.pixelSize: 13
                                    elide: Text.ElideRight
                                }
                            }
                            HoverHandler { id: choiceHover }
                            TapHandler {
                                id: choiceTap
                                onTapped: sheet.chooseLight(modelData[0])
                            }
                            Accessible.role: Accessible.RadioButton
                            Accessible.name: modelData[1]
                            Accessible.checked: picked
                            Accessible.onPressAction: sheet.chooseLight(modelData[0])
                        }
                    }
                }
                // The painting on the wall: one of Monet's series, each in the same four lights.
                Caption {
                    tone: look
                    text: i18n("Painting")
                }
                // Three to a row, like paintings on a gallery wall.
                GridLayout {
                    Layout.fillWidth: true
                    columns: 3
                    columnSpacing: 12
                    rowSpacing: 12
                    Repeater {
                        model: [
                            ["hours", i18n("The Hours"), i18n("The harbor at Le Havre")],
                            ["lilies", i18n("Water Lilies"), i18n("The pond at Giverny")],
                            ["haystacks", i18n("Haystacks"), i18n("A field after the harvest")],
                            ["magpie", i18n("The Magpie"), i18n("A farm under snow")],
                            ["seasons", i18n("Through the year"), i18n("Each season its painting")],
                            ["photo", i18n("Your photo"), i18n("A photo of yours, painted")]
                        ]
                        Rectangle {
                            id: seriesChoice
                            readonly property bool picked: (sheet.prefs.series || "hours") === modelData[0]
                            Layout.fillWidth: true
                            Layout.fillHeight: true
                            Layout.preferredWidth: 1
                            implicitHeight: seriesColumn.implicitHeight + 20
                            radius: 18
                            color: picked ? Qt.rgba(0.302, 0.706, 0.627, 0.1) : seriesHover.hovered ? look.wash2 : look.wash
                            border.width: picked || activeFocus ? 2 : 1
                            border.color: picked || activeFocus ? look.lily : look.line
                            scale: seriesTap.pressed ? 0.98 : 1
                            activeFocusOnTab: true
                            Keys.onSpacePressed: sheet.chooseSeries(modelData[0])
                            Behavior on scale { NumberAnimation { duration: Math.round(160 * sheet.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
                            Behavior on color { ColorAnimation { duration: Math.round(160 * sheet.speed) } }
                            ColumnLayout {
                                id: seriesColumn
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 10
                                spacing: 3
                                Image {
                                    id: seriesArt
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: Math.round(width * 236 / 480)
                                    Layout.bottomMargin: 7
                                    source: modelData[0] !== "photo" ? sheet.art + "series-" + modelData[0] + ".png"
                                        : sheet.photoInfo.preview || ""
                                    smooth: true
                                    mipmap: true
                                    // No photo painted yet (or one on the way): an empty frame to fill.
                                    Rectangle {
                                        anchors.fill: parent
                                        visible: modelData[0] === "photo" && (seriesArt.status !== Image.Ready || sheet.photoInfo.state === "painting")
                                        radius: 12
                                        color: look.wash2
                                        border.width: 1
                                        border.color: look.line
                                        Column {
                                            anchors.centerIn: parent
                                            spacing: 6
                                            Kirigami.Icon {
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                width: 28
                                                height: 28
                                                source: "folder-pictures"
                                                opacity: 0.8
                                            }
                                            Text {
                                                anchors.horizontalCenter: parent.horizontalCenter
                                                text: sheet.photoInfo.state === "painting"
                                                    ? i18n("Painting… %1%", sheet.photoInfo.percent || 0) : i18n("Choose a photo…")
                                                color: look.dim
                                                font.pixelSize: 12
                                            }
                                        }
                                    }
                                }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    Layout.leftMargin: 4
                                    text: modelData[1]
                                    color: look.ink
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    Layout.leftMargin: 4
                                    text: modelData[2]
                                    color: look.dim
                                    font.pixelSize: 13
                                    // Four side by side: room for two lines rather than cutting the words off.
                                    wrapMode: Text.WordWrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                }
                            }
                            HoverHandler { id: seriesHover }
                            TapHandler {
                                id: seriesTap
                                onTapped: sheet.chooseSeries(modelData[0])
                            }
                            Accessible.role: Accessible.RadioButton
                            Accessible.name: modelData[1]
                            Accessible.checked: picked
                            Accessible.onPressAction: sheet.chooseSeries(modelData[0])
                        }
                    }
                }
                Card {
                    tone: look
                    visible: sheet.photoInfo.state !== "" || sheet.photoInfo.failed === true
                    SettingRow {
                        tone: look
                        divider: false
                        title: i18n("Your photo")
                        detail: sheet.photoInfo.state === "painting"
                            ? i18n("Monet is painting it in the four lights: %1%. It goes on the wall by itself when it's done.", sheet.photoInfo.percent || 0)
                            : sheet.photoInfo.failed === true ? i18n("That picture couldn't be painted. Try a JPEG or PNG photo.")
                            : i18n("Painted in Monet's hand, in the same four lights as The Hours.")
                        Pill {
                            tone: look
                            enabledPill: sheet.photoInfo.state !== "painting"
                            text: sheet.photoInfo.state === "ready" ? i18n("Another photo…") : i18n("Choose a photo…")
                            onClicked: photoPicker.open()
                        }
                    }
                }
                Card {
                    tone: look
                    Repeater {
                        model: [
                            ["hours", i18n("Through the day"), i18n("The painting's light follows the sun where you are, from dawn to night")],
                            ["weather", i18n("Weather"), i18n("Rain, fog and snow where you are soften the painting with mist")],
                            ["placard", i18n("Placard"), i18n("The time and the painting's name on the desktop")],
                            ["dodge", i18n("Bar steps aside"), i18n("The bar slides away when a window comes over it, and back when you point at the bottom of the screen")],
                            ["snap", i18n("Snap layouts"), i18n("Drag a window to the top of the screen for its layouts, and Snap Assist fills the rest. Off, an edge still gives it half the screen and the top all of it")]
                        ]
                        SettingRow {
                            tone: look
                            divider: index > 0
                            tappable: true
                            title: modelData[1]
                            detail: modelData[2]
                            onTapped: sheet.pref(modelData[0])
                            Switch {
                                tone: look
                                active: sheet.prefs[modelData[0]] !== false
                            }
                        }
                    }
                    // How see-through panels, windows and widgets are: four steps from none to clear.
                    Item {
                        id: glassRow
                        readonly property var levels: ["solid", "matte", "frosted", "clear"]
                        readonly property var names: [i18nc("how see-through Monet's glass is", "Solid"), i18nc("how see-through Monet's glass is", "Matte"), i18nc("how see-through Monet's glass is", "Frosted"), i18nc("how see-through Monet's glass is", "Clear")]
                        readonly property int step: Math.max(0, levels.indexOf(sheet.prefs.glass))
                        Layout.fillWidth: true
                        implicitHeight: glassColumn.implicitHeight + 32
                        Rectangle {
                            anchors.top: parent.top
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: 18
                            anchors.rightMargin: 18
                            height: 1
                            color: look.line
                        }
                        ColumnLayout {
                            id: glassColumn
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.leftMargin: 18
                            anchors.rightMargin: 18
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 3
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: i18n("Glass")
                                color: look.ink
                                font.pixelSize: 14
                                font.weight: Font.DemiBold
                            }
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: [i18n("No glass: panels, windows and widgets on paper. Lighter on older PCs."),
                                       i18n("Matte glass: the painting's color comes through, its strokes don't. Calm, and easy to read."),
                                       i18n("Frosted glass: the painting's light and color, softened."),
                                       i18n("Clear glass: the painting shows through panels, windows and widgets.")][glassRow.step]
                                color: look.dim
                                font.pixelSize: 13
                                wrapMode: Text.Wrap
                            }
                            Slide {
                                id: glassSlider
                                tone: look
                                Layout.fillWidth: true
                                Layout.topMargin: 8
                                from: 0
                                to: 3
                                stepSize: 1
                                snapMode: T.Slider.SnapAlways
                                value: glassRow.step
                                Accessible.name: i18n("Glass")
                                Accessible.description: glassRow.names[glassRow.step]
                                // Dressing the desktop takes a moment: once it's let go, not at every step dragged past.
                                onPressedChanged: if (!pressed) sheet.chooseGlass(glassRow.levels[Math.round(value)])
                                onMoved: if (!pressed) sheet.chooseGlass(glassRow.levels[Math.round(value)])
                            }
                            // Each step's name under its place on the slider.
                            Item {
                                Layout.fillWidth: true
                                implicitHeight: 18
                                Repeater {
                                    model: glassRow.names
                                    Text {
                                        readonly property real at: glassSlider.leftPadding + glassSlider.handle.width / 2
                                            + (glassSlider.availableWidth - glassSlider.handle.width) * index / 3
                                        x: Math.max(0, Math.min(parent.width - width, at - width / 2))
                                        text: modelData
                                        color: index === glassRow.step ? look.ink : look.dim
                                        font.pixelSize: 12
                                        font.weight: index === glassRow.step ? Font.DemiBold : Font.Normal
                                        TapHandler {
                                            onTapped: sheet.chooseGlass(glassRow.levels[index])
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                // The widget gallery, also from here: Settings steps aside for the desktop.
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        tappable: true
                        title: i18n("Widgets")
                        detail: i18n("Add, move or take away the cards on your desktop")
                        onTapped: sheet.ask("widgets")
                        Pill {
                            tone: look
                            kind: "lily"
                            text: i18n("Edit widgets")
                            onClicked: sheet.ask("widgets")
                        }
                    }
                }
                // The way back when More settings changed how Monet looks (KDE's theme buttons once
                // took its app style away): its colors, styles, frames and painting again, for this
                // account, no restart. Files, apps and the bar's islands stay.
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        title: i18n("Monet's look")
                        detail: sheet.restoring ? i18n("Putting it back…")
                            : sheet.restored ? i18n("Monet's look has been put back. Your files, apps and bar are unchanged.")
                            : sheet.restoreFailed ? i18n("Monet's look couldn't be fully put back. Try again.")
                            : i18n("Something in More settings changed how Monet looks? Its colors, styles, window frames and painting come back. Your files, apps and bar stay.")
                        Pill {
                            objectName: "restoreLookButton"
                            tone: look
                            kind: sheet.restored ? "lily" : "plain"
                            text: sheet.restoring ? i18n("Putting it back…")
                                : sheet.restored ? i18n("Put back again")
                                : sheet.restoreFailed ? i18n("Try again") : i18nc("Monet's look, as it was", "Put back")
                            enabledPill: !sheet.restoring
                            onClicked: sheet.restoreLook()
                        }
                    }
                }
            }
        }

        Component {
            id: wifiPage
            ColumnLayout {
                spacing: 20
                PageTitle {
                    tone: look
                    entry: sheet.entry("wifi")
                    art: sheet.art
                    text: i18n("Wi-Fi")
                    detail: sheet.info.wifi === true
                        ? ((sheet.info.network || "") !== "" ? i18n("Connected to %1", sheet.info.network) : i18n("Not connected"))
                        : sheet.info.wifi === false ? i18n("Off") : ""
                }
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        tappable: typeof sheet.info.wifi === "boolean"
                        title: i18n("Wi-Fi")
                        detail: typeof sheet.info.wifi === "boolean" ? "" : i18n("This PC has no Wi-Fi")
                        onTapped: sheet.flip("wifi", "wifi")
                        Switch {
                            tone: look
                            visible: typeof sheet.info.wifi === "boolean"
                            active: sheet.info.wifi === true
                        }
                    }
                }
                Card {
                    tone: look
                    visible: sheet.info.wifi === true && (sheet.info.network || "") !== ""
                    SettingRow {
                        tone: look
                        divider: false
                        title: sheet.info.network || ""
                        detail: i18n("Connected")
                        lead: Check {
                            tone: look
                            active: true
                        }
                    }
                }
                Caption {
                    tone: look
                    visible: sheet.info.wifi === true
                    text: (sheet.info.network || "") !== "" ? i18n("Other networks") : i18n("Networks")
                }
                Card {
                    tone: look
                    visible: sheet.info.wifi === true
                    SettingRow {
                        tone: look
                        divider: false
                        visible: sheet.nets.filter(n => !n.active).length === 0
                        strong: false
                        title: sheet.netsLoaded ? i18n("No other networks nearby") : i18n("Looking for networks…")
                    }
                    Repeater {
                        model: sheet.nets.filter(n => !n.active)
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 0
                            SettingRow {
                                tone: look
                                divider: index > 0
                                tappable: true
                                strong: false
                                title: modelData.name
                                detail: sheet.joining === modelData.name && sheet.joinState === "failed" && !modelData.secure
                                    ? i18n("Couldn't join") : ""
                                lead: Bars {
                                    tone: look
                                    level: modelData.signal > 66 ? 3 : modelData.signal > 33 ? 2 : 1
                                }
                                onTapped: {
                                    sheet.joinState = ""
                                    if (modelData.enterprise && !modelData.known) {
                                        // A work or school network wants a name as well: KDE's page asks for both.
                                        sheet.ask("kde wifi")
                                    } else if (modelData.secure && !modelData.known) {
                                        sheet.joining = sheet.joining === modelData.name ? "" : modelData.name
                                    } else {
                                        // Open, or known: straight in (a known one that fails asks for its password).
                                        sheet.joining = modelData.name
                                        sheet.join(modelData.name, "")
                                    }
                                }
                                Row {
                                    readonly property bool busy: sheet.joining === modelData.name && sheet.joinState === "joining"
                                    spacing: 6
                                    Text {
                                        horizontalAlignment: Text.AlignLeft
                                        visible: parent.busy
                                        text: i18n("Joining…")
                                        color: look.dim
                                        font.pixelSize: 13
                                    }
                                    // A lock for networks that ask for a password.
                                    Glyph {
                                        visible: modelData.secure && !parent.busy
                                        width: 15
                                        height: 15
                                        path: "M7.5 11V8a4.5 4.5 0 0 1 9 0v3M6 11h12v9H6z"
                                        color: look.dim
                                    }
                                    Accessible.role: Accessible.StaticText
                                    Accessible.name: modelData.secure ? i18n("Secured") : i18n("Open")
                                }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                Layout.leftMargin: 18
                                Layout.rightMargin: 18
                                Layout.bottomMargin: 14
                                visible: sheet.joining === modelData.name && modelData.secure
                                spacing: 8
                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 38
                                    radius: 12
                                    color: look.dark ? Qt.rgba(0, 0, 0, 0.28) : Qt.rgba(1, 1, 1, 0.9)
                                    border.width: password.activeFocus ? 2 : 1
                                    border.color: password.activeFocus ? look.lily : look.line
                                    TextInput {
                                        id: password
                                        anchors.fill: parent
                                        anchors.leftMargin: 12
                                        anchors.rightMargin: 12
                                        verticalAlignment: TextInput.AlignVCenter
                                        echoMode: TextInput.Password
                                        color: look.ink
                                        font.pixelSize: 14
                                        clip: true
                                        Accessible.role: Accessible.EditableText
                                        Accessible.name: i18n("Password for %1", modelData.name)
                                        onVisibleChanged: if (visible) forceActiveFocus()
                                        onAccepted: sheet.join(modelData.name, text)
                                        Text {
                                            horizontalAlignment: Text.AlignLeft
                                            anchors.fill: parent
                                            verticalAlignment: Text.AlignVCenter
                                            visible: password.text === ""
                                            text: sheet.joinState === "failed" ? i18n("That didn't work. Check the password.") : i18n("Password")
                                            color: sheet.joinState === "failed" ? "#E0603A" : look.dim
                                            font.pixelSize: 14
                                        }
                                    }
                                }
                                Pill {
                                    tone: look
                                    text: i18n("Cancel")
                                    onClicked: sheet.joining = ""
                                }
                                Pill {
                                    tone: look
                                    kind: "lily"
                                    text: sheet.joinState === "joining" ? i18n("Joining…") : i18n("Join")
                                    enabledPill: sheet.joinState !== "joining"
                                    onClicked: sheet.join(modelData.name, password.text)
                                }
                            }
                        }
                    }
                }
                // A hotspot: this PC's own Wi-Fi network, so a phone or tablet can use its internet.
                Card {
                    tone: look
                    visible: sheet.hotspot.on === true || sheet.hotspot.possible === true
                    SettingRow {
                        tone: look
                        divider: false
                        tappable: sheet.hotspotState !== "starting"
                        title: i18n("Hotspot")
                        detail: sheet.hotspotState === "starting" ? i18n("Starting…")
                            : sheet.hotspotState === "failed" ? i18n("This Wi-Fi can't share. Wired internet shares best.")
                            : sheet.hotspot.on === true ? i18n("Join %1 with the password %2", sheet.hotspot.name, sheet.hotspot.password)
                            : i18n("Lets a phone or tablet use this PC's internet")
                        onTapped: {
                            const on = sheet.hotspot.on !== true
                            sheet.hotspotState = on ? "starting" : ""
                            sheet.ask(on ? "hotspot-on" : "hotspot-off", out => {
                                const state = sheet.json(out, { on: false })
                                sheet.hotspot = state
                                sheet.hotspotState = on && !state.on ? "failed" : ""
                            })
                        }
                        Switch {
                            tone: look
                            active: sheet.hotspot.on === true
                        }
                    }
                }
                Pill {
                    tone: look
                    text: i18n("More Wi-Fi settings…")
                    onClicked: sheet.ask("kde wifi")
                }
            }
        }

        Component {
            id: bluetoothPage
            ColumnLayout {
                spacing: 20
                PageTitle {
                    readonly property int connected: sheet.devices.filter(d => d.connected).length
                    tone: look
                    entry: sheet.entry("bluetooth")
                    art: sheet.art
                    text: i18n("Bluetooth")
                    detail: sheet.info.bluetooth === true
                        ? (connected > 0 ? i18np("%1 device connected", "%1 devices connected", connected) : i18n("On"))
                        : sheet.info.bluetooth === false ? i18n("Off") : ""
                }
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        tappable: typeof sheet.info.bluetooth === "boolean"
                        title: i18n("Bluetooth")
                        detail: typeof sheet.info.bluetooth === "boolean" ? "" : i18n("This PC has no Bluetooth")
                        onTapped: sheet.flip("bluetooth", "bluetooth")
                        Switch {
                            tone: look
                            visible: typeof sheet.info.bluetooth === "boolean"
                            active: sheet.info.bluetooth === true
                        }
                    }
                }
                Card {
                    tone: look
                    visible: sheet.info.bluetooth === true
                    SettingRow {
                        tone: look
                        divider: false
                        visible: sheet.devices.length === 0
                        strong: false
                        title: i18n("No devices yet")
                        detail: i18n("Pair headphones, a controller or a mouse to see them here.")
                    }
                    Repeater {
                        model: sheet.devices
                        SettingRow {
                            tone: look
                            divider: index > 0
                            title: modelData.name
                            detail: modelData.connected ? i18n("Connected") : i18n("Not connected")
                            // What it is, in a lily chip while it's connected (like Quick Settings).
                            lead: Rectangle {
                                width: 34
                                height: 34
                                radius: 17
                                color: modelData.connected ? look.lily : look.wash2
                                Behavior on color { ColorAnimation { duration: Math.round(180 * look.speed) } }
                                Glyph {
                                    anchors.centerIn: parent
                                    width: 18
                                    height: 18
                                    path: sheet.deviceGlyph(modelData.icon || "")
                                    color: modelData.connected ? "#FFFFFF" : look.ink
                                }
                            }
                            Pill {
                                tone: look
                                text: sheet.busyDevice === modelData.address ? (modelData.connected ? i18n("Disconnecting…") : i18n("Connecting…"))
                                    : modelData.connected ? i18n("Disconnect") : i18n("Connect")
                                enabledPill: sheet.busyDevice === ""
                                onClicked: sheet.connectDevice(modelData)
                            }
                        }
                    }
                }
                Pill {
                    tone: look
                    visible: sheet.info.bluetooth === true
                    text: i18n("Pair a new device…")
                    onClicked: sheet.ask("kde bluetooth")
                }
            }
        }

        Component {
            id: phonePage
            ColumnLayout {
                id: phoneColumn
                spacing: 20
                readonly property var paired: sheet.phoneList.filter(p => p.paired)
                readonly property var near: sheet.phoneList.filter(p => !p.paired && p.near)
                PageTitle {
                    tone: look
                    entry: sheet.entry("phone")
                    art: sheet.art
                    text: i18n("Phone")
                    detail: i18n("Texts, notifications and files between your phone and this PC.")
                }
                // Phones come and go as they join the Wi-Fi, and a pairing is answered on the phone.
                Timer {
                    interval: 4000
                    repeat: true
                    running: sheet.page === "phone" && sheet.visible && sheet.phoneApp
                    onTriggered: sheet.loadPhones()
                }
                // A pairing declined (or never seen) on the phone: Pair again after a while.
                Timer {
                    id: pairWait
                    interval: 30000
                    onTriggered: sheet.phoneAsked = ""
                }
                Card {
                    tone: look
                    visible: phoneColumn.paired.length > 0
                    Repeater {
                        model: phoneColumn.paired
                        SettingRow {
                            tone: look
                            divider: index > 0
                            title: modelData.name
                            detail: !modelData.near ? i18n("Not nearby")
                                : typeof modelData.battery !== "number" ? i18n("Connected")
                                : modelData.charging ? i18n("Connected · charging, %1%", modelData.battery)
                                : i18n("Connected · %1% battery", modelData.battery)
                            lead: Rectangle {
                                width: 34
                                height: 34
                                radius: 17
                                color: modelData.near ? look.lily : look.wash2
                                Behavior on color { ColorAnimation { duration: Math.round(180 * look.speed) } }
                                Glyph {
                                    anchors.centerIn: parent
                                    width: 18
                                    height: 18
                                    path: sheet.deviceGlyph("phone")
                                    color: modelData.near ? "#FFFFFF" : look.ink
                                }
                            }
                            Row {
                                spacing: 8
                                Pill {
                                    tone: look
                                    visible: modelData.near
                                    text: i18n("Ring")
                                    onClicked: sheet.ask("phone-ring " + modelData.id)
                                }
                                Pill {
                                    tone: look
                                    visible: modelData.near
                                    kind: "lily"
                                    text: i18n("Send a file…")
                                    onClicked: sheet.ask("phone-send " + modelData.id)
                                }
                                Pill {
                                    tone: look
                                    text: i18n("Forget")
                                    onClicked: sheet.ask("phone-unpair " + modelData.id, () => sheet.loadPhones())
                                }
                            }
                        }
                    }
                }
                Row {
                    spacing: 8
                    visible: phoneColumn.paired.some(p => p.near)
                    Pill {
                        tone: look
                        text: i18n("Texts")
                        onClicked: sheet.ask("phone-texts")
                    }
                    Pill {
                        tone: look
                        text: i18n("Files on your phone")
                        onClicked: sheet.ask("phone-files " + phoneColumn.paired.find(p => p.near).id)
                    }
                }
                // Phones on the same Wi-Fi with KDE Connect open, to pair (the phone asks to accept).
                Card {
                    tone: look
                    visible: phoneColumn.near.length > 0
                    Repeater {
                        model: phoneColumn.near
                        SettingRow {
                            tone: look
                            divider: index > 0
                            title: modelData.name
                            detail: sheet.phoneAsked === modelData.id ? i18n("Accept on your phone") : i18n("Nearby, not paired")
                            Pill {
                                tone: look
                                kind: "lily"
                                text: sheet.phoneAsked === modelData.id ? i18n("Waiting…") : i18n("Pair")
                                enabledPill: sheet.phoneAsked !== modelData.id
                                onClicked: {
                                    sheet.phoneAsked = modelData.id
                                    pairWait.restart()
                                    sheet.ask("phone-pair " + modelData.id)
                                }
                            }
                        }
                    }
                }
                // No phone yet: the app, a scan away.
                Card {
                    tone: look
                    visible: phoneColumn.paired.length === 0 && sheet.phoneApp
                    Item {
                        Layout.fillWidth: true
                        implicitHeight: Math.max(qr.height, getApp.implicitHeight) + 36
                        Image {
                            id: qr
                            anchors.left: parent.left
                            anchors.leftMargin: 18
                            anchors.verticalCenter: parent.verticalCenter
                            width: 132
                            height: 132
                            source: sheet.art + "phone-qr.png"
                            smooth: false
                        }
                        ColumnLayout {
                            id: getApp
                            anchors.left: qr.right
                            anchors.leftMargin: 18
                            anchors.right: parent.right
                            anchors.rightMargin: 18
                            anchors.verticalCenter: parent.verticalCenter
                            spacing: 6
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: i18n("Get the app on your phone")
                                color: look.ink
                                font.pixelSize: 15
                                font.weight: Font.DemiBold
                                wrapMode: Text.WordWrap
                            }
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: i18n("Point your phone's camera at this and install the app it shows. Open it on the same Wi-Fi as this PC, and your phone shows up here to pair.")
                                color: look.dim
                                font.pixelSize: 13
                                wrapMode: Text.WordWrap
                            }
                        }
                    }
                }
                Card {
                    tone: look
                    visible: !sheet.phoneApp
                    SettingRow {
                        tone: look
                        divider: false
                        strong: false
                        title: i18n("Phones can't connect to this PC yet")
                        detail: i18n("The part of Monet that talks to phones is missing here.")
                    }
                }
                Pill {
                    tone: look
                    visible: sheet.phoneApp
                    text: i18n("More phone settings…")
                    onClicked: sheet.ask("kde phone")
                }
            }
        }

        Component {
            id: displayPage
            ColumnLayout {
                spacing: 20
                PageTitle {
                    tone: look
                    entry: sheet.entry("display")
                    art: sheet.art
                    text: i18n("Display")
                    detail: i18n("Brightness, and warmer colors at night.")
                }
                Card {
                    tone: look
                    SliderRow {
                        tone: look
                        divider: false
                        visible: typeof sheet.info.brightness === "number"
                        title: i18n("Brightness")
                        from: 1
                        value: sheet.info.brightness ?? 50
                        onHeld: down => sheet.dragging = down
                        onMoved: value => sheet.queue("brightness", value)
                    }
                    SettingRow {
                        tone: look
                        divider: typeof sheet.info.brightness === "number"
                        tappable: true
                        title: i18n("Night Light")
                        detail: i18n("Warmer colors from sunset to sunrise, easier on the eyes")
                        onTapped: sheet.flip("night", "night")
                        Switch {
                            tone: look
                            active: sheet.info.night === true
                        }
                    }
                }
                // For games and films: HDR, and the refresh rate keeping pace with the game,
                // on the screens that can (named when there's more than one).
                Caption {
                    tone: look
                    visible: sheet.screenInfo.length > 0
                    text: i18n("Games and films")
                }
                Repeater {
                    model: sheet.screenInfo
                    Card {
                        id: screenCard
                        required property var modelData
                        tone: look
                        SettingRow {
                            tone: look
                            divider: false
                            visible: screenCard.modelData.hdr !== null
                            tappable: true
                            title: sheet.screenInfo.length > 1 ? i18n("HDR on %1", screenCard.modelData.name) : i18n("HDR")
                            detail: i18n("Brighter highlights and deeper colors, in games and films made for it")
                            onTapped: sheet.screenFeature(screenCard.modelData.name, "hdr", !screenCard.modelData.hdr)
                            Switch {
                                tone: look
                                active: screenCard.modelData.hdr === true
                            }
                        }
                        SettingRow {
                            tone: look
                            divider: screenCard.modelData.hdr !== null
                            visible: screenCard.modelData.vrr !== null
                            tappable: true
                            title: sheet.screenInfo.length > 1 ? i18n("Smoother games on %1", screenCard.modelData.name)
                                : i18n("Smoother games")
                            detail: i18n("The screen keeps pace with the game, without tearing (FreeSync, G-Sync)")
                            onTapped: sheet.screenFeature(screenCard.modelData.name, "vrr", !screenCard.modelData.vrr)
                            Switch {
                                tone: look
                                active: screenCard.modelData.vrr === true
                            }
                        }
                    }
                }
                Pill {
                    tone: look
                    text: i18n("Arrange displays and size…")
                    onClicked: sheet.ask("kde display")
                }
            }
        }

        Component {
            id: soundPage
            ColumnLayout {
                id: soundColumn
                readonly property var speakers: sheet.outputs.filter(o => !o.none)
                spacing: 20
                PageTitle {
                    readonly property var playing: sheet.outputs.find(o => o.default)
                    tone: look
                    entry: sheet.entry("sound")
                    art: sheet.art
                    text: i18n("Sound")
                    detail: !playing ? "" : playing.none ? i18n("No speakers or headphones") : i18n("Playing through %1", playing.name)
                }
                Card {
                    tone: look
                    SliderRow {
                        tone: look
                        divider: false
                        title: i18n("Volume")
                        value: sheet.info.volume || 0
                        onHeld: down => sheet.dragging = down
                        onMoved: value => sheet.queue("volume", value)
                    }
                }
                Caption {
                    tone: look
                    visible: soundColumn.speakers.length > 0
                    text: i18n("Play sound through")
                }
                Card {
                    tone: look
                    objectName: "search-output"
                    Accessible.role: Accessible.Grouping
                    Accessible.name: i18n("Headphones and speakers")
                    SettingRow {
                        tone: look
                        visible: soundColumn.speakers.length === 0
                        divider: false
                        title: i18n("No speakers or headphones")
                        detail: i18n("Connect an audio device, or pair wireless headphones in Bluetooth.")
                        Pill {
                            tone: look
                            text: i18n("Bluetooth")
                            onClicked: sheet.open("bluetooth")
                        }
                    }
                    Repeater {
                        model: soundColumn.speakers
                        SettingRow {
                            tone: look
                            divider: index > 0
                            tappable: true
                            strong: false
                            title: modelData.name
                            onTapped: sheet.pickOutput(modelData)
                            lead: Glyph {
                                width: 18
                                height: 18
                                path: sheet.outputGlyph(modelData.name)
                                color: look.ink
                                opacity: modelData.default === true ? 1 : 0.6
                            }
                            Check {
                                tone: look
                                active: modelData.default === true
                            }
                        }
                    }
                }
                // Each app's own volume, as Windows' mixer has it (apps come and go as they play).
                Caption {
                    tone: look
                    visible: sheet.appsSound.length > 0
                    text: i18n("Apps playing sound")
                }
                Card {
                    tone: look
                    visible: sheet.appsSound.length > 0
                    Repeater {
                        model: sheet.appsSound
                        SliderRow {
                            required property var modelData
                            required property int index
                            tone: look
                            divider: index > 0
                            title: modelData.name
                            value: modelData.volume
                            onHeld: down => sheet.dragging = down
                            onMoved: value => sheet.queue("app-volume " + modelData.id, value)
                        }
                    }
                }
                Timer {
                    interval: 3000
                    repeat: true
                    running: sheet.page === "sound" && sheet.visible
                    onTriggered: sheet.ask("apps-sound", out => { if (!sheet.dragging) sheet.appsSound = sheet.json(out, sheet.appsSound) })
                }
                Card {
                    tone: look
                    objectName: "search-microphone"
                    Accessible.role: Accessible.Grouping
                    Accessible.name: i18n("Microphone")
                    SettingRow {
                        tone: look
                        divider: false
                        visible: typeof sheet.info.mic !== "number"
                        title: i18n("No microphone found")
                        detail: i18n("Connect a microphone or headset, then check More sound settings below.")
                    }
                    SliderRow {
                        tone: look
                        visible: typeof sheet.info.mic === "number"
                        divider: false
                        title: i18n("Microphone")
                        value: sheet.info.mic || 0
                        onHeld: down => sheet.dragging = down
                        onMoved: value => sheet.queue("mic", value)
                    }
                }
                Pill {
                    tone: look
                    text: i18n("More sound settings…")
                    onClicked: sheet.ask("kde sound")
                }
            }
        }

        Component {
            id: datetimePage
            ColumnLayout {
                id: datetimeColumn
                property date now: new Date()
                spacing: 20
                Timer {
                    interval: 1000
                    running: true
                    repeat: true
                    onTriggered: datetimeColumn.now = new Date()
                }
                PageTitle {
                    tone: look
                    entry: sheet.entry("datetime")
                    art: sheet.art
                    text: i18n("Date & Time")
                    detail: i18n("Your clock, and where in the world it keeps time.")
                }
                // The time now, as the clocks will show it.
                Card {
                    tone: look
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.margins: 20
                        spacing: 2
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            text: datetimeColumn.now.toLocaleTimeString(sheet.timeLocale(), Locale.ShortFormat)
                            color: look.ink
                            font.family: "Fraunces 72pt SuperSoft"
                            font.weight: Font.Light
                            font.pixelSize: 52
                            font.letterSpacing: -1
                            font.features: { "tnum": 1 }
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            text: datetimeColumn.now.toLocaleDateString(sheet.timeLocale(), Locale.LongFormat)
                                + ((sheet.clock.zone || "") !== "" ? " · " + sheet.zoneCity(sheet.clock.zone) : "")
                            color: look.dim
                            font.pixelSize: 14
                            elide: Text.ElideRight
                        }
                    }
                }
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        tappable: typeof sheet.clock.ntp === "boolean"
                        title: i18n("Set automatically")
                        detail: typeof sheet.clock.ntp === "boolean" ? i18n("From the internet, to the second") : i18n("This PC can't set its own time")
                        onTapped: sheet.flipNtp()
                        Switch {
                            tone: look
                            visible: typeof sheet.clock.ntp === "boolean"
                            active: sheet.clock.ntp === true
                        }
                    }
                    SettingRow {
                        id: clockRow
                        readonly property bool on24: sheet.hours24(sheet.timeLocale())
                        tone: look
                        tappable: sheet.otherClock() !== ""
                        title: i18n("24-hour time")
                        detail: !tappable ? i18n("As your region keeps it")
                            : on24 ? i18n("13:00, not 1:00 PM") : i18n("1:00 PM, not 13:00")
                        onTapped: sheet.flipClock()
                        Switch {
                            tone: look
                            active: clockRow.on24
                            opacity: clockRow.tappable ? 1 : 0.5
                        }
                    }
                }
                Caption {
                    tone: look
                    text: i18n("Time zone")
                }
                Card {
                    tone: look
                    Field {
                        id: zoneSearch
                        Layout.margins: 14
                        tone: look
                        hint: i18n("Search for a city")
                        onAccepted: {
                            const first = sheet.findZones(text)[0]
                            if (first) {
                                sheet.chooseZone(first)
                                text = ""
                            }
                        }
                    }
                    Repeater {
                        model: zoneSearch.text.trim() === "" ? [sheet.clock.zone || ""].filter(z => z !== "") : sheet.findZones(zoneSearch.text)
                        SettingRow {
                            tone: look
                            tappable: modelData !== sheet.clock.zone
                            strong: false
                            title: sheet.zoneCity(modelData)
                            detail: sheet.zoneRegion(modelData)
                            onTapped: {
                                sheet.chooseZone(modelData)
                                zoneSearch.text = ""
                            }
                            Check {
                                tone: look
                                active: modelData === sheet.clock.zone
                            }
                        }
                    }
                    SettingRow {
                        tone: look
                        visible: zoneSearch.text.trim() !== "" && sheet.findZones(zoneSearch.text).length === 0
                        strong: false
                        title: i18n("No time zone by that name")
                        detail: i18n("Try a big city near you.")
                    }
                }
                Pill {
                    tone: look
                    text: i18n("More date & time settings…")
                    onClicked: sheet.ask("kde datetime")
                }
            }
        }

        Component {
            id: usersPage
            ColumnLayout {
                id: usersColumn
                readonly property var you: sheet.people.find(p => p.you) || null
                readonly property var others: sheet.people.filter(p => !p.you && !p.guest)
                readonly property bool passwordOpen: ["open", "changing", "failed"].indexOf(sheet.passwordState) !== -1
                spacing: 20
                PageTitle {
                    tone: look
                    entry: sheet.entry("users")
                    art: sheet.art
                    text: i18n("Accounts")
                    detail: i18n("You, and the people who share this PC.")
                }
                Card {
                    tone: look
                    visible: usersColumn.you !== null
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.margins: 20
                        spacing: 18
                        // Your initial on a dab of lily, as in the menu.
                        Face {
                            Layout.preferredWidth: 64
                            Layout.preferredHeight: 64
                            name: usersColumn.you ? usersColumn.you.name : ""
                            picture: usersColumn.you ? usersColumn.you.picture : ""
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: usersColumn.you ? usersColumn.you.name : ""
                                color: look.ink
                                font.family: "Fraunces 72pt SuperSoft"
                                font.weight: Font.Light
                                font.pixelSize: 26
                                elide: Text.ElideRight
                            }
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: !usersColumn.you ? ""
                                    : usersColumn.you.admin ? i18n("%1 · Administrator", usersColumn.you.login)
                                    : i18n("%1 · Standard account", usersColumn.you.login)
                                color: look.dim
                                font.pixelSize: 13
                                elide: Text.ElideRight
                            }
                        }
                        Pill {
                            tone: look
                            visible: !sheet.renaming
                            text: i18n("Change name")
                            onClicked: {
                                sheet.nameProblem = ""
                                sheet.renaming = true
                            }
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: 20
                        Layout.rightMargin: 20
                        Layout.bottomMargin: 18
                        visible: sheet.renaming
                        spacing: 8
                        onVisibleChanged: {
                            if (visible) {
                                nameField.text = usersColumn.you ? usersColumn.you.name : ""
                                nameField.focusInput()
                            }
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Field {
                                id: nameField
                                tone: look
                                hint: i18n("Your name")
                                onAccepted: sheet.rename(text)
                            }
                            Pill {
                                tone: look
                                text: i18n("Cancel")
                                onClicked: sheet.renaming = false
                            }
                            Pill {
                                tone: look
                                kind: "lily"
                                text: i18n("Save")
                                onClicked: sheet.rename(nameField.text)
                            }
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            visible: sheet.nameProblem !== ""
                            text: sheet.nameProblem
                            color: "#E0603A"
                            font.pixelSize: 13
                            wrapMode: Text.Wrap
                        }
                    }
                }
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        title: i18n("Password")
                        detail: sheet.passwordState === "done" ? i18n("Changed. Use the new one from now on.")
                            : i18n("For signing in, unlocking and allowing changes")
                        Pill {
                            tone: look
                            visible: !usersColumn.passwordOpen
                            text: i18n("Change…")
                            onClicked: sheet.passwordState = "open"
                        }
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: 18
                        Layout.rightMargin: 18
                        Layout.bottomMargin: 18
                        visible: usersColumn.passwordOpen
                        spacing: 8
                        onVisibleChanged: {
                            if (visible) {
                                oldPassword.text = ""
                                newPassword.text = ""
                                againPassword.text = ""
                                oldPassword.focusInput()
                            }
                        }
                        Field {
                            id: oldPassword
                            tone: look
                            secret: true
                            hint: i18n("Current password")
                            onAccepted: newPassword.focusInput()
                        }
                        Field {
                            id: newPassword
                            tone: look
                            secret: true
                            hint: i18n("New password")
                            onAccepted: againPassword.focusInput()
                        }
                        Field {
                            id: againPassword
                            tone: look
                            secret: true
                            hint: i18n("New password, again")
                            onAccepted: sheet.changePassword(oldPassword.text, newPassword.text, againPassword.text)
                        }
                        RowLayout {
                            Layout.fillWidth: true
                            Layout.topMargin: 4
                            spacing: 8
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: sheet.passwordState === "failed" ? sheet.passwordMessage : ""
                                color: "#E0603A"
                                font.pixelSize: 13
                                wrapMode: Text.Wrap
                            }
                            Pill {
                                tone: look
                                text: i18n("Cancel")
                                enabledPill: sheet.passwordState !== "changing"
                                onClicked: sheet.passwordState = ""
                            }
                            Pill {
                                tone: look
                                kind: "lily"
                                text: sheet.passwordState === "changing" ? i18n("Changing…") : i18n("Change password")
                                enabledPill: sheet.passwordState !== "changing"
                                onClicked: sheet.changePassword(oldPassword.text, newPassword.text, againPassword.text)
                            }
                        }
                    }
                }
                Caption {
                    tone: look
                    text: i18n("Other people")
                }
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        visible: usersColumn.others.length === 0
                        strong: false
                        title: i18n("Only you, so far")
                        detail: i18n("Add someone in More account settings.")
                    }
                    Repeater {
                        model: usersColumn.others
                        SettingRow {
                            tone: look
                            divider: index > 0
                            title: modelData.name
                            detail: modelData.admin ? i18n("Administrator") : i18n("Standard account")
                            lead: Face {
                                width: 34
                                height: 34
                                name: modelData.name
                                picture: modelData.picture
                                glaze: sheet.glaze(modelData.login)
                            }
                        }
                    }
                }
                // A guest: someone signs in without a password and leaves nothing behind.
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        tappable: !sheet.guestBusy
                        title: i18n("Guest")
                        detail: sheet.guestBusy ? i18n("Asking for an administrator's password…")
                            : i18n("Someone can sign in as Guest, with no password, without seeing your files, games or Windows. Everything they do is gone when they sign out.")
                        onTapped: {
                            const on = sheet.guestInfo.on !== true
                            sheet.guestBusy = true
                            sheet.ask(on ? "guest-on" : "guest-off", out => {
                                sheet.guestBusy = false
                                sheet.guestInfo = sheet.json(out, sheet.guestInfo)
                            })
                        }
                        Switch {
                            tone: look
                            active: sheet.guestInfo.on === true
                        }
                    }
                }
                Pill {
                    tone: look
                    text: i18n("More account settings…")
                    onClicked: sheet.ask("kde users")
                }
            }
        }

        Component {
            id: inputPage
            ColumnLayout {
                id: inputColumn
                readonly property var codes: (sheet.inputInfo.layouts || []).map(l => l.code)
                spacing: 20
                PageTitle {
                    tone: look
                    entry: sheet.entry("input")
                    art: sheet.art
                    text: i18n("Mouse & Keyboard")
                    detail: i18n("How the pointer moves and scrolls, and the languages you type in.")
                }
                // The mouse and the touchpad, each set as one (all mice alike).
                Repeater {
                    // The touchpad first: on a laptop it's the pointer you have.
                    model: [["touchpad", i18n("Touchpad")], ["mouse", i18n("Mouse")]].filter(k => !!sheet.inputInfo[k[0]])
                    ColumnLayout {
                        id: pointerKind
                        required property var modelData
                        readonly property var settings: sheet.inputInfo[modelData[0]] || {}
                        Layout.fillWidth: true
                        spacing: 20
                        Caption {
                            tone: look
                            text: pointerKind.modelData[1]
                        }
                        Card {
                            tone: look
                            SliderRow {
                                tone: look
                                divider: false
                                visible: pointerKind.settings.speed !== undefined
                                title: i18n("Pointer speed")
                                value: pointerKind.settings.speed !== undefined ? pointerKind.settings.speed : 50
                                onHeld: down => sheet.dragging = down
                                onMoved: value => sheet.queue("pointer " + pointerKind.modelData[0] + " speed", value)
                            }
                            Repeater {
                                model: [
                                    ["tap", i18n("Tap to click"), i18n("A light tap is a click")],
                                    ["natural", i18n("Natural scrolling"), i18n("The page follows your fingers, as on a phone")],
                                    ["left", i18n("Left-handed"), i18n("The buttons swap sides")],
                                    ["typing", i18n("Off while typing"), i18n("A palm on it won't move the pointer")]
                                ].filter(s => pointerKind.settings[s[0]] !== undefined)
                                SettingRow {
                                    id: pointerRow
                                    required property var modelData
                                    required property int index
                                    tone: look
                                    divider: index > 0 || pointerKind.settings.speed !== undefined
                                    tappable: true
                                    title: modelData[1]
                                    detail: modelData[2]
                                    onTapped: sheet.pointer(pointerKind.modelData[0], modelData[0], pointerKind.settings[modelData[0]] !== true)
                                    Switch {
                                        tone: look
                                        active: pointerKind.settings[pointerRow.modelData[0]] === true
                                    }
                                }
                            }
                        }
                    }
                }
                Caption {
                    tone: look
                    text: i18n("Keyboard")
                }
                Card {
                    tone: look
                    Repeater {
                        model: sheet.inputInfo.layouts || []
                        SettingRow {
                            id: layoutRow
                            required property var modelData
                            required property int index
                            tone: look
                            divider: index > 0
                            tappable: index > 0
                            strong: index === 0
                            title: modelData.name
                            detail: index === 0 ? i18n("Typing starts in this one") : i18n("Click to make this the main one")
                            onTapped: sheet.setLayouts([modelData.code].concat(inputColumn.codes.filter(c => c !== layoutRow.modelData.code)))
                            Pill {
                                tone: look
                                visible: inputColumn.codes.length > 1
                                text: i18n("Remove")
                                onClicked: sheet.setLayouts(inputColumn.codes.filter(c => c !== layoutRow.modelData.code))
                            }
                        }
                    }
                    Field {
                        id: layoutSearch
                        Layout.margins: 14
                        tone: look
                        hint: i18n("Add a language or layout")
                        onAccepted: {
                            const first = sheet.findLayouts(text)[0]
                            if (first) {
                                sheet.setLayouts(inputColumn.codes.concat([first.code]))
                                text = ""
                            }
                        }
                    }
                    Repeater {
                        model: sheet.findLayouts(layoutSearch.text)
                        SettingRow {
                            required property var modelData
                            tone: look
                            tappable: true
                            strong: false
                            title: modelData.name
                            onTapped: {
                                sheet.setLayouts(inputColumn.codes.concat([modelData.code]))
                                layoutSearch.text = ""
                            }
                            Glyph {
                                width: 14
                                height: 14
                                path: "M12 5v14M5 12h14"
                                color: look.lily
                            }
                        }
                    }
                    SettingRow {
                        tone: look
                        visible: layoutSearch.text.trim() !== "" && sheet.findLayouts(layoutSearch.text).length === 0
                        strong: false
                        title: i18n("No layout by that name")
                        detail: i18n("Try your language's name, like Swedish or Japanese.")
                    }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    Layout.topMargin: -8
                    visible: inputColumn.codes.length > 1
                    text: i18n("The bar shows which one you're typing in. Click it to switch.")
                    color: look.dim
                    font.pixelSize: 13
                    wrapMode: Text.Wrap
                }
                // Plasma's own keys (and Monet's menu, on the Windows key), to learn them by.
                Caption {
                    tone: look
                    text: i18n("Keyboard shortcuts")
                }
                Card {
                    tone: look
                    GridLayout {
                        Layout.fillWidth: true
                        Layout.margins: 20
                        columns: 2
                        columnSpacing: 28
                        rowSpacing: 10
                        Repeater {
                            // Windows' own keys where Windows has one (monet-look --keys sets those).
                            model: [[i18n("Open the menu"), ["Meta"]], [i18n("Settings"), ["Meta", "I"]],
                                    [i18n("Quick Settings"), ["Meta", "A"]], [i18n("Games"), ["Meta", "G"]],
                                    [i18n("Files"), ["Meta", "E"]], [i18n("Run or find"), ["Meta", "R"]],
                                    [i18n("Lock the screen"), ["Meta", "L"]], [i18n("The desktop"), ["Meta", "D"]],
                                    [i18n("All your windows"), ["Meta", "Tab"]], [i18n("Switch windows"), ["Alt", "Tab"]],
                                    [i18n("A window on one half"), ["Meta", "\u2190", "\u2192"]],
                                    ...(sheet.prefs.snap !== false ? [[i18n("Snap layouts"), ["Meta", "Z"]]] : []),
                                    [i18n("A window on the whole screen"), ["Meta", "\u2191"]],
                                    [i18n("Minimize a window"), ["Meta", "\u2193"]],
                                    [i18n("What's running"), ["Ctrl", "Shift", "Esc"]],
                                    [i18n("What you copied"), ["Meta", "V"]], [i18n("Emoji"), ["Meta", "."]],
                                    [i18n("Next keyboard layout"), ["Meta", "Space"]],
                                    [i18n("Screenshot"), ["Print"]], [i18n("Part of the screen"), ["Meta", "Shift", "S"]],
                                    [i18n("Save the last 30 seconds"), ["Meta", "Alt", "G"]],
                                    [i18n("Record the screen"), ["Meta", "Alt", "R"]],
                                    [i18n("Restart or shut down"), ["Ctrl", "Alt", "Del"]]]
                            RowLayout {
                                id: shortcutRow
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                spacing: 10
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    text: shortcutRow.modelData[0]
                                    color: look.ink
                                    font.pixelSize: 13
                                    elide: Text.ElideRight
                                }
                                Row {
                                    spacing: 4
                                    Repeater {
                                        model: shortcutRow.modelData[1]
                                        Key {
                                            required property var modelData
                                            tone: look
                                            keyName: modelData
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                Row {
                    spacing: 8
                    Pill {
                        tone: look
                        text: i18n("More mouse & keyboard settings…")
                        onClicked: sheet.ask("kde input")
                    }
                    Pill {
                        tone: look
                        text: i18n("Change shortcuts…")
                        onClicked: sheet.ask("kde keys")
                    }
                }
            }
        }

        Component {
            id: powerPage
            ColumnLayout {
                id: powerColumn
                readonly property var screenTimes: [300, 600, 1800, 3600, 0].map(s => [s, sheet.span(s)])
                readonly property var sleepTimes: [900, 1800, 3600, 7200, 0].map(s => [s, sheet.span(s)])
                // On battery, KDE sleeps after 10 minutes: shorter times, that one among them, and 15
                // (the shortest this offered before, so a time chosen then still shows).
                readonly property var batterySleepTimes: [300, 600, 900, 1800, 3600, 0].map(s => [s, sheet.span(s)])
                spacing: 20
                PageTitle {
                    tone: look
                    entry: sheet.entry("power")
                    art: sheet.art
                    text: i18n("Power & Sleep")
                    detail: i18n("When the screen rests, when the PC sleeps, and how hard it works.")
                }
                // The battery, on a laptop: how full, and charging or how long it lasts.
                Card {
                    tone: look
                    visible: typeof sheet.info.battery === "number"
                    SettingRow {
                        tone: look
                        divider: false
                        title: i18n("Battery %1%", sheet.info.battery)
                        detail: sheet.info.charging
                            ? (sheet.info.minutes ? i18nc("%1 is a time like 1:20", "Charging, full in %1", sheet.hm(sheet.info.minutes)) : i18n("Charging"))
                            : sheet.info.plugged ? i18n("Plugged in")
                            : sheet.info.minutes ? i18nc("%1 is a time like 2:15", "About %1 left", sheet.hm(sheet.info.minutes)) : i18n("On battery")
                    }
                    // Battery care, where the battery can do it (ThinkPads and many others): it stops at 80%.
                    SettingRow {
                        tone: look
                        visible: sheet.batteryCare.supported === true
                        tappable: true
                        title: i18n("Protect the battery")
                        detail: i18n("Stops charging at 80%, so the battery lasts more years. Best for a laptop that's mostly plugged in.")
                        onTapped: {
                            const limit = sheet.batteryCare.limit <= 80 ? 100 : 80
                            sheet.batteryCare = { supported: true, limit: limit }
                            sheet.ask("battery-limit " + limit, () => sheet.ask("battery-care", out => sheet.batteryCare = sheet.json(out, sheet.batteryCare)))
                        }
                        Switch {
                            tone: look
                            active: sheet.batteryCare.limit <= 80
                        }
                    }
                }
                // How hard it works: three choices, like Light's.
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 12
                    visible: (sheet.powerInfo.modes || []).length > 0
                    Repeater {
                        model: [
                            ["power-saver", i18n("Power saver"), i18n("Cooler and quieter, longer on battery"),
                             "M5 19c0-9 5-14 14-14c0 9-5 14-14 14zM5 19l7-7"],
                            ["balanced", i18n("Balanced"), i18n("Quick when it counts"),
                             "M12 4v16M6 8h12M6 8l-3 6a3 3 0 0 0 6 0zM18 8l-3 6a3 3 0 0 0 6 0zM8 20h8"],
                            ["performance", i18n("Performance"), i18n("As fast as it goes, warmer and louder"),
                             "M13 3L5 13h6l-1 8 8-10h-6z"]
                        ].filter(m => (sheet.powerInfo.modes || []).indexOf(m[0]) !== -1)
                        Rectangle {
                            id: modeChoice
                            required property var modelData
                            readonly property bool picked: sheet.powerInfo.mode === modelData[0]
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            implicitHeight: modeColumn.implicitHeight + 28
                            radius: 18
                            color: picked ? Qt.rgba(0.302, 0.706, 0.627, 0.1) : modeHover.hovered ? look.wash2 : look.wash
                            border.width: picked || activeFocus ? 2 : 1
                            border.color: picked || activeFocus ? look.lily : look.line
                            scale: modeTap.pressed ? 0.98 : 1
                            activeFocusOnTab: true
                            Keys.onSpacePressed: sheet.powerMode(modelData[0])
                            Behavior on scale { NumberAnimation { duration: Math.round(160 * sheet.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
                            Behavior on color { ColorAnimation { duration: Math.round(160 * sheet.speed) } }
                            ColumnLayout {
                                id: modeColumn
                                anchors.left: parent.left
                                anchors.right: parent.right
                                anchors.top: parent.top
                                anchors.margins: 14
                                spacing: 4
                                Glyph {
                                    Layout.preferredWidth: 22
                                    Layout.preferredHeight: 22
                                    Layout.bottomMargin: 6
                                    path: modeChoice.modelData[3]
                                    color: modeChoice.picked ? look.lily : look.ink
                                }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    text: modeChoice.modelData[1]
                                    color: look.ink
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    text: modeChoice.modelData[2]
                                    color: look.dim
                                    font.pixelSize: 13
                                    wrapMode: Text.Wrap
                                }
                            }
                            HoverHandler { id: modeHover }
                            TapHandler {
                                id: modeTap
                                onTapped: sheet.powerMode(modeChoice.modelData[0])
                            }
                            Accessible.role: Accessible.RadioButton
                            Accessible.name: modelData[1]
                            Accessible.description: modelData[2]
                            Accessible.checked: picked
                            Accessible.onPressAction: sheet.powerMode(modelData[0])
                        }
                    }
                }
                // Plugged in, and on battery when there is one.
                Repeater {
                    model: sheet.powerInfo.hasBattery === true ? [["ac", i18n("Plugged in")], ["battery", i18n("On battery")]] : [["ac", ""]]
                    ColumnLayout {
                        id: powerState
                        required property var modelData
                        readonly property var times: sheet.powerInfo[modelData[0]] || {}
                        Layout.fillWidth: true
                        spacing: 20
                        Caption {
                            tone: look
                            visible: powerState.modelData[1] !== ""
                            text: powerState.modelData[1]
                        }
                        Card {
                            tone: look
                            SettingRow {
                                tone: look
                                divider: false
                                title: i18n("Turn off the screen")
                                detail: i18n("After this long untouched")
                                Segments {
                                    tone: look
                                    options: powerColumn.screenTimes
                                    current: powerState.times.screen
                                    onPicked: value => sheet.powerTime(powerState.modelData[0], "screen", value)
                                }
                            }
                            SettingRow {
                                tone: look
                                title: i18n("Sleep")
                                detail: i18n("It wakes where you left off")
                                Segments {
                                    tone: look
                                    options: powerState.modelData[0] === "battery" ? powerColumn.batterySleepTimes : powerColumn.sleepTimes
                                    current: powerState.times.sleep
                                    onPicked: value => sheet.powerTime(powerState.modelData[0], "sleep", value)
                                }
                            }
                        }
                    }
                }
                Caption {
                    tone: look
                    text: i18n("Buttons")
                }
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        title: i18n("Power button")
                        detail: i18n("What a press does")
                        Segments {
                            tone: look
                            options: [[16, i18n("Ask")], [1, i18n("Sleep")], [8, i18n("Shut down")], [0, i18n("Nothing")]]
                            current: sheet.powerInfo.button
                            onPicked: value => sheet.powerAction("button", value)
                        }
                    }
                    SettingRow {
                        tone: look
                        visible: sheet.powerInfo.hasLid === true
                        title: i18n("Closing the lid")
                        Segments {
                            tone: look
                            options: [[1, i18n("Sleep")], [32, i18n("Lock")], [64, i18n("Screen off")], [0, i18n("Nothing")]]
                            current: sheet.powerInfo.lidAction
                            onPicked: value => sheet.powerAction("lid", value)
                        }
                    }
                }
                Pill {
                    tone: look
                    text: i18n("More power settings…")
                    onClicked: sheet.ask("kde power")
                }
            }
        }

        Component {
            id: notificationsPage
            ColumnLayout {
                spacing: 20
                PageTitle {
                    tone: look
                    entry: sheet.entry("notifications")
                    art: sheet.art
                    text: i18n("Notifications")
                    detail: i18n("What may interrupt you, and when it waits.")
                }
                Card {
                    tone: look
                    enabled: sheet.notifyBusy === ""
                    SettingRow {
                        objectName: "doNotDisturb"
                        tone: look
                        divider: false
                        tappable: true
                        checkable: true
                        checked: sheet.notifyInfo.quiet === true
                        title: i18n("Do not disturb")
                        detail: sheet.quietDescription()
                        onTapped: sheet.changeNotification("quiet " + (sheet.notifyInfo.quiet ? "off" : "on"))
                        Switch {
                            tone: look
                            active: sheet.notifyInfo.quiet === true
                            Accessible.ignored: true
                        }
                    }
                    Flow {
                        Layout.fillWidth: true
                        Layout.leftMargin: 18
                        Layout.rightMargin: 18
                        Layout.bottomMargin: 14
                        spacing: 8
                        Repeater {
                            model: [["hour", i18n("For 1 hour")], ["four-hours", i18n("For 4 hours")],
                                    ["tomorrow", i18n("Until tomorrow morning")]]
                            Pill {
                                objectName: "quiet-" + modelData[0]
                                tone: look
                                text: modelData[1]
                                onClicked: sheet.changeNotification("quiet " + modelData[0])
                            }
                        }
                    }
                    SettingRow {
                        tone: look
                        title: i18n("Sounds")
                        detail: i18n("Choose sounds for individual apps")
                        Pill {
                            tone: look
                            text: i18n("Choose…")
                            onClicked: sheet.ask("kde notifications")
                        }
                    }
                }
                Caption {
                    tone: look
                    text: i18n("Quiet by itself")
                }
                Card {
                    tone: look
                    enabled: sheet.notifyBusy === ""
                    Repeater {
                        model: [
                            ["fullscreen", i18n("While a game or film fills the screen"), i18n("They wait until you're done")],
                            ["mirrored", i18n("While you share or mirror your screen"), i18n("So nothing private pops up for others")],
                            ["urgent", i18n("Let urgent ones through"), i18n("Like a low battery, even while quiet")]
                        ]
                        SettingRow {
                            id: ruleRow
                            required property var modelData
                            required property int index
                            tone: look
                            divider: index > 0
                            tappable: true
                            checkable: true
                            checked: sheet.notifyInfo[modelData[0]] !== false
                            title: modelData[1]
                            detail: modelData[2]
                            onTapped: sheet.notifyRule(modelData[0], sheet.notifyInfo[modelData[0]] === false)
                            Switch {
                                tone: look
                                active: sheet.notifyInfo[ruleRow.modelData[0]] !== false
                                Accessible.ignored: true
                            }
                        }
                    }
                }
                Caption {
                    tone: look
                    text: i18n("Popups")
                }
                Card {
                    tone: look
                    enabled: sheet.notifyBusy === ""
                    SettingRow {
                        tone: look
                        divider: false
                        title: i18n("Where they appear")
                    }
                    Segments {
                        Layout.leftMargin: 18
                        Layout.rightMargin: 18
                        Layout.bottomMargin: 14
                        tone: look
                        options: [["clock", i18n("By the clock")], ["topright", i18n("Top right")], ["topcenter", i18n("Top center")]]
                        current: sheet.notifyInfo.place || "clock"
                        onPicked: value => sheet.notifyPopups("place", value)
                    }
                    SettingRow {
                        tone: look
                        title: i18n("How long they stay")
                        Segments {
                            tone: look
                            options: [3, 5, 10].map(s => [s, i18n("%1 s", s)])
                            current: sheet.notifyInfo.time || 5
                            onPicked: value => sheet.notifyPopups("time", value)
                        }
                    }
                }
                Caption {
                    tone: look
                    text: i18n("Apps")
                }
                Card {
                    tone: look
                    enabled: sheet.notifyBusy === ""
                    Repeater {
                        model: sheet.notifyInfo.apps || []
                        SettingRow {
                            id: appRow
                            required property var modelData
                            required property int index
                            tone: look
                            divider: index > 0
                            tappable: true
                            checkable: true
                            checked: modelData.popups === true
                            strong: false
                            title: modelData.name
                            detail: modelData.popups ? i18n("Pops up") : i18n("Only in the list, without popping up")
                            lead: Kirigami.Icon {
                                width: 28
                                height: 28
                                source: appRow.modelData.icon
                            }
                            onTapped: sheet.notifyApp(modelData, !modelData.popups)
                            Switch {
                                tone: look
                                active: appRow.modelData.popups === true
                                Accessible.ignored: true
                            }
                        }
                    }
                    SettingRow {
                        tone: look
                        visible: (sheet.notifyInfo.apps || []).length === 0
                        divider: false
                        strong: false
                        title: i18n("No apps yet")
                        detail: i18n("Apps show up here once they've sent a notification.")
                    }
                }
                Pill {
                    tone: look
                    text: i18n("More notification settings…")
                    onClicked: sheet.ask("kde notifications")
                }
            }
        }

        Component {
            id: appsPage
            ColumnLayout {
                id: appsColumn
                // The kind whose apps are showing, to pick one.
                property string choosing: ""
                readonly property var names: ({
                    browser: i18n("Web browser"), mail: i18n("Email"), files: i18n("Folders"), music: i18n("Music"),
                    video: i18n("Video"), photos: i18n("Photos"), pdf: i18n("PDF documents"), text: i18n("Text files")
                })
                spacing: 20
                PageTitle {
                    tone: look
                    entry: sheet.entry("apps")
                    art: sheet.art
                    text: i18n("Default Apps")
                    detail: i18n("What opens web links, mail, folders, music, films, photos, PDFs and text.")
                }
                Card {
                    tone: look
                    Repeater {
                        model: sheet.appDefaults
                        ColumnLayout {
                            id: kindBlock
                            required property var modelData
                            required property int index
                            readonly property var current: modelData.apps.find(a => a.id === modelData.current) || null
                            readonly property bool opened: appsColumn.choosing === modelData.id
                            Layout.fillWidth: true
                            spacing: 0
                            SettingRow {
                                tone: look
                                divider: kindBlock.index > 0
                                tappable: kindBlock.modelData.apps.length > 0 || (kindBlock.modelData.store || "") !== ""
                                title: appsColumn.names[kindBlock.modelData.id] || kindBlock.modelData.id
                                detail: kindBlock.current ? kindBlock.current.name
                                    : kindBlock.modelData.apps.length > 0 ? i18n("Nothing chosen yet")
                                    : (kindBlock.modelData.store || "") !== "" ? i18n("No app for this yet. Find one in the Store")
                                    : i18n("No app for this yet")
                                lead: Kirigami.Icon {
                                    width: 28
                                    height: 28
                                    source: kindBlock.current ? kindBlock.current.icon : "application-x-executable"
                                }
                                onTapped: {
                                    if (kindBlock.modelData.apps.length > 0) {
                                        appsColumn.choosing = kindBlock.opened ? "" : kindBlock.modelData.id
                                    } else {
                                        sheet.ask("launch " + sheet.hex(kindBlock.modelData.store))
                                    }
                                }
                                // A row, so only what shows takes room.
                                Row {
                                    Glyph {
                                        visible: kindBlock.modelData.apps.length > 0
                                        width: 14
                                        height: 14
                                        path: kindBlock.opened ? "M6 15l6-6 6 6" : "M6 9l6 6 6-6"
                                        color: look.dim
                                    }
                                    Pill {
                                        tone: look
                                        visible: kindBlock.modelData.apps.length === 0 && (kindBlock.modelData.store || "") !== ""
                                        kind: "lily"
                                        text: i18n("Find one")
                                        onClicked: sheet.ask("launch " + sheet.hex(kindBlock.modelData.store))
                                    }
                                }
                            }
                            Repeater {
                                model: kindBlock.opened ? kindBlock.modelData.apps : []
                                SettingRow {
                                    id: takerRow
                                    required property var modelData
                                    Layout.leftMargin: 28
                                    tone: look
                                    tappable: true
                                    strong: false
                                    title: modelData.name
                                    lead: Kirigami.Icon {
                                        width: 24
                                        height: 24
                                        source: takerRow.modelData.icon
                                    }
                                    onTapped: {
                                        sheet.setDefault(kindBlock.modelData.id, modelData)
                                        appsColumn.choosing = ""
                                    }
                                    Check {
                                        tone: look
                                        active: takerRow.modelData.id === kindBlock.modelData.current
                                    }
                                }
                            }
                        }
                    }
                }
                Pill {
                    tone: look
                    text: i18n("More default apps…")
                    onClicked: sheet.ask("kde apps")
                }
                Caption { tone: look; text: i18n("Browser bookmarks") }
                Card {
                    id: bookmarkImport
                    objectName: "search-bookmarks"
                    tone: look
                    readonly property var profiles: sheet.browserInfo.profiles || []
                    property string profile: profiles.length === 1 ? profiles[0].id : ""
                    property string source: sheet.browserInfo.count > 0 ? "windows" : ""
                    property bool busy: false
                    property var preview: ({})
                    property var preparedImport: ({})
                    property string message: ""
                    property string checkedState: ""
                    readonly property var previousImport: (sheet.browserInfo.imports || []).find(item => item.profile === profile) || ({})
                    function reset() { preview = ({}); preparedImport = ({}); message = ""; checkedState = "" }
                    function problem(code) {
                        return ({busy: i18n("Close this Zen profile, then try again. Your bookmarks are unchanged."),
                            profile: i18n("Choose a Zen profile. Open Zen once if the list is empty."),
                            browser: i18n("Install Zen before importing bookmarks."),
                            source: i18n("This file could not be read. Choose the bookmark export again."),
                            invalid: i18n("This is not a supported bookmark HTML export. Export bookmarks as HTML from your old browser."),
                            large: i18n("This export is too large. Choose an export under 16 MB with fewer than 25,000 bookmarks."),
                            database: i18n("Zen's bookmarks could not be read. Open Zen to check this profile, then try again."),
                            changed: i18n("The file or bookmarks changed. Review the import again."),
                            storage: i18n("The import file could not be saved. Check free space and try again.")})[code]
                            || i18n("The import could not be checked. Try again.")
                    }
                    function act(action) {
                        if (busy) return
                        busy = true; message = ""; checkedState = ""
                        const request = action === "verify" ? {"id": preparedImport.id}
                            : {profile: profile, source: source, token: preview.token || ""}
                        sheet.ask("bookmarks-" + action + " " + sheet.hex(JSON.stringify(request)), (out, code) => {
                            busy = false
                            const result = sheet.json(out, ({}))
                            if (code !== 0 || !result.ok) {
                                if (action !== "verify") preview = ({})
                                message = problem(result.error)
                                return
                            }
                            if (action === "preview") preview = result
                            else if (action === "prepare") {
                                preparedImport = result
                                if (!result.opened && result.state === "prepared")
                                    message = i18n("The file is ready, but Zen did not start. Open the selected profile to import it.")
                            } else {
                                checkedState = result.state
                                message = result.state === "verified"
                                    ? i18np("Verified %1 imported bookmark.", "Verified %1 imported bookmarks.", result.count)
                                    : result.state === "partial" ? i18n("%1 of %2 bookmarks found. Finish the import in the selected profile, then check again.", result.count, result.expected)
                                    : i18n("No imported bookmarks found yet. Import the prepared file in the selected profile, then check again.")
                                if (result.duplicates > 0) message += " " + i18n("This file was imported more than once. Remove the extra imported folder in Zen.")
                            }
                        })
                    }
                    SettingRow {
                        tone: look
                        title: i18n("Bring your bookmarks")
                        detail: i18n("Choose an HTML export and a Zen profile. Existing links are skipped. Your current bookmarks stay in place.")
                    }
                    SettingRow {
                        tone: look
                        title: i18n("Source")
                        detail: bookmarkImport.source === "windows" ? i18n("Bookmarks from Windows") : bookmarkImport.source
                        Pill {
                            tone: look; text: i18n("Choose HTML file")
                            enabledPill: !bookmarkImport.busy
                            onClicked: bookmarkPicker.open()
                        }
                    }
                    SettingRow {
                        tone: look; visible: sheet.browserInfo.count > 0
                        title: i18n("From Windows")
                        detail: i18np("%1 bookmark", "%1 bookmarks", sheet.browserInfo.count || 0)
                        Pill {
                            tone: look; text: i18n("Use these")
                            enabledPill: !bookmarkImport.busy
                            onClicked: { bookmarkImport.reset(); bookmarkImport.source = "windows" }
                        }
                    }
                    SettingRow {
                        tone: look; title: i18n("Destination profile")
                        detail: bookmarkImport.profiles.length ? i18n("Only the selected profile is used. Close it before reviewing or checking an import.")
                            : i18n("Open Zen once to create a profile, then reopen this page.")
                    }
                    Repeater {
                        model: bookmarkImport.profiles
                        SettingRow {
                            id: bookmarkProfile
                            required property var modelData
                            objectName: "bookmarkProfile-" + modelData.id
                            tone: look; title: modelData.name; detail: modelData.id
                            tappable: !bookmarkImport.busy; checkable: true
                            checked: bookmarkImport.profile === modelData.id
                            Accessible.role: Accessible.RadioButton
                            onTapped: { bookmarkImport.reset(); bookmarkImport.profile = modelData.id }
                            Text {
                                text: bookmarkProfile.checked ? i18n("Selected") : i18n("Choose")
                                color: bookmarkProfile.checked ? look.lily : look.dim
                                font.pixelSize: 13
                                font.weight: bookmarkProfile.checked ? Font.DemiBold : Font.Normal
                            }
                        }
                    }
                    SettingRow {
                        tone: look; visible: !!bookmarkImport.previousImport.id && !bookmarkImport.preparedImport.id
                        title: i18n("Previous import")
                        detail: bookmarkImport.previousImport.folder || ""
                        Pill {
                            tone: look; text: i18n("Check previous import")
                            enabledPill: !bookmarkImport.busy
                            onClicked: { bookmarkImport.preparedImport = bookmarkImport.previousImport; bookmarkImport.act("verify") }
                        }
                    }
                    SettingRow {
                        tone: look; title: i18n("Review import")
                        detail: bookmarkImport.preview.ok
                            ? i18n("New links: %1. Already bookmarked or repeated: %2. Unsupported links skipped: %3.", bookmarkImport.preview.new, bookmarkImport.preview.duplicates, bookmarkImport.preview.unsupported)
                            : i18n("Review the file before creating an import. No browser data is changed by this step.")
                        Pill {
                            objectName: "bookmarkReview"
                            tone: look; text: bookmarkImport.busy ? i18n("Checking…") : i18n("Review")
                            enabledPill: !bookmarkImport.busy && bookmarkImport.profile !== "" && bookmarkImport.source !== ""
                            onClicked: { bookmarkImport.preparedImport = ({}); bookmarkImport.checkedState = ""; bookmarkImport.act("preview") }
                        }
                    }
                    Repeater {
                        model: bookmarkImport.preview.sample || []
                        Text {
                            required property string modelData
                            Layout.fillWidth: true; Layout.margins: 12
                            text: modelData; textFormat: Text.PlainText
                            color: look.dim; wrapMode: Text.WrapAnywhere
                        }
                    }
                    SettingRow {
                        tone: look; visible: bookmarkImport.preview.ok === true && !bookmarkImport.preparedImport.id
                        title: bookmarkImport.preview.new > 0 ? i18n("Ready to import") : i18n("Nothing new to import")
                        detail: i18n("New links go into their own folder. To undo, remove that folder in Zen. Import the prepared file only once.")
                        Pill {
                            objectName: "bookmarkPrepare"
                            tone: look; kind: "lily"; text: i18n("Prepare and open Zen")
                            enabledPill: !bookmarkImport.busy && bookmarkImport.preview.new > 0
                            onClicked: bookmarkImport.act("prepare")
                        }
                    }
                    SettingRow {
                        tone: look; visible: !!bookmarkImport.preparedImport.id
                        title: i18n("Finish in Zen")
                        detail: i18n("In the selected profile's Library, choose Import and Backup, then Import Bookmarks from HTML. Select %1. The new folder is %2. Close this profile when finished, then check the import here.", bookmarkImport.preparedImport.file || "", bookmarkImport.preparedImport.folder || "")
                        Pill {
                            objectName: "bookmarkVerify"
                            tone: look; text: i18n("Check import")
                            enabledPill: !bookmarkImport.busy
                            onClicked: bookmarkImport.act("verify")
                        }
                    }
                    SettingRow {
                        objectName: "bookmarkMessage"
                        tone: look; visible: bookmarkImport.message !== ""
                        title: bookmarkImport.checkedState === "verified" ? i18n("Import checked") : i18n("Import status")
                        detail: bookmarkImport.message
                        divider: false
                    }
                    FileDialog {
                        id: bookmarkPicker
                        title: i18n("Choose a bookmark export")
                        nameFilters: [i18n("Bookmark HTML files") + " (*.html *.htm)"]
                        onAccepted: { bookmarkImport.reset(); bookmarkImport.source = selectedFile.toString() }
                    }
                }

                // Windows seals its saved passwords; moving them remains an explicit action.
                Caption {
                    tone: look
                    visible: fromWindows.visible
                    text: i18n("From Windows")
                }
                Card {
                    id: fromWindows
                    tone: look
                    readonly property var b: sheet.browserInfo
                    readonly property int count: b.count || 0
                    visible: count > 0
                    SettingRow {
                        tone: look
                        title: i18n("Passwords")
                        detail: i18n("Windows keeps them sealed, so they can't come over by themselves. In Windows, export them from Edge or Chrome (in its passwords settings) into Shared with Monet. Then in Zen, open about:logins, choose Import from a File, and delete the file once they're in.")
                        Pill {
                            tone: look
                            visible: (fromWindows.b.shared || "") !== ""
                            text: i18n("Show the folder")
                            onClicked: Qt.openUrlExternally("file://" + encodeURI(fromWindows.b.shared))
                        }
                    }
                }
            }
        }

        Component {
            id: accessibilityPage
            ColumnLayout {
                spacing: 20
                PageTitle {
                    tone: look
                    entry: sheet.entry("accessibility")
                    art: sheet.art
                    text: i18n("Accessibility")
                    detail: i18n("Make Monet easier to see, read and use.")
                }
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        visible: typeof sheet.accessInfo.scale === "number"
                        objectName: "search-size"
                        title: i18n("Size of everything")
                        detail: i18n("Text, pictures and windows, on every screen")
                        Segments {
                            tone: look
                            options: [100, 125, 150, 175, 200].map(s => [s, s + "%"])
                            current: sheet.accessInfo.scale
                            onPicked: value => sheet.access("scale", value)
                        }
                    }
                    SettingRow {
                        tone: look
                        divider: typeof sheet.accessInfo.scale === "number"
                        title: i18n("Pointer size")
                        objectName: "search-pointer"
                        Segments {
                            tone: look
                            options: [[24, i18n("Normal")], [36, i18n("Large")], [48, i18n("Larger")]]
                            current: sheet.accessInfo.cursor || 24
                            onPicked: value => sheet.access("cursor", value)
                        }
                    }
                    SettingRow {
                        tone: look
                        tappable: true
                        title: i18n("Reduce motion")
                        objectName: "search-motion"
                        detail: i18n("Things appear without sliding, fading or bouncing")
                        onTapped: sheet.access("reduced", sheet.accessInfo.reduced !== true)
                        Switch {
                            tone: look
                            active: sheet.accessInfo.reduced === true
                        }
                    }
                    SettingRow {
                        tone: look
                        visible: typeof sheet.accessInfo.reader === "boolean"
                        tappable: true
                        title: i18n("Screen reader")
                        detail: i18n("Reads aloud what's on the screen and what you type")
                        onTapped: sheet.access("reader", sheet.accessInfo.reader !== true)
                        Switch {
                            tone: look
                            active: sheet.accessInfo.reader === true
                        }
                    }
                    SettingRow {
                        tone: look
                        visible: typeof sheet.accessInfo.zoom === "boolean"
                        tappable: true
                        title: i18n("Magnifier")
                        detail: i18n("The Windows key and + zooms in where the pointer is, the Windows key and − zooms out")
                        onTapped: sheet.access("zoom", sheet.accessInfo.zoom !== true)
                        Switch {
                            tone: look
                            active: sheet.accessInfo.zoom === true
                        }
                    }
                }
                Pill {
                    tone: look
                    text: i18n("More accessibility settings…")
                    onClicked: sheet.ask("kde access")
                }
            }
        }

        Component {
            id: storagePage
            ColumnLayout {
                id: storageColumn
                // What fills the disk, each in a color of The Hours.
                readonly property var parts: [
                    ["games", i18n("Games"), "#F2552C"], ["apps", i18n("Apps"), "#5C88D0"],
                    ["files", i18n("Your files"), "#357F72"], ["system", i18n("Monet"), "#9C7BC0"]
                ]
                readonly property real total: sheet.storageInfo.total || 0
                // Emptying the Trash asks once more.
                property bool askingTrash: false
                spacing: 20
                PageTitle {
                    tone: look
                    entry: sheet.entry("storage")
                    art: sheet.art
                    text: i18n("Storage")
                    detail: i18n("What fills this PC, and room to make.")
                }
                Card {
                    tone: look
                    SettingRow {
                        objectName: "search-shared-files"
                        tone: look
                        divider: false
                        title: i18n("Windows files")
                        detail: sheet.windowsFiles.available
                            ? i18n("The shared folder opens in Files. In Windows, it is called Shared with Monet.")
                            : sheet.windowsFiles.state === "asleep"
                                ? i18n("Shut down Windows completely, then return to Monet to use the shared folder.")
                            : sheet.windowsFiles.state === "bitlocker"
                                ? i18n("Windows' drive is locked. Open its access settings to unlock it.")
                            : sheet.windowsFiles.state === "unclean"
                                ? i18n("Windows' drive needs checking. Start Windows and shut it down fully before trying again.")
                            : sheet.windowsFiles.state === "open"
                                ? i18n("The shared folder isn't available to this account.")
                            : sheet.windowsFiles.state === "no-bridge"
                                ? i18n("Start Windows once to finish setting up the shared folder.")
                            : i18n("Shared files become available after Windows is set up on this PC.")
                        Pill {
                            tone: look
                            text: sheet.windowsFiles.available ? i18n("Open folder") : i18n("Windows settings")
                            onClicked: {
                                if (sheet.windowsFiles.available)
                                    Qt.openUrlExternally("file://" + encodeURI(sheet.windowsFiles.path))
                                else sheet.open(sheet.windowsFiles.state === "bitlocker" ? "games#shared" : "windows")
                            }
                        }
                    }
                }
                Card {
                    tone: look
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.margins: 20
                        spacing: 12
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 10
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                text: storageColumn.total > 0 ? i18n("%1 free", sheet.bytes(sheet.storageInfo.free)) : i18n("Measuring…")
                                color: look.ink
                                font.family: "Fraunces 72pt SuperSoft"
                                font.weight: Font.Light
                                font.pixelSize: 32
                            }
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                Layout.alignment: Qt.AlignBaseline
                                visible: storageColumn.total > 0
                                text: i18n("of %1", sheet.bytes(storageColumn.total))
                                color: look.dim
                                font.pixelSize: 14
                            }
                        }
                        // The disk as one bar: each part its share, free space left plain.
                        Rounded {
                            Layout.fillWidth: true
                            Layout.preferredHeight: 14
                            radius: 7
                            Rectangle {
                                anchors.fill: parent
                                color: look.wash2
                            }
                            Row {
                                anchors.fill: parent
                                Repeater {
                                    model: storageColumn.parts
                                    Rectangle {
                                        required property var modelData
                                        width: parent.width * (sheet.storageInfo[modelData[0]] || 0) / Math.max(1, storageColumn.total)
                                        height: parent.height
                                        color: modelData[2]
                                        Behavior on width { NumberAnimation { duration: Math.round(400 * sheet.speed); easing.type: Easing.OutCubic } }
                                    }
                                }
                            }
                        }
                        Flow {
                            Layout.fillWidth: true
                            spacing: 18
                            visible: storageColumn.total > 0
                            Repeater {
                                model: storageColumn.parts
                                Row {
                                    required property var modelData
                                    spacing: 7
                                    Rectangle {
                                        anchors.verticalCenter: parent.verticalCenter
                                        width: 10
                                        height: 10
                                        radius: 5
                                        color: parent.modelData[2]
                                    }
                                    Text {
                                        horizontalAlignment: Text.AlignLeft
                                        text: parent.modelData[1] + "  " + sheet.bytes(sheet.storageInfo[parent.modelData[0]])
                                        color: look.dim
                                        font.pixelSize: 13
                                    }
                                }
                            }
                        }
                    }
                }
                Caption {
                    tone: look
                    text: i18n("Make room")
                }
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        title: i18n("Trash")
                        detail: storageColumn.askingTrash ? i18n("Everything in it is gone for good. Sure?")
                            : (sheet.storageInfo.trash || 0) > 0 ? sheet.bytes(sheet.storageInfo.trash) : i18n("Empty")
                        Row {
                            spacing: 8
                            Pill {
                                tone: look
                                visible: storageColumn.askingTrash
                                text: i18n("Keep it")
                                onClicked: storageColumn.askingTrash = false
                            }
                            Pill {
                                tone: look
                                visible: (sheet.storageInfo.trash || 0) > 0
                                text: storageColumn.askingTrash ? i18n("Empty for good") : i18n("Empty Trash")
                                onClicked: {
                                    if (storageColumn.askingTrash) {
                                        storageColumn.askingTrash = false
                                        sheet.emptyTrash()
                                    } else {
                                        storageColumn.askingTrash = true
                                    }
                                }
                            }
                        }
                    }
                    SettingRow {
                        tone: look
                        title: i18n("Downloads")
                        detail: (sheet.storageInfo.downloads || 0) > 0
                            ? i18n("%1 · look through them in Files", sheet.bytes(sheet.storageInfo.downloads)) : i18n("Empty")
                        Pill {
                            tone: look
                            visible: (sheet.storageInfo.downloadsPath || "") !== ""
                            text: i18n("Show")
                            onClicked: Qt.openUrlExternally("file://" + encodeURI(sheet.storageInfo.downloadsPath))
                        }
                    }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: i18n("What apps leave behind when they update is cleared away with each update, by itself.")
                    color: look.dim
                    font.pixelSize: 14
                    lineHeight: 1.3
                    wrapMode: Text.Wrap
                }
                // OneDrive in Files (monet-quick onedrive-connect: rclone, signed in once in the browser).
                Caption {
                    tone: look
                    visible: oneDriveCard.visible
                    text: i18n("In the cloud")
                }
                Card {
                    id: oneDriveCard
                    tone: look
                    readonly property var o: sheet.oneDrive
                    visible: o.here === true
                    SettingRow {
                        tone: look
                        divider: false
                        title: "OneDrive"
                        detail: sheet.oneDriveBusy === "connect" ? i18n("Sign in with Microsoft in the browser that opened. Settings carries on once you're in.")
                            : oneDriveCard.o.connected && oneDriveCard.o.total
                                ? i18n("In Files, with your places: %1 of %2 used. Files come down as you open them.", sheet.bytes(oneDriveCard.o.used || 0), sheet.bytes(oneDriveCard.o.total))
                            : oneDriveCard.o.connected ? i18n("In Files, with your places. Files come down as you open them.")
                            : sheet.oneDriveProblem ? i18n("OneDrive wasn't connected. Try again, and sign in with Microsoft in the browser.")
                            : i18n("Your OneDrive in Files, with your places, its files coming down as you open them. Sign in with Microsoft once, in the browser.")
                        Row {
                            spacing: 8
                            Pill {
                                tone: look
                                visible: oneDriveCard.o.connected === true
                                text: i18n("Show")
                                onClicked: Qt.openUrlExternally("file://" + encodeURI(oneDriveCard.o.path))
                            }
                            Pill {
                                tone: look
                                kind: oneDriveCard.o.connected ? "plain" : "lily"
                                enabledPill: sheet.oneDriveBusy === ""
                                text: sheet.oneDriveBusy === "connect" ? i18n("Signing in…")
                                    : sheet.oneDriveBusy === "disconnect" ? i18n("Disconnecting…")
                                    : oneDriveCard.o.connected ? i18n("Disconnect") : i18n("Connect")
                                onClicked: {
                                    const what = oneDriveCard.o.connected ? "disconnect" : "connect"
                                    sheet.oneDriveBusy = what
                                    sheet.oneDriveProblem = false
                                    sheet.ask("onedrive-" + what, out => {
                                        const done = sheet.json(out, { ok: false })
                                        sheet.oneDriveBusy = ""
                                        sheet.oneDriveProblem = what === "connect" && !done.ok && !sheet.oneDriveCancelled
                                        sheet.oneDriveCancelled = false
                                        sheet.oneDrive = done
                                    })
                                }
                            }
                            // The browser's sign-in can wait a long time: Cancel stops it.
                            Pill {
                                tone: look
                                visible: sheet.oneDriveBusy === "connect"
                                text: i18n("Cancel")
                                onClicked: {
                                    sheet.oneDriveCancelled = true
                                    sheet.ask("onedrive-cancel", () => {})
                                }
                            }
                        }
                    }
                }
            }
        }

        Component {
            id: backupsPage
            ColumnLayout {
                id: backupsColumn
                readonly property var versions: sheet.earlier.versions || []
                spacing: 20
                // A copy in progress: how far along, every two seconds.
                Timer {
                    interval: 2000
                    repeat: true
                    running: sheet.backup.copying === true
                    onTriggered: sheet.ask("backup", out => sheet.backup = sheet.json(out, sheet.backup))
                }
                PageTitle {
                    tone: look
                    entry: sheet.entry("backups")
                    art: sheet.art
                    text: i18n("Backups")
                    detail: sheet.backup.versions === false ? i18n("Copies of your files, for when something goes wrong.")
                        : i18n("Monet keeps your files as they were, every hour.")
                }

                // From Files' menu: this file's earlier versions.
                Caption {
                    tone: look
                    visible: (sheet.earlier.file || "") !== ""
                    text: i18n("Earlier versions of %1", sheet.earlier.name || "")
                }
                Card {
                    tone: look
                    visible: (sheet.earlier.file || "") !== ""
                    SettingRow {
                        tone: look
                        divider: false
                        visible: backupsColumn.versions.length === 0
                        title: i18n("No earlier versions yet")
                        detail: i18n("Monet keeps one every hour from now on.")
                    }
                    Repeater {
                        model: backupsColumn.versions.slice(0, 12)
                        SettingRow {
                            required property var modelData
                            required property int index
                            tone: look
                            divider: index > 0
                            title: sheet.moment(modelData.time)
                            detail: modelData.folder ? i18n("Folder") : sheet.bytes(modelData.size)
                            Row {
                                spacing: 8
                                Pill {
                                    tone: look
                                    text: i18n("Show")
                                    onClicked: sheet.ask("version-open " + index)
                                }
                                Pill {
                                    tone: look
                                    text: i18n("Put back")
                                    onClicked: sheet.ask("put-back " + index)
                                }
                            }
                        }
                    }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    visible: (sheet.earlier.file || "") !== "" && backupsColumn.versions.length > 0
                    text: i18n("Put back keeps both: the earlier version goes beside it, with its time in the name.")
                    color: look.dim
                    font.pixelSize: 14
                    lineHeight: 1.3
                    wrapMode: Text.Wrap
                }
                Pill {
                    tone: look
                    visible: (sheet.earlier.file || "") !== ""
                    text: i18n("Done")
                    onClicked: sheet.ask("versions-done", () => sheet.earlier = {})
                }

                Caption {
                    tone: look
                    text: i18n("Earlier versions")
                }
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        tappable: true
                        title: i18n("Keep earlier versions")
                        detail: i18n("Every hour, for two months. Only what changed takes room.")
                        onTapped: {
                            const on = sheet.backup.versions === false
                            sheet.backup = sheet.changed(sheet.backup, ["versions"], on)
                            sheet.ask("keep " + (on ? "on" : "off"), out => sheet.backup = sheet.json(out, sheet.backup))
                        }
                        Switch {
                            tone: look
                            active: sheet.backup.versions !== false
                        }
                    }
                    SettingRow {
                        tone: look
                        visible: sheet.backup.versions !== false
                        title: i18n("Your files as they were")
                        detail: (sheet.backup.kept || 0) > 0 ? i18n("Opens in Files: copy back what you need.")
                            : i18n("The first one is kept within the hour.")
                        Row {
                            spacing: 8
                            Repeater {
                                model: [["hour", i18n("An hour ago")], ["day", i18n("Yesterday")], ["week", i18n("Last week")]]
                                Pill {
                                    required property var modelData
                                    readonly property var snapshot: (sheet.backup.lookBack || {})[modelData[0]]
                                    tone: look
                                    visible: !!snapshot
                                    text: modelData[1]
                                    onClicked: sheet.ask("backup-open " + snapshot.time)
                                }
                            }
                        }
                    }
                }

                Caption {
                    tone: look
                    text: i18n("A copy on a drive")
                }
                Card {
                    tone: look
                    // The drive chosen for copies.
                    SettingRow {
                        tone: look
                        divider: false
                        visible: !!sheet.backup.drive
                        title: sheet.backup.label || i18n("Your backup drive")
                        detail: sheet.backup.copying ? i18n("Copying… %1%", sheet.backup.percent || 0)
                            : (sheet.backup.error || "") !== "" ? sheet.backup.error
                            : sheet.backup.last ? i18n("Last copy: %1", sheet.moment(sheet.backup.last))
                            : sheet.backup.plugged ? i18n("Not copied yet") : i18n("Plug it in to copy your files")
                        Row {
                            spacing: 8
                            Pill {
                                tone: look
                                visible: sheet.backup.plugged === true && !sheet.backup.copying
                                text: i18n("Copy now")
                                onClicked: {
                                    sheet.backup = sheet.changed(sheet.backup, ["copying"], true)
                                    sheet.ask("backup-now")
                                }
                            }
                            Pill {
                                tone: look
                                visible: sheet.backup.plugged === true
                                text: i18n("Open")
                                onClicked: sheet.ask("backup-open-drive")
                            }
                        }
                    }
                    SettingRow {
                        tone: look
                        visible: !!sheet.backup.drive
                        title: i18n("Stop copying to this drive")
                        detail: i18n("What's on it stays there")
                        Pill {
                            tone: look
                            text: i18n("Stop")
                            onClicked: sheet.ask("backup-drive none", out => sheet.backup = sheet.json(out, sheet.backup))
                        }
                    }
                    // No drive chosen: the ones plugged in, or how to start.
                    Repeater {
                        model: sheet.backup.drive ? [] : (sheet.backup.drives || [])
                        SettingRow {
                            required property var modelData
                            required property int index
                            tone: look
                            divider: index > 0
                            title: modelData.label || i18n("USB drive")
                            detail: sheet.bytes(modelData.size)
                            Pill {
                                tone: look
                                text: i18n("Copy to this drive")
                                onClicked: sheet.ask("backup-drive " + modelData.uuid, out => sheet.backup = sheet.json(out, sheet.backup))
                            }
                        }
                    }
                    SettingRow {
                        tone: look
                        divider: false
                        visible: !sheet.backup.drive && (sheet.backup.drives || []).length === 0
                        title: i18n("Plug in a USB drive")
                        detail: i18n("Monet copies your files to it whenever it's plugged in, at most once a day.")
                    }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: i18n("Games aren't copied: Steam and the other stores download them again. Neither is the Trash.")
                    color: look.dim
                    font.pixelSize: 14
                    lineHeight: 1.3
                    wrapMode: Text.Wrap
                }
            }
        }

        Component {
            id: privacyPage
            ColumnLayout {
                id: privacyColumn
                // Forgetting recent files asks once more.
                property bool askingForget: false
                // Said once it's done, until the page is left.
                property bool forgot: false
                spacing: 20
                PageTitle {
                    tone: look
                    entry: sheet.entry("privacy")
                    art: sheet.art
                    text: i18n("Lock & Privacy")
                    detail: sheet.privacyInfo.lockAfter === 0 ? i18n("The screen doesn't lock by itself.")
                        : sheet.privacyInfo.lockAfter > 0 ? i18np("The screen locks after %1 minute away.",
                                                                  "The screen locks after %1 minutes away.", sheet.privacyInfo.lockAfter)
                        : i18n("Who can get in, and what Monet remembers.")
                }
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        title: i18n("Lock the screen")
                        detail: i18n("When you've been away this long")
                        Segments {
                            tone: look
                            options: [[1, i18n("1 min")], [5, i18n("5 min")], [15, i18n("15 min")], [30, i18n("30 min")],
                                      [0, i18n("Never")]]
                            current: typeof sheet.privacyInfo.lockAfter === "number" ? sheet.privacyInfo.lockAfter : 5
                            onPicked: value => sheet.privacy("lockAfter", value)
                        }
                    }
                    SettingRow {
                        tone: look
                        tappable: true
                        title: i18n("Ask for the password after sleep")
                        detail: i18n("Waking the PC shows the lock screen")
                        onTapped: sheet.privacy("lockOnResume", sheet.privacyInfo.lockOnResume === false)
                        Switch {
                            tone: look
                            active: sheet.privacyInfo.lockOnResume !== false
                        }
                    }
                    SettingRow {
                        tone: look
                        title: i18n("Lock now")
                        detail: i18n("Or press the Windows key and L")
                        Pill {
                            tone: look
                            text: i18n("Lock")
                            onClicked: sheet.ask("lock-now")
                        }
                    }
                    // With a fingerprint reader: a finger unlocks and says yes to administrator
                    // questions. KDE's Accounts page sets one up (Configure Fingerprint).
                    SettingRow {
                        tone: look
                        visible: !!sheet.privacyInfo.fingerprint
                        title: i18n("Fingerprint")
                        detail: sheet.privacyInfo.fingerprint && sheet.privacyInfo.fingerprint.enrolled
                            ? i18n("Your finger unlocks the screen and says yes when Monet asks for your password")
                            : i18n("Set up a finger to unlock the screen and say yes when Monet asks for your password")
                        Pill {
                            tone: look
                            kind: sheet.privacyInfo.fingerprint && sheet.privacyInfo.fingerprint.enrolled ? "plain" : "lily"
                            text: sheet.privacyInfo.fingerprint && sheet.privacyInfo.fingerprint.enrolled ? i18n("Change…") : i18n("Set up…")
                            onClicked: sheet.ask("kde users")
                        }
                    }
                }
                Caption {
                    tone: look
                    text: i18n("What Monet remembers")
                }
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        tappable: true
                        title: i18n("Remember recent files")
                        detail: i18n("Files and the menu show what you opened lately")
                        onTapped: sheet.privacy("remember", sheet.privacyInfo.remember === false)
                        Switch {
                            tone: look
                            active: sheet.privacyInfo.remember !== false
                        }
                    }
                    SettingRow {
                        tone: look
                        title: i18n("Forget recent files")
                        detail: privacyColumn.askingForget ? i18n("The list of what you opened is cleared. Your files stay. Sure?")
                            : privacyColumn.forgot ? i18n("Cleared. Your files are still there.")
                            : i18n("Clears the list, not the files")
                        Row {
                            spacing: 8
                            Pill {
                                tone: look
                                visible: privacyColumn.askingForget
                                text: i18n("Keep it")
                                onClicked: privacyColumn.askingForget = false
                            }
                            Pill {
                                tone: look
                                text: privacyColumn.askingForget ? i18n("Forget") : i18n("Forget…")
                                onClicked: {
                                    if (privacyColumn.askingForget) {
                                        privacyColumn.askingForget = false
                                        sheet.ask("forget-recent", () => privacyColumn.forgot = true)
                                    } else {
                                        privacyColumn.askingForget = true
                                    }
                                }
                            }
                        }
                    }
                }
                Row {
                    spacing: 8
                    Pill {
                        tone: look
                        text: i18n("More lock screen settings…")
                        onClicked: sheet.ask("kde screenlocker")
                    }
                    Pill {
                        tone: look
                        text: i18n("More recent files settings…")
                        onClicked: sheet.ask("kde recentfiles")
                    }
                }
            }
        }

        Component {
            id: printersPage
            ColumnLayout {
                id: printersColumn
                readonly property var found: sheet.printerInfo.printers || []
                spacing: 20
                PageTitle {
                    tone: look
                    entry: sheet.entry("printers")
                    art: sheet.art
                    text: i18n("Printers")
                    detail: printersColumn.found.length === 0 ? i18n("Printers on your network show up by themselves.")
                        : i18np("%1 printer", "%1 printers", printersColumn.found.length)
                }
                Card {
                    tone: look
                    Repeater {
                        model: printersColumn.found
                        SettingRow {
                            id: printerRow
                            required property var modelData
                            required property int index
                            tone: look
                            divider: index > 0
                            title: modelData.label
                            detail: [modelData.default ? i18n("Your default") : "",
                                     modelData.state === "printing" ? i18n("Printing") : modelData.state === "off" ? i18n("Turned off")
                                         : i18n("Ready"),
                                     modelData.jobs > 0 ? i18np("%1 waiting", "%1 waiting", modelData.jobs) : ""]
                                    .filter(s => s !== "").join(" · ")
                            Pill {
                                tone: look
                                visible: !printerRow.modelData.default
                                text: i18n("Make default")
                                onClicked: sheet.printerDefault(printerRow.modelData.name)
                            }
                        }
                    }
                    SettingRow {
                        tone: look
                        divider: printersColumn.found.length > 0
                        title: printersColumn.found.length > 0 ? i18n("Another printer") : i18n("No printers yet")
                        detail: i18n("Turn it on and join it to your Wi-Fi: Monet finds most printers by itself")
                        Pill {
                            tone: look
                            text: i18n("Add…")
                            onClicked: sheet.ask("kde printers")
                        }
                    }
                }
                Pill {
                    tone: look
                    text: i18n("More printer settings…")
                    onClicked: sheet.ask("kde printers")
                }
            }
        }

        Component {
            id: gamesPage
            ColumnLayout {
                readonly property var pads: sheet.gameInfo.controllers || []
                readonly property var libraries: sheet.gameInfo.libraries || []
                id: gamesColumn
                spacing: 20
                PageTitle {
                    tone: look
                    entry: sheet.entry("games")
                    art: sheet.art
                    text: i18n("Games & Controllers")
                    detail: gamesColumn.pads.length > 0
                        ? i18np("%1 controller connected", "%1 controllers connected", gamesColumn.pads.length)
                        : i18n("Your controllers, and where your games are kept.")
                }
                Caption {
                    tone: look
                    text: i18n("Controllers")
                }
                Card {
                    tone: look
                    Repeater {
                        model: gamesColumn.pads
                        SettingRow {
                            required property var modelData
                            required property int index
                            tone: look
                            divider: index > 0
                            title: modelData.name
                            detail: modelData.battery === null ? (modelData.wireless ? i18n("Connected") : i18nc("a controller, connected by its cable", "Plugged in"))
                                : modelData.charging ? i18n("%1% · charging", modelData.battery)
                                : i18n("%1% battery", modelData.battery)
                        }
                    }
                    SettingRow {
                        tone: look
                        divider: gamesColumn.pads.length > 0
                        title: gamesColumn.pads.length > 0 ? i18n("Another controller") : i18n("No controller connected")
                        detail: i18n("Plug one in, or pair one over Bluetooth")
                        Row {
                            spacing: 8
                            Pill {
                                tone: look
                                visible: sheet.gameInfo.pair === true
                                text: i18n("Pair…")
                                onClicked: sheet.ask("pair-controller")
                            }
                            Pill {
                                tone: look
                                text: i18n("Test buttons…")
                                onClicked: sheet.ask("kde gamecontroller")
                            }
                        }
                    }
                }
                Caption {
                    tone: look
                    visible: typeof sheet.gameInfo.overlay === "boolean"
                    text: i18n("While you play")
                }
                Card {
                    tone: look
                    visible: typeof sheet.gameInfo.overlay === "boolean" || typeof sheet.gameInfo.replay === "boolean"
                    SettingRow {
                        tone: look
                        divider: false
                        visible: typeof sheet.gameInfo.overlay === "boolean"
                        tappable: true
                        title: i18n("Performance overlay")
                        detail: i18n("Frames per second and what the PC is doing, over every game, from your next sign-in. Right Shift+F12 hides it while you play.")
                        onTapped: sheet.overlay(sheet.gameInfo.overlay !== true)
                        Switch {
                            tone: look
                            active: sheet.gameInfo.overlay === true
                        }
                    }
                    // As Xbox Game Bar has it: the last 30 seconds, kept to save.
                    SettingRow {
                        tone: look
                        divider: typeof sheet.gameInfo.overlay === "boolean"
                        visible: typeof sheet.gameInfo.replay === "boolean"
                        tappable: !sheet.replaying
                        title: i18n("Save the last 30 seconds")
                        detail: sheet.replaying ? i18n("Getting it ready…")
                            : sheet.replayFailed ? i18n("It couldn't be installed. Check the internet connection, then try again.")
                            : i18n("Windows key + Alt + G keeps the last 30 seconds on screen in Videos. The first time, choose the screen to record.")
                        onTapped: sheet.replay(sheet.gameInfo.replay !== true)
                        Switch {
                            tone: look
                            active: sheet.gameInfo.replay === true
                        }
                    }
                }
                // Windows' Games folder: one copy of a game that Steam plays on both sides
                // (monet-windows-drive opens it when Windows' drive is safe to write).
                Caption {
                    tone: look
                    visible: sharedCard.visible
                    text: i18n("Shared with Windows")
                }
                Card {
                    id: sharedCard
                    objectName: "search-shared"
                    tone: look
                    readonly property var s: sheet.gameInfo.shared || {}
                    visible: ["open", "asleep", "unclean", "bitlocker", "failed", "unknown"].indexOf(s.state) !== -1
                             || (s.state === "no-bridge" && s.unlocked === true)
                    SettingRow {
                        tone: look
                        divider: false
                        title: sharedCard.s.state === "open" && sharedCard.s.steam ? i18n("Windows games")
                            : i18n("Install each game once")
                        detail: sharedCard.s.state === "asleep" ? i18n("Windows didn't shut down fully, so its drive isn't open to Monet this time. It is again after your next trip to Windows.")
                            : sharedCard.s.state === "unclean" ? i18n("Windows wants to check its drive first. It does that by itself the next time it starts.")
                            : sharedCard.s.state === "bitlocker" && sharedCard.s.handover === true
                                ? i18n("Windows' drive is encrypted with BitLocker. Start Windows once, and Monet Bridge hands its recovery key over: Monet opens it by itself from then on. Or type the key here.")
                            : sharedCard.s.state === "bitlocker" ? i18n("Windows' drive is encrypted with BitLocker. Type its recovery key once, and Monet opens it at every start, for games, files and Wi-Fi in both.")
                            : sharedCard.s.state === "no-bridge" ? i18n("Windows' drive is open. Monet Bridge installs itself the next time Windows starts, and from then on games, files and Wi-Fi work in both.")
                            : sharedCard.s.state !== "open" ? i18n("Windows' drive couldn't be opened this time.")
                            : sharedCard.s.steam ? sheet.library(sharedCard.s) + ". " + i18n("Steam here and Steam in Windows both play from it. When you install a game, choose Windows games, and it's ready on both.")
                            : sharedCard.s.mine ? i18n("Steam here can keep games in Windows' Games folder, where Windows plays them too. Steam closes for a moment to add it.")
                            : i18n("Steam keeps games for both in Windows' Games folder for the person who set up this PC.")
                        Pill {
                            tone: look
                            visible: sharedCard.s.state === "open" && sharedCard.s.mine === true && sharedCard.s.steam !== true
                            text: sheet.sharing ? i18n("Adding…") : i18n("Add to Steam")
                            enabledPill: !sheet.sharing
                            onClicked: {
                                sheet.sharing = true
                                sheet.ask("steam-share now", out => {
                                    sheet.sharing = false
                                    sheet.gameInfo = sheet.changed(sheet.gameInfo, ["shared"], sheet.json(out, sharedCard.s))
                                })
                            }
                        }
                        Pill {
                            tone: look
                            visible: sharedCard.s.state === "open" && sharedCard.s.steam === true
                            text: i18n("Show")
                            onClicked: Qt.openUrlExternally("file://" + encodeURI(sharedCard.s.path + "/steamapps/common"))
                        }
                    }
                    // BitLocker: its recovery key, typed once; monet-windows-drive opens the drive with it at
                    // every start, the key sealed by the PC's security chip.
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.leftMargin: 18
                        Layout.rightMargin: 18
                        Layout.bottomMargin: 16
                        visible: sharedCard.s.state === "bitlocker"
                        spacing: 8
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Field {
                                id: recoveryKey
                                tone: look
                                hint: i18n("Recovery key, 48 digits")
                                onAccepted: sheet.unlockWindows(text)
                            }
                            Pill {
                                tone: look
                                kind: "lily"
                                text: sheet.unlocking ? i18n("Unlocking…") : i18n("Unlock")
                                enabledPill: !sheet.unlocking && recoveryKey.text.trim() !== ""
                                onClicked: sheet.unlockWindows(recoveryKey.text)
                            }
                        }
                        Text {
                            Layout.fillWidth: true
                            text: sheet.unlockProblem !== "" ? sheet.unlockProblem
                                : i18n("It's in your Microsoft account, or in Windows: search for Manage BitLocker, then Back up your recovery key.")
                            color: sheet.unlockProblem !== "" ? "#E0603A" : look.dim
                            font.pixelSize: 13
                            wrapMode: Text.Wrap
                        }
                        Pill {
                            tone: look
                            text: i18n("Find my key")
                            onClicked: Qt.openUrlExternally("https://aka.ms/myrecoverykey")
                        }
                    }
                    // Heroic's games go there too: Epic's launcher in Windows takes them over, GOG's start by themselves.
                    SettingRow {
                        tone: look
                        visible: sharedCard.s.state === "open" && sharedCard.s.heroic === true
                        title: i18n("Epic and GOG games")
                        detail: i18n("In Heroic, choose Windows games as the folder when you install one, and Windows plays it too: Epic's launcher there takes it over, and GOG's games start by themselves.")
                    }
                    // No Heroic yet: one tap gets it from Flathub, and opens it to sign in.
                    SettingRow {
                        tone: look
                        visible: sharedCard.s.state === "open" && sharedCard.s.heroic === false
                        title: i18n("Epic and GOG games")
                        detail: i18n("Get Heroic for your Epic and GOG games. One you install in Windows games plays in Windows too.")
                        Pill {
                            tone: look
                            text: sheet.gettingHeroic ? i18n("Getting Heroic…") : i18n("Get Heroic")
                            enabledPill: !sheet.gettingHeroic
                            onClicked: {
                                sheet.gettingHeroic = true
                                sheet.ask("get-heroic", out => {
                                    sheet.gettingHeroic = false
                                    sheet.gameInfo = sheet.changed(sheet.gameInfo, ["shared"], sheet.json(out, sharedCard.s))
                                })
                            }
                        }
                    }
                    // Battle.net's, Ubisoft's and EA's launchers in Monet (Lutris) have Windows games as drive W:.
                    SettingRow {
                        tone: look
                        visible: sharedCard.s.state === "open"
                        title: i18n("Battle.net, Ubisoft and EA games")
                        detail: i18n("In Battle.net, Ubisoft Connect or the EA app here, install to drive W: (Windows games), and Windows plays it too. The first time, its launcher there may ask where it is: Play says what to pick.")
                        // Got through Lutris here (Flathub's, if there's none); open once it's here.
                        Row {
                            spacing: 8
                            Repeater {
                                model: [["battlenet", "Battle.net"], ["ubisoft", "Ubisoft Connect"], ["ea", "EA app"]]
                                Pill {
                                    required property var modelData
                                    tone: look
                                    text: sheet.gettingLauncher === modelData[0] ? i18n("Getting %1…", modelData[1])
                                        : sharedCard.s[modelData[0]] === true ? i18n("Open %1", modelData[1])
                                        : i18n("Get %1", modelData[1])
                                    enabledPill: sheet.gettingLauncher === ""
                                    onClicked: {
                                        sheet.gettingLauncher = modelData[0]
                                        sheet.ask("get-launcher " + modelData[0], out => {
                                            sheet.gettingLauncher = ""
                                            sheet.gameInfo = sheet.changed(sheet.gameInfo, ["shared"], sheet.json(out, sharedCard.s))
                                        })
                                    }
                                }
                            }
                        }
                    }
                    // Downloads, mods and installers saved once, for both.
                    SettingRow {
                        tone: look
                        visible: sharedCard.s.state === "open" && !!sharedCard.s.files
                        title: i18n("Shared with Windows")
                        detail: i18n("A folder Windows has too, as Shared with Monet: save a download, a mod or an installer there once, and it's in both. Files lists it with your places.")
                        Pill {
                            tone: look
                            text: i18n("Show")
                            onClicked: Qt.openUrlExternally("file://" + encodeURI(sharedCard.s.files))
                        }
                    }
                }
                Caption {
                    tone: look
                    text: i18n("Where your games are")
                }
                Card {
                    tone: look
                    Repeater {
                        model: gamesColumn.libraries
                        SettingRow {
                            id: libraryRow
                            required property var modelData
                            required property int index
                            tone: look
                            divider: index > 0
                            title: modelData.name
                            detail: sheet.library(modelData)
                            Pill {
                                tone: look
                                text: i18n("Show")
                                onClicked: Qt.openUrlExternally("file://" + encodeURI(libraryRow.modelData.path))
                            }
                        }
                    }
                    SettingRow {
                        tone: look
                        divider: false
                        visible: gamesColumn.libraries.length === 0
                        title: i18n("No games yet")
                        detail: i18n("Steam, Heroic and Lutris keep theirs here once you install one")
                    }
                }
                // Games installed here whose anti-cheat only lets them run on Windows.
                Caption {
                    tone: look
                    visible: (sheet.gameMarks.blocked || []).length > 0
                    text: i18n("Needs Windows")
                }
                Card {
                    tone: look
                    visible: (sheet.gameMarks.blocked || []).length > 0
                    Repeater {
                        model: sheet.gameMarks.blocked || []
                        SettingRow {
                            id: blockedRow
                            required property var modelData
                            required property int index
                            tone: look
                            divider: index > 0
                            title: modelData.name
                            detail: modelData.shared ? i18n("Its anti-cheat only allows Windows. It's in Windows games, ready there.")
                                : modelData.onWindows ? i18n("Its anti-cheat only allows Windows. It's there too.")
                                : (sheet.gameInfo.shared || {}).steam ? i18n("Its anti-cheat only allows Windows. In Steam, move it to Windows games (Properties, Installed Files, Move install folder), and it's ready there.")
                                : i18n("Its anti-cheat only allows Windows. Install it in Windows' Steam to play.")
                            Pill {
                                tone: look
                                visible: blockedRow.modelData.onWindows === true
                                text: i18n("Play on Windows…")
                                onClicked: {
                                    sheet.page = "windows"
                                    sheet.asking = ({ id: "steam:" + blockedRow.modelData.id, name: blockedRow.modelData.name })
                                }
                            }
                        }
                    }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    visible: (sheet.gameMarks.blocked || []).length > 0
                    text: i18n("Which games need Windows comes from AreWeAntiCheatYet and ProtonDB.")
                    color: look.dim
                    font.pixelSize: 13
                    wrapMode: Text.Wrap
                }
                Pill {
                    tone: look
                    text: i18n("More controller settings…")
                    onClicked: sheet.ask("kde gamecontroller")
                }
            }
        }

        // Security: one look at what keeps this PC safe, each with what would fix it. Monet only
        // looks here (monet-quick security); a fix that needs an administrator asks for the password.
        Component {
            id: securityPage
            ColumnLayout {
                spacing: 20
                readonly property var s: sheet.safety
                readonly property int problems: sheet.securityProblems()
                PageTitle {
                    tone: look
                    entry: sheet.entry("security")
                    art: sheet.art
                    text: i18n("Security")
                    detail: parent.s.secureBoot === undefined ? i18n("Looking…")
                        : parent.problems === 0 ? i18n("Your PC is protected.")
                        : i18np("One thing to look at.", "%1 things to look at.", parent.problems)
                }
                Card {
                    id: safetyCard
                    tone: look
                    readonly property var s: sheet.safety
                    // Secure Boot: only signed software starts. Before it goes on, the firmware has
                    // to trust Monet's key (its blue screen), or Monet wouldn't start.
                    SettingRow {
                        id: bootRow
                        tone: look
                        title: i18n("Secure Boot")
                        readonly property bool needsKey: safetyCard.s.secureBoot === "off" && safetyCard.s.keyTrusted !== true
                        detail: safetyCard.s.secureBoot === "on" ? i18n("On: only software signed by its makers starts with the PC.")
                            : safetyCard.s.secureBoot === "" ? i18n("This PC didn't start in UEFI mode, so Secure Boot can't be on.")
                            : safetyCard.s.secureBoot === undefined ? ""
                            : sheet.keyAsked ? i18n("At the next restart a blue screen asks to trust Monet: choose Enroll MOK, Continue and Yes, type monetsetup and choose Reboot. Then turn Secure Boot on in the firmware settings.")
                            : bootRow.needsKey ? i18n("Off. Before it goes on, the PC has to trust Monet, or Monet won't start: a blue screen asks once, at the next restart.")
                            : sheet.askingFirmwareSetup ? i18n("Your PC restarts into its firmware settings. Find Secure Boot (often under Boot or Security), turn it on, then save and exit.")
                            : i18n("Off. Games with anti-cheat in Windows need it too. It's turned on in the PC's firmware settings.")
                        lead: Mark {
                            tone: look
                            known: safetyCard.s.secureBoot === "on" || safetyCard.s.secureBoot === "off"
                            good: safetyCard.s.secureBoot === "on"
                        }
                        Row {
                            spacing: 8
                            visible: safetyCard.s.secureBoot === "off"
                            Pill {
                                tone: look
                                visible: sheet.askingFirmwareSetup && !sheet.keyAsked && !bootRow.needsKey
                                text: i18n("Cancel")
                                onClicked: sheet.askingFirmwareSetup = false
                            }
                            Pill {
                                tone: look
                                kind: sheet.askingFirmwareSetup || sheet.keyAsked ? "sun" : "plain"
                                enabledPill: sheet.securityFixing === ""
                                text: sheet.securityFixing === "trust-key" ? i18n("Asking…")
                                    : sheet.keyAsked || sheet.askingFirmwareSetup ? i18n("Restart")
                                    : bootRow.needsKey ? i18n("Trust Monet…")
                                    : i18n("Firmware settings…")
                                onClicked: {
                                    if (sheet.keyAsked) {
                                        sheet.ask("restart")
                                    } else if (bootRow.needsKey) {
                                        sheet.fixSecurity("trust-key")
                                    } else if (sheet.askingFirmwareSetup) {
                                        sheet.ask("firmware-setup")
                                    } else {
                                        sheet.askingFirmwareSetup = true
                                    }
                                }
                            }
                        }
                    }
                    SettingRow {
                        tone: look
                        title: i18n("Encryption")
                        detail: safetyCard.s.encrypted === true ? i18n("On: only this PC can read Monet's disk.")
                            : safetyCard.s.encrypted === false ? i18n("Off: someone who takes the disk out can read your files. Monet Setup encrypts the disk when it installs Monet.")
                            : safetyCard.s.secureBoot === undefined ? "" : i18n("Monet couldn't tell.")
                        lead: Mark {
                            tone: look
                            known: typeof safetyCard.s.encrypted === "boolean"
                            good: safetyCard.s.encrypted === true
                        }
                    }
                    SettingRow {
                        tone: look
                        title: i18n("Firewall")
                        detail: safetyCard.s.firewall === "on" && safetyCard.s.firewallStrict === true
                                ? i18n("On: only what Monet uses comes in from the network.")
                            : safetyCard.s.firewall === "on" && safetyCard.s.firewallStrict === false
                                ? i18n("On, with the system's usual openings for the network.")
                            : safetyCard.s.firewall === "on" ? i18n("On: connections from the network go through it first.")
                            : safetyCard.s.firewall === "off" ? i18n("Off: anything on the network can try to reach this PC.")
                            : safetyCard.s.firewall === "" ? i18n("This Monet has no firewall.") : ""
                        lead: Mark {
                            tone: look
                            known: safetyCard.s.firewall === "on" || safetyCard.s.firewall === "off"
                            good: safetyCard.s.firewall === "on"
                        }
                        Pill {
                            tone: look
                            visible: safetyCard.s.firewall === "off"
                            enabledPill: sheet.securityFixing === ""
                            text: sheet.securityFixing === "firewall-on" ? i18n("Turning on…") : i18n("Turn on")
                            onClicked: sheet.fixSecurity("firewall-on")
                        }
                    }
                    // Monet's zone (linux/firewalld/monet.xml) or the system's own; asks for the password.
                    SettingRow {
                        tone: look
                        strong: false
                        tappable: sheet.securityFixing === ""
                        visible: safetyCard.s.firewall === "on" && typeof safetyCard.s.firewallStrict === "boolean"
                        title: i18n("Only what Monet uses comes in")
                        detail: i18n("The phone, Steam's Remote Play and game transfers on this network, and finding printers. Games you host and other apps can be let in below.")
                        onTapped: sheet.fixSecurity("firewall-strict " + (safetyCard.s.firewallStrict ? "off" : "on"))
                        Switch {
                            tone: look
                            active: safetyCard.s.firewallStrict === true
                        }
                    }
                    SettingRow {
                        tone: look
                        title: i18n("Updates")
                        detail: safetyCard.s.autoUpdates === false ? i18n("Only when you ask, so fixes for security holes wait until then.")
                            : safetyCard.s.updateWaiting === true ? i18n("An update is ready. It's used from the next restart.")
                            : safetyCard.s.autoUpdates === true ? i18n("Monet and your apps update by themselves, with every fix for security holes.") : ""
                        lead: Mark {
                            tone: look
                            known: typeof safetyCard.s.autoUpdates === "boolean"
                            good: safetyCard.s.autoUpdates === true && safetyCard.s.updateWaiting !== true
                        }
                        Pill {
                            tone: look
                            visible: safetyCard.s.autoUpdates === false || safetyCard.s.updateWaiting === true
                            enabledPill: sheet.securityFixing === ""
                            text: safetyCard.s.autoUpdates === false ? i18n("Turn on") : i18n("Restart")
                            onClicked: {
                                if (safetyCard.s.autoUpdates === false) {
                                    sheet.securityFixing = "updates"
                                    sheet.ask("auto-updates on", () => { sheet.securityFixing = ""; sheet.loadSecurity() })
                                } else {
                                    sheet.ask("restart")
                                }
                            }
                        }
                    }
                    SettingRow {
                        tone: look
                        title: i18n("Firmware")
                        detail: sheet.firmwareState === "none" ? i18n("Up to date: this PC's own parts have no updates from their makers.")
                            : sheet.firmwareState === "available" ? sheet.firmwareTitle() + ". " + sheet.firmwareDetail()
                            : sheet.firmwareState === "checking" || sheet.firmwareState === "" ? i18n("Looking for updates for this PC's own parts…")
                            : sheet.firmwareDetail()
                        lead: Mark {
                            tone: look
                            known: sheet.firmwareState !== "checking" && sheet.firmwareState !== "" && sheet.firmwareState !== "failed"
                            good: sheet.firmwareState === "none" || (sheet.firmwareState === "done" && !sheet.firmwareRestart)
                        }
                        Pill {
                            tone: look
                            visible: sheet.firmwareState === "available" || sheet.firmwareState === "installing"
                                || sheet.firmwareState === "failed" || (sheet.firmwareState === "done" && sheet.firmwareRestart)
                            enabledPill: sheet.firmwareState !== "installing" && (sheet.firmwareState !== "available" || sheet.firmware.some(f => !f.blocked))
                            text: sheet.firmwareState === "installing" ? i18n("Installing…")
                                : sheet.firmwareState === "done" ? i18n("Restart now")
                                : sheet.firmwareState === "failed" ? i18n("Try again")
                                : i18n("Install")
                            onClicked: sheet.firmwareState === "done" ? sheet.ask("restart")
                                : sheet.firmwareState === "failed" ? sheet.checkFirmware()
                                : sheet.installFirmware()
                        }
                    }
                    SettingRow {
                        tone: look
                        divider: false
                        title: i18n("Backups")
                        detail: safetyCard.s.versions === false ? i18n("Off: a file deleted or changed by mistake can't be brought back.")
                            : safetyCard.s.versions === true && safetyCard.s.drive ? i18n("Earlier versions of your files every hour, and copies on %1.", safetyCard.s.drive)
                            : safetyCard.s.versions === true ? i18n("Earlier versions of your files every hour. Copies on a USB drive keep them safe from a broken disk too.")
                            : ""
                        lead: Mark {
                            tone: look
                            known: typeof safetyCard.s.versions === "boolean"
                            good: safetyCard.s.versions === true
                        }
                        Pill {
                            tone: look
                            visible: safetyCard.s.versions === false || (safetyCard.s.versions === true && !safetyCard.s.drive)
                            enabledPill: sheet.securityFixing === ""
                            text: safetyCard.s.versions === false ? (sheet.securityFixing === "keep" ? i18n("Turning on…") : i18n("Turn on"))
                                : i18n("Add a drive…")
                            onClicked: {
                                if (safetyCard.s.versions === false) {
                                    sheet.securityFixing = "keep"
                                    sheet.ask("keep on", () => { sheet.securityFixing = ""; sheet.loadSecurity() })
                                } else {
                                    sheet.page = "backups"
                                }
                            }
                        }
                    }
                }
                // What Monet's zone keeps out by default, let in one app at a time (monet-secure
                // firewall-allow: a fixed set of ports each, after an administrator's yes).
                Caption {
                    tone: look
                    visible: allowedCard.visible
                    text: i18n("Apps that can accept connections")
                }
                Card {
                    id: allowedCard
                    tone: look
                    visible: safetyCard.s.firewall === "on" && safetyCard.s.firewallStrict === true
                    Repeater {
                        model: [
                            ["games", i18n("Games you host"), i18n("Minecraft, Terraria, Valheim, Factorio and Stardew Valley worlds that others on this network join")],
                            ["localsend", "LocalSend", i18n("Files from phones and computers nearby")],
                            ["syncthing", "Syncthing", i18n("Folders kept in step with your other devices")],
                            ["sunshine", i18n("Streaming this PC"), i18n("Sunshine, for playing this PC's games on a TV or another device with Moonlight")],
                            ["deskflow", "Deskflow", i18n("One mouse and keyboard for two computers")]
                        ]
                        SettingRow {
                            id: allowRow
                            required property var modelData
                            required property int index
                            tone: look
                            divider: index > 0
                            tappable: sheet.securityFixing === ""
                            title: modelData[1]
                            detail: modelData[2]
                            readonly property bool open: (safetyCard.s.allowed || []).indexOf(modelData[0]) !== -1
                            onTapped: sheet.fixSecurity("firewall-allow " + modelData[0] + (open ? " off" : " on"))
                            Switch {
                                tone: look
                                active: allowRow.open
                            }
                        }
                    }
                    // Programs asked about when they started accepting connections (monet-quick listening).
                    Repeater {
                        model: safetyCard.s.listening || []
                        SettingRow {
                            id: askedRow
                            required property var modelData
                            tone: look
                            tappable: sheet.securityFixing === ""
                            title: modelData.name
                            detail: i18n("Asked when it started accepting connections, on port %1", modelData.port)
                            onTapped: sheet.fixSecurity("listening-allow " + modelData.key + (modelData.allowed ? " off" : " on"))
                            Switch {
                                tone: look
                                active: askedRow.modelData.allowed === true
                            }
                        }
                    }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: i18n("In Windows, Windows Security keeps watch: Monet never turns it off.")
                    color: look.dim
                    font.pixelSize: 13
                    wrapMode: Text.Wrap
                }
            }
        }

        Component {
            id: windowsPage
            ColumnLayout {
                id: windowsColumn
                // A Monet-only PC: no Windows to restart in (`monet` says Not found), and none on its
                // way (Setup left no room for one, monet-prepare-windows' no-space, or wasn't asked).
                readonly property bool noWindows: sheet.pc.windows === "Not found" && ["", "no-space"].includes(sheet.pc.setup || "")
                spacing: 20
                PageTitle {
                    tone: look
                    entry: sheet.entry("windows")
                    art: sheet.art
                    text: i18n("Play on Windows")
                    detail: i18n("Games that need Windows, a restart away.")
                }
                Card {
                    tone: look
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.margins: 18
                        spacing: 18
                        Kirigami.Icon {
                            Layout.preferredWidth: 56
                            Layout.preferredHeight: 56
                            source: "monet-windows"
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: sheet.switching ? i18n("Restarting in Windows…")
                                    : sheet.switchProblem !== "" ? i18n("Couldn't open Windows")
                                    : sheet.asking && sheet.asking.id ? i18n("Play %1?", sheet.asking.name)
                                    : sheet.asking && sheet.asking.task === "launchers" ? i18n("Sign in to your game launchers?")
                                    : sheet.asking && sheet.asking.task === "update" ? i18n("Update Windows games?")
                                    : sheet.asking ? i18n("Restart in Windows?")
                                    : (sheet.pc.notice || "") !== "" ? i18n("The last trip didn't reach Windows")
                                    : sheet.pc.setup === "waiting" || sheet.pc.setup === "preparing" ? i18n("Getting Windows ready")
                                    : sheet.pc.setup === "pending" ? i18n("Windows is ready to install")
                                    : windowsColumn.noWindows ? i18n("No Windows on this PC")
                                    : sheet.pc.windows === "Ready" ? i18n("Windows is ready")
                                    : (sheet.pc.windows || "") === "" ? i18n("Windows")
                                    : i18n("Windows isn't ready")
                                color: look.ink
                                font.pixelSize: 15
                                font.weight: Font.DemiBold
                                wrapMode: Text.Wrap
                            }
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: sheet.switching ? i18n("Your PC restarts in a moment.")
                                    : sheet.switchProblem !== "" ? sheet.switchProblem
                                    : !sheet.asking && (sheet.pc.notice || "") !== "" ? i18n(sheet.pc.notice)
                                    : sheet.pc.setup === "waiting" || sheet.pc.setup === "preparing" ? i18n("Monet is downloading Windows for your games. Keep using your PC; Monet asks before it restarts.")
                                    : sheet.pc.setup === "pending" ? i18n("Restart to install it. It takes about 10 minutes, then you're back in Monet.")
                                        + (typeof sheet.info.battery === "number" && !sheet.info.plugged ? " " + i18n("Plug in the charger first.") : "")
                                    : sheet.asking && sheet.asking.id ? i18n("Your PC restarts in Windows and opens the game. When you quit, you're back here. Save your work first.")
                                    : sheet.asking && sheet.asking.task === "launchers" ? i18n("Your PC restarts in Windows with your game launchers ready. Sign in to each once, then choose Back to Monet. Save your work first.")
                                    : sheet.asking && sheet.asking.task === "update" ? i18n("Your PC restarts in Windows, updates it and your games, and switches off when they're done, within an hour and a half. Save your work first.")
                                        + (typeof sheet.info.battery === "number" && !sheet.info.plugged ? " " + i18n("Plug in the charger first.") : "")
                                    : sheet.asking ? i18n("Your PC restarts in Windows. Open apps close, so save your work first.")
                                    : windowsColumn.noWindows ? i18n("Games that need Windows for their anti-cheat can't start on this PC. Everything else plays here, in Monet.")
                                    : sheet.pc.windows === "Ready" || (sheet.pc.windows || "") === "" ? i18n("Games that need Windows start there, and you come back here when you quit.")
                                    : i18n("Windows: %1. Check Monet below to see what's missing.", i18n(sheet.pc.windows))
                                color: look.dim
                                font.pixelSize: 13
                                wrapMode: Text.Wrap
                            }
                            Text {
                                Layout.fillWidth: true
                                visible: sheet.asking !== null && !sheet.switching
                                text: i18n("Unsaved changes and private tabs aren't captured. Downloads stop during the restart; check Store's Downloads when you return.")
                                color: look.dim
                                font.pixelSize: 13
                                wrapMode: Text.Wrap
                            }
                        }
                        Pill {
                            tone: look
                            visible: sheet.asking !== null
                            text: i18n("Cancel")
                            onClicked: sheet.asking = null
                        }
                        Pill {
                            tone: look
                            kind: "sun"
                            visible: !sheet.switching && sheet.pc.setup !== "waiting" && sheet.pc.setup !== "preparing" && !windowsColumn.noWindows
                            text: sheet.asking && sheet.asking.id ? i18n("Restart & Play")
                                : sheet.asking ? i18n("Restart")
                                : sheet.pc.setup === "pending" ? i18n("Restart and install")
                                : i18n("Restart in Windows")
                            onClicked: {
                                if (sheet.pc.setup === "pending" && !sheet.asking) {
                                    sheet.ask("restart")
                                } else if (sheet.asking) {
                                    sheet.restart()
                                } else {
                                    sheet.switchProblem = ""
                                    sheet.asking = ({})
                                }
                            }
                        }
                    }
                }
                GridLayout {
                    Layout.fillWidth: true
                    visible: sheet.games.length > 0 && !windowsColumn.noWindows
                    columns: 4
                    columnSpacing: 12
                    rowSpacing: 12
                    Repeater {
                        model: sheet.games.slice(0, 8)
                        Cover {
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.preferredHeight: implicitHeight
                            name: modelData.name
                            artwork: modelData.art
                            glaze: sheet.glaze(modelData.name)
                            // Plays in Monet too: no restart needed.
                            here: modelData.here === true
                            onPicked: {
                                sheet.switchProblem = ""
                                sheet.asking = modelData
                            }
                        }
                    }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    visible: sheet.games.length === 0 && !windowsColumn.noWindows
                    text: i18n("Your Windows games show up here once Windows has started with Monet Bridge.")
                    color: look.dim
                    font.pixelSize: 14
                    wrapMode: Text.Wrap
                }
                // Trips that make the next ones smoother: signed in everywhere, everything up to date.
                Card {
                    tone: look
                    visible: (sheet.games.length > 0 || sheet.pc.windows === "Ready") && !windowsColumn.noWindows
                    SettingRow {
                        tone: look
                        title: i18n("Game launchers")
                        detail: i18n("Sign in once to Steam, Riot, Battle.net and the rest in Windows, and the games you play from here start without asking. If you use Discord here, it comes along, so a call carries on in Windows.")
                        Pill {
                            tone: look
                            text: i18n("Sign in…")
                            enabledPill: !sheet.switching
                            onClicked: {
                                sheet.switchProblem = ""
                                sheet.asking = { task: "launchers" }
                            }
                        }
                    }
                    SettingRow {
                        tone: look
                        divider: false
                        title: i18n("Update Windows games")
                        detail: (sheet.gamesUpdated > 0
                                 ? i18n("Last done %1.", Qt.formatDate(new Date(sheet.gamesUpdated * 1000), Locale.ShortFormat)) + " " : "")
                            + i18n("Windows updates itself and your games, then switches the PC off. Good before you go to bed.")
                        Pill {
                            tone: look
                            text: i18n("Update & switch off")
                            enabledPill: !sheet.switching
                            onClicked: {
                                sheet.switchProblem = ""
                                sheet.asking = { task: "update" }
                            }
                        }
                    }
                }
                Card {
                    id: returnCard
                    objectName: "search-return"
                    tone: look
                    Accessible.role: Accessible.Grouping
                    Accessible.name: i18n("After your last return")
                    Keys.onTabPressed: event => {
                        if (sheet.activeFocusItem !== returnCard) { event.accepted = false; return }
                        for (const name of ["returnRetryAll", "returnDismiss", "returnRefresh"]) {
                            const next = sheet.returnFocusTarget(returnCard, name)
                            if (next && next.visible && next.enabledPill) {
                                next.forceActiveFocus(Qt.TabFocusReason)
                                return
                            }
                        }
                        event.accepted = false
                    }
                    SettingRow {
                        tone: look
                        divider: false
                        title: i18n("After your last return")
                        detail: sheet.returnInfo.busy ? i18n("Reopening your work…")
                            : sheet.returnInfo.available ? i18n("What opened, and what still needs attention. Open app uses its normal startup settings.")
                            : i18n("After a trip to Windows, your recovery summary appears here. Save your work before leaving; unsaved changes and private tabs aren't captured.")
                        Row {
                            spacing: 8
                            Pill {
                                objectName: "returnRetryAll"
                                tone: look
                                visible: sheet.returnInfo.retry === true
                                text: i18n("Retry pending")
                                enabledPill: !sheet.returnBusy && !sheet.returnInfo.busy
                                onClicked: sheet.returnAction("retry", "")
                            }
                            Pill {
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
                        SettingRow {
                            required property var modelData
                            tone: look
                            title: modelData.name
                            detail: modelData.detail + ((modelData.missing || []).length > 0
                                ? "\n" + i18n("Unavailable: %1", modelData.missing.join(", ")) : "")
                            Row {
                                spacing: 8
                                Pill {
                                    objectName: "returnRetry-" + modelData.app
                                    tone: look
                                    visible: modelData.retry === true
                                    text: modelData.missingCount > 0 ? i18n("Retry documents") : i18n("Retry")
                                    enabledPill: !sheet.returnBusy && !sheet.returnInfo.busy
                                    onClicked: sheet.returnAction("retry", modelData.app)
                                }
                                Pill {
                                    objectName: "returnOpen-" + modelData.app
                                    tone: look
                                    visible: modelData.canOpen === true
                                    text: i18n("Open app")
                                    enabledPill: !sheet.returnBusy && !sheet.returnInfo.busy
                                    onClicked: sheet.returnAction("open", modelData.app)
                                }
                                Pill {
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
                        font.pixelSize: 12
                        wrapMode: Text.Wrap
                    }
                    SettingRow {
                        tone: look
                        visible: sheet.returnProblem !== "" || sheet.returnReadProblem !== ""
                        title: sheet.returnProblem || sheet.returnReadProblem
                        strong: false
                        Pill {
                            objectName: "returnRefresh"
                            tone: look
                            text: i18n("Refresh")
                            enabledPill: !sheet.returnLoading && !sheet.returnBusy
                            onClicked: sheet.loadReturn()
                        }
                    }
                }
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        title: i18n("Check Monet")
                        detail: i18n("See that Windows, Secure Boot and switching are all set up")
                        Pill {
                            tone: look
                            text: sheet.checkingDoctor ? i18n("Checking…") : i18n("Check")
                            enabledPill: !sheet.checkingDoctor
                            onClicked: sheet.checkMonet()
                        }
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        Layout.leftMargin: 18
                        Layout.rightMargin: 18
                        Layout.bottomMargin: 16
                        visible: sheet.doctorReport !== ""
                        textFormat: Text.StyledText
                        text: sheet.report(sheet.doctorReport)
                        color: look.ink
                        font.pixelSize: 13
                        lineHeight: 1.35
                        wrapMode: Text.Wrap
                    }
                }
                // Ready when you come back: off until it's chosen, as it signs in without asking first.
                Card {
                    tone: look
                    visible: !windowsColumn.noWindows
                    SettingRow {
                        tone: look
                        divider: false
                        tappable: true
                        title: i18n("Ready when you come back")
                        detail: i18n("After Windows, Monet starts your desktop behind the lock screen, so it's there as soon as you type your password.")
                        onTapped: {
                            const on = sheet.ready.on !== true
                            sheet.ready = sheet.changed(sheet.ready, ["on"], on)
                            sheet.ask(on ? "ready-on" : "ready-off", out => sheet.ready = sheet.json(out, sheet.ready))
                        }
                        Switch {
                            tone: look
                            active: sheet.ready.on === true
                        }
                    }
                    // The apps that were open before the trip start again (monet-quick remembers them).
                    SettingRow {
                        tone: look
                        tappable: true
                        title: i18n("Open your apps again")
                        detail: i18n("Reopen apps, saved documents and Files tabs after Windows. Zen follows its tab-restore preference. Save your work first; private tabs aren't restored.")
                        onTapped: {
                            const on = sheet.ready.apps === false
                            sheet.ready = sheet.changed(sheet.ready, ["apps"], on)
                            sheet.ask("trip-apps " + (on ? "on" : "off"), out => sheet.ready = sheet.json(out, sheet.ready))
                        }
                        Switch {
                            tone: look
                            active: sheet.ready.apps !== false
                        }
                    }
                }
            }
        }

        Component {
            id: updatesPage
            ColumnLayout {
                spacing: 20
                PageTitle {
                    tone: look
                    entry: sheet.entry("updates")
                    art: sheet.art
                    text: i18n("Updates")
                    detail: sheet.pc.autoUpdates === false ? i18n("Only when you ask.")
                        : i18n("Monet and your apps keep themselves up to date.")
                }
                Card {
                    tone: look
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.margins: 20
                        spacing: 18
                        Kirigami.Icon {
                            Layout.preferredWidth: 56
                            Layout.preferredHeight: 56
                            source: "monet"
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: sheet.updateTitle()
                                color: look.ink
                                font.pixelSize: 15
                                font.weight: Font.DemiBold
                                wrapMode: Text.Wrap
                            }
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: sheet.updateDetail()
                                color: sheet.updateState === "failed" ? "#E0603A" : look.dim
                                font.pixelSize: 13
                                wrapMode: Text.Wrap
                            }
                            // Still working: there's no number to show, so it just moves.
                            Busy {
                                tone: look
                                Layout.fillWidth: true
                                Layout.topMargin: 6
                                visible: sheet.updateState === "checking" || sheet.updateState === "installing"
                                indeterminate: true
                            }
                        }
                        Pill {
                            tone: look
                            kind: sheet.updateState === "available" || (sheet.updateState === "done" && sheet.updateFound.system) ? "lily" : "plain"
                            visible: !(sheet.updateState === "done" && !sheet.updateFound.system)
                            text: sheet.updateState === "checking" ? i18n("Checking…")
                                : sheet.updateState === "installing" ? i18n("Installing…")
                                : sheet.updateState === "available" ? i18n("Install")
                                : sheet.updateState === "done" ? i18n("Restart now")
                                : sheet.updateState === "failed" ? i18n("Try again")
                                : i18n("Check for updates")
                            enabledPill: sheet.updateState !== "checking" && sheet.updateState !== "installing"
                            onClicked: {
                                if (sheet.updateState === "available") {
                                    sheet.installUpdates()
                                } else if (sheet.updateState === "done") {
                                    sheet.ask("restart")
                                } else {
                                    sheet.checkUpdates()
                                }
                            }
                        }
                    }
                }
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        tappable: true
                        title: i18n("Update automatically")
                        detail: sheet.pc.autoUpdates === false
                            ? i18n("Monet and your apps update only when you choose Check for updates")
                            : i18n("Once a day, in the background: your apps right away, Monet at your next restart")
                        onTapped: sheet.flipAutoUpdates()
                        Switch {
                            tone: look
                            active: sheet.pc.autoUpdates !== false
                        }
                    }
                }
                // What came with this Monet, from its release notes (also offered once after an update).
                Caption {
                    tone: look
                    visible: (sheet.whatsNew.items || []).length > 0
                    text: i18n("New in Monet %1", sheet.whatsNew.version || "")
                }
                Card {
                    tone: look
                    visible: (sheet.whatsNew.items || []).length > 0
                    ColumnLayout {
                        Layout.fillWidth: true
                        Layout.margins: 20
                        spacing: 14
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            visible: (sheet.whatsNew.headline || "") !== ""
                            text: sheet.whatsNew.headline || ""
                            color: look.ink
                            font.family: "Fraunces 72pt SuperSoft"
                            font.pixelSize: 24
                            wrapMode: Text.Wrap
                        }
                        Repeater {
                            model: sheet.whatsNew.items || []
                            ColumnLayout {
                                required property var modelData
                                Layout.fillWidth: true
                                spacing: 2
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    text: parent.modelData.title
                                    color: look.ink
                                    font.pixelSize: 14
                                    font.weight: Font.DemiBold
                                    wrapMode: Text.Wrap
                                }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    Layout.fillWidth: true
                                    text: parent.modelData.text
                                    color: look.dim
                                    font.pixelSize: 13
                                    lineHeight: 1.25
                                    wrapMode: Text.Wrap
                                }
                            }
                        }
                    }
                }
                // An update that didn't start on this PC: Monet went back by itself (monet-boot).
                Card {
                    tone: look
                    visible: sheet.wentBack.version !== undefined
                    SettingRow {
                        tone: look
                        divider: false
                        title: sheet.wentBack.to ? i18n("Monet went back to %1", sheet.wentBack.to) : i18n("Monet went back")
                        detail: sheet.wentBack.version
                            ? i18n("Monet %1 didn't start properly on this PC, so it went back by itself. Your files are as they were, and the daily update waits for the next one.", sheet.wentBack.version)
                            : i18n("The new Monet didn't start properly on this PC, so it went back by itself. Your files are as they were, and the daily update waits for the next one.")
                    }
                }
                // The Monet from before the last update, kept for when one misbehaves (not the one that
                // just didn't start).
                Card {
                    tone: look
                    visible: sheet.previous.date !== undefined
                        && !(sheet.wentBack.version && sheet.wentBack.version === sheet.previous.version)
                    SettingRow {
                        id: backRow
                        property bool asking: false
                        tone: look
                        divider: false
                        title: sheet.previous.pending === true ? i18n("%1 starts at your next restart", sheet.previousName())
                            : i18n("Go back to %1", sheet.previousName())
                        detail: sheet.previous.pending === true ? i18n("The one you're using now stays too, to come back to.")
                            : backRow.asking ? i18n("It starts the next time you restart. Your files and apps stay as they are.")
                            : sheet.previous.date ? i18n("From %1. If something stopped working after an update, the one before is still here.", sheet.previous.date)
                            : i18n("If something stopped working after an update, the one before is still here.")
                        Row {
                            spacing: 8
                            Pill {
                                tone: look
                                visible: backRow.asking
                                text: i18n("Stay")
                                onClicked: backRow.asking = false
                            }
                            Pill {
                                tone: look
                                visible: sheet.previous.pending !== true
                                text: backRow.asking ? i18n("Go back at restart") : i18n("Go back")
                                onClicked: {
                                    if (backRow.asking) {
                                        backRow.asking = false
                                        sheet.goBack()
                                    } else {
                                        backRow.asking = true
                                    }
                                }
                            }
                            Pill {
                                tone: look
                                visible: sheet.previous.pending === true
                                kind: "lily"
                                text: i18n("Restart now")
                                onClicked: sheet.ask("restart")
                            }
                        }
                    }
                }
                // Reset this PC: Monet as it comes, with files, games and apps kept (monet-reset, at the
                // next restart, after an administrator's password).
                Card {
                    tone: look
                    SettingRow {
                        id: resetRow
                        property bool asking: false
                        readonly property bool pending: sheet.resetState.pending === true
                        tone: look
                        divider: false
                        title: pending ? i18n("Monet resets itself at your next restart") : i18n("Reset this PC")
                        detail: pending ? i18n("Everyone's settings go back to how Monet comes. Files, games and apps stay.")
                            : asking ? i18n("Monet's settings, the desktop's look and the changes made to the system go back to how Monet comes, for everyone. Files, games and apps stay, and so do accounts, Wi-Fi and printers. It happens at your next restart.")
                            : i18n("For when something's wrong, and going back to the Monet from before didn't help.")
                        Row {
                            spacing: 8
                            Pill {
                                tone: look
                                visible: resetRow.asking && !resetRow.pending
                                text: i18n("Stay")
                                onClicked: resetRow.asking = false
                            }
                            Pill {
                                tone: look
                                visible: !resetRow.pending
                                text: resetRow.asking ? i18n("Reset at restart") : i18n("Reset")
                                onClicked: {
                                    if (resetRow.asking) {
                                        resetRow.asking = false
                                        sheet.ask("reset on", out => sheet.resetState = sheet.json(out, sheet.resetState))
                                    } else {
                                        resetRow.asking = true
                                    }
                                }
                            }
                            Pill {
                                tone: look
                                visible: resetRow.pending
                                text: i18n("Don't reset")
                                onClicked: sheet.ask("reset off", out => sheet.resetState = sheet.json(out, sheet.resetState))
                            }
                            Pill {
                                tone: look
                                visible: resetRow.pending
                                kind: "lily"
                                text: i18n("Restart now")
                                onClicked: sheet.ask("restart")
                            }
                        }
                    }
                }
                // Firmware, only when there's some to install.
                Card {
                    tone: look
                    visible: sheet.firmware.length > 0
                    RowLayout {
                        Layout.fillWidth: true
                        Layout.margins: 20
                        spacing: 18
                        Rounded {
                            Layout.preferredWidth: 56
                            Layout.preferredHeight: 56
                            radius: 16
                            Image {
                                anchors.fill: parent
                                source: sheet.art + "swatch-updates.png"
                                sourceSize: Qt.size(112, 112)
                                smooth: true
                            }
                            Glyph {
                                anchors.centerIn: parent
                                width: 28
                                height: 28
                                // A chip on its pins.
                                path: "M7 7h10v10H7zM10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4"
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: sheet.firmwareTitle()
                                color: look.ink
                                font.pixelSize: 15
                                font.weight: Font.DemiBold
                                wrapMode: Text.Wrap
                            }
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: sheet.firmwareDetail()
                                color: sheet.firmwareState === "failed" ? "#E0603A" : look.dim
                                font.pixelSize: 13
                                wrapMode: Text.Wrap
                            }
                            Busy {
                                tone: look
                                Layout.fillWidth: true
                                Layout.topMargin: 6
                                visible: sheet.firmwareState === "installing"
                                indeterminate: true
                            }
                        }
                        Pill {
                            tone: look
                            kind: sheet.firmwareState === "available" || (sheet.firmwareState === "done" && sheet.firmwareRestart) ? "lily" : "plain"
                            visible: !(sheet.firmwareState === "done" && !sheet.firmwareRestart)
                            text: sheet.firmwareState === "installing" ? i18n("Installing…")
                                : sheet.firmwareState === "done" ? i18n("Restart now")
                                : sheet.firmwareState === "failed" ? i18n("Try again")
                                : i18n("Install")
                            enabledPill: sheet.firmwareState !== "installing" && sheet.firmware.some(f => !f.blocked)
                            onClicked: sheet.firmwareState === "done" ? sheet.ask("restart") : sheet.installFirmware()
                        }
                    }
                    Repeater {
                        model: sheet.firmware
                        SettingRow {
                            tone: look
                            strong: false
                            title: modelData.vendor && modelData.device.indexOf(modelData.vendor) < 0
                                ? modelData.vendor + " " + modelData.device : modelData.device
                            detail: sheet.firmwareLine(modelData)
                        }
                    }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: i18n("A new Monet starts the next time you restart, never while you work, and the one before stays in the start menu, just in case.")
                    color: look.dim
                    font.pixelSize: 14
                    lineHeight: 1.3
                    wrapMode: Text.Wrap
                }
            }
        }

        Component {
            id: aboutPage
            ColumnLayout {
                spacing: 20
                Rounded {
                    id: banner
                    Layout.fillWidth: true
                    // Clear of the close button.
                    Layout.topMargin: 22
                    Layout.preferredHeight: Math.round(width * 360 / 1200)
                    radius: 18
                    Image {
                        anchors.fill: parent
                        source: sheet.art + "about.jpg"
                        fillMode: Image.PreserveAspectCrop
                        smooth: true
                    }
                    Rectangle {
                        anchors.fill: parent
                        gradient: Gradient {
                            GradientStop { position: 0.4; color: "transparent" }
                            GradientStop { position: 1; color: Qt.rgba(0.05, 0.03, 0.1, 0.45) }
                        }
                    }
                    Column {
                        anchors.left: parent.left
                        anchors.bottom: parent.bottom
                        anchors.leftMargin: 24
                        anchors.bottomMargin: 18
                        spacing: 4
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            text: "Monet"
                            color: "#FFFFFF"
                            font.family: "Fraunces 72pt SuperSoft"
                            font.weight: Font.Light
                            font.pixelSize: 48
                            font.letterSpacing: -1.2
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            text: sheet.pc.monet ? i18n("%1 · Impression", sheet.pc.monet) : i18n("Impression")
                            color: "#E6FFFFFF"
                            font.pixelSize: 14
                        }
                    }
                }
                Card {
                    tone: look
                    Repeater {
                        model: [
                            [i18n("Graphics"), sheet.pc.graphics],
                            [i18n("Processor"), sheet.pc.processor],
                            [i18n("Memory"), sheet.pc.memory],
                            [i18n("Storage"), sheet.pc.storage],
                            [i18n("Windows"), sheet.pc.windows === "Ready" ? i18n("Ready for games") : (sheet.pc.windows ? i18n(sheet.pc.windows) : "")]
                        ].filter(r => r[1])
                        SettingRow {
                            tone: look
                            divider: index > 0
                            strong: false
                            title: modelData[0]
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                width: Math.min(implicitWidth, 380)
                                text: modelData[1]
                                color: look.ink
                                font.pixelSize: 14
                                elide: Text.ElideRight
                            }
                        }
                    }
                }
                // How long the last start took, and where the time went: to see what a change does.
                Card {
                    tone: look
                    visible: sheet.startup.total !== undefined
                    SettingRow {
                        tone: look
                        divider: false
                        strong: false
                        title: i18n("Last start")
                        detail: [
                            sheet.startup.pc ? i18nc("how long the PC's own start took, in seconds", "The PC %1 s", sheet.secs(sheet.startup.pc)) : "",
                            sheet.startup.monet ? i18nc("how long Monet took to start, in seconds", "Monet %1 s", sheet.secs(sheet.startup.monet)) : "",
                            sheet.startup.desktop ? i18nc("from signing in until the desktop was there, in seconds", "Your desktop %1 s", sheet.secs(sheet.startup.desktop)) : ""
                        ].filter(t => t !== "").join("  ·  ")
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            text: i18nc("a time in seconds", "%1 s", sheet.secs(sheet.startup.total || 0))
                            color: look.ink
                            font.pixelSize: 14
                        }
                    }
                }
                // Everything that helps find out why something went wrong, in one file to send.
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        title: i18n("Save a report")
                        detail: sheet.reportSaved !== "" ? i18n("In Documents, as %1.", sheet.reportSaved)
                            : i18n("What helps find out why something went wrong, in one file in Documents. It stays on this PC until you send it to someone.")
                        Pill {
                            tone: look
                            text: sheet.reporting ? i18n("Saving…") : i18n("Save")
                            enabledPill: !sheet.reporting
                            onClicked: {
                                if (sheet.reporting)
                                    return
                                sheet.reporting = true
                                sheet.ask("report", out => {
                                    sheet.reporting = false
                                    sheet.reportSaved = sheet.json(out, {}).saved || ""
                                })
                            }
                        }
                    }
                }
                // For people from Linux: the system can't be changed (that keeps updates safe),
                // so command-line tools go in a container, which BoxBuddy makes (Distrobox's).
                Card {
                    tone: look
                    SettingRow {
                        tone: look
                        divider: false
                        title: i18n("Command-line tools")
                        detail: i18n("Monet's system can't be changed, which keeps every update safe, so tools for the command line go in a container beside it, where you install what you like. BoxBuddy makes one in a few clicks.")
                        Pill {
                            tone: look
                            text: sheet.gettingTools ? i18n("Getting…") : i18n("Get BoxBuddy")
                            enabledPill: !sheet.gettingTools
                            onClicked: {
                                sheet.gettingTools = true
                                sheet.ask("get-tools", () => sheet.gettingTools = false)
                            }
                        }
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
