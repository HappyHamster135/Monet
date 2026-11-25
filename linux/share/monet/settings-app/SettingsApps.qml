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
    id: appsColumn
    // The kind whose apps are showing, to pick one.
    property string choosing: ""
    readonly property var names: ({
        browser: i18n("Web browser"), mail: i18n("Email"), files: i18n("Folders"), music: i18n("Music"),
        video: i18n("Video"), photos: i18n("Photos"), pdf: i18n("PDF documents"), text: i18n("Text files")
    })
    spacing: 20
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("apps")
        art: sheet.art
        text: i18n("Default Apps")
        detail: i18n("What opens web links, mail, folders, music, films, photos, PDFs and text.")
    }
    SettingsControls.Card {
        tone: look
        Repeater {
            model: sheet.appDefaults
            ColumnLayout {
                id: kindBlock
                required property var modelData
                required property int index
                readonly property var current: modelData.apps.find(a => a.id === modelData.current) || null
                readonly property bool opened: appsColumn.choosing === modelData.id
                Layout.fillWidth: true
                spacing: 0
                SettingsControls.SettingRow {
                    tone: look
                    divider: kindBlock.index > 0
                    tappable: kindBlock.modelData.apps.length > 0 || (kindBlock.modelData.store || "") !== ""
                    title: appsColumn.names[kindBlock.modelData.id] || kindBlock.modelData.id
                    detail: kindBlock.current ? kindBlock.current.name
                        : kindBlock.modelData.apps.length > 0 ? i18n("Nothing chosen yet")
                        : (kindBlock.modelData.store || "") !== "" ? i18n("No app for this yet. Find one in the Store")
                        : i18n("No app for this yet")
                    lead: Kirigami.Icon {
                        width: 28
                        height: 28
                        source: kindBlock.current ? kindBlock.current.icon : "application-x-executable"
                    }
                    onTapped: {
                        if (kindBlock.modelData.apps.length > 0) {
                            appsColumn.choosing = kindBlock.opened ? "" : kindBlock.modelData.id
                        } else {
                            sheet.ask("launch " + sheet.hex(kindBlock.modelData.store))
                        }
                    }
                    // A row, so only what shows takes room.
                    Row {
                        SettingsControls.Glyph {
                            visible: kindBlock.modelData.apps.length > 0
                            width: 14
                            height: 14
                            path: kindBlock.opened ? "M6 15l6-6 6 6" : "M6 9l6 6 6-6"
                            color: look.dim
                        }
                        SettingsControls.Pill {
                            tone: look
                            visible: kindBlock.modelData.apps.length === 0 && (kindBlock.modelData.store || "") !== ""
                            kind: "lily"
                            text: i18n("Find one")
                            onClicked: sheet.ask("launch " + sheet.hex(kindBlock.modelData.store))
                        }
                    }
                }
                Repeater {
                    model: kindBlock.opened ? kindBlock.modelData.apps : []
                    SettingsControls.SettingRow {
                        id: takerRow
                        required property var modelData
                        Layout.leftMargin: 28
                        tone: look
                        tappable: true
                        strong: false
                        title: modelData.name
                        lead: Kirigami.Icon {
                            width: 24
                            height: 24
                            source: takerRow.modelData.icon
                        }
                        onTapped: {
                            sheet.setDefault(kindBlock.modelData.id, modelData)
                            appsColumn.choosing = ""
                        }
                        SettingsControls.Check {
                            tone: look
                            active: takerRow.modelData.id === kindBlock.modelData.current
                        }
                    }
                }
            }
        }
    }
    SettingsControls.Pill {
        tone: look
        text: i18n("More default apps…")
        onClicked: sheet.ask("kde apps")
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            objectName: "quitOnCloseSettings"
            tone: look
            divider: false
            tappable: true
            title: i18n("Quit on last window")
            detail: i18n("Choose which apps quit when you close their last window.")
            onTapped: sheet.ask("utilities quit-on-close")
            SettingsControls.Glyph {
                width: 16
                height: 16
                path: "M9 5l7 7-7 7"
                color: look.dim
            }
        }
    }
    SettingsControls.Caption { tone: look; text: i18n("Browser bookmarks") }
    SettingsControls.Card {
        id: bookmarkImport
        objectName: "search-bookmarks"
        tone: look
        readonly property var profiles: sheet.browserInfo.profiles || []
        property string profile: profiles.length === 1 ? profiles[0].id : ""
        property string source: sheet.browserInfo.count > 0 ? "windows" : ""
        property bool busy: false
        property var preview: ({})
        property var preparedImport: ({})
        property string message: ""
        property string checkedState: ""
        readonly property var previousImport: (sheet.browserInfo.imports || []).find(item => item.profile === profile) || ({})
        function reset() { preview = ({}); preparedImport = ({}); message = ""; checkedState = "" }
        function problem(code) {
            return ({busy: i18n("Close this Zen profile, then try again. Your bookmarks are unchanged."),
                profile: i18n("Choose a Zen profile. Open Zen once if the list is empty."),
                browser: i18n("Install Zen before importing bookmarks."),
                source: i18n("This file could not be read. Choose the bookmark export again."),
                invalid: i18n("This is not a supported bookmark HTML export. Export bookmarks as HTML from your old browser."),
                large: i18n("This export is too large. Choose an export under 16 MB with fewer than 25,000 bookmarks."),
                database: i18n("Zen's bookmarks could not be read. Open Zen to check this profile, then try again."),
                changed: i18n("The file or bookmarks changed. Review the import again."),
                storage: i18n("The import file could not be saved. Check free space and try again.")})[code]
                || i18n("The import could not be checked. Try again.")
        }
        function act(action) {
            if (busy) return
            busy = true; message = ""; checkedState = ""
            const request = action === "verify" ? {"id": preparedImport.id}
                : {profile: profile, source: source, token: preview.token || ""}
            sheet.ask("bookmarks-" + action + " " + sheet.hex(JSON.stringify(request)), (out, code) => {
                busy = false
                const result = sheet.json(out, ({}))
                if (code !== 0 || !result.ok) {
                    if (action !== "verify") preview = ({})
                    message = problem(result.error)
                    return
                }
                if (action === "preview") preview = result
                else if (action === "prepare") {
                    preparedImport = result
                    if (!result.opened && result.state === "prepared")
                        message = i18n("The file is ready, but Zen did not start. Open the selected profile to import it.")
                } else {
                    checkedState = result.state
                    message = result.state === "verified"
                        ? i18np("Verified %1 imported bookmark.", "Verified %1 imported bookmarks.", result.count)
                        : result.state === "partial" ? i18n("%1 of %2 bookmarks found. Finish the import in the selected profile, then check again.", result.count, result.expected)
                        : i18n("No imported bookmarks found yet. Import the prepared file in the selected profile, then check again.")
                    if (result.duplicates > 0) message += " " + i18n("This file was imported more than once. Remove the extra imported folder in Zen.")
                }
            })
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Bring your bookmarks")
            detail: i18n("Choose an HTML export and a Zen profile. Existing links are skipped. Your current bookmarks stay in place.")
        }
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Source")
            detail: bookmarkImport.source === "windows" ? i18n("Bookmarks from Windows") : bookmarkImport.source
            SettingsControls.Pill {
                tone: look; text: i18n("Choose HTML file")
                enabledPill: !bookmarkImport.busy
                onClicked: bookmarkPicker.open()
            }
        }
        SettingsControls.SettingRow {
            tone: look; visible: sheet.browserInfo.count > 0
            title: i18n("From Windows")
            detail: i18np("%1 bookmark", "%1 bookmarks", sheet.browserInfo.count || 0)
            SettingsControls.Pill {
                tone: look; text: i18n("Use these")
                enabledPill: !bookmarkImport.busy
                onClicked: { bookmarkImport.reset(); bookmarkImport.source = "windows" }
            }
        }
        SettingsControls.SettingRow {
            tone: look; title: i18n("Destination profile")
            detail: bookmarkImport.profiles.length ? i18n("Only the selected profile is used. Close it before reviewing or checking an import.")
                : i18n("Open Zen once to create a profile, then reopen this page.")
        }
        Repeater {
            model: bookmarkImport.profiles
            SettingsControls.SettingRow {
                id: bookmarkProfile
                required property var modelData
                objectName: "bookmarkProfile-" + modelData.id
                tone: look; title: modelData.name; detail: modelData.id
                tappable: !bookmarkImport.busy; checkable: true
                checked: bookmarkImport.profile === modelData.id
                Accessible.role: Accessible.RadioButton
                onTapped: { bookmarkImport.reset(); bookmarkImport.profile = modelData.id }
                Text {
                    text: bookmarkProfile.checked ? i18n("Selected") : i18n("Choose")
                    color: bookmarkProfile.checked ? look.lily : look.dim
                    font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                    font.weight: bookmarkProfile.checked ? Font.DemiBold : Font.Normal
                }
            }
        }
        SettingsControls.SettingRow {
            tone: look; visible: !!bookmarkImport.previousImport.id && !bookmarkImport.preparedImport.id
            title: i18n("Previous import")
            detail: bookmarkImport.previousImport.folder || ""
            SettingsControls.Pill {
                tone: look; text: i18n("Check previous import")
                enabledPill: !bookmarkImport.busy
                onClicked: { bookmarkImport.preparedImport = bookmarkImport.previousImport; bookmarkImport.act("verify") }
            }
        }
        SettingsControls.SettingRow {
            tone: look; title: i18n("Review import")
            detail: bookmarkImport.preview.ok
                ? i18n("New links: %1. Already bookmarked or repeated: %2. Unsupported links skipped: %3.", bookmarkImport.preview.new, bookmarkImport.preview.duplicates, bookmarkImport.preview.unsupported)
                : i18n("Review the file before creating an import. No browser data is changed by this step.")
            SettingsControls.Pill {
                objectName: "bookmarkReview"
                tone: look; text: bookmarkImport.busy ? i18n("Checking…") : i18n("Review")
                enabledPill: !bookmarkImport.busy && bookmarkImport.profile !== "" && bookmarkImport.source !== ""
                onClicked: { bookmarkImport.preparedImport = ({}); bookmarkImport.checkedState = ""; bookmarkImport.act("preview") }
            }
        }
        Repeater {
            model: bookmarkImport.preview.sample || []
            Text {
                required property string modelData
                Layout.fillWidth: true; Layout.margins: 12
                text: modelData; textFormat: Text.PlainText
                color: look.dim; wrapMode: Text.WrapAnywhere
            }
        }
        SettingsControls.SettingRow {
            tone: look; visible: bookmarkImport.preview.ok === true && !bookmarkImport.preparedImport.id
            title: bookmarkImport.preview.new > 0 ? i18n("Ready to import") : i18n("Nothing new to import")
            detail: i18n("New links go into their own folder. To undo, remove that folder in Zen. Import the prepared file only once.")
            SettingsControls.Pill {
                objectName: "bookmarkPrepare"
                tone: look; kind: "lily"; text: i18n("Prepare and open Zen")
                enabledPill: !bookmarkImport.busy && bookmarkImport.preview.new > 0
                onClicked: bookmarkImport.act("prepare")
            }
        }
        SettingsControls.SettingRow {
            tone: look; visible: !!bookmarkImport.preparedImport.id
            title: i18n("Finish in Zen")
            detail: i18n("In the selected profile's Library, choose Import and Backup, then Import Bookmarks from HTML. Select %1. The new folder is %2. Close this profile when finished, then check the import here.", bookmarkImport.preparedImport.file || "", bookmarkImport.preparedImport.folder || "")
            SettingsControls.Pill {
                objectName: "bookmarkVerify"
                tone: look; text: i18n("Check import")
                enabledPill: !bookmarkImport.busy
                onClicked: bookmarkImport.act("verify")
            }
        }
        SettingsControls.SettingRow {
            objectName: "bookmarkMessage"
            tone: look; visible: bookmarkImport.message !== ""
            title: bookmarkImport.checkedState === "verified" ? i18n("Import checked") : i18n("Import status")
            detail: bookmarkImport.message
            divider: false
        }
        FileDialog {
            id: bookmarkPicker
            title: i18n("Choose a bookmark export")
            nameFilters: [i18n("Bookmark HTML files") + " (*.html *.htm)"]
            onAccepted: { bookmarkImport.reset(); bookmarkImport.source = selectedFile.toString() }
        }
    }

    // Windows seals its saved passwords; moving them remains an explicit action.
    SettingsControls.Caption {
        tone: look
        visible: fromWindows.visible
        text: i18n("From Windows")
    }
    SettingsControls.Card {
        id: fromWindows
        tone: look
        readonly property var b: sheet.browserInfo
        readonly property int count: b.count || 0
        visible: count > 0
        SettingsControls.SettingRow {
            tone: look
            title: i18n("Passwords")
            detail: i18n("Windows keeps them sealed, so they can't come over by themselves. In Windows, export them from Edge or Chrome (in its passwords settings) into Shared with Monet. Then in Zen, open about:logins, choose Import from a File, and delete the file once they're in.")
            SettingsControls.Pill {
                tone: look
                visible: (fromWindows.b.shared || "") !== ""
                text: i18n("Show the folder")
                onClicked: Qt.openUrlExternally("file://" + encodeURI(fromWindows.b.shared))
            }
        }
    }
}
