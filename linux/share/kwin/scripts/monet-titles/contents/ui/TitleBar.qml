/*
 * The title bar Monet Titles slides down over a window's top: the frames' matte glass (KWin's own
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
    readonly property bool held: grip.holding
    readonly property bool lit: window !== null && window.active
    readonly property bool filling: window !== null && Hover.filling(window.maximizeMode)
    readonly property color ink: lit ? (smoke ? "#EFECE6" : "#1C1B19") : (smoke ? "#B4AEA5" : "#6B665E")

    // What KWin does only for the active window, the script asks of it (main.qml).
    signal activateAsked()
    signal moveAsked()
    signal menuAsked()

    title: "Monet title bar"
    // A tooltip to KWin: above everything, no focus taken, no frame of its own, no grab of the
    // pointer, and no window-opening animation over its own slide.
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

    function close() {
        if (!open) {
            return
        }
        open = false
        settle.restart()
    }

    // Once KWin moves the window, the pointer is KWin's: the bar never hears the button let go.
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
        interval: Math.round(160 * bar.speed) + 40
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
        // Down from the window's top edge as it comes, back up as it goes (quicker going).
        y: bar.open ? 0 : -height
        opacity: bar.open ? 1 : 0
        Behavior on y {
            NumberAnimation {
                duration: Math.round((bar.open ? 220 : 160) * bar.speed)
                easing.type: Easing.Bezier
                easing.bezierCurve: bar.open ? [0.2, 0.9, 0.25, 1, 1, 1] : [0.4, 0, 1, 1, 1, 1]
            }
        }
        Behavior on opacity {
            NumberAnimation {
                duration: Math.round((bar.open ? 140 : 160) * bar.speed)
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
            property bool asked: false
            // Held down by the person. Not MouseArea's pressed: that stays set when KWin takes the
            // pointer for a move, as no release ever comes.
            property bool holding: false
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            enabled: bar.open
            onPressed: mouse => {
                from = Qt.point(mouse.x, mouse.y)
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
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            spacing: 2
            BarButton {
                objectName: "titleMinimize"
                kind: "minimize"
                name: i18nd("monet", "Minimize")
                folder: bar.art
                smoke: bar.smoke
                lit: bar.lit
                ink: bar.ink
                enabled: bar.open && bar.window !== null && bar.window.minimizable
                onActivated: {
                    bar.window.minimized = true
                    bar.close()
                }
            }
            BarButton {
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
                objectName: "titleClose"
                kind: "close"
                name: i18nd("monet", "Close")
                folder: bar.art
                smoke: bar.smoke
                lit: bar.lit
                ink: bar.ink
                enabled: bar.open && bar.window !== null && bar.window.closeable
                onActivated: bar.window.closeWindow()
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
        width: 40
        height: 32
        Accessible.role: Accessible.Button
        Accessible.name: name
        Accessible.onPressAction: if (enabled) activated()
        Image {
            id: picture
            objectName: "titleArt-" + button.kind
            anchors.centerIn: parent
            width: 26
            height: 26
            sourceSize: Qt.size(78, 78)
            source: Hover.art(button.folder, button.smoke, button.kind, press.pressed, press.containsMouse, button.lit)
            opacity: button.enabled ? 1 : 0.35
        }
        Text {
            anchors.centerIn: parent
            visible: picture.status !== Image.Ready
            text: button.kind === "close" ? "×" : button.kind === "minimize" ? "−" : "□"
            color: button.ink
            font.pixelSize: 22
            Accessible.ignored: true
        }
        MouseArea {
            id: press
            anchors.fill: parent
            hoverEnabled: true
            onClicked: button.activated()
        }
    }
}
