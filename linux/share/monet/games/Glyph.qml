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
    Shape {
        anchors.fill: parent
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
