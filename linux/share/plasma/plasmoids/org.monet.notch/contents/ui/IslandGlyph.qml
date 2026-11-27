import QtQuick
import org.kde.kirigami as K
import "IslandSymbols.js" as Symbols

Item {
    id: glyph
    property string source: ""
    property color color: "#ededf2"
    property bool solid: false
    readonly property string filledPath: ({
        "media-playback-start": "M7 3Q5 2 5 4V20Q5 22 7 21L21 13Q23 12 21 11Z",
        "media-playback-pause": "M5 3H10V21H5ZM14 3H19V21H14Z",
        "media-skip-forward": "M3 4V20L17 12ZM18 4H22V20H18Z",
        "media-skip-backward": "M21 4V20L7 12ZM2 4H6V20H2Z"
    })[source] || ""
    implicitWidth: 18; implicitHeight: 18
    Image {
        anchors.fill: parent
        visible: !!Symbols.path(glyph.source)
        sourceSize: Qt.size(96, 96)
        source: visible ? "data:image/svg+xml," + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24"><path fill="' + (glyph.solid && glyph.filledPath ? glyph.color : 'none') + '" stroke="' + glyph.color + '" stroke-width="' + (glyph.solid && glyph.filledPath ? '0' : '1.7') + '" stroke-linecap="round" stroke-linejoin="round" d="' + (glyph.solid && glyph.filledPath ? glyph.filledPath : Symbols.path(glyph.source)) + '"/></svg>') : ""
    }
    K.Icon { anchors.fill: parent; visible: !Symbols.path(glyph.source); source: glyph.source; isMask: true; color: glyph.color }
}
