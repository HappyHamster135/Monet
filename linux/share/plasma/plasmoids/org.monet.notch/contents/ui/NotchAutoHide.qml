import QtQuick

// The owner supplies a fixed target covering the notch's normal position.
// Never shrink it or depend on a control whose visibility changes on hover.
// This changes presentation only, not panel geometry or keyboard focus.
Item {
    id: conceal
    property bool automatic: false
    property bool occupied: false
    readonly property bool hovered: pointer.hovered
    readonly property bool shown: !automatic || occupied || hovered || leaveDelay.running
    HoverHandler { id: pointer; blocking: false }

    onHoveredChanged: {
        if (hovered) leaveDelay.stop()
        else if (automatic) leaveDelay.restart()
    }
    onOccupiedChanged: {
        if (occupied) leaveDelay.stop()
        else if (automatic) leaveDelay.restart()
    }
    onAutomaticChanged: leaveDelay.stop()
    Timer { id: leaveDelay; interval: 600 }
}
