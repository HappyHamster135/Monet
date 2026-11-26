import QtQuick
import QtQuick.Controls as C
import QtQuick.Dialogs as D
import QtQuick.Layouts
import org.kde.plasma.plasma5support as P5

ColumnLayout {
    id: page
    required property string provider
    required property bool presented
    signal settingsChanged()
    readonly property bool choosingFile: picker.visible
    property var result: ({})
    property string pending: ""
    property string problem: ""
    function read(action, extra = "") {
        if (pending || !presented) return
        pending = "/usr/bin/python3 '@DATADIR@/monet/utilities/notch_agents.py' " + provider + " " + action + (extra ? " " + extra : "")
        source.connectSource(pending)
    }
    Component.onCompleted: read("read")
    onPresentedChanged: if (presented) Qt.callLater(() => read("read"))
    Timer { repeat: true; interval: page.provider === "session" ? 12000 : 60000
        running: page.presented && !!(page.result.enabled || page.result.name)
        onTriggered: page.read("read")
    }
    P5.DataSource {
        id: source; engine: "executable"; connectedSources: []
        onNewData: (cmd, data) => {
            disconnectSource(cmd)
            if (page.pending !== cmd) return
            page.pending = ""
            let next = null
            try { next = JSON.parse(data.stdout) } catch (_) {}
            page.problem = next?.ok ? "" : i18n("Could not read the selected source.")
            if (next?.ok) page.result = next
            if (!cmd.endsWith(" read")) page.settingsChanged()
        }
    }
    D.FileDialog {
        id: picker; title: page.provider === "session" ? i18n("Choose a local session log or database")
            : page.provider === "codex" ? i18n("Choose the Codex CLI executable") : i18n("Choose the Claude Code executable")
        onAccepted: {
            const data = unescape(encodeURIComponent(String(selectedFile)))
            page.read(page.provider === "session" ? "select" : "cli", Array.from(data,c => c.charCodeAt(0).toString(16).padStart(2,"0")).join(""))
        }
    }
    RowLayout {
        Layout.fillWidth: true
        C.Label { Layout.fillWidth: true; elide: Text.ElideRight; textFormat: Text.PlainText; font.bold: true
            text: page.provider === "session" ? (page.result.name || i18n("Session file")) : i18n("Account limits") }
        IslandButton { visible: page.provider === "session"; caption: true; text: i18n("Choose session…"); onClicked: picker.open() }
        IslandButton { visible: page.provider !== "session"; enabled: !page.pending; caption: true
            text: page.result.enabled ? i18n("Disconnect") : i18n("Connect"); onClicked: page.read(page.result.enabled ? "off" : "on") }
        IslandButton { visible: !!page.result.enabled || !!page.result.name; enabled: !page.pending
            text: i18n("Refresh"); icon.name: "view-refresh"; onClicked: page.read(page.provider === "session" ? "read" : "refresh") }
    }
    C.ScrollView {
        id: content
        Layout.fillWidth: true; Layout.fillHeight: true; clip: true; contentWidth: availableWidth
        ColumnLayout {
            width: content.availableWidth; spacing: 6
            C.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; textFormat: Text.PlainText
                text: page.problem || (page.pending && !page.result.ok ? i18n("Loading…") : (page.result.state && page.result.state !== "ready" ? page.result.details : page.result.summary) ||
                    (page.provider === "session" ? i18n("Choose a local session log to see its activity and token usage.") :
                     i18n("Connect to read limits from your signed-in CLI on this computer."))) }
            Repeater {
                model: page.result.rows || []
                ColumnLayout { required property var modelData; Layout.fillWidth: true
                    C.Label { text: modelData.name + " · " + modelData.remaining }
                    C.ProgressBar { Layout.fillWidth: true; from: 0; to: 100; value: modelData.value }
                    C.Label { text: modelData.reset || ""; visible: !!text; opacity: 0.7 }
                }
            }
            IslandButton {
                visible: page.provider !== "session" && !!page.result.enabled && page.result.state !== "ready"
                caption: true; enabled: !page.pending
                text: page.provider === "codex" ? i18n("Choose Codex CLI…") : i18n("Choose Claude Code CLI…")
                onClicked: picker.open()
            }
            C.Label { visible: !!page.result.checked; text: page.result.checked || "" }
            IslandButton { visible: page.provider === "session" && !!page.result.name; caption: true
                text: i18n("Forget session"); enabled: !page.pending; onClicked: page.read("forget") }
        }
    }
}
