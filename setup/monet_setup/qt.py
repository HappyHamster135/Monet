"""Qt for Python: PySide6 on the USB stick, PyQt6 where that's what's installed
(the screenshot tests). The two differ only in names for these few things."""

try:
    from PySide6.QtCore import Property, QObject, QProcess, QTimer, QUrl, Signal, Slot  # noqa: F401
    from PySide6.QtGui import QFontDatabase, QGuiApplication  # noqa: F401
    from PySide6.QtQml import QQmlApplicationEngine  # noqa: F401
    BINDING = "PySide6"
except ImportError:
    from PyQt6.QtCore import QObject, QProcess, QTimer, QUrl  # noqa: F401
    from PyQt6.QtCore import pyqtProperty as Property, pyqtSignal as Signal, pyqtSlot as Slot  # noqa: F401
    from PyQt6.QtGui import QFontDatabase, QGuiApplication  # noqa: F401
    from PyQt6.QtQml import QQmlApplicationEngine  # noqa: F401
    BINDING = "PyQt6"
