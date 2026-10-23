/*
 * Monet Settings: one glass sheet with the settings people actually change.
 * The glass is the Plasma style's dialog; the pages sit on solid paper (or
 * smoke) so text is always easy to read. Anything rarer is one click away
 * in KDE's System Settings ("More settings").
 *
 * The `monet-quick` helper does the work; this only draws it.
 */
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Shapes
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmaCore.Dialog {
    id: sheet

    property string helper
    property string monet: "@BINDIR@/monet"
    property real speed: 1
    // The screen to open on, from the panel.
    property rect area: Qt.rect(0, 0, 1280, 800)
    // The size people gave it by dragging its corner or edges (0: the size that fits).
    property real chosenWidth: 0
    property real chosenHeight: 0
    signal resized(real width, real height)
    readonly property real fittingWidth: Math.min(1000, area.width - 64)
    readonly property real fittingHeight: Math.min(780, area.height - 96)
    property string page: "light"

    readonly property string art: "file://@DATADIR@/monet/settings/"
    // Each page's search words are said in your language too: what people might type to find
    // it, with the English ones people use anyway (wifi, bluetooth) kept in.
    readonly property var pages: [
        { id: "light", name: i18n("Light & Wallpaper"), glyph: "M5 15a7 7 0 0 1 14 0M3 19h18",
          words: i18nc("Settings search words, space-separated",
                      "light wallpaper painting hours mist smoke dark mode glass placard clock theme appearance colors") },
        { id: "wifi", name: i18n("Wi-Fi"), glyph: "M4 10a12 12 0 0 1 16 0M7 13.5a7.5 7.5 0 0 1 10 0M10 17a3 3 0 0 1 4 0",
          words: i18nc("Settings search words, space-separated",
                      "wifi wi-fi wireless network internet password") },
        { id: "bluetooth", name: i18n("Bluetooth"), glyph: "M7 7l10 10-5 5V2l5 5L7 17",
          words: i18nc("Settings search words, space-separated",
                      "bluetooth headphones controller gamepad mouse keyboard pair") },
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
                      "accounts users password picture people name login sign in") },
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
                      "lock screen locker password wake sleep privacy recent files history forget remember away") },
        { id: "notifications", name: i18n("Notifications"),
          glyph: "M6 16v-5a6 6 0 0 1 12 0v5l2 2H4zM10 20h4",
          words: i18nc("Settings search words, space-separated",
                      "notifications alerts do not disturb quiet popups sounds apps") },
        { id: "accessibility", name: i18n("Accessibility"),
          glyph: "M12 5h.01M5 8.5l7 1.5 7-1.5M12 10v4.5M8.5 20.5l3.5-6 3.5 6",
          words: i18nc("Settings search words, space-separated",
                      "accessibility bigger larger text size scale zoom pointer cursor motion animation screen reader orca see read") },
        { id: "apps", name: i18n("Default Apps"),
          glyph: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z",
          words: i18nc("Settings search words, space-separated",
                      "default apps browser web email mail files music video photos pdf text open with") },
        { id: "storage", name: i18n("Storage"),
          glyph: "M4 7.5h16v9H4zM7.5 12h.01M11 12h5.5",
          words: i18nc("Settings search words, space-separated",
                      "storage disk space room full free trash downloads clean games apps") },
        { id: "backups", name: i18n("Backups"), glyph: "M4.5 12a7.5 7.5 0 1 0 2.2-5.3M4.5 4.5v3h3M12 8.5V12l2.5 1.5",
          words: i18nc("Settings search words, space-separated",
                      "backups backup copy restore earlier versions history snapshot undo lost deleted usb drive time machine") },
        { id: "games", name: i18n("Games & Controllers"), gap: true,
          glyph: "M7.5 8h9a4.5 4.5 0 0 1 4.5 4.5v1a3.5 3.5 0 0 1-6.4 2L14 14.5h-4l-.6 1A3.5 3.5 0 0 1 3 13.5v-1A4.5 4.5 0 0 1 7.5 8zM8 10.5v3M6.5 12h3M15.5 11.5h.01M17.5 13h.01",
          words: i18nc("Settings search words, space-separated",
                      "games controller gamepad joystick xbox playstation dualsense battery pair test buttons overlay fps mangohud performance steam library installed heroic lutris") },
        { id: "windows", name: i18n("Play on Windows"), glyph: "M9 6.5L18 12l-9 5.5z", filled: true,
          words: i18nc("Settings search words, space-separated",
                      "windows games play anti-cheat steam restart boot doctor check") },
        { id: "updates", name: i18n("Updates"), glyph: "M12 4v11M7 10l5 5 5-5M5 20h14",
          words: i18nc("Settings search words, space-separated",
                      "updates update version upgrade new reset restore rollback") },
        { id: "about", name: i18n("About Monet"), glyph: "M12 7.5h.01M12 11v6",
          words: i18nc("Settings search words, space-separated",
                      "about pc computer specs graphics gpu processor cpu memory ram storage disk version") }
    ]

    // What the helper reported.
    property var info: ({})
    property var prefs: ({ hours: true, placard: true, glass: true, weather: true, dodge: true })
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
    // Power & Sleep, Mouse & Keyboard, Notifications and Default Apps, as the helper reports them.
    property var powerInfo: ({})
    property var inputInfo: ({})
    property var knownLayouts: []
    property var notifyInfo: ({})
    property var appDefaults: []
    property var storageInfo: ({})
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
    property bool dragging: false

    // Wi-Fi: the network being joined, and how it went.
    property string joining: ""
    property string joinState: ""
    // Bluetooth: the device that's connecting or disconnecting.
    property string busyDevice: ""
    // Windows: the game (or {} for Windows itself) waiting for a yes.
    property var asking: null
    property bool switching: false
    property string switchProblem: ""
    property string doctorReport: ""
    property bool checkingDoctor: false
    // Updates: "", "checking", "none", "available", "installing", "done" or
    // "failed"; what the check found; and what Monet said.
    property string updateState: ""
    property var updateFound: ({})
    property string updateMessage: ""
    // Firmware for the PC's own parts (fwupd): the same states, and the updates.
    property string firmwareState: ""
    property var firmware: []
    property string firmwareMessage: ""
    readonly property bool firmwareRestart: firmware.some(f => f.restart)
    // Accounts: changing your name, and your password: "", "open", "changing", "done" or
    // "failed", with what went wrong.
    property bool renaming: false
    property string nameProblem: ""
    property string passwordState: ""
    property string passwordMessage: ""
    // Each language's locale with a 12-hour clock, and its nearest with a 24-hour one.
    readonly property var clocks: ({ en: ["en_US.UTF-8", "en_GB.UTF-8"] })

    title: i18n("Settings")
    location: PlasmaCore.Types.Floating
    hideOnWindowDeactivate: false
    visible: false

    function open(which) {
        if (which && (which === "welcome" || pages.some(p => p.id === which))) {
            page = which
        }
        center()
        visible = true
        raise()
        requestActivate()
        load()
    }

    function center() {
        x = Math.round(area.x + (area.width - mainItem.width) / 2)
        y = Math.round(area.y + Math.max(16, (area.height - mainItem.height) / 2 - area.height * 0.03))
    }

    // Double-clicking the name: as big as the screen allows, or back to the size that fits.
    function toggleBig() {
        const big = mainItem.width >= area.width - 72 && mainItem.height >= area.height - 104
        chosenWidth = big ? 0 : area.width - 64
        chosenHeight = big ? 0 : area.height - 96
        resized(chosenWidth, chosenHeight)
        Qt.callLater(center)
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

    function call(command, then) {
        waiting[command] = then || null
        asker.connectSource(command)
    }
    // Arguments are fixed words, numbers, or hex; never raw text from people.
    function ask(args, then) {
        call(helper + " " + args, then)
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
        } else if (page === "windows") {
            ask("ready", out => sheet.ready = sheet.json(out, sheet.ready))
            ask("game-marks", out => sheet.gameMarks = sheet.json(out, sheet.gameMarks))
            call(monet + " games --json", out => sheet.games = sheet.json(out, []))
        } else if (page === "datetime") {
            ask("time", out => sheet.clock = sheet.json(out, sheet.clock))
            if (zones.length === 0) {
                ask("zones", out => sheet.zones = sheet.json(out, []))
            }
        } else if (page === "users") {
            ask("accounts", out => sheet.people = sheet.json(out, sheet.people))
        } else if (page === "power") {
            ask("power", out => sheet.powerInfo = sheet.json(out, sheet.powerInfo))
            ask("battery-care", out => sheet.batteryCare = sheet.json(out, sheet.batteryCare))
        } else if (page === "input") {
            ask("input", out => sheet.inputInfo = sheet.json(out, sheet.inputInfo))
            if (knownLayouts.length === 0) {
                ask("layouts-known", out => sheet.knownLayouts = sheet.json(out, []))
            }
        } else if (page === "notifications") {
            ask("notify", out => sheet.notifyInfo = sheet.json(out, sheet.notifyInfo))
        } else if (page === "apps") {
            ask("defaults", out => sheet.appDefaults = sheet.json(out, sheet.appDefaults))
        } else if (page === "display") {
            ask("screens", out => sheet.screenInfo = sheet.json(out, []))
        } else if (page === "storage") {
            ask("storage", out => sheet.storageInfo = sheet.json(out, sheet.storageInfo))
        } else if (page === "backups") {
            ask("backup", out => sheet.backup = sheet.json(out, sheet.backup))
            ask("versions", out => sheet.earlier = sheet.json(out, {}))
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

    function chooseSeries(name) {
        prefs = changed(prefs, ["series"], name)
        ask("series " + name)
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

    // Game ids only contain letters, digits, ":", ".", "_" and "-".
    function restart() {
        const game = asking && asking.id && /^[A-Za-z0-9:._-]+$/.test(asking.id) ? asking : null
        switchProblem = ""
        asking = null
        switching = true
        call(game ? monet + " play '" + game.id + "'" : monet + " windows", (out, code, err) => {
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

    // The locale the time is shown in from the next sign-in.
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

    function notifyRule(name, on) {
        notifyInfo = changed(notifyInfo, [name], on)
        ask("notify-rule " + name + (on ? " on" : " off"))
    }
    function notifyPopups(what, value) {
        notifyInfo = changed(notifyInfo, [what], value)
        ask((what === "place" ? "notify-place " : "notify-time ") + value)
    }
    function notifyApp(app, on) {
        notifyInfo = changed(notifyInfo, ["apps"], (notifyInfo.apps || []).map(a => a.id === app.id ? Object.assign({}, a, { popups: on }) : a))
        ask("notify-app " + hex(app.id) + (on ? " on" : " off"))
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

    function access(what, value) {
        accessInfo = changed(accessInfo, [what], value)
        const said = what === "reduced" ? (value ? "reduced" : "normal") : what === "reader" ? (value ? "on" : "off") : value
        ask("access-" + ({ scale: "scale", cursor: "cursor", reduced: "motion", reader: "reader" })[what] + " " + said)
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
        border.width: 1
        border.color: tone.line
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
        property bool strong: true
        default property alias trailing: slot.data
        property alias lead: leadSlot.data
        signal tapped()
        Layout.fillWidth: true
        implicitHeight: Math.max(texts.implicitHeight, slot.childrenRect.height, leadSlot.childrenRect.height) + 28
        activeFocusOnTab: tappable
        Keys.onSpacePressed: row.tapped()
        Keys.onReturnPressed: row.tapped()

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
            anchors.verticalCenter: parent.verticalCenter
            width: childrenRect.width
            height: childrenRect.height
        }
        ColumnLayout {
            id: texts
            anchors.left: leadSlot.right
            anchors.leftMargin: leadSlot.width > 0 ? 12 : 0
            anchors.right: slot.left
            anchors.rightMargin: 16
            anchors.verticalCenter: parent.verticalCenter
            spacing: 3
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: row.title
                color: row.tone.ink
                font.pixelSize: 14
                font.weight: row.strong ? Font.DemiBold : Font.Medium
                elide: Text.ElideRight
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                visible: row.detail !== ""
                text: row.detail
                color: row.tone.dim
                font.pixelSize: 13
                wrapMode: Text.Wrap
            }
        }
        Item {
            id: slot
            anchors.right: parent.right
            anchors.rightMargin: 18
            anchors.verticalCenter: parent.verticalCenter
            width: childrenRect.width
            height: childrenRect.height
        }
        HoverHandler { id: hover }
        TapHandler {
            enabled: row.tappable
            onTapped: row.tapped()
        }
        Accessible.role: tappable ? Accessible.Button : Accessible.StaticText
        Accessible.name: title
        Accessible.description: detail
        Accessible.onPressAction: if (tappable) row.tapped()
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
            PlasmaComponents.Slider {
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

    mainItem: Item {
        id: frame
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true
        // Tall enough for every page in the list on most screens (it scrolls on short ones), or
        // the size people dragged it to, never bigger than the screen nor too small to read.
        width: Math.max(Math.min(760, sheet.area.width - 32),
                        Math.min(sheet.chosenWidth > 0 ? sheet.chosenWidth : sheet.fittingWidth, sheet.area.width - 32))
        height: Math.max(Math.min(520, sheet.area.height - 48),
                         Math.min(sheet.chosenHeight > 0 ? sheet.chosenHeight : sheet.fittingHeight, sheet.area.height - 48))
        // Mist or smoke, from the colors Monet's light chose.
        readonly property bool dark: Kirigami.Theme.backgroundColor.hslLightness < 0.5

        Shortcut {
            sequences: ["Escape"]
            onActivated: sheet.visible = false
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

            // Drag the sheet by its glass.
            DragHandler {
                target: null
                onActiveChanged: if (active) sheet.startSystemMove()
            }

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
                    TapHandler {
                        onDoubleTapped: sheet.toggleBig()
                    }
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
                            Layout.fillWidth: true
                            color: look.ink
                            font.pixelSize: 14
                            clip: true
                            selectByMouse: true
                            selectionColor: look.lily
                            Accessible.role: Accessible.EditableText
                            Accessible.name: i18n("Search settings")
                            onAccepted: {
                                const first = sheet.pages.find(p => side.matches(p))
                                if (first) {
                                    sheet.page = first.id
                                }
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
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentHeight: navColumn.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    interactive: contentHeight > height
                    // On a laptop's screen not every page fits: a scrollbar says there are more,
                    // and the page that opens (from a notification, say) is scrolled into view.
                    QQC2.ScrollBar.vertical: PlasmaComponents.ScrollBar { id: navScroll }

                    function reveal() {
                        const shown = pebble.target
                        if (shown && (shown.y < contentY || shown.y + shown.height > contentY + height)) {
                            contentY = Math.max(0, Math.min(shown.y - (height - shown.height) / 2, contentHeight - height))
                        }
                    }

                    Connections {
                        target: sheet
                        function onPageChanged() { Qt.callLater(navList.reveal) }
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
                            visible: !sheet.pages.some(p => side.matches(p))
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
                const words = fold(search.text.trim())
                return words === "" || fold(entry.name + " " + entry.words).indexOf(words) !== -1
            }
        }

        // Bigger or smaller: drag the right edge, the bottom edge or the corner (kept for next time).
        Repeater {
            model: [[true, false], [false, true], [true, true]]
            Item {
                id: grip
                required property var modelData
                readonly property bool sideways: modelData[0]
                readonly property bool downwards: modelData[1]
                property real fromWidth: 0
                property real fromHeight: 0
                LayoutMirroring.enabled: false
                z: 10
                x: sideways ? frame.width - (downwards ? 18 : 6) : 0
                y: downwards ? frame.height - (sideways ? 18 : 6) : 0
                width: sideways ? (downwards ? 18 : 6) : frame.width - 18
                height: downwards ? (sideways ? 18 : 6) : frame.height - 18
                HoverHandler {
                    cursorShape: grip.sideways && grip.downwards ? Qt.SizeFDiagCursor
                        : grip.sideways ? Qt.SizeHorCursor : Qt.SizeVerCursor
                }
                DragHandler {
                    target: null
                    onActiveChanged: {
                        if (active) {
                            grip.fromWidth = frame.width
                            grip.fromHeight = frame.height
                        } else {
                            sheet.resized(sheet.chosenWidth, sheet.chosenHeight)
                        }
                    }
                    onTranslationChanged: {
                        if (grip.sideways) {
                            sheet.chosenWidth = Math.max(760, grip.fromWidth + translation.x)
                        }
                        if (grip.downwards) {
                            sheet.chosenHeight = Math.max(520, grip.fromHeight + translation.y)
                        }
                    }
                }
                // The corner shows it can be pulled: two short strokes.
                Glyph {
                    visible: grip.sideways && grip.downwards
                    anchors.fill: parent
                    anchors.margins: 3
                    path: "M20 10L10 20M20 16L16 20"
                    color: look.dim
                    opacity: 0.6
                }
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
            color: look.paper
            border.width: 1
            border.color: look.dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(1, 1, 1, 0.7)

            Flickable {
                id: scroller
                anchors.fill: parent
                anchors.topMargin: 2
                anchors.bottomMargin: 2
                clip: true
                contentWidth: width
                contentHeight: pageLoader.height + 60
                boundsBehavior: Flickable.StopAtBounds
                QQC2.ScrollBar.vertical: PlasmaComponents.ScrollBar {}

                Loader {
                    id: pageLoader
                    x: 34
                    y: 28
                    width: scroller.width - 68
                    property real shift: 0
                    transform: Translate { y: pageLoader.shift }
                    sourceComponent: ({
                        light: lightPage, wifi: wifiPage, bluetooth: bluetoothPage, display: displayPage,
                        sound: soundPage, datetime: datetimePage, users: usersPage, input: inputPage,
                        power: powerPage, notifications: notificationsPage, accessibility: accessibilityPage, apps: appsPage,
                        storage: storagePage, backups: backupsPage, games: gamesPage, windows: windowsPage, privacy: privacyPage,
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

            // Close.
            Rectangle {
                anchors.top: parent.top
                anchors.right: parent.right
                anchors.margins: 14
                width: 30
                height: 30
                radius: 15
                color: closeHover.hovered ? look.press : look.wash2
                Glyph {
                    anchors.centerIn: parent
                    width: 12
                    height: 12
                    path: "M6 6l12 12M18 6L6 18"
                    color: look.ink
                }
                HoverHandler { id: closeHover }
                TapHandler { onTapped: sheet.visible = false }
                Accessible.role: Accessible.Button
                Accessible.name: i18n("Close")
                Accessible.onPressAction: sheet.visible = false
            }
        }

        // Not drawn: the helper, timers, colors and the pages. They live in
        // here because a Dialog hands everything inside it to mainItem.

        P5Support.DataSource {
            id: asker
            engine: "executable"
            connectedSources: []
            onNewData: (source, data) => {
                disconnectSource(source)
                const then = sheet.waiting[source]
                delete sheet.waiting[source]
                if (then) {
                    then(data["stdout"] || "", data["exit code"], data["stderr"] || "")
                }
            }
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
                    onClicked: sheet.visible = false
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
                            ["mist", i18n("Mist"), i18n("Always light")],
                            ["smoke", i18n("Smoke"), i18n("Always dark")]
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
                            ["seasons", i18n("Through the year"), i18n("Each season its painting")]
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
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: Math.round(width * 236 / 480)
                                    Layout.bottomMargin: 7
                                    source: sheet.art + "series-" + modelData[0] + ".png"
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
                    Repeater {
                        model: [
                            ["hours", i18n("Through the day"), i18n("The painting's light follows the sun where you are, from dawn to night")],
                            ["weather", i18n("Weather"), i18n("Rain, fog and snow where you are soften the painting with mist")],
                            ["placard", i18n("Placard"), i18n("The time and the painting's name on the desktop")],
                            ["dodge", i18n("Bar steps aside"), i18n("The bar slides away when a window comes over it, and back when you point at the bottom of the screen")],
                            ["glass", i18n("Glass"), i18n("See the painting through panels, windows and widgets. Off is lighter on older PCs.")]
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
                spacing: 20
                PageTitle {
                    readonly property string playing: (sheet.outputs.find(o => o.default) || {}).name || ""
                    tone: look
                    entry: sheet.entry("sound")
                    art: sheet.art
                    text: i18n("Sound")
                    detail: playing !== "" ? i18n("Playing through %1", playing) : ""
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
                    visible: sheet.outputs.length > 0
                    text: i18n("Play sound through")
                }
                Card {
                    tone: look
                    visible: sheet.outputs.length > 0
                    Repeater {
                        model: sheet.outputs
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
                    visible: typeof sheet.info.mic === "number"
                    SliderRow {
                        tone: look
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
                        detail: sheet.hours24(Qt.locale()) !== on24 ? i18n("Your clocks change the next time you sign in")
                            : !tappable ? i18n("As your region keeps it")
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
                readonly property var others: sheet.people.filter(p => !p.you)
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
                            model: [[i18n("Open the menu"), ["Meta"]], [i18n("Search"), ["Alt", "Space"]],
                                    [i18n("Files"), ["Meta", "E"]], [i18n("Lock the screen"), ["Meta", "L"]],
                                    [i18n("All your windows"), ["Meta", "W"]], [i18n("The desktop"), ["Meta", "D"]],
                                    [i18n("Switch windows"), ["Alt", "Tab"]], [i18n("A window on one half"), ["Meta", "\u2190", "\u2192"]],
                                    [i18n("A window on the whole screen"), ["Meta", "PgUp"]], [i18n("What you copied"), ["Meta", "V"]],
                                    [i18n("Emoji"), ["Meta", "."]], [i18n("Screenshot"), ["Print"]],
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
                    SettingRow {
                        tone: look
                        divider: false
                        tappable: true
                        title: i18n("Do not disturb")
                        detail: sheet.info.quiet === true ? i18n("Notifications wait quietly in the list") : i18n("Notifications pop up as they come")
                        onTapped: sheet.flip("quiet", "quiet")
                        Switch {
                            tone: look
                            active: sheet.info.quiet === true
                        }
                    }
                    SettingRow {
                        tone: look
                        tappable: true
                        title: i18n("Sounds")
                        detail: i18n("A soft sound with each one")
                        onTapped: sheet.notifyRule("sounds", sheet.notifyInfo.sounds === false)
                        Switch {
                            tone: look
                            active: sheet.notifyInfo.sounds !== false
                        }
                    }
                }
                Caption {
                    tone: look
                    text: i18n("Quiet by itself")
                }
                Card {
                    tone: look
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
                            title: modelData[1]
                            detail: modelData[2]
                            onTapped: sheet.notifyRule(modelData[0], sheet.notifyInfo[modelData[0]] === false)
                            Switch {
                                tone: look
                                active: sheet.notifyInfo[ruleRow.modelData[0]] !== false
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
                    SettingRow {
                        tone: look
                        divider: false
                        title: i18n("Where they appear")
                        Segments {
                            tone: look
                            options: [["clock", i18n("By the clock")], ["topright", i18n("Top right")], ["topcenter", i18n("Top center")]]
                            current: sheet.notifyInfo.place || "clock"
                            onPicked: value => sheet.notifyPopups("place", value)
                        }
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
                    Repeater {
                        model: sheet.notifyInfo.apps || []
                        SettingRow {
                            id: appRow
                            required property var modelData
                            required property int index
                            tone: look
                            divider: index > 0
                            tappable: true
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
                            detail: modelData.onWindows ? i18n("Its anti-cheat only allows Windows. It's there too.")
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
                    text: i18n("Which games need Windows comes from AreWeAntiCheatYet.")
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

        Component {
            id: windowsPage
            ColumnLayout {
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
                                    : sheet.asking ? i18n("Restart in Windows?")
                                    : (sheet.pc.notice || "") !== "" ? i18n("The last trip didn't reach Windows")
                                    : sheet.pc.setup === "waiting" || sheet.pc.setup === "preparing" ? i18n("Getting Windows ready")
                                    : sheet.pc.setup === "pending" ? i18n("Windows is ready to install")
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
                                    : sheet.asking ? i18n("Your PC restarts in Windows. Open apps close, so save your work first.")
                                    : sheet.pc.windows === "Ready" || (sheet.pc.windows || "") === "" ? i18n("Games that need Windows start there, and you come back here when you quit.")
                                    : i18n("Windows: %1. Check Monet below to see what's missing.", i18n(sheet.pc.windows))
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
                            visible: !sheet.switching && sheet.pc.setup !== "waiting" && sheet.pc.setup !== "preparing"
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
                    visible: sheet.games.length > 0
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
                            artwork: modelData.id.indexOf("steam:") === 0
                                ? "https://cdn.cloudflare.steamstatic.com/steam/apps/" + modelData.id.slice(6) + "/header.jpg" : ""
                            glaze: sheet.glaze(modelData.name)
                            // Plays in Monet too: no restart needed, once it's in Steam here.
                            here: modelData.id.indexOf("steam:") === 0
                                && (sheet.gameMarks.marks || {})[modelData.id.slice(6)] === "here"
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
                    visible: sheet.games.length === 0
                    text: i18n("Your Windows games show up here once Windows has started with Monet Bridge.")
                    color: look.dim
                    font.pixelSize: 14
                    wrapMode: Text.Wrap
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
                    SettingRow {
                        tone: look
                        divider: false
                        tappable: true
                        title: i18n("Ready when you come back")
                        detail: i18n("After Windows, Monet starts your desktop behind the lock screen, so it's there as soon as you type your password.")
                        onTapped: {
                            const on = sheet.ready.on !== true
                            sheet.ready = { on: on }
                            sheet.ask(on ? "ready-on" : "ready-off", out => sheet.ready = sheet.json(out, sheet.ready))
                        }
                        Switch {
                            tone: look
                            active: sheet.ready.on === true
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
                            PlasmaComponents.ProgressBar {
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
                            PlasmaComponents.ProgressBar {
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
            }
        }
    }

    // Seconds with one decimal, the way this PC's region writes them.
    function secs(value) {
        return Number(value).toLocaleString(Qt.locale(), "f", 1)
    }

    // A page of Monet's own, or one KDE's settings show (then this stays put).
    function go(entry) {
        if (entry.kde)
            ask("kde " + entry.kde)
        else
            page = entry.id
    }

    function kdePage() {
        return ({ wifi: "wifi", bluetooth: "bluetooth", display: "display", sound: "sound", datetime: "datetime",
                  users: "users", input: "input", power: "power", notifications: "notifications", apps: "apps",
                  accessibility: "access" })[page] || "all"
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
