"""Real shipped catalogs route everyday queries to the exact read-only controls."""
import gettext
from pathlib import Path
import unittest
from unittest.mock import patch

from tests.test_look import quick_helper

ROOT = Path(__file__).resolve().parents[1]
# User phrases are separate from the catalog's complete synonym lists.
QUERIES = {
    'ar': ('إيقاف قفل الشاشة', 'مجلد التنزيلات', 'حد شحن البطارية', 'إبقاء الشاشة مضاءة'),
    'cs': ('vypnout zamykání obrazovky', 'složka pro stahování', 'limit nabíjení baterie', 'ponechat obrazovku zapnutou'),
    'da': ('deaktiver skærmlås', 'downloadmappe', 'batteriets opladningsgrænse', 'hold skærmen tændt'),
    'de': ('Bildschirmsperre deaktivieren', 'Downloadordner', 'Ladelimit des Akkus', 'Bildschirm eingeschaltet lassen'),
    'el': ('απενεργοποίηση κλειδώματος οθόνης', 'φάκελος λήψεων', 'όριο φόρτισης μπαταρίας', 'διατήρηση οθόνης ενεργής'),
    'es': ('desactivar bloqueo de pantalla', 'carpeta de descargas', 'límite de carga de la batería', 'mantener la pantalla encendida'),
    'fi': ('poista näytön lukitus käytöstä', 'latauskansio', 'akun latausraja', 'pidä näyttö päällä'),
    'fr': ('désactiver le verrouillage de l’écran', 'dossier de téléchargement', 'limite de charge de la batterie', 'garder l’écran allumé'),
    'he': ('ביטול נעילת המסך', 'תיקיית הורדות', 'מגבלת טעינת הסוללה', 'השארת המסך דלוק'),
    'hi': ('स्क्रीन लॉक बंद करें', 'डाउनलोड फ़ोल्डर', 'बैटरी चार्ज सीमा', 'स्क्रीन चालू रखें'),
    'hu': ('képernyőzár kikapcsolása', 'letöltési mappa', 'akkumulátor töltési korlátja', 'képernyő bekapcsolva tartása'),
    'id': ('nonaktifkan kunci layar', 'folder unduhan', 'batas pengisian baterai', 'biarkan layar menyala'),
    'it': ('disattivare il blocco schermo', 'cartella dei download', 'limite di carica della batteria', 'mantieni lo schermo acceso'),
    'ja': ('画面ロックを無効にする', 'ダウンロードフォルダー', 'バッテリーの充電上限', '画面をオンのままにする'),
    'ko': ('화면 잠금 끄기', '다운로드 폴더', '배터리 충전 제한', '화면 켜진 상태로 유지'),
    'nb': ('deaktiver skjermlås', 'nedlastingsmappe', 'batteriets ladegrense', 'hold skjermen på'),
    'nl': ('schermvergrendeling uitschakelen', 'downloadmap', 'oplaadlimiet van de accu', 'scherm aan laten'),
    'pl': ('wyłącz blokowanie ekranu', 'folder pobierania', 'limit ładowania baterii', 'pozostaw ekran włączony'),
    'pt': ('desativar bloqueio do ecrã', 'pasta de transferências', 'limite de carga da bateria', 'manter o ecrã ligado'),
    'pt_BR': ('desativar bloqueio de tela', 'pasta de downloads', 'limite de carga da bateria', 'manter a tela ligada'),
    'ro': ('dezactivează blocarea ecranului', 'dosar de descărcări', 'limita de încărcare a bateriei', 'menține ecranul pornit'),
    'ru': ('отключить блокировку экрана', 'папка загрузок', 'предел заряда батареи', 'не выключать экран'),
    'sv': ('sluta låsa skärmen', 'nedladdningsmapp', 'laddningsgräns', 'håll skärmen på'),
    'th': ('ปิดการล็อกหน้าจอ', 'โฟลเดอร์ดาวน์โหลด', 'จำกัดการชาร์จแบตเตอรี่', 'เปิดหน้าจอค้างไว้'),
    'tr': ('ekran kilidini devre dışı bırak', 'indirme klasörü', 'pil şarj sınırı', 'ekranı açık tut'),
    'uk': ('вимкнути блокування екрана', 'тека завантажень', 'обмеження заряду батареї', 'не вимикати екран'),
    'vi': ('tắt khóa màn hình', 'thư mục tải xuống', 'giới hạn sạc pin', 'giữ màn hình bật'),
    'zh_CN': ('关闭屏幕锁定', '下载文件夹', '电池充电上限', '保持屏幕开启'),
    'zh_TW': ('關閉螢幕鎖定', '下載資料夾', '電池充電上限', '保持螢幕開啟'),
}
TARGETS = ('power#lock', 'storage#downloads', 'power#battery-limit', 'power#keep-awake')


class SearchLocalization(unittest.TestCase):
    def test_supported_catalogs_route_native_phrases_without_setting_changes(self):
        q = quick_helper()
        self.assertEqual(set(QUERIES), {p.stem for p in (ROOT/'po').glob('*.po')})
        english = {x['target']: x for x in q.search_catalog() if x['target'] in TARGETS}
        with patch.object(q, 'kwrite') as write, patch.object(q, 'open_settings') as opened:
            for language, phrases in QUERIES.items():
                with self.subTest(language=language):
                    words = gettext.translation('monet', localedir=str(ROOT/'linux/share/locale'), languages=[language])
                    with patch.object(q, '_', words.gettext):
                        for query, target in zip(phrases, TARGETS):
                            results = q.everyday_search(query)
                            self.assertTrue(results, (language, query))
                            result = results[0]
                            self.assertEqual(result['target'], target, (language, query, result))
                            self.assertNotEqual(result['name'], english[target]['name'])
                            self.assertNotEqual(result['detail'], english[target]['detail'])
                            self.assertTrue(q.open_search_result(result['id']))
                            self.assertEqual(opened.call_args.args, (target,))
            write.assert_not_called()

    def test_english_fallback_keeps_all_four_destinations_in_every_catalog(self):
        q = quick_helper()
        for language in QUERIES:
            words = gettext.translation('monet', localedir=str(ROOT/'linux/share/locale'), languages=[language])
            with self.subTest(language=language), patch.object(q, '_', words.gettext):
                for query, target in zip(('stop screen locking', 'download folder', 'battery limit', 'keep awake'), TARGETS):
                    self.assertEqual(q.everyday_search(query)[0]['target'], target)
