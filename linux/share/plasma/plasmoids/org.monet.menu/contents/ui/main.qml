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
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasma5support as P5Support
import org.kde.plasma.plasmoid
import org.kde.plasma.private.kicker as Kicker
import org.kde.plasma.private.sessions

PlasmoidItem {
    id: root

    Plasmoid.icon: "monet"
    toolTipMainText: i18n("Menu")
    toolTipSubText: i18n("Your apps, and a search for everything on this PC")
    preferredRepresentation: compactRepresentation

    // Animations follow the desktop's speed, and stop when it's set to instant.
    readonly property real speed: Kirigami.Units.longDuration / 200
    // Every app from A to Z, once KDE's model has read them.
    property var everyApp: null
    readonly property string firstName: (user.fullName || user.loginName || "").trim().split(" ")[0]

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
        onNewData: source => disconnectSource(source)
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
        Layout.preferredWidth: Kirigami.Units.gridUnit * 30
        Layout.preferredHeight: Kirigami.Units.gridUnit * 33
        Layout.minimumWidth: Kirigami.Units.gridUnit * 24
        Layout.minimumHeight: Kirigami.Units.gridUnit * 26
        collapseMarginsHint: true
        focus: true

        // Pinned apps and recent files, or all apps from A to Z; search results while there's a search.
        property bool everything: false
        property bool launchWhenFound: false
        readonly property bool searching: search.text.trim() !== ""
        readonly property var found: root.finder.count > 0 ? root.finder.modelForRow(0) : null
        readonly property Item shownView: searching ? results : everything ? allApps : pinned
        readonly property color ink: Kirigami.Theme.textColor

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
            if (found && found.count > 0) {
                root.launch(found, Math.max(results.currentIndex, 0))
            } else if (root.finder.querying) {
                launchWhenFound = true
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
            function onExpandedChanged() {
                if (root.expanded) {
                    page.reset()
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
                Layout.fillWidth: true
                implicitHeight: 42
                leftPadding: 44
                rightPadding: 16
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
                    root.finder.query = text
                    results.currentIndex = 0
                }
                Keys.onReturnPressed: page.launchFirst()
                Keys.onEnterPressed: page.launchFirst()
                Keys.onDownPressed: {
                    page.shownView.forceActiveFocus()
                    if (page.shownView.currentIndex < 0) {
                        page.shownView.currentIndex = 0
                    }
                }
                background: Rectangle {
                    radius: height / 2
                    color: Qt.rgba(page.ink.r, page.ink.g, page.ink.b, 0.06)
                    border.width: search.activeFocus ? 2 : 1
                    border.color: search.activeFocus ? Kirigami.Theme.highlightColor : Qt.rgba(page.ink.r, page.ink.g, page.ink.b, 0.1)
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
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.smallSpacing
                    text: page.everything ? i18n("All apps") : i18n("Pinned")
                    color: page.ink
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: 20
                }
                PlasmaComponents.ToolButton {
                    text: page.everything ? i18n("Pinned") : i18n("All apps")
                    icon.name: page.everything ? "go-previous" : "go-next"
                    LayoutMirroring.enabled: !page.everything
                    onClicked: {
                        page.everything = !page.everything
                        page.shownView.currentIndex = -1
                    }
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
                    model: page.found
                    keyNavigationEnabled: true
                    boundsBehavior: Flickable.StopAtBounds
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
                        id: resultRow
                        required property int index
                        required property var model
                        width: results.width
                        icon: model.decoration
                        name: model.display
                        detail: model.description || ""
                        // Lily on the result Enter opens.
                        current: results.currentIndex === index
                        speed: root.speed
                        onActivated: root.launch(results.model, index)
                        onMenuRequested: root.showAppMenu(resultRow, model.favoriteId || "")
                    }

                    Text {
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: parent.top
                        anchors.topMargin: Kirigami.Units.gridUnit * 2
                        width: parent.width - Kirigami.Units.gridUnit * 4
                        visible: results.count === 0 && !root.finder.querying
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
