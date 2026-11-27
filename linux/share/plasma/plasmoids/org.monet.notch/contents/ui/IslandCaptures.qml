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
    required property bool showCopied
    signal addFile(string url)
    property var recent: []
    property bool loading: false
    property int filter: 0
    readonly property var shown: recent.filter(row => filter === 0 || (filter === 2) === !!row.video)
    readonly property string command: !images && !videos ? "" : helper + " notch-captures " + (images && videos ? "all" : images ? "images" : "videos")
    function refresh() {
        if (!images && !videos) { recent = []; loading = false; return }
        loading = true
        fetch.connectSource(command)
    }
    Component.onCompleted: refresh()
    onCommandChanged: if (fetch) refresh()
    P5.DataSource {
        id: fetch
        engine: "executable"
        onNewData: (name, data) => {
            disconnectSource(name)
            if (name !== page.command || (!page.images && !page.videos)) return
            try { page.recent = JSON.parse(data.stdout) } catch (_) { page.recent = [] }
            page.loading = false
        }
    }
    Loader {
        id: copies
        active: page.showCopied; visible: active && !!item?.count
        Layout.fillWidth: true
        source: "CopiedCaptures.qml"
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 6
        Repeater {
            model: [i18n("All"), i18n("Images"), i18n("Videos")]
            IslandButton { required property int index; required property string modelData
                caption: true; text: modelData; checked: page.filter === index
                visible: index === 0 || (index === 1 ? page.images : page.videos)
                onClicked: page.filter = index }
        }
        Item { Layout.fillWidth: true }
        IslandButton { plain: true; text: i18n("Refresh"); icon.name: "view-refresh"; enabled: !page.loading; onClicked: page.refresh() }
    }
    GridView {
        id: files; objectName: "notchCaptureGrid"
        visible: page.shown.length > 0
        Layout.fillWidth: true; Layout.fillHeight: true; clip: true
        cellWidth: width / Math.max(2, Math.floor(width / 140)); cellHeight: 126
        model: page.shown
        C.ScrollBar.vertical: C.ScrollBar {}
        delegate: C.AbstractButton {
            id: capture
            required property var modelData
            width: files.cellWidth - 6; height: 120; padding: 7; hoverEnabled: true
            Accessible.name: modelData.name
            onClicked: Qt.openUrlExternally(modelData.url)
            background: Rectangle { radius: 12; color: capture.hovered ? "#28282d" : "#19191d"; border.width: capture.visualFocus ? 1 : 0; border.color: "#aaaab2" }
            contentItem: ColumnLayout {
                spacing: 5
                Rectangle {
                    Layout.fillWidth: true; Layout.fillHeight: true; color: "#101013"; radius: 7; clip: true
                    Image { id: thumbnail; anchors.fill: parent; asynchronous: true; fillMode: Image.PreserveAspectFit
                        source: capture.modelData.video ? "" : capture.modelData.url; sourceSize.width: 320; sourceSize.height: 180 }
                    IslandGlyph { anchors.centerIn: parent; width: 26; height: 26; visible: thumbnail.status !== Image.Ready
                        source: capture.modelData.video ? "video" : "image"; color: "#888893" }
                }
                RowLayout {
                    Text { Layout.fillWidth: true; text: capture.modelData.name; textFormat: Text.PlainText; color: "#dedee5"; font.pixelSize: 10; elide: Text.ElideMiddle }
                    IslandButton { visible: page.shelf; plain: true; implicitWidth: 22; implicitHeight: 22; glyphSize: 12
                        icon.name: "plus"; text: i18n("Add to file shelf"); onClicked: page.addFile(capture.modelData.url) }
                }
            }
        }
    }
    IslandEmpty {
        visible: !page.shown.length && !copies.item?.count
        Layout.fillWidth: true; Layout.fillHeight: true
        symbol: "image-x-generic"; tint: "#99c7ed"
        title: page.loading ? i18n("Loading…") : page.recent.length ? i18n("No captures in this category") : i18n("No saved captures yet.")
        detail: i18n("Your screenshots and recordings appear here.")
    }

}
