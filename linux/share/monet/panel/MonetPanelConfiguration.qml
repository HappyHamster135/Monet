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
    property bool iconsAvailable: false
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
        function onLocationChanged() { editor.schedulePlacement(true) }
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
                if (!event.isAutoRepeat) item.clicked()
                event.accepted = true
            }
        }
    }

    function requestIcons(alignment) {
        busy = true
        runner.connectSource("@LIBEXECDIR@/monet-quick panel-icons " + plasmoid.id + (alignment ? " " + alignment : ""))
    }
    Component.onCompleted: requestIcons("")
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
                editor.problem = ""
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
                                {name: editor.vertical ? i18nd("monet", "Top") : i18nd("monet", "Start"), alignment: mirrored ? Qt.AlignRight : Qt.AlignLeft},
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
                            text: editor.vertical ? i18nd("monet", "Top") : i18nd("monet", "Start")
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
                    onActiveChanged: if (active) setSource(Qt.resolvedUrl("KdePanelConfiguration.qml"), {panelConfiguration: editor.panelConfiguration})
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
