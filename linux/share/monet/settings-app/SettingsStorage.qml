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
    id: storageColumn
    function cancelConfirmation() {
        if (sheet.retainedReview !== null) {
            if (!sheet.retainedBusy) {
                const id = sheet.retainedReview.id
                sheet.retainedReview = null
                sheet.retainedConsent = false
                sheet.focusControl("reviewRetained-" + id)
            }
        } else if (askingTrash) {
            askingTrash = false
            sheet.focusControl("emptyTrash")
        } else return false
        return true
    }
    // What fills the disk, each in a color of The Hours. Only a whole measurement
    // that fits in the space in use is split up; otherwise the bar shows what's in use.
    readonly property var parts: sheet.storageInfo.breakdown ? [
        ["games", i18n("Games"), "#F2552C"], ["apps", i18n("Apps"), "#5C88D0"],
        ["files", i18n("Your files"), "#357F72"], ["system", i18n("Other or unmeasured"), "#9C7BC0"]
    ] : [["occupied", i18n("Used"), "#357F72"]]
    readonly property real total: sheet.storageInfo.total || 0
    // Emptying the Trash asks once more.
    property bool askingTrash: false
    property string expandedDisk: ""
    spacing: 20
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("storage")
        art: sheet.art
        text: i18n("Storage")
        detail: i18n("What fills this PC, and room to make.")
    }
    // Physical drives and their volumes are independent of the folder-size scan.
    SettingsControls.Pill {
        objectName: "moreStorageSettings"
        tone: look
        text: i18n("More storage settings…")
        onClicked: storageDetailsDialog.open()
    }
    QQC2.Dialog {
        id: storageDetailsDialog
        objectName: "storageDetailsDialog"
        parent: QQC2.Overlay.overlay
        anchors.centerIn: parent
        title: i18n("More storage settings")
        width: Math.min(700, parent ? parent.width - 32 : 700)
        height: Math.min(650, parent ? parent.height - 48 : 650)
        modal: true
        standardButtons: QQC2.Dialog.Close
        contentItem: StorageDetails { id: storageDetails; host: sheet }
        onOpened: storageDetails.refresh()
    }
    SettingsControls.Card {
        id: disksCard
        objectName: "search-disks"
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Disks and partitions")
            detail: sheet.diskBusy ? i18n("Working on the disk…")
                : sheet.disksLoading ? i18n("Checking connected drives…")
                : sheet.diskProblem || (sheet.disks.length === 0 && sheet.disksLoaded
                    ? i18n("No drives found.") : "")
            SettingsControls.Pill {
                tone: look
                text: i18n("Refresh")
                enabledPill: !sheet.disksLoading && !sheet.diskBusy
                onClicked: {
                    sheet.diskProblem = ""
                    sheet.loadDisks()
                }
            }
        }
        Repeater {
            model: sheet.disks
            ColumnLayout {
                id: diskRow
                required property var modelData
                readonly property var drive: modelData
                readonly property bool opened: storageColumn.expandedDisk === drive.path
                Layout.fillWidth: true
                spacing: 0

                SettingsControls.SettingRow {
                    tone: look
                    title: diskRow.drive.name
                    detail: sheet.bytes(diskRow.drive.size) + " · " + diskRow.drive.path
                        + (diskRow.drive.system ? " · " + i18n("System drive")
                        : diskRow.drive.locked ? " · " + i18n("Read-only or in use")
                        : diskRow.drive.removable ? " · " + i18n("Removable drive") : "")
                    SettingsControls.Pill {
                        objectName: "diskDetails-" + diskRow.drive.path
                        tone: look
                        text: diskRow.opened ? i18n("Hide details") : i18n("Show details")
                        onClicked: storageColumn.expandedDisk = diskRow.opened ? "" : diskRow.drive.path
                    }
                }
                ColumnLayout {
                    visible: diskRow.opened
                    Layout.fillWidth: true
                    Layout.leftMargin: 16
                    Layout.rightMargin: 16
                    spacing: 0
                    Repeater {
                        model: diskRow.drive.table ? diskRow.drive.partitions
                            : diskRow.drive.format ? [diskRow.drive] : []
                        SettingsControls.SettingRow {
                            id: volumeRow
                            required property var modelData
                            tone: look
                            strong: false
                            title: modelData.name || i18n("Unnamed volume")
                            detail: sheet.bytes(modelData.size) + " · " + modelData.path
                                + (modelData.format ? " · " + modelData.format : "")
                                + (modelData.mounts.length > 0 ? "\n" + modelData.mounts.join(", ") : "")
                            SettingsControls.Pill {
                                objectName: "diskVolume-" + volumeRow.modelData.path
                                tone: look
                                visible: !diskRow.drive.locked && !volumeRow.modelData.busy
                                    && !volumeRow.modelData.readonly && !volumeRow.modelData.container
                                enabledPill: !sheet.diskBusy && !sheet.disksLoading
                                text: volumeRow.modelData.mounts.length ? i18n("Unmount…") : i18n("Volume actions…")
                                onClicked: {
                                    const volume = volumeRow.modelData
                                    if (volume.mounts.length)
                                        diskChange.review("unmount", diskRow.drive, volume)
                                    else
                                        diskChange.review("format", diskRow.drive, volume)
                                }
                            }
                        }
                    }
                    Repeater {
                        model: diskRow.drive.gaps
                        SettingsControls.SettingRow {
                            id: freeRow
                            required property var modelData
                            tone: look
                            strong: false
                            title: i18n("Unallocated space")
                            detail: sheet.bytes(modelData.size) + " · " + i18n("Starts at %1", sheet.bytes(modelData.offset))
                            SettingsControls.Pill {
                                objectName: "diskCreate-" + diskRow.drive.path + "-" + freeRow.modelData.offset
                                tone: look
                                visible: !diskRow.drive.locked
                                enabledPill: !sheet.diskBusy && !sheet.disksLoading
                                text: i18n("Create partition…")
                                onClicked: diskChange.review("create", diskRow.drive, freeRow.modelData)
                            }
                        }
                    }
                    SettingsControls.SettingRow {
                        tone: look
                        visible: !diskRow.drive.locked
                        title: i18n("Partition table")
                        detail: diskRow.drive.table ? diskRow.drive.table.toUpperCase() : i18n("No partition table")
                        SettingsControls.Pill {
                            objectName: "diskErase-" + diskRow.drive.path
                            tone: look
                            enabledPill: !sheet.diskBusy && !sheet.disksLoading
                            text: diskRow.drive.table || diskRow.drive.format ? i18n("Erase disk…") : i18n("Initialize disk…")
                            onClicked: diskChange.review("erase", diskRow.drive, null)
                        }
                    }
                }
            }
        }
    }
    QQC2.Dialog {
        id: diskChange
        objectName: "diskChangeDialog"
        parent: QQC2.Overlay.overlay
        anchors.centerIn: parent
        width: Math.min(470, parent ? parent.width - 32 : 470)
        modal: true
        standardButtons: QQC2.Dialog.Ok | QQC2.Dialog.Cancel
        property string action: ""
        property var drive: ({})
        property var target: ({})
        onOpened: standardButton(QQC2.Dialog.Ok).text = Qt.binding(() => action === "erase"
            ? i18n("Create GPT") : action === "create" ? i18n("Create")
            : action === "unmount" ? i18n("Unmount") : action === "delete" ? i18n("Delete") : i18n("Format"))
        function review(operation, drive, target) {
            action = operation
            this.drive = drive
            this.target = target || ({})
            fileSystem.currentIndex = 0
            volumeName.text = ""
            sizeMiB.value = operation === "create" ? sizeMiB.to : 1
            open()
        }
        title: action === "erase" ? i18n("Create a new GPT partition table")
            : action === "create" ? i18n("Create partition")
            : action === "unmount" ? i18n("Unmount volume")
            : action === "delete" ? i18n("Delete partition") : i18n("Format volume")
        onAccepted: sheet.changeDisk(action, drive,
            action === "create" ? target.offset : target.path ? sheet.hex(target.path) : "-",
            fileSystem.currentValue || "-", sizeMiB.value, volumeName.text)
        contentItem: ColumnLayout {
            spacing: 12
            QQC2.Label {
                Layout.fillWidth: true
                text: (diskChange.drive.name || "") + " · " + (diskChange.target.path || diskChange.drive.path || "")
                textFormat: Text.PlainText
                wrapMode: Text.Wrap
            }
            QQC2.Label {
                Layout.fillWidth: true
                text: diskChange.action === "erase" ? i18n("This removes every partition and its files from the selected drive.")
                    : diskChange.action === "delete" || diskChange.action === "format"
                        ? i18n("This deletes all files on the selected volume.")
                    : diskChange.action === "unmount" ? i18n("Close any files on this volume before unmounting it.") : ""
                visible: text !== ""
                wrapMode: Text.Wrap
            }
            QQC2.ComboBox {
                visible: diskChange.action === "format" && !!diskChange.drive.table || diskChange.action === "delete"
                Accessible.name: i18n("Volume action")
                Layout.fillWidth: true
                model: [i18n("Format volume"), i18n("Delete partition")]
                onActivated: index => diskChange.action = index === 0 ? "format" : "delete"
                currentIndex: diskChange.action === "delete" ? 1 : 0
            }
            QQC2.ComboBox {
                id: fileSystem
                Layout.fillWidth: true
                visible: diskChange.action === "format" || diskChange.action === "create"
                Accessible.name: i18n("File system")
                textRole: "name"
                valueRole: "id"
                model: [{name: i18n("Ext4 · Monet"), id: "ext4"},
                        {name: i18n("NTFS · Windows"), id: "ntfs"},
                        {name: i18n("exFAT · Shared storage"), id: "exfat"},
                        {name: "FAT32", id: "vfat"}]
            }
            QQC2.TextField {
                id: volumeName
                Layout.fillWidth: true
                visible: fileSystem.visible
                maximumLength: 32
                placeholderText: i18n("Volume name (optional)")
            }
            RowLayout {
                visible: diskChange.action === "create"
                Layout.fillWidth: true
                QQC2.Label {
                    Layout.fillWidth: true
                    text: i18n("Size in MiB")
                    wrapMode: Text.Wrap
                }
                QQC2.SpinBox {
                    id: sizeMiB
                    editable: true
                    from: 1
                    to: Math.max(1, Math.min(2147483647, Math.floor((diskChange.target.size || 0) / 1048576)))
                }
            }
            QQC2.Label {
                Layout.fillWidth: true
                visible: diskChange.action === "create"
                text: i18n("%1 selected · %2 available",
                           sheet.bytes(sizeMiB.value * 1048576), sheet.bytes(diskChange.target.size))
                wrapMode: Text.Wrap
            }
        }
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            objectName: "search-shared-files"
            tone: look
            divider: false
            title: i18n("Windows files")
            detail: sheet.windowsFiles.available
                ? i18n("The shared folder opens in Files. In Windows, it is called Shared with Monet.")
                : sheet.windowsFiles.state === "asleep"
                    ? i18n("Shut down Windows completely, then return to Monet to use the shared folder.")
                : sheet.windowsFiles.state === "bitlocker"
                    ? i18n("Windows' drive is locked. Open its access settings to unlock it.")
                : sheet.windowsFiles.state === "unclean"
                    ? i18n("Windows' drive needs checking. Start Windows and shut it down fully before trying again.")
                : sheet.windowsFiles.state === "open"
                    ? i18n("The shared folder isn't available to this account.")
                : sheet.windowsFiles.state === "no-bridge"
                    ? i18n("Start Windows once to finish setting up the shared folder.")
                : i18n("Shared files become available after Windows is set up on this PC.")
            SettingsControls.Pill {
                tone: look
                text: sheet.windowsFiles.available ? i18n("Open folder") : i18n("Windows settings")
                onClicked: {
                    if (sheet.windowsFiles.available)
                        Qt.openUrlExternally("file://" + encodeURI(sheet.windowsFiles.path))
                    else sheet.open(sheet.windowsFiles.state === "bitlocker" ? "games#shared" : "windows")
                }
            }
        }
    }
    SettingsControls.Card {
        tone: look
        ColumnLayout {
            Layout.fillWidth: true
            Layout.margins: 20
            spacing: 12
            RowLayout {
                Layout.fillWidth: true
                spacing: 10
                Text {
                    horizontalAlignment: Text.AlignLeft
                    text: storageColumn.total > 0 ? i18n("%1 free", sheet.bytes(sheet.storageInfo.free))
                        : sheet.storageLoaded ? i18n("Free space couldn't be read.") : i18n("Measuring…")
                    color: look.ink
                    font.family: "Fraunces 72pt SuperSoft"
                    font.weight: Font.Light
                    font.pixelSize: 32
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignBaseline
                    visible: storageColumn.total > 0
                    text: i18n("of %1", sheet.bytes(storageColumn.total))
                    color: look.dim
                    font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
                }
            }
            // The disk as one bar: each part its share, free space left plain.
            SettingsControls.Rounded {
                Layout.fillWidth: true
                Layout.preferredHeight: 14
                radius: 7
                Rectangle {
                    anchors.fill: parent
                    color: look.wash2
                }
                Row {
                    anchors.fill: parent
                    Repeater {
                        model: storageColumn.parts
                        Rectangle {
                            required property var modelData
                            width: parent.width * (sheet.storageInfo[modelData[0]] || 0) / Math.max(1, storageColumn.total)
                            height: parent.height
                            color: modelData[2]
                            Behavior on width { NumberAnimation { duration: Math.round(400 * sheet.speed); easing.type: Easing.OutCubic } }
                        }
                    }
                }
            }
            Flow {
                Layout.fillWidth: true
                spacing: 18
                visible: storageColumn.total > 0
                Repeater {
                    model: storageColumn.parts
                    Row {
                        required property var modelData
                        spacing: 7
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: 10
                            height: 10
                            radius: 5
                            color: parent.modelData[2]
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            text: parent.modelData[1] + "  " + sheet.bytes(sheet.storageInfo[parent.modelData[0]])
                            color: look.dim
                            font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                        }
                    }
                }
            }
            RowLayout {
                Layout.fillWidth: true
                Text {
                    Layout.fillWidth: true
                    text: sheet.storageProblem || (sheet.storageBusy ? i18n("Measuring folder sizes…")
                        : sheet.storageInfo.overcounted ? i18n("Some files are shared between folders, so the folders add up to more than the space in use. The bar shows only what is in use.")
                        : sheet.storageInfo.limited || sheet.storageInfo.unreadable ? i18n("Partial measurement. Some folders could not be measured within this scan. Other or unmeasured space includes them.")
                        : i18n("Folder sizes are measured only when you ask, to keep disk activity low."))
                    color: look.dim
                    font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                    wrapMode: Text.Wrap
                }
                SettingsControls.Pill {
                    objectName: "measureStorageButton"
                    tone: look
                    text: sheet.storageBusy ? i18n("Measuring…") : i18n("Measure folder sizes")
                    enabled: !sheet.storageBusy
                    onClicked: sheet.measureStorage()
                }
            }
        }
    }
    SettingsControls.Caption { tone: look; text: i18n("Unfinished installations") }
    SettingsControls.Card {
        tone: look
        ColumnLayout {
            Layout.fillWidth: true; Layout.margins: 20; spacing: 12
            SettingsControls.MaintenanceText { tone: look; text: i18n("Setup keeps an unfinished installation when you retry. Review its files before making room. Your current system and its rollback are protected.") }
            SettingsControls.Pill {
                tone: look; objectName: "scanRetained"
                text: sheet.retainedBusy ? i18n("Working…") : i18n("Find saved installations")
                enabledPill: !sheet.retainedBusy
                onClicked: sheet.recoverStorage("list", null)
            }
            SettingsControls.MaintenanceText { tone: look;
                objectName: "retainedStatus"
                text: sheet.retainedMessage || (sheet.retainedLoaded && sheet.retained.length === 0 ? i18n("No unfinished installations found.") : i18n("This check requires administrator permission. Nothing is removed automatically."))
            }
            SettingsControls.Pill {
                tone: look; visible: sheet.retainedArchive !== ""; text: i18n("Open recovered archive")
                onClicked: Qt.openUrlExternally("file://" + encodeURI(sheet.retainedArchive))
            }
        }
    }
    Repeater {
        model: sheet.retained
        SettingsControls.Card {
            id: savedInstall
            required property var modelData
            tone: look
            ColumnLayout {
                Layout.fillWidth: true; Layout.margins: 20; spacing: 12
                SettingsControls.MaintenanceText { tone: look; font.bold: true; text: i18n("Saved installation · %1", new Date(savedInstall.modelData.time).toLocaleString(Qt.locale(), Locale.ShortFormat)) }
                SettingsControls.MaintenanceText { tone: look; text: savedInstall.modelData.id }
                SettingsControls.Pill {
                    tone: look; objectName: "reviewRetained-" + savedInstall.modelData.id
                    text: i18n("Review files and cleanup"); enabledPill: !sheet.retainedBusy
                    onClicked: sheet.recoverStorage("review", savedInstall.modelData)
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 12
                    visible: sheet.retainedReview !== null && sheet.retainedReview.id === savedInstall.modelData.id
                    onVisibleChanged: if (visible) Qt.callLater(() => cancelRetained.forceActiveFocus())
                    SettingsControls.MaintenanceText { tone: look;
                        text: sheet.retainedReview && sheet.retainedReview.bytes !== null
                            ? i18n("Referenced data: %1. Shared data means the space freed may be smaller.", sheet.bytes(sheet.retainedReview.bytes))
                            : i18n("Size is unavailable. No data has been removed.")
                    }
                    SettingsControls.MaintenanceText { tone: look; text: i18n("Save your account's files as an archive first. Choose another drive if this disk is low on space. Other accounts' files are not exported. Removing this installation permanently removes all accounts' files inside it, including any saved boot files.") }
                    SettingsControls.Pill {
                        tone: look; text: i18n("Save my files…"); objectName: "exportRetained"
                        enabledPill: !sheet.retainedBusy && sheet.retainedReview !== null && sheet.retainedReview.homes === 1
                        onClicked: { sheet.retainedExport = sheet.retainedReview; recoveryFolder.open() }
                    }
                    SettingsControls.MaintenanceText { tone: look;
                        visible: sheet.retainedReview !== null && sheet.retainedReview.homes !== 1
                        text: i18n("A unique home folder for this account was not found. Keep this installation if it may contain files you need.")
                    }
                    QQC2.CheckBox {
                        id: recoveryConsent
                        objectName: "consentRetained"; Layout.fillWidth: true
                        text: i18n("I have checked and saved everything I need.")
                        checked: sheet.retainedConsent; enabled: !sheet.retainedBusy
                        onToggled: sheet.retainedConsent = checked
                        font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                        indicator: Rectangle {
                            width: 24; height: 24; radius: 6
                            x: recoveryConsent.leftPadding; y: (recoveryConsent.height - height) / 2
                            color: recoveryConsent.checked ? look.lily : look.wash
                            border.color: recoveryConsent.activeFocus ? look.lily : look.dim
                            border.width: recoveryConsent.activeFocus ? 2 : 1
                            Text {
                                anchors.centerIn: parent; text: "✓"; visible: recoveryConsent.checked
                                color: look.dark ? "#1C1B19" : "#FFFFFF"; font.pixelSize: 18
                            }
                        }
                        contentItem: Text {
                            text: recoveryConsent.text; font: recoveryConsent.font; color: look.ink
                            wrapMode: Text.Wrap; leftPadding: recoveryConsent.indicator.width + recoveryConsent.spacing
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                    Flow {
                        Layout.fillWidth: true; spacing: 8
                        SettingsControls.Pill { id: cancelRetained; tone: look; text: i18n("Cancel"); enabledPill: !sheet.retainedBusy; onClicked: sheet.retainedReview = null }
                        SettingsControls.Pill {
                            tone: look; objectName: "deleteRetained"; text: i18n("Permanently remove this installation")
                            enabledPill: !sheet.retainedBusy && sheet.retainedConsent
                            onClicked: sheet.recoverStorage("delete", sheet.retainedReview)
                        }
                    }
                }
            }
        }
    }
    SettingsControls.Caption {
        tone: look
        text: i18n("Make room")
    }
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Trash")
            detail: storageColumn.askingTrash ? i18n("Everything in it is gone for good. Sure?")
                : !sheet.storageInfo.measured || sheet.storageInfo.trash === null ? i18n("Not measured")
                : (sheet.storageInfo.trash || 0) > 0 ? sheet.bytes(sheet.storageInfo.trash) : i18n("Empty")
            Row {
                spacing: 8
                SettingsControls.Pill {
                    tone: look
                    visible: storageColumn.askingTrash
                    text: i18n("Keep it")
                    onClicked: storageColumn.askingTrash = false
                }
                SettingsControls.Pill {
                    tone: look
                    visible: (sheet.storageInfo.trash || 0) > 0
                    text: storageColumn.askingTrash ? i18n("Empty for good") : i18n("Empty Trash")
                    objectName: "emptyTrash"
                    onClicked: {
                        if (storageColumn.askingTrash) {
                            storageColumn.askingTrash = false
                            sheet.emptyTrash()
                        } else {
                            storageColumn.askingTrash = true
                        }
                    }
                }
            }
        }
        SettingsControls.SettingRow {
            tone: look
            objectName: "search-downloads"
            title: i18n("Downloads")
            detail: sheet.storageInfo.downloadsPath || i18n("Desktop")
            SettingsControls.Pill {
                tone: look
                visible: (sheet.storageInfo.downloadsPath || "") !== ""
                text: i18n("Show")
                onClicked: Qt.openUrlExternally("file://" + encodeURI(sheet.storageInfo.downloadsPath))
            }
        }
    }
    Text {
        horizontalAlignment: Text.AlignLeft
        Layout.fillWidth: true
        text: i18n("What apps leave behind when they update is cleared away with each update, by itself.")
        color: look.dim
        font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
        lineHeight: 1.3
        wrapMode: Text.Wrap
    }
    // OneDrive in Files (monet-quick onedrive-connect: rclone, signed in once in the browser).
    SettingsControls.Caption {
        tone: look
        visible: oneDriveCard.visible
        text: i18n("In the cloud")
    }
    SettingsControls.Card {
        id: oneDriveCard
        tone: look
        readonly property var o: sheet.oneDrive
        visible: o.here === true
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: "OneDrive"
            detail: sheet.oneDriveBusy === "connect" ? i18n("Sign in with Microsoft in the browser that opened. Settings carries on once you're in.")
                : oneDriveCard.o.connected && oneDriveCard.o.total
                    ? i18n("In Files, with your places: %1 of %2 used. Files come down as you open them.", sheet.bytes(oneDriveCard.o.used || 0), sheet.bytes(oneDriveCard.o.total))
                : oneDriveCard.o.connected ? i18n("In Files, with your places. Files come down as you open them.")
                : sheet.oneDriveProblem ? i18n("OneDrive wasn't connected. Try again, and sign in with Microsoft in the browser.")
                : i18n("Your OneDrive in Files, with your places, its files coming down as you open them. Sign in with Microsoft once, in the browser.")
            Row {
                spacing: 8
                SettingsControls.Pill {
                    tone: look
                    visible: oneDriveCard.o.connected === true
                    text: i18n("Show")
                    onClicked: Qt.openUrlExternally("file://" + encodeURI(oneDriveCard.o.path))
                }
                SettingsControls.Pill {
                    tone: look
                    kind: oneDriveCard.o.connected ? "plain" : "lily"
                    enabledPill: sheet.oneDriveBusy === ""
                    text: sheet.oneDriveBusy === "connect" ? i18n("Signing in…")
                        : sheet.oneDriveBusy === "disconnect" ? i18n("Disconnecting…")
                        : oneDriveCard.o.connected ? i18n("Disconnect") : i18n("Connect")
                    onClicked: {
                        const what = oneDriveCard.o.connected ? "disconnect" : "connect"
                        sheet.oneDriveBusy = what
                        sheet.oneDriveProblem = false
                        sheet.ask("onedrive-" + what, out => {
                            const done = sheet.json(out, { ok: false })
                            sheet.oneDriveBusy = ""
                            sheet.oneDriveProblem = what === "connect" && !done.ok && !sheet.oneDriveCancelled
                            sheet.oneDriveCancelled = false
                            sheet.oneDrive = done
                        })
                    }
                }
                // The browser's sign-in can wait a long time: Cancel stops it.
                SettingsControls.Pill {
                    tone: look
                    visible: sheet.oneDriveBusy === "connect"
                    text: i18n("Cancel")
                    onClicked: {
                        sheet.oneDriveCancelled = true
                        sheet.ask("onedrive-cancel", () => {})
                    }
                }
            }
        }
    }
}
