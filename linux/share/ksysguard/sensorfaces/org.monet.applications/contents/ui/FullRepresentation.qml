import QtQuick
import "../../../org.monet.performance/contents/ui" as Performance
import "file:///usr/share/ksysguard/sensorfaces/org.kde.ksysguard.applicationstable/contents/ui" as Native

// KDE reparents contentItem into its page; the face itself has no window.
// Preserve KDE's table, actions, selection and column settings. Its process
// model follows item visibility, which otherwise remains true when minimized.
Native.FullRepresentation {
    id: face
    Performance.WindowActivity { id: activity; item: face.contentItem }
    readonly property bool windowVisible: activity.windowVisible
    Binding {
        target: face.contentItem
        property: "visible"
        value: face.visible && face.windowVisible
        restoreMode: Binding.RestoreBindingOrValue
    }
}
