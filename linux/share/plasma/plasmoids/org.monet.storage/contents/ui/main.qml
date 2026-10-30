/* Free space for this account's home filesystem; no directory scans. */
import QtCore
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root
    Plasmoid.backgroundHints: PlasmaCore.Types.NoBackground
    Plasmoid.icon: "drive-harddisk"
    preferredRepresentation: fullRepresentation
    toolTipMainText: i18nd("monet", "Storage")
    property var space: null
    property bool busy: false
    property bool failed: false
    readonly property url homeUrl: StandardPaths.writableLocation(StandardPaths.HomeLocation)
    readonly property string home: decodeURIComponent(String(homeUrl).replace(/^file:\/\//, ""))
    property int requestSerial: 0
    readonly property string command: "@LIBEXECDIR@/monet-files-tools --space '" + home.replace(/'/g, "'\\''") + "'"
    function bytes(value) {
        const units = ["B", "KiB", "MiB", "GiB", "TiB"];
        let unit = 0;
        while (value >= 1024 && unit < units.length - 1) { value /= 1024; ++unit; }
        return Number(value).toLocaleString(Qt.locale(), 'f', unit < 2 ? 0 : 1) + " " + units[unit];
    }
    function refresh() { if (!busy) { busy = true; reader.connectSource(command + " # space-refresh-" + (++requestSerial)); } }
    P5Support.DataSource {
        id: reader
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source); root.busy = false;
            try {
                if (data["exit code"] !== 0) throw new Error("space unavailable");
                const result = JSON.parse(data.stdout);
                if (!Number.isFinite(result.free) || !Number.isFinite(result.total) || result.total <= 0) throw new Error("space invalid");
                root.space = result; root.failed = false;
            } catch (error) { root.failed = true; }
        }
    }
    Timer { interval: 60000; running: root.visible; repeat: true; onTriggered: root.refresh() }
    Component.onCompleted: refresh()
    fullRepresentation: Glass {
        id: card
        Layout.minimumWidth: Kirigami.Units.gridUnit * 14
        Layout.minimumHeight: Kirigami.Units.gridUnit * 13
        Layout.preferredWidth: Kirigami.Units.gridUnit * 18
        Layout.preferredHeight: Kirigami.Units.gridUnit * 14
        ColumnLayout {
            anchors.fill: parent; anchors.margins: Kirigami.Units.gridUnit
            spacing: Kirigami.Units.smallSpacing
            Text { text: i18nd("monet", "Storage"); color: card.ink; font.family: "Fraunces 72pt SuperSoft"; font.pixelSize: 22 }
            Text { text: i18nd("monet", "Your files and downloads"); color: card.dim; font.family: "Inter"; font.pixelSize: 12; Layout.fillWidth: true; elide: Text.ElideRight }
            Item { Layout.fillHeight: true }
            Text {
                text: root.space ? i18nd("monet", "%1 available", root.bytes(root.space.free)) : "—"
                color: card.ink; font.family: "Inter"; font.pixelSize: 20; font.weight: Font.DemiBold
                Layout.fillWidth: true; fontSizeMode: Text.Fit; minimumPixelSize: 14
            }
            QQC2.ProgressBar {
                Layout.fillWidth: true
                value: root.space ? Math.max(0, Math.min(1, 1 - root.space.free / root.space.total)) : 0
                Accessible.name: i18nd("monet", "Drive space used")
            }
            Text {
                text: root.failed ? i18nd("monet", "Could not refresh drive space. Try again.")
                    : root.space ? i18nd("monet", "%1 total", root.bytes(root.space.total)) : i18nd("monet", "Reading drive space…")
                color: card.dim; font.family: "Inter"; font.pixelSize: 12; wrapMode: Text.Wrap; Layout.fillWidth: true
            }
            Item { Layout.fillHeight: true }
            RowLayout {
                QQC2.Button { text: i18nd("monet", "Open Files"); icon.name: "system-file-manager"; onClicked: Qt.openUrlExternally(root.homeUrl); enabled: !Plasmoid.containment.corona.editMode }
                Item { Layout.fillWidth: true }
                QQC2.ToolButton { icon.name: "view-refresh"; text: i18nd("monet", "Refresh"); display: QQC2.AbstractButton.IconOnly; enabled: !root.busy && !Plasmoid.containment.corona.editMode; onClicked: root.refresh(); QQC2.ToolTip.text: text; QQC2.ToolTip.visible: hovered }
            }
        }
    }
}
