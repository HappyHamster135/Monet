#!/usr/bin/env python3
"""Exercise the setup checker in real WinPE using only newly created image files.

Requires an amd64 ADK WinPE Media directory and winpe.wim, a built checker and
Windows test executables, QEMU/KVM, OVMF, wimlib, mtools, dosfstools, ntfs-3g and
util-linux. The work directory must not exist. No host disk is passed to QEMU.
The tiny applied image is deliberately not bootable: BCDBoot must fail, leaving
an applied checkpoint that retries without reapplying or changing the fallback.
This does not replace full Windows install, Secure Boot or power-loss acceptance.
"""

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import uuid
from pathlib import Path

MIB = 1024 * 1024
EFI = "C12A7328-F81F-11D2-BA4B-00A0C93EC93B"
DATA = "EBD0A0A2-B9E5-4433-87C0-68B6B72699C7"
PARTS = [("efi", 1, 128, EFI), ("windows", 129, 512, DATA), ("setup", 641, 128, DATA)]
FALLBACK = b"Original Monet fallback sentinel; never booted.\n"


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def sparse(path, size):
    with path.open("xb") as stream:
        stream.truncate(size)


def copy_region(source, destination, offset, length):
    with source.open("rb") as src, destination.open("xb") as dst:
        src.seek(offset)
        while length:
            data = src.read(min(length, MIB))
            if not data:
                raise RuntimeError("The disposable disk image was truncated")
            dst.write(data)
            length -= len(data)


def mdrive(path, offset=0):
    return f"{path}@@{offset}" if offset else str(path)


def mcopy(image, source, destination="::/", offset=0):
    run(["mcopy", "-s", "-o", "-i", mdrive(image, offset), source, destination])


def mread(image, path, offset):
    return run(["mtype", "-i", mdrive(image, offset), f"::/{path}"], capture_output=True).stdout


def make_disk(work):
    disk = work / "target.raw"
    sparse(disk, 800 * MIB)
    manifest = {"version": 1, "disk_guid": str(uuid.uuid4())}
    table = ["label: gpt", f"label-id: {manifest['disk_guid']}", "unit: sectors", ""]
    for name, start, size, kind in PARTS:
        part = work / f"{name}.img"
        sparse(part, size * MIB)
        if name == "windows":
            run(["mkfs.ntfs", "-F", "-Q", "-L", "MONET_VM_TARGET", part], capture_output=True)
        else:
            run(["mkfs.vfat", "-F", "32", "-n", f"MTEST{name.upper()}", part], capture_output=True)
        serial = run(["blkid", "-p", "-s", "UUID", "-o", "value", part],
                     capture_output=True, text=True).stdout.strip()
        guid = str(uuid.uuid4())
        manifest[name] = {"guid": guid, "offset": start * MIB, "length": size * MIB,
                          "filesystem": "ntfs" if name == "windows" else "vfat",
                          "filesystem_id": serial}
        table.append(f'start={start * 2048},size={size * 2048},type={kind},uuid={guid}')
    run(["sfdisk", disk], input="\n".join(table) + "\n", text=True, capture_output=True)
    with disk.open("r+b") as dst:
        for name, start, *_ in PARTS:
            dst.seek(start * MIB)
            with (work / f"{name}.img").open("rb") as src:
                shutil.copyfileobj(src, dst, MIB)
    return disk, manifest


