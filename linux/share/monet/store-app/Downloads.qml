import QtQuick
import QtQuick.Layouts
import QtQuick.Templates as T
import "../games"

Flickable {
    id: view
    objectName: "storeDownloads"
    MouseScroll { view: view }
    property var tone
    property var store
    property var jobs: []
    property string issue: ""
    signal action(string id, string command)
    signal recheck()
    signal openApp(string id)
    // Keep delegates/focus alive as progress changes, rather than replacing every row.
    ListModel { id: rows; dynamicRoles: true }
    function syncJobs() {
        const wanted = jobs.map(job => job.id)
        // The row with the keys, if it goes (dismissed): the keys go to the one in its place.
        const holder = rowWithKeys()
        const leaving = holder && !wanted.includes(holder.key) ? holder.index : -1
        for (let i = rows.count - 1; i >= 0; --i)
            if (!wanted.includes(rows.get(i).key)) rows.remove(i)
        for (let i = 0; i < jobs.length; ++i) {
            let at = -1
            for (let j = i; j < rows.count; ++j)
                if (rows.get(j).key === jobs[i].id) { at = j; break }
            if (at < 0) rows.insert(i, { key: jobs[i].id, value: jobs[i] })
            else {
                if (at !== i) rows.move(at, i, 1)
                rows.setProperty(i, "value", jobs[i])
            }
        }
        if (leaving >= 0) Qt.callLater(giveKeys, leaving)
    }
    function rowWithKeys() {
        for (let item = view.Window.activeFocusItem; item; item = item.parent)
            for (let i = 0; i < downloadRows.count; ++i)
                if (downloadRows.itemAt(i) === item) return item
        return null
    }
    // Whether the keys are on this download's row: its buttons, or the row itself.
    function holdsKeys(id) {
        const row = rowWithKeys()
        return row !== null && row.key === id
    }
    // To the row at `index` (or the last); with none left, to Downloads in the side.
    function giveKeys(index) {
        if (!view.visible) return
        if (downloadRows.count > 0) {
            downloadRows.itemAt(Math.min(index, downloadRows.count - 1)).takeKeys()
        } else {
            const entry = view.store.sectionEntry("downloads")
            if (entry) entry.forceActiveFocus(Qt.OtherFocusReason)
        }
    }
    onJobsChanged: syncJobs()
    Component.onCompleted: syncJobs()
    contentHeight: content.implicitHeight + 64
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    ScrollInput { id: scrollInput; view: view; onScrollRequested: view.store.cancelFocusReveal(view) }
    Keys.priority: Keys.AfterItem
    Keys.onPressed: event => scrollInput.key(event)
    ColumnLayout {
        id: content
        x: 32
        y: 32
        width: view.width - 64
        spacing: 16
        Text {
            text: i18n("Downloads")
            color: view.tone.ink
            font.family: "Fraunces 72pt SuperSoft"
            font.pixelSize: 34
        }
        Text {
            Layout.fillWidth: true
            text: i18n("Downloads keep going when you close the Store. After a restart or interruption, you can retry here.")
            color: view.tone.dim
            font.pixelSize: 14
            wrapMode: Text.Wrap
        }
        Text {
            Layout.fillWidth: true
            visible: view.issue !== ""
            text: view.issue
            color: view.tone.ink
            font.pixelSize: 14
            wrapMode: Text.Wrap
        }
        Pill {
            visible: view.issue !== ""
            tone: view.tone
            text: i18n("Try again")
            onClicked: view.recheck()
        }
        Text {
            Layout.fillWidth: true
            Layout.topMargin: 24
            visible: view.jobs.length === 0 && view.issue === ""
            text: i18n("Nothing downloading. Choose an app in the Store to get started.")
            color: view.tone.dim
            wrapMode: Text.Wrap
            font.pixelSize: 15
        }
        Repeater {
            id: downloadRows
            model: rows
            Rectangle {
                id: card
                required property var value
                required property string key
                required property int index
                readonly property var modelData: value
                readonly property bool active: ["queued", "running", "cancelling"].includes(modelData.state)
                readonly property bool installing: view.store.installing(modelData)
                readonly property string words: view.store.jobWords(modelData)
                readonly property bool hasButtons: openButton.visible || cancelButton.visible || retryButton.visible || dismissButton.visible
                objectName: "download-" + key
                Layout.fillWidth: true
                implicitHeight: details.implicitHeight + 32
                radius: 16
                color: view.tone.wash
                border.width: activeFocus ? 2 : 1
                border.color: activeFocus ? view.tone.lily : view.tone.line
                // With no button (installing, cancelling), the row itself is where the keys stop.
                activeFocusOnTab: !hasButtons || activeFocus
                Accessible.role: Accessible.Grouping
                Accessible.name: modelData.name
                Accessible.description: words
                // The keys on its first button; with none, on the row.
                function takeKeys() {
                    if (!view.visible) return
                    const button = [openButton, cancelButton, retryButton, dismissButton].find(b => b.visible)
                    if (button) button.forceActiveFocus(Qt.OtherFocusReason)
                    else card.forceActiveFocus(Qt.OtherFocusReason)
                }
                // A button with the keys that goes (Cancel becomes Retry or Open) hands them on,
                // and a row with them gives them to its button when it has one again.
                onHasButtonsChanged: if (hasButtons && activeFocus) Qt.callLater(takeKeys)
                ColumnLayout {
                    id: details
                    x: 16; y: 16
                    width: parent.width - 32
                    spacing: 10
                    Text {
                        Layout.fillWidth: true
                        text: card.modelData.name
                        textFormat: Text.PlainText
                        font.pixelSize: 16
                        font.weight: Font.DemiBold
                        color: view.tone.ink
                        wrapMode: Text.Wrap
                    }
                    Text {
                        Layout.fillWidth: true
                        text: view.store.jobText(card.modelData)
                        font.pixelSize: 14
                        color: view.tone.dim
                        wrapMode: Text.Wrap
                        Accessible.role: Accessible.StaticText
                        Accessible.name: text
                    }
                    // How far it is, as a progress bar's value for a screen reader.
                    T.ProgressBar {
                        id: meter
                        objectName: "progress-" + card.modelData.id
                        Layout.fillWidth: true
                        implicitHeight: 4
                        visible: card.active
                        from: 0
                        to: 1
                        value: card.modelData.progress
                        background: Rectangle { radius: 2; color: view.tone.wash2 }
                        contentItem: Item {
                            Rectangle {
                                width: parent.width * meter.visualPosition
                                height: parent.height
                                radius: 2
                                color: view.tone.lily
                            }
                        }
                        Accessible.name: card.modelData.name
                    }
                    // Each says which app, and how it's going.
                    Flow {
                        Layout.fillWidth: true
                        spacing: 10
                        Pill {
                            id: openButton
                            objectName: "open-" + card.modelData.id
                            visible: card.modelData.state === "done" && card.modelData.action === "install"
                            text: i18n("Open")
                            kind: "lily"
                            tone: view.tone
                            Accessible.name: i18n("Open %1", card.modelData.name)
                            Accessible.description: card.words
                            onVisibleChanged: if (!visible && activeFocus) Qt.callLater(card.takeKeys)
                            onClicked: view.openApp(card.modelData.id)
                        }
                        Pill {
                            id: cancelButton
                            objectName: "cancel-" + card.modelData.id
                            // Not once it's cancelling, nor while it installs, which Cancel can't stop.
                            visible: card.active && card.modelData.state !== "cancelling" && !card.installing
                            text: i18n("Cancel")
                            tone: view.tone
                            Accessible.name: card.modelData.action === "remove" ? i18n("Cancel removing %1", card.modelData.name)
                                                                               : i18n("Cancel downloading %1", card.modelData.name)
                            Accessible.description: card.words
                            onVisibleChanged: if (!visible && activeFocus) Qt.callLater(card.takeKeys)
                            onClicked: view.action(card.modelData.id, "cancel")
                        }
                        Pill {
                            id: retryButton
                            objectName: "retry-" + card.modelData.id
                            visible: ["failed", "cancelled", "interrupted"].includes(card.modelData.state)
                            text: i18n("Retry")
                            kind: "lily"
                            tone: view.tone
                            Accessible.name: i18n("Retry %1", card.modelData.name)
                            Accessible.description: card.words
                            onVisibleChanged: if (!visible && activeFocus) Qt.callLater(card.takeKeys)
                            onClicked: view.action(card.modelData.id, "retry")
                        }
                        Pill {
                            id: dismissButton
                            objectName: "dismiss-" + card.modelData.id
                            visible: !card.active
                            text: i18n("Dismiss")
                            tone: view.tone
                            Accessible.name: i18n("Dismiss %1", card.modelData.name)
                            Accessible.description: card.words
                            onVisibleChanged: if (!visible && activeFocus) Qt.callLater(card.takeKeys)
                            onClicked: view.action(card.modelData.id, "dismiss")
                        }
                    }
                }
            }
        }
    }
}
