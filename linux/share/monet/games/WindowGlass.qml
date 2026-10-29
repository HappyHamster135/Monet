/*
 * The glass under one of Monet's own app windows (Games, Settings, the Store), as the bar's and
 * Plasma's popups have it: KWin blurs what's behind the window (monet-games' glaze asks for it)
 * and mist or smoke is washed over the blur as thickly as Settings' Glass slider says. It
 * follows the slider at once: monet-light leaves glass-off, glass-frosted or glass-matte in
 * ~/.config/monet, as for the desktop widgets. Paper with Glass on Solid, on a PC whose
 * processor draws the screen, or while KWin can't blur.
 */
import QtCore
import QtQuick
import Qt.labs.folderlistmodel

Rectangle {
    id: glass
    property bool dark: false
    // KWin blurs behind the window (the context's blurBehind, from glaze).
    property bool blurred: false
    readonly property string level: off.count > 0 ? "solid" : matte.count > 0 ? "matte"
        : frosted.count > 0 ? "frosted" : "clear"
    readonly property bool seeThrough: blurred && level !== "solid" && GraphicsInfo.api !== GraphicsInfo.Software
    readonly property color paper: dark ? "#1E1D1B" : "#ECE9E3"
    // How much paper is washed over the blur: more than Plasma's popups have
    // (make-plasma-style.py), as a window's words sit on it all the time.
    readonly property real wash: !seeThrough ? 1 : level === "matte" ? 0.8 : level === "frosted" ? 0.56 : 0.42

    color: Qt.rgba(paper.r, paper.g, paper.b, wash)
    Behavior on color { ColorAnimation { duration: 260 } }

    FolderListModel {
        id: off
        folder: StandardPaths.writableLocation(StandardPaths.GenericConfigLocation) + "/monet"
        nameFilters: ["glass-off"]
        showDirs: false
    }
    FolderListModel {
        id: frosted
        folder: off.folder
        nameFilters: ["glass-frosted"]
        showDirs: false
    }
    FolderListModel {
        id: matte
        folder: off.folder
        nameFilters: ["glass-matte"]
        showDirs: false
    }
}
