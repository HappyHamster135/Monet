#!/usr/bin/env python3
"""Cold-boot a disposable overlay of an installed Monet disk to its visible login form.

No physical disks or host settings are changed. This measures a complete QEMU
power-on, including UEFI/GRUB, rather than treating a systemd target as a screen.
The VM-only provisioning credential adds a synthetic user and a temporary SSH key.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import socket
import statistics
import subprocess
import tempfile
import time



def login_controls(image):
    """Find a wide orange input outline/button in Monet's right-hand login panel.

    Excludes the clock's small orange dot, round avatars, black power screens,
    and text glyphs. Daemon activation is independently required by the caller.
    """
    image = image.convert('RGB').resize((320, 200))
    pixels = image.load()
    points = {(x, y) for y in range(40, 190) for x in range(145, 315)
              if (lambda r, g, b: r > 95 and r > g * 1.65 and g > b * 1.1 and g < 150)(*pixels[x, y])}
    while points:
        start = points.pop(); todo = [start]; component = [start]
        while todo:
            x, y = todo.pop()
            for neighbour in ((x-1,y), (x+1,y), (x,y-1), (x,y+1)):
                if neighbour in points:
                    points.remove(neighbour); todo.append(neighbour); component.append(neighbour)
        xs, ys = zip(*component)
        width, height = max(xs)-min(xs)+1, max(ys)-min(ys)+1
        if len(component) >= 60 and width >= 25 and height >= 5 and width / height >= 2.2:
            return True
    return False


def password_bullet(image):
    """Read the first masked character in the bench's fixed 1280x800 login field."""
    if image.size != (1280, 800):
        return False
    patch = image.crop((816, 450, 829, 463)).convert('RGB')
    # A cursor alone is a narrow vertical line. Require a filled, roughly
    # round character with dark corners as in the real native greeter fixture.
    bright = {(x, y) for y in range(13) for x in range(13)
              if min(patch.getpixel((x, y))) > 180}
    return (50 <= len(bright) <= 125 and (6, 6) in bright
            and all(corner not in bright for corner in ((0, 0), (0, 12), (12, 0), (12, 12))))


def login_clock(image):
    """Recognize the brand dot and large clock in the spacious greeter layout."""
    pixels = image.convert('RGB').resize((320, 200)).load()
    orange = sum(1 for y in range(55, 95) for x in range(60, 100)
                 if (lambda r,g,b: r>140 and r>g*1.7 and g>b*1.1)(*pixels[x,y]))
    white = sum(1 for y in range(75, 125) for x in range(25, 140)
                if min(pixels[x,y])>165 and max(pixels[x,y])-min(pixels[x,y])<65)
    return 1 <= orange <= 16 and white >= 90


def timing_phases(values):
    """systemd's firmware timestamp includes the loader; do not count it twice."""
    firmware = int(values.get('FirmwareTimestampMonotonic', 0))
    loader = int(values.get('LoaderTimestampMonotonic', 0))
    initrd = int(values.get('InitRDTimestampMonotonic', 0))
    userspace = int(values.get('UserspaceTimestampMonotonic', 0))
    return dict(firmware_ms=max(0, firmware-loader)/1000 if firmware and loader else None,
                loader_ms=loader/1000 if loader else None,
                kernel_ms=initrd/1000 if initrd else userspace/1000,
                initrd_ms=max(0, userspace-initrd)/1000 if initrd else 0,
                userspace_start_ms=userspace/1000)


def properties(text):
    return dict(line.split('=', 1) for line in text.splitlines() if '=' in line)


def qmp(path, command, **arguments):
    with socket.socket(socket.AF_UNIX) as sock:
        sock.settimeout(8); sock.connect(str(path))
        with sock.makefile('rwb') as stream:
            json.loads(stream.readline())
            for request in ({'execute':'qmp_capabilities'}, {'execute':command, 'arguments':arguments}):
                stream.write(json.dumps(request).encode()+b'\n'); stream.flush()
                while True:
                    reply = json.loads(stream.readline())
                    if 'event' not in reply: break
                if 'error' in reply: raise RuntimeError(str(reply['error']))
            return reply.get('return')


