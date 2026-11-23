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
    id: backupsColumn
    readonly property var versions: sheet.earlier.versions || []
    spacing: 20
    // A copy in progress: how far along, every two seconds.
    Timer {
        interval: 2000
        repeat: true
        triggeredOnStart: true
        running: sheet.pollingActive && sheet.backup.copying === true
        onTriggered: sheet.loadBackup()
    }
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("backups")
        art: sheet.art
        text: i18n("Backups")
        detail: sheet.backup.versions === false ? i18n("Copies of your files, for when something goes wrong.")
            : i18n("Monet keeps your files as they were, every hour.")
    }

    // From Files' menu: this file's earlier versions.
    SettingsControls.Caption {
        tone: look
        visible: (sheet.earlier.file || "") !== ""
        text: i18n("Earlier versions of %1", sheet.earlier.name || "")
    }
    SettingsControls.Card {
        tone: look
        visible: (sheet.earlier.file || "") !== ""
        SettingsControls.SettingRow {
            tone: look
            divider: false
            visible: backupsColumn.versions.length === 0
            title: i18n("No earlier versions yet")
            detail: i18n("Monet keeps one every hour from now on.")
        }
        Repeater {
            model: backupsColumn.versions.slice(0, 12)
            SettingsControls.SettingRow {
                required property var modelData
                required property int index
                tone: look
                divider: index > 0
                title: sheet.moment(modelData.time)
                detail: modelData.folder ? i18n("Folder") : sheet.bytes(modelData.size)
                Row {
                    spacing: 8
                    SettingsControls.Pill {
                        tone: look
                        text: i18n("Show")
                        enabledPill: !sheet.earlierBusy
                        onClicked: sheet.useEarlier("version-open", modelData)
                    }
                    SettingsControls.Pill {
                        tone: look
                        text: i18n("Put back")
                        enabledPill: !sheet.earlierBusy
                        onClicked: sheet.useEarlier("put-back", modelData)
                    }
                }
            }
        }
    }
    Text {
        horizontalAlignment: Text.AlignLeft
        Layout.fillWidth: true
        visible: (sheet.earlier.file || "") !== "" && backupsColumn.versions.length > 0
        text: sheet.earlierMessage || i18n("Put back keeps both: the earlier version goes beside it, with its time in the name.")
        color: look.dim
        font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
        lineHeight: 1.3
        wrapMode: Text.Wrap
    }
    SettingsControls.Pill {
        tone: look
        visible: (sheet.earlier.file || "") !== ""
        text: i18n("Done")
        enabledPill: !sheet.earlierBusy
        onClicked: sheet.ask("versions-done", () => { sheet.earlier = {}; sheet.earlierMessage = "" })
    }

    SettingsControls.Caption {
        tone: look
        text: i18n("Earlier versions")
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            tappable: true
            title: i18n("Keep earlier versions")
            detail: i18n("Every hour, for two months. Only what changed takes room.")
            onTapped: {
                const on = sheet.backup.versions === false
                sheet.backup = sheet.changed(sheet.backup, ["versions"], on)
                sheet.ask("keep " + (on ? "on" : "off"), out => sheet.backup = sheet.json(out, sheet.backup))
            }
            SettingsControls.Switch {
                tone: look
                active: sheet.backup.versions !== false
            }
        }
        SettingsControls.SettingRow {
            tone: look
            visible: sheet.backup.versions !== false
            title: i18n("Your files as they were")
            detail: (sheet.backup.kept || 0) > 0 ? i18n("Opens in Files: copy back what you need.")
                : i18n("The first one is kept within the hour.")
            Row {
                spacing: 8
                Repeater {
                    model: [["hour", i18n("An hour ago")], ["day", i18n("Yesterday")], ["week", i18n("Last week")]]
                    SettingsControls.Pill {
                        required property var modelData
                        readonly property var snapshot: (sheet.backup.lookBack || {})[modelData[0]]
                        tone: look
                        visible: !!snapshot
                        text: modelData[1]
                        onClicked: sheet.ask("backup-open " + snapshot.time)
                    }
                }
            }
        }
    }

    SettingsControls.Caption {
        tone: look
        text: i18n("A copy on a drive")
    }
    SettingsControls.Card {
        tone: look
        // The drive chosen for copies.
        SettingsControls.SettingRow {
            tone: look
            divider: false
            visible: !!sheet.backup.drive
            title: sheet.backup.label || i18n("Your backup drive")
            detail: sheet.backup.copying ? i18n("Copying… %1%", sheet.backup.percent || 0)
                : (sheet.backup.error || "") !== "" ? sheet.backup.error
                : sheet.backup.last ? i18n("Last copy: %1", sheet.moment(sheet.backup.last))
                : sheet.backup.plugged ? i18n("Not copied yet") : i18n("Plug it in to copy your files")
            Row {
                spacing: 8
                SettingsControls.Pill {
                    tone: look
                    visible: sheet.backup.plugged === true && !sheet.backup.copying
                    text: i18n("Copy now")
                    onClicked: {
                        sheet.backup = sheet.changed(sheet.backup, ["copying"], true)
                        sheet.ask("backup-now")
                    }
                }
                SettingsControls.Pill {
                    tone: look
                    visible: sheet.backup.plugged === true
                    text: i18n("Open")
                    onClicked: sheet.ask("backup-open-drive")
                }
            }
        }
        SettingsControls.SettingRow {
            tone: look
            visible: !!sheet.backup.drive
            title: i18n("Stop copying to this drive")
            detail: i18n("What's on it stays there")
            SettingsControls.Pill {
                tone: look
                text: i18n("Stop")
                onClicked: sheet.ask("backup-drive none", out => sheet.backup = sheet.json(out, sheet.backup))
            }
        }
        // No drive chosen: the ones plugged in, or how to start.
        Repeater {
            model: sheet.backup.drive ? [] : (sheet.backup.drives || [])
            SettingsControls.SettingRow {
                required property var modelData
                required property int index
                tone: look
                divider: index > 0
                title: modelData.label || i18n("USB drive")
                detail: sheet.bytes(modelData.size)
                SettingsControls.Pill {
                    tone: look
                    text: i18n("Copy to this drive")
                    onClicked: sheet.ask("backup-drive " + modelData.uuid, out => sheet.backup = sheet.json(out, sheet.backup))
                }
            }
        }
        SettingsControls.SettingRow {
            tone: look
            divider: false
            visible: !sheet.backup.drive && (sheet.backup.drives || []).length === 0
            title: i18n("Plug in a USB drive")
            detail: i18n("Monet copies your files to it whenever it's plugged in, at most once a day.")
        }
    }
    Text {
        horizontalAlignment: Text.AlignLeft
        Layout.fillWidth: true
        text: i18n("Games aren't copied: Steam and the other stores download them again. Neither is the Trash.")
        color: look.dim
        font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
        lineHeight: 1.3
        wrapMode: Text.Wrap
    }
}
