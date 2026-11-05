/* SPDX-License-Identifier: GPL-2.0-or-later */
import QtQuick

// Attach directly to the native ToolTipArea: it consumes events before an
// ancestor handler sees them. Share the latest hovered task for neighbour motion.
// This handler takes no grabs and does not block the area's own hover handling.
HoverHandler {
    id: tracker
    property bool trackingEnabled: true
    property QtObject coordinator: null
    readonly property bool hovering: trackingEnabled && hovered
    readonly property point position: point.position
    enabled: trackingEnabled
    target: null
    blocking: false

    onHoveredChanged: {
        if (!coordinator) return
        if (hovered) coordinator.current = tracker
        else if (coordinator.current === tracker) coordinator.current = null
    }
    onPointChanged: { if (hovered && coordinator) coordinator.current = tracker }
    Component.onDestruction: { if (coordinator && coordinator.current === tracker) coordinator.current = null }
}
