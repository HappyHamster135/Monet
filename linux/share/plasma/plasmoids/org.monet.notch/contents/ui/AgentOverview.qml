import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: page
    required property var codex
    required property var claude
    required property bool presented
    required property bool sessionSelected
    required property string widgetId
    property var history: null
    property alias sessionReading: session.reading
    signal selected(string provider)
    spacing: 8
    AgentStats { Layout.fillWidth: true; visible: !!page.history; history: page.history }
    // Each provider owns a permanent slot, whether connected, loading or ready.
    RowLayout {
        Layout.fillWidth: true; spacing: 8
        AccountLimitButton {
            objectName: "notchAgent-codex"; Layout.fillWidth: true; Layout.minimumWidth: 0
            usage: page.codex; providerName: "Codex"
            onClicked: page.selected("codex")
        }
        AccountLimitButton {
            objectName: "notchAgent-claude"; Layout.fillWidth: true; Layout.minimumWidth: 0
            usage: page.claude; providerName: "Claude"
            onClicked: page.selected("claude")
        }
    }
    AgentActivity { Layout.fillWidth: true; visible: !!page.history; history: page.history }
    SessionButton {
        id: session; objectName: "notchAgent-session"
        Layout.fillWidth: true; Layout.minimumWidth: 0; visible: true
        widgetId: page.widgetId; active: page.sessionSelected && page.presented
        subtitle: page.sessionSelected ? text : i18n("Follow activity and token usage from a session file.")
        connected: page.sessionSelected && !!reading
        onClicked: page.selected("session")
    }
    Text { visible: !page.history; Layout.fillWidth: true; text: i18n("Account limits · Local session activity"); color: "#777781"; font.pixelSize: 10; elide: Text.ElideRight }
    Item { Layout.fillHeight: true }
}
