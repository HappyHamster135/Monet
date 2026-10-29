/* Shared preferences and a cached forecast, watched across every weather card. */
import QtCore
import QtQuick
import QtQml.Models
import Qt.labs.folderlistmodel
import org.kde.plasma.plasma5support as P5Support

QtObject {
    id: store
    property var config: ({place: "", latitude: 0, longitude: 0, places: [], fahrenheit: false})
    property var weather: null
    property bool loaded: false
    property bool stale: false
    property string problem: ""
    property double updated: 0
    property string helper: "@LIBEXECDIR@/monet-weather"
    property var queue: []
    property string inFlight: ""
    readonly property P5Support.DataSource runner: P5Support.DataSource {
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source);
            store.inFlight = "";
            try {
                if (data["exit code"] !== 0) throw new Error("weather helper");
                const result = JSON.parse(data.stdout);
                store.config = result.config;
                store.weather = result.weather;
                store.updated = result.updated;
                store.stale = result.stale;
                store.problem = result.problem ? i18n("Weather is unavailable. Try again.") : "";
                store.loaded = true;
            } catch (e) {
                store.problem = i18n("Weather could not be updated. Try again.");
            }
            store.sendNext();
        }
    }
    function hex(text) {
        return Array.from(unescape(encodeURIComponent(text))).map(c => c.charCodeAt(0).toString(16).padStart(2, "0")).join("");
    }
    function sendNext() {
        if (inFlight || !queue.length) return;
        inFlight = queue[0];
        queue = queue.slice(1);
        runner.connectSource(inFlight);
    }
    function run(args) {
        const command = helper + " " + args;
        if (!queue.includes(command)) queue = queue.concat([command]);
        sendNext();
    }
    function write(patch) { run("set " + hex(JSON.stringify(patch))); }
    function seed(legacy) { run("seed " + hex(JSON.stringify(legacy))); }
    function refresh() { run("status"); }
    function retry() { run("refresh"); }
    readonly property FolderListModel preferences: FolderListModel {
        folder: StandardPaths.writableLocation(StandardPaths.ConfigLocation) + "/monet"
        nameFilters: ["weather.json"]; showDirs: false
    }
    readonly property FolderListModel forecasts: FolderListModel {
        folder: StandardPaths.writableLocation(StandardPaths.GenericCacheLocation) + "/monet"
        nameFilters: ["weather.json"]; showDirs: false
    }
    readonly property Instantiator prefChanges: Instantiator {
        model: store.preferences
        delegate: QtObject {
            required property date fileModified
            onFileModifiedChanged: debounce.restart()
            Component.onCompleted: debounce.restart()
        }
    }
    readonly property Instantiator forecastChanges: Instantiator {
        model: store.forecasts
        delegate: QtObject {
            required property date fileModified
            onFileModifiedChanged: debounce.restart()
            Component.onCompleted: debounce.restart()
        }
    }
    readonly property Timer debounce: Timer { interval: 150; onTriggered: store.refresh() }
    readonly property Timer poll: Timer { interval: 60000; running: true; repeat: true; onTriggered: store.refresh() }
    Component.onCompleted: refresh()
}
