/*
 * Clock: the time and the date in the panel, in Monet's type. A click opens
 * the day and its month on the panel's glass: the day's name in Fraunces,
 * the month as Monet's calendar draws it, today on a dab of the sun. A click
 * chooses a day; a day with a note has a dot of lily (point at it to read
 * it), and the line under the month says the chosen day's note. Notes (or a
 * click on the line) brings the day's note out beside the month, to read and
 * write: the same notes as the Calendar widget's.
 */
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property date now: new Date()
    // The notes beside the month, out or away (it stays as it was left).
    property bool notesOpen: false
    readonly property color ink: Kirigami.Theme.textColor
    readonly property color dim: Qt.rgba(ink.r, ink.g, ink.b, 0.62)
    readonly property bool smoke: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    readonly property color lily: smoke ? "#4DB4A0" : "#357F72"

    Plasmoid.icon: "x-office-calendar"
    toolTipMainText: Qt.formatDate(now, Qt.locale().dateFormat(Locale.LongFormat))
    toolTipSubText: Qt.formatTime(now, Qt.locale().timeFormat(Locale.ShortFormat))
    // A fresh look at the notes whenever the page opens.
    onExpandedChanged: if (expanded) noteStore.refresh()

    NoteStore {
        id: noteStore
        helper: "@LIBEXECDIR@/monet-quick"
    }

    Timer {
        // On the minute, so the time turns when the clock on the wall does.
        interval: (60 - new Date().getSeconds()) * 1000
        running: true
        repeat: true
        onTriggered: {
            root.now = new Date();
            interval = (60 - root.now.getSeconds()) * 1000;
        }
    }

    compactRepresentation: MouseArea {
        Layout.minimumWidth: Math.max(time.implicitWidth, date.implicitWidth) + Kirigami.Units.smallSpacing * 2
        Layout.preferredWidth: Layout.minimumWidth
        hoverEnabled: true
        onClicked: root.expanded = !root.expanded

        Column {
            anchors.centerIn: parent
            spacing: 0
            Text {
                horizontalAlignment: Text.AlignLeft
                id: time
                anchors.horizontalCenter: parent.horizontalCenter
                text: Qt.formatTime(root.now, Qt.locale().timeFormat(Locale.ShortFormat))
                color: root.ink
                font.family: "Inter"
                font.pixelSize: 14
                font.weight: Font.DemiBold
                font.features: { "tnum": 1 }
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                id: date
                anchors.horizontalCenter: parent.horizontalCenter
                text: Qt.formatDate(root.now, "ddd d MMM")
                color: root.dim
                font.family: "Inter"
                font.pixelSize: 11
            }
        }
    }

    fullRepresentation: RowLayout {
        id: page
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true
        Layout.minimumWidth: Kirigami.Units.gridUnit * (root.notesOpen ? 33 : 16)
        Layout.preferredWidth: Kirigami.Units.gridUnit * (root.notesOpen ? 35 : 17)
        Layout.preferredHeight: Kirigami.Units.gridUnit * 19
        spacing: Kirigami.Units.largeSpacing

        // Back on today whenever the page opens, the arrow keys ready to move the day.
        Connections {
            target: root
            function onExpandedChanged() {
                if (root.expanded) {
                    month.choose(root.now);
                    month.forceActiveFocus();
                }
            }
        }

        ColumnLayout {
            Layout.preferredWidth: Kirigami.Units.gridUnit * 17
            Layout.fillWidth: !root.notesOpen
            Layout.fillHeight: true
            spacing: Kirigami.Units.smallSpacing

            // The day: a click comes back to it.
            ColumnLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.smallSpacing
                    text: Qt.locale().standaloneDayName(root.now.getDay(), Locale.LongFormat)
                    color: root.ink
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: 28
                    font.weight: Font.Light
                    elide: Text.ElideRight
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.smallSpacing
                    Layout.bottomMargin: Kirigami.Units.largeSpacing
                    text: Qt.formatDate(root.now, Qt.locale().dateFormat(Locale.LongFormat).replace(/dddd,?\s*/i, ""))
                    color: root.dim
                    font.family: "Inter"
                    font.pixelSize: 13
                    elide: Text.ElideRight
                }
                TapHandler {
                    onTapped: month.choose(root.now)
                }
            }
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 1
                color: Qt.rgba(root.ink.r, root.ink.g, root.ink.b, 0.12)
            }

            Month {
                id: month
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.topMargin: Kirigami.Units.smallSpacing
                today: root.now
                store: noteStore
                ink: root.ink
                dim: root.dim
                lily: root.lily
                titleSize: 19
                notesShown: root.notesOpen
                onNotesToggled: root.notesOpen = !root.notesOpen
                onOpened: {
                    root.notesOpen = true;
                    notes.write();
                }
            }
        }

        // The notes, beside the month.
        Rectangle {
            visible: root.notesOpen
            Layout.preferredWidth: 1
            Layout.fillHeight: true
            color: Qt.rgba(root.ink.r, root.ink.g, root.ink.b, 0.12)
        }
        DayNotes {
            id: notes
            visible: root.notesOpen
            Layout.preferredWidth: Kirigami.Units.gridUnit * 16
            Layout.fillWidth: true
            Layout.fillHeight: true
            store: noteStore
            day: month.chosen
            today: root.now
            ink: root.ink
            dim: root.dim
            lily: root.lily
            closable: true
            onMoved: day => month.choose(day)
            onClosed: root.notesOpen = false
        }
    }
}
