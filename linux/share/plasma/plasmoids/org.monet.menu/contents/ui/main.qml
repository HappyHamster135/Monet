/*
 * The Monet menu, behind the sun in the left island: your pinned apps and the
 * files you opened last, on the glass; a search that finds apps, files and
 * settings as you type; every app from A to Z; and you at the foot with Lock
 * and the power sign, which asks on Monet's restart and shut-down screen.
 *
 * KDE's menu models do the work (org.kde.plasma.private.kicker): pinning,
 * search, recent files and launching are KDE's own menu's, so pins carry over.
 */
import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Templates as T
import org.kde.coreaddons as KCoreAddons
import org.kde.kirigami as Kirigami
import org.kde.kitemmodels as KItemModels
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasma5support as P5Support
import org.kde.plasma.plasmoid
import org.kde.plasma.private.kicker as Kicker
import org.kde.plasma.private.sessions

PlasmoidItem {
    id: root

    Plasmoid.icon: "monet"
    Plasmoid.contextualActions: [TaskManagerAction {}]
    toolTipMainText: i18n("Menu")
    toolTipSubText: i18n("Your apps, and a search for everything on this PC")
    preferredRepresentation: compactRepresentation

    // Animations follow the desktop's speed, and stop when it's set to instant.
    readonly property real speed: Kirigami.Units.longDuration / 200
    // Every app from A to Z, once KDE's model has read them.
    property var everyApp: null
    readonly property string firstName: (user.fullName || user.loginName || "").trim().split(" ")[0]
    property var everydayResults: []
    property string everydaySource: ""
    property string everydayQuery: ""
    property bool everydayPending: false
    property string everydayError: ""
    property string openingResult: ""
    signal everydayReady()
    Timer { id: everydayDelay; interval: 140; onTriggered: root.runEveryday() }

    function findEveryday(query) {
        everydayDelay.stop()
        everydayQuery = query
        everydayResults = []
        everydayError = ""
        everydayPending = query.trim() !== ""
        everydaySource = ""
        if (!everydayPending) { everydayReady(); return }
        everydayDelay.restart()
    }
    function runEveryday() {
        const bytes = unescape(encodeURIComponent(everydayQuery.trim().slice(0, 256)))
        let encoded = ""
        for (let i = 0; i < bytes.length; i++) encoded += bytes.charCodeAt(i).toString(16).padStart(2, "0")
        everydaySource = "'@LIBEXECDIR@/monet-quick' search " + encoded
        helper.connectSource(everydaySource)
    }
    function launchEveryday(entry) {
        if (openingResult !== "" || !entry || !/^[a-z-]+$/.test(entry.id)) return
        openingResult = "'@LIBEXECDIR@/monet-quick' search-open " + entry.id
        helper.connectSource(openingResult)
    }

    readonly property Kicker.RootModel apps: Kicker.RootModel {
        autoPopulate: false
        appletInterface: root
        appNameFormat: 0 // names only: "Files", not "Files (File Manager)"
        flat: true
        sorted: true
        showSeparators: false
        showTopLevelItems: true
        showAllApps: true
        showAllAppsCategorized: false
        showRecentApps: false
        showRecentDocs: false
        showPowerSession: false
        showFavoritesPlaceholder: true
        highlightNewlyInstalledApps: false

        onRefreshed: root.everyApp = root.findEveryApp()

        Component.onCompleted: {
            favoritesModel.initForClient("org.monet.menu.favorites.instance-" + Plasmoid.id)
            // A new account starts with Monet's pins (kicker-extra-favoritesrc);
            // one that had KDE's menu keeps its own.
            if (!Plasmoid.configuration.favoritesPinned) {
                if (favoritesModel.count < 1) {
                    favoritesModel.portOldFavorites([])
                }
                Plasmoid.configuration.favoritesPinned = true
            }
        }
    }

    readonly property Kicker.RunnerModel finder: Kicker.RunnerModel {
        appletInterface: root
        mergeResults: true
        favoritesModel: root.apps.favoritesModel
    }

    readonly property Kicker.RecentUsageModel recent: Kicker.RecentUsageModel {
        shownItems: Kicker.RecentUsageModel.OnlyDocs
        favoritesModel: root.apps.favoritesModel
    }

    function findEveryApp() {
        for (let row = 0; row < apps.count; ++row) {
            const model = apps.modelForRow(row)
            if (model && model.description === "KICKER_ALL_MODEL") {
                return model
            }
        }
        return null
    }

    // Opens an app, file or setting; the menu closes when it did.
    function launch(model, index) {
        if (model && index >= 0 && index < model.count && model.trigger(index, "", null)) {
            root.expanded = false
        }
    }

    function isPinned(id) {
        return id !== "" && apps.favoritesModel.isFavorite(id)
    }

    // Apps can be pinned and unpinned (search results that aren't apps have no id).
    function showAppMenu(item, id) {
        if (!id) {
            return
        }
        appMenu.favoriteId = id
        appMenu.visualParent = item
        appMenu.openRelative()
    }

    SessionManagement {
        id: sessions
    }

    KCoreAddons.KUser {
        id: user
    }

    // Accounts in KDE's settings, the way Monet Settings opens it.
    P5Support.DataSource {
        id: helper
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            if (source === root.everydaySource) {
                let result = {}
                try { result = JSON.parse(data.stdout || "{}") } catch (error) {}
                const ok = data["exit code"] === 0 && Array.isArray(result.results)
                root.everydayResults = ok ? result.results : []
                root.everydayError = ok ? "" : i18n("Suggestions couldn't load. Other search results are still available.")
                root.everydayPending = false
                root.everydayReady()
            } else if (source === root.openingResult) {
                let result = {}
                try { result = JSON.parse(data.stdout || "{}") } catch (error) {}
                root.openingResult = ""
                if (data["exit code"] === 0 && result.ok === true) root.expanded = false
                else root.everydayError = i18n("Couldn't open this result. Try again.")
            }
        }
    }

    PlasmaExtras.Menu {
        id: appMenu
        property string favoriteId
        placement: PlasmaExtras.Menu.BottomPosedLeftAlignedPopup

        PlasmaExtras.MenuItem {
            text: root.isPinned(appMenu.favoriteId) ? i18n("Unpin from Menu") : i18n("Pin to Menu")
            icon: root.isPinned(appMenu.favoriteId) ? "list-remove" : "window-pin"
            onClicked: {
                if (root.isPinned(appMenu.favoriteId)) {
                    root.apps.favoritesModel.removeFavorite(appMenu.favoriteId)
                } else {
                    root.apps.favoritesModel.addFavorite(appMenu.favoriteId)
                }
            }
        }
    }

    fullRepresentation: PlasmaExtras.Representation {
        id: page
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true
        Layout.preferredWidth: Kirigami.Units.gridUnit * 30
        Layout.preferredHeight: Kirigami.Units.gridUnit * 33
        Layout.minimumWidth: Kirigami.Units.gridUnit * 24
        Layout.minimumHeight: Kirigami.Units.gridUnit * 26
        collapseMarginsHint: true
        focus: true

        // Pinned apps and recent files, or all apps from A to Z; search results while there's a search.
        property bool everything: false
        property bool launchWhenFound: false
        property int everydayIndex: 0
        property int applicationIndex: -1
        readonly property bool searching: search.text.trim() !== ""
        readonly property var found: root.finder.count > 0 ? root.finder.modelForRow(0) : null
        readonly property Item shownView: searching ? results : everything ? allApps : pinned
        readonly property color ink: Kirigami.Theme.textColor

        // Kicker supplies favoriteId only for installed application matches.
        // Partition one native query, preserving its relevance order and actions.
        KItemModels.KSortFilterProxyModel {
            id: applicationMatches
            sourceModel: page.found
            filterRoleName: "favoriteId"
            filterRegularExpression: /.+/
        }
        KItemModels.KSortFilterProxyModel {
            id: otherMatches
            sourceModel: page.found
            filterRoleName: "favoriteId"
            filterRegularExpression: /^$/
        }
        function launchMatch(proxy, index) {
            if (!root.finder.querying && index >= 0 && index < proxy.count)
                root.launch(found, proxy.mapToSource(proxy.index(index, 0)).row)
        }
        function focusOtherResults() {
            if (results.count < 1) return
            applicationIndex = -1
            everydayIndex = -1
            results.currentIndex = 0
            results.positionViewAtIndex(0, ListView.Contain)
            // Focus the delegate, not the ListView scope (which may restore its header).
            if (results.currentItem) results.currentItem.forceActiveFocus(Qt.TabFocusReason)
        }

        function reset() {
            search.text = ""
            everything = false
            launchWhenFound = false
            pinned.currentIndex = -1
            recentFiles.currentIndex = -1
            allApps.currentIndex = -1
            allApps.positionViewAtBeginning()
            search.forceActiveFocus()
        }

        // Enter in the search opens the first result, as soon as there is one.
        function launchFirst() {
            // Kicker retains old rows during a query. Never open a stale match
            // or a folder while the matching application is still arriving.
            if (!searching) return
            if (root.finder.querying) {
                launchWhenFound = true
            } else if (applicationMatches.count > 0) {
                launchMatch(applicationMatches, 0)
            } else if (root.everydayPending) {
                launchWhenFound = true
            } else if (root.everydayError !== "" && root.everydayResults.length === 0 && everydayIndex >= 0) {
                launchWhenFound = true
                root.findEveryday(search.text)
            } else if (root.everydayResults.length > 0 && everydayIndex >= 0) {
                root.launchEveryday(root.everydayResults[Math.min(everydayIndex, root.everydayResults.length - 1)])
            } else if (otherMatches.count > 0) {
                launchMatch(otherMatches, Math.max(results.currentIndex, 0))
            }
        }

        // Typing anywhere goes to the search.
        function typeIntoSearch(event) {
            if (event.text !== "" && /\S/.test(event.text)
                    && !(event.modifiers & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))) {
                search.text += event.text
                search.forceActiveFocus()
                event.accepted = true
            }
        }

        Keys.onEscapePressed: {
            if (searching) {
                search.text = ""
                search.forceActiveFocus()
            } else if (everything) {
                everything = false
                search.forceActiveFocus()
            } else {
                root.expanded = false
            }
        }

        Component.onCompleted: {
            root.apps.refresh()
            reset()
        }

        Connections {
            target: root
            function onEverydayReady() {
                if (page.launchWhenFound) {
                    page.launchWhenFound = false
                    if (root.everydayError === "") page.launchFirst()
                }
            }
            function onExpandedChanged() {
                if (root.expanded) {
                    page.reset()
                } else {
                    page.launchWhenFound = false
                }
            }
        }

        Connections {
            target: root.finder
            function onQueryFinished() {
                if (page.launchWhenFound) {
                    page.launchWhenFound = false
                    page.launchFirst()
                }
            }
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: Kirigami.Units.largeSpacing * 2
            spacing: Kirigami.Units.largeSpacing * 2

            // The search: a well with a lily ring while you type.
            T.TextField {
                id: search
                objectName: "menuSearch"
                maximumLength: 256
                Layout.fillWidth: true
                implicitHeight: 42
                // Room for the magnifier, on the right in a right-to-left language.
                leftPadding: LayoutMirroring.enabled ? 16 : 44
                rightPadding: LayoutMirroring.enabled ? 44 : 16
                verticalAlignment: TextInput.AlignVCenter
                color: page.ink
                placeholderText: i18n("Search apps, files and settings")
                placeholderTextColor: Qt.rgba(page.ink.r, page.ink.g, page.ink.b, 0.5)
                selectionColor: Kirigami.Theme.highlightColor
                selectedTextColor: Kirigami.Theme.highlightedTextColor
                font.family: "Inter"
                font.pixelSize: 15
                Accessible.name: i18n("Search")
                onTextChanged: {
                    page.launchWhenFound = false
                    page.everydayIndex = 0
                    page.applicationIndex = -1
                    root.finder.query = text
                    root.findEveryday(text)
                    results.currentIndex = 0
                }
                Keys.onReturnPressed: page.launchFirst()
                Keys.onEnterPressed: page.launchFirst()
                Keys.onDownPressed: {
                    if (page.searching && applicationMatches.count > 0) {
                        results.headerItem.focusApp(0)
                        return
                    }
                    if (page.searching && root.everydayResults.length > 0) {
                        results.headerItem.focusAt(0)
                        return
                    }
                    page.everydayIndex = -1
                    page.shownView.forceActiveFocus()
                    if (page.shownView.currentIndex < 0) {
                        page.shownView.currentIndex = 0
                    }
                }
                // A pebble of lighter glass with light caught in its rim, as Settings' search is.
                background: Rectangle {
                    readonly property bool dark: Kirigami.Theme.backgroundColor.hslLightness < 0.5
                    radius: height / 2
                    color: dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.34)
                    border.width: search.activeFocus ? 2 : 1
                    border.color: search.activeFocus ? Kirigami.Theme.highlightColor
                        : dark ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.75)
                    Kirigami.Icon {
                        anchors.left: parent.left
                        anchors.leftMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        width: 20
                        height: 20
                        source: "edit-find"
                        opacity: 0.7
                    }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    anchors.fill: parent
                    leftPadding: search.leftPadding
                    rightPadding: search.rightPadding
                    verticalAlignment: Text.AlignVCenter
                    visible: search.length === 0 && search.preeditText === ""
                    text: search.placeholderText
                    color: search.placeholderTextColor
                    elide: Text.ElideRight
                    font: search.font
                }
            }

            // What the list is: pinned or all apps, and the way to the other.
            RowLayout {
                Layout.fillWidth: true
                visible: !page.searching

                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.smallSpacing
                    text: page.everything ? i18n("All apps") : i18n("Pinned")
                    color: page.ink
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: 20
                }
                // The way to the other list: a pebble of the glass, as Monet's buttons are, its
                // arrow pointing where it goes ("All apps ›", "‹ Pinned").
                Rectangle {
                    id: otherList
                    function go() {
                        page.everything = !page.everything
                        page.shownView.currentIndex = -1
                    }
                    readonly property bool dark: Kirigami.Theme.backgroundColor.hslLightness < 0.5
                    implicitWidth: otherRow.implicitWidth + 24
                    implicitHeight: 30
                    radius: 11
                    color: dark ? Qt.rgba(1, 1, 1, otherHover.hovered ? 0.16 : 0.1)
                        : Qt.rgba(0.11, 0.106, 0.098, otherHover.hovered ? 0.11 : 0.07)
                    scale: otherTap.pressed ? 0.96 : 1
                    border.width: activeFocus ? 2 : 0
                    border.color: dark ? "#4DB4A0" : "#357F72"
                    activeFocusOnTab: true
                    Keys.onReturnPressed: go()
                    Keys.onEnterPressed: go()
                    Keys.onSpacePressed: go()
                    Behavior on color { ColorAnimation { duration: Kirigami.Units.shortDuration } }
                    Behavior on scale { NumberAnimation { duration: Kirigami.Units.shortDuration } }
                    RowLayout {
                        id: otherRow
                        anchors.centerIn: parent
                        spacing: 4
                        layoutDirection: page.everything ? Qt.RightToLeft : Qt.LeftToRight
                        Text {
                            text: page.everything ? i18n("Pinned") : i18n("All apps")
                            color: page.ink
                            font.family: "Inter"
                            font.pixelSize: 13
                            font.weight: Font.DemiBold
                        }
                        Kirigami.Icon {
                            source: page.everything ? "go-previous" : "go-next"
                            Layout.preferredWidth: 14
                            Layout.preferredHeight: 14
                        }
                    }
                    HoverHandler { id: otherHover; cursorShape: Qt.PointingHandCursor }
                    TapHandler { id: otherTap; onTapped: otherList.go() }
                    Accessible.role: Accessible.Button
                    Accessible.name: page.everything ? i18n("Pinned") : i18n("All apps")
                    Accessible.onPressAction: go()
                }
            }

            Item {
                Layout.fillWidth: true
                Layout.fillHeight: true

                // Pinned apps, then the files you opened last.
                ColumnLayout {
                    anchors.fill: parent
                    visible: !page.searching && !page.everything
                    spacing: Kirigami.Units.largeSpacing * 2

                    GridView {
                        id: pinned
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.max(1, Math.min(2, Math.ceil(count / 6))) * cellHeight
                        clip: true
                        model: root.apps.favoritesModel
                        cellWidth: Math.floor(width / 6)
                        cellHeight: 96
                        keyNavigationEnabled: true
                        currentIndex: -1
                        boundsBehavior: Flickable.StopAtBounds
                        Keys.onReturnPressed: root.launch(model, currentIndex)
                        Keys.onEnterPressed: root.launch(model, currentIndex)
                        Keys.onUpPressed: {
                            if (currentIndex < 6) {
                                search.forceActiveFocus()
                            } else {
                                moveCurrentIndexUp()
                            }
                        }
                        Keys.onDownPressed: {
                            if (currentIndex + 6 >= count && recentFiles.count > 0) {
                                recentFiles.forceActiveFocus()
                                recentFiles.currentIndex = 0
                            } else {
                                moveCurrentIndexDown()
                            }
                        }
                        Keys.onPressed: event => page.typeIntoSearch(event)

                        delegate: AppTile {
                            id: pinnedTile
                            required property int index
                            required property var model
                            width: pinned.cellWidth
                            height: pinned.cellHeight
                            icon: model.decoration
                            name: model.display
                            current: pinned.activeFocus && pinned.currentIndex === index
                            speed: root.speed
                            onActivated: root.launch(pinned.model, index)
                            onMenuRequested: root.showAppMenu(pinnedTile, model.favoriteId || "")
                        }

                        Text {
                            anchors.centerIn: parent
                            width: parent.width - Kirigami.Units.gridUnit * 2
                            visible: pinned.count === 0
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            text: i18n("Nothing pinned yet. Right-click an app in All apps to pin it here.")
                            color: page.ink
                            opacity: 0.6
                            font.family: "Inter"
                            font.italic: true
                            font.pixelSize: 13
                        }
                    }

                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.leftMargin: Kirigami.Units.smallSpacing
                        text: i18n("Recent")
                        color: page.ink
                        font.family: "Fraunces 72pt SuperSoft"
                        font.pixelSize: 20
                    }

                    ListView {
                        id: recentFiles
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        clip: true
                        model: root.recent
                        keyNavigationEnabled: true
                        currentIndex: -1
                        boundsBehavior: Flickable.StopAtBounds
                        Keys.onReturnPressed: root.launch(model, currentIndex)
                        Keys.onEnterPressed: root.launch(model, currentIndex)
                        Keys.onUpPressed: {
                            if (currentIndex <= 0) {
                                pinned.forceActiveFocus()
                                if (pinned.currentIndex < 0) {
                                    pinned.currentIndex = 0
                                }
                            } else {
                                decrementCurrentIndex()
                            }
                        }
                        Keys.onPressed: event => page.typeIntoSearch(event)

                        delegate: AppRow {
                            required property int index
                            required property var model
                            width: recentFiles.width
                            icon: model.decoration
                            name: model.display
                            detail: model.description || ""
                            current: recentFiles.activeFocus && recentFiles.currentIndex === index
                            speed: root.speed
                            onActivated: root.launch(recentFiles.model, index)
                        }

                        Text {
                            anchors.horizontalCenter: parent.horizontalCenter
                            anchors.top: parent.top
                            anchors.topMargin: Kirigami.Units.gridUnit
                            width: parent.width - Kirigami.Units.gridUnit * 2
                            visible: recentFiles.count === 0
                            horizontalAlignment: Text.AlignHCenter
                            wrapMode: Text.Wrap
                            text: i18n("Files you open show up here.")
                            color: page.ink
                            opacity: 0.6
                            font.family: "Inter"
                            font.italic: true
                            font.pixelSize: 13
                        }
                    }
                }

                ListView {
                    id: allApps
                    anchors.fill: parent
                    visible: !page.searching && page.everything
                    clip: true
                    model: root.everyApp
                    keyNavigationEnabled: true
                    currentIndex: -1
                    boundsBehavior: Flickable.StopAtBounds
                    section.property: "group"
                    section.delegate: Text {
                        horizontalAlignment: Text.AlignLeft
                        required property string section
                        width: ListView.view.width
                        leftPadding: 12
                        topPadding: 10
                        bottomPadding: 2
                        text: section
                        color: Kirigami.Theme.textColor
                        opacity: 0.55
                        font.family: "Fraunces 72pt SuperSoft"
                        font.italic: true
                        font.pixelSize: 18
                    }
                    Keys.onReturnPressed: root.launch(model, currentIndex)
                    Keys.onEnterPressed: root.launch(model, currentIndex)
                    Keys.onUpPressed: {
                        if (currentIndex <= 0) {
                            search.forceActiveFocus()
                        } else {
                            decrementCurrentIndex()
                        }
                    }
                    Keys.onPressed: event => page.typeIntoSearch(event)

                    delegate: AppRow {
                        id: appRow
                        required property int index
                        required property var model
                        width: allApps.width
                        icon: model.decoration
                        name: model.display
                        current: allApps.activeFocus && allApps.currentIndex === index
                        speed: root.speed
                        onActivated: root.launch(allApps.model, index)
                        onMenuRequested: root.showAppMenu(appRow, model.favoriteId || "")
                    }
                }

                ListView {
                    id: results
                    anchors.fill: parent
                    visible: page.searching
                    clip: true
                    model: otherMatches
                    keyNavigationEnabled: true
                    boundsBehavior: Flickable.StopAtBounds
                    Keys.onReturnPressed: page.launchMatch(otherMatches, currentIndex)
                    Keys.onEnterPressed: page.launchMatch(otherMatches, currentIndex)
                    Keys.onDownPressed: incrementCurrentIndex()
                    Keys.onUpPressed: {
                        if (currentIndex <= 0) {
                            if (root.everydayResults.length > 0)
                                headerItem.focusAt(root.everydayResults.length - 1)
                            else if (applicationMatches.count > 0)
                                headerItem.focusApp(applicationMatches.count - 1)
                            else search.forceActiveFocus()
                        } else {
                            decrementCurrentIndex()
                        }
                    }
                    Keys.onPressed: event => page.typeIntoSearch(event)

                    header: Column {
                        width: results.width
                        // Suggestions arrive after native results and grow above the scroll origin.
                        onHeightChanged: Qt.callLater(() => {
                            if (search.activeFocus) {
                                results.forceLayout()
                                results.positionViewAtBeginning()
                            }
                        })
                        function focusAt(index) {
                            const item = everydayRepeater.itemAt(index)
                            if (!item) return
                            page.everydayIndex = index
                            page.applicationIndex = -1
                            item.forceActiveFocus(Qt.TabFocusReason)
                            const top = item.mapToItem(results.contentItem, 0, 0).y
                            if (top < results.contentY) results.contentY = top
                            else if (top + item.height > results.contentY + results.height)
                                results.contentY = top + item.height - results.height
                        }
                        function focusApp(index) {
                            const item = applicationRepeater.itemAt(index)
                            if (!item) return
                            page.applicationIndex = index
                            page.everydayIndex = -1
                            item.forceActiveFocus(Qt.TabFocusReason)
                            const top = item.mapToItem(results.contentItem, 0, 0).y
                            if (top < results.contentY) results.contentY = top
                            else if (top + item.height > results.contentY + results.height)
                                results.contentY = top + item.height - results.height
                        }
                        Text {
                            visible: applicationMatches.count > 0
                            text: i18n("Applications")
                            color: page.ink; opacity: 0.65; font.pixelSize: 12
                            topPadding: 6; bottomPadding: 6
                        }
                        Repeater {
                            id: applicationRepeater
                            model: applicationMatches
                            AppRow {
                                id: applicationRow
                                required property var model
                                required property int index
                                objectName: "menuApplicationResult-" + index
                                width: results.width
                                icon: model.decoration; name: model.display
                                detail: model.description || i18n("Application")
                                enabled: !root.finder.querying
                                current: search.activeFocus ? index === 0 : page.applicationIndex === index
                                speed: root.speed
                                activeFocusOnTab: true
                                onActiveFocusChanged: if (activeFocus) {
                                    page.applicationIndex = index
                                    page.everydayIndex = -1
                                }
                                onActivated: page.launchMatch(applicationMatches, index)
                                onMenuRequested: root.showAppMenu(applicationRow, model.favoriteId || "")
                                Keys.onReturnPressed: activated()
                                Keys.onEnterPressed: activated()
                                Keys.onSpacePressed: activated()
                                Keys.onUpPressed: {
                                    if (index > 0) results.headerItem.focusApp(index - 1)
                                    else search.forceActiveFocus(Qt.BacktabFocusReason)
                                }
                                Keys.onDownPressed: {
                                    if (index + 1 < applicationMatches.count) results.headerItem.focusApp(index + 1)
                                    else if (root.everydayResults.length > 0) results.headerItem.focusAt(0)
                                    else page.focusOtherResults()
                                }
                                Keys.onPressed: event => page.typeIntoSearch(event)
                            }
                        }
                        Text {
                            visible: root.everydayResults.length > 0
                            text: i18n("Suggestions")
                            color: page.ink; opacity: 0.65; font.pixelSize: 12
                            topPadding: 6; bottomPadding: 6
                        }
                        Repeater {
                            id: everydayRepeater
                            model: root.everydayResults
                            AppRow {
                                required property var modelData
                                required property int index
                                objectName: "menuSearchResult-" + modelData.id
                                width: results.width
                                icon: modelData.icon; name: modelData.name; detail: modelData.detail
                                current: page.everydayIndex === index && !(search.activeFocus && applicationMatches.count > 0)
                                speed: root.speed
                                activeFocusOnTab: true
                                onActiveFocusChanged: if (activeFocus) {
                                    page.everydayIndex = index
                                    page.applicationIndex = -1
                                }
                                onActivated: root.launchEveryday(modelData)
                                Keys.onReturnPressed: root.launchEveryday(modelData)
                                Keys.onEnterPressed: root.launchEveryday(modelData)
                                Keys.onSpacePressed: root.launchEveryday(modelData)
                                Keys.onUpPressed: {
                                    if (index > 0) results.headerItem.focusAt(index - 1)
                                    else if (applicationMatches.count > 0) results.headerItem.focusApp(applicationMatches.count - 1)
                                    else search.forceActiveFocus(Qt.BacktabFocusReason)
                                }
                                Keys.onDownPressed: {
                                    if (index + 1 < root.everydayResults.length) results.headerItem.focusAt(index + 1)
                                    else page.focusOtherResults()
                                }
                                Keys.onPressed: event => page.typeIntoSearch(event)
                            }
                        }
                        Text {
                            visible: results.count > 0
                            text: i18n("Files, settings and more")
                            color: page.ink; opacity: 0.65; font.pixelSize: 12
                            topPadding: 6; bottomPadding: 6
                        }
                        Text {
                            width: parent.width
                            topPadding: 6
                            bottomPadding: 6
                            visible: root.everydayError !== ""
                            text: root.everydayError
                            color: page.ink; opacity: 0.7; font.pixelSize: 12
                            wrapMode: Text.Wrap
                        }
                    }

                    delegate: AppRow {
                        id: resultRow
                        required property int index
                        required property var model
                        objectName: "menuNativeResult-" + index
                        width: results.width
                        icon: model.decoration
                        name: model.display
                        detail: model.description || ""
                        // Lily on the result Enter opens.
                        enabled: !root.finder.querying
                        current: page.applicationIndex < 0 && (root.everydayResults.length === 0 || page.everydayIndex < 0)
                            && !(search.activeFocus && applicationMatches.count > 0) && results.currentIndex === index
                        speed: root.speed
                        onActivated: page.launchMatch(otherMatches, index)
                        onMenuRequested: root.showAppMenu(resultRow, model.favoriteId || "")
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: parent.top
                        anchors.topMargin: Kirigami.Units.gridUnit * 2
                        width: parent.width - Kirigami.Units.gridUnit * 4
                        visible: results.count === 0 && applicationMatches.count === 0 && root.everydayResults.length === 0
                            && !root.finder.querying && !root.everydayPending && root.everydayError === ""
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: i18n("Nothing here by that name.")
                        color: page.ink
                        opacity: 0.6
                        font.family: "Inter"
                        font.italic: true
                        font.pixelSize: 14
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 1
                color: page.ink
                opacity: 0.1
            }

            // You, then Lock and the power sign.
            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                T.AbstractButton {
                    id: you
                    Layout.fillWidth: true
                    implicitHeight: 40
                    Accessible.name: i18n("Accounts")
                    PlasmaComponents.ToolTip.text: Accessible.name
                    PlasmaComponents.ToolTip.visible: hovered
                    PlasmaComponents.ToolTip.delay: Kirigami.Units.toolTipDelay
                    onClicked: {
                        helper.connectSource("@LIBEXECDIR@/monet-quick open users")
                        root.expanded = false
                    }
                    background: Rectangle {
                        radius: height / 2
                        color: page.ink
                        opacity: you.hovered || you.visualFocus ? 0.07 : 0
                    }
                    contentItem: RowLayout {
                        spacing: 10

                        // Your face, or your initial on a dab of lily, as on the lock screen.
                        Item {
                            id: avatar
                            Layout.leftMargin: 6
                            implicitWidth: 30
                            implicitHeight: 30
                            readonly property bool hasFace: face.status === Image.Ready && GraphicsInfo.api !== GraphicsInfo.Software

                            Rectangle {
                                anchors.fill: parent
                                radius: width / 2
                                visible: !avatar.hasFace
                                gradient: Gradient {
                                    GradientStop { position: 0; color: "#4DB4A0" }
                                    GradientStop { position: 1; color: "#245A50" }
                                }
                                Text {
                                    horizontalAlignment: Text.AlignLeft
                                    anchors.centerIn: parent
                                    anchors.verticalCenterOffset: -1
                                    text: (root.firstName || "M").charAt(0).toUpperCase()
                                    color: "#FBF7EE"
                                    font.family: "Fraunces 72pt SuperSoft"
                                    font.pixelSize: 15
                                }
                            }
                            Image {
                                id: face
                                anchors.fill: parent
                                visible: false
                                asynchronous: true
                                fillMode: Image.PreserveAspectCrop
                                sourceSize.width: 60
                                sourceSize.height: 60
                                source: user.faceIconUrl
                            }
                            Item {
                                id: faceMask
                                anchors.fill: parent
                                visible: false
                                layer.enabled: true
                                Rectangle { anchors.fill: parent; radius: width / 2 }
                            }
                            MultiEffect {
                                anchors.fill: parent
                                source: face
                                visible: avatar.hasFace
                                maskEnabled: true
                                maskSource: faceMask
                                maskThresholdMin: 0.5
                                maskSpreadAtMin: 1
                            }
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            text: user.fullName || user.loginName
                            color: page.ink
                            elide: Text.ElideRight
                            textFormat: Text.PlainText
                            font.family: "Inter"
                            font.pixelSize: 14
                        }
                    }
                }

                PlasmaComponents.ToolButton {
                    icon.name: "system-lock-screen"
                    display: PlasmaComponents.AbstractButton.IconOnly
                    text: i18n("Lock")
                    visible: sessions.canLock
                    PlasmaComponents.ToolTip.text: text
                    PlasmaComponents.ToolTip.visible: hovered
                    PlasmaComponents.ToolTip.delay: Kirigami.Units.toolTipDelay
                    onClicked: {
                        root.expanded = false
                        sessions.lock()
                    }
                }
                PlasmaComponents.ToolButton {
                    icon.name: "system-shutdown"
                    display: PlasmaComponents.AbstractButton.IconOnly
                    text: i18n("Sleep, restart or shut down")
                    PlasmaComponents.ToolTip.text: text
                    PlasmaComponents.ToolTip.visible: hovered
                    PlasmaComponents.ToolTip.delay: Kirigami.Units.toolTipDelay
                    onClicked: {
                        root.expanded = false
                        sessions.requestLogoutPrompt()
                    }
                }
            }
        }
    }
}
