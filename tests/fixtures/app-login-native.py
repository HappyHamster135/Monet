#!/usr/bin/python3
"""Private-bus fixture. Production has no automatic-approval test switch."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'linux/share/monet/passwords'))
assert os.environ.get('MONET_PASSWORDS_PRIVATE_BUS') == '1'

if sys.argv[1] == 'service':
    from app_offers import main
    sys.exit(main(str(Path(__file__).resolve())))
elif sys.argv[1] == '--app-login-prompt':
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtTest import QTest
    from app_prompt import OfferDialog, main
    execute = OfferDialog.exec
    def run(dialog):
        def interact():
            mode = os.environ.get('APP_LOGIN_FIXTURE_ACTION', 'decline')
            if mode == 'hold': return
            button = dialog.save if mode == 'save' else dialog.never if mode == 'never' else dialog.cancel
            QTest.mouseClick(button, Qt.LeftButton)
        QTimer.singleShot(100, interact)
        return execute(dialog)
    OfferDialog.exec = run
    sys.exit(main())
elif sys.argv[1] == '--app-login-fill':
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtTest import QTest
    from app_fill import FillDialog, main
    execute = FillDialog.exec
    def run(dialog):
        def interact():
            mode = os.environ.get('APP_LOGIN_FIXTURE_ACTION', 'decline')
            if mode == 'hold': return
            if mode != 'save': dialog.reject(); return
            if not dialog.loaded and not dialog.busy: dialog.load()
            if not dialog.loaded:
                QTimer.singleShot(20, interact); return
            if not dialog.accounts.count(): dialog.reject(); return
            dialog.accounts.setCurrentRow(0)
            QTest.mouseClick(dialog.fill, Qt.LeftButton)
        QTimer.singleShot(int(os.environ.get('APP_LOGIN_FIXTURE_FILL_DELAY','100')), interact)
        return execute(dialog)
    FillDialog.exec = run
    sys.exit(main())
elif sys.argv[1] in ('client', 'doc-save'):
    import dbus
    from app_offers import BUS_NAME, BUS_PATH
    bus = dbus.SessionBus()
    method='OfferDocumentLogin' if sys.argv[1]=='doc-save' else 'OfferLogin'
    prefix=[sys.argv[2]] if method=='OfferDocumentLogin' else []
    result = getattr(bus.get_object(BUS_NAME, BUS_PATH),method)(
        *prefix, 'fixture@example.invalid', 'synthetic-app-only', 'Test service', 'login',
        dbus_interface=BUS_NAME, timeout=15)
    print(str(result))
elif sys.argv[1] in ('get', 'doc-get'):
    import dbus,json
    from app_offers import BUS_NAME, BUS_PATH
    bus = dbus.SessionBus()
    method='RequestDocumentLogin' if sys.argv[1]=='doc-get' else 'RequestLogin'
    prefix=[sys.argv[2]] if method=='RequestDocumentLogin' else []
    result = getattr(bus.get_object(BUS_NAME, BUS_PATH),method)(
        *prefix, 'fixture@example.invalid', 'Test service' if prefix else sys.argv[2] if len(sys.argv)>2 else 'Test service', dbus_interface=BUS_NAME, timeout=15)
    print(json.dumps({'status':str(result['status']), 'matches':result.get('password')=='synthetic-app-only',
                      'has_secret':'password' in result}))
