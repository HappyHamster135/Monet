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
    id: bluetoothPage
    spacing: 20
    property string sleepMode: ""
    property bool sleepBusy: true
    property bool sleepError: false

    function sleepSetting(choice) {
        sleepBusy = true
        sheet.ask("bluetooth-sleep " + choice, (out) => {
            if (!bluetoothPage) return
            const result = sheet.json(out, {})
            bluetoothPage.sleepBusy = false
            bluetoothPage.sleepError = !result.ok
            if (["off", "restore", "stay-off"].includes(result.mode))
                bluetoothPage.sleepMode = result.mode
        })
    }
    Component.onCompleted: sleepSetting("status")
    SettingsControls.PageTitle {
        readonly property int connected: sheet.devices.filter(d => d.connected).length
        tone: look
        entry: sheet.entry("bluetooth")
        art: sheet.art
        text: i18n("Bluetooth")
        detail: sheet.info.bluetooth === true
            ? (connected > 0 ? i18np("%1 device connected", "%1 devices connected", connected) : i18n("On"))
            : sheet.info.bluetooth === false ? i18n("Off") : ""
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            tappable: typeof sheet.info.bluetooth === "boolean"
            title: i18n("Bluetooth")
            detail: typeof sheet.info.bluetooth === "boolean" ? "" : i18n("This PC has no Bluetooth")
            onTapped: sheet.flip("bluetooth", "bluetooth")
            SettingsControls.Switch {
                tone: look
                visible: typeof sheet.info.bluetooth === "boolean"
                active: sheet.info.bluetooth === true
            }
        }
    }
    SettingsControls.Card {
        tone: look
        visible: sheet.info.bluetooth === true
        SettingsControls.SettingRow {
            tone: look
            divider: false
            visible: sheet.devices.length === 0
            strong: false
            title: i18n("No devices yet")
            detail: i18n("Pair headphones, a controller or a mouse to see them here.")
        }
        Repeater {
            model: sheet.devices
            SettingsControls.SettingRow {
                tone: look
                divider: index > 0
                title: modelData.name
                detail: modelData.connected ? i18n("Connected") : i18n("Not connected")
                // What it is, in a lily chip while it's connected (like Quick Settings).
                lead: Rectangle {
                    width: 34
                    height: 34
                    radius: 17
                    color: modelData.connected ? look.lily : look.wash2
                    Behavior on color { ColorAnimation { duration: Math.round(180 * look.speed) } }
                    SettingsControls.Glyph {
                        anchors.centerIn: parent
                        width: 18
                        height: 18
                        path: sheet.deviceGlyph(modelData.icon || "")
                        color: modelData.connected ? "#FFFFFF" : look.ink
                    }
                }
                SettingsControls.Pill {
                    tone: look
                    text: sheet.busyDevice === modelData.address ? (modelData.connected ? i18n("Disconnecting…") : i18n("Connecting…"))
                        : modelData.connected ? i18n("Disconnect") : i18n("Connect")
                    enabledPill: sheet.busyDevice === ""
                    onClicked: sheet.connectDevice(modelData)
                }
            }
        }
    }
    SettingsControls.Pill {
        tone: look
        visible: sheet.info.bluetooth === true
        text: i18n("Pair a new device…")
        onClicked: sheet.ask("kde bluetooth")
    }
    SettingsControls.Card {
        tone: look
        visible: typeof sheet.info.bluetooth === "boolean" || ["restore", "stay-off"].includes(bluetoothPage.sleepMode)
        SettingsControls.SettingRow {
            tone: look
            id: sleepRow
            objectName: "bluetoothSleepRow"
            checkable: true
            checked: ["restore", "stay-off"].includes(bluetoothPage.sleepMode)
            title: i18n("Turn Bluetooth off during sleep")
            detail: bluetoothPage.sleepError ? i18n("Could not apply the Bluetooth sleep setting. Try again.")
                : i18n("Wake this PC with its power button or built-in keyboard.")
            divider: false
            tappable: !bluetoothPage.sleepBusy
            onTapped: bluetoothPage.sleepSetting(["off", ""].includes(bluetoothPage.sleepMode) ? "restore" : "off")
            SettingsControls.Switch {
                tone: look
                active: sleepRow.checked
            }
        }
        SettingsControls.SettingRow {
            tone: look
            id: wakeRow
            objectName: "bluetoothWakeRow"
            checkable: true
            checked: bluetoothPage.sleepMode === "restore"
            visible: ["restore", "stay-off"].includes(bluetoothPage.sleepMode)
            title: i18n("Restore Bluetooth on wake")
            detail: i18n("Turn previously active adapters back on and reconnect paired mice and keyboards that were connected before sleep.")
            tappable: !bluetoothPage.sleepBusy
            onTapped: bluetoothPage.sleepSetting(bluetoothPage.sleepMode === "restore" ? "stay-off" : "restore")
            SettingsControls.Switch { tone: look; active: wakeRow.checked }
        }
    }
}
