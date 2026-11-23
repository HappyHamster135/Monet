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
    id: phoneColumn
    spacing: 20
    readonly property var paired: sheet.phoneList.filter(p => p.paired)
    readonly property var near: sheet.phoneList.filter(p => !p.paired && p.near)
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("phone")
        art: sheet.art
        text: i18n("Phone")
        detail: i18n("Texts, notifications and files between your phone and this PC.")
    }
    SettingsControls.Card {
        tone: look
        visible: sheet.phoneFailed
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Couldn't check phones")
            detail: i18n("The connection check didn't finish. Try again, or open More phone settings.")
            Accessible.role: Accessible.AlertMessage
            SettingsControls.Pill {
                tone: look
                text: sheet.phoneChecking ? i18n("Checking…") : i18n("Try again")
                enabledPill: !sheet.phoneChecking
                onClicked: sheet.loadPhones()
            }
        }
    }
    // Phones come and go as they join the Wi-Fi, and a pairing is answered on the phone.
    Timer {
        interval: 4000
        repeat: true
        triggeredOnStart: true
        running: sheet.page === "phone" && sheet.pollingActive && sheet.phoneApp
        onTriggered: sheet.loadPhones()
    }
    // A pairing declined (or never seen) on the phone: Pair again after a while.
    Timer {
        id: pairWait
        interval: 30000
        onTriggered: sheet.phoneAsked = ""
    }
    SettingsControls.Card {
        tone: look
        visible: phoneColumn.paired.length > 0
        Repeater {
            model: phoneColumn.paired
            SettingsControls.SettingRow {
                tone: look
                divider: index > 0
                title: modelData.name
                detail: !modelData.near ? i18n("Not nearby")
                    : typeof modelData.battery !== "number" ? i18n("Connected")
                    : modelData.charging ? i18n("Connected · charging, %1%", modelData.battery)
                    : i18n("Connected · %1% battery", modelData.battery)
                lead: Rectangle {
                    width: 34
                    height: 34
                    radius: 17
                    color: modelData.near ? look.lily : look.wash2
                    Behavior on color { ColorAnimation { duration: Math.round(180 * look.speed) } }
                    SettingsControls.Glyph {
                        anchors.centerIn: parent
                        width: 18
                        height: 18
                        path: sheet.deviceGlyph("phone")
                        color: modelData.near ? "#FFFFFF" : look.ink
                    }
                }
                Row {
                    spacing: 8
                    SettingsControls.Pill {
                        tone: look
                        visible: modelData.near
                        text: i18n("Ring")
                        onClicked: sheet.ask("phone-ring " + modelData.id)
                    }
                    SettingsControls.Pill {
                        tone: look
                        visible: modelData.near
                        kind: "lily"
                        text: i18n("Send a file…")
                        enabledPill: !sheet.phoneSending
                        onClicked: sheet.sendPhoneFile(modelData.id)
                    }
                    SettingsControls.Pill {
                        tone: look
                        visible: modelData.near
                        text: i18n("Files")
                        onClicked: sheet.ask("phone-files " + modelData.id)
                    }
                    SettingsControls.Pill {
                        tone: look
                        text: i18n("Forget")
                        onClicked: sheet.ask("phone-unpair " + modelData.id, () => sheet.loadPhones())
                    }
                }
            }
        }
    }
    SettingsControls.Card {
        tone: look
        visible: sheet.phoneSending || sheet.phoneFileState !== ""
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: sheet.phoneSending ? i18n("Choose a file to share")
                : sheet.phoneFileState === "canceled" ? i18n("No file sent")
                : sheet.phoneFileState === "dispatched" ? i18n("Sharing requested") : i18n("The file couldn't be shared")
            detail: sheet.phoneFileState === "dispatched" ? i18n("Check your phone for the file. This PC can't confirm its arrival.")
                : sheet.phoneFileState === "failed" ? i18n("Check the connection and try again.") : ""
            Accessible.role: sheet.phoneFileState === "failed" ? Accessible.AlertMessage : Accessible.StaticText
        }
    }
    SettingsControls.Pill {
        tone: look
        visible: phoneColumn.paired.some(p => p.near)
        text: i18n("Texts")
        onClicked: sheet.ask("phone-texts")
    }
    // Phones on the same Wi-Fi with KDE Connect open, to pair (the phone asks to accept).
    SettingsControls.Card {
        tone: look
        visible: phoneColumn.near.length > 0
        Repeater {
            model: phoneColumn.near
            SettingsControls.SettingRow {
                tone: look
                divider: index > 0
                title: modelData.name
                detail: sheet.phoneAsked === modelData.id ? i18n("Accept on your phone") : i18n("Nearby, not paired")
                SettingsControls.Pill {
                    tone: look
                    kind: "lily"
                    text: sheet.phoneAsked === modelData.id ? i18n("Waiting…") : i18n("Pair")
                    enabledPill: sheet.phoneAsked !== modelData.id
                    onClicked: {
                        sheet.phoneAsked = modelData.id
                        pairWait.restart()
                        sheet.ask("phone-pair " + modelData.id)
                    }
                }
            }
        }
    }
    // No phone yet: the app, a scan away.
    SettingsControls.Card {
        tone: look
        visible: phoneColumn.paired.length === 0 && sheet.phoneApp && !sheet.phoneFailed
        Item {
            Layout.fillWidth: true
            implicitHeight: Math.max(qr.height, getApp.implicitHeight) + 36
            Image {
                id: qr
                anchors.left: parent.left
                anchors.leftMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                width: 132
                height: 132
                source: sheet.art + "phone-qr.png"
                smooth: false
            }
            ColumnLayout {
                id: getApp
                anchors.left: qr.right
                anchors.leftMargin: 18
                anchors.right: parent.right
                anchors.rightMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                spacing: 6
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: i18n("Get the app on your phone")
                    color: look.ink
                    font.pixelSize: Math.max(17, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 1)
                    font.weight: Font.DemiBold
                    wrapMode: Text.WordWrap
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: i18n("Point your phone's camera at this and install the app it shows. Open it on the same Wi-Fi as this PC, and your phone shows up here to pair.")
                    color: look.dim
                    font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                    wrapMode: Text.WordWrap
                }
            }
        }
    }
    SettingsControls.Card {
        tone: look
        visible: !sheet.phoneApp
        SettingsControls.SettingRow {
            tone: look
            divider: false
            strong: false
            title: i18n("Phones can't connect to this PC yet")
            detail: i18n("The part of Monet that talks to phones is missing here.")
        }
    }
    SettingsControls.Pill {
        tone: look
        visible: sheet.phoneApp || sheet.phoneFailed
        text: i18n("More phone settings…")
        onClicked: sheet.ask("kde phone")
    }
}
