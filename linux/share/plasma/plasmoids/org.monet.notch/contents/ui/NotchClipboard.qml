import QtQuick
import QtQuick.Controls as C
import org.kde.plasma.extras as Extras
import org.kde.plasma.private.clipboard as Clipboard
import org.kde.kitemmodels as Models

Extras.Representation {
    id: page
    objectName: "notchClipboardHistory"
    signal requestHidePopup()
    readonly property bool inDetail: stack.depth > 1
    function back() { if (inDetail) stack.pop() }
    header: stack.currentItem?.header ?? null
    focus: true; collapseMarginsHint: true
    Clipboard.HistoryModel { id: history }
    Models.KSortFilterProxyModel {
        id: nonImages
        sourceModel: history; filterRoleName: "type"
        filterRegularExpression: /^(?!4$).+$/
    }
    C.StackView {
        id: stack
        anchors.fill: parent
        initialItem: Clipboard.ClipboardMenu {
            id: menu
            dialogItem: page; model: history
            expanded: page.visible
            showsClearHistoryButton: false; keyboardActivated: true; barcodeType: "QRCode"
            // Keep Klipper's search, edit, favorite and original MIME selection actions.
            Component.onCompleted: view.model.sourceModel = nonImages
            onItemSelected: page.requestHidePopup()
        }
    }
}
