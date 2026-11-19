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
            && !["applications.page", "history.page", "overview.page", "processes.page", "monet-system.page", "monet-applications.page", "monet-performance.page", "monet-graphics.page", "monet-processes.page", "monet-startup.page"].includes(controller.fileName);
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
    patch_editor(source)
    main = Path(source) / 'src/main.cpp'
    code = main.read_text()
    anchor = '    auto sessionManager = new SessionManager(&app);'
    if code.count(anchor) != 1: raise ValueError('Task Manager startup source changed')
    code = '#include <QDir>\n#include <QFileInfo>\n#include <QProcess>\n#include <QStandardPaths>\n' + code
    code = code.replace(anchor, '''    // Reset before PageManager can read or cache an older customized layout.
    const QString receipt = QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation)
        + QStringLiteral("/monet/task-manager-backups/0.9.8-8/complete.json");
    if (!QFileInfo::exists(receipt)) {
        const QStringList helpers{QCoreApplication::applicationDirPath() + QStringLiteral("/monet-quick"),
                                  QStringLiteral("/usr/libexec/monet-quick"), QStringLiteral("/usr/local/libexec/monet-quick")};
        for (const auto &helper : helpers) {
            if (!QFileInfo(helper).isExecutable()) continue;
            QProcess reset;
            reset.start(helper, {QStringLiteral("task-manager-reset")});
            if (!reset.waitForFinished(10000) || reset.exitStatus() != QProcess::NormalExit || reset.exitCode() != 0)
                qWarning("Monet could not reset Task Manager; the previous layout and its backup are preserved");
            break;
        }
    }

''' + anchor)
    main.write_text(code)
    check_faces(source)
    path.write_text(text)


def patch_editor(source):
    """Keep KDE's editor, with plain layout names and useful chart starting points."""
    root = Path(source) / 'src/page'
    def edit(name, old, new):
        file = root / name
        text = file.read_text()
        if text.count(old) != 1:
            raise ValueError('Task Manager editor source changed: ' + name + ': ' + old[:60])
        file.write_text(text.replace(old, new))
    edit('FaceControl.qml', '    id: control\n', '''    id: control
    Accessible.name: i18nd("monet", "Configure chart")
    Accessible.role: Accessible.Button
    Accessible.onPressAction: control.select(control)
    activeFocusOnTab: true
    Keys.onReturnPressed: control.select(control)
    Keys.onSpacePressed: control.select(control)
''')
    edit('PageEditor.qml', 'let reservedHeight = missingMessage.visible ? missingMessage.height : 0;',
         'let reservedHeight = (missingMessage.visible ? missingMessage.height : 0) + editorHelp.height + root.spacing;')
    edit('PageEditor.qml', 'let minimumTotalHeight = 0\n',
         'let minimumTotalHeight = editorHelp.height + root.spacing + (missingMessage.visible ? missingMessage.height + root.spacing : 0);')
    edit('PageEditor.qml', '    Kirigami.InlineMessage {\n        id: missingMessage', '''    Kirigami.InlineMessage {
        id: editorHelp
        width: parent.width
        visible: true
        onHeightChanged: Qt.callLater(root.relayout)
        type: Kirigami.MessageType.Information
        text: i18nd("monet", "Build your page with rows, side-by-side groups and charts. Select a chart to choose what it shows. Use the move handle to reorder items. Choose Save Changes when finished, or Discard Changes to undo this edit.")
        actions: [
            Kirigami.Action { text: i18nd("monet", "Add row"); icon.name: "list-add"; onTriggered: root.addRow(-1) },
            Kirigami.Action { text: i18nd("monet", "Add heading"); icon.name: "format-text-bold"; onTriggered: root.addTitle(-1) }
        ]
    }
    Kirigami.InlineMessage {
        id: missingMessage''')
    for file, old, new in (
        ('EditablePage.qml', 'i18nc("@action", "Add Row")', 'i18nd("monet", "Add row")'),
        ('EditablePage.qml', 'i18nc("@action", "Add Title")', 'i18nd("monet", "Add heading")'),
        ('ColumnControl.qml', 'i18nc("@action", "Add Section")', 'i18nd("monet", "Add chart")'),
        ('ColumnControl.qml', 'i18nc("@action", "Add Separator")', 'i18nd("monet", "Add divider")'),
        ('RowControl.qml', 'i18nc("@action", "Add Column")', 'i18nd("monet", "Add side-by-side group")'),
        ('RowControl.qml', 'i18nc("@action:inmenu", "Minimum")', 'i18nd("monet", "Fit to contents")'),
        ('RowControl.qml', 'i18nc("@action:inmenu", "Maximum")', 'i18nd("monet", "Use remaining space")')):
        edit(file, old, new)
    edit('FaceConfigurationPage.qml', '    ColumnLayout {\n        id: layout', '''    ColumnLayout {
        id: layout
        Kirigami.InlineMessage {
            Layout.fillWidth: true
            visible: true
            text: i18nd("monet", "Choose a starting chart below, then adjust its title, display style and readings. These choices change only the selected chart.")
        }
        Label { text: i18nd("monet", "Start with a common chart"); Layout.fillWidth: true; wrapMode: Text.WordWrap }
        ComboBox {
            objectName: "monetChartPreset"
            Accessible.name: i18nd("monet", "Chart preset")
            Layout.fillWidth: true
            textRole: "label"
            model: [
                {label:i18nd("monet", "Choose a chart…"), ids:[]},
                {label:i18nd("monet", "CPU workload"), ids:["cpu/all/usage"]},
                {label:i18nd("monet", "Memory use"), ids:["memory/physical/usedPercent"]},
                {label:i18nd("monet", "Graphics workload"), ids:["gpu/all/usage"]},
                {label:i18nd("monet", "Network traffic"), ids:["network/all/download", "network/all/upload"]},
                {label:i18nd("monet", "Disk activity"), ids:["disk/all/read", "disk/all/write"]}
            ]
            onActivated: index => {
                if (index <= 0) return;
                const preset = model[index];
                page.loader.controller.faceId = "org.kde.ksysguard.linechart";
                page.loader.controller.highPrioritySensorIds = preset.ids;
                page.loader.controller.lowPrioritySensorIds = [];
                page.loader.controller.title = preset.label;
                page.loader.controller.showTitle = true;
                page.loader.controller.updateRateLimit = 1000;
                page.loader.dataObject.markDirty();
            }
        }''')


