import QtQuick
import QtQuick.Layouts
import QtCore
import "LayoutMath.js" as LayoutMath

Item {
    id: guard
    visible: false
    property var layout: null
    property var snapshots: ({})
    property var last: null
    property bool pending: false
    property bool initialized: false
    property url storageFile: StandardPaths.writableLocation(StandardPaths.ConfigLocation) + "/monet/widget-layouts.conf"
    property string savedValue: ""
    Settings { id: saved; location: guard.storageFile }
    Timer { id: flush; interval: 700; onTriggered: saved.sync() }
    // PropertyAction bypasses Plasma's animated x/y Behaviors. Its allocator
    // must see the destination, rather than the first frame of the animation.
    SequentialAnimation {
        id: jump
        property Item item
        property real destinationX
        property real destinationY
        PropertyAction { target: jump.item; property: "x"; value: jump.destinationX }
        PropertyAction { target: jump.item; property: "y"; value: jump.destinationY }
    }

    function containers() {
        return layout ? Array.from(layout.children).filter(c => c.applet && c.applet.plasmoid) : [];
    }
    function leader() {
        const own = containers().filter(c => c.applet.plasmoid.pluginName.startsWith("org.monet."));
        own.sort((a,b) => a.applet.plasmoid.id-b.applet.plasmoid.id);
        if (!own.length) return false;
        let item = guard.parent;
        while (item && item !== own[0]) item = item.parent;
        return item === own[0];
    }
    function storageKey() {
        const first = containers()[0];
        if (!first) return "";
        const applet = first.applet.plasmoid;
        return applet.containment ? "desktop-" + applet.containment.id : "widget-" + applet.id;
    }
    function validSnapshot(value) {
        const positive = n => typeof n === "number" && isFinite(n) && n > 0;
        const position = n => typeof n === "number" && isFinite(n) && n >= 0;
        return value && value.area && positive(value.area.width) && positive(value.area.height)
            && Array.isArray(value.items) && value.items.length <= 200 && value.items.every(r => r && position(r.id)
                && position(r.x) && position(r.y) && positive(r.width) && positive(r.height)
                && positive(r.minWidth) && positive(r.minHeight));
    }
    function load() {
        saved.sync();
        try {
            const record = JSON.parse(saved.value(storageKey(), "{}"));
            const restored = {};
            Object.keys(record.snapshots || {}).slice(-20).forEach(key => {
                if (validSnapshot(record.snapshots[key])) restored[key] = record.snapshots[key];
            });
            snapshots = restored;
            last = snapshots[layout.configKey] || snapshots[record.lastKey] || null;
        } catch (e) {
            snapshots = {}; last = null;
        }
    }
    function persist() {
        const keys = Object.keys(snapshots);
        while (keys.length > 20) delete snapshots[keys.shift()];
        const value = JSON.stringify({snapshots:snapshots,lastKey:layout.configKey});
        if (value === savedValue) return;
        savedValue = value;
        saved.setValue(storageKey(), value);
        if (!flush.running) flush.start();
    }
    function capture(edited = false) {
        if (!layout || !initialized || !leader()
                || (!edited && (pending || layout.editMode || layout.relayoutLock))) return;
        const items = containers().map(c => ({id:c.applet.plasmoid.id,x:c.x,y:c.y,width:c.width,height:c.height,
                                              minWidth:Math.max(48,c.Layout.minimumWidth),minHeight:Math.max(48,c.Layout.minimumHeight)}));
        // Edit mode temporarily reserves room for the panels; keep the screen's saved area.
        const previous = snapshots[layout.configKey];
        const area = edited && previous ? previous.area : {width:layout.width,height:layout.height};
        last = {items:items,area:area};
        snapshots[layout.configKey] = last;
        persist();
    }
    function schedule() { pending = true; settle.restart(); }
    function fit() {
        if (!layout || !leader()) { pending=false; return; }
        if (!initialized || layout.relayoutLock || layout.editMode) { settle.restart(); return; }
        const source = snapshots[layout.configKey] || last;
        if (!source) { pending=false; capture(); return; }
        const area = {width:layout.width,height:Math.min(layout.height,layout.containmentItem.height-80)};
        const known = snapshots[layout.configKey];
        const children = containers();
        const items = children.map(c => source.items.find(r => r.id===c.applet.plasmoid.id)
            || {id:c.applet.plasmoid.id,x:c.x,y:c.y,width:c.width,height:c.height,
                minWidth:c.Layout.minimumWidth,minHeight:c.Layout.minimumHeight});
        const valid = items.every((r,i) => r.x>=0 && r.y>=0 && r.x+r.width<=area.width
            && r.y+r.height<=area.height && !items.slice(0,i).some(p => LayoutMath.overlaps(p,r,0)));
        const rects = known && valid && known.area.width===layout.width && known.area.height===layout.height
            ? items : LayoutMath.arrange(items,source.area,area,layout.cellWidth);
        children.forEach(c => layout.releaseSpace(c));
        rects.forEach(r => {
            const c = children.find(c => c.applet.plasmoid.id===r.id);
            if (!c) return;
            c.width=r.width; c.height=r.height;
            jump.item=c; jump.destinationX=r.x; jump.destinationY=r.y; jump.start();
            layout.positionItem(c);
        });
        layout.save();
        pending=false;
        Qt.callLater(capture);
    }
    Timer {
        interval: 500; running: true; repeat: true
        onTriggered: {
            if (!guard.layout) {
                let item=guard.parent;
                while(item && !(item.positionItem && item.releaseSpace && item.containmentItem)) item=item.parent;
                guard.layout=item;
            }
            if (guard.layout && guard.leader() && !guard.initialized) {
                if (guard.layout.relayoutLock) return;
                guard.load();
                guard.initialized = true;
                guard.pending = false;
                // Never overwrite a saved arrangement with Plasma's temporary
                // startup/scaling geometry before it has been restored.
                if (!guard.last) guard.capture();
                guard.schedule();
            }
            guard.capture();
        }
    }
    Timer { id: settle; interval: 650; onTriggered: guard.fit() }
    Connections {
        target: guard.layout
        function onEditModeChanged() {
            if (!guard.layout.editMode && guard.leader()) {
                if (!guard.initialized) { guard.load(); guard.initialized = true; }
                // Done is a new arrangement, not a screen resize to restore from the old snapshot.
                guard.capture(true);
                guard.schedule();
            }
        }
        function onWidthChanged() { guard.schedule(); }
        function onHeightChanged() { guard.schedule(); }
        function onConfigKeyChanged() { guard.schedule(); }
        function onRelayoutLockChanged() { if (!guard.layout.relayoutLock && guard.pending) settle.restart(); }
    }
}
