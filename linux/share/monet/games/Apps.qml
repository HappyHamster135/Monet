/*
 * Apps: every app in the menu in one library, as Games lists games (`monet-quick app-library`).
 * Down the side: all of them, the ones opened lately, where they came from (the Store, Monet,
 * added by you, Windows) and what kind of app each is; the rest is their icons, by name or by
 * when each was last opened. An icon opens its app's page: what it is, where it came from and
 * Open; for one from the Store, its Store page, where it updates and is removed; a shortcut
 * added on this account can be removed here. The games launchers add are in Games.
 *
 * `monet-games --apps` opens it, with Games' `helper` (which runs monet-quick), its i18n calls
 * and where Monet's pictures are (`art`, `texture`).
 */
import QtCore
import QtQuick
import QtQuick.Layouts
import QtQuick.Templates as T
import QtQuick.Window
import org.kde.kirigami as Kirigami
import "Library.js" as Library

MonetWindow {
    id: root
    title: i18n("Apps")
    width: 1080
    height: 720
    minimumWidth: 720
    minimumHeight: 500
    visible: true
    // See-through: WindowGlass is its glass.
    color: "transparent"

    // [{id, name, detail, icon, source, store, group, last, removable}] (monet-quick app-library).
    property var apps: []
    property bool loaded: false
    property bool libraryBusy: false
    property bool libraryProblem: false
    property bool libraryQueued: false
    property string libraryText: ""
    // What's shown: "all", "recent", a source ("store", "system", "mine", "windows") or "kind:KIND".
    property string section: "all"
    // How they're sorted: "name" or "recent" (kept for next time).
    property string sort: "name"
    property string query: ""
    // The app whose page is open (its menu id), or "".
    property string pageId: ""
    readonly property var current: apps.find(a => a.id === pageId) || null
    property bool confirmRemove: false
    property string problem: ""
    property var waiting: ({})
    readonly property string texture: brush
    readonly property real speed: Kirigami.Units.longDuration / 200

    Settings {
        category: "Apps"
        property alias windowWidth: root.width
        property alias windowHeight: root.height
        property alias sort: root.sort
    }

    // Runs monet-quick ("helper") with its words, then `then(out, code, err)`.
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
        // Apps opened again: this one, forward.
        function onWanted() {
            if (root.visibility === Window.Minimized)
                root.visibility = Window.Windowed
            root.raise()
            root.requestActivate()
        }
    }
    function refresh() {
        if (libraryBusy) {
            libraryQueued = true
            return
        }
        libraryBusy = true
        run(["helper", "app-library"], (out, code) => {
            const found = Library.read(out, code, ["id", "name", "detail", "icon", "source", "store", "group"])
            libraryProblem = found === null
            if (found !== null) {
                const text = JSON.stringify(found)
                if (text !== libraryText) {
                    apps = found
                    libraryText = text
                }
                loaded = true
            }
            libraryBusy = false
            libraryStatus.finish(found !== null)
            if (libraryQueued) {
                libraryQueued = false
                refresh()
            }
        })
    }
    Component.onCompleted: refresh()
    // An app installed or removed meanwhile (in the Store, say): there when you come back.
    onActiveChanged: if (active && loaded) refresh()

    // What can be done --------------------------------------------------------

    function hex(text) {
        const bytes = unescape(encodeURIComponent(text))
        let encoded = ""
        for (let i = 0; i < bytes.length; i++)
            encoded += bytes.charCodeAt(i).toString(16).padStart(2, "0")
        return encoded
    }
    function open(app) {
        problem = ""
        run(["helper", "menu-app-open", hex(app.id)], (out, code) => {
            if (code !== 0)
                root.problem = i18n("%1 didn't open. Try again, or open it from the menu.", app.name)
        })
    }
    function storePage(app) {
        run(["helper", "store-app", app.store])
    }
    function remove(app) {
        run(["helper", "app-remove", hex(app.id)], (out, code) => {
            root.confirmRemove = false
            if (code === 0) {
                root.closePage()
                root.refresh()
            } else {
                root.problem = i18n("The shortcut couldn't be removed.")
            }
        })
    }
    function openPage(app) {
        pageId = app.id
        confirmRemove = false
        problem = ""
        Qt.callLater(() => openButton.forceActiveFocus())
    }
    function closePage() {
        pageId = ""
        confirmRemove = false
        Qt.callLater(() => grid.forceActiveFocus())
    }
    function goBack() {
        if (confirmRemove) {
            confirmRemove = false
            Qt.callLater(() => removeButton.forceActiveFocus())
        } else if (current !== null) {
            closePage()
        }
    }

    // Words -----------------------------------------------------------------

    function sourceName(source) {
        return { store: i18n("From the Store"), system: i18n("Came with Monet"), mine: i18n("Added by you"),
                 windows: i18n("Windows program") }[source] || ""
    }
    function kindName(group) {
        return { internet: i18n("Internet"), office: i18n("Office"), graphics: i18nc("a kind of app: drawing, photos and design", "Graphics"),
                 media: i18n("Sound and video"), games: i18n("Games"), development: i18n("Development"),
                 utilities: i18n("Utilities"), system: i18n("System"), other: i18n("Other") }[group] || i18n("Other")
    }
    function lastText(last) {
        if (!last)
            return i18n("Not opened yet")
        const then = new Date(last * 1000)
        const today = new Date()
        today.setHours(0, 0, 0, 0)
        const days = Math.ceil((today - then) / 86400000)
        return then >= today ? i18n("Today")
            : days <= 1 ? i18n("Yesterday")
            : days < 7 ? i18np("%1 day ago", "%1 days ago", days)
            : then.toLocaleDateString(Qt.locale(), Locale.ShortFormat)
    }

    // The library ------------------------------------------------------------

    // Without accents or capitals on either side: "etretat" finds "Étretat".
    function fold(text) {
        return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase()
    }
    function inSection(app, which) {
        return which === "all" ? true
            : which === "recent" ? app.last > 0
            : which.startsWith("kind:") ? app.group === which.slice(5)
            : app.source === which
    }
    readonly property var sections: [
        { id: "all", name: i18n("All apps"), swatch: "apps", glyph: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" },
        { id: "recent", name: i18n("Recently used"), swatch: "datetime", glyph: "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 7v5l3 2" },
        { id: "store", name: i18n("From the Store"), swatch: "updates", source: true, glyph: "M12 4v11M7 10l5 5 5-5M5 20h14" },
        { id: "system", name: i18n("Came with Monet"), swatch: "about", source: true, glyph: "M12 7.5h.01M12 11v6" },
        { id: "mine", name: i18n("Added by you"), swatch: "users", source: true, glyph: "M8 8a4 4 0 1 0 8 0a4 4 0 1 0-8 0M4 21a8 8 0 0 1 16 0" },
        { id: "windows", name: i18n("Windows programs"), swatch: "windows", source: true, glyph: "M4 5.5l7-1v7H4zM13 4.2l7-1v8.3h-7zM4 13.5h7v7l-7-1zM13 13.5h7v8.3l-7-1z" }
    ]
    readonly property var kinds: [
        { id: "kind:internet", swatch: "wifi", glyph: "M4 10a12 12 0 0 1 16 0M7 13.5a7.5 7.5 0 0 1 10 0M10 17a3 3 0 0 1 4 0" },
        { id: "kind:office", swatch: "printers", glyph: "M7 9V4h10v5M7 17H5a1 1 0 0 1-1-1v-5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v5a1 1 0 0 1-1 1h-2M7 14h10v6H7z" },
        { id: "kind:graphics", swatch: "display", glyph: "M4 5h16v11H4zM10 20h4" },
        { id: "kind:media", swatch: "sound", glyph: "M5 10h3l5-4v12l-5-4H5zM17 9a4.5 4.5 0 0 1 0 6" },
        { id: "kind:games", swatch: "games", glyph: "M7.5 8h9a4.5 4.5 0 0 1 4.5 4.5v1a3.5 3.5 0 0 1-6.4 2L14 14.5h-4l-.6 1A3.5 3.5 0 0 1 3 13.5v-1A4.5 4.5 0 0 1 7.5 8zM8 10.5v3M6.5 12h3M15.5 11.5h.01M17.5 13h.01" },
        { id: "kind:development", swatch: "input", glyph: "M9 3h6a3 3 0 0 1 3 3v12a3 3 0 0 1-3 3H9a3 3 0 0 1-3-3V6a3 3 0 0 1 3-3zM12 3v5" },
        { id: "kind:utilities", swatch: "storage", glyph: "M4 7.5h16v9H4zM7.5 12h.01M11 12h5.5" },
        { id: "kind:system", swatch: "security", glyph: "M12 3l7.5 3v5.5c0 4.6-3.1 8.4-7.5 9.5-4.4-1.1-7.5-4.9-7.5-9.5V6zM9 12l2.2 2.2L15.5 10" },
        { id: "kind:other", swatch: "notifications", glyph: "M12 7.5h.01M12 11v6" }
    ].map(kind => Object.assign({ name: kindName(kind.id.slice(5)), kind: true }, kind))
    // Only the sections with an app in them (no "Windows programs" without any).
    readonly property var entries: sections.filter(s => !s.source || apps.some(a => a.source === s.id))
        .concat(kinds.filter(k => apps.some(a => inSection(a, k.id))))
    readonly property var sectionEntry: entries.find(e => e.id === section) || sections[0]
    readonly property var shown: {
        const words = fold(query.trim())
        const by = section === "recent" ? "recent" : sort
        const named = (a, b) => a.name.localeCompare(b.name)
        return apps.filter(a => inSection(a, section) && (words === "" || fold(a.name).indexOf(words) !== -1
                                                          || fold(a.detail).indexOf(words) !== -1))
            .sort(by === "name" ? named : (a, b) => (b.last || 0) - (a.last || 0) || named(a, b))
    }
    onEntriesChanged: if (loaded && !entries.some(e => e.id === section)) section = "all"
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
    Shortcut {
        sequences: [StandardKey.Back, "Escape"]
        enabled: root.current !== null
        onActivated: root.goBack()
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

        TapHandler {
            acceptedButtons: Qt.BackButton
            onTapped: root.goBack()
        }

        // The side: the name, search, then the sections ------------------------------
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
                    text: i18n("Apps")
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
                            objectName: "appsSearch"
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
                            // Enter opens the one app it finds, else goes to the icons.
                            onAccepted: {
                                if (root.shown.length === 1)
                                    root.open(root.shown[0])
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
                                text: i18n("Find an app")
                                color: look.dim
                                font: search.font
                                elide: Text.ElideRight
                            }
                        }
                    }
                }

                // The sections, then the kinds; the current one's pebble of glass glides to it.
                Flickable {
                    id: navList
                    objectName: "appsSections"
                    MouseScroll { view: navList }
                    ScrollInput { view: navList }
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    contentHeight: navColumn.implicitHeight
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    interactive: contentHeight > height

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
                                readonly property int count: root.apps.filter(a => root.inSection(a, modelData.id)).length
                                // The kinds, a little apart under their caption.
                                readonly property bool firstKind: modelData.kind === true && index > 0
                                    && root.entries[index - 1].kind !== true
                                Layout.fillWidth: true
                                Layout.preferredHeight: 34
                                Layout.topMargin: firstKind ? 34 : 0
                                radius: 12
                                color: navMouse.containsMouse && !current ? (look.dark ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(1, 1, 1, 0.4)) : "transparent"
                                Behavior on color { ColorAnimation { duration: Math.round(140 * root.speed) } }
                                border.width: activeFocus ? 2 : 0
                                border.color: look.lily
                                activeFocusOnTab: true
                                Keys.onSpacePressed: root.section = modelData.id
                                Keys.onReturnPressed: root.section = modelData.id
                                Accessible.role: Accessible.Button
                                Accessible.name: modelData.name

                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    visible: navItem.firstKind
                                    anchors.left: parent.left
                                    anchors.leftMargin: 10
                                    anchors.bottom: parent.top
                                    anchors.bottomMargin: 6
                                    text: i18n("Kinds")
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
                                    // A swatch cut from the paintings with a white mark.
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
                                            color: Qt.rgba(0, 0, 0, 0.3)
                                        }
                                        Glyph {
                                            anchors.centerIn: parent
                                            width: 15
                                            height: 15
                                            path: navItem.modelData.glyph
                                        }
                                    }
                                    Text {
                                        horizontalAlignment: Text.AlignLeft
                                        Layout.fillWidth: true
                                        text: navItem.modelData.name
                                        color: look.ink
                                        elide: Text.ElideRight
                                        font.pixelSize: 14
                                        font.weight: navItem.current ? Font.DemiBold : Font.Normal
                                    }
                                    Text {
                                        visible: root.loaded
                                        text: navItem.count
                                        color: look.dim
                                        font.pixelSize: 12
                                    }
                                }
                                MouseArea {
                                    id: navMouse
                                    anchors.fill: parent
                                    hoverEnabled: true
                                    onClicked: root.section = navItem.modelData.id
                                }
                            }
                        }
                    }
                }
            }
        }

        // The icons, or an app's page: on paper, so reading never fights the painting ------------
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
                            text: root.query !== "" ? i18n("Apps called “%1”", root.query.trim()) : root.sectionEntry.name
                            color: look.ink
                            elide: Text.ElideRight
                            font.family: "Fraunces 72pt SuperSoft"
                            font.weight: Font.Light
                            font.pixelSize: 30
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            visible: root.loaded
                            text: i18np("%1 app", "%1 apps", root.shown.length)
                            color: look.dim
                            font.pixelSize: 13
                        }
                    }
                    // By name or by when last opened: the chosen one on a pebble, as Settings' choices are.
                    Rectangle {
                        visible: root.section !== "recent" && root.shown.length > 1
                        implicitWidth: sortRow.implicitWidth + 6
                        implicitHeight: 34
                        radius: 17
                        color: look.wash
                        Row {
                            id: sortRow
                            anchors.centerIn: parent
                            spacing: 2
                            Repeater {
                                model: [["name", i18n("Name")], ["recent", i18n("Last opened")]]
                                Rectangle {
                                    id: sortChoice
                                    required property var modelData
                                    readonly property bool chosen: root.sort === modelData[0]
                                    width: sortLabel.implicitWidth + 24
                                    height: 28
                                    radius: 14
                                    color: chosen ? (look.dark ? Qt.rgba(1, 1, 1, 0.14) : "#FFFFFF")
                                        : sortMouse.containsMouse ? look.wash2 : "transparent"
                                    border.width: activeFocus ? 2 : 0
                                    border.color: look.lily
                                    activeFocusOnTab: true
                                    Keys.onReturnPressed: root.sort = modelData[0]
                                    Keys.onSpacePressed: root.sort = modelData[0]
                                    Accessible.role: Accessible.RadioButton
                                    Accessible.name: modelData[1]
                                    Accessible.checked: chosen
                                    Text {
                                        id: sortLabel
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
                                        onClicked: root.sort = sortChoice.modelData[0]
                                    }
                                }
                            }
                        }
                    }
                }

                LibraryStatus {
                    id: libraryStatus
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: header.bottom
                    anchors.leftMargin: 32
                    anchors.rightMargin: 24
                    anchors.topMargin: visible ? 12 : 0
                    tone: look
                    busy: root.libraryBusy
                    failed: root.libraryProblem
                    loaded: root.loaded
                    onRetry: root.refresh()
                    onRecovered: if (root.current === null) Qt.callLater(grid.enter)
                }

                GridView {
                    id: grid
                    objectName: "appsGrid"
                    MouseScroll { view: grid }
                    ScrollInput { view: grid }
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: libraryStatus.bottom
                    anchors.bottom: parent.bottom
                    anchors.topMargin: 16
                    anchors.leftMargin: 24
                    anchors.rightMargin: 16
                    clip: true
                    model: root.shown
                    // Tiles of about 150 pixels, as many as fit; they grow or shrink a little to fill the row.
                    readonly property int columns: Math.max(3, Math.round(width / 150))
                    cellWidth: Math.floor(width / columns)
                    cellHeight: 156
                    boundsBehavior: Flickable.StopAtBounds
                    cacheBuffer: cellHeight * 2
                    currentIndex: -1
                    activeFocusOnTab: true
                    keyNavigationEnabled: true
                    Accessible.name: i18n("Apps")
                    // From the search (Enter or ↓): the keys go to the icons.
                    function enter() {
                        forceActiveFocus()
                        if (count > 0 && currentIndex < 0)
                            currentIndex = 0
                    }
                    Keys.onReturnPressed: if (currentIndex >= 0) root.openPage(root.shown[currentIndex])
                    Keys.onEnterPressed: if (currentIndex >= 0) root.openPage(root.shown[currentIndex])
                    Keys.onSpacePressed: if (currentIndex >= 0) root.openPage(root.shown[currentIndex])
                    Keys.onUpPressed: event => {
                        if (currentIndex < columns)
                            search.forceActiveFocus()
                        else
                            moveCurrentIndexUp()
                    }

                    delegate: Item {
                        id: tile
                        required property var modelData
                        required property int index
                        width: grid.cellWidth
                        height: grid.cellHeight
                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: 6
                            radius: 18
                            color: tileMouse.pressed ? look.press
                                : tileMouse.containsMouse || grid.currentIndex === tile.index && grid.activeFocus ? look.wash2
                                : "transparent"
                            border.width: grid.activeFocus && grid.currentIndex === tile.index ? 2 : 0
                            border.color: look.lily
                            Behavior on color { ColorAnimation { duration: Math.round(120 * root.speed) } }
                            ColumnLayout {
                                anchors.fill: parent
                                anchors.margins: 10
                                anchors.topMargin: 16
                                spacing: 8
                                Kirigami.Icon {
                                    Layout.alignment: Qt.AlignHCenter
                                    Layout.preferredWidth: 56
                                    Layout.preferredHeight: 56
                                    source: tile.modelData.icon
                                    fallback: "application-x-executable"
                                }
                                Text {
                                    Layout.fillWidth: true
                                    horizontalAlignment: Text.AlignHCenter
                                    text: tile.modelData.name
                                    color: look.ink
                                    wrapMode: Text.Wrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                    font.pixelSize: 14
                                }
                                Item { Layout.fillHeight: true }
                            }
                        }
                        MouseArea {
                            id: tileMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            acceptedButtons: Qt.LeftButton
                            onClicked: {
                                grid.currentIndex = tile.index
                                root.openPage(tile.modelData)
                            }
                            onDoubleClicked: root.open(tile.modelData)
                        }
                        Accessible.role: Accessible.Button
                        Accessible.name: tile.modelData.name
                        Accessible.description: tile.modelData.detail
                    }
                }

                // Nothing found, or nothing yet.
                Text {
                    anchors.centerIn: grid
                    width: Math.min(grid.width - 64, 420)
                    horizontalAlignment: Text.AlignHCenter
                    visible: root.loaded && root.shown.length === 0
                    text: root.query !== "" ? i18n("No app is called “%1”.", root.query.trim())
                        : root.section === "recent" ? i18n("The apps you open will be here.")
                        : i18n("No apps here.")
                    color: look.dim
                    wrapMode: Text.Wrap
                    font.pixelSize: 15
                }
            }

            // An app's page ---------------------------------------------------------------
            Item {
                id: appPage
                objectName: "appPage"
                anchors.fill: parent
                visible: root.current !== null
                readonly property var app: root.current || ({})

                Pill {
                    id: back
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.margins: 20
                    tone: look
                    glyph: "M15 5l-7 7 7 7"
                    text: root.sectionEntry.name
                    onClicked: root.goBack()
                }

                ColumnLayout {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: back.bottom
                    anchors.leftMargin: 48
                    anchors.rightMargin: 48
                    anchors.topMargin: 28
                    spacing: 18

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 24
                        Kirigami.Icon {
                            Layout.preferredWidth: 96
                            Layout.preferredHeight: 96
                            Layout.alignment: Qt.AlignTop
                            source: appPage.app.icon || ""
                            fallback: "application-x-executable"
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: appPage.app.name || ""
                                color: look.ink
                                wrapMode: Text.Wrap
                                font.family: "Fraunces 72pt SuperSoft"
                                font.weight: Font.Light
                                font.pixelSize: 34
                            }
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                visible: text !== ""
                                text: appPage.app.detail || ""
                                color: look.dim
                                wrapMode: Text.Wrap
                                font.pixelSize: 15
                            }
                            RowLayout {
                                Layout.topMargin: 12
                                spacing: 10
                                Pill {
                                    id: openButton
                                    objectName: "appOpen"
                                    tone: look
                                    kind: "lily"
                                    text: i18n("Open")
                                    onClicked: root.open(appPage.app)
                                }
                                Pill {
                                    objectName: "appStore"
                                    visible: appPage.app.source === "store" && appPage.app.store !== ""
                                    tone: look
                                    text: i18n("Update or remove in the Store")
                                    onClicked: root.storePage(appPage.app)
                                }
                                Pill {
                                    id: removeButton
                                    objectName: "appRemove"
                                    visible: appPage.app.removable === true && !root.confirmRemove
                                    tone: look
                                    text: i18n("Remove…")
                                    onClicked: root.confirmRemove = true
                                }
                            }
                        }
                    }

                    // Before a shortcut goes: what it means, and the button that does it.
                    Rectangle {
                        Layout.fillWidth: true
                        visible: root.confirmRemove
                        implicitHeight: confirmRow.implicitHeight + 28
                        radius: 14
                        color: look.wash
                        RowLayout {
                            id: confirmRow
                            anchors.fill: parent
                            anchors.margins: 14
                            spacing: 12
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                Layout.fillWidth: true
                                text: i18n("Remove %1 from your apps? The program itself stays where it is.", appPage.app.name || "")
                                color: look.ink
                                wrapMode: Text.Wrap
                                font.pixelSize: 14
                            }
                            Pill {
                                tone: look
                                text: i18n("Cancel")
                                onClicked: root.confirmRemove = false
                            }
                            Pill {
                                objectName: "appRemoveConfirm"
                                tone: look
                                kind: "lily"
                                text: i18n("Remove")
                                onClicked: root.remove(appPage.app)
                            }
                        }
                    }

                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        visible: root.problem !== ""
                        text: root.problem
                        color: look.ink
                        wrapMode: Text.Wrap
                        font.pixelSize: 14
                        Accessible.role: Accessible.AlertMessage
                    }

                    // What it is, plainly.
                    GridLayout {
                        Layout.topMargin: 8
                        columns: 2
                        columnSpacing: 32
                        rowSpacing: 10
                        Text { text: i18n("Came from"); color: look.dim; font.pixelSize: 14 }
                        Text { text: root.sourceName(appPage.app.source); color: look.ink; font.pixelSize: 14 }
                        Text { text: i18n("Kind"); color: look.dim; font.pixelSize: 14 }
                        Text { text: root.kindName(appPage.app.group); color: look.ink; font.pixelSize: 14 }
                        Text { text: i18n("Last opened"); color: look.dim; font.pixelSize: 14 }
                        Text { text: root.lastText(appPage.app.last); color: look.ink; font.pixelSize: 14 }
                    }
                }
            }
        }
    }
}
