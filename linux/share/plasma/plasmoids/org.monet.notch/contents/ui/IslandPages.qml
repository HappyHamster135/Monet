import QtQuick

Item {
    id: deck
    clip: true
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
    property int endpoint: 0
    property real position: 0
    readonly property real progress: outgoing ? Math.max(0, Math.min(1, endpoint ? position : 1 - position)) : 1
    Behavior on position {
        enabled: !!deck.outgoing && deck.duration > 1
        IslandSlide { duration: deck.duration }
    }
    onPositionChanged: if (outgoing && position === endpoint) Qt.callLater(finishSlide)
    onDurationChanged: if (outgoing && duration <= 1) {
        position = endpoint
        finishSlide()
    }
    property bool failed: false
    property int direction: 1
    property int navigationDirection: 0
    property real outgoingHeight: 0
    readonly property real pixelRatio: Screen.devicePixelRatio || 1
    readonly property real seam: Math.round(width * progress * pixelRatio) / pixelRatio
    signal pageShown()

    // A single navigation action can change several bindings. Incubate only its final destination.
    function resolve() {
        if (!presented) return
        failed = false
        // A private page releases its contents as soon as it loses selection.
        // Finish the visible public page underneath it before the next slide.
        if (current && privatePages.includes(current.modelData) && current.modelData !== requested && outgoing?.visible) {
            current = outgoing
            outgoing = null
            position = endpoint
        }
        targetPage = requested
        if (!targetPage) return
        for (let i = 0; i < slots.count; ++i) {
            const slot = slots.itemAt(i)
            if (slot?.modelData !== targetPage) continue
            if (slot.status === Loader.Ready) display(slot)
            else if (slot.status === Loader.Error) unavailable()
        }
    }
    function clear() {
        current = null; outgoing = null; position = endpoint
    }
    function unavailable() {
        clear()
        failed = true
    }
    function display(slot) {
        if (!presented || slot.modelData !== requested || current === slot) return
        // Reverse the same moving boundary. A third ready page waits for the boundary
        // to clear, so rapid navigation never drops a half-visible page mid-frame.
        const reversing = outgoing === slot
        if (!reversing && current?.visible && outgoing?.visible) return
        const previous = current
        const previousHeight = previous?.height ?? 0
        direction = reversing ? -direction : navigationDirection || (previous && slot.index < previous.index ? -1 : 1)
        outgoing = duration > 1 && previous?.visible ? previous : null
        outgoingHeight = previousHeight
        current = slot
        // Swapping the two slots flips the target on the same moving coordinate.
        if (outgoing) endpoint = 1 - endpoint
        position = endpoint
        if (outgoing && position === endpoint) Qt.callLater(finishSlide)
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
    function finishSlide() {
        if (!outgoing || position !== endpoint) return
        outgoing = null
        resolve()
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
            required property int index
            property bool visited: false
            readonly property bool allowed: modelData === deck.requested || !deck.privatePages.includes(modelData)
            width: deck.width
            height: deck.outgoing === slot ? deck.outgoingHeight : deck.height
            // Clip the contents of each moving page, including scroll views and focus rings.
            clip: visible && deck.outgoing !== null
            sourceComponent: modelData
            active: modelData === deck.prewarm || (deck.presented && allowed &&
                (modelData === deck.targetPage || modelData === deck.anticipated || deck.current === slot || deck.outgoing === slot || visited))
            asynchronous: true
            visible: deck.presented && allowed && status === Loader.Ready && (deck.current === slot || deck.outgoing === slot)
            enabled: deck.current === slot && modelData === deck.requested
            z: deck.current === slot ? 1 : 0
            x: deck.outgoing ? deck.direction * (deck.current === slot ? width - deck.seam : -deck.seam) : 0
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
