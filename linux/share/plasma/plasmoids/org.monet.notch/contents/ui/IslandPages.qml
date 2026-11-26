import QtQuick

Item {
    id: deck
    required property var components
    required property Component requested
    required property var reusable
    required property var privatePages
    property Component prewarm
    required property bool presented
    required property int duration
    property Component targetPage: null
    property Component anticipated: null
    property Item current: null
    property Item outgoing: null
    readonly property Item item: current?.item ?? null
    property real progress: 1
    property bool failed: false
    signal pageShown()

    // A single navigation action can change several bindings. Incubate only its final destination.
    function resolve() {
        if (!presented) return
        failed = false
        targetPage = requested
        if (!targetPage) { clear(); return }
        for (let i = 0; i < slots.count; ++i) {
            const slot = slots.itemAt(i)
            if (slot?.modelData !== targetPage) continue
            if (slot.status === Loader.Ready) display(slot)
            else if (slot.status === Loader.Error) unavailable()
        }
    }
    function clear() {
        entry.stop()
        current = null; outgoing = null; progress = 1
    }
    function unavailable() {
        clear()
        failed = true
    }
    function display(slot) {
        if (!presented || slot.modelData !== requested || current === slot) return
        const start = outgoing === slot ? 1 - progress : 0.12
        entry.stop()
        outgoing = duration > 1 && current?.visible ? current : null
        progress = outgoing ? start : 1
        current = slot
        if (outgoing) { entry.from = start; entry.start() }
        pageShown()
    }
    onRequestedChanged: Qt.callLater(resolve)
    onPresentedChanged: {
        if (presented) Qt.callLater(resolve)
        else {
            clear(); targetPage = null; anticipated = null; failed = false
        }
    }
    Component.onCompleted: Qt.callLater(resolve)
    NumberAnimation {
        id: entry
        target: deck; property: "progress"; from: 0; to: 1
        duration: Math.round((1 - from) * deck.duration); easing.type: Easing.OutCubic
        onFinished: deck.outgoing = null
    }
    Text {
        visible: deck.presented && deck.failed
        anchors.centerIn: parent; text: i18n("Unavailable"); color: "#c4c4c8"
    }
    Repeater {
        id: slots
        model: deck.components
        Loader {
            id: slot
            required property var modelData
            property bool visited: false
            readonly property bool allowed: modelData === deck.requested || !deck.privatePages.includes(modelData)
            anchors.fill: parent
            sourceComponent: modelData
            active: modelData === deck.prewarm || (deck.presented && allowed &&
                (modelData === deck.targetPage || modelData === deck.anticipated || deck.current === slot || deck.outgoing === slot || visited))
            asynchronous: true
            visible: deck.presented && allowed && status === Loader.Ready && (deck.current === slot || deck.outgoing === slot)
            enabled: deck.current === slot && modelData === deck.requested
            z: deck.current === slot ? 1 : 0
            opacity: deck.current === slot ? deck.progress : 1 - deck.progress
            transform: Translate { y: deck.current === slot ? 4 * (1 - deck.progress) : -3 * deck.progress }
            onStatusChanged: if (status === Loader.Error && deck.presented && modelData === deck.requested) deck.unavailable()
            onLoaded: {
                visited = deck.presented && deck.reusable.includes(modelData)
                deck.display(slot)
            }
            Connections {
                target: deck
                function onPresentedChanged() { if (!deck.presented) slot.visited = false }
            }
        }
    }
}
