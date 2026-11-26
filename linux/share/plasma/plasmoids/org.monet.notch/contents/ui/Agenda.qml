import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5

ColumnLayout {
    id: page
    property bool embedded: false
    required property Item editorParent
    required property date day
    signal choose(date date)
    signal monthRequested()
    signal calendarsRequested()
    readonly property string reader: "/usr/bin/nice -n 10 /usr/bin/python3 '@DATADIR@/monet/utilities/agenda.py' "
    readonly property string dateKey: Qt.formatDate(day, "yyyy-MM-dd")
    readonly property string query: reader + (embedded ? "day " : "list ") + dateKey
    property string writeRequest: ""
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
        const source = query
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
    Timer { id: dayChange; interval: 100; onTriggered: page.list() }
    onDateKeyChanged: if (ready) { state = null; dayChange.restart() }
    property bool ready: false
    Component.onCompleted: { ready = true; list() }
    P5.DataSource {
        id: commands
        engine: "executable"; connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            if (source === page.writeRequest) {
                page.writeRequest = ""
                let ok = false
                try { ok = JSON.parse(data.stdout).ok === true } catch (_) {}
                if (ok) { edit.close(); page.list() }
                else edit.problem = i18n("Could not save this change. Try again.")
            } else if (source.startsWith(page.reader + "sync")) {
                page.syncing = false
                page.list()
            } else if (source === page.pending) {
                page.pending = ""
                if (source !== page.query) return
                if (page.readAgain) { Qt.callLater(page.list); return }
                try { page.state = JSON.parse(data.stdout) }
                catch (_) { page.state = {error: true} }
                if (page.state.needsSync && page.canSync) page.sync(false)
            }
        }
    }
    C.Dialog {
        id: edit
        objectName: "notchEventEditor"
        parent: page.editorParent
        anchors.centerIn: parent
        width: Math.min(380, parent.width - 24)
        popupType: C.Popup.Item; modal: true; focus: true; dim: false
        closePolicy: page.writeRequest ? C.Popup.NoAutoClose : C.Popup.CloseOnEscape
        property string ident: ""
        property string eventDay: ""
        property string problem: ""
        title: ident ? i18n("Edit event") : i18n("New event")
        function show(event) {
            if (page.writeRequest) return
            ident = event?.localId || ""
            eventDay = event ? event.start.slice(0,10) : page.dateKey
            titleBox.text = event?.title || ""
            clock.text = event && !event.allDay ? event.start.slice(11,16) : ""
            problem = ""
            open()
            titleBox.forceActiveFocus()
        }
        function submit(remove) {
            if (page.writeRequest) return
            const value = {id: ident, day: eventDay, title: titleBox.text.trim(), time: clock.text.trim()}
            const bytes = unescape(encodeURIComponent(JSON.stringify(value)))
            const hex = Array.from(bytes, c => c.charCodeAt(0).toString(16).padStart(2,"0")).join("")
            page.writeRequest = page.reader + (remove ? "remove-event " : "save-event ") + hex
            commands.connectSource(page.writeRequest)
        }
        contentItem: ColumnLayout {
            spacing: 6
            C.Label { text: edit.eventDay ? Qt.formatDate(new Date(edit.eventDay + "T12:00:00"), Qt.locale().dateFormat(Locale.LongFormat)) : ""; visible: !!edit.eventDay }
            C.TextField { id: titleBox; Layout.fillWidth: true; maximumLength: 256; Accessible.name: i18n("Event title"); placeholderText: Accessible.name }
            C.TextField {
                id: clock; Layout.fillWidth: true; maximumLength: 5
                Accessible.name: i18n("Time"); placeholderText: i18n("HH:MM, or leave blank for all day")
                validator: RegularExpressionValidator { regularExpression: /(?:[01][0-9]|2[0-3]):[0-5][0-9]/ }
                onAccepted: if (save.enabled) edit.submit(false)
            }
            C.Label { visible: !!edit.problem; text: edit.problem; Layout.fillWidth: true; wrapMode: Text.Wrap }
            RowLayout {
                Layout.fillWidth: true; enabled: !page.writeRequest
                C.Button { visible: !!edit.ident; text: i18n("Delete"); onClicked: edit.submit(true) }
                Item { Layout.fillWidth: true }
                C.Button { text: i18n("Cancel"); onClicked: edit.close() }
                C.Button {
                    id: save; text: i18n("Save")
                    enabled: !!titleBox.text.trim() && (!clock.text.trim() || clock.acceptableInput)
                    onClicked: edit.submit(false)
                }
            }
        }
    }
    RowLayout {
        visible: !page.embedded
        Layout.fillWidth: true
        C.ToolButton { icon.name: "go-previous"; text: i18n("Month"); onClicked: page.monthRequested() }
        Item { Layout.fillWidth: true }
        C.ToolButton {
            text: i18n("Link a calendar…"); icon.name: "view-calendar"; onClicked: page.calendarsRequested()
        }
        C.ToolButton {
            icon.name: "view-refresh"; Accessible.name: i18n("Refresh events")
            enabled: !page.syncing && !page.pending
            onClicked: page.sync(true)
        }
    }
    RowLayout {
        visible: !page.embedded
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
    IslandButton {
        caption: true; text: i18n("New event"); Layout.alignment: Qt.AlignLeft
        onClicked: edit.show(null)
    }
    C.Label {
        visible: page.embedded; Layout.fillWidth: true
        text: Qt.locale().toString(page.day, "ddd d MMM")
        font.weight: Font.DemiBold; font.pixelSize: 13; elide: Text.ElideRight
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
            RowLayout {
                Layout.fillWidth: true
                C.Label { Layout.fillWidth: true; elide: Text.ElideRight; textFormat: Text.PlainText; text: modelData.title || i18n("Untitled event"); font.bold: true }
                IslandButton {
                    visible: !!modelData.localId; plain: true; implicitWidth: 24; implicitHeight: 24
                    icon.name: "document-edit"; text: i18n("Edit event"); onClicked: edit.show(modelData)
                }
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
            text: !page.state || page.syncing ? i18n("Loading events…")
                : page.state.error ? i18n("Could not read your calendars.")
                : page.state.unavailable?.length ? i18n("Some calendars could not be read.")
                : page.embedded ? i18n("No events on this day.") : i18n("No events in these two weeks.")
        }
    }
    IslandButton {
        visible: page.embedded
        Layout.alignment: Qt.AlignHCenter; caption: true
        text: i18n("Link a calendar…"); onClicked: page.calendarsRequested()
    }
    C.Label {
        Layout.fillWidth: true; visible: text.length > 0; wrapMode: Text.Wrap; textFormat: Text.PlainText
        text: [page.state?.unavailable?.length ? i18n("Unavailable · %1", page.state.unavailable.join(", ")) : "",
            page.state?.saved?.length ? i18n("Showing saved copy · %1", page.state.saved.join(", ")) : "",
            page.state?.truncated ? i18n("Showing the first 200 appointments.") : ""].filter(Boolean).join("\n")
        maximumLineCount: 2; elide: Text.ElideRight
    }
}
