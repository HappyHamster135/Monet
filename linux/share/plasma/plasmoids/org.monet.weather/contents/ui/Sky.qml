/*
 * The sky, painted the way Monet's mark is: the sun and three strokes of its
 * reflection for a clear day, a crescent for a clear night, and clouds,
 * rain, snow, fog or a storm in the paintings' colors.
 */
import QtQuick
import QtQuick.Shapes

Item {
    id: sky

    // WMO weather code (Open-Meteo), and whether it's day.
    property int code: 0
    property bool day: true
    property real size: 64
    implicitWidth: size
    implicitHeight: size

    readonly property string kind: code === 0 ? (day ? "sun" : "moon")
        : code <= 2 ? (day ? "sun-cloud" : "moon-cloud")
        : code === 3 ? "cloud"
        : code === 45 || code === 48 ? "fog"
        : (code >= 71 && code <= 77) || code === 85 || code === 86 ? "snow"
        : code >= 95 ? "storm"
        : "rain"
    readonly property real u: size / 64
    readonly property color sun: "#F2552C"
    readonly property color cloud: day ? "#F6F3EC" : "#B8BCD0"
    readonly property color shade: day ? "#C9C4D8" : "#7E84A0"

    // Sun or moon, high on the left when there are clouds too.
    Item {
        id: light
        visible: sky.kind === "sun" || sky.kind === "sun-cloud" || sky.kind === "moon" || sky.kind === "moon-cloud"
        readonly property bool alone: sky.kind === "sun" || sky.kind === "moon"
        x: alone ? 14 * sky.u : 6 * sky.u
        y: alone ? 6 * sky.u : 4 * sky.u
        width: (alone ? 36 : 30) * sky.u
        height: width

        Rectangle {
            visible: sky.day
            anchors.fill: parent
            radius: width / 2
            gradient: Gradient {
                GradientStop { position: 0; color: "#FF9A5E" }
                GradientStop { position: 1; color: "#E5401C" }
            }
        }
        Shape {
            visible: !sky.day
            anchors.fill: parent
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: "#F3EBD2"
                strokeColor: "transparent"
                // Round the left half of the disc, then back along a flatter curve.
                startX: light.width * 0.5; startY: 0
                PathArc { x: light.width * 0.5; y: light.height; radiusX: light.width / 2; radiusY: light.height / 2; direction: PathArc.Counterclockwise }
                PathArc { x: light.width * 0.5; y: 0; radiusX: light.width; radiusY: light.height; direction: PathArc.Clockwise }
            }
        }
    }

    // Monet's reflection: three strokes under the sun.
    Repeater {
        model: sky.kind === "sun" ? 3 : 0
        Rectangle {
            required property int index
            readonly property real long: [30, 21, 12][index] * sky.u
            x: 32 * sky.u - long / 2
            y: (48 + index * 5.5) * sky.u
            width: long
            height: 3.4 * sky.u
            radius: height / 2
            color: sky.sun
            opacity: 1 - index * 0.22
        }
    }

    // A cloud: three puffs on a soft base, with violet in its shade.
    Item {
        id: cloudShape
        visible: sky.kind !== "sun" && sky.kind !== "moon" && sky.kind !== "fog"
        x: 8 * sky.u
        y: (sky.kind === "cloud" ? 16 : 18) * sky.u
        width: 50 * sky.u
        height: 30 * sky.u
        Rectangle { x: 0; y: 12 * sky.u; width: 50 * sky.u; height: 18 * sky.u; radius: height / 2; color: sky.shade }
        Rectangle { x: 6 * sky.u; y: 6 * sky.u; width: 20 * sky.u; height: 20 * sky.u; radius: width / 2; color: sky.cloud }
        Rectangle { x: 18 * sky.u; y: 0; width: 24 * sky.u; height: 24 * sky.u; radius: width / 2; color: sky.cloud }
        Rectangle { x: 2 * sky.u; y: 11 * sky.u; width: 46 * sky.u; height: 15 * sky.u; radius: height / 2; color: sky.cloud }
    }

    // Rain: slanted strokes of ultramarine.
    Repeater {
        model: sky.kind === "rain" || sky.kind === "storm" ? 3 : 0
        Rectangle {
            required property int index
            x: (19 + index * 11) * sky.u
            y: 50 * sky.u
            width: 3 * sky.u
            height: 11 * sky.u
            radius: width / 2
            rotation: 18
            color: "#5C88D0"
        }
    }

    // Snow: white dabs.
    Repeater {
        model: sky.kind === "snow" ? 5 : 0
        Rectangle {
            required property int index
            x: (16 + index * 8) * sky.u
            y: (50 + (index % 2) * 6) * sky.u
            width: 5 * sky.u
            height: width
            radius: width / 2
            color: "#FFFFFF"
            border.width: 1
            border.color: sky.shade
        }
    }

    // A storm: an ochre flash.
    Shape {
        visible: sky.kind === "storm"
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            fillColor: "#F2B84B"
            strokeColor: "transparent"
            PathPolyline {
                path: [Qt.point(34 * sky.u, 42 * sky.u), Qt.point(26 * sky.u, 54 * sky.u), Qt.point(32 * sky.u, 54 * sky.u),
                       Qt.point(28 * sky.u, 64 * sky.u), Qt.point(40 * sky.u, 50 * sky.u), Qt.point(34 * sky.u, 50 * sky.u),
                       Qt.point(38 * sky.u, 42 * sky.u)]
            }
        }
    }

    // Fog: long soft strokes, like mist on the water.
    Repeater {
        model: sky.kind === "fog" ? 4 : 0
        Rectangle {
            required property int index
            readonly property real long: [44, 36, 40, 26][index] * sky.u
            x: 32 * sky.u - long / 2 + (index % 2 ? 4 : -4) * sky.u
            y: (18 + index * 9) * sky.u
            width: long
            height: 4 * sky.u
            radius: height / 2
            color: sky.shade
            opacity: 0.9 - index * 0.12
        }
    }
}
