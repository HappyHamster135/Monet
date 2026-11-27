"""Usage survives page reloads; async responses cannot move cards or leak accounts."""
import json
from pathlib import Path
import tempfile
import time
import unittest

try:
    from PySide6.QtCore import QObject, QPointF, QSettings, QStandardPaths, QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQuick import QQuickView
    from PySide6.QtQuickControls2 import QQuickStyle
    from PySide6.QtTest import QTest
except ImportError:
    QQuickView = None

UI = Path(__file__).resolve().parents[1] / 'linux/share/plasma/plasmoids/org.monet.notch/contents/ui'


@unittest.skipUnless(QQuickView, 'requires Qt Quick')
class Agents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        QQuickStyle.setStyle('org.kde.desktop')
        cls.app = QGuiApplication.instance() or QGuiApplication([])

    def scene(self, content):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / 'Agents.qml'
        path.write_text('import QtQuick\nimport "' + UI.as_uri() + '''" as Monet
Item {
    id: fixture
    width: 288; height: 257
    property var rememberedCards: []
    function cards(item = fixture) {
        let found = item.objectName.startsWith("notchQuota-") ? [item] : []
        for (const child of item.children) found = found.concat(cards(child))
        return found
    }
    function rememberCards() { rememberedCards = cards() }
    function cardSnapshot() {
        const current = cards()
        let bounded = true
        function check(item, card) {
            if (String(item).startsWith("QQuickText(")) {
                const p = item.mapToItem(card,0,0)
                bounded = bounded && p.x >= 0 && p.y >= 0 && p.x + item.width <= card.width + 0.1 && p.y + item.height <= card.height + 0.1
            }
            for (const child of item.children) check(child,card)
        }
        for (const card of current) check(card,card)
        return JSON.stringify({names:current.map(c=>c.objectName),positions:current.map(c=>c.y),
            same:current.length===rememberedCards.length && current.every((c,i)=>c===rememberedCards[i]),bounded:bounded})
    }
    function i18n(s,...args) { return s.replace(/%([1-9])/g,(_,n)=>args[Number(n)-1]) }
''' + content + '\n}')
        view = QQuickView()
        errors = []
        view.engine().warnings.connect(lambda values: errors.extend(e.toString() for e in values))
        view.setSource(QUrl.fromLocalFile(str(path)))
        self.assertEqual(view.status(), QQuickView.Ready, [e.toString() for e in view.errors()])
        view.show()
        self.addCleanup(view.close)
        self.addCleanup(lambda: self.assertFalse(errors, errors))
        QTest.qWait(30)
        return view, view.rootObject()

    def settings(self):
        config = Path(QStandardPaths.writableLocation(QStandardPaths.GenericConfigLocation))
        cache = Path(QStandardPaths.writableLocation(QStandardPaths.GenericCacheLocation))
        settings = QSettings(str(config / 'Monet/Utilities.conf'), QSettings.IniFormat)
        stored = QSettings(str(cache / 'monet/notch-agent-usage.conf'), QSettings.IniFormat)
        settings.clear(); stored.clear()
        settings.setValue('codexLimits', 'a'*32)
        settings.sync(); stored.sync()
        return settings, stored

    def item(self, root, name):
        named = root.findChild(QObject, name)
        if named is not None:
            return named
        pending = [root]
        while pending:
            item = pending.pop()
            if item.objectName() == name:
                return item
            pending.extend(item.childItems())
        self.fail('Missing visual item ' + name)

    def test_cached_usage_renders_immediately_refreshes_in_place_and_survives_restart(self):
        settings, cache = self.settings()
        previous = dict(ok=True, enabled=True, generation='a'*32, state='ready',
                        summary='Codex · 72% left', checked='Checked earlier', rows=[])
        cache.setValue('codex/reading', json.dumps(dict(generation='a'*32, result=previous, savedAt=(time.time()-120)*1000)))
        cache.sync()
        with tempfile.TemporaryDirectory() as tmp:
            answer = Path(tmp)/'answer.json'
            calls = Path(tmp)/'calls'
            script = Path(tmp)/'reader.py'
            next_reading = dict(previous, summary='Codex · 63% left')
            answer.write_text(json.dumps(next_reading))
            script.write_text('import pathlib,time\n' + f'p=pathlib.Path({str(calls)!r});p.write_text(p.read_text()+"x" if p.exists() else "x")\n'
                              + 'time.sleep(0.35)\n' + f'print(pathlib.Path({str(answer)!r}).read_text())\n')
            content = '''
    property bool shown: false
    Monet.AgentUsage { id: codexModel; objectName:"usage"; provider:"codex"; presented:fixture.shown; reader:''' + json.dumps('/usr/bin/python3 '+str(script)) + ''' }
    Monet.AgentUsage { id: claudeModel; provider:"claude"; presented:false }
    Monet.AgentOverview { anchors.fill:parent; codex:codexModel; claude:claudeModel; presented:false; sessionSelected:false; widgetId:"fixture" }
'''
            view, root = self.scene(content)
            usage = root.findChild(QObject, 'usage')
            self.assertEqual(usage.property('result').toVariant()['summary'], previous['summary'])
            positions = {name:self.item(root,'notchAgent-'+name).y() for name in ('codex','claude','session')}
            root.setProperty('shown', True)
            QTest.qWait(60)
            self.assertTrue(usage.property('pending'))
            self.assertEqual(usage.property('result').toVariant()['summary'], previous['summary'])
            QTest.qWait(500)
            self.assertEqual(usage.property('result').toVariant()['summary'], next_reading['summary'])
            self.assertEqual(positions, {name:self.item(root,'notchAgent-'+name).y() for name in positions})
            root.setProperty('shown', False)
            root.setProperty('shown', True)
            QTest.qWait(100)
            self.assertEqual(calls.read_text(), 'x')
            root.setProperty('shown', False)
            view.close()
            second, root2 = self.scene(content)
            restored = root2.findChild(QObject, 'usage')
            self.assertEqual(restored.property('result').toVariant()['summary'], next_reading['summary'])
            root2.setProperty('shown', True)
            QTest.qWait(100)
            self.assertFalse(restored.property('pending'))
            self.assertEqual(calls.read_text(), 'x')

            # A transient failure retains the useful reading and labels it stale.
            answer.write_text('not json')
            restored.read('refresh', '')
            QTest.qWait(500)
            self.assertEqual(restored.property('result').toVariant()['summary'], next_reading['summary'])
            self.assertTrue(restored.property('problem'))
            # An old in-flight account response must never populate a new account.
            answer.write_text(json.dumps(next_reading))
            restored.read('refresh', '')
            QTest.qWait(50)
            root2.setProperty('shown', False)
            settings.setValue('codexLimits', 'b'*32); settings.sync()
            restored.reloadConfiguration()
            QTest.qWait(500)
            self.assertEqual(restored.property('result').toVariant(), {})
            cache.sync()
            self.assertEqual(json.loads(cache.value('codex/reading')), {})

    def test_quota_cards_keep_identity_order_and_bounds_when_values_change(self):
        view, root = self.scene('''
    QtObject {
        id: fakeUsage; objectName:"usage"
        property bool enabled:true
        property string pending:""
        property string problem:""
        property var result: ({ok:true,enabled:true,state:"ready",summary:"Usage",checked:"Checked earlier",rows:[
            {name:"Short window with a very long title",remaining:"28% left",reset:"Resets tomorrow",value:28},
            {name:"Weekly",remaining:"65% left",reset:"Resets Friday",value:65}]})
        function refreshIfNeeded() {}
    }
    Monet.AgentDetail { anchors.fill:parent; provider:"codex"; presented:false; usage:fakeUsage }
''')
        before = json.loads(root.cardSnapshot())
        self.assertEqual(len(before['names']), 2, before)
        root.rememberCards()
        usage = root.findChild(QObject, 'usage')
        result = usage.property('result').toVariant()
        result['rows'].reverse()
        result['rows'][1]['remaining'] = '27.5% remaining in this window'
        result['rows'][1]['value'] = 27.5
        usage.setProperty('result', result)
        QTest.qWait(100)
        after = json.loads(root.cardSnapshot())
        self.assertTrue(after['same'])
        self.assertTrue(after['bounded'])
        self.assertEqual(before['names'], after['names'])
        self.assertEqual(before['positions'], after['positions'])

    def test_overview_meters_keep_their_slots_and_text_inside_narrow_cards(self):
        view, root = self.scene('''
    QtObject {
        id: model; objectName: "overviewUsage"
        property var result: ({state:"ready",checked:"Checked just now",rows:[
            {name:"Session allowance with a long account name",remaining:"98.5% left",value:98.5,reset:"Resets Friday at 14:30"},
            {name:"Weekly allowance",remaining:"3% left",value:3,reset:"Resets in six days"}]})
        property bool enabled: true
        property string pending: ""
        property string problem: ""
    }
    Monet.AgentOverview { id: overview; anchors.fill:parent; codex:model; claude:model; presented:false; sessionSelected:false; widgetId:"fixture" }
    function overviewSnapshot() {
        let bounded = true, boxes = []
        function visit(item, card) {
            if (!item.visible) return
            if (item.objectName.startsWith("notchAgent-")) {
                card = item
                const p = item.mapToItem(fixture,0,0)
                boxes.push([p.x,p.y,item.width,item.height])
                bounded = bounded && p.x >= 0 && p.y >= 0 && p.x+item.width <= fixture.width+0.1 && p.y+item.height <= fixture.height+0.1
            }
            if (card && String(item).startsWith("QQuickText(")) {
                const p = item.mapToItem(card,0,0)
                bounded = bounded && p.x >= 0 && p.y >= 0 && p.x+item.width <= card.width+0.1 && p.y+item.height <= card.height+0.1
            }
            for (const child of item.children) visit(child,card)
        }
        visit(overview,null)
        return JSON.stringify({bounded:bounded,boxes:boxes})
    }
''')
        usage = root.findChild(QObject, 'overviewUsage')
        for width in (288, 414):
            root.setProperty('width', width); view.resize(width, 257)
            QTest.qWait(60)
            before = json.loads(root.overviewSnapshot())
            self.assertTrue(before['bounded'], before)
            self.assertEqual(len(before['boxes']), 3)
            self.assertGreater(before['boxes'][1][0], before['boxes'][0][0])
            usage.setProperty('pending', 'refresh')
            QTest.qWait(40)
            self.assertEqual(json.loads(root.overviewSnapshot()), before)
            usage.setProperty('pending', '')
