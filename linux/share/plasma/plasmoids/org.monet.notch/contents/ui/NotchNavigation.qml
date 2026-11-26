import QtQuick

QtObject {
    required property string route
    required property var sections
    required property var available
    signal requested(string key, bool backwards)

    // The chooser sits outside the path. Opening it preserves the tab and its details.
    property var path: []
    readonly property var availablePath: path.filter(key => available(key))
    readonly property bool canGoBack: route !== "sections" || availablePath.length > 0
    readonly property bool inDetail: route !== "sections" && availablePath.indexOf(route) > 0
    readonly property string lastSection: {
        for (let i = availablePath.length - 1; i >= 0; --i)
            if (sections.some(section => section.key === availablePath[i])) return availablePath[i]
        return ""
    }

    function pathHere() {
        const index = availablePath.indexOf(route)
        return index >= 0 ? availablePath.slice(0, index + 1) : [route]
    }
    function openTab(key) {
        path = [key]
        requested(key, false)
    }
    function openDetail(key) {
        if (route === key) return
        if (route === "sections") { openTab(key); return }
        const parents = pathHere()
        const index = parents.indexOf(key)
        path = index < 0 ? parents.concat(key) : parents.slice(0, index + 1)
        requested(key, index >= 0)
    }
    function showSections() {
        if (route === "sections") return
        path = pathHere()
        requested("sections", true)
    }
    function back() {
        if (route === "sections") {
            if (availablePath.length) requested(availablePath[availablePath.length - 1], false)
        } else if (inDetail) {
            path = pathHere().slice(0, -1)
            requested(path[path.length - 1], true)
        } else {
            showSections()
        }
    }
    function dismiss() {
        // Reopening the notch can return to the last tab without reopening a detail or editor.
        const tab = sections.some(section => section.key === route) ? route : lastSection
        path = tab ? [tab] : []
    }
}
