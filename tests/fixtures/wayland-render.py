"""Run native Qt rendering checks on a private KWin output and selected client renderer.

Expose a render node only; never the host compositor, bus, display-control device
or account. This qualifies a client renderer, not a physical display or hotplug.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def session(output, renderer, module, scale, render_loop):
    import dbus
    from tools.test import worker

    os.environ.update(QT_QUICK_BACKEND="" if renderer=="opengl" else "software",
                      QSG_RHI_BACKEND="opengl", QSG_INFO="1",
                      QT_LOGGING_RULES="qt.scenegraph.general=true;qt.rhi.general=true",
                      MONET_TEST_GRAPHICS_API="OpenGL" if renderer=="opengl" else "Software",
                      MONET_TEST_EXPECT_DPR=str(scale), MONET_TEST_REQUIRE_FONTS="1",
                      MONET_TEST_FONT_SIZE="10", MONET_SETTINGS_TEST_LANGUAGE="en",
                      MONET_NAV_CAPTURE=str(output), QSG_RENDER_LOOP=render_loop,
                      MONET_TEST_COLLECT_DRIVER="1" if render_loop=="basic" else "0")
    config = subprocess.run(["kscreen-doctor", "-j"], capture_output=True, text=True, check=True, timeout=15)
    names = [item["name"] for item in json.loads(config.stdout)["outputs"] if item["connected"]]
    assert len(names)==1, names
    doctor = subprocess.run(["kscreen-doctor", f"output.{names[0]}.scale.{scale}"],
                            capture_output=True, text=True, check=True, timeout=15)
    (output/"doctor.log").write_text(doctor.stdout+doctor.stderr)
    info = str(dbus.SessionBus().get_object("org.kde.KWin", "/KWin").supportInformation(dbus_interface="org.kde.KWin"))
    assert "Compositing is active" in info and "Compositing Type: OpenGL" in info, info
    (output/"support.txt").write_text(info)
    code = worker(module, str(output/"tests.json"))
    data = json.loads((output/"tests.json").read_text())
    data.update(ok=code==0 and not data["skipped"], exit_code=code,
                requested_client_renderer=renderer, render_loop=render_loop,
                native_scale=scale, compositor="KWin OpenGL",
                physical_outputs=False)
    (output/"result.json").write_text(json.dumps(data, indent=2)+"\n")
    return code if code else int(not data["ok"])


def parent(args):
    from tools.test import private_session, stop

    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    with private_session() as env:
        folder = Path(env["HOME"]).parent
        binary = folder/"bin/kwin_wayland"; binary.parent.mkdir()
        # Same basename, without the system binary's file capability, which
        # cannot execute in a rootless container.
        shutil.copyfile(shutil.which("kwin_wayland"), binary); binary.chmod(0o700)
        env.update(QT_QPA_PLATFORM="wayland", XDG_SESSION_TYPE="wayland", XDG_CURRENT_DESKTOP="KDE",
                   WAYLAND_DISPLAY="monet-render-test", KWIN_DRM_DEVICES="/dev/dri/renderD128", PYTHONFAULTHANDLER="1")
        for key in ("QT_QUICK_BACKEND", "QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS", "QSG_RHI_BACKEND", "QSG_INFO", "QSG_RENDER_LOOP"):
            env.pop(key, None)
        script = folder/"session.sh"
        script.write_text("#!/bin/sh\nexec "+shlex.join([sys.executable, str(Path(__file__).resolve()), "--session",
            str(output), args.renderer, args.module, str(args.scale), args.render_loop])+"\n"); script.chmod(0o700)
        with (output/"session.log").open("w") as log:
            process = subprocess.Popen([str(binary), "--virtual", "--output-count", "1", "--width", "1920", "--height", "1080",
                "--socket", "monet-render-test", "--no-lockscreen", "--no-global-shortcuts", "--no-kactivities",
                "--exit-with-session", str(script)], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            try: code = process.wait(timeout=120)
            finally: stop(process)
        assert code==0, "Private Wayland session failed: "+str(code)
        result = json.loads((output/"result.json").read_text()); assert result["ok"]
        print(json.dumps(result), flush=True)


if __name__=="__main__":
    if len(sys.argv)>1 and sys.argv[1]=="--session":
        sys.exit(session(Path(sys.argv[2]), sys.argv[3], sys.argv[4], float(sys.argv[5]), sys.argv[6]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--renderer", choices=["software", "opengl"], default="opengl")
    parser.add_argument("--module", default="tests.test_store_artwork")
    parser.add_argument("--scale", type=float, default=1.5)
    parser.add_argument("--render-loop", choices=["basic", "threaded"], default="threaded")
    args = parser.parse_args()
    if args.scale <= 0: parser.error("--scale must be positive")
    parent(args)
