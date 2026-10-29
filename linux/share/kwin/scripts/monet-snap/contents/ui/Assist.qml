/*
 * Snap Assist: right after a window is snapped, the rest of its layout offers the other
 * windows, one part at a time, as pictures of them on a pane of Monet's glass. Pick one and it
 * takes the part; click anywhere else, or press Esc, and it's gone. The arrows and Tab walk
 * the pictures and Enter or Space picks, as in Windows (main.qml lends it those keys).
 */
import QtQuick
import QtQuick.Window
import org.kde.kwin as KWin
import org.kde.kirigami as Kirigami

Window {
    id: assist

    property real speed: 1
    property bool smoke: false
    property color lily: "#357F72"
    property var layouts: []
    property var partRect: null
    signal picked(var window, rect rect)

    property var free: []        // the parts still empty, on the screen: the first is offered
    property var choices: []     // the windows that could go there, the latest first
    property bool shown: false
    readonly property rect offered: free.length > 0 ? free[0] : Qt.rect(0, 0, 0, 0)
    // The picture the keys are on: none until one is pressed (the pointer's ring is enough before).
    property int keyed: -1

    flags: Qt.BypassWindowManagerHint | Qt.FramelessWindowHint
    color: "transparent"
    visible: false

    function offer(w, layout, zone, area) {
        // The other windows one can see and switch to: an app's, not KWin's own, not hidden away.
        const others = KWin.Workspace.stackingOrder.slice().reverse().filter(o => o !== w && o.normalWindow
            && !o.specialWindow && !o.skipSwitcher && !o.hidden && o.caption !== "" && o.resourceClass !== "kwin_wayland"
            && o.resizeable && !o.fullScreen && o.output === w.output
            && (o.onAllDesktops || o.desktops.indexOf(KWin.Workspace.currentDesktop) >= 0))
        const parts = layouts[layout].map((z, i) => i).filter(i => i !== zone).map(i => partRect(layout, i, area))
        if (others.length === 0 || parts.length === 0) {
            return
        }
        const out = w.output.geometry
        x = out.x
        y = out.y
        width = out.width
        height = out.height
        choices = others
        free = parts
        keyed = -1
        hide.stop()
        show()
        shown = true
    }

    function close() {
        shown = false
        hide.restart()
    }

    function pick(o) {
        const part = free[0]
        if (o.minimized) {
            o.minimized = false
        }
        assist.picked(o, part)
        choices = choices.filter(c => c !== o)
        free = free.slice(1)
        keyed = keyed >= 0 ? 0 : -1
        if (free.length === 0 || choices.length === 0) {
            close()
        }
    }

    // A key: "left", "right", "up", "down", "next", "choose" or "close".
    function press(k) {
        if (k === "close") {
            close()
        } else if (k === "choose") {
            pick(choices[Math.max(0, keyed)])
        } else {
            const step = { left: -1, right: 1, up: -grid.columns, down: grid.columns, next: 1 }[k]
            keyed = keyed < 0 ? 0 : k === "next" ? (keyed + 1) % choices.length
                                             : Math.max(0, Math.min(choices.length - 1, keyed + step))
            const tile = tiles.itemAt(keyed)
            if (tile) {
                // In sight, when there are more pictures than the pane shows.
                const top = grid.y + tile.y, bottom = top + tile.height
                if (top < scroller.contentY) {
                    scroller.contentY = top
                } else if (bottom > scroller.contentY + scroller.height) {
                    scroller.contentY = bottom - scroller.height
                }
            }
        }
    }

    Timer {
        id: hide
        interval: Math.round(220 * assist.speed) + 20
        onTriggered: if (!assist.shown) assist.hide()
    }

    // Anywhere but a window's picture, the pane's empty glass too: no, thanks (as in Windows).
    MouseArea {
        anchors.fill: parent
        onClicked: assist.close()
    }

    // The pane over the part on offer, gliding to the next one once this one's taken.
    Rectangle {
        id: pane
        x: assist.offered.x - assist.x
        y: assist.offered.y - assist.y
        width: assist.offered.width
        height: assist.offered.height
        radius: 16
        color: assist.smoke ? Qt.rgba(0.14, 0.137, 0.13, 0.9) : Qt.rgba(0.97, 0.96, 0.945, 0.9)
        border.width: 1
        border.color: assist.smoke ? Qt.rgba(1, 1, 1, 0.16) : Qt.rgba(1, 1, 1, 0.9)
        opacity: assist.shown ? 1 : 0
        scale: assist.shown ? 1 : 0.96
        Behavior on x { NumberAnimation { duration: Math.round(320 * assist.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] } }
        Behavior on y { NumberAnimation { duration: Math.round(320 * assist.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] } }
        Behavior on width { NumberAnimation { duration: Math.round(320 * assist.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] } }
        Behavior on height { NumberAnimation { duration: Math.round(320 * assist.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] } }
        Behavior on opacity { NumberAnimation { duration: Math.round((assist.shown ? 240 : 200) * assist.speed) } }
        Behavior on scale { NumberAnimation { duration: Math.round(380 * assist.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.08, 1, 1] } }

        Flickable {
            id: scroller
            anchors.fill: parent
            anchors.margins: 18
            contentHeight: Math.max(grid.height, height)
            clip: true
            interactive: grid.height > height

            Flow {
                id: grid
                // As many columns as fit at about 240 pixels each, up to 300 wide, in the middle of the part.
                readonly property int columns: Math.max(1, Math.min(assist.choices.length, Math.floor((scroller.width + spacing) / 240)))
                readonly property real tileWidth: Math.min(300, (scroller.width - spacing * (columns - 1)) / columns)
                width: columns * tileWidth + spacing * (columns - 1)
                x: Math.round((scroller.width - width) / 2)
                y: Math.max(0, Math.round((scroller.height - height) / 2))
                spacing: 14

                Repeater {
                    id: tiles
                    model: assist.choices
                    // One window: its picture, its icon and its name.
                    Rectangle {
                        id: tile
                        required property var modelData
                        required property int index
                        readonly property bool lit: hover.hovered || assist.keyed === index
                        width: grid.tileWidth
                        height: Math.round(width * 0.62) + 40
                        radius: 12
                        color: lit ? (assist.smoke ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(1, 1, 1, 0.75)) : "transparent"
                        border.width: lit ? 2 : 0
                        border.color: assist.lily
                        scale: tap.pressed ? 0.97 : 1
                        // Arriving one after another, a breath apart.
                        opacity: 0
                        Component.onCompleted: arrive.start()
                        SequentialAnimation {
                            id: arrive
                            PauseAnimation { duration: Math.round(tile.index * 30 * assist.speed) }
                            NumberAnimation { target: tile; property: "opacity"; to: 1; duration: Math.round(220 * assist.speed) }
                        }
                        Behavior on color { ColorAnimation { duration: Math.round(120 * assist.speed) } }
                        Behavior on scale { NumberAnimation { duration: Math.round(160 * assist.speed) } }
                        Accessible.role: Accessible.Button
                        Accessible.name: modelData.caption
                        Accessible.onPressAction: assist.pick(modelData)

                        // KWin.WindowThumbnail wants an item of its own to fill.
                        Item {
                            id: picture
                            anchors.top: parent.top
                            anchors.left: parent.left
                            anchors.right: parent.right
                            anchors.margins: 8
                            height: parent.height - 48
                            KWin.WindowThumbnail {
                                anchors.fill: parent
                                wId: tile.modelData.internalId
                            }
                        }
                        Row {
                            anchors.top: picture.bottom
                            anchors.topMargin: 8
                            anchors.horizontalCenter: parent.horizontalCenter
                            width: Math.min(implicitWidth, parent.width - 16)
                            spacing: 8
                            Kirigami.Icon {
                                width: 20
                                height: 20
                                source: tile.modelData.icon
                            }
                            Text {
                                width: Math.min(implicitWidth, tile.width - 44)
                                text: tile.modelData.caption
                                elide: Text.ElideRight
                                color: assist.smoke ? "#EFECE6" : "#1C1B19"
                                font.pixelSize: 13
                                verticalAlignment: Text.AlignVCenter
                                height: 20
                            }
                        }
                        HoverHandler {
                            id: hover
                        }
                        TapHandler {
                            id: tap
                            // Its own from the press, so the click doesn't also reach the "no, thanks" under it.
                            gesturePolicy: TapHandler.ReleaseWithinBounds
                            onTapped: assist.pick(tile.modelData)
                        }
                    }
                }
            }
        }
    }
}
