/* The everyday choices stay in Quick Settings; advanced configuration remains in Settings. */
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.components as PC
import org.kde.kirigami as Kirigami

Item {
    id: pane
    objectName: "quickOptionsPane"
    required property var bridge
    required property string page
    property bool busy: false
    property string error: ""
    property var networks: []
    property var devices: []
    property var selectedNetwork: null
    property var night: ({enabled: false, strength: 36})
    property var power: ({})
    readonly property var saverLevels: [10, 20, 30, 50, power.batterySaverThreshold || 20]
        .filter((value, index, values) => Number.isInteger(value) && value > (power.batteryCriticalLevel || 5) && values.indexOf(value) === index)
        .sort((a, b) => a - b)
    property int epoch: 0
    property bool initialized: false
    property int draftStrength: 36
    property bool strengthDirty: false
    property string quietChoice: ""
    property double quietChoiceUntil: 0
    readonly property bool enabledRadio: page === "wifi" ? bridge.info.wifi === true
        : page === "bluetooth" ? bridge.info.bluetooth === true : night.enabled === true
    readonly property string heading: page === "wifi" ? i18n("Wi-Fi") : page === "bluetooth" ? i18n("Bluetooth")
        : page === "night" ? i18n("Night Light") : page === "power" ? i18n("Power & Battery") : i18n("Do Not Disturb")
    readonly property string batteryZone: bridge.info.plugged === true ? "ac"
        : typeof bridge.info.battery !== "number" ? "unknown" : bridge.info.battery <= (power.batterySaverThreshold || 20) ? "low" : "battery"
    onBatteryZoneChanged: if (initialized && page === "power") changedExternally()
    implicitHeight: 460
    signal dismissed()

    function hex(text) {
        return Array.from(unescape(encodeURIComponent(text)), c => c.charCodeAt(0).toString(16).padStart(2, "0")).join("")
    }
    function clearPassword() { password.text = ""; showPassword.checked = false }
    function goBack() {
        clearPassword()
        if (selectedNetwork) selectedNetwork = null
        else dismissed()
    }
    function focusFirst() { back.forceActiveFocus() }
    function updateState(result) {
        if (page === "power") {
            const state = result.state || result
            if (typeof state.mode === "string" && Array.isArray(state.modes)) power = state
        }
        if (page === "night" && typeof result.enabled === "boolean" && Number.isInteger(result.strength)) {
            night = result
            if (!strengthDirty && !strength.pressed) draftStrength = result.strength
        }
        if ((page === "wifi" || page === "bluetooth") && (typeof result.enabled === "boolean" || result.enabled === null)) {
            const change = {}; change[page] = result.enabled
            bridge.info = Object.assign({}, bridge.info, change)
            if (page === "wifi" && result.enabled !== true) { clearPassword(); selectedNetwork = null }
        }
        if (Array.isArray(result.networks)) networks = result.networks.filter(n => n && typeof n.name === "string"
            && typeof n.secure === "boolean" && typeof n.active === "boolean")
        if (Array.isArray(result.devices)) devices = result.devices.filter(d => d && typeof d.name === "string"
            && /^[0-9a-fA-F:]{17}$/.test(d.address || "") && typeof d.connected === "boolean")
    }
    function request(command, completed) {
        if (busy) return
        busy = true; error = ""
        const generation = epoch
        bridge.askOptions(command, (out, code) => {
            if (generation !== epoch) return
            busy = false
            let result = {}
            try { const parsed = JSON.parse(out); if (parsed && !Array.isArray(parsed) && typeof parsed === "object") result = parsed } catch(e) {}
            updateState(result)
            if (code !== 0 || (result.ok !== true && !(page === "power" && command === "power" && Array.isArray(result.modes)))) {
                error = i18n("That didn't work. Check the device or connection and try again.")
                if (command.startsWith("quick-options wifi-join ")) error = i18n("Couldn't connect. Check the password and try again.")
            }
            if (completed) completed(result, result.ok === true && code === 0)
        })
    }
    function reload(scan = false) {
        if (busy) return
        if (page === "wifi") request("quick-options " + (scan ? "wifi-scan" : "wifi-list"))
        else if (page === "bluetooth") request("quick-options bluetooth-list")
        else if (page === "night") request("quick-options night")
        else if (page === "power") request("power")
        else bridge.refresh()
    }
    function toggleRadio() {
        if (busy) return
        clearPassword(); selectedNetwork = null
        request("quick-options " + (page === "night" ? "night" : page) + (enabledRadio ? " off" : " on"), (result, good) => {
            bridge.refresh()
            if (good && page !== "night") reload()
        })
    }
    function selectNetwork(network) {
        if (busy) return
        clearPassword(); selectedNetwork = null
        if (network.active) request("quick-options wifi disconnect", (result, good) => { if (good) reload(); bridge.refresh() })
        else if (network.enterprise && !network.known) { selectedNetwork = network }
        else if (network.secure && !network.known) { selectedNetwork = network; Qt.callLater(() => password.forceActiveFocus()) }
        else joinNetwork(network, "")
    }
    function joinNetwork(network, secret) {
        if (!network || busy) return
        const command = "quick-options wifi-join " + hex(network.name) + (secret ? " " + hex(secret) : "")
        clearPassword()
        request(command, (result, good) => {
            bridge.refresh()
            if (good) { selectedNetwork = null; reload() }
            else if (network.secure && enabledRadio) {
                selectedNetwork = network
                if (!network.enterprise) Qt.callLater(() => password.forceActiveFocus())
            }
        })
    }
    function setQuiet(mode) {
        request("quiet " + mode, (result, good) => {
            if (result.state && typeof result.state.quiet === "boolean") {
                bridge.info = Object.assign({}, bridge.info, result.state)
                if (good) { quietChoice = mode; quietChoiceUntil = result.state.quietUntil || 0 }
            }
            bridge.refresh()
        })
    }
    function changedExternally() { refreshSoon.restart() }
    Timer { id: refreshSoon; interval: 250; onTriggered: pane.busy ? restart() : pane.reload() }
    Timer {
        id: warmth
        interval: 200
        onTriggered: {
            if (!pane.busy) {
                pane.strengthDirty = false
                pane.request("quick-options night-strength " + pane.draftStrength)
            }
            else restart()
        }
    }
    Component.onCompleted: { initialized = true; reload() }
    Component.onDestruction: clearPassword()
    onPageChanged: if (initialized) {
        ++epoch; warmth.stop(); refreshSoon.stop(); strengthDirty = false
        busy = false; error = ""; networks = []; devices = []; selectedNetwork = null; clearPassword(); reload()
    }
    Keys.onEscapePressed: event => { goBack(); event.accepted = true }

    ColumnLayout {
        anchors.fill: parent
        spacing: 10
        RowLayout {
            Layout.fillWidth: true
            PC.Button { id: back; objectName: "quickOptionsBack"; icon.name: "go-previous"; text: i18n("Back"); onClicked: pane.goBack() }
            PC.Label { Layout.fillWidth: true; text: pane.heading; font.weight: Font.DemiBold; elide: Text.ElideRight }
            PC.Button {
                objectName: "quickOptionsRefresh"
                icon.name: "view-refresh"; text: i18n("Refresh"); display: QQC2.AbstractButton.IconOnly
                Accessible.name: text; enabled: !pane.busy; onClicked: pane.reload(true)
            }
        }
        PC.Label { Layout.fillWidth: true; visible: pane.error !== ""; text: pane.error; wrapMode: Text.WordWrap; color: Kirigami.Theme.negativeTextColor }
        PC.BusyIndicator { Layout.alignment: Qt.AlignHCenter; visible: pane.busy; running: visible; Layout.preferredHeight: 24; Layout.preferredWidth: 24 }
        QQC2.ScrollView {
            id: scroll
            Layout.fillWidth: true; Layout.fillHeight: true
            contentWidth: availableWidth
            QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff
            ColumnLayout {
                width: scroll.availableWidth
                spacing: 12
                PC.Switch {
                    objectName: "quickOptionsRadio"
                    Layout.fillWidth: true; visible: ["wifi", "bluetooth", "night"].indexOf(pane.page) !== -1
                    text: pane.heading; checked: pane.enabledRadio
                    enabled: !pane.busy && (pane.page === "night" || typeof pane.bridge.info[pane.page] === "boolean")
                    onClicked: pane.toggleRadio()
                }
                PC.Label { Layout.fillWidth: true; visible: pane.page === "wifi" && pane.bridge.info.lanConnected === true; text: i18n("Connected by Ethernet"); wrapMode: Text.WordWrap }
                PC.Label {
                    Layout.fillWidth: true
                    visible: (pane.page === "wifi" || pane.page === "bluetooth") && !pane.enabledRadio
                    text: typeof pane.bridge.info[pane.page] === "boolean" ? i18n("Turn it on to see available connections.") : i18n("This PC doesn't have this wireless adapter.")
                    wrapMode: Text.WordWrap
                }
                ColumnLayout {
                    Layout.fillWidth: true; visible: pane.page === "wifi" && pane.enabledRadio && !pane.selectedNetwork
                    PC.Label { visible: !pane.busy && pane.networks.length === 0; text: i18n("No networks found. Try Refresh."); wrapMode: Text.WordWrap; Layout.fillWidth: true }
                    Repeater {
                        model: pane.networks
                        RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 2
                                PC.Label { Layout.fillWidth: true; text: modelData.name; textFormat: Text.PlainText; elide: Text.ElideRight }
                                PC.Label { Layout.fillWidth: true; opacity: .7; text: modelData.active ? i18n("Connected") : modelData.secure ? i18n("Secured") : i18n("Open network") }
                            }
                            PC.Button { objectName: "quickNetwork-" + modelData.name; text: modelData.active ? i18n("Disconnect") : i18n("Connect"); enabled: !pane.busy; onClicked: pane.selectNetwork(modelData) }
                        }
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true; visible: pane.page === "wifi" && pane.selectedNetwork !== null
                    PC.Label { Layout.fillWidth: true; text: pane.selectedNetwork?.name ?? ""; textFormat: Text.PlainText; wrapMode: Text.WordWrap; font.weight: Font.DemiBold }
                    PC.Label { Layout.fillWidth: true; visible: pane.selectedNetwork?.enterprise ?? false; text: i18n("This network needs an account or certificate. Open its advanced Wi-Fi settings to finish setup."); wrapMode: Text.WordWrap }
                    PC.TextField {
                        id: password; objectName: "quickWifiPassword"; Layout.fillWidth: true
                        visible: !(pane.selectedNetwork?.enterprise ?? false)
                        placeholderText: i18n("Network password"); Accessible.name: placeholderText
                        echoMode: showPassword.checked ? TextInput.Normal : TextInput.Password
                        enabled: !pane.busy
                        onAccepted: if (text && !pane.busy) pane.joinNetwork(pane.selectedNetwork, text)
                    }
                    PC.CheckBox { id: showPassword; text: i18n("Show password"); visible: password.visible; enabled: !pane.busy }
                    PC.Button { objectName: "quickWifiJoin"; text: i18n("Connect"); visible: password.visible; enabled: !pane.busy && password.text.length > 0; onClicked: pane.joinNetwork(pane.selectedNetwork, password.text) }
                }
                ColumnLayout {
                    Layout.fillWidth: true; visible: pane.page === "bluetooth" && pane.enabledRadio
                    PC.Label { Layout.fillWidth: true; visible: !pane.busy && pane.devices.length === 0; text: i18n("No paired devices yet."); wrapMode: Text.WordWrap }
                    Repeater {
                        model: pane.devices
                        RowLayout {
                            required property var modelData
                            Layout.fillWidth: true
                            ColumnLayout {
                                Layout.fillWidth: true; spacing: 2
                                PC.Label { Layout.fillWidth: true; text: modelData.name; textFormat: Text.PlainText; elide: Text.ElideRight }
                                PC.Label { Layout.fillWidth: true; opacity: .7; text: modelData.connected ? i18n("Connected") : i18n("Not connected") }
                            }
                            PC.Button { objectName: "quickBluetooth-" + modelData.address; text: modelData.connected ? i18n("Disconnect") : i18n("Connect"); enabled: !pane.busy
                                onClicked: pane.request("quick-options bluetooth-device " + (modelData.connected ? "disconnect " : "connect ") + modelData.address, () => pane.bridge.refresh()) }
                        }
                    }
                    PC.Button { objectName: "quickBluetoothPair"; text: i18n("Pair a new device…"); icon.name: "list-add"; enabled: !pane.busy; onClicked: pane.request("quick-options bluetooth-pair") }
                }
                ColumnLayout {
                    Layout.fillWidth: true; visible: pane.page === "night"
                    PC.Label { Layout.fillWidth: true; text: i18n("Strength"); font.weight: Font.DemiBold }
                    RowLayout {
                        Layout.fillWidth: true
                        PC.Slider { id: strength; objectName: "quickNightStrength"; Layout.fillWidth: true; from: 0; to: 100; stepSize: 1; value: pane.draftStrength
                            Accessible.name: i18n("Night Light strength"); onMoved: { pane.draftStrength = Math.round(value); pane.strengthDirty = true; warmth.restart() } }
                        PC.Label { text: i18n("%1%", Math.round(strength.value)) }
                    }
                    PC.Label { Layout.fillWidth: true; text: i18n("Higher strength makes the screen warmer. Your Night Light schedule still applies."); wrapMode: Text.WordWrap; opacity: .7 }
                }
                ColumnLayout {
                    Layout.fillWidth: true; visible: pane.page === "power"
                    PC.Label { Layout.fillWidth: true; text: i18n("Power mode"); font.weight: Font.DemiBold }
                    QQC2.ButtonGroup { id: powerButtons }
                    Repeater {
                        model: [{mode: "automatic", label: i18n("Automatic")}, {mode: "power-saver", label: i18n("Power saver")},
                                {mode: "balanced", label: i18n("Balanced")}, {mode: "performance", label: i18n("Performance")}]
                            .filter(choice => (pane.power.modes || []).indexOf(choice.mode) !== -1)
                        PC.RadioButton {
                            required property var modelData
                            objectName: "quickPower-" + modelData.mode; Layout.fillWidth: true
                            QQC2.ButtonGroup.group: powerButtons
                            text: modelData.label; enabled: !pane.busy; checked: pane.power.mode === modelData.mode
                            onClicked: pane.request("power-mode " + modelData.mode)
                        }
                    }
                    PC.Label { Layout.fillWidth: true; text: i18n("Automatic gives demanding apps more power and saves energy during lighter work."); wrapMode: Text.WordWrap; opacity: .7 }
                    PC.Label { Layout.fillWidth: true; visible: !pane.busy && (pane.power.modes || []).length === 0; text: i18n("This PC doesn't report adjustable power modes."); wrapMode: Text.WordWrap }
                    PC.Switch {
                        objectName: "quickAutoBatterySaver"; Layout.fillWidth: true
                        visible: pane.power.hasBattery === true && (pane.power.modes || []).indexOf("power-saver") !== -1
                        text: i18n("Automatic battery saver"); checked: pane.power.batterySaverAuto === true; enabled: !pane.busy
                        onClicked: pane.request("battery-saver " + (pane.power.batterySaverAuto ? "off" : "automatic"))
                    }
                    RowLayout {
                        Layout.fillWidth: true; visible: pane.power.hasBattery === true && pane.power.batterySaverAuto === true
                        PC.Label { Layout.fillWidth: true; text: i18n("Turn on at"); wrapMode: Text.WordWrap }
                        PC.ComboBox {
                            objectName: "quickSaverThreshold"
                            implicitWidth: Kirigami.Units.gridUnit * 6
                            implicitHeight: Math.max(Kirigami.Units.gridUnit * 2, font.pixelSize + 16)
                            Accessible.name: i18n("Turn on battery saver at")
                            model: pane.saverLevels.map(v => ({value: v, text: i18n("%1%", v)}))
                            textRole: "text"; valueRole: "value"; currentIndex: pane.saverLevels.indexOf(pane.power.batterySaverThreshold || 20)
                            enabled: !pane.busy
                            onActivated: pane.request("battery-saver threshold " + currentValue)
                        }
                    }
                    PC.Label { Layout.fillWidth: true; visible: pane.power.activeMode === "power-saver"; text: i18n("Power saver is active"); font.weight: Font.DemiBold; wrapMode: Text.WordWrap }
                    PC.Label { Layout.fillWidth: true; visible: pane.power.hasBattery === true && pane.power.batterySaverAuto === true
                        text: i18n("Automatic battery saving ends when you plug in. A manually selected Power saver stays on."); wrapMode: Text.WordWrap; opacity: .7 }
                }
                ColumnLayout {
                    Layout.fillWidth: true; visible: pane.page === "quiet"
                    PC.Label { Layout.fillWidth: true; text: pane.bridge.quietCaption(); wrapMode: Text.WordWrap; font.weight: Font.DemiBold }
                    QQC2.ButtonGroup { id: quietButtons }
                    Repeater {
                        model: [{mode: "off", label: i18n("Off")}, {mode: "hour", label: i18n("For one hour")},
                                {mode: "four-hours", label: i18n("For four hours")}, {mode: "tomorrow", label: i18n("Until tomorrow")},
                                {mode: "on", label: i18n("Until I turn it off")}]
                        PC.RadioButton {
                            required property var modelData
                            objectName: "quickQuiet-" + modelData.mode; Layout.fillWidth: true
                            QQC2.ButtonGroup.group: quietButtons
                            text: modelData.label; enabled: !pane.busy
                            checked: modelData.mode === "off" ? !pane.bridge.info.quiet
                                : modelData.mode === "on" ? pane.bridge.info.quiet && pane.bridge.info.quietIndefinite
                                : pane.bridge.info.quiet && !pane.bridge.info.quietIndefinite && pane.quietChoice === modelData.mode
                                  && pane.quietChoiceUntil === pane.bridge.info.quietUntil
                            onClicked: pane.setQuiet(modelData.mode)
                        }
                    }
                }
            }
        }
        PC.Button {
            objectName: "quickOptionsAdvanced"; Layout.fillWidth: true
            text: i18n("More settings…")
            onClicked: pane.bridge.openSettings(pane.page === "night" ? "display" : pane.page === "quiet" ? "notifications"
                : pane.page === "wifi" && pane.bridge.info.lanConnected ? "wifi#lan" : pane.page)
        }
    }
}
