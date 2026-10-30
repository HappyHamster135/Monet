import QtQuick
import QtCore
import Qt.labs.folderlistmodel

QtObject {
    id: settings
    property bool enabled: true
    property url directory: StandardPaths.writableLocation(StandardPaths.GenericConfigLocation) + "/monet"
    property var flags: ({})
    readonly property bool off: !!flags["glass-off"]
    readonly property bool lite: !!flags["glass-lite"]
    readonly property int level: flags["glass-matte"] ? 2 : flags["glass-frosted"] ? 1 : 0

    // A FolderListModel owns a worker thread. One filtered watcher handles all
    // four flags, including a rename that leaves the file count unchanged.
    function scan() {
        const found = {};
        for (let i = 0; i < files.count; ++i) found[files.get(i, "fileName")] = true;
        flags = found;
    }
    readonly property FolderListModel files: FolderListModel {
        folder: settings.enabled ? settings.directory : ""
        nameFilters: ["glass-off", "glass-lite", "glass-frosted", "glass-matte"]
        showDirs: false
        onCountChanged: refresh.restart()
        onStatusChanged: refresh.restart()
    }
    readonly property Connections changes: Connections {
        target: settings.files
        function onDataChanged() { refresh.restart(); }
        function onModelReset() { refresh.restart(); }
    }
    readonly property Timer refresh: Timer { interval: 0; onTriggered: settings.scan() }
}
