/*
 * Monet's widget gallery, on the glass down the side of the screen, with the
 * desktop beside it: search and Monet's widgets down the left, each with a
 * small picture; big cards with a picture of each widget, Add, and Remove for
 * the ones already out; every other widget under More widgets. Click a card
 * to add it, or drag it where you want it. Done ends the editing.
 *
 * Opened by WidgetExplorer.qml in Plasma's desktop shell; Desktop.qml around
 * it keeps the gallery's model (root.widgetExplorer) and pendingUninstallTimer.
 */
import QtQuick
import QtQuick.Layouts
import QtQuick.Templates as T
import QtQuick.Window
import org.kde.kirigami as Kirigami
import org.kde.kitemmodels as KItemModels
import org.kde.kwindowsystem
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.private.shell

Item {
    id: gallery

    property QtObject containment
    property PlasmaCore.Dialog sidePanel
    property bool draggingWidget: false
    // "all", a widget's plugin name, or "more" for everyone else's.
    property string shown: "all"

    // While a widget is dragged out, the gallery fades and lets the drop through.
    readonly property bool preventWindowHide: draggingWidget
    readonly property bool outputOnly: draggingWidget
    readonly property QtObject explorer: root.widgetExplorer
    readonly property real speed: Kirigami.Units.longDuration / 200
    readonly property bool smoke: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    readonly property color ink: smoke ? "#EFECE6" : "#1C1B19"
    readonly property color dim: smoke ? "#B4AEA5" : "#6B665E"
    readonly property color pebble: smoke ? Qt.rgba(1, 1, 1, 0.07) : Qt.rgba(0.11, 0.106, 0.098, 0.05)
    readonly property color hairline: smoke ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(0, 0, 0, 0.08)
    readonly property color lily: smoke ? "#4DB4A0" : "#357F72"
    // Adding to a panel: the bar's widgets; to the desktop: the desktop's.
    readonly property bool forBar: containment !== null && (containment.containmentType === 1 || containment.containmentType === 128)
    readonly property string mineIds: forBar ? "clock|games|menu|quick" : "calendar|frame|notes|nowplaying|placard|weather"

    signal closed()

    // Wide enough for the list and two big cards; the desktop shrinks beside it.
    width: Math.round(Math.min(Kirigami.Units.gridUnit * 46, Math.max(Kirigami.Units.gridUnit * 32, Screen.width * 0.55)))
    height: 800
    opacity: draggingWidget ? 0.3 : 1

    function add(pluginName) {
        if (explorer && pluginName) {
            explorer.addApplet(pluginName)
        }
    }

    function remove(pluginName) {
        if (explorer && pluginName) {
            explorer.removeAllInstances(pluginName)
        }
    }

    // Enter adds the first widget that matches the search.
    function addFirst() {
        const cards = shown === "more" ? moreRows : mineCards
        for (let i = 0; i < cards.count; ++i) {
            const card = cards.itemAt(i)
            if (card && card.visible) {
                add(card.pluginName)
                return
            }
        }
    }

    // Done: the gallery closes and the desktop comes back to full size.
    function done() {
        if (containment && containment.corona) {
            containment.corona.editMode = false
        }
        gallery.closed()
    }

    onClosed: {
        // Opened from a panel: back to the panel's settings, as KDE's gallery does.
        if (explorer && explorer.containment && explorer.containment.containmentType == 1
                && !explorer.containment.userConfiguring) {
            explorer.containment.internalAction("configure").trigger()
        }
    }

    onVisibleChanged: {
        if (!visible) {
            KWindowSystem.showingDesktop = false
        }
    }

    Component.onCompleted: {
        if (!root.widgetExplorer) {
            root.widgetExplorer = explorerComponent.createObject(root)
        }
        root.widgetExplorer.containment = gallery.containment
        search.forceActiveFocus()
    }

    Component.onDestruction: {
        // Widgets marked for removal are taken out a minute later; keep the model till then.
        if (pendingUninstallTimer.running) {
            root.widgetExplorer.widgetsModel.searchTerm = ""
        } else {
            root.widgetExplorer.destroy()
            root.widgetExplorer = null
        }
    }

    Component {
        id: explorerComponent
        WidgetExplorer {
            onShouldClose: gallery.closed()
        }
    }

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
        filterRegularExpression: new RegExp("^(?!org\\.monet\\.(" + gallery.mineIds + ")$)")
    }

    Keys.onEscapePressed: {
        if (search.text !== "") {
            search.text = ""
        } else {
            gallery.done()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: Kirigami.Units.gridUnit
        spacing: Kirigami.Units.largeSpacing * 2

        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing

            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    text: i18n("Widgets")
                    color: gallery.ink
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: 30
                }
                Text {
                    Layout.fillWidth: true
                    text: gallery.forBar ? i18n("Click one to add it to the bar, or drag it there.")
                                         : i18n("Click one to add it to your desktop, or drag it where you want it.")
                    color: gallery.dim
                    elide: Text.ElideRight
                    font.family: "Inter"
                    font.pixelSize: 13
                }
            }
            Pill {
                Layout.alignment: Qt.AlignTop
                text: i18n("Done")
                ink: gallery.smoke ? "#242321" : "#F3F1EC"
                tint: gallery.ink
                ring: gallery.lily
                speed: gallery.speed
                onClicked: gallery.done()
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: Kirigami.Units.gridUnit

            // Search, then the widgets one by one, then everyone else's.
            ColumnLayout {
                Layout.preferredWidth: Kirigami.Units.gridUnit * 12
                Layout.maximumWidth: Kirigami.Units.gridUnit * 12
                Layout.fillHeight: true
                spacing: Kirigami.Units.smallSpacing

                T.TextField {
                    id: search
                    Layout.fillWidth: true
                    Layout.bottomMargin: Kirigami.Units.largeSpacing
                    implicitHeight: 38
                    leftPadding: 38
                    rightPadding: 12
                    verticalAlignment: TextInput.AlignVCenter
                    color: gallery.ink
                    placeholderText: i18n("Search")
                    placeholderTextColor: Qt.rgba(gallery.ink.r, gallery.ink.g, gallery.ink.b, 0.5)
                    selectionColor: Kirigami.Theme.highlightColor
                    selectedTextColor: Kirigami.Theme.highlightedTextColor
                    font.family: "Inter"
                    font.pixelSize: 14
                    Accessible.name: i18n("Search widgets")
                    onTextChanged: {
                        if (gallery.explorer) {
                            gallery.explorer.widgetsModel.searchTerm = text
                        }
                        if (text !== "" && gallery.shown !== "more") {
                            gallery.shown = "all"
                        }
                    }
                    Keys.onReturnPressed: gallery.addFirst()
                    Keys.onEnterPressed: gallery.addFirst()
                    background: Rectangle {
                        radius: height / 2
                        color: Qt.rgba(gallery.ink.r, gallery.ink.g, gallery.ink.b, 0.06)
                        border.width: search.activeFocus ? 2 : 1
                        border.color: search.activeFocus ? gallery.lily : gallery.hairline
                        Kirigami.Icon {
                            anchors.left: parent.left
                            anchors.leftMargin: 12
                            anchors.verticalCenter: parent.verticalCenter
                            width: 17
                            height: 17
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

                Kind {
                    title: i18n("All widgets")
                    sign: gallery.forBar ? "monet" : "preferences-desktop-wallpaper"
                    chosen: gallery.shown === "all"
                    ink: gallery.ink
                    wash: gallery.pebble
                    ring: gallery.lily
                    speed: gallery.speed
                    onClicked: gallery.shown = "all"
                }

                Repeater {
                    model: mine
                    delegate: Kind {
                        required property var model
                        Layout.fillWidth: true
                        title: model.name
                        // The bar's widgets are small in their pictures: their signs read better here.
                        picture: gallery.forBar ? "" : (model.screenshot || "")
                        sign: model.decoration
                        smoke: gallery.smoke
                        chosen: gallery.shown === model.pluginName
                        ink: gallery.ink
                        wash: gallery.pebble
                        ring: gallery.lily
                        speed: gallery.speed
                        onClicked: gallery.shown = model.pluginName
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.topMargin: Kirigami.Units.smallSpacing
                    Layout.bottomMargin: Kirigami.Units.smallSpacing
                    implicitHeight: 1
                    color: gallery.hairline
                    visible: others.count > 0
                }

                Kind {
                    visible: others.count > 0
                    title: i18n("More widgets")
                    sign: "list-add"
                    chosen: gallery.shown === "more"
                    ink: gallery.ink
                    wash: gallery.pebble
                    ring: gallery.lily
                    speed: gallery.speed
                    onClicked: gallery.shown = "more"
                }

                Item {
                    Layout.fillHeight: true
                }
            }

            Flickable {
                id: scroller
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                contentWidth: width
                contentHeight: shelf.implicitHeight
                boundsBehavior: Flickable.StopAtBounds

                ColumnLayout {
                    id: shelf
                    width: scroller.width
                    spacing: Kirigami.Units.largeSpacing

                    // Monet's widgets as big cards: two side by side, or the chosen one alone.
                    GridLayout {
                        Layout.fillWidth: true
                        visible: gallery.shown !== "more"
                        columns: gallery.shown === "all" ? 2 : 1
                        columnSpacing: Kirigami.Units.largeSpacing
                        rowSpacing: Kirigami.Units.largeSpacing

                        Repeater {
                            id: mineCards
                            model: mine
                            delegate: Card {
                                required property var model
                                Layout.fillWidth: true
                                Layout.preferredWidth: 1
                                visible: gallery.shown === "all" || gallery.shown === model.pluginName
                                big: gallery.shown !== "all"
                                pluginName: model.pluginName
                                name: model.name
                                description: model.description
                                sign: model.decoration
                                screenshot: model.screenshot || ""
                                running: model.running || 0
                                supported: model.isSupported !== false
                                smoke: gallery.smoke
                                forBar: gallery.forBar
                                ink: gallery.ink
                                dim: gallery.dim
                                wash: gallery.pebble
                                ring: gallery.lily
                                speed: gallery.speed
                                onAdd: gallery.add(pluginName)
                                onTakeAway: gallery.remove(pluginName)
                                onDragging: on => gallery.draggingWidget = on
                            }
                        }
                    }

                    // Everyone else's, as a plain list: no pictures to show for them.
                    Repeater {
                        id: moreRows
                        model: gallery.shown === "more" ? others : null
                        delegate: Listed {
                            required property var model
                            Layout.fillWidth: true
                            pluginName: model.pluginName
                            name: model.name
                            description: model.description
                            sign: model.decoration
                            running: model.running || 0
                            supported: model.isSupported !== false
                            ink: gallery.ink
                            dim: gallery.dim
                            wash: gallery.pebble
                            ring: gallery.lily
                            speed: gallery.speed
                            onAdd: gallery.add(pluginName)
                            onDragging: on => gallery.draggingWidget = on
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        Layout.topMargin: Kirigami.Units.gridUnit * 2
                        visible: gallery.shown === "more" ? others.count === 0 : mine.count === 0
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: i18n("No widget by that name.")
                        color: gallery.dim
                        font.family: "Inter"
                        font.italic: true
                        font.pixelSize: 14
                    }
                }
            }
        }
    }

    // A pill: Done in ink, or Add on a pebble of glass.
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

    // An entry down the left: the widget's small picture (or a sign) and its name.
    component Kind: T.AbstractButton {
        id: kind
        property string title
        property string picture
        property var sign
        property bool smoke: false
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
            Item {
                Layout.leftMargin: 6
                implicitWidth: 34
                implicitHeight: 24
                Image {
                    id: thumb
                    anchors.fill: parent
                    visible: status === Image.Ready
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    mipmap: true
                    source: kind.picture === "" ? ""
                        : kind.smoke ? kind.picture.replace(/screenshot\.png$/, "screenshot-smoke.png") : kind.picture
                    onStatusChanged: {
                        if (status === Image.Error && source != kind.picture) {
                            source = kind.picture
                        }
                    }
                }
                Kirigami.Icon {
                    anchors.centerIn: parent
                    width: 22
                    height: 22
                    visible: !thumb.visible
                    source: kind.sign
                }
            }
            Text {
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
        property string pluginName
        property string name
        property string description
        property var sign
        property string screenshot
        property int running: 0
        property bool supported: true
        property bool big: false
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
        Accessible.name: i18nc("%1 is a widget's name", "Add %1", name)
        Accessible.description: description
        onClicked: add()
        Keys.onReturnPressed: add()
        Keys.onEnterPressed: add()

        background: Rectangle {
            radius: 18
            color: card.wash
            border.width: card.visualFocus ? 2 : 1
            border.color: card.visualFocus ? card.ring : Qt.rgba(card.ink.r, card.ink.g, card.ink.b, card.hovered ? 0.16 : 0.07)
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
                implicitHeight: card.big ? 240 : 150
                scale: card.down ? 0.97 : 1
                Behavior on scale { NumberAnimation { duration: Math.round(160 * card.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }

                Image {
                    id: look
                    anchors.fill: parent
                    visible: status === Image.Ready
                    fillMode: Image.PreserveAspectFit
                    asynchronous: true
                    mipmap: true
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

            RowLayout {
                Layout.fillWidth: true
                Layout.leftMargin: 16
                Layout.rightMargin: 12
                Layout.bottomMargin: 2
                spacing: Kirigami.Units.smallSpacing

                Text {
                    visible: card.running > 0
                    text: card.forBar ? i18n("In your bar") : i18n("On your desktop")
                    color: card.ring
                    font.family: "Inter"
                    font.pixelSize: 12
                }
                Item {
                    Layout.fillWidth: true
                }
                T.AbstractButton {
                    id: takeAwayButton
                    visible: card.running > 0
                    text: i18n("Remove")
                    implicitWidth: takeAwayLabel.implicitWidth + 24
                    implicitHeight: 30
                    Accessible.name: i18nc("%1 is a widget's name", "Remove %1", card.name)
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
                        font.family: "Inter"
                        font.pixelSize: 13
                    }
                }
                T.AbstractButton {
                    id: addButton
                    text: i18n("Add")
                    implicitWidth: addLabel.implicitWidth + 30
                    implicitHeight: 30
                    Accessible.name: i18nc("%1 is a widget's name", "Add %1", card.name)
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
                        font.family: "Inter"
                        font.pixelSize: 13
                        font.weight: Font.DemiBold
                    }
                }
            }
        }
    }

    // One of everyone else's widgets: its sign, its name and what it does, and Add.
    component Listed: T.AbstractButton {
        id: row
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
        signal dragging(bool on)

        implicitHeight: 56
        enabled: supported
        opacity: supported ? 1 : 0.5
        activeFocusOnTab: true
        Accessible.name: i18nc("%1 is a widget's name", "Add %1", name)
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
                    Layout.fillWidth: true
                    text: row.name
                    color: row.ink
                    elide: Text.ElideRight
                    textFormat: Text.PlainText
                    font.family: "Inter"
                    font.pixelSize: 14
                }
                Text {
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
                Layout.rightMargin: 12
                text: row.running > 0 ? i18n("Added") : i18n("+ Add")
                color: row.ring
                font.family: "Inter"
                font.pixelSize: 13
                font.weight: Font.DemiBold
            }
        }
    }
}