def credentials(public_key, *, provision=True):
    if not re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/=]+ monet-boot-benchmark', public_key):
        raise ValueError('Unexpected benchmark public key')
    setup = ('install -d -m 0755 /etc/ssh /etc/sudoers.d; ssh-keygen -A; '
             # ExecStart expands systemd's %s specifier even inside shell quotes.
             # The validated key contains no echo options or backslash escapes.
             f'echo "{public_key}" > /etc/ssh/monet-bench-authorized_keys; '
             'chmod 0644 /etc/ssh/monet-bench-authorized_keys; '
             'if ! id monet-bench >/dev/null 2>&1; then useradd -m monet-bench; '
             'echo monet-bench:MonetBenchmarkOnly42 | chpasswd; fi; '
             'echo "monet-bench ALL=(root) NOPASSWD: ALL" > /etc/sudoers.d/90-monet-bench; '
             'chmod 0440 /etc/sudoers.d/90-monet-bench; '
             'restorecon -RF /etc/ssh /etc/sudoers.d/90-monet-bench')
    unit = ('[Unit]\nDefaultDependencies=no\nConditionPathExists=!/etc/initrd-release\n'
            'After=local-fs.target systemd-tmpfiles-setup.service systemd-sysusers.service\n'
            'Before=systemd-user-sessions.service plasmalogin.service monet-boot-bench-sshd.service\n'
            '[Service]\nType=oneshot\nRemainAfterExit=yes\nExecStart=/bin/sh -ec \''+setup+'\'\n')
    setup_units = {'systemd.extra-unit.monet-boot-bench-setup.service':unit,
            'systemd.unit-dropin.sysinit.target':'[Unit]\nWants=monet-boot-bench-setup.service monet-boot-bench-journal.service\n',
            'systemd.extra-unit.monet-boot-bench-journal.service':
                '[Unit]\nDefaultDependencies=no\nConditionPathExists=!/etc/initrd-release\n'
                'After=local-fs.target systemd-journal-flush.service\n[Service]\n'
                "ExecStart=/bin/sh -c 'exec journalctl -b -f -n all -o short-monotonic >/dev/ttyS0'\n",
    }
    return {**(setup_units if provision else {}),
            'systemd.extra-unit.monet-boot-bench-sshd.service':
                '[Unit]\nAfter=network.target firewalld.service monet-boot-bench-setup.service\n'
                '[Service]\nType=exec\nRuntimeDirectory=sshd\n'
                'ExecStartPre=-/usr/bin/firewall-cmd --add-service=ssh --timeout=900\n'
                'ExecStart=/usr/sbin/sshd -D -e -f /dev/null -h /etc/ssh/ssh_host_ed25519_key '
                '-oPermitRootLogin=no -oAllowUsers=monet-bench -oUsePAM=no '
                '-oPasswordAuthentication=no -oKbdInteractiveAuthentication=no '
                '-oAuthorizedKeysFile=/etc/ssh/monet-bench-authorized_keys\n',
            'systemd.unit-dropin.sshd.service':'[Unit]\nConditionPathExists=/run/monet-bench-stock-sshd-disabled\n',
            'systemd.unit-dropin.sshd.socket':'[Unit]\nConditionPathExists=/run/monet-bench-stock-sshd-disabled\n',
            'systemd.unit-dropin.multi-user.target':'[Unit]\nWants=monet-boot-bench-sshd.service\n'}


def ssh_command(port, key, command):
    return ['ssh','-i',str(key),'-p',str(port),'-o','IdentitiesOnly=yes',
        '-o','StrictHostKeyChecking=no','-o','UserKnownHostsFile=/dev/null',
        '-o','ConnectTimeout=2','-o','BatchMode=yes','monet-bench@127.0.0.1',
        'sudo -n /bin/sh -c '+shlex.quote(command)]


def ssh(port, key, command, timeout=15):
    return subprocess.run(ssh_command(port,key,command),capture_output=True,text=True,timeout=timeout)


