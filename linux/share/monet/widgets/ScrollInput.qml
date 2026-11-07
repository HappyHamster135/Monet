/* Vertical scrolling shared by Monet's app panels and menu. Editors and other focused
 * controls handle their keys first; the view forwards unhandled page keys here.
 * Mouse/touchpad input stays in the panel under the pointer, with no polling. */
import QtQuick

WheelHandler {
    required property Flickable view
    signal scrollRequested()
    target: null
    acceptedDevices: PointerDevice.Mouse | PointerDevice.TouchPad

    function scrollTo(position) {
        scrollRequested()
        view.cancelFlick()
        const first = view.originY - view.topMargin
        const last = Math.max(first, view.originY + view.contentHeight - view.height + view.bottomMargin)
        view.contentY = Math.max(first, Math.min(last, position))
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
        const delta = page && event.angleDelta.y !== 0 ? event.angleDelta.y / 120 * view.height
            : event.pixelDelta.y !== 0 ? event.pixelDelta.y : event.angleDelta.y / 120 * 96
        scrollTo(view.contentY - delta)
        // Consume zero-delta begin/end too: Flickable must not restore its old
        // gesture origin after the final pixel update.
        event.accepted = true
    }
}
