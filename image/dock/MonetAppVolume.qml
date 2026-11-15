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

    function restore(stream) {
        if (!stream || stream.corked) return;
        const value = levels()[key(stream)];
        if (!Number.isFinite(value) || value < 0 || value > 1) return;
        stream.model.Volume = Math.round(value * normalVolume);
        // Restoring a positive volume must preserve a deliberate app mute.
        if (value === 0) stream.model.Muted = true;
    }
}
