/*
 * The day notes the Calendar widget and the bar's clock share: one note a
 * day, kept by Monet's helper (monet-quick notes, note DAY TEXT), so a note
 * written in one shows in the other. Changes show here at once; the helper
 * keeps them a moment later, and the other one sees that at once too: the
 * helper swaps notes.json in whole, which a watch on its folder catches.
 *
 * install.sh copies this file into the Calendar's and the Clock's packages.
 */
import "NoteLogic.js" as NoteLogic
import QtCore
import QtQuick
import QtQml.Models
import Qt.labs.folderlistmodel
import org.kde.plasma.plasma5support as P5Support

QtObject {
    id: store

    property string helper
    // {"2026-10-23": "…"}
    property var notes: ({})
    property bool loaded: false
    // Writes the helper hasn't kept yet: a look meanwhile could bring back an older note.
    property var queue: []
    property string inFlight: ""
    property string problem: ""
    readonly property int writing: queue.length + (inFlight ? 1 : 0)

    readonly property P5Support.DataSource runner: P5Support.DataSource {
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source);
            if (source === store.helper + " notes") {
                if (store.writing === 0) {
                    try {
                        store.notes = JSON.parse(data["stdout"]) || {};
                    } catch (e) {
                    }
                }
                store.loaded = true;
            } else if (source.startsWith(store.helper + " note ")) {
                store.inFlight = "";
                if (data["exit code"] !== 0) {
                    store.problem = i18n("The note could not be saved. Try again.");
                } else {
                    store.queue = store.queue.slice(1);
                    store.problem = "";
                    store.sendNext();
                    if (store.queue.length === 0) store.refresh();
                }
            }
        }
    }

    // notes.json changing anywhere (the other widget, a second screen): a fresh look.
    readonly property FolderListModel watch: FolderListModel {
        folder: StandardPaths.writableLocation(StandardPaths.GenericDataLocation) + "/monet"
        nameFilters: ["notes.json"]
        showDirs: false
    }
    readonly property Instantiator changes: Instantiator {
        model: store.watch
        delegate: QtObject {
            required property date fileModified
            onFileModifiedChanged: Qt.callLater(store.refresh)
            Component.onCompleted: Qt.callLater(store.refresh)
        }
    }

    function pad(n) {
        return String(n).padStart(2, "0");
    }

    function key(day) {
        return day.getFullYear() + "-" + pad(day.getMonth() + 1) + "-" + pad(day.getDate());
    }

    function noteFor(day) {
        return NoteLogic.text(notes, day);
    }

    function hex(text) {
        const bytes = unescape(encodeURIComponent(text));
        let out = "";
        for (let i = 0; i < bytes.length; i++) {
            out += bytes.charCodeAt(i).toString(16).padStart(2, "0");
        }
        return out;
    }

    function refresh() {
        runner.connectSource(helper + " notes");
    }

    function repeatFor(day) { return NoteLogic.repeat(notes, day); }

    function sendNext() {
        if (inFlight || !queue.length || problem) return;
        inFlight = queue[0];
        runner.connectSource(inFlight);
    }
    function retry() { problem = ""; sendNext(); }

    function write(day, text, recurrence) {
        recurrence = recurrence || repeatFor(day);
        notes = NoteLogic.updated(notes,day,text,recurrence);
        queue = queue.concat([helper + " note " + key(day) + " '" + hex(text) + "' " + recurrence]);
        sendNext();
    }

    // Notes kept before they were shared (the Calendar's own settings), handed over once.
    function merge(older) {
        if (older && Object.keys(older).length > 0) {
            notes = Object.assign({}, older, notes);
            runner.connectSource(helper + " notes-merge " + hex(JSON.stringify(older)));
        }
    }

    // The next days with a note, from the day given: [{day, text}].
    function after(day, count) {
        return NoteLogic.after(notes,day,count);
    }
}
