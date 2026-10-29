/* Mouse users scroll with a wheel, touchpad or scrollbar. Leave unhandled
 * left-button presses to the window background; touch flicking still works.
 * Older Qt versions retain their existing flick behavior. Where WheelHandler
 * is present, its filterMouseEvents must also be off on Qt 6.9+: otherwise it
 * consumes blank presses before they can reach MonetWindow's background. */
import QtQuick

QtObject {
    required property var view
    Component.onCompleted: {
        if ("acceptedButtons" in view) view.acceptedButtons = Qt.NoButton
    }
}
