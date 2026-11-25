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
    property var panels: []
    readonly property var layout: window && window.output ? Hover.barLayout(window.clientGeometry, window.output.geometry, panels)
                                                          : {main: Hover.rect(0, 0, 1, 1), side: null}
    readonly property var area: layout.main
    readonly property bool dragHeld: grip.holding || sideGrip.holding
    readonly property point dragOrigin: sideGrip.holding ? sideGrip.origin : grip.origin
    readonly property var dragSurface: sideGrip.holding ? sideBar : bar
    readonly property bool held: dragHeld || (grip.pressedButtons & Qt.RightButton) !== 0
        || (sideGrip.pressedButtons & Qt.RightButton) !== 0 || minimize.held || maximize.held || dismiss.held
    readonly property bool lit: window !== null && window.active
    readonly property bool filling: window !== null && Hover.filling(window.maximizeMode)
    readonly property bool inputReady: visible && window !== null && !window.deleted
        && !window.minimized && !window.fullScreen
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

    // KWin can create the notch after this script loads. Take a fresh list on
    // reveal and when a dock arrives or leaves while the title is visible.
    function updatePanels(stack) {
        panels = stack.filter(w => w && w.dock && !w.deleted)
    }

    // Out over w's top, or at once over another window's top if it's out already.
    function openFor(w, stack) {
        updatePanels(stack)
        settle.stop()
        if (!open || window !== w) {
            letGo()
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
            finishClosing()
        } else {
            settle.restart()
        }
    }

    function finishClosing() {
        if (open) return
        settle.stop()
        bar.hide()
        bar.window = null
    }

    // KWin consumes the physical release; its native bridge finishes Qt's press at handoff.
    function letGo() {
        grip.holding = false
        sideGrip.holding = false
    }

    // A bar that is still painted must still accept a press. Re-entering or
    // pressing it reverses the fade instead of losing the first gesture.
    function keepOpen() {
        if (!inputReady) return
        settle.stop()
        open = true
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
        onTriggered: bar.finishClosing()
    }

    Item {
        id: sheet
        objectName: "titleSheet"
        width: bar.width
        height: bar.height
        // Keep the hit targets in place through the animation.
        opacity: bar.open ? 1 : 0
        // Do not leave an invisible input window behind for another timer tick.
        onOpacityChanged: if (bar.visible && !bar.open && opacity === 0) bar.finishClosing()
        Behavior on opacity {
            NumberAnimation {
                duration: Math.round((bar.open ? 110 : 100) * bar.speed)
            }
        }

        TitleGlass { anchors.fill: parent }
        TitleGrip {
            id: grip
            surface: bar
            anchors.fill: parent
            anchors.rightMargin: buttons.width
        }

        // The app's icon and title, in the middle, as on the frames.
        Row {
            id: label
            parent: bar.layout.side && bar.layout.side.width >= bar.width - buttons.width ? sideSheet : sheet
            readonly property real room: Math.max(0, parent.width - 2 * (parent === sheet ? buttons.width + 24 : 12))
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
                enabled: bar.inputReady && bar.window.minimizable
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
                enabled: bar.inputReady && bar.window.maximizable
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
                enabled: bar.inputReady && bar.window.closeable
                onActivated: {
                    const target = bar.window
                    bar.close(true)
                    target.closeWindow()
                }
            }
        }
    }

    Window {
        id: sideBar
        title: bar.title
        transientParent: null
        flags: bar.flags
        color: "transparent"
        x: bar.layout.side?.x ?? 0
        y: bar.layout.side?.y ?? 0
        width: bar.layout.side?.width ?? 1
        height: bar.area.height
        readonly property bool needed: bar.visible && bar.layout.side !== null
        onNeededChanged: if (needed) show(); else hide()
        Item {
            id: sideSheet
            anchors.fill: parent
            opacity: sheet.opacity
            TitleGlass { anchors.fill: parent }
            TitleGrip {
                id: sideGrip
                anchors.fill: parent
                surface: sideBar
            }
        }
    }

    component TitleGlass: Item {
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

    }

    // Held and dragged, the window moves; double-clicked, it fills the screen or gets its
    // size back; right-clicked, its menu. A press brings the window forward, as a title bar's does.
    component TitleGrip: MouseArea {
        required property Window surface
        objectName: "titleGrip"
        property point from: Qt.point(0, 0)
        property point origin: Qt.point(0, 0)
        property bool asked: false
        // Track intent separately from MouseArea's press. The scripting-only
        // fallback cannot finish Qt's press when KWin takes the pointer.
        property bool holding: false
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        // KWin owns the pointer during a move; keep the grip idle until it finishes.
        enabled: bar.inputReady && !bar.window.move && !bar.window.resize
        hoverEnabled: true
        onEntered: bar.keepOpen()
        onPressed: mouse => {
            bar.keepOpen()
            from = Qt.point(mouse.x, mouse.y)
            origin = Qt.point(surface.x + mouse.x, surface.y + mouse.y)
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
        width: Math.min(Hover.BUTTON_WIDTH, bar.width / 3)
        height: bar.height
        Accessible.role: Accessible.Button
        Accessible.name: name
        Accessible.onPressAction: if (enabled) { bar.keepOpen(); activated() }
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
            onEntered: bar.keepOpen()
            onPressed: bar.keepOpen()
            onClicked: mouse => mouse.button === Qt.RightButton ? bar.menuAsked() : button.activated()
        }
    }
}
