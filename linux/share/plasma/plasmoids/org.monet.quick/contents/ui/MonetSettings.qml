/*
 * Monet Settings: one glass sheet with the settings people actually change.
 * The glass is the Plasma style's dialog; the pages sit on solid paper (or
 * smoke) so text is always easy to read. Anything rarer is one click away
 * in KDE's System Settings ("More settings in KDE").
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
    property string page: "light"

    readonly property string art: "file://@DATADIR@/monet/settings/"
    readonly property var pages: [
        { id: "light", name: i18n("Light & Wallpaper"), glyph: "M5 15a7 7 0 0 1 14 0M3 19h18",
          words: "light wallpaper painting hours mist smoke dark mode glass placard clock theme appearance colors" },
        { id: "wifi", name: i18n("Wi-Fi"), glyph: "M4 10a12 12 0 0 1 16 0M7 13.5a7.5 7.5 0 0 1 10 0M10 17a3 3 0 0 1 4 0",
          words: "wifi wi-fi wireless network internet password" },
        { id: "bluetooth", name: i18n("Bluetooth"), glyph: "M7 7l10 10-5 5V2l5 5L7 17",
          words: "bluetooth headphones controller gamepad mouse keyboard pair" },
        { id: "display", name: i18n("Display"), glyph: "M4 5h16v11H4zM10 20h4",
          words: "display screen brightness night light monitor resolution scale size" },
        { id: "sound", name: i18n("Sound"), glyph: "M5 10h3l5-4v12l-5-4H5zM17 9a4.5 4.5 0 0 1 0 6",
          words: "sound volume speakers headphones microphone mic audio output" },
        { id: "windows", name: i18n("Windows & Games"), glyph: "M9 6.5L18 12l-9 5.5z", filled: true,
          words: "windows games play anti-cheat steam restart boot doctor check" },
        { id: "updates", name: i18n("Updates"), glyph: "M12 4v11M7 10l5 5 5-5M5 20h14",
          words: "updates update version upgrade new" },
        { id: "about", name: i18n("About Monet"), glyph: "M12 7.5h.01M12 11v6",
          words: "about pc computer specs graphics gpu processor cpu memory ram storage disk version" }
    ]

    // What the helper reported.
    property var info: ({})
    property var prefs: ({ hours: true, placard: true, glass: true })
    property var nets: []
    property var devices: []
    property var outputs: []
    property var games: []
    property var pc: ({})
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

    title: i18n("Settings")
    location: PlasmaCore.Types.Floating
    hideOnWindowDeactivate: false
    visible: false

    function open(which) {
        if (which && pages.some(p => p.id === which)) {
            page = which
        }
        x = Math.round(area.x + (area.width - mainItem.width) / 2)
        y = Math.round(area.y + (area.height - mainItem.height) / 2 - area.height * 0.03)
        visible = true
        raise()
        requestActivate()
        load()
    }

    onPageChanged: {
        joining = ""
        asking = null
        if (visible) {
            load()
        }
    }

    // Running the helper ----------------------------------------------------

    property var waiting: ({})

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
            ask("wifi-list", out => sheet.nets = sheet.json(out, []))
        } else if (page === "bluetooth") {
            ask("bt-list", out => sheet.devices = sheet.json(out, []))
        } else if (page === "sound") {
            ask("outputs", out => sheet.outputs = sheet.json(out, []))
        } else if (page === "windows") {
            call(monet + " games --json", out => sheet.games = sheet.json(out, []))
        }
        if (page === "windows" || page === "updates" || page === "about") {
            ask("about", out => sheet.pc = sheet.json(out, sheet.pc))
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
    Timer {
        id: rescan
        interval: 4000
        onTriggered: sheet.ask("wifi-list", out => sheet.nets = sheet.json(out, []))
    }

    function pref(key) {
        const on = prefs[key] === false
        const next = Object.assign({}, prefs)
        next[key] = on
        prefs = next
        tell("pref " + key + (on ? " on" : " off"))
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

    // Monet never updates by itself: first look, then install if asked.
    function checkUpdates() {
        updateState = "checking"
        ask("update-check", out => {
            const found = sheet.json(out, { ok: false })
            sheet.updateFound = found
            sheet.updateMessage = found.message || ""
            sheet.updateState = !found.ok ? "failed" : found.system || found.apps > 0 ? "available" : "none"
        })
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
            return found.version ? i18n("Monet %1 is ready", found.version) : i18n("A new Monet is ready")
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

    function glaze(name) {
        const glazes = [["#E2603A", "#5B2350"], ["#3F9A89", "#1C3556"], ["#9C7BC0", "#2B2547"],
                        ["#5C88D0", "#1B2546"], ["#F0A048", "#7A3326"], ["#D46A8C", "#2E2A55"]]
        let h = 0
        for (let i = 0; i < name.length; i++) {
            h = (Math.imul(h, 31) + name.charCodeAt(i)) >>> 0
        }
        return glazes[h % glazes.length]
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
            layer.enabled: true
            layer.samples: 4
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

    component PageTitle: ColumnLayout {
        id: heading
        property var tone
        property string text
        property string detail
        Layout.fillWidth: true
        spacing: 6
        Text {
            Layout.fillWidth: true
            text: heading.text
            color: heading.tone.ink
            font.family: "Fraunces 72pt SuperSoft"
            font.weight: Font.Light
            font.pixelSize: 30
            elide: Text.ElideRight
        }
        Text {
            Layout.fillWidth: true
            visible: heading.detail !== ""
            text: heading.detail
            color: heading.tone.dim
            font.pixelSize: 14
            wrapMode: Text.Wrap
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
                Layout.fillWidth: true
                text: row.title
                color: row.tone.ink
                font.pixelSize: 14
                font.weight: row.strong ? Font.DemiBold : Font.Medium
                elide: Text.ElideRight
            }
            Text {
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
            Text {
                Layout.preferredWidth: 120
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

    // The game covers on Windows & Games.
    component Cover: Item {
        id: cover
        property string name
        property string artwork
        property var glaze: ["#5C88D0", "#1B2546"]
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
        width: Math.min(1000, sheet.area.width - 64)
        height: Math.min(660, sheet.area.height - 96)
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
                    color: look.dark ? Qt.rgba(0, 0, 0, 0.2) : Qt.rgba(1, 1, 1, 0.4)
                    border.width: search.activeFocus ? 2 : 0
                    border.color: look.lily
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

                Repeater {
                    model: sheet.pages
                    Rectangle {
                        id: navItem
                        readonly property bool current: sheet.page === modelData.id
                        Layout.fillWidth: true
                        Layout.preferredHeight: visible ? 40 : 0
                        visible: side.matches(modelData)
                        radius: 12
                        color: current ? (look.dark ? Qt.rgba(1, 1, 1, 0.15) : Qt.rgba(1, 1, 1, 0.55))
                            : navHover.hovered ? (look.dark ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.3)) : "transparent"
                        Behavior on color { ColorAnimation { duration: Math.round(140 * sheet.speed) } }
                        border.width: activeFocus ? 2 : 0
                        border.color: look.lily
                        activeFocusOnTab: true
                        Keys.onSpacePressed: sheet.page = modelData.id
                        Keys.onReturnPressed: sheet.page = modelData.id

                        RowLayout {
                            anchors.fill: parent
                            anchors.leftMargin: 8
                            anchors.rightMargin: 8
                            spacing: 12
                            // A swatch cut from the paintings, with a white mark.
                            Item {
                                Layout.preferredWidth: 28
                                Layout.preferredHeight: 28
                                Image {
                                    anchors.fill: parent
                                    source: sheet.art + "swatch-" + modelData.id + ".png"
                                    sourceSize: Qt.size(56, 56)
                                    smooth: true
                                }
                                Glyph {
                                    anchors.centerIn: parent
                                    anchors.verticalCenterOffset: 1
                                    width: 16
                                    height: 16
                                    path: modelData.glyph
                                    filled: modelData.filled === true
                                    color: Qt.rgba(0, 0, 0, 0.3)
                                }
                                Glyph {
                                    anchors.centerIn: parent
                                    width: 16
                                    height: 16
                                    path: modelData.glyph
                                    filled: modelData.filled === true
                                }
                            }
                            Text {
                                Layout.fillWidth: true
                                text: modelData.name
                                color: look.ink
                                opacity: navItem.current ? 1 : 0.88
                                font.pixelSize: 14
                                font.weight: navItem.current ? Font.DemiBold : Font.Normal
                                elide: Text.ElideRight
                            }
                        }
                        HoverHandler { id: navHover }
                        TapHandler { onTapped: sheet.page = modelData.id }
                        Accessible.role: Accessible.PageTab
                        Accessible.name: modelData.name
                        Accessible.selected: current
                        Accessible.onPressAction: sheet.page = modelData.id
                    }
                }

                Text {
                    Layout.fillWidth: true
                    Layout.leftMargin: 10
                    Layout.topMargin: 8
                    visible: !sheet.pages.some(p => side.matches(p))
                    text: i18n("Nothing here by that name. Try More settings in KDE.")
                    color: look.dim
                    font.pixelSize: 13
                    wrapMode: Text.Wrap
                }

                Item { Layout.fillHeight: true }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 34
                    radius: 10
                    color: kdeHover.hovered ? (look.dark ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.3)) : "transparent"
                    Text {
                        anchors.left: parent.left
                        anchors.leftMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        text: i18n("More settings in KDE ›")
                        color: look.ink
                        opacity: 0.78
                        font.pixelSize: 13
                        font.weight: Font.Medium
                    }
                    HoverHandler { id: kdeHover }
                    TapHandler { onTapped: sheet.ask("kde " + sheet.kdePage()) }
                    Accessible.role: Accessible.Link
                    Accessible.name: i18n("More settings in KDE")
                    Accessible.onPressAction: sheet.ask("kde " + sheet.kdePage())
                }
            }

            function matches(entry) {
                const words = search.text.trim().toLowerCase()
                return words === "" || (entry.name + " " + entry.words).toLowerCase().indexOf(words) !== -1
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
                        sound: soundPage, windows: windowsPage, updates: updatesPage, about: aboutPage
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
    }

    function kdePage() {
        return ({ wifi: "wifi", bluetooth: "bluetooth", display: "display", sound: "sound", about: "about" })[page] || "all"
    }

    // Pages -----------------------------------------------------------------

    Component {
        id: lightPage
        ColumnLayout {
            spacing: 20
            PageTitle {
                tone: look
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
                                Layout.fillWidth: true
                                Layout.leftMargin: 4
                                text: modelData[1]
                                color: look.ink
                                font.pixelSize: 14
                                font.weight: Font.DemiBold
                                elide: Text.ElideRight
                            }
                            Text {
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
            Card {
                tone: look
                Repeater {
                    model: [
                        ["hours", i18n("The Hours"), i18n("The painting drifts from dawn to night as the day goes")],
                        ["placard", i18n("Placard"), i18n("The time and the painting's name on the desktop")],
                        ["glass", i18n("Glass"), i18n("See the painting through panels and windows")]
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
        }
    }

    Component {
        id: wifiPage
        ColumnLayout {
            spacing: 20
            PageTitle {
                tone: look
                text: i18n("Wi-Fi")
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
                    title: i18n("Looking for networks…")
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
                            lead: Bars {
                                tone: look
                                level: modelData.signal > 66 ? 3 : modelData.signal > 33 ? 2 : 1
                            }
                            onTapped: {
                                sheet.joinState = ""
                                if (modelData.secure) {
                                    sheet.joining = sheet.joining === modelData.name ? "" : modelData.name
                                } else {
                                    sheet.joining = modelData.name
                                    sheet.join(modelData.name, "")
                                }
                            }
                            Text {
                                text: sheet.joining === modelData.name && sheet.joinState === "joining" ? i18n("Joining…")
                                    : modelData.secure ? i18n("Secured") : i18n("Open")
                                color: look.dim
                                font.pixelSize: 13
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
                tone: look
                text: i18n("Bluetooth")
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
                text: i18n("Display")
            }
            Card {
                tone: look
                SliderRow {
                    tone: look
                    divider: false
                    visible: typeof sheet.info.brightness === "number"
                    title: i18n("Brightness")
                    from: 1
                    value: sheet.info.brightness || 50
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
                tone: look
                text: i18n("Sound")
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
                        Check {
                            tone: look
                            active: modelData.default === true
                        }
                    }
                }
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
        id: windowsPage
        ColumnLayout {
            spacing: 20
            PageTitle {
                tone: look
                text: i18n("Windows & Games")
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
                            Layout.fillWidth: true
                            text: sheet.switching ? i18n("Your PC restarts in a moment.")
                                : sheet.switchProblem !== "" ? sheet.switchProblem
                                : !sheet.asking && (sheet.pc.notice || "") !== "" ? sheet.pc.notice
                                : sheet.pc.setup === "waiting" || sheet.pc.setup === "preparing" ? i18n("Monet is downloading Windows for your games. Keep using your PC; Monet asks before it restarts.")
                                : sheet.pc.setup === "pending" ? i18n("Restart to install it. It takes about 10 minutes, then you're back in Monet.")
                                : sheet.asking && sheet.asking.id ? i18n("Your PC restarts in Windows and opens the game. When you quit, you're back here. Save your work first.")
                                : sheet.asking ? i18n("Your PC restarts in Windows. Open apps close, so save your work first.")
                                : sheet.pc.windows === "Ready" || (sheet.pc.windows || "") === "" ? i18n("Games that need Windows start there, and you come back here when you quit.")
                                : i18n("Windows: %1. Check Monet below to see what's missing.", sheet.pc.windows)
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
                        onPicked: {
                            sheet.switchProblem = ""
                            sheet.asking = modelData
                        }
                    }
                }
            }
            Text {
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
        }
    }

    Component {
        id: updatesPage
        ColumnLayout {
            spacing: 20
            PageTitle {
                tone: look
                text: i18n("Updates")
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
                            Layout.fillWidth: true
                            text: sheet.updateTitle()
                            color: look.ink
                            font.pixelSize: 15
                            font.weight: Font.DemiBold
                            wrapMode: Text.Wrap
                        }
                        Text {
                            Layout.fillWidth: true
                            text: sheet.updateDetail()
                            color: sheet.updateState === "failed" ? "#E0603A" : look.dim
                            font.pixelSize: 13
                            wrapMode: Text.Wrap
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
            Text {
                Layout.fillWidth: true
                text: i18n("Monet never updates by itself. When you install an update, the new version starts the next time you restart, and the one before stays in the start menu, just in case.")
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
                        text: "Monet"
                        color: "#FFFFFF"
                        font.family: "Fraunces 72pt SuperSoft"
                        font.weight: Font.Light
                        font.pixelSize: 48
                        font.letterSpacing: -1.2
                    }
                    Text {
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
                        [i18n("Windows"), sheet.pc.windows === "Ready" ? i18n("Ready for games") : sheet.pc.windows]
                    ].filter(r => r[1])
                    SettingRow {
                        tone: look
                        divider: index > 0
                        strong: false
                        title: modelData[0]
                        Text {
                            width: Math.min(implicitWidth, 380)
                            text: modelData[1]
                            color: look.ink
                            font.pixelSize: 14
                            elide: Text.ElideRight
                        }
                    }
                }
            }
            Pill {
                tone: look
                text: i18n("More about this PC…")
                onClicked: sheet.ask("kde about")
            }
        }
    }
}
