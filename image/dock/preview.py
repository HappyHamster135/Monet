#!/usr/bin/python3
"""Launch Plasma with a verified account-local dock, otherwise the stock applet."""
import json
import os
from pathlib import Path
import sys
import subprocess


def main():
    here=Path(__file__).resolve().parent
    try:
        from bundle import verify, digest, PLUGIN
        manifest=json.loads((here/'runtime.json').read_text())
        verify(manifest)
        plugin=here/'plugins/plasma/applets'/PLUGIN
        if digest(plugin)!=manifest['files'][PLUGIN]:
            raise ValueError('Changed dock plugin')
        paths=[str(here/'plugins')]
        if os.environ.get('QT_PLUGIN_PATH'):paths.append(os.environ['QT_PLUGIN_PATH'])
        os.environ['QT_PLUGIN_PATH']=os.pathsep.join(paths)
    except (ImportError,OSError,ValueError,KeyError,RuntimeError,subprocess.SubprocessError):
        print('Monet dock preview does not match this runtime; using the system dock.',file=sys.stderr)
    os.execv('/usr/bin/plasmashell',['plasmashell','--no-respawn'])

if __name__=='__main__':main()
