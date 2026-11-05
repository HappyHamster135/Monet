import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5Support
import "../../../org.monet.performance/contents/ui" as Performance

ColumnLayout {
    id: startup
    objectName: "monetStartup"
    property string helper: "@LIBEXECDIR@/monet-startup"
    property var entries: []
    property bool adding: false
    property bool busy: false
    property bool loaded: false
    property string problem: ""
    property string message: ""
    property int serial: 0
    readonly property bool dark: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    readonly property color ink: dark ? "#F1EEE8" : "#1C1B19"
    readonly property color lily: dark ? "#62B6A6" : "#357F72"
    readonly property color wash: dark ? Qt.rgba(1, 1, 1, 0.05) : Qt.rgba(0.11, 0.106, 0.098, 0.035)
    readonly property var filtered: entries.filter(item => item.name.toLocaleLowerCase().includes(search.text.toLocaleLowerCase()))
    Performance.WindowActivity { id: activity; item: startup }
    spacing: 14

    function request(args) {
        if (busy) return
        busy = true
        problem = ""
        message = ""
        reader.connectSource("'" + helper.replace(/'/g, "'\\''") + "' " + args + " # startup-" + (++serial))
    }
    function refresh() { request(adding ? "available" : "list") }
    function change(item) {
        // Only opaque IDs and revision hashes cross the executable engine.
        if (!/^(?:[0-9a-f]{2}){1,512}$/.test(item.id) || !/^[0-9a-f]{64}$/.test(item.token)) return
        request((adding ? "add " : "set ") + item.id + " " + item.token + (adding ? "" : item.enabled ? " off" : " on"))
    }
    Component.onCompleted: if (activity.active) refresh()
    Connections {
        target: activity
        function onActiveChanged() { if (activity.active && !startup.loaded && !startup.busy && !startup.problem) startup.refresh() }
    }
    P5Support.DataSource {
        id: reader
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            startup.busy = false
            try {
                const result = JSON.parse(data.stdout)
                if (data["exit code"] !== 0 || result.ok !== true || !Array.isArray(result.items)) throw new Error("failed")
                const changed = source.includes("' add ") || source.includes("' set ")
                if (changed) {
                    startup.adding = false
                    startup.message = i18nd("monet", "Saved. This takes effect next time you sign in. Running apps stay open.")
                }
                startup.entries = result.items
                startup.loaded = true
                if (result.unreadable) startup.problem = i18nd("monet", "Some startup entries could not be read. They have been left unchanged.")
            } catch (_) {
                startup.problem = i18nd("monet", "Startup apps could not be read or saved. An app may have changed its entry. Refresh and try again.")
            }
        }
    }
    component Action: QQC2.Button {
        id: button
        required property var tone
        Keys.onReturnPressed: if (enabled) clicked()
        Keys.onEnterPressed: if (enabled) clicked()
        implicitHeight: Math.max(38, contentItem.implicitHeight + 16)
        implicitWidth: contentItem.implicitWidth + 28
        contentItem: Text {
            text: button.text; color: button.enabled ? button.tone.ink : Kirigami.Theme.disabledTextColor
            font: button.font; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            radius: height / 2
            color: button.down ? Qt.alpha(button.tone.lily, 0.22) : button.hovered ? Qt.alpha(button.tone.lily, 0.12) : button.tone.wash
            border.color: button.activeFocus ? button.tone.lily : Qt.alpha(button.tone.ink, 0.16)
            border.width: button.activeFocus ? 2 : 1
        }
    }
    QQC2.Label {
        color: startup.ink
        text: i18nd("monet", "Startup")
        font.family: "Fraunces 72pt SuperSoft"; font.pixelSize: 30; font.weight: Font.Light
    }
    QQC2.Label {
        color: startup.ink
        Layout.fillWidth: true; wrapMode: Text.Wrap
        text: i18nd("monet", "Choose which apps open when you sign in. Restoring an earlier session is separate; switching an app off here does not close it or change its saved work.")
    }
    Flow {
        Layout.fillWidth: true; spacing: 8
        Action { tone: startup; objectName: "startupRefresh"; text: i18nd("monet", "Refresh"); enabled: !startup.busy; onClicked: startup.refresh() }
        Action { tone: startup;
            objectName: "startupAdd"; text: startup.adding ? i18nd("monet", "Back to startup apps") : i18nd("monet", "Add an app")
            enabled: !startup.busy
            onClicked: { startup.adding = !startup.adding; startup.entries = []; search.clear(); startup.refresh() }
        }
    }
    QQC2.TextField {
        id: search; objectName: "startupSearch"; Layout.fillWidth: true
        placeholderText: i18nd("monet", "Find an app…"); Accessible.name: placeholderText
        onTextChanged: startup.message = ""
        color: startup.ink
        placeholderTextColor: Qt.alpha(startup.ink, 0.65)
        selectionColor: startup.lily
        selectedTextColor: startup.dark ? "#1C1B19" : "#FFFFFF"
        leftPadding: 14; rightPadding: 14
        background: Rectangle {
            radius: 12; color: startup.wash
            border.color: search.activeFocus ? startup.lily : Qt.alpha(startup.ink, 0.16)
            border.width: search.activeFocus ? 2 : 1
        }
    }
    QQC2.Label {
        color: startup.ink
        objectName: "startupStatus"; Layout.fillWidth: true; wrapMode: Text.Wrap
        text: startup.busy ? i18nd("monet", "Loading…") : startup.problem || startup.message
            || (startup.filtered.length ? (startup.adding ? i18nd("monet", "Adding an app schedules it for your next sign-in.") : i18nd("monet", "Desktop components are managed by Monet."))
                : search.text ? i18nd("monet", "No matching apps.") : i18nd("monet", "No startup apps here yet."))
    }
    QQC2.ScrollView {
        Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumHeight: 180
        clip: true
        ListView {
            id: list; objectName: "startupList"; model: startup.filtered; spacing: 8
            clip: true; boundsBehavior: Flickable.StopAtBounds
            delegate: Rectangle {
                id: row
                required property var modelData
                required property int index
                width: list.width; height: contents.implicitHeight + 28
                radius: 16; color: startup.wash
                ColumnLayout {
                    id: contents; anchors.left: parent.left; anchors.right: parent.right
                    anchors.top: parent.top; anchors.margins: 14; spacing: 6
                    QQC2.Label {
                        color: startup.ink
                        Layout.fillWidth: true; text: row.modelData.name; textFormat: Text.PlainText
                        font.bold: true; wrapMode: Text.Wrap
                    }
                    QQC2.Label {
                        color: startup.ink
                        Layout.fillWidth: true; wrapMode: Text.Wrap
                        text: row.modelData.managed ? i18nd("monet", "Managed desktop component")
                            : !row.modelData.available ? i18nd("monet", "Unavailable in this desktop or the app is missing")
                            : row.modelData.conditional ? i18nd("monet", "Also follows the app's own startup preference")
                            : row.modelData.enabled && !startup.adding ? i18nd("monet", "Opens at sign-in") : i18nd("monet", "Does not open at sign-in")
                    }
                    Action { tone: startup;
                        objectName: "startupToggle-" + row.index
                        text: startup.adding ? i18nd("monet", "Add to startup") : row.modelData.enabled ? i18nd("monet", "Turn off") : i18nd("monet", "Turn on")
                        visible: !row.modelData.managed
                        enabled: !startup.busy && row.modelData.available
                        Accessible.name: text + " · " + row.modelData.name
                        onClicked: { list.currentIndex = row.index; startup.change(row.modelData) }
                    }
                }
            }
        }
    }
}
