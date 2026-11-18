/*
 * The title bar Monet Titles shows over a window's top: the frames' matte glass (KWin's own
 * windows have no blur behind them), the app's icon and title, and the frames' buttons, signs
 * brushed in ink that swell into a dab of paint under the pointer. Drag it to move the window,
 * double-click it to fill the screen or give the window its size back, right-click it for the
 * window's menu. It lies over the window: the app keeps its size and place.
 */
import QtQuick
import QtQuick.Window
import org.kde.kirigami as Kirigami
import "hover.js" as Hover

Window {
    id: bar

    // The KWin window this is the title bar of, while the bar is out or going.
    property var window: null
    property bool open: false
    property real speed: 1
    property bool smoke: false
    // The frames' own buttons (tools/make-decoration.py; install.sh fills in where Monet's files are).
    property string art: "file://@DATADIR@/monet/window-buttons/"
    readonly property var area: window && window.output ? Hover.barRect(window.clientGeometry, window.output.geometry)
                                                        : Hover.rect(0, 0, 1, 1)
    readonly property bool dragHeld: grip.holding
    readonly property point dragOrigin: grip.origin
    readonly property bool held: dragHeld || (grip.pressedButtons & Qt.RightButton) !== 0
        || minimize.held || maximize.held || dismiss.held
    readonly property bool lit: window !== null && window.active
    readonly property bool filling: window !== null && Hover.filling(window.maximizeMode)
    readonly property color ink: lit ? (smoke ? "#EFECE6" : "#1C1B19") : (smoke ? "#B4AEA5" : "#6B665E")

    // What KWin does only for the active window, the script asks of it (main.qml).
    signal activateAsked()
    signal moveAsked()
    signal menuAsked()

    title: "Monet title bar"
    // A tooltip to KWin: above everything, no focus taken, no frame of its own, no grab of the
    // pointer, and no window-opening animation over its own fade.
    flags: Qt.ToolTip | Qt.FramelessWindowHint | Qt.BypassWindowManagerHint | Qt.WindowDoesNotAcceptFocus
    color: "transparent"
    visible: false
    x: area.x
    y: area.y
    width: area.width
    height: area.height

    // Out over w's top, or at once over another window's top if it's out already.
    function openFor(w) {
        settle.stop()
        if (!open || window !== w) {
            grip.holding = false
        }
        window = w
        if (!visible) {
            show()
        }
        open = true
    }

    function close(immediate = false) {
        if (!open && !immediate) return
        open = false
        if (immediate || speed <= 0) {
            settle.stop()
            hide()
            window = null
        } else {
            settle.restart()
        }
    }

    // KWin consumes the physical release; its native bridge finishes Qt's press at handoff.
    function letGo() {
        grip.holding = false
    }

    function toggleFilling() {
        if (window && window.maximizable) {
            const fill = !filling
            window.setMaximize(fill, fill)
        }
    }

    // Shown and hidden by hand: KWin doesn't show a script's window for a visible it's given.
    Timer {
        id: settle
        interval: Math.round(100 * bar.speed) + 16
        onTriggered: {
            if (!bar.open) {
                bar.hide()
                bar.window = null
            }
        }
    }

    Item {
        id: sheet
        objectName: "titleSheet"
        width: bar.width
        height: bar.height
        // Keep the hit targets in place through the animation.
        opacity: bar.open ? 1 : 0
        Behavior on opacity {
            NumberAnimation {
                duration: Math.round((bar.open ? 110 : 100) * bar.speed)
            }
        }

        // The frames' matte glass, light along its top and a hairline under it.
        Rectangle {
            objectName: "titleGlass"
            anchors.fill: parent
            color: bar.smoke ? Qt.rgba(34 / 255, 33 / 255, 31 / 255, 0.94) : Qt.rgba(247 / 255, 245 / 255, 241 / 255, 0.93)
        }
        Rectangle {
            y: 1
            width: parent.width
            height: 1
            color: bar.smoke ? Qt.rgba(1, 1, 1, 0.12) : Qt.rgba(1, 1, 1, 0.47)
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width
            height: 1
            color: bar.smoke ? Qt.rgba(1, 1, 1, 0.10) : Qt.rgba(0, 0, 0, 0.10)
        }

        // Held and dragged, the window moves; double-clicked, it fills the screen or gets its
        // size back; right-clicked, its menu. A press brings the window forward, as a title bar's does.
        MouseArea {
            id: grip
            objectName: "titleGrip"
            property point from: Qt.point(0, 0)
            property point origin: Qt.point(0, 0)
            property bool asked: false
            // Track intent separately from MouseArea's press. The scripting-only
            // fallback cannot finish Qt's press when KWin takes the pointer.
            property bool holding: false
            anchors.left: parent.left
            anchors.right: buttons.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            // KWin owns the pointer during a move; keep the grip idle until it finishes.
            enabled: bar.open && !(bar.window && bar.window.move)
            onPressed: mouse => {
                from = Qt.point(mouse.x, mouse.y)
                origin = Qt.point(bar.x + mouse.x, bar.y + mouse.y)
                asked = false
                holding = mouse.button === Qt.LeftButton
                if (holding) {
                    bar.activateAsked()
                }
            }
            onReleased: holding = false
            onCanceled: holding = false
            onPositionChanged: mouse => {
                if (holding && !asked
                        && Math.abs(mouse.x - from.x) + Math.abs(mouse.y - from.y) >= Qt.styleHints.startDragDistance) {
                    asked = true
                    bar.moveAsked()
                }
            }
            onDoubleClicked: mouse => {
                if (mouse.button === Qt.LeftButton) {
                    bar.toggleFilling()
                }
            }
            onClicked: mouse => {
                if (mouse.button === Qt.RightButton) {
                    bar.menuAsked()
                }
            }
        }

        // The app's icon and title, in the middle, as on the frames.
        Row {
            id: label
            readonly property real room: Math.max(0, bar.width - 2 * (buttons.width + 24))
            anchors.centerIn: parent
            spacing: 8
            visible: room > 40
            Kirigami.Icon {
                id: icon
                anchors.verticalCenter: parent.verticalCenter
                width: 18
                height: 18
                source: bar.window ? bar.window.icon : ""
                visible: label.room > 120
            }
            Text {
                objectName: "titleCaption"
                anchors.verticalCenter: parent.verticalCenter
                width: Math.min(implicitWidth, label.room - (icon.visible ? icon.width + label.spacing : 0))
                text: bar.window ? bar.window.caption : ""
                textFormat: Text.PlainText
                elide: Text.ElideRight
                color: bar.ink
                font.family: "Fraunces 72pt SuperSoft"
                font.pixelSize: 15
            }
        }

        Row {
            id: buttons
            anchors.right: parent.right
            anchors.top: parent.top
            BarButton {
                id: minimize
                objectName: "titleMinimize"
                kind: "minimize"
                name: i18nd("monet", "Minimize")
                folder: bar.art
                smoke: bar.smoke
                lit: bar.lit
                ink: bar.ink
                enabled: bar.open && bar.window !== null && bar.window.minimizable
                onActivated: {
                    const target = bar.window
                    bar.close(true)
                    target.minimized = true
                }
            }
            BarButton {
                id: maximize
                objectName: "titleMaximize"
                kind: bar.filling ? "restore" : "maximize"
                name: bar.filling ? i18nd("monet", "Restore") : i18nd("monet", "Maximize")
                folder: bar.art
                smoke: bar.smoke
                lit: bar.lit
                ink: bar.ink
                enabled: bar.open && bar.window !== null && bar.window.maximizable
                onActivated: bar.toggleFilling()
            }
            BarButton {
                id: dismiss
                objectName: "titleClose"
                kind: "close"
                name: i18nd("monet", "Close")
                folder: bar.art
                smoke: bar.smoke
                lit: bar.lit
                ink: bar.ink
                enabled: bar.open && bar.window !== null && bar.window.closeable
                onActivated: {
                    const target = bar.window
                    bar.close(true)
                    target.closeWindow()
                }
            }
        }
    }

    // A button: the sign alone, and under the pointer its dab of paint. A packaging or artwork
    // error must never leave a window without a way to close it: then a plain sign.
    component BarButton: Item {
        id: button
        required property string kind
        required property string name
        required property string folder
        required property bool smoke
        required property bool lit
        required property color ink
        signal activated()
        readonly property bool held: press.pressed
        width: Math.min(44, bar.width / 3)
        height: bar.height
        Accessible.role: Accessible.Button
        Accessible.name: name
        Accessible.onPressAction: if (enabled) activated()
        Image {
            id: picture
            objectName: "titleArt-" + button.kind
            anchors.centerIn: parent
            width: Math.min(26, button.width, button.height)
            height: width
            sourceSize: Qt.size(78, 78)
            source: Hover.art(button.folder, button.smoke, button.kind, press.pressed, press.containsMouse, button.lit)
            opacity: button.enabled ? 1 : 0.35
        }
        Text {
            anchors.centerIn: parent
            visible: picture.status !== Image.Ready
            text: button.kind === "close" ? "×" : button.kind === "minimize" ? "−" : button.kind === "restore" ? "❐" : "□"
            color: button.ink
            font.pixelSize: 22
            Accessible.ignored: true
        }
        MouseArea {
            id: press
            anchors.fill: parent
            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onClicked: mouse => mouse.button === Qt.RightButton ? bar.menuAsked() : button.activated()
        }
    }
}
