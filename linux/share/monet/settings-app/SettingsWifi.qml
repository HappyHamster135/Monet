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
    id: internetPage
    function cancelConfirmation() {
        if (sheet.joining === "") return false
        const name = sheet.joining
        sheet.joining = ""
        sheet.focusControl("wifiNetwork-" + sheet.hex(name))
        return true
    }
    readonly property var wiredDevices: sheet.wiredNetwork ? sheet.wiredNetwork.devices : []
    readonly property bool lanConnected: sheet.wiredNetwork && sheet.wiredNetwork.available
        ? wiredDevices.some(device => device.state === "connected") : sheet.info.lanConnected === true
    readonly property var wiredStates: ({
        connected: i18n("Connected"),
        connecting: i18n("Connecting…"),
        unmanaged: i18n("Unmanaged"),
        unplugged: i18n("Cable unplugged"),
        disconnected: i18n("Not connected")
    })
    spacing: 20
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("wifi")
        art: sheet.art
        text: i18n("Internet")
        detail: internetPage.lanConnected
            ? i18n("Connected to LAN")
            : sheet.info.wifi === true && sheet.info.network ? i18n("Connected to %1", sheet.info.network)
            : sheet.wiredNetwork && sheet.wiredNetwork.available ? i18n("Not connected") : ""
    }
    // On a cable: each adapter, and its addresses while it's connected (monet-quick lan).
    SettingsControls.Caption { objectName: "search-lan"; tone: look; text: i18n("LAN (Ethernet)") }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            visible: internetPage.wiredDevices.length === 0
            title: !sheet.wiredNetwork ? i18n("Checking wired connections…")
                : sheet.wiredNetwork.available ? i18n("No Ethernet adapter detected")
                : i18n("Wired connection details unavailable")
        }
        Repeater {
            model: internetPage.wiredDevices
            ColumnLayout {
                id: wiredDevice
                required property var modelData
                required property int index
                Layout.fillWidth: true
                spacing: 0
                SettingsControls.SettingRow {
                    tone: look
                    divider: wiredDevice.index > 0
                    title: wiredDevice.modelData.profile || wiredDevice.modelData.device
                    detail: internetPage.wiredStates[wiredDevice.modelData.state] || i18n("Unavailable")
                }
                Repeater {
                    model: wiredDevice.modelData.state === "connected" ? [
                        [i18n("Network adapter"), [wiredDevice.modelData.device]],
                        [i18n("IPv4 address"), wiredDevice.modelData.ipv4],
                        [i18n("IPv6 address"), wiredDevice.modelData.ipv6],
                        [i18n("Default gateway"), wiredDevice.modelData.gateways],
                        [i18n("DNS servers"), wiredDevice.modelData.dns]
                    ].filter(row => row[1] && row[1].length) : []
                    SettingsControls.SettingRow {
                        required property var modelData
                        tone: look
                        title: modelData[0]
                        detail: modelData[1].join("\n")
                    }
                }
            }
        }
        SettingsControls.SettingRow {
            objectName: "manageWiredConnections"
            tone: look
            tappable: true
            title: i18n("Manage wired connections…")
            detail: i18n("Edit Ethernet profiles, IP addresses and DNS in system network settings.")
            onTapped: sheet.ask("kde wifi")
        }
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            tappable: typeof sheet.info.wifi === "boolean"
            title: i18n("Wi-Fi")
            detail: typeof sheet.info.wifi === "boolean" ? "" : i18n("This PC has no Wi-Fi")
            onTapped: sheet.flip("wifi", "wifi")
            SettingsControls.Switch {
                tone: look
                visible: typeof sheet.info.wifi === "boolean"
                active: sheet.info.wifi === true
            }
        }
    }
    SettingsControls.Card {
        tone: look
        visible: sheet.info.wifi === true && (sheet.info.network || "") !== ""
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: sheet.info.network || ""
            detail: i18n("Connected")
            lead: SettingsControls.Check {
                tone: look
                active: true
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        visible: sheet.info.wifi === true
        text: (sheet.info.network || "") !== "" ? i18n("Other networks") : i18n("Networks")
    }
    SettingsControls.Card {
        tone: look
        visible: sheet.info.wifi === true
        SettingsControls.SettingRow {
            tone: look
            divider: false
            visible: sheet.nets.filter(n => !n.active).length === 0
            strong: false
            title: sheet.netsLoaded ? i18n("No other networks nearby") : i18n("Looking for networks…")
        }
        Repeater {
            model: sheet.nets.filter(n => !n.active)
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 0
                SettingsControls.SettingRow {
                    tone: look
                    divider: index > 0
                    tappable: true
                    strong: false
                    title: modelData.name
                    objectName: "wifiNetwork-" + sheet.hex(modelData.name)
                    detail: sheet.joining === modelData.name && sheet.joinState === "failed" && !modelData.secure
                        ? i18n("Couldn't join") : ""
                    lead: SettingsControls.Bars {
                        tone: look
                        level: modelData.signal > 66 ? 3 : modelData.signal > 33 ? 2 : 1
                    }
                    onTapped: {
                        sheet.joinState = ""
                        if (modelData.enterprise && !modelData.known) {
                            // A work or school network wants a name as well: KDE's page asks for both.
                            sheet.ask("kde wifi")
                        } else if (modelData.secure && !modelData.known) {
                            sheet.joining = sheet.joining === modelData.name ? "" : modelData.name
                        } else {
                            // Open, or known: straight in (a known one that fails asks for its password).
                            sheet.joining = modelData.name
                            sheet.join(modelData.name, "")
                        }
                    }
                    Row {
                        readonly property bool busy: sheet.joining === modelData.name && sheet.joinState === "joining"
                        spacing: 6
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            visible: parent.busy
                            text: i18n("Joining…")
                            color: look.dim
                            font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                        }
                        // A lock for networks that ask for a password.
                        SettingsControls.Glyph {
                            visible: modelData.secure && !parent.busy
                            width: 15
                            height: 15
                            path: "M7.5 11V8a4.5 4.5 0 0 1 9 0v3M6 11h12v9H6z"
                            color: look.dim
                        }
                        Accessible.role: Accessible.StaticText
                        Accessible.name: modelData.secure ? i18n("Secured") : i18n("Open")
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: 18
                    Layout.rightMargin: 18
                    Layout.bottomMargin: 14
                    visible: sheet.joining === modelData.name && modelData.secure
                    spacing: 8
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 38
                        radius: 12
                        color: look.dark ? Qt.rgba(0, 0, 0, 0.28) : Qt.rgba(1, 1, 1, 0.9)
                        border.width: password.activeFocus ? 2 : 1
                        border.color: password.activeFocus ? look.lily : look.line
                        TextInput {
                            id: password
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            verticalAlignment: TextInput.AlignVCenter
                            echoMode: TextInput.Password
                            color: look.ink
                            font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
                            clip: true
                            Accessible.role: Accessible.EditableText
                            Accessible.name: i18n("Password for %1", modelData.name)
                            onVisibleChanged: if (visible) forceActiveFocus()
                            onAccepted: sheet.join(modelData.name, text)
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                anchors.fill: parent
                                verticalAlignment: Text.AlignVCenter
                                visible: password.text === ""
                                text: sheet.joinState === "failed" ? i18n("That didn't work. Check the password.") : i18n("Password")
                                color: sheet.joinState === "failed" ? "#E0603A" : look.dim
                                font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
                            }
                        }
                    }
                    SettingsControls.Pill {
                        tone: look
                        text: i18n("Cancel")
                        onClicked: sheet.joining = ""
                    }
                    SettingsControls.Pill {
                        tone: look
                        kind: "lily"
                        text: sheet.joinState === "joining" ? i18n("Joining…") : i18n("Join")
                        enabledPill: sheet.joinState !== "joining"
                        onClicked: sheet.join(modelData.name, password.text)
                    }
                }
            }
        }
    }
    // A hotspot: this PC's own Wi-Fi network, so a phone or tablet can use its internet.
    SettingsControls.Card {
        tone: look
        visible: sheet.hotspot.on === true || sheet.hotspot.possible === true
        SettingsControls.SettingRow {
            tone: look
            divider: false
            tappable: sheet.hotspotState !== "starting"
            title: i18n("Hotspot")
            detail: sheet.hotspotState === "starting" ? i18n("Starting…")
                : sheet.hotspotState === "failed" ? i18n("This Wi-Fi can't share. Wired internet shares best.")
                : sheet.hotspot.on === true ? i18n("Join %1 with the password %2", sheet.hotspot.name, sheet.hotspot.password)
                : i18n("Lets a phone or tablet use this PC's internet")
            onTapped: {
                const on = sheet.hotspot.on !== true
                sheet.hotspotState = on ? "starting" : ""
                sheet.ask(on ? "hotspot-on" : "hotspot-off", out => {
                    const state = sheet.json(out, { on: false })
                    sheet.hotspot = state
                    sheet.hotspotState = on && !state.on ? "failed" : ""
                })
            }
            SettingsControls.Switch {
                tone: look
                active: sheet.hotspot.on === true
            }
        }
    }
    SettingsControls.Pill {
        tone: look
        text: i18n("More Wi-Fi settings…")
        onClicked: sheet.ask("kde wifi")
    }
}
