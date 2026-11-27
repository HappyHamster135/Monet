import QtQuick
import QtQuick.Layouts

ColumnLayout {
    id: stats
    required property var history
    spacing: 8
    RowLayout {
        Layout.fillWidth: true; spacing: 4
        Repeater {
            model: [{key:"today",label:i18n("Today")},{key:"week",label:i18n("7 days")},{key:"month",label:i18n("30 days")}]
            IslandButton {
                required property var modelData
                objectName: "notchAgentPeriod-" + modelData.key
                Layout.fillWidth: true; Layout.preferredWidth: 0; Layout.minimumWidth: 0
                caption: true; text: modelData.label; checked: stats.history?.period === modelData.key
                implicitHeight: 27; onClicked: stats.history.period = modelData.key
            }
        }
        IslandButton {
            objectName: "notchAgentHistoryRefresh"; plain: true; implicitWidth: 27; implicitHeight: 27
            icon.name: "view-refresh"; text: i18n("Refresh usage"); enabled: !stats.history?.pending
            onClicked: stats.history.refresh(true)
        }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 8
        AgentMetricCard {
            objectName: "notchAgentSpend"
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 0
            heading: i18n("Spend"); symbol: "wallet"; accent: "#ededf2"
            value: stats.history?.cost(stats.history.total) || "—"
            detail: i18n("Estimated API value · USD")
            footnote: stats.history?.total.unpriced ? i18n("Some model prices unavailable") : i18n("At current standard token rates")
        }
        AgentMetricCard {
            objectName: "notchAgentTokens"
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 0
            heading: i18n("Tokens"); symbol: "activity"; accent: "#b9c9ff"
            value: stats.history?.tokens(stats.history.total.tokens) || "—"
            detail: i18n("%1 in · %2 out", stats.history?.tokens(stats.history.total.input) || "—", stats.history?.tokens(stats.history.total.output) || "—")
            footnote: i18n("%1 requests · %2 sessions", stats.history?.total.requests ?? "—", stats.history?.total.sessions ?? "—")
        }
    }
}
