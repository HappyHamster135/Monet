"""Type into the actual menu with Kicker runners on a private bus; never launch."""
import json, os, subprocess, sys, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT))
from tools.test import private_session, stop

if len(sys.argv)==2:
    out=Path(sys.argv[1]).resolve();out.mkdir(parents=True,exist_ok=True)
    with private_session() as env:
        # Read the real installed app/file catalog, without the user's bus,
        # display or caches. All launch hooks in the representation are inert.
        env.update(HOME=str(Path.home()),XDG_DATA_HOME=str(Path.home()/'.local/share'))
        with (out/'run.log').open('w') as log:
            p=subprocess.Popen([sys.executable,__file__,str(out),'child'],env=env,stdout=log,stderr=log,start_new_session=True)
            try:
                try: code=p.wait(timeout=35)
                except subprocess.TimeoutExpired:
                    (out/'timeout.json').write_text(json.dumps(dict(timed_out=True)))
                    raise
                assert code==0,(out/'run.log').read_text()
            finally:stop(p)
    print((out/'result.json').read_text())
else:
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtTest import QTest
    from tests.test_everyday_search import MenuSearchUI
    out=Path(sys.argv[1]);MenuSearchUI.setUpClass()
    case=MenuSearchUI();case.native_runner=True;case.setUp()
    ticks=[];timer=QTimer();timer.setInterval(10);timer.timeout.connect(lambda:ticks.append(time.monotonic()));timer.start()
    records=[]
    try:
        for query in ['chatgpt','zen','chatgpt','settings']:
            case.search.setProperty('text','');case.search.forceActiveFocus();QTest.qWait(100)
            for index,char in enumerate(query):
                start=time.monotonic();QTest.keyClick(case.window,Qt.Key(ord(char.upper())));QTest.qWait(180)
                record=dict(query=query,text=case.search.property('text'),elapsed=time.monotonic()-start)
                records.append(record);print(json.dumps(record),flush=True)
                assert record['text']==query[:index+1] and record['elapsed']<1,record
            QTest.qWait(500)
        max_gap=max((b-a for a,b in zip(ticks,ticks[1:])),default=0)
        assert max_gap<1,max_gap
        result=dict(passed=True,queries=4,characters=len(records),maximum_key_seconds=max(r['elapsed'] for r in records),maximum_event_loop_gap_seconds=max_gap,records=records,app_launches=0)
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    finally:case.tearDown()
