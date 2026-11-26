import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C
import org.kde.kirigami as K

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

    property int mode: 0 // Timer, focus, stopwatch
    readonly property bool stopwatch: mode === 2
    readonly property bool inSession: !stopwatch && timer.active
    readonly property double watchElapsed: settings.watchElapsed + (watchStart ? Math.max(0, now - watchStart) : 0)
    readonly property int seconds: stopwatch ? Math.floor(watchElapsed / 1000)
        : inSession ? Math.ceil(timer.remaining(now) / 1000) : settings.timerMinutes * 60
    readonly property string phase: stopwatch ? i18n("Stopwatch")
        : timer.onBreak ? (timer.longBreak ? i18n("Long break") : i18n("Short break"))
        : inSession && settings.focus ? i18n("Focus session %1 of %2", Math.max(1, timer.round), settings.focusSessions)
        : mode === 1 ? i18n("Focus") : i18n("Timer")
    readonly property color amber: "#ffad53"
    Component.onCompleted: mode = timer.active ? Number(settings.focus || timer.onBreak) : watchStart || settings.watchElapsed ? 2 : 0
    onVisibleChanged: if (visible && timer?.active && !stopwatch) mode = Number(settings.focus || timer.onBreak)
    function toggleWatch() {
        const stamp = Date.now()
        if (watchStart) {
            settings.watchElapsed += Math.max(0, stamp - watchStart)
            settings.watchStart = ""
        } else settings.watchStart = String(stamp)
    }
    component StepMark: Text {
        width: 30; height: parent.height
        horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        color: enabled ? "#eeeeef" : "#727278"; font.pixelSize: 18
    }
    component Stepper: C.SpinBox {
        id: spin
        from: 1; to: 1440; editable: true
        implicitWidth: 106; implicitHeight: 30
        leftPadding: 30; rightPadding: 30; topPadding: 0; bottomPadding: 0
        background: Rectangle {
            radius: 9; color: "#252527"
            border.width: spin.activeFocus ? 1 : 0; border.color: "#ffad53"
        }
        contentItem: TextInput {
            text: spin.displayText; font.pixelSize: 13; color: "#ffb669"; selectByMouse: true
            horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
            validator: spin.validator; readOnly: !spin.editable
            inputMethodHints: Qt.ImhDigitsOnly
        }
        up.indicator: StepMark { x: spin.mirrored ? 0 : spin.width - width; text: "+" }
        down.indicator: StepMark { x: spin.mirrored ? spin.width - width : 0; text: "−" }
    }
    ColumnLayout {
        width: page.availableWidth
        spacing: 9
        Item {
            id: modes
            objectName: "notchTimeModes"
            Layout.fillWidth: true; Layout.preferredHeight: 34
            Row {
                id: tabs
                anchors.fill: parent
                Repeater {
                    model: [i18n("Timer"), i18n("Focus"), i18n("Stopwatch")]
                    C.AbstractButton {
                        id: tab
                        required property int index
                        required property string modelData
                        width: tabs.width / 3; height: tabs.height
                        text: modelData; checked: page.mode === index
                        enabled: !page.timer.active || index === 2 || index === Number(page.settings.focus || page.timer.onBreak)
                        Accessible.role: Accessible.PageTab
                        onClicked: page.mode = index
                        background: Rectangle {
                            radius: 7; color: tab.hovered ? "#202023" : "transparent"
                            border.width: tab.visualFocus ? 1 : 0; border.color: "#9ecaff"
                        }
                        contentItem: Text {
                            text: tab.text; elide: Text.ElideRight; horizontalAlignment: Text.AlignHCenter
                            verticalAlignment: Text.AlignVCenter; font.pixelSize: 13; font.weight: Font.DemiBold
                            color: tab.checked ? "#f9f9fa" : tab.enabled ? "#aaaab0" : "#737379"
                        }
                    }
                }
            }
            Rectangle {
                width: Math.min(44, tabs.width / 3 - 4); height: 2; radius: 1
                y: parent.height - height
                x: (tabs.width / 3) * (page.mirrored ? 2.5 - page.mode : page.mode + 0.5) - width / 2
                color: page.amber
                Behavior on x { enabled: K.Units.longDuration > 1; NumberAnimation { duration: K.Units.longDuration; easing.type: Easing.OutCubic } }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true; spacing: 3
            Item { Layout.preferredHeight: 8 }
            Text {
                Layout.alignment: Qt.AlignRight; Layout.maximumWidth: page.availableWidth
                elide: Text.ElideRight
                text: page.inSession && page.timer.paused ? page.phase + " · " + i18n("Paused") : page.phase
                color: page.amber; font.pixelSize: 12; font.weight: Font.DemiBold
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 10
                MinuteRuler {
                    visible: !page.inSession && !page.stopwatch
                    Layout.fillWidth: true; Layout.minimumWidth: 0
                    minutes: page.settings.timerMinutes; onChosen: minutes => page.settings.timerMinutes = minutes
                }
                RowLayout {
                    visible: page.inSession || page.stopwatch
                    spacing: 6
                    IslandButton {
                        implicitWidth: 42; implicitHeight: 42; tint: page.amber; base: "#4a3220"
                        text: page.stopwatch ? (page.watchStart ? i18n("Pause stopwatch") : page.settings.watchElapsed ? i18n("Resume stopwatch") : i18n("Start"))
                            : page.timer.deadline ? i18n("Pause timer") : page.timer.waiting ? (page.timer.onBreak ? i18n("Start break") : i18n("Start next session")) : i18n("Resume timer")
                        icon.name: (page.stopwatch ? !!page.watchStart : !!page.timer.deadline) ? "media-playback-pause" : "media-playback-start"
                        onClicked: {
                            if (page.stopwatch) page.toggleWatch()
                            else if (page.timer.deadline) page.timer.pause(Date.now())
                            else page.timer.resume(Date.now())
                        }
                    }
                    IslandButton {
                        implicitWidth: 38; implicitHeight: 38
                        text: page.stopwatch ? i18n("Reset stopwatch") : i18n("Cancel")
                        icon.name: page.stopwatch ? "edit-reset" : "window-close"
                        onClicked: {
                            if (page.stopwatch) { page.settings.watchStart = ""; page.settings.watchElapsed = 0 }
                            else page.timer.cancel()
                        }
                    }
                }
                Item { visible: page.inSession || page.stopwatch; Layout.fillWidth: true }
                Text {
                    Layout.maximumWidth: page.availableWidth - (page.inSession || page.stopwatch ? 106 : 40)
                    text: page.formatDuration(page.seconds); color: page.amber
                    horizontalAlignment: Text.AlignRight; font.pixelSize: page.availableWidth < 300 ? 43 : 58
                    font.weight: Font.Light; font.features: ({"tnum": 1})
                    minimumPixelSize: 24; fontSizeMode: Text.HorizontalFit
                }
            }
            Rectangle {
                Layout.fillWidth: true; Layout.preferredHeight: 2; color: "#343032"
                Rectangle {
                    visible: page.inSession; height: parent.height; color: page.amber
                    width: parent.width * Math.min(1, page.seconds / Math.max(1, page.timer.phaseMinutes * 60))
                }
            }
        }
        GridLayout {
            Layout.fillWidth: true
            columns: page.availableWidth < 400 ? 1 : 2
            columnSpacing: 5; rowSpacing: 4
            RowLayout {
                visible: !page.stopwatch
                spacing: 5
                IslandButton {
                    caption: true; prominent: true
                    visible: !page.inSession && !page.stopwatch
                    text: i18n("Start"); onClicked: page.timer.start(page.mode === 1, Date.now())
                }
                C.Label { visible: minutesBox.visible; text: i18n("Minutes"); color: "#bdbdc2" }
                Stepper {
                    id: minutesBox
                    visible: !page.inSession
                    value: page.settings.timerMinutes; Accessible.name: i18n("Minutes")
                    onValueModified: page.settings.timerMinutes = value
                }
            }
            RowLayout {
                Layout.fillWidth: true; spacing: 5
                Item { Layout.fillWidth: true }
                IslandButton {
                    id: awakeButton; caption: true
                    visible: page.offerAwake; text: i18n("Keep awake"); onClicked: page.awakeRequested()
                }
                IslandButton {
                    id: options; caption: true; checkable: true
                    visible: page.mode === 1 && !page.timer.active
                    text: i18n("Focus options")
                }
            }
        }
        C.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; visible: !!text; text: page.message || page.timer.completion }
        IslandButton {
            caption: true; visible: !!page.timer.completion; text: i18n("Dismiss"); onClicked: page.timer.dismiss()
        }
        GridLayout {
            Layout.fillWidth: true
            Layout.maximumWidth: page.availableWidth
            visible: options.visible && options.checked
            columns: 2
            C.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: i18n("Focus sessions") }
            Stepper {
                from: 1; to: 24; editable: true; value: page.settings.focusSessions
                Accessible.name: i18n("Focus sessions")
                onValueModified: page.settings.focusSessions = value
            }
            C.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: i18n("Short break (minutes)") }
            Stepper {
                value: page.settings.shortBreakMinutes; Accessible.name: i18n("Short break (minutes)")
                onValueModified: page.settings.shortBreakMinutes = value
            }
            C.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: i18n("Long break (minutes)") }
            Stepper {
                value: page.settings.longBreakMinutes; Accessible.name: i18n("Long break (minutes)")
                onValueModified: page.settings.longBreakMinutes = value
            }
            C.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; text: i18n("Sessions per long break") }
            Stepper {
                from: 1; to: 24; editable: true; value: page.settings.longBreakEvery
                Accessible.name: i18n("Sessions per long break")
                onValueModified: page.settings.longBreakEvery = value
            }
        }
    }
}
