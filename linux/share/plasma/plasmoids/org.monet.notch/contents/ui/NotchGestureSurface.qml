import QtQuick

MouseArea {
    required property var gestures
    anchors.fill: parent
    enabled: gestures?.enabled ?? false
    acceptedButtons: Qt.NoButton
    scrollGestureEnabled: true
    onWheel: event => {
        const used = gestures.scroll(event)
        // Qt Quick suppresses subsequent pixel-only updates after an accepted
        // wheel event. These two fixed surfaces have no scrollable parent.
        event.accepted = used && event.phase === Qt.NoScrollPhase
    }
}
