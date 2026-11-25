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
    id: page
    spacing: 20
    readonly property var power: typeof displayPower !== "undefined" ? displayPower : null
    readonly property bool watching: visible && sheet.pollingActive
    onWatchingChanged: if (power) power.observe(watching)
    Component.onCompleted: if (power) power.observe(watching)
    Component.onDestruction: if (power) power.observe(false)
    Loader {
        id: brightnessBackend
        active: page.watching
        source: "DisplayBrightness.qml"
        visible: false
    }
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("display")
        art: sheet.art
        text: i18n("Display")
        detail: i18n("Screen size, brightness and warmer colors at night.")
    }
    SettingsControls.ScreenSizes {
        tone: look
        displays: sheet.displaySizes
        busy: sheet.scaleBusy
        problem: sheet.scaleProblem
        onPicked: (name, percent) => sheet.changeScreenSize(name, percent)
    }
    SettingsControls.Caption {
        tone: look
        visible: brightnessRows.count > 1
        text: i18n("Brightness")
    }
    SettingsControls.Card {
        tone: look
        Repeater {
            id: brightnessRows
            model: brightnessBackend.item?.displays ?? null
            SettingsControls.SliderRow {
                required property var model
                required property int index
                objectName: "brightness-" + model.displayName
                tone: look
                divider: index > 0
                enabled: model.maxBrightness > 0
                title: brightnessRows.count > 1 ? model.label || model.displayName : i18n("Brightness")
                value: model.maxBrightness > 0 ? Math.round(model.brightness * 100 / model.maxBrightness) : 0
                onMoved: percent => brightnessBackend.item?.setBrightness(model.displayName, Math.round(percent * model.maxBrightness / 100))
            }
        }
        SettingsControls.SliderRow {
            id: defaultBrightness
            tone: look
            divider: false
            visible: !brightnessRows.count && (brightnessBackend.status === Loader.Error || sheet.info.legacyBrightness === true) && typeof sheet.info.brightness === "number"
            title: i18n("Brightness")
            from: 1
            value: sheet.info.brightness ?? 50
            onHeld: down => sheet.dragging = down
            onMoved: value => sheet.queue("brightness", value)
        }
        SettingsControls.SettingRow {
            tone: look
            divider: brightnessRows.count > 0 || defaultBrightness.visible
            tappable: true
            title: i18n("Night Light")
            detail: i18n("Warmer colors from sunset to sunrise, easier on the eyes")
            onTapped: sheet.flip("night", "night")
            SettingsControls.Switch {
                tone: look
                active: sheet.info.night === true
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        visible: powerRows.count > 0
        text: i18n("Display power")
    }
    SettingsControls.Card {
        tone: look
        visible: powerRows.count > 0
        Repeater {
            id: powerRows
            model: page.power
            SettingsControls.SettingRow {
                id: screenPowerRow
                required property int index
                required property var model
                objectName: "power-" + model.connector
                property bool waiting: false
                property bool failed: false
                readonly property bool awake: model.powered
                onAwakeChanged: {
                    ack.stop()
                    waiting = false
                    failed = false
                }
                Timer {
                    id: ack
                    interval: 3000
                    onTriggered: { screenPowerRow.waiting = false; screenPowerRow.failed = true }
                }
                divider: index > 0
                tone: look
                title: model.displayLabel || model.connector
                detail: failed ? i18n("The display did not confirm the change.") : model.connector
                SettingsControls.Pill {
                    tone: look
                    enabledPill: !screenPowerRow.waiting
                    text: screenPowerRow.waiting ? i18n("Changing…")
                        : screenPowerRow.awake ? i18n("Sleep display") : i18n("Wake display")
                    Accessible.name: i18n("%1, %2", text, screenPowerRow.title)
                    onClicked: {
                        screenPowerRow.failed = !page.power.setPower(screenPowerRow.model.outputId,
                            screenPowerRow.model.connector, !screenPowerRow.awake)
                        screenPowerRow.waiting = !screenPowerRow.failed
                        if (screenPowerRow.waiting) ack.restart()
                    }
                }
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("Display colors")
    }
    SettingsControls.Card {
        tone: look
        objectName: "search-color"
        Accessible.role: Accessible.Grouping
        Accessible.name: i18n("Display colors")
        SettingsControls.SettingRow {
            tone: look
            objectName: "openColorProfiles"
            divider: false
            tappable: true
            title: i18n("Color profiles…")
            detail: i18n("Choose your display to apply an ICC profile.")
            onTapped: sheet.ask("kde display")
            Kirigami.Icon {
                width: 18
                height: 18
                source: "go-next-symbolic"
                color: look.dim
            }
        }
        SettingsControls.SettingRow {
            tone: look
            objectName: "openDisplayTest"
            tappable: true
            title: i18n("Test display colors")
            detail: i18n("Check shadow detail, highlights and neutral grays on this display.")
            onTapped: {
                displayTest.showFullScreen()
                displayTest.requestActivate()
            }
            Kirigami.Icon {
                width: 18
                height: 18
                source: "go-next-symbolic"
                color: look.dim
            }
        }
    }
    DisplayTest {
        id: displayTest
        transientParent: sheet
        screen: sheet.screen
    }
    // For games and films: HDR, and the refresh rate keeping pace with the game,
    // on the screens that can (named when there's more than one).
    SettingsControls.Caption {
        tone: look
        visible: sheet.screenInfo.length > 0
        text: i18n("Games and films")
    }
    Repeater {
        model: sheet.screenInfo
        SettingsControls.Card {
            id: screenCard
            required property var modelData
            tone: look
            SettingsControls.SettingRow {
                tone: look
                divider: false
                visible: screenCard.modelData.hdr !== null
                tappable: true
                title: sheet.screenInfo.length > 1 ? i18n("HDR on %1", screenCard.modelData.name) : i18n("HDR")
                detail: i18n("Brighter highlights and deeper colors, in games and films made for it")
                onTapped: sheet.screenFeature(screenCard.modelData.name, "hdr", !screenCard.modelData.hdr)
                SettingsControls.Switch {
                    tone: look
                    active: screenCard.modelData.hdr === true
                }
            }
            SettingsControls.SettingRow {
                tone: look
                divider: screenCard.modelData.hdr !== null
                visible: screenCard.modelData.vrr !== null
                tappable: true
                title: sheet.screenInfo.length > 1 ? i18n("Smoother games on %1", screenCard.modelData.name)
                    : i18n("Smoother games")
                detail: i18n("The screen keeps pace with the game, without tearing (FreeSync, G-Sync)")
                onTapped: sheet.screenFeature(screenCard.modelData.name, "vrr", !screenCard.modelData.vrr)
                SettingsControls.Switch {
                    tone: look
                    active: screenCard.modelData.vrr === true
                }
            }
        }
    }
}
