import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5

ColumnLayout {
    id: page
    spacing: 7
    property bool embedded: false
    required property Item editorParent
    required property date day
    signal choose(date date)
    signal monthRequested()
    signal calendarsRequested()
    signal upcomingRequested()
    readonly property bool editingEvent: edit.visible
    function closeEditor() { if (!writeRequest) edit.close() }
    onEnabledChanged: if (!enabled) edit.close()
    readonly property string reader: "/usr/bin/nice -n 10 /usr/bin/python3 '@DATADIR@/monet/utilities/agenda.py' "
    readonly property string dateKey: Qt.formatDate(day, "yyyy-MM-dd")
    readonly property string query: reader + (embedded ? "day " : "list ") + dateKey
    property string writeRequest: ""
    property string pending: ""
    property bool readAgain: false
    property bool syncing: false
    property bool canSync: true
    property var calendarState: null
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
    onDateKeyChanged: if (ready) { calendarState = null; dayChange.restart() }
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
                try { page.calendarState = JSON.parse(data.stdout) }
                catch (_) { page.calendarState = {error: true} }
                if (page.calendarState.needsSync && page.canSync) page.sync(false)
            }
        }
    }
    FocusScope {
        id: edit
        objectName: "notchEventEditor"
        parent: page.editorParent
        anchors.fill: parent; anchors.margins: 9
        visible: false; z: 100; clip: true
        Keys.onEscapePressed: event => { page.closeEditor(); event.accepted = true }
        function close() { visible = false; if (page.enabled) (page.embedded ? embeddedAdd : newEvent).forceActiveFocus() }
        Rectangle { anchors.fill: parent; radius: 16; color: "#19191d" }
        MouseArea { anchors.fill: parent; onWheel: wheel => wheel.accepted = true }
        property string ident: ""
        property string eventDay: ""
        property string problem: ""
        function show(event) {
            if (page.writeRequest) return
            ident = event?.localId || ""
            eventDay = event ? event.start.slice(0,10) : page.dateKey
            titleBox.text = event?.title || ""
            clock.text = event && !event.allDay ? event.start.slice(11,16) : ""
            problem = ""
            visible = true
            titleBox.forceActiveFocus()
        }
        function submit(remove) {
            if (page.writeRequest) return
            const value = {"id": ident, day: eventDay, title: titleBox.text.trim(), time: clock.text.trim()}
            const bytes = unescape(encodeURIComponent(JSON.stringify(value)))
            const hex = Array.from(bytes, c => c.charCodeAt(0).toString(16).padStart(2,"0")).join("")
            page.writeRequest = page.reader + (remove ? "remove-event " : "save-event ") + hex
            commands.connectSource(page.writeRequest)
        }
        TimeScrollView {
            id: form
            anchors.fill: parent; anchors.margins: 12
            ColumnLayout {
                width: form.availableWidth
                C.Label { font.pixelSize: 12; text: edit.ident ? i18n("Edit event") : i18n("New event"); font.bold: true }
                spacing: 6
                C.Label { font.pixelSize: 12; text: edit.eventDay ? Qt.formatDate(new Date(edit.eventDay + "T12:00:00"), Qt.locale().dateFormat(Locale.LongFormat)) : ""; visible: !!edit.eventDay }
                IslandTextField { id: titleBox; Layout.fillWidth: true; maximumLength: 256; Accessible.name: i18n("Event title"); placeholderText: Accessible.name }
                IslandTextField {
                    id: clock; Layout.fillWidth: true; maximumLength: 5
                    Accessible.name: i18n("Time"); placeholderText: i18n("HH:MM, or leave blank for all day")
                    validator: RegularExpressionValidator { regularExpression: /(?:[01][0-9]|2[0-3]):[0-5][0-9]/ }
                    onAccepted: if (save.enabled) edit.submit(false)
                }
                C.Label { visible: !!edit.problem; text: edit.problem; Layout.fillWidth: true; wrapMode: Text.Wrap }
                RowLayout {
                    Layout.fillWidth: true; enabled: !page.writeRequest
                    IslandButton { caption: true; visible: !!edit.ident; text: i18n("Delete"); onClicked: edit.submit(true) }
                    Item { Layout.fillWidth: true }
                    IslandButton { caption: true; text: i18n("Cancel"); onClicked: edit.close() }
                    IslandButton { caption: true;
                        id: save; prominent: true; text: i18n("Save")
                        enabled: !!titleBox.text.trim() && (!clock.text.trim() || clock.acceptableInput)
                        onClicked: edit.submit(false)
                    }
                }
            }
        }
    }
    RowLayout {
        visible: !page.embedded
        Layout.fillWidth: true
        IslandButton { plain: true; icon.name: "go-previous"; text: i18n("Month"); onClicked: page.monthRequested() }
        Item { Layout.fillWidth: true }
        IslandButton {
            plain: true; text: i18n("Link a calendar…"); icon.name: "view-calendar"; onClicked: page.calendarsRequested()
        }
        IslandButton {
            plain: true; icon.name: "view-refresh"; text: i18n("Refresh events")
            enabled: !page.syncing && !page.pending
            onClicked: page.sync(true)
        }
    }
    RowLayout {
        visible: !page.embedded
        Layout.fillWidth: true
        IslandButton { plain: true; icon.name: "go-previous"; text: i18n("Previous two weeks"); onClicked: page.choose(page.shifted(-14)) }
        IslandButton {
            caption: true; Layout.fillWidth: true; Layout.minimumWidth: 0
            text: Qt.locale().toString(page.day, "d MMM") + " – " + Qt.locale().toString(page.shifted(13), "d MMM yyyy")
            Accessible.description: i18n("Return to today")
            onClicked: page.choose(new Date())
        }
        IslandButton { plain: true; icon.name: "go-next"; text: i18n("Next two weeks"); onClicked: page.choose(page.shifted(14)) }
    }
    IslandButton {
        id: newEvent; visible: !page.embedded; caption: true; text: i18n("New event"); Layout.alignment: Qt.AlignHCenter
        onClicked: edit.show(null)
    }
    RowLayout {
        visible: page.embedded; Layout.fillWidth: true
        Text { Layout.fillWidth: true; text: Qt.locale().toString(page.day,"ddd d MMM")
            font.weight: Font.DemiBold; font.pixelSize: 12; color: "#ededf2"; elide: Text.ElideRight }
        IslandButton { id: embeddedAdd; plain: true; icon.name: "plus"; text: i18n("New event"); onClicked: edit.show(null) }
    }
    ListView {
        id: events
        objectName: "notchAppointments"
        Layout.fillWidth: true; Layout.fillHeight: true; clip: true
        spacing: 6; boundsBehavior: Flickable.StopAtBounds
        model: page.calendarState?.events || []
        C.ScrollBar.vertical: C.ScrollBar {}
        delegate: Rectangle {
            id: eventRow
            required property var modelData
            readonly property date start: new Date(modelData.start)
            readonly property date end: new Date(modelData.end)
            width: events.width
            height: eventContent.implicitHeight + 18
            radius: 11; color: "#19191e"
            Rectangle { x: 0; y: 10; width: 3; height: parent.height - 20; radius: 1.5; color: "#ff8797" }
            ColumnLayout {
                id: eventContent
                x: 12; y: 9; width: parent.width - 24; spacing: 4
                RowLayout {
                    Layout.fillWidth: true
                    C.Label { Layout.fillWidth: true; elide: Text.ElideRight; textFormat: Text.PlainText; text: modelData.title || i18n("Untitled event"); font.weight: Font.DemiBold; font.pixelSize: 12 }
                    IslandButton {
                        visible: !!modelData.localId; plain: true; implicitWidth: 24; implicitHeight: 24
                        icon.name: "document-edit"; text: i18n("Edit event"); onClicked: edit.show(modelData)
                    }
                }
                C.Label {
                    font.pixelSize: 11; color: "#aaaab2"; Layout.fillWidth: true; elide: Text.ElideRight
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
                    Layout.fillWidth: true; visible: !!text
                    textFormat: Text.PlainText; elide: Text.ElideRight; color: "#9696a2"; font.pixelSize: 11
                    text: [modelData.source, modelData.location].filter(Boolean).join(" · ")
                }
            }
        }
        IslandEmpty {
            anchors.fill: parent
            visible: events.count === 0
            symbol: "view-calendar"; tint: "#ff8797"
            title: !page.calendarState || page.syncing ? i18n("Loading events…")
                : page.calendarState.error ? i18n("Could not read your calendars.")
                : page.calendarState.unavailable?.length ? i18n("Some calendars could not be read.")
                : page.embedded ? i18n("No events on this day.") : i18n("No events in these two weeks.")
        }
    }
    RowLayout {
        visible: page.embedded; Layout.fillWidth: true
        IslandButton { plain: true; icon.name: "view-calendar"; text: i18n("Link a calendar…"); onClicked: page.calendarsRequested() }
        IslandButton { caption: true; Layout.fillWidth: true; Layout.minimumWidth: 0; text: i18n("Upcoming"); onClicked: page.upcomingRequested() }
    }
    C.Label {
        Layout.fillWidth: true; visible: text.length > 0; wrapMode: Text.Wrap; textFormat: Text.PlainText
        text: [page.calendarState?.unavailable?.length ? i18n("Unavailable · %1", page.calendarState.unavailable.join(", ")) : "",
            page.calendarState?.saved?.length ? i18n("Showing saved copy · %1", page.calendarState.saved.join(", ")) : "",
            page.calendarState?.truncated ? i18n("Showing the first 200 appointments.") : ""].filter(Boolean).join("\n")
        maximumLineCount: 2; elide: Text.ElideRight
    }
}
