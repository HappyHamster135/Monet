"""Short-lived Files tools; importing this package does not load Qt."""
import json
import sys


def main(args):
    if not args:
        return 2
    if args[0] == 'preview' and len(args) == 2:
        from .preview import show
        return show(args[1])
    if args[0] == 'preview-hex' and len(args) == 2 and len(args[1]) < 32768:
        from .preview import show
        return show(bytes.fromhex(args[1]).decode())
    if args[0] == '--preview-data' and len(args) == 2:
        from .preview import data
        print(json.dumps(data(args[1]), ensure_ascii=True))
        return 0
    if args[0] in {'transfers', 'stacks-toggle', 'stacks-disable', 'stacks-reconcile'} and len(args) == 1:
        from .desktop import activate
        activate(args[0])
        return 0
    if args[0] in {'stacks-disable', 'stacks-enable'} and len(args) == 2 and args[1].isdigit():
        from .desktop import activate
        activate(args[0], int(args[1]))
        return 0
    if args[0] == 'stacks-list' and len(args) == 2 and args[1] in {'type', 'date'}:
        from .desktop import stacks
        print(json.dumps(stacks(args[1]), ensure_ascii=True))
        return 0
    if args[0] == 'open' and len(args) == 2:
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices, QGuiApplication
        app = QGuiApplication(sys.argv[:1])
        return 0 if QDesktopServices.openUrl(QUrl.fromLocalFile(bytes.fromhex(args[1]).decode())) else 1
    return 2
