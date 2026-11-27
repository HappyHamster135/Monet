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
        spacing: 8
        RowLayout {
            IslandButton {
                id: back; plain: true
                icon.name: "go-previous"; Accessible.name: i18n("Back to Time")
                onClicked: page.backRequested()
            }
            Text { text: i18n("Keep awake"); color: "white"; font.pixelSize: 13; font.weight: Font.DemiBold }
        }
        Rectangle {
            Layout.fillWidth: true; implicitHeight: 72; radius: 14; color: "#19191c"
            RowLayout {
                anchors.fill: parent; anchors.margins: 14; spacing: 12
                IslandGlyph { source: "cup"; color: page.awake.active ? "#ffad53" : "#777781"; Layout.preferredWidth: 32; Layout.preferredHeight: 32 }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 4
                    Text { text: page.awake.active ? i18n("Keeping you awake") : i18n("Ready when you are"); font.pixelSize: 14; color: "#ededf2"; font.weight: Font.Medium }
                    Text { Layout.fillWidth: true; wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; text: page.awake.statusText; font.pixelSize: 11; color: "#aaaab2" }
                }
            }
        }
        Text { text: i18n("KEEP AWAKE FOR"); font.pixelSize: 10; font.letterSpacing: 1; color: "#888893" }
        Flow {
            Layout.fillWidth: true
            spacing: 8
            Repeater {
                model: [{seconds: 1800, label: i18n("30 min")}, {seconds: 3600, label: i18n("1 hour")},
                        {seconds: 7200, label: i18n("2 hours")}, {seconds: -1, label: i18n("Until off")}]
                IslandButton {
                    caption: true;
                    required property var modelData
                    text: modelData.label
                    checked: page.awake.active && page.awake.sessionState.duration === modelData.seconds
                    enabled: !page.awake.busy
                    onClicked: page.awake.setDuration(modelData.seconds)
                }
            }
            IslandButton {
                    caption: true;
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
            IslandStepper {
                id: hours
                from: 0; to: 23; editable: true; wrap: true
                Accessible.name: i18n("Hour (24-hour clock)")
            }
            Text { text: ":"; color: "#aaaaaf" }
            IslandStepper {
                id: minutes
                from: 0; to: 59; editable: true; wrap: true
                Accessible.name: i18n("Minutes")
                textFromValue: (value, locale) => Number(value).toLocaleString(locale, "f", 0).padStart(2, locale.zeroDigit)
            }
        }
        IslandButton {
                    caption: true;
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
        IslandButton {
                    caption: true;
            visible: !!page.awake.sessionState.duration
            text: i18n("Stop manual timer")
            enabled: !page.awake.busy
            onClicked: page.awake.setDuration(0)
        }
        C.Label {
            Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: 11; color: "#888893"
            text: i18n("A manual timer keeps the screen on and delays automatic locking and sleep until it ends.")
        }
    }
}
