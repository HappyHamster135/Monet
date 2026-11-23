#!/usr/bin/python3
"""Fetch this exact commit's CI Linux package for the non-publishing boot bench."""
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
import tarfile
import time


def api(path):
    return json.loads(subprocess.check_output(['gh','api',path],text=True))


def main():
    repo=os.environ['GITHUB_REPOSITORY'];sha=os.environ['GITHUB_SHA']
    root=Path('target/boot-profile');download=root/'download';download.mkdir(parents=True,exist_ok=True)
    deadline=time.monotonic()+2400
    while time.monotonic()<deadline:
        runs=api(f'repos/{repo}/actions/workflows/build.yml/runs?head_sha={sha}&per_page=5')['workflow_runs']
        found=None
        for run in runs:
            if run['head_sha']!=sha:continue
            for artifact in api(f'repos/{repo}/actions/runs/{run["id"]}/artifacts')['artifacts']:
                if artifact['name']=='release-linux' and not artifact['expired']: found=(run,artifact);break
            if found:break
        if found:break
        print('Waiting for this commit’s release-linux build artifact',flush=True);time.sleep(15)
    else:raise RuntimeError('This commit did not produce a Linux package before the timeout')
    run,artifact=found
    subprocess.run(['gh','run','download',str(run['id']),'--repo',repo,'--name','release-linux','--dir',str(download)],check=True)
    version=Path('VERSION').read_text().strip()
    packages=list(download.rglob(f'Monet-{version}-Linux.tar.gz'))
    if len(packages)!=1:raise RuntimeError('Expected one version-matched Linux package')
    package=root/'package';package.mkdir()
    with tarfile.open(packages[0]) as tar:
        # This is a trusted CI artifact, but do not permit filesystem escapes.
        for member in tar:
            path=PurePosixPath(member.name)
            if path.is_absolute() or '..' in path.parts or member.isdev():raise ValueError('Unsafe package member')
        tar.extractall(package,filter='data')
    # Release archives contain a named top-level directory.
    installs=list(package.glob('*/install.sh'))
    if len(installs)==1 and not (package/'install.sh').exists():
        folder=installs[0].parent
        for child in folder.iterdir():child.rename(package/child.name)
        folder.rmdir()
    if not (package/'install.sh').is_file() or not (package/'monet').is_file():
        raise RuntimeError('Linux package layout changed')
    (root/'package-source.json').write_text(json.dumps(dict(sha=sha,run=run['id'],artifact=artifact['id'],version=version),indent=2)+'\n')


if __name__=='__main__':main()
