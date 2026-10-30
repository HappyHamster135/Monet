"""Run only inside the test's separate user and mount namespaces."""
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
loader = importlib.machinery.SourceFileLoader("seal_mount_fixture", str(ROOT / "linux/libexec/monet-seal"))
spec = importlib.util.spec_from_loader(loader.name, loader)
seal = importlib.util.module_from_spec(spec)
loader.exec_module(seal)

with tempfile.TemporaryDirectory(prefix="monet-private-boot-") as tmp:
    boot = Path(tmp) / "boot"
    boot.mkdir()
    # Like the installed /boot, this test mount has an fstab entry. Explicit
    # namespace-local IDs also avoid replaying host IDs from tmpfs mountinfo.
    fstab = Path(tmp) / "fstab"
    fstab.write_text(f"tmpfs {boot} tmpfs ro,size=1m,uid=0,gid=0 0 0\n")
    os.environ["LIBMOUNT_FSTAB"] = str(fstab)
    subprocess.run(["mount", "-t", "tmpfs", "-o", "size=1m,ro", "tmpfs", str(boot)], check=True)
    try:
        seal.FIRST_KEY = boot / "monet-firstboot.key"
        assert seal.boot_read_only()
        with seal.writable_boot(True):
            assert not seal.boot_read_only()
            seal.FIRST_KEY.write_bytes(b"disposable fixture only")
        assert seal.boot_read_only()
        try:
            with seal.writable_boot(True):
                seal.FIRST_KEY.unlink()
                raise RuntimeError("interrupted cleanup fixture")
        except RuntimeError as error:
            assert str(error) == "interrupted cleanup fixture"
        assert seal.boot_read_only()
        assert not seal.FIRST_KEY.exists()
        seal.FIRST_KEY = Path(tmp) / "not-a-mount/key"
        try:
            seal.boot_read_only()
        except (RuntimeError, ValueError):
            pass
        else:
            raise AssertionError("An arbitrary directory was accepted as a boot mount")
    finally:
        subprocess.run(["umount", str(boot)], check=True)
