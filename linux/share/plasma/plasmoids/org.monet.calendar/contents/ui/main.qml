/*
 * Calendar: the month on Monet's glass, its name in Fraunces and today on a
 * dab of the sun. The arrows (or the wheel) turn the page; a click on the
 * name comes back to today. Click a day for its page: the date in Fraunces,
 * ‹ › to the day before or after, and a note for that day, kept as you type.
 * Days with a note have a dot of lily under them. Made wide, the month and
 * the day sit side by side.
 */
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import QtQuick.Templates as T
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property date today: new Date()
    // The month on the page: its first day.
    property date shown: new Date(today.getFullYear(), today.getMonth(), 1)
    // The day whose page is open, and whether it is (side by side, it always is).
    property date day: today
    property bool dayOpen: false
    readonly property int firstWeekday: Qt.locale().firstDayOfWeek  // 0 is Sunday

    // Notes by day ("2026-10-22": "…"), kept in the widget's settings.
    readonly property var notes: {
        try {
            return JSON.parse(Plasmoid.configuration.notes || "{}");
        } catch (e) {
            return {};
        }
    }

    function key(d) {
        return d.getFullYear() + "-" + String(d.getMonth() + 1).padStart(2, "0") + "-" + String(d.getDate()).padStart(2, "0");
    }

    function noteFor(d) {
        return notes[key(d)] || "";
    }

    function write(d, text) {
        const all = Object.assign({}, notes);
        if (text.trim() === "") {
            delete all[key(d)];
        } else {
            all[key(d)] = text;
        }
        Plasmoid.configuration.notes = JSON.stringify(all);
    }

    function sameDay(a, b) {
        return a.toDateString() === b.toDateString();
    }

    function turn(by) {
        shown = new Date(shown.getFullYear(), shown.getMonth() + by, 1);
    }

    function pick(d) {
        day = new Date(d.getFullYear(), d.getMonth(), d.getDate());
        shown = new Date(d.getFullYear(), d.getMonth(), 1);
        dayOpen = true;
    }

    function step(by) {
        pick(new Date(day.getFullYear(), day.getMonth(), day.getDate() + by));
    }

    // The 42 days the page shows, from the week the month starts in.
    readonly property var days: {
        const lead = (shown.getDay() - firstWeekday + 7) % 7;
        const out = [];
        for (let i = 0; i < 42; i++) {
            out.push(new Date(shown.getFullYear(), shown.getMonth(), 1 - lead + i));
        }
        return out;
    }

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "x-office-calendar"
    preferredRepresentation: fullRepresentation
    toolTipMainText: Qt.formatDate(today, Qt.locale().dateFormat(Locale.LongFormat))
    toolTipSubText: noteFor(today) !== "" ? noteFor(today).split("\n")[0] : ""

    Timer {
        // The day turns at midnight.
        interval: 60 * 1000
        running: true
        repeat: true
        onTriggered: {
            const now = new Date();
            if (now.getDate() !== root.today.getDate()) {
                const following = root.shown.getMonth() === root.today.getMonth();
                const onToday = root.sameDay(root.day, root.today);
                root.today = now;
                if (following) {
                    root.shown = new Date(now.getFullYear(), now.getMonth(), 1);
                }
                if (onToday) {
                    root.day = now;
                }
            }
        }
    }

    fullRepresentation: Item {
        id: face
        Layout.minimumWidth: Kirigami.Units.gridUnit * 11
        Layout.minimumHeight: Kirigami.Units.gridUnit * 11
        Layout.preferredWidth: Kirigami.Units.gridUnit * 12
        Layout.preferredHeight: Kirigami.Units.gridUnit * 12

        readonly property bool wide: width >= Kirigami.Units.gridUnit * 20
        readonly property int margin: Math.round(Kirigami.Units.gridUnit * 0.8)
        readonly property bool showsDay: wide || root.dayOpen

        Glass {
            id: card
            anchors.fill: parent

            readonly property color lily: smoke ? "#4DB4A0" : "#357F72"

            // The month.
            ColumnLayout {
                id: monthPage
                x: face.margin
                y: face.margin
                width: face.wide ? Kirigami.Units.gridUnit * 10.4 : card.width - 2 * face.margin
                height: card.height - 2 * face.margin
                spacing: Kirigami.Units.smallSpacing
                opacity: face.wide || !root.dayOpen ? 1 : 0
                visible: opacity > 0
                Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

                RowLayout {
                    Layout.fillWidth: true

                    Text {
                        Layout.fillWidth: true
                        text: Qt.locale().standaloneMonthName(root.shown.getMonth())
                              + (root.shown.getFullYear() !== root.today.getFullYear() ? " " + root.shown.getFullYear() : "")
                        color: card.ink
                        elide: Text.ElideRight
                        font.family: "Fraunces 72pt SuperSoft"
                        font.pixelSize: 20
                        MouseArea {
                            anchors.fill: parent
                            onClicked: root.shown = new Date(root.today.getFullYear(), root.today.getMonth(), 1)
                        }
                    }
                    Repeater {
                        model: [-1, 1]
                        Text {
                            required property int modelData
                            text: modelData < 0 ? "‹" : "›"
                            color: turnArea.containsMouse ? card.ink : card.dim
                            font.family: "Inter"
                            font.pixelSize: 20
                            Layout.preferredWidth: 18
                            horizontalAlignment: Text.AlignHCenter
                            Accessible.role: Accessible.Button
                            Accessible.name: modelData < 0 ? i18n("Previous month") : i18n("Next month")
                            MouseArea {
                                id: turnArea
                                anchors.fill: parent
                                anchors.margins: -6
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.turn(parent.modelData)
                            }
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    columns: 7
                    rowSpacing: 0
                    columnSpacing: 0

                    // The wheel turns the month, a notch at a time.
                    WheelHandler {
                        property real gathered: 0
                        onWheel: event => {
                            gathered += event.angleDelta.y;
                            if (Math.abs(gathered) >= 120) {
                                root.turn(gathered > 0 ? -1 : 1);
                                gathered = 0;
                            }
                        }
                    }

                    // The days of the week, as letters.
                    Repeater {
                        model: 7
                        Text {
                            required property int index
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            horizontalAlignment: Text.AlignHCenter
                            text: Qt.locale().dayName((root.firstWeekday + index) % 7, Locale.NarrowFormat)
                            color: card.dim
                            font.family: "Inter"
                            font.pixelSize: 10
                            font.weight: Font.DemiBold
                        }
                    }

                    Repeater {
                        model: root.days
                        Item {
                            id: cell
                            required property var modelData
                            readonly property bool inMonth: modelData.getMonth() === root.shown.getMonth()
                            readonly property bool isToday: root.sameDay(modelData, root.today)
                            readonly property bool isPicked: face.showsDay && root.sameDay(modelData, root.day)
                            readonly property bool noted: root.noteFor(modelData) !== ""
                            Layout.fillWidth: true
                            Layout.preferredWidth: 1
                            Layout.fillHeight: true
                            implicitHeight: 20
                            Accessible.role: Accessible.Button
                            Accessible.name: Qt.formatDate(modelData, Qt.locale().dateFormat(Locale.LongFormat))

                            readonly property real side: Math.min(width, height) - 2

                            // Under the pointer, a faint wash.
                            Rectangle {
                                anchors.centerIn: parent
                                width: cell.side
                                height: width
                                radius: width / 2
                                color: card.ink
                                opacity: dayArea.containsMouse && !cell.isToday ? 0.07 : 0
                            }
                            // Today: a dab of the sun.
                            Rectangle {
                                anchors.centerIn: parent
                                width: cell.side
                                height: width
                                radius: width / 2
                                visible: cell.isToday
                                gradient: Gradient {
                                    GradientStop { position: 0; color: "#FF7A45" }
                                    GradientStop { position: 1; color: "#E2471F" }
                                }
                            }
                            // The open day: a ring of lily.
                            Rectangle {
                                anchors.centerIn: parent
                                width: cell.side + 2
                                height: width
                                radius: width / 2
                                color: "transparent"
                                border.width: 2
                                border.color: card.lily
                                visible: cell.isPicked && !cell.isToday
                            }
                            Text {
                                anchors.centerIn: parent
                                anchors.verticalCenterOffset: cell.noted ? -1 : 0
                                text: cell.modelData.getDate()
                                color: cell.isToday ? "#FBF7EE" : card.ink
                                opacity: cell.inMonth ? 1 : 0.32
                                font.family: "Inter"
                                font.pixelSize: 12
                                font.weight: cell.isToday || cell.isPicked ? Font.DemiBold : Font.Normal
                            }
                            // A note that day.
                            Rectangle {
                                anchors.horizontalCenter: parent.horizontalCenter
                                anchors.top: parent.verticalCenter
                                anchors.topMargin: 6
                                width: 4
                                height: 4
                                radius: 2
                                visible: cell.noted
                                color: cell.isToday ? "#FBF7EE" : card.lily
                                opacity: cell.inMonth ? 1 : 0.4
                            }
                            MouseArea {
                                id: dayArea
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.pick(cell.modelData)
                            }
                        }
                    }
                }
            }

            // Between the two, side by side.
            Rectangle {
                visible: face.wide
                x: monthPage.x + monthPage.width + face.margin - 1
                y: face.margin
                width: 1
                height: card.height - 2 * face.margin
                color: card.ink
                opacity: 0.1
            }

            // The day.
            ColumnLayout {
                id: dayPage
                x: face.wide ? monthPage.x + monthPage.width + 2 * face.margin : face.margin
                y: face.margin
                width: card.width - x - face.margin
                height: card.height - 2 * face.margin
                spacing: Kirigami.Units.smallSpacing
                opacity: face.showsDay ? 1 : 0
                visible: opacity > 0
                Behavior on opacity { NumberAnimation { duration: 180; easing.type: Easing.OutCubic } }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 0

                    // Back to the month.
                    T.AbstractButton {
                        id: back
                        visible: !face.wide
                        text: "‹ " + Qt.locale().standaloneMonthName(root.day.getMonth())
                        implicitWidth: backLabel.implicitWidth + 12
                        implicitHeight: 24
                        Accessible.name: i18n("Back to the month")
                        onClicked: root.dayOpen = false
                        background: Rectangle {
                            radius: height / 2
                            color: card.ink
                            opacity: back.hovered ? 0.08 : 0
                        }
                        contentItem: Text {
                            id: backLabel
                            text: back.text
                            color: card.dim
                            leftPadding: 6
                            verticalAlignment: Text.AlignVCenter
                            font.family: "Inter"
                            font.pixelSize: 12
                        }
                    }
                    Item {
                        Layout.fillWidth: true
                    }
                    T.AbstractButton {
                        id: toToday
                        visible: !root.sameDay(root.day, root.today)
                        text: i18n("Today")
                        implicitWidth: todayLabel.implicitWidth + 18
                        implicitHeight: 24
                        onClicked: root.pick(root.today)
                        background: Rectangle {
                            radius: height / 2
                            color: card.lily
                            opacity: toToday.hovered ? 0.2 : 0.12
                        }
                        contentItem: Text {
                            id: todayLabel
                            text: toToday.text
                            color: card.lily
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
                        Text {
                            required property int modelData
                            text: modelData < 0 ? "‹" : "›"
                            color: stepArea.containsMouse ? card.ink : card.dim
                            font.family: "Inter"
                            font.pixelSize: 20
                            Layout.preferredWidth: 20
                            horizontalAlignment: Text.AlignHCenter
                            Accessible.role: Accessible.Button
                            Accessible.name: modelData < 0 ? i18n("The day before") : i18n("The day after")
                            MouseArea {
                                id: stepArea
                                anchors.fill: parent
                                anchors.margins: -4
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.step(parent.modelData)
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    // The date, today's in the sun's color.
                    Text {
                        text: root.day.getDate()
                        color: root.sameDay(root.day, root.today) ? "#E2471F" : card.ink
                        font.family: "Fraunces 72pt SuperSoft"
                        font.pixelSize: 40
                        Layout.alignment: Qt.AlignVCenter
                    }
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 0
                        Text {
                            Layout.fillWidth: true
                            text: Qt.locale().dayName(root.day.getDay(), Locale.LongFormat)
                            color: card.ink
                            elide: Text.ElideRight
                            font.family: "Fraunces 72pt SuperSoft"
                            font.italic: true
                            font.pixelSize: 17
                        }
                        Text {
                            Layout.fillWidth: true
                            text: Qt.locale().standaloneMonthName(root.day.getMonth()) + " " + root.day.getFullYear()
                            color: card.dim
                            elide: Text.ElideRight
                            font.family: "Inter"
                            font.pixelSize: 12
                        }
                    }
                }

                // The day's note, on a sheet of the glass.
                Rectangle {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    radius: 12
                    color: Qt.rgba(card.ink.r, card.ink.g, card.ink.b, 0.05)
                    border.width: note.activeFocus ? 2 : 0
                    border.color: card.lily

                    QQC2.ScrollView {
                        anchors.fill: parent
                        anchors.margins: 4
                        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

                        QQC2.TextArea {
                            id: note
                            // The day this text belongs to, so a pending save keeps to it.
                            property date written: root.day
                            placeholderText: i18n("Nothing planned. Write something for this day…")
                            placeholderTextColor: card.dim
                            color: card.ink
                            wrapMode: TextEdit.Wrap
                            font.family: "Inter"
                            font.pixelSize: 13
                            selectionColor: "#9FD3C4"
                            selectedTextColor: "#1C1B19"
                            background: null
                            Keys.onEscapePressed: {
                                note.focus = false;
                                root.dayOpen = false;
                            }
                            onTextChanged: if (activeFocus) keep.restart()
                            Component.onCompleted: text = root.noteFor(root.day)
                        }
                    }

                    Timer {
                        id: keep
                        interval: 600
                        onTriggered: root.write(note.written, note.text)
                    }

                    // Another day: keep what was written, then show its own.
                    Connections {
                        target: root
                        function onDayChanged() {
                            if (keep.running) {
                                keep.stop();
                                root.write(note.written, note.text);
                            }
                            note.written = root.day;
                            note.text = root.noteFor(root.day);
                        }
                    }
                }
            }
        }
    }
}
