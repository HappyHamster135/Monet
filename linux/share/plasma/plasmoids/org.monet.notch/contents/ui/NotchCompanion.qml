import QtQuick
import org.kde.kirigami as Kirigami

// The pill owns pointer and keyboard input. The companion only draws inside it.
Item {
    id: buddy
    implicitWidth: 23
    implicitHeight: 24
    property string styleName: "soft"
    property string shapeName: "round"
    property string paletteName: "mint"
    property string side: "left"
    property string frequency: "normal"
    property bool visits: true
    property bool reactions: true
    property bool hideIdle: false
    property bool presented: true
    property bool motionAllowed: Kirigami.Units.longDuration > 1
    readonly property bool showing: presented && (!hideIdle || moment !== "")
    readonly property bool moving: hop.running
    readonly property bool waitingForVisit: visitsTimer.running
    property string moment: ""
    property double lastAt: 0
    property string lastMoment: ""
    property real lift: 0
    property real lean: 0
    readonly property color coat: ({pearl:"#ece8da", lemon:"#eacd78", peach:"#e9ae89", rose:"#df9ca8",
                                    lilac:"#c2abdb", sky:"#98c8e1", mint:"#a5d7c4"})[paletteName] || "#a5d7c4"
    readonly property color ink: "#263436"
    readonly property bool robot: styleName === "robot"
    readonly property bool wideEyes: moment === "finish" || moment === "battery"
    readonly property bool smiling: moment === "greeting" || moment === "music" || moment === "shelf" || moment === "download" || moment === "charging"
    Accessible.ignored: true

    function nextVisit() {
        const seconds = frequency === "rare" ? [600, 1200] : frequency === "frequent" ? [90, 180] : [240, 540]
        return Math.round(1000 * (seconds[0] + Math.random() * (seconds[1] - seconds[0])))
    }
    function scheduleVisit() {
        visitsTimer.stop()
        if (presented && visits) {
            visitsTimer.interval = nextVisit()
            visitsTimer.start()
        }
    }
    function clearMoment() {
        hold.stop()
        hop.stop()
        lift = 0
        lean = 0
        moment = ""
    }
    function perform(kind) {
        clearMoment()
        moment = kind
        if (motionAllowed) hop.start()
        hold.start()
    }
    function greet() {
        if (presented) perform("greeting")
    }
    function react(kind) {
        if (!presented || !reactions) return
        const now = Date.now()
        if (now >= lastAt && ((kind === lastMoment && now - lastAt < 30000)
                || (kind !== "finish" && now - lastAt < 2500))) return
        lastAt = now
        lastMoment = kind
        perform(kind)
    }
    Timer {
        id: visitsTimer
        onTriggered: {
            if (!buddy.moment) buddy.greet()
            buddy.scheduleVisit()
        }
    }
    Timer { id: hold; interval: 2600; onTriggered: buddy.clearMoment() }
    Component.onCompleted: scheduleVisit()
    onFrequencyChanged: scheduleVisit()
    onVisitsChanged: {
        if (!visits && moment === "greeting") clearMoment()
        scheduleVisit()
    }
    onReactionsChanged: if (!reactions && moment !== "greeting") clearMoment()
    onPresentedChanged: {
        if (!presented) clearMoment()
        scheduleVisit()
    }
    onMotionAllowedChanged: if (!motionAllowed) { hop.stop(); lift = 0; lean = 0 }
    SequentialAnimation {
        id: hop
        readonly property real direction: buddy.side === "right" ? -1 : 1
        ParallelAnimation {
            NumberAnimation { target: buddy; property: "lift"; to: -0.11; duration: 140; easing.type: Easing.OutCubic }
            NumberAnimation { target: buddy; property: "lean"; to: -9 * hop.direction; duration: 140; easing.type: Easing.OutCubic }
        }
        ParallelAnimation {
            NumberAnimation { target: buddy; property: "lift"; to: 0; duration: 200; easing.type: Easing.InOutSine }
            NumberAnimation { target: buddy; property: "lean"; to: 5 * hop.direction; duration: 200; easing.type: Easing.InOutSine }
        }
        NumberAnimation { target: buddy; property: "lean"; to: 0; duration: 150; easing.type: Easing.OutCubic }
    }

    Item {
        visible: buddy.showing
        readonly property real unit: Math.min(buddy.width, buddy.height)
        width: unit; height: unit
        anchors.centerIn: parent
        anchors.verticalCenterOffset: buddy.lift * unit
        rotation: buddy.lean
        Rectangle {
            visible: buddy.robot
            width: Math.max(1.4, parent.unit * 0.065); height: parent.unit * 0.18
            x: parent.width * 0.49; y: parent.height * 0.04
            radius: width / 2; color: Qt.darker(buddy.coat, 1.15)
            Rectangle { anchors.horizontalCenter: parent.horizontalCenter; width: parent.width * 2; height: width; radius: width / 2; color: buddy.coat }
        }
        Rectangle {
            id: body
            width: parent.unit * (buddy.shapeName === "egg" ? 0.64 : buddy.shapeName === "pill" ? 0.94 : 0.79)
            height: parent.unit * (buddy.shapeName === "egg" ? 0.86 : buddy.shapeName === "pill" ? 0.63 : 0.79)
            anchors.centerIn: parent
            gradient: Gradient {
                GradientStop { position: 0; color: Qt.lighter(buddy.coat, 1.13) }
                GradientStop { position: 0.57; color: buddy.coat }
                GradientStop { position: 1; color: Qt.darker(buddy.coat, 1.25) }
            }
            radius: buddy.shapeName === "square" ? height * 0.25 : height / 2
            Rectangle {
                anchors.centerIn: parent
                width: parent.width * 0.81; height: parent.height * 0.54
                radius: height * 0.33; color: buddy.ink; visible: buddy.robot
            }
            Rectangle {
                visible: !buddy.robot
                width: parent.width * 0.28; height: Math.max(1, parent.height * 0.085)
                x: parent.width * 0.19; y: parent.height * 0.13
                radius: height / 2; rotation: -20; color: "#98ffffff"
            }
            Repeater {
                model: 2
                Rectangle {
                    required property int index
                    readonly property bool wink: buddy.moment === "greeting" && index === (buddy.side === "right" ? 1 : 0)
                    width: Math.max(2, parent.width * (wink ? 0.20 : buddy.wideEyes ? 0.16 : 0.13))
                    height: Math.max(1.3, parent.height * (wink || buddy.moment === "focus" ? 0.085 : buddy.wideEyes ? 0.25 : 0.19))
                    x: parent.width * (index ? 0.67 : 0.33) - width / 2
                    rotation: buddy.moment === "timer" || buddy.moment === "focus" ? (index ? 12 : -12) : 0
                    y: parent.height * (buddy.moment === "timer" ? 0.37 : 0.44) - height / 2
                    radius: buddy.robot ? width * 0.24 : height / 2
                    color: buddy.robot ? buddy.coat : buddy.ink
                }
            }
            Rectangle {
                width: buddy.wideEyes ? height : parent.width * (buddy.smiling ? 0.26 : 0.16)
                height: Math.max(1, parent.height * (buddy.wideEyes ? 0.15 : 0.075))
                x: (parent.width - width) / 2; y: parent.height * 0.61
                radius: height / 2; color: buddy.robot ? buddy.coat : buddy.ink
            }
        }
    }
}