# What Monet's Applications and Processes faces (linux/share/ksysguard/sensorfaces) find in
# KDE's tables at run time: each app's processes, its overrides, its cells and columns. Without
# these the faces leave KDE's tables as they are; the build stops so it's seen first.
FACE_ANCHORS = {
    'src/faces/applicationstable/contents/ui/ApplicationsTableView.qml': (
        'property alias sourceModel: appModel\n',
        'property var selectedApplications: {',
        'property alias columnDisplay: displayModel.columnDisplay\n',
        'sourceModel.data(sourceModel.index(row, 0, parent), Process.ProcessDataModel.PIDs)',
        'property int commandColumn\n',
        'property int iconColumn: enabledAttributes.indexOf("iconName")\n',
        'property var hiddenAttributes: []\n',
        'applicationOverrides: {\n',
        'delegate: DelegateChooser {\n        role: "displayStyle"\n',
        'Table.FirstCellDelegate {',
        'roleValue: "lineScaled"',
        'DelegateChoice { Table.TextCellDelegate { } }'),
    'src/faces/applicationstable/contents/ui/FullRepresentation.qml': (
        'ApplicationsTableView {\n                id: table\n',),
    'src/faces/processtable/contents/ui/ProcessTableView.qml': (
        'property alias processModel: processModel\n',
        'property bool flatList\n',
        'property int pidColumn\n',
        'model: Table.ProcessSortFilterModel {\n',
        'Table.ComponentCacheProxyModel {\n',
        'Table.ColumnDisplayModel {\n'),
    'src/table/BaseTableView.qml': (
        'property alias view: tableView\n',
        'property alias delegate: tableView.delegate\n',
        'TreeView {\n'),
    'src/table/BaseCellDelegate.qml': ('TreeViewDelegate\n',),
    'src/table/FirstCellDelegate.qml': ('property string iconName\n', 'property real iconSize'),
}


def check_faces(source):
    for name, anchors in FACE_ANCHORS.items():
        text = (Path(source) / name).read_text()
        for anchor in anchors:
            if anchor not in text:
                raise ValueError('Task Manager source changed: review Monet\'s table faces against ' + name + ': ' + anchor[:60])


if __name__ == '__main__':
    patch(sys.argv[1])
