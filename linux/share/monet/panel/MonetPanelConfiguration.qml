// Edit the existing panel in place, so its widgets and pins keep their identities.
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C
import QtQuick.Templates as T
import org.kde.kirigami as Kirigami
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.shell
import org.kde.plasma.plasma5support as P5Support

Item {
    id: editor
    objectName: "monetPanelEditor"
    required property QtObject panelConfiguration
    property url advancedPage: Qt.resolvedUrl("KdePanelConfiguration.qml")
    property Item panelRuler: advanced.item ? advanced.item.panelRuler : null
    signal closeContextMenu
    onCloseContextMenu: if (advanced.item) advanced.item.closeContextMenu()

    readonly property bool vertical: panel.location === PlasmaCore.Types.LeftEdge || panel.location === PlasmaCore.Types.RightEdge
    readonly property color accent: Kirigami.Theme.highlightColor
    readonly property int minimumSize: Math.max(20, panel.minThickness)
    readonly property int maximumSize: Math.max(minimumSize, Math.min(120, Math.floor(
        Math.min(screenGeometry.width, screenGeometry.height) / 3)))
    readonly property rect screenGeometry: panel.screenToFollow ? panel.screenToFollow.geometry : Qt.rect(0, 0, Screen.width, Screen.height)
    // Leave room for the bar at its largest selectable size, floating margins and
    // Plasma's frame. The viewport stays the same size while resizing the bar.
    readonly property int clearance: Math.max(maximumSize, panel.thickness) + 56
    implicitWidth: Math.min(showAdvanced ? 640 : 460, Math.max(180, screenGeometry.width - clearance))
    implicitHeight: Math.min(580, Math.max(200, screenGeometry.height - clearance))
    clip: true
    LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

    property int page: 0
    property bool showAdvanced: false
    property int draftSize: panel.thickness
    property string icons: ""
    property var iconActions: ({})
    property bool iconsAvailable: false
    property string barLayout: ""
    property bool layoutAvailable: false
    property string notchMode: ""
    property bool notchBusy: false
    property var notchOptions: ({})
    property var notchTabs: []
    property var companionSettings: ({})
    readonly property var tabTitles: ({music:i18nd("monet", "Music"), activity:i18nd("monet", "Activity"),
        time:i18nd("monet", "Time"), calendar:i18nd("monet", "Calendar"), notes:i18nd("monet", "Notes"),
        camera:i18nd("monet", "Camera"), clipboard:i18nd("monet", "Clipboard")})
    ListModel {
        id: tabRows
        ListElement { key: "music" }
        ListElement { key: "activity" }
        ListElement { key: "time" }
        ListElement { key: "calendar" }
        ListElement { key: "notes" }
        ListElement { key: "camera" }
        ListElement { key: "clipboard" }
    }
    onNotchTabsChanged: {
        const order = notchTabs.concat(Object.keys(tabTitles).filter(key => !notchTabs.includes(key)))
        order.forEach((key, index) => {
            for (let i = index; i < tabRows.count; ++i) {
                if (tabRows.get(i).key !== key) continue
                if (i !== index) tabRows.move(i, index, 1)
                break
            }
        })
    }
    property bool layoutBusy: false
    property bool busy: false
    property string problem: ""
    property bool surfaceResizePending: false

    function refreshPlacement() {
        // Plasma computes the popup position from the panel's current geometry.
        // Ask it to recompute after the layer-shell resize and floating animation.
        if (configDialog.visible && configDialog.queuePositionUpdate) {
            configDialog.queuePositionUpdate()
            configDialog.requestUpdate()
        }
    }
    Timer {
        id: settlePlacement
        interval: Kirigami.Units.longDuration + 40
        onTriggered: {
            if (editor.surfaceResizePending) {
                editor.surfaceResizePending = false
                editor.syncPanelSurface()
            }
            editor.refreshPlacement()
        }
    }
    function syncPanelSurface() {
        // PanelView sends a desired size to layer-shell. A live surface can keep
        // its old buffer size until it is resized locally or its edge changes.
        // Match PanelView's size calculation for both presets, including the
        // floating insets. Leave KDE's custom-length ruler in charge of length.
        const view = panel.contentItem?.children.find(item => item.fixedTopFloatingPadding !== undefined)
        if (!view) return
        const horizontalPadding = view.fixedLeftFloatingPadding + view.fixedRightFloatingPadding
        const verticalPadding = view.fixedTopFloatingPadding + view.fixedBottomFloatingPadding
        const thickness = panel.thickness + (vertical ? horizontalPadding : verticalPadding)
        const available = vertical ? screenGeometry.height : screenGeometry.width
        const natural = panel.length + (vertical ? verticalPadding : horizontalPadding)
        let length = vertical ? panel.height : panel.width
        if (panel.lengthMode === Panel.FillAvailable) length = available
        else if (panel.lengthMode === Panel.FitContent) length = Math.min(available, Math.max(thickness, natural))
        if (length <= 0 || thickness <= 0) return
        const width = vertical ? thickness : length
        const height = vertical ? length : thickness
        if (panel.width !== width || panel.height !== height) {
            panel.setGeometry(panel.x, panel.y, width, height)
        }
    }
    function schedulePlacement(resizeSurface = false) {
        surfaceResizePending = surfaceResizePending || resizeSurface
        Qt.callLater(editor.refreshPlacement)
        settlePlacement.restart()
    }
    onImplicitWidthChanged: schedulePlacement()
    onImplicitHeightChanged: schedulePlacement()

    Connections {
        target: panel
        ignoreUnknownSignals: true // geometryChanged is a PanelView signal.
        function onGeometryChanged() { settlePlacement.restart() }
        function onThicknessChanged() {
            editor.draftSize = panel.thickness
            sizeInput.text = String(editor.draftSize)
            editor.schedulePlacement(true)
        }
        function onLocationChanged() {
            // PanelView owns the orientation change. A delayed setGeometry()
            // can otherwise apply the previous edge's buffer size to the new
            // edge after several quick moves.
            editor.surfaceResizePending = false
            editor.schedulePlacement()
        }
        function onFloatingChanged() { editor.schedulePlacement(true) }
        function onLengthModeChanged() { editor.schedulePlacement(true) }
        function onAlignmentChanged() { editor.schedulePlacement() }
        function onVisibilityModeChanged() { editor.schedulePlacement() }
    }

    function selectPage(index) {
        if (showAdvanced) panelConfiguration.panelRulerView.visible = false
        showAdvanced = false
        page = index
        scroll.contentItem.contentX = 0
        scroll.contentItem.contentY = 0
    }
    function toggleAdvanced() {
        if (showAdvanced) selectPage(page)
        else {
            showAdvanced = true
            scroll.contentItem.contentY = 0
        }
    }
    function revealFocus() {
        const item = editor.Window.window ? editor.Window.window.activeFocusItem : null
        let ancestor = item
        while (ancestor && ancestor !== content) ancestor = ancestor.parent
        if (!ancestor) return
        const view = scroll.contentItem
        const bounds = item.mapToItem(view, 0, 0, item.width, item.height)
        const delta = bounds.y < 0 ? bounds.y : Math.max(0, bounds.y + bounds.height - view.height)
        view.contentY = Math.max(0, Math.min(view.contentHeight - view.height, view.contentY + delta))
    }
    Connections {
        target: editor.Window.window
        function onActiveFocusItemChanged() { Qt.callLater(editor.revealFocus) }
    }
    Keys.onPressed: event => {
        // The keypad's Enter always carries the keypad modifier.
        if ((event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && (event.modifiers & ~Qt.KeypadModifier) === Qt.NoModifier) {
            const item = editor.Window.window ? editor.Window.window.activeFocusItem : null
            if (item instanceof T.AbstractButton && item.visible && item.enabled) {
                if (!event.isAutoRepeat) item.click()
                event.accepted = true
            }
        }
    }

    function requestIcons(choice) {
        busy = true
        runner.connectSource("@LIBEXECDIR@/monet-quick panel-icons " + plasmoid.id + (choice ? " " + choice : ""))
    }
    function requestLayout(layout) {
        layoutBusy = true
        layoutRunner.connectSource("@LIBEXECDIR@/monet-quick panel-layout " + plasmoid.id + (layout ? " " + layout : ""))
    }
    function requestNotch(mode) {
        notchBusy = true
        notchRunner.connectSource("@LIBEXECDIR@/monet-quick panel-notch " + plasmoid.id + (mode ? " " + mode : ""))
    }
    Component.onCompleted: { requestLayout(""); requestNotch("") }
    P5Support.DataSource {
        id: notchRunner
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source)
            editor.notchBusy = false
            try {
                const result = JSON.parse(data.stdout)
                if (!result.ok) throw new Error()
                editor.notchMode = result.mode
                editor.notchOptions = result.options || ({})
                editor.notchTabs = result.tabs || []
                editor.companionSettings = result.companionSettings || ({})
            } catch (error) {
                editor.problem = i18nd("monet", "Could not read or change the notch on this screen.")
            }
        }
    }
    P5Support.DataSource {
        id: layoutRunner
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source)
            editor.layoutBusy = false
            try {
                const result = JSON.parse(data.stdout)
                if (data["exit code"] !== 0 || !result.ok) throw new Error()
                editor.layoutAvailable = result.available
                editor.barLayout = result.layout
                editor.problem = result.available ? "" : i18nd("monet", "This screen has extra bars. Use Advanced to arrange them first.")
                editor.schedulePlacement(true)
            } catch (e) {
                editor.problem = i18nd("monet", "Could not change the bar layout. Close this editor and try again.")
            }
            editor.requestIcons("")
        }
    }
    P5Support.DataSource {
        id: runner
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source)
            editor.busy = false
            try {
                const result = JSON.parse(data.stdout)
                if (data["exit code"] !== 0 || !result.ok) throw new Error()
                editor.iconsAvailable = result.available
                editor.icons = result.alignment
                editor.iconActions = result
            } catch (e) {
                editor.problem = i18nd("monet", "Could not read the app layout. Close this editor and try again.")
            }
        }
    }

    function preset(compact) {
        if (compact) panel.alignment = Qt.AlignCenter
        panel.floating = compact
        panel.lengthMode = compact ? Panel.FitContent : Panel.FillAvailable
        syncPanelSurface()
        schedulePlacement()
    }
    function selectSize(value) {
        draftSize = Math.max(minimumSize, Math.min(maximumSize, Math.round(value)))
        sizeInput.text = String(draftSize)
    }
    function applySize() {
        selectSize(Number(sizeInput.text) || draftSize)
        panel.thickness = draftSize
        syncPanelSurface()
    }

    component Heading: C.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        font.bold: true
    }
    component Hint: C.Label {
        Layout.fillWidth: true
        wrapMode: Text.WordWrap
        opacity: 0.75
    }
    component Choice: C.Button {
        id: choice
        readonly property color accent: Kirigami.Theme.highlightColor
        property bool primary: false
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        implicitHeight: Math.max(38, implicitContentHeight + topPadding + bottomPadding)
        padding: 10
        activeFocusOnTab: true
        contentItem: C.Label {
            text: choice.text
            font: choice.font
            wrapMode: Text.Wrap
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            color: choice.primary && choice.enabled ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.textColor
            opacity: choice.enabled ? 1 : 0.55
        }
        background: Rectangle {
            radius: 10
            color: choice.primary && choice.enabled ? choice.accent
                : choice.checked ? Qt.rgba(choice.accent.r, choice.accent.g, choice.accent.b, 0.16)
                : Qt.rgba(0.5, 0.5, 0.5, choice.down ? 0.22 : choice.hovered ? 0.15 : 0.07)
            border.width: choice.visualFocus ? 2 : choice.checked ? 1 : 0
            border.color: choice.accent
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            C.Label {
                text: i18nd("monet", "Home Bar")
                font.family: "Fraunces 72pt SuperSoft"
                font.pixelSize: 26
                Layout.fillWidth: true
            }
            Choice {
                objectName: "panelDone"
                Layout.fillWidth: false
                text: i18nd("monet", "Done")
                onClicked: plasmoid.internalAction("configure").trigger()
            }
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: 6
            Repeater {
                model: [i18nd("monet", "Layout"), i18nd("monet", "Appearance"), i18nd("monet", "Behavior")]
                Choice {
                    required property int index
                    required property string modelData
                    objectName: ["panelLayoutPage", "panelAppearancePage", "panelBehaviorPage"][index]
                    text: modelData
                    checked: !editor.showAdvanced && editor.page === index
                    onClicked: editor.selectPage(index)
                }
            }
        }

        C.ScrollView {
            id: scroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            rightPadding: contentHeight > availableHeight ? 12 : 0
            contentWidth: Math.max(availableWidth, advanced.item ? advanced.item.implicitWidth : 0)
            contentHeight: content.implicitHeight
            C.ScrollBar.horizontal.policy: contentWidth > availableWidth ? C.ScrollBar.AsNeeded : C.ScrollBar.AlwaysOff

            ColumnLayout {
                id: content
                width: scroll.contentWidth
                spacing: 12

                ColumnLayout {
                    visible: !editor.showAdvanced && editor.page === 0
                    Layout.fillWidth: true
                    spacing: 10
                    Hint { text: i18nd("monet", "Drag items on the bar to reorder them.") }
                    Heading { text: i18nd("monet", "Bar layout") }
                    RowLayout {
                        Layout.fillWidth: true
                        Choice {
                            objectName: "panelOneBar"; text: i18nd("monet", "One bar")
                            checked: editor.barLayout === "one"
                            enabled: editor.layoutAvailable && !editor.layoutBusy
                            onClicked: editor.requestLayout("one")
                        }
                        Choice {
                            objectName: "panelThreeBars"; text: i18nd("monet", "Three bars")
                            checked: editor.barLayout === "three"
                            enabled: editor.layoutAvailable && !editor.layoutBusy
                            onClicked: editor.requestLayout("three")
                        }
                    }
                    Hint { text: i18nd("monet", "Includes the menu, apps, quick settings, sound and clock. Your pins and widgets stay with you.") }
                    Heading { text: i18nd("monet", "Top-center notch") }
                    RowLayout {
                        Layout.fillWidth: true
                        Repeater {
                            model: [{id:"off", title:i18nd("monet", "Off")}, {id:"compact", title:i18nd("monet", "Compact")}, {id:"wide", title:i18nd("monet", "Wide")}]
                            Choice {
                                required property var modelData
                                text: modelData.title
                                checked: editor.notchMode === modelData.id
                                enabled: !editor.notchBusy && editor.notchMode !== ""
                                onClicked: editor.requestNotch(modelData.id)
                            }
                        }
                    }
                    Repeater {
                        model: [{key:"gestures", label:i18nd("monet", "Scroll to open the notch or skip tracks")},
                                {key:"levels", label:i18nd("monet", "Show music level")},
                                {key:"previews", label:i18nd("monet", "Preview notifications in the notch")},
                                {key:"countdown", label:i18nd("monet", "Show running timers in the closed notch")},
                                {key:"awake", label:i18nd("monet", "Show Keep awake in the closed notch")},
                                {key:"alerts", label:i18nd("monet", "Low accessory battery alerts")},
                                {key:"companion", label:i18nd("monet", "Show notch companion")}]
                        C.CheckBox {
                            required property var modelData
                            objectName: "notchOption-" + modelData.key
                            visible: editor.notchMode === "compact" || editor.notchMode === "wide"
                            text: modelData.label; enabled: !editor.notchBusy
                            checked: !!editor.notchOptions[modelData.key]
                            onClicked: editor.requestNotch(modelData.key + (checked ? "-on" : "-off"))
                        }
                    }
                    C.Button {
                        id: editCompanion
                        objectName: "editNotchCompanion"
                        visible: editor.notchMode !== "off" && !!editor.notchOptions.companion
                        text: i18nd("monet", "Customize companion")
                        checkable: true
                        icon.name: checked ? "arrow-down" : "arrow-right"
                    }
                    Loader {
                        Layout.fillWidth: true
                        active: editCompanion.visible && editCompanion.checked
                        visible: active
                        sourceComponent: ColumnLayout {
                            RowLayout {
                                Rectangle {
                                    Layout.preferredWidth: 74; Layout.preferredHeight: 38
                                    radius: height / 2; color: "#202323"
                                    Loader {
                                        id: companionPreview
                                        anchors.centerIn: parent; width: 34; height: 34
                                        source: "file://@DATADIR@/plasma/plasmoids/org.monet.notch/contents/ui/NotchCompanion.qml"
                                        onLoaded: {
                                            item.visits = false
                                            item.styleName = Qt.binding(() => editor.companionSettings.style || "soft")
                                            item.shapeName = Qt.binding(() => editor.companionSettings.shape || "round")
                                            item.paletteName = Qt.binding(() => editor.companionSettings.color || "mint")
                                            item.side = Qt.binding(() => editor.companionSettings.side || "left")
                                        }
                                    }
                                }
                                C.Button {
                                    objectName: "greetCompanion"
                                    text: i18nd("monet", "Say hello")
                                    enabled: !!companionPreview.item
                                    onClicked: companionPreview.item.greet()
                                }
                            }
                            Repeater {
                                model: [
                                    {key:"style", title:i18nd("monet", "Style"), keys:["soft","robot"], names:[i18nd("monet","Soft"),i18nd("monet","Robot")]},
                                    {key:"shape", title:i18nd("monet", "Shape"), keys:["round","egg","square","pill"], names:[i18nd("monet","Round"),i18nd("monet","Egg"),i18nd("monet","Rounded square"),i18nd("monet","Capsule")]},
                                    {key:"color", title:i18nd("monet", "Color"), keys:["mint","pearl","lemon","peach","rose","lilac","sky"], names:[i18nd("monet","Mint"),i18nd("monet","Pearl"),i18nd("monet","Lemon"),i18nd("monet","Peach"),i18nd("monet","Rose"),i18nd("monet","Lilac"),i18nd("monet","Sky")]},
                                    {key:"side", title:i18nd("monet", "Side"), keys:["left","right"], names:[i18nd("monet","Left"),i18nd("monet","Right")]},
                                    {key:"visits", title:i18nd("monet", "Visits"), keys:["off","rare","normal","frequent"], names:[i18nd("monet","Off"),i18nd("monet","Rare"),i18nd("monet","Regular"),i18nd("monet","Frequent")]}
                                ]
                                RowLayout {
                                    id: field
                                    required property var modelData
                                    Layout.fillWidth: true
                                    C.Label { Layout.fillWidth: true; text: field.modelData.title; wrapMode: Text.Wrap }
                                    C.ComboBox {
                                        objectName: "companion-" + field.modelData.key
                                        Accessible.name: field.modelData.title
                                        enabled: !editor.notchBusy
                                        model: field.modelData.names
                                        currentIndex: field.modelData.keys.indexOf(editor.companionSettings[field.modelData.key])
                                        onActivated: index => editor.requestNotch("companion-" + field.modelData.key + "-" + field.modelData.keys[index])
                                    }
                                }
                            }
                            C.CheckBox {
                                objectName: "companion-reactions"
                                text: i18nd("monet", "React to desktop activity")
                                enabled: !editor.notchBusy
                                checked: editor.companionSettings.reactions === "on"
                                onClicked: editor.requestNotch("companion-reactions-" + (checked ? "on" : "off"))
                            }
                            C.CheckBox {
                                objectName: "companion-rest"
                                text: i18nd("monet", "Hide between visits and reactions")
                                enabled: !editor.notchBusy
                                checked: editor.companionSettings.rest === "hide"
                                onClicked: editor.requestNotch("companion-rest-" + (checked ? "hide" : "show"))
                            }
                        }
                    }
                    C.Button {
                        id: editTabs
                        objectName: "editNotchTabs"
                        visible: editor.notchMode === "compact" || editor.notchMode === "wide"
                        text: i18nd("monet", "Edit notch tabs")
                        checkable: true
                        icon.name: checked ? "arrow-down" : "arrow-right"
                    }
                    ColumnLayout {
                        visible: editTabs.visible && editTabs.checked
                        Layout.fillWidth: true
                        Repeater {
                            model: tabRows
                            RowLayout {
                                id: tabRow
                                required property string key
                                required property int index
                                readonly property bool shown: editor.notchTabs.includes(key)
                                Layout.fillWidth: true
                                C.CheckBox {
                                    objectName: "notchTab-" + tabRow.key
                                    Layout.fillWidth: true
                                    text: editor.tabTitles[tabRow.key]
                                    checked: tabRow.shown
                                    enabled: !editor.notchBusy
                                    onClicked: editor.requestNotch("tab-" + tabRow.key + (checked ? "-show" : "-hide"))
                                }
                                C.ToolButton {
                                    objectName: "notchEarlier-" + tabRow.key
                                    icon.name: "arrow-up"
                                    Accessible.name: i18nd("monet", "Move %1 earlier", editor.tabTitles[tabRow.key])
                                    C.ToolTip.text: Accessible.name; C.ToolTip.visible: hovered
                                    enabled: tabRow.shown && tabRow.index > 0 && !editor.notchBusy
                                    onClicked: editor.requestNotch("tab-" + tabRow.key + "-earlier")
                                }
                                C.ToolButton {
                                    objectName: "notchLater-" + tabRow.key
                                    icon.name: "arrow-down"
                                    Accessible.name: i18nd("monet", "Move %1 later", editor.tabTitles[tabRow.key])
                                    C.ToolTip.text: Accessible.name; C.ToolTip.visible: hovered
                                    enabled: tabRow.shown && tabRow.index < editor.notchTabs.length - 1 && !editor.notchBusy
                                    onClicked: editor.requestNotch("tab-" + tabRow.key + "-later")
                                }
                            }
                        }
                    }
                    Heading { text: i18nd("monet", "Bar shape") }
                    RowLayout {
                        Layout.fillWidth: true
                        Repeater {
                            model: [i18nd("monet", "Full-width bar"), i18nd("monet", "Compact dock")]
                            Choice {
                                id: shape
                                required property int index
                                required property string modelData
                                objectName: index ? "panelDock" : "panelFullWidth"
                                text: modelData
                                topPadding: 46
                                checked: panel.lengthMode === (index ? Panel.FitContent : Panel.FillAvailable)
                                onClicked: editor.preset(index === 1)
                                Rectangle {
                                    x: 12
                                    y: 10
                                    width: Math.max(0, parent.width - 24)
                                    height: 28
                                    radius: 6
                                    color: Qt.rgba(0.5, 0.5, 0.5, 0.08)
                                    Rectangle {
                                        width: shape.index ? parent.width * 0.55 : Math.max(0, parent.width - 8)
                                        height: 9
                                        radius: shape.index ? 5 : 2
                                        anchors.horizontalCenter: parent.horizontalCenter
                                        anchors.bottom: parent.bottom
                                        anchors.bottomMargin: 4
                                        color: editor.accent
                                    }
                                }
                            }
                        }
                    }

                    Heading { text: i18nd("monet", "Screen edge") }
                    GridLayout {
                        Layout.fillWidth: true
                        columns: scroll.availableWidth >= Kirigami.Units.gridUnit * 22 ? 4 : 2
                        Repeater {
                            model: [
                                {name: i18nd("monet", "Bottom"), edge: PlasmaCore.Types.BottomEdge},
                                {name: i18nd("monet", "Top"), edge: PlasmaCore.Types.TopEdge},
                                {name: i18nd("monet", "Left"), edge: PlasmaCore.Types.LeftEdge},
                                {name: i18nd("monet", "Right"), edge: PlasmaCore.Types.RightEdge}]
                            Choice {
                                required property var modelData
                                text: modelData.name
                                checked: panel.location === modelData.edge
                                onClicked: panel.location = modelData.edge
                            }
                        }
                    }
                    Heading { visible: alongEdge.visible; text: i18nd("monet", "Bar position along edge") }
                    RowLayout {
                        id: alongEdge
                        visible: panel.lengthMode !== Panel.FillAvailable
                        Layout.fillWidth: true
                        Repeater {
                            // Plasma places a bar by screen side, so in a
                            // right-to-left language Start is the right side.
                            readonly property bool mirrored: !editor.vertical && Qt.application.layoutDirection === Qt.RightToLeft
                            model: [
                                {name: editor.vertical ? i18nd("monet", "Top") : i18ndc("monet", "where on the bar: at its start, not the verb", "Start"), alignment: mirrored ? Qt.AlignRight : Qt.AlignLeft},
                                {name: i18nd("monet", "Center"), alignment: Qt.AlignCenter},
                                {name: editor.vertical ? i18nd("monet", "Bottom") : i18nd("monet", "End"), alignment: mirrored ? Qt.AlignLeft : Qt.AlignRight}]
                            Choice {
                                required property var modelData
                                text: modelData.name
                                checked: panel.alignment === modelData.alignment
                                onClicked: panel.alignment = modelData.alignment
                            }
                        }
                    }

                    Heading { visible: editor.iconsAvailable; text: i18nd("monet", "App icon position") }
                    RowLayout {
                        visible: editor.iconsAvailable
                        Layout.fillWidth: true
                        Choice {
                            objectName: "panelIconsStart"
                            text: editor.vertical ? i18nd("monet", "Top") : i18ndc("monet", "where on the bar: at its start, not the verb", "Start")
                            checked: editor.icons === "start"
                            enabled: !editor.busy
                            onClicked: editor.requestIcons("start")
                        }
                        Choice {
                            objectName: "panelIconsCenter"
                            text: i18nd("monet", "Center")
                            checked: editor.icons === "center"
                            enabled: !editor.busy
                            onClicked: editor.requestIcons("center")
                        }
                    }
                    Hint { visible: editor.iconsAvailable; text: i18nd("monet", "Places app icons within the space between the other items on this bar.") }
                    Hint { visible: editor.problem !== ""; text: editor.problem }
                }

                ColumnLayout {
                    visible: !editor.showAdvanced && editor.page === 1
                    Layout.fillWidth: true
                    spacing: 10
                    Heading { text: editor.vertical ? i18nd("monet", "Bar width") : i18nd("monet", "Bar height") }
                    RowLayout {
                        Layout.fillWidth: true
                        Repeater {
                            model: [
                                {name: i18nd("monet", "Small"), size: 40},
                                {name: i18nd("monet", "Medium"), size: 56},
                                {name: i18nd("monet", "Large"), size: 72}]
                            Choice {
                                required property var modelData
                                text: modelData.name
                                checked: editor.draftSize === modelData.size
                                enabled: modelData.size >= editor.minimumSize && modelData.size <= editor.maximumSize
                                onClicked: editor.selectSize(modelData.size)
                            }
                        }
                    }
                    C.Slider {
                        objectName: "panelSizeSlider"
                        Layout.fillWidth: true
                        Accessible.name: editor.vertical ? i18nd("monet", "Bar width") : i18nd("monet", "Bar height")
                        from: editor.minimumSize
                        to: editor.maximumSize
                        stepSize: 1
                        wheelEnabled: false
                        value: editor.draftSize
                        onMoved: editor.selectSize(value)
                    }
                    RowLayout {
                        Layout.fillWidth: true
                        Choice {
                            objectName: "panelSizeDecrease"
                            text: "−"
                            Accessible.name: i18nd("monet", "Decrease bar size")
                            Layout.fillWidth: false
                            enabled: editor.draftSize > editor.minimumSize
                            onClicked: editor.selectSize(editor.draftSize - 1)
                        }
                        C.TextField {
                            id: sizeInput
                            objectName: "panelSizeInput"
                            Layout.preferredWidth: 58
                            Accessible.name: i18nd("monet", "Bar size in pixels")
                            horizontalAlignment: Text.AlignHCenter
                            inputMethodHints: Qt.ImhDigitsOnly
                            validator: IntValidator { bottom: editor.minimumSize; top: editor.maximumSize }
                            text: String(editor.draftSize)
                            onTextEdited: if (acceptableInput) editor.draftSize = Number(text)
                            onAccepted: editor.applySize()
                            onEditingFinished: if (!acceptableInput) text = String(editor.draftSize)
                        }
                        Choice {
                            objectName: "panelSizeIncrease"
                            text: "+"
                            Accessible.name: i18nd("monet", "Increase bar size")
                            Layout.fillWidth: false
                            enabled: editor.draftSize < editor.maximumSize
                            onClicked: editor.selectSize(editor.draftSize + 1)
                        }
                        Choice {
                            objectName: "panelSizeApply"
                            text: i18nd("monet", "Apply size")
                            primary: true
                            enabled: sizeInput.acceptableInput && editor.draftSize !== panel.thickness
                            onClicked: editor.applySize()
                        }
                    }

                    Heading { text: i18nd("monet", "Floating bar") }
                    RowLayout {
                        Layout.fillWidth: true
                        Choice {
                            text: i18nd("monet", "Flush with edge")
                            checked: !panel.floating
                            onClicked: panel.floating = false
                        }
                        Choice {
                            text: i18nd("monet", "Floating")
                            checked: panel.floating
                            onClicked: panel.floating = true
                        }
                    }
                    Heading { visible: opacityChoices.visible; text: i18nd("monet", "Background opacity") }
                    RowLayout {
                        id: opacityChoices
                        visible: panel.adaptiveOpacityEnabled
                        Layout.fillWidth: true
                        Repeater {
                            model: [
                                {name: i18nd("monet", "Adaptive"), opacity: Panel.Adaptive},
                                {name: i18nd("monet", "Opaque"), opacity: Panel.Opaque},
                                {name: i18nd("monet", "Translucent"), opacity: Panel.Translucent}]
                            Choice {
                                required property var modelData
                                text: modelData.name
                                checked: panel.opacityMode === modelData.opacity
                                onClicked: panel.opacityMode = modelData.opacity
                            }
                        }
                    }
                }

                ColumnLayout {
                    visible: !editor.showAdvanced && editor.page === 2
                    Layout.fillWidth: true
                    spacing: 10
                    Repeater {
                        model: editor.iconsAvailable ? [
                            {key: "active", label: i18nd("monet", "Click an active window’s icon"),
                             options: [i18nd("monet", "Keep the window visible"), i18nd("monet", "Minimize the window")]},
                            {key: "group", label: i18nd("monet", "Click an app with several windows"),
                             options: [i18nd("monet", "Cycle through windows"), i18nd("monet", "Show previews on click and hover"),
                                       i18nd("monet", "Show window overview"), i18nd("monet", "List window titles")]},
                            {key: "middle", label: i18nd("monet", "Middle-click an app icon"),
                             options: [i18nd("monet", "Do nothing"), i18nd("monet", "Close the window or group"),
                                       i18nd("monet", "Open a new window"), i18nd("monet", "Minimize or restore the window or group"),
                                       i18nd("monet", "Group or ungroup windows"), i18nd("monet", "Move windows to this desktop")]}
                        ] : []
                        ColumnLayout {
                            id: actionRow
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 3
                            Heading { text: actionRow.modelData.label }
                            C.ComboBox {
                                objectName: "panelClick-" + actionRow.modelData.key
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                Accessible.name: actionRow.modelData.label
                                model: actionRow.modelData.options
                                currentIndex: editor.iconActions[actionRow.modelData.key] ?? -1
                                displayText: currentIndex < 0 ? i18nd("monet", "Choose an action") : currentText
                                enabled: !editor.busy && !editor.layoutBusy
                                onActivated: index => editor.requestIcons(actionRow.modelData.key + "-" + index)
                            }
                        }
                    }
                    Hint { visible: editor.problem !== ""; text: editor.problem }
                    Heading { text: i18nd("monet", "Bar visibility") }
                    Repeater {
                        model: [
                            {name: i18nd("monet", "Reserve space"), mode: Panel.NormalPanel,
                                detail: i18nd("monet", "Maximized windows stop at the bar.")},
                            {name: i18nd("monet", "Keep visible"), mode: Panel.WindowsGoBelow,
                                detail: i18nd("monet", "The bar stays above windows.")},
                            {name: i18nd("monet", "Dodge windows"), mode: Panel.DodgeWindows,
                                detail: i18nd("monet", "Hide the bar when a window overlaps it.")},
                            {name: i18nd("monet", "Auto-hide"), mode: Panel.AutoHide,
                                detail: i18nd("monet", "Move the pointer to the screen edge to show the bar.")}]
                        ColumnLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            spacing: 3
                            Choice {
                                text: modelData.name
                                checked: panel.visibilityMode === modelData.mode
                                onClicked: panel.visibilityMode = modelData.mode
                            }
                            Hint { text: modelData.detail }
                        }
                    }
                }

                Loader {
                    id: advanced
                    Layout.fillWidth: true
                    active: editor.showAdvanced
                    visible: active
                    onActiveChanged: if (active) setSource(editor.advancedPage, {panelConfiguration: editor.panelConfiguration})
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Choice {
                text: i18nd("monet", "Add widgets…")
                onClicked: { configDialog.close(); configDialog.showAddWidgetDialog() }
            }
            Choice {
                objectName: "panelAdvanced"
                text: editor.showAdvanced ? i18nd("monet", "Back") : i18nd("monet", "Advanced…")
                onClicked: editor.toggleAdvanced()
            }
        }
    }
}
