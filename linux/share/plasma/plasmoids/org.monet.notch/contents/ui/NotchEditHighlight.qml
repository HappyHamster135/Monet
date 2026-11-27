import QtQuick

// Plasma's edit click target includes the panel's invisible margins. Keep that
// target working, but paint selection on the notch itself instead of filling it.
Item {
    id: glow
    required property Item applet
    property bool active: false
    property bool standalone: true
    property real shoulder: 0
    property real chin: 8
    readonly property Item panelItem: {
        let item = applet.parent
        while (item && !(item.layoutManager !== undefined && item.configOverlay !== undefined)) item = item.parent
        return item
    }
    readonly property Item nativeFill: {
        if (!panelItem) return null
        for (const area of panelItem.children) {
            if (area.hoverEnabled === undefined || area.containsMouse === undefined) continue
            for (const item of area.children) {
                if (item.color !== undefined && item.opacity === 0.5) return item
            }
        }
        return null
    }
    Binding {
        target: glow.nativeFill
        property: "visible"
        value: false
        when: glow.standalone && !!glow.nativeFill
        restoreMode: Binding.RestoreBindingOrValue
    }
    visible: active
    Repeater {
        model: [5, 2, 1]
        IslandSurface {
            required property int index
            required property real modelData
            anchors.fill: parent
            shoulder: glow.shoulder; chin: glow.chin
            topColor: "transparent"; bottomColor: "transparent"
            outlineColor: "#80baff"
            outlineWidth: modelData
            opacity: index === 0 ? 0.12 : index === 1 ? 0.28 : 0.9
        }
    }
}
