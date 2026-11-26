import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.plasma.plasma5support as P5

ColumnLayout {
    id: page
    required property var rows
    required property var groups
    required property var hidden
    required property var favorites
    required property string group
    required property string query
    signal filterChanged(string group, string query)
    signal selected(string key)
    signal loaded(var rows, var groups)
    property bool failed: false
    spacing: 5
    readonly property var matches: {
        const words = query.normalize("NFKD").toLowerCase().trim().split(/\s+/).filter(Boolean)
        const result = rows.filter(row => !hidden.includes(row.key) &&
            (words.length || group === "all" || (group === "favorites" ? favorites.includes(row.key) : row.group === group)) &&
            words.every(word => (row.label.toLowerCase()+" "+row.terms).includes(word)))
        function rank(row) {
            const index = favorites.indexOf(row.key)
            return index === -1 ? favorites.length : index
        }
        return result.sort((a,b) => (words.length ? 0 : rank(a)-rank(b)) || a.label.localeCompare(b.label))
    }
    P5.DataSource {
        id: catalog
        engine: "executable"; connectedSources: []
        function read() { if (!connectedSources.length) connectSource("/usr/bin/python3 '@DATADIR@/monet/utilities/actions.py'") }
        onNewData: (cmd, data) => {
            disconnectSource(cmd)
            try {
                const result = JSON.parse(data.stdout)
                page.loaded(result.rows, result.groups)
                page.failed = false
            } catch (_) { page.failed = true }
        }
    }
    Component.onCompleted: if (!rows.length) catalog.read()
    RowLayout {
        Layout.fillWidth: true
        C.TextField {
            Layout.fillWidth: true; Layout.minimumWidth: 0; text: page.query; placeholderText: i18n("Find a tool…")
            onTextEdited: page.filterChanged(page.group, text)
            onAccepted: if (page.matches.length) page.selected(page.matches[0].key)
        }
        C.ComboBox {
            Layout.maximumWidth: page.width * 0.42; model: page.groups; textRole: "label"
            Accessible.name: i18n("Category")
            currentIndex: Math.max(0, page.groups.findIndex(g => g.key === page.group))
            onActivated: i => page.filterChanged(page.groups[i].key, "")
        }
    }
    ListView {
        id: results
        Layout.fillWidth: true; Layout.fillHeight: true; clip: true
        model: page.matches; spacing: 3; boundsBehavior: Flickable.StopAtBounds
        onModelChanged: positionViewAtBeginning()
        delegate: C.ItemDelegate {
            required property var modelData
            width: results.width; height: 38
            text: modelData.label; icon.name: modelData.icon; icon.width: 19; icon.height: 19
            onClicked: page.selected(modelData.key)
            Accessible.name: text
        }
        C.Label {
            anchors.centerIn: parent
            visible: results.count === 0
            text: page.failed ? i18n("Could not load tools.") : page.rows.length ? i18n("No matching tools.") : i18n("Loading…")
        }
    }
    IslandButton { visible: page.failed; caption: true; text: i18n("Retry"); onClicked: catalog.read() }
}
