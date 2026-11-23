// Loaded by the Settings page loader; shares its window context.
import QtCore
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Dialogs
import QtQuick.Effects
import QtQuick.Layouts
import QtQuick.Templates as T
import QtQuick.Window
import org.kde.kirigami as Kirigami
import "../games" as Shared
import "FocusNavigation.js" as FocusNavigation


ColumnLayout {
    spacing: 20
    SettingsControls.PageTitle {
        tone: look
        entry: sheet.entry("light")
        art: sheet.art
        text: i18n("Light & Wallpaper")
        detail: i18n("How Monet looks, and when it changes.")
    }
    SettingsControls.ChoiceGrid {
        Repeater {
            model: [
                ["hours", i18n("Follow the hours"), i18n("Mist by day, smoke after dark")],
                // The colors stay; the painting can still follow the day (Through the day).
                ["mist", i18n("Mist"), i18n("Light colors all day")],
                ["smoke", i18n("Smoke"), i18n("Dark colors all day")]
            ]
            Rectangle {
                id: choice
                objectName: "lightChoice-" + modelData[0]
                readonly property bool picked: (sheet.info.light || "hours") === modelData[0]
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                implicitHeight: choiceColumn.implicitHeight + 20
                radius: 18
                color: picked ? Qt.rgba(0.302, 0.706, 0.627, 0.1) : choiceHover.hovered ? look.wash2 : look.wash
                border.width: picked || activeFocus ? 2 : 1
                border.color: picked || activeFocus ? look.lily : look.line
                scale: choiceTap.pressed ? 0.98 : 1
                activeFocusOnTab: true
                Keys.onSpacePressed: sheet.chooseLight(modelData[0])
                Keys.onReturnPressed: sheet.chooseLight(modelData[0])
                Keys.onEnterPressed: sheet.chooseLight(modelData[0])
                Behavior on scale { NumberAnimation { duration: Math.round(160 * sheet.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
                Behavior on color { ColorAnimation { duration: Math.round(160 * sheet.speed) } }
                ColumnLayout {
                    id: choiceColumn
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 10
                    spacing: 3
                    Image {
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.round(width * 236 / 480)
                        Layout.bottomMargin: 7
                        source: sheet.art + "light-" + modelData[0] + ".png"
                        smooth: true
                        mipmap: true
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        Layout.leftMargin: 4
                        text: modelData[1]
                        color: look.ink
                        font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
                        font.weight: Font.DemiBold
                        wrapMode: Text.Wrap
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        Layout.leftMargin: 4
                        text: modelData[2]
                        color: look.dim
                        font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                        wrapMode: Text.Wrap
                    }
                }
                HoverHandler { id: choiceHover }
                TapHandler {
                    id: choiceTap
                    onTapped: sheet.chooseLight(modelData[0])
                }
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData[1]
                Accessible.description: modelData[2]
                Accessible.checked: picked
                Accessible.onPressAction: sheet.chooseLight(modelData[0])
            }
        }
    }
    // The painting on the wall: one of Monet's series, each in the same four lights.
    SettingsControls.Caption {
        tone: look
        text: i18n("Painting")
    }
    // Keep room for the painting and its full caption at larger text sizes.
    SettingsControls.ChoiceGrid {
        optionCount: 6
        Repeater {
            model: [
                ["hours", i18n("The Hours"), i18n("The harbor at Le Havre")],
                ["lilies", i18n("Water Lilies"), i18n("The pond at Giverny")],
                ["haystacks", i18n("Haystacks"), i18n("A field after the harvest")],
                ["magpie", i18n("The Magpie"), i18n("A farm under snow")],
                ["seasons", i18n("Through the year"), i18n("Each season its painting")],
                ["photo", i18n("Your photo"), i18n("A photo of yours, painted")]
            ]
            Rectangle {
                id: seriesChoice
                objectName: "seriesChoice-" + modelData[0]
                readonly property bool picked: (sheet.prefs.series || "hours") === modelData[0]
                Layout.fillWidth: true
                Layout.fillHeight: true
                Layout.preferredWidth: 1
                implicitHeight: seriesColumn.implicitHeight + 20
                radius: 18
                color: picked ? Qt.rgba(0.302, 0.706, 0.627, 0.1) : seriesHover.hovered ? look.wash2 : look.wash
                border.width: picked || activeFocus ? 2 : 1
                border.color: picked || activeFocus ? look.lily : look.line
                scale: seriesTap.pressed ? 0.98 : 1
                activeFocusOnTab: true
                Keys.onSpacePressed: sheet.chooseSeries(modelData[0])
                Keys.onReturnPressed: sheet.chooseSeries(modelData[0])
                Keys.onEnterPressed: sheet.chooseSeries(modelData[0])
                Behavior on scale { NumberAnimation { duration: Math.round(160 * sheet.speed); easing.type: Easing.Bezier; easing.bezierCurve: [0.2, 0.9, 0.25, 1.25, 1, 1] } }
                Behavior on color { ColorAnimation { duration: Math.round(160 * sheet.speed) } }
                ColumnLayout {
                    id: seriesColumn
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    anchors.margins: 10
                    spacing: 3
                    Image {
                        id: seriesArt
                        Layout.fillWidth: true
                        Layout.preferredHeight: Math.max(Math.round(width * 236 / 480),
                            modelData[0] === "photo" ? photoPlaceholder.implicitHeight + 16 : 0)
                        Layout.bottomMargin: 7
                        source: modelData[0] !== "photo" ? sheet.art + "series-" + modelData[0] + ".png"
                            : sheet.photoInfo.preview || ""
                        smooth: true
                        mipmap: true
                        // No photo painted yet (or one on the way): an empty frame to fill.
                        Rectangle {
                            anchors.fill: parent
                            visible: modelData[0] === "photo" && (seriesArt.status !== Image.Ready || sheet.photoInfo.state === "painting")
                            radius: 12
                            color: look.wash2
                            border.width: 1
                            border.color: look.line
                            Column {
                                id: photoPlaceholder
                                anchors.centerIn: parent
                                width: Math.max(0, parent.width - 12)
                                spacing: 6
                                Kirigami.Icon {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    width: 28
                                    height: 28
                                    source: "folder-pictures"
                                    opacity: 0.8
                                }
                                Text {
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    width: parent.width
                                    horizontalAlignment: Text.AlignHCenter
                                    wrapMode: Text.Wrap
                                    text: sheet.photoInfo.state === "painting"
                                        ? i18n("Painting… %1%", sheet.photoInfo.percent || 0) : i18n("Choose a photo…")
                                    color: look.dim
                                    font.pixelSize: Math.max(14, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 2)
                                }
                            }
                        }
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        Layout.leftMargin: 4
                        text: modelData[1]
                        color: look.ink
                        font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
                        font.weight: Font.DemiBold
                        wrapMode: Text.Wrap
                    }
                    Text {
                        horizontalAlignment: Text.AlignLeft
                        Layout.fillWidth: true
                        Layout.leftMargin: 4
                        text: modelData[2]
                        color: look.dim
                        font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                        wrapMode: Text.Wrap
                    }
                }
                HoverHandler { id: seriesHover }
                TapHandler {
                    id: seriesTap
                    onTapped: sheet.chooseSeries(modelData[0])
                }
                Accessible.role: Accessible.RadioButton
                Accessible.name: modelData[1]
                Accessible.description: modelData[2]
                Accessible.checked: picked
                Accessible.onPressAction: sheet.chooseSeries(modelData[0])
            }
        }
    }
    SettingsControls.Card {
        tone: look
        visible: sheet.photoInfo.state !== "" || sheet.photoInfo.failed === true
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Your photo")
            detail: sheet.photoInfo.state === "painting"
                ? i18n("Monet is painting it in the four lights: %1%. It goes on the wall by itself when it's done.", sheet.photoInfo.percent || 0)
                : sheet.photoInfo.failed === true ? i18n("That picture couldn't be painted. Try a JPEG or PNG photo.")
                : i18n("Painted in Monet's hand, in the same four lights as The Hours.")
            SettingsControls.Pill {
                tone: look
                enabledPill: sheet.photoInfo.state !== "painting"
                text: sheet.photoInfo.state === "ready" ? i18n("Another photo…") : i18n("Choose a photo…")
                onClicked: photoPicker.open()
            }
        }
    }
    SettingsControls.Card {
        tone: look
        Repeater {
            model: [
                ["hours", i18n("Through the day"), i18n("The painting's light follows the sun where you are, from dawn to night")],
                ["weather", i18n("Weather"), i18n("Rain, fog and snow where you are soften the painting with mist")],
                ["placard", i18n("Placard"), i18n("The time and the painting's name on the desktop")],
                ["snap", i18n("Snap layouts"), i18n("Drag a window to the top of the screen for its layouts, and Snap Assist fills the rest. Off, an edge still gives it half the screen and the top all of it")],
                ["titles", i18n("Title bars appear when you point at the top"), i18n("Windows go without a title bar until you move the pointer to the top of one. Then it slides down, with the buttons. Off, every window keeps its glass title bar")]
            ]
            SettingsControls.SettingRow {
                tone: look
                divider: index > 0
                tappable: true
                title: modelData[1]
                detail: modelData[2]
                onTapped: sheet.pref(modelData[0])
                SettingsControls.Switch {
                    tone: look
                    active: sheet.prefs[modelData[0]] !== false
                }
            }
        }
        // How see-through panels, windows and widgets are: four steps from none to clear.
        Item {
            id: glassRow
            readonly property var levels: ["solid", "matte", "frosted", "clear"]
            readonly property var names: [i18nc("how see-through Monet's glass is", "Solid"), i18nc("how see-through Monet's glass is", "Matte"), i18nc("how see-through Monet's glass is", "Frosted"), i18nc("how see-through Monet's glass is", "Clear")]
            readonly property int step: Math.max(0, levels.indexOf(sheet.prefs.glass))
            Layout.fillWidth: true
            implicitHeight: glassColumn.implicitHeight + 32
            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: 18
                anchors.rightMargin: 18
                height: 1
                color: look.line
            }
            ColumnLayout {
                id: glassColumn
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.leftMargin: 18
                anchors.rightMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                spacing: 3
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: i18n("Glass")
                    color: look.ink
                    font.pixelSize: Math.max(16, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) + 0)
                    font.weight: Font.DemiBold
                }
                Text {
                    horizontalAlignment: Text.AlignLeft
                    Layout.fillWidth: true
                    text: [i18n("No glass: panels, windows and widgets on paper. Lighter on older PCs."),
                           i18n("Matte glass: the painting's color comes through, its strokes don't. Calm, and easy to read."),
                           i18n("Frosted glass: the painting's light and color, softened."),
                           i18n("Clear glass: the painting shows through panels, windows and widgets.")][glassRow.step]
                    color: look.dim
                    font.pixelSize: Math.max(15, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 1)
                    wrapMode: Text.Wrap
                }
                SettingsControls.Slide {
                    id: glassSlider
                    tone: look
                    Layout.fillWidth: true
                    Layout.topMargin: 8
                    from: 0
                    to: 3
                    stepSize: 1
                    snapMode: T.Slider.SnapAlways
                    value: glassRow.step
                    Accessible.name: i18n("Glass")
                    Accessible.description: glassRow.names[glassRow.step]
                    // Dressing the desktop takes a moment: once it's let go, not at every step dragged past.
                    onPressedChanged: if (!pressed) sheet.chooseGlass(glassRow.levels[Math.round(value)])
                    onMoved: if (!pressed) sheet.chooseGlass(glassRow.levels[Math.round(value)])
                }
                // Each step's name under its place on the slider.
                Item {
                    Layout.fillWidth: true
                    implicitHeight: 18
                    Repeater {
                        model: glassRow.names
                        Text {
                            readonly property real at: glassSlider.leftPadding + glassSlider.handle.width / 2
                                + (glassSlider.availableWidth - glassSlider.handle.width) * index / 3
                            x: Math.max(0, Math.min(parent.width - width, at - width / 2))
                            text: modelData
                            color: index === glassRow.step ? look.ink : look.dim
                            font.pixelSize: Math.max(14, Math.round(Kirigami.Theme.defaultFont.pointSize * 4 / 3) - 2)
                            font.weight: index === glassRow.step ? Font.DemiBold : Font.Normal
                            TapHandler {
                                onTapped: sheet.chooseGlass(glassRow.levels[index])
                            }
                        }
                    }
                }
            }
        }
    }
    // The widget gallery, also from here: Settings steps aside for the desktop.
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            tappable: true
            title: i18n("Widgets")
            detail: i18n("Add, move or take away the cards on your desktop")
            onTapped: sheet.ask("widgets")
            SettingsControls.Pill {
                tone: look
                kind: "lily"
                text: i18n("Edit widgets")
                onClicked: sheet.ask("widgets")
            }
        }
    }
    // The way back when More settings changed how Monet looks (KDE's theme buttons once
    // took its app style away): its colors, styles, frames and painting again, for this
    // account, no restart. Files, apps and the bar's islands stay.
    SettingsControls.Card {
        tone: look
        SettingsControls.SettingRow {
            tone: look
            divider: false
            title: i18n("Monet's look")
            detail: sheet.restoring ? i18n("Putting it back…")
                : sheet.restored ? i18n("Monet's look has been put back. Your files, apps and bar are unchanged.")
                : sheet.restoreFailed ? i18n("Monet's look couldn't be fully put back. Try again.")
                : i18n("Something in More settings changed how Monet looks? Its colors, styles, window frames and painting come back. Your files, apps and bar stay.")
            SettingsControls.Pill {
                objectName: "restoreLookButton"
                tone: look
                kind: sheet.restored ? "lily" : "plain"
                text: sheet.restoring ? i18n("Putting it back…")
                    : sheet.restored ? i18n("Put back again")
                    : sheet.restoreFailed ? i18n("Try again") : i18nc("Monet's look, as it was", "Put back")
                enabledPill: !sheet.restoring
                onClicked: sheet.restoreLook()
            }
        }
    }
}
