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
    id: privacyColumn
    function cancelConfirmation() {
        if (!askingForget) return false
        askingForget = false
        sheet.focusControl("forgetRecentApps")
        return true
    }
    // Forgetting recent files asks once more.
    property bool askingForget: false
    // Said once it's done, until the page is left.
    property bool forgot: false
    spacing: 20
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("privacy")
        art: sheet.art
        text: i18n("Privacy")
        detail: i18n("Who can get in, and what Monet remembers.")
    }
    SettingsControls.Card {
        tone: look
        visible: !!sheet.privacyInfo.fingerprint
        // With a fingerprint reader: a finger unlocks and says yes to administrator
        // questions. KDE's Accounts page sets one up (Configure Fingerprint).
        SettingsControls.SettingRow {
            tone: look
            visible: !!sheet.privacyInfo.fingerprint
            divider: false
            title: i18n("Fingerprint")
            detail: sheet.privacyInfo.fingerprint && sheet.privacyInfo.fingerprint.enrolled
                ? i18n("Your finger unlocks the screen and says yes when Monet asks for your password")
                : i18n("Set up a finger to unlock the screen and say yes when Monet asks for your password")
            SettingsControls.Pill {
                tone: look
                kind: sheet.privacyInfo.fingerprint && sheet.privacyInfo.fingerprint.enrolled ? "plain" : "lily"
                text: sheet.privacyInfo.fingerprint && sheet.privacyInfo.fingerprint.enrolled ? i18n("Change…") : i18n("Set up…")
                onClicked: sheet.ask("kde users")
            }
        }
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Passwords")
            detail: i18n("Saved logins, app access and vault unlocking")
            SettingsControls.Pill {
                tone: look
                text: i18n("Open Passwords")
                onClicked: sheet.open("passwords")
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("What Monet remembers")
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            tappable: true
            title: i18n("Remember recent files")
            detail: i18n("Files and the menu show what you opened lately")
            onTapped: sheet.rememberFiles(sheet.privacyInfo.remember === false)
            SettingsControls.Switch {
                tone: look
                active: sheet.privacyInfo.remember !== false
            }
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Forget recent files")
            detail: privacyColumn.askingForget ? i18n("The list of what you opened is cleared. Your files stay. Sure?")
                : privacyColumn.forgot ? i18n("Cleared. Your files are still there.")
                : i18n("Clears the list, not the files")
            Row {
                spacing: 8
                SettingsControls.Pill {
                    tone: look
                    visible: privacyColumn.askingForget
                    text: i18n("Keep it")
                    onClicked: privacyColumn.askingForget = false
                }
                SettingsControls.Pill {
                    tone: look
                    text: privacyColumn.askingForget ? i18n("Forget") : i18n("Forget…")
                    objectName: "forgetRecentApps"
                    onClicked: {
                        if (privacyColumn.askingForget) {
                            privacyColumn.askingForget = false
                            sheet.ask("forget-recent", () => privacyColumn.forgot = true)
                        } else {
                            privacyColumn.askingForget = true
                        }
                    }
                }
            }
        }
    }
    Row {
        spacing: 8
        SettingsControls.Pill {
            tone: look
            text: i18n("More lock screen settings…")
            onClicked: sheet.ask("kde screenlocker")
        }
        SettingsControls.Pill {
            tone: look
            text: i18n("More recent files settings…")
            onClicked: sheet.ask("kde recentfiles")
        }
    }
}
