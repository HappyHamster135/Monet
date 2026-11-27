import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C

C.Slider {
    id: timeline
    required property var page
    objectName: "notchPlaybackPosition"
    Layout.fillWidth: true; Layout.minimumWidth: 1; implicitHeight: 28
    from: 0; to: page.lengthMs; value: page.elapsed
    enabled: !!page.player?.canSeek && page.trackId.startsWith("/")
    live: false
    leftPadding: 5; rightPadding: 5
    background: Rectangle {
        x: timeline.leftPadding; y: (timeline.height - height) / 2
        width: timeline.availableWidth; height: timeline.pressed ? 6 : 4; radius: height / 2; color: "#4b4b50"
        Rectangle { width: parent.width * timeline.visualPosition; height: parent.height; radius: height / 2; color: "#eeeef2" }
    }
    handle: Rectangle {
        x: timeline.leftPadding + timeline.visualPosition * (timeline.availableWidth - width)
        y: (timeline.height - height) / 2; width: 10; height: 10; radius: 5; color: "white"
        visible: timeline.pressed || timeline.hovered || timeline.visualFocus
    }
    Accessible.name: i18n("Playback position")
    Accessible.description: page.formatDuration(page.elapsed / 1000) + " / " + page.formatDuration(to / 1000)
    Accessible.onIncreaseAction: if (enabled) page.seek(page.elapsed + 5000)
    Accessible.onDecreaseAction: if (enabled) page.seek(page.elapsed - 5000)
    property var pressedPlayer: null
    property string pressedTrack: ""
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Left || event.key === Qt.Key_Right) {
            page.seek(page.elapsed + ((event.key === Qt.Key_Right) !== mirrored ? 5000 : -5000))
        } else if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
            page.seek(event.key === Qt.Key_Home ? 0 : to)
        } else {
            return
        }
        event.accepted = true
    }
    onPressedChanged: {
        if (pressed) {
            forceActiveFocus(Qt.MouseFocusReason)
            pressedPlayer = page.player
            pressedTrack = page.trackId
        } else {
            if (visible && enabled && pressedPlayer && pressedPlayer === page.player && pressedTrack === page.trackId) {
                page.seek(position * to)
            }
            pressedPlayer = null
        }
    }
}
