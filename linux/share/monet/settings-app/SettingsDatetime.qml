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
    id: datetimeColumn
    property date now: new Date()
    spacing: 20
    Timer {
        interval: 1000
        running: sheet.pollingActive
        triggeredOnStart: true
        repeat: true
        onTriggered: datetimeColumn.now = new Date()
    }
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("datetime")
        art: sheet.art
        text: i18n("Date & Time")
        detail: i18n("Your clock, and where in the world it keeps time.")
    }
    // The time now, as the clocks will show it.
    SettingsControls.Card {
        tone: look
        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: 20
            spacing: 2
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: datetimeColumn.now.toLocaleTimeString(sheet.timeLocale(), Locale.ShortFormat)
                color: look.ink
                font.family: "Fraunces 72pt SuperSoft"
                font.weight: Font.Light
                font.pixelSize: 52
                font.letterSpacing: -1
                font.features: { "tnum": 1 }
            }
            Text {
                horizontalAlignment: Text.AlignLeft
                Layout.fillWidth: true
                text: datetimeColumn.now.toLocaleDateString(sheet.timeLocale(), Locale.LongFormat)
                    + ((sheet.clock.zone || "") !== "" ? " · " + sheet.zoneCity(sheet.clock.zone) : "")
                color: look.dim
                font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
                elide: Text.ElideRight
            }
        }
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            tappable: typeof sheet.clock.ntp === "boolean"
            title: i18n("Set automatically")
            detail: typeof sheet.clock.ntp === "boolean" ? i18n("From the internet, to the second") : i18n("This PC can't set its own time")
            onTapped: sheet.flipNtp()
            SettingsControls.Switch {
                tone: look
                visible: typeof sheet.clock.ntp === "boolean"
                active: sheet.clock.ntp === true
            }
        }
        SettingsControls.SettingRow {
            id: clockRow
            readonly property bool on24: sheet.hours24(sheet.timeLocale())
            tone: look
            tappable: sheet.otherClock() !== ""
            title: i18n("24-hour time")
            detail: !tappable ? i18n("As your region keeps it")
                : on24 ? i18n("13:00, not 1:00 PM") : i18n("1:00 PM, not 13:00")
            onTapped: sheet.flipClock()
            SettingsControls.Switch {
                tone: look
                active: clockRow.on24
                opacity: clockRow.tappable ? 1 : 0.5
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("Time zone")
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.Field {
            id: zoneSearch
            Layout.margins: 14
            tone: look
            hint: i18n("Search for a city")
            onAccepted: {
                const first = sheet.findZones(text)[0]
                if (first) {
                    sheet.chooseZone(first)
                    text = ""
                }
            }
        }
        Repeater {
            model: zoneSearch.text.trim() === "" ? [sheet.clock.zone || ""].filter(z => z !== "") : sheet.findZones(zoneSearch.text)
            SettingsControls.SettingRow {
                tone: look
                tappable: modelData !== sheet.clock.zone
                strong: false
                title: sheet.zoneCity(modelData)
                detail: sheet.zoneRegion(modelData)
                onTapped: {
                    sheet.chooseZone(modelData)
                    zoneSearch.text = ""
                }
                SettingsControls.Check {
                    tone: look
                    active: modelData === sheet.clock.zone
                }
            }
        }
        SettingsControls.SettingRow {
            tone: look
            visible: zoneSearch.text.trim() !== "" && sheet.findZones(zoneSearch.text).length === 0
            strong: false
            title: i18n("No time zone by that name")
            detail: i18n("Try a big city near you.")
        }
    }
    SettingsControls.Pill {
        tone: look
        text: i18n("More date & time settings…")
        onClicked: sheet.ask("kde datetime")
    }
}
