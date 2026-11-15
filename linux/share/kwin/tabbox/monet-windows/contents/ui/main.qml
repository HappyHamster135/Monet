/*
 * Based on KWin's thumbnail grid.
 * SPDX-FileCopyrightText: 2020 Chris Holland <zrenfire@gmail.com>
 * SPDX-FileCopyrightText: 2023 Nate Graham <nate@kde.org>
 * SPDX-License-Identifier: GPL-2.0-or-later
 */

import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kwin as KWin
import org.kde.plasma.components as PlasmaComponents
import org.kde.plasma.core as PlasmaCore

KWin.TabBoxSwitcher {
    id: switcher

    Instantiator {
        active: switcher.visible
        delegate: PlasmaCore.Dialog {
            location: PlasmaCore.Types.Floating
            visible: true
            flags: Qt.ToolTip | Qt.X11BypassWindowManagerHint
            x: Math.round(switcher.screenGeometry.x + (switcher.screenGeometry.width - sheet.width) / 2)
            y: Math.round(switcher.screenGeometry.y + (switcher.screenGeometry.height - sheet.height) / 2)

            mainItem: FocusScope {
                id: sheet
                focus: true

                readonly property int gap: Kirigami.Units.smallSpacing
                readonly property int padding: gap * 2
                readonly property int scrollbarWidth: gap * 2
                readonly property int maxWidth: Math.floor(switcher.screenGeometry.width * 0.9)
                readonly property int maxHeight: Math.floor(switcher.screenGeometry.height * 0.8)
                readonly property int titleHeight: Math.ceil(captionMetrics.lineSpacing * 2)
                readonly property int headerHeight: Math.ceil(headerMetrics.lineSpacing * 2)
                readonly property int availableWidth: Math.max(1, maxWidth - padding * 2 - scrollbarWidth)
                readonly property int availableHeight: Math.max(1, maxHeight - headerHeight - padding * 3)
                readonly property var tiles: fitGrid(Math.max(1, grid.count))
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
                        text: grid.currentItem ? grid.currentItem.caption : i18nd("kwin", "No open windows")
                        textFormat: Text.PlainText
                        wrapMode: Text.Wrap
                        maximumLineCount: 2
                        elide: Text.ElideRight
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
                    model: switcher.model
                    currentIndex: switcher.currentIndex
                    cellWidth: sheet.tiles.width
                    cellHeight: sheet.tiles.height
                    keyNavigationWraps: true
                    highlightMoveDuration: 0
                    boundsBehavior: Flickable.StopAtBounds
                    onCurrentIndexChanged: {
                        if (currentIndex >= 0) {
                            switcher.currentIndex = currentIndex;
                            positionViewAtIndex(currentIndex, GridView.Contain);
                        }
                    }

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
                        onClicked: switcher.model.activate(index)

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

                        ColumnLayout {
                            anchors.fill: parent
                            anchors.margins: sheet.gap * 1.5
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
                                    visible: card.model.closeable && typeof switcher.model.close !== "undefined"
                                             && (card.containsMouse || card.GridView.isCurrentItem || hovered || Kirigami.Settings.tabletMode
                                                 || Kirigami.Settings.hasTransientTouchInput)
                                    icon.name: "window-close-symbolic"
                                    Accessible.name: i18nd("kwin", "Close")
                                    onClicked: switcher.model.close(card.index)
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

                Keys.onPressed: event => {
                    switch (event.key) {
                    case Qt.Key_Left: grid.moveCurrentIndexLeft(); break;
                    case Qt.Key_Right: grid.moveCurrentIndexRight(); break;
                    case Qt.Key_Up: grid.moveCurrentIndexUp(); break;
                    case Qt.Key_Down: grid.moveCurrentIndexDown(); break;
                    default: return;
                    }
                    event.accepted = true;
                }
            }

            onSceneGraphError: {
                // Disconnecting from the graphics device can otherwise abort Qt Quick.
            }
        }
    }
}
