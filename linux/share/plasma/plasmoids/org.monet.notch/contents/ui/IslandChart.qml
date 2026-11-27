import QtQuick

Canvas {
    id: chart
    property var samples: []
    property real ceiling: 100
    property color ink: "#ffad53"
    property int capacity: 60
    function append(value) { samples = samples.concat([Number.isFinite(value) ? Math.max(0, value) : null]).slice(-capacity) }
    onSamplesChanged: requestPaint()
    onCeilingChanged: requestPaint()
    onInkChanged: requestPaint()
    onWidthChanged: requestPaint()
    onHeightChanged: requestPaint()
    onPaint: {
        const c = getContext("2d")
        c.clearRect(0, 0, width, height)
        c.strokeStyle = "#25ffffff"; c.lineWidth = 1
        for (let i = 0; i < 4; ++i) {
            const y = 2 + i * (height - 4) / 3
            c.beginPath(); c.moveTo(0, y); c.lineTo(width, y); c.stroke()
        }
        c.strokeStyle = ink; c.lineWidth = 2; c.lineJoin = "round"
        c.beginPath()
        let connected = false
        for (let i = 0; i < samples.length; ++i) {
            if (samples[i] === null) { connected = false; continue }
            const x = (capacity - samples.length + i) * width / Math.max(1, capacity - 1)
            const y = height - 2 - Math.min(1, samples[i] / Math.max(1, ceiling)) * (height - 4)
            if (connected) c.lineTo(x, y); else c.moveTo(x, y)
            connected = true
        }
        c.stroke()
    }
}
