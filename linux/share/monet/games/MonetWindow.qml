/* One frame for Monet's apps: the title and body share their glass and rounded outline.
 * Moves and resizes belong to the compositor, so snapping and screen edges keep working. */
import QtQuick
import QtQuick.Window
import QtQuick.Controls as QQC2
import QtQuick.Templates as T
import QtQuick.Effects
import org.kde.kirigami as Kirigami

Window {
    id: window
    default property alias appData: contents.data
    flags: Qt.Window | Qt.FramelessWindowHint
    color: "transparent"
    readonly property bool frameDark: Kirigami.Theme.backgroundColor.hslLightness < 0.5
    readonly property bool frameMaximized: visibility === Window.Maximized || visibility === Window.FullScreen
    readonly property int frameRadius: frameMaximized ? 0 : 14
    readonly property int titleHeight: visibility === Window.FullScreen ? 0 : 40
    readonly property color frameInk: frameDark ? "#F1EEE8" : "#1C1B19"

    signal backgroundMoveRequested()
    onBackgroundMoveRequested: window.startSystemMove()

    function toggleMaximized() {
        if (frameMaximized) showNormal()
        else showMaximized()
    }

    // Explicit data keeps the frame outside the default property used by the app's children.
    data: [
        Item {
            id: surface
            anchors.fill: parent
            layer.enabled: window.frameRadius > 0 && GraphicsInfo.api !== GraphicsInfo.Software
            layer.effect: MultiEffect {
                maskEnabled: true
                maskSource: outline
                autoPaddingEnabled: false
                maskThresholdMin: 0.5
                maskSpreadAtMin: 1
            }

            WindowGlass {
                id: glass
                objectName: "windowGlass"
                anchors.fill: parent
                radius: window.frameRadius
                dark: window.frameDark
                blurred: blurBehind
            }

            // Behind the app: only presses that its controls do not handle reach
            // this surface. Never put a drag handler over buttons or editors.
            MouseArea {
                id: backgroundDrag
                objectName: "windowBackgroundDrag"
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                enabled: window.visibility !== Window.FullScreen
                property point origin
                property bool requested: false
                onPressed: mouse => {
                    if (mouse.modifiers !== Qt.NoModifier) {
                        mouse.accepted = false
                        return
                    }
                    origin = Qt.point(mouse.x, mouse.y)
                    requested = false
                }
                onPositionChanged: mouse => {
                    if (pressed && !requested
                            && Math.abs(mouse.x - origin.x) + Math.abs(mouse.y - origin.y)
                                >= Qt.styleHints.startDragDistance) {
                        requested = true
                        window.backgroundMoveRequested()
                    }
                }
            }

            Item {
                id: contents
                objectName: "windowContents"
                anchors.fill: parent
                anchors.topMargin: window.titleHeight
                clip: true
            }

            Item {
                id: titleBar
                objectName: "windowTitleBar"
                width: parent.width
                height: window.titleHeight
                visible: height > 0
                // No second background: the same WindowGlass is behind the title and sidebar.
                Item {
                    anchors.fill: parent
                    anchors.rightMargin: controls.width + 8
                    DragHandler {
                        target: null
                        onActiveChanged: if (active) window.startSystemMove()
                    }
                    TapHandler {
                        onDoubleTapped: window.toggleMaximized()
                    }
                }
                Text {
                    anchors.centerIn: parent
                    width: Math.max(0, parent.width - 2 * (controls.width + 16))
                    text: window.title
                    color: window.frameInk
                    opacity: window.active ? 1 : 0.68
                    font.family: "Fraunces 72pt SuperSoft"
                    font.pixelSize: 15
                    horizontalAlignment: Text.AlignHCenter
                    elide: Text.ElideRight
                    Accessible.ignored: true
                }
                Row {
                    id: controls
                    anchors.right: parent.right
                    anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 2
                    FrameButton {
                        objectName: "windowMinimize"
                        dark: window.frameDark
                        windowActive: window.active
                        text: i18n("Minimize")
                        paintAction: "minimize"
                        paint: "#3F9A89"
                        onClicked: window.showMinimized()
                    }
                    FrameButton {
                        objectName: "windowMaximize"
                        dark: window.frameDark
                        windowActive: window.active
                        text: window.frameMaximized ? i18n("Restore") : i18n("Maximize")
                        paintAction: window.frameMaximized ? "restore" : "maximize"
                        paint: "#E8AE48"
                        onClicked: window.toggleMaximized()
                    }
                    FrameButton {
                        objectName: "windowClose"
                        dark: window.frameDark
                        windowActive: window.active
                        text: i18n("Close")
                        paintAction: "close"
                        paint: "#F2552C"
                        onClicked: window.close()
                    }
                }
            }
        },
        Rectangle {
            id: outline
            width: window.width
            height: window.height
            radius: window.frameRadius
            color: "white"
            visible: false
            layer.enabled: true
        },
        // These sit above both the app and title controls. Corners win over straight edges.
        Repeater {
            model: [Qt.TopEdge, Qt.BottomEdge, Qt.LeftEdge, Qt.RightEdge,
                    Qt.TopEdge | Qt.LeftEdge, Qt.TopEdge | Qt.RightEdge,
                    Qt.BottomEdge | Qt.LeftEdge, Qt.BottomEdge | Qt.RightEdge]
            delegate: MouseArea {
                required property int modelData
                readonly property bool leftEdge: (modelData & Qt.LeftEdge) !== 0
                readonly property bool rightEdge: (modelData & Qt.RightEdge) !== 0
                readonly property bool topEdge: (modelData & Qt.TopEdge) !== 0
                readonly property bool bottomEdge: (modelData & Qt.BottomEdge) !== 0
                readonly property bool corner: (leftEdge || rightEdge) && (topEdge || bottomEdge)
                readonly property int grip: corner ? 12 : 6
                objectName: "windowResize" + modelData
                parent: window.contentItem
                z: 100
                visible: !window.frameMaximized
                x: rightEdge ? window.width - width : 0
                y: bottomEdge ? window.height - height : 0
                width: leftEdge || rightEdge ? grip : window.width
                height: topEdge || bottomEdge ? grip : window.height
                cursorShape: corner ? (leftEdge === topEdge ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor)
                    : leftEdge || rightEdge ? Qt.SizeHorCursor : Qt.SizeVerCursor
                acceptedButtons: Qt.LeftButton
                onPressed: window.startSystemResize(modelData)
            }
        }
    ]

    component FrameButton: T.Button {
        id: button
        required property string paintAction
        required property color paint
        required property bool dark
        required property bool windowActive
        width: 40
        height: 32
        hoverEnabled: true
        focusPolicy: Qt.TabFocus
        Accessible.name: text
        QQC2.ToolTip.visible: hovered
        QQC2.ToolTip.delay: 700
        QQC2.ToolTip.text: text
        background: Rectangle {
            radius: 9
            color: "transparent"
            border.width: parent.activeFocus ? 1 : 0
            border.color: parent.paint
        }
        contentItem: Item {
            Image {
                id: artwork
                objectName: "windowButtonArtwork-" + button.paintAction
                anchors.centerIn: parent
                width: 26
                height: 26
                sourceSize: Qt.size(78, 78)
                readonly property string appearance: button.down ? "pressed"
                    : button.hovered || button.activeFocus ? "hover" : button.windowActive ? "active" : "inactive"
                source: Qt.resolvedUrl("../window-buttons/" + (button.dark ? "MonetSmoke" : "Monet")
                    + "-" + button.paintAction + "-" + appearance + ".svg")
                opacity: button.enabled ? 1 : 0.35
            }
            // A packaging or artwork error must never make a frameless window
            // impossible to close. Keep the action recognizable without assets.
            Text {
                objectName: "windowButtonFallback-" + button.paintAction
                anchors.centerIn: parent
                visible: artwork.status !== Image.Ready
                text: button.paintAction === "close" ? "×" : button.paintAction === "minimize" ? "−" : "□"
                color: button.dark ? "#F1EEE8" : "#1C1B19"
                font.pixelSize: 24
                Accessible.ignored: true
            }
        }
    }
}
