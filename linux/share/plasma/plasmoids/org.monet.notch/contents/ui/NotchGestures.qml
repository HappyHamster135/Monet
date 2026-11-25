import QtQuick

// Shared by the pill and the music header, including while the popup opens.
QtObject {
    id: gestures
    required property bool enabled
    required property bool expanded
    signal expansionRequested(bool open)
    signal trackRequested(bool next)

    property bool tracking: false
    property bool phased: false
    property bool ended: false
    property bool handled: false
    property bool startedOpen: false
    property real lastTime: 0
    property real travelX: 0
    property real travelY: 0
    property int axis: 0
    onEnabledChanged: tracking = false

    function begin(withPhase) {
        tracking = true
        phased = withPhase
        ended = false
        handled = false
        startedOpen = expanded
        travelX = travelY = 0
        axis = 0
    }

    function scroll(event) {
        if (!enabled || event.buttons || event.modifiers) {
            tracking = false
            return false
        }
        const now = Date.now()
        const phase = event.phase
        const unphased = phase === Qt.NoScrollPhase
        const gap = now - lastTime
        const pixel = event.pixelDelta
        const usePixels = pixel.x !== 0 || pixel.y !== 0
        const delta = usePixels ? pixel : event.angleDelta
        if (unphased && !delta.x && !delta.y) return false
        const direction = event.inverted ? -1 : 1
        // A wheel can reverse by one detent immediately or tilt after opening
        // the pill. A finger swipe keeps its original axis until it ends.
        const detent = unphased && !usePixels
            && Math.max(Math.abs(delta.x), Math.abs(delta.y)) >= 120
        const changedDirection = detent && axis && (axis === Qt.Horizontal
            ? delta.x === 0 || delta.x * direction * travelX < 0
            : delta.y === 0 || delta.y * direction * travelY < 0)
        if (phase === Qt.ScrollBegin || (unphased && (!tracking || phased || gap > 320 || gap < 0 || changedDirection))) {
            begin(!unphased)
        }
        if (!tracking || (!unphased && !phased)) return false
        const momentum = phase === Qt.ScrollMomentum
        if (momentum && (axis !== Qt.Vertical || gap > 320 || gap < 0)) {
            handled = true
            return false
        }
        if (ended && !momentum) return false
        lastTime = now
        // A conventional 120-unit wheel step acts immediately. Fractional wheel
        // steps and trackpad pixels accumulate before an axis is chosen.
        const factor = direction * (usePixels ? 1 : 0.4)
        const x = delta.x * factor
        const y = delta.y * factor
        if (phase === Qt.ScrollEnd) ended = true
        if (handled) return true
        if (momentum && (Math.abs(x) > Math.abs(y) || y * travelY < 0)) {
            handled = true
            return false
        }
        travelX += x
        travelY += y
        const dx = Math.abs(travelX)
        const dy = Math.abs(travelY)
        if (!axis) {
            if (dx >= 7 && dx >= dy * 1.5) axis = Qt.Horizontal
            else if (dy >= 7 && dy >= dx * 1.5) axis = Qt.Vertical
        }
        if (axis === Qt.Horizontal && dx >= 40 && !momentum) {
            handled = true
            trackRequested(travelX < 0)
        } else if (axis === Qt.Vertical && dy >= 18) {
            handled = true
            const open = travelY < 0
            if (open !== startedOpen && open !== expanded) expansionRequested(open)
        }
        return true
    }
}
