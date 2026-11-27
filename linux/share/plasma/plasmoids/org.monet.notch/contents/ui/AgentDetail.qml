import QtQuick
import QtQuick.Controls as C
import QtQuick.Dialogs as D
import QtQuick.Layouts
import org.kde.plasma.plasma5support as P5

ColumnLayout {
    id: page
    required property string provider
    required property bool presented
    property var usage: null
    signal settingsChanged()
    readonly property bool choosingFile: picker.visible
    property var result: usage ? usage.result : ({})
    property string pending: usage ? usage.pending : ""
    property string problem: usage ? usage.problem : ""
    readonly property bool connectedSource: usage ? usage.enabled : !!result.enabled
    readonly property bool unconfigured: !connectedSource && !result.name && !problem && !pending
    ListModel { id: limits }
    function updateRows() {
        if (!limits) return
        const rows = result.rows || []
        for (let i = limits.count - 1; i >= 0; --i)
            if (!rows.some(row => row.name === limits.get(i).name)) limits.remove(i)
        for (const row of rows) {
            const values = {name: String(row.name), remaining: String(row.remaining), reset: String(row.reset || ""), value: Number(row.value)}
            let index = -1
            for (let i = 0; i < limits.count; ++i) if (limits.get(i).name === row.name) { index = i; break }
            if (index < 0) limits.append(values)
            else limits.set(index, values)
        }
    }
    onResultChanged: updateRows()
    function read(action, extra = "") {
        if (pending || !presented) return
        if (usage) { usage.read(action, extra); return }
        pending = "/usr/bin/python3 '@DATADIR@/monet/utilities/notch_agents.py' " + provider + " " + action + (extra ? " " + extra : "")
        source.connectSource(pending)
    }
    Component.onCompleted: { updateRows(); if (usage) usage.refreshIfNeeded(); else read("read") }
    onPresentedChanged: if (presented) Qt.callLater(() => { if (usage) usage.refreshIfNeeded(); else read("read") })
    Timer { repeat: true; interval: page.provider === "session" ? 12000 : 60000
        running: !page.usage && page.presented && !!(page.result.enabled || page.result.name)
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
        C.Label { Layout.fillWidth: true; elide: Text.ElideRight; textFormat: Text.PlainText; font.bold: true; font.pixelSize: 13
            text: page.provider === "session" ? (page.result.name || i18n("Session file")) : i18n("Account limits") }
        IslandButton { visible: page.provider === "session"; caption: true; text: i18n("Choose session…"); onClicked: picker.open() }
        IslandButton { visible: page.provider !== "session"; enabled: !page.pending; caption: true
            text: page.connectedSource ? i18n("Disconnect") : i18n("Connect"); onClicked: page.read(page.connectedSource ? "off" : "on") }
        IslandButton { visible: page.connectedSource || !!page.result.name; enabled: !page.pending
            text: i18n("Refresh"); icon.name: "view-refresh"; onClicked: page.read(page.provider === "session" ? "read" : "refresh") }
    }
    C.ScrollView {
        id: content
        visible: !page.unconfigured
        implicitWidth: 240; implicitHeight: 180
        Layout.fillWidth: true; Layout.fillHeight: true; clip: true; contentWidth: availableWidth
        ColumnLayout {
            width: content.availableWidth; spacing: 6
            C.Label { font.pixelSize: 12; color: "#b0b0bc"; Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredHeight: 34
                wrapMode: Text.Wrap; maximumLineCount: 2; elide: Text.ElideRight; textFormat: Text.PlainText
                text: page.problem || (page.pending && !page.result.ok ? i18n("Loading…") : (page.result.state && page.result.state !== "ready" ? page.result.details : page.result.summary) ||
                    (page.provider === "session" ? i18n("Choose a local session log to see its activity and token usage.") :
                     i18n("Connect to read limits from your signed-in CLI on this computer."))) }
            Repeater {
                model: limits
                Rectangle {
                    id: quota
                    required property var model
                    objectName: "notchQuota-" + model.name
                    Layout.fillWidth: true; implicitHeight: 84; radius: 12; color: "#19191d"
                    ColumnLayout {
                        anchors.fill: parent; anchors.margins: 12; spacing: 7
                        RowLayout {
                            Layout.fillWidth: true; Layout.minimumWidth: 0
                            Text { Layout.fillWidth: true; Layout.minimumWidth: 0; text: quota.model.name; elide: Text.ElideRight; color: "#ededf2"; font.pixelSize: 12 }
                            Text { Layout.maximumWidth: (quota.width - 24) * 0.4; Layout.minimumWidth: 0; elide: Text.ElideRight
                                text: quota.model.remaining; color: "#ededf2"; font.pixelSize: 12; font.weight: Font.DemiBold }
                        }
                        Rectangle {
                            Layout.fillWidth: true; height: 4; radius: 2; color: "#333339"
                            Rectangle { width: parent.width * Math.max(0,Math.min(1,quota.model.value / 100)); height: 4; radius: 2; color: quota.model.value < 15 ? "#ffad53" : "#dedee5" }
                        }
                        Text { Layout.fillWidth: true; Layout.minimumWidth: 0; text: quota.model.reset; elide: Text.ElideRight; color: "#9999a4"; font.pixelSize: 10 }
                    }
                }
            }
            IslandButton {
                visible: page.provider !== "session" && page.connectedSource && page.result.state !== "ready"
                caption: true; enabled: !page.pending
                text: page.provider === "codex" ? i18n("Choose Codex CLI…") : i18n("Choose Claude Code CLI…")
                onClicked: picker.open()
            }
            C.Label { font.pixelSize: 10; color: "#888894"; Layout.fillWidth: true; Layout.minimumWidth: 0; elide: Text.ElideRight
                visible: !!page.result.checked; text: page.pending ? i18n("Updating · %1", page.result.checked) : page.result.checked || "" }
            IslandButton { visible: page.provider === "session" && !!page.result.name; caption: true
                text: i18n("Forget session"); enabled: !page.pending; onClicked: page.read("forget") }
        }
    }
    IslandEmpty {
        visible: page.unconfigured
        Layout.fillWidth: true; Layout.fillHeight: true
        symbol: page.provider === "session" ? "code" : "terminal"
        tint: page.provider === "claude" ? "#dbab8e" : "#a6d9ca"
        title: page.provider === "session" ? i18n("Follow a local session") : i18n("Your usage, at a glance")
        detail: page.provider === "session" ? i18n("Choose a session log to see its latest activity and token usage.") : i18n("Connect your signed-in CLI to see available limits and reset times.")
    }

}
