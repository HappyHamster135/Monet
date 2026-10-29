import QtCore
import QtQuick
import QtQml.Models
import Qt.labs.folderlistmodel

QtObject {
    id: format
    property url configFolder: StandardPaths.writableLocation(StandardPaths.GenericConfigLocation)
    property var locale: Qt.locale()

    readonly property Settings preferences: Settings {
        location: format.configFolder + "/plasma-localerc"
        category: "Formats"
    }
    readonly property FolderListModel watch: FolderListModel {
        folder: format.configFolder
        nameFilters: ["plasma-localerc"]
        showDirs: false
        onCountChanged: Qt.callLater(format.refresh)
    }
    readonly property Instantiator changes: Instantiator {
        model: format.watch
        delegate: QtObject {
            required property date fileModified
            onFileModifiedChanged: Qt.callLater(format.refresh)
            Component.onCompleted: Qt.callLater(format.refresh)
        }
    }

    function refresh() {
        // Processes keep their startup locale; read the saved preference after each change.
        preferences.sync()
        const name = preferences.value("LC_TIME", "") || preferences.value("LANG", "")
        locale = name ? Qt.locale(name) : Qt.locale()
    }
    function time(date) {
        return date.toLocaleTimeString(locale, Locale.ShortFormat)
    }
    Component.onCompleted: refresh()
}
