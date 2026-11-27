pragma ComponentBehavior: Bound
// Edit the existing panel in place, so its widgets and pins keep their identities.
import QtQuick
import "file://@DATADIR@/monet/panel" as EditorUI
import QtQuick.Layouts
import QtQuick.Controls as C
import QtQuick.Templates as T
import org.kde.kirigami as Kirigami
import org.kde.plasma.core as PlasmaCore
import org.kde.kquickcontrols
import org.kde.plasma.shell
import org.kde.plasma.plasma5support as P5Support

Item {
    id: editor
    objectName: "monetPanelEditor"
    required property QtObject panelConfiguration
    property Item panelRuler: null
    signal closeContextMenu

    readonly property bool vertical: panel.location === PlasmaCore.Types.LeftEdge || panel.location === PlasmaCore.Types.RightEdge
    readonly property color accent: Kirigami.Theme.highlightColor
    readonly property int minimumSize: Math.max(20, panel.minThickness)
    readonly property int maximumSize: Math.max(minimumSize, Math.min(120, Math.floor(
        Math.min(screenGeometry.width, screenGeometry.height) / 3)))
    readonly property rect screenGeometry: panel.screenToFollow ? panel.screenToFollow.geometry : Qt.rect(0, 0, Screen.width, Screen.height)
    // All pages share a fixed viewport, independent of the bar being edited.
    implicitWidth: Math.min(640, Math.max(180, screenGeometry.width - 64))
    implicitHeight: Math.min(760, Math.max(200, screenGeometry.height - 192))
    clip: true
    LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
    LayoutMirroring.childrenInherit: true

    readonly property bool notchPanel: Array.from(plasmoid.applets || []).some(applet => applet.pluginName === "org.monet.notch")
    property int page: notchPanel ? 3 : 0
    property bool showAdvanced: false
    property bool addingPanel: false
    property string addStatus: ""
    property int addedPanel: 0
    property string notchProblem: ""
    property var scrollOffsets: ({})
    property int draftSize: panel.thickness
    property bool resizingBar: false
    property bool lengthEdited: false
    property int draftLength: 600
    property int draftOffset: 0
    property int resizeAlignment: Qt.AlignCenter
    readonly property int shownAlignment: resizingBar ? resizeAlignment : panel.alignment
    readonly property int shownOffset: resizingBar ? draftOffset : panel.offset
    readonly property int screenLength: Math.floor(vertical ? screenGeometry.height : screenGeometry.width)
    readonly property int maximumBarLength: Math.max(1, screenLength - Math.abs(panel.offset) * (panel.alignment === Qt.AlignCenter ? 2 : 1))
    readonly property int minimumBarLength: Math.min(240, maximumBarLength)
    // Panel.length is the widgets' natural length, even in Custom mode. Showing
    // it after a drag made the preview snap back instead of keeping the size set.
    readonly property int shownLength: resizingBar || lengthEdited ? draftLength : panel.lengthMode === Panel.FillAvailable ? screenLength
        : panel.lengthMode === Panel.Custom ? Math.min(screenLength, Math.max(panel.minimumLength, Math.min(panel.maximumLength, panel.length)))
        : Math.min(screenLength, panel.length)
    property string icons: ""
    property var iconActions: ({})
    property bool iconsAvailable: false
    property string barLayout: ""
    property bool layoutAvailable: false
    property var notchState: ({})
    property string notchMode: ""
    property bool notchBusy: false
    property var notchQueue: []
    property var notchOptions: ({})
    property var notchTabs: []
    property var companionSettings: ({})
    property bool layoutBusy: false
    property bool busy: false
    property string problem: ""
    property bool surfaceResizePending: false

    Loader {
        id: windowPlacement
        active: configDialog.visualParent !== undefined && panel.contentItem instanceof Item
        sourceComponent: EditorUI.EditorWindowPlacement {
            host: configDialog
            panelContent: panel.contentItem
            screenGeometry: editor.screenGeometry
            panelX: panel.x
            panelY: panel.y
        }
    }

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
        // floating insets and the limits used by custom-length panels.
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
        else length = Math.max(panel.minimumLength, Math.min(panel.maximumLength, available - panel.offset, natural))
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
            editor.schedulePlacement(true)
        }
        function onLocationChanged() {
            // PanelView owns the orientation change. A delayed setGeometry()
            // can otherwise apply the previous edge's buffer size to the new
            // edge after several quick moves.
            editor.surfaceResizePending = false
            editor.lengthEdited = false
            editor.resizingBar = false
            editor.schedulePlacement()
        }
        function onFloatingChanged() { editor.schedulePlacement(true) }
        function onLengthModeChanged() { editor.lengthEdited = false; editor.schedulePlacement(true) }
        function onAlignmentChanged() { editor.schedulePlacement() }
        function onVisibilityModeChanged() { editor.schedulePlacement() }
    }

    function selectPage(index) {
        if ((index === 3 || index === 4) && !notchBusy) requestNotch("")
        if (page === index && !showAdvanced) return
        scrollOffsets[showAdvanced ? "advanced" : page] = scroll.contentItem.contentY
        showAdvanced = false
        page = index
        restoreScroll()
    }
    function restoreScroll() {
        Qt.callLater(() => {
            const view = scroll.contentItem
            view.contentX = 0
            view.contentY = Math.max(0, Math.min(scrollOffsets[showAdvanced ? "advanced" : page] || 0, view.contentHeight - view.height))
        })
    }
    function toggleAdvanced() {
        if (showAdvanced) selectPage(page)
        else {
            scrollOffsets[page] = scroll.contentItem.contentY
            showAdvanced = true
            restoreScroll()
        }
    }
    function revealFocus() {
        // Mouse focus must not scroll the canvas out from under a resize grip.
        const item = editor.Window.window ? editor.Window.window.activeFocusItem : null
        if (resizingBar || item?.dragging) return
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
        if (notchBusy) { notchQueue = notchQueue.concat([mode]); return }
        notchProblem = ""
        notchBusy = true
        notchRunner.connectSource("@LIBEXECDIR@/monet-quick panel-notch " + plasmoid.id + (mode ? " " + mode : ""))
    }
    function selectTaskbar() {
        if (!notchPanel) { selectPage(0); return }
        taskbarRunner.connectSource("@LIBEXECDIR@/monet-quick panel-taskbar-configure " + plasmoid.id)
    }
    P5Support.DataSource {
        id: taskbarRunner
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source)
            let ok = false
            try { ok = JSON.parse(data.stdout).ok } catch (_) {}
            if (!ok) editor.notchProblem = i18nd("monet", "No taskbar was found on this screen. Use Add panel to create one.")
        }
    }
    function addPanel(kind) {
        if (addingPanel) return
        addingPanel = true
        addStatus = ""
        addedPanel = 0
        panelCreator.connectSource("@LIBEXECDIR@/monet-quick panel-add " + plasmoid.id + " " + kind)
    }
    P5Support.DataSource {
        id: panelCreator
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source)
            editor.addingPanel = false
            try {
                const result = JSON.parse(data.stdout)
                if (!result.ok) throw new Error()
                if (source.includes(" panel-configure ")) return
                editor.addedPanel = result.id
                const edges = {top:i18nd("monet","Top"), bottom:i18nd("monet","Bottom"),
                    left:i18nd("monet","Left"), right:i18nd("monet","Right")}
                editor.addStatus = i18nd("monet","Panel added (%1).", edges[result.edge])
                editor.requestLayout("")
            } catch (_) {
                editor.addStatus = source.includes(" panel-configure ") ? i18nd("monet","Could not open this panel.")
                    : i18nd("monet","Could not add the panel. Try again.")
            }
        }
    }
    Component.onCompleted: { requestLayout(""); if (page === 3) requestNotch("") }
    P5Support.DataSource {
        id: notchRunner
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source)
            editor.notchBusy = false
            try {
                const result = JSON.parse(data.stdout)
                if (data["exit code"] !== 0 || !result.ok) throw new Error()
                editor.notchState = result
                editor.notchMode = result.mode
                if (source.endsWith(" add") && editor.page === 4) editor.selectPage(3)
                editor.notchOptions = result.options || ({})
                editor.notchTabs = result.tabs || []
                editor.companionSettings = result.companionSettings || ({})
            } catch (error) {
                editor.notchProblem = i18nd("monet", "Could not read or change the notch on this screen.")
            }
            if (editor.notchQueue.length) {
                const next = editor.notchQueue[0]
                editor.notchQueue = editor.notchQueue.slice(1)
                editor.requestNotch(next)
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
                if (/ (one|three)$/.test(source)) editor.schedulePlacement(true)
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

    property string advancedStatus: ""
    function panelAction(action) {
        advancedStatus = ""
        advancedRunner.connectSource("@LIBEXECDIR@/monet-quick panel-detail " + plasmoid.id + " " + action)
    }
    P5Support.DataSource {
        id: advancedRunner
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source)
            let ok = false
            try { ok = JSON.parse(data.stdout).ok === true } catch (_) {}
            editor.advancedStatus = ok ? i18nd("monet", "Updated") : i18nd("monet", "Could not update this bar. Please try again.")
        }
    }

    function preset(compact) {
        if (compact) alignBar(Qt.AlignCenter)
        lengthEdited = false
        panel.floating = compact
        panel.maximumLength = screenLength
        panel.minimumLength = minimumBarLength
        panel.lengthMode = compact ? Panel.FitContent : Panel.FillAvailable
        syncPanelSurface()
        schedulePlacement()
    }
    function selectSize(value) {
        draftSize = Math.max(minimumSize, Math.min(maximumSize, Math.round(value)))
    }
    function applySize(value) {
        selectSize(Number(value) || draftSize)
        panel.thickness = draftSize
        syncPanelSurface()
    }
    function alignBar(alignment) {
        panel.offset = 0
        panel.alignment = alignment
        schedulePlacement()
    }
    function previewBarSize(length, thickness) {
        draftLength = Math.max(minimumBarLength, Math.min(maximumBarLength, Math.round(length)))
        lengthEdited = true
        selectSize(thickness)
    }
    function applyBarSize() {
        const length = lengthEdited || resizingBar ? draftLength : shownLength
        if (resizingBar) { panel.offset = draftOffset; panel.alignment = resizeAlignment }
        resizingBar = false
        // Set both limits so the custom bar has the size shown in the preview.
        // Grow the maximum first to avoid an intermediate invalid range.
        if (length > panel.maximumLength) panel.maximumLength = length
        panel.minimumLength = length
        panel.maximumLength = length
        panel.lengthMode = Panel.Custom
        lengthEdited = false
        applySize(draftSize)
        schedulePlacement(true)
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
        Layout.preferredWidth: choice.Layout.fillWidth ? 1 : implicitWidth
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

    component EditorPage: Loader {
        required property int number
        property bool visited: false
        visible: !editor.showAdvanced && editor.page === number
        active: visible || visited
        asynchronous: true
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        onLoaded: { visited = true; if (visible) editor.restoreScroll() }
    }
    component ActionRow: C.AbstractButton {
        id: action
        required property string detail
        Layout.fillWidth: true
        Layout.minimumWidth: 0
        padding: 10
        Accessible.name: text
        Accessible.description: detail
        background: Rectangle {
            radius: 10
            color: Qt.rgba(editor.accent.r, editor.accent.g, editor.accent.b, action.down ? 0.20 : action.hovered ? 0.12 : 0.055)
            border.color: action.visualFocus ? editor.accent : Qt.rgba(0.5,0.5,0.5,0.18)
            border.width: action.visualFocus ? 2 : 1
        }
        contentItem: RowLayout {
            spacing: 12
            Kirigami.Icon { source: action.icon.name; Layout.preferredWidth: 23; Layout.preferredHeight: 23; color: editor.accent }
            ColumnLayout {
                Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 2
                C.Label { text: action.text; font.bold: true; Layout.fillWidth: true; wrapMode: Text.Wrap }
                Hint { text: action.detail; font.pointSize: Kirigami.Theme.smallFont.pointSize }
            }
            Kirigami.Icon { source: Qt.application.layoutDirection === Qt.RightToLeft ? "go-previous" : "go-next"; Layout.preferredWidth: 14; Layout.preferredHeight: 14 }
        }
    }

    Rectangle {
        anchors.fill: parent
        visible: configDialog.titleHeight === undefined
        radius: 12
        color: Kirigami.Theme.backgroundColor
        border.width: 1
        border.color: Qt.rgba(0.5,0.5,0.5,0.25)
    }
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 10
        RowLayout {
            visible: configDialog.titleHeight === undefined
            Layout.fillWidth: true
            C.Label {
                id: windowTitle
                visible: configDialog.titleHeight === undefined
                Layout.minimumWidth: 0
                elide: Text.ElideRight
                text: i18nd("monet", "Desktop layout")
                font.family: "Fraunces 72pt SuperSoft"
                font.pixelSize: 26
                Layout.fillWidth: true
                MouseArea {
                    anchors.fill: parent
                    enabled: !!configDialog.startSystemMove || !!windowPlacement.item
                    cursorShape: pressed ? Qt.ClosedHandCursor : Qt.OpenHandCursor
                    property point origin
                    property point windowOrigin
                    onDoubleClicked: { if (configDialog.visibility === Window.Maximized) configDialog.showNormal(); else if (configDialog.showMaximized) configDialog.showMaximized() }
                    onPressed: mouse => {
                        if (configDialog.startSystemMove) { configDialog.startSystemMove(); return }
                        origin = mapToGlobal(mouse.x, mouse.y)
                        windowOrigin = Qt.point(windowPlacement.item.windowX, windowPlacement.item.windowY)
                    }
                    onPositionChanged: mouse => {
                        if (!pressed || !windowPlacement.item) return
                        const point = mapToGlobal(mouse.x, mouse.y)
                        windowPlacement.item.moveTo(windowOrigin.x + point.x - origin.x, windowOrigin.y + point.y - origin.y)
                    }
                }
            }
            Item { visible: configDialog.titleHeight !== undefined; Layout.fillWidth: true }
            EditorUI.WindowControls { host: configDialog; visible: configDialog.titleHeight === undefined }

        }
        RowLayout {
            Layout.fillWidth: true; spacing: 6
            Choice { objectName: "panelTaskbarPage"; text: i18nd("monet","Taskbar"); checked: !editor.showAdvanced && editor.page < 3; onClicked: editor.selectTaskbar() }
            Choice { objectName: "panelNotchPage"; text: i18nd("monet","Notch"); checked: !editor.showAdvanced && editor.page === 3; onClicked: editor.selectPage(3) }
            Choice {
                objectName: "panelDone"
                Layout.fillWidth: false
                text: i18nd("monet", "Done")
                onClicked: configDialog.finishEditing ? configDialog.finishEditing() : configDialog.close()
            }
        }
        RowLayout {
            visible: !editor.showAdvanced && editor.page < 3
            Layout.fillWidth: true; spacing: 4
            Repeater {
                model: [{page:0,id:"panelLayoutPage",name:i18nd("monet","Layout")},
                        {page:1,id:"panelAppearancePage",name:i18nd("monet","Size & style")},
                        {page:2,id:"panelBehaviorPage",name:i18nd("monet","Behavior")}]
                Choice {
                    required property var modelData
                    objectName: modelData.id; text: modelData.name
                    Layout.preferredWidth: 1; padding: 5
                    checked: editor.page === modelData.page
                    onClicked: editor.selectPage(modelData.page)
                }
            }
        }

        C.ScrollView {
            id: scroll
            objectName: "panelEditorScroll"
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            // Keep previews and controls still when a page starts scrolling.
            rightPadding: 12
            contentWidth: availableWidth
            contentHeight: content.implicitHeight
            C.ScrollBar.horizontal.policy: C.ScrollBar.AlwaysOff

            ColumnLayout {
                id: content
                width: scroll.contentWidth
                spacing: 12

                C.Pane {
                    visible: !editor.showAdvanced && editor.page < 3
                    Layout.fillWidth: true; padding: 16
                    background: Rectangle { radius: 18; color: Qt.rgba(0.5,0.5,0.5,0.08) }
                    contentItem: ColumnLayout {
                    spacing: 10
                    RowLayout {
                        Heading { text: i18nd("monet","Shape and position") }
                        C.Label { text: editor.shownLength+" × "+editor.draftSize+" px"; opacity: 0.65; font.pixelSize: 12 }
                    }
                    Rectangle {
                        id: desktopPreview
                        objectName: "taskbarPreviewCanvas"
                        Layout.fillWidth: true; Layout.preferredHeight: 182; radius: 10
                        color: Qt.rgba(editor.accent.r,editor.accent.g,editor.accent.b,0.07)
                        border.width: 1; border.color: Qt.rgba(0.5,0.5,0.5,0.16)
                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter; width: 62; height: 13; radius: 7; color: "#151519"
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: editor.selectPage(3) }
                        }
                        Rectangle {
                            anchors.centerIn: parent; width: parent.width*0.52; height: 68; radius: 8
                            color: Qt.rgba(0.5,0.5,0.5,0.1); border.width: 1; border.color: Qt.rgba(0.5,0.5,0.5,0.12)
                            C.Label { anchors.centerIn: parent; text: i18nd("monet","Your screen"); opacity: 0.5; font.pixelSize: 12 }
                        }
                        Rectangle { anchors.horizontalCenter: parent.horizontalCenter; width: 1; height: parent.height-24; y: 12; color: editor.accent; opacity: 0.22; visible: !editor.vertical }
                        Rectangle { anchors.verticalCenter: parent.verticalCenter; height: 1; width: parent.width-24; x: 12; color: editor.accent; opacity: 0.22; visible: editor.vertical }
                        Repeater {
                            model: editor.barLayout === "three" && !editor.vertical ? [0,1] : []
                            Rectangle {
                                required property int modelData
                                width: Math.min(64,desktopPreview.width*0.14); height: 18; radius: 6
                                x: modelData ? desktopPreview.width-width-16 : 16
                                y: panel.location === PlasmaCore.Types.TopEdge ? 24 : desktopPreview.height-height-16
                                color: Qt.rgba(0.5,0.5,0.5,0.17)
                            }
                        }
                        Rectangle {
                            id: previewBar
                            objectName: "taskbarSizePreview"
                            readonly property real lengthScale: ((editor.vertical ? parent.height : parent.width)-32)/editor.screenLength
                            readonly property real thicknessScale: 0.35
                            readonly property real thickness: editor.draftSize*thicknessScale
                            readonly property real span: editor.shownLength*lengthScale
                            readonly property real remaining: (editor.vertical ? parent.height : parent.width)-32-span
                            readonly property real position: 16 + (panel.lengthMode === Panel.FillAvailable && !editor.resizingBar && !editor.lengthEdited ? 0
                                : editor.shownAlignment === Qt.AlignCenter ? remaining/2+editor.shownOffset*lengthScale
                                : editor.shownAlignment === Qt.AlignRight ? remaining-editor.shownOffset*lengthScale : editor.shownOffset*lengthScale)
                            width: editor.vertical ? thickness : span
                            height: editor.vertical ? span : thickness
                            x: editor.vertical ? (panel.location === PlasmaCore.Types.LeftEdge ? 16 : parent.width-width-16) : position
                            y: !editor.vertical ? (panel.location === PlasmaCore.Types.TopEdge ? 24 : parent.height-height-16) : position
                            radius: panel.floating ? 9 : 3; color: Qt.rgba(editor.accent.r,editor.accent.g,editor.accent.b,0.24)
                            Row {
                                objectName: "taskbarPreviewIconsHorizontal"
                                x: editor.icons === "center" ? (parent.width-width)/2 : (Qt.application.layoutDirection === Qt.RightToLeft ? parent.width-width-8 : 8)
                                anchors.verticalCenter: parent.verticalCenter; spacing: 4; visible: !editor.vertical
                                readonly property real iconSize: Math.max(2,Math.min(10,(parent.width-36)/6,parent.height-4))
                                Repeater { model: 6; Rectangle { required property int index; width: parent.iconSize; height: width; radius: 3; color: index % 2 ? editor.accent : Qt.rgba(editor.accent.r,editor.accent.g,editor.accent.b,0.55) } }
                            }
                            Column {
                                objectName: "taskbarPreviewIconsVertical"
                                y: editor.icons === "center" ? (parent.height-height)/2 : 8
                                anchors.horizontalCenter: parent.horizontalCenter; spacing: 3; visible: editor.vertical
                                readonly property real iconSize: Math.max(2,Math.min(9,(parent.height-28)/5,parent.width-4))
                                Repeater { model: 5; Rectangle { width: parent.iconSize; height: width; radius: 3; color: editor.accent } }
                            }
                        }
                        Repeater {
                            model: [-1,1]
                            EditorUI.ResizeGrip {
                                required property int modelData
                                objectName: modelData < 0 ? "taskbarResizeStart" : "taskbarResizeEnd"
                                referenceItem: desktopPreview
                                mirrored: editor.vertical ? (modelData < 0) === (panel.location === PlasmaCore.Types.LeftEdge) : (modelData < 0) === (panel.location === PlasmaCore.Types.TopEdge)
                                description: i18nd("monet","Resize taskbar")
                                x: previewBar.x + (editor.vertical ? (panel.location === PlasmaCore.Types.LeftEdge ? previewBar.width : 0) : (modelData < 0 ? 0 : previewBar.width)) - width/2
                                y: previewBar.y + (editor.vertical ? (modelData < 0 ? 0 : previewBar.height) : (panel.location === PlasmaCore.Types.TopEdge ? previewBar.height : 0)) - height/2
                                property int startLength
                                property int startThickness
                                property int startOffset
                                property real startScale
                                onStarted: {
                                    startLength = editor.shownLength; startThickness = editor.draftSize
                                    startScale = previewBar.lengthScale
                                    startOffset = panel.lengthMode === Panel.FillAvailable ? 0 : panel.offset
                                    editor.draftLength = startLength; editor.draftOffset = startOffset
                                    editor.resizeAlignment = panel.lengthMode === Panel.FillAvailable ? Qt.AlignCenter : panel.alignment
                                    editor.resizingBar = true
                                }
                                onDragged: (dx,dy) => {
                                    const along = editor.vertical ? dy : dx
                                    const inward = editor.vertical ? (panel.location === PlasmaCore.Types.LeftEdge ? dx : -dx) : (panel.location === PlasmaCore.Types.TopEdge ? dy : -dy)
                                    const centered = editor.resizeAlignment === Qt.AlignCenter
                                    const movingOffset = !centered && (editor.resizeAlignment === Qt.AlignLeft ? modelData < 0 : modelData > 0)
                                    const maximum = centered ? editor.screenLength-2*Math.abs(startOffset) : movingOffset ? startLength+startOffset : editor.screenLength-startOffset
                                    editor.draftLength = Math.round(Math.max(Math.min(240,maximum),Math.min(maximum,startLength+modelData*along/startScale*(centered ? 2 : 1))))
                                    editor.draftOffset = movingOffset ? startOffset+startLength-editor.draftLength : startOffset
                                    editor.lengthEdited = true
                                    editor.selectSize(startThickness+inward/previewBar.thicknessScale)
                                }
                                onFinished: editor.applyBarSize()
                                onCanceled: { editor.resizingBar = false; editor.lengthEdited = false; editor.draftSize = panel.thickness }
                                onNudged: (dx,dy) => { editor.previewBarSize(editor.shownLength+(editor.vertical ? dy : dx),editor.draftSize+(editor.vertical ? dx : -dy)); editor.applyBarSize() }
                            }
                        }
                    }
                    Hint { text: i18nd("monet","Drag a corner to change length and thickness. Release to apply; Esc cancels."); font.pixelSize: 12 }
                    RowLayout {
                        Layout.fillWidth: true
                        ColumnLayout {
                            Layout.fillWidth: true
                            C.Label { text: i18nd("monet", "Length (px)"); opacity: 0.7; font.pixelSize: 12 }
                            C.TextField {
                                id: exactLength
                                objectName: "panelExactLength"
                                Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 1
                                Accessible.name: i18nd("monet", "Bar length in pixels")
                                inputMethodHints: Qt.ImhDigitsOnly
                                validator: IntValidator { bottom: editor.minimumBarLength; top: editor.maximumBarLength }
                                text: String(editor.shownLength)
                                onTextEdited: if (acceptableInput) { editor.draftLength = Number(text); editor.lengthEdited = true }
                                onAccepted: if (acceptableInput && exactThickness.acceptableInput) editor.applyBarSize()
                                onEditingFinished: if (!acceptableInput) text = String(editor.shownLength)
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            C.Label { text: editor.vertical ? i18nd("monet", "Width (px)") : i18nd("monet", "Height (px)"); opacity: 0.7; font.pixelSize: 12 }
                            C.TextField {
                                id: exactThickness
                                objectName: "panelExactThickness"
                                Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 1
                                Accessible.name: i18nd("monet", "Bar size in pixels")
                                inputMethodHints: Qt.ImhDigitsOnly
                                validator: IntValidator { bottom: editor.minimumSize; top: editor.maximumSize }
                                text: String(editor.draftSize)
                                onTextEdited: if (acceptableInput) editor.selectSize(Number(text))
                                onAccepted: if (acceptableInput && exactLength.acceptableInput) editor.applyBarSize()
                                onEditingFinished: if (!acceptableInput) text = String(editor.draftSize)
                            }
                        }
                        Choice {
                            objectName: "panelExactApply"
                            Layout.fillWidth: false; Layout.alignment: Qt.AlignBottom
                            text: i18nd("monet", "Apply")
                            primary: true
                            enabled: exactLength.acceptableInput && exactThickness.acceptableInput && (editor.lengthEdited || editor.draftSize !== panel.thickness)
                            onClicked: editor.applyBarSize()
                        }
                    }
                    RowLayout {
                        Choice { objectName: "panelCenterBar"; text: i18nd("monet","Center bar"); checked: panel.alignment === Qt.AlignCenter && panel.offset === 0; onClicked: editor.alignBar(Qt.AlignCenter) }
                        Choice { objectName: "panelCenterApps"; text: i18nd("monet","Center app icons"); visible: editor.iconsAvailable; enabled: !editor.busy; checked: editor.icons === "center"; onClicked: editor.requestIcons("center") }
                    }
                    }
                }

                EditorPage {
                    number: 0
                    sourceComponent: ColumnLayout {
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
                                    onClicked: editor.alignBar(modelData.alignment)
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
                        Hint { visible: panel.lengthMode === Panel.Custom; text: i18nd("monet", "Custom length. Drag the preview corners to reshape, or choose a bar shape above to reset.") }
                        Hint { visible: editor.problem !== ""; text: editor.problem }
                    }
                }

                EditorPage {
                    number: 1
                    sourceComponent: ColumnLayout {
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
                            wheelEnabled: false;
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
                                onAccepted: editor.applySize(sizeInput.text)
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
                                onClicked: editor.applySize(sizeInput.text)
                            }
                        }

                        Heading { text: i18nd("monet", "Bar length") }
                        C.Slider {
                            objectName: "panelLengthSlider"; Layout.fillWidth: true
                            Accessible.name: i18nd("monet", "Bar length")
                            from: editor.minimumBarLength; to: editor.maximumBarLength; stepSize: 2
                            wheelEnabled: false; value: editor.shownLength
                            onMoved: editor.previewBarSize(value,editor.draftSize)
                            onPressedChanged: if (!pressed && editor.lengthEdited) editor.applyBarSize()
                            Keys.onReleased: event => { if ([Qt.Key_Left,Qt.Key_Right,Qt.Key_Home,Qt.Key_End,Qt.Key_PageUp,Qt.Key_PageDown].includes(event.key) && editor.lengthEdited) editor.applyBarSize() }
                        }
                        Hint { text: i18nd("monet", "Length changes apply when you release the slider. Choose Compact dock on Layout to fit the bar to its contents.") }

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
                }

                EditorPage {
                    number: 2
                    sourceComponent: ColumnLayout {
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
            wheelEnabled: false;
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
                }

                EditorPage {
                    number: 3
                    sourceComponent: ColumnLayout {
                        EditorUI.NotchEditor {
                            Layout.fillWidth: true
                            notchState: editor.notchState
                            busy: editor.notchBusy
                            onRequested: command => editor.requestNotch(command)
                        }
                        Hint { visible: !!editor.notchProblem; text: editor.notchProblem }
                    }
                }

                EditorPage {
                    number: 4
                    sourceComponent: ColumnLayout {
                        spacing: 10
                        Heading { text: i18nd("monet","Add panel") }
                        ActionRow {
                            objectName: "panelAddNotch"; icon.name: "view-media-visualization"
                            text: i18nd("monet","Top-center notch")
                            detail: i18nd("monet","Open music, timers and quick controls from the top of this screen.")
                            enabled: !editor.notchBusy && !editor.addingPanel
                            onClicked: editor.requestNotch("add")
                        }
                        ActionRow {
                            objectName: "panelAddHome"; icon.name: "preferences-desktop"
                            text: i18nd("monet","Home Bar")
                            detail: i18nd("monet","Start with the app menu, taskbar, quick settings and clock.")
                            enabled: !editor.addingPanel && !editor.notchBusy
                            onClicked: editor.addPanel("home")
                        }
                        ActionRow {
                            objectName: "panelAddEmpty"; icon.name: "list-add"
                            text: i18nd("monet","Empty panel")
                            detail: i18nd("monet","Start with an empty bar and add your own widgets.")
                            enabled: !editor.addingPanel && !editor.notchBusy
                            onClicked: editor.addPanel("empty")
                        }
                        Hint {
                            text: editor.addingPanel ? i18nd("monet","Adding panel…") : editor.notchProblem || editor.addStatus
                            visible: !!text
                            Accessible.role: Accessible.StaticText
                        }
                        Choice {
                            visible: editor.addedPanel > 0
                            objectName: "configureNewPanel"; text: i18nd("monet","Customize new panel")
                            onClicked: panelCreator.connectSource("@LIBEXECDIR@/monet-quick panel-configure " + editor.addedPanel)
                        }
                    }
                }

                ColumnLayout {
                    id: advanced
                    visible: editor.showAdvanced
                    Layout.fillWidth: true
                    spacing: 14
                    Heading { text: i18nd("monet", "More ways to arrange your bar") }
                    Hint { text: i18nd("monet", "Fine-tune spacing, move to another display, or add room between widgets.") }
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: placementOptions.implicitHeight + 32
                        radius: 16; color: Qt.rgba(0.5,0.5,0.5,0.07)
                        ColumnLayout {
                            id: placementOptions
                            anchors.fill: parent; anchors.margins: 16; spacing: 10
                            Heading { text: i18nd("monet", "Position and spacing") }
                            C.Label { text: i18nd("monet", "Display"); Layout.fillWidth: true }
                            C.ComboBox {
                                id: displayChoice
                                objectName: "panelDisplay"
                                Layout.fillWidth: true; Layout.minimumWidth: 0
                                model: Application.screens
                                textRole: "name"
                                wheelEnabled: false
                                currentIndex: Math.max(0, Array.from(Application.screens).findIndex(s => s.name === panel.screenToFollow?.name))
                                onActivated: index => editor.panelAction("screen-" + index)
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                C.Label { text: i18nd("monet", "Offset from alignment"); wrapMode: Text.WordWrap; Layout.fillWidth: true }
                                C.SpinBox {
                                    objectName: "panelAdvancedOffset"
                                    from: 0; to: Math.max(0, editor.screenLength - editor.shownLength)
                                    value: panel.offset
                                    editable: true; wheelEnabled: false
                                    onValueModified: { panel.offset = value; editor.schedulePlacement() }
                                }
                            }
                            C.CheckBox {
                                objectName: "panelFloatingWidgets"
                                text: i18nd("monet", "Float widgets individually")
                                checked: panel.floatingApplets
                                onToggled: { panel.floatingApplets = checked; if (checked) panel.floating = false }
                            }
                            RowLayout {
                                Layout.fillWidth: true
                                Choice { objectName: "panelAddSpacer"; text: i18nd("monet", "Add flexible space"); onClicked: editor.panelAction("spacer") }
                                Choice { objectName: "panelAddSeparator"; text: i18nd("monet", "Add separator"); onClicked: editor.panelAction("separator") }
                            }
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: shortcutOptions.implicitHeight + 32
                        radius: 16; color: Qt.rgba(0.5,0.5,0.5,0.07)
                        ColumnLayout {
                            id: shortcutOptions
                            anchors.fill: parent; anchors.margins: 16; spacing: 10
                            Heading { text: i18nd("monet", "Keyboard access") }
                            Hint { text: i18nd("monet", "Choose a shortcut to move keyboard focus to this bar.") }
                            KeySequenceItem {
                                objectName: "panelFocusShortcut"
                                Layout.alignment: Qt.AlignLeft
                                patterns: ShortcutPattern.Modifier | ShortcutPattern.ModifierAndKey
                                keySequence: plasmoid.globalShortcut
                                onCaptureFinished: plasmoid.globalShortcut = keySequence
                            }
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: manageOptions.implicitHeight + 32
                        radius: 16; color: Qt.rgba(0.5,0.5,0.5,0.07)
                        ColumnLayout {
                            id: manageOptions
                            anchors.fill: parent; anchors.margins: 16; spacing: 10
                            Heading { text: i18nd("monet", "Manage this bar") }
                            Choice {
                                objectName: "panelDuplicate"
                                text: i18nd("monet", "Duplicate bar")
                                onClicked: panel.clonePanelTo(panel.location, panel.screenToFollow)
                            }
                            Choice {
                                objectName: "panelRemove"
                                text: i18nd("monet", "Remove bar")
                                onClicked: { plasmoid.internalAction("remove")?.trigger(); configDialog.close() }
                            }
                            Hint { visible: !!editor.advancedStatus; text: editor.advancedStatus }
                        }
                    }
                }
            }
        }

        RowLayout {
            Layout.fillWidth: true
            Choice { objectName: "panelAddPage"; text: i18nd("monet","Add panel"); onClicked: editor.selectPage(4) }
            Choice { objectName: "panelAddWidgets"; visible: !editor.notchPanel; text: i18nd("monet","Add widgets…"); onClicked: { configDialog.close(); configDialog.showAddWidgetDialog() } }
            Choice {
                objectName: "panelAdvanced"
                text: editor.showAdvanced ? i18nd("monet", "Back") : i18nd("monet", "Advanced…")
                onClicked: editor.toggleAdvanced()
            }
        }
    }
}
