// SPDX-License-Identifier: GPL-3.0-or-later
// Small line drawings, independent of the desktop icon theme.
import QtQuick
import QtQuick.Shapes

Item {
    id: mark
    property string kind: "shutdown"
    property color ink: "#1C1B19"
    implicitWidth: 28
    implicitHeight: 28
    readonly property string path: ({
        sleep: "M20.7 13.1A8.8 8.8 0 0 1 10.9 3.3A9 9 0 1 0 20.7 13.1Z",
        hibernate: "M17 3h4l-4 4h4M19.8 14.3A8 8 0 0 1 9.7 4.2A8.5 8.5 0 1 0 19.8 14.3Z",
        restart: "M20 11a8 8 0 1 0-2.3 6M20 11V5M20 11h-6",
        shutdown: "M12 3v9M6.35 5.65a8 8 0 1 0 11.3 0",
        logout: "M9 4H4v16h5M16 8l4 4-4 4M8 12h12",
        arrow: "M9 6l6 6-6 6"
    })[kind] || ""

    function intersectsClips() {
        let bounds = Qt.rect(0, 0, width, height)
        for (let item = mark; item.parent; item = item.parent) {
            const parent = item.parent
            const geometry = [item.x, item.y, item.width, item.height, item.scale, item.rotation]
            bounds = item.mapToItem(parent, bounds)
            if (parent.clip) {
                const left = Math.max(0, bounds.x), top = Math.max(0, bounds.y)
                const right = Math.min(parent.width, bounds.x + bounds.width)
                const bottom = Math.min(parent.height, bounds.y + bounds.height)
                if (right <= left || bottom <= top) return false
                bounds = Qt.rect(left, top, right - left, bottom - top)
            }
        }
        return true
    }

    Shape {
        anchors.fill: parent
        visible: GraphicsInfo.api !== GraphicsInfo.Software || mark.intersectsClips()
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            scale: Qt.size(mark.width / 24, mark.height / 24)
            strokeColor: mark.ink
            strokeWidth: 1.8
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: mark.path }
        }
    }
}
