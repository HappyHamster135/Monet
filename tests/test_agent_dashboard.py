"""Real compact dashboard: period filters, bounded cards, scrolling and warm cache."""
import json
from pathlib import Path
import tempfile
import unittest

from tests import test_notch_agents as agent_tests
try:
    from PySide6.QtCore import QObject, QPoint, QSettings, QStandardPaths, Qt
    from PySide6.QtTest import QTest
except ImportError:
    pass


def sample():
    total = dict(input=1200000,output=34000,cached=900000,tokens=1234000,requests=48,sessions=3,
                 cost=8.75,savings=6.5,unpriced=0,cacheRate=.75,activeDays=5,reasoning=9000)
    reading = dict(total=total,providers={'codex':total,'claude':dict(total,tokens=0,cost=0)},
                   models=[dict(total,name='A deliberately long model name that must stay inside its card')],
                   buckets=[dict(total,label=f'2026-11-{20+i:02}',cost=i/3,tokens=i*1000) for i in range(7)])
    return dict(ok=True,checked=1800000000,pricingDate='2026-11-26',partial=False,
                periods={p:dict(reading,total=dict(total,cost=c)) for p,c in [('today',8.75),('week',42.5),('month',90.2)]},
                activity=[dict(provider='codex',model='gpt-6.2-astra',last=1800000000,active=1)])


@unittest.skipUnless(agent_tests.QQuickView, 'requires Qt Quick')
class Dashboard(unittest.TestCase):
    setUpClass = classmethod(agent_tests.Agents.setUpClass.__func__)
    scene = agent_tests.Agents.scene

    def test_all_cards_fit_and_period_changes_preserve_provider_positions(self):
        content = '''
    Monet.AgentHistory { id: historyModel; objectName: "history"; presented:false }
    QtObject { id: limits; property var result:({}); property bool enabled:false; property string pending:""; property string problem:"" }
    Monet.TimeScrollView {
        id: scroll; anchors.fill:parent
        Monet.AgentOverview { id: overview; width:scroll.availableWidth; history:historyModel; codex:limits; claude:limits; presented:false; sessionSelected:false; widgetId:"test" }
    }
    function lookup(name,item=fixture) {
        if (item.objectName===name) return item
        for (const child of item.children) { const found=lookup(name,child); if (found) return found }
        return null
    }
    function point(name) { const c=lookup(name); const p=c.mapToItem(fixture,c.width/2,c.height/2); return JSON.stringify([p.x,p.y]) }
    function snapshot() {
        let errors=[]
        function visit(item,card) {
            if (!item.visible) return
            if (item.objectName.startsWith("notchAgent") && !item.objectName.startsWith("notchAgentPeriod") && item.objectName!=="notchAgentHistoryRefresh") card=item
            if (card && String(item).startsWith("QQuickText(")) {
                const p=item.mapToItem(card,0,0)
                if (p.x<-.1||p.y<-.1||p.x+item.width>card.width+.1||p.y+item.height>card.height+.1) errors.push([card.objectName,item.text,p.x,p.y,item.width,item.height])
            }
            for (const child of item.children) visit(child,card)
        }
        visit(overview,null)
        return JSON.stringify({errors:errors,positions:[lookup("notchAgent-codex").y,lookup("notchAgent-claude").y],
            width:overview.width,viewport:scroll.availableWidth,contentHeight:scroll.contentItem.contentHeight,viewHeight:scroll.height})
    }
    function scrollBottom() { scroll.contentItem.contentY=scroll.contentItem.contentHeight-scroll.availableHeight }
    function scrollTop() { scroll.contentItem.contentY=0 }
'''
        view, root = self.scene(content)
        history = root.findChild(QObject,'history'); history.accept(json.dumps(sample()))
        for width in (288,414):
            root.setProperty('width',width); view.resize(width,257);root.scrollTop();QTest.qWait(100)
            before=json.loads(root.snapshot())
            self.assertFalse(before['errors'],before)
            self.assertLessEqual(before['width'],before['viewport'])
            self.assertGreater(before['contentHeight'],before['viewHeight'])
            for period, amount in [('week',42.5),('month',90.2),('today',8.75)]:
                x,y=json.loads(root.point('notchAgentPeriod-'+period))
                QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(round(x),round(y)));QTest.qWait(40)
                self.assertEqual(history.property('period'),period)
                self.assertEqual(history.property('total').toVariant()['cost'],amount)
                after=json.loads(root.snapshot());self.assertFalse(after['errors'],after)
                self.assertEqual(after['positions'],before['positions'])
            root.scrollBottom();QTest.qWait(50)
            x,y=json.loads(root.point('notchAgent-session'))
            self.assertTrue(0<y<257,(x,y))

    def test_saved_totals_restore_and_failures_keep_the_previous_snapshot(self):
        cache=QSettings(str(Path(QStandardPaths.writableLocation(QStandardPaths.GenericCacheLocation))/'monet/notch-agent-history.conf'),QSettings.IniFormat)
        cache.clear();cache.setValue('reading',json.dumps(sample()));cache.setValue('period','month');cache.sync()
        with tempfile.TemporaryDirectory() as tmp:
            script=Path(tmp)/'reader.py'
            script.write_text('import time;time.sleep(.2);print(\'{"ok":false}\')')
            content='''property bool shown:false
                Monet.AgentHistory { objectName:"history"; presented:fixture.shown; reader:''' + json.dumps('/usr/bin/python3 '+str(script)) + ''' }'''
            view,root=self.scene(content);history=root.findChild(QObject,'history')
            self.assertEqual(history.property('total').toVariant()['cost'],90.2)
            root.setProperty('shown',True);QTest.qWait(50)
            self.assertTrue(history.property('pending'))
            self.assertEqual(history.property('result').toVariant(),sample())
            QTest.qWait(300)
            self.assertTrue(history.property('failed'))
            self.assertEqual(history.property('result').toVariant(),sample())
            history.accept(json.dumps(dict(sample(),checked=1800000100)))
            self.assertFalse(history.property('failed'))
            view.close()
            _,root2=self.scene(content)
            self.assertEqual(root2.findChild(QObject,'history').property('result').toVariant()['checked'],1800000100)
