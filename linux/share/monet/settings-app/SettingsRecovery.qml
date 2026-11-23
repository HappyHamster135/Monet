// Loaded by the Settings page loader; shares its window context.
import QtCore
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Templates as T
import QtQuick.Window
import org.kde.kirigami as Kirigami
import "../games" as Shared
import "FocusNavigation.js" as FocusNavigation


ColumnLayout {
    function cancelConfirmation() {
        if (sheet.profileReview !== null) {
            if (!sheet.profileRestoring) {
                const id = sheet.profileReview.id
                sheet.profileReview = null
                sheet.focusControl("reviewProfile-" + id)
            }
        } else return false
        return true
    }
    spacing: 20
    SettingsControls.PageTitle {
        tone: look; entry: sheet.entry("recovery"); art: sheet.art
        text: i18n("Recovery")
        detail: i18n("Recover your files, return to an earlier system, or undo desktop changes.")
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look; divider: false
            title: i18n("Files and earlier versions")
            detail: i18n("Find a backup or restore an earlier copy of a file.")
            SettingsControls.Pill { tone: look; text: i18n("Open Backups"); onClicked: sheet.page = "backups" }
        }
        SettingsControls.SettingRow {
            tone: look; divider: false
            title: i18n("An earlier Monet system")
            detail: i18n("Check whether the previous system is available in Updates.")
            SettingsControls.Pill { tone: look; text: i18n("Open Updates"); onClicked: sheet.page = "updates" }
        }
    }
    SettingsControls.Caption { tone: look; text: i18n("Troubleshooting") }
    SettingsControls.Card {
        tone: look
        ColumnLayout {
            Layout.fillWidth: true; Layout.margins: 20; spacing: 12
            SettingsControls.MaintenanceText { tone: look; text: i18n("Check disk space, updates, backups and recovery availability. The report contains status facts only, with no account names, personal paths or log contents. Nothing is sent.") }
            SettingsControls.Pill { tone: look; objectName: "checkRecoveryHealth"; text: sheet.healthBusy ? i18n("Checking…") : i18n("Check now"); enabledPill: !sheet.healthBusy; onClicked: sheet.checkHealth() }
            SettingsControls.MaintenanceText { tone: look; visible: sheet.healthError !== ""; text: sheet.healthError }
            SettingsControls.MaintenanceText { tone: look;
                visible: sheet.health.ok === true
                text: (sheet.health.low ? i18n("Storage is running low. Review Storage before installing updates.") : i18n("There is room on the system disk."))
                    + "\n" + (sheet.health.rollback === true ? i18n("An earlier system is available in Updates.") : sheet.health.rollback === false ? i18n("No earlier system is available yet.") : i18n("System rollback availability could not be checked."))
                    + "\n" + (sheet.health.services || []).filter(item => item.state === "failed").map(item => item.area === "updates" ? i18n("An update task failed. Open Updates to review and retry.") : i18n("A backup task failed. Open Backups to review it.")).join("\n")
            }
            Flow {
                Layout.fillWidth: true; spacing: 8
                SettingsControls.Pill { tone: look; text: i18n("Open Storage"); onClicked: sheet.page = "storage" }
                SettingsControls.Pill { tone: look; text: i18n("Open Updates"); onClicked: sheet.page = "updates" }
                SettingsControls.Pill { tone: look; text: i18n("Open Backups"); onClicked: sheet.page = "backups" }
            }
            QQC2.TextArea {
                id: recoveryReport; objectName: "recoveryReport"
                Layout.fillWidth: true; visible: sheet.health.ok === true
                readOnly: true; selectByMouse: true; wrapMode: TextEdit.Wrap
                textFormat: TextEdit.PlainText; text: sheet.health.report || ""
                color: look.ink; background: Rectangle { color: look.wash; radius: 12 }
                Accessible.name: i18n("Diagnostic report preview")
            }
            SettingsControls.Pill {
                tone: look; text: i18n("Copy report"); visible: sheet.health.ok === true
                onClicked: { recoveryReport.selectAll(); recoveryReport.copy(); recoveryReport.deselect() }
            }
        }
    }
    SettingsControls.Caption { tone: look; text: i18n("Undo desktop changes") }
    SettingsControls.Card {
        tone: look
        ColumnLayout {
            Layout.fillWidth: true; Layout.margins: 20; spacing: 12
            Text {
                Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1); color: look.dim
                text: i18n("Review changes Monet made to this account's settings and shortcuts. Newer personal choices are protected. This does not restore documents or change the installed system.")
            }
            SettingsControls.Pill {
                tone: look; objectName: "refreshProfileHistory"
                text: sheet.profileLoading ? i18n("Loading…") : i18n("Refresh")
                enabledPill: !sheet.profileLoading && !sheet.profileRestoring
                onClicked: sheet.loadProfileHistory()
            }
            Text {
                Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1); color: look.dim
                objectName: "profileHistoryStatus"
                text: sheet.profileLoading ? i18n("Loading saved desktop changes…")
                    : sheet.profileState === "busy" ? i18n("Desktop settings are being updated. Wait for that to finish, then refresh.")
                    : sheet.profileState !== "ready" ? i18n("Saved desktop changes could not be read. The record has been kept; try refreshing.")
                    : sheet.profileHistory.length === 0 ? i18n("No saved desktop changes yet.")
                    : i18n("Recent changes, newest first. Review one before undoing it.")
            }
            Text {
                Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1); color: look.ink
                objectName: "profileRecoveryResult"
                visible: text !== ""; text: sheet.profileMessage
                Accessible.role: Accessible.StaticText
            }
        }
    }
    Repeater {
        model: sheet.profileHistory
        SettingsControls.Card {
            required property var modelData
            id: historyCard
            tone: look
            ColumnLayout {
                Layout.fillWidth: true; Layout.margins: 20; spacing: 12
                Text {
                    Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1); color: look.ink; font.bold: true
                    text: new Date(historyCard.modelData.time).toLocaleString(Qt.locale(), Locale.ShortFormat)
                        + " · " + sheet.profileStatus(historyCard.modelData)
                }
                Text {
                    Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1); color: look.dim
                    text: sheet.profileAreas(historyCard.modelData)
                }
                Text {
                    Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1); color: look.dim
                    text: [i18np("%1 setting", "%1 settings", historyCard.modelData.settings),
                           i18np("%1 shortcut", "%1 shortcuts", historyCard.modelData.shortcuts),
                           i18np("%1 change remaining", "%1 changes remaining", historyCard.modelData.remaining)].join(" · ")
                }
                SettingsControls.Pill {
                    id: reviewChanges
                    tone: look; objectName: "reviewProfile-" + historyCard.modelData.id
                    text: i18n("Review changes")
                    visible: historyCard.modelData.remaining > 0
                    enabledPill: !sheet.profileLoading && !sheet.profileRestoring
                    onClicked: { sheet.reviewProfile(historyCard.modelData); Qt.callLater(() => cancelUndo.forceActiveFocus()) }
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 12
                    visible: sheet.profileReview !== null && sheet.profileReview.id === historyCard.modelData.id
                    Text {
                        Layout.fillWidth: true; wrapMode: Text.Wrap; font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1); color: look.ink
                        text: i18n("Undo this set of desktop changes? Only settings and shortcuts that still match the saved changes will be restored. Your apps stay open. Save your work before signing out later.")
                    }
                    Flow {
                        Layout.fillWidth: true; spacing: 8
                        SettingsControls.Pill {
                            id: cancelUndo
                            tone: look; text: i18n("Cancel"); objectName: "cancelProfileUndo-" + historyCard.modelData.id
                            enabledPill: !sheet.profileRestoring
                            onClicked: { sheet.profileReview = null; reviewChanges.forceActiveFocus() }
                        }
                        SettingsControls.Pill {
                            tone: look; kind: "lily"; objectName: "confirmProfileUndo-" + historyCard.modelData.id
                            text: sheet.profileRestoring ? i18n("Undoing…") : i18n("Undo these changes")
                            enabledPill: !sheet.profileLoading && !sheet.profileRestoring
                            onClicked: sheet.undoProfile()
                        }
                    }
                }
            }
        }
    }
}
