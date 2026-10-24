// Monet Setup: the installer on the USB stick.
//
// The dawn harbor fills the screen; the steps sit on a sheet of frosted glass
// (the painting blurred in advance and drawn once, so it needs no graphics
// card). Laid out on a 1440 x 900 grid and scaled to the screen with `u`.
// Steps: Hello, Wi-Fi, who's using this PC, your apps, Ready, then installing and done.

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtQuick.Shapes

ApplicationWindow {
    id: win
    visible: true
    visibility: Window.FullScreen
    width: 1440
    height: 900
    color: "#9C9DB4"
    title: tr("Monet Setup")

    readonly property real u: Math.min(width / 1440, height / 900)
    readonly property color ink: "#1B1A19"
    readonly property color dim: Qt.rgba(27 / 255, 26 / 255, 25 / 255, 0.64)
    readonly property color sun: "#F2552C"
    readonly property color lily: "#357F72"
    readonly property string serif: "Fraunces 72pt SuperSoft"
    readonly property string sans: "Inter"

    // 0 hello, 1 wifi, 2 person, 3 apps, 4 ready, 5 installing (then done or failed)
    property int step: setup.startStep
    readonly property bool installing: step === 5
    readonly property string phase: setup.phase
    // An encrypted Monet's recovery key comes before All set, until it's said to be kept.
    property bool keyKept: false
    readonly property bool showingKey: installing && phase === "done" && setup.recoveryKey !== "" && !keyKept

    function px(n) { return Math.max(1, Math.round(n * u)) }

    // Setup's words in the language picked on the first page. Reading setup.lang makes
    // every text that asks say itself again when the language changes.
    function tr(text, value) {
        setup.lang
        return setup.say(text, value === undefined ? "" : String(value))
    }
    function trc(context, text, value) {
        setup.lang
        return setup.sayIn(context, text, value === undefined ? "" : String(value))
    }

    // The painting, cropped to fill the screen.
    Image {
        id: painting
        anchors.fill: parent
        source: art + "painting.jpg"
        fillMode: Image.PreserveAspectCrop
        asynchronous: false
        smooth: true
    }

    // Monet's mark and name, top right, on the painting.
    Row {
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.rightMargin: px(64)
        anchors.topMargin: px(56)
        spacing: px(12)
        Image {
            source: art + "mark.png"
            width: px(40); height: px(40)
            smooth: true
            mipmap: true
        }
        Text {
            horizontalAlignment: Text.AlignLeft
            text: "Monet"
            color: "#FFFFFF"
            font.family: serif
            font.weight: Font.Normal
            font.pixelSize: px(30)
            anchors.verticalCenter: parent.verticalCenter
        }
    }

    // The sheet's shadow (drawn in advance: tools/make-setup-art.py).
    BorderImage {
        x: glass.sheet.x - 120
        y: glass.sheet.y - 120
        width: glass.sheet.width + 240
        height: glass.sheet.height + 240
        source: art + "shadow.png"
        border { left: 160; right: 160; top: 160; bottom: 160 }
    }

    // The glass sheet: the painting blurred, a white wash and a bright edge.
    Canvas {
        id: glass
        anchors.fill: parent
        readonly property rect sheet: Qt.rect(px(64), px(64), px(540), win.height - px(128))
        readonly property string blurred: art + "glass.jpg"
        Component.onCompleted: loadImage(blurred)
        onImageLoaded: requestPaint()
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()

        function rounded(ctx, r, radius) {
            ctx.beginPath()
            ctx.moveTo(r.x + radius, r.y)
            ctx.arcTo(r.x + r.width, r.y, r.x + r.width, r.y + r.height, radius)
            ctx.arcTo(r.x + r.width, r.y + r.height, r.x, r.y + r.height, radius)
            ctx.arcTo(r.x, r.y + r.height, r.x, r.y, radius)
            ctx.arcTo(r.x, r.y, r.x + r.width, r.y, radius)
            ctx.closePath()
        }

        onPaint: {
            var ctx = getContext("2d")
            ctx.reset()
            ctx.clearRect(0, 0, width, height)
            var r = glass.sheet, radius = px(32)
            // The painting, blurred, lined up with the one behind it.
            ctx.save()
            rounded(ctx, r, radius)
            ctx.clip()
            if (isImageLoaded(blurred)) {
                var iw = 2560, ih = 1440
                var s = Math.max(width / iw, height / ih)
                ctx.drawImage(blurred, (width - iw * s) / 2, (height - ih * s) / 2, iw * s, ih * s)
            }
            var wash = ctx.createLinearGradient(0, r.y, 0, r.y + r.height)
            wash.addColorStop(0, Qt.rgba(1, 1, 1, 0.68))
            wash.addColorStop(1, Qt.rgba(1, 1, 1, 0.48))
            ctx.fillStyle = wash
            ctx.fillRect(r.x, r.y, r.width, r.height)
            ctx.restore()
            // A bright edge, brightest along the top.
            ctx.lineWidth = Math.max(1, u)
            ctx.strokeStyle = Qt.rgba(1, 1, 1, 0.55)
            rounded(ctx, Qt.rect(r.x + 0.5, r.y + 0.5, r.width - 1, r.height - 1), radius)
            ctx.stroke()
        }
    }

    // What's on the sheet.
    Item {
        id: sheetContent
        LayoutMirroring.enabled: setup.rtl
        LayoutMirroring.childrenInherit: true
        x: glass.sheet.x
        y: glass.sheet.y
        width: glass.sheet.width
        height: glass.sheet.height

        Item {
            id: page
            anchors.fill: parent
            anchors.leftMargin: px(48)
            anchors.rightMargin: px(48)
            anchors.topMargin: px(48)
            anchors.bottomMargin: px(36)

            Loader {
                id: stepLoader
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: footer.top
                anchors.bottomMargin: px(16)
                sourceComponent: !installing ? [helloStep, wifiStep, personStep, appsStep, readyStep][step]
                               : showingKey ? keyStep : phase === "done" ? doneStep : phase === "failed" ? failedStep : progressStep
                onLoaded: rise.restart()
                ParallelAnimation {
                    id: rise
                    NumberAnimation { target: stepLoader.item; property: "opacity"; from: 0; to: 1; duration: 420; easing.type: Easing.OutCubic }
                    NumberAnimation { target: stepLoader.item; property: "y"; from: px(14); to: 0; duration: 420; easing.type: Easing.OutBack; easing.overshoot: 1.1 }
                }
            }

            // Where you are, and the way forward.
            RowLayout {
                id: footer
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: px(46)
                spacing: px(8)
                visible: !installing || phase === "done"

                Row {
                    spacing: px(6)
                    Layout.alignment: Qt.AlignVCenter
                    visible: !installing
                    Repeater {
                        model: 6
                        Rectangle {
                            required property int index
                            height: px(5)
                            width: index === Math.min(step, 5) ? px(28) : px(10)
                            radius: height / 2
                            color: index === Math.min(step, 5) ? sun : Qt.rgba(27 / 255, 26 / 255, 25 / 255, 0.18)
                            Behavior on width { NumberAnimation { duration: 300; easing.type: Easing.OutBack } }
                        }
                    }
                }
                Item { Layout.fillWidth: true }
                PillButton {
                    text: tr("Back")
                    plain: true
                    visible: step > 0 && !installing
                    onClicked: step = step - 1
                }
                PillButton {
                    id: next
                    text: showingKey ? tr("Continue") : installing ? tr("Restart")
                        : step === 4 ? (setup.mode === "erase" ? tr("Erase & Install") : tr("Install"))
                        : stepLoader.item && stepLoader.item.busy ? stepLoader.item.busyText : tr("Continue")
                    accent: step === 4 && !installing
                    enabled: showingKey ? !!stepLoader.item && stepLoader.item.ready === true
                        : installing || (stepLoader.item && stepLoader.item.ready === true && !stepLoader.item.busy)
                    onClicked: {
                        if (showingKey) { keyKept = true; return }
                        if (installing) { setup.restart(); return }
                        var item = stepLoader.item
                        if (item.leave && !item.leave())
                            return
                        if (step === 4) { setup.install(); step = 5 } else step = step + 1
                    }
                }
            }
        }
    }

    // ---- Steps ----

    Component {
        id: helloStep
        Column {
            property bool ready: true
            property bool busy: false
            function leave() { return !setup.applyKeyboard() }
            spacing: px(22)
            // Room for the note about an installed Monet that can't start, when there is one.
            Title { text: tr("Hello"); big: true; topPadding: setup.untrusted ? 0 : px(40) }
            Body { text: tr("Let's set up Monet. It takes about 15 minutes, and Windows sets itself up afterwards."); visible: !setup.untrusted }
            Field {
                label: tr("Language")
                Choice {
                    width: parent.width
                    model: setup.languages
                    currentIndex: setup.language
                    onActivated: (i) => setup.setLanguage(i)
                }
            }
            Field {
                label: tr("Keyboard")
                Choice {
                    width: parent.width
                    model: setup.keyboards
                    currentIndex: setup.keyboard
                    onActivated: (i) => setup.setKeyboard(i)
                }
            }
            // A region, then a city in it (as Fedora's installer asks): guessed from the
            // language, then from where the PC is once it's online, unless chosen.
            Field {
                label: tr("Time zone")
                Row {
                    width: parent.width
                    spacing: px(10)
                    Choice {
                        width: Math.round((parent.width - parent.spacing) * 0.42)
                        model: setup.regions
                        currentIndex: setup.region
                        onActivated: (i) => setup.setRegion(i)
                    }
                    Choice {
                        width: parent.width - parent.spacing - Math.round((parent.width - parent.spacing) * 0.42)
                        model: setup.cities
                        currentIndex: setup.city
                        onActivated: (i) => setup.setCity(i)
                    }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    opacity: setup.zoneNow !== "" ? 1 : 0     // keeps its place, so nothing jumps
                    text: tr("It's %1 there now", setup.zoneNow)
                    font.family: sans; font.pixelSize: px(12); color: dim
                }
            }
            // A PC Monet can't run on hears it now, not after the questions.
            Note { text: setup.pcBlocker; warm: true; visible: text !== "" }
            // Monet is installed here but can't start: its first start's blue screen was skipped.
            Note {
                visible: setup.untrusted
                warm: true
                text: tr("Monet is already installed on this PC, but it can't start yet: the blue screen at its first start was skipped. Monet can ask again. Restart, and on the blue screen choose Enroll MOK, then Continue and Yes, type monetsetup, and choose Reboot.")
            }
            PillButton {
                visible: setup.untrusted
                text: tr("Ask again and restart")
                onClicked: setup.trustAndRestart()
            }
        }
    }

    Component {
        id: wifiStep
        Column {
            id: wifiPage
            spacing: px(22)
            property string chosen: setup.joined || (setup.networks.length ? setup.networks[0].name : "")
            readonly property var chosenNet: setup.networks.find(n => n.name === chosen) || null
            readonly property bool needsPassword: chosenNet && chosenNet.secure && chosen !== setup.joined
            property bool ready: setup.wired || setup.joined !== "" || chosen !== ""
            property bool busy: setup.joining
            property string busyText: tr("Connecting…")
            property bool waiting: false

            // Continue joins the chosen network first, then moves on.
            function leave() {
                if (setup.wired || (chosen === setup.joined && chosen !== ""))
                    return true
                waiting = true
                setup.join(chosen, password.text)
                return false
            }
            Connections {
                target: setup
                function onWifiChanged() {
                    if (wifiPage.waiting && !setup.joining) {
                        wifiPage.waiting = false
                        if (setup.joined === wifiPage.chosen && setup.wifiError === "")
                            step = 2
                    }
                }
            }

            Title { text: setup.wired ? tr("You're online") : tr("Connect to Wi-Fi") }
            Body { text: tr("Monet downloads itself and Windows while it installs. Windows will use this network too.") }
            Card {
                visible: setup.wired
                height: px(64)
                Row {
                    anchors.verticalCenter: parent.verticalCenter
                    x: px(16)
                    spacing: px(14)
                    Glyph { kind: "cable"; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: tr("Connected with a cable"); font.family: sans; font.pixelSize: px(15); font.weight: Font.Medium; color: ink }
                }
            }
            Card {
                visible: !setup.wired
                height: Math.min(list.contentHeight, px(4 * 52)) + px(12)
                ListView {
                    id: list
                    anchors.fill: parent
                    anchors.margins: px(6)
                    clip: true
                    model: setup.networks
                    spacing: px(2)
                    boundsBehavior: Flickable.StopAtBounds
                    delegate: Option {
                        required property var modelData
                        width: list.width
                        height: px(50)
                        picked: modelData.name === wifiPage.chosen
                        onClicked: wifiPage.chosen = modelData.name
                        Glyph { kind: "wifi"; strength: modelData.signal; Layout.alignment: Qt.AlignVCenter }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            Layout.fillWidth: true
                            text: modelData.name
                            elide: Text.ElideRight
                            font.family: sans; font.pixelSize: px(15); font.weight: Font.Medium; color: ink
                        }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            text: modelData.name === setup.joined ? tr("Connected") : modelData.secure ? tr("Secured")
                                : trc("a Wi-Fi network anyone can join, without a password", "Open")
                            font.family: sans; font.pixelSize: px(12); color: dim
                        }
                    }
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    anchors.centerIn: parent
                    visible: list.count === 0
                    text: setup.scanning ? tr("Looking for networks…") : tr("No networks found")
                    font.family: sans; font.pixelSize: px(14); color: dim
                }
            }
            Field {
                label: tr("Password")
                visible: !setup.wired && wifiPage.needsPassword
                Entry {
                    id: password
                    width: parent.width
                    secret: true
                    onAccepted: next.clicked()
                }
            }
            Note { text: setup.wifiError; warm: true; visible: text !== "" }
            Link {
                visible: !setup.wired
                text: setup.scanning ? tr("Looking…") : tr("Look again")
                onClicked: setup.scan()
            }
        }
    }

    Component {
        id: personStep
        Column {
            id: person
            spacing: px(22)
            // Any password, or none: it's theirs to choose. Twice, so a slip doesn't lock them out.
            readonly property bool mismatch: again.text !== "" && pass.text !== again.text
            readonly property bool none: pass.text === "" && again.text === "" && name.text.trim() !== ""
            property bool ready: name.text.trim() !== "" && pass.text === again.text
            property bool busy: false
            property string problem: ""
            function leave() {
                problem = setup.setPerson(name.text, pass.text, again.text)
                return problem === ""
            }
            Title { text: tr("Who's using this PC?") }
            Body { text: tr("This is your account in Monet and in Windows.") }
            Field {
                label: tr("Your name")
                Entry { id: name; width: parent.width; placeholder: tr("Name"); focus: true; text: setup.personName }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    opacity: name.text.trim() !== "" ? 1 : 0     // keeps its place, so nothing jumps
                    text: tr("You sign in as %1", setup.accountFor(name.text))
                    font.family: sans; font.pixelSize: px(12); color: dim
                }
            }
            Field {
                label: tr("Password")
                Entry { id: pass; width: parent.width; secret: true; text: setup.personPassword; onAccepted: again.forceActiveFocus() }
            }
            Field {
                label: tr("Password again")
                Entry { id: again; width: parent.width; secret: true; text: setup.personPassword; onAccepted: next.clicked() }
            }
            Note {
                text: person.mismatch ? tr("The passwords don't match.")
                    : person.none ? tr("No password: Monet signs you in by itself, and anyone who uses this PC can open your account and change its settings.")
                    : person.problem
                warm: true
                visible: text !== ""
            }
        }
    }

    // What's on the PC from the start: the everyday apps ticked, the rest to pick.
    // They arrive after the first sign-in; the Store has everything else.
    Component {
        id: appsStep
        Column {
            property bool ready: true
            property bool busy: false
            spacing: px(16)
            Title { text: tr("Your apps") }
            Body { text: tr("Photos, Documents, Video, Music and Calculator are built in. What you add arrives after you sign in.") }
            Repeater {
                model: [[trc("the apps people use every day", "Everyday"), true], [trc("more apps to choose from", "More"), false]]
                Column {
                    id: appSection
                    required property var modelData
                    width: parent.width
                    spacing: px(8)
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        text: appSection.modelData[0]
                        font.family: sans; font.pixelSize: px(13); font.weight: Font.DemiBold; color: ink
                    }
                    Grid {
                        width: parent.width
                        columns: 2
                        columnSpacing: px(8)
                        rowSpacing: px(8)
                        Repeater {
                            model: setup.apps.filter(app => app.everyday === appSection.modelData[1])
                            AbstractButton {
                                id: appTile
                                required property var modelData
                                // Built in: there already, nothing to choose.
                                readonly property bool builtIn: modelData.index < 0
                                width: (appSection.width - px(8)) / 2
                                height: px(54)
                                hoverEnabled: !builtIn
                                leftPadding: px(12)
                                rightPadding: px(10)
                                onClicked: if (!builtIn) setup.toggleApp(modelData.index)
                                Accessible.role: Accessible.CheckBox
                                Accessible.name: modelData.name
                                Accessible.checked: modelData.picked
                                background: Rectangle {
                                    radius: px(14)
                                    color: appTile.builtIn ? Qt.rgba(1, 1, 1, 0.5)
                                         : appTile.modelData.picked ? Qt.rgba(1, 1, 1, 0.85)
                                         : appTile.hovered ? Qt.rgba(1, 1, 1, 0.55) : Qt.rgba(1, 1, 1, 0.3)
                                    border.color: appTile.modelData.picked && !appTile.builtIn ? lily : "transparent"
                                    border.width: Math.max(2, px(2))
                                    Behavior on color { ColorAnimation { duration: 140 } }
                                }
                                contentItem: RowLayout {
                                    spacing: px(10)
                                    // The tick: lily when it's coming.
                                    Rectangle {
                                        Layout.preferredWidth: px(20)
                                        Layout.preferredHeight: px(20)
                                        radius: width / 2
                                        color: appTile.modelData.picked ? lily : "transparent"
                                        border.width: appTile.modelData.picked ? 0 : Math.max(1, px(1.5))
                                        border.color: Qt.rgba(27 / 255, 26 / 255, 25 / 255, 0.3)
                                        Shape {
                                            visible: appTile.modelData.picked
                                            anchors.centerIn: parent
                                            width: 24
                                            height: 24
                                            scale: px(12) / 24
                                            ShapePath {
                                                strokeColor: "#FFFFFF"
                                                strokeWidth: 3
                                                fillColor: "transparent"
                                                capStyle: ShapePath.RoundCap
                                                joinStyle: ShapePath.RoundJoin
                                                PathSvg { path: "M 5 12.4 L 9.8 17 L 19 7" }
                                            }
                                        }
                                    }
                                    Column {
                                        Layout.fillWidth: true
                                        spacing: px(1)
                                        Text {
                                            horizontalAlignment: Text.AlignLeft
                                            width: parent.width
                                            text: appTile.modelData.name
                                            elide: Text.ElideRight
                                            font.family: sans; font.pixelSize: px(14); font.weight: Font.DemiBold; color: ink
                                        }
                                        Text {
                                            horizontalAlignment: Text.AlignLeft
                                            width: parent.width
                                            text: appTile.modelData.detail
                                            elide: Text.ElideRight
                                            font.family: sans; font.pixelSize: px(12); color: dim
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: readyStep
        Column {
            spacing: px(22)
            readonly property bool ready: setup.blocker === ""
            property bool busy: false
            readonly property var disk: setup.disks.length ? setup.disks[Math.min(setup.disk, setup.disks.length - 1)] : null
            Title { text: tr("Ready to install") }
            Column {
                width: parent.width
                spacing: px(8)
                Option {
                    width: parent.width
                    height: px(78)
                    picked: setup.mode === "erase"
                    onClicked: setup.setMode("erase")
                    Image { source: art + "mark.png"; Layout.preferredWidth: px(36); Layout.preferredHeight: px(36); mipmap: true }
                    Column {
                        Layout.fillWidth: true
                        spacing: px(3)
                        Text { text: tr("Monet and Windows"); font.family: sans; font.pixelSize: px(15); font.weight: Font.DemiBold; color: ink }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            width: parent.width
                            text: tr("Erases this PC. Windows installs itself, only for games.")
                            wrapMode: Text.WordWrap
                            font.family: sans; font.pixelSize: px(13); lineHeight: px(18); lineHeightMode: Text.FixedHeight; color: dim
                        }
                    }
                }
                Option {
                    width: parent.width
                    height: px(78)
                    picked: setup.mode === "keep"
                    onClicked: setup.setMode("keep")
                    Image { source: art + "windows.png"; Layout.preferredWidth: px(36); Layout.preferredHeight: px(36); mipmap: true }
                    Column {
                        Layout.fillWidth: true
                        spacing: px(3)
                        Text { text: tr("Monet next to my Windows"); font.family: sans; font.pixelSize: px(15); font.weight: Font.DemiBold; color: ink }
                        Text {
                            horizontalAlignment: Text.AlignLeft
                            width: parent.width
                            text: tr("Keeps Windows and your files. Monet makes room for itself.")
                            wrapMode: Text.WordWrap
                            font.family: sans; font.pixelSize: px(13); lineHeight: px(18); lineHeightMode: Text.FixedHeight; color: dim
                        }
                    }
                }
            }
            Card {
                height: px(52)
                visible: setup.disks.length <= 1
                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: px(16)
                    anchors.rightMargin: px(16)
                    Text { text: tr("Disk"); font.family: sans; font.pixelSize: px(13); color: dim }
                    Item { Layout.fillWidth: true }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        text: disk ? disk.label : tr("Looking for disks…")
                        elide: Text.ElideRight
                        Layout.maximumWidth: px(330)
                        font.family: sans; font.pixelSize: px(13); font.weight: Font.DemiBold; color: ink
                    }
                }
            }
            Field {
                label: tr("Disk")
                visible: setup.disks.length > 1
                Choice {
                    width: parent.width
                    model: setup.disks.map(d => d.label)
                    currentIndex: setup.disk
                    onActivated: (i) => setup.setDisk(i)
                }
            }
            Note { text: setup.blocker; warm: true; visible: text !== "" }
            Note { text: setup.roomNote; visible: setup.blocker === "" && text !== "" }
            // Windows' files come along, copied into Monet's folders.
            Tick {
                width: parent.width
                visible: setup.blocker === "" && !!setup.files && setup.files.fits
                title: tr("Bring my files")
                detail: setup.files ? setup.files.text : ""
                checked: setup.bring
                onClicked: setup.setBring(!setup.bring)
            }
            // Encrypted, as Windows and Macs are: only on a PC whose security chip unlocks it by itself.
            Tick {
                width: parent.width
                visible: setup.blocker === "" && setup.tpm
                title: tr("Encrypt this PC")
                detail: tr("Only this PC can read its disk: taken out, it's locked. Monet unlocks it by itself when it starts.")
                checked: setup.encrypt
                onClicked: setup.setEncrypt(!setup.encrypt)
            }
            Note {
                text: setup.files ? setup.files.text : ""
                visible: setup.blocker === "" && !!setup.files && !setup.files.fits
            }
            Repeater {
                model: setup.blocker === "" ? setup.pcNotes : []
                Note { required property string modelData; text: modelData }
            }
            Note {
                text: tr("Everything on this disk is erased, Windows and your files too. To keep them, choose Monet next to my Windows.")
                warm: true
                visible: setup.blocker === "" && setup.mode === "erase" && disk !== null && disk.hasWindows
            }
        }
    }

    Component {
        id: progressStep
        Column {
            property bool ready: false
            property bool busy: false
            spacing: px(22)
            topPadding: px(70)
            Ripple { anchors.horizontalCenter: parent.horizontalCenter }
            Title { text: tr("Installing Monet"); anchors.horizontalCenter: parent.horizontalCenter }
            Bar { width: parent.width; value: setup.progress }
            Text {
                width: parent.width
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: setup.status
                font.family: sans; font.pixelSize: px(14); color: dim
            }
            Text {
                width: parent.width
                topPadding: px(24)
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
                text: tr("You can leave it running. If the connection drops, Monet picks up where it stopped.")
                font.family: sans; font.pixelSize: px(13); lineHeight: px(19); lineHeightMode: Text.FixedHeight; color: dim
            }
        }
    }

    Component {
        id: doneStep
        Column {
            property bool ready: true
            property bool busy: false
            spacing: px(22)
            Title { text: tr("All set"); big: true; topPadding: px(40) }
            Body {
                text: setup.mode === "erase"
                      ? tr("Take out the USB stick and restart. After you sign in, Monet gets Windows ready for your games by itself.")
                      : tr("Take out the USB stick and restart. Your PC starts in Monet, and Windows is one click away.")
            }
            // The blue screen at the first start: easy to skip by accident,
            // and then Secure Boot refuses Monet.
            Card {
                height: firstStart.implicitHeight + px(36)
                Column {
                    id: firstStart
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: px(18)
                    spacing: px(6)
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        width: parent.width
                        wrapMode: Text.WordWrap
                        text: tr("Once, when it first starts")
                        font.family: sans; font.pixelSize: px(15); font.weight: Font.DemiBold; color: ink
                    }
                    Body {
                        font.pixelSize: px(14)
                        text: trc("Enroll MOK, Continue, Yes, Reboot and monetsetup stay in English: the blue screen shows them that way", "A blue screen asks to trust Monet. With the arrow keys and Enter, choose Enroll MOK, then Continue and Yes, type monetsetup and choose Reboot. It opens on Continue boot: don't choose that, or Monet can't start.")
                    }
                    Body {
                        font.pixelSize: px(14)
                        text: tr("Take a photo of these steps with your phone first: this screen goes away when the PC restarts.")
                    }
                }
            }
        }
    }

    // An encrypted Monet's recovery key: shown once, before All set, and kept nowhere.
    Component {
        id: keyStep
        Column {
            readonly property bool ready: kept.checked
            property bool busy: false
            spacing: px(18)
            Title { text: tr("Your recovery key") }
            Body {
                text: tr("This PC's disk is encrypted, and Monet unlocks it by itself. If it ever can't, after a big firmware update or with the disk in another PC, it asks for this key. Without it nobody can read the disk, not even you.")
            }
            Card {
                height: recovery.implicitHeight + px(36)
                Text {
                    id: recovery
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.margins: px(18)
                    LayoutMirroring.enabled: false
                    horizontalAlignment: Text.AlignHCenter
                    textFormat: Text.PlainText
                    // Four groups to a line, as it's typed: dashes and all.
                    text: setup.recoveryKey.split("-").slice(0, 4).join("-") + "-\n" + setup.recoveryKey.split("-").slice(4).join("-")
                    font.family: "monospace"; font.pixelSize: px(18); lineHeight: px(28); lineHeightMode: Text.FixedHeight; color: ink
                }
            }
            Body {
                font.pixelSize: px(14)
                text: tr("Take a photo of it or write it down, and keep it somewhere other than this PC. It isn't shown again.")
            }
            Tick {
                id: kept
                width: parent.width
                checkable: true
                title: tr("I've kept my recovery key")
            }
        }
    }

    Component {
        id: failedStep
        Column {
            property bool ready: false
            property bool busy: false
            spacing: px(22)
            Title { text: tr("That didn't work") }
            Body { text: setup.error }
            Row {
                spacing: px(8)
                PillButton { text: tr("Try again"); onClicked: setup.retry() }
                PillButton { text: details.visible ? tr("Hide details") : tr("Details"); plain: true; onClicked: details.visible = !details.visible }
            }
            Card {
                id: details
                visible: false
                height: px(260)
                // Opens at the end, where why it stopped is.
                onVisibleChanged: if (visible) logView.toEnd()
                Flickable {
                    id: logView
                    anchors.fill: parent
                    anchors.margins: px(14)
                    clip: true
                    contentHeight: log.implicitHeight
                    function toEnd() { contentY = Math.max(0, contentHeight - height) }
                    onContentHeightChanged: toEnd()
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        id: log
                        width: parent.width
                        text: setup.details
                        wrapMode: Text.WrapAnywhere
                        font.family: "monospace"; font.pixelSize: px(11); color: ink
                    }
                }
            }
        }
    }

    // ---- Pieces ----

    component Title: Text {
        readonly property real u: Window.window ? Window.window.u : 1
        property bool big: false
        width: parent ? parent.width : implicitWidth
        wrapMode: Text.WordWrap
        color: "#1B1A19"
        font.family: "Fraunces 72pt SuperSoft"
        font.weight: Font.Light
        font.pixelSize: Math.round((big ? 76 : 40) * u)
        font.letterSpacing: (big ? -3 : -0.8) * u
        lineHeight: big ? 1.0 : 1.1
    }

    component Body: Text {
        readonly property real u: Window.window ? Window.window.u : 1
        width: parent ? parent.width : implicitWidth
        wrapMode: Text.WordWrap
        color: Qt.rgba(27 / 255, 26 / 255, 25 / 255, 0.64)
        font.family: "Inter"
        font.pixelSize: Math.round(16 * u)
        lineHeight: Math.round(24 * u)
        lineHeightMode: Text.FixedHeight
    }

    component Note: Rectangle {
        readonly property real u: Window.window ? Window.window.u : 1
        property alias text: noteText.text
        property bool warm: false
        width: parent ? parent.width : 0
        height: noteText.implicitHeight + Math.round(24 * u)
        radius: Math.round(14 * u)
        color: warm ? Qt.rgba(251 / 255, 231 / 255, 207 / 255, 0.85) : Qt.rgba(1, 1, 1, 0.55)
        Text {
            horizontalAlignment: Text.AlignLeft
            id: noteText
            anchors.fill: parent
            anchors.margins: Math.round(12 * u)
            anchors.leftMargin: Math.round(16 * u)
            verticalAlignment: Text.AlignVCenter
            wrapMode: Text.WordWrap
            color: "#1B1A19"
            font.family: "Inter"
            font.pixelSize: Math.round(13 * u)
            lineHeight: Math.round(19 * u)
            lineHeightMode: Text.FixedHeight
        }
    }

    component Field: Column {
        readonly property real u: Window.window ? Window.window.u : 1
        property string label
        default property alias content: holder.data
        width: parent ? parent.width : 0
        spacing: Math.round(6 * u)
        Text {
            horizontalAlignment: Text.AlignLeft
            text: label
            color: "#1B1A19"
            font.family: "Inter"
            font.pixelSize: Math.round(13 * u)
            font.weight: Font.DemiBold
        }
        Column {
            id: holder
            width: parent.width
            spacing: Math.round(6 * u)
        }
    }

    component Card: Rectangle {
        readonly property real u: Window.window ? Window.window.u : 1
        width: parent ? parent.width : 0
        radius: Math.round(18 * u)
        color: Qt.rgba(1, 1, 1, 0.55)
        border.color: Qt.rgba(27 / 255, 26 / 255, 25 / 255, 0.05)
        border.width: 1
    }

    component Option: AbstractButton {
        id: option
        readonly property real u: Window.window ? Window.window.u : 1
        property bool picked: false
        default property alias content: row.data
        hoverEnabled: true
        background: Rectangle {
            radius: Math.round(16 * u)
            color: option.picked ? Qt.rgba(1, 1, 1, 0.85) : option.hovered ? Qt.rgba(1, 1, 1, 0.5) : "transparent"
            border.color: option.picked ? "#357F72" : "transparent"
            border.width: Math.max(2, Math.round(2 * u))
            Behavior on color { ColorAnimation { duration: 140 } }
        }
        contentItem: RowLayout {
            id: row
            spacing: Math.round(14 * u)
        }
        leftPadding: Math.round(16 * u)
        rightPadding: Math.round(16 * u)
    }

    // A choice to tick: a pebble of paper with a lily ring, and the check in a lily dot.
    component Tick: AbstractButton {
        id: tick
        readonly property real u: Window.window ? Window.window.u : 1
        property string title
        property string detail
        height: Math.round((detail !== "" ? 68 : 52) * u)
        hoverEnabled: true
        leftPadding: Math.round(16 * u)
        rightPadding: Math.round(16 * u)
        Accessible.role: Accessible.CheckBox
        Accessible.name: title
        Accessible.checked: checked
        background: Rectangle {
            radius: Math.round(16 * tick.u)
            color: tick.checked ? Qt.rgba(1, 1, 1, 0.85) : tick.hovered ? Qt.rgba(1, 1, 1, 0.55) : Qt.rgba(1, 1, 1, 0.3)
            border.color: tick.checked ? "#357F72" : "transparent"
            border.width: Math.max(2, Math.round(2 * tick.u))
            Behavior on color { ColorAnimation { duration: 140 } }
        }
        contentItem: RowLayout {
            spacing: Math.round(12 * tick.u)
            Rectangle {
                Layout.preferredWidth: Math.round(20 * tick.u)
                Layout.preferredHeight: Math.round(20 * tick.u)
                radius: width / 2
                color: tick.checked ? "#357F72" : "transparent"
                border.width: tick.checked ? 0 : Math.max(1, Math.round(1.5 * tick.u))
                border.color: Qt.rgba(27 / 255, 26 / 255, 25 / 255, 0.3)
                Shape {
                    visible: tick.checked
                    anchors.centerIn: parent
                    width: 24
                    height: 24
                    scale: Math.round(12 * tick.u) / 24
                    ShapePath {
                        strokeColor: "#FFFFFF"
                        strokeWidth: 3
                        fillColor: "transparent"
                        capStyle: ShapePath.RoundCap
                        joinStyle: ShapePath.RoundJoin
                        PathSvg { path: "M 5 12.4 L 9.8 17 L 19 7" }
                    }
                }
            }
            Column {
                Layout.fillWidth: true
                spacing: Math.round(2 * tick.u)
                Text {
                    text: tick.title
                    font.family: "Inter"; font.pixelSize: Math.round(14 * tick.u); font.weight: Font.DemiBold; color: "#1B1A19"
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    width: parent.width
                    visible: tick.detail !== ""
                    text: tick.detail
                    wrapMode: Text.WordWrap
                    font.family: "Inter"; font.pixelSize: Math.round(12 * tick.u)
                    lineHeight: Math.round(16 * tick.u); lineHeightMode: Text.FixedHeight
                    color: Qt.rgba(27 / 255, 26 / 255, 25 / 255, 0.64)
                }
            }
        }
    }

    component PillButton: AbstractButton {
        id: pill
        readonly property real u: Window.window ? Window.window.u : 1
        property bool accent: false
        property bool plain: false
        hoverEnabled: true
        implicitHeight: Math.round(46 * u)
        implicitWidth: caption.implicitWidth + 2 * Math.round((plain ? 18 : 24) * u)
        opacity: enabled ? 1 : 0.45
        scale: pressed ? 0.97 : hovered && !plain ? 1.03 : 1
        Behavior on scale { NumberAnimation { duration: 160; easing.type: Easing.OutBack } }
        background: Rectangle {
            radius: height / 2
            color: pill.plain ? (pill.hovered ? Qt.rgba(1, 1, 1, 0.45) : "transparent")
                 : pill.accent ? (pill.hovered ? "#FF6A42" : "#F2552C")
                 : (pill.hovered ? "#34322E" : "#1C1B19")
        }
        contentItem: Text {
            id: caption
            text: pill.text
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            color: pill.plain ? Qt.rgba(27 / 255, 26 / 255, 25 / 255, 0.7) : "#FFFFFF"
            font.family: "Inter"
            font.pixelSize: Math.round(15 * u)
            font.weight: Font.DemiBold
        }
    }

    component Link: AbstractButton {
        id: link
        readonly property real u: Window.window ? Window.window.u : 1
        hoverEnabled: true
        contentItem: Text {
            horizontalAlignment: Text.AlignLeft
            text: link.text
            color: link.hovered ? "#1F5249" : "#2A6A5F"
            font.family: "Inter"
            font.pixelSize: Math.round(13 * u)
            font.weight: Font.DemiBold
        }
        background: null
    }

    component Entry: TextField {
        id: entry
        readonly property real u: Window.window ? Window.window.u : 1
        property bool secret: false
        property string placeholder: ""
        property bool shown: false
        placeholderText: placeholder
        echoMode: secret && !shown ? TextInput.Password : TextInput.Normal
        implicitHeight: Math.round(44 * u)
        leftPadding: Math.round(14 * u)
        rightPadding: secret ? Math.round(64 * u) : Math.round(14 * u)
        color: "#1B1A19"
        placeholderTextColor: Qt.rgba(27 / 255, 26 / 255, 25 / 255, 0.4)
        selectionColor: "#357F72"
        selectedTextColor: "#FFFFFF"
        font.family: "Inter"
        font.pixelSize: Math.round(15 * u)
        background: Rectangle {
            radius: Math.round(13 * u)
            color: Qt.rgba(1, 1, 1, 0.75)
            border.color: entry.activeFocus ? "#357F72" : Qt.rgba(27 / 255, 26 / 255, 25 / 255, 0.08)
            border.width: entry.activeFocus ? Math.max(2, Math.round(2 * u)) : 1
        }
        AbstractButton {
            visible: entry.secret && entry.text !== ""
            anchors.right: parent.right
            anchors.rightMargin: Math.round(14 * u)
            anchors.verticalCenter: parent.verticalCenter
            onClicked: entry.shown = !entry.shown
            contentItem: Text {
                horizontalAlignment: Text.AlignLeft
                text: (setup.lang, entry.shown ? setup.say("Hide", "") : setup.say("Show", ""))
                color: "#2A6A5F"
                font.family: "Inter"
                font.pixelSize: Math.round(12 * u)
                font.weight: Font.DemiBold
            }
            background: null
        }
    }

    component Choice: ComboBox {
        id: choice
        readonly property real u: Window.window ? Window.window.u : 1
        implicitHeight: Math.round(44 * u)
        font.family: "Inter"
        font.pixelSize: Math.round(15 * u)
        background: Rectangle {
            radius: Math.round(13 * u)
            color: Qt.rgba(1, 1, 1, 0.75)
            border.color: choice.activeFocus || choice.popup.visible ? "#357F72" : Qt.rgba(27 / 255, 26 / 255, 25 / 255, 0.08)
            border.width: choice.activeFocus || choice.popup.visible ? Math.max(2, Math.round(2 * u)) : 1
        }
        contentItem: Text {
            horizontalAlignment: Text.AlignLeft
            leftPadding: Math.round(14 * u)
            text: choice.displayText
            font: choice.font
            color: "#1B1A19"
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
        indicator: Shape {
            x: choice.width - width - Math.round(16 * u)
            y: (choice.height - height) / 2
            width: Math.round(10 * u)
            height: Math.round(6 * u)
            ShapePath {
                strokeColor: Qt.rgba(27 / 255, 26 / 255, 25 / 255, 0.6)
                strokeWidth: Math.max(1.5, 1.6 * u)
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                startX: 0; startY: 0
                PathLine { x: Math.round(5 * u); y: Math.round(6 * u) }
                PathLine { x: Math.round(10 * u); y: 0 }
            }
        }
        delegate: ItemDelegate {
            required property int index
            required property var modelData
            width: choice.width - Math.round(12 * u)
            height: Math.round(40 * u)
            highlighted: choice.highlightedIndex === index
            contentItem: Text {
                horizontalAlignment: Text.AlignLeft
                leftPadding: Math.round(8 * u)
                text: modelData
                color: "#1B1A19"
                font: choice.font
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
            }
            background: Rectangle {
                radius: Math.round(10 * u)
                color: index === choice.currentIndex ? Qt.rgba(53 / 255, 127 / 255, 114 / 255, 0.16)
                     : highlighted ? Qt.rgba(27 / 255, 26 / 255, 25 / 255, 0.06) : "transparent"
            }
        }
        popup: Popup {
            y: choice.height + Math.round(6 * u)
            width: choice.width
            height: Math.min(contentItem.implicitHeight + 2 * Math.round(6 * u), Math.round(320 * u))
            padding: Math.round(6 * u)
            contentItem: ListView {
                clip: true
                implicitHeight: contentHeight
                model: choice.popup.visible ? choice.delegateModel : null
                currentIndex: choice.highlightedIndex
                boundsBehavior: Flickable.StopAtBounds
            }
            background: Rectangle {
                radius: Math.round(14 * u)
                color: "#FBFAF7"
                border.color: Qt.rgba(27 / 255, 26 / 255, 25 / 255, 0.10)
            }
        }
    }

    component Bar: Rectangle {
        readonly property real u: Window.window ? Window.window.u : 1
        property real value: 0
        height: Math.round(6 * u)
        radius: height / 2
        color: Qt.rgba(27 / 255, 26 / 255, 25 / 255, 0.10)
        Rectangle {
            width: Math.max(parent.height, parent.width * Math.max(0, Math.min(1, parent.value)))
            height: parent.height
            radius: parent.radius
            gradient: Gradient {
                orientation: Gradient.Horizontal
                GradientStop { position: 0; color: "#357F72" }
                GradientStop { position: 1; color: "#4DB4A0" }
            }
            Behavior on width { NumberAnimation { duration: 600; easing.type: Easing.OutCubic } }
        }
    }

    // The sun over the water, its reflection breathing while Monet installs.
    component Ripple: Item {
        readonly property real u: Window.window ? Window.window.u : 1
        width: Math.round(112 * u)
        height: width
        readonly property real k: width / 128
        Rectangle {
            x: (64 - 27) * parent.k; y: (44 - 27) * parent.k
            width: 54 * parent.k; height: width; radius: width / 2
            color: "#F2552C"
        }
        Repeater {
            model: [[26, 80, 76, 10, 0.9], [34, 95, 54, 8, 0.66], [51, 108, 30, 6.5, 0.42]]
            Rectangle {
                required property var modelData
                required property int index
                x: modelData[0] * parent.k; y: modelData[1] * parent.k
                width: modelData[2] * parent.k; height: modelData[3] * parent.k
                radius: height / 2
                color: "#F2552C"
                opacity: modelData[4]
                transform: Scale {
                    id: sx
                    origin.x: modelData[2] * parent.k / 2
                    xScale: 1
                }
                SequentialAnimation {
                    running: true
                    loops: Animation.Infinite
                    PauseAnimation { duration: index * 180 }
                    ParallelAnimation {
                        NumberAnimation { target: sx; property: "xScale"; to: 1.18; duration: 800; easing.type: Easing.InOutSine }
                    }
                    NumberAnimation { target: sx; property: "xScale"; to: 1; duration: 800; easing.type: Easing.InOutSine }
                }
            }
        }
    }

    // Small line icons on a 24-unit grid: Wi-Fi (with its strength) and a cable.
    component Glyph: Item {
        id: glyph
        readonly property real u: Window.window ? Window.window.u : 1
        readonly property real size: Math.round(20 * u)
        property string kind: "wifi"
        property int strength: 100
        implicitWidth: size
        implicitHeight: size
        Shape {
            width: 24
            height: 24
            transform: Scale { xScale: glyph.size / 24; yScale: glyph.size / 24 }
            ShapePath {
                strokeColor: "#1B1A19"
                strokeWidth: 2
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                joinStyle: ShapePath.RoundJoin
                PathSvg { path: kind === "wifi" ? "M 8.5 16 A 5 5 0 0 1 15.5 16" : "M 8 3 L 8 8 M 16 3 L 16 8 M 5 8 L 19 8 L 19 12 A 7 7 0 0 1 5 12 Z M 12 19 L 12 22" }
            }
            ShapePath {
                strokeColor: Qt.rgba(27 / 255, 26 / 255, 25 / 255, kind === "wifi" && strength < 45 ? 0.25 : 1)
                strokeWidth: 2
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                PathSvg { path: kind === "wifi" ? "M 5 12.5 A 10 10 0 0 1 19 12.5" : "M 12 12 L 12 12" }
            }
            ShapePath {
                strokeColor: Qt.rgba(27 / 255, 26 / 255, 25 / 255, kind === "wifi" && strength < 70 ? 0.25 : 1)
                strokeWidth: 2
                fillColor: "transparent"
                capStyle: ShapePath.RoundCap
                PathSvg { path: kind === "wifi" ? "M 2 9 A 15 15 0 0 1 22 9" : "M 12 12 L 12 12" }
            }
        }
    }
}
