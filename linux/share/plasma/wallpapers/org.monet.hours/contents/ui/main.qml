/*
 * The Hours: Monet's wallpaper. One painting in four lights (dawn, midday,
 * dusk and night). When an hour turns, the next light drifts in over 45
 * minutes, so the desktop changes the way daylight does.
 */
import QtQuick
import QtQuick.Window
import org.kde.plasma.plasmoid

WallpaperItem {
    id: root

    // Which series (monet-light writes it, from Monet Settings): The Hours, Water
    // Lilies or Haystacks, each in the same four lights. A change fades in like a new light.
    readonly property string series: ["hours", "lilies", "haystacks"].indexOf(root.configuration.Series) >= 0
        ? root.configuration.Series : "hours"
    readonly property string folder: "file://@DATADIR@/wallpapers/Monet/contents/" + series + "/"
    onFolderChanged: update()
    // Each light starts at this minute of the day, then drifts into the next.
    readonly property var hours: [
        { name: "night", from: 21 * 60 },
        { name: "dawn", from: 5 * 60 },
        { name: "day", from: 10 * 60 },
        { name: "dusk", from: 17 * 60 }
    ]
    readonly property int drift: 45

    // Which light we're in and how far the next one has come in (0 to 1).
    property int current: 0
    property real progress: 0

    // Monet's light sets this (monet-light paint): "hours" drifts through all
    // four lights, "mist" through the light ones and "smoke" through the dark
    // ones, to go with the colors; a light's own name keeps that one.
    readonly property string fixed: root.configuration.Painting || "hours"
    readonly property var pools: ({ mist: ["dawn", "day"], smoke: ["dusk", "night"] })
    onFixedChanged: update()

    function update() {
        const pinned = hours.findIndex(h => h.name === fixed)
        if (pinned >= 0) {
            show(pinned, pinned, 0)
            return
        }
        const pool = pools[fixed]
        const lights = hours.filter(h => !pool || pool.includes(h.name))
        const now = new Date()
        const minute = now.getHours() * 60 + now.getMinutes() + now.getSeconds() / 60
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
        const at = i => hours.indexOf(lights[(i + lights.length) % lights.length])
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

    Timer {
        interval: 60 * 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.update()
    }
}
