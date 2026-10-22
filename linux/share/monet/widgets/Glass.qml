/*
 * Monet's widget glass: the patch of painting behind a widget, frosted,
 * washed in mist or smoke, with light along the top, a hairline edge and a
 * soft shadow under it.
 *
 * Widgets on the desktop share its surface with the wallpaper, so KWin can't
 * blur behind them. The glass finds The Hours in the scene instead and
 * frosts the part of it the widget covers, so it follows the light as it
 * drifts, a painting that's kept, and the widget as it's moved. Without The
 * Hours (another wallpaper, a panel) it's frosted paper.
 *
 * install.sh copies this file into each of Monet's widgets.
 */
import QtQuick
import QtQuick.Effects
import org.kde.kirigami as Kirigami

Item {
    id: glass

    property real radius: 24
    // Room the frost reaches beyond the card, so its edges don't darken.
    readonly property int bleed: 40
    // Mist or smoke, the way monet-light set the colors.
    readonly property bool smoke: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    readonly property color ink: smoke ? "#EFECE6" : "#1C1B19"
    readonly property color dim: smoke ? "#B4AEA5" : "#6B665E"
    // How much the wash hides the painting: paper for reading, glass for looking.
    property real wash: 0.46
    default property alias content: inside.data

    property Item painting: null
    property rect patch: Qt.rect(0, 0, 1, 1)

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
        anchors.fill: parent
        radius: glass.radius
        color: glass.smoke ? "#242321" : "#F3F1EC"
        layer.enabled: true
        layer.effect: MultiEffect {
            shadowEnabled: true
            shadowColor: glass.smoke ? "#AA000000" : "#661C1B19"
            shadowBlur: 1
            shadowVerticalOffset: 6
        }
    }

    // The painting behind it, frosted.
    ShaderEffectSource {
        id: grab
        visible: false
        sourceItem: glass.painting
        sourceRect: glass.patch
        live: true
        recursive: false
    }
    Item {
        id: frostMask
        anchors.fill: frost
        visible: false
        layer.enabled: true
        Rectangle {
            anchors.fill: parent
            anchors.margins: glass.bleed
            radius: glass.radius
        }
    }
    MultiEffect {
        id: frost
        anchors.fill: parent
        anchors.margins: -glass.bleed
        visible: glass.painting !== null
        source: grab
        autoPaddingEnabled: false
        blurEnabled: true
        blurMax: 64
        blur: 1
        saturation: 0.35
        maskEnabled: true
        maskSource: frostMask
        maskThresholdMin: 0.5
        maskSpreadAtMin: 1
    }

    // The wash, heavier with nothing to frost.
    Rectangle {
        anchors.fill: parent
        radius: glass.radius
        readonly property color tone: glass.smoke ? "#201F1D" : "#F7F5F1"
        color: Qt.rgba(tone.r, tone.g, tone.b, glass.painting ? glass.wash : 0.86)
    }
    // Light along the top, the way light catches the edge of a pane.
    Rectangle {
        anchors.fill: parent
        radius: glass.radius
        gradient: Gradient {
            GradientStop { position: 0; color: Qt.rgba(1, 1, 1, glass.smoke ? 0.10 : 0.30) }
            GradientStop { position: 0.32; color: Qt.rgba(1, 1, 1, 0) }
        }
    }
    Rectangle {
        anchors.fill: parent
        radius: glass.radius
        color: "transparent"
        border.width: 1
        border.color: glass.smoke ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(1, 1, 1, 0.55)
    }
    Rectangle {
        anchors.fill: parent
        anchors.margins: -1
        radius: glass.radius + 1
        color: "transparent"
        border.width: 1
        border.color: glass.smoke ? Qt.rgba(0, 0, 0, 0.30) : Qt.rgba(0.11, 0.106, 0.098, 0.10)
    }

    Item {
        id: inside
        anchors.fill: parent
    }
}
