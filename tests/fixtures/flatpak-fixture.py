"""Install a tiny fixture into the container's private user installation only."""
import os
from pathlib import Path
import subprocess
import tempfile

APP_ID = 'org.monet.AutofillFixture'

def command(program, arguments, readonly=(), talk=()):
    assert os.environ.get('MONET_PASSWORDS_PRIVATE_BUS') == '1'
    root = tempfile.TemporaryDirectory(prefix='monet-flatpak-form-')
    build = Path(root.name)/'build'; (build/'files/bin').mkdir(parents=True)
    (build/'metadata').write_text('[Application]\nname='+APP_ID+'\n'
                                  'runtime=org.freedesktop.Platform/x86_64/25.08\n'
                                  'sdk=org.freedesktop.Platform/x86_64/25.08\ncommand=fixture\n')
    launcher = build/'files/bin/fixture'
    launcher.write_text('#!/bin/sh\nexec "$@"\n'); launcher.chmod(0o755)
    repo = Path(root.name)/'repo'
    data = Path(root.name)/'data'
    environment = dict(os.environ, XDG_DATA_HOME=str(data))
    # Private test buses have no desktop session manager to export this address.
    # Use the actual private accessibility bus, still behind Flatpak's filter.
    import dbus
    a11y = str(dbus.SessionBus().get_object('org.a11y.Bus','/org/a11y/bus').GetAddress(dbus_interface='org.a11y.Bus'))
    for args in (
        ['flatpak','build-finish','--socket=x11','--share=ipc',*['--talk-name='+name for name in talk],str(build)],
        ['flatpak','build-export','--disable-sandbox',str(repo),str(build)],
        ['flatpak','install','--user','--assumeyes','--no-deps','--no-related',str(repo),APP_ID],
    ):
        result=subprocess.run(args,capture_output=True,text=True,timeout=30,env=environment)
        if result.returncode: raise RuntimeError(result.stderr[-2000:])
    if os.environ.get('MONET_FLATPAK_SUPPORT_FIXTURE') == '1':
        from app_support import AppSupport
        support=AppSupport(data,Path(root.name)/'config',runner=lambda *a,**kw:subprocess.run(*a,**kw,env=environment))
        support.change(APP_ID,True)
        cleanup=root.cleanup
        def restore():
            support.change(APP_ID,False)
            assert not (support.overrides/APP_ID).exists()
            cleanup()
        root.cleanup=restore
    return root, ['env','XDG_DATA_HOME='+str(data),'AT_SPI_BUS_ADDRESS='+a11y,'flatpak','run',*(['--verbose'] if os.environ.get('MONET_LOGIN_TRACE')=='1' else []),'--user','--a11y-bus','--unshare=network',
                  *['--filesystem='+str(path)+':ro' for path in readonly], APP_ID, program, *arguments]
