"""Real Qt requests: failures, cancellation and retries in both weather surfaces."""
import json
import os
from pathlib import Path
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit
try:
    from PySide6.QtCore import QObject, Slot, QUrl
    from PySide6.QtWidgets import QApplication
    from PySide6.QtQml import QQmlEngine, QQmlComponent
    from PySide6.QtTest import QTest
except ImportError:
    QApplication = None
ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(QApplication, 'Qt native runtime')
class PlaceSearch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args): pass
            def do_GET(self):
                query = parse_qs(urlsplit(self.path).query)['name'][0]
                if query in {'Slow', 'Timeout'}: time.sleep(.3)
                data = {} if query == 'Missing' else {'results': [{'name': query, 'latitude': 59.3, 'longitude': 18.1}]}
                if query == 'Invalid': data = {'error': True}
                self.send_response(503 if query == 'Offline' else 200)
                self.end_headers()
                try: self.wfile.write(json.dumps(data).encode())
                except (BrokenPipeError, ConnectionResetError): pass
        cls.app = QApplication.instance() or QApplication([])
        cls.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True); cls.thread.start()
    @classmethod
    def tearDownClass(cls): cls.server.shutdown(); cls.server.server_close()
    def setUp(self):
        class Words(QObject):
            @Slot(str, str, result=str)
            def i18nd(self, domain, text): return text
        self.engine = QQmlEngine(); self.words = Words(); self.engine.rootContext().setContextObject(self.words)
        file = ROOT / 'linux/share/plasma/plasmoids/org.monet.weather/contents/ui/PlaceSearch.qml'
        self.component = QQmlComponent(self.engine, QUrl.fromLocalFile(str(file)))
        self.item = self.component.create()
        self.assertIsNotNone(self.item, [e.toString() for e in self.component.errors()])
        self.item.setProperty('endpoint', f'http://127.0.0.1:{self.server.server_port}/search')
        self.obj = self.engine.newQObject(self.item)
    def tearDown(self): self.item.deleteLater(); QTest.qWait(10)
    def call(self, name, *args):
        self.obj.property(name).call([self.engine.toScriptValue(arg) for arg in args])
    def results(self): return self.obj.property('results').toVariant()
    def wait(self):
        for _ in range(200):
            QTest.qWait(10)
            if not self.item.property('busy'): break
        self.assertFalse(self.item.property('busy'))
    def test_unicode_place_and_empty_results(self):
        self.call('find', ' Västerås '); self.wait()
        self.assertEqual(self.results()[0]['name'], 'Västerås')
        self.call('find', 'Missing'); self.wait()
        self.assertEqual(self.results(), []); self.assertEqual(self.item.property('problem'), '')
    def test_failure_is_not_a_missing_town_and_retry_recovers(self):
        for query in ['Offline', 'Invalid']:
            self.call('find', query); self.wait()
            self.assertTrue(self.item.property('problem')); self.assertEqual(self.results(), [])
        self.call('find', 'Stockholm'); self.wait()
        self.assertEqual(self.results()[0]['name'], 'Stockholm'); self.assertEqual(self.item.property('problem'), '')
    def test_new_query_cannot_be_overwritten_by_old_response(self):
        self.call('find', 'Slow'); QTest.qWait(25)
        self.call('find', 'Uppsala'); self.wait(); QTest.qWait(400)
        self.assertEqual(self.results()[0]['name'], 'Uppsala')
    def test_cancel_immediately_removes_old_results_and_invalidates_inflight(self):
        self.call('find', 'Slow'); QTest.qWait(25); self.call('cancel'); QTest.qWait(400)
        self.assertEqual(self.results(), []); self.assertFalse(self.item.property('busy'))
    def test_deadline_reports_timeout_and_can_retry(self):
        self.item.setProperty('timeout', 60); self.call('find', 'Timeout'); self.wait()
        self.assertIn('timed out', self.item.property('problem'))
        self.call('find', 'Malmö'); self.wait(); self.assertEqual(self.results()[0]['name'], 'Malmö')


if __name__ == '__main__': unittest.main()
