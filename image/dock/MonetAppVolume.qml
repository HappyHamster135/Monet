// The Home Bar's app volume belongs to the app, not a video's temporary stream.
import QtQuick
import QtCore

QtObject {
    id: memory
    property int normalVolume: 65536
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

    function remember(stream, value) {
        const app = key(stream);
        if (!app || !Number.isFinite(value)) return;
        const values = levels();
        values[app] = Math.max(0, Math.min(1, value / normalVolume));
        settings.levels = JSON.stringify(values);
    }

    // False until the stream plays and says which app it is, so the caller
    // tries again then.
    function restore(stream) {
        if (!stream || stream.corked || !key(stream)) return false;
        const value = levels()[key(stream)];
        if (Number.isFinite(value) && value >= 0 && value <= 1) {
            stream.model.Volume = Math.round(value * normalVolume);
            // Restoring a positive volume must preserve a deliberate app mute.
            if (value === 0) stream.model.Muted = true;
        }
        return true;
    }

    // True when the app has a saved level and this stream is somewhere else.
    function moved(stream) {
        const value = levels()[key(stream)];
        return Number.isFinite(value) && value >= 0 && value <= 1
            && Math.abs(Math.round(value * normalVolume) - stream.volume) >= 2;
    }

    // Another mixer moved an app the Home Bar remembers: keep the new level,
    // so the next track doesn't jump back to the old one. Like the Home Bar's
    // slider, an app's level is its loudest stream.
    function follow(stream, streams) {
        const app = key(stream);
        const saved = levels()[app];
        if (!app || !Number.isFinite(saved)) return;
        const loudest = Math.max(stream.volume, ...streams.filter(other => key(other) === app).map(other => other.volume));
        if (Math.abs(saved * normalVolume - loudest) >= 2) remember(stream, loudest);
    }
}
