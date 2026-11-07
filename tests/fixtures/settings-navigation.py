"""Run actual Settings key/wheel tests on a private 1920x1080 X server.

Each scale/font/language uses a new Qt process and isolated account/session.
This validates rendered software layouts and input events, not physical devices.
"""
import argparse
import json
import os
from pathlib import Path
import select
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from tools.test import private_session, stop


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--scales", type=float, nargs="+", default=[1.25, 1.5, 2])
    parser.add_argument("--fonts", type=int, nargs="+", default=[10, 14])
    parser.add_argument("--module", default="tests.test_settings_navigation")
    parser.add_argument("--language", choices=['en', *sorted(p.stem for p in (ROOT/'po').glob('*.po'))],
                        help="Use this catalog and Qt locale instead of the default English/Swedish matrix")
    parser.add_argument("--reduced-motion", action="store_true")
    parser.add_argument("--two-screens", action="store_true")
    args = parser.parse_args(); args.output.mkdir(parents=True, exist_ok=True)
    reports = []
    for scale in args.scales:
        for font in args.fonts:
            language = args.language or ("sv" if font > 10 else "en")
            name = f"scale-{scale}-font-{font}-{language}"
            output = args.output / name; output.mkdir(exist_ok=True)
            with private_session() as env, (output / "xvfb.log").open("w") as xlog:
                if args.reduced_motion:
                    (Path(env["XDG_CONFIG_HOME"]) / "kdeglobals").write_text("[KDE]\nAnimationDurationFactor=0\n")
                    env["MONET_TEST_REDUCED_MOTION"] = "1"
                    env["QT_QUICK_CONTROLS_STYLE"] = "org.kde.desktop"
                    env["QT_QPA_PLATFORMTHEME"] = "kde"
                read_fd, write_fd = os.pipe()
                command = ["Xvfb", "-displayfd", str(write_fd), "-screen", "0", "1920x1080x24", "-nolisten", "tcp"]
                if args.two_screens: command += ["-screen", "1", "1280x720x24"]
                server = subprocess.Popen(command,
                                          env=env, pass_fds=(write_fd,), stdout=xlog, stderr=xlog, start_new_session=True)
                os.close(write_fd)
                try:
                    if not select.select([read_fd], [], [], 10)[0]:
                        raise RuntimeError("Private X server did not start")
                    display = os.read(read_fd, 32).decode().strip()
                    if not display.isdecimal(): raise RuntimeError("Invalid private display number")
                    env.update(DISPLAY=":" + display, QT_QPA_PLATFORM="xcb", QT_SCALE_FACTOR=str(scale),
                               MONET_TEST_FONT_SIZE=str(font), MONET_TEST_REQUIRE_FONTS="1",
                               MONET_NAV_CAPTURE=str(output), MONET_SETTINGS_TEST_LANGUAGE=language)
                    if args.language:
                        env['MONET_SETTINGS_TEST_LOCALE'] = args.language
                    command = [sys.executable, str(ROOT / "tools/test.py"), "--worker", args.module, str(output / "tests.json")]
                    with (output / "tests.log").open("w") as log:
                        completed = subprocess.run(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=90)
                    result = json.loads((output / "tests.json").read_text())
                    result.update(scale=scale, font_points=font, language=language, exit_code=completed.returncode,
                                  screen_pixels=[1920, 1080],
                                  screens_pixels=[[1920, 1080], [1280, 720]] if args.two_screens else [[1920, 1080]],
                                  renderer="Qt Widgets raster" if args.module.startswith("tests.test_extraction_navigation") else "Qt Quick software",
                                  input="Qt key/wheel events",
                                  reduced_motion=args.reduced_motion, two_screens=args.two_screens)
                    reports.append(result)
                    print(json.dumps(result), flush=True)
                finally:
                    os.close(read_fd); stop(server)
    summary = dict(runs=reports, checks=sum(r["tests"] for r in reports),
                   ok=all(not (r["exit_code"] or r["failures"] or r["errors"] or r["skipped"]) for r in reports))
    (args.output / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
