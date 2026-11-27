import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import "../panel" as EditorUI

C.ScrollView {
    id: view
    clip: true
    background: Rectangle { color: "transparent" }
    contentWidth: availableWidth
    C.ScrollBar.horizontal.policy: C.ScrollBar.AlwaysOff
    ColumnLayout {
        width: view.availableWidth; spacing: 12
        C.ComboBox {
            wheelEnabled: false;
            visible: settingsBridge.screens.length > 1
            model: settingsBridge.screens; textRole: "label"; enabled: !settingsBridge.busy
            Accessible.name: qsTr("Display")
            onActivated: index => settingsBridge.selectScreen(index)
        }
        EditorUI.NotchEditor {
            id: editor; Layout.fillWidth: true
            showNavigation: false
            showIntroduction: false
            notchState: settingsBridge.state; busy: settingsBridge.busy
            Component.onCompleted: page = settingsBridge.page
            onPageChanged: if (page !== settingsBridge.page) settingsBridge.selectPage(page)
            onRequested: command => settingsBridge.request(command)
        }
        Connections {
            target: settingsBridge
            function onChanged() { editor.page = settingsBridge.page }
        }
        C.Label { Layout.fillWidth: true; wrapMode: Text.Wrap; visible: !!settingsBridge.problem; text: settingsBridge.problem }
    }
}
