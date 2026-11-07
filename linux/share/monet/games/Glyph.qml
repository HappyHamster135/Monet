/*
 * A small drawn mark (an SVG path on a 24-unit square), as Settings draws its own.
 */
import QtQuick
import QtQuick.Shapes

Item {
    id: glyph
    property string path
    property bool filled
    property color color: "#FFFFFF"
    property real stroke: 2.4
    implicitWidth: 16
    implicitHeight: 16

    function intersectsClips() {
        let bounds = Qt.rect(0, 0, width, height)
        for (let item = glyph; item.parent; item = item.parent) {
            const parent = item.parent
            // mapToItem's native implementation does not capture dependencies.
            // Read the geometry that drives its mapping for this binding too.
            const geometry = [item.x, item.y, item.width, item.height,
                              item.scale, item.rotation, item.transformOrigin]
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
        // Qt's software Shape renderer can paint an entirely clipped path.
        // Cull the Shape, keeping its layout slot and the normal GPU path.
        visible: GraphicsInfo.api !== GraphicsInfo.Software || glyph.intersectsClips()
        // Smooth edges without a multisampled layer for every glyph.
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            scale: Qt.size(glyph.width / 24, glyph.height / 24)
            strokeColor: glyph.color
            strokeWidth: glyph.stroke
            fillColor: glyph.filled ? glyph.color : "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin
            PathSvg { path: glyph.path }
        }
    }
}
