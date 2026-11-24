import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5

ColumnLayout {
    id: page
    required property date day
    signal choose(date date)
    signal monthRequested()
    signal calendarsRequested()
    readonly property string reader: "/usr/bin/nice -n 10 /usr/bin/python3 '@DATADIR@/monet/utilities/agenda.py' "
    readonly property string dateKey: Qt.formatDate(day, "yyyy-MM-dd")
    property string pending: ""
    property bool readAgain: false
    property bool syncing: false
    property bool canSync: true
    property var state: null
    function shifted(days) {
        return new Date(day.getFullYear(), day.getMonth(), day.getDate() + days)
    }
    function list() {
        if (!/^\d{4}-\d{2}-\d{2}$/.test(dateKey)) return
        const source = reader + "list " + dateKey
        if (pending === source) { readAgain = true; return }
        readAgain = false
        pending = source
        commands.connectSource(pending)
    }
    function sync(force) {
        if (syncing) return
        syncing = true
        canSync = false
        commands.connectSource(reader + (force ? "sync force" : "sync"))
    }
    onDateKeyChanged: if (ready) { state = null; list() }
    property bool ready: false
    Component.onCompleted: { ready = true; list() }
    P5.DataSource {
        id: commands
        engine: "executable"; connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            if (source.startsWith(page.reader + "sync")) {
                page.syncing = false
                page.list()
            } else if (source === page.pending) {
                page.pending = ""
                if (page.readAgain) { Qt.callLater(page.list); return }
                try { page.state = JSON.parse(data.stdout) }
                catch (_) { page.state = {error: true} }
                if (page.state.needsSync && page.canSync) page.sync(false)
            }
        }
    }
    RowLayout {
        Layout.fillWidth: true
        C.ToolButton { icon.name: "go-previous"; text: i18n("Month"); onClicked: page.monthRequested() }
        Item { Layout.fillWidth: true }
        C.ToolButton {
            text: i18n("Calendars…"); icon.name: "view-calendar"; onClicked: page.calendarsRequested()
        }
        C.ToolButton {
            icon.name: "view-refresh"; Accessible.name: i18n("Refresh appointments")
            C.ToolTip.text: Accessible.name; C.ToolTip.visible: hovered
            enabled: !page.syncing && !page.pending
            onClicked: page.sync(true)
        }
    }
    RowLayout {
        Layout.fillWidth: true
        C.ToolButton { icon.name: "go-previous"; Accessible.name: i18n("Previous two weeks"); onClicked: page.choose(page.shifted(-14)) }
        C.Button {
            Layout.fillWidth: true
            text: Qt.locale().toString(page.day, "d MMM") + " – " + Qt.locale().toString(page.shifted(13), "d MMM yyyy")
            Accessible.description: i18n("Return to today")
            onClicked: page.choose(new Date())
        }
        C.ToolButton { icon.name: "go-next"; Accessible.name: i18n("Next two weeks"); onClicked: page.choose(page.shifted(14)) }
    }
    ListView {
        id: events
        objectName: "notchAppointments"
        Layout.fillWidth: true; Layout.fillHeight: true; clip: true
        model: page.state?.events || []
        C.ScrollBar.vertical: C.ScrollBar {}
        delegate: ColumnLayout {
            required property var modelData
            readonly property date start: new Date(modelData.start)
            readonly property date end: new Date(modelData.end)
            width: events.width - Kirigami.Units.smallSpacing * 2
            spacing: 0
            C.Label {
                Layout.fillWidth: true; elide: Text.ElideRight; textFormat: Text.PlainText
                text: modelData.title || i18n("Untitled appointment"); font.bold: true
            }
            C.Label {
                Layout.fillWidth: true; elide: Text.ElideRight
                text: {
                    const date = Qt.locale().toString(start, "ddd d MMM")
                    if (modelData.allDay) {
                        const finalDay = new Date(end.getFullYear(), end.getMonth(), end.getDate() - 1)
                        return date + (start.toDateString() === finalDay.toDateString() ? "" : " – " + Qt.locale().toString(finalDay, "d MMM")) + " · " + i18n("All day")
                    }
                    const from = date + " · " + Qt.formatTime(start, Locale.ShortFormat)
                    if (start.getTime() === end.getTime()) return from
                    return from + " – " + (start.toDateString() === end.toDateString() ? "" : Qt.locale().toString(end, "d MMM") + " ") + Qt.formatTime(end, Locale.ShortFormat)
                }
            }
            C.Label {
                Layout.fillWidth: true; Layout.bottomMargin: Kirigami.Units.smallSpacing
                textFormat: Text.PlainText; elide: Text.ElideRight; opacity: 0.8
                text: [modelData.source, modelData.location].filter(Boolean).join(" · ")
            }
        }
        C.Label {
            anchors.centerIn: parent; width: parent.width - 12
            visible: events.count === 0
            horizontalAlignment: Text.AlignHCenter; wrapMode: Text.Wrap
            text: !page.state || page.syncing ? i18n("Loading appointments…")
                : page.state.error ? i18n("Could not read your calendars.")
                : !page.state.sources ? i18n("Add a calendar to see your appointments here.")
                : page.state.unavailable?.length ? i18n("No appointments available.")
                : i18n("No appointments in these two weeks.")
        }
    }
    C.Label {
        Layout.fillWidth: true; visible: text.length > 0; wrapMode: Text.Wrap; textFormat: Text.PlainText
        text: [page.state?.unavailable?.length ? i18n("Unavailable · %1", page.state.unavailable.join(", ")) : "",
            page.state?.saved?.length ? i18n("Showing saved copy · %1", page.state.saved.join(", ")) : "",
            page.state?.truncated ? i18n("Showing the first 200 appointments.") : ""].filter(Boolean).join("\n")
        maximumLineCount: 2; elide: Text.ElideRight
    }
}
