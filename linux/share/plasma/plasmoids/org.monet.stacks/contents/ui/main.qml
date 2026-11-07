import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import QtCore
import Qt.labs.folderlistmodel
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root
    SessionActivity { id: activity; viewVisible: root.visible; onActiveChanged: if (active) Qt.callLater(root.refresh) }
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "view-group"
    preferredRepresentation: fullRepresentation
    property var groups: []
    property string openGroup: ""
    property string problem: ""
    property bool busy: false
    property bool pending: false
    property string folderUrl: ""
    readonly property string grouping: Plasmoid.configuration.groupBy === "date" ? "date" : "type"
    function refresh() {
        if (!activity.active) { pending = true; return; }
        if (busy) { pending = true; return; }
        pending = false;
        busy = true;
        runner.connectSource("@BINDIR@/monet-files stacks-list " + grouping);
    }
    function title(name) {
        const names = {"Folders": i18n("Folders"), "Images": i18n("Images"), "Documents": i18n("Documents"), "Archives": i18n("Archives"),
            "Applications": i18n("Applications"), "Videos": i18n("Videos"), "Music": i18n("Music"), "Other files": i18n("Other files"),
            "Today": i18n("Today"), "Yesterday": i18n("Yesterday"), "Last 7 days": i18n("Last 7 days"), "Older": i18n("Older")};
        return names[name] || name;
    }
    P5Support.DataSource {
        id: runner
        engine: "executable"
        onNewData: (source, data) => {
            disconnectSource(source);
            if (source.includes("stacks-list")) {
                root.busy = false;
                try {
                    if (data["exit code"] !== 0) throw new Error();
                    const result = JSON.parse(data.stdout);
                    root.groups = result.groups; root.folderUrl = result.folder;
                    root.problem = result.limited ? i18n("Showing part of a large Desktop. Open Files to see everything.") : "";
                } catch (error) { root.problem = i18n("Could not read Desktop. Try refreshing."); }
                if (root.pending) { root.pending = false; refresh(); }
            }
        }
    }
    FolderListModel { id: watcher; folder: root.folderUrl || StandardPaths.writableLocation(StandardPaths.DesktopLocation); showHidden: false; onCountChanged: debounce.restart() }
    Connections { target: watcher; function onDataChanged() { debounce.restart(); } }
    Timer { id: debounce; interval: 250; onTriggered: root.refresh() }
    onGroupingChanged: refresh()
    Component.onCompleted: {
        refresh();
        // Removing the widget through Plasma's own menu restores desktop icons too.
        const remove = Plasmoid.internalAction("remove");
        if (Plasmoid.containment) runner.connectSource("@BINDIR@/monet-files stacks-enable " + Plasmoid.containment.id);
        if (remove && Plasmoid.containment) {
            const desktopId = Plasmoid.containment.id;
            remove.triggered.connect(() => runner.connectSource("@BINDIR@/monet-files stacks-disable " + desktopId));
        }
    }
    Plasmoid.contextualActions: [
        PlasmaCore.Action { text: i18n("Refresh stacks"); icon.name: "view-refresh"; onTriggered: root.refresh() },
        PlasmaCore.Action { text: i18n("Turn off desktop stacks"); icon.name: "view-list-icons"; onTriggered: runner.connectSource("@BINDIR@/monet-files stacks-disable") }
    ]
    fullRepresentation: Item {
        Layout.minimumWidth: 320; Layout.minimumHeight: 260
        Layout.preferredWidth: 480; Layout.preferredHeight: 350
        Glass {
            id: card; anchors.fill: parent; radius: 18
            ColumnLayout {
                anchors.fill: parent; anchors.margins: 16; spacing: 8
                C.Label { text: i18n("Desktop stacks"); color: card.ink; font.family: "Fraunces 72pt SuperSoft"; font.pixelSize: 23; Layout.fillWidth: true; elide: Text.ElideRight }
                C.ComboBox { model: [i18n("Group by type"), i18n("Group by date")]; currentIndex: root.grouping === "date" ? 1 : 0; onActivated: Plasmoid.configuration.groupBy = currentIndex ? "date" : "type"; Accessible.name: i18n("Group desktop files by") }
                C.ScrollView {
                    Layout.fillWidth: true; Layout.fillHeight: true; clip: true
                    ListView {
                        model: root.groups; spacing: 6; reuseItems: true
                        delegate: Column {
                            required property var modelData
                            width: ListView.view.width
                            C.ItemDelegate {
                                width: parent.width; text: root.title(modelData.name) + " · " + modelData.count
                                icon.name: root.openGroup === modelData.name ? "folder-open" : "folder"
                                onClicked: root.openGroup = root.openGroup === modelData.name ? "" : modelData.name
                            }
                            Repeater {
                                model: root.openGroup === modelData.name ? modelData.items : []
                                delegate: RowLayout {
                                    required property var modelData
                                    width: parent.width
                                    C.ItemDelegate {
                                        id: fileButton
                                        text: modelData.name; Layout.fillWidth: true; onClicked: Qt.openUrlExternally(modelData.url)
                                        contentItem: Text { text: fileButton.text; textFormat: Text.PlainText; elide: Text.ElideMiddle; color: card.ink; verticalAlignment: Text.AlignVCenter }
                                    }
                                    C.ToolButton { icon.name: "document-preview"; Accessible.name: i18n("Preview %1", modelData.name); onClicked: runner.connectSource("@BINDIR@/monet-files preview-hex " + modelData.path) }
                                }
                            }
                        }
                        C.Label { anchors.centerIn: parent; visible: root.groups.length === 0; text: root.busy ? i18n("Loading…") : i18n("Your desktop is clear"); color: card.dim }
                    }
                }
                C.Label { visible: root.problem !== ""; text: root.problem; wrapMode: Text.WordWrap; Layout.fillWidth: true; color: card.dim }
                C.Button { text: i18n("Open Desktop in Files"); onClicked: Qt.openUrlExternally(root.folderUrl) }
            }
        }
    }
}
