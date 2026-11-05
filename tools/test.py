#!/usr/bin/env python3
"""Run tests in separate processes and a disposable desktop session on Linux."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def stop(process):
    """Also stop service/Qt children which outlive a test or a timed-out module."""
    if sys.platform == "linux":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    elif process.poll() is None:
        process.kill()
    process.wait()


@contextmanager
def private_session():
    if sys.platform != "linux":
        yield dict(os.environ)
        return
    if not shutil.which("dbus-daemon"):
        raise RuntimeError("dbus-daemon is required to isolate tests from the desktop session")
    import select
    with tempfile.TemporaryDirectory(prefix="monet-tests-") as folder:
        root = Path(folder)
        paths = {key: str(root / leaf) for key, leaf in (
            ("HOME", "home"), ("XDG_CONFIG_HOME", "config"), ("XDG_DATA_HOME", "data"),
            ("XDG_STATE_HOME", "state"), ("XDG_CACHE_HOME", "cache"), ("XDG_RUNTIME_DIR", "runtime"))}
        for path in [*paths.values(), str(root / "artifacts")]:
            Path(path).mkdir(mode=0o700)
        env = dict(os.environ, **paths, QT_QPA_PLATFORM="offscreen", QT_QUICK_BACKEND="software",
                   QT_QUICK_CONTROLS_STYLE="Basic", QT_QPA_PLATFORMTHEME="generic",
                   DBUS_SYSTEM_BUS_ADDRESS="unix:path=/nonexistent",
                   PULSE_SERVER="unix:" + paths["XDG_RUNTIME_DIR"] + "/pulse/native",
                   PIPEWIRE_RUNTIME_DIR=paths["XDG_RUNTIME_DIR"],
                   MONET_PHONE_WINDOW_ROOT=folder)
        # These suites otherwise omit native classes entirely, rather than
        # reporting a skip. Enable them whenever this Python has Qt installed.
        import importlib.util
        if importlib.util.find_spec("PySide6"):
            env["MONET_PASSWORDS_QT_TESTS"] = "1"
        else:
            env.pop("MONET_PASSWORDS_QT_TESTS", None)
        if env.get("MONET_PASSWORDS_QT_TESTS") == "1" and importlib.util.find_spec("dbus"):
            env["MONET_PASSWORDS_PRIVATE_BUS"] = "1"
        else:
            env.pop("MONET_PASSWORDS_PRIVATE_BUS", None)
        for key in ("DISPLAY", "WAYLAND_DISPLAY", "SESSION_MANAGER", "DBUS_SESSION_BUS_ADDRESS",
                    "MONET_NOTIFICATION_TEST_BUS", "MONET_NATIVE_SYSTEMD_TESTS"):
            env.pop(key, None)
        # No system service directories: Qt must not activate a desktop wallet
        # or a portal which mounts FUSE in this disposable runtime directory.
        config = root / "bus.conf"
        config.write_text('<busconfig><type>session</type><auth>EXTERNAL</auth>'
                          '<listen>unix:path=' + paths["XDG_RUNTIME_DIR"] + '/bus</listen>'
                          '<policy context="default"><allow send_destination="*"/>'
                          '<allow receive_sender="*"/><allow own="*"/></policy></busconfig>')
        bus = subprocess.Popen(["dbus-daemon", "--config-file=" + str(config), "--nofork", "--print-address=1"],
                               env=env, stdout=subprocess.PIPE, text=True, start_new_session=True)
        try:
            if not select.select([bus.stdout], [], [], 10)[0]:
                raise RuntimeError("Private test bus did not start within ten seconds")
            address = bus.stdout.readline().strip()
            if not address.startswith("unix:path=" + paths["XDG_RUNTIME_DIR"] + "/bus"):
                raise RuntimeError("Private test bus did not return its expected address")
            env["DBUS_SESSION_BUS_ADDRESS"] = address
            yield env
        finally:
            stop(bus)
            bus.stdout.close()


def worker(module, report):
    sys.path.insert(0, str(ROOT))
    suite = unittest.defaultTestLoader.loadTestsFromName(module)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    Path(report).write_text(json.dumps({"module": module, "tests": result.testsRun,
        "failures": len(result.failures), "errors": len(result.errors),
        "skipped": [{"test": case.id(), "reason": reason} for case, reason in result.skipped]}))
    return 0 if result.wasSuccessful() else 1


def expected_skip(item):
    name, reason = item["test"], item["reason"]
    # The parent fixture runs these on another private bus and checks its exit code.
    if name.startswith("tests.test_notification_policy.NativePolicy."):
        return reason == "only run on the isolated test bus"
    # These need a real user manager or nested mount privileges, neither of
    # which is provided to the desktop container. The mount check has its own
    # required CI step; transient-service integration remains a VM check.
    if name.startswith("tests.test_update_schedule.NativeRetry."):
        return reason == "opt-in transient user-service fixture"
    if name.startswith(("tests.test_app_documents.FlatpakAccessibility.", "tests.test_app_documents.FlatpakElectronAccessibility.",
                        "tests.test_electron_integration.FlatpakElectronIntegration.")):
        return reason == "explicit isolated Flatpak runtime"
    if name.startswith("tests.test_seal.BootMount.test_actual_read_only_boot_"):
        return reason == "Private user/mount namespaces are unavailable"
    # Windows CI owns PowerShell; a container need not expose physical disks.
    return ((name.startswith(("tests.test_windows_setup_scripts.", "tests.test_installer."))
             and reason in ("PowerShell runtime not installed", "PowerShell not installed"))
            or (name.startswith("tests.test_windows_partitions.")
                and reason == "no native partition devices exposed"))


def run(command, env, timeout):
    process = subprocess.Popen(command, cwd=ROOT, env=env, start_new_session=sys.platform == "linux")
    try:
        return process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        print(f"Timed out after {timeout}s: {' '.join(command)}", file=sys.stderr)
        return 124
    finally:
        stop(process)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("modules", nargs="*", help="unittest module/class/test names (default: all)")
    parser.add_argument("--require-desktop", action="store_true", help="fail on missing desktop dependencies or unexpected skips")
    parser.add_argument("--timeout", type=float, default=600, help="seconds allowed per module (default: 600)")
    parser.add_argument("--summary", type=Path, help="write machine-readable results, including skips")
    parser.add_argument("--worker", nargs=2, metavar=("MODULE", "REPORT"), help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        return worker(*args.worker)
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    modules = args.modules or [f"tests.{p.stem}" for p in sorted((ROOT / "tests").glob("test_*.py"))]
    failed, reports = [], []
    with tempfile.TemporaryDirectory(prefix="monet-results-") as temp, private_session() as env:
        if args.require_desktop:
            if run([sys.executable, str(ROOT / "tools/test-runtime.py")], env, 60):
                return 1
        for index, module in enumerate(modules):
            report = Path(temp) / f"{index}.json"
            code = run([sys.executable, str(Path(__file__).resolve()), "--worker", module, str(report)], env, args.timeout)
            if not report.exists():
                result = {"module": module, "tests": 0, "failures": 0, "errors": 1, "skipped": []}
                code = code or 1
            else:
                result = json.loads(report.read_text())
            result["exit_code"] = code
            reports.append(result)
            unexpected = [item for item in result["skipped"] if not expected_skip(item)] if args.require_desktop else []
            if code or unexpected:
                failed.append(module)
                for item in unexpected:
                    print(f"Required check skipped: {item['test']}: {item['reason']}", file=sys.stderr)
        if not args.modules:
            # Form tests need the reproducibly rebuilt upstream connector below.
            scripts = sorted(p for p in (ROOT / "tests").glob("test_*.cjs") if p.name != "test_browser_forms.cjs")
            if scripts and shutil.which("node"):
                if run(["node", "--test", *map(str, scripts)], env, args.timeout):
                    failed.append("JavaScript")
            elif scripts:
                print("JavaScript checks skipped: node is not installed", file=sys.stderr)
                if args.require_desktop:
                    failed.append("JavaScript")
            upstream = os.environ.get("MONET_TEST_BROWSER_UPSTREAM")
            if upstream:
                if run([sys.executable, str(ROOT / "tools/test-browser.py"), str(Path(upstream).resolve())], env, args.timeout):
                    failed.append("Browser forms")
            else:
                print("Browser form checks require MONET_TEST_BROWSER_UPSTREAM (the pinned official XPI).", file=sys.stderr)
                if args.require_desktop:
                    failed.append("Browser forms")
    summary = {"modules": reports, "failed": failed,
               "tests": sum(r["tests"] for r in reports), "skipped": sum(len(r["skipped"]) for r in reports)}
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Python: {summary['tests']} checks, {summary['skipped']} skipped; {len(failed)} failed modules", flush=True)
    if failed:
        print("Failed test modules: " + ", ".join(failed), file=sys.stderr)
    return int(bool(failed))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError) as error:
        sys.exit(str(error))
