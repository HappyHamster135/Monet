import QtQuick
import QtQuick.Controls as C
import org.kde.kirigami as K
import "IslandLayout.js" as IslandLayout

Item {
    id: gridView
    required property var entries
    property string lastSection: ""
    property var detailFor: null
    property bool motion: true
    signal selected(string key)
    signal previewRequested(string key)

    readonly property int rows: 3
    // On narrow screens keep all enabled sections reachable within two pages.
    readonly property int columns: Math.max(IslandLayout.columns(width), Math.ceil(entries.length / (2 * rows)))
    readonly property int capacity: rows * columns
    readonly property int pageCount: Math.ceil(entries.length / capacity)
    property real pull: 0
    onMotionChanged: if (!motion) pull = 0
    onVisibleChanged: if (!visible) pull = 0
    property int currentPage: 0
    onPageCountChanged: currentPage = Math.min(currentPage, Math.max(0, pageCount - 1))

    function focusTile(index, reason) {
        const i = Math.max(0, Math.min(entries.length - 1, index))
        pull = 0
        currentPage = Math.floor(i / capacity)
        tiles.itemAt(i)?.forceActiveFocus(reason)
    }
    function focusFirst() {
        focusTile(entries.findIndex(entry => entry.key === lastSection), Qt.OtherFocusReason)
    }
    function turnTo(page, reason) {
        if (page >= 0 && page < pageCount && page !== currentPage)
            focusTile(page * capacity, reason)
    }

    Item {
        id: viewport
        anchors.fill: parent
        anchors.rightMargin: dots.visible ? dots.width : 0
        clip: true

        Grid {
            id: tilesGrid
            width: parent.width
            columns: gridView.columns
            spacing: IslandLayout.gap
            readonly property real destination: Math.max(0, Math.min(gridView.pageCount - 1,
                gridView.currentPage + gridView.pull / Math.max(1, viewport.height + spacing)))
            property real shownPage: 0
            onDestinationChanged: shownPage = destination
            readonly property real boundedPage: Math.max(0, Math.min(gridView.pageCount - 1, shownPage))
            y: -boundedPage * (viewport.height + spacing)
            Behavior on shownPage {
                enabled: gridView.motion && gridView.pageCount > 1
                onEnabledChanged: if (!enabled) tilesGrid.shownPage = tilesGrid.destination
                IslandSlide { id: slide; duration: IslandLayout.slideDuration(K.Units.longDuration) }
            }
            Repeater {
                id: tiles
                model: gridView.entries
                IslandButton {
                    id: tile
                    required property var modelData
                    required property int index
                    readonly property bool onPage: Math.floor(index / gridView.capacity) === gridView.currentPage
                    tile: true
                    width: Math.max(1, (viewport.width - (gridView.columns - 1) * IslandLayout.gap) / gridView.columns)
                    height: Math.max(1, (viewport.height - (gridView.rows - 1) * IslandLayout.gap) / gridView.rows)
                    focusPolicy: onPage ? Qt.StrongFocus : Qt.NoFocus
                    Accessible.ignored: !onPage
                    detail: gridView.detailFor ? gridView.detailFor(modelData.key) : ""
                    text: modelData.label
                    icon.name: modelData.icon
                    tint: modelData.color
                    objectName: "island-section-" + modelData.key
                    Accessible.description: [detail, modelData.key === gridView.lastSection ? i18n("Selected") : ""].filter(Boolean).join(" · ")
                    Text {
                        visible: tile.modelData.key === gridView.lastSection
                        anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 7
                        text: "✓"; color: "#c4c5cc"; font.pixelSize: 11
                        Accessible.ignored: true
                    }
                    onHoveredChanged: if (hovered && onPage && !slide.running) gridView.previewRequested(modelData.key)
                    onVisualFocusChanged: if (visualFocus) gridView.previewRequested(modelData.key)
                    onClicked: if (onPage) gridView.selected(modelData.key)
                    Keys.onPressed: event => {
                        const delta = event.key === Qt.Key_Left ? -1 : event.key === Qt.Key_Right ? 1 :
                            event.key === Qt.Key_Up ? -gridView.columns : event.key === Qt.Key_Down ? gridView.columns : 0
                        if (delta) gridView.focusTile(index + delta, Qt.TabFocusReason)
                        else if (event.key === Qt.Key_PageUp || event.key === Qt.Key_PageDown)
                            gridView.turnTo(gridView.currentPage + (event.key === Qt.Key_PageDown ? 1 : -1), Qt.TabFocusReason)
                        else return
                        event.accepted = true
                    }
                }
            }
        }
        DragHandler {
            target: null
            enabled: gridView.pageCount > 1
            acceptedDevices: PointerDevice.TouchScreen
            xAxis.enabled: false
            property bool turned: false
            onActiveChanged: {
                turned = false
                if (!active) gridView.pull = 0
            }
            onActiveTranslationChanged: {
                if (!active || turned) return
                if (Math.abs(activeTranslation.y) < 32) {
                    gridView.pull = gridView.motion ? -activeTranslation.y : 0
                } else {
                    gridView.pull = 0
                    turned = true
                    gridView.turnTo(activeTranslation.y < 0 ? 1 : 0, Qt.OtherFocusReason)
                }
            }
        }
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.NoButton
        enabled: gridView.pageCount > 1
        scrollGestureEnabled: true
        property real travel: 0
        property real lastWheelTime: 0
        property bool turned: false
        onWheel: event => {
            const phased = event.phase !== Qt.NoScrollPhase
            // Qt can suppress later pixel-only updates after an accepted event.
            // The chooser has no scrolling ancestor that needs these phases.
            event.accepted = !phased
            if (event.phase === Qt.ScrollMomentum) {
                gridView.pull = 0
                return
            }
            const now = Date.now()
            if (event.phase === Qt.ScrollBegin || event.phase === Qt.ScrollEnd || (!phased && now - lastWheelTime > 300)) {
                travel = 0
                gridView.pull = 0
                turned = false
            }
            lastWheelTime = now
            if (event.phase === Qt.ScrollEnd || (phased && turned)) return
            const pixels = event.pixelDelta
            const precise = pixels.x !== 0 || pixels.y !== 0
            const delta = precise ? pixels : event.angleDelta
            if (!delta.y || Math.abs(delta.x) >= Math.abs(delta.y)) return
            if (travel * delta.y < 0) travel = 0
            travel += delta.y * (precise ? 1 : 0.25)
            if (Math.abs(travel) < 24) {
                if (phased && precise && gridView.motion) gridView.pull = -travel
            } else {
                gridView.pull = 0
                gridView.turnTo(travel < 0 ? 1 : 0, Qt.OtherFocusReason)
                travel = 0
                turned = phased
            }
        }
    }

    Column {
        id: dots
        anchors.verticalCenter: parent.verticalCenter
        anchors.right: parent.right
        width: 24
        visible: gridView.pageCount > 1
        Repeater {
            model: gridView.pageCount
            C.AbstractButton {
                id: dot
                required property int index
                objectName: "island-dot-" + index
                width: dots.width; height: 26
                hoverEnabled: true
                Accessible.name: i18n("Page %1 of %2", index + 1, gridView.pageCount)
                Accessible.role: Accessible.PageTab
                Accessible.selected: index === gridView.currentPage
                onClicked: gridView.turnTo(index, Qt.OtherFocusReason)
                Keys.onReturnPressed: click()
                contentItem: Item {
                    Rectangle {
                        anchors.centerIn: parent
                        width: 8; height: width; radius: width / 2
                        color: dot.hovered ? "#aaaab3" : "#66666d"
                        Rectangle {
                            anchors.fill: parent; radius: parent.radius; color: "#f5f5f7"
                            opacity: Math.max(0, 1 - Math.abs(dot.index - tilesGrid.boundedPage))
                        }
                        border.width: dot.visualFocus ? 1 : 0
                        border.color: "#a3ccff"
                    }
                }
            }
        }
    }
}
