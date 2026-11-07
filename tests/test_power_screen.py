"""Native power-page rendering and signal routing, without a power backend."""
import gettext
import importlib.machinery
import importlib.util
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
try:
    from PySide6.QtCore import QObject, QMetaObject, QUrl, Qt, Slot, QPoint
    from PySide6.QtGui import QFontDatabase, QGuiApplication
    from PySide6.QtQml import QQmlComponent
    from PySide6.QtQuick import QQuickView, QQuickItem
    from PySide6.QtTest import QTest
    QT = True
except ImportError:
    QT = False


if QT:
    class Words(QObject):
        def __init__(self, language='en'):
            super().__init__()
            self.words = gettext.translation('monet', str(ROOT/'linux/share/locale'), languages=[language], fallback=True)

        @staticmethod
        def format(text, args):
            for n, value in reversed(list(enumerate(args, 1))): text = text.replace('%'+str(n), str(value))
            return text

        @Slot(str, str, result=str)
        @Slot(str, str, 'QVariant', result=str)
        def i18nd(self, domain, text, *args): return self.format(self.words.gettext(text), args)

        @Slot(str, str, str, result=str)
        @Slot(str, str, str, 'QVariant', result=str)
        def i18ndc(self, domain, context, text, *args): return self.format(self.words.pgettext(context, text), args)

        @Slot(str, str, str, int, result=str)
        def i18ndp(self, domain, one, many, count): return self.format(self.words.ngettext(one, many, count), [count])


