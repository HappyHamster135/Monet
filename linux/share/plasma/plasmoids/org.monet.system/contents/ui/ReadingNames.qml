import QtQuick

QtObject {
    // Keep stable sensor IDs in settings, including when a device is unplugged.
    readonly property var common: ({
        "cpu/all/usage": i18nd("monet", "CPU"),
        "memory/physical/usedPercent": i18nd("monet", "Memory"),
        "cpu/all/maximumTemperature": i18nd("monet", "CPU temperature"),
        "disk/all/usedPercent": i18nd("monet", "Disk usage"),
        "network/all/download": i18nd("monet", "Download"),
        "network/all/upload": i18nd("monet", "Upload"),
        "disk/all/read": i18nd("monet", "Disk read speed"),
        "disk/all/write": i18nd("monet", "Disk write speed"),
        "battery/charge": i18nd("monet", "Battery charge"),
        "battery/time": i18nd("monet", "Battery time")
    })
    function name(key) {
        if (common[key]) return common[key]
        const gpu = /^gpu\/gpu(\d+)\/(usage|temperature)$/.exec(key)
        if (gpu) return gpu[2] === "usage" ? i18nd("monet", "GPU %1", gpu[1]) : i18nd("monet", "GPU %1 temperature", gpu[1])
        const fan = /^lmsensors\/(.+)\/fan(\d+)$/.exec(key)
        return fan ? i18nd("monet", "Fan %1 (%2)", fan[2], fan[1]) : key
    }
    function shortName(key) {
        if (key === "network/all/download") return "↓"
        if (key === "network/all/upload") return "↑"
        if (key === "cpu/all/maximumTemperature") return i18nd("monet", "CPU °")
        if (key === "disk/all/usedPercent") return i18nd("monet", "Disk")
        if (key === "disk/all/read") return i18nd("monet", "Read")
        if (key === "disk/all/write") return i18nd("monet", "Write")
        if (key === "battery/charge") return i18nd("monet", "Battery")
        const fan = /^lmsensors\/.+\/fan(\d+)$/.exec(key)
        if (fan) return i18nd("monet", "Fan %1", fan[1])
        if (key.startsWith("gpu/") && key.endsWith("/temperature")) return name(key.replace("/temperature", "/usage")) + " °"
        return name(key)
    }
    function percentage(key) {
        return key.endsWith("/usage") || key.endsWith("usedPercent") || key === "battery/charge"
    }
    function choices(detected) {
        return Object.keys(common).concat(detected.filter(key =>
            /^gpu\/gpu\d+\/(usage|temperature)$/.test(key) || /^lmsensors\/.+\/fan\d+$/.test(key)))
    }
}
