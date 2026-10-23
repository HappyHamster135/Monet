/*
 * The day notes the Calendar widget and the bar's clock share: one note a
 * day, kept by Monet's helper (monet-quick notes, note DAY TEXT), so a note
 * written in one shows in the other. Changes show here at once; the helper
 * keeps them a moment later.
 *
 * install.sh copies this file into the Calendar's and the Clock's packages.
 */
import QtQuick
import org.kde.plasma.plasma5support as P5Support

QtObject {
    id: store

    property string helper
    // {"2026-10-23": "…"}
    property var notes: ({})
    property bool loaded: false
    // Writes the helper hasn't kept yet: a look meanwhile could bring back an older note.
    property int writing: 0

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
                store.writing = Math.max(0, store.writing - 1);
            }
        }
    }

    function pad(n) {
        return String(n).padStart(2, "0");
    }

    function key(day) {
        return day.getFullYear() + "-" + pad(day.getMonth() + 1) + "-" + pad(day.getDate());
    }

    function noteFor(day) {
        return notes[key(day)] || "";
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

    function write(day, text) {
        const all = Object.assign({}, notes);
        if (text.trim() === "") {
            delete all[key(day)];
        } else {
            all[key(day)] = text;
        }
        notes = all;
        writing += 1;
        runner.connectSource(helper + " note " + key(day) + (text.trim() === "" ? "" : " " + hex(text)));
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
        const from = key(day);
        return Object.keys(notes).filter(k => k > from).sort().slice(0, count).map(k => {
            const parts = k.split("-");
            return { day: new Date(Number(parts[0]), Number(parts[1]) - 1, Number(parts[2])), text: notes[k] };
        });
    }
}
