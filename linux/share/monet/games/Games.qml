/*
 * Games: every game you have in one library, Steam's, Heroic's and Lutris' in Monet and the
 * ones in Windows, each saying where it plays (`monet-quick library`). Down the side: the
 * library's sections (favorites, recently played, each side) and each store; the rest is the
 * covers, sorted by when they were played, by name, play time or size. A cover opens its
 * game's page (its picture, how long it's been played, Play). A game that plays on Monet
 * starts right away; one that plays on Windows asks once, then the sun sets and the PC
 * restarts in Windows with the game (the `monet` command).
 *
 * monet-games opens it, and gives it `helper` (which runs monet-quick and monet), its i18n
 * calls, and where Monet's pictures are (`art`, `texture`).
 */
import QtCore
import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Templates as T
import QtQuick.Window
import org.kde.kirigami as Kirigami

MonetWindow {
    id: root
    title: i18n("Games")
    width: 1140
    height: 760
    minimumWidth: 760
    minimumHeight: 520
    visible: true
    // See-through: WindowGlass is its glass.
    color: "transparent"

    // [{id, name, store, plays, why, here, windows, shared, move, progress, locate, art, last,
    // minutes, size, favorite, tall, hero}] (monet-quick library).
    property var games: []
    // Windows' Games folder (monet-quick shared): {state, steam, mine, hint, ...}.
    property var shared: ({})
    property bool sharing: false
    property bool loaded: false
    // What the covers are: "all", "favorites", "recent", "monet", "windows" or "store:STORE".
    property string section: "all"
    // How they're sorted: "recent", "name", "playtime" or "size" (kept for next time).
    property string sort: "recent"
    property string query: ""
    // The game whose page is open (by id, so a refresh keeps it on the page); "" for the covers.
    property string pageId: ""
    readonly property var current: games.find(g => g.id === pageId) || null
    // The game the sheet asks about; null for "just open Windows".
    property var asking: null
    property bool sheetOpen: false
    property string problem: ""
    // Whether this PC has a Windows to restart in (`monet` says Not found on a Monet-only PC).
    property bool windowsHere: true
    // Someone finding their way with the keys: the game they're on gets a ring.
    property bool keys: false
    property string keyed: ""
    property var waiting: ({})
    readonly property string texture: brush
    readonly property real speed: Kirigami.Units.longDuration / 200

    Settings {
        category: "Library"
        property alias windowWidth: root.width
        property alias windowHeight: root.height
        property alias sort: root.sort
    }

    // Runs monet-quick ("helper") or monet with its words, then `then(out, code, err)`.
    function run(command, then) {
        const ticket = helper.run(command)
        if (then)
            waiting[ticket] = then
    }
    Connections {
        target: helper
        function onDone(ticket, out, code, err) {
            const then = root.waiting[ticket]
            delete root.waiting[ticket]
            if (then)
                then(out, code, err)
        }
        // Games opened again: this one, forward.
        function onWanted() {
            if (root.visibility === Window.Minimized)
                root.visibility = Window.Windowed
            root.raise()
            root.requestActivate()
        }
    }

    function refresh() {
        run(["helper", "library"], out => {
            try {
                games = JSON.parse(out)
            } catch (e) {
                // Keep what's shown rather than an empty library.
            }
            if (!loaded)
                Qt.callLater(grid.positionViewAtBeginning)
            loaded = true
        })
        run(["helper", "shared"], out => {
            try {
                shared = JSON.parse(out)
            } catch (e) {
            }
        })
    }
    Component.onCompleted: {
        refresh()
        run(["monet"], out => root.windowsHere = !/Windows\s+(Not found|Unavailable)/.test(out))
    }
    onActiveChanged: if (active && loaded) refresh()
    // While Steam is downloading a game: how far it is, every few seconds.
    Timer {
        interval: 5000
        repeat: true
        running: root.active && root.games.some(g => typeof g.progress === "number")
        onTriggered: root.refresh()
    }

    // Playing ---------------------------------------------------------------

    function play(game) {
        if (game.plays === "monet")
            run(["helper", "play", game.here])
        else
            ask(game)
    }
    function ask(game) {
        problem = ""
        asking = game
        sheetOpen = true
    }
    // To Windows: with the game when Windows has it, else just Windows, to install it there.
    function go() {
        const game = asking && asking.windows !== "" ? asking : null
        sheetOpen = false
        sunset.begin(game ? game.name : "")
        launch.command = game ? ["monet", "play", game.windows] : ["monet", "windows"]
        launch.start()
    }
    // Let the sun start setting before the PC goes.
    Timer {
        id: launch
        property var command: []
        interval: Math.round(900 * root.speed) + 100
        onTriggered: root.run(command, (out, code, err) => {
            if (code !== 0) {
                // Switching didn't happen: the library back, and why (the plain first part;
                // the technical rest is for monet's own log).
                sunset.close()
                root.problem = (err || "").trim().split("\n\n")[0] || i18n("Monet couldn't switch to Windows.")
                root.sheetOpen = true
            }
        })
    }
    // A game that needs Windows, in Monet's own Steam folder: its page in Steam, to move it
    // to Windows games (Properties, Installed Files), where Windows plays it.
    function showInSteam(game) {
        sheetOpen = false
        run(["helper", "steam-page", game.id.slice(6)])
    }
    // Steam itself, from its menu entry (the helper takes the entry's name as hex).
    function openSteam() {
        let out = ""
        for (const c of "steam.desktop")
            out += c.charCodeAt(0).toString(16).padStart(2, "0")
        run(["helper", "launch", out])
    }
    // Windows games into Steam here (Steam closes for a moment): from then on a game
    // installed there plays on both sides.
    function addToSteam() {
        sharing = true
        run(["helper", "steam-share", "now"], out => {
            try {
                shared = JSON.parse(out)
            } catch (e) {
            }
            sharing = false
            refresh()
        })
    }
    function setFavorite(game, on) {
        games = games.map(g => g.id === game.id ? Object.assign({}, g, { favorite: on }) : g)
        run(["helper", "favorite", game.id, on ? "on" : "off"])
    }
    function openPage(game) {
        pageId = game.id
        keyed = game.id
        Qt.callLater(() => gamePage.focusPlay())
    }
    function closePage() {
        pageId = ""
        Qt.callLater(() => grid.forceActiveFocus())
    }

    // Words -----------------------------------------------------------------

    function storeName(store) {
        return { steam: "Steam", epic: "Epic", gog: "GOG", amazon: "Amazon", heroic: "Heroic", lutris: "Lutris",
                 riot: "Riot", battlenet: "Battle.net", ubisoft: "Ubisoft", rockstar: "Rockstar", ea: "EA", custom: i18n("Windows"),
                 program: i18n("Windows") }[store] || store
    }
    function lastText(last) {
        if (!last)
            return i18n("Never")
        const then = new Date(last * 1000)
        const today = new Date()
        today.setHours(0, 0, 0, 0)
        const days = Math.ceil((today - then) / 86400000)
        return then >= today ? i18n("Today")
            : days <= 1 ? i18n("Yesterday")
            : days < 7 ? i18np("%1 day ago", "%1 days ago", days)
            : then.toLocaleDateString(Qt.locale(), Locale.ShortFormat)
    }
    function timeText(minutes) {
        return !minutes ? i18n("Not played yet")
            : minutes < 90 ? i18np("%1 minute", "%1 minutes", minutes)
            : i18np("%1 hour", "%1 hours", Math.round(minutes / 60))
    }
    function sizeText(bytes) {
        return !bytes ? ""
            : bytes >= 1e9 ? i18n("%1 GB", (bytes / 1e9).toLocaleString(Qt.locale(), "f", 1))
            : i18n("%1 MB", Math.max(1, Math.round(bytes / 1e6)))
    }
    // Under a cover: its store, and how long it's been played or its download.
    function detail(game) {
        return typeof game.progress === "number" ? i18n("%1 · Downloading, %2%", storeName(game.store), game.progress)
            : game.minutes > 0 ? storeName(game.store) + " · " + timeText(game.minutes)
            : storeName(game.store)
    }
    // A painted cover for games without artwork: a glaze from the paintings.
    readonly property var glazes: [
        ["#E2603A", "#5B2350"], ["#3F9A89", "#1C3556"], ["#9C7BC0", "#2B2547"],
        ["#5C88D0", "#1B2546"], ["#F0A048", "#7A3326"], ["#D46A8C", "#2E2A55"]
    ]
    function glaze(name) {
        let h = 0
        for (let i = 0; i < name.length; i++)
            h = (Math.imul(h, 31) + name.charCodeAt(i)) >>> 0
        return glazes[h % glazes.length]
    }

    // The library ------------------------------------------------------------

    // Without accents or capitals on either side: "etretat" finds "Étretat".
    function fold(text) {
        return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
    }
    function inSection(g, which) {
        return which === "all" ? true
            : which === "favorites" ? g.favorite === true
            : which === "recent" ? g.last > 0
            : which === "monet" ? g.plays === "monet"
            : which === "windows" ? g.plays === "windows" || g.windows !== ""
            : g.store === which.slice(6)
    }
    readonly property bool bothSides: games.some(g => g.plays === "monet") && games.some(g => g.plays === "windows" || g.windows !== "")
    readonly property var sections: [
        { id: "all", name: i18n("All games"), swatch: "games",
          glyph: "M7.5 8h9a4.5 4.5 0 0 1 4.5 4.5v1a3.5 3.5 0 0 1-6.4 2L14 14.5h-4l-.6 1A3.5 3.5 0 0 1 3 13.5v-1A4.5 4.5 0 0 1 7.5 8zM8 10.5v3M6.5 12h3M15.5 11.5h.01M17.5 13h.01" },
        { id: "favorites", name: i18n("Favorites"), swatch: "light", filled: true,
          glyph: "M12 3.8l2.5 5.1 5.6.8-4 3.9.9 5.6-5-2.6-5 2.6.9-5.6-4-3.9 5.6-.8z" },
        { id: "recent", name: i18n("Recently played"), swatch: "datetime", glyph: "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 7v5l3 2" },
        { id: "monet", name: i18n("Plays on Monet"), swatch: "display", side: true, glyph: "M5 15a7 7 0 0 1 14 0M3 19h18M12 4v2.5M5.2 7.2l1.6 1.6M18.8 7.2l-1.6 1.6" },
        { id: "windows", name: i18n("Plays on Windows"), swatch: "windows", side: true,
          glyph: "M4 5.5l7-1v7H4zM13 4.2l7-1v8.3h-7zM4 13.5h7v7l-7-1zM13 13.5h7v8.3l-7-1z" }
    ]
    // Each store with games, by name; launchers here have their own pictures.
    readonly property var stores: [...new Set(games.map(g => g.store))]
        .sort((a, b) => storeName(a).localeCompare(storeName(b)))
        .map(s => ({ id: "store:" + s, name: storeName(s),
                     icon: { steam: "steam", lutris: "net.lutris.Lutris", heroic: "com.heroicgameslauncher.hgl",
                             epic: "com.heroicgameslauncher.hgl", gog: "com.heroicgameslauncher.hgl",
                             amazon: "com.heroicgameslauncher.hgl" }[s] || "" }))
    readonly property var entries: sections.filter(s => !s.side || bothSides).concat(stores)
    readonly property var sectionEntry: entries.find(e => e.id === section) || sections[0]
    readonly property var shown: {
        const words = fold(query.trim())
        const by = section === "recent" ? "recent" : sort
        const named = (a, b) => a.name.localeCompare(b.name)
        return games.filter(g => inSection(g, section) && (words === "" || fold(g.name).indexOf(words) !== -1))
            .sort(by === "name" ? named
                : by === "playtime" ? (a, b) => (b.minutes || 0) - (a.minutes || 0) || named(a, b)
                : by === "size" ? (a, b) => (b.size || 0) - (a.size || 0) || named(a, b)
                : (a, b) => (b.last || 0) - (a.last || 0) || named(a, b))
    }
    // Played lately, on top of every game: where you left off.
    readonly property var lately: section === "all" && query === ""
        ? games.filter(g => g.last > 0).sort((a, b) => b.last - a.last).slice(0, 4) : []
    // A section gone (its store's last game uninstalled): back to every game.
    onEntriesChanged: if (loaded && !entries.some(e => e.id === section)) section = "all"
    // A new list starts at its top (the shelf above it too, which the view leaves above
    // the top when it grows in after the covers).
    onSectionChanged: {
        pageId = ""
        Qt.callLater(grid.positionViewAtBeginning)
    }
    onQueryChanged: {
        if (query !== "")
            pageId = ""
        Qt.callLater(grid.positionViewAtBeginning)
    }
    onSortChanged: Qt.callLater(grid.positionViewAtBeginning)

    // Colors: Settings' own, mist or smoke as Monet's light chose ---------------
    QtObject {
        id: look
        readonly property bool dark: Kirigami.Theme.backgroundColor.hslLightness < 0.5
        readonly property color glass: dark ? "#1E1D1B" : "#ECE9E3"
        readonly property color ink: dark ? "#F1EEE8" : "#1C1B19"
        readonly property color dim: dark ? Qt.rgba(0.945, 0.933, 0.91, 0.62) : Qt.rgba(0.11, 0.106, 0.098, 0.6)
        readonly property color wash: dark ? Qt.rgba(1, 1, 1, 0.05) : Qt.rgba(0.11, 0.106, 0.098, 0.035)
        readonly property color wash2: dark ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(0.11, 0.106, 0.098, 0.07)
        readonly property color press: dark ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(0.11, 0.106, 0.098, 0.11)
        readonly property color line: dark ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(0.11, 0.106, 0.098, 0.08)
        readonly property color paper: dark ? "#262523" : "#FBFAF7"
        readonly property color lily: dark ? "#4DB4A0" : "#357F72"
        readonly property real speed: root.speed
    }

    Shortcut {
        sequences: [StandardKey.Find]
        onActivated: search.forceActiveFocus()
    }
    Shortcut {
        sequences: [StandardKey.Refresh]
        onActivated: root.refresh()
    }

    // A canvas under the side, as faint as paper's grain.
    Image {
        anchors.fill: parent
        anchors.margins: 14
        source: texture
        fillMode: Image.Tile
        opacity: look.dark ? 0.05 : 0.07
    }

    // Under the item it's for (a cover, or a page's "more"), or where the pointer is.
    function showMenu(game, item, below) {
        const items = [["play", game.plays === "windows" && game.windows !== "" ? i18n("Play on Windows") : i18n("Play")]]
        if (current === null)
            items.push(["page", i18n("Open its page")])
        if (game.plays === "monet" && game.windows !== "")
            items.push(["windows", i18n("Play on Windows")])
        // Players' reports can be out of date: try it here all the same.
        if (game.plays === "windows" && game.why === "reports")
            items.push(["monet", i18n("Play in Monet")])
        items.push(["favorite", game.favorite ? i18n("Remove from favorites") : i18n("Add to favorites")])
        if (game.store === "steam" && game.here !== "") {
            items.push(["steam", i18n("Show in Steam")])
            // Steam asks itself, and says what goes.
            items.push(["uninstall", i18n("Uninstall…")])
        }
        menu.game = game
        menu.items = items
        const point = below ? item.mapToItem(body, 0, item.height + 6)
            : item.mapToItem(body, item.width / 2, item.height / 3)
        menu.x = below && !body.LayoutMirroring.enabled ? point.x + item.width - menu.implicitWidth : point.x
        menu.y = point.y
        menu.open()
    }
    function choose(what) {
        const game = menu.game
        menu.close()
        if (what === "play")
            play(game)
        else if (what === "page")
            openPage(game)
        else if (what === "windows")
            ask(game)
        else if (what === "monet")
            run(["helper", "play", game.here])
        else if (what === "favorite")
            setFavorite(game, !game.favorite)
        else if (what === "steam")
            run(["helper", "steam-page", game.id.slice(6)])
        else if (what === "uninstall")
            run(["helper", "steam-uninstall", game.id.slice(6)])
    }

    // Everything drawn, mirrored for a right-to-left language (a Window itself can't be).
    Item {
        id: body
        anchors.fill: parent
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true

        // The side: the name, search, the sections and the stores ----------------------
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
                anchors.bottomMargin: 12
                spacing: 4

                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.leftMargin: 10
                    Layout.bottomMargin: 12
                    text: i18n("Games")
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
                    color: look.dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.55)
                    border.width: search.activeFocus ? 2 : 1
                    border.color: search.activeFocus ? look.lily : look.dark ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(1, 1, 1, 0.9)
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
                            text: root.query
                            onTextChanged: root.query = text
                            Accessible.role: Accessible.EditableText
                            Accessible.name: i18n("Find a game")
                            // Enter plays the one game it finds, else goes to the covers.
                            onAccepted: {
                                if (root.shown.length === 1)
                                    root.play(root.shown[0])
                                else
                                    grid.enter()
                            }
                            Keys.onDownPressed: grid.enter()
                            Keys.onEscapePressed: event => {
                                if (text !== "")
                                    root.query = ""
                                else
                                    event.accepted = false
                            }
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                anchors.fill: parent
                                verticalAlignment: Text.AlignVCenter
                                visible: search.text === "" && search.preeditText === ""
                                text: i18n("Find a game")
                                color: look.dim
                                font: search.font
                                elide: Text.ElideRight
                            }
                        }
                    }
                }

                // The sections, then the stores; the current one's pebble of glass glides to it.
                Flickable {
                    id: navList
                    MouseScroll { view: navList }
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentHeight: navColumn.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    interactive: contentHeight > height

                    // The chosen section in view (a store far down the list, on a short window).
                    function reveal() {
                        const shown = pebble.target
                        if (shown && (shown.y < contentY || shown.y + shown.height > contentY + height))
                            contentY = Math.max(0, Math.min(shown.y - (height - shown.height) / 2, contentHeight - height))
                    }
                    Connections {
                        target: root
                        function onSectionChanged() { Qt.callLater(navList.reveal) }
                    }

                    Rectangle {
                        id: pebble
                        readonly property Item target: navRepeater.count > 0
                            ? navRepeater.itemAt(root.entries.findIndex(e => e.id === root.section)) : null
                        width: navColumn.width
                        height: target ? target.height : 0
                        y: target ? target.y : 0
                        visible: target !== null
                        radius: 12
                        color: look.dark ? Qt.rgba(1, 1, 1, 0.13) : Qt.rgba(1, 1, 1, 0.75)
                        border.width: 1
                        border.color: look.dark ? Qt.rgba(1, 1, 1, 0.18) : Qt.rgba(1, 1, 1, 0.95)
                        Behavior on y {
                            NumberAnimation { duration: Math.round(320 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] }
                        }
                    }

                    ColumnLayout {
                        id: navColumn
                        width: navList.width
                        spacing: 2

                        Repeater {
                            id: navRepeater
                            model: root.entries
                            Rectangle {
                                id: navItem
                                required property var modelData
                                required property int index
                                readonly property bool current: root.section === modelData.id
                                readonly property int count: root.games.filter(g => root.inSection(g, modelData.id)).length
                                Layout.fillWidth: true
                                Layout.preferredHeight: 34
                                // The stores, a little apart under their caption.
                                Layout.topMargin: modelData.id.startsWith("store:") && index > 0
                                    && !root.entries[index - 1].id.startsWith("store:") ? 34 : 0
                                radius: 12
                                color: navMouse.containsMouse && !current ? (look.dark ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.4)) : "transparent"
                                Behavior on color { ColorAnimation { duration: Math.round(140 * root.speed) } }
                                border.width: activeFocus ? 2 : 0
                                border.color: look.lily
                                activeFocusOnTab: true
                                Keys.onSpacePressed: root.section = modelData.id
                                Keys.onReturnPressed: root.section = modelData.id

                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    visible: navItem.Layout.topMargin > 0
                                    anchors.left: parent.left
                                    anchors.leftMargin: 10
                                    anchors.bottom: parent.top
                                    anchors.bottomMargin: 6
                                    text: i18n("Stores")
                                    color: look.dim
                                    font.pixelSize: 12
                                    font.weight: Font.DemiBold
                                    font.letterSpacing: 0.7
                                    font.capitalization: Font.AllUppercase
                                }

                                RowLayout {
                                    anchors.fill: parent
                                    anchors.leftMargin: 8
                                    anchors.rightMargin: 12
                                    spacing: 12
                                    // A swatch cut from the paintings with a white mark, or the launcher's own picture.
                                    Item {
                                        Layout.preferredWidth: 26
                                        Layout.preferredHeight: 26
                                        Kirigami.Icon {
                                            anchors.fill: parent
                                            visible: navItem.modelData.icon !== undefined && navItem.modelData.icon !== ""
                                            source: navItem.modelData.icon || ""
                                        }
                                        Item {
                                            anchors.fill: parent
                                            visible: !navItem.modelData.icon
                                            Image {
                                                anchors.fill: parent
                                                source: art + "swatch-" + (navItem.modelData.swatch || "windows") + ".png"
                                                sourceSize: Qt.size(56, 56)
                                                smooth: true
                                            }
                                            Glyph {
                                                anchors.centerIn: parent
                                                anchors.verticalCenterOffset: 1
                                                width: 15
                                                height: 15
                                                path: navItem.modelData.glyph || root.sections[4].glyph
                                                filled: navItem.modelData.filled === true
                                                color: Qt.rgba(0, 0, 0, 0.3)
                                            }
                                            Glyph {
                                                anchors.centerIn: parent
                                                width: 15
                                                height: 15
                                                path: navItem.modelData.glyph || root.sections[4].glyph
                                                filled: navItem.modelData.filled === true
                                            }
                                        }
                                    }
                                    Text {
                                        horizontalAlignment: Text.AlignLeft
                                        Layout.fillWidth: true
                                        text: navItem.modelData.name
                                        color: look.ink
                                        opacity: navItem.current ? 1 : 0.88
                                        font.pixelSize: 14
                                        font.weight: navItem.current ? Font.DemiBold : Font.Normal
                                        elide: Text.ElideRight
                                    }
                                    Text {
                                        horizontalAlignment: Text.AlignLeft
                                        visible: root.loaded
                                        text: navItem.count.toLocaleString(Qt.locale(), "f", 0)
                                        color: look.dim
                                        font.pixelSize: 13
                                        font.features: ({ "tnum": 1 })
                                    }
                                }
                                MouseArea {
                                    id: navMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.section = navItem.modelData.id
                                }
                                Accessible.role: Accessible.PageTab
                                Accessible.name: modelData.name
                                Accessible.selected: current
                                Accessible.onPressAction: root.section = modelData.id
                            }
                        }
                    }
                }

                Pill {
                    Layout.leftMargin: 4
                    visible: root.windowsHere
                    tone: look
                    iconName: "monet-windows"
                    text: i18n("Open Windows")
                    onClicked: root.ask(null)
                }
            }
        }

        // The covers, or a game's page: on paper, so reading never fights the painting ------------
        Rectangle {
            id: pageArea
            anchors.left: side.right
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            anchors.margins: 8
            anchors.leftMargin: 0
            radius: 14
            color: look.paper
            border.width: 1
            border.color: look.dark ? Qt.rgba(1, 1, 1, 0.06) : Qt.rgba(1, 1, 1, 0.9)

            Item {
                id: library
                anchors.fill: parent
                visible: root.current === null

                // The section's name, how many, and the order.
                RowLayout {
                    id: header
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.leftMargin: 32
                    anchors.rightMargin: 24
                    anchors.topMargin: 24
                    spacing: 16
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            text: root.query !== "" ? i18n("Games called “%1”", root.query.trim()) : root.sectionEntry.name
                            color: look.ink
                            elide: Text.ElideRight
                            font.family: "Fraunces 72pt SuperSoft"
                            font.weight: Font.Light
                            font.pixelSize: 30
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            visible: root.loaded
                            text: i18np("%1 game", "%1 games", root.shown.length)
                            color: look.dim
                            font.pixelSize: 13
                        }
                    }
                    // Recent, name, play time or size: the chosen one on a pebble, as Settings' choices are.
                    Rectangle {
                        id: sorts
                        visible: root.section !== "recent" && root.shown.length > 1
                        implicitWidth: sortRow.implicitWidth + 6
                        implicitHeight: 36
                        radius: 18
                        color: look.wash2
                        Accessible.role: Accessible.Grouping
                        Accessible.name: i18n("Sort by")
                        Row {
                            id: sortRow
                            anchors.centerIn: parent
                            spacing: 2
                            Repeater {
                                model: [["recent", i18n("Recent")], ["name", i18n("Name")], ["playtime", i18n("Play time")], ["size", i18n("Size")]]
                                Rectangle {
                                    id: sortChoice
                                    required property var modelData
                                    readonly property bool chosen: root.sort === modelData[0]
                                    width: sortLabel.implicitWidth + 24
                                    height: 30
                                    radius: 15
                                    color: chosen ? (look.dark ? Qt.rgba(1, 1, 1, 0.16) : "#FFFFFF")
                                        : sortMouse.containsMouse ? look.wash2 : "transparent"
                                    border.width: activeFocus ? 2 : 0
                                    border.color: look.lily
                                    activeFocusOnTab: true
                                    Keys.onReturnPressed: root.sort = modelData[0]
                                    Keys.onSpacePressed: root.sort = modelData[0]
                                    Behavior on color { ColorAnimation { duration: Math.round(140 * root.speed) } }
                                    Text {
                                        id: sortLabel
                                        horizontalAlignment: Text.AlignLeft
                                        anchors.centerIn: parent
                                        text: sortChoice.modelData[1]
                                        color: look.ink
                                        opacity: sortChoice.chosen ? 1 : 0.7
                                        font.pixelSize: 13
                                        font.weight: sortChoice.chosen ? Font.DemiBold : Font.Normal
                                    }
                                    MouseArea {
                                        id: sortMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.sort = sortChoice.modelData[0]
                                    }
                                    Accessible.role: Accessible.RadioButton
                                    Accessible.name: modelData[1]
                                    Accessible.checked: chosen
                                }
                            }
                        }
                    }
                }

                // Windows games, not in Steam here yet: one tap, and a game installs once for both.
                Rectangle {
                    id: hint
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: header.bottom
                    anchors.leftMargin: 32
                    anchors.rightMargin: 24
                    anchors.topMargin: visible ? 16 : 0
                    visible: root.shared.state === "open" && root.shared.mine === true && root.shared.steam !== true
                        && root.shared.hint === true
                    height: visible ? hintRow.implicitHeight + 16 : 0
                    radius: 14
                    color: Qt.rgba(0.302, 0.706, 0.627, 0.12)
                    border.width: 1
                    border.color: Qt.rgba(0.302, 0.706, 0.627, 0.4)
                    RowLayout {
                        id: hintRow
                        anchors.fill: parent
                        anchors.margins: 8
                        anchors.leftMargin: 14
                        spacing: 10
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            wrapMode: Text.Wrap
                            color: look.ink
                            font.pixelSize: 13
                            text: i18n("Install each game once: add Windows games to Steam here, and a game you install there plays in Monet and in Windows.")
                        }
                        Pill {
                            tone: look
                            kind: "lily"
                            text: root.sharing ? i18n("Adding…") : i18n("Add to Steam")
                            enabled: !root.sharing
                            onClicked: root.addToSteam()
                        }
                        // Put away for good: a round pebble with a drawn ×.
                        Pill {
                            tone: look
                            glyph: "M7 7l10 10M17 7L7 17"
                            Accessible.name: i18n("Close")
                            onClicked: {
                                root.shared = Object.assign({}, root.shared, { hint: false })
                                root.run(["helper", "shared-hint-off"])
                            }
                        }
                    }
                }

                GridView {
                    id: grid
                    MouseScroll { view: grid }
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: hint.bottom
                    anchors.bottom: parent.bottom
                    anchors.topMargin: 10
                    anchors.leftMargin: 24
                    anchors.rightMargin: 16
                    clip: true
                    model: root.shown
                    // Covers of about 180 pixels, as many as fit; they grow or shrink a little to fill the row.
                    readonly property int columns: Math.max(2, Math.round(width / 185))
                    cellWidth: Math.floor(width / columns)
                    cellHeight: Math.round((cellWidth - 16) * 1.5) + 62
                    boundsBehavior: Flickable.StopAtBounds
                    // A wheel's turn glides (the arrows stay the covers' own).
                    Kirigami.WheelHandler {
                        target: grid
                        filterMouseEvents: !("acceptedButtons" in grid)
                        keyNavigationEnabled: false
                        verticalStepSize: 96
                    }
                    cacheBuffer: cellHeight * 2
                    currentIndex: -1
                    activeFocusOnTab: true
                    keyNavigationEnabled: true
                    Accessible.name: i18n("Games")

                    // From the search (Enter or ↓): the keys go to the covers.
                    function enter() {
                        root.keys = true
                        forceActiveFocus()
                        if (count > 0 && !root.shown.some(g => g.id === root.keyed)) {
                            currentIndex = 0
                            root.keyed = root.shown[0].id
                        }
                    }
                    // The keys: arrows move between games, Enter or Space opens one, the Menu key its
                    // menu, and up from the top row goes back to the search; typing finds a game.
                    Keys.onPressed: event => {
                        if (root.sheetOpen)
                            return
                        root.keys = true
                        const at = root.shown.findIndex(g => g.id === root.keyed)
                        const modifiers = Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier
                        if ([Qt.Key_Left, Qt.Key_Right, Qt.Key_Up, Qt.Key_Down].includes(event.key)) {
                            if (event.key === Qt.Key_Up && at >= 0 && at < columns) {
                                search.forceActiveFocus()
                            } else if (count > 0) {
                                currentIndex = Math.max(at, 0)
                                if (at >= 0) {
                                    if (event.key === Qt.Key_Left) moveCurrentIndexLeft()
                                    else if (event.key === Qt.Key_Right) moveCurrentIndexRight()
                                    else if (event.key === Qt.Key_Up) moveCurrentIndexUp()
                                    else moveCurrentIndexDown()
                                }
                                root.keyed = root.shown[currentIndex].id
                            }
                        } else if ([Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space].includes(event.key) && at >= 0) {
                            root.openPage(root.shown[at])
                        } else if (event.key === Qt.Key_Menu && at >= 0) {
                            currentIndex = at
                            root.showMenu(root.shown[at], currentItem, false)
                        } else if (event.text.length === 1 && event.text > " " && event.text !== "\x7f"
                                   && !(event.modifiers & modifiers)) {
                            root.query += event.text
                            search.forceActiveFocus()
                            search.cursorPosition = search.length
                        } else {
                            return
                        }
                        event.accepted = true
                    }
                    // A refresh keeps the keys on the game they were on.
                    Connections {
                        target: root
                        function onShownChanged() {
                            Qt.callLater(() => {
                                const at = root.shown.findIndex(g => g.id === root.keyed)
                                if (at >= 0)
                                    grid.currentIndex = at
                            })
                        }
                    }

                    // Where you left off: the games played last, wide, above every game.
                    header: Item {
                        width: grid.width
                        height: root.lately.length > 0 ? shelf.height + 30 : 0
                        visible: root.lately.length > 0
                        Text {
                            id: shelfTitle
                            horizontalAlignment: Text.AlignLeft
                            anchors.left: parent.left
                            anchors.leftMargin: 8
                            y: 8
                            text: i18n("Continue playing")
                            color: look.dim
                            font.pixelSize: 12
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.7
                            font.capitalization: Font.AllUppercase
                        }
                        Row {
                            id: shelf
                            anchors.left: parent.left
                            anchors.leftMargin: 8
                            anchors.top: shelfTitle.bottom
                            anchors.topMargin: 10
                            spacing: 16
                            readonly property real cardWidth: Math.floor((grid.width - 16 - spacing * 3) / 4)
                            height: Math.round(cardWidth * 215 / 460) + 50
                            Repeater {
                                model: root.lately
                                Item {
                                    id: card
                                    required property var modelData
                                    width: shelf.cardWidth
                                    height: shelf.height
                                    Cover {
                                        id: cardCover
                                        width: parent.width
                                        height: Math.round(width * 215 / 460)
                                        name: card.modelData.name
                                        source: card.modelData.art
                                        glaze: root.glaze(card.modelData.name)
                                        texture: root.texture
                                        radius: 12
                                        progress: typeof card.modelData.progress === "number" ? card.modelData.progress : -1
                                        scale: cardMouse.pressed ? 0.98 : cardMouse.containsMouse ? 1.02 : 1
                                        Behavior on scale {
                                            NumberAnimation { duration: Math.round(180 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.2, 1, 1] }
                                        }
                                    }
                                    MouseArea {
                                        id: cardMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        acceptedButtons: Qt.LeftButton | Qt.RightButton
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: mouse => mouse.button === Qt.RightButton
                                            ? root.showMenu(card.modelData, card, false) : root.openPage(card.modelData)
                                    }
                                    // Straight back into it.
                                    Rectangle {
                                        anchors.right: cardCover.right
                                        anchors.bottom: cardCover.bottom
                                        anchors.margins: 10
                                        width: 40
                                        height: 40
                                        radius: 20
                                        color: cardPlay.containsMouse ? "#FF6A42" : "#F2552C"
                                        opacity: cardMouse.containsMouse || cardPlay.containsMouse ? 1 : 0
                                        Behavior on opacity { NumberAnimation { duration: Math.round(140 * root.speed) } }
                                        Glyph {
                                            anchors.centerIn: parent
                                            anchors.horizontalCenterOffset: 1
                                            width: 16
                                            height: 16
                                            path: "M8 5.5L18 12 8 18.5z"
                                            filled: true
                                        }
                                        MouseArea {
                                            id: cardPlay
                                            anchors.fill: parent
                                            hoverEnabled: true
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: root.play(card.modelData)
                                        }
                                    }
                                    Text {
                                        horizontalAlignment: Text.AlignLeft
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.top: cardCover.bottom
                                        anchors.topMargin: 8
                                        text: card.modelData.name
                                        color: look.ink
                                        elide: Text.ElideRight
                                        font.pixelSize: 14
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        horizontalAlignment: Text.AlignLeft
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.top: cardCover.bottom
                                        anchors.topMargin: 27
                                        text: root.lastText(card.modelData.last)
                                        color: look.dim
                                        elide: Text.ElideRight
                                        font.pixelSize: 12
                                    }
                                }
                            }
                        }
                    }

                    delegate: Item {
                        id: tile
                        required property var modelData
                        required property int index
                        width: grid.cellWidth
                        height: grid.cellHeight
                        readonly property bool lit: tileMouse.containsMouse || starMouse.containsMouse || playMouse.containsMouse
                        readonly property bool both: modelData.plays === "monet" && modelData.windows !== ""

                        Cover {
                            id: tileCover
                            x: 8
                            y: 8
                            width: parent.width - 16
                            height: Math.round(width * 1.5)
                            name: tile.modelData.name
                            source: tile.modelData.tall
                            banner: tile.modelData.art
                            glaze: root.glaze(tile.modelData.name)
                            texture: root.texture
                            radius: 12
                            progress: typeof tile.modelData.progress === "number" ? tile.modelData.progress : -1
                            scale: tileMouse.pressed ? 0.98 : tile.lit ? 1.03 : 1
                            Behavior on scale {
                                NumberAnimation { duration: Math.round(180 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.2, 1, 1] }
                            }
                        }
                        // Where the keys are.
                        Rectangle {
                            x: tileCover.x - 4
                            y: tileCover.y - 4
                            width: tileCover.width + 8
                            height: tileCover.height + 8
                            radius: 16
                            color: "transparent"
                            border.width: 2
                            border.color: look.lily
                            visible: root.keys && grid.activeFocus && tile.modelData.id === root.keyed
                        }
                        MouseArea {
                            id: tileMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton | Qt.RightButton
                            cursorShape: Qt.PointingHandCursor
                            onClicked: mouse => mouse.button === Qt.RightButton
                                ? root.showMenu(tile.modelData, tile, false) : root.openPage(tile.modelData)
                        }
                        // Windows' games say so on their cover.
                        Rectangle {
                            anchors.left: tileCover.left
                            anchors.top: tileCover.top
                            anchors.margins: 8
                            visible: tile.modelData.plays === "windows" || tile.both
                            width: sideText.implicitWidth + 16
                            height: 22
                            radius: 11
                            color: Qt.rgba(0.07, 0.07, 0.09, 0.66)
                            Text {
                                id: sideText
                                horizontalAlignment: Text.AlignLeft
                                anchors.centerIn: parent
                                // Names: the same in every language.
                                text: tile.both ? "Monet · Windows" : "Windows"
                                color: "#FFFFFF"
                                font.pixelSize: 11
                                font.weight: Font.DemiBold
                            }
                        }
                        // The star: there on favorites, and on any cover the pointer's on.
                        Rectangle {
                            anchors.right: tileCover.right
                            anchors.top: tileCover.top
                            anchors.margins: 8
                            width: 30
                            height: 30
                            radius: 15
                            color: starMouse.containsMouse ? Qt.rgba(0, 0, 0, 0.6) : Qt.rgba(0, 0, 0, 0.42)
                            opacity: tile.modelData.favorite || tile.lit ? 1 : 0
                            Behavior on opacity { NumberAnimation { duration: Math.round(140 * root.speed) } }
                            Glyph {
                                anchors.centerIn: parent
                                width: 16
                                height: 16
                                stroke: 2
                                path: root.sections[1].glyph
                                filled: tile.modelData.favorite === true
                                color: tile.modelData.favorite ? "#F6C453" : "#FFFFFF"
                            }
                            MouseArea {
                                id: starMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.setFavorite(tile.modelData, !tile.modelData.favorite)
                            }
                            Accessible.role: Accessible.CheckBox
                            Accessible.name: i18n("Favorite")
                            Accessible.checked: tile.modelData.favorite === true
                        }
                        // Play, without opening its page: the sun, on the cover the pointer's on.
                        Rectangle {
                            anchors.right: tileCover.right
                            anchors.bottom: tileCover.bottom
                            anchors.margins: 10
                            width: 42
                            height: 42
                            radius: 21
                            color: playMouse.containsMouse ? "#FF6A42" : "#F2552C"
                            opacity: tile.lit ? 1 : 0
                            scale: playMouse.pressed ? 0.94 : 1
                            Behavior on opacity { NumberAnimation { duration: Math.round(140 * root.speed) } }
                            Glyph {
                                anchors.centerIn: parent
                                anchors.horizontalCenterOffset: 1
                                width: 17
                                height: 17
                                path: "M8 5.5L18 12 8 18.5z"
                                filled: true
                            }
                            MouseArea {
                                id: playMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.play(tile.modelData)
                            }
                        }

                        Text {
                            horizontalAlignment: Text.AlignLeft
                            anchors.left: tileCover.left
                            anchors.right: tileCover.right
                            anchors.top: tileCover.bottom
                            anchors.topMargin: 9
                            text: tile.modelData.name
                            color: look.ink
                            elide: Text.ElideRight
                            font.pixelSize: 14
                            font.weight: Font.DemiBold
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            anchors.left: tileCover.left
                            anchors.right: tileCover.right
                            anchors.top: tileCover.bottom
                            anchors.topMargin: 28
                            text: root.detail(tile.modelData)
                            color: look.dim
                            elide: Text.ElideRight
                            font.pixelSize: 12
                        }
                    }
                }

                // Nothing to show: why, and the way to some.
                ColumnLayout {
                    anchors.centerIn: parent
                    width: Math.min(parent.width - 96, 420)
                    visible: root.loaded && root.shown.length === 0
                    spacing: 10
                    Text {
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        color: look.ink
                        font.family: "Fraunces 72pt SuperSoft"
                        font.weight: Font.Light
                        font.pixelSize: 26
                        text: root.query !== "" ? i18n("No game called that")
                            : root.section === "favorites" && root.games.length > 0 ? i18n("No favorites yet")
                            : root.section === "recent" && root.games.length > 0 ? i18n("Nothing played yet")
                            : i18n("No games yet")
                    }
                    Text {
                        horizontalAlignment: Text.AlignHCenter
                        Layout.fillWidth: true
                        wrapMode: Text.Wrap
                        color: look.dim
                        font.pixelSize: 14
                        text: root.query !== "" ? ""
                            : root.section === "favorites" && root.games.length > 0 ? i18n("Tap the star on a game to keep it here.")
                            : root.section === "recent" && root.games.length > 0 ? i18n("The games you play show up here, the latest first.")
                            : i18n("Install games with Steam, Heroic or Lutris here, or in Windows. They show up here by themselves.")
                    }
                    Pill {
                        Layout.alignment: Qt.AlignHCenter
                        Layout.topMargin: 8
                        visible: root.query === "" && root.games.length === 0
                        tone: look
                        iconName: "steam"
                        text: i18n("Open Steam")
                        onClicked: root.openSteam()
                    }
                }
            }

            GamePage {
                id: gamePage
                anchors.fill: parent
                visible: root.current !== null
                app: root
                tone: look
                game: root.current || ({})
                onBack: root.closePage()
            }
        }

        // A game's menu: a pebble of glass with what else there is to do with it ------------------
        T.Popup {
            id: menu
            property var game: null
            property var items: []
            padding: 6
            margins: 8
            modal: false
            focus: true
            closePolicy: T.Popup.CloseOnEscape | T.Popup.CloseOnPressOutside
            implicitWidth: Math.max(220, menuColumn.implicitWidth + leftPadding + rightPadding)
            implicitHeight: menuColumn.implicitHeight + topPadding + bottomPadding
            background: Rectangle {
                radius: 14
                color: look.dark ? "#2D2C29" : "#FFFFFF"
                border.width: 1
                border.color: look.dark ? Qt.rgba(1, 1, 1, 0.1) : Qt.rgba(0, 0, 0, 0.08)
                layer.enabled: true
                layer.effect: MultiEffect {
                    shadowEnabled: true
                    shadowColor: Qt.rgba(0, 0, 0, 0.28)
                    shadowBlur: 0.8
                    shadowVerticalOffset: 4
                }
            }
            contentItem: ColumnLayout {
                id: menuColumn
                spacing: 2
                Repeater {
                    model: menu.items
                    Rectangle {
                        id: menuRow
                        required property var modelData
                        required property int index
                        Layout.fillWidth: true
                        implicitWidth: menuLabel.implicitWidth + 28
                        implicitHeight: 34
                        radius: 9
                        color: menuMouse.containsMouse || activeFocus ? look.wash2 : "transparent"
                        activeFocusOnTab: true
                        focus: index === 0
                        Keys.onReturnPressed: root.choose(modelData[0])
                        Keys.onSpacePressed: root.choose(modelData[0])
                        Keys.onUpPressed: nextItemInFocusChain(false).forceActiveFocus()
                        Keys.onDownPressed: nextItemInFocusChain(true).forceActiveFocus()
                        Text {
                            id: menuLabel
                            horizontalAlignment: Text.AlignLeft
                            anchors.left: parent.left
                            anchors.leftMargin: 14
                            anchors.verticalCenter: parent.verticalCenter
                            text: menuRow.modelData[1]
                            color: menuRow.modelData[0] === "uninstall" ? (look.dark ? "#FF8A6B" : "#C2410C") : look.ink
                            font.pixelSize: 14
                        }
                        MouseArea {
                            id: menuMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.choose(menuRow.modelData[0])
                        }
                        Accessible.role: Accessible.MenuItem
                        Accessible.name: modelData[1]
                        Accessible.onPressAction: root.choose(modelData[0])
                    }
                }
            }
            enter: Transition {
                NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Math.round(120 * root.speed) }
                NumberAnimation { property: "scale"; from: 0.96; to: 1; duration: Math.round(160 * root.speed); easing.type: Easing.OutCubic }
            }
            exit: Transition {
                NumberAnimation { property: "opacity"; to: 0; duration: Math.round(90 * root.speed) }
            }
        }
        // The question, over the library ----------------------------------------------------------
        Rectangle {
            id: veil
            anchors.fill: parent
            color: "#000000"
            opacity: root.sheetOpen ? 0.32 : 0
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: Math.round(240 * root.speed) } }
            MouseArea {
                anchors.fill: parent
                onClicked: root.sheetOpen = false
            }
        }

        Rectangle {
            id: sheet
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.verticalCenter: parent.verticalCenter
            anchors.verticalCenterOffset: root.sheetOpen ? 0 : 16
            width: Math.min(520, parent.width - 64)
            height: sheetColumn.implicitHeight + 44
            radius: 22
            color: look.paper
            border.color: look.line
            opacity: root.sheetOpen ? 1 : 0
            scale: root.sheetOpen ? 1 : 0.96
            visible: opacity > 0
            Behavior on opacity { NumberAnimation { duration: Math.round((root.sheetOpen ? 380 : 200) * root.speed) } }
            Behavior on scale {
                NumberAnimation { duration: Math.round(380 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] }
            }
            Behavior on anchors.verticalCenterOffset {
                NumberAnimation { duration: Math.round(380 * root.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] }
            }
            layer.enabled: visible
            layer.effect: MultiEffect {
                shadowEnabled: true
                shadowColor: Qt.rgba(0, 0, 0, 0.3)
                shadowBlur: 1
                shadowVerticalOffset: 6
            }
            Keys.onEscapePressed: root.sheetOpen = false
            // The sheet takes the keys while it's up (its bright button first), and gives them back.
            Connections {
                target: root
                function onSheetOpenChanged() {
                    if (root.sheetOpen)
                        Qt.callLater(() => sheetGo.visible ? sheetGo.forceActiveFocus() : sheetCancel.forceActiveFocus())
                    else if (root.current !== null)
                        gamePage.focusPlay()
                    else
                        grid.forceActiveFocus()
                }
            }

            ColumnLayout {
                id: sheetColumn
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 22
                spacing: 14

                Cover {
                    visible: root.asking !== null
                    name: root.asking ? root.asking.name : ""
                    source: root.asking ? root.asking.art : ""
                    glaze: root.glaze(name)
                    texture: root.texture
                    radius: 14
                    Layout.fillWidth: true
                    Layout.preferredHeight: visible ? Math.round(width * 215 / 460) : 0
                }

                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    color: look.ink
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: 24
                    text: root.problem !== "" ? i18n("Couldn't open Windows")
                        : root.asking && root.asking.windows === "" ? i18n("%1 needs Windows", root.asking.name)
                        : root.asking ? i18n("Play %1?", root.asking.name)
                        : i18n("Restart in Windows?")
                }

                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    wrapMode: Text.Wrap
                    color: look.ink
                    opacity: root.problem !== "" ? 1 : 0.75
                    font.pixelSize: 14
                    text: root.problem !== "" ? root.problem
                        : root.asking && root.asking.move && root.asking.why === "reports"
                            ? i18n("Players report it doesn't run in Monet, so it plays in Windows. In Steam, move it to Windows games (Properties, Installed Files, Move install folder), and Play starts it there, with nothing to download.")
                        : root.asking && root.asking.move
                            ? i18n("Its anti-cheat only lets it play in Windows. In Steam, move it to Windows games (Properties, Installed Files, Move install folder), and Play starts it there, with nothing to download.")
                        : root.asking && root.asking.windows === "" && root.asking.why === "reports"
                            ? i18n("Players report it doesn't run in Monet, and it isn't installed in Windows yet. Restart in Windows and install it with %1.", root.storeName(root.asking.store))
                        : root.asking && root.asking.windows === ""
                            ? i18n("Its anti-cheat only lets it play in Windows, and it isn't installed there yet. Restart in Windows and install it with %1.", root.storeName(root.asking.store))
                        : root.asking && root.asking.locate && root.asking.store === "ea"
                            ? i18n("Your PC restarts in Windows and opens it in the EA app. Choose Download and pick %1 as where to install it: the game is there already, so the EA app only checks it.", root.asking.locate)
                        : root.asking && root.asking.locate
                            ? i18n("Your PC restarts in Windows and opens it. If %1 there asks to install it, choose its option to locate the game instead and pick %2: it's there already.", root.storeName(root.asking.store), root.asking.locate)
                        : root.asking ? i18n("Your PC restarts in Windows and opens the game. When you quit, you're back here. Save your work first.")
                        : i18n("Your PC restarts in Windows. Open apps close, so save your work first.")
                }

                Text {
                    Layout.fillWidth: true
                    visible: root.problem === "" && !(root.asking && root.asking.move)
                    text: i18n("Unsaved changes and private tabs aren't captured. Downloads stop during the restart; check Store's Downloads when you return.")
                    color: look.dim
                    font.pixelSize: 13
                    wrapMode: Text.Wrap
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.topMargin: 4
                    spacing: 8
                    Item { Layout.fillWidth: true }
                    Pill {
                        id: sheetCancel
                        tone: look
                        text: root.problem !== "" ? i18n("Close") : i18n("Cancel")
                        onClicked: root.sheetOpen = false
                    }
                    SunButton {
                        id: sheetGo
                        speed: root.speed
                        size: 14
                        visible: root.problem === ""
                        text: root.asking && root.asking.move ? i18n("Show in Steam")
                            : root.asking && root.asking.windows !== "" ? i18n("Restart & Play") : i18n("Restart")
                        onClicked: root.asking && root.asking.move ? root.showInSteam(root.asking) : root.go()
                    }
                }
            }
        }
    }

    Sunset {
        id: sunset
        speed: root.speed
    }
}
