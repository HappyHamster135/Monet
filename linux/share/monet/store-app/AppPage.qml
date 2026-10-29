/*
 * An app's own page in the Store, under a strip of the painting of what it's for: its picture
 * and name, who makes it, Install (or Open and Remove once you have it, with how far it is
 * meanwhile); its screenshots as a small gallery (one big, the rest to pick from); what it says
 * about itself; what it can reach outside its own space (Flatpak's own list for it); and more
 * apps like it.
 */
import QtQuick
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Templates as T
import org.kde.kirigami as Kirigami
import "../games"

Flickable {
    id: page
    MouseScroll { view: page }
    // The Store's window: install, remove, open, openApp, showPicture.
    property var store
    property var tone
    property var app: ({})
    // From Flatpak, once known: {reach: [...], download, installed, known}.
    property var facts: ({})
    property real progress: -1
    property string problem: ""
    property var job: ({})
    property string jobStatus: ""
    readonly property bool retryable: ["failed", "cancelled", "interrupted"].includes(job.state)
    // The painting of the section it's in.
    property string painting: ""
    property int columns: 2
    readonly property bool working: app.state === "working" || progress >= 0
    readonly property var shots: app.screenshots || []
    property int shown: 0
    signal back()

    function focusFirst() {
        (page.working ? cancelPill : page.retryable ? retryPill : action.visible ? action : openPill).forceActiveFocus()
    }
    onAppChanged: shown = 0

    contentHeight: column.implicitHeight + 48
    clip: true
    boundsBehavior: Flickable.StopAtBounds
    Keys.onEscapePressed: page.back()
    Keys.onBackPressed: page.back()

    Kirigami.WheelHandler {
        target: page
        filterMouseEvents: !("acceptedButtons" in page)
        keyNavigationEnabled: true
        verticalStepSize: 96
    }

    // What it can reach, each as words and a mark; "programs" is the one to think twice about.
    readonly property var reachWords: ({
        programs: [i18n("Can run programs outside its own space"), "M12 3l9 16H3zM12 9.5v4.5M12 17h.01"],
        "all-files": [i18n("All your files"), "M4 7.5h6l2 2h8v9H4z"],
        home: [i18n("Your home folder"), "M4 11l8-6.5 8 6.5M6.5 9.5v9h11v-9"],
        folders: [i18n("Some of your folders"), "M4 7.5h6l2 2h8v9H4z"],
        devices: [i18n("Devices like cameras, microphones and controllers"), "M4 8h11v8H4zM15 10.5l5-2.5v8l-5-2.5"],
        network: [i18n("The internet"), "M12 3a9 9 0 1 0 .01 0M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"]
    })

    Column {
        id: column
        width: page.width
        spacing: 0

        // The painting of what it's for, fading into the paper; the way back on it.
        Item {
            width: parent.width
            height: 170
            Image {
                anchors.fill: parent
                source: page.painting
                fillMode: Image.PreserveAspectCrop
                sourceSize.width: 1800
                asynchronous: true
                opacity: status === Image.Ready ? 0.95 : 0
                Behavior on opacity { NumberAnimation { duration: Math.round(300 * page.tone.speed) } }
            }
            Rectangle {
                anchors.fill: parent
                gradient: Gradient {
                    GradientStop { position: 0.25; color: Qt.rgba(page.tone.paper.r, page.tone.paper.g, page.tone.paper.b, 0) }
                    GradientStop { position: 1.0; color: page.tone.paper }
                }
            }
            Pill {
                anchors.left: parent.left
                anchors.leftMargin: 24
                anchors.top: parent.top
                anchors.topMargin: 20
                tone: page.tone
                glyph: "M14.5 6l-6 6 6 6"
                text: i18n("Back")
                color: page.tone.dark ? Qt.rgba(0.15, 0.145, 0.137, lit ? 0.92 : 0.8) : Qt.rgba(1, 1, 1, lit ? 0.95 : 0.8)
                onClicked: page.back()
            }
        }

        // The app: its picture on a tile of paper over the painting's edge, then the rest.
        Item {
            width: parent.width
            height: header.implicitHeight - 64
            RowLayout {
                id: header
                x: 32
                y: -64
                width: parent.width - 64
                spacing: 26
                Item {
                    Layout.preferredWidth: 132
                    Layout.preferredHeight: 132
                    Layout.alignment: Qt.AlignTop
                    Rectangle {
                        id: tile
                        anchors.fill: parent
                        radius: 30
                        color: page.tone.paper
                        visible: false
                    }
                    MultiEffect {
                        source: tile
                        anchors.fill: tile
                        shadowEnabled: true
                        shadowColor: "#000000"
                        shadowOpacity: page.tone.dark ? 0.5 : 0.18
                        shadowBlur: 0.8
                        shadowVerticalOffset: 6
                    }
                    Image {
                        anchors.fill: parent
                        anchors.margins: 12
                        source: page.app.icon || ""
                        sourceSize: Qt.size(216, 216)
                        fillMode: Image.PreserveAspectFit
                        smooth: true
                    }
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignTop
                    Layout.topMargin: 58
                    spacing: 4
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        text: page.app.name || ""
                        textFormat: Text.PlainText
                        color: page.tone.ink
                        font.family: "Fraunces 72pt SuperSoft"
                        font.weight: Font.Light
                        font.pixelSize: 36
                        wrapMode: Text.Wrap
                    }
                    RowLayout {
                        spacing: 6
                        visible: (page.app.developer || "") !== ""
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            text: page.app.developer || ""
                            textFormat: Text.PlainText
                            color: page.tone.dim
                            font.pixelSize: 14
                        }
                        Glyph {
                            Layout.preferredWidth: 15
                            Layout.preferredHeight: 15
                            visible: page.app.verified === true
                            path: "M12 3l2.4 1.8 3-.2.9 2.9 2.4 1.8-1 2.8 1 2.8-2.4 1.8-.9 2.9-3-.2L12 21l-2.4-1.8-3 .2-.9-2.9-2.4-1.8 1-2.8-1-2.8 2.4-1.8.9-2.9 3 .2zM8.5 12.2l2.3 2.3 4.7-4.7"
                            color: page.tone.lily
                            stroke: 1.8
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            visible: page.app.verified === true
                            text: i18n("Checked by Flathub")
                            color: page.tone.lily
                            font.pixelSize: 13
                        }
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        Layout.topMargin: 2
                        text: page.app.summary || ""
                        textFormat: Text.PlainText
                        color: page.tone.ink
                        font.pixelSize: 15
                        wrapMode: Text.Wrap
                    }
                    // Install, the one bright thing; or Open and Remove; or how far it's got.
                    RowLayout {
                        Layout.topMargin: 12
                        spacing: 10
                        SunButton {
                            id: action
                            visible: page.app.state === "get" && !page.working && !page.retryable
                            speed: page.tone.speed
                            text: i18n("Install")
                            onClicked: page.store.install(page.app.id)
                        }
                        Pill {
                            id: openPill
                            visible: (page.app.state === "installed" || page.app.state === "built-in") && !page.working
                            tone: page.tone
                            kind: "lily"
                            text: i18n("Open")
                            onClicked: page.store.open(page.app.id)
                        }
                        Pill {
                            visible: page.app.state === "installed" && !page.working && !page.retryable
                            tone: page.tone
                            text: i18n("Remove")
                            onClicked: page.store.remove(page.app.id)
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            visible: page.app.state === "built-in"
                            text: i18n("Part of Monet")
                            color: page.tone.dim
                            font.pixelSize: 13
                        }
                        ColumnLayout {
                            visible: page.working
                            spacing: 6
                            Text {
                                horizontalAlignment: Text.AlignLeft
                                text: page.jobStatus || i18n("Working on it…")
                                color: page.tone.ink
                                font.pixelSize: 14
                            }
                            T.ProgressBar {
                                id: meter
                                Layout.preferredWidth: Math.min(260, header.width - 158)
                                implicitHeight: 6
                                from: 0
                                to: 1
                                value: Math.max(0, page.progress)
                                indeterminate: page.progress <= 0
                                background: Rectangle { radius: 3; color: page.tone.wash2 }
                                contentItem: Item {
                                    Rectangle {
                                        // Sliding while it's not known how far it is; from the start once it is.
                                        property real shift: 0
                                        x: meter.indeterminate ? shift : 0
                                        width: meter.indeterminate ? parent.width * 0.3 : parent.width * meter.visualPosition
                                        height: parent.height
                                        radius: 3
                                        color: page.tone.lily
                                        Behavior on width { NumberAnimation { duration: Math.round(200 * page.tone.speed) } }
                                        SequentialAnimation on shift {
                                            running: meter.indeterminate && meter.visible
                                            loops: Animation.Infinite
                                            NumberAnimation { from: 0; to: meter.width * 0.7; duration: 900; easing.type: Easing.InOutSine }
                                            NumberAnimation { from: meter.width * 0.7; to: 0; duration: 900; easing.type: Easing.InOutSine }
                                        }
                                    }
                                }
                            }
                        }
                    }
                    RowLayout {
                        visible: page.working || page.retryable
                        spacing: 10
                        Pill {
                            id: cancelPill
                            objectName: "appCancel"
                            visible: page.working
                            enabled: page.job.state !== "cancelling"
                            tone: page.tone
                            text: page.job.state === "cancelling" ? i18n("Cancelling…") : i18n("Cancel")
                            onClicked: page.store.downloadAction(page.app.id, "cancel")
                        }
                        Pill {
                            id: retryPill
                            objectName: "appRetry"
                            visible: page.retryable
                            tone: page.tone
                            kind: "lily"
                            text: i18n("Retry")
                            onClicked: page.store.downloadAction(page.app.id, "retry")
                        }
                        Pill {
                            visible: page.retryable
                            tone: page.tone
                            text: i18n("Dismiss")
                            onClicked: page.store.downloadAction(page.app.id, "dismiss")
                        }
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        visible: page.problem !== ""
                        text: page.problem
                        textFormat: Text.PlainText
                        color: page.job.state === "cancelled" ? page.tone.dim : "#C2462A"
                        font.pixelSize: 13
                        wrapMode: Text.Wrap
                    }
                }
            }
        }

        // Its screenshots: one big in a mat (a click shows it whole), the rest to pick from.
        Item {
            id: gallery
            x: 32
            width: Math.min(parent.width - 64, 980)
            height: page.shots.length > 0 ? galleryColumn.implicitHeight + 36 : 0
            visible: page.shots.length > 0
            activeFocusOnTab: true
            Keys.onLeftPressed: page.shown = Math.max(0, page.shown - 1)
            Keys.onRightPressed: page.shown = Math.min(page.shots.length - 1, page.shown + 1)
            Keys.onReturnPressed: page.store.showPicture(page.shots[page.shown].image)
            Accessible.role: Accessible.Graphic
            Accessible.name: page.shots.length > 0 ? page.shots[page.shown].caption : ""

            Column {
                id: galleryColumn
                y: 36
                width: parent.width
                spacing: 12
                Item {
                    width: parent.width
                    height: Math.round(width * 0.5625)
                    Rectangle {
                        id: galleryMat
                        anchors.fill: parent
                        radius: 14
                        color: page.tone.dark ? "#34322F" : "#FFFFFF"
                        visible: false
                    }
                    MultiEffect {
                        source: galleryMat
                        anchors.fill: galleryMat
                        shadowEnabled: true
                        shadowColor: "#000000"
                        shadowOpacity: page.tone.dark ? 0.5 : 0.16
                        shadowBlur: 0.8
                        shadowVerticalOffset: 8
                    }
                    Rectangle {
                        anchors.fill: parent
                        anchors.margins: 8
                        radius: 8
                        color: page.tone.wash
                        // The small picture until the big one is there.
                        Image {
                            anchors.fill: parent
                            visible: big.status !== Image.Ready
                            source: page.shots.length > 0 ? page.shots[page.shown].thumb : ""
                            fillMode: Image.PreserveAspectFit
                            asynchronous: true
                        }
                        Image {
                            id: big
                            anchors.fill: parent
                            source: page.shots.length > 0 ? page.shots[page.shown].image : ""
                            fillMode: Image.PreserveAspectFit
                            sourceSize.width: 1600
                            asynchronous: true
                            smooth: true
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: page.store.showPicture(page.shots[page.shown].image)
                        }
                    }
                    // The one before and the one after.
                    Pill {
                        anchors.left: parent.left
                        anchors.leftMargin: 18
                        anchors.verticalCenter: parent.verticalCenter
                        visible: page.shots.length > 1
                        enabled: page.shown > 0
                        tone: page.tone
                        glyph: "M14.5 6l-6 6 6 6"
                        text: ""
                        color: page.tone.dark ? Qt.rgba(0.15, 0.145, 0.137, 0.85) : Qt.rgba(1, 1, 1, 0.9)
                        Accessible.name: i18n("Back")
                        onClicked: page.shown -= 1
                    }
                    Pill {
                        anchors.right: parent.right
                        anchors.rightMargin: 18
                        anchors.verticalCenter: parent.verticalCenter
                        visible: page.shots.length > 1
                        enabled: page.shown < page.shots.length - 1
                        tone: page.tone
                        glyph: "M9.5 6l6 6-6 6"
                        text: ""
                        color: page.tone.dark ? Qt.rgba(0.15, 0.145, 0.137, 0.85) : Qt.rgba(1, 1, 1, 0.9)
                        Accessible.name: i18n("Next")
                        onClicked: page.shown += 1
                    }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    width: parent.width
                    visible: text !== ""
                    text: page.shots.length > 0 ? page.shots[page.shown].caption : ""
                    textFormat: Text.PlainText
                    color: page.tone.dim
                    font.family: "Fraunces 72pt SuperSoft"
                    font.italic: true
                    font.pixelSize: 15
                    wrapMode: Text.Wrap
                }
                Flow {
                    width: parent.width
                    visible: page.shots.length > 1
                    spacing: 10
                    Repeater {
                        model: page.shots
                        Rectangle {
                            id: thumb
                            required property var modelData
                            required property int index
                            width: 116
                            height: 66
                            radius: 9
                            color: page.tone.wash2
                            border.width: page.shown === index ? 2 : 0
                            border.color: page.tone.lily
                            opacity: page.shown === index || thumbMouse.containsMouse ? 1 : 0.72
                            Behavior on opacity { NumberAnimation { duration: Math.round(140 * page.tone.speed) } }
                            Image {
                                anchors.fill: parent
                                anchors.margins: page.shown === thumb.index ? 3 : 0
                                source: thumb.modelData.thumb
                                fillMode: Image.PreserveAspectCrop
                                verticalAlignment: Image.AlignTop
                                sourceSize.width: 240
                                asynchronous: true
                            }
                            MouseArea {
                                id: thumbMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: page.shown = thumb.index
                            }
                        }
                    }
                }
            }
        }

        // What it says about itself.
        Text {
            x: 32
            width: Math.min(parent.width - 64, 820)
            topPadding: 32
            visible: (page.app.description || "") !== ""
            text: page.app.description || ""
            textFormat: Text.RichText
            color: page.tone.ink
            font.pixelSize: 15
            lineHeight: 1.25
            wrapMode: Text.Wrap
            onLinkActivated: link => Qt.openUrlExternally(link)
        }

        // What it can reach, its version, its license and its size.
        GridLayout {
            x: 32
            width: Math.min(parent.width - 64, 820)
            columns: width > 560 ? 2 : 1
            columnSpacing: 32
            rowSpacing: 18
            Item { Layout.columnSpan: parent.columns; Layout.preferredHeight: 16 }

                        ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: 8
                Text {
                    horizontalAlignment: Text.AlignLeft
                    text: i18n("What it can reach")
                    color: page.tone.dim
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.7
                    font.capitalization: Font.AllUppercase
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    visible: page.facts.known !== true
                    text: page.facts.known === false ? i18n("Flatpak didn't say this time.") : i18n("Asking Flatpak…")
                    color: page.tone.dim
                    font.pixelSize: 14
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    visible: page.facts.known === true && (page.facts.reach || []).length === 0
                    text: i18n("Only its own space")
                    color: page.tone.ink
                    font.pixelSize: 14
                }
                Repeater {
                    model: page.facts.known === true ? page.facts.reach : []
                    RowLayout {
                        required property string modelData
                        spacing: 10
                        Glyph {
                            Layout.preferredWidth: 18
                            Layout.preferredHeight: 18
                            path: page.reachWords[modelData] ? page.reachWords[modelData][1] : ""
                            color: modelData === "programs" ? "#C2462A" : page.tone.ink
                            stroke: 1.8
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            text: page.reachWords[modelData] ? page.reachWords[modelData][0] : modelData
                            color: modelData === "programs" ? "#C2462A" : page.tone.ink
                            font.pixelSize: 14
                        }
                    }
                }
            }

            ColumnLayout {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                spacing: 8
                Text {
                    horizontalAlignment: Text.AlignLeft
                    text: i18n("About it")
                    color: page.tone.dim
                    font.pixelSize: 12
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.7
                    font.capitalization: Font.AllUppercase
                }
                Repeater {
                    model: [
                        page.app.version ? (page.app.released
                            ? i18n("Version %1, %2", page.app.version, new Date(page.app.released * 1000).toLocaleDateString(Qt.locale(), Locale.ShortFormat))
                            : i18n("Version %1", page.app.version)) : "",
                        page.app.free === true ? i18n("Free and open source") : page.app.license ? i18n("Not open source") : "",
                        page.facts.download ? i18n("Download: %1", page.facts.download) : "",
                        page.facts.installed ? i18n("On disk: %1", page.facts.installed) : ""
                    ].filter(x => x !== "")
                    Text {
                        required property string modelData
                        horizontalAlignment: Text.AlignLeft
                        text: modelData
                        textFormat: Text.PlainText
                        color: page.tone.ink
                        font.pixelSize: 14
                    }
                }
                Pill {
                    visible: (page.app.homepage || "") !== ""
                    tone: page.tone
                    glyph: "M10 6H6v12h12v-4M13 4h7v7M20 4l-9 9"
                    text: i18n("Its website")
                    onClicked: Qt.openUrlExternally(page.app.homepage)
                }
            }
        }

        // More apps for the same things.
        ColumnLayout {
            x: 32
            width: parent.width - 64
            visible: (page.app.similar || []).length > 0
            spacing: 14
            Item { Layout.preferredHeight: 26 }
            Text {
                horizontalAlignment: Text.AlignLeft
                text: i18n("More like this")
                color: page.tone.ink
                font.family: "Fraunces 72pt SuperSoft"
                font.weight: Font.Light
                font.pixelSize: 26
            }
            GridLayout {
                Layout.fillWidth: true
                columns: page.columns
                columnSpacing: 12
                rowSpacing: 12
                Repeater {
                    model: page.app.similar || []
                    AppCard {
                        required property var modelData
                        Layout.fillWidth: true
                        Layout.preferredWidth: 1
                        tone: page.tone
                        app: modelData
                        onChosen: page.store.openApp(modelData.id)
                    }
                }
            }
        }
    }
}
