import QtQuick

// Keep Plasma's panel editor and its live panel context, but position it like a
// floating inspector. The anchor is in screen coordinates, not on the bar.
Item {
    id: placement
    objectName: "panelEditorPlacement"
    required property QtObject host
    required property Item panelContent
    required property rect screenGeometry
    property real panelX: 0
    property real panelY: 0
    property real preferredX: screenGeometry.x + 32
    property real preferredY: screenGeometry.y + (screenGeometry.height - host.height) / 2
    readonly property real windowX: Math.max(screenGeometry.x + 12,
        Math.min(screenGeometry.x + screenGeometry.width - host.width - 12, preferredX))
    readonly property real windowY: Math.max(screenGeometry.y + 12,
        Math.min(screenGeometry.y + screenGeometry.height - host.height - 12, preferredY))
    parent: panelContent
    width: 0; height: 0
    // PanelConfigView chooses a direction when its panel moves. Compensate for
    // that direction so every edge resolves to the same floating window rect.
    x: windowX - panelX + (host.popupDirection === Qt.LeftEdge ? host.width + host.margin
        : host.popupDirection === Qt.RightEdge ? -host.margin : host.width / 2)
    y: windowY - panelY + (host.popupDirection === Qt.TopEdge ? host.height + host.margin
        : host.popupDirection === Qt.BottomEdge ? -host.margin : host.height / 2)
    Binding { target: placement.host; property: "floating"; value: true }
    Binding { target: placement.host; property: "visualParent"; value: placement }
    function moveTo(x, y) {
        preferredX = x
        preferredY = y
        updatePosition()
    }
    function updatePosition() {
        if (host.visible) {
            host.queuePositionUpdate()
            host.requestUpdate()
        }
    }
    onXChanged: updatePosition()
    onYChanged: updatePosition()
}
