// Sizes in logical pixels, shared by the section grid and its native popup.
.pragma library

var tileHeight = 57
var gap = 5

function columns(width) {
    return Math.max(1, Math.min(6, Math.floor((width + gap) / 88)))
}

function gridHeight(count, width) {
    var rows = Math.ceil(count / columns(width))
    return rows * tileHeight + Math.max(0, rows - 1) * gap
}
