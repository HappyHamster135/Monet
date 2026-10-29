/*
 * Calendar: the month on Monet's glass, its name in Fraunces and today on a
 * dab of the sun. The arrows (or the wheel) turn the page; a click on the
 * name comes back to today. A click chooses a day; a day with a note has a
 * dot of lily (point at it to read the note), and the line under the month
 * says the chosen day's note.
 *
 * The notes come out beside the month: the Notes button, the line, or a click
 * on the chosen day brings out a panel with the day's note to read and write,
 * the day before and after, and what's coming up. Made wide, the month and
 * the notes sit side by side on the card. The notes are the bar clock's too
 * (Monet's helper keeps them), so a note written there shows here.
 */
import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property date today: new Date()
    // The notes panel, beside the card (on a wide card they're always out).
    property bool notesOpen: false

    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "x-office-calendar"
    preferredRepresentation: fullRepresentation
    toolTipMainText: Qt.locale().toString(today, Qt.locale().dateFormat(Locale.LongFormat))
    toolTipSubText: noteStore.noteFor(today).split("\n")[0]

    NoteStore {
        id: noteStore
        helper: "@LIBEXECDIR@/monet-quick"
    }

    Component.onCompleted: {
        noteStore.refresh();
        // Notes this widget kept in its own settings, before they were shared: handed over once.
        let older = {};
        try {
            older = JSON.parse(Plasmoid.configuration.notes || "{}");
        } catch (e) {
        }
        if (Object.keys(older).length > 0) {
            noteStore.merge(older);
            Plasmoid.configuration.notes = "";
        }
    }

    Timer {
        // The day turns at midnight; and a look at the notes, for ones written at the clock.
        interval: 60 * 1000
        running: true
        repeat: true
        onTriggered: {
            const now = new Date();
            if (now.getDate() !== root.today.getDate()) {
                root.today = now;
            }
            noteStore.refresh();
        }
    }

    fullRepresentation: Item {
        id: face
        Layout.minimumWidth: Kirigami.Units.gridUnit * 13
        Layout.minimumHeight: Kirigami.Units.gridUnit * 14
        Layout.preferredWidth: Kirigami.Units.gridUnit * 12
        Layout.preferredHeight: Kirigami.Units.gridUnit * 13
        // Right to left, the month runs from the right and the notes come out on its left.
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true

        readonly property bool mirrored: LayoutMirroring.enabled
        readonly property bool wide: width >= Kirigami.Units.gridUnit * 36
        readonly property int margin: Math.round(Kirigami.Units.gridUnit * 0.8)

        function openNotes() {
            if (face.wide) { inline.write(); return; }
            root.notesOpen = true;
            side.write();
        }

        Glass {
            id: card
            anchors.fill: parent

            readonly property color lily: smoke ? "#4DB4A0" : "#357F72"

            // Whenever the pointer comes, a look at the notes, so the clock's show at once.
            HoverHandler {
                onHoveredChanged: if (hovered) noteStore.refresh()
            }

            Month {
                id: month
                x: face.mirrored ? card.width - width - face.margin : face.margin
                y: face.margin
                width: face.wide ? Kirigami.Units.gridUnit * 10.4 : card.width - 2 * face.margin
                height: card.height - 2 * face.margin
                today: root.today
                store: noteStore
                ink: card.ink
                dim: card.dim
                lily: card.lily
                notesButton: !face.wide
                notesShown: root.notesOpen
                // Wide, the notes are already beside the month: no line for them under it.
                peekLine: !face.wide
                onNotesToggled: {
                    if (root.notesOpen) {
                        root.notesOpen = false;
                    } else {
                        face.openNotes();
                    }
                }
                onOpened: face.openNotes()
            }

            // Wide: the notes beside the month, on the card.
            Rectangle {
                visible: face.wide
                x: face.mirrored ? month.x - face.margin : month.x + month.width + face.margin - 1
                y: face.margin
                width: 1
                height: card.height - 2 * face.margin
                color: card.ink
                opacity: 0.1
            }
            DayNotes {
                id: inline
                visible: face.wide
                x: face.mirrored ? face.margin : month.x + month.width + 2 * face.margin
                y: face.margin
                width: card.width - month.width - 4 * face.margin
                height: card.height - 2 * face.margin
                store: noteStore
                day: month.chosen
                today: root.today
                ink: card.ink
                dim: card.dim
                lily: card.lily
                onMoved: day => month.choose(day)
            }
        }

        NotesPopup {
            id: side
            anchorItem: card
            visible: root.notesOpen && !face.wide
            store: noteStore; day: month.chosen; today: root.today
            onMoved: day => month.choose(day)
            onClosed: { root.notesOpen=false; month.forceActiveFocus(); }
        }
    }
}