@unittest.skipUnless(QT, 'requires native Qt Quick and Plasma QML modules')
class PowerScreen(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
        os.environ.setdefault('QT_QUICK_BACKEND', 'software')
        cls.app = QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)
        for path in (ROOT/'linux/share/fonts/monet').glob('*.ttf'): QFontDatabase.addApplicationFont(str(path))

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='monet-power-test-')
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.fixtures = []
        self.addCleanup(self.close_views)

    def close_views(self):
        for view, words, warnings in self.fixtures:
            view.close(); view.deleteLater()
        QTest.qWait(20)
        self.fixtures.clear()

    def load(self, mode=-1, *, smoke=True, width=1280, height=800, pending=False,
             power=True, logout=True, sleep=True, hibernate=False, language='en', notes=False):
        wrapper = self.folder/f'case-{len(self.fixtures)}.qml'
        wrapper.write_text('import QtQuick\nimport org.kde.kirigami as Kirigami\n'
            f'import "{(ROOT/"linux/share/monet/logout").as_uri()}" as MonetPower\n'
            'Item { Kirigami.Theme.inherit: false; '
            f'Kirigami.Theme.backgroundColor: "{"#242321" if smoke else "#F3F1EC"}"; '
            'MonetPower.Logout { anchors.fill: parent } }\n')
        view = QQuickView(); view.setResizeMode(QQuickView.SizeRootObjectToView)
        warnings = []; view.engine().warnings.connect(lambda errors: warnings.extend(e.toString() for e in errors))
        words = Words(language); ctx = view.rootContext(); ctx.setContextObject(words)
        values = dict(sdtype=mode, ShutdownType=dict(ShutdownTypeDefault=-1, ShutdownTypeNone=0, ShutdownTypeReboot=1, ShutdownTypeHalt=2),
            maysd=power, canLogout=logout, spdMethods=dict(SuspendState=sleep, HibernateState=hibernate),
            softwareUpdatePending=pending, rebootToFirmwareSetup=notes, isUefi=True,
            rebootToBootLoaderMenu=False, rebootToBootLoaderEntry='Windows' if notes else '')
        for name, value in values.items(): ctx.setContextProperty(name, value)
        self.fixtures.append((view, words, warnings))
        view.setSource(QUrl.fromLocalFile(str(wrapper))); self.assertEqual(view.status(), QQuickView.Ready, warnings)
        view.resize(width, height); view.show(); view.requestActivate(); QTest.qWait(120)
        renderer = None
        if os.environ.get('MONET_TEST_GRAPHICS_API'):
            renderer = dict(api=view.rendererInterface().graphicsApi().name,
                            render_loop=os.environ.get('QSG_RENDER_LOOP','default'))
            self.assertEqual(renderer['api'],os.environ['MONET_TEST_GRAPHICS_API'])
            if os.environ.get('MONET_TEST_COLLECT_DRIVER')=='1':
                self.assertEqual(renderer['render_loop'],'basic')
                frames=[]
                def collect():
                    try:
                        info=view.rhi().driverInfo()
                        name=info.deviceName if isinstance(info.deviceName,str) else bytes(info.deviceName).decode('utf-8','replace')
                        frames.append(dict(device_name=name,device_type=info.deviceType.name))
                    except Exception as error:frames.append(dict(error=str(error)))
                view.afterFrameEnd.connect(collect,Qt.DirectConnection)
                try:
                    view.update()
                    for _ in range(100):
                        if frames:break
                        QTest.qWait(10)
                finally:view.afterFrameEnd.disconnect(collect)
                self.assertTrue(frames);self.assertNotIn('error',frames[0]);renderer.update(frames[0])
                self.assertNotEqual(renderer['device_type'],'CpuDevice')
                for software in ['llvmpipe','softpipe','swrast','swiftshader']:self.assertNotIn(software,renderer['device_name'].lower())
            if os.environ.get('MONET_NAV_CAPTURE'):
                (Path(os.environ['MONET_NAV_CAPTURE'])/f'renderer-{self._testMethodName}-{len(self.fixtures)}.json').write_text(json.dumps(renderer,indent=2)+'\n')
        if os.environ.get('MONET_TEST_EXPECT_DPR'):
            self.assertAlmostEqual(view.devicePixelRatio(),float(os.environ['MONET_TEST_EXPECT_DPR']),places=2)
        page = view.rootObject().findChild(QQuickItem, 'MonetPowerScreen'); self.assertIsNotNone(page)
        self.assertEqual(page.property('smoke'), smoke)
        events = []
        for name in ['logoutRequested', 'haltRequested', 'haltUpdateRequested', 'rebootRequested',
                     'rebootUpdateRequested', 'cancelRequested', 'lockScreenRequested', 'cancelSoftwareUpdateRequested']:
            getattr(page, name).connect(lambda n=name: events.append(n))
        page.suspendRequested.connect(lambda value: events.append(('suspend', value)))
        self.assertFalse(warnings, warnings)
        return view, page, events, warnings

    def item(self, page, name):
        item = page.findChild(QQuickItem, name); self.assertIsNotNone(item, name); return item

    def capture(self, view, name):
        destination = os.environ.get('MONET_POWER_CAPTURE')
        if destination:
            folder = Path(destination); folder.mkdir(parents=True, exist_ok=True)
            self.assertTrue(view.grabWindow().save(str(folder/(name+'.png'))))

    def test_mist_smoke_and_small_screen_render_without_clipping(self):
        for smoke, width, height, name in [(True,1280,800,'smoke'),(False,1280,800,'mist'),
                                           (True,480,800,'portrait'),(False,800,480,'short')]:
            with self.subTest(name=name):
                view, page, events, warnings = self.load(smoke=smoke,width=width,height=height)
                panel=self.item(page,'powerSheet'); cancel=self.item(page,'cancelChoice')
                origin=panel.mapToItem(page,0,0)
                self.assertGreaterEqual(origin.x(),0); self.assertGreaterEqual(origin.y(),0)
                self.assertLessEqual(origin.x()+panel.width(),page.width()+1); self.assertLessEqual(origin.y()+panel.height(),page.height()+1)
                self.assertTrue(cancel.isVisible()); p=cancel.mapToItem(page,0,0)
                self.assertGreaterEqual(p.y(),0); self.assertLessEqual(p.y()+cancel.height(),page.height()+1)
                self.assertFalse(events); self.assertFalse(warnings,warnings)
                self.capture(view,name)

    def test_available_actions_route_to_the_original_signals(self):
        for name, expected in [('sleepChoice',('suspend',2)),('hibernateChoice',('suspend',4)),
                               ('restartChoice','rebootRequested'),('shutDownChoice','haltRequested'),('logoutChoice','logoutRequested')]:
            with self.subTest(action=name):
                view,page,events,warnings=self.load(hibernate=True)
                button=self.item(page,name); self.assertTrue(button.isVisible())
                QMetaObject.invokeMethod(button,'clicked'); QTest.qWait(400)
                self.assertEqual(events,[expected]); self.assertFalse(warnings,warnings)

    def test_pending_updates_keep_update_and_plain_actions_separate(self):
        for name, expected in [('restartChoice','rebootUpdateRequested'),('plainRestartChoice','rebootRequested'),
                               ('shutDownChoice','haltUpdateRequested'),('plainShutDownChoice','haltRequested')]:
            with self.subTest(action=name):
                view,page,events,warnings=self.load(pending=True)
                self.capture(view,'updates')
                QMetaObject.invokeMethod(self.item(page,name),'clicked'); QTest.qWait(400)
                self.assertEqual(events,[expected]); self.assertFalse(warnings,warnings)

    def test_confirmation_pages_and_double_click_emit_only_one_action(self):
        for mode,pending,expected in [(1,False,'rebootRequested'),(2,False,'haltRequested'),
                                       (0,False,'logoutRequested'),(1,True,'rebootUpdateRequested'),(2,True,'haltUpdateRequested')]:
            with self.subTest(mode=mode,pending=pending):
                view,page,events,warnings=self.load(mode=mode,pending=pending,notes=mode==1)
                button=self.item(page,'goPill'); self.assertTrue(button.isVisible())
                self.capture(view,('restart' if mode==1 else 'shutdown' if mode==2 else 'logout')+('-updates' if pending else ''))
                QMetaObject.invokeMethod(button,'clicked'); QMetaObject.invokeMethod(button,'clicked'); QTest.qWait(400)
                self.assertEqual(events,[expected]); self.assertFalse(warnings,warnings)

    def test_capabilities_hide_unavailable_actions_and_disable_countdown(self):
        view,page,events,warnings=self.load(power=False,logout=False,sleep=False)
        for name in ['sleepChoice','hibernateChoice','restartChoice','shutDownChoice','logoutChoice']:
            self.assertFalse(self.item(page,name).isVisible(),name)
        view,page,events,warnings=self.load(mode=1,power=False)
        self.assertFalse(page.property('counting')); self.assertFalse(self.item(page,'goPill').isVisible())
        QMetaObject.invokeMethod(page,'go'); QTest.qWait(400); self.assertFalse(events)
        self.assertFalse(warnings,warnings)

    def test_transition_application_review_does_not_repeat_a_power_action(self):
        view,page,events,warnings=self.load(mode=1)
        reviews=[];page.showApplicationsRequested.connect(lambda:reviews.append(True))
        QMetaObject.invokeMethod(self.item(page,'goPill'),'clicked');QTest.qWait(400)
        self.assertEqual(events,['rebootRequested'])
        button=self.item(page,'showApplications');self.assertFalse(button.isVisible())
        page.setProperty('offerApplicationReview',True);QTest.qWait(20)
        self.assertTrue(button.isVisible())
        point=button.mapToScene(button.boundingRect().center()).toPoint()
        QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,point);QTest.qWait(20)
        self.assertEqual(reviews,[True]);self.assertEqual(events,['rebootRequested'])
        self.assertFalse(warnings,warnings)

    def test_escape_and_outside_click_cancel_without_power_actions(self):
        view,page,events,warnings=self.load()
        QTest.keyClick(view,Qt.Key_Escape); QTest.qWait(20)
        self.assertEqual(events,['cancelRequested']); self.assertFalse(warnings,warnings)

    def test_mouse_highlight_stays_on_across_each_card_and_its_children(self):
        for width,height,pending in [(1280,800,False),(480,800,False),(800,400,True)]:
            view,page,events,warnings=self.load(width=width,height=height,pending=pending)
            scroll=self.item(page,'powerFlickable')
            for name in ['sleepChoice','restartChoice','logoutChoice']:
                button=self.item(page,name)
                button.forceActiveFocus(Qt.TabFocusReason);QTest.qWait(30)
                # Include the far edge where an unneeded ScrollView bar used
                # to intercept hover, plus the icon, label and arrow.
                for x in [3,30,65,button.width()/2,button.width()-3]:
                    point=button.mapToItem(view.contentItem(),x,button.height()/2)
                    QTest.mouseMove(view,point.toPoint());QTest.qWait(20)
                    self.assertTrue(button.property('hovered'),(width,height,name,x))
                    before=button.property('background').property('color')
                    QTest.qWait(80)
                    self.assertTrue(button.property('hovered'),(width,height,name,x))
                    self.assertEqual(button.property('background').property('color'),before)
            self.assertFalse(events);self.assertFalse(warnings,warnings)
        view,page,events,warnings=self.load()
        QTest.mouseClick(view,Qt.LeftButton,Qt.NoModifier,QPoint(5,5)); QTest.qWait(20)
        self.assertEqual(events,['cancelRequested']); self.assertFalse(warnings,warnings)

    def test_tab_arrows_and_both_enter_keys_keep_focus_and_stop_countdown(self):
        for key in [Qt.Key_Return,Qt.Key_Enter]:
            view,page,events,warnings=self.load(mode=1)
            cancel=self.item(page,'cancelChoice'); cancel.forceActiveFocus(Qt.TabFocusReason)
            QTest.keyClick(view,Qt.Key_Tab); QTest.qWait(20)
            self.assertFalse(page.property('counting'))
            self.item(page,'goPill').forceActiveFocus(Qt.TabFocusReason)
            QTest.keyClick(view,key); QTest.qWait(400)
            self.assertEqual(events,['rebootRequested']); self.assertFalse(warnings,warnings)
        view,page,events,warnings=self.load()
        self.item(page,'sleepChoice').forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(view,Qt.Key_Right); QTest.qWait(20)
        self.assertEqual(view.activeFocusItem(),self.item(page,'restartChoice'))
        self.assertFalse(events); self.assertFalse(warnings,warnings)

    def test_countdown_uses_the_requested_action(self):
        view,page,events,warnings=self.load(mode=2,pending=True)
        page.setProperty('remaining',1); QTest.qWait(1500)
        self.assertEqual(events,['haltUpdateRequested']); self.assertFalse(warnings,warnings)

    def test_short_translated_update_page_reveals_large_text_controls(self):
        view,page,events,warnings=self.load(width=520,height=400,pending=True,hibernate=True,language='de')
        page.setProperty('fontScale',1.6); QTest.qWait(60)
        scroll=self.item(page,'powerFlickable')
        self.assertGreater(scroll.property('contentHeight'),scroll.height())
        for name in ['sleepChoice','hibernateChoice','restartChoice','plainRestartChoice',
                     'shutDownChoice','plainShutDownChoice','logoutChoice']:
            button=self.item(page,name); button.forceActiveFocus(Qt.TabFocusReason); QTest.qWait(30)
            point=button.mapToItem(scroll,0,0)
            self.assertGreaterEqual(point.y(),-1,name)
            self.assertLessEqual(point.y()+button.height(),scroll.height()+1,name)
        self.capture(view,'short-large-text')
        self.assertTrue(self.item(page,'cancelChoice').isVisible())
        self.assertFalse(events); self.assertFalse(warnings,warnings)

    def test_keyboard_space_and_rtl_direction(self):
        view,page,events,warnings=self.load()
        self.item(page,'sleepChoice').forceActiveFocus(Qt.TabFocusReason)
        QTest.keyClick(view,Qt.Key_Space); QTest.qWait(20)
        self.assertEqual(events,[('suspend',2)]); self.assertFalse(warnings,warnings)
        original=self.app.layoutDirection(); self.app.setLayoutDirection(Qt.RightToLeft)
        try:
            view,page,events,warnings=self.load(language='ar')
            self.item(page,'sleepChoice').forceActiveFocus(Qt.TabFocusReason)
            QTest.keyClick(view,Qt.Key_Left); QTest.qWait(20)
            self.assertEqual(view.activeFocusItem(),self.item(page,'restartChoice'))
            self.capture(view,'rtl')
            self.assertFalse(events); self.assertFalse(warnings,warnings)
        finally: self.app.setLayoutDirection(original)

    def second_page(self, view):
        component=QQmlComponent(view.engine(),QUrl.fromLocalFile(str(ROOT/'linux/share/monet/logout/Logout.qml')))
        page=component.create(view.rootContext());self.assertIsNotNone(page,[e.toString() for e in component.errors()])
        page.setParent(view.rootObject());page.setParentItem(view.rootObject())
        page.setWidth(view.width());page.setHeight(view.height());QTest.qWait(20)
        return page

    def test_two_screens_cannot_commit_different_actions_during_the_fade(self):
        view,page,events,warnings=self.load()
        other=self.second_page(view);other_events=[]
        other.haltRequested.connect(lambda:other_events.append('haltRequested'))
        QMetaObject.invokeMethod(self.item(page,'restartChoice'),'clicked')
        QMetaObject.invokeMethod(self.item(other,'shutDownChoice'),'clicked');QTest.qWait(400)
        self.assertEqual(events,['rebootRequested']);self.assertEqual(other_events,[])
        self.assertFalse(warnings,warnings)

    def test_removing_the_screen_that_owned_an_action_releases_the_claim(self):
        view,page,events,warnings=self.load()
        other=self.second_page(view);other_events=[]
        other.haltRequested.connect(lambda:other_events.append('haltRequested'))
        QMetaObject.invokeMethod(self.item(page,'restartChoice'),'clicked')
        page.deleteLater();QTest.qWait(20)
        QMetaObject.invokeMethod(self.item(other,'shutDownChoice'),'clicked');QTest.qWait(400)
        self.assertEqual(events,[]);self.assertEqual(other_events,['haltRequested'])
        self.assertFalse(warnings,warnings)

    def test_countdown_cancellation_is_shared_between_screens(self):
        view,page,events,warnings=self.load(mode=1)
        other=self.second_page(view)
        self.assertTrue(page.property('counting'));self.assertTrue(other.property('counting'))
        QMetaObject.invokeMethod(page,'stopCounting')
        self.assertFalse(page.property('counting'));self.assertFalse(other.property('counting'))
        page.setProperty('remaining',1);other.setProperty('remaining',1);QTest.qWait(1100)
        self.assertFalse(events);self.assertFalse(warnings,warnings)


if __name__=='__main__': unittest.main()
