/*
 * Windows+Z, as in Windows: the snap layouts for the window you're in, at the top of its screen,
 * for a touchpad or anyone who'd rather not drag. A click on a part puts the window there; a
 * click anywhere else, Esc or Windows+Z again puts them away. The arrows and Tab walk the parts
 * (up and down, the layouts) and Enter or Space chooses; or a layout's number, then a part's, as in
 * Windows (main.qml lends it those keys).
 */
import QtQuick
import QtQuick.Window

Window {
    id: picker

    property var layouts: []
    property bool smoke: false
    property color lily: "#357F72"
    property real speed: 1
    signal chosen(var window, int layout, int zone)

    property var target: null
    property bool shown: false
    property rect area: Qt.rect(0, 0, 0, 0)
    // The part under the pointer, lit as on the bar a dragged window comes up to.
    property int litLayout: -1
    property int litZone: -1
    // Windows' numbers: each layout's (-1), then, once one is picked, its parts'.
    property int numbered: -1

    flags: Qt.BypassWindowManagerHint | Qt.FramelessWindowHint
    color: "transparent"
    visible: false

    function open(w, screen, workArea) {
        if (!w || !w.resizeable || w.fullScreen || w.specialWindow) {
            return
        }
        target = w
        area = workArea
        x = screen.x
        y = screen.y
        width = screen.width
        height = screen.height
        numbered = -1
        hide.stop()
        show()
        shown = true
    }

    function close() {
        shown = false
        litLayout = -1
        hide.restart()
    }

    // A key: "left", "right", "up", "down", "next", "choose", "close", or a number ("1" to "9"):
    // a layout's, then a part's in it, as in Windows. Left and right go part by part through all
    // the layouts, up and down from layout to layout.
    function press(k) {
        if (/^[1-9]$/.test(k)) {
            const n = Number(k) - 1
            if (numbered < 0 && n < layouts.length) {
                numbered = litLayout = n
                litZone = 0
            } else if (numbered >= 0 && n < layouts[numbered].length) {
                choose(numbered, n)
            }
        } else if (k === "close") {
            close()
        } else if (k === "choose") {
            if (litLayout >= 0) {
                choose(litLayout, litZone)
            }
        } else if (litLayout < 0) {
            litLayout = 0
            litZone = 0
        } else if (k === "up" || k === "down") {
            litLayout = Math.max(0, Math.min(layouts.length - 1, litLayout + (k === "up" ? -1 : 1)))
            litZone = Math.min(litZone, layouts[litLayout].length - 1)
            numbered = numbered < 0 ? -1 : litLayout
        } else {
            const all = []
            layouts.forEach((parts, layout) => parts.forEach((part, zone) => all.push([layout, zone])))
            const at = all.findIndex(p => p[0] === litLayout && p[1] === litZone)
            const to = k === "next" ? (at + 1) % all.length : Math.max(0, Math.min(all.length - 1, at + (k === "left" ? -1 : 1)))
            litLayout = all[to][0]
            litZone = all[to][1]
        }
    }

    function choose(layout, zone) {
        const w = target
        close()
        if (w) {
            picker.chosen(w, layout, zone)
        }
    }

    Timer {
        id: hide
        interval: Math.round(220 * picker.speed) + 20
        onTriggered: if (!picker.shown) picker.hide()
    }

    // Anywhere but the layouts: no, thanks.
    MouseArea {
        anchors.fill: parent
        onClicked: picker.close()
    }

    // Comes down from the top of the screen, and goes back up.
    Pebble {
        id: glass
        smoke: picker.smoke
        width: row.implicitWidth + 28
        // Room under the layouts for their numbers.
        height: row.implicitHeight + 28 + 16
        x: Math.round((picker.width - width) / 2)
        y: picker.shown ? picker.area.y - picker.y + 12 : -height - 12
        opacity: picker.shown ? 1 : 0
        Behavior on y { NumberAnimation { duration: Math.round((picker.shown ? 380 : 200) * picker.speed); easing.type: Easing.Bezier; easing.bezierCurve: picker.shown ? [0.2, 0.9, 0.25, 1.08, 1, 1] : [0.4, 0, 1, 1, 1, 1] } }
        Behavior on opacity { NumberAnimation { duration: Math.round(200 * picker.speed) } }

        HoverHandler {
            onPointChanged: {
                const hit = row.partAt(glass, point.position.x, point.position.y)
                picker.litLayout = hit ? hit.layout : -1
                picker.litZone = hit ? hit.zone : -1
            }
            onHoveredChanged: if (!hovered) picker.litLayout = -1
        }
        // Clicks on the glass itself stay on it.
        MouseArea {
            anchors.fill: parent
        }
        Layouts {
            id: row
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.top: parent.top
            anchors.topMargin: 14
            layouts: picker.layouts
            smoke: picker.smoke
            lily: picker.lily
            speed: picker.speed
            litLayout: picker.litLayout
            litZone: picker.litZone
            numbered: picker.numbered
            onChosen: (layout, zone) => picker.choose(layout, zone)
        }
    }
}