def boot(args, disk, variables, key, index, runtime):
    from PIL import Image
    work = args.output / f'boot-{index:02d}'; work.mkdir()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); port = sock.getsockname()[1]
    monitor = runtime / 'qmp.sock'; monitor.unlink(missing_ok=True)
    frame = runtime / 'frame.ppm'
    command = ['qemu-system-x86_64','-machine','q35,smm=on','-accel','kvm','-cpu','host',
        '-smp',str(args.cpus),'-m',str(args.memory),'-display','none',
        '-drive',f'if=pflash,format=raw,unit=0,readonly=on,file={args.firmware_code}',
        '-drive',f'if=pflash,format=raw,unit=1,file={variables}',
        '-blockdev',json.dumps({'driver':'file','filename':str(disk),'node-name':'disk-file'}),
        '-blockdev',json.dumps({'driver':'qcow2','file':'disk-file','node-name':'disk'}),
        '-device','virtio-blk-pci,drive=disk,bootindex=1',
        '-device','VGA,edid=on,xres=1280,yres=800,vgamem_mb=32',
        '-device','qemu-xhci','-device','usb-tablet','-device','usb-kbd',
        '-nic',f'user,model=virtio-net-pci,hostfwd=tcp:127.0.0.1:{port}-:22',
        '-qmp',f'unix:{monitor},server,nowait','-serial',f'file:{work / "serial.log"}']
    for name, value in credentials(key.with_suffix('.pub').read_text().strip(), provision=index == 0).items():
        payload = base64.b64encode(value.encode()).decode()
        command += ['-smbios', f'type=11,value=io.systemd.credential.binary:{name}={payload}']
    process = None; probe = None; active = False
    started = time.monotonic(); first = None; stable = 0
    clock_frame = None; input_sent = None; input_verified = None
    try:
        with (work/'qemu.log').open('w') as log:
            process = subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
        # Initial hardware setup stages a deployment and reboots the VM. Its
        # whole sequence is excluded from steady-state boot measurements.
        deadline = started + (args.setup_timeout if index == 0 else args.timeout)
        next_ssh = started
        while time.monotonic() < deadline:
            if process.poll() is not None: raise RuntimeError('VM exited before its login screen')
            if shutil.disk_usage(args.output).free < 8 * 1024**3: raise RuntimeError('Keeping 8 GiB disk headroom')
            # SSH readiness must not block first-frame sampling. In particular,
            # a refused connection or slow PAM handshake is not a display delay.
            if probe is not None and (probe.poll() is not None or time.monotonic()-probe_started > 5):
                if probe.poll() is None: probe.kill()
                output,error = probe.communicate()
                with (work/'ssh-readiness.log').open('a') as log:
                    log.write(json.dumps(dict(elapsed_ms=round((time.monotonic()-started)*1000),
                        returncode=probe.returncode,stdout=output[-200:],stderr=error[-600:]))+'\n')
                active = probe.returncode == 0 and output.strip() == 'active'
                probe = None; next_ssh = time.monotonic()+2
            if input_verified is not None and not active and probe is None and time.monotonic() >= next_ssh:
                probe = subprocess.Popen(ssh_command(port,key,'systemctl is-active plasmalogin.service'),
                    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
                probe_started = time.monotonic()
            if monitor.exists():
                qmp(monitor,'screendump',filename=str(frame))
                captured=time.monotonic()-started
                with Image.open(frame) as image:
                    detected = login_controls(image)
                    if clock_frame is None and (detected or login_clock(image)):
                        clock_frame = captured
                        image.save(work/'login-first-frame.png')
                    if clock_frame is not None and input_sent is None:
                        # A single test keystroke reveals the native prompt.
                        # Never submit a password or authenticate a desktop.
                        qmp(monitor,'send-key',keys=[{'type':'qcode','data':'spc'}],)
                        input_sent = time.monotonic()-started
                    if detected and first is None:
                        first = captured
                    if detected and password_bullet(image):
                        stable += 1
                        if stable >= 2 and input_verified is None:
                            input_verified = captured
                            image.save(work/'login.png')
                        if input_verified is not None and active:
                            break
                    else:
                        stable = 0
            time.sleep(.25)
        else:
            if monitor.exists():
                qmp(monitor,'screendump',filename=str(frame))
                with Image.open(frame) as image:image.save(work/'timeout.png')
            raise RuntimeError('No stable visible Monet login controls before timeout')
        if index > 0:
            journal = ssh(port, key, 'journalctl -b --no-pager -o short-monotonic', timeout=30)
            if journal.returncode:
                raise RuntimeError('Could not collect the timed guest journal')
            (work/'guest-journal.log').write_text(journal.stdout)
        props = 'FirmwareTimestampMonotonic LoaderTimestampMonotonic InitRDTimestampMonotonic UserspaceTimestampMonotonic FinishTimestampMonotonic'
        reply = ssh(port,key,'systemctl show '+ ' '.join('-p '+p for p in props.split()))
        if reply.returncode: raise RuntimeError('Cannot collect guest boot timing')
        values = properties(reply.stdout)
        evidence = ssh(port,key,'monet --version; uname -r; bootc status --json; systemd-analyze time; systemd-analyze critical-chain plasmalogin.service; '
            'systemd-analyze blame | head -n 20; printf "\\nBOOT_MENU\\n"; '
            'grep -E "^[[:space:]]*set timeout(_style)?=" /boot/grub2/grub.cfg; '
            'grub2-editenv - list | grep -E "^(boot_success|boot_indeterminate|menu_auto_hide|menu_show_once_timeout|boot_counter)="')
        (work/'guest.txt').write_text(evidence.stdout+'\n'+evidence.stderr)
        trust_reply = ssh(port,key,'systemctl show bootc-update-ca-trust.service '
            '-p ConditionResult -p Result -p ExecMainStartTimestampMonotonic '
            '-p ExecMainExitTimestampMonotonic; stat -c "%n %y" /etc/.updated /usr >&2')
        (work/'trust-refresh.txt').write_text(trust_reply.stdout+'\n'+trust_reply.stderr)
        trust = properties(trust_reply.stdout)
        if args.check_trust_refresh:
            expected = 'yes' if index == 0 else 'no'
            if (trust_reply.returncode or trust.get('ConditionResult') != expected
                    or trust.get('Result') != 'success'
                    or (index == 0 and int(trust.get('ExecMainExitTimestampMonotonic', 0)) <= 0)):
                raise RuntimeError('Trust refresh must run on the first boot and skip normal reboots: '+str(trust))
        migration_reply = ssh(port,key,'systemctl show bazzite-iwd-migration.service '
            '-p ConditionResult -p Result -p ExecMainStartTimestampMonotonic '
            '-p ExecMainExitTimestampMonotonic -p ExecCondition')
        migration = properties(migration_reply.stdout)
        radio = ssh(port,key,'systemctl show NetworkManager.service bluetooth.service monet-input-connect.service '
            '-p Id -p LoadState -p ActiveState -p ConditionResult -p ExecMainStartTimestampMonotonic '
            '-p ActiveEnterTimestampMonotonic; journalctl -b -u bazzite-iwd-migration.service --no-pager -o short-monotonic')
        (work/'radio-startup.txt').write_text(migration_reply.stdout+'\n'+migration_reply.stderr
            +'\n'+radio.stdout+'\n'+radio.stderr)
        if args.check_wifi_migration and index > 0:
            if (migration_reply.returncode or migration.get('Result') not in ('success', 'exec-condition')
                    or migration.get('ExecMainStartTimestampMonotonic') != '0'
                    or not re.search(r'code=exited\s*;\s*status=1\b', migration.get('ExecCondition', ''))):
                raise RuntimeError('Routine Wi-Fi migration should skip its reload on normal boots: '+str(migration))
        if args.check_install_bluetooth and index == 0:
            setup = ssh(port, key, "cat /proc/cmdline; journalctl -b --no-pager -o cat -u bazzite-hardware-setup.service")
            (work/'hardware-setup.txt').write_text(setup.stdout + '\n' + setup.stderr)
            cmdline, _, messages = setup.stdout.partition('\n')
            kernels = (work/'serial.log').read_bytes().count(b'monet kernel: Linux version ')
            if (setup.returncode or cmdline.split().count('bluetooth.disable_ertm=1') != 1
                    or 'No karg changes needed' not in messages or kernels != 1):
                raise RuntimeError('Expected one setup boot with the Bluetooth default present at kernel start')
        sessions = ssh(port,key,"loginctl list-sessions --no-legend | while read -r sid rest; do loginctl show-session \"$sid\" -p Type -p Class; echo; done")
        for session in sessions.stdout.split('\n\n'):
            fields=properties(session)
            if fields.get('Type') in ('wayland','x11') and fields.get('Class')=='user':
                raise RuntimeError('A desktop autologged in; this is not a login-screen sample')
        result = dict(index=index,warmup=index==0,power_on_to_visible_login_ms=round(clock_frame*1000,3),
                      power_on_to_controls_ms=round(first*1000,3),
                      keyboard_verified_ms=round(input_verified*1000,3),
                      sampling_interval_ms=250,guest_properties=values,guest_phases=timing_phases(values),
                      trust_refresh=trust,wifi_migration=migration)
        (work/'timing.json').write_text(json.dumps(result,indent=2)+'\n')
        # Seed the next *normal* boot exactly as the stock successful-login helper
        # would. No trial counters are changed. This is only the disposable VM.
        marked = ssh(port,key,'grub2-set-bootflag boot_success')
        if marked.returncode:
            # Atomic systems can mount /boot read-only. Use Monet's existing
            # private-mount-namespace writer, still solely inside this VM.
            program = ("import importlib.machinery,importlib.util; "
                "l=importlib.machinery.SourceFileLoader('bench_boot_flags','/usr/libexec/monet-boot'); "
                "m=importlib.util.module_from_spec(importlib.util.spec_from_loader(l.name,l)); "
                "l.exec_module(m); m.edit_grub('set','boot_success=1','boot_indeterminate=0')")
            marked = ssh(port,key,'python3 -c '+shlex.quote(program))
        if marked.returncode: raise RuntimeError('Could not seed a successful normal boot: '+marked.stderr[-300:])
        ssh(port,key,'systemctl --no-block poweroff',timeout=10)
        try: process.wait(timeout=60)
        except subprocess.TimeoutExpired: raise RuntimeError('VM did not shut down cleanly; refusing another sample')
        return result
    finally:
        (work/'observations.json').write_text(json.dumps(dict(
            visible_login_ms=round(clock_frame*1000,3) if clock_frame is not None else None,
            visible_controls_ms=round(first*1000,3) if first is not None else None,
            input_sent_ms=round(input_sent*1000,3) if input_sent is not None else None,
            keyboard_verified_ms=round(input_verified*1000,3) if input_verified is not None else None,
            service_verified=active),indent=2)+'\n')
        if probe is not None:
            if probe.poll() is None: probe.kill()
            probe.wait()
        if process and process.poll() is None: process.kill(); process.wait()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('disk',type=Path); parser.add_argument('output',type=Path)
    parser.add_argument('--samples',type=int,default=3); parser.add_argument('--cpus',type=int,default=1)
    parser.add_argument('--memory',type=int,default=8192); parser.add_argument('--timeout',type=int,default=240)
    parser.add_argument('--setup-timeout', type=int, default=600,
        help='Time limit for the excluded setup sequence including any deployment reboot')
    parser.add_argument('--check-trust-refresh',action='store_true',
        help='Require trust regeneration on the initial boot and no regeneration on subsequent boots')
    parser.add_argument('--check-install-bluetooth', action='store_true',
        help='Verify the first installed VM boot starts with the hardware setup default and reaches login in one boot')
    parser.add_argument('--check-wifi-migration',action='store_true',
        help='Require routine Wi-Fi migration to skip its systemd reload on normal boots')
    parser.add_argument('--firmware-code',type=Path,default=Path('/usr/share/OVMF/OVMF_CODE_4M.fd'))
    parser.add_argument('--firmware-vars',type=Path,default=Path('/usr/share/OVMF/OVMF_VARS_4M.fd'))
    args=parser.parse_args()
    if not 1<=args.samples<=10 or not 1<=args.cpus<=4 or not 1<=args.timeout<=600: parser.error('Invalid sample/resource limits')
    if not 1 <= args.setup_timeout <= 1200: parser.error('Invalid initial setup timeout')
    args.disk=args.disk.resolve(); args.output=args.output.resolve()
    if not args.disk.is_file() or args.disk.suffix not in ('.qcow2','.raw'): parser.error('An installed qcow2 or raw file is required')
    for path in (args.firmware_code,args.firmware_vars):
        if not path.is_file(): parser.error('Missing UEFI firmware: '+str(path))
    for path in (args.disk,args.output,args.firmware_code,args.firmware_vars):
        if ',' in str(path) or '\n' in str(path): parser.error('QEMU paths cannot contain commas/newlines')
    if not os.access('/dev/kvm',os.R_OK|os.W_OK):parser.error('KVM is required; do not benchmark TCG emulation')
    args.output.mkdir(parents=True,exist_ok=False)
    info=json.loads(subprocess.check_output(['qemu-img','info','--output=json',str(args.disk)],text=True))
    if info['format'] not in ('qcow2','raw'):parser.error('Not a qcow2 or raw image')
    disk=args.output/'working.qcow2'
    subprocess.run(['qemu-img','create','-q','-f','qcow2','-F',info['format'],'-b',str(args.disk),str(disk)],check=True)
    variables=args.output/'vars.fd';shutil.copy2(args.firmware_vars,variables)
    with tempfile.TemporaryDirectory(prefix='monet-boot-') as tmp:
        runtime=Path(tmp);key=runtime/'key'
        subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-C','monet-boot-benchmark','-f',str(key)],check=True)
        samples=[]
        for index in range(args.samples+1):
            result=boot(args,disk,variables,key,index,runtime);samples.append(result)
            print(json.dumps(result),flush=True)
    times=[r['power_on_to_visible_login_ms'] for r in samples if not r['warmup']]
    report=dict(schema=1,scope='Installed disk cold boots under KVM; not physical laptop timings',
        secure_boot=False,host_page_cache='uncontrolled',cpus=args.cpus,memory_mib=args.memory,first_boot_excluded=True,
        boot_state='Successful normal boot seeded between samples; trial counters untouched',
        median_ms=statistics.median(times),min_ms=min(times),max_ms=max(times),samples=samples)
    (args.output/'summary.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='samples'}),flush=True)


if __name__=='__main__':main()
