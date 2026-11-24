#!/usr/bin/python3
"""Install only a new CI disk-image file, outside the timed KVM boot test.

Uses bootc's documented --generic-image --via-loopback path. No physical block
device is accepted. Generic mode does not register boot entries in host firmware.
"""
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
    'dmesg --ctime | tail -n 25')


def installer_container():
    reply = subprocess.run(['/usr/bin/podman', 'ps', '-q', '--no-trunc',
        '--filter', 'label=monet.boot-profile.install=1'], capture_output=True, text=True,
        timeout=10, check=True)
    identifiers = reply.stdout.split()
    if len(identifiers) > 1:
        raise RuntimeError('Expected a single isolated installer container')
    if identifiers and not re.fullmatch(r'[0-9a-f]{64}', identifiers[0]):
        raise RuntimeError('Unexpected container identifier')
    return identifiers[0] if identifiers else None


def stop(process, container):
    if process.poll() is None:
        try: os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError: pass
        try:
            process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: pass
            process.wait()
    if container:
        try:
            subprocess.run(['/usr/bin/podman', 'rm', '-f', container],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=20)
        except subprocess.TimeoutExpired:
            print('Installer container cleanup timed out', flush=True)


def detach_image(disk):
    # Only detach loop devices backed by the exact new file this helper made.
    reply = subprocess.run(['losetup','--associated',str(disk),'--output','NAME',
        '--noheadings'],capture_output=True,text=True,check=True,timeout=10)
    for device in reply.stdout.split():
        if not re.fullmatch(r'/dev/loop[0-9]+',device):
            raise RuntimeError('Unexpected loop device; refusing to detach it')
        subprocess.run(['losetup','--detach',device],check=True,timeout=10)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('disk', type=Path)
    parser.add_argument('logs', type=Path)
    parser.add_argument('--timeout', type=int, default=1200)
    args = parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS') != 'true':
        parser.error('This installer is only for disposable GitHub runners')
    if not 60 <= args.timeout <= 1800:
        parser.error('Installer timeout must be between 60 and 1800 seconds')
    args.disk=args.disk.resolve()
    workspace=Path(__file__).resolve().parents[1]/'target/boot-profile'
    if (args.disk.exists() or args.disk.suffix != '.raw'
            or not args.disk.is_relative_to(workspace)):
        parser.error('A new raw disk file inside target/boot-profile is required')
    if installer_container():
        parser.error('An installer container is already running')
    args.logs.mkdir(parents=True, exist_ok=True)
    with args.disk.open('xb') as disk:
        disk.truncate(64*1024**3)
    command = ['/usr/bin/podman','run','--rm','--privileged','--pid=host','--ipc=host',
        '--label=monet.boot-profile.install=1','--security-opt=label=disable',
        '--cpus='+str(min(2,len(os.sched_getaffinity(0)))),'--memory=8g','--memory-swap=10g',
        '-v','/dev:/dev','-v','/var/lib/containers:/var/lib/containers',
        '-v',str(args.disk.parent)+':/output','-e','RUST_LOG=bootc=debug,ostree_ext=debug',
        '--entrypoint=/usr/bin/bootc',args.image,'install','to-disk',
        '--generic-image','--via-loopback','--filesystem','btrfs',
        '--target-transport','containers-storage','/output/'+args.disk.name]
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
                                subprocess.run(['/usr/bin/podman','exec',container,
                                    '/bin/sh','-c',SNAPSHOT], stdout=snapshot,
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
            try: stop(process, container)
            finally: detach_image(args.disk)
    with args.disk.open('rb') as disk: os.fsync(disk.fileno())
    print(f'Installed test disk in {time.monotonic()-started:.0f}s (not a boot timing)', flush=True)


if __name__ == '__main__':
    main()
