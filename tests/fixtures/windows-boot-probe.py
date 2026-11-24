"""Exercise the installed boot command with synthetic disks and a private state directory."""
from pathlib import Path
import os
import shutil
import subprocess
import sys
import tempfile


def main(binary):
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        commands, helpers, payload, state = (root/name for name in
            ('bin', 'libexec', 'share/monet/windows', 'state'))
        for path in (commands, helpers, payload, state):
            path.mkdir(parents=True)
        shutil.copy2(binary, commands/'monet')
        (helpers/'monet-prepare-windows').touch()
        (payload/'monet-bridge.exe').touch()
        # No real disk commands are on PATH. Each scan consumes one reply.
        for path, body in [
            (commands/'lsblk', '''echo scan >> "$TRACE"
if [ -f "$READY" ]; then echo '/dev/mapper/windows ntfs'; exit 0; fi
case "$FIRST" in
    error) exit 1 ;;
    malformed) echo 'invalid';;
    encrypted) echo '/dev/sda2 BitLocker';;
    ntfs) echo '/dev/sda2 ntfs';;
    plain) printf '/dev/sda \\n/dev/sda1 btrfs\\n';;
esac'''),
            (helpers/'monet-windows-drive', '''echo "$1" >> "$TRACE"
: > "$READY"
exit 1'''),  # One mapper may have opened even when a later unlock failed.
            (commands/'mount', '''echo "mount ${5}" >> "$TRACE"; exit 1'''),
        ]:
            path.write_text('#!/bin/sh\n' + body + '\n')
            path.chmod(0o755)
        ready, trace = root/'ready', root/'trace'
        env = dict(os.environ, PATH=str(commands), MONET_STATE_DIR=str(state),
                   READY=str(ready), TRACE=str(trace))
        for first, stored, flags, expected in [
            ('plain', '', ['--unlock-saved'], ['scan']),
            ('plain', '', [], ['scan']),
            ('ntfs', '', ['--unlock-saved'], ['scan'] + ['mount /dev/sda2']*3),
            *[(first, '', ['--unlock-saved'], ['scan', 'unlock-saved', 'scan'] + ['mount /dev/mapper/windows']*3)
              for first in ('encrypted', 'error', 'malformed')],
            ('encrypted', 'staged', ['--unlock-saved'], ['scan', 'unlock-saved']),
            ('encrypted', 'installed', ['--unlock-saved'], ['scan', 'unlock-saved']),
            ('encrypted', 'staged', [], []),
        ]:
            trace.write_text('')
            ready.unlink(missing_ok=True)
            (state/'windows-setup').write_text(stored)
            (state/'windows-updater-current').touch()
            run = subprocess.run([commands/'monet', 'helper', 'stage-windows', *flags],
                           env=dict(env, FIRST=first), check=True, text=True, capture_output=True)
            actual = trace.read_text().splitlines()
            if actual != expected:
                raise AssertionError((first, stored, flags, actual, expected, run.stdout, run.stderr))
            result = (state/'windows-setup').read_text().strip()
            if result != (stored or 'not-found'):
                raise AssertionError((first, stored, flags, result))


if __name__ == '__main__':
    main(sys.argv[1])
