import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts

ColumnLayout {
    id: panel
    required property var host
    required property var tone
    readonly property var settings: host.inputInfo.windowFocus || ({})
    readonly property string policy: settings.policy || ""
    readonly property bool hovering: ["FocusFollowsMouse", "FocusUnderMouse", "FocusStrictlyUnderMouse"].includes(policy)
    Layout.fillWidth: true
    Layout.minimumWidth: 0
    Layout.maximumWidth: parent.width
    spacing: 12

    SettingsControls.Caption {
        objectName: "search-window-focus"
        tone: panel.tone
        text: i18n("Window focus")
    }
    SettingsControls.Card {
        tone: panel.tone
        SettingsControls.SettingRow {
            tone: panel.tone
            divider: false
            title: i18n("Switch windows by")
            detail: panel.policy !== "" && !["ClickToFocus", "FocusFollowsMouse"].includes(panel.policy)
                ? i18n("An advanced focus policy is active.") : i18n("Choose which window receives your typing.")
            SettingsControls.Segments {
                objectName: "windowFocusPolicy"
                tone: panel.tone
                enabled: !!panel.policy && !panel.host.focusChanging
                options: [["click", i18n("Click")], ["hover", i18n("Hover")]]
                current: panel.policy === "ClickToFocus" ? "click" : panel.policy === "FocusFollowsMouse" ? "hover" : ""
                onPicked: value => { if (value !== current) panel.host.changeWindowFocus("policy", value) }
            }
        }
        SettingsControls.SettingRow {
            tone: panel.tone
            visible: panel.hovering
            title: i18n("Hover delay")
            detail: i18n("How long the pointer rests on a window before it gets focus.")
            C.ComboBox {
                objectName: "windowFocusDelay"
                enabled: !panel.host.focusChanging
                Accessible.name: i18n("Hover delay")
                textRole: "label"
                readonly property var times: {
                    const presets = [0, 150, 300, 600, 1000]
                    const saved = panel.settings.delay
                    if (Number.isInteger(saved) && !presets.includes(saved)) presets.push(saved)
                    return presets.sort((a, b) => a - b)
                }
                model: times.map(ms => ({label: ms === 0 ? i18n("Immediately") : i18n("%1 ms", ms)}))
                currentIndex: times.indexOf(panel.settings.delay)
                onActivated: index => {
                    if (times[index] !== panel.settings.delay) panel.host.changeWindowFocus("delay", times[index])
                }
            }
        }
        SettingsControls.SettingRow {
            tone: panel.tone
            title: i18n("Click in an inactive window")
            detail: panel.settings.first === "custom" ? i18n("A custom mouse action is active.")
                : i18n("Use the button under the pointer on the first click, or select the window first.")
            SettingsControls.Segments {
                objectName: "windowFirstClick"
                tone: panel.tone
                enabled: !!panel.settings.first && !panel.host.focusChanging
                options: [["pass", i18n("Use first click")], ["focus", i18n("Focus only")]]
                current: panel.settings.first || ""
                onPicked: value => { if (value !== current) panel.host.changeWindowFocus("first", value) }
            }
        }
        SettingsControls.SettingRow {
            tone: panel.tone
            tappable: true
            title: i18n("Advanced window behavior")
            onTapped: panel.host.ask("kde window-focus")
            SettingsControls.Glyph {
                width: 16
                height: 16
                path: "M9 5l7 7-7 7"
                color: panel.tone.dim
            }
        }
        SettingsControls.SettingRow {
            tone: panel.tone
            visible: !!panel.host.focusProblem
            title: panel.host.focusProblem
        }
    }
}
