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
    id: usersColumn
    function cancelConfirmation() {
        if (sheet.renaming) {
            sheet.renaming = false
            sheet.focusControl("changeUserName")
        } else if (passwordOpen) {
            if (sheet.passwordState !== "changing") {
                sheet.passwordState = ""
                sheet.focusControl("changeUserPassword")
            }
        } else return false
        return true
    }
    readonly property var you: sheet.people.find(p => p.you) || null
    readonly property var others: sheet.people.filter(p => !p.you && !p.guest)
    readonly property bool passwordOpen: ["open", "changing", "failed"].indexOf(sheet.passwordState) !== -1
    spacing: 20
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("users")
        art: sheet.art
        text: i18n("Accounts")
        detail: i18n("You, and the people who share this PC.")
    }
    SettingsControls.Card {
        tone: look
        visible: usersColumn.you !== null
        RowLayout {
            Layout.fillWidth: true
            Layout.margins: 20
            spacing: 18
            // Your initial on a dab of lily, as in the menu.
            SettingsControls.Face {
                Layout.preferredWidth: 64
                Layout.preferredHeight: 64
                name: usersColumn.you ? usersColumn.you.name : ""
                picture: usersColumn.you ? usersColumn.you.picture : ""
            }
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 2
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: usersColumn.you ? usersColumn.you.name : ""
                    color: look.ink
                    font.family: "Fraunces 72pt SuperSoft"
                    font.weight: Font.Light
                    font.pixelSize: 26
                    elide: Text.ElideRight
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: !usersColumn.you ? ""
                        : usersColumn.you.admin ? i18n("%1 · Administrator", usersColumn.you.login)
                        : i18n("%1 · Standard account", usersColumn.you.login)
                    color: look.dim
                    font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                    elide: Text.ElideRight
                }
            }
            SettingsControls.Pill {
                tone: look
                visible: !sheet.renaming
                objectName: "changeUserName"
                text: i18n("Change name")
                onClicked: {
                    sheet.nameProblem = ""
                    sheet.renaming = true
                }
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 20
            Layout.rightMargin: 20
            Layout.bottomMargin: 18
            visible: sheet.renaming
            spacing: 8
            onVisibleChanged: {
                if (visible) {
                    nameField.text = usersColumn.you ? usersColumn.you.name : ""
                    nameField.focusInput()
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                SettingsControls.Field {
                    id: nameField
                    tone: look
                    hint: i18n("Your name")
                    onAccepted: sheet.rename(text)
                }
                SettingsControls.Pill {
                    tone: look
                    text: i18n("Cancel")
                    onClicked: sheet.renaming = false
                }
                SettingsControls.Pill {
                    tone: look
                    kind: "lily"
                    text: i18n("Save")
                    onClicked: sheet.rename(nameField.text)
                }
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                visible: sheet.nameProblem !== ""
                text: sheet.nameProblem
                color: "#E0603A"
                font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                wrapMode: Text.Wrap
            }
        }
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Password")
            detail: sheet.passwordState === "done" ? i18n("Changed. Use the new one from now on.")
                : i18n("For signing in, unlocking and allowing changes")
            SettingsControls.Pill {
                tone: look
                visible: !usersColumn.passwordOpen
                objectName: "changeUserPassword"
                text: i18n("Change…")
                onClicked: sheet.passwordState = "open"
            }
        }
        ColumnLayout {
            Layout.fillWidth: true
            Layout.leftMargin: 18
            Layout.rightMargin: 18
            Layout.bottomMargin: 18
            visible: usersColumn.passwordOpen
            spacing: 8
            onVisibleChanged: {
                if (visible) {
                    oldPassword.text = ""
                    newPassword.text = ""
                    againPassword.text = ""
                    oldPassword.focusInput()
                }
            }
            SettingsControls.Field {
                id: oldPassword
                tone: look
                secret: true
                hint: i18n("Current password")
                onAccepted: newPassword.focusInput()
            }
            SettingsControls.Field {
                id: newPassword
                tone: look
                secret: true
                hint: i18n("New password")
                onAccepted: againPassword.focusInput()
            }
            SettingsControls.Field {
                id: againPassword
                tone: look
                secret: true
                hint: i18n("New password, again")
                onAccepted: sheet.changePassword(oldPassword.text, newPassword.text, againPassword.text)
            }
            RowLayout {
                Layout.fillWidth: true
                Layout.topMargin: 4
                spacing: 8
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: sheet.passwordState === "failed" ? sheet.passwordMessage : ""
                    color: "#E0603A"
                    font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                    wrapMode: Text.Wrap
                }
                SettingsControls.Pill {
                    tone: look
                    text: i18n("Cancel")
                    enabledPill: sheet.passwordState !== "changing"
                    onClicked: sheet.passwordState = ""
                }
                SettingsControls.Pill {
                    tone: look
                    kind: "lily"
                    text: sheet.passwordState === "changing" ? i18n("Changing…") : i18n("Change password")
                    enabledPill: sheet.passwordState !== "changing"
                    onClicked: sheet.changePassword(oldPassword.text, newPassword.text, againPassword.text)
                }
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("Other people")
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            visible: usersColumn.others.length === 0
            strong: false
            title: i18n("Only you, so far")
            detail: i18n("Add someone in More account settings.")
        }
        Repeater {
            model: usersColumn.others
            SettingsControls.SettingRow {
                tone: look
                divider: index > 0
                title: modelData.name
                detail: modelData.admin ? i18n("Administrator") : i18n("Standard account")
                lead: SettingsControls.Face {
                    width: 34
                    height: 34
                    name: modelData.name
                    picture: modelData.picture
                    glaze: sheet.glaze(modelData.login)
                }
            }
        }
    }
    // A guest: someone signs in without a password and leaves nothing behind.
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            tappable: !sheet.guestBusy
            title: i18n("Guest")
            detail: sheet.guestBusy ? i18n("Asking for an administrator's password…")
                : i18n("Someone can sign in as Guest, with no password, without seeing your files, games or Windows. Everything they do is gone when they sign out.")
            onTapped: {
                const on = sheet.guestInfo.on !== true
                sheet.guestBusy = true
                sheet.ask(on ? "guest-on" : "guest-off", out => {
                    sheet.guestBusy = false
                    sheet.guestInfo = sheet.json(out, sheet.guestInfo)
                })
            }
            SettingsControls.Switch {
                tone: look
                active: sheet.guestInfo.on === true
            }
        }
    }
    SettingsControls.Pill {
        tone: look
        text: i18n("More account settings…")
        onClicked: sheet.ask("kde users")
    }
}
