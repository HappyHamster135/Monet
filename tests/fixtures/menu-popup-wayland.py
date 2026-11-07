"""Real Plasma menu/Transfers bounds on private mixed-scale KWin outputs.

Only a render node is exposed to the container. No host display, account, bus
or physical output-control device is used. Physical hotplug remains separate.
"""
import argparse
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def session(folder, output, points, source, widget):
    import dbus
    from tools.test import stop

    bus = dbus.SessionBus()
    env = dict(os.environ, QT_QUICK_BACKEND="software", QT_QPA_PLATFORMTHEME="kde",
               QT_QUICK_CONTROLS_STYLE="org.kde.desktop", QT_FORCE_STDERR_LOGGING="1",
               QT_LOGGING_RULES="qml.debug=true")
    data = Path(env["XDG_DATA_HOME"]); config = Path(env["XDG_CONFIG_HOME"])
    plugin = "org.monet." + widget
    title = "Monet " + widget + " popup fixture"
    observed_items = (["menuSearch", "menuOtherList", "menuPinned", "menuRecentFiles"] if widget == "menu"
                      else ["refreshTransfers", "transferScroll"])
    package = data / "plasma/plasmoids" / plugin
    shutil.copytree(ROOT / "linux/share/plasma/plasmoids" / plugin, package)
    ui = package / "contents/ui"
    for part in (ROOT / "linux/share/monet/widgets").iterdir():
        if part.is_file(): shutil.copy2(part, ui / part.name)
    if source: shutil.copyfile(source, ui / "main.qml")
    for part in ui.glob("*.qml"):
        part.write_text(part.read_text().replace("@LIBEXECDIR@", str(ROOT / "linux/libexec"))
                        .replace("@DATADIR@", str(ROOT / "linux/share")))
    main = ui / "main.qml"; code = main.read_text()
    injection = '''
    // Observation only: the actual shell creates and owns this popup.
    hideOnWindowDeactivate: false
    property int fixtureSerial: 0
    function fixtureItems(item, page) {
        let result = [];
        for (const child of item.children || []) {
            if (@ITEMS@.includes(child.objectName)) {
                const p = child.mapToItem(page, 0, 0);
                result.push({name: child.objectName, rect: [p.x, p.y, child.width, child.height]});
            }
            result = result.concat(fixtureItems(child, page));
        }
        return result;
    }
    Timer {
        interval: 300; running: true; repeat: true
        onTriggered: {
            root.expanded = true;
            const page = root.fullRepresentationItem;
            if (!page || !page.Window.window) return;
            const w = page.Window.window;
            w.title = @TITLE@;
            const record = {serial: ++root.fixtureSerial, window: [w.x, w.y, w.width, w.height],
                page: [page.width, page.height], screen: page.Screen.name,
                geometry: Plasmoid.containment.screenGeometry, available: Plasmoid.containment.availableScreenRect,
                font_points: Kirigami.Theme.defaultFont.pointSize, local_jobs: root.localJobs?.length || 0,
                items: fixtureItems(page, page)};
            console.log("MENU_POPUP_SAMPLE", JSON.stringify(record));
        }
    }
'''.replace("@ITEMS@", json.dumps(observed_items)).replace("@TITLE@", json.dumps(title))
    main.write_text(code[:code.rfind("}")] + injection + "}\n")
    (config / "kdeglobals").write_text(f"[General]\nfont=Inter,{points},-1,5,400,0,0,0,0,0\n[KDE]\nAnimationDurationFactor=0\n")
    # Use only this panel rather than letting a stock first-run layout load.
    (config / "plasma-org.kde.plasma.desktop-appletsrc").write_text(
        "[Containments][1]\nactivityId=\nformfactor=2\nimmutability=1\nlastScreen=0\nlocation=4\nplugin=org.kde.panel\n"
        f"\n[Containments][1][Applets][2]\nimmutability=1\nplugin={plugin}\n"
        "\n[Containments][1][General]\nAppletOrder=2\n"
        "\n[PlasmaViews][Panel 1][Defaults]\nthickness=48\n")

    def until(predicate, description, seconds=10):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            result = predicate()
            if result: return result
            time.sleep(.05)
        raise AssertionError(description() if callable(description) else description)

    def doctor(*arguments):
        result = subprocess.run(["kscreen-doctor", *arguments], capture_output=True, text=True, check=True, timeout=15)
        with (output / "doctor.log").open("a") as log: log.write(result.stdout + result.stderr)
        return result.stdout

    initial = json.loads(doctor("-j")); (output / "outputs.json").write_text(json.dumps(initial, indent=2) + "\n")
    names = [item["name"] for item in initial["outputs"] if item["connected"]]
    assert len(names) == 2, names
    # KScreen's JSON list is not ordered by the virtual output number.
    large, small = sorted(names)
    doctor(f"output.{large}.scale.1.25", f"output.{large}.position.0,0",
           f"output.{small}.scale.2", f"output.{small}.position.1920,0")
    info = str(bus.get_object("org.kde.KWin", "/KWin").supportInformation(dbus_interface="org.kde.KWin"))
    (output / "support.txt").write_text(info)
    assert "Compositing is active" in info and "Compositing Type: OpenGL" in info, info
    scripting = dbus.Interface(bus.get_object("org.kde.KWin", "/Scripting"), "org.kde.kwin.Scripting")
    records = []; shell = None; activity = None
    with (output / "plasma.log").open("w") as log, (output / "activity.log").open("w") as activity_log:
        try:
            activity = subprocess.Popen(["/usr/libexec/kactivitymanagerd"], env=env, stdout=activity_log,
                                        stderr=activity_log, start_new_session=True)
            until(lambda: bus.name_has_owner("org.kde.ActivityManager"), "No private activity service")
            shell = subprocess.Popen(["plasmashell", "--no-respawn"], env=env, stdout=log, stderr=log, start_new_session=True)
            until(lambda: bus.name_has_owner("org.kde.plasmashell"), "No private Plasma service")
            plasma = dbus.Interface(bus.get_object("org.kde.plasmashell", "/PlasmaShell"), "org.kde.PlasmaShell")

            def samples():
                assert shell.poll() is None, (output / "plasma.log").read_text()
                return [json.loads(line.split("MENU_POPUP_SAMPLE ", 1)[1])
                        for line in (output / "plasma.log").read_text().splitlines() if "MENU_POPUP_SAMPLE " in line]

            frame_serial = 0
            def frame(label):
                nonlocal frame_serial
                frame_serial += 1
                token = "MENU_POPUP_FRAME_" + str(frame_serial)
                path = folder / (token + ".js")
                path.write_text('const matches = workspace.stackingOrder.filter(w => w.caption === ' + json.dumps(title) + ');\n'
                    'print(' + json.dumps(token + " ") + ' + JSON.stringify(matches.map(w => ({frame: w.frameGeometry, '
                    'screen: w.output.name, output: w.output.geometry, resource: String(w.resourceClass)}))));\n')
                ident = int(scripting.loadScript(str(path))); assert ident >= 0
                try:
                    dbus.Interface(bus.get_object("org.kde.KWin", "/Scripting/Script" + str(ident)), "org.kde.kwin.Script").run()
                    line = until(lambda: next((line for line in (output / "kwin.log").read_text().splitlines() if token + " " in line), None), label)
                    values = json.loads(line.split(token + " ", 1)[1]); assert len(values) == 1, values
                    return values[0]
                finally: scripting.unloadScript(str(path))

            def check(label, name, scale):
                before = samples(); serial = before[-1]["serial"] if before else 0
                expected_width = round(1920 / scale); expected_height = round(1080 / scale)
                matching = until(lambda: next((sample for sample in reversed(samples()) if sample["serial"] > serial
                    and sample["screen"] == name and abs(sample["geometry"]["width"] - expected_width) <= 1
                    and abs(sample["geometry"]["height"] - expected_height) <= 1), None), lambda: samples()[-3:])
                # Let native frame/anchor updates settle, then compare the compositor.
                time.sleep(.4)
                matching = samples()[-1]
                def placed():
                    native = frame(label); rect = native["frame"]; screen = native["output"]; area = matching["available"]
                    left = screen["x"] + area["x"]; top = screen["y"] + area["y"]
                    if (native["screen"] == name and rect["x"] >= left - 1 and rect["y"] >= top - 1
                        and rect["x"] + rect["width"] <= left + area["width"] + 1
                        and rect["y"] + rect["height"] <= top + area["height"] + 1): return native
                    return None
                native = until(placed, lambda: dict(sample=samples()[-1], native=frame(label)), seconds=5)
                rect = native["frame"]; screen = native["output"]; area = matching["available"]
                context = dict(label=label, sample=matching, native=native)
                assert matching["font_points"] == points, context
                if widget == "transfers": assert matching["local_jobs"] == 3, context
                assert native["screen"] == name, context
                # Containment's available rectangle is relative to its own output.
                left = screen["x"] + area["x"]; top = screen["y"] + area["y"]
                assert rect["x"] >= left - 1 and rect["y"] >= top - 1, context
                assert rect["x"] + rect["width"] <= left + area["width"] + 1, context
                assert rect["y"] + rect["height"] <= top + area["height"] + 1, context
                for item in matching["items"]:
                    x, y, width, height = item["rect"]
                    assert width >= 30 and height >= 30 and x >= -1 and y >= -1, context
                    assert x + width <= matching["page"][0] + 1 and y + height <= matching["page"][1] + 1, context
                records.append(context); print(json.dumps(context), flush=True)

            until(lambda: bool(samples()), lambda: (output / "plasma.log").read_text())
            if widget == "transfers":
                from tests.test_files_qol import jobs_module
                queue = jobs_module().Queue()
                archive = folder / "Native popup archive # å.zip"
                with zipfile.ZipFile(archive, "w") as packed: packed.writestr("readme.txt", "small native extraction")
                for i in range(3):
                    destination = folder / ("Extracted output " + str(i))
                    job = queue.submit(archive, destination); queue.run(job["token"], reveal=False)
                    assert queue.read(job["token"])["state"] == "done"
                    assert (destination / "readme.txt").read_text() == "small native extraction"
                until(lambda: samples()[-1]["local_jobs"] == 3, lambda: (output / "plasma.log").read_text())
            for scale in (1.25, 1.5, 2):
                doctor(f"output.{large}.scale.{scale}")
                check("bottom panel, live scale " + str(scale), large, scale)
            doctor(f"output.{large}.scale.1.25")
            plasma.evaluateScript("panels()[0].screen = 1;")
            check("panel moved to other output", small, 2)
            doctor(f"output.{small}.scale.1.75")
            check("other output live scale", small, 1.75)
            plasma.evaluateScript('panels()[0].location = "top";')
            check("top panel", small, 1.75)
            text = (output / "plasma.log").read_text()
            assert not any(error in text for error in ("ReferenceError:", "TypeError:", "Unable to assign", "Cannot assign to non-existent property")), text
        finally:
            if shell is not None: stop(shell)
            if activity is not None: stop(activity)
    result = dict(ok=True, widget=widget, font_points=points, records=records, renderer="Qt Quick software", compositor="KWin OpenGL", physical_outputs=False)
    (output / "result.json").write_text(json.dumps(result, indent=2) + "\n")
    return 0


