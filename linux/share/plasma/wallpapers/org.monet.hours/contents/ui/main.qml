/*
 * The Hours: Monet's wallpaper. One painting in four lights (dawn, midday,
 * dusk and night). When an hour turns, the next light drifts in over 45
 * minutes, so the desktop changes the way daylight does: at this place's own
 * sunrise and sunset, and under its weather (rain, fog and snow soften it with
 * mist), as Monet painted his series.
 */
import QtQuick
import QtQuick.Window
import org.kde.plasma.plasmoid

WallpaperItem {
    id: root

    // Which series (monet-light writes it, from Monet Settings): The Hours, Water
    // Lilies or Haystacks, each in the same four lights. A change fades in like a new light.
    readonly property string series: ["hours", "lilies", "haystacks", "magpie"].indexOf(root.configuration.Series) >= 0
        ? root.configuration.Series : "hours"
    readonly property string folder: "file://@DATADIR@/wallpapers/Monet/contents/" + series + "/"
    onFolderChanged: update()
    // Each light starts at this minute of the day, then drifts into the next: these where
    // the place isn't known, or the sun doesn't rise and set today (far north and south).
    readonly property var hours: [
        { name: "night", from: 21 * 60 },
        { name: "dawn", from: 5 * 60 },
        { name: "day", from: 10 * 60 },
        { name: "dusk", from: 17 * 60 }
    ]
    readonly property int drift: 45

    // Where the PC is ("59.33,18.07", from monet-light), for its sunrise, sunset and weather.
    readonly property var place: /^(-?[\d.]+),(-?[\d.]+)$/.exec(root.configuration.Place || "")
    onPlaceChanged: { update(); sky() }

    // Sunrise and sunset today, in minutes after midnight here (the sunrise equation,
    // as NOAA has it), or null where the sun doesn't rise or doesn't set today.
    function sun(lat, lon, now) {
        const rad = Math.PI / 180
        const noon = Date.UTC(now.getFullYear(), now.getMonth(), now.getDate(), 12) / 86400000 + 2440587.5
        const j = Math.round(noon - 2451545.0 + 0.0008) - lon / 360
        const m = (357.5291 + 0.98560028 * j) % 360
        const c = 1.9148 * Math.sin(m * rad) + 0.02 * Math.sin(2 * m * rad) + 0.0003 * Math.sin(3 * m * rad)
        const l = (m + c + 180 + 102.9372) % 360
        const transit = 2451545.0 + j + 0.0053 * Math.sin(m * rad) - 0.0069 * Math.sin(2 * l * rad)
        const decl = Math.asin(Math.sin(l * rad) * Math.sin(23.4397 * rad))
        const cosW = (Math.sin(-0.833 * rad) - Math.sin(lat * rad) * Math.sin(decl)) / (Math.cos(lat * rad) * Math.cos(decl))
        if (cosW < -1 || cosW > 1)
            return null
        const w = Math.acos(cosW) / rad / 360
        const local = jd => {
            const d = new Date((jd - 2440587.5) * 86400000)
            return d.getHours() * 60 + d.getMinutes()
        }
        return { rise: local(transit - w), set: local(transit + w) }
    }

    // Today's start of each light: dawn an hour before sunrise, midday two hours after
    // it, dusk an hour and a half before sunset, night just after it.
    function starts(now) {
        const fixedStarts = {}
        hours.forEach(h => fixedStarts[h.name] = h.from)
        const times = place ? sun(+place[1], +place[2], now) : null
        if (!times || times.set - times.rise < 180)
            return fixedStarts
        const dawn = Math.max(times.rise - 60, 0)
        const dusk = times.set - 90
        const night = Math.min(times.set + 45, 1439)
        const day = Math.min(times.rise + 120, Math.round((dawn + dusk) / 2))
        return dawn < day && day < dusk && dusk < night ? { night: night, dawn: dawn, day: day, dusk: dusk } : fixedStarts
    }

    // Which light we're in and how far the next one has come in (0 to 1).
    property int current: 0
    property real progress: 0

    // Monet's light sets this (monet-light paint): "hours" drifts through all
    // four lights, "mist" through the light ones and "smoke" through the dark
    // ones, to go with the colors; a light's own name keeps that one.
    readonly property string fixed: root.configuration.Painting || "hours"
    readonly property var pools: ({ mist: ["dawn", "day"], smoke: ["dusk", "night"] })
    onFixedChanged: update()

    // Plein-air focus (the Timer, through monet-light): "start,end" in Unix seconds. Meanwhile
    // a whole day, dawn to night, passes on the painting, whatever light was chosen.
    readonly property var focus: /^(\d+),(\d+)$/.exec(root.configuration.Focus || "")
    property bool focusing: false

    function update() {
        focusing = focus !== null && Date.now() / 1000 < +focus[2]
        const pinned = hours.findIndex(h => h.name === fixed)
        if (pinned >= 0 && !focusing) {
            show(pinned, pinned, 0)
            return
        }
        const pool = focusing ? null : pools[fixed]
        const now = new Date()
        const today = starts(now)
        const lights = hours.filter(h => !pool || pool.includes(h.name)).map(h => ({ name: h.name, from: today[h.name] }))
        let minute = now.getHours() * 60 + now.getMinutes() + now.getSeconds() / 60
        if (focusing) {
            // From dawn's start to night's, the session's share of the way.
            const share = Math.max(0, Math.min(1, (Date.now() / 1000 - focus[1]) / Math.max(60, focus[2] - focus[1])))
            minute = today.dawn + share * (today.night + drift - today.dawn)
        }
        // The light whose start is the latest one before now.
        let index = 0
        let best = -1
        for (let i = 0; i < lights.length; i++) {
            const since = (minute - lights[i].from + 1440) % 1440
            if (best < 0 || since < best) {
                best = since
                index = i
            }
        }
        // `index` started `best` minutes ago; while that's under `drift`, the
        // previous light is still fading out.
        const at = i => hours.findIndex(h => h.name === lights[(i + lights.length) % lights.length].name)
        dark = lights[index].name === "dusk" || lights[index].name === "night"
        if (best < drift) {
            show(at(index - 1), at(index), best / drift)
        } else {
            show(at(index), at(index + 1), 0)
        }
    }

    function source(i) {
        return folder + hours[i].name + ".jpg"
    }

    // Two images take turns: the one below shows the light we're in, the one
    // above fades in the next light. When it's fully in, they swap roles
    // without reloading anything that's on screen.
    property Image below: first
    property Image above: second
    // A jump to another light waits for its painting to load, so nothing blinks.
    property bool arriving: false

    function show(from, to, t) {
        if (below.source.toString() !== source(from)) {
            if (above.source.toString() === source(from)) {
                if (arriving)
                    return
                // The next light has come all the way in: it becomes the one below.
                swap()
            } else if (below.source.toString() === "") {
                // The first painting: nothing on screen to fade from.
                below.source = source(from)
            } else {
                // A jump (another light chosen, or waking hours later): the new
                // light comes in over the one on screen, then takes its place.
                if (above.opacity > 0.5)
                    swap()
                fade.stop()
                above.opacity = 0
                arriving = true
                above.source = source(from)
                fade.target = above
                fade.to = 1
                return
            }
        }
        if (above.source.toString() !== source(to)) {
            fade.stop()
            arriving = false
            above.opacity = 0
            above.source = source(to)
        }
        fade.target = above
        fade.to = t
        fade.restart()
    }

    function swap() {
        fade.stop()
        const old = below
        below = above
        above = old
        above.opacity = 0
        below.opacity = 1
        below.z = 0
        above.z = 1
    }

    function loaded(image) {
        if (arriving && image === above && image.status !== Image.Loading) {
            arriving = false
            if (image.status === Image.Ready)
                fade.restart()
        }
    }

    NumberAnimation {
        id: fade
        property: "opacity"
        duration: 1500
        easing.type: Easing.InOutSine
    }

    Image {
        id: first
        anchors.fill: parent
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: false
        sourceSize: Qt.size(root.width * Screen.devicePixelRatio, root.height * Screen.devicePixelRatio)
        z: 0
        onStatusChanged: root.loaded(first)
    }

    Image {
        id: second
        anchors.fill: parent
        fillMode: Image.PreserveAspectCrop
        asynchronous: true
        cache: false
        sourceSize: Qt.size(root.width * Screen.devicePixelRatio, root.height * Screen.devicePixelRatio)
        opacity: 0
        z: 1
        onStatusChanged: root.loaded(second)
    }

    // Each minute; every few seconds while a focus session runs a day through.
    Timer {
        interval: root.focusing ? 4000 : 60 * 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.update()
    }
    onFocusChanged: update()

    // The weather there: rain, fog and snow lay a veil of mist over the painting,
    // drifting in and out over a few minutes, darker in the dusk and night lights.
    property bool dark: false
    property real veil: 0
    property bool snowy: false
    function sky() {
        if (root.configuration.Weather === false || !place) {
            veil = 0
            return
        }
        const request = new XMLHttpRequest()
        request.onreadystatechange = () => {
            if (request.readyState !== XMLHttpRequest.DONE || request.status !== 200)
                return
            try {
                const code = JSON.parse(request.responseText).current.weather_code
                snowy = (code >= 71 && code <= 77) || code === 85 || code === 86
                veil = code === 45 || code === 48 ? 0.32 : snowy ? 0.24
                    : (code >= 51 && code <= 67) || (code >= 80 && code <= 82) || code >= 95 ? 0.2
                    : code === 3 ? 0.08 : 0
            } catch (e) {
            }
        }
        request.open("GET", "https://api.open-meteo.com/v1/forecast?latitude=" + place[1] + "&longitude=" + place[2]
                     + "&current=weather_code")
        request.send()
    }
    Connections {
        target: root.configuration
        function onWeatherChanged() { root.sky() }
    }

    Rectangle {
        anchors.fill: parent
        z: 2
        color: root.dark ? (root.snowy ? "#4A5260" : "#2E3642") : (root.snowy ? "#EEF1F3" : "#D3DADF")
        opacity: root.veil
        Behavior on opacity { NumberAnimation { duration: 180000; easing.type: Easing.InOutSine } }
        Behavior on color { ColorAnimation { duration: 1500 } }
    }

    Timer {
        interval: 30 * 60 * 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.sky()
    }
}
