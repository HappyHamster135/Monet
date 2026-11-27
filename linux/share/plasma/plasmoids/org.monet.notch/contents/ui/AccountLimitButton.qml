import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts

C.AbstractButton {
    id: card
    required property var usage
    property string providerName: ""
    readonly property color accent: providerName === "Codex" ? "#7d99ff" : "#d97a57"
    readonly property var windows: (usage.result.rows || []).slice(0, 2)
    readonly property string subtitle: usage.result.summary || (usage.enabled ? i18n("Checking account limits…") : i18n("Connect your CLI to see account limits and resets."))
    implicitWidth: 200; implicitHeight: 152
    padding: 12; hoverEnabled: true
    Accessible.name: providerName
    Accessible.description: [subtitle, usage.result.details || "", usage.problem || ""].filter(Boolean).join(" · ")
    Accessible.onPressAction: click()
    Keys.onReturnPressed: click()
    Keys.onEnterPressed: click()
    background: Rectangle {
        radius: 18; color: card.down ? "#2b2b30" : card.hovered ? "#232326" : "#171719"
        border.width: card.visualFocus ? 1 : 0; border.color: card.accent
    }
    contentItem: ColumnLayout {
        spacing: 6
        RowLayout {
            Layout.fillWidth: true; spacing: 6
            IslandGlyph {
                source: card.providerName === "Codex" ? "code" : "sparkles"
                color: card.accent; Layout.preferredWidth: 15; Layout.preferredHeight: 15
            }
            Text {
                Layout.fillWidth: true; Layout.minimumWidth: 0
                text: card.providerName; color: "#ededf2"; font.pixelSize: 11; font.weight: Font.DemiBold
                textFormat: Text.PlainText; elide: Text.ElideRight
            }
            IslandGlyph { source: "forward"; color: "#707078"; Layout.preferredWidth: 10; Layout.preferredHeight: 10 }
        }
        ColumnLayout {
            Layout.fillWidth: true; Layout.fillHeight: true; spacing: 7
            visible: card.windows.length > 0
            Repeater {
                // Permanent slots: a background refresh updates their values in place.
                model: 2
                ColumnLayout {
                    id: quota
                    required property int index
                    readonly property var reading: card.windows[index] || null
                    readonly property real remaining: Number(reading?.value)
                    readonly property bool known: !!reading && Number.isFinite(remaining)
                    readonly property color tint: known && remaining <= 5 ? "#ff686e" : known && remaining <= 20 ? "#ffb257" : card.accent
                    Layout.fillWidth: true; Layout.minimumWidth: 0; spacing: 3
                    opacity: reading ? 1 : 0
                    objectName: "notchOverviewQuota-" + index
                    RowLayout {
                        Layout.fillWidth: true; spacing: 4
                        Text {
                            Layout.fillWidth: true; Layout.minimumWidth: 0
                            text: quota.reading?.name || ""; textFormat: Text.PlainText
                            color: "#b3b3bc"; font.pixelSize: 10; elide: Text.ElideRight
                        }
                        Text {
                            Layout.maximumWidth: quota.width * 0.55
                            text: quota.reading?.remaining || ""; textFormat: Text.PlainText
                            color: quota.tint; font.pixelSize: 10; font.weight: Font.Medium; elide: Text.ElideRight
                        }
                    }
                    Rectangle {
                        Layout.fillWidth: true; implicitHeight: 4; radius: 2; color: "#35353a"
                        Rectangle {
                            height: parent.height; radius: height / 2; color: quota.tint
                            width: parent.width * (quota.known ? Math.max(0, Math.min(100, quota.remaining)) / 100 : 0)
                        }
                    }
                    Text {
                        Layout.fillWidth: true; Layout.minimumWidth: 0
                        text: quota.reading?.reset || ""; textFormat: Text.PlainText
                        color: "#7f7f89"; font.pixelSize: 9; elide: Text.ElideRight
                    }
                }
            }
        }
        Text {
            Layout.fillWidth: true; Layout.fillHeight: true; Layout.minimumWidth: 0
            visible: !card.windows.length
            text: card.subtitle; textFormat: Text.PlainText
            color: "#8c8c96"; font.pixelSize: 11; wrapMode: Text.Wrap; maximumLineCount: 3; elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }
        Text {
            Layout.fillWidth: true; Layout.minimumWidth: 0; Layout.preferredHeight: 12
            text: card.usage.problem ? i18n("Last known usage") : card.usage.pending ? i18n("Updating…")
                : card.windows.length ? card.usage.result.checked || i18n("Account limits") : card.usage.enabled ? i18n("View details") : i18n("Connect account")
            textFormat: Text.PlainText; elide: Text.ElideRight; font.pixelSize: 9
            color: card.usage.problem ? "#d7ad73" : card.windows.length ? "#777781" : card.accent
        }
    }
}
