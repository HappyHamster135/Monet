import QtQuick
import "../../../org.monet.performance/contents/ui" as Performance
import "file:///usr/share/ksysguard/sensorfaces/org.kde.ksysguard.applicationstable/contents/ui" as Native

// KDE reparents contentItem into its page; the face itself has no window.
// Preserve KDE's table, actions, selection and column settings. Its process
// model follows item visibility, which otherwise remains true when minimized.
// Monet adds each app's own name and what its windows show, and System (Apps).
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
    Apps {
        id: apps
        active: activity.active
    }
    // KDE's table is made with the face; a few tries in case it comes a moment later.
    Timer {
        id: attaching
        interval: 200
        repeat: true
        property int tries: 0
        running: true
        onTriggered: if (apps.attach(face.contentItem) || ++tries >= 25) stop()
    }
}
