"""Remove only an abandoned seatd socket before restarting the Setup display."""
import errno
import os
from pathlib import Path
import socket
import stat
import sys


def ready(path=Path('/run/seatd.sock')):
    try:
        before = path.lstat()
    except FileNotFoundError:
        return True
    if not stat.S_ISSOCK(before.st_mode) or before.st_uid != os.geteuid():
        return False
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
        probe.settimeout(1)
        if probe.connect_ex(str(path)) != errno.ECONNREFUSED:
            return False
    # An active server or a replacement file is never removed.
    try:
        after = path.lstat()
        if (before.st_dev, before.st_ino) != (after.st_dev, after.st_ino):
            return False
        path.unlink()
    except FileNotFoundError:
        pass
    return True


if __name__ == '__main__':
    try:
        available = ready()
    except OSError as error:
        print(f'Could not check the Setup display socket: {error}', file=sys.stderr)
        available = False
    if not available:
        print('Setup is waiting for its display socket to be available.', file=sys.stderr)
    sys.exit(0 if available else 1)
