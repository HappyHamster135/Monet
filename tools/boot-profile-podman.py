#!/usr/bin/python3
"""Runner-only bcvk adapter: allow its mount setup and preserve setup failures.

bcvk already asks for all capabilities, unconfined seccomp and disabled SELinux
labels. Ubuntu additionally confines mounts with AppArmor. Scope that exception
to bcvk's labelled installer container, and keep its entrypoint output outside
the automatically removed container. Ordinary Podman commands pass through.
Never install this adapter on an end user's PC.
"""
import os
from pathlib import Path
import sys


def prepare(arguments):
    arguments = list(arguments)
    if not arguments or arguments[0] != 'run' or '--label=bcvk.ephemeral=1' not in arguments:
        return arguments
    if any(arg.startswith('--security-opt=apparmor=') for arg in arguments):
        raise ValueError('Review bcvk’s new AppArmor policy before adapting it')
    arguments.insert(1, '--security-opt=apparmor=unconfined')
    suffix = ':/var/lib/bcvk/entrypoint'
    mounts = [arg for arg in arguments if arg.endswith(suffix)]
    if len(mounts) != 1:
        raise ValueError('Expected the pinned bcvk entrypoint mount')
    source = Path(mounts[0][:-len(suffix)])
    if source.is_symlink() or not source.is_file():
        raise ValueError('Expected a regular generated entrypoint')
    script = source.read_text()
    header = '#!/bin/bash\nset -euo pipefail\n'
    if not script.startswith(header):
        raise ValueError('Review the changed bcvk entrypoint before adapting it')
    source.write_text(script.replace(header, header +
        'exec > /run/bcvk-console-log/entrypoint.log 2>&1\nset -x\n', 1))
    return arguments


if __name__ == '__main__':
    if '--label=bcvk.ephemeral=1' in sys.argv and os.environ.get('GITHUB_ACTIONS') != 'true':
        raise SystemExit('This adapter is only for disposable GitHub runners')
    os.execv('/usr/bin/podman', ['podman', *prepare(sys.argv[1:])])
