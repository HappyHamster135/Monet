import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.plasma.plasma5support as P5Support

// What each app uses of the graphics card (monet-graphics-use), every two seconds while
// the Graphics page is in view and not paused. Nothing is measured otherwise: reading
// NVIDIA's report can wake a sleeping graphics card.
ColumnLayout {
    id: use
    objectName: "graphicsApps"
    property bool sampling: false
    property color accent: Kirigami.Theme.highlightColor
    property string helper: "@LIBEXECDIR@/monet-graphics-use"
    property var apps: []
    property bool measured: false
    property bool reported: true
    property bool busy: false
    property int serial: 0
    spacing: 8

    function refresh() {
        if (busy || !sampling) return
        busy = true
        reader.connectSource("'" + helper.replace(/'/g, "'\\''") + "' # graphics-use-" + (++serial))
    }
    onSamplingChanged: if (sampling) refresh()
    Component.onCompleted: if (sampling) refresh()
    Timer { interval: 2000; repeat: true; running: use.sampling; onTriggered: use.refresh() }
    P5Support.DataSource {
        id: reader
        engine: "executable"
        connectedSources: []
        onNewData: (source, data) => {
            disconnectSource(source)
            use.busy = false
            try {
                const result = JSON.parse(data.stdout)
                if (data["exit code"] !== 0 || result.version !== 1 || !Array.isArray(result.apps)) throw new Error("invalid")
                use.reported = result.ok === true
                use.apps = result.apps
            } catch (_) {
                use.reported = false
                use.apps = []
            }
            use.measured = true
        }
    }
    function label(app) {
        return app.part === "windows" ? i18nd("monet", "Windows and effects")
            : app.part === "desktop" ? i18nd("monet", "Desktop, wallpaper and Home Bar")
            : app.part === "xwayland" ? i18nd("monet", "Windows of older apps")
            : String(app.name || "")
    }

    QQC2.Label {
        text: i18nd("monet", "Apps using graphics")
        font.weight: Font.DemiBold
    }
    Repeater {
        model: use.apps
        RowLayout {
            id: row
            required property var modelData
            Layout.fillWidth: true
            spacing: 12
            readonly property real share: Math.max(0, Math.min(100, Number(modelData.percent) || 0))
            Accessible.role: Accessible.StaticText
            Accessible.name: use.label(modelData) + ": " + i18nd("monet", "%1%", share.toLocaleString(Qt.locale(), "f", 1))
            QQC2.Label {
                Layout.preferredWidth: 1
                Layout.fillWidth: true
                text: use.label(row.modelData)
                elide: Text.ElideRight
            }
            Rectangle {
                Layout.preferredWidth: 1
                Layout.fillWidth: true
                Layout.preferredHeight: 6
                radius: 3
                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.1)
                Rectangle {
                    width: parent.width * row.share / 100
                    height: parent.height
                    radius: parent.radius
                    color: use.accent
                }
            }
            QQC2.Label {
                Layout.minimumWidth: 52
                horizontalAlignment: Text.AlignRight
                text: i18nd("monet", "%1%", row.share.toLocaleString(Qt.locale(), "f", 1))
                font.weight: Font.DemiBold
            }
        }
    }
    QQC2.Label {
        Layout.fillWidth: true
        visible: use.measured && use.reported && use.apps.length === 0
        text: i18nd("monet", "No app is using the graphics card right now.")
        color: Kirigami.Theme.disabledTextColor
        wrapMode: Text.Wrap
    }
    QQC2.Label {
        Layout.fillWidth: true
        visible: use.measured && !use.reported
        text: i18nd("monet", "This graphics driver does not report how much each app uses.")
        color: Kirigami.Theme.disabledTextColor
        wrapMode: Text.Wrap
    }
}
