#!/usr/bin/env python3
"""Test full Windows deployment and first logon on disposable file-backed disks.

Supply independently verified x64 Windows media: a single-image install.wim,
WinPE Media directory, and a single-image, bootable WinPE WIM. No images are
downloaded. Requires tools/test-winpe.py's dependencies, QEMU/KVM, OVMF, swtpm
and virt-fw-vars (python3-virt-firmware).
The first-logon payload records the handoff instead of installing Bridge/Steam.
Secure Boot, physical power loss and the return to Monet are separate acceptance.
"""

import argparse
from contextlib import contextmanager
import hashlib
import importlib.machinery
import importlib.util
import json
import shutil
import socket
import subprocess
import sys
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("winpe_fixture", ROOT / "tools/test-winpe.py")
pe = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pe)
PREPARE_LOADER = importlib.machinery.SourceFileLoader(
    "windows_preparation", str(ROOT / "linux/libexec/monet-prepare-windows"))
PREPARE_SPEC = importlib.util.spec_from_loader(PREPARE_LOADER.name, PREPARE_LOADER)
preparation = importlib.util.module_from_spec(PREPARE_SPEC)
PREPARE_LOADER.exec_module(preparation)
# Exercise the collision that would shadow a local user with the account domain.
TEST_USER = "Monet-Games"
TEST_COMPUTER = preparation.windows_computer_name(TEST_USER)
PARTS = [("efi", 1, 256, pe.EFI), ("windows", 257, 48 * 1024, pe.DATA),
         ("setup", 49409, 12 * 1024, pe.DATA)]


def make_disk(work):
    disk = work / "target.raw"
    pe.sparse(disk, 64 * 1024 * pe.MIB)
    manifest = {"version": 1, "disk_guid": str(uuid.uuid4())}
    table = ["label: gpt", f"label-id: {manifest['disk_guid']}", "unit: sectors", ""]
    for name, start, size, kind in PARTS:
        part = work / f"{name}.img"
        pe.sparse(part, size * pe.MIB)
        # A standalone file has no partition geometry for mkntfs to discover.
        # Windows' loader needs the same start sector as the containing GPT.
        command = (["mkfs.ntfs", "-F", "-Q", "-p", str(start * 2048), "-H", "255",
                    "-S", "63", "-L", "MONET_VM_TARGET", part]
                   if name == "windows" else
                   ["mkfs.vfat", "-F", "32", "-n", "MTEST" + name.upper(), part])
        pe.run(command, capture_output=True)
        serial = pe.run(["blkid", "-p", "-s", "UUID", "-o", "value", part],
                        capture_output=True, text=True).stdout.strip()
        guid = str(uuid.uuid4())
        manifest[name] = {"guid": guid, "offset": start * pe.MIB, "length": size * pe.MIB,
                          "filesystem": "ntfs" if name == "windows" else "vfat",
                          "filesystem_id": serial}
        table.append(f"start={start * 2048},size={size * 2048},type={kind},uuid={guid}")
    pe.run(["sfdisk", disk], input="\n".join(table) + "\n", text=True, capture_output=True)
    for name, start, *_ in PARTS:
        pe.copy_sparse(work / f"{name}.img", disk, start * pe.MIB)
    return disk, manifest


