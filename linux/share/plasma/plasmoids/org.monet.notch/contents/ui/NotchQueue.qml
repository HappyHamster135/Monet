pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: page
    required property var player
    required property string service
    required property string track
    required property var snapshot
    required property bool fresh
    required property var playback
    signal refreshRequested()
    readonly property bool shared: Array.isArray(snapshot.queue)
    readonly property bool canChoose: !!playback && fresh && snapshot.service === service && snapshot.trackId === track
        && !!snapshot.owner && !!player?.canControl && !!player?.canPlay
    readonly property bool pending: !!playback?.busy
    readonly property bool failed: !!playback?.failedOwner && playback.failedOwner === snapshot.owner
    function choose(row) {
        if (canChoose && snapshot.queue.some(item => item.id === row.id))
            playback?.choose(snapshot.owner, track, row.id, player)
    }
    Connections {
        target: page.playback
        function onFailedOwnerChanged() { if (page.failed) page.refreshRequested() }
    }

    C.Label {
        Layout.fillWidth: true
        visible: page.failed
        text: i18n("The player couldn’t play that track.")
        wrapMode: Text.Wrap
        Accessible.role: Accessible.AlertMessage
    }
    ListView {
        id: list
        objectName: "notchQueue"
        Layout.fillWidth: true; Layout.fillHeight: true
        visible: count > 0; clip: true
        activeFocusOnTab: count > 0
        keyNavigationEnabled: true
        Accessible.role: Accessible.List
        Accessible.name: i18n("Up next")
        function playCurrent(event) {
            if (currentItem?.enabled) page.choose(currentItem.modelData)
            event.accepted = true
        }
        Keys.onReturnPressed: event => playCurrent(event)
        Keys.onEnterPressed: event => playCurrent(event)
        Keys.onSpacePressed: event => playCurrent(event)
        model: page.snapshot.queue || []
        C.ScrollBar.vertical: C.ScrollBar {}
        delegate: C.ItemDelegate {
            id: row
            required property int index
            required property var modelData
            readonly property string title: modelData.title || i18n("Untitled")
            width: ListView.view.width - Kirigami.Units.largeSpacing
            enabled: page.canChoose && !page.pending
            Accessible.name: enabled ? i18n("Play %1", title) : title
            Accessible.description: modelData.artist
            highlighted: list.activeFocus && ListView.isCurrentItem
            onClicked: { list.currentIndex = index; page.choose(modelData) }
            contentItem: RowLayout {
                spacing: Kirigami.Units.smallSpacing
                Item {
                    Layout.preferredHeight: Kirigami.Units.iconSizes.medium
                    Layout.preferredWidth: Layout.preferredHeight
                    Kirigami.Icon { anchors.fill: parent; visible: cover.status !== Image.Ready; source: "audio-x-generic" }
                    Image {
                        id: cover
                        anchors.fill: parent
                        asynchronous: true; fillMode: Image.PreserveAspectCrop
                        sourceSize: Qt.size(width * Screen.devicePixelRatio, height * Screen.devicePixelRatio)
                        source: /^(file|https?):\/\//i.test(row.modelData.art) ? row.modelData.art : ""
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true; spacing: 0
                    C.Label { Layout.fillWidth: true; elide: Text.ElideRight; textFormat: Text.PlainText; text: row.title }
                    C.Label { Layout.fillWidth: true; elide: Text.ElideRight; textFormat: Text.PlainText; visible: !!text; opacity: 0.75; text: row.modelData.artist }
                }
                Item {
                    visible: !!page.player?.canControl && !!page.player?.canPlay
                    Layout.preferredHeight: Kirigami.Units.iconSizes.small
                    Layout.preferredWidth: Layout.preferredHeight
                    Kirigami.Icon { anchors.fill: parent; visible: !progress.running; source: "media-playback-start" }
                    C.BusyIndicator {
                        id: progress; anchors.fill: parent; visible: running
                        running: page.pending && page.playback.owner === page.snapshot.owner && page.playback.targetId === row.modelData.id
                    }
                }
            }
        }
    }
    ColumnLayout {
        Layout.fillWidth: true; Layout.fillHeight: true
        visible: list.count === 0
        Item { Layout.fillHeight: true }
        C.Label {
            Layout.fillWidth: true; horizontalAlignment: Text.AlignHCenter; wrapMode: Text.WordWrap
            text: !page.player ? i18n("Nothing playing") : !page.fresh ? i18n("Loading…") :
                page.shared ? i18n("Nothing else is queued.") : i18n("No upcoming tracks shared by this player.")
        }
        C.Button {
            Layout.alignment: Qt.AlignHCenter; visible: !!page.player?.canRaise
            text: i18n("Open %1", page.player?.identity || "")
            onClicked: page.player?.Raise()
        }
        Item { Layout.fillHeight: true }
    }
}
