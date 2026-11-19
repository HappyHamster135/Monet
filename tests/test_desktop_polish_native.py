"""Native desktop checks require the candidate Task Manager test image."""
import importlib.util
import importlib.machinery
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.environ.get('MONET_TASK_MANAGER_NATIVE'), 'candidate native desktop image')
class NativePolish(unittest.TestCase):
    def fixture(self, name):
        with tempfile.TemporaryDirectory() as folder:
            subprocess.run([sys.executable,str(ROOT/'tests/fixtures'/name),folder], check=True, timeout=90)
            result = Path(folder)/'result.json'
            self.assertTrue(json.loads(result.read_text())['passed'])

    def test_region_capture_warms_without_taking_a_screenshot(self):
        self.fixture('screenshot-ready.py')

    def test_task_manager_graphics_reset_and_editor_preset(self):
        self.fixture('task-manager-editor.py')

    def test_flatpak_native_unused_api_recognizes_an_empty_disposable_user_installation(self):
        spec=importlib.util.spec_from_file_location('storage_details',ROOT/'linux/share/monet/monet_runtime/storage_details.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        # The fixture intentionally disconnects the system bus. Exercise the real
        # user-installation API without asking the privileged system helper.
        import gi
        gi.require_version('Flatpak','1.0')
        from gi.repository import Flatpak
        with patch.object(Flatpak,'get_system_installations',return_value=[]):
            self.assertEqual(module.unused_refs(), [])


@unittest.skipUnless(os.environ.get('MONET_TASK_MANAGER_NATIVE'), 'candidate native desktop image')
class PerformancePage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtGui import QGuiApplication
        cls.app=QGuiApplication.instance() or QGuiApplication([])
        cls.app.setQuitOnLastWindowClosed(False)

    def test_full_performance_component_loads_and_graphics_stays_selected_at_both_widths(self):
        from PySide6.QtCore import QObject, QUrl, Slot
        from PySide6.QtQml import QQmlEngine, QQmlComponent
        from PySide6.QtQuick import QQuickWindow
        from PySide6.QtTest import QTest
        loader=importlib.machinery.SourceFileLoader('performance_words',str(ROOT/'linux/libexec/monet-games'))
        module=importlib.util.module_from_spec(importlib.util.spec_from_loader(loader.name,loader));loader.exec_module(module)
        class Words(module.Words):
            @Slot(str,str,result=str)
            @Slot(str,str,'QVariant',result=str)
            @Slot(str,str,'QVariant','QVariant',result=str)
            @Slot(str,str,'QVariant','QVariant','QVariant',result=str)
            def i18nd(self,domain,text,*values): return self.i18n(text,*values)
        words=Words();engine=QQmlEngine();engine.rootContext().setContextObject(words)
        path=ROOT/'linux/share/ksysguard/sensorfaces/org.monet.performance/contents/ui/Performance.qml'
        component=QQmlComponent(engine,QUrl.fromLocalFile(str(path)))
        self.assertFalse(component.isError(),[e.toString() for e in component.errors()])
        item=component.createWithInitialProperties(dict(graphicsOnly=True,section=2,paused=True,width=900,height=650))
        self.assertIsNotNone(item,[e.toString() for e in component.errors()])
        window=QQuickWindow();window.resize(900,650);item.setParentItem(window.contentItem());window.show()
        def find(name):
            pending=[item]
            while pending:
                node=pending.pop()
                if node.objectName()==name:return node
                pending.extend(node.childItems())
        try:
            for width in (900,430,900):
                item.setWidth(width);QTest.qWait(50)
                self.assertEqual(item.property('section'),2)
                self.assertFalse(find('resourceTabs').isVisible())
                self.assertFalse(find('resourceSelector').isVisible())
        finally:
            window.close();item.deleteLater();component.deleteLater();engine.deleteLater();QTest.qWait(20)


if __name__=='__main__': unittest.main()
