/*
 * A month of Monet's calendar, for the Calendar widget and the bar's clock:
 * its name in Fraunces (a click comes back to today), arrows or the wheel to
 * turn it, the weekdays, and the days. Today is a dab of the sun, the chosen
 * day a ring of lily, and a day with a note has a dot of lily (point at it to
 * read the note). Under the month, a line with the chosen day's note.
 *
 * A click chooses a day; a click on the chosen day, the line under the month,
 * or Enter opens its note. The arrow keys move from day to day.
 *
 * install.sh copies this file into the Calendar's and the Clock's packages.
 */
import QtQuick
import QtQuick.Layouts
import QtQuick.Shapes
import org.kde.plasma.core as PlasmaCore

FocusScope {
    id: month

    property date today: new Date()
    // The month on the page (its first day), and the chosen day.
    property date shown: new Date(today.getFullYear(), today.getMonth(), 1)
    property date chosen: today
    property QtObject store: null
    property color ink
    property color dim
    property color lily
    property int titleSize: 20
    // A Notes button in the header, lit while the notes are out.
    property bool notesButton: true
    property bool notesShown: false
    // The line under the month with the chosen day's note.
    property bool peekLine: true
    readonly property int firstWeekday: Qt.locale().firstDayOfWeek  // 0 is Sunday
    signal opened(date day)
    signal notesToggled()

    activeFocusOnTab: true
    Accessible.role: Accessible.Table
    Accessible.name: i18n("Calendar")
    Accessible.description: Qt.formatDate(chosen, Qt.locale().dateFormat(Locale.LongFormat))
        + ". " + i18n("Arrow keys change the day. Enter opens its note. Home returns to today.")

    function sameDay(a, b) {
        return a.toDateString() === b.toDateString();
    }

    function turn(by) {
        shown = new Date(shown.getFullYear(), shown.getMonth() + by, 1);
    }

    function choose(day) {
        chosen = new Date(day.getFullYear(), day.getMonth(), day.getDate());
        if (day.getMonth() !== shown.getMonth() || day.getFullYear() !== shown.getFullYear()) {
            shown = new Date(day.getFullYear(), day.getMonth(), 1);
        }
    }

    function move(by) {
        choose(new Date(chosen.getFullYear(), chosen.getMonth(), chosen.getDate() + by));
    }

    // "Today", "Tomorrow", "Yesterday", or the day itself ("Fri 30 Oct").
    function dayName(day) {
        const days = Math.round((new Date(day.getFullYear(), day.getMonth(), day.getDate())
                                 - new Date(today.getFullYear(), today.getMonth(), today.getDate())) / 86400000);
        return days === 0 ? i18nc("a day in the calendar", "Today")
             : days === 1 ? i18nc("a day in the calendar", "Tomorrow")
             : days === -1 ? i18nc("a day in the calendar", "Yesterday")
             : Qt.locale().toString(day, "ddd d MMM");
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

    // Left and right follow the page's direction.
    Keys.onLeftPressed: move(LayoutMirroring.enabled ? 1 : -1)
    Keys.onRightPressed: move(LayoutMirroring.enabled ? -1 : 1)
    Keys.onUpPressed: move(-7)
    Keys.onDownPressed: move(7)
    Keys.onReturnPressed: opened(chosen)
    Keys.onEnterPressed: opened(chosen)
    Keys.onSpacePressed: opened(chosen)
    Keys.onPressed: event => {
        if (event.key === Qt.Key_Home) {
            choose(today);
            event.accepted = true;
        } else if (event.key === Qt.Key_PageUp || event.key === Qt.Key_PageDown) {
            const by = event.key === Qt.Key_PageUp ? -1 : 1;
            const lastDay = new Date(shown.getFullYear(), shown.getMonth()+by+1, 0).getDate();
            choose(new Date(shown.getFullYear(), shown.getMonth()+by, Math.min(chosen.getDate(),lastDay)));
            event.accepted = true;
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 4

        RowLayout {
            Layout.fillWidth: true
            spacing: 2

            Text {
                Layout.fillWidth: true
                horizontalAlignment: Text.AlignLeft
                text: Qt.locale().standaloneMonthName(month.shown.getMonth())
                      + (month.shown.getFullYear() !== month.today.getFullYear() ? " " + month.shown.getFullYear() : "")
                color: month.ink
                elide: Text.ElideRight
                font.family: "Fraunces 72pt SuperSoft"
                font.pixelSize: month.titleSize
                MouseArea {
                    anchors.fill: parent
                    onClicked: month.choose(month.today)
                }
            }
            // Notes: the day's note beside the month, out or away.
            PlasmaCore.ToolTipArea {
                id: notesTab
                activeFocusOnTab: true
                Keys.onReturnPressed: month.notesToggled()
                Keys.onSpacePressed: month.notesToggled()
                visible: month.notesButton
                Layout.preferredWidth: 26
                Layout.preferredHeight: 26
                mainText: month.notesShown ? i18n("Put the notes away") : i18n("Notes")
                subText: month.notesShown ? "" : i18n("Write something for the chosen day")
                Accessible.role: Accessible.Button
                Accessible.name: mainText
                Accessible.onPressAction: month.notesToggled()

                Rectangle {
                    anchors.fill: parent
                    radius: 13
                    color: month.notesShown ? month.lily : month.ink
                    border.width: notesTab.activeFocus ? 2 : 0
                    border.color: month.lily
                    opacity: notesTab.activeFocus ? 0.5 : month.notesShown ? 0.18 : notesArea.pressed ? 0.14 : notesArea.containsMouse ? 0.08 : 0
                }
                // A page with lines on it.
                Shape {
                    anchors.centerIn: parent
                    width: 14
                    height: 14
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        strokeColor: month.notesShown ? month.lily : notesArea.containsMouse ? month.ink : month.dim
                        strokeWidth: 1.5
                        fillColor: "transparent"
                        joinStyle: ShapePath.RoundJoin
                        PathPolyline { path: [Qt.point(2.5, 1.5), Qt.point(11.5, 1.5), Qt.point(11.5, 12.5), Qt.point(2.5, 12.5), Qt.point(2.5, 1.5)] }
                    }
                    ShapePath {
                        strokeColor: month.notesShown ? month.lily : notesArea.containsMouse ? month.ink : month.dim
                        strokeWidth: 1.3
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        PathMove { x: 5; y: 5 }
                        PathLine { x: 9; y: 5 }
                        PathMove { x: 5; y: 7.5 }
                        PathLine { x: 9; y: 7.5 }
                        PathMove { x: 5; y: 10 }
                        PathLine { x: 7.5; y: 10 }
                    }
                }
                MouseArea {
                    id: notesArea
                    anchors.fill: parent
                    hoverEnabled: true
                    cursorShape: Qt.PointingHandCursor
                    onClicked: month.notesToggled()
                }
            }
            Repeater {
                model: [-1, 1]
                Item {
                    id: arrow
                    activeFocusOnTab: true
                    Keys.onReturnPressed: month.turn(arrow.modelData)
                    Keys.onSpacePressed: month.turn(arrow.modelData)
                    Accessible.onPressAction: month.turn(arrow.modelData)
                    required property int modelData
                    Layout.preferredWidth: 26
                    Layout.preferredHeight: 26
                    Accessible.role: Accessible.Button
                    Accessible.name: modelData < 0 ? i18n("Previous month") : i18n("Next month")

                    Rectangle {
                        anchors.fill: parent
                        radius: 13
                        color: month.ink
                        border.width: arrow.activeFocus ? 2 : 0
                        border.color: month.lily
                        opacity: arrow.activeFocus ? 0.5 : arrowArea.pressed ? 0.14 : arrowArea.containsMouse ? 0.08 : 0
                    }
                    Text {
                        anchors.centerIn: parent
                        anchors.verticalCenterOffset: -1
                        // The previous month points back, whichever way the page reads.
                        text: (arrow.modelData < 0) !== month.LayoutMirroring.enabled ? "‹" : "›"
                        color: arrowArea.containsMouse ? month.ink : month.dim
                        font.family: "Inter"
                        font.pixelSize: 20
                    }
                    MouseArea {
                        id: arrowArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: month.turn(arrow.modelData)
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
                        month.turn(gathered > 0 ? -1 : 1);
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
                    text: Qt.locale().dayName((month.firstWeekday + index) % 7, Locale.NarrowFormat)
                    color: month.dim
                    font.family: "Inter"
                    font.pixelSize: 10
                    font.weight: Font.DemiBold
                }
            }

            Repeater {
                model: month.days
                PlasmaCore.ToolTipArea {
                    id: cell
                    required property var modelData
                    readonly property bool inMonth: modelData.getMonth() === month.shown.getMonth()
                    readonly property bool isToday: month.sameDay(modelData, month.today)
                    readonly property bool isChosen: month.sameDay(modelData, month.chosen)
                    readonly property string note: month.store ? month.store.noteFor(modelData) : ""
                    readonly property real side: Math.min(width, height) - 2
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    Layout.fillHeight: true
                    implicitHeight: 20
                    // A day's note, under the pointer.
                    active: note !== ""
                    mainText: Qt.locale().toString(modelData, Qt.locale().dateFormat(Locale.LongFormat))
                    subText: note.split("\n").slice(0, 4).join("\n")
                    Accessible.onPressAction: { month.choose(cell.modelData); month.opened(cell.modelData); }
                    Accessible.role: Accessible.Button
                    Accessible.name: mainText + (note !== "" ? ", " + note.split("\n")[0] : "")

                    // Under the pointer, a faint wash.
                    Rectangle {
                        anchors.centerIn: parent
                        width: cell.side
                        height: width
                        radius: width / 2
                        color: month.ink
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
                    // The chosen day: a ring of lily (round today's sun too).
                    Rectangle {
                        anchors.centerIn: parent
                        width: cell.side + (cell.isToday ? 5 : 1)
                        height: width
                        radius: width / 2
                        color: "transparent"
                        border.width: 2
                        border.color: month.lily
                        visible: cell.isChosen && (!cell.isToday || month.activeFocus)
                    }
                    Text {
                        anchors.centerIn: parent
                        anchors.verticalCenterOffset: cell.note !== "" ? -1 : 0
                        horizontalAlignment: Text.AlignHCenter
                        text: cell.modelData.getDate()
                        color: cell.isToday ? "#FBF7EE" : month.ink
                        opacity: cell.inMonth ? 1 : 0.32
                        font.family: "Inter"
                        font.pixelSize: 12
                        font.weight: cell.isToday || cell.isChosen ? Font.DemiBold : Font.Normal
                        font.features: { "tnum": 1 }
                    }
                    // A note that day.
                    Rectangle {
                        anchors.horizontalCenter: parent.horizontalCenter
                        anchors.top: parent.verticalCenter
                        anchors.topMargin: 6
                        width: 4
                        height: 4
                        radius: 2
                        visible: cell.note !== ""
                        color: cell.isToday ? "#FBF7EE" : month.lily
                        opacity: cell.inMonth ? 1 : 0.4
                    }
                    MouseArea {
                        id: dayArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        // The chosen day again opens its note; any other is chosen.
                        onClicked: {
                            month.forceActiveFocus();
                            if (cell.isChosen) {
                                month.opened(cell.modelData);
                            } else {
                                month.choose(cell.modelData);
                            }
                        }
                        onDoubleClicked: month.opened(cell.modelData)
                    }
                }
            }
        }

        // The chosen day's note, in a line: a click opens it.
        Item {
            id: peek
            activeFocusOnTab: true
            Keys.onReturnPressed: month.opened(month.chosen)
            Keys.onSpacePressed: month.opened(month.chosen)
            Accessible.onPressAction: month.opened(month.chosen)
            readonly property string note: month.store ? month.store.noteFor(month.chosen) : ""
            readonly property int radius: 9
            visible: month.peekLine
            Layout.fillWidth: true
            Layout.preferredHeight: 26
            Rectangle {
                anchors.fill: parent
                radius: parent.radius
                color: month.ink
                border.width: peek.activeFocus ? 2 : 0
                border.color: month.lily
                opacity: peek.activeFocus ? 0.5 : peekArea.pressed ? 0.12 : peekArea.containsMouse ? 0.08 : 0.04
            }
            Accessible.role: Accessible.Button
            Accessible.name: i18nc("%1 is a day, like Today or Fri 30 Oct", "Notes for %1", month.dayName(month.chosen))

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 6
                spacing: 6
                Text {
                    horizontalAlignment: Text.AlignLeft
                    text: month.dayName(month.chosen)
                    color: month.ink
                    font.family: "Inter"
                    font.pixelSize: 11
                    font.weight: Font.DemiBold
                }
                Text {
                    Layout.fillWidth: true
                    horizontalAlignment: Text.AlignLeft
                    text: peek.note !== "" ? peek.note.split("\n")[0] : i18n("Nothing planned")
                    color: peek.note !== "" ? month.ink : month.dim
                    elide: Text.ElideRight
                    textFormat: Text.PlainText
                    font.family: "Inter"
                    font.pixelSize: 11
                    font.italic: peek.note === ""
                }
                // A pencil to write, or a plus for a day with nothing yet.
                Shape {
                    Layout.preferredWidth: 14
                    Layout.preferredHeight: 14
                    preferredRendererType: Shape.CurveRenderer
                    ShapePath {
                        strokeColor: peekArea.containsMouse ? month.ink : month.dim
                        strokeWidth: 1.5
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.RoundJoin
                        PathPolyline {
                            path: peek.note !== ""
                                ? [Qt.point(2.5, 11.5), Qt.point(3, 9), Qt.point(9.5, 2.5), Qt.point(11.5, 4.5), Qt.point(5, 11), Qt.point(2.5, 11.5)]
                                : [Qt.point(7, 2.5), Qt.point(7, 11.5)]
                        }
                    }
                    ShapePath {
                        strokeColor: peekArea.containsMouse ? month.ink : month.dim
                        strokeWidth: 1.5
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        PathPolyline {
                            path: peek.note !== "" ? [Qt.point(8, 4), Qt.point(10, 6)] : [Qt.point(2.5, 7), Qt.point(11.5, 7)]
                        }
                    }
                }
            }
            MouseArea {
                id: peekArea
                anchors.fill: parent
                hoverEnabled: true
                cursorShape: Qt.PointingHandCursor
                onClicked: month.opened(month.chosen)
            }
        }
    }
}
