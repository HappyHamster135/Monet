"""Compare real Ark plugins and test selected extraction with an isolated RPM.

Usage: rpm-list-native.py LIST_PROBE ORIGINAL_PLUGIN CANDIDATE_PLUGIN OUTPUT
Builds a tiny fixture package; never installs it or executes its scriptlets.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import zipfile

probe,original,candidate,output=map(Path,sys.argv[1:]);output.mkdir(parents=True,exist_ok=False)
with tempfile.TemporaryDirectory(prefix='monet-rpm-index-') as temp:
    root=Path(temp);build=root/'rpmbuild'
    for name in ['BUILD','BUILDROOT','RPMS','SOURCES','SPECS','SRPMS']:(build/name).mkdir(parents=True)
    spec=build/'SPECS/monet-rpm-index.spec'
    spec.write_text('''Name: monet-rpm-index-fixture
Version: 1
Release: 1
Summary: Disposable file index fixture
License: MIT
BuildArch: noarch
%description
Not an application. Never install this fixture.
%install
mkdir -p %{buildroot}/opt/monet-index
python3 - '%{buildroot}/opt/monet-index' <<'PYFILES'
import os,sys
from pathlib import Path
p=Path(sys.argv[1])
(p/'space \\"quote\\" å $(touch NO).txt').write_text('Read-only preview and selected extraction.\\n')
(p/'source.txt').write_text('hard-linked file\\n')
os.link(p/'source.txt',p/'linked.txt')
(p/'shortcut').symlink_to('source.txt')
(p/'empty').mkdir()
PYFILES
%post
exit 99
%files
/opt/monet-index
%ghost /opt/monet-ghost
''')
    with (output/'build.log').open('w') as log:
        subprocess.run(['rpmbuild','-bb','--define','_topdir '+str(build),str(spec)],check=True,stdout=log,stderr=log)
    package=next((build/'RPMS').rglob('*.rpm'))
    def run(plugin,source,label,*extra,ok=True):
        report=output/(label+'.json')
        with (output/(label+'.log')).open('w') as log:
            result=subprocess.run([str(probe),str(plugin),str(source),str(report),*map(str,extra)],stdout=log,stderr=log,timeout=20)
        assert (result.returncode==0)==ok,(label,result.returncode,(output/(label+'.log')).read_text())
        return json.loads(report.read_text())
    old=run(original,package,'original')
    new=run(candidate,package,'candidate')
    old_paths={e['fullPath'] for e in old['entries']};new_paths={e['fullPath'] for e in new['entries']}
    assert old_paths==new_paths and not any('monet-ghost' in p for p in new_paths),(old_paths,new_paths)
    member=next(p for p in new_paths if 'quote' in p)
    target=root/'extracted';target.mkdir()
    extracted=run(candidate,package,'selected-extraction',member,target)
    assert extracted['extracted']
    files=[p for p in target.rglob('*') if p.is_file()]
    assert len(files)==1 and files[0].read_text()=='Read-only preview and selected extraction.\n',files
    assert not (root/'NO').exists()
    source=root/'plain.zip'
    with zipfile.ZipFile(source,'w') as archive:archive.writestr('normal.txt','normal fallback')
    zipped=run(candidate,source,'zip-fallback')
    assert zipped['count']==1 and zipped['entries'][0]['fullPath']=='normal.txt'
    broken=root/'broken.rpm';broken.write_bytes(bytes.fromhex('edabeedb')+b'not a valid header')
    invalid=run(candidate,broken,'invalid-fallback',ok=False)
    assert not invalid['ok'] and invalid['error']
    cancelled=run(candidate,package,'cancelled-list','cancel',ok=False)
    assert not cancelled['ok'] and cancelled['count']==0
    result=dict(passed=True,matching_paths=len(new_paths),ghost_omitted=True,unicode_quotes_shell_characters=True,
                selected_extraction=True,only_selected_file_extracted=True,zip_fallback=True,invalid_rpm_error=True,
                cancelled_list=True,package_installed=False,scriptlets_executed=False)
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
