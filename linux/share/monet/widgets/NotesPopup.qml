import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import org.kde.plasma.core as PlasmaCore
import org.kde.kirigami as Kirigami
import "LayoutMath.js" as LayoutMath

PlasmaCore.Dialog {
    id: popup
    property Item anchorItem
    property QtObject store
    property date day
    property date today
    signal moved(date day)
    signal closed()
    location: PlasmaCore.Types.Floating
    hideOnWindowDeactivate: false
    transientParent: anchorItem ? anchorItem.Window.window : null
    flags: Qt.Tool | Qt.WindowStaysOnTopHint

    function place() {
        if (!anchorItem) return;
        const at=anchorItem.mapToGlobal(0,0);
        const screen={x:anchorItem.Screen.virtualX,y:anchorItem.Screen.virtualY,
                      width:anchorItem.Screen.width,height:anchorItem.Screen.height};
        const position=LayoutMath.beside({x:at.x,y:at.y,width:anchorItem.width,height:anchorItem.height},
                                       {width:popup.width,height:popup.height},screen,12);
        x=Math.round(position.x); y=Math.round(position.y);
    }
    // The calendar owns visibility. Assigning it here would break that binding
    // and leave an orphaned note window after the clock's calendar closes.
    function write() { Qt.callLater(function() { if (visible) { place(); requestActivate(); editor.write(); } }); }
    function finish() {
        editor.keepNow();
        if (anchorItem && anchorItem.Window.window) anchorItem.Window.window.requestActivate();
        closed();
    }
    onClosing: event => { event.accepted=false; finish(); }
    onVisibleChanged: {
        if (visible) Qt.callLater(place);
        else editor.keepNow();
    }
    onWidthChanged: if (visible) Qt.callLater(place)
    onHeightChanged: if (visible) Qt.callLater(place)
    mainItem: Item {
        width: Math.min(Kirigami.Units.gridUnit*19, popup.anchorItem ? popup.anchorItem.Screen.width-32 : 304)
        height: Math.min(Kirigami.Units.gridUnit*25, popup.anchorItem ? popup.anchorItem.Screen.height-32 : 400)
        LayoutMirroring.enabled: Qt.application.layoutDirection === Qt.RightToLeft
        LayoutMirroring.childrenInherit: true
        DayNotes {
            id: editor
            anchors.fill: parent
            anchors.margins: Kirigami.Units.smallSpacing
            store: popup.store; day: popup.day; today: popup.today
            ink: Kirigami.Theme.textColor
            dim: Qt.rgba(ink.r,ink.g,ink.b,0.62)
            lily: Kirigami.Theme.backgroundColor.hslLightness < 0.5 ? "#4DB4A0" : "#357F72"
            closable: true
            onMoved: day => popup.moved(day)
            onClosed: popup.finish()
        }
    }
}
