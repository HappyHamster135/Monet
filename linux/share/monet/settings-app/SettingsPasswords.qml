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
        entry: sheet.entry("passwords")
        art: sheet.art
        text: i18n("Passwords")
        detail: i18n("Saved logins, app access and vault unlocking")
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            objectName: "appLoginOffersRow"
            tone: look
            divider: false
            title: i18n("Save and fill app logins")
            detail: i18n("Ask before saving or filling logins in supported apps. Choose an account from Monet’s notification to fill it. Some apps keep their fields private and need you to enter the password once when saving.")
            tappable: !sheet.walletBusy && sheet.walletInfo.appOffersAvailable === true
            onTapped: sheet.walletAction("app-offers", sheet.walletInfo.appOffers ? "off" : "on")
            SettingsControls.Switch {
                tone: look
                active: sheet.walletInfo.appOffers === true
            }
        }
        SettingsControls.SettingRow {
            tone: look
            title: sheet.walletInfo.appOffers ? (sheet.walletInfo.appOffersRunning ? i18n("Ready for supported apps") : i18n("App login offers need attention")) : i18n("App login offers are off")
            detail: sheet.walletInfo.appOffers && !sheet.walletInfo.appOffersRunning
                ? i18n("Turn the switch off and on to try again.")
                : i18n("Browser passwords stay in your browser. Apps with custom sign-in screens may need a login added manually in Monet Passwords.")
        }
        SettingsControls.SettingRow {
            tone: look
            visible: sheet.walletInfo.appOffersIgnored > 0
            title: i18n("Skipped apps")
            detail: i18n("Allow prompts again for apps where you chose Never for this app.")
            SettingsControls.Pill {
                tone: look
                text: i18n("Reset skipped apps")
                enabled: !sheet.walletBusy
                onClicked: sheet.walletAction("app-offers", "reset")
            }
        }
        SettingsControls.SettingRow {
            objectName: "appLoginSupportRow"
            tone: look
            title: i18n("App login support")
            detail: i18n("Help sandboxed apps expose their sign-in fields, or restore their earlier support settings. Reopen the app after a change.")
            SettingsControls.Pill {
                objectName: "appLoginSupportButton"
                tone: look
                text: i18n("Review app support")
                enabled: !sheet.walletBusy
                onClicked: sheet.walletAction("app-support")
            }
        }
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Saved logins")
            detail: i18n("Open Monet Passwords to search, show, copy and manage saved logins and app credentials.")
            SettingsControls.Pill {
                objectName: "walletManageButton"
                tone: look
                text: i18n("Open Monet Passwords")
                enabled: !sheet.walletBusy && sheet.walletInfo.manager === true
                onClicked: sheet.walletAction("manage")
            }
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("App access and prompts")
            detail: i18n("Review browser pairings and desktop apps that can access your vault. Revoke a browser connection without deleting your logins.")
            SettingsControls.Pill {
                objectName: "walletAccessButton"
                tone: look
                text: i18n("Manage access")
                enabled: !sheet.walletBusy && sheet.walletInfo.preferences === true
                onClicked: sheet.walletAction("access")
            }
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Optional Zen connection")
            detail: i18n("Connect Zen to Monet Passwords. Monet asks before saving or updating a login; the connector needs no separate password.")
            SettingsControls.Pill {
                objectName: "walletZenButton"
                tone: look
                text: i18n("Set up Zen autofill")
                enabled: !sheet.walletBusy && sheet.walletInfo.manager === true
                onClicked: sheet.walletAction("zen")
            }
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Website passwords")
            detail: i18n("Passwords previously saved only in your browser remain there. Open the browser’s own list to manage those entries.")
            SettingsControls.Pill {
                objectName: "walletBrowserButton"
                tone: look
                text: i18n("Browser passwords")
                enabled: !sheet.walletBusy && sheet.walletInfo.browser === true
                onClicked: sheet.walletAction("browser")
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("Unlocking")
    }
    SettingsControls.Card {
        objectName: "search-passwords"
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Encrypted password vault")
            detail: sheet.walletInfo.enabled === false ? i18n("The desktop password vault is disabled.")
                : sheet.walletInfo.unlocked === true ? i18n("Unlocked. Apps can use your saved passwords.")
                : sheet.walletInfo.unlocked === false ? i18n("Locked. Unlock it when an app first needs a saved password.")
                : i18n("Refresh to check whether the vault is unlocked.")
            SettingsControls.Pill {
                tone: look
                text: i18n("Refresh")
                enabled: !sheet.walletBusy
                onClicked: sheet.walletAction("status")
            }
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Keep passwords unlocked")
            detail: i18n("After the first unlock, apps can fill saved passwords without asking again. New apps may still ask for access.")
            SettingsControls.Segments {
                objectName: "walletPolicy"
                tone: look
                enabled: !sheet.walletBusy && sheet.walletInfo.enabled === true
                options: [["session", i18n("Until sign-out")], ["10", i18n("10 min idle")], ["30", i18n("30 min idle")]]
                current: sheet.walletInfo.policy || ""
                onPicked: value => sheet.walletAction("policy", value)
            }
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Your login and vault passwords")
            detail: sheet.walletInfo.automaticLogin === true
                ? i18n("Automatic sign-in needs one vault unlock each session. You can keep a separate vault password. For automatic unlocking at password sign-in, give kdewallet the same password as your login.")
                : i18n("Separate passwords are supported: unlock the vault once when first needed. To unlock automatically at password sign-in, give kdewallet the same password as your login. Fingerprint sign-in may still need a vault unlock.")
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Lock saved passwords now")
            detail: i18n("Apps will need to unlock the vault before using saved passwords again.")
            SettingsControls.Pill {
                tone: look
                text: i18n("Lock")
                enabled: !sheet.walletBusy && sheet.walletInfo.unlocked === true
                onClicked: sheet.walletAction("lock")
            }
        }
    }
    Text {
        Layout.fillWidth: true
        visible: sheet.walletChanged || sheet.walletProblem !== ""
        text: sheet.walletProblem || i18n("Saved. The unlock policy takes full effect at your next sign-in. Lock now works immediately.")
        color: sheet.walletProblem ? look.sun : look.dim
        wrapMode: Text.WordWrap
        font.pixelSize: Math.max(14, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 2)
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Sign-in options")
            detail: i18n("Until sign-out does not carry over a restart. Password sign-in can unlock kdewallet automatically when both passwords match. Separate passwords still work with one vault unlock each session.")
            SettingsControls.Pill {
                tone: look
                text: i18n("Accounts")
                onClicked: sheet.open("users")
            }
        }
    }
}
