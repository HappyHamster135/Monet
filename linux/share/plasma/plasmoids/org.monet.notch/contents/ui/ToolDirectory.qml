import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as K
import org.kde.plasma.plasma5support as P5

ColumnLayout {
    id: page
    required property var rows
    required property var groups
    required property var hidden
    required property var favorites
    required property string group
    required property string query
    signal filterChanged(string group, string query)
    signal selected(string key)
    signal manageRequested()
    signal radialRequested()
    signal loaded(var rows, var groups)
    property bool failed: false
    property bool motion: true
    property bool searching: query.length > 0
    readonly property bool editingEvent: searching
    function closeEditor() { searching = false; filterChanged(group, ""); results.forceActiveFocus() }
    function focusSearch() { searching = true; search.forceActiveFocus(); search.selectAll() }
    readonly property bool menuOpen: category.popup.opened
    onEnabledChanged: if (!enabled) category.popup.close()
    spacing: 6
    // The catalogue keeps descriptive names for search and accessibility;
    // launcher captions must fit beneath a small glyph without splitting words.
    readonly property var captions: ({
        "switch-appearance": i18n("Appearance"), "automatic-appearance": i18n("Auto appearance"),
        "keyboard-light": i18n("Keyboard light"), "empty-trash": i18n("Empty Trash"),
        "lock-screen": i18n("Lock screen"), "display-off": i18n("Displays off"),
        "emoji": i18n("Emoji"), "calendars": i18n("Calendars"), "downloads": i18n("Downloads"),
        "scripts": i18n("Scripts"), "snippets": i18n("Snippets"), "clipboard": i18n("Clipboard"),
        "extra-clicks": i18n("Click filter"), "wheel-scrolling": i18n("Scrolling"),
        "quit-on-close": i18n("Quit on close"), "quit-protection": i18n("Quit protection"),
        "paste-shortcut": i18n("Plain paste"), "plain": i18n("Plain text"),
        "clipboard-expiry": i18n("Clipboard expiry"), "link-settings": i18n("Link settings"),
        "clean": i18n("Clean link"), "color": i18n("Color picker"), "screenshot": i18n("Screenshot"),
        "ocr": i18n("Text scanner"), "record": i18n("Record screen"), "recordings": i18n("Recordings"),
        "camera": i18n("Camera"), "watch": i18n("Watch"), "compress": i18n("Compress"),
        "trash": i18n("Trash"), "rename-shortcut": i18n("Rename"), "files": i18n("Files"),
        "storage": i18n("Storage"), "appimage": i18n("AppImage"), "apps": i18n("Uninstaller"),
        "updates": i18n("Updates"), "homebrew": i18n("Homebrew"), "store": i18n("App store"),
        "wallpaper": i18n("Wallpaper"), "display": i18n("Displays"), "power": i18n("Power"),
        "mouse": i18n("Mouse"), "touchpad": i18n("Trackpad"), "window-switcher": i18n("App switcher"),
        "windows": i18n("Window focus"), "remap": i18n("Remap keys"), "shortcuts": i18n("Shortcuts"),
        "debounce": i18n("Sticky keys"), "sound": i18n("Sound"), "media-keys": i18n("Media keys"),
        "output-order": i18n("Audio priority"), "output": i18n("Audio output"), "mic": i18n("Microphone"),
        "media": i18n("Queue & lyrics"), "notifications": i18n("Notifications"), "theme": i18n("Theme"),
        "agents": i18n("AI agents"), "process-control": i18n("End process"), "ports": i18n("Ports"),
        "processes": i18n("System monitor"), "network": i18n("Network"), "monitor-alerts": i18n("System alerts"),
        "fans": i18n("Fans"), "devices": i18n("USB devices"), "bluetooth": i18n("Bluetooth"),
        "wheel-settings": i18n("Edit wheels"), "wheel": i18n("Radial menu"),
        "shelf": i18n("File shelf"), "notes": i18n("Notes"), "awake": i18n("Keep awake"),
        "mixer": i18n("Volume mixer"),
        "notch-settings": i18n("Notch settings"), "text-tools": i18n("Text tools"), "color-tools": i18n("Color palette")
    })
    readonly property var matches: {
        const words = query.normalize("NFKD").toLowerCase().trim().split(/\s+/).filter(Boolean)
        const result = rows.filter(row => !hidden.includes(row.key) &&
            (words.length || group === "all" || (group === "favorites" ? favorites.includes(row.key) : row.group === group)) &&
            words.every(word => (row.label.toLowerCase()+" "+row.terms).includes(word)))
        function rank(row) {
            const index = favorites.indexOf(row.key)
            return index === -1 ? favorites.length : index
        }
        return result.sort((a,b) => (words.length ? 0 : rank(a)-rank(b)) || a.label.localeCompare(b.label))
    }
    P5.DataSource {
        id: catalog
        engine: "executable"; connectedSources: []
        function read() { if (!connectedSources.length) connectSource("/usr/bin/python3 '@DATADIR@/monet/utilities/actions.py'") }
        onNewData: (cmd, data) => {
            disconnectSource(cmd)
            try {
                const result = JSON.parse(data.stdout)
                page.loaded(result.rows, result.groups)
                page.failed = false
            } catch (_) { page.failed = true }
        }
    }
    Component.onCompleted: if (!rows.length) catalog.read()
    RowLayout {
        Layout.fillWidth: true
        spacing: 5
        IslandComboBox {
            id: category
            popupBounds: page
            objectName: "notchToolCategory"
            visible: !page.searching
            Layout.preferredWidth: Math.min(155, page.width - 84); Layout.minimumWidth: 0
            model: page.groups; textRole: "label"
            Accessible.name: i18n("Category")
            currentIndex: Math.max(0, page.groups.findIndex(g => g.key === page.group))
            onActivated: i => page.filterChanged(page.groups[i].key, "")
        }
        IslandTextField {
            id: search
            objectName: "notchToolSearch"
            visible: page.searching
            Layout.fillWidth: true; Layout.minimumWidth: 0; text: page.query; placeholderText: i18n("Find a tool…")
            Accessible.name: placeholderText
            onTextEdited: page.filterChanged(page.group, text)
            onAccepted: if (page.matches.length) page.selected(page.matches[0].key)
        }
        Item { visible: !page.searching; Layout.fillWidth: true }
        IslandButton {
            objectName: "notchToolSearchToggle"
            plain: true; icon.name: page.searching ? "window-close" : "system-search"
            text: page.searching ? i18n("Close search") : i18n("Find a tool")
            onClicked: page.searching ? page.closeEditor() : page.focusSearch()
        }
        IslandButton {
            objectName: "notchRadialButton"
            plain: true; icon.name: "wheel"; text: i18n("Radial menu")
            onClicked: page.radialRequested()
        }
        IslandButton {
            plain: true; icon.name: "configure"; text: i18n("Choose tools and favorites")
            onClicked: page.manageRequested()
        }
    }
    GridView {
        id: results
        objectName: "notchToolGrid"
        Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 0; clip: true
        readonly property int columns: Math.max(1, Math.min(Math.floor(width / 84), Math.ceil(page.matches.length / rowsVisible)))
        readonly property int rowsVisible: Math.max(1, Math.min(3, Math.floor(height / 78)))
        readonly property int capacity: columns * rowsVisible
        readonly property int pageCount: Math.ceil(page.matches.length / capacity)
        readonly property int currentPage: Math.max(0, Math.min(pageCount - 1, Math.round(contentX / Math.max(1, width))))
        cellWidth: width / columns; cellHeight: height / rowsVisible
        flow: GridView.FlowTopToBottom; flickableDirection: Flickable.HorizontalFlick
        // Pad the last page so its tools never overlap the preceding page.
        model: page.matches.concat(Array(pageCount * capacity - page.matches.length).fill(null))
        boundsBehavior: Flickable.StopAtBounds
        cacheBuffer: width
        reuseItems: true
        activeFocusOnTab: page.matches.length > 0
        Accessible.role: Accessible.List
        Accessible.name: i18n("Tools")
        highlightFollowsCurrentItem: false
        property bool smoothing: false
        property int targetPage: 0
        function turnTo(index, focus = false) {
            if (flicking) cancelFlick()
            const target = Math.max(0, Math.min(pageCount - 1, index))
            currentIndex = Math.min(page.matches.length - 1, target * capacity)
            const destination = target * width
            smoothing = page.motion && K.Units.longDuration > 1
            targetPage = target
            contentX = destination
            if (focus) forceActiveFocus(Qt.TabFocusReason)
        }
        function focusTool(index) {
            const target = Math.max(0, Math.min(page.matches.length - 1, index))
            turnTo(Math.floor(target / capacity))
            currentIndex = target
        }
        onModelChanged: {
            smoothing = false; slide.stop(); targetPage = 0; currentIndex = page.matches.length ? 0 : -1
            Qt.callLater(positionViewAtBeginning)
        }
        onMovementStarted: { smoothing = false; slide.stop() }
        onMovementEnded: turnTo(currentPage)
        Behavior on contentX {
            enabled: results.smoothing
            SmoothedAnimation { id: slide; duration: 120; velocity: results.width * 10; maximumEasingTime: 40; reversingMode: SmoothedAnimation.Immediate }
        }
        Connections { target: page; function onMotionChanged() { if (!page.motion) { slide.stop(); results.turnTo(results.currentPage) } } }
        Keys.onPressed: event => {
            if (event.key === Qt.Key_Home) focusTool(0)
            else if (event.key === Qt.Key_End) focusTool(page.matches.length - 1)
            else if (event.key === Qt.Key_PageDown || event.key === Qt.Key_PageUp)
                turnTo(currentPage + (event.key === Qt.Key_PageDown ? 1 : -1))
            else if (event.key === Qt.Key_Left || event.key === Qt.Key_Right)
                focusTool(currentIndex + (event.key === Qt.Key_Right ? rowsVisible : -rowsVisible))
            else if (event.key === Qt.Key_Down || event.key === Qt.Key_Up)
                focusTool(currentIndex + (event.key === Qt.Key_Down ? 1 : -1))
            else return
            event.accepted = true
        }
        Keys.onReturnPressed: if (currentItem?.modelData) currentItem.clicked()
        Keys.onEnterPressed: if (currentItem?.modelData) currentItem.clicked()
        delegate: IslandActionTile {
            required property var modelData
            required property int index
            diameter: 40
            objectName: modelData ? "notch-tool-" + modelData.key : ""
            width: results.cellWidth; height: results.cellHeight
            visible: !!modelData; enabled: !!modelData
            focusPolicy: Qt.NoFocus
            Accessible.ignored: !modelData || Math.floor(index / results.capacity) !== results.currentPage
            text: modelData ? page.captions[modelData.key] || modelData.label : ""; fullName: modelData?.label || ""
            icon.name: modelData?.icon || ""; symbol: modelData?.key || ""
            favorite: !!modelData && page.favorites.includes(modelData.key)
            checked: !!modelData && results.activeFocus && results.currentIndex === index
            onClicked: if (modelData) page.selected(modelData.key)
        }
        WheelHandler {
            id: wheel
            parent: results; target: null
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            property real travel: 0
            property bool direct: false
            function settle() { if (direct) { direct = false; results.turnTo(results.currentPage) } }
            property Timer wheelEnd: Timer { interval: 100; onTriggered: wheel.settle() }
            onWheel: event => handle(event, false)
            function handle(event, horizontal) {
                const dx = event.pixelDelta.x || event.angleDelta.x
                const dy = event.pixelDelta.y || event.angleDelta.y
                if ((dx || dy) && (Math.abs(dx) > Math.abs(dy)) !== horizontal) { event.accepted = false; return }
                event.accepted = true
                if (event.phase === Qt.ScrollBegin) {
                    travel = 0; wheelEnd.stop(); results.smoothing = false; slide.stop(); results.cancelFlick()
                }
                const pixels = event.pixelDelta.x || event.pixelDelta.y
                if (pixels) {
                    if (!direct) { results.smoothing = false; slide.stop(); results.cancelFlick(); direct = true }
                    results.contentX = Math.max(0, Math.min((results.pageCount - 1) * results.width, results.contentX - pixels))
                    if (event.phase === Qt.NoScrollPhase) wheelEnd.restart()
                } else if (event.phase === Qt.NoScrollPhase) {
                    const delta = event.angleDelta.x || event.angleDelta.y
                    if (travel * delta < 0) travel = 0
                    travel += delta
                    if (Math.abs(travel) < 120) return
                    const at = slide.running ? results.targetPage : results.currentPage
                    const steps = Math.trunc(travel / 120)
                    travel -= steps * 120
                    results.turnTo(at - steps)
                }
                if (event.phase === Qt.ScrollEnd) { wheelEnd.stop(); settle() }
            }
            property Connections changes: Connections { target: page; function onMatchesChanged() { wheel.wheelEnd.stop(); wheel.direct = false; wheel.travel = 0 } }
        }
        WheelHandler {
            parent: results; target: null; orientation: Qt.Horizontal
            acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad
            onWheel: event => wheel.handle(event, true)
        }
        IslandEmpty {
            anchors.fill: parent
            visible: results.count === 0
            symbol: "system-search"
            title: page.failed ? i18n("Could not load tools.") : !page.rows.length ? i18n("Loading…")
                : page.group === "favorites" && !page.query ? i18n("No favorites yet") : i18n("No matching tools.")
        }
    }
    Item {
        // Reserve the same space on single-page categories so pagination cannot
        // change the grid capacity and create a layout feedback loop.
        Layout.fillWidth: true; Layout.preferredHeight: 24
        ListView {
            id: dots; objectName: "notchToolPageDots"
            anchors.centerIn: parent; width: Math.min(parent.width, count * 24); height: 24
            visible: count > 1; clip: true; orientation: ListView.Horizontal
            boundsBehavior: Flickable.StopAtBounds
            model: results.pageCount; currentIndex: results.currentPage
            onCurrentIndexChanged: positionViewAtIndex(currentIndex, ListView.Contain)
            delegate: C.AbstractButton {
                id: dot
                required property int index
                objectName: "notch-tool-dot-" + index
                width: 24; height: 24; hoverEnabled: true
                Accessible.role: Accessible.PageTab
                Accessible.name: i18n("Page %1 of %2", index + 1, results.pageCount)
                Accessible.selected: results.currentPage === index
                onClicked: results.turnTo(index, true)
                Keys.onReturnPressed: click()
                Keys.onEnterPressed: click()
                background: null
                contentItem: Item {
                    Rectangle {
                        anchors.centerIn: parent
                        width: results.currentPage === dot.index ? 16 : 6; height: 6; radius: 3
                        color: results.currentPage === dot.index ? "#eeeeef" : dot.hovered ? "#a0a0aa" : "#55555f"
                        border.width: dot.visualFocus ? 1 : 0; border.color: "#a3ccff"
                    }
                }
            }
        }
    }
    IslandButton { visible: page.group === "favorites" && !page.query && page.rows.length > 0 && !page.matches.length
        caption: true; Layout.alignment: Qt.AlignHCenter; text: i18n("Browse all tools"); onClicked: page.filterChanged("all", "") }
    IslandButton { visible: page.failed; caption: true; text: i18n("Retry"); onClicked: catalog.read() }
    Shortcut { sequences: [StandardKey.Find]; enabled: page.visible && page.enabled; onActivated: page.focusSearch() }
}
