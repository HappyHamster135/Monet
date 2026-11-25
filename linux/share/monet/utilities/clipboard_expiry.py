"""Configure automatic expiry of the regular Wayland clipboard."""
from dataclasses import asdict, dataclass
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import NamedTemporaryFile

UNIT = "monet-clipboard-expiry.service"
DELAYS = (0, 15, 30, 60, 300, 900, 3600)


@dataclass(frozen=True)
class Policy:
    seconds: int = 0
    lock: bool = False
    sleep: bool = False

    def __post_init__(self):
        if (type(self.seconds) is not int or self.seconds not in DELAYS or
                type(self.lock) is not bool or type(self.sleep) is not bool):
            raise ValueError("Invalid clipboard setting.")

    def enabled(self):
        return bool(self.seconds or self.lock or self.sleep)


def config_path():
    return Path(os.getenv("XDG_CONFIG_HOME") or Path.home() / ".config") / "monet" / "clipboard-expiry.json"


def read_policy():
    try:
        return Policy(**json.loads(config_path().read_text()))
    except FileNotFoundError:
        return Policy()


def write_policy(policy):
    path = config_path()
    with NamedTemporaryFile("w", dir=path.parent, delete=False) as tmp:
        try:
            json.dump(asdict(policy), tmp)
            tmp.flush()
            os.replace(tmp.name, path)
        finally:
            Path(tmp.name).unlink(missing_ok=True)


def control(verb):
    return subprocess.run(["systemctl", "--user", verb, UNIT], capture_output=True, text=True, timeout=15)


def unit_enabled():
    result = control("is-enabled")
    state = result.stdout.strip()
    if state in ("enabled", "enabled-runtime"):
        return True
    if state in ("disabled", "masked", "masked-runtime"):
        return False
    raise RuntimeError(result.stderr.strip() or f"Could not read the state of {UNIT}")


def configure_unit(on):
    for verb in (("enable", "reload-or-restart") if on else ("disable", "try-reload-or-restart")):
        result = control(verb)
        if result.returncode:
            raise RuntimeError(result.stderr.strip() or f"Could not {verb} {UNIT}")


def configure(policy):
    path = config_path()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        prev = read_policy()
        active = unit_enabled()
        write_policy(policy)
        try:
            configure_unit(policy.enabled())
        except (OSError, RuntimeError, subprocess.SubprocessError):
            write_policy(prev)
            configure_unit(active)
            raise


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["status"]:
            on = unit_enabled()
            print(json.dumps(asdict(read_policy() if on else Policy())))
        elif sys.argv[1:2] == ["apply"] and len(sys.argv) == 3:
            configure(Policy(**json.loads(sys.argv[2])))
        else:
            sys.exit(2)
    except (OSError, RuntimeError, ValueError, TypeError, subprocess.SubprocessError) as error:
        sys.exit(str(error))
