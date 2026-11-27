import QtQuick
import QtQuick.Controls as C

Item {
    id: layer
    // Plasma sizes the content before its window. Qt can leave the controls
    // overlay at (-width/2, -height/2), moving menus above the visible notch.
    Binding {
        target: layer.C.Overlay.overlay
        property: "anchors.fill"
        value: layer.Window.window?.contentItem ?? null
    }
}
