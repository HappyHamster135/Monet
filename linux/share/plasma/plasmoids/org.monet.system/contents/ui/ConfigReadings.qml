import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM

KCM.SimpleKCM {
    id: page
    property var cfg_readings: []
    property var cfg_readingsDefault: []
    property string cfg_readingStyle
    property string cfg_readingStyleDefault
    property bool cfg_monitorDedicatedGraphics
    property bool cfg_monitorDedicatedGraphicsDefault

    readonly property ReadingNames names: ReadingNames {}
    readonly property var available: names.choices(catalog.sensorIds).filter(key => !cfg_readings.includes(key))
    function move(from, to) {
        if (from === to || to < 0 || to >= cfg_readings.length) return
        const order = Array.from(cfg_readings)
        order.splice(to, 0, order.splice(from, 1)[0])
        cfg_readings = order
    }

    Kirigami.FormLayout {
        SensorCatalog { id: catalog }
        Controls.CheckBox {
            text: i18nd("monet", "Monitor dedicated graphics on laptops")
            checked: page.cfg_monitorDedicatedGraphics
            onToggled: page.cfg_monitorDedicatedGraphics = checked
        }
        Controls.Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            text: i18nd("monet", "Live NVIDIA readings can keep the graphics chip awake and use more power. Leave this off for longer battery life; Task Manager still offers detailed readings.")
        }
        Controls.ComboBox {
            id: style
            Kirigami.FormData.label: i18nd("monet", "Display style")
            model: [{key:"values", label:i18nd("monet", "Numbers")},
                    {key:"bars", label:i18nd("monet", "Usage bars")},
                    {key:"both", label:i18nd("monet", "Numbers and usage bars")}]
            textRole: "label"
            currentIndex: {
                const selected = model.findIndex(entry => entry.key === page.cfg_readingStyle)
                return selected < 0 ? 2 : selected
            }
            onActivated: index => page.cfg_readingStyle = model[index].key
        }
        ColumnLayout {
            Kirigami.FormData.label: i18nd("monet", "On the bar")
            Layout.fillWidth: true
            Repeater {
                model: page.cfg_readings
                RowLayout {
                    id: entry
                    required property int index
                    required property string modelData
                    Layout.fillWidth: true
                    Controls.Label {
                        Layout.fillWidth: true
                        text: names.name(entry.modelData)
                        wrapMode: Text.Wrap
                    }
                    Controls.ToolButton {
                        icon.name: "arrow-up"; display: Controls.AbstractButton.IconOnly
                        text: i18nd("monet", "Move %1 earlier", names.name(entry.modelData))
                        enabled: entry.index > 0
                        Controls.ToolTip.text: text; Controls.ToolTip.visible: hovered
                        onClicked: page.move(entry.index, entry.index - 1)
                    }
                    Controls.ToolButton {
                        icon.name: "arrow-down"; display: Controls.AbstractButton.IconOnly
                        text: i18nd("monet", "Move %1 later", names.name(entry.modelData))
                        enabled: entry.index + 1 < page.cfg_readings.length
                        Controls.ToolTip.text: text; Controls.ToolTip.visible: hovered
                        onClicked: page.move(entry.index, entry.index + 1)
                    }
                    Controls.ToolButton {
                        icon.name: "list-remove"; display: Controls.AbstractButton.IconOnly
                        text: i18nd("monet", "Remove %1", names.name(entry.modelData))
                        Controls.ToolTip.text: text; Controls.ToolTip.visible: hovered
                        onClicked: page.cfg_readings = page.cfg_readings.filter((k, i) => i !== entry.index)
                    }
                }
            }
        }
        RowLayout {
            Layout.fillWidth: true
            Kirigami.FormData.label: i18nd("monet", "Add a reading")
            Controls.ComboBox {
                id: candidates
                Layout.fillWidth: true
                model: page.available.map(key => ({key:key, label:names.name(key)}))
                textRole: "label"
                enabled: count > 0
            }
            Controls.Button {
                text: i18nd("monet", "Add")
                enabled: candidates.currentIndex >= 0 && candidates.currentIndex < candidates.count
                onClicked: {
                    const key = candidates.model[candidates.currentIndex].key
                    if (!page.cfg_readings.includes(key)) page.cfg_readings = Array.from(page.cfg_readings).concat(key)
                }
            }
        }
    }
}
