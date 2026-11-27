import QtQuick
import QtQuick.Controls as C
import QtQuick.Layouts
import org.kde.plasma.plasma5support as P5

ColumnLayout {
    id: page
    required property var slots
    required property var rows
    signal selected(string key)
    signal configureRequested()
    signal loaded(var rows,var groups)
    property int current: 0
    readonly property var captions: ({screenshot:qsTr("Capture"),record:qsTr("Record"),color:qsTr("Pick color"),"color-tools":qsTr("Palette"),"text-tools":qsTr("Text tools"),snippets:qsTr("Snippets"),emoji:qsTr("Emoji"),mic:qsTr("Mic"),awake:qsTr("Keep awake"),ocr:qsTr("Scan text"),clean:qsTr("Clean link"),plain:qsTr("Plain text"),compress:qsTr("Compress"),clipboard:qsTr("Clipboard"),notes:qsTr("Notes"),camera:qsTr("Camera"),watch:qsTr("Watch")})
    function entry(index) { return rows.find(row => row.key === slots[index]) }
    function choose(index) { if (entry(index)) selected(slots[index]) }
    function move(step) {
        for (let n=1;n<=8;n++) { const target=(current+step*n+16)%8; if (entry(target)) { current=target; buttons.itemAt(target).forceActiveFocus(); return } }
    }
    spacing: 3
    P5.DataSource {
        id: catalog; engine:"executable"
        onNewData: (source,data) => { disconnectSource(source); try { const result=JSON.parse(data.stdout); page.loaded(result.rows,result.groups) } catch (_) {} }
    }
    Component.onCompleted: { if (!rows.length) catalog.connectSource("/usr/bin/python3 '@DATADIR@/monet/utilities/actions.py'"); ring.forceActiveFocus() }
    FocusScope {
        id: ring; Layout.fillWidth:true; Layout.fillHeight:true; Layout.minimumHeight:0
        readonly property real diameter: Math.max(1,Math.min(width,height,296))
        readonly property bool compact: diameter < 230
        readonly property real radius: Math.max(1,(diameter-68)/2)
        Rectangle { visible:!ring.compact; anchors.centerIn:parent; width:ring.radius*2; height:width; radius:width/2; color:"transparent"; border.color:"#27272e"; border.width:1 }
        Repeater {
            id: buttons; model:8
            IslandButton {
                required property int index
                objectName:"radialSlot"+index
                readonly property var entry:page.entry(index)
                readonly property real angle:(index*45-90)*Math.PI/180
                x:ring.compact ? (index%4+0.5)*ring.width/4-width/2 : ring.width/2+Math.cos(angle)*ring.radius-width/2
                y:ring.compact ? Math.max(0,(ring.height-130)/2)+Math.floor(index/4)*72 : ring.height/2+Math.sin(angle)*ring.radius-height/2
                width:ring.compact ? Math.min(70,ring.width/4-4) : Math.min(70,ring.radius*Math.SQRT1_2-6); height:58
                tile:true; glyphSize:19
                enabled:!!entry
                text:entry ? (page.captions[entry.key] || entry.label) : qsTr("Empty")
                icon.name:entry ? entry.key : "plus"
                Accessible.name:(index+1)+" · "+(entry ? entry.label : qsTr("Empty slot"))
                onClicked:page.choose(index)
                onActiveFocusChanged:if(activeFocus)page.current=index
                Text {
                    anchors.right:parent.right; anchors.top:parent.top; anchors.margins:4
                    text:index+1; color:"#92929e"; font.pixelSize:8
                    Accessible.ignored:true
                }
            }
        }
        Column {
            visible:!ring.compact
            anchors.centerIn:parent; width:80; spacing:5
            IslandGlyph { anchors.horizontalCenter:parent.horizontalCenter; source:"wheel"; width:24; height:24; color:"#9dcdbf" }
            C.Label { width:parent.width; text:qsTr("Quick actions"); wrapMode:Text.Wrap; horizontalAlignment:Text.AlignHCenter; font.pixelSize:11; color:"#c9c9d1" }
        }
        Keys.onPressed:event=>{
            if ([Qt.Key_Right,Qt.Key_Down,Qt.Key_Left,Qt.Key_Up].includes(event.key)) { page.move([Qt.Key_Right,Qt.Key_Down].includes(event.key)?1:-1); event.accepted=true }
            else if(event.key>=Qt.Key_1 && event.key<=Qt.Key_8) { const index=event.key-Qt.Key_1; if(page.entry(index)) { page.current=index; buttons.itemAt(index).forceActiveFocus() };event.accepted=true }
            else if([Qt.Key_Return,Qt.Key_Enter,Qt.Key_Space].includes(event.key)) { page.choose(page.current);event.accepted=true }
        }
    }
    IslandButton { Layout.alignment:Qt.AlignHCenter; caption:true; text:qsTr("Customize radial menu"); onClicked:page.configureRequested() }
}
