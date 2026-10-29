import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "../games"

Flickable {
    id: view
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
    }
    onJobsChanged: syncJobs()
    Component.onCompleted: syncJobs()
    contentHeight: content.implicitHeight + 64
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    Kirigami.WheelHandler { target: view; keyNavigationEnabled: true }
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
            model: rows
            Rectangle {
                id: card
                required property var value
                readonly property var modelData: value
                readonly property bool active: ["queued", "running", "cancelling"].includes(modelData.state)
                Layout.fillWidth: true
                implicitHeight: details.implicitHeight + 32
                radius: 16
                color: view.tone.wash
                border.width: 1
                border.color: view.tone.line
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
                    Rectangle {
                        Layout.fillWidth: true
                        implicitHeight: 4
                        visible: card.active
                        radius: 2
                        color: view.tone.wash2
                        Rectangle {
                            width: parent.width * card.modelData.progress
                            height: parent.height
                            radius: 2
                            color: view.tone.lily
                        }
                        Accessible.role: Accessible.ProgressBar
                        Accessible.name: card.modelData.name + ": " + Math.round(card.modelData.progress * 100) + "%"
                    }
                    Flow {
                        Layout.fillWidth: true
                        spacing: 10
                        Pill {
                            visible: card.modelData.state === "done" && card.modelData.action === "install"
                            text: i18n("Open")
                            kind: "lily"
                            tone: view.tone
                            Accessible.name: i18n("Open %1", card.modelData.name)
                            onClicked: view.openApp(card.modelData.id)
                        }
                        Pill {
                            objectName: "cancel-" + card.modelData.id
                            visible: card.active
                            enabled: card.modelData.state !== "cancelling"
                            text: card.modelData.state === "cancelling" ? i18n("Cancelling…") : i18n("Cancel")
                            tone: view.tone
                            Accessible.name: i18n("Cancel %1", card.modelData.name)
                            onClicked: view.action(card.modelData.id, "cancel")
                        }
                        Pill {
                            objectName: "retry-" + card.modelData.id
                            visible: ["failed", "cancelled", "interrupted"].includes(card.modelData.state)
                            text: i18n("Retry")
                            kind: "lily"
                            tone: view.tone
                            Accessible.name: i18n("Retry %1", card.modelData.name)
                            onClicked: view.action(card.modelData.id, "retry")
                        }
                        Pill {
                            visible: !card.active
                            text: i18n("Dismiss")
                            tone: view.tone
                            Accessible.name: i18n("Dismiss %1", card.modelData.name)
                            onClicked: view.action(card.modelData.id, "dismiss")
                        }
                    }
                }
            }
        }
    }
}
