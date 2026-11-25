import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C
import org.kde.kirigami as Kirigami

TimeScrollView {
    id: page
    required property NotchAwake awake
    signal backRequested()
    function focusBack() { back.forceActiveFocus(Qt.TabFocusReason) }
    Component.onCompleted: awake.refresh()

    // The next occurrence in the service's 24-hour window. Walking elapsed
    // minutes also handles missing and repeated local times on DST weekends.
    function nextEnd(now, hour, minute) {
        const first = Math.floor(now / 60000) * 60000 + 60000
        const date = new Date(first)
        for (let t = first; t <= now + 86400000; t += 60000) {
            date.setTime(t)
            if (date.getHours() === hour && date.getMinutes() === minute) return t
        }
        return 0
    }
    ColumnLayout {
        width: page.availableWidth
        spacing: Kirigami.Units.smallSpacing
        RowLayout {
            C.ToolButton {
                id: back
                icon.name: "go-previous"; Accessible.name: i18n("Back to Time")
                onClicked: page.backRequested()
            }
            Kirigami.Heading { level: 3; text: i18n("Keep awake") }
        }
        C.Label {
            Layout.fillWidth: true; wrapMode: Text.Wrap
            text: page.awake.statusText
        }
        Flow {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            Repeater {
                model: [{seconds: 1800, label: i18n("30 min")}, {seconds: 3600, label: i18n("1 hour")},
                        {seconds: -1, label: i18n("Until off")}]
                C.Button {
                    required property var modelData
                    text: modelData.label
                    checked: page.awake.active && page.awake.state.duration === modelData.seconds
                    enabled: !page.awake.busy
                    onClicked: page.awake.setDuration(modelData.seconds)
                }
            }
            C.Button {
                id: chooseTime
                text: i18n("End at…"); checkable: true
                onClicked: if (checked) {
                    const later = new Date(page.awake.endTime || Date.now() + 3600000)
                    hours.value = later.getHours()
                    minutes.value = later.getMinutes()
                    hours.forceActiveFocus(Qt.TabFocusReason)
                }
            }
        }
        RowLayout {
            visible: chooseTime.checked
            C.SpinBox {
                id: hours
                from: 0; to: 23; editable: true; wrap: true
                Accessible.name: i18n("Hour (24-hour clock)")
            }
            C.Label { text: ":" }
            C.SpinBox {
                id: minutes
                from: 0; to: 59; editable: true; wrap: true
                Accessible.name: i18n("Minutes")
                textFromValue: (value, locale) => Number(value).toLocaleString(locale, "f", 0).padStart(2, locale.zeroDigit)
            }
        }
        C.Button {
            visible: chooseTime.checked
            // Re-evaluate while the picker is open, including across midnight.
            property double now: Date.now()
            property double end: visible ? page.nextEnd(now, hours.value, minutes.value) : 0
            Timer {
                id: clock
                function sync() {
                    parent.now = Date.now()
                    interval = 60000 - (parent.now % 60000)
                    restart()
                }
                onTriggered: sync()
            }
            onVisibleChanged: if (visible) clock.sync(); else clock.stop()
            text: !end ? i18n("Choose a time within 24 hours") :
                new Date(end).getDate() === new Date(now).getDate()
                ? i18n("Until %1 today", new Date(end).toLocaleTimeString(Qt.locale(), Locale.ShortFormat))
                : i18n("Until %1 tomorrow", new Date(end).toLocaleTimeString(Qt.locale(), Locale.ShortFormat))
            enabled: end > 0 && !page.awake.busy
            onClicked: {
                const current = Date.now()
                const target = page.nextEnd(current, hours.value, minutes.value)
                if (target && target === end) page.awake.setDuration(Math.ceil((target - current) / 1000))
                now = current
            }
        }
        C.Button {
            visible: !!page.awake.state.duration
            text: i18n("Stop manual timer")
            enabled: !page.awake.busy
            onClicked: page.awake.setDuration(0)
        }
        C.Label {
            Layout.fillWidth: true; wrapMode: Text.Wrap
            text: i18n("A manual timer keeps the screen on and delays automatic locking and sleep until it ends.")
        }
    }
}
