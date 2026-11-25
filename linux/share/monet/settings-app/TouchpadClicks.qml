import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.plasma.workspace.dbus as DBus

ColumnLayout {
    id: panel
    required property var host
    required property var tone
    readonly property var pads: host.inputInfo.touchpads || []
    property string selectedId: ""
    readonly property var pad: pads.find(p => p.id === selectedId) || pads[0] || null
    property bool testing: false
    property int primary: 0
    property int secondary: 0
    property int middle: 0
    visible: !!pad || !!host.padProblem || host.currentAnchor === "touchpad-clicks"
    Layout.fillWidth: true
    Layout.minimumWidth: 0
    Layout.maximumWidth: parent.width
    spacing: 12

    // Replacing a ComboBox model resets its selection, even if only a tap setting changed.
    function syncPicker() {
        const choices = pads.map(p => ({id: p.id, name: p.name}))
        if (JSON.stringify(choices) !== JSON.stringify(picker.model)) picker.model = choices
        picker.currentIndex = choices.findIndex(p => p.id === pad?.id)
    }
    onPadsChanged: Qt.callLater(syncPicker)
    Component.onCompleted: syncPicker()
    function change(key, value) {
        if (pad && !host.padChanging) host.changePad(pad.id, key, value)
    }
    function count(button) {
        if (button === Qt.LeftButton) primary++
        else if (button === Qt.RightButton) secondary++
        else if (button === Qt.MiddleButton) middle++
    }
    DBus.SignalWatcher {
        objectName: "touchpadDevicesWatcher"
        enabled: panel.host.pollingActive && panel.host.page === "input"
        busType: DBus.BusType.Session; service: "org.kde.KWin"
        path: "/org/kde/KWin/InputDevice"; iface: "org.kde.KWin.InputDeviceManager"
        // SignalWatcher appends the case-sensitive KWin signal name to "dbus".
        function dbusdeviceAdded(name) { reload.restart() }
        function dbusdeviceRemoved(name) { reload.restart() }
    }
    Connections {
        target: panel.host
        function onActiveChanged() { if (panel.host.active) reload.restart() }
    }
    Timer { id: reload; interval: 90; onTriggered: panel.host.loadInputDevices() }
    SettingsControls.Caption { objectName: "search-touchpad-clicks"; tone: panel.tone; text: i18n("Touchpad clicks") }
    SettingsControls.Card {
        tone: panel.tone
        SettingsControls.SettingRow {
            tone: panel.tone; divider: false
            title: panel.pad?.name || (panel.host.inputReading ? i18n("Checking touchpads…") : i18n("No touchpad connected"))
            visible: panel.pads.length <= 1
        }
        SettingsControls.SettingRow {
            tone: panel.tone; divider: false; visible: panel.pads.length > 1
            title: i18n("Touchpad")
            C.ComboBox {
                id: picker; objectName: "clickTouchpadDevice"
                width: Math.min(implicitWidth, parent.controlsAvailableWidth)
                model: []; textRole: "name"; enabled: !panel.host.padChanging
                Accessible.name: i18n("Touchpad")
                onActivated: index => panel.selectedId = model[index].id
            }
        }
        SettingsControls.SettingRow {
            id: tapRow; objectName: "touchpadTapEnabled"
            tone: panel.tone; visible: panel.pad?.tap !== undefined
            title: i18n("Tap to click"); detail: i18n("A light tap is a click")
            enabled: !panel.host.padChanging; tappable: true; checkable: true; checked: !!panel.pad?.tap
            onTapped: panel.change("tap", checked ? "off" : "on")
            SettingsControls.Switch { tone: panel.tone; active: tapRow.checked }
        }
        SettingsControls.SettingRow {
            tone: panel.tone; visible: !!panel.pad?.tap && panel.pad?.map !== undefined
            title: i18n("Two-finger tap")
            detail: (panel.pad?.fingers || 0) < 3 ? "" : panel.pad?.map === "middle"
                ? i18n("Three fingers give a secondary click.") : i18n("Three fingers give a middle click.")
            SettingsControls.Segments {
                objectName: "touchpadTapButtons"; tone: panel.tone; enabled: !panel.host.padChanging
                options: [["secondary", i18n("Secondary")], ["middle", i18n("Middle")]]
                current: panel.pad?.map || ""
                onPicked: value => { if (value !== current) panel.change("map", value) }
            }
        }
        SettingsControls.SettingRow {
            id: dragRow
            tone: panel.tone; visible: !!panel.pad?.tap && panel.pad?.drag !== undefined
            title: i18n("Tap and drag"); detail: i18n("Tap, then touch and hold to drag.")
            enabled: !panel.host.padChanging; tappable: true; checkable: true; checked: !!panel.pad?.drag
            onTapped: panel.change("drag", checked ? "off" : "on")
            SettingsControls.Switch { tone: panel.tone; active: dragRow.checked }
        }
        SettingsControls.SettingRow {
            tone: panel.tone; visible: !!panel.pad?.methods?.length
            title: i18n("Physical click")
            detail: panel.pad?.method === "fingers" ? i18n("Press with two fingers for a secondary click or three for a middle click.")
                : panel.pad?.method === "areas" ? i18n("Where you press along the bottom selects the button.") : ""
            SettingsControls.Segments {
                objectName: "touchpadPressMethod"; tone: panel.tone; enabled: !panel.host.padChanging && options.length > 1
                options: [["areas", i18n("Button areas")], ["fingers", i18n("Finger count")]].filter(o => panel.pad?.methods?.includes(o[0]))
                current: panel.pad?.method || ""
                onPicked: value => { if (value !== current) panel.change("method", value) }
            }
        }
        SettingsControls.SettingRow {
            objectName: "touchpadTestToggle"
            tone: panel.tone; visible: !!panel.pad
            tappable: true; checkable: true; checked: panel.testing; title: i18n("Test clicks")
            onTapped: panel.testing = !panel.testing
            SettingsControls.Switch { tone: panel.tone; active: panel.testing }
        }
        Rectangle {
            id: target; objectName: "touchpadClickTest"
            visible: panel.testing && !!panel.pad
            Layout.fillWidth: true; Layout.margins: 10
            implicitHeight: counter.implicitHeight + 34; radius: 10; color: panel.tone.wash2
            Accessible.role: Accessible.StaticText; Accessible.name: counter.text
            Text {
                id: counter; anchors.centerIn: parent; width: parent.width - 20
                horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
                color: panel.tone.ink
                text: i18n("Click in the box to test each button.") + "\n" +
                    i18n("Primary %1 · Secondary %2 · Middle %3", panel.primary, panel.secondary, panel.middle)
            }
            TapHandler {
                acceptedButtons: Qt.LeftButton | Qt.RightButton | Qt.MiddleButton
                onTapped: (point, button) => panel.count(button)
            }
        }
        SettingsControls.Pill {
            visible: target.visible; Layout.alignment: Qt.AlignHCenter; Layout.bottomMargin: 8
            tone: panel.tone; text: i18n("Reset count")
            onClicked: { panel.primary = 0; panel.secondary = 0; panel.middle = 0 }
        }
    }
    SettingsControls.MaintenanceText { tone: panel.tone; visible: !!panel.host.padProblem; text: panel.host.padProblem }
    SettingsControls.Pill {
        tone: panel.tone; text: i18n("More touchpad settings…")
        onClicked: panel.host.ask("kde touchpad")
    }
}