def make_payload(work, manifest, injected, install_wim):
    staged = work / "staged"
    (staged / "sources").mkdir(parents=True)
    (staged / "monet/bridge").mkdir(parents=True)
    with (work / "wim-build.log").open("w") as log:
        pe.run(["wimlib-imagex", "split", install_wim, staged / "sources/install.swm", "3800"],
               stdout=log, stderr=subprocess.STDOUT)
    answer = (ROOT / "linux/share/monet/winpe/unattend.xml").read_text()
    values = {"USER": preparation.windows_name(TEST_USER), "FULLNAME": "Monet VM acceptance", "COMPUTER": TEST_COMPUTER,
              "TIMEZONE": "UTC", "UILANG": "en-US", "LOCALE": "en-US", "INPUT": "0409:00000409"}
    (staged / "monet/unattend.xml").write_text(preparation.fill(answer, values))
    (staged / "monet/bridge/monet-bridge.exe").write_text("First-logon fixture; never executed.\n")
    (staged / "monet/bridge/Install-Monet.ps1").write_text(r'''param([switch]$FromMonet,[switch]$GameProfile,[switch]$RemoveApps,[switch]$InstallSteam)
$ErrorActionPreference = 'Stop'
try {
    $checkpoint = Get-Content -Raw 'C:\.monet-setup.json' | ConvertFrom-Json
    $os = Get-CimInstance Win32_OperatingSystem
    $principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
    $result = [ordered]@{version=1;username=$env:USERNAME;computer=$env:COMPUTERNAME;build=$os.BuildNumber;caption=$os.Caption;job=$checkpoint.job_id;phase=$checkpoint.phase;isAdministrator=$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator);fromMonet=[bool]$FromMonet;gameProfile=[bool]$GameProfile;removeApps=[bool]$RemoveApps;installSteam=[bool]$InstallSteam}
    $result | ConvertTo-Json | Set-Content -Encoding UTF8 'C:\monet-vm-first-logon.json'
} catch {
    $_ | Out-String | Set-Content -Encoding UTF8 'C:\monet-vm-first-logon-error.txt'
}
shutdown.exe /s /t 5 /f
''')
    files = []
    for path in sorted(staged.rglob("*")):
        if path.is_file():
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            files.append({"path": path.relative_to(staged).as_posix(),
                          "size": path.stat().st_size, "sha256": digest})
    job = {"version": 1, "id": str(uuid.uuid4()), "partitions": manifest, "files": files}
    (injected / "deployment.json").write_text(json.dumps(job))
    return staged, job


def make_script(injected):
    script = r'''@echo off
wpeinit > X:\startup.log 2>&1
set LOG=X:\monet-results.log
for %%d in (C D E F G H I J K L M N O P Q R S T U V W Y Z) do if exist %%d:\monet-vm-setup.marker set LOG=%%d:\monet-results.log
call :run > %LOG% 2>&1
wpeutil shutdown
exit /b
:run
echo MONET_FULL_VM_BEGIN
for %%d in (C D E F G H I J K L M N O P Q R S T U V W Y Z) do if exist %%d:\monet-vm-setup.marker call :identity %%d
X:\monet\check.exe --deploy X:\monet\deployment.json
echo DEPLOY_FIRST_EXIT=%errorlevel%
type C:\.monet-setup.json
echo.
echo USER_SENTINEL > C:\keep-after-complete.txt
X:\monet\check.exe --deploy X:\monet\deployment.json
echo DEPLOY_RETRY_EXIT=%errorlevel%
type C:\.monet-setup.json
echo.
type Z:\EFI\Boot\bootx64.efi
dir Z:\EFI\Microsoft\Boot\bootmgfw.efi
echo MONET_FULL_VM_END
exit /b
:identity
X:\monet\check.exe X:\monet\manifest.json %1
echo IDENTITY_EXIT=%errorlevel%
exit /b
'''
    (injected / "tests.cmd").write_bytes(script.replace("\n", "\r\n").encode("ascii"))


def verify_deployment(work, manifest, job):
    disk = work / "target.raw"
    output = pe.mread(disk, "monet-results.log", manifest["setup"]["offset"])
    (work / "results.log").write_bytes(output)
    text = output.decode("utf-8", errors="replace").replace("\r", "")
    for expected in ("MONET_FULL_VM_BEGIN", "MONET_FULL_VM_END", "IDENTITY_EXIT=0",
                     "DEPLOY_FIRST_EXIT=0", "DEPLOY_RETRY_EXIT=0"):
        if expected not in text:
            raise RuntimeError(f"Missing result: {expected}; see results.log")
    if text.count("Applying the verified Windows image...") != 1:
        raise RuntimeError("Expected one image application across two attempts")
    verify_preservation(work, manifest, job, "after-deploy.img")


