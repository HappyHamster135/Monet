#!/usr/bin/env python3
"""Small, fail-closed QML patch to the distribution's native Task Manager."""
from pathlib import Path
import sys


def patch(source):
    path = Path(source) / 'src/Main.qml'
    text = path.read_text()
    def replace(old, new):
        nonlocal text
        if text.count(old) != 1:
            raise ValueError('Task Manager source changed: review sidebar anchor ' + old[:80])
        text = text.replace(old, new)
    replace('                actions: [\n', '''                actions: [collapseAction, toolsAction]
                display: ToolButton.IconOnly
                property list<QtObject> menuActions: [
''')
    replace('id: toolsAction\n', 'id: toolsAction\n                        visible: !globalDrawer.collapsed\n')
    for icon, name in [('list-add', 'addPageAction'), ('document-import', 'importPageAction'),
                       ('tools-report-bug', 'reportAction'), ('utilities-system-monitor', 'aboutAction'), ('kde', 'aboutKdeAction')]:
        replace(f'                        icon.name: "{icon}"', f'                        id: {name}\n                        icon.name: "{icon}"')
    replace('icon.name: app.globalDrawer.collapsed ? "view-split-left-right" : "view-left-close"', 'icon.name: "application-menu"')
    replace('''                        onTriggered: app.globalDrawer.collapsed = !app.globalDrawer.collapsed
                        displayHint: Kirigami.DisplayHint.AlwaysHide''', '''                        onTriggered: app.globalDrawer.collapsed = !app.globalDrawer.collapsed''')
    replace('''                Component.onCompleted: {
                    app.quitAction.displayHint = Kirigami.DisplayHint.AlwaysHide
                    actions.push(app.quitAction)
                }''', '')
    replace('''            TapHandler {
                acceptedButtons: Qt.RightButton
                onTapped: globalContextMenu.popup(eventPoint.scenePosition.x, eventPoint.scenePosition.y, globalDrawer)''', '''            MouseArea {
                parent: globalDrawer.contentItem
                anchors.fill: parent
                z: 100
                acceptedButtons: Qt.RightButton
                onPressed: mouse => {
                    const headerBottom = globalDrawer.header.mapToItem(parent, 0, globalDrawer.header.height).y;
                    if (mouse.y >= headerBottom) globalContextMenu.popup(parent, mouse.x, mouse.y);
                    else mouse.accepted = false;
                }''')
    replace('''                MenuItem { action: editPagesAction }
                MenuItem { action: ghnsAction }
                MenuItem { action: collapseAction }''', '''                MenuItem { action: addPageAction }
                MenuItem { action: editPagesAction }
                MenuItem {
                    text: i18nd("monet", "Remove Current Page…")
                    icon.name: "edit-delete"
                    enabled: app.canRemovePage()
                    onTriggered: {
                        removePageDialog.fileName = app.pageStack.currentItem.controller.fileName;
                        removePageDialog.pageTitle = app.pageStack.currentItem.title;
                        removePageDialog.open();
                    }
                }
                MenuSeparator {}
                MenuItem { action: exportAction }
                MenuItem { action: importPageAction }
                MenuItem { action: ghnsAction }
                MenuSeparator {}
                MenuItem { action: collapseAction }
                MenuItem { action: reportAction }
                MenuItem { action: aboutAction }
                MenuItem { action: aboutKdeAction }
                MenuSeparator {}
                MenuItem { action: app.quitAction }''')
    replace('''    Page.DialogLoader {
        id: pageDialog''', '''    // Navigate away before deleting a controller. The native manager removes
    // it from saveAll(), so closing the application cannot recreate the file.
    function canRemovePage() {
        const controller = app.pageStack.currentItem?.controller;
        return !!controller && controller.writeableState === Page.PageController.Writeable
            && !["applications.page", "history.page", "overview.page", "processes.page", "monet-system.page", "monet-applications.page", "monet-performance.page", "monet-processes.page"].includes(controller.fileName);
    }
    function availablePage(exclude) {
        return Array.from(globalDrawer.actions).find(action => action.visible
            && action.controller && action.controller.fileName !== exclude);
    }
    Kirigami.Dialog {
        id: removePageDialog
        property string fileName: ""
        property string pageTitle: ""
        title: i18nd("monet", "Remove page?")
        standardButtons: Dialog.Cancel | Dialog.Ok
        Label {
            text: i18nd("monet", "Remove %1 and its saved layout?", removePageDialog.pageTitle)
            wrapMode: Text.Wrap
            padding: Kirigami.Units.largeSpacing
        }
        onAccepted: {
            const fallback = app.availablePage(fileName);
            if (!fallback || !app.canRemovePage() || app.pageStack.currentItem.controller.fileName !== fileName) return;
            if (Page.Configuration.startPage === fileName) Page.Configuration.startPage = fallback.controller.fileName;
            Page.Configuration.lastVisitedPage = fallback.controller.fileName;
            fallback.trigger();
            Page.PageManager.removeLocalPageFiles(fileName);
        }
    }

    Page.DialogLoader {
        id: pageDialog''')
    replace('''                    Array.prototype.find.call(globalDrawer.actions, action => action.controller.fileName === startPage).trigger()''', '''                    const next = Array.from(globalDrawer.actions).find(action => action.visible && action.controller?.fileName === startPage)
                        || app.availablePage(currentPage);
                    if (next) {
                        if (Page.Configuration.startPage === currentPage) Page.Configuration.startPage = next.controller.fileName;
                        next.trigger();
                    }''')
    replace('const currentPage = pageStack.currentItem.controller.fileName', 'const currentPage = pageStack.currentItem?.controller?.fileName || ""')
    replace('newPage.savePage()', 'newPage.save()')
    path.write_text(text)


if __name__ == '__main__':
    patch(sys.argv[1])
