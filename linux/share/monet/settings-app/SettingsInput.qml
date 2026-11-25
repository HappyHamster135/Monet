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
    id: inputColumn
    readonly property var codes: (sheet.inputInfo.layouts || []).map(l => l.code)
    spacing: 20
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("input")
        art: sheet.art
        text: i18n("Mouse & Keyboard")
        detail: i18n("How the pointer moves and scrolls, and the languages you type in.")
    }
    // The mouse and the touchpad, each set as one (all mice alike).
    Repeater {
        // The touchpad first: on a laptop it's the pointer you have.
        model: [["touchpad", i18n("Touchpad")], ["mouse", i18n("Mouse")]].filter(k => !!sheet.inputInfo[k[0]])
        ColumnLayout {
            id: pointerKind
            required property var modelData
            readonly property var settings: sheet.inputInfo[modelData[0]] || {}
            Layout.fillWidth: true
            spacing: 20
            SettingsControls.Caption {
                tone: look
                text: pointerKind.modelData[1]
            }
            SettingsControls.Card {
                tone: look
                SettingsControls.SliderRow {
                    tone: look
                    divider: false
                    visible: pointerKind.settings.speed !== undefined
                    title: i18n("Pointer speed")
                    value: pointerKind.settings.speed !== undefined ? pointerKind.settings.speed : 50
                    onHeld: down => sheet.dragging = down
                    onMoved: value => sheet.queue("pointer " + pointerKind.modelData[0] + " speed", value)
                }
                Repeater {
                    model: [
                        ["tap", i18n("Tap to click"), i18n("A light tap is a click")],
                        ["natural", i18n("Natural scrolling"), i18n("The page follows your fingers, as on a phone")],
                        ["left", i18n("Left-handed"), i18n("The buttons swap sides")],
                        ["typing", i18n("Off while typing"), i18n("A palm on it won't move the pointer")]
                    ].filter(s => pointerKind.settings[s[0]] !== undefined)
                    SettingsControls.SettingRow {
                        id: pointerRow
                        required property var modelData
                        required property int index
                        tone: look
                        divider: index > 0 || pointerKind.settings.speed !== undefined
                        tappable: true
                        title: modelData[1]
                        detail: modelData[2]
                        onTapped: sheet.pointer(pointerKind.modelData[0], modelData[0], pointerKind.settings[modelData[0]] !== true)
                        SettingsControls.Switch {
                            tone: look
                            active: pointerKind.settings[pointerRow.modelData[0]] === true
                        }
                    }
                }
            }
        }
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: true
            tappable: true
            objectName: "wheelScrollingSettings"
            title: i18n("Mouse wheel scrolling")
            detail: i18n("Adjust wheel distance, smoothing and sideways scrolling.")
            onTapped: sheet.ask("utilities wheel-scrolling")
            SettingsControls.Glyph {
                width: 16
                height: 16
                path: "M9 5l7 7-7 7"
                color: look.dim
            }
        }
        SettingsControls.SettingRow {
            tone: look
            divider: false
            tappable: true
            objectName: "extraClickSettings"
            title: i18n("Extra click filter")
            detail: i18n("Filter rapid extra clicks from a worn mouse button.")
            onTapped: sheet.ask("utilities extra-clicks")
            SettingsControls.Glyph {
                width: 16
                height: 16
                path: "M9 5l7 7-7 7"
                color: look.dim
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("Keyboard")
    }
    SettingsControls.Card {
        tone: look
        Repeater {
            model: sheet.inputInfo.layouts || []
            SettingsControls.SettingRow {
                id: layoutRow
                required property var modelData
                required property int index
                tone: look
                divider: index > 0
                tappable: index > 0
                strong: index === 0
                title: modelData.name
                detail: index === 0 ? i18n("Typing starts in this one") : i18n("Click to make this the main one")
                onTapped: sheet.setLayouts([modelData.code].concat(inputColumn.codes.filter(c => c !== layoutRow.modelData.code)))
                SettingsControls.Pill {
                    tone: look
                    visible: inputColumn.codes.length > 1
                    text: i18n("Remove")
                    onClicked: sheet.setLayouts(inputColumn.codes.filter(c => c !== layoutRow.modelData.code))
                }
            }
        }
        SettingsControls.Field {
            id: layoutSearch
            Layout.margins: 14
            tone: look
            hint: i18n("Add a language or layout")
            onAccepted: {
                const first = sheet.findLayouts(text)[0]
                if (first) {
                    sheet.setLayouts(inputColumn.codes.concat([first.code]))
                    text = ""
                }
            }
        }
        Repeater {
            model: sheet.findLayouts(layoutSearch.text)
            SettingsControls.SettingRow {
                required property var modelData
                tone: look
                tappable: true
                strong: false
                title: modelData.name
                onTapped: {
                    sheet.setLayouts(inputColumn.codes.concat([modelData.code]))
                    layoutSearch.text = ""
                }
                SettingsControls.Glyph {
                    width: 14
                    height: 14
                    path: "M12 5v14M5 12h14"
                    color: look.lily
                }
            }
        }
        SettingsControls.SettingRow {
            tone: look
            visible: layoutSearch.text.trim() !== "" && sheet.findLayouts(layoutSearch.text).length === 0
            strong: false
            title: i18n("No layout by that name")
            detail: i18n("Try your language's name, like Swedish or Japanese.")
        }
    }
    Text {
        horizontalAlignment: Text.AlignLeft
        Layout.fillWidth: true
        Layout.topMargin: -8
        visible: inputColumn.codes.length > 1
        text: i18n("The bar shows which one you're typing in. Click it to switch.")
        color: look.dim
        font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
        wrapMode: Text.Wrap
    }
    // Plasma's own keys (and Monet's menu, on the Windows key), to learn them by.
    SettingsControls.Caption {
        tone: look
        text: i18n("Keyboard shortcuts")
    }
    SettingsControls.Card {
        tone: look
        GridLayout {
            Layout.fillWidth: true
            Layout.margins: 20
            columns: 2
            columnSpacing: 28
            rowSpacing: 10
            Repeater {
                // Windows' own keys where Windows has one (monet-look --keys sets those).
                model: [[i18n("Open the menu"), ["Meta"]], [i18n("Settings"), ["Meta", "I"]],
                        [i18n("Quick Settings"), ["Meta", "A"]], [i18n("Games"), ["Meta", "G"]],
                        [i18n("Files"), ["Meta", "E"]], [i18n("Run or find"), ["Meta", "R"]],
                        [i18n("Lock the screen"), ["Meta", "L"]], [i18n("The desktop"), ["Meta", "D"]],
                        [i18n("All your windows"), ["Meta", "Tab"]], [i18n("Switch windows"), ["Alt", "Tab"]],
                        [i18n("A window on one half"), ["Meta", "\u2190", "\u2192"]],
                        ...(sheet.prefs.snap !== false ? [[i18n("Snap layouts"), ["Meta", "Z"]]] : []),
                        [i18n("A window on the whole screen"), ["Meta", "\u2191"]],
                        [i18n("Minimize a window"), ["Meta", "\u2193"]],
                        [i18n("What's running"), ["Ctrl", "Shift", "Esc"]],
                        [i18n("What you copied"), ["Meta", "V"]], [i18n("Emoji"), ["Meta", "."]],
                        [i18n("Next keyboard layout"), ["Meta", "Space"]],
                        [i18n("Screenshot"), ["Print"]], [i18n("Part of the screen"), ["Meta", "Shift", "S"]],
                        [i18n("Save the last 30 seconds"), ["Meta", "Alt", "G"]],
                        [i18n("Record the screen"), ["Meta", "Alt", "R"]],
                        [i18n("Restart or shut down"), ["Ctrl", "Alt", "Del"]]]
                RowLayout {
                    id: shortcutRow
                    required property var modelData
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1
                    spacing: 10
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        text: shortcutRow.modelData[0]
                        color: look.ink
                        font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                        elide: Text.ElideRight
                    }
                    Row {
                        spacing: 4
                        Repeater {
                            model: shortcutRow.modelData[1]
                            SettingsControls.Key {
                                required property var modelData
                                tone: look
                                keyName: modelData
                            }
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
            text: i18n("More mouse & keyboard settings…")
            onClicked: sheet.ask("kde input")
        }
        SettingsControls.Pill {
            tone: look
            text: i18n("Change shortcuts…")
            onClicked: sheet.ask("kde keys")
        }
    }
}
