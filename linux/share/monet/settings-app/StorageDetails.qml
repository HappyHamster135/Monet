import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: view
    objectName: "storageDetailsView"
    required property var host
    property var info: ({})
    property bool busy: false
    property bool confirming: false
    property string message: ""
    signal finished()
    function refresh() {
        if (busy) return
        busy = true; message = ""; confirming = false
        host.ask("storage-details", out => {
            busy = false
            const result = host.json(out, {})
            if (result.ok === true) info = result
            else message = i18n("Storage details couldn't be read. Try again.")
        })
    }
    function clean() {
        if (busy || !info.token) return
        busy = true; confirming = false
        host.ask("storage-unused-clean " + info.token, out => {
            busy = false
            const result = host.json(out, {})
            message = result.ok === true ? i18n("Unused app support files were removed.")
                : result.problem === "changed" ? i18n("The installed apps changed. Refresh and review the cleanup again.")
                : i18n("Cleanup couldn't finish. Check permissions and try again.")
            if (result.ok === true) info = Object.assign({}, info, {unused: [], token: ""})
        })
    }
    spacing: 12
    RowLayout {
        Layout.fillWidth: true
        QQC2.Button { text: i18n("Refresh"); enabled: !view.busy; onClicked: view.refresh() }
        QQC2.BusyIndicator { running: view.busy; visible: running; Layout.preferredHeight: 28; Layout.preferredWidth: 28 }
        QQC2.Label { Layout.fillWidth: true; visible: view.busy; text: i18n("Checking storage…") }
    }
    QQC2.Label { Layout.fillWidth: true; visible: view.message !== ""; text: view.message; wrapMode: Text.WordWrap }
    QQC2.ScrollView {
        id: scroll
        Layout.fillWidth: true; Layout.fillHeight: true
        contentWidth: availableWidth
        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
        ColumnLayout {
            width: scroll.availableWidth
            spacing: 14
            QQC2.Label { text: i18n("See exactly where the space goes"); font.bold: true; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            QQC2.Label { Layout.fillWidth: true; text: i18n("Explore folders and individual files in an interactive disk map. Large folders are easy to spot, and you can open them in Files to manage their contents."); wrapMode: Text.WordWrap }
            Flow {
                Layout.fillWidth: true
                spacing: 8
                QQC2.Button { objectName: "storageMapHome"; text: i18n("Analyze your files"); onClicked: view.host.ask("storage-map home", view.openedMap) }
                QQC2.Button { objectName: "storageMapDisk"; text: i18n("Analyze the whole disk"); onClicked: view.host.ask("storage-map disk", view.openedMap) }
                QQC2.Button { text: i18n("Manage apps"); onClicked: view.host.ask("launch " + view.host.hex("monet-apps.desktop")) }
            }
            QQC2.Label { text: i18n("Unused app support files"); font.bold: true; Layout.fillWidth: true; wrapMode: Text.WordWrap }
            QQC2.Label {
                Layout.fillWidth: true; wrapMode: Text.WordWrap
                text: view.info.unusedKnown !== true ? i18n("App support files couldn't be checked.")
                    : (view.info.unused || []).length === 0 ? i18n("No unused app support files were found.")
                    : i18n("These components are not needed by installed apps. Pinned components and personal files are kept. Shared data means the space freed can be smaller than the listed sizes.")
            }
            Repeater {
                model: view.info.unused || []
                QQC2.Label {
                    required property var modelData
                    Layout.fillWidth: true
                    text: modelData.name + " · " + view.host.bytes(modelData.size)
                    textFormat: Text.PlainText; wrapMode: Text.WrapAnywhere
                }
            }
            QQC2.Button {
                objectName: "storageUnusedReview"
                visible: (view.info.unused || []).length > 0 && !view.confirming
                enabled: !view.busy
                text: i18n("Review cleanup…"); onClicked: view.confirming = true
            }
            RowLayout {
                visible: view.confirming
                QQC2.Button { text: i18n("Cancel"); enabled: !view.busy; onClicked: view.confirming = false }
                QQC2.Button { objectName: "storageUnusedConfirm"; text: i18n("Remove unused support files"); enabled: !view.busy; onClicked: view.clean() }
            }
            QQC2.Label { text: i18n("App cache"); font.bold: true; Layout.fillWidth: true }
            QQC2.Label {
                Layout.fillWidth: true; wrapMode: Text.WordWrap
                text: (typeof view.info.cacheSize === "number" ? view.host.bytes(view.info.cacheSize) + " · " : "")
                    + i18n("Temporary files that apps can recreate. Review the folders before removing anything; apps may need to download cached files again.")
            }
            QQC2.Button { text: i18n("Review cache folders"); enabled: !!view.info.cache; onClicked: Qt.openUrlExternally(view.info.cache) }
            QQC2.Label { text: i18n("Older downloads to review"); font.bold: true; Layout.fillWidth: true }
            QQC2.Label { Layout.fillWidth: true; wrapMode: Text.WordWrap; text: i18n("These downloads haven't changed for at least 90 days. That doesn't mean they are unused—choose which ones you still need.") }
            Repeater {
                model: view.info.oldDownloads || []
                QQC2.Label { required property var modelData; Layout.fillWidth: true; text: modelData.name + " · " + view.host.bytes(modelData.size); textFormat: Text.PlainText; wrapMode: Text.WrapAnywhere }
            }
            QQC2.Button { text: i18n("Review Downloads"); enabled: !!view.info.downloads; onClicked: Qt.openUrlExternally(view.info.downloads) }
        }
    }
    function openedMap(out) { if (host.json(out, {}).ok !== true) message = i18n("The disk usage map couldn't open. Try again.") }
}
