import QtQuick
import QtQuick.Layouts
import QtCore
import QtQml.Models
import "LayoutMath.js" as LayoutMath

Item {
    id: guard
    visible: false
    property var layout: null
    property var snapshots: ({})
    property var last: null
    property bool pending: false
    property bool initialized: false
    property bool custom: false
    property var editStart: null
    property var ancestors: []
    readonly property bool isLeader: leader()
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
            custom = record.custom === true;
            const restored = {};
            Object.keys(record.snapshots || {}).slice(-20).forEach(key => {
                if (validSnapshot(record.snapshots[key])) restored[key] = record.snapshots[key];
            });
            snapshots = restored;
            last = snapshots[layout.configKey] || snapshots[record.lastKey] || null;
        } catch (e) {
            snapshots = {}; last = null; custom = false;
        }
    }
    function persist() {
        const keys = Object.keys(snapshots);
        while (keys.length > 20) delete snapshots[keys.shift()];
        const value = JSON.stringify({snapshots:snapshots,lastKey:layout.configKey,custom:custom});
        if (value === savedValue) return;
        savedValue = value;
        saved.setValue(storageKey(), value);
        if (!flush.running) flush.start();
    }
    function capture(edited = false) {
        if (!layout || !initialized || !isLeader
                || (!edited && (pending || layout.editMode || layout.relayoutLock))) return;
        const items = containers().map(metrics);
        // Edit mode temporarily reserves room for the panels; keep the screen's saved area.
        const previous = snapshots[layout.configKey];
        const area = edited && previous ? previous.area : {width:layout.width,height:layout.height};
        last = {items:items,area:area};
        snapshots[layout.configKey] = last;
        persist();
    }
    function metrics(c) {
        return {id:c.applet.plasmoid.id, x:c.x, y:c.y, width:c.width, height:c.height,
            minWidth:Math.max(48,c.Layout.minimumWidth), minHeight:Math.max(48,c.Layout.minimumHeight)};
    }
    function editGeometry() {
        return JSON.stringify(containers().map(c => [c.applet.plasmoid.id,c.x,c.y,c.width,c.height])
            .sort((a,b) => a[0]-b[0]));
    }
    function schedule() { pending = true; settle.restart(); }
    function fit() {
        if (!layout || !isLeader) { pending=false; return; }
        if (!initialized || layout.relayoutLock || layout.editMode) return;
        const area = {width:layout.width,height:Math.min(layout.height,layout.containmentItem.height-80)};
        if (area.width < layout.cellWidth * 3 || area.height < layout.cellWidth * 3) return;
        const known = snapshots[layout.configKey];
        const source = known || last;
        const children = containers();
        const stock = !custom && children.length === 3 && ["placard", "weather", "calendar"].every(type =>
            children.some(c => c.applet.plasmoid.pluginName === "org.monet." + type
                && c.applet.plasmoid.configuration?.monetDefaultPlacement === true));
        const items = children.map(c => {
            const item = metrics(c);
            const previous = source?.items.find(r => r.id === item.id);
            if (previous) {
                item.x = previous.x; item.y = previous.y;
                item.width = previous.width; item.height = previous.height;
            }
            return item;
        });
        const valid = items.every((r,i) => r.x>=0 && r.y>=0 && r.x+r.width<=area.width
            && r.y+r.height<=area.height && !items.slice(0,i).some(p => LayoutMath.overlaps(p,r,0)));
        let rects = items;
        if (stock) {
            children.forEach((c, index) => {
                items[index].type = c.applet.plasmoid.pluginName.slice("org.monet.".length);
                items[index].preferredWidth = Math.max(0,c.Layout.preferredWidth);
                items[index].preferredHeight = Math.max(0,c.Layout.preferredHeight);
            });
            rects = LayoutMath.desktopDefaults(items,area,layout.cellWidth);
        } else if (!valid || (source && (!known || known.area.width!==layout.width || known.area.height!==layout.height))) {
            rects = LayoutMath.arrange(items,source?.area || area,area,layout.cellWidth);
        }
        if (rects.every(r => children.some(c => c.applet.plasmoid.id===r.id
                && c.x===r.x && c.y===r.y && c.width===r.width && c.height===r.height))) {
            pending=false;
            capture();
            return;
        }
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
    function discover() {
        const chain = [];
        let item = guard.parent;
        while (item && !(item.positionItem && item.releaseSpace && item.containmentItem)) {
            chain.push(item);
            item = item.parent;
        }
        ancestors = chain;
        if (layout !== item) { initialized = false; layout = item; }
        initialize();
    }
    function initialize() {
        if (!layout || !isLeader || initialized || layout.relayoutLock) return;
        load();
        initialized = true;
        pending = false;
        // Wait for the desktop and panel geometry before taking the first snapshot.
        schedule();
    }
    // Plasma reparents representations after construction. Watch that lifecycle
    // instead of walking every widget's scene tree twice per second forever.
    Timer { id: discoverLater; interval: 0; onTriggered: guard.discover() }
    onParentChanged: discoverLater.restart()
    Component.onCompleted: discoverLater.restart()
    onIsLeaderChanged: {
        if (isLeader) initialize();
        else { initialized = false; pending = false; settle.stop(); captureLater.stop(); }
    }
    Instantiator {
        model: guard.ancestors
        delegate: Connections {
            required property var modelData
            target: modelData
            function onParentChanged() { discoverLater.restart(); }
        }
    }
    // Only the desktop's leader listens to geometry; panel widgets own no
    // layout timers or geometry subscriptions. Dragging coalesces into one save.
    Instantiator {
        model: guard.isLeader ? guard.containers() : []
        delegate: Connections {
            required property var modelData
            target: modelData
            function onXChanged() { captureLater.restart(); }
            function onYChanged() { captureLater.restart(); }
            function onWidthChanged() { captureLater.restart(); }
            function onHeightChanged() { captureLater.restart(); }
        }
    }
    Timer { id: captureLater; interval: 250; onTriggered: guard.capture() }
    Timer { id: settle; interval: 650; onTriggered: guard.fit() }
    Connections {
        target: guard.layout
        function onEditModeChanged() {
            if (!guard.isLeader) return;
            if (guard.layout.editMode) {
                guard.editStart = guard.editGeometry();
            } else {
                if (!guard.initialized) { guard.load(); guard.initialized = true; }
                // Done is a new arrangement, not a screen resize to restore from the old snapshot.
                if (guard.custom || guard.editStart === null || guard.editStart !== guard.editGeometry()) {
                    guard.custom = true;
                    guard.capture(true);
                }
                guard.editStart = null;
                guard.schedule();
            }
        }
        function onWidthChanged() { guard.schedule(); }
        function onHeightChanged() { guard.schedule(); }
        function onConfigKeyChanged() { guard.schedule(); }
        function onChildrenChanged() { captureLater.restart(); }
        function onRelayoutLockChanged() {
            guard.initialize();
            if (!guard.layout.relayoutLock && guard.pending) settle.restart();
        }
    }
}
