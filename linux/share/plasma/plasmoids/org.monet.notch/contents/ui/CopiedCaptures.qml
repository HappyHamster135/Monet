import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.kitemmodels as Models
import org.kde.plasma.private.clipboard as Clipboard

ColumnLayout {
    id: page
    readonly property int count: items.count
    Clipboard.HistoryModel { id: history }
    C.Label { visible: items.count > 0; text: i18n("Copied images"); font.weight: Font.DemiBold }
    ListView {
        id: items
        Layout.fillWidth: true; Layout.preferredHeight: count ? 68 : 0
        orientation: ListView.Horizontal; spacing: 6; clip: true
        model: Models.KSortFilterProxyModel { sourceModel: history; filterRoleName: "type"; filterRegularExpression: /^4$/ }
        delegate: C.AbstractButton {
            id: tile
            required property var decoration
            required property var uuid
            required property var imageSize
            width: 84; height: items.height
            text: i18n("Copy image (%1 × %2)", imageSize.width, imageSize.height)
            Accessible.name: text
            onClicked: history.moveToTop(uuid)
            background: Rectangle { radius: 8; color: "#29292e"; border.width: tile.visualFocus ? 1 : 0; border.color: "#adcfff" }
            contentItem: Image { source: tile.decoration; sourceSize.height: 100; asynchronous: true; fillMode: Image.PreserveAspectFit }
        }
    }
}
