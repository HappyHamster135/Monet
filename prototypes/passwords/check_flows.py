#!/usr/bin/env python3
"""Exercise synthetic login flows in the explicitly isolated Zen/vault fixture.

Requires setup-fixture.py's private bus, loopback server and disposable profile.
Never point Marionette at the normal user profile. Run after installing a fixture
build and enabling single-account autofill through its actual options UI.
"""
from pathlib import Path
import argparse
import sys,json,time,os,dbus
ROOT=Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--state-dir',type=Path,required=True)
parser.add_argument('--result',default='flow-results.json')
args=parser.parse_args();OUT=args.state_dir.resolve()
if Path(args.result).name != args.result: parser.error('Result must be a filename within the fixture directory.')
profile=Path.home()/'.var/app/app.zen_browser.zen/.zen/monet-browser-flows-test'
address=json.loads((OUT/'fixture-bus.json').read_text())[0]
assert address != os.environ.get('DBUS_SESSION_BUS_ADDRESS'), 'Refuse the desktop session bus'
sys.path[:0]=[str(ROOT/'prototypes/passwords'),str(ROOT/'linux/share/monet/passwords')]
from test_zen import Browser
from vault import pack_map,unpack_map
bus=dbus.bus.BusConnection(address)
assert bus.get_unique_name() and not str(bus.get_unique_name()).startswith('unix:')
api=dbus.Interface(bus.get_object('org.kde.kwalletd6','/modules/kwalletd6'),'org.kde.KWallet')
assert str(api.localWallet())=='fixture', 'Refuse a real vault'
APP='Monet Passwords';SITE='http://127.0.0.1:8765';b=Browser();results=[]
assert b.js('return Services.dirsvc.get("ProfD", Ci.nsIFile).path;')==str(profile), 'Refuse the normal browser profile'
b.call('Marionette:SetContext',{'value':'content'})
anchor=b.call('WebDriver:GetWindowHandle')['value']
def accounts():return [unpack_map(bytes(api.readMap(42,'Monet Logins',k,APP))) for k in api.entryList(42,'Monet Logins',APP)]
def seed(rows):
 for key in api.entryList(42,'Monet Logins',APP):api.removeEntry(42,'Monet Logins',key,APP)
 for name,password in rows:api.writeMap(42,'Monet Logins','Fixture '+name,dbus.ByteArray(pack_map({'Username':name,'Password':password,'Website':SITE,'Notes':''})),APP)
def proposals():return [json.loads(x) for x in (OUT/'fixture-consents.jsonl').read_text().splitlines()] if (OUT/'fixture-consents.jsonl').exists() else []
def nav(path):b.call('WebDriver:Navigate',{'url':SITE+path});time.sleep(.65)
def values(fields):
 for name,value in fields.items():
  b.js('const e=document.querySelector('+json.dumps('[name='+name+']')+');e.value='+json.dumps(value)+';e.dispatchEvent(new Event("input",{bubbles:true}));return true;')
def click():
 el=b.call('WebDriver:FindElement',{'using':'css selector','value':'button'})['value'];b.call('WebDriver:ElementClick',{'id':next(iter(el.values()))});time.sleep(.8)
def blank(name):return b.js('return document.querySelector('+json.dumps('[name='+name+']')+')?.value === "";')
def equals(name,value):return b.js('return document.querySelector('+json.dumps('[name='+name+']')+')?.value === '+json.dumps(value)+';')
def case(name,rows,fn):
 seed(rows);new=b.call('WebDriver:NewWindow',{'type':'tab'})['handle'];b.call('WebDriver:SwitchToWindow',{'handle':new});time.sleep(.1)
 try:fn();results.append({'case':name,'pass':True})
 except AssertionError as exc:results.append({'case':name,'pass':False,'reason':str(exc)})
 finally:
  b.call('WebDriver:CloseWindow');b.call('WebDriver:SwitchToWindow',{'handle':anchor})
 print(results[-1],flush=True)
def simple():
 nav('/');values({'username':'alice','password':'SyntheticFirst1'});click();r=accounts();assert len(r)==1 and r[0]['Username']=='alice','simple save missing'
 nav('/');assert equals('username','alice') and equals('password','SyntheticFirst1'),'simple autofill missing'
def multi_new():
 nav('/multi-user');values({'username':'alice'});click();assert b.js('return location.pathname;')=='/multi-password'
 values({'password':'SyntheticFirst1'});click();r=accounts();assert len(r)==1 and r[0]['Username']=='alice','username not carried to password step'
def multi_existing():
 nav('/multi-user');assert equals('username','alice'),'username first-step autofill missing';click();assert equals('password','SyntheticFirst1'),'password second-step autofill missing'
def change():
 nav('/change-full');assert equals('current','SyntheticFirst1'),'current password not filled';assert blank('newpassword') and blank('confirmation'),'old password filled into new-password fields'
 values({'username':'alice','current':'SyntheticFirst1','newpassword':'SyntheticChanged2','confirmation':'SyntheticChanged2'});click();r=accounts();assert len(r)==1 and r[0]['Password']=='SyntheticChanged2','new password not updated'
 nav('/');assert equals('password','SyntheticChanged2'),'autofill retained old password'
def change_no_user():
 nav('/change-no-user');values({'current':'SyntheticFirst1','newpassword':'SyntheticChanged2','confirmation':'SyntheticChanged2'});click();r=accounts();assert len(r)==1 and r[0]['Username']=='alice' and r[0]['Password']=='SyntheticChanged2','password-only update lost account'
