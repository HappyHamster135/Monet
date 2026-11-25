import QtQuick
import org.kde.plasma.configuration

ConfigModel {
    ConfigCategory {
        name: i18nd("monet", "Home Bar readings")
        icon: "utilities-system-monitor"
        source: "ConfigReadings.qml"
    }
}
