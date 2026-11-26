// Sizes in logical pixels, shared by the section grid and its native popup.
.pragma library

var tileHeight = 68
var gap = 7

function columns(width) {
    return Math.max(1, Math.min(4, Math.floor((width + gap) / 90)))
}

function gridHeight(count, width) {
    var rows = Math.ceil(count / columns(width))
    return rows * tileHeight + Math.max(0, rows - 1) * gap
}

function slideDuration(desktopDuration) {
    return desktopDuration > 1 ? Math.round(desktopDuration * 1.4) : 0
}
