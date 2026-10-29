/*
 * Monet's widget glass: the patch of painting behind a widget, frosted,
 * washed in mist or smoke, with light along the top, a hairline edge and a
 * soft shadow under it.
 *
 * Widgets on the desktop share its surface with the wallpaper, so KWin can't
 * blur behind them. The glass finds The Hours in the scene instead and
 * frosts the part of it the widget covers, so it follows the light as it
 * drifts, a painting that's kept, and the widget as it's moved. Without The
 * Hours (another wallpaper, a panel), or with glass switched off (Settings →
 * Light & Wallpaper; Monet does it on a PC whose processor draws the screen),
 * it's frosted paper, which is far lighter to draw.
 *
 * install.sh copies this file into each of Monet's widgets.
 */
import QtCore
import QtQuick
import QtQuick.Effects
import QtQuick.Shapes
import Qt.labs.folderlistmodel
import org.kde.kirigami as Kirigami

Item {
    id: glass
    LayoutGuard {}

    property real radius: 24
    // A panel popup already has KWin's themed glass; keep only our content there.
    property bool drawBackground: true
    // Room the frost reaches beyond the card, so its edges don't darken.
    readonly property int bleed: 40
    // Mist or smoke, the way monet-light set the colors.
    readonly property bool smoke: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    readonly property color ink: smoke ? "#EFECE6" : "#1C1B19"
    readonly property color dim: smoke ? "#B4AEA5" : "#6B665E"
    // How much the wash hides the painting: paper for reading, glass for looking.
    property real wash: 0.16
    default property alias content: inside.data

    property Item painting: null
    property rect patch: Qt.rect(0, 0, 1, 1)
    // The painting frosted behind it, unless glass is off (monet-light leaves glass-off).
    readonly property bool frosted: drawBackground && painting !== null && glassOff.count === 0
                                    && GraphicsInfo.api !== GraphicsInfo.Software

    // On an older PC (monet-session leaves glass-lite) the frost reaches the edge, without the lens.
    readonly property bool lite: glassLite.count > 0
    // Settings' Glass slider (monet-light leaves glass-frosted or glass-matte): 0 clear, 1 frosted,
    // 2 matte, the painting softer each step and more washed over, until only its color is left.
    readonly property int level: glassMatte.count > 0 ? 2 : glassFrosted.count > 0 ? 1 : 0
    readonly property bool lensed: !lite && level < 2

    FolderListModel {
        id: glassOff
        folder: StandardPaths.writableLocation(StandardPaths.GenericConfigLocation) + "/monet"
        nameFilters: ["glass-off"]
        showDirs: false
    }
    FolderListModel {
        id: glassLite
        folder: glassOff.folder
        nameFilters: ["glass-lite"]
        showDirs: false
    }
    FolderListModel {
        id: glassFrosted
        folder: glassOff.folder
        nameFilters: ["glass-frosted"]
        showDirs: false
    }
    FolderListModel {
        id: glassMatte
        folder: glassOff.folder
        nameFilters: ["glass-matte"]
        showDirs: false
    }

    // The Hours: the item with its two lights, wherever the scene keeps it.
    function findPainting() {
        let top = glass;
        while (top.parent) {
            top = top.parent;
        }
        const queue = [top];
        while (queue.length > 0) {
            const item = queue.shift();
            if (item !== glass && item.hours !== undefined && item.below !== undefined && item.above !== undefined) {
                return item;
            }
            for (let i = 0; i < item.children.length; i++) {
                queue.push(item.children[i]);
            }
        }
        return null;
    }

    function place() {
        if (painting && glass.width > 0) {
            const r = glass.mapToItem(painting, -bleed, -bleed, glass.width + 2 * bleed, glass.height + 2 * bleed);
            patch = Qt.rect(r.x, r.y, r.width, r.height);
        }
    }

    function follow() {
        // Moving the widget moves one of its ancestors: follow them all.
        for (let item = glass.parent; item; item = item.parent) {
            item.xChanged.connect(place);
            item.yChanged.connect(place);
        }
    }

    onWidthChanged: place()
    onHeightChanged: place()
    Component.onCompleted: Qt.callLater(() => {
        painting = findPainting();
        follow();
        place();
    })

    // Its shadow, softer than a window's.
    Rectangle {
        id: shape
        visible: glass.drawBackground
        anchors.fill: parent
        radius: glass.radius
        color: glass.smoke ? "#242321" : "#F3F1EC"
        layer.enabled: GraphicsInfo.api !== GraphicsInfo.Software
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: glass.smoke ? "#AA000000" : "#521C1B19"
            shadowBlur: 1
            shadowVerticalOffset: 8
        }
    }

    // The painting behind it, as through Apple's clear glass: the strokes still there,
    // only softened, and along the edge a lens that magnifies and brightens them, the
    // way light bends in the thickness of a pane.
    readonly property real lensWidth: Math.min(16, glass.radius * 0.7)
    readonly property real magnify: 1.08
    readonly property rect lensPatch: Qt.rect(patch.x + patch.width * (1 - 1 / magnify) / 2,
                                              patch.y + patch.height * (1 - 1 / magnify) / 2,
                                              patch.width / magnify, patch.height / magnify)
    ShaderEffectSource {
        id: grab
        visible: false
        sourceItem: glass.painting
        sourceRect: glass.patch
        // Glass off: nothing to keep up with.
        live: glass.frosted
        recursive: false
    }
    ShaderEffectSource {
        id: lensGrab
        visible: false
        sourceItem: glass.painting
        sourceRect: glass.lensPatch
        live: glass.frosted && glass.lensed
        recursive: false
    }
    // The pane's shape, and its middle (inside the lens) with a soft edge.
    Item {
        id: frostMask
        anchors.fill: frost
        visible: false
        // Always a layer: the effects take it as their mask once, when they're made.
        layer.enabled: true
        Rectangle {
            anchors.fill: parent
            anchors.margins: glass.bleed
            radius: glass.radius
        }
    }
    Item {
        id: middleShape
        anchors.fill: frost
        visible: false
        layer.enabled: true
        Rectangle {
            readonly property real band: glass.lensed ? glass.lensWidth : 0
            anchors.fill: parent
            anchors.margins: glass.bleed + band
            radius: Math.max(glass.radius - band, 4)
        }
    }
    MultiEffect {
        id: middleMask
        anchors.fill: frost
        visible: false
        layer.enabled: true
        source: middleShape
        autoPaddingEnabled: false
        // A long fade, so the lens melts into the middle instead of framing it.
        blurEnabled: true
        blurMax: 32
        blur: 1
    }
    MultiEffect {
        id: lens
        anchors.fill: frost
        visible: glass.frosted && glass.lensed
        source: lensGrab
        autoPaddingEnabled: false
        blurEnabled: true
        blurMax: 32
        blur: 0.3
        saturation: 0.3
        brightness: glass.smoke ? 0.04 : 0.08
        maskEnabled: true
        maskSource: frostMask
        maskThresholdMin: 0.5
        maskSpreadAtMin: 1
    }
    MultiEffect {
        id: frost
        anchors.fill: parent
        anchors.margins: -glass.bleed
        visible: glass.frosted
        source: grab
        autoPaddingEnabled: false
        // Just enough to soften the strokes under the words; Apple's vibrancy brings the
        // painting's color up, and the glass is a touch brighter in mist, darker in smoke.
        blurEnabled: true
        blurMax: 32
        blur: [0.35, 0.7, 1][glass.level]
        saturation: 0.25
        brightness: glass.smoke ? -0.06 : 0.07
        maskEnabled: true
        maskSource: middleMask
        // With these two the soft mask is taken as it is (0 outside, 1 in the middle).
        maskThresholdMin: 0.5
        maskSpreadAtMin: 1
    }

    // The wash, heavier with nothing to frost.
    Rectangle {
        visible: glass.drawBackground
        anchors.fill: parent
        radius: glass.radius
        readonly property color tone: glass.smoke ? "#201F1D" : "#F7F5F1"
        color: Qt.rgba(tone.r, tone.g, tone.b, glass.frosted ? Math.min(glass.wash + [0, 0.2, 0.52][glass.level], 0.86) : 0.86)
    }
    // The pane's body: light gathered at the top, a breath of shade at the foot.
    Rectangle {
        visible: glass.drawBackground
        anchors.fill: parent
        radius: glass.radius
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.rgba(1, 1, 1, glass.smoke ? 0.08 : 0.24) }
            GradientStop { position: 0.4; color: Qt.rgba(1, 1, 1, 0) }
            GradientStop { position: 0.75; color: Qt.rgba(0, 0, 0, 0) }
            GradientStop { position: 1; color: Qt.rgba(0, 0, 0, glass.smoke ? 0.10 : 0.035) }
        }
    }
    // The rim: light caught in the pane's edge, brightest where it falls on it (top left)
    // and where it leaves (bottom right), dim at the other two corners, as on Apple's glass.
    Shape {
        visible: glass.drawBackground
        anchors.fill: parent
        preferredRendererType: Shape.CurveRenderer
        ShapePath {
            readonly property real w: Math.max(glass.width, 1)
            readonly property real h: Math.max(glass.height, 1)
            strokeWidth: -1
            fillRule: ShapePath.OddEvenFill
            // Along this line the top-right and bottom-left corners both fall halfway.
            fillGradient: LinearGradient {
                x1: 0
                y1: 0
                x2: 2 * parent.w * parent.h * parent.h / (parent.w * parent.w + parent.h * parent.h)
                y2: 2 * parent.w * parent.w * parent.h / (parent.w * parent.w + parent.h * parent.h)
                GradientStop { position: 0; color: Qt.rgba(1, 1, 1, glass.smoke ? 0.42 : 0.92) }
                GradientStop { position: 0.5; color: Qt.rgba(1, 1, 1, glass.smoke ? 0.07 : 0.24) }
                GradientStop { position: 1; color: Qt.rgba(1, 1, 1, glass.smoke ? 0.24 : 0.62) }
            }
            PathRectangle { width: glass.width; height: glass.height; radius: glass.radius }
            PathRectangle {
                x: 1.25
                y: 1.25
                width: glass.width - 2.5
                height: glass.height - 2.5
                radius: glass.radius - 1.25
            }
        }
    }
    // A hairline outside, so the pane keeps its edge on light paint.
    Rectangle {
        visible: glass.drawBackground
        anchors.fill: parent
        anchors.margins: -1
        radius: glass.radius + 1
        color: "transparent"
        border.width: 1
        border.color: glass.smoke ? Qt.rgba(0, 0, 0, 0.30) : Qt.rgba(0.11, 0.106, 0.098, 0.08)
    }

    Item {
        id: inside
        anchors.fill: parent
    }
}
