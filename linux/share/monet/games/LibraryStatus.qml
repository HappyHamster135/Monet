/* Shared loading and recovery, with the last working library kept underneath. */
import QtQuick
import QtQuick.Layouts

RowLayout {
    id: status
    property var tone
    property bool busy: false
    property bool failed: false
    property bool loaded: false
    property bool retryWithKeys: false
    signal retry()
    signal recovered()
    visible: !loaded || failed
    height: visible ? implicitHeight : 0
    spacing: 12

    function finish(success) {
        if (retryWithKeys) {
            retryWithKeys = false
            if (success) recovered()
            else retryButton.forceActiveFocus()
        }
    }

    Text {
        Layout.fillWidth: true
        text: status.busy ? (status.loaded ? i18n("Refreshing…") : i18n("Loading…"))
            : i18n("Couldn't load the library. Try again.")
        color: status.tone.dim
        font.pixelSize: 14
        wrapMode: Text.Wrap
        Accessible.role: status.failed && !status.busy ? Accessible.AlertMessage : Accessible.StaticText
    }
    Pill {
        id: retryButton
        objectName: "libraryRetry"
        tone: status.tone
        text: i18n("Try again")
        visible: status.failed
        enabled: !status.busy
        onClicked: {
            status.retryWithKeys = activeFocus
            status.retry()
        }
    }
}
