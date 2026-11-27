// Widgets for the selected containment, with preview cards and a searchable catalog.
// Desktop.qml owns the shared model and keeps it alive while an uninstall is pending.
import QtQuick
import "file://@DATADIR@/monet/panel" as EditorUI
import QtQuick.Layouts
import QtQuick.Templates as T
import QtQuick.Controls as C
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.kitemmodels as KItemModels
import org.kde.kwindowsystem
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.plasma.private.shell

Item {
    id: gallery
    objectName: "monetWidgetPicker"
    LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

    property QtObject containment
    property QtObject sidePanel
    property bool draggingWidget: false
    onDraggingWidgetChanged: {
        if (!draggingWidget) {
            // Normal application windows hide during Show Desktop. Bring the
            // picker back after a completed or cancelled drag, ready for the next.
            KWindowSystem.showingDesktop = false
            if (sidePanel?.visible && sidePanel.raise) {
                sidePanel.raise()
                sidePanel.requestActivate()
            }
        }
    }
    onContainmentChanged: if (explorer) explorer.containment = containment
    // "all", a widget's plugin name, or "more" for everyone else's.
    property string shown: "all"

    // While a widget is dragged out, the gallery fades and lets the drop through.
    readonly property bool preventWindowHide: draggingWidget
    readonly property bool outputOnly: draggingWidget
    readonly property QtObject explorer: root?.widgetExplorer ?? null
    readonly property real speed: Kirigami.Units.longDuration / 200
    readonly property bool smoke: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    readonly property color ink: smoke ? "#EFECE6" : "#1C1B19"
    readonly property color dim: smoke ? "#B4AEA5" : "#6B665E"
    // Pebbles of lighter glass on the glass, as in Quick Settings: not a grey wash of ink.
    readonly property color pebble: smoke ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.34)
    readonly property color rim: smoke ? Qt.rgba(1, 1, 1, 0.14) : Qt.rgba(1, 1, 1, 0.7)
    readonly property color hairline: smoke ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(0, 0, 0, 0.08)
    readonly property color lily: smoke ? "#4DB4A0" : "#357F72"
    // Adding to a panel: the bar's widgets; to the desktop: the desktop's.
    readonly property bool forBar: containment !== null && (containment.containmentType === 1 || containment.containmentType === 128)
    readonly property string mineIds: forBar ? "clock|games|menu|quick|sound|system|transfers" : "batteries|calendar|frame|network|notes|nowplaying|placard|played|stacks|storage|system|timer|weather|worldclock"

    readonly property bool notchMatch: !!search.text.trim() && !!containment &&
        [i18nd("monet","Top-center notch"), "notch"].some(label => label.toLocaleLowerCase().includes(search.text.trim().toLocaleLowerCase()))
    property bool notchPending: false
    property string notchResult: ""
    function addNotch() {
        if (notchPending || !containment) return
        notchPending = true
        notchResult = ""
        notchRunner.connectSource("@LIBEXECDIR@/monet-quick panel-notch " + containment.id + " add")
    }
    P5Support.DataSource {
        id: notchRunner
        engine: "executable"
        onNewData: (source,data) => {
            disconnectSource(source)
            gallery.notchPending = false
            let ok = false
            try { ok = JSON.parse(data.stdout).ok === true } catch (_) {}
            gallery.notchResult = ok ? i18nd("monet","Added") : i18nd("monet","Could not read or change the notch on this screen.")
        }
    }
    signal closed()
    signal moveRequested(real x, real y)

    // A compact two-column window over the desktop, with a single column on
    // smaller screens. Its size does not depend on the selected category.
    width: Math.round(Math.min(640, Math.max(240, Screen.width - 64)))
    height: 800
    opacity: draggingWidget ? 0.3 : 1

    function add(pluginName) {
        if (explorer && pluginName) {
            explorer.addApplet(pluginName)
        }
    }

    function remove(pluginName) {
        if (explorer && pluginName) {
            if (pluginName === "org.monet.stacks" && containment) {
                const runner = Qt.createQmlObject('import org.kde.plasma.plasma5support as P5Support\n'
                    + 'P5Support.DataSource { engine: "executable" }', gallery, "restoreIcons")
                runner.newData.connect(source => { runner.disconnectSource(source); runner.destroy(); })
                runner.connectSource("@BINDIR@/monet-files stacks-disable " + containment.id)
            }
            // The model counts instances across the session, including other screens and bars.
            // Apply Remove only to the containment the gallery was opened for.
            const matching = Array.from(containment?.applets || []).filter(applet => applet.pluginName === pluginName)
            for (const applet of matching) {
                applet.internalAction("remove")?.trigger()
            }
        }
    }

    // Enter adds the first widget that matches the search.
    function addFirst() {
        if (notchMatch) { addNotch(); return }
        const view = catalog.visible ? catalog : previews
        const item = view.currentItem
        if (item?.supported) add(item.pluginName)
    }

    // Done returns to the panel editor or ends desktop editing.
    function done() {
        gallery.closed()
    }

    onClosed: {
        // Keep the panel editor open when returning from its widget gallery.
        if (forBar) {
            if (containment?.corona.editMode && !containment.userConfiguring)
                containment.internalAction("configure")?.trigger()
            return
        }
        if (containment && containment.corona) {
            containment.corona.editMode = false
        }
    }

    onVisibleChanged: {
        if (!visible) {
            KWindowSystem.showingDesktop = false
        }
    }

    Component.onCompleted: {
        if (!root) return
        if (!root.widgetExplorer) {
            root.widgetExplorer = explorerComponent.createObject(root)
        }
        root.widgetExplorer.containment = gallery.containment
        search.forceActiveFocus()
    }

    Component.onDestruction: {
        // Widgets marked for removal are taken out a minute later; keep the model till then.
        if (!root || !root.widgetExplorer) return
        if (pendingUninstallTimer.running) {
            root.widgetExplorer.widgetsModel.searchTerm = ""
        } else {
            root.widgetExplorer?.destroy()
            root.widgetExplorer = null
        }
    }

    Component {
        id: explorerComponent
        WidgetExplorer {}
    }

    Connections { target: gallery.explorer; function onShouldClose() { gallery.closed() } }

    KItemModels.KSortFilterProxyModel {
        id: mine
        sourceModel: gallery.explorer ? gallery.explorer.widgetsModel : null
        filterRoleName: "pluginName"
        filterRegularExpression: new RegExp("^org\\.monet\\.(" + gallery.mineIds + ")$")
    }

    KItemModels.KSortFilterProxyModel {
        id: others
        sourceModel: gallery.explorer ? gallery.explorer.widgetsModel : null
        filterRoleName: "pluginName"
        filterRegularExpression: new RegExp("^(?!org\\.monet\\.(" + gallery.mineIds + "|notch)$)")
    }

    KItemModels.KSortFilterProxyModel {
        id: searchable
        sourceModel: gallery.explorer ? gallery.explorer.widgetsModel : null
        filterRoleName: "pluginName"
        filterRegularExpression: /^(?!org\.monet\.notch$)/
    }
    Keys.onEscapePressed: {
        if (search.text !== "") {
            search.text = ""
        } else {
            gallery.done()
        }
    }

    Rectangle {
        anchors.fill: parent
        radius: 12
        color: gallery.smoke ? "#242321" : "#F3F1EC"
        border.width: 1
        border.color: gallery.hairline
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Kirigami.Units.gridUnit
        spacing: Kirigami.Units.largeSpacing * 2

        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing

            Item {
                Layout.fillWidth: true
                Layout.preferredHeight: headerText.implicitHeight
                // This header is the window's move area; widget cards keep
                // their existing drag-and-drop behavior.
                MouseArea {
                    objectName: "widgetGalleryTitleDrag"
                    anchors.fill: parent
                    enabled: !!gallery.sidePanel
                    cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                    property point origin
                    property point windowOrigin
                    onPressed: mouse => {
                        if (gallery.sidePanel.startSystemMove) gallery.sidePanel.startSystemMove()
                        origin = mapToGlobal(mouse.x, mouse.y)
                        windowOrigin = Qt.point(gallery.sidePanel.x, gallery.sidePanel.y)
                    }
                    onPositionChanged: mouse => {
                        if (!pressed) return
                        const point = mapToGlobal(mouse.x, mouse.y)
                        gallery.moveRequested(windowOrigin.x + point.x - origin.x, windowOrigin.y + point.y - origin.y)
                    }
                }
                ColumnLayout {
                    id: headerText
                    anchors.fill: parent
                    spacing: 2
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        text: i18nd("monet", "Widgets")
                        color: gallery.ink
                        font.family: "Fraunces 72pt SuperSoft"
                        font.pixelSize: 30
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        text: gallery.forBar ? i18nd("monet", "Click one to add it to the bar, or drag it there.")
                                             : i18nd("monet", "Click one to add it to your desktop, or drag it where you want it.")
                        color: gallery.dim
                        elide: Text.ElideRight
                        font.family: "Inter"
                        font.pixelSize: 13
                    }
                }
            }
            EditorUI.WindowControls { host: gallery.sidePanel; visible: gallery.sidePanel?.titleHeight === undefined }
            Pill {
                Layout.alignment: Qt.AlignTop
                text: i18nd("monet", "Done")
                ink: gallery.smoke ? "#242321" : "#F3F1EC"
                tint: gallery.ink
                ring: gallery.lily
                speed: gallery.speed
                onClicked: gallery.done()
            }
        }

        C.TextField {
            id: search
            objectName: "widgetSearch"
            Layout.fillWidth: true
            placeholderText: i18nd("monet","Search widgets")
            Accessible.name: placeholderText
            onTextChanged: if (gallery.explorer) gallery.explorer.widgetsModel.searchTerm = text
            Keys.onReturnPressed: gallery.addFirst()
            Keys.onEnterPressed: gallery.addFirst()
        }
        RowLayout {
            Layout.fillWidth: true
            visible: !search.text
            Kind {
                objectName: "monetWidgetCategory"
                title: i18nd("monet","Monet widgets"); sign: "monet"
                chosen: gallery.shown === "all"; ink: gallery.ink; wash: gallery.pebble; ring: gallery.lily; speed: gallery.speed
                onClicked: gallery.shown = "all"
            }
            Kind {
                objectName: "moreWidgetCategory"
                title: i18nd("monet","More widgets"); sign: "view-grid"
                chosen: gallery.shown === "more"; ink: gallery.ink; wash: gallery.pebble; ring: gallery.lily; speed: gallery.speed
                onClicked: gallery.shown = "more"
            }
        }
        C.Button {
            objectName: "galleryAddNotch"
            visible: gallery.notchMatch
            enabled: !gallery.notchPending
            Layout.fillWidth: true
            text: i18nd("monet","Top-center notch"); icon.name: "list-add"
            Accessible.description: i18nd("monet","Open music, timers and quick controls from the top of this screen.")
            onClicked: gallery.addNotch()
        }
        C.Label { visible: gallery.notchMatch && !!gallery.notchResult; text: gallery.notchResult; Layout.fillWidth: true; wrapMode: Text.Wrap }
        Item {
            Layout.fillWidth: true; Layout.fillHeight: true
            GridView {
                id: previews
                anchors.fill: parent; clip: true; visible: !search.text && gallery.shown === "all"
                model: mine
                cellWidth: width / (width >= 435 ? 2 : 1)
                cellHeight: 258
                boundsBehavior: Flickable.StopAtBounds
                C.ScrollBar.vertical: C.ScrollBar {}
                delegate: Card {
                    required property var model
                    width: Math.max(1,previews.cellWidth - 10); height: previews.cellHeight - 10
                    pluginName: model.pluginName; name: model.name
                    description: gallery.forBar && model.pluginName === "org.monet.system"
                        ? i18nd("monet","Show your choice of system readings directly on this bar.") : model.description
                    sign: model.decoration; screenshot: model.screenshot || ""
                    running: gallery.containment?.applets?.filter(a => a.pluginName === pluginName).length || 0
                    supported: model.isSupported !== false
                    smoke: gallery.smoke; forBar: gallery.forBar; ink: gallery.ink; dim: gallery.dim
                    wash: gallery.pebble; ring: gallery.lily; speed: gallery.speed
                    onAdd: gallery.add(pluginName)
                    onTakeAway: gallery.remove(pluginName)
                    onDragging: on => gallery.draggingWidget = on
                }
            }
            ListView {
                id: catalog
                anchors.fill: parent; clip: true
                visible: !!search.text || gallery.shown === "more"
                model: search.text ? searchable : others
                boundsBehavior: Flickable.StopAtBounds
                C.ScrollBar.vertical: C.ScrollBar {}
                delegate: Listed {
                    required property var model
                    width: Math.max(1,catalog.width - 10)
                    pluginName: model.pluginName; name: model.name; description: model.description
                    sign: model.decoration; supported: model.isSupported !== false
                    running: gallery.containment?.applets?.filter(a => a.pluginName === pluginName).length || 0
                    ink: gallery.ink; dim: gallery.dim; wash: gallery.pebble; ring: gallery.lily; speed: gallery.speed
                    onAdd: gallery.add(pluginName)
                    onDragging: on => gallery.draggingWidget = on
                    onTakeAway: gallery.remove(pluginName)
                }
            }
            Text {
                anchors.centerIn: parent
                width: parent.width; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
                visible: !gallery.notchMatch && (catalog.visible ? catalog.count : previews.count) === 0
                text: i18nd("monet","No widget by that name."); color: gallery.dim
            }
        }
    }

    component Pill: T.AbstractButton {
        id: pill
        property color ink
        property color tint
        property color ring
        property real speed: 1
        implicitWidth: label.implicitWidth + 32
        implicitHeight: 34
        activeFocusOnTab: true
        Accessible.name: text
        Keys.onEnterPressed: clicked()
        Keys.onReturnPressed: clicked()
        scale: down ? 0.95 : hovered ? 1.04 : 1
        Behavior on scale { NumberAnimation { duration: Math.round(160 * pill.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
        background: Rectangle {
            radius: height / 2
            color: pill.tint
            border.width: pill.visualFocus ? 2 : 0
            border.color: pill.ring
        }
        contentItem: Text {
            id: label
            text: pill.text
            color: pill.ink
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            font.family: "Inter"
            font.pixelSize: 14
            font.weight: Font.DemiBold
        }
    }

    // An entry down the left: the widget's icon and its name. (Its picture is
    // in its card: at this size the picture would be specks.)
    component Kind: T.AbstractButton {
        id: kind
        property string title
        property var sign
        property bool chosen: false
        property color ink
        property color wash
        property color ring
        property real speed: 1
        Layout.fillWidth: true
        implicitHeight: 40
        activeFocusOnTab: true
        Accessible.name: title
        Keys.onEnterPressed: clicked()
        Keys.onReturnPressed: clicked()
        background: Rectangle {
            radius: 12
            color: kind.chosen ? kind.ring : kind.ink
            opacity: kind.chosen ? 0.16 : kind.hovered ? 0.07 : 0
            border.width: kind.visualFocus ? 2 : 0
            border.color: kind.ring
            Behavior on opacity { NumberAnimation { duration: Math.round(140 * kind.speed) } }
        }
        contentItem: RowLayout {
            spacing: 10
            Kirigami.Icon {
                Layout.leftMargin: 6
                Layout.preferredWidth: 24
                Layout.preferredHeight: 24
                source: kind.sign
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: kind.title
                color: kind.ink
                elide: Text.ElideRight
                textFormat: Text.PlainText
                font.family: "Inter"
                font.pixelSize: 14
                font.weight: kind.chosen ? Font.DemiBold : Font.Normal
            }
        }
    }

    // A widget's card: its name and what it does, a picture of it, and Add (or
    // Remove, when it's out already). The whole card adds it, or drags it out.
    component Card: T.AbstractButton {
        id: card
        objectName: "widgetCard-" + pluginName
        property string pluginName
        property string name
        property string description
        property var sign
        property string screenshot
        property int running: 0
        property bool supported: true

        property bool smoke: false
        property bool forBar: false
        property color ink
        property color dim
        property color wash
        property color ring
        property real speed: 1

        signal add()
        signal takeAway()
        signal dragging(bool on)

        implicitHeight: column.implicitHeight + 32
        enabled: supported
        opacity: supported ? 1 : 0.5
        activeFocusOnTab: true
        Accessible.name: i18ndc("monet", "%1 is a widget's name", "Add %1", name)
        Accessible.description: description
        onClicked: add()
        Keys.onReturnPressed: add()
        Keys.onEnterPressed: add()

        background: Rectangle {
            radius: 18
            color: card.wash
            border.width: card.visualFocus ? 2 : 1
            // The light caught in its edge, brighter under the pointer.
            border.color: card.visualFocus ? card.ring : Qt.rgba(1, 1, 1, card.wash.a > 0.2 ? (card.hovered ? 0.95 : 0.7) : (card.hovered ? 0.24 : 0.14))
            Behavior on border.color { ColorAnimation { duration: Math.round(140 * card.speed) } }
        }

        // Dragged out onto the desktop or a panel, as in KDE's own. The handler sits on
        // the card itself: in a child item over it, it would keep clicks from the card.
        Drag.dragType: Drag.Automatic
        Drag.supportedActions: Qt.MoveAction | Qt.LinkAction
        Drag.mimeData: ({ "text/x-plasmoidservicename": card.pluginName })
        Drag.onDragStarted: {
            KWindowSystem.showingDesktop = true
            card.dragging(true)
        }
        Drag.onDragFinished: card.dragging(false)

        DragHandler {
            id: dragHandler
            target: null
            enabled: card.supported
            onActiveChanged: {
                if (active) {
                    preview.grabToImage(result => {
                        if (!dragHandler.active) {
                            return
                        }
                        card.Drag.imageSource = result.url
                        card.Drag.active = true
                    }, Qt.size(preview.width, preview.height))
                } else {
                    card.Drag.active = false
                    card.Drag.imageSource = ""
                }
            }
        }

        contentItem: ColumnLayout {
            id: column
            spacing: 6

            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                Layout.leftMargin: 16
                Layout.rightMargin: 16
                Layout.topMargin: 14
                text: card.name
                color: card.ink
                elide: Text.ElideRight
                textFormat: Text.PlainText
                font.family: "Inter"
                font.pixelSize: 15
                font.weight: Font.DemiBold
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                Layout.leftMargin: 16
                Layout.rightMargin: 16
                text: card.description
                color: card.dim
                wrapMode: Text.Wrap
                maximumLineCount: 2
                elide: Text.ElideRight
                textFormat: Text.PlainText
                font.family: "Inter"
                font.pixelSize: 12
            }

            // The widget as it looks, in mist or in smoke.
            Item {
                id: preview
                Layout.fillWidth: true
                Layout.leftMargin: 12
                Layout.rightMargin: 12
                Layout.topMargin: 6
                Layout.fillHeight: true
                Layout.minimumHeight: 24
                implicitHeight: 90
                scale: card.down ? 0.97 : 1
                Behavior on scale { NumberAnimation { duration: Math.round(160 * card.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }

                Image {
                    id: look
                    anchors.fill: parent
                    visible: status === Image.Ready
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    sourceSize.width: Math.ceil(Math.max(1,card.width) * Screen.devicePixelRatio)
                    source: card.screenshot === "" ? ""
                        : card.smoke ? card.screenshot.replace(/screenshot\.png$/, "screenshot-smoke.png") : card.screenshot
                    onStatusChanged: {
                        if (status === Image.Error && source != card.screenshot) {
                            source = card.screenshot
                        }
                    }
                }
                Kirigami.Icon {
                    anchors.centerIn: parent
                    visible: !look.visible
                    width: 64
                    height: 64
                    source: card.sign
                }
            }

            Text {
                Layout.fillWidth: true
                Layout.leftMargin: 16
                Layout.rightMargin: 12
                horizontalAlignment: Text.AlignLeft
                visible: card.running > 0
                text: card.forBar ? i18nd("monet", "In your bar") : i18ndp("monet", "On your desktop", "%1 on your desktop", card.running)
                wrapMode: Text.Wrap
                color: card.ring
                font.family: "Inter"
                font.pixelSize: 12
            }

            Flow {
                Layout.fillWidth: true
                Layout.leftMargin: 16
                Layout.rightMargin: 12
                Layout.bottomMargin: 2
                Layout.preferredHeight: childrenRect.height
                layoutDirection: Qt.RightToLeft
                spacing: Kirigami.Units.smallSpacing

                T.AbstractButton {
                    id: addButton
                    text: i18nd("monet", "Add")
                    width: Math.min(parent.width, addLabel.implicitWidth + 30)
                    height: 30
                    Accessible.name: i18ndc("monet", "%1 is a widget's name", "Add %1", card.name)
                    onClicked: card.add()
                    background: Rectangle {
                        radius: height / 2
                        color: card.ring
                        opacity: addButton.hovered ? 1 : 0.9
                    }
                    contentItem: Text {
                        id: addLabel
                        text: "+ " + addButton.text
                        color: "#FBF7EE"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        font.family: "Inter"
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                }
                T.AbstractButton {
                    id: takeAwayButton
                    visible: card.running > 0
                    // Every copy goes: say so when there's more than one.
                    text: card.running > 1 ? i18nd("monet", "Remove all") : i18nd("monet", "Remove")
                    width: Math.min(parent.width, takeAwayLabel.implicitWidth + 24)
                    height: 30
                    Accessible.name: i18ndc("monet", "%1 is a widget's name", "Remove %1", card.name)
                    onClicked: card.takeAway()
                    background: Rectangle {
                        radius: height / 2
                        color: card.ink
                        opacity: takeAwayButton.hovered ? 0.08 : 0
                    }
                    contentItem: Text {
                        id: takeAwayLabel
                        text: takeAwayButton.text
                        color: card.dim
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        font.family: "Inter"
                        font.pixelSize: 13
                    }
                }
            }
        }
    }

    // One of everyone else's widgets: its sign, its name and what it does, and Add.
    component Listed: T.AbstractButton {
        id: row
        objectName: "widgetRow-" + pluginName
        property string pluginName
        property string name
        property string description
        property var sign
        property int running: 0
        property bool supported: true
        property color ink
        property color dim
        property color wash
        property color ring
        property real speed: 1

        signal add()
        signal takeAway()
        signal dragging(bool on)

        implicitHeight: 56
        enabled: supported
        opacity: supported ? 1 : 0.5
        activeFocusOnTab: true
        Accessible.name: i18ndc("monet", "%1 is a widget's name", "Add %1", name)
        Accessible.description: description
        onClicked: add()
        Keys.onReturnPressed: add()
        Keys.onEnterPressed: add()

        background: Rectangle {
            radius: 12
            color: row.visualFocus ? row.ring : row.ink
            opacity: row.visualFocus ? 0.16 : row.hovered ? 0.07 : 0
        }

        Drag.dragType: Drag.Automatic
        Drag.supportedActions: Qt.MoveAction | Qt.LinkAction
        Drag.mimeData: ({ "text/x-plasmoidservicename": row.pluginName })
        Drag.onDragStarted: {
            KWindowSystem.showingDesktop = true
            row.dragging(true)
        }
        Drag.onDragFinished: row.dragging(false)

        DragHandler {
            id: rowDrag
            target: null
            enabled: row.supported
            onActiveChanged: {
                if (active) {
                    rowSign.grabToImage(result => {
                        if (!rowDrag.active) {
                            return
                        }
                        row.Drag.imageSource = result.url
                        row.Drag.active = true
                    }, Qt.size(48, 48))
                } else {
                    row.Drag.active = false
                    row.Drag.imageSource = ""
                }
            }
        }

        contentItem: RowLayout {
            spacing: 12
            Kirigami.Icon {
                id: rowSign
                Layout.leftMargin: 10
                implicitWidth: 32
                implicitHeight: 32
                source: row.sign
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: row.name
                    color: row.ink
                    elide: Text.ElideRight
                    textFormat: Text.PlainText
                    font.family: "Inter"
                    font.pixelSize: 14
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: row.description
                    color: row.dim
                    elide: Text.ElideRight
                    textFormat: Text.PlainText
                    font.family: "Inter"
                    font.pixelSize: 12
                }
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.rightMargin: 12
                text: row.running > 0 ? i18nd("monet", "Added") : i18nd("monet", "+ Add")
                color: row.ring
                font.family: "Inter"
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }
        }
    }
}