def make_payload(work, manifest, injected):
    root = work / "tiny-windows"
    (root / "Windows/System32").mkdir(parents=True)
    (root / "Windows/System32/winload.efi").write_text("Non-bootable DISM retry fixture.\n")
    staged = work / "staged"
    (staged / "sources").mkdir(parents=True)
    (staged / "monet/bridge").mkdir(parents=True)
    with (work / "wim-build.log").open("w") as log:
        run(["wimlib-imagex", "capture", root, work / "tiny.wim", "Monet VM test"],
            stdout=log, stderr=subprocess.STDOUT)
        run(["wimlib-imagex", "split", work / "tiny.wim", staged / "sources/install.swm", "100"],
            stdout=log, stderr=subprocess.STDOUT)
    (staged / "monet/unattend.xml").write_text('<unattend xmlns="urn:schemas-microsoft-com:unattend"/>\n')
    (staged / "monet/bridge/monet-bridge.exe").write_text("Copied fixture; never executed.\n")
    (staged / "monet/bridge/Install-Monet.ps1").write_text("# Copied fixture; never executed.\n")
    files = [{"path": f.relative_to(staged).as_posix(), "size": f.stat().st_size,
              "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}
             for f in sorted(staged.rglob("*")) if f.is_file()]
    job = {"version": 1, "id": str(uuid.uuid4()), "partitions": manifest, "files": files}
    (injected / "deployment.json").write_text(json.dumps(job))
    return staged, job


def make_script(injected):
    # Commands use fixed names and letters verified by the checker. The isolated
    # single SATA fixture gets C (target), D (setup) and Z (explicit EFI mount).
    script = r"""@echo off
wpeinit > X:\startup.log 2>&1
set LOG=X:\monet-results.log
for %%d in (C D E F G H I J K L M N O P Q R S T U V W Y Z) do if exist %%d:\monet-vm-setup.marker set LOG=%%d:\monet-results.log
call :run > %LOG% 2>&1
wpeutil shutdown
exit /b
:run
echo MONET_VM_BEGIN
for %%f in (X:\monet\test-*.exe) do call :test "%%f"
for %%d in (C D E F G H I J K L M N O P Q R S T U V W Y Z) do if exist %%d:\monet-vm-setup.marker call :identity %%d
X:\monet\check.exe --deploy X:\monet\deployment.json
echo DEPLOY_FIRST_EXIT=%errorlevel%
type C:\.monet-setup.json
echo.
echo PRESERVE_LOADER > C:\Windows\System32\winload.efi
echo USER_SENTINEL > C:\keep-after-failure.txt
X:\monet\check.exe --deploy X:\monet\deployment.json
echo DEPLOY_RETRY_EXIT=%errorlevel%
type C:\.monet-setup.json
echo.
type Z:\EFI\Boot\bootx64.efi
echo MONET_VM_END
exit /b
:test
echo RUN_TEST=%~1
%1 --nocapture
echo TEST_EXIT=%errorlevel%
exit /b
:identity
echo SETUP_LETTER=%1
X:\monet\check.exe X:\monet\manifest.json %1
echo IDENTITY_EXIT=%errorlevel%
X:\monet\check.exe X:\monet\changed.json %1
echo CHANGED_IDENTITY_EXIT=%errorlevel%
exit /b
"""
    (injected / "tests.cmd").write_bytes(script.replace("\n", "\r\n").encode("ascii"))


def prepare(args, work):
    injected = work / "injected"
    injected.mkdir()
    disk, manifest = make_disk(work)
    (injected / "manifest.json").write_text(json.dumps(manifest))
    changed = json.loads(json.dumps(manifest))
    changed["windows"]["filesystem_id"] = "FFFFFFFFFFFFFFFF"
    (injected / "changed.json").write_text(json.dumps(changed))
    shutil.copy2(args.checker, injected / "check.exe")
    for index, test in enumerate(args.test_exe):
        shutil.copy2(test, injected / f"test-{index}.exe")
    make_script(injected)
    staged, job = make_payload(work, manifest, injected)
    for item in staged.iterdir():
        mcopy(disk, item, offset=manifest["setup"]["offset"])
    marker = work / "monet-vm-setup.marker"
    marker.write_text("Disposable WinPE fixture\n")
    mcopy(disk, marker, offset=manifest["setup"]["offset"])
    for directory in ("::/EFI", "::/EFI/Boot"):
        run(["mmd", "-i", mdrive(disk, manifest["efi"]["offset"]), directory])
    fallback = work / "original-fallback.efi"
    fallback.write_bytes(FALLBACK)
    mcopy(disk, fallback, "::/EFI/Boot/bootx64.efi", manifest["efi"]["offset"])

    media = work / "media"
    shutil.copytree(args.media, media)
    (media / "sources").mkdir(exist_ok=True)
    shutil.copy2(args.wim, media / "sources/boot.wim")
    (work / "winpeshl.ini").write_bytes(
        b'[LaunchApps]\r\n%SYSTEMROOT%\\System32\\cmd.exe, "/c X:\\monet\\tests.cmd"\r\n')
    with (work / "wim-inject.log").open("w") as log:
        run(["wimlib-imagex", "update", "media/sources/boot.wim", "1"], cwd=work,
            input="add injected /monet\nadd winpeshl.ini /Windows/System32/winpeshl.ini\n",
            text=True, stdout=log, stderr=subprocess.STDOUT)
    fat = work / "boot.img"
    sparse(fat, 1024 * MIB)
    run(["mkfs.vfat", "-F", "32", "-n", "MONET_VM_PE", fat], capture_output=True)
    for item in media.iterdir():
        mcopy(fat, item)
    usb = work / "boot-usb.raw"
    sparse(usb, 1026 * MIB)
    run(["sfdisk", usb], input=f"label: gpt\nstart=2048,size=2097152,type={EFI}\n",
        text=True, capture_output=True)
    with usb.open("r+b") as dst, fat.open("rb") as src:
        dst.seek(MIB)
        shutil.copyfileobj(src, dst, MIB)
    shutil.copy2(args.ovmf_code, work / "OVMF_CODE.fd")
    shutil.copy2(args.ovmf_vars, work / "OVMF_VARS.fd")
    return disk, manifest, job


def boot(args, work):
    command = [args.qemu, "-machine", "q35,accel=kvm", "-cpu", "host", "-smp", "2", "-m", "4096",
               "-drive", "if=pflash,format=raw,readonly=on,file=OVMF_CODE.fd",
               "-drive", "if=pflash,format=raw,file=OVMF_VARS.fd", "-device", "qemu-xhci",
               "-drive", "if=none,id=pe,format=raw,snapshot=on,file=boot-usb.raw",
               "-device", "usb-storage,drive=pe,bootindex=1",
               "-drive", "if=none,id=fixture,format=raw,file=target.raw",
               "-device", "ide-hd,drive=fixture,bus=ide.0", "-display", "none",
               "-serial", "file:serial.log", "-monitor", "none", "-nic", "none", "-no-reboot"]
    with (work / "qemu.log").open("w") as log:
        run(command, cwd=work, timeout=args.timeout, stdout=log, stderr=subprocess.STDOUT)


def verify(args, work, disk, manifest, job):
    output = mread(disk, "monet-results.log", manifest["setup"]["offset"])
    (work / "results.log").write_bytes(output)
    text = output.decode("utf-8", errors="replace").replace("\r", "")
    for expected in ("MONET_VM_BEGIN", "MONET_VM_END", '"windows":"C"', '"setup":"D"',
                     "IDENTITY_EXIT=0", "CHANGED_IDENTITY_EXIT=1", "DEPLOY_FIRST_EXIT=1",
                     "DEPLOY_RETRY_EXIT=1", "bcdboot.exe stopped", FALLBACK.decode().strip()):
        if expected not in text:
            raise RuntimeError(f"Missing acceptance result: {expected}; see results.log")
    exits = re.findall(r"^TEST_EXIT=(\d+)$", text, re.M)
    if exits != ["0"] * len(args.test_exe):
        raise RuntimeError(f"Windows test executable results: {exits}")
    if text.count("Applying the verified Windows image...") != 1:
        raise RuntimeError("Expected exactly one DISM application across two attempts")
    if mread(disk, "EFI/Boot/bootx64.efi", manifest["efi"]["offset"]) != FALLBACK:
        raise RuntimeError("The original fallback loader changed")
    ntfs = work / "target-after.img"
    copy_region(disk, ntfs, manifest["windows"]["offset"], manifest["windows"]["length"])

    def read(path):
        return run(["ntfscat", ntfs, path], capture_output=True).stdout

    checkpoint = json.loads(read("/.monet-setup.json"))
    expected_hash = hashlib.sha256((work / "injected/deployment.json").read_bytes()).hexdigest()
    if checkpoint != {"version": 1, "job_id": job["id"], "manifest_sha256": expected_hash,
                      "phase": "applied"}:
        raise RuntimeError(f"Wrong retry checkpoint: {checkpoint}")
    if read("/Windows/System32/winload.efi").strip() != b"PRESERVE_LOADER":
        raise RuntimeError("Retry reapplied the image over an existing file")
    if read("/keep-after-failure.txt").strip() != b"USER_SENTINEL":
        raise RuntimeError("Retry did not preserve the user file")
    passed = sum(int(n) for n in re.findall(r"test result: ok\. (\d+) passed;", text))
    print(f"Passed: {passed} Windows tests, native identity rejection, DISM/EFI retry and preservation.")
    print(f"Evidence: {work / 'results.log'}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("media", "wim", "checker", "ovmf-code", "ovmf-vars", "work"):
        parser.add_argument(f"--{name}", required=True, type=Path)
    parser.add_argument("--test-exe", required=True, action="append", type=Path)
    parser.add_argument("--qemu", default="qemu-system-x86_64")
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()
    for name in ("media", "wim", "checker", "ovmf_code", "ovmf_vars"):
        setattr(args, name, getattr(args, name).resolve(strict=True))
    args.test_exe = [p.resolve(strict=True) for p in args.test_exe]
    for path in [args.wim, args.checker, args.ovmf_code, args.ovmf_vars, *args.test_exe]:
        if not path.is_file():
            parser.error(f"Expected a regular input file: {path}")
    if not (args.media / "EFI/Boot/bootx64.efi").is_file():
        parser.error("--media must be the amd64 ADK WinPE Media directory")
    if not 30 <= args.timeout <= 900:
        parser.error("--timeout must be between 30 and 900 seconds")
    args.qemu = shutil.which(args.qemu) or parser.error("QEMU executable not found")
    for command in ("sfdisk", "mkfs.vfat", "mkfs.ntfs", "blkid", "mcopy", "mmd", "mtype",
                    "ntfscat", "wimlib-imagex"):
        if not shutil.which(command):
            parser.error(f"Required fixture tool not found: {command}")
    work = args.work.resolve()
    try:
        work.mkdir(parents=True, exist_ok=False)
    except FileExistsError:
        parser.error("--work must name a new directory; existing evidence is never overwritten")
    disk, manifest, job = prepare(args, work)
    boot(args, work)
    verify(args, work, disk, manifest, job)


if __name__ == "__main__":
    main()
