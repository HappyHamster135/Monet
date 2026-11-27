import QtQuick
import QtQuick.Controls as C
import QtQuick.Templates as T
import org.kde.kirigami as K

T.ComboBox {
    id: choice
    required property Item popupBounds
    implicitHeight: 32
    leftPadding: 10; rightPadding: 28
    hoverEnabled: true
    focusPolicy: Qt.StrongFocus
    contentItem: Text {
        text: choice.displayText; textFormat: Text.PlainText; color: "#ededf2"
        font.pixelSize: 12; verticalAlignment: Text.AlignVCenter; elide: Text.ElideRight
    }
    indicator: K.Icon {
        x: choice.width - width - 9; y: (choice.height - height) / 2
        width: 12; height: width; source: "arrow-down"; isMask: true; color: "#aaaab4"
    }
    background: Rectangle {
        radius: 10; color: choice.hovered ? "#303036" : "#202024"
        border.width: 1; border.color: choice.visualFocus ? "#a3ccff" : "#24ffffff"
    }
    delegate: C.ItemDelegate {
        width: choice.popup.availableWidth; implicitHeight: 32
        required property var model
        required property int index
        highlighted: choice.highlightedIndex === index
        contentItem: Text {
            text: choice.textRole ? parent.model[choice.textRole] : parent.model.modelData
            textFormat: Text.PlainText; color: "#f5f5f7"; font.pixelSize: 12
            elide: Text.ElideRight; verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle { radius: 7; color: parent.highlighted ? "#3a3a42" : "transparent" }
    }
    popup: C.Popup {
        id: listPopup
        objectName: "notchComboPopup"
        popupType: C.Popup.Item
        parent: choice.popupBounds
        property point origin: Qt.point(0, 0)
        onAboutToShow: origin = choice.mapToItem(parent, 0, 0)
        width: Math.min(choice.width, parent.width)
        height: Math.min(implicitHeight, Math.max(10, Math.floor((parent.height - 10) / 32) * 32 + 10))
        x: Math.max(0, Math.min(origin.x, parent.width - width))
        y: Math.max(0, Math.min(origin.y + choice.height + 4, parent.height - height))
        implicitHeight: Math.min(choice.count, 5) * 32 + 10
        padding: 5; margins: 0
        contentItem: ListView {
            clip: true; implicitHeight: contentHeight
            boundsBehavior: Flickable.StopAtBounds
            highlightMoveDuration: 0
            cacheBuffer: 320
            model: choice.popup.visible ? choice.delegateModel : null
            currentIndex: choice.highlightedIndex
            C.ScrollBar.vertical: C.ScrollBar {}
        }
        background: Rectangle { color: "#26262b"; radius: 12; border.width: 1; border.color: "#38ffffff" }
        Connections {
            target: choice.popupBounds
            function onVisibleChanged() { if (!target.visible) listPopup.close() }
            function onEnabledChanged() { if (!target.enabled) listPopup.close() }
        }
    }
}
