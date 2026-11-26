import QtQuick
import org.kde.layershell as Layer

QtObject {
    required property var target
    readonly property QtObject placement: target.Layer.Window
    Component.onCompleted: {
        placement.scope = "monet-notch-tool"
        placement.anchors = Layer.Window.AnchorTop | Layer.Window.AnchorLeft
        placement.layer = Layer.Window.LayerOverlay
        placement.exclusionZone = -1
        placement.activateOnShow = true
        placement.keyboardInteractivity = Layer.Window.KeyboardInteractivityOnDemand
    }
}
