/* SPDX-License-Identifier: GPL-2.0-or-later */
import QtQuick

// Paint transforms only: task geometry, hit targets and drag/drop never move.
Item {
    id: motion
    property bool motionEnabled: true
    property bool hovering: false
    property real distance: 3
    property real iconHeight: 48
    property int duration: 150
    readonly property bool animate: motionEnabled && duration > 0
    property real amount: animate && hovering ? Math.pow(Math.max(0, 1 - Math.abs(distance) / 1.5), 2) : 0
    readonly property real iconScale: animate ? 0.94 + 0.16 * amount : 1
    readonly property real lift: animate ? Math.min(5, iconHeight * 0.08) * amount : 0
    Behavior on amount {
        enabled: motion.animate
        NumberAnimation { duration: motion.duration; easing.type: Easing.OutCubic }
    }
}
