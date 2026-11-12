/* Vertical scrolling shared by Monet's app panels and menu. Editors and other focused
 * controls handle their keys first; the view forwards unhandled page keys here.
 * Mouse/touchpad input stays in the panel under the pointer, with no polling. */
import QtQuick
import org.kde.kirigami as Kirigami

WheelHandler {
    id: input
    required property Flickable view
    signal scrollRequested()
    target: null
    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad

    property real animatedPosition: 0
    property bool applyingWheelPosition: false
    readonly property NumberAnimation wheelAnimation: NumberAnimation {
        target: input
        property: "animatedPosition"
        duration: Math.min(160, Kirigami.Units.longDuration)
        easing.type: Easing.OutCubic
    }

    // An external scroll (a scrollbar drag, focus reveal or page change)
    // takes over immediately. Only wheel events drive this animation.
    readonly property Connections viewChanges: Connections {
        target: input.view
        function onContentYChanged() {
            if (!input.applyingWheelPosition) input.stopWheelAnimation()
        }
        function onMovementStarted() { input.stopWheelAnimation() }
        function onVisibleChanged() {
            if (!input.view.visible) input.stopWheelAnimation()
        }
    }
    onAnimatedPositionChanged: {
        applyingWheelPosition = true
        view.contentY = boundedPosition(animatedPosition)
        applyingWheelPosition = false
    }

    function boundedPosition(position) {
        const first = view.originY - view.topMargin
        const last = Math.max(first, view.originY + view.contentHeight - view.height + view.bottomMargin)
        return Math.max(first, Math.min(last, position))
    }
    function stopWheelAnimation() {
        wheelAnimation.stop()
    }
    function scrollTo(position) {
        stopWheelAnimation()
        scrollRequested()
        view.cancelFlick()
        view.contentY = boundedPosition(position)
    }
    function scrollWheel(distance) {
        if (wheelAnimation.duration <= 1) {
            scrollTo(view.contentY + distance)
            return
        }
        scrollRequested()
        view.cancelFlick()
        const current = view.contentY
        const pending = wheelAnimation.running ? wheelAnimation.to - current : 0
        // Combine quick notches in the same direction. A reversal takes
        // effect from the visible position instead of queuing behind them.
        const destination = boundedPosition(current + distance + (pending * distance > 0 ? pending : 0))
        stopWheelAnimation()
        if (destination === current) return
        wheelAnimation.from = current
        wheelAnimation.to = destination
        wheelAnimation.start()
    }
    function key(event) {
        if (event.modifiers !== Qt.NoModifier) { event.accepted = false; return }
        switch (event.key) {
        case Qt.Key_Up: scrollTo(view.contentY - 96); break
        case Qt.Key_Down: scrollTo(view.contentY + 96); break
        case Qt.Key_PageUp: scrollTo(view.contentY - view.height); break
        case Qt.Key_PageDown: scrollTo(view.contentY + view.height); break
        case Qt.Key_Home: scrollTo(view.originY - view.topMargin); break
        case Qt.Key_End: scrollTo(view.originY + view.contentHeight); break
        default: event.accepted = false; return
        }
        event.accepted = true
    }
    onWheel: event => {
        // Preserve touchpad pixels; a mouse detent scrolls the usual 96px.
        // Keep horizontal gestures in their original handler.
        if (event.pixelDelta.x !== 0 && event.pixelDelta.y === 0
                || event.angleDelta.x !== 0 && event.angleDelta.y === 0) {
            event.accepted = false
            return
        }
        const page = event.modifiers & (Qt.ControlModifier | Qt.ShiftModifier)
        const notches = event.angleDelta.y / 120
        if (page && notches !== 0) scrollTo(view.contentY - notches * view.height)
        else if (event.pixelDelta.y !== 0) scrollTo(view.contentY - event.pixelDelta.y)
        else if (notches !== 0) scrollWheel(-notches * 96)
        // Consume zero-delta begin/end too: Flickable must not restore its old
        // gesture origin after the final pixel update.
        event.accepted = true
    }
}
