// The Home Bar's app volume belongs to the app, not a video's temporary stream.
// While a window is open it can also have a level of its own.
import QtQuick
import QtCore

QtObject {
    id: memory
    property int normalVolume: 65536
    // The open windows ([{id, pid, appId, title}]) and a process's parent
    // (-1: unknown). The Home Bar fills these in from its task list.
    property var windows: () => []
    property var parentOf: pid => -1
    // A window's own level while it is open, by window id: {level: 0 to 1, app: key}.
    property var windowLevels: ({})
    readonly property Settings settings: Settings {
        location: StandardPaths.writableLocation(StandardPaths.ConfigLocation) + "/monet/app-volume.ini"
        category: "HomeBar"
        property string levels: "{}"
    }

    function key(stream) {
        const props = stream.model.Client?.properties ?? {};
        const app = stream.portalAppId || props["application.id"];
        if (app) return "id:" + app;
        const binary = props["application.process.binary"];
        return binary ? "binary:" + binary : stream.appName ? "name:" + stream.appName : "";
    }

    function levels() {
        try {
            const values = JSON.parse(settings.levels);
            return values && typeof values === "object" && !Array.isArray(values) ? values : {};
        } catch (error) { return {}; }
    }

    function clamp(value) {
        return Math.max(0, Math.min(1, value / normalVolume));
    }

    function save(app, value) {
        const values = levels();
        values[app] = clamp(value);
        settings.levels = JSON.stringify(values);
    }

    // The app's slider: the level is the app's again, in every window.
    function remember(stream, value) {
        const app = key(stream);
        if (!app || !Number.isFinite(value)) return;
        save(app, value);
        for (const id in windowLevels)
            if (windowLevels[id].app === app) delete windowLevels[id];
    }

    // A window's own slider: only that window's sound, while it is open.
    function rememberWindow(id, stream, value) {
        const app = key(stream);
        if (!id || !app || !Number.isFinite(value)) return;
        windowLevels[id] = {level: clamp(value), app: app};
    }

    // The windows still open. A closed window's level goes with it.
    function openWindows() {
        let list = [];
        try { list = windows() ?? []; } catch (error) { list = []; }
        for (const id in windowLevels)
            if (!list.some(window => window.id === id)) delete windowLevels[id];
        return list;
    }

    // The one window a stream plays for, or null when that isn't certain.
    // A window's own process (or its child, like a browser's sound process)
    // is enough when no other window shares it. Browsers play every tab from
    // one process; Firefox names a tab's stream after the page, which is also
    // the window's title while the tab is showing.
    function owner(stream, list) {
        let candidates;
        if (stream.portalAppId) {
            // Inside Flatpak the stream's process id is the sandbox's own.
            candidates = list.filter(window => window.appId === stream.portalAppId);
        } else {
            candidates = list.filter(window => window.pid > 0 && window.pid === stream.pid);
            if (!candidates.length && stream.pid > 0) {
                const parent = stream.parentPid > 0 ? stream.parentPid : parentOf(stream.pid);
                candidates = list.filter(window => window.pid > 0 && window.pid === parent);
            }
        }
        if (candidates.length === 1) return candidates[0];
        const name = String(stream.model.Name ?? "").trim();
        if (!name) return null;
        // The title without the app's name at its end, as the tooltip shows it.
        const titled = candidates.filter(window => window.title === name
            || (window.title.match(/.*(?=\s+(—|-|–))/) ?? [""])[0] === name);
        return titled.length === 1 ? titled[0] : null;
    }

    // Each of a tooltip's windows with the streams it plays ({window id:
    // [streams]}), when every one of the app's streams plays for one of them.
    // Otherwise null, and the app keeps one slider.
    function byWindow(streams, ids, list) {
        if (!streams.length || ids.length < 2) return null;
        const all = list ?? openWindows();
        const found = {};
        for (const stream of streams) {
            const window = owner(stream, all);
            if (!window || !ids.includes(window.id)) return null;
            (found[window.id] = found[window.id] ?? []).push(stream);
        }
        return found;
    }

    // The window a stream plays for, when that window has a level of its own.
    function windowOf(stream, list) {
        if (!Object.keys(windowLevels).length) return null;
        const window = owner(stream, list ?? openWindows());
        return window && windowLevels[window.id] ? window : null;
    }

    // What the Home Bar keeps for a stream, from 0 to 1 (-1: nothing).
    function level(stream) {
        const window = windowOf(stream);
        if (window) return windowLevels[window.id].level;
        const value = levels()[key(stream)];
        return Number.isFinite(value) && value >= 0 && value <= 1 ? value : -1;
    }

    // False until the stream plays and says which app it is, so the caller
    // tries again then.
    function restore(stream, value) {
        if (!stream || stream.corked || !key(stream)) return false;
        if (value === undefined) value = level(stream);
        if (value >= 0) {
            stream.model.Volume = Math.round(value * normalVolume);
            // Restoring a positive volume must preserve a deliberate app mute.
            if (value === 0) stream.model.Muted = true;
        }
        return true;
    }

    // True when there is a level for this stream and the stream is somewhere else.
    function moved(stream) {
        const value = level(stream);
        return value >= 0 && Math.abs(Math.round(value * normalVolume) - stream.volume) >= 2;
    }

    // Another mixer moved a stream the Home Bar keeps a level for: keep the
    // new level, so the next track doesn't jump back to the old one. Like
    // the sliders, a level is the loudest of its streams (the window's, or
    // the app's streams that have no window level).
    function follow(stream, streams) {
        const app = key(stream);
        if (!app) return;
        const list = Object.keys(windowLevels).length ? openWindows() : [];
        const window = windowOf(stream, list);
        if (window) {
            const same = streams.filter(other => other !== stream && key(other) === app && windowOf(other, list)?.id === window.id);
            const loudest = Math.max(stream.volume, ...same.map(other => other.volume));
            if (Math.abs(windowLevels[window.id].level * normalVolume - loudest) >= 2)
                windowLevels[window.id].level = clamp(loudest);
            return;
        }
        const saved = levels()[app];
        if (!Number.isFinite(saved)) return;
        const same = streams.filter(other => other !== stream && key(other) === app && !windowOf(other, list));
        const loudest = Math.max(stream.volume, ...same.map(other => other.volume));
        if (Math.abs(saved * normalVolume - loudest) >= 2) save(app, loudest);
    }
}
