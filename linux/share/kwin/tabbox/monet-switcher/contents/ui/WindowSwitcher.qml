/*
 * Based on KWin's thumbnail grid.
 * SPDX-FileCopyrightText: 2020 Chris Holland <zrenfire@gmail.com>
 * SPDX-FileCopyrightText: 2023 Nate Graham <nate@kde.org>
 * SPDX-License-Identifier: GPL-2.0-or-later
 */

import QtQuick
import QtCore as Core
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kwin as KWin
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.core as PlasmaCore

KWin.TabBoxSwitcher {
    id: switcher
    property bool searchable: false
    property bool dismissing: false
    onAboutToShow: dismissing = false
    // A Plasma dialog can stay mapped until its deferred deletion. KWin
    // must hit-test the newly activated app as soon as the grab ends.
    onAboutToHide: dismissing = true

    Instantiator {
        active: switcher.visible
        delegate: PlasmaCore.Dialog {
            location: PlasmaCore.Types.Floating
            outputOnly: switcher.dismissing
            visible: switcher.visible
            flags: Qt.ToolTip | Qt.X11BypassWindowManagerHint
            x: Math.round(switcher.screenGeometry.x + (switcher.screenGeometry.width - sheet.width) / 2)
            y: Math.round(switcher.screenGeometry.y + (switcher.screenGeometry.height - sheet.height) / 2)

            mainItem: FocusScope {
                id: sheet
                focus: true

                Core.Settings {
                    id: preferences
                    location: Core.StandardPaths.writableLocation(Core.StandardPaths.ConfigLocation) + "/monet/window-switcher.ini"
                    category: "View"
                    property bool compact: false
                }
                readonly property bool compact: switcher.searchable && (preferences.compact || GraphicsInfo.api === GraphicsInfo.Software)
                WindowMatches { id: matches; sourceModel: switcher.model }
                property bool editing: false
                property bool selecting: false
                property int lastSource: -1
                readonly property bool searching: switcher.searchable && matches.query.length > 0

                function selectResult(row) {
                    if (row < 0 || row >= matches.count) return;
                    grid.currentIndex = row;
                    lastSource = matches.sourceRow(row);
                    switcher.currentIndex = lastSource;
                    grid.positionViewAtIndex(row, GridView.Contain);
                }

                function syncSelection() {
                    if (selecting || switcher.dismissing || !switcher.visible) return;
                    const row = switcher.currentIndex;
                    const result = matches.resultRow(row);
                    if (result >= 0) {
                        selectResult(result);
                    } else if (!matches.count && searching && lastSource >= 0 && row !== lastSource) {
                        selecting = true;
                        switcher.currentIndex = lastSource;
                        selecting = false;
                    } else if (matches.count && row >= 0) {
                        // KWin cycles source windows with Alt+Tab. Skip hidden
                        // rows in the same direction, including wraparound.
                        const total = switcher.model.rowCount();
                        const step = row === (lastSource - 1 + total) % total ? -1 : 1;
                        for (let n = 1; n <= total; ++n) {
                            const found = matches.resultRow((row + n * step + total) % total);
                            if (found >= 0) { selectResult(found); break; }
                        }
                    }
                }

                function search(text) {
                    selecting = true;
                    matches.updateWords(text);
                    const row = matches.resultRow(switcher.currentIndex);
                    if (matches.count) {
                        selectResult(row < 0 ? 0 : row);
                    } else {
                        // Releasing the modifier on an empty result returns
                        // to the original window when it belongs to this scope.
                        const id = KWin.Workspace?.activeWindow?.internalId;
                        for (let i = 0; id && i < switcher.model.rowCount(); ++i) {
                            if (String(switcher.model.data(switcher.model.index(i, 0), matches.windowIdRole)) === String(id)) {
                                switcher.currentIndex = i;
                                break;
                            }
                        }
                        lastSource = switcher.currentIndex;
                        grid.currentIndex = -1;
                    }
                    selecting = false;
                }
                Connections {
                    target: switcher
                    function onCurrentIndexChanged() { sheet.syncSelection(); }
                }
                Connections {
                    target: switcher.model
                    function onModelReset() {
                        matches.refreshApps();
                        Qt.callLater(sheet.syncSelection);
                    }
                }
                Component.onCompleted: syncSelection()

                readonly property int gap: Kirigami.Units.smallSpacing
                readonly property int padding: gap * 2
                readonly property int scrollbarWidth: gap * 2
                readonly property int maxWidth: Math.floor(switcher.screenGeometry.width * 0.9)
                readonly property int maxHeight: Math.floor(switcher.screenGeometry.height * 0.8)
                readonly property int titleHeight: Math.ceil(captionMetrics.lineSpacing * 2)
                readonly property int headerHeight: Math.ceil(headerMetrics.lineSpacing * 2)
                readonly property int availableWidth: Math.max(1, maxWidth - padding * 2 - scrollbarWidth)
                readonly property int availableHeight: Math.max(1, maxHeight - headerHeight - padding * 3)
                readonly property var tiles: compact ? {
                    columns: 1, rows: Math.min(Math.max(1, grid.count), Math.max(1, Math.floor(availableHeight / compactHeight))),
                    width: Math.min(availableWidth, Kirigami.Units.gridUnit * 25), height: compactHeight
                } : fitGrid(Math.max(1, grid.count))
                readonly property int compactHeight: Math.min(availableHeight, Math.max(captionMetrics.lineSpacing, Kirigami.Units.iconSizes.medium) + gap * 3)
                width: tiles.width * tiles.columns + padding * 2 + scrollbarWidth
                height: headerHeight + grid.height + padding * 3

                function fitGrid(count) {
                    const preferredWidth = Kirigami.Units.gridUnit * 15;
                    const minWidth = Kirigami.Units.gridUnit * 8;
                    const minHeight = Kirigami.Units.gridUnit * 3 + titleHeight + gap * 3;
                    const maxColumns = Math.min(count, Math.max(1, Math.floor(availableWidth / minWidth)));
                    let best = null;
                    let bestArea = 0;
                    for (let columns = 1; columns <= maxColumns; ++columns) {
                        const rows = Math.ceil(count / columns);
                        const width = Math.min(preferredWidth, Math.floor(availableWidth / columns));
                        const idealHeight = Math.round(width * 0.52) + titleHeight + gap * 3;
                        const height = Math.min(idealHeight, Math.floor(availableHeight / rows));
                        // When a few windows fit at full size either way, a
                        // row reads better than a column: prefer fewer rows.
                        if (height >= minHeight && (width * height > bestArea
                                || best && width * height === bestArea && rows < best.rows)) {
                            bestArea = width * height;
                            best = {columns, rows, width, height};
                        }
                    }
                    if (best)
                        return best;
                    // Very long lists still show complete rows and a scrollbar.
                    const width = Math.min(preferredWidth, Math.floor(availableWidth / maxColumns));
                    const height = Math.min(minHeight, availableHeight);
                    const rows = Math.min(Math.ceil(count / maxColumns), Math.floor(availableHeight / height));
                    return {columns: maxColumns, rows, width, height};
                }

                FontMetrics {
                    id: captionMetrics
                    font: Kirigami.Theme.defaultFont
                }
                FontMetrics {
                    id: headerMetrics
                    font: selectedTitle.font
                }

                RowLayout {
                    id: header
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.margins: sheet.padding
                    height: sheet.headerHeight
                    spacing: sheet.padding

                    PlasmaComponents.Label {
                        id: selectedTitle
                        Layout.fillWidth: true
                        font.bold: true
                        text: sheet.searching ? i18nd("monet", "Search: %1", matches.query)
                              : sheet.editing ? i18nd("monet", "Type to find a window")
                              : grid.currentItem ? grid.currentItem.caption : i18nd("kwin", "No open windows")
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
                    }
                    PlasmaComponents.ToolButton {
                        visible: switcher.searchable
                        focusPolicy: Qt.NoFocus
                        icon.name: sheet.editing || sheet.searching ? "edit-clear-symbolic" : "edit-find-symbolic"
                        text: sheet.editing || sheet.searching ? i18nd("monet", "Clear search") : i18nd("monet", "Type to find a window")
                        display: Controls.AbstractButton.IconOnly
                        Accessible.name: text
                        Controls.ToolTip.text: text
                        Controls.ToolTip.visible: hovered
                        onClicked: {
                            sheet.editing = !sheet.editing && !sheet.searching;
                            sheet.search("");
                        }
                    }
                    PlasmaComponents.Label {
                        visible: grid.count > 1 && grid.currentIndex >= 0
                        opacity: 0.8
                        text: (grid.currentIndex + 1).toLocaleString(Qt.locale(), "f", 0)
                              + " / " + grid.count.toLocaleString(Qt.locale(), "f", 0)
                    }
                }

                GridView {
                    id: grid
                    anchors.top: header.bottom
                    anchors.topMargin: sheet.padding
                    anchors.left: sheet.left
                    anchors.leftMargin: sheet.padding
                    width: sheet.tiles.width * sheet.tiles.columns
                    height: sheet.tiles.height * sheet.tiles.rows
                    clip: true
                    focus: true
                    model: matches
                    keyNavigationEnabled: false
                    cellWidth: sheet.tiles.width
                    cellHeight: sheet.tiles.height
                    keyNavigationWraps: true
                    highlightMoveDuration: 0
                    boundsBehavior: Flickable.StopAtBounds
                    Controls.ScrollBar.vertical: Controls.ScrollBar {
                        parent: sheet
                        anchors.left: grid.right
                        anchors.top: grid.top
                        anchors.bottom: grid.bottom
                        width: sheet.scrollbarWidth
                        policy: grid.contentHeight > grid.height ? Controls.ScrollBar.AlwaysOn : Controls.ScrollBar.AlwaysOff
                    }

                    delegate: MouseArea {
                        id: card
                        required property int index
                        required property var model
                        readonly property string caption: model.caption
                        width: grid.cellWidth
                        height: grid.cellHeight
                        hoverEnabled: true
                        Accessible.name: caption
                        Accessible.role: Accessible.ListItem
                        onClicked: switcher.model.activate(matches.sourceRow(index))

                        Rectangle {
                            anchors.fill: parent
                            anchors.margins: sheet.gap / 2
                            radius: sheet.gap * 2
                            color: card.GridView.isCurrentItem
                                ? Qt.alpha(Kirigami.Theme.highlightColor, 0.22)
                                : card.containsMouse ? Qt.alpha(Kirigami.Theme.textColor, 0.08) : "transparent"
                            border.width: card.GridView.isCurrentItem ? 2 : 0
                            border.color: Kirigami.Theme.highlightColor
                        }

                        Loader {
                            anchors.fill: parent
                            anchors.margins: sheet.compact ? sheet.gap : sheet.gap * 1.5
                            sourceComponent: sheet.compact ? listRow : previewCard
                        }
                        Component {
                            id: listRow
                            RowLayout {
                                Kirigami.Icon {
                                    source: card.model.icon
                                    Layout.preferredWidth: Kirigami.Units.iconSizes.medium
                                    Layout.preferredHeight: Layout.preferredWidth
                                }
                                PlasmaComponents.Label {
                                    Layout.fillWidth: true
                                    text: card.caption
                                    elide: Text.ElideRight
                                    textFormat: Text.PlainText
                                }
                                PlasmaComponents.ToolButton {
                                    visible: !!card.model.closeable && (card.containsMouse || card.GridView.isCurrentItem || hovered)
                                    icon.name: "window-close-symbolic"
                                    Accessible.name: i18nd("kwin", "Close")
                                    onClicked: switcher.model.close(matches.sourceRow(card.index))
                                }
                            }
                        }
                        Component {
                            id: previewCard
                            ColumnLayout {
                                spacing: 0

                                Item {
                                    Layout.fillWidth: true
                                    Layout.fillHeight: true

                                    KWin.WindowThumbnail {
                                        anchors.fill: parent
                                        wId: card.model.windowId
                                    }

                                    Kirigami.Icon {
                                        anchors.left: parent.left
                                        anchors.bottom: parent.bottom
                                        width: Kirigami.Units.iconSizes.medium
                                        height: width
                                        source: card.model.icon
                                    }

                                    PlasmaComponents.Button {
                                        anchors.top: parent.top
                                        anchors.right: parent.right
                                        visible: !!card.model.closeable && typeof switcher.model.close !== "undefined"
                                                 && (card.containsMouse || card.GridView.isCurrentItem || hovered || Kirigami.Settings.tabletMode
                                                     || Kirigami.Settings.hasTransientTouchInput)
                                        icon.name: "window-close-symbolic"
                                        Accessible.name: i18nd("kwin", "Close")
                                        onClicked: switcher.model.close(matches.sourceRow(card.index))
                                    }
                                }

                                PlasmaComponents.Label {
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: sheet.titleHeight
                                    verticalAlignment: Text.AlignVCenter
                                    text: card.caption
                                    textFormat: Text.PlainText
                                    wrapMode: Text.Wrap
                                    maximumLineCount: 2
                                    elide: Text.ElideRight
                                }
                            }
                        }
                    }
                }

                PlasmaComponents.Label {
                    visible: sheet.searching && grid.count === 0
                    anchors.centerIn: grid
                    width: grid.width - sheet.padding
                    text: i18nd("monet", "No matching windows")
                    textFormat: Text.PlainText
                    wrapMode: Text.Wrap
                    horizontalAlignment: Text.AlignHCenter
                }

                Keys.onPressed: event => {
                    switch (event.key) {
                    case Qt.Key_Left: grid.moveCurrentIndexLeft(); break;
                    case Qt.Key_Right: grid.moveCurrentIndexRight(); break;
                    case Qt.Key_Up: grid.moveCurrentIndexUp(); break;
                    case Qt.Key_Down: grid.moveCurrentIndexDown(); break;
                    case Qt.Key_Return:
                    case Qt.Key_Enter:
                        event.accepted = true;
                        if (grid.currentIndex >= 0) switcher.model.activate(matches.sourceRow(grid.currentIndex));
                        return;
                    case Qt.Key_Backspace:
                        if (!sheet.searching) return;
                        sheet.search(Array.from(matches.query).slice(0, -1).join(""));
                        break;
                    default: {
                        if (!switcher.searchable) return;
                        // KWin forwards a logical key with empty event.text
                        // while it owns the keyboard grab.
                        const key = event.text || (event.key >= 32 && event.key <= 0x10ffff
                                  ? String.fromCodePoint(event.key).toLocaleLowerCase() : "");
                        if (!key || (key === " " && !sheet.searching)) return;
                        sheet.search(matches.query + key);
                        break;
                    }
                    }
                    if (grid.currentIndex >= 0) sheet.selectResult(grid.currentIndex);
                    event.accepted = true;
                }
            }

            onSceneGraphError: {
                // Disconnecting from the graphics device can otherwise abort Qt Quick.
            }
        }
    }
}
