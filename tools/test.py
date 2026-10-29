#!/usr/bin/env python3
"""Run every test module; Qt's process-global type registry cannot reset between apps."""
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
failed = []
for path in sorted((root / "tests").glob("test_*.py")):
    result = subprocess.run([sys.executable, "-m", "unittest", "-v", f"tests.{path.stem}"], cwd=root)
    if result.returncode:
        failed.append(path.name)
if failed:
    print("Failed test modules: " + ", ".join(failed), file=sys.stderr)
sys.exit(bool(failed))
