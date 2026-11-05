import QtQuick

QtObject {
    // At most a minute, including both endpoints. Timestamps also bound the
    // history after a delayed timer tick; we never fill missing time with zero.
    property var samples: []
    readonly property int duration: samples.length > 1
        ? Math.round((samples[samples.length - 1].time - samples[0].time) / 1000) : 0

    function clear() { samples = [] }
    function append(values, now) {
        if (!values.length || !values.every(value => typeof value === "number"
                                           && Number.isFinite(value) && value >= 0)) return
        const last = samples.length ? samples[samples.length - 1] : null
        // A first value may arrive between timer ticks. Avoid recording it twice
        // in the same second, and restart cleanly if the system clock changes.
        if (last && now >= last.time && now - last.time < 900) return
        const previous = last && now >= last.time && now - last.time < 2500
            && last.values.length === values.length
            ? samples.filter(row => now - row.time <= 60000) : []
        samples = previous.concat([{time: now, values: values.slice()}]).slice(-61)
    }
}