def verify_preservation(work, manifest, job, name):
    disk = work / "target.raw"
    if pe.mread(disk, "EFI/Boot/bootx64.efi", manifest["efi"]["offset"]) != pe.FALLBACK:
        raise RuntimeError("The original EFI fallback changed")
    ntfs = work / name
    pe.copy_region(disk, ntfs, manifest["windows"]["offset"], manifest["windows"]["length"])
    checkpoint = json.loads(pe.run(["ntfscat", ntfs, "/.monet-setup.json"], capture_output=True).stdout)
    expected_hash = hashlib.sha256((work / "injected/deployment.json").read_bytes()).hexdigest()
    if checkpoint != {"version": 1, "job_id": job["id"], "manifest_sha256": expected_hash,
                      "phase": "complete"}:
        raise RuntimeError(f"Incorrect checkpoint: {checkpoint}")
    sentinel = pe.run(["ntfscat", ntfs, "/keep-after-complete.txt"], capture_output=True).stdout
    if sentinel.strip() != b"USER_SENTINEL":
        raise RuntimeError("The completed retry did not preserve the user file")
    return ntfs


def configure_windows_boot(args, work):
    # Select the explicit Windows loader on the target's original ESP. Copying
    # its BCD onto another USB is not equivalent and can fail device discovery.
    # Only this test's OVMF file changes; host firmware is never accessed.
    with (work / "firmware-boot.log").open("w") as log:
        pe.run([args.firmware_vars, "-i", work / "OVMF_VARS.fd", "-o", work / "OVMF_VARS-windows.fd",
                "--delete", "BootOrder", "--delete", "BootNext", "--append-boot-filepath",
                r"\EFI\Microsoft\Boot\bootmgfw.efi", "--print"], cwd=work,
               stdout=log, stderr=subprocess.STDOUT)


def boot(args, work, installed=False):
    phase = "first-logon" if installed else "deploy"
    variables = "OVMF_VARS-windows.fd" if installed else "OVMF_VARS.fd"
    command = [args.qemu, "-machine", "q35,accel=kvm", "-cpu", "host", "-smp", "4", "-m", "8192",
               "-drive", "if=pflash,format=raw,readonly=on,file=OVMF_CODE.fd",
               "-drive", f"if=pflash,format=raw,file={variables}",
               "-chardev", "socket,id=chrtpm,path=tpm.sock",
               "-tpmdev", "emulator,id=tpm0,chardev=chrtpm", "-device", "tpm-tis,tpmdev=tpm0",
               "-drive", "if=none,id=fixture,format=raw,file=target.raw",
               "-device", "ide-hd,drive=fixture,bus=ide.0", "-display", "none",
               "-serial", f"file:{phase}-serial.log", "-qmp", "unix:qmp.sock,server=on,wait=off",
               "-monitor", "none", "-nic", "none"]
    if not installed:
        command.extend(["-device", "qemu-xhci", "-drive",
                        "if=none,id=pe,format=raw,snapshot=on,file=boot-usb.raw",
                        "-device", "usb-storage,drive=pe,bootindex=1", "-no-reboot"])
    with virtual_tpm(args, work), (work / f"{phase}-qemu.log").open("w") as log:
        try:
            pe.run(command, cwd=work, timeout=args.timeout, stdout=log, stderr=subprocess.STDOUT)
        except subprocess.TimeoutExpired:
            # A container wrapper may exit before its QEMU does. Request the
            # disposable guest's exit through QMP too, retaining timeout evidence.
            stop_guest(work, phase)
            raise


def stop_guest(work, phase):
    try:
        with socket.socket(socket.AF_UNIX) as connection:
            connection.settimeout(2)
            connection.connect(str(work / "qmp.sock"))
            stream = connection.makefile("rwb")
            stream.readline()
            for command in ({"execute": "qmp_capabilities"},
                            {"execute": "screendump", "arguments": {"filename": f"{phase}-timeout.ppm"}},
                            {"execute": "quit"}):
                stream.write((json.dumps(command) + "\n").encode())
                stream.flush()
                while line := stream.readline():
                    response = json.loads(line)
                    if "return" in response or "error" in response:
                        break
    except (OSError, ValueError):
        pass  # Directly launched QEMU is already killed by subprocess.run.