def parent(args):
    from tools.test import private_session, stop
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=True)
    results = []
    for points in args.fonts:
        part = output / ("font-" + str(points)); part.mkdir(exist_ok=True)
        with private_session() as env:
            folder = Path(env["HOME"]).parent; binary = folder / "bin/kwin_wayland"; binary.parent.mkdir()
            shutil.copyfile(shutil.which("kwin_wayland"), binary); binary.chmod(0o700)
            env.update(QT_QPA_PLATFORM="wayland", XDG_SESSION_TYPE="wayland", XDG_CURRENT_DESKTOP="KDE",
                       WAYLAND_DISPLAY="monet-menu-popup", KWIN_DRM_DEVICES="/dev/dri/renderD128",
                       QT_FORCE_STDERR_LOGGING="1",
                       QT_LOGGING_RULES="kwin_scripting.debug=true;js.debug=true;qml.debug=true")
            for key in ("QT_QUICK_BACKEND", "QT_SCALE_FACTOR", "QT_SCREEN_SCALE_FACTORS", "QSG_RHI_BACKEND", "QSG_RENDER_LOOP"):
                env.pop(key, None)
            script = folder / "session.sh"
            script.write_text("#!/bin/sh\nexec " + shlex.join([sys.executable, str(Path(__file__).resolve()), "--session",
                str(folder), str(part), str(points), str(args.source.resolve()) if args.source else "", args.widget]) + "\n"); script.chmod(0o700)
            with (part / "kwin.log").open("w") as log:
                process = subprocess.Popen([str(binary), "--virtual", "--output-count", "2", "--width", "1920", "--height", "1080",
                    "--socket", "monet-menu-popup", "--no-lockscreen", "--no-global-shortcuts", "--no-kactivities",
                    "--exit-with-session", str(script)], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                try: code = process.wait(timeout=90)
                finally: stop(process)
            assert code == 0, "Private Plasma/menu session failed: " + str(code)
            results.append(json.loads((part / "result.json").read_text()))
    summary = dict(ok=all(result["ok"] for result in results), runs=results,
                   checks=sum(len(result["records"]) for result in results))
    (output / "result.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(dict(ok=summary["ok"], checks=summary["checks"])), flush=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--session":
        sys.exit(session(Path(sys.argv[2]), Path(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6]))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--fonts", type=int, nargs="+", default=[10, 14])
    parser.add_argument("--source", type=Path, help="Controlled menu source override for a failure reproduction")
    parser.add_argument("--widget", choices=["menu", "transfers"], default="menu")
    parent(parser.parse_args())
