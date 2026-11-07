/* Search highlights a whole setting. Its next Tab enters the first usable
 * control rather than restarting traversal at the window's sidebar. */
function enter(group) {
    for (const child of group.children) {
        if (!child.visible || !child.enabled) continue
        if (child.activeFocusOnTab) {
            child.forceActiveFocus(Qt.TabFocusReason)
            return true
        }
        if (enter(child)) return true
    }
    return false
}
