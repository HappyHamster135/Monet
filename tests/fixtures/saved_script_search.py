"""Drive saved scripts through the real runner on a private desktop bus."""
import json
from pathlib import Path
import sys
import time

import dbus
import dbus.service
from gi.repository import GLib


def check_script_search(bus, runner, other, call, config, copied):
    from saved_scripts import save
    notes = []

    class Notices(dbus.service.Object):
        @dbus.service.method("org.freedesktop.Notifications", in_signature="susssasa{sv}i", out_signature="u")
        def Notify(self, app, replaces, icon, title, body, actions, hints, duration):
            notes.append((str(title), str(body)))
            return 1

    receiver = Notices(dbus.service.BusName("org.freedesktop.Notifications", bus), "/org/freedesktop/Notifications")
    def await_notice(count):
        context = GLib.MainContext.default()
        until = time.monotonic() + 3
        while time.monotonic() < until and len(notes) < count:
            while context.pending():
                context.iteration(False)
            time.sleep(.005)
        assert len(notes) == count, notes

    config.setValue("hidden", "[]")
    config.sync()
    manage, = runner.Match("script:")
    assert manage[0] == "scripts"
    folder = Path.home()/"my saved scripts"
    folder.mkdir()
    path = folder/"echo argument"
    path.write_text(f"#!{sys.executable}\n" + """import json,sys
from pathlib import Path
with Path("runs").open("a") as stream:
    print(json.dumps(sys.argv[1:]), file=stream)
if sys.argv[1] == "slow":
    import time
    time.sleep(1)
    Path("obsolete").touch()
if sys.argv[1] == "failure":
    print("failed <check>", file=sys.stderr)
    sys.exit(4)
if sys.argv[1]:
    print(sys.argv[1])
""")
    path.chmod(0o700)
    script = save(config, "Echo text", str(path), False, False)
    def runs():
        records = folder/"runs"
        return [json.loads(s) for s in records.read_text().splitlines()] if records.exists() else []
    arg = 'C++  "two" $(spaces); á'
    row, = runner.Match("tools script: ECHO text " + arg)
    assert not runs() and arg not in row[0] and row[1] == "Echo text"
    call(other.Run, row[0], "")
    assert not other.Match("script:") and not runs()
    call(runner.Run, row[0], "")
    await_notice(1)
    assert runs() == [[arg]] and copied[-1] == arg
    for query, expected in (("script: Echo text", "Finished with no output"), ("script: Echo text failure", "code 4")):
        choice, = runner.Match(query)
        count = len(notes) + 1
        call(runner.Run, choice[0], "")
        await_notice(count)
        assert expected in notes[-1][1] and copied[-1] == arg, notes

    save(config, script.name, str(path), True, True, script.ident)
    obsolete = []
    runner.Match("script: Echo text slow", reply_handler=obsolete.append, error_handler=obsolete.append)
    until = time.monotonic() + 3
    while ["slow"] not in runs() and time.monotonic() < until:
        GLib.MainContext.default().iteration(False)
        time.sleep(.01)
    assert ["slow"] in runs()
    call(runner.Match, "tools")
    assert obsolete == [[]]
    previous = runs()
    short, = runner.Match("script: echo")
    assert "Add text" in short[-1]["subtext"] and not runs()[len(previous):]
    replies = []
    runner.Match("script: Echo text old", reply_handler=replies.append, error_handler=lambda e: replies.append(e))
    choice, = call(runner.Match, "script: Echo text preview value")[0]
    assert replies == [[]] and runs() == previous + [["preview value"]]
    assert choice[-1]["subtext"] == "preview value"
    same, = runner.Match("script: Echo text preview value")
    assert choice[0] == same[0] and runs() == previous + [["preview value"]]
    runner.Teardown()
    call(runner.Run, choice[0], "")
    await_notice(4)
    assert copied[-1] == "preview value" and runs() == previous + [["preview value"]]
    before = list(copied)
    config.remove("savedScripts/" + script.ident)
    config.sync()
    call(runner.Run, choice[0], "")
    assert copied == before and "no longer" in notes[-1][0]
    config.setValue("hidden", json.dumps(["scripts"]))
    config.sync()
    assert not runner.Match("script:")
    time.sleep(1.05)
    assert not (folder/"obsolete").exists()
    receiver.remove_from_connection()