def mismatch():
 nav('/change-full');before=len(proposals());values({'username':'alice','current':'SyntheticFirst1','newpassword':'MismatchNew2','confirmation':'MismatchOther3'});click()
 assert len(proposals())==before,'invalid confirmation opened consent';assert accounts()[0]['Password']=='SyntheticFirst1','mismatch changed saved password'
def dynamic():
 nav('/multi-dynamic');values({'username':'alice'});click();values({'password':'SyntheticFirst1'});click();r=accounts();assert len(r)==1 and r[0]['Username']=='alice','dynamic username step lost account'
def multi_different():
 nav('/multi-user');values({'username':'bob'});click();assert blank('password'),'different account received alice password';values({'password':'SyntheticBob2'});click()
 r=accounts();assert len(r)==2 and any(x['Username']=='bob' and x['Password']=='SyntheticBob2' for x in r),'different account updated alice'
def multi_choice():
 nav('/multi-user');assert blank('username'),'multiple accounts autofilled before choice';values({'username':'bob'});click();assert equals('password','SyntheticBob2'),'chosen username did not select matching password'
 before=len(proposals());click();assert len(proposals())==before,'unchanged chosen account prompted'
def update_choice():
 nav('/multi-user');values({'username':'bob'});click();values({'password':'SyntheticChanged3'});click();r=accounts()
 assert len(r)==2 and any(x['Username']=='bob' and x['Password']=='SyntheticChanged3' for x in r) and any(x['Username']=='alice' and x['Password']=='SyntheticFirst1' for x in r),'update changed the wrong account'
def change_choice():
 nav('/change-no-user');values({'current':'SyntheticBob2','newpassword':'SyntheticChanged3','confirmation':'SyntheticChanged3'});click();r=accounts()
 assert len(r)==2 and any(x['Username']=='bob' and x['Password']=='SyntheticChanged3' for x in r),'current-password account not updated'
def ambiguous_change():
 nav('/change-no-user');before=len(proposals());values({'current':'SharedTest1','newpassword':'SyntheticChanged3','confirmation':'SyntheticChanged3'});click()
 assert len(proposals())==before,'ambiguous account opened save prompt';assert len(accounts())==2 and all(x['Password']=='SharedTest1' for x in accounts()),'ambiguous change wrote a login'
def signup_match():
 nav('/signup-confirm');values({'username':'alice','newpassword':'SyntheticFirst1','confirmation':'SyntheticFirst1'});click();r=accounts();assert len(r)==1 and r[0]['Password']=='SyntheticFirst1','matching signup not saved'
def signup_mismatch():
 nav('/signup-confirm');before=len(proposals());values({'username':'alice','newpassword':'MismatchNew2','confirmation':'MismatchOther3'});click()
 assert len(proposals())==before and len(accounts())==0,'mismatched signup was offered for saving'
def denied_change():
 nav('/change-full');before=len(proposals());(OUT/'fixture-approval.json').write_text('{"approved":false}')
 try:
  values({'username':'alice','current':'SyntheticFirst1','newpassword':'SyntheticChanged2','confirmation':'SyntheticChanged2'});click()
  assert len(proposals())==before+1 and proposals()[-1]['kind']=='update','no update approval requested';assert accounts()[0]['Password']=='SyntheticFirst1','declined change replaced password'
 finally:(OUT/'fixture-approval.json').write_text('{"approved":true}')
def cross_origin_step():
 nav('/multi-user');values({'username':'bob'});click();b.call('WebDriver:Navigate',{'url':'http://localhost:8765/multi-password'});time.sleep(.7)
 assert blank('password'),'different origin received a password'
 nav('/multi-password');assert equals('password','SyntheticFirst1'),'origin change did not clear previous account context'
def locked_step():
 screen=dbus.Interface(bus.get_object('org.freedesktop.ScreenSaver','/ScreenSaver'),'org.monet.Test')
 nav('/multi-user');values({'username':'bob'});click();screen.SetActive(True);time.sleep(.4)
 nav('/multi-password');assert blank('password'),'screen lock allowed autofill'
 screen.SetActive(False);time.sleep(.6);nav('/multi-password');assert equals('password','SyntheticFirst1'),'unlock retained previous account context or failed to refill'
try:
 case('basic save and autofill',[],simple)
 case('new account over two pages',[],multi_new)
 case('existing account over two pages',[('alice','SyntheticFirst1')],multi_existing)
 case('three-field password change',[('alice','SyntheticFirst1')],change)
 case('change without username',[('alice','SyntheticFirst1')],change_no_user)
 case('mismatched confirmation',[('alice','SyntheticFirst1')],mismatch)
 case('dynamic username step',[],dynamic)
 case('username differs from saved account',[('alice','SyntheticFirst1')],multi_different)
 case('two accounts, explicit username choice',[('alice','SyntheticFirst1'),('bob','SyntheticBob2')],multi_choice)
 case('two accounts, update chosen username',[('alice','SyntheticFirst1'),('bob','SyntheticBob2')],update_choice)
 case('password change identifies current account',[('alice','SyntheticFirst1'),('bob','SyntheticBob2')],change_choice)
 case('ambiguous password change requires choice',[('alice','SharedTest1'),('bob','SharedTest1')],ambiguous_change)
 case('matching signup confirmation',[],signup_match)
 case('mismatched signup confirmation',[],signup_mismatch)
 case('declined password change',[('alice','SyntheticFirst1')],denied_change)
 case('cross-origin username step isolated',[('alice','SyntheticFirst1')],cross_origin_step)
 case('screen lock clears username step',[('alice','SyntheticFirst1')],locked_step)
 (OUT/args.result).write_text(json.dumps(results,indent=2))
finally:b.close();bus.close()
if not all(row['pass'] for row in results):raise SystemExit(1)
