"""A separate keyboard-focus owner for pointer-targeted mouse filter tests."""
from contextlib import contextmanager
import subprocess
import sys
import time


@contextmanager
def other_active_app(pump, kwin_script):
    proc = subprocess.Popen([sys.executable, __file__])
    try:
        end = time.monotonic() + 5
        while time.monotonic() < end:
            pump(.03)
            if kwin_script("""const w=windows().find(w=>w.caption==='Mouse peer');
                if (w) { w.frameGeometry={x:20,y:420,width:160,height:80};
                         workspace.activeWindow=w; }
                reply(Boolean(w && workspace.activeWindow===w))"""):
                break
        else:
            raise AssertionError("Could not focus mouse test peer")
        yield
    finally:
        proc.terminate()
        proc.wait(timeout=4)


if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication, QLabel
    app = QApplication([])
    app.setDesktopFileName("org.monet.MousePeer")
    window = QLabel("Mouse peer")
    window.setWindowTitle("Mouse peer")
    window.show()
    sys.exit(app.exec())
