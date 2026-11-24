"""Ask KWin to keep a newly opened Scratchpad above other windows on Wayland."""
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader
import json
import os
from pathlib import Path
import sys


def keep_above(helpers, caption):
    loader = SourceFileLoader("monet_resume", str(helpers / "monet-resume"))
    resume = module_from_spec(spec_from_loader(loader.name, loader))
    loader.exec_module(resume)
    # KWin may add the window just after the application has shown its editor.
    return resume.kwin_script("""
        function matches(w) {
            return w.normalWindow && w.pid === %d && appId(w) === "monet-utilities.desktop"
                && w.captionNormal === %s;
        }
        function pin(w) {
            w.keepAbove = true;
            reply(w.keepAbove);
        }
        const existing = workspace.stackingOrder.slice().reverse().find(matches);
        if (existing) pin(existing);
        else workspace.windowAdded.connect(w => { if (matches(w)) pin(w); });
    """ % (os.getppid(), json.dumps(caption)))


if __name__ == "__main__":
    sys.exit(0 if keep_above(Path(sys.argv[1]), sys.stdin.buffer.read().decode("utf-8")) else 1)
