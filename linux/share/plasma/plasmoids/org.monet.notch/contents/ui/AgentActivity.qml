import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts

ColumnLayout {
    id: page
    required property var history
    property bool byCost: true
    property int selectedBucket: -1
    readonly property var buckets: history?.reading.buckets || []
    readonly property real peak: Math.max(1e-9, ...buckets.map(b=>byCost ? b.cost : b.tokens))
    function tint(provider) { return provider === "codex" ? "#7d99ff" : "#d97a57" }
    function name(provider) { return provider === "codex" ? "Codex" : "Claude" }
    function when(stamp) { return stamp ? Qt.formatDateTime(new Date(stamp*1000), "ddd hh:mm") : "" }
    Connections { target: page.history; function onPeriodChanged() { page.selectedBucket = -1 } }
    spacing: 8
    Rectangle {
        objectName: "notchAgentTrend"
        Layout.fillWidth: true; implicitHeight: 137; radius: 18; color: "#171719"
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 12; spacing: 5
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; color: "#b6b6c0"; text: i18n("Usage history"); font.pixelSize: 11 }
                IslandButton { caption: true; implicitHeight: 23; text: i18n("Cost"); checked: page.byCost; onClicked: page.byCost = true }
                IslandButton { caption: true; implicitHeight: 23; text: i18n("Tokens"); checked: !page.byCost; onClicked: page.byCost = false }
            }
            RowLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: page.buckets.length > 24 ? 3 : 4
                Repeater {
                    model: page.buckets.length
                    C.AbstractButton {
                        id: bar
                        required property int index
                        readonly property var reading: page.buckets[index] || ({})
                        readonly property real value: page.byCost ? reading.cost || 0 : reading.tokens || 0
                        Layout.fillWidth: true; Layout.fillHeight: true; Layout.preferredWidth: 0; Layout.minimumWidth: 0
                        Accessible.name: reading.label + ": " + (page.byCost ? page.history.cost(reading) : page.history.tokens(reading.tokens))
                        onClicked: page.selectedBucket = index
                        contentItem: Item {
                            Rectangle {
                                anchors.bottom: parent.bottom; width: parent.width
                                height: Math.max(2, parent.height * bar.value / page.peak)
                                radius: Math.min(3, width/2); color: page.selectedBucket === bar.index ? "#c3ceff" : bar.value ? "#7d99ff" : "#35353b"
                                border.width: bar.visualFocus ? 1 : 0; border.color: "white"
                            }
                        }
                        background: Item {}
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; Layout.minimumWidth: 0; color: "#8e8e99"; font.pixelSize: 9; elide: Text.ElideRight
                    text: page.selectedBucket >= 0 && page.buckets[page.selectedBucket]
                        ? page.buckets[page.selectedBucket].label + " · " + (page.byCost ? page.history.cost(page.buckets[page.selectedBucket]) : page.history.tokens(page.buckets[page.selectedBucket].tokens))
                        : page.buckets[0]?.label || i18n("No recorded activity") }
                Text { color: "#8e8e99"; font.pixelSize: 9; text: page.buckets[page.buckets.length-1]?.label || "" }
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true; spacing: 8
        AgentMetricCard {
            objectName: "notchAgentCache"
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 0
            heading: i18n("Cache savings"); symbol: "copy"; accent: "#a6d9ca"
            value: page.history?.total.unpriced === page.history?.total.requests && page.history?.total.requests > 0 ? "—" : page.history?.money(page.history.total.savings) || "—"
            detail: i18n("%1% of input cached", Math.round((page.history?.total.cacheRate || 0)*100))
            footnote: i18n("Estimated API savings · USD")
        }
        AgentMetricCard {
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredWidth: 0
            heading: i18n("Activity"); symbol: "calendar"; accent: "#e8c497"
            value: String(page.history?.total.activeDays ?? "—")
            detail: i18n("Active days in this period")
            footnote: i18n("%1 reasoning tokens", page.history?.tokens(page.history.total.reasoning) || "—")
        }
    }
    Rectangle {
        objectName: "notchAgentShare"
        Layout.fillWidth: true; implicitHeight: 117; radius: 18; color: "#171719"
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 12; spacing: 7
            Text { text: i18n("By agent"); color: "#b6b6c0"; font.pixelSize: 11 }
            Repeater {
                model: ["codex", "claude"]
                ColumnLayout {
                    id: provider
                    required property string modelData
                    readonly property var reading: page.history?.reading.providers?.[modelData] || ({})
                    Layout.fillWidth: true; spacing: 4
                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: page.name(provider.modelData); color: page.tint(provider.modelData); font.pixelSize: 11; Layout.fillWidth: true }
                        Text { text: (page.history?.tokens(provider.reading.tokens) || "—") + " · " + (page.history?.cost(provider.reading) || "—"); color: "#b6b6c0"; font.pixelSize: 10 }
                    }
                    Rectangle {
                        Layout.fillWidth: true; height: 4; radius: 2; color: "#35353b"
                        Rectangle { height: 4; radius: 2; color: page.tint(provider.modelData); width: parent.width * ((provider.reading.tokens || 0) / Math.max(1,page.history?.total.tokens || 0)) }
                    }
                }
            }
        }
    }
    Rectangle {
        objectName: "notchAgentModels"
        Layout.fillWidth: true; implicitHeight: Math.max(77, modelRows.implicitHeight + 24); radius: 18; color: "#171719"
        ColumnLayout {
            id: modelRows
            anchors.left: parent.left; anchors.right: parent.right; anchors.top: parent.top; anchors.margins: 12; spacing: 8
            RowLayout {
                Layout.fillWidth: true
                Text { Layout.fillWidth: true; text: i18n("By model"); color: "#b6b6c0"; font.pixelSize: 11 }
                Text { text: i18n("Tokens / API value"); color: "#777781"; font.pixelSize: 9 }
            }
            Repeater {
                model: page.history?.reading.models || []
                RowLayout {
                    required property var modelData
                    Layout.fillWidth: true; spacing: 10
                    Text { Layout.fillWidth: true; Layout.minimumWidth: 0; text: parent.modelData.name; textFormat: Text.PlainText; color: "#d6d6de"; font.pixelSize: 10; elide: Text.ElideRight }
                    Text { text: page.history.tokens(parent.modelData.tokens); color: "#8f8f9b"; font.pixelSize: 10 }
                    Text { text: page.history.cost(parent.modelData); color: "#c4ceef"; font.pixelSize: 10 }
                }
            }
            Text { visible: !(page.history?.reading.models?.length); text: i18n("No local usage recorded in this period."); color: "#777781"; font.pixelSize: 10; Layout.fillWidth: true; wrapMode: Text.Wrap }
        }
    }
    Rectangle {
        objectName: "notchAgentNow"
        Layout.fillWidth: true; implicitHeight: 125; radius: 18; color: "#171719"
        ColumnLayout {
            anchors.fill: parent; anchors.margins: 12; spacing: 8
            Text { text: i18n("Recent activity"); color: "#b6b6c0"; font.pixelSize: 11 }
            Repeater {
                model: ["codex", "claude"]
                RowLayout {
                    id: live
                    required property string modelData
                    readonly property var reading: page.history?.result.activity?.find(r=>r.provider === modelData) || ({})
                    Layout.fillWidth: true; spacing: 8
                    Rectangle { width: 5; height: 5; radius: 2.5; color: live.reading.active ? page.tint(live.modelData) : "#505057" }
                    ColumnLayout {
                        Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 2
                        Text { Layout.fillWidth: true; text: page.name(live.modelData); font.pixelSize: 11; color: "#d6d6de" }
                        Text { Layout.fillWidth: true; Layout.minimumWidth: 0; text: live.reading.model || i18n("No local sessions"); font.pixelSize: 9; color: "#777781"; elide: Text.ElideRight }
                    }
                    Text { Layout.maximumWidth: page.width*0.4; text: live.reading.active ? i18n("%1 active",live.reading.active) : page.when(live.reading.last); font.pixelSize: 9; color: live.reading.active ? page.tint(live.modelData) : "#8f8f99"; elide: Text.ElideRight }
                }
            }
        }
    }
    Text {
        Layout.fillWidth: true; color: page.history?.failed ? "#d7ad73" : "#777781"; font.pixelSize: 9; wrapMode: Text.Wrap
        text: page.history?.failed ? i18n("Could not update. Showing saved usage.")
            : page.history?.pending ? i18n("Updating local usage…")
            : page.history?.result.partial ? i18n("Partial history · Some records are still loading or unavailable.")
            : i18n("Local Codex and Claude logs · Updated %1", page.history?.result.checked ? Qt.formatTime(new Date(page.history.result.checked*1000), "hh:mm") : "—")
    }
    Text { Layout.fillWidth: true; text: i18n("API estimates exclude subscription fees, credits and tool charges. Prices checked %1.", page.history?.result.pricingDate || "—"); color: "#64646f"; font.pixelSize: 9; wrapMode: Text.Wrap }
}
