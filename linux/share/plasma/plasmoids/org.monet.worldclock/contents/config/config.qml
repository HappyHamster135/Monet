import QtQuick
import org.kde.plasma.configuration

ConfigModel {
    ConfigCategory {
        name: i18n("Towns")
        icon: "preferences-system-time"
        source: "ConfigTowns.qml"
    }
}
