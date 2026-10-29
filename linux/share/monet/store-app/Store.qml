/*
 * Store: apps for Monet, hung like a gallery. The front page has today's pick, Monet's picks in
 * rooms under strips of The Hours, the apps installed most this month and Fresh paint; then
 * every app on Flathub by what it's for, each section under its own painting, in the order and
 * of the kind you ask; what you have; and the apps in your Windows. A search finds them all,
 * Windows' too, and suggests apps for familiar tasks from other systems.
 * An app's page installs it, opens it or removes it.
 *
 * monet-store opens it, and gives it `shop` (the catalog and what it does), `helper` (which
 * runs monet-quick), its i18n calls, and where Monet's pictures are (`banners`, `art`, `brush`).
 */
import QtCore
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import org.kde.kirigami as Kirigami
import "../games"

MonetWindow {
    id: root
    title: i18n("Store")
    width: 1180
    height: 780
    minimumWidth: 780
    minimumHeight: 540
    visible: true
    // See-through: WindowGlass is its glass.
    color: "transparent"

    property bool loaded: false
    // What's shown: "home", a section ("games", "graphics"...), "installed" or "windows".
    property string section: "home"
    property string query: ""
    // The app whose page is open; "" for the lists.
    property string pageId: ""
    property var pageApp: ({})
    property var pageFacts: ({})
    // How far each app being installed or removed has got.
    property var working: ({})
    property var downloads: []
    property string downloadStates: ""
    property string queueIssue: ""
    // The lists, asked of the shop when they're shown.
    property var homeShown: ({ rows: [], today: null, top: [], fresh: [] })
    property var listApps: []
    property var listKinds: []
    // A section's order ("popular", "updated", "name"; kept for next time), the kind of app
    // shown ("" for all), and whether only the apps Flathub checked are.
    property string order: "popular"
    property string kind: ""
    property bool checkedOnly: false
    property var found: ({ apps: [], windows: [], instead: null })
    property var counts: ({})
    // No catalog: Flathub was out of reach when this PC first asked for it.
    readonly property bool empty: loaded && Object.keys(counts).every(k => k === "installed" || !counts[k])
    property var windowsApps: []
    // A screenshot shown big.
    property string picture: ""
    // What this start was asked for, until the catalog's read.
    property string pending: firstPage
    readonly property string texture: brush
    readonly property real speed: Kirigami.Units.longDuration / 200

    Settings {
        category: "Store"
        property alias windowWidth: root.width
        property alias windowHeight: root.height
        property alias order: root.order
    }

    // The front page's rows, in Monet's own words (store/content.yaml lists their apps).
    readonly property var rowWords: ({
        play: [i18n("Play"), i18n("Launchers, old consoles and new games. Steam is already here.")],
        talk: [i18n("Talk & stream"), i18n("Friends, calls, and going live.")],
        watch: [i18n("Music & film"), i18n("Something to listen to, and something to watch.")],
        work: [i18n("Work & make"), i18n("Writing, drawing, editing, sending, and tools for the command line.")],
        everyday: [i18n("Everyday"), i18n("Passwords, sharing, and the small things that help.")]
    })
    readonly property var entries: [
        { id: "home", name: i18n("Monet's picks"), swatch: "apps", glyph: "M12 3.8l2.5 5.1 5.6.8-4 3.9.9 5.6-5-2.6-5 2.6.9-5.6-4-3.9 5.6-.8z", filled: true },
        { id: "games", name: i18n("Games"), swatch: "games", glyph: "M7.5 8h9a4.5 4.5 0 0 1 4.5 4.5v1a3.5 3.5 0 0 1-6.4 2L14 14.5h-4l-.6 1A3.5 3.5 0 0 1 3 13.5v-1A4.5 4.5 0 0 1 7.5 8zM8 10.5v3M6.5 12h3" },
        { id: "graphics", name: i18n("Photos & drawing"), swatch: "light", glyph: "M4 6h16v12H4zM4 15l5-4 4 3 3-2 4 3M15.5 9.5h.01" },
        { id: "media", name: i18n("Music & video"), swatch: "sound", glyph: "M9 17.5V6l10-2v11.5M9 17.5a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0zM19 15.5a2.5 2.5 0 1 1-5 0 2.5 2.5 0 0 1 5 0z" },
        { id: "office", name: i18n("Writing & office"), swatch: "about", glyph: "M7 3.5h7l4 4V20.5H7zM14 3.5v4h4M9.5 12h6M9.5 15.5h6" },
        { id: "internet", name: i18n("Internet & chat"), swatch: "wifi", glyph: "M5 6h14v9.5H10l-4 3v-3H5z" },
        { id: "learning", name: i18n("Learning"), swatch: "accessibility", glyph: "M3 9l9-4 9 4-9 4zM7 11v4.5c3 2 7 2 10 0V11" },
        { id: "developer", name: i18n("Developer tools"), swatch: "input", glyph: "M9 8l-4 4 4 4M15 8l4 4-4 4" },
        { id: "tools", name: i18n("Tools"), swatch: "storage", glyph: "M14.5 5.5a4 4 0 0 0-5 5l-5 5 2.5 2.5 5-5a4 4 0 0 0 5-5l-2.5 2.5-2-.5-.5-2z" },
        { id: "installed", name: i18n("Installed"), swatch: "updates", glyph: "M12 4v11M7.5 10.5l4.5 4.5 4.5-4.5M5 19.5h14", mine: true },
        { id: "downloads", name: i18n("Downloads"), swatch: "storage", glyph: "M12 4v10M8 10l4 4 4-4M5 17v3h14v-3", mine: true },
        { id: "windows", name: i18n("On your Windows"), swatch: "windows", mine: true,
          glyph: "M4 5.5l7-1v7H4zM13 4.2l7-1v8.3h-7zM4 13.5h7v7l-7-1zM13 13.5h7v8.3l-7-1z" }
    ].filter(e => e.id !== "windows" || windowsApps.length > 0)
    readonly property var entry: entries.find(e => e.id === section) || entries[0]
    // The kinds of app a section can be narrowed to (monet-store's KINDS).
    readonly property var kindWords: ({
        action: i18nc("a kind of app, a filter in the Store", "Action"),
        arcade: i18nc("a kind of app, a filter in the Store", "Arcade"),
        strategy: i18nc("a kind of app, a filter in the Store", "Strategy"),
        puzzles: i18nc("a kind of app, a filter in the Store", "Puzzles"),
        adventure: i18nc("a kind of app, a filter in the Store", "Adventure & role-playing"),
        simulation: i18nc("a kind of app, a filter in the Store", "Simulation & sports"),
        board: i18nc("a kind of app, a filter in the Store", "Board & cards"),
        kids: i18nc("a kind of app, a filter in the Store", "For kids"),
        emulators: i18nc("a kind of app, a filter in the Store", "Emulators"),
        drawing: i18nc("a kind of app, a filter in the Store", "Drawing & painting"),
        photos: i18nc("a kind of app, a filter in the Store", "Photos"),
        vector: i18nc("a kind of app, a filter in the Store", "Vector"),
        "3d": i18nc("a kind of app, a filter in the Store", "3D"),
        viewers: i18nc("a kind of app, a filter in the Store", "Viewers"),
        scanning: i18nc("a kind of app, a filter in the Store", "Scanning"),
        players: i18nc("a kind of app, a filter in the Store", "Players"),
        music: i18nc("a kind of app, a filter in the Store", "Making music"),
        editing: i18nc("a kind of app, a filter in the Store", "Editing"),
        video: i18nc("a kind of app, a filter in the Store", "Video & TV"),
        recording: i18nc("a kind of app, a filter in the Store", "Recording"),
        writing: i18nc("a kind of app, a filter in the Store", "Writing"),
        money: i18nc("a kind of app, a filter in the Store", "Money"),
        planning: i18nc("a kind of app, a filter in the Store", "Calendars & planning"),
        email: i18nc("a kind of app, a filter in the Store", "Email"),
        chat: i18nc("a kind of app, a filter in the Store", "Chat"),
        browsers: i18nc("a kind of app, a filter in the Store", "Browsers"),
        calls: i18nc("a kind of app, a filter in the Store", "Calls"),
        sharing: i18nc("a kind of app, a filter in the Store", "Sharing & downloads"),
        news: i18nc("a kind of app, a filter in the Store", "News"),
        remote: i18nc("a kind of app, a filter in the Store", "Remote access"),
        science: i18nc("a kind of app, a filter in the Store", "Science"),
        math: i18nc("a kind of app, a filter in the Store", "Math"),
        languages: i18nc("a kind of app, a filter in the Store", "Languages"),
        computing: i18nc("a kind of app, a filter in the Store", "Computing & data"),
        code: i18nc("a kind of app, a filter in the Store", "Code editors"),
        versions: i18nc("a kind of app, a filter in the Store", "Version control"),
        web: i18nc("a kind of app, a filter in the Store", "Web"),
        debugging: i18nc("a kind of app, a filter in the Store", "Debugging"),
        electronics: i18nc("a kind of app, a filter in the Store", "Electronics"),
        system: i18nc("a kind of app, a filter in the Store", "System"),
        files: i18nc("a kind of app, a filter in the Store", "Files"),
        text: i18nc("a kind of app, a filter in the Store", "Text"),
        security: i18nc("a kind of app, a filter in the Store", "Security"),
        terminals: i18nc("a kind of app, a filter in the Store", "Terminals"),
        clocks: i18nc("a kind of app, a filter in the Store", "Clocks & calculators")
    })

    function list() {
        if (!loaded || section === "home" || section === "windows" || section === "downloads")
            return
        const shelf = shop.section(section, order, kind, checkedOnly)
        listApps = shelf.apps
        listKinds = shelf.kinds
    }
    function refresh() {
        homeShown = shop.home()
        counts = shop.counts()
        windowsApps = shop.windows()
        list()
        if (query.trim() !== "")
            found = shop.find(query)
        if (pageId !== "")
            pageApp = shop.app(pageId) || pageApp
    }
    // A new order or kind: the room from its top.
    function relist() {
        list()
        // From the room's painting (a grid's beginning is its first app, under the header).
        Qt.callLater(() => shelfView.contentY = shelfView.originY)
    }
    function show(what) {
        if (!what)
            return
        if (!loaded && what !== "downloads") {
            pending = what
            return
        }
        if (what.startsWith("appstream://") || what.startsWith("appstream:"))
            openApp(what.replace(/^appstream:(\/\/)?/, "").replace(/\/$/, "").replace(/\.desktop$/, ""))
        else if (what.startsWith("search:"))
            query = what.slice(7)
        else if (entries.some(e => e.id === what))
            chooseSection(what)
        else
            openApp(what)
    }
    function openApp(id) {
        const app = shop.app(id)
        if (!app)
            return
        pageApp = app
        pageFacts = {}
        pageId = id
        appPage.contentY = 0
        appPage.shown = 0
        shop.learn(id)
        Qt.callLater(() => appPage.focusFirst())
    }
    function closePage() {
        pageId = ""
    }
    function chooseSection(which) {
        pageId = ""
        query = ""
        section = which
    }
    function jobFor(id) { return downloads.find(j => j.id === id) || ({}) }
    function jobText(job) {
        if (job.state === "queued") return i18n("Waiting its turn")
        if (job.state === "cancelling") return i18n("Cancelling…")
        if (job.state === "cancelled") return i18n("Cancelled. You can try again whenever you're ready.")
        if (job.state === "interrupted") return job.action === "remove" ? i18n("Interrupted. Retry to finish removing this app.") : i18n("Interrupted. Retry to continue the download.")
        if (job.state === "done") return job.action === "remove" ? i18n("Removed") : i18n("Installed")
        if (job.state === "running") return job.progress >= 1 ? i18n("Finishing…") : job.action === "remove" ? i18n("Removing…") : i18n("Downloading & installing… %1%", Math.round(job.progress * 100))
        if (job.error === "no-space") return i18n("There isn't enough free space. Free some space, then retry.")
        if (job.error === "offline") return i18n("The download stopped because Flathub couldn't be reached. Check your connection, then retry.")
        if (job.error === "not-allowed") return i18n("Only an administrator of this PC can install and remove apps.")
        if (job.error === "worker") return i18n("The download couldn't start. Try again.")
        if (job.error === "storage") return i18n("The download list couldn't be saved. Check free space and try again.")
        return i18n("That didn't work. Try again in a moment.")
    }
    function choose(card, kind) {
        if (kind === "windows")
            shop.openWindows(card.id)
        else
            openApp(card.id)
    }
    // What a picture of the painting a row is under (by daylight Mist, by night Smoke).
    function banner(row) {
        return banners + row + (look.dark ? "-smoke.jpg" : "-mist.jpg")
    }

    Connections {
        target: shop
        function onJobsChanged(jobs) {
            root.downloads = jobs
            const active = {}
            for (const job of jobs)
                if (["queued", "running", "cancelling"].includes(job.state)) active[job.id] = job.progress
            root.working = active
            const states = jobs.map(j => j.id + ":" + j.state).join("|")
            if (states !== root.downloadStates) {
                root.downloadStates = states
                if (root.loaded) root.refresh()
            }
        }
        function onQueueProblem(why) {
            root.queueIssue = i18n("The saved download list couldn't be read or saved. Check free space and folder access, then try again. Your existing list has been kept.")
            root.section = "downloads"
        }
        function onLoaded() {
            root.loaded = true
            root.refresh()
            // The room's header grew with its kinds and podium: from its painting again.
            Qt.callLater(() => shelfView.contentY = shelfView.originY)
            if (root.pending !== "") {
                const what = root.pending
                root.pending = ""
                root.show(what)
            }
        }
        function onFacts(id, facts) {
            if (id === root.pageId)
                root.pageFacts = facts
        }
        // The Store opened again (from a link, the menu): this one, forward, at what it was asked.
        function onWanted(what) {
            if (root.visibility === Window.Minimized)
                root.visibility = Window.Windowed
            root.raise()
            root.requestActivate()
            root.show(what)
        }
    }
    onSectionChanged: {
        pageId = ""
        query = ""
        kind = ""
        relist()
    }
    onOrderChanged: relist()
    onKindChanged: relist()
    onCheckedOnlyChanged: relist()
    onQueryChanged: {
        if (query !== "")
            pageId = ""
        found = loaded && query.trim() !== "" ? shop.find(query) : { apps: [], windows: [], instead: null }
    }
    Component.onCompleted: if (pending !== "" && !pending.startsWith("appstream") && entries.some(e => e.id === pending)) section = pending

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
        readonly property color sun: "#F2552C"
        readonly property color ochre: dark ? "#E8AE48" : "#B9802A"
        readonly property real speed: root.speed
    }

    Shortcut {
        sequences: [StandardKey.Find]
        onActivated: search.forceActiveFocus()
    }

    // A canvas under the side, as faint as paper's grain.
    Image {
        anchors.fill: parent
        anchors.margins: 14
        source: texture
        fillMode: Image.Tile
        opacity: look.dark ? 0.05 : 0.07
    }

    // Everything drawn, mirrored for a right-to-left language (a Window itself can't be).
    Item {
        id: body
        anchors.fill: parent
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true

        // The side: the name, search, the sections -----------------------------------
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
                    text: i18n("Store")
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
                            Accessible.name: i18n("Find an app")
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
                                text: i18n("Find an app")
                                color: look.dim
                                font: search.font
                                elide: Text.ElideRight
                            }
                        }
                    }
                }

                // The sections, then yours; the current one's pebble of glass glides to it.
                Flickable {
                    id: navList
                    MouseScroll { view: navList }
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentHeight: navColumn.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    interactive: contentHeight > height

                    Rectangle {
                        id: pebble
                        readonly property Item target: navRepeater.count > 0 && root.query === ""
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
                                readonly property bool current: root.section === modelData.id && root.query === ""
                                readonly property var count: modelData.id === "downloads" ? root.downloads.filter(j => j.state !== "done").length : modelData.id === "windows" ? root.windowsApps.length : root.counts[modelData.id]
                                Layout.fillWidth: true
                                Layout.preferredHeight: 34
                                // Yours, a little apart under their caption.
                                Layout.topMargin: modelData.mine === true && index > 0 && root.entries[index - 1].mine !== true ? 34 : 0
                                radius: 12
                                color: navMouse.containsMouse && !current ? (look.dark ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.4)) : "transparent"
                                Behavior on color { ColorAnimation { duration: Math.round(140 * root.speed) } }
                                border.width: activeFocus ? 2 : 0
                                border.color: look.lily
                                activeFocusOnTab: true
                                Keys.onSpacePressed: root.chooseSection(modelData.id)
                                Keys.onReturnPressed: root.chooseSection(modelData.id)

                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    visible: navItem.Layout.topMargin > 0
                                    anchors.left: parent.left
                                    anchors.leftMargin: 10
                                    anchors.bottom: parent.top
                                    anchors.bottomMargin: 6
                                    text: i18n("Yours")
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
                                    Item {
                                        Layout.preferredWidth: 26
                                        Layout.preferredHeight: 26
                                        Image {
                                            anchors.fill: parent
                                            source: art + "swatch-" + navItem.modelData.swatch + ".png"
                                            sourceSize: Qt.size(56, 56)
                                            smooth: true
                                        }
                                        Glyph {
                                            anchors.centerIn: parent
                                            anchors.verticalCenterOffset: 1
                                            width: 15
                                            height: 15
                                            path: navItem.modelData.glyph
                                            filled: navItem.modelData.filled === true
                                            color: Qt.rgba(0, 0, 0, 0.3)
                                        }
                                        Glyph {
                                            anchors.centerIn: parent
                                            width: 15
                                            height: 15
                                            path: navItem.modelData.glyph
                                            filled: navItem.modelData.filled === true
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
                                        visible: root.loaded && typeof navItem.count === "number"
                                        text: typeof navItem.count === "number" ? navItem.count.toLocaleString(Qt.locale(), "f", 0) : ""
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
                                    onClicked: {
                                        root.query = ""
                                        root.chooseSection(navItem.modelData.id)
                                        root.pageId = ""
                                    }
                                }
                                Accessible.role: Accessible.PageTab
                                Accessible.name: modelData.name
                                Accessible.selected: current
                                Accessible.onPressAction: root.chooseSection(modelData.id)
                            }
                        }
                    }
                }
            }
        }

        // The lists, or an app's page: on paper ---------------------------------------
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
            clip: true

            readonly property int columns: Math.max(1, Math.floor((width - 64) / 320))

            // Until Flathub's catalog is read (under a second, usually).
            Column {
                anchors.centerIn: parent
                width: Math.min(parent.width - 64, 520)
                spacing: 16
                visible: root.section !== "downloads" && (!root.loaded || root.empty)
                Text {
                    width: parent.width
                    horizontalAlignment: Text.AlignHCenter
                    wrapMode: Text.WordWrap
                    text: root.loaded ? i18n("The app catalog is unavailable. Check your connection and try again. Your downloads are still available.") : i18n("Opening the Store…")
                    color: look.dim
                    font.pixelSize: 15
                }
                Pill {
                    anchors.horizontalCenter: parent.horizontalCenter
                    visible: root.loaded
                    tone: look
                    text: i18n("Try again")
                    onClicked: { root.loaded = false; shop.reload() }
                }
            }

            Downloads {
                anchors.fill: parent
                visible: root.section === "downloads" && root.pageId === "" && root.query === ""
                tone: look
                store: root
                jobs: root.downloads
                issue: root.queueIssue
                onAction: (id, command) => shop.downloadAction(id, command)
                onOpenApp: id => shop.open(id)
                onRecheck: { root.queueIssue = ""; shop.poll() }
            }

            // The front page.
            Home {
                id: home
                anchors.fill: parent
                visible: root.loaded && !root.empty && root.pageId === "" && root.query === "" && root.section === "home"
                tone: look
                store: root
                shown: root.homeShown
                columns: pageArea.columns
            }

            // A section, what you have, or your Windows' apps.
            Shelf {
                id: shelfView
                anchors.fill: parent
                anchors.leftMargin: 32
                anchors.rightMargin: 20
                visible: root.loaded && !root.empty && root.pageId === "" && root.query === "" && root.section !== "home" && root.section !== "downloads"
                tone: look
                store: root
                section: root.section
                name: root.entry.name
                subtitle: root.section === "windows"
                    ? i18n("Apps in your Windows. Each opens there: your PC restarts in Windows, and Back to Monet brings you back.")
                    : root.section === "installed"
                        ? (root.listApps.length > 0 ? i18n("Apps you installed from the Store. They update by themselves.")
                                                    : i18n("Apps you install from the Store show up here."))
                        : i18np("%1 app", "%1 apps", root.listApps.length)
                apps: root.section === "windows" ? root.windowsApps : root.listApps
                kinds: root.section === "windows" ? [] : root.listKinds
                columns: pageArea.columns
            }

            // What a search found: Windows' answer first, then your Windows' apps, then the Store's.
            Flickable {
                id: results
                MouseScroll { view: results }
                anchors.fill: parent
                visible: root.loaded && root.pageId === "" && root.query !== ""
                contentHeight: resultsColumn.implicitHeight + 40
                boundsBehavior: Flickable.StopAtBounds
                clip: true
                Kirigami.WheelHandler {
                    target: results
                    filterMouseEvents: !("acceptedButtons" in results)
                    keyNavigationEnabled: true
                    verticalStepSize: 96
                }
                Column {
                    id: resultsColumn
                    x: 32
                    width: results.width - 64
                    spacing: 16
                    Item { width: 1; height: 8 }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        width: parent.width
                        text: i18n("Apps for “%1”", root.query.trim())
                        color: look.ink
                        elide: Text.ElideRight
                        font.family: "Fraunces 72pt SuperSoft"
                        font.weight: Font.Light
                        font.pixelSize: 30
                    }
                    // Familiar names help people find apps without promising file compatibility.
                    Rectangle {
                        width: parent.width
                        height: insteadColumn.implicitHeight + 32
                        visible: root.found.instead !== null && root.found.instead !== undefined
                        radius: 14
                        color: look.wash
                        border.width: 1
                        border.color: look.line
                        ColumnLayout {
                            id: insteadColumn
                            anchors.fill: parent
                            anchors.margins: 16
                            spacing: 10
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: root.found.instead ? i18n("Looking for %1?", root.found.instead.name) : ""
                                color: look.ink
                                font.pixelSize: 18
                                font.weight: Font.DemiBold
                                wrapMode: Text.Wrap
                            }
                            Text {
                                objectName: "familiarAppExplanation"
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: !root.found.instead ? ""
                                    : root.found.instead.apps.length > 0
                                        ? i18n("These apps cover similar tasks on Monet. Features and file formats differ; try a copy of your work first.")
                                        : i18n("No suggestions are available in this catalog. Check the publisher's website for a web version or supported systems.")
                                color: look.ink
                                font.pixelSize: 14
                                wrapMode: Text.Wrap
                            }
                            GridLayout {
                                Layout.fillWidth: true
                                columns: pageArea.columns
                                columnSpacing: 12
                                rowSpacing: 12
                                visible: root.found.instead && root.found.instead.apps.length > 0
                                Repeater {
                                    model: root.found.instead ? root.found.instead.apps : []
                                    AppCard {
                                        required property var modelData
                                        Layout.fillWidth: true
                                        Layout.preferredWidth: 1
                                        tone: look
                                        app: modelData
                                        onChosen: root.choose(modelData, "flathub")
                                    }
                                }
                            }
                        }
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        visible: root.found.windows.length > 0
                        text: i18n("On your Windows")
                        color: look.dim
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        font.letterSpacing: 0.7
                        font.capitalization: Font.AllUppercase
                    }
                    GridLayout {
                        width: parent.width
                        visible: root.found.windows.length > 0
                        columns: pageArea.columns
                        columnSpacing: 12
                        rowSpacing: 12
                        Repeater {
                            model: root.found.windows
                            AppCard {
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                tone: look
                                kind: "windows"
                                app: modelData
                                onChosen: root.choose(modelData, "windows")
                            }
                        }
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        visible: root.found.apps.length > 0 && (root.found.windows.length > 0 || !!root.found.instead)
                        text: i18n("For Monet")
                        color: look.dim
                        font.pixelSize: 12
                        font.weight: Font.DemiBold
                        font.letterSpacing: 0.7
                        font.capitalization: Font.AllUppercase
                    }
                    GridLayout {
                        width: parent.width
                        columns: pageArea.columns
                        columnSpacing: 12
                        rowSpacing: 12
                        Repeater {
                            model: root.found.apps
                            AppCard {
                                required property var modelData
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                tone: look
                                app: modelData
                                onChosen: root.choose(modelData, "flathub")
                            }
                        }
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        width: parent.width
                        visible: root.found.apps.length === 0 && root.found.windows.length === 0 && !root.found.instead
                        text: i18n("Nothing in the Store goes by “%1”. Try other words, or what it's for: “photo editor”, “music”.", root.query.trim())
                        color: look.dim
                        font.pixelSize: 14
                        wrapMode: Text.Wrap
                    }
                }
            }

            AppPage {
                id: appPage
                anchors.fill: parent
                visible: root.pageId !== ""
                store: QtObject {
                    function install(id) { shop.install(id) }
                    function remove(id) { shop.remove(id) }
                    function downloadAction(id, command) { shop.downloadAction(id, command) }
                    function open(id) { shop.open(id) }
                    function showPicture(url) { root.picture = url }
                    function openApp(id) { root.openApp(id) }
                }
                tone: look
                painting: root.pageId !== "" ? root.banner(root.pageApp.section || "tools") : ""
                columns: pageArea.columns
                app: root.pageApp
                facts: root.pageFacts
                progress: root.working[root.pageId] !== undefined ? root.working[root.pageId] : -1
                job: root.jobFor(root.pageId)
                jobStatus: job.state ? root.jobText(job) : ""
                problem: job.state === "failed" || job.state === "interrupted" || job.state === "cancelled" ? jobStatus : ""
                onBack: root.closePage()
            }
        }

        // A screenshot, big: a click puts it away.
        Rectangle {
            anchors.fill: parent
            visible: root.picture !== ""
            color: Qt.rgba(0, 0, 0, 0.82)
            Image {
                anchors.fill: parent
                anchors.margins: 40
                source: root.picture
                fillMode: Image.PreserveAspectFit
                asynchronous: true
                smooth: true
            }
            MouseArea {
                anchors.fill: parent
                onClicked: root.picture = ""
            }
            Keys.onEscapePressed: root.picture = ""
        }
    }
}
