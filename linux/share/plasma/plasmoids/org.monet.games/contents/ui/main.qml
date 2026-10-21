/*
 * Windows Games: a panel widget that lists Windows games and starts them
 * with one click. All the work is done by the `monet` command.
 */
import QtQuick
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    property var games: []
    property bool loaded: false
    readonly property string monet: "@BINDIR@/monet"

    Plasmoid.icon: "monet-windows"
    toolTipMainText: i18n("Windows Games")
    toolTipSubText: games.length > 0
        ? i18np("%1 game ready to play", "%1 games ready to play", games.length)
        : i18n("Play Windows games with one click")

    P5Support.DataSource {
        id: runner
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            if (source.indexOf(" games --json") !== -1) {
                try {
                    root.games = JSON.parse(data["stdout"])
                } catch (e) {
                    root.games = []
                }
                root.loaded = true
            }
        }
    }

    function refresh() {
        runner.connectSource(monet + " games --json")
    }

    // Game ids only contain letters, digits, ":", ".", "_" and "-".
    function play(id) {
        root.expanded = false
        runner.connectSource(monet + " play '" + id + "' --confirm")
    }

    function openWindows() {
        root.expanded = false
        runner.connectSource(monet + " windows --confirm")
    }

    Component.onCompleted: refresh()
    onExpandedChanged: if (expanded) refresh()

    fullRepresentation: PlasmaExtras.Representation {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 18
        Layout.preferredHeight: Kirigami.Units.gridUnit * 22
        collapseMarginsHint: true

        header: PlasmaExtras.PlasmoidHeading {
            RowLayout {
                anchors.fill: parent

                Kirigami.Heading {
                    Layout.fillWidth: true
                    level: 2
                    text: i18n("Windows Games")
                }

                PlasmaComponents.ToolButton {
                    icon.name: "system-reboot"
                    text: i18n("Open Windows")
                    onClicked: root.openWindows()
                }
            }
        }

        PlasmaComponents.ScrollView {
            anchors.fill: parent

            ListView {
                id: list
                model: root.games
                clip: true

                delegate: PlasmaComponents.ItemDelegate {
                    width: ListView.view.width
                    onClicked: root.play(modelData.id)

                    contentItem: RowLayout {
                        spacing: Kirigami.Units.largeSpacing

                        Kirigami.Icon {
                            source: "monet-windows"
                            Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                            Layout.preferredHeight: Kirigami.Units.iconSizes.medium
                        }

                        PlasmaComponents.Label {
                            Layout.fillWidth: true
                            text: modelData.name
                            elide: Text.ElideRight
                        }

                        PlasmaComponents.Button {
                            text: i18n("Play")
                            onClicked: root.play(modelData.id)
                        }
                    }
                }

                PlasmaExtras.PlaceholderMessage {
                    anchors.centerIn: parent
                    width: parent.width - Kirigami.Units.gridUnit * 4
                    visible: root.loaded && list.count === 0
                    iconName: "monet-windows"
                    text: i18n("No Windows games yet")
                    explanation: i18n("Install Monet Bridge in Windows and start Windows once. Your games will show up here.")
                }
            }
        }
    }
}
