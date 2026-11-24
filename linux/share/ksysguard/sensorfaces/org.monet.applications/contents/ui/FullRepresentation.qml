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
    // Attach as soon as the native table is constructed. A delayed face can
    // still finish loading after this event-loop turn.
    function attachTable() {
        if (!apps.attach(face.contentItem) && ++attaching.tries < 25) attaching.restart()
    }
    Component.onCompleted: Qt.callLater(attachTable)
    Timer {
        id: attaching
        interval: 200
        property int tries: 0
        onTriggered: face.attachTable()
    }
}
