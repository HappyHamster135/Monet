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
    spacing: 20
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("notifications")
        art: sheet.art
        text: i18n("Notifications")
        detail: i18n("What may interrupt you, and when it waits.")
    }
    SettingsControls.Card {
        tone: look
        enabled: sheet.notifyBusy === ""
        SettingsControls.SettingRow {
            objectName: "doNotDisturb"
            tone: look
            divider: false
            tappable: true
            checkable: true
            checked: sheet.notifyInfo.quiet === true
            title: i18n("Do not disturb")
            detail: sheet.quietDescription()
            onTapped: sheet.changeNotification("quiet " + (sheet.notifyInfo.quiet ? "off" : "on"))
            SettingsControls.Switch {
                tone: look
                active: sheet.notifyInfo.quiet === true
                Accessible.ignored: true
            }
        }
        Flow {
            Layout.fillWidth: true
            Layout.leftMargin: 18
            Layout.rightMargin: 18
            Layout.bottomMargin: 14
            spacing: 8
            Repeater {
                model: [["hour", i18n("For 1 hour")], ["four-hours", i18n("For 4 hours")],
                        ["tomorrow", i18n("Until tomorrow morning")]]
                SettingsControls.Pill {
                    objectName: "quiet-" + modelData[0]
                    tone: look
                    text: modelData[1]
                    onClicked: sheet.changeNotification("quiet " + modelData[0])
                }
            }
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Sounds")
            detail: i18n("Choose sounds for individual apps")
            SettingsControls.Pill {
                tone: look
                text: i18n("Choose…")
                onClicked: sheet.ask("kde notifications")
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("Quiet by itself")
    }
    SettingsControls.Card {
        tone: look
        enabled: sheet.notifyBusy === ""
        Repeater {
            model: [
                ["fullscreen", i18n("While a game or film fills the screen"), i18n("They wait until you're done")],
                ["mirrored", i18n("While you share or mirror your screen"), i18n("So nothing private pops up for others")],
                ["urgent", i18n("Let urgent ones through"), i18n("Like a low battery, even while quiet")]
            ]
            SettingsControls.SettingRow {
                id: ruleRow
                required property var modelData
                required property int index
                tone: look
                divider: index > 0
                tappable: true
                checkable: true
                checked: sheet.notifyInfo[modelData[0]] !== false
                title: modelData[1]
                detail: modelData[2]
                onTapped: sheet.notifyRule(modelData[0], sheet.notifyInfo[modelData[0]] === false)
                SettingsControls.Switch {
                    tone: look
                    active: sheet.notifyInfo[ruleRow.modelData[0]] !== false
                    Accessible.ignored: true
                }
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("Popups")
    }
    SettingsControls.Card {
        tone: look
        enabled: sheet.notifyBusy === ""
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Where they appear")
        }
        SettingsControls.Segments {
            Layout.leftMargin: 18
            Layout.rightMargin: 18
            Layout.bottomMargin: 14
            tone: look
            options: [["clock", i18n("By the clock")], ["topright", i18n("Top right")], ["topcenter", i18n("Top center")]]
            current: sheet.notifyInfo.place || "clock"
            onPicked: value => sheet.notifyPopups("place", value)
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("How long they stay")
            SettingsControls.Segments {
                tone: look
                options: [3, 5, 10].map(s => [s, i18n("%1 s", s)])
                current: sheet.notifyInfo.time || 5
                onPicked: value => sheet.notifyPopups("time", value)
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("Apps")
    }
    Repeater {
        model: sheet.notifyInfo.apps || []
        SettingsControls.Card {
            id: appCard
            required property var modelData
            tone: look
            enabled: sheet.notifyBusy === ""
            SettingsControls.SettingRow {
                tone: look
                divider: false
                tappable: true
                checkable: true
                checked: appCard.modelData.popups === true
                title: appCard.modelData.name
                detail: checked ? i18n("Pops up") : i18n("Only in the list, without popping up")
                lead: Kirigami.Icon {
                    width: 28
                    height: 28
                    source: appCard.modelData.icon
                }
                onTapped: sheet.notifyApp(appCard.modelData, !checked)
                SettingsControls.Switch {
                    tone: look
                    active: appCard.modelData.popups === true
                    Accessible.ignored: true
                }
            }
            SettingsControls.SettingRow {
                objectName: "taskbarBadge-" + appCard.modelData.id
                tone: look
                tappable: true
                checkable: true
                checked: appCard.modelData.badges === true
                strong: false
                title: i18n("Show taskbar badge")
                detail: i18n("Show a count on the %1 icon.", appCard.modelData.name)
                onTapped: sheet.notifyBadge(appCard.modelData, !checked)
                SettingsControls.Switch {
                    tone: look
                    active: appCard.modelData.badges === true
                    Accessible.ignored: true
                }
            }
        }
    }
    SettingsControls.Card {
        tone: look
        visible: (sheet.notifyInfo.apps || []).length === 0
        SettingsControls.SettingRow {
            tone: look
            divider: false
            strong: false
            title: i18n("No apps yet")
            detail: i18n("Apps show up here once they've sent a notification.")
        }
    }
    SettingsControls.Pill {
        tone: look
        text: i18n("More notification settings…")
        onClicked: sheet.ask("kde notifications")
    }
}
