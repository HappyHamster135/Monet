/*
 * The towns on the world clock: each can go, and more come from a search
 * of every time zone (by town, country or region, in your language).
 */
import QtQuick
import QtQuick.Controls as QQC2
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import org.kde.kcmutils as KCM
import org.kde.plasma.private.digitalclock

KCM.SimpleKCM {
    id: page

    property var cfg_zones: []
    property var cfg_zonesDefault: []

    function add(zone) {
        if (cfg_zones.indexOf(zone) < 0) {
            cfg_zones = Array.from(cfg_zones).concat([zone]);
        }
        query.text = "";
    }

    Kirigami.FormLayout {
        ColumnLayout {
            Kirigami.FormData.label: i18n("Towns:")
            spacing: 0

            QQC2.Label {
                visible: page.cfg_zones.length === 0
                text: i18n("No town yet")
            }
            Repeater {
                model: page.cfg_zones
                RowLayout {
                    id: town
                    required property string modelData
                    required property int index
                    QQC2.Label {
                        Layout.minimumWidth: Kirigami.Units.gridUnit * 10
                        text: TimeZonesI18n.i18nCity(town.modelData)
                    }
                    QQC2.ToolButton {
                        icon.name: "list-remove"
                        text: i18nc("%1 is a town", "Remove %1", TimeZonesI18n.i18nCity(town.modelData))
                        display: QQC2.AbstractButton.IconOnly
                        QQC2.ToolTip.text: text
                        QQC2.ToolTip.visible: hovered
                        onClicked: page.cfg_zones = Array.from(page.cfg_zones).filter((zone, i) => i !== town.index)
                    }
                }
            }
        }

        QQC2.TextField {
            id: query
            Kirigami.FormData.label: i18n("Add a town:")
            placeholderText: i18n("A town or a city")
        }

        // What the search finds, eight towns high (it scrolls for more).
        ListView {
            id: matches
            visible: query.text.trim().length >= 2
            Layout.preferredWidth: Kirigami.Units.gridUnit * 18
            Layout.preferredHeight: Math.min(count, 8) * Kirigami.Units.gridUnit * 2
            clip: true
            model: TimeZoneFilterProxy {
                sourceModel: TimeZoneModel {}
                filterString: query.text.trim()
            }
            delegate: QQC2.ItemDelegate {
                required property var model
                width: ListView.view.width
                height: Kirigami.Units.gridUnit * 2
                text: [model.city, model.region].filter(p => p).join(", ")
                onClicked: page.add(model.timeZoneId)
            }
        }
    }
}
