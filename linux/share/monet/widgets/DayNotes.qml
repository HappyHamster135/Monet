/*
 * A day's note, to read and to write: the date in Fraunces, the day before
 * and after (and back to today), the note on a sheet of paper, kept as you
 * type, and the next days that have a note, a click away. The Calendar
 * widget shows it in a panel beside the month; the bar's clock, beside its
 * month in a separate inward-opening panel.
 *
 * install.sh copies this file into the Calendar's and the Clock's packages.
 */
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Templates as T

ColumnLayout {
    id: page

    property QtObject store: null
    property date day
    property date today
    property color ink
    property color dim
    property color lily
    // A way to put it away (the Calendar's panel); the clock's has its own.
    property bool closable: false
    property string recurrence: "none"
    // To another day: the day before or after, today, or one coming up.
    signal moved(date day)
    signal closed()

    spacing: 8
    Keys.onEscapePressed: { keepNow(); closed(); }
    onVisibleChanged: if (!visible) keepNow()
    Component.onDestruction: keepNow()

    function sameDay(a, b) {
        return a.toDateString() === b.toDateString();
    }

    function step(by) {
        moved(new Date(day.getFullYear(), day.getMonth(), day.getDate() + by));
    }

    // What's typed is kept before anything else shows.
    function keepNow() {
        if (keep.running) {
            keep.stop();
            store.write(note.written, note.text, recurrence);
        }
    }

    function write() {
        note.forceActiveFocus();
        note.cursorPosition = note.length;
    }

    // Another day: keep what was written, then show its own.
    onDayChanged: {
        keepNow();
        note.written = day;
        recurrence = store ? store.repeatFor(day) : "none";
        note.text = store ? store.noteFor(day) : "";
    }
    // Notes that arrive (from the helper, or the other calendar), unless they're being typed.
    Connections {
        target: page.store
        function onNotesChanged() {
            if (!note.activeFocus && !keep.running) {
                note.text = page.store.noteFor(page.day);
                page.recurrence = page.store.repeatFor(page.day);
            }
        }
    }

    RowLayout {
        Layout.fillWidth: true
        spacing: 8

        // The date, today's in the sun's color.
        Text {
            horizontalAlignment: Text.AlignLeft
            text: page.day.getDate()
            color: page.sameDay(page.day, page.today) ? "#E2471F" : page.ink
            font.family: "Fraunces 72pt SuperSoft"
            font.pixelSize: 40
            font.features: { "tnum": 1 }
            Layout.alignment: Qt.AlignVCenter
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            Text {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignLeft
                text: Qt.locale().dayName(page.day.getDay(), Locale.LongFormat)
                color: page.ink
                elide: Text.ElideRight
                font.family: "Fraunces 72pt SuperSoft"
                font.italic: true
                font.pixelSize: 17
            }
            Text {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignLeft
                text: Qt.locale().standaloneMonthName(page.day.getMonth()) + " " + page.day.getFullYear()
                color: page.dim
                elide: Text.ElideRight
                font.family: "Inter"
                font.pixelSize: 12
            }
        }
        T.AbstractButton {
            id: toToday
            visible: !page.sameDay(page.day, page.today)
            text: i18n("Today")
            implicitWidth: todayLabel.implicitWidth + 18
            implicitHeight: 26
            onClicked: page.moved(page.today)
            background: Rectangle {
                radius: height / 2
                color: page.lily
                opacity: toToday.hovered ? 0.2 : 0.12
            }
            contentItem: Text {
                id: todayLabel
                text: toToday.text
                color: page.lily
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                font.family: "Inter"
                font.pixelSize: 12
                font.weight: Font.DemiBold
            }
        }
        // The day before, the day after.
        Repeater {
            model: [-1, 1]
            Item {
                id: stepper
                activeFocusOnTab: true
                Keys.onReturnPressed: page.step(stepper.modelData)
                Keys.onEnterPressed: page.step(stepper.modelData)
                Keys.onSpacePressed: page.step(stepper.modelData)
                Accessible.onPressAction: page.step(stepper.modelData)
                required property int modelData
                Layout.preferredWidth: 26
                Layout.preferredHeight: 26
                Accessible.role: Accessible.Button
                Accessible.name: modelData < 0 ? i18n("The day before") : i18n("The day after")
                Rectangle {
                    anchors.fill: parent
                    radius: 13
                    color: stepper.activeFocus ? "transparent" : page.ink
                    border.width: stepper.activeFocus ? 2 : 0
                    border.color: page.lily
                    opacity: stepper.activeFocus ? 1 : stepArea.pressed ? 0.14 : stepArea.containsMouse ? 0.08 : 0
                }
                Text {
                    anchors.centerIn: parent
                    anchors.verticalCenterOffset: -1
                    text: (stepper.modelData < 0) !== page.LayoutMirroring.enabled ? "‹" : "›"
                    color: stepArea.containsMouse ? page.ink : page.dim
                    font.family: "Inter"
                    font.pixelSize: 20
                }
                MouseArea {
                    id: stepArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: page.step(stepper.modelData)
                }
            }
        }
        // Put away.
        Item {
            id: closeButton
            visible: page.closable
            activeFocusOnTab: true
            Keys.onReturnPressed: { page.keepNow(); page.closed(); }
            Keys.onSpacePressed: { page.keepNow(); page.closed(); }
            Accessible.onPressAction: { page.keepNow(); page.closed(); }
            Layout.preferredWidth: 26
            Layout.preferredHeight: 26
            Accessible.role: Accessible.Button
            Accessible.name: i18n("Close")
            Rectangle {
                anchors.fill: parent
                radius: 13
                color: closeButton.activeFocus ? "transparent" : page.ink
                border.width: closeButton.activeFocus ? 2 : 0
                border.color: page.lily
                opacity: closeButton.activeFocus ? 1 : closeArea.pressed ? 0.14 : closeArea.containsMouse ? 0.08 : 0
            }
            Text {
                anchors.centerIn: parent
                text: "×"
                color: closeArea.containsMouse ? page.ink : page.dim
                font.family: "Inter"
                font.pixelSize: 18
            }
            MouseArea {
                id: closeArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: {
                    page.keepNow();
                    page.closed();
                }
            }
        }
    }

    // The day's note, on a sheet of paper.
    Rectangle {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 90
        // Lighter glass with light in its rim, as Monet's fields are.
        readonly property bool dark: page.ink.hslLightness > 0.5
        radius: 12
        color: dark ? Qt.rgba(1, 1, 1, 0.08) : Qt.rgba(1, 1, 1, 0.34)
        border.width: note.activeFocus ? 2 : 1
        border.color: note.activeFocus ? page.lily : dark ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.75)

        QQC2.ScrollView {
            anchors.fill: parent
            anchors.margins: 4
            QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

            QQC2.TextArea {
                id: note
                // The day this text belongs to, so a save on its way keeps to it.
                property date written: new Date()
                placeholderText: i18n("Nothing planned. Write something for this day…")
                placeholderTextColor: page.dim
                color: page.ink
                wrapMode: TextEdit.Wrap
                font.family: "Inter"
                font.pixelSize: 13
                selectionColor: "#9FD3C4"
                selectedTextColor: "#1C1B19"
                background: null
                Keys.onTabPressed: repeatChoice.forceActiveFocus()
                Keys.onEscapePressed: {
                    page.keepNow();
                    page.closed();
                }
                onTextChanged: if (activeFocus) keep.restart()
                onActiveFocusChanged: if (!activeFocus) page.keepNow()
                Accessible.name: i18n("Note for %1", Qt.formatDate(page.day, Qt.locale().dateFormat(Locale.LongFormat)))
                KeyNavigation.tab: repeatChoice
                Component.onCompleted: {
                    written = page.day;
                    text = page.store ? page.store.noteFor(page.day) : "";
                    page.recurrence = page.store ? page.store.repeatFor(page.day) : "none";
                }
            }
        }

        Timer {
            id: keep
            interval: 600
            onTriggered: page.store.write(note.written, note.text, page.recurrence)
        }
    }

    RowLayout {
        Layout.fillWidth: true
        QQC2.ComboBox {
            id: repeatChoice
            objectName: "noteRepeat"
            Layout.fillWidth: true
            readonly property var intervals: ["none", "yearly", "monthly", "weekly", "daily"]
            model: [i18n("Doesn't repeat"), i18n("Every year"), i18n("Every month"), i18n("Every week"), i18n("Every day")]
            currentIndex: Math.max(0, intervals.indexOf(page.recurrence))
            Accessible.name: i18n("Repeat note")
            onActivated: {
                page.keepNow();
                page.recurrence = intervals[currentIndex];
                if (note.text.trim()) page.store.write(note.written,note.text,page.recurrence);
            }
        }
    }
    Text {
        Layout.fillWidth: true
        visible: page.recurrence !== "none"
        text: i18n("Changes apply to every occurrence.")
            + (page.recurrence === "monthly" && page.day.getDate() > 28
               ? " " + i18n("Months without this date are skipped.")
               : page.recurrence === "yearly" && page.day.getMonth() === 1 && page.day.getDate() === 29
               ? " " + i18n("29 February repeats in leap years.") : "")
        color: page.dim; font.pixelSize: 11; wrapMode: Text.WordWrap
    }
    QQC2.Button {
        Layout.fillWidth: true
        visible: page.store && page.store.problem !== ""
        text: i18n("Try saving again")
        Accessible.description: page.store ? page.store.problem : ""
        onClicked: page.store.retry()
    }

    // The next days with a note.
    Text {
        Layout.fillWidth: true
        Layout.topMargin: 2
        horizontalAlignment: Text.AlignLeft
        visible: upcoming.count > 0
        text: i18n("Coming up")
        color: page.dim
        font.family: "Inter"
        font.pixelSize: 11
        font.weight: Font.DemiBold
        font.capitalization: Font.AllUppercase
        font.letterSpacing: 0.6
    }
    Repeater {
        id: upcoming
        model: page.store ? page.store.after(page.day, 3) : []
        Item {
            id: soon
            activeFocusOnTab: true
            Keys.onReturnPressed: page.moved(soon.modelData.day)
            Keys.onSpacePressed: page.moved(soon.modelData.day)
            Accessible.onPressAction: page.moved(soon.modelData.day)
            required property var modelData
            Layout.fillWidth: true
            Layout.preferredHeight: 26
            Accessible.role: Accessible.Button
            Accessible.name: Qt.locale().toString(modelData.day, Qt.locale().dateFormat(Locale.LongFormat)) + ", "
                             + modelData.text.split("\n")[0]
            Rectangle {
                anchors.fill: parent
                radius: 9
                color: page.ink
                border.width: soon.activeFocus ? 2 : 0
                border.color: page.lily
                opacity: soon.activeFocus ? 0.3 : soonArea.pressed ? 0.12 : soonArea.containsMouse ? 0.07 : 0
            }
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 8
                // A dot of lily, as the month marks the day.
                Rectangle {
                    Layout.preferredWidth: 5
                    Layout.preferredHeight: 5
                    radius: 2.5
                    color: page.lily
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    text: Qt.locale().toString(soon.modelData.day, "ddd d MMM")
                    color: page.ink
                    font.family: "Inter"
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignLeft
                    text: soon.modelData.text.split("\n")[0]
                    textFormat: Text.PlainText
                    color: page.dim
                    elide: Text.ElideRight
                    font.family: "Inter"
                    font.pixelSize: 12
                }
            }
            MouseArea {
                id: soonArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: page.moved(soon.modelData.day)
            }
        }
    }
}
