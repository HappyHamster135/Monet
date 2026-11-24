"""Supply a selected player to Fedora's existing media shortcut handlers."""
from pathlib import Path
import re
import shutil
import sys


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError("Unexpected upstream media service around " + before[:60])
    return text.replace(before, after)


def adapt(source, output):
    header = (source / "mprisservice.h").read_text()
    code = (source / "mprisservice.cpp").read_text()
    header = once(header, "#include <QBindable>", '#include "rules.h"')
    header = once(header, "Q_OBJECT_BINDABLE_PROPERTY_WITH_ARGS(MprisService, PlayerContainer *, m_activePlayer, nullptr)",
                  "MediaKeyRules m_rules;")
    code = once(code, """    m_activePlayer.setBinding([this] {
        return m_multiplexer->activePlayer().value();
    });""", "")
    code = once(code, "void (MprisService::*callback)()", "void (MprisService::*callback)(PlayerContainer *)")
    code = once(code, "connect(action, &QAction::triggered, this, callback);", """connect(action, &QAction::triggered, this, [this, name, callback] {
            if (auto *player = m_rules.target(m_multiplexer->activePlayer().value(), name)) {
                (this->*callback)(player);
            }
        });""")
    methods = re.findall(r"    void (on\w+)\(\);", header)
    if not methods or "onPlayPause" not in methods:
        raise ValueError("Upstream playback shortcuts could not be identified")
    for method in methods:
        header = once(header, f"void {method}();", f"void {method}(PlayerContainer *player);")
        code = once(code, "MprisService::" + method + "()", "MprisService::" + method + "(PlayerContainer *player)")
    (output / "mprisservice.h").write_text(header)
    (output / "mprisservice.cpp").write_text(code.replace("m_activePlayer", "player"))
    shutil.copyfile(source / "mprisservice.json", output / "mprisservice.json")


if __name__ == "__main__":
    adapt(Path(sys.argv[1]), Path(sys.argv[2]))
