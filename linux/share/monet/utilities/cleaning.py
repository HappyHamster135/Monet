"""Request a timed cleaning screen from the user's existing Plasma locker."""
from pathlib import Path
import sys
import time

import dbus
from PySide6.QtCore import QLockFile, QSettings, QStandardPaths

from actions import tr


def start(seconds, locker, settings):
    if seconds not in (30, 60, 120):
        raise ValueError(tr("Choose a cleaning time from the list."))
    if locker.GetActive(timeout=3):
        raise ValueError(tr("The screen is already locked."))
    deadline = time.time_ns() // 1_000_000 + seconds * 1000
    settings.setValue("Cleaning/deadline", deadline)
    settings.sync()
    if settings.status() != QSettings.NoError:
        raise OSError(tr("Could not start the cleaning timer."))
    try:
        locker.Lock(timeout=10)
    except dbus.DBusException:
        settings.sync()
        if str(settings.value("Cleaning/deadline")) == str(deadline):
            settings.remove("Cleaning/deadline")
            settings.sync()
        raise


def main():
    runtime = QStandardPaths.writableLocation(QStandardPaths.RuntimeLocation)
    if not QStandardPaths.locate(QStandardPaths.GenericDataLocation,
                                 "plasma/shells/org.kde.plasma.desktop/contents/lockscreen/CleaningScreen.qml"):
        raise OSError(tr("Cleaning mode requires the Monet lock screen."))
    if not runtime:
        raise OSError(tr("Could not start the cleaning timer."))
    settings = QSettings(str(Path(runtime) / "monet-cleaning.ini"), QSettings.IniFormat)
    service = "org.freedesktop.ScreenSaver"
    bus = dbus.SessionBus()
    owner = bus.get_name_owner(service)
    locker = dbus.Interface(bus.get_object(owner, "/ScreenSaver"), service)
    # A second activation cannot replace the first request before Lock replies.
    guard = QLockFile(str(Path(runtime) / "monet-cleaning-request.lock"))
    if not guard.tryLock(0):
        if guard.error() == QLockFile.LockFailedError:
            return
        raise OSError(tr("Could not start the cleaning timer."))
    try:
        start(int(sys.argv[1]), locker, settings)
    finally:
        guard.unlock()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(2)
    try:
        main()
    except dbus.DBusException:
        sys.exit(tr("The desktop could not lock the screen."))
    except (ValueError, OSError) as error:
        sys.exit(str(error))
