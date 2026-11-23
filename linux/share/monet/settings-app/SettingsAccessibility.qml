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
        entry: sheet.entry("accessibility")
        art: sheet.art
        text: i18n("Accessibility")
        detail: i18n("Make Monet easier to see, read and use.")
    }
    SettingsControls.ScreenSizes {
        tone: look
        displays: sheet.displaySizes
        busy: sheet.scaleBusy
        problem: sheet.scaleProblem
        onPicked: (name, percent) => sheet.changeScreenSize(name, percent)
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Pointer size")
            objectName: "search-pointer"
            SettingsControls.Segments {
                tone: look
                options: [[24, i18n("Normal")], [36, i18n("Large")], [48, i18n("Larger")]]
                current: sheet.accessInfo.cursor || 24
                onPicked: value => sheet.access("cursor", value)
            }
        }
        SettingsControls.SettingRow {
            tone: look
            tappable: true
            title: i18n("Reduce motion")
            objectName: "search-motion"
            detail: i18n("Things appear without sliding, fading or bouncing")
            onTapped: sheet.access("reduced", sheet.accessInfo.reduced !== true)
            SettingsControls.Switch {
                tone: look
                active: sheet.accessInfo.reduced === true
            }
        }
        SettingsControls.SettingRow {
            tone: look
            visible: typeof sheet.accessInfo.reader === "boolean"
            tappable: true
            title: i18n("Screen reader")
            detail: i18n("Reads aloud what's on the screen and what you type")
            onTapped: sheet.access("reader", sheet.accessInfo.reader !== true)
            SettingsControls.Switch {
                tone: look
                active: sheet.accessInfo.reader === true
            }
        }
        SettingsControls.SettingRow {
            tone: look
            visible: typeof sheet.accessInfo.zoom === "boolean"
            tappable: true
            title: i18n("Magnifier")
            detail: i18n("The Windows key and + zooms in where the pointer is, the Windows key and − zooms out")
            onTapped: sheet.access("zoom", sheet.accessInfo.zoom !== true)
            SettingsControls.Switch {
                tone: look
                active: sheet.accessInfo.zoom === true
            }
        }
    }
    SettingsControls.Pill {
        tone: look
        text: i18n("More accessibility settings…")
        onClicked: sheet.ask("kde access")
    }
}
