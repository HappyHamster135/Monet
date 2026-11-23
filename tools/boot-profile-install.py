#!/usr/bin/python3
"""Bound and diagnose the disposable installer VM, outside the timed boot test."""
import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import time


SNAPSHOT = ('date -u; free -m; df -hT; '
    'ps -eo pid,stat,wchan:32,pcpu,comm --sort=-pcpu | head -n 24; '
    'for p in /proc/pressure/*; do echo "$p"; cat "$p"; done; '
    'journalctl -k -n 25 --no-pager')


def installer_container():
    reply = subprocess.run(['/usr/bin/podman', 'ps', '-q', '--no-trunc',
        '--filter', 'label=bcvk.ephemeral=1'], capture_output=True, text=True,
        timeout=10, check=True)
    identifiers = reply.stdout.split()
    if len(identifiers) > 1:
        raise RuntimeError('Expected a single isolated installer container')
    if identifiers and not re.fullmatch(r'[0-9a-f]{64}', identifiers[0]):
        raise RuntimeError('Unexpected container identifier')
    return identifiers[0] if identifiers else None


def stop(process, container):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
    if container:
        try:
            subprocess.run(['/usr/bin/podman', 'rm', '-f', container],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        except subprocess.TimeoutExpired:
            print('Installer container cleanup timed out', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('disk', type=Path)
    parser.add_argument('logs', type=Path)
    parser.add_argument('--bcvk', type=Path,
        default=Path('target/boot-profile/bcvk-x86_64-unknown-linux-gnu'))
    parser.add_argument('--timeout', type=int, default=1200)
    args = parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        parser.error('This installer is only for disposable GitHub runners')
    if not 60 <= args.timeout <= 1800:
        parser.error('Installer timeout must be between 60 and 1800 seconds')
    if args.disk.exists() or args.disk.suffix != '.qcow2':
        parser.error('A new disposable qcow2 path is required')
    if installer_container():
        parser.error('An installer container is already running')
    args.logs.mkdir(parents=True, exist_ok=True)
    command = [str(args.bcvk.resolve()), 'to-disk',
        '--log-dir', 'journal,console=' + str(args.logs.resolve()),
        '--install-log', 'bootc=debug,ostree_ext=debug',
        '--format', 'qcow2', '--filesystem', 'btrfs', '--disk-size', '64G',
        '--vcpus', '2', '--memory', '8G', '--target-transport', 'containers-storage',
        args.image, str(args.disk.resolve())]
    started = time.monotonic()
    container = None
    next_snapshot = started + 60
    with (args.logs / 'install.log').open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT,
            start_new_session=True)
        try:
            while process.poll() is None:
                if time.monotonic() - started > args.timeout:
                    raise RuntimeError('Installer exceeded its bounded time window')
                if shutil.disk_usage(args.logs).free < 8 * 1024**3:
                    raise RuntimeError('Keeping 8 GiB installer disk headroom')
                if time.monotonic() >= next_snapshot:
                    print(f'Installer running: {time.monotonic()-started:.0f}s', flush=True)
                    with (args.logs / 'diagnostics.log').open('a') as snapshot:
                        snapshot.write('\n' + datetime.now(timezone.utc).isoformat() + '\n')
                        snapshot.flush()
                        try:
                            container = installer_container() or container
                            if container:
                                subprocess.run([str(args.bcvk.resolve()), 'ephemeral',
                                    'ssh', container, '--', SNAPSHOT], stdout=snapshot,
                                    stderr=subprocess.STDOUT, timeout=20)
                        except (subprocess.SubprocessError, OSError, RuntimeError) as error:
                            snapshot.write(str(error) + '\n')
                    next_snapshot = time.monotonic() + 60
                time.sleep(2)
            if process.returncode:
                raise RuntimeError(f'Installer exited with status {process.returncode}')
            if not args.disk.is_file() or not args.disk.stat().st_size:
                raise RuntimeError('Installer did not produce a disk')
        finally:
            stop(process, container)
    print(f'Installed test disk in {time.monotonic()-started:.0f}s (not a boot timing)', flush=True)


if __name__ == '__main__':
    main()
