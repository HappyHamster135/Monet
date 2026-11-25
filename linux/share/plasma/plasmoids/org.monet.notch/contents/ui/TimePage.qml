import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C
import org.kde.kirigami as Kirigami

TimeScrollView {
    id: page
    required property NotchTimer timer
    required property double now
    required property string message
    required property var formatDuration
    readonly property QtObject settings: timer.settings
    readonly property double watchStart: Number(settings.watchStart) || 0
    property bool offerAwake: false
    signal awakeRequested()
    function focusAwake() { awakeButton.forceActiveFocus(Qt.BacktabFocusReason) }

    component MinutesBox: C.SpinBox {
        from: 1
        to: 1440
        editable: true
    }
    ColumnLayout {
        id: content
        width: page.availableWidth
        spacing: Kirigami.Units.smallSpacing
        C.Label {
            Layout.alignment: Qt.AlignHCenter
            visible: page.timer.active
            text: page.timer.onBreak ? (page.timer.longBreak ? i18n("Long break") : i18n("Short break"))
                : page.settings.focus ? i18n("Focus session %1 of %2", Math.max(1, page.timer.round), page.timer.round ? page.settings.focusSessions : 1)
                : i18n("Timer")
        }
        C.Label {
            Layout.alignment: Qt.AlignHCenter
            font.pointSize: 23
            text: page.timer.active ? page.formatDuration(Math.ceil(page.timer.remaining(page.now) / 1000)) : i18n("Timer")
        }
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            visible: !page.timer.active
            C.Label { text: i18n("Minutes") }
            MinutesBox {
                value: page.settings.timerMinutes
                Accessible.name: i18n("Minutes")
                onValueModified: page.settings.timerMinutes = value
            }
        }
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            C.Button {
                id: primary
                text: !page.timer.active ? i18n("Start") : page.timer.deadline ? i18n("Pause")
                    : page.timer.paused ? i18n("Resume") : page.timer.onBreak ? i18n("Start break") : i18n("Start next session")
                onClicked: {
                    const now = Date.now()
                    if (!page.timer.active) page.timer.start(false, now)
                    else if (page.timer.deadline) page.timer.pause(now)
                    else page.timer.resume(now)
                }
            }
            C.Button {
                text: page.timer.active ? i18n("Cancel") : i18n("Focus")
                onClicked: {
                    if (page.timer.active) page.timer.cancel()
                    else page.timer.start(true, Date.now())
                    primary.forceActiveFocus(Qt.OtherFocusReason)
                }
            }
        }
        C.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            visible: text.length > 0
            text: page.message
        }
        C.ToolButton {
            id: options
            Layout.alignment: Qt.AlignHCenter
            visible: !page.timer.active
            text: i18n("Focus options")
            icon.name: checked ? "arrow-down" : "arrow-right"
            checkable: true
        }
        GridLayout {
            Layout.alignment: Qt.AlignHCenter
            Layout.maximumWidth: page.availableWidth
            visible: options.visible && options.checked
            columns: 2
            C.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: i18n("Focus sessions") }
            C.SpinBox {
                from: 1; to: 24; editable: true; value: page.settings.focusSessions
                Accessible.name: i18n("Focus sessions")
                onValueModified: page.settings.focusSessions = value
            }
            C.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: i18n("Short break (minutes)") }
            MinutesBox {
                value: page.settings.shortBreakMinutes; Accessible.name: i18n("Short break (minutes)")
                onValueModified: page.settings.shortBreakMinutes = value
            }
            C.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: i18n("Long break (minutes)") }
            MinutesBox {
                value: page.settings.longBreakMinutes; Accessible.name: i18n("Long break (minutes)")
                onValueModified: page.settings.longBreakMinutes = value
            }
            C.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: i18n("Sessions per long break") }
            C.SpinBox {
                from: 1; to: 24; editable: true; value: page.settings.longBreakEvery
                Accessible.name: i18n("Sessions per long break")
                onValueModified: page.settings.longBreakEvery = value
            }
        }
        C.Button {
            id: awakeButton
            Layout.alignment: Qt.AlignHCenter
            visible: page.offerAwake
            text: i18n("Keep awake")
            icon.name: "system-suspend-inhibited"
            onClicked: page.awakeRequested()
        }
        Kirigami.Separator { Layout.fillWidth: true }
        RowLayout {
            Layout.alignment: Qt.AlignHCenter
            C.Label { text: page.formatDuration((page.settings.watchElapsed + (page.watchStart ? Math.max(0, page.now - page.watchStart) : 0)) / 1000) }
            C.Button {
                text: page.watchStart ? i18n("Pause stopwatch") : page.settings.watchElapsed ? i18n("Resume stopwatch") : i18n("Stopwatch")
                onClicked: {
                    const now = Date.now()
                    if (page.watchStart) {
                        page.settings.watchElapsed += Math.max(0, now - page.watchStart)
                        page.settings.watchStart = ""
                    } else page.settings.watchStart = String(now)
                }
            }
            C.ToolButton {
                icon.name: "edit-reset"; Accessible.name: i18n("Reset stopwatch")
                onClicked: { page.settings.watchStart = ""; page.settings.watchElapsed = 0 }
            }
        }
    }
}
