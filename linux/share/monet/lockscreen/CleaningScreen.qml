// The real locker owns the input surfaces; its normal unlock UI loads afterwards.
import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Rectangle {
    id: cleaning
    color: "#111413"
    focus: true
    property int seconds: Math.max(0, Math.ceil((root.cleaningUntil - Date.now()) / 1000))
    property int presses: 0
    property bool enterDown: false
    Component.onCompleted: forceActiveFocus()

    Timer {
        interval: 1000; running: true; repeat: true
        onTriggered: {
            // Keep displays together after an early finish. Never lengthen a
            // running interval if the wall clock is adjusted backwards.
            request.sync()
            cleaning.seconds = Math.min(cleaning.seconds - 1, Math.ceil((root.cleaningUntil - Date.now()) / 1000))
            if (cleaning.seconds <= 0 || Number(request.value("deadline", 0)) !== root.cleaningUntil)
                root.finishCleaning()
        }
    }
    Timer { id: sequence; interval: 6000; onTriggered: { cleaning.presses = 0; cleaning.enterDown = false } }
    Keys.onPressed: event => {
        event.accepted = true
        if (event.isAutoRepeat) return
        enterDown = (event.key === Qt.Key_Return || event.key === Qt.Key_Enter) && !(event.modifiers & ~Qt.KeypadModifier)
        if (!enterDown) { presses = 0; sequence.stop() }
    }
    Keys.onReleased: event => {
        event.accepted = true
        if (event.isAutoRepeat || (event.key !== Qt.Key_Return && event.key !== Qt.Key_Enter) || !enterDown) return
        enterDown = false
        if (++presses >= 5) root.finishCleaning()
        else sequence.restart()
    }
    MouseArea {
        anchors.fill: parent; acceptedButtons: Qt.AllButtons
        onWheel: event => event.accepted = true
    }
    ColumnLayout {
        anchors.centerIn: parent
        width: Math.min(430, parent.width - 32)
        spacing: 12
        Kirigami.Icon {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 36; Layout.preferredHeight: 36
            source: "input-keyboard"; isMask: true; color: "#a8ddc8"
            Accessible.ignored: true
        }
        C.Label {
            Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter
            color: "#f3f3ec"; font.family: "Fraunces 72pt SuperSoft"
            font.pointSize: Kirigami.Theme.defaultFont.pointSize * 1.9; wrapMode: Text.Wrap
            text: i18nd("monet", "Cleaning mode")
        }
        C.Label {
            Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter
            color: "#cecec7"; wrapMode: Text.Wrap
            text: cleaning.presses ? i18nd("monet", "Enter presses: %1 of 5", cleaning.presses)
                    : i18nd("monet", "Keyboard paused. Press Enter five times to finish early.")
        }
        C.Label {
            Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter
            color: "#f3f3ec"; font.bold: true
            text: i18nd("monet", "Cleaning ends in %1 s", Math.max(0, cleaning.seconds))
        }
        C.Button {
            id: finish
            Layout.alignment: Qt.AlignHCenter
            topPadding: 9; bottomPadding: 9; leftPadding: 20; rightPadding: 20
            text: i18nd("monet", "Finish cleaning")
            background: Rectangle {
                radius: height / 2
                color: finish.down ? "#245448" : finish.hovered ? "#3c7569" : "#305f55"
                border.color: "#70968c"
            }
            contentItem: C.Label {
                text: finish.text; textFormat: Text.PlainText; color: "#ffffff"
                horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            }
            focusPolicy: Qt.NoFocus
            onClicked: root.finishCleaning()
        }
    }
}
