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
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 6
        Text {
            horizontalAlignment: Text.AlignLeft
            Layout.fillWidth: true
            text: i18n("Welcome to Monet")
            color: look.ink
            font.family: "Fraunces 72pt SuperSoft"
            font.weight: Font.Light
            font.pixelSize: 36
            elide: Text.ElideRight
        }
        Text {
            horizontalAlignment: Text.AlignLeft
            Layout.fillWidth: true
            text: i18n("A few things worth knowing, then it's yours.")
            color: look.dim
            font.pixelSize: Math.max(17, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 1)
            wrapMode: Text.Wrap
        }
    }
    SettingsControls.Card {
        tone: look
        Repeater {
            // glyph, title, what it is, the way there (a page, or the widget gallery), its button
            model: [
                ["M4 7h10M18 7h2M4 17h4M12 17h8M16 4v6M10 14v6", i18n("Quick Settings, at the right of the bar"),
                 i18n("Wi-Fi, sound, brightness and the light, a click away. The arrow on a tile opens its page here."), "", ""],
                ["M4 4h7v7H4zM13 4h7v7h-7zM4 13h7v7H4zM13 13h7v7h-7z", i18n("Widgets on your desktop"),
                 i18n("Weather, a calendar with notes, your batteries, clocks around the world and more."), "widgets",
                 i18n("Edit widgets")],
                ["M9 6.5L18 12l-9 5.5z", i18n("Play on Windows"),
                 i18n("Games that need Windows are a restart away, and you come back here after."), "windows",
                 i18n("See your games")],
                [sheet.entry("light").glyph || "", i18n("Make it yours"),
                 i18n("Choose the light and the painting, and how big things are on the screen."), "light",
                 i18n("Light & Wallpaper")],
                ["M10 4a6 6 0 1 0 0 12a6 6 0 1 0 0-12M15 15l5 5", i18n("Find any setting"),
                 i18n("Type what you're looking for in the search at the top left, in your own words."), "", ""]
            ]
            SettingsControls.SettingRow {
                required property var modelData
                required property int index
                tone: look
                divider: index > 0
                title: modelData[1]
                detail: modelData[2]
                lead: SettingsControls.Glyph {
                    width: 20
                    height: 20
                    path: modelData[0]
                    filled: modelData[3] === "windows"
                    color: look.ink
                }
                SettingsControls.Pill {
                    tone: look
                    visible: modelData[4] !== ""
                    text: modelData[4]
                    onClicked: modelData[3] === "widgets" ? sheet.ask("widgets") : sheet.page = modelData[3]
                }
            }
        }
    }
    SettingsControls.Pill {
        tone: look
        kind: "lily"
        Layout.alignment: Qt.AlignRight
        text: i18n("Start using Monet")
        onClicked: sheet.close()
    }
}
