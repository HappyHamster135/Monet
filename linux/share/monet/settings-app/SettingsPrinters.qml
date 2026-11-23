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
    id: printersColumn
    readonly property var found: sheet.printerInfo.printers || []
    spacing: 20
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("printers")
        art: sheet.art
        text: i18n("Printers")
        detail: printersColumn.found.length === 0 ? i18n("Printers on your network show up by themselves.")
            : i18np("%1 printer", "%1 printers", printersColumn.found.length)
    }
    SettingsControls.Card {
        tone: look
        Repeater {
            model: printersColumn.found
            SettingsControls.SettingRow {
                id: printerRow
                required property var modelData
                required property int index
                tone: look
                divider: index > 0
                title: modelData.label
                detail: [modelData.default ? i18n("Your default") : "",
                         modelData.state === "printing" ? i18n("Printing") : modelData.state === "off" ? i18n("Turned off")
                             : i18n("Ready"),
                         modelData.jobs > 0 ? i18np("%1 waiting", "%1 waiting", modelData.jobs) : ""]
                        .filter(s => s !== "").join(" · ")
                SettingsControls.Pill {
                    tone: look
                    visible: !printerRow.modelData.default
                    text: i18n("Make default")
                    onClicked: sheet.printerDefault(printerRow.modelData.name)
                }
            }
        }
        SettingsControls.SettingRow {
            tone: look
            divider: printersColumn.found.length > 0
            title: printersColumn.found.length > 0 ? i18n("Another printer") : i18n("No printers yet")
            detail: i18n("Turn it on and join it to your Wi-Fi: Monet finds most printers by itself")
            SettingsControls.Pill {
                tone: look
                text: i18n("Add…")
                onClicked: sheet.ask("kde printers")
            }
        }
    }
    SettingsControls.Pill {
        tone: look
        text: i18n("More printer settings…")
        onClicked: sheet.ask("kde printers")
    }
}
