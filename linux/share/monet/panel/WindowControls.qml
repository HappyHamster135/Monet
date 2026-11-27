import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Controls as C
RowLayout {
    id: controls
    required property QtObject host
    spacing: 2
    visible: !!host.startSystemMove
    Repeater {
        model: [ {name: i18nd("monet", "Minimize"), glyph: "−", action: 0},
                 {name: i18nd("monet", "Maximize or restore"), glyph: "□", action: 1},
                 {name: i18nd("monet", "Close"), glyph: "×", action: 2} ]
        C.ToolButton {
            required property var modelData
            text: modelData.glyph
            Accessible.name: modelData.name
            implicitWidth: 32; implicitHeight: 32
            onClicked: {
                if (modelData.action === 0) controls.host.showMinimized()
                else if (modelData.action === 1) {
                    if (controls.host.visibility === Window.Maximized) controls.host.showNormal()
                    else controls.host.showMaximized()
                } else controls.host.close()
            }
        }
    }
}