@contextmanager
def virtual_tpm(args, work):
    # swtpm exits when QEMU disconnects. Restart it for each boot while preserving
    # the same private TPM state, just as the OVMF variable store is preserved.
    (work / "tpm").mkdir(exist_ok=True)
    with (work / "tpm.log").open("a") as log:
        tpm = subprocess.Popen([args.swtpm, "socket", "--tpm2", "--tpmstate", "dir=tpm",
                                "--ctrl", "type=unixio,path=tpm.sock", "--flags", "not-need-init"],
                               cwd=work, stdout=log, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 10
            while not (work / "tpm.sock").exists():
                if tpm.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Virtual TPM did not start; see tpm.log")
                time.sleep(0.1)
            yield
        finally:
            tpm.terminate()
            try:
                tpm.wait(timeout=5)
            except subprocess.TimeoutExpired:
                tpm.kill()
                tpm.wait()


def verify_first_logon(work, manifest, job):
    ntfs = verify_preservation(work, manifest, job, "after-logon.img")
    result = json.loads(pe.run(["ntfscat", ntfs, "/monet-vm-first-logon.json"],
                              capture_output=True).stdout.decode("utf-8-sig"))
    expected = {"version": 1, "username": TEST_USER, "computer": TEST_COMPUTER, "job": job["id"],
                "phase": "complete", "isAdministrator": True, "fromMonet": True, "gameProfile": True,
                "removeApps": True, "installSteam": True}
    if any(result.get(key) != value for key, value in expected.items()):
        raise RuntimeError(f"Incorrect first-logon handoff: {result}")
    (work / "first-logon.json").write_text(json.dumps(result, indent=2) + "\n")
    print(f"Passed deployment, completed retry, preserved EFI and first logon: {result['caption']} {result['build']}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("media", "wim", "install-wim", "checker", "ovmf-code", "ovmf-vars", "work"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--qemu", default="qemu-system-x86_64")
    parser.add_argument("--swtpm", default="swtpm")
    parser.add_argument("--firmware-vars", default="virt-fw-vars")
    parser.add_argument("--timeout", default=900, type=int, help="seconds per guest boot (30–1800)")
    args = parser.parse_args()
    for name in ("media", "wim", "install_wim", "checker", "ovmf_code", "ovmf_vars"):
        path = getattr(args, name).resolve(strict=True)
        if not (path.is_dir() if name == "media" else path.is_file()):
            parser.error(f"Invalid fixture input: {path}")
        setattr(args, name, path)
    if not (args.media / "EFI/Boot/bootx64.efi").is_file():
        parser.error("--media must contain EFI/Boot/bootx64.efi")
    if not 30 <= args.timeout <= 1800:
        parser.error("--timeout must be 30–1800 seconds")
    for name in ("qemu", "swtpm", "firmware_vars"):
        executable = shutil.which(getattr(args, name)) or parser.error(f"Missing {name}")
        setattr(args, name, str(Path(executable).resolve()))
    for command in ("sfdisk", "mkfs.vfat", "mkfs.ntfs", "blkid", "mcopy", "mmd", "mtype",
                    "ntfscat", "wimlib-imagex"):
        if not shutil.which(command):
            parser.error(f"Missing fixture tool: {command}")
    info = pe.run(["wimlib-imagex", "info", args.install_wim, "--xml"], capture_output=True).stdout
    images = ET.fromstring(info).findall("IMAGE")
    if len(images) != 1 or images[0].findtext("WINDOWS/ARCH") != "9":
        parser.error("--install-wim must have exactly one x64 Windows image; export the desired edition first")
    work = args.work.resolve()
    try:
        work.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error("--work must be new; existing evidence is never overwritten")
    args.test_exe = []
    _, manifest, job = pe.prepare(args, work, disk_factory=make_disk, script_factory=make_script,
                                 payload_factory=lambda w, m, i: make_payload(w, m, i, args.install_wim))
    (work / "manifest.json").write_text(json.dumps(manifest, indent=2))
    (work / "job.json").write_text(json.dumps(job, indent=2))
    print("Applying full Windows image in the disposable VM...", flush=True)
    boot(args, work)
    verify_deployment(work, manifest, job)
    configure_windows_boot(args, work)
    print("Booting Windows and checking first logon...", flush=True)
    boot(args, work, installed=True)
    verify_first_logon(work, manifest, job)


if __name__ == "__main__":
    main()
