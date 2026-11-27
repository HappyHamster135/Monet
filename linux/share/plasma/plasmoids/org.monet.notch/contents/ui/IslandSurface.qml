import QtQuick
import QtQuick.Shapes

// The shoulder curves out into the screen edge, like the corners of a physical cutout.
Shape {
    id: surface
    property real shoulder: 0
    property real chin: 16
    property color topColor: "#060608"
    property color bottomColor: "#1c1c20"
    property color outlineColor: "transparent"
    property real outlineWidth: -1
    property real bottomRadius: Math.max(0, Math.min(chin, height - shoulder, width / 3))
    preferredRendererType: Shape.CurveRenderer
    ShapePath {
        strokeWidth: surface.outlineWidth
        strokeColor: surface.outlineColor
        fillGradient: LinearGradient {
            x1: 0; y1: 0; x2: 0; y2: surface.height
            GradientStop { position: 0; color: surface.topColor }
            GradientStop { position: 1; color: surface.bottomColor }
        }
        startX: 0; startY: 0
        PathLine { x: surface.width; y: 0 }
        PathQuad { controlX: surface.width - surface.shoulder; controlY: 0; x: controlX; y: surface.shoulder }
        PathLine { x: surface.width - surface.shoulder; y: surface.height - surface.bottomRadius }
        PathQuad { controlX: surface.width - surface.shoulder; controlY: surface.height; x: controlX - surface.bottomRadius; y: surface.height }
        PathLine { x: surface.shoulder + surface.bottomRadius; y: surface.height }
        PathQuad { controlX: surface.shoulder; controlY: surface.height; x: controlX; y: surface.height - surface.bottomRadius }
        PathLine { x: surface.shoulder; y: surface.shoulder }
        PathQuad { controlX: surface.shoulder; controlY: 0; x: 0; y: 0 }
    }
}
