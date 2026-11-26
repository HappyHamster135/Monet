import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as K
import org.kde.plasma.plasma5support as P5

ColumnLayout {
    id: page
    required property string helper
    required property bool images
    required property bool videos
    required property bool shelf
    signal addFile(string url)
    property var recent: []
    property bool loading: false
    readonly property string command: helper + " notch-captures " + (images && videos ? "all" : images ? "images" : "videos")
    function refresh() {
        loading = true
        fetch.connectSource(command)
    }
    Component.onCompleted: refresh()
    onCommandChanged: if (fetch && (images || videos)) refresh()
    P5.DataSource {
        id: fetch
        engine: "executable"
        onNewData: (name, data) => {
            disconnectSource(name)
            if (name !== page.command) return
            try { page.recent = JSON.parse(data.stdout) } catch (_) { page.recent = [] }
            page.loading = false
        }
    }
    RowLayout {
        Layout.fillWidth: true
        Item { Layout.fillWidth: true }
        IslandButton { text: i18n("Refresh"); icon.name: "view-refresh"; enabled: !page.loading; onClicked: page.refresh() }
    }
    C.Label {
        visible: !page.recent.length
        Layout.fillWidth: true
        text: page.loading ? i18n("Loading…") : i18n("No saved captures yet.")
        horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
    }
    C.ScrollView {
        Layout.fillWidth: true; Layout.fillHeight: true; clip: true
        ListView {
            id: files
            model: page.recent
            spacing: 4
            delegate: RowLayout {
                required property var modelData
                width: ListView.view.width
                K.Icon { source: modelData.video ? "video-x-generic" : "image-x-generic"; Layout.preferredWidth: 22; Layout.preferredHeight: 22 }
                C.Button {
                    Layout.fillWidth: true; Layout.minimumWidth: 0; flat: true
                    text: modelData.name; Accessible.name: text
                    contentItem: Text { text: parent.text; textFormat: Text.PlainText; color: "white"; elide: Text.ElideMiddle; verticalAlignment: Text.AlignVCenter }
                    onClicked: Qt.openUrlExternally(modelData.url)
                }
                IslandButton { visible: page.shelf; icon.name: "folder-add"; text: i18n("Add to file shelf"); onClicked: page.addFile(modelData.url) }
            }
        }
    }
}
