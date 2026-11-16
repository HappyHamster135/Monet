import QtQuick
import org.kde.plasma.plasma5support as P5Support
import "appnames.js" as Names

// Names for the apps (and web app windows) KDE's Task Manager couldn't name: a Steam game
// started before Monet made its entry, a Flatpak app whose entry KDE missed. monet-quick
// app-names looks each up once; the answers go into KDE's model as its own overrides, beside
// KDE's (Background Services), so search, Quit and the details sidebar say them too. So do the
// sums of rows that gained processes their app started (numbers, from Accounting).
QtObject {
    id: names
    // KDE's ApplicationDataModel (org.kde.ksysguard.process).
    property QtObject model
    property bool active: false
    property string helper: "@LIBEXECDIR@/monet-quick"
    // {id: {name, icon}}, and every id asked (answered or not), so none is asked twice.
    property var found: ({})
    property var asked: ({})
    property var base: null
    // {row id: {attribute: value}}: rows with the processes they gained.
    property var numbers: ({})
    property bool busy: false
    property int serial: 0
    // Roles of KDE's model, from org.kde.ksysguard.process's ProcessDataModel.
    property int valueRole: Qt.UserRole

    function column(attribute) {
        return model && model.enabledAttributes ? model.enabledAttributes.indexOf(attribute) : -1
    }
    // The raw ids of the rows KDE couldn't name.
    function unnamed() {
        const ids = [], nameColumn = column("appName"), menuColumn = column("menuId"), iconColumn = column("iconName")
        if (!model || nameColumn < 0 || menuColumn < 0 || iconColumn < 0) return ids
        const named = Object.values(found).map(f => f && f.name)
        for (let row = 0; row < model.rowCount(); ++row) {
            const value = c => model.data(model.index(row, c), valueRole)
            const name = String(value(nameColumn) || "")
            // A name Monet gave already (one without an icon still has no menu entry or icon).
            if (Names.unresolved(name, value(menuColumn), value(iconColumn)) && !named.includes(name)) ids.push(name)
        }
        return ids
    }
    function look(windows) {
        if (!active || busy || !model) return
        const ids = unnamed()
        for (const window of windows || []) {
            // A web app's window, whatever KDE called it (it may say its browser's name).
            if (Names.webAppId(String(window.appId || ""))) ids.push(String(window.appId).replace(/\.desktop$/, ""))
        }
        const wanted = Names.toAsk(ids, asked)
        if (!wanted.length) return
        busy = true
        const now = Object.assign({}, asked)
        for (const id of wanted) now[id] = true
        asked = now
        reader.connectSource("'" + helper.replace(/'/g, "'\\''") + "' app-names " + wanted.map(Names.hex).join(" ")
            + " # app-names-" + (++serial))
    }
    function answer(text) {
        busy = false
        let result = {}
        try {
            result = JSON.parse(text)
        } catch (_) {
            return
        }
        if (!result || typeof result !== "object") return
        found = Object.assign({}, found, result)
        apply()
    }
    function apply() {
        if (!model) return
        if (base === null) base = model.applicationOverrides || {}
        model.applicationOverrides = Names.overrides(base, found, numbers)
    }
    onNumbersChanged: if (base !== null || Object.keys(numbers).length) apply()
    // The id KDE files a row under, for its overrides.
    function key(name, menuId) {
        return Names.rowKey(name, menuId, found)
    }
    property QtObject reader: P5Support.DataSource {
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            names.answer(data["exit code"] === 0 ? String(data.stdout || "") : "")
        }
    }
}
