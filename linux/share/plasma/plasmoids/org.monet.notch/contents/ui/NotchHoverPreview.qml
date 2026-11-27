import QtQuick

// Hover is temporary. Clicking adopts the open surface; dismissing it explicitly
// requires leaving the notch before hover can open it again.
Item {
    id: preview
    property bool allowed: true
    property bool opened: false
    property bool overPill: false
    property bool overPreview: false
    property bool held: false
    property bool previewing: false
    property bool suppressed: false
    readonly property bool underPointer: overPill || overPreview
    signal requested()
    signal dismissed()
    signal adopted()

    function adopt() {
        if (!previewing) return
        previewing = false
        adopted()
    }
    function cancel() {
        previewing = false
        suppressed = underPointer
    }
    onUnderPointerChanged: if (!underPointer) suppressed = false
    onOpenedChanged: if (!opened) cancel()
    onAllowedChanged: if (!allowed && previewing) { cancel(); dismissed() }
    Timer {
        interval: 320
        running: preview.allowed && !preview.opened && preview.overPill && !preview.suppressed
        onTriggered: { preview.previewing = true; preview.requested() }
    }
    Timer {
        interval: 420
        running: preview.previewing && preview.opened && !preview.underPointer && !preview.held
        onTriggered: { preview.cancel(); preview.dismissed() }
    }
}
