import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as C
import QtQuick.Templates as T
import org.kde.kirigami as Kirigami
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.extras as PlasmaExtras
import org.kde.milou as Milou

ColumnLayout {
    id: page
    signal backRequested()
    signal activated()
    function focusSearch() { field.forceActiveFocus(Qt.ShortcutFocusReason) }
    function suppressHoverHints(item) {
        if (!item) return
        // Milou supplies its own label and action tooltips. Keep its native
        // result actions, applying the notch's presentation to those hints.
        for (const child of item.data || []) {
            if (child instanceof T.ToolTip) child.visible = false
            else if (child instanceof Item) suppressHoverHints(child)
        }
    }

    RowLayout {
        Layout.fillWidth: true
        PlasmaComponents.ToolButton {
            icon.name: "go-previous"
            text: i18n("Back")
            display: C.AbstractButton.IconOnly


            onClicked: page.backRequested()
        }
        PlasmaExtras.SearchField {
            id: field
            Layout.fillWidth: true
            placeholderText: i18n("Search apps, files and commands")
            Accessible.name: i18n("Command Bar")
            function submit(event) {
                if (!text.trim() || inputMethodComposing) { event.accepted = false; return }
                // An immediate Enter can arrive before the native results view is ready.
                // Finish creating it and let Milou queue Enter against the current query.
                if (provider.status === Loader.Loading) provider.asynchronous = false
                provider.item?.runCurrentIndex(event)
                provider.asynchronous = true
            }
            Keys.onPressed: event => {
                if (!inputMethodComposing && provider.item?.count && (event.key === Qt.Key_Down || event.key === Qt.Key_Up))
                    provider.item.navigationKeyHandler(event)
            }
            Keys.onReturnPressed: event => submit(event)
            Keys.onEnterPressed: event => submit(event)
        }
    }
    Item {
        Layout.fillWidth: true; Layout.fillHeight: true
        Loader {
            id: provider
            anchors.fill: parent
            active: !!field.text.trim()
            asynchronous: true
            sourceComponent: Milou.ResultsView {
                id: results
                objectName: "notchCommandResults"
                clip: true
                queryField: field
                queryString: field.text
                section.delegate: PlasmaComponents.Label {
                    required property string section
                    width: results.width
                    padding: Kirigami.Units.smallSpacing
                    elide: Text.ElideRight
                    font.weight: Font.DemiBold
                    textFormat: Text.PlainText
                    text: section
                }
                delegate: Milou.ResultDelegate {
                    width: ListView.view.width
                    categoryWidth: Kirigami.Units.largeSpacing
                    typeText: ""
                    Component.onCompleted: Qt.callLater(page.suppressHoverHints, this)
                    onIsCurrentChanged: Qt.callLater(page.suppressHoverHints, this)
                }
                C.ScrollBar.vertical: C.ScrollBar {}
                onUpdateQueryString: (text, pos) => {
                    field.text = text
                    field.cursorPosition = pos
                    page.focusSearch()
                }
                onActivated: page.activated()
            }
        }
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: parent.width - Kirigami.Units.largeSpacing * 2
            visible: !provider.active || (!!provider.item && !provider.item.querying && !provider.item.count)
            text: provider.active ? i18n("No results") : i18n("Command Bar")
            explanation: provider.active ? "" : i18n("Find an app, run a calculation, or type tools to see your favorite actions.")
        }
    }
}
