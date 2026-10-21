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

    readonly property string folder: "file://@DATADIR@/wallpapers/Monet/contents/hours/"
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

    function update() {
        const now = new Date()
        const minute = now.getHours() * 60 + now.getMinutes() + now.getSeconds() / 60
        // The light whose start is the latest one before now.
        let index = 0
        let best = -1
        for (let i = 0; i < hours.length; i++) {
            const since = (minute - hours[i].from + 1440) % 1440
            if (best < 0 || since < best) {
                best = since
                index = i
            }
        }
        // `index` started `best` minutes ago; while that's under `drift`, the
        // previous light is still fading out.
        const previous = (index + hours.length - 1) % hours.length
        if (best < drift) {
            show(previous, index, best / drift)
        } else {
            show(index, (index + 1) % hours.length, 0)
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

    function show(from, to, t) {
        if (below.source.toString() !== source(from)) {
            if (above.source.toString() === source(from)) {
                // The next light has come all the way in: it becomes the one below.
                fade.stop()
                const old = below
                below = above
                above = old
                above.opacity = 0
                below.opacity = 1
                below.z = 0
                above.z = 1
            } else {
                below.source = source(from)
                below.opacity = 1
            }
        }
        if (above.source.toString() !== source(to)) {
            fade.stop()
            above.opacity = 0
            above.source = source(to)
        }
        fade.target = above
        fade.to = t
        fade.restart()
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
    }

    Timer {
        interval: 60 * 1000
        running: true
        repeat: true
        triggeredOnStart: true
        onTriggered: root.update()
    }
}
