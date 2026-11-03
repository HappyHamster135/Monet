"""Synthetic credentials only: browser consent, origin boundaries and protocol."""
import base64
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from tests.test_native_passwords import FakeWallet, Vault, VaultError, PERSONAL_FOLDER, pack_map
from browser_store import BrowserStore, BrowserError, origin, entry_id, CONNECTIONS
from browser_setup import configured_user_js, plan, apply
try:
    from nacl.public import PrivateKey, Box, PublicKey
    from browser_protocol import Protocol, b64, increment, read_message, write_message
    NACL = True
except ImportError:
    NACL = False

class BrowserStorage(unittest.TestCase):
    def setUp(self):
        self.transport=FakeWallet();self.vault=Vault(self.transport);self.vault.unlock('fixture')
        self.locked=False;self.answer={'approved':False};self.proposals=[]
        def prompt(proposal):self.proposals.append(proposal);return self.answer
        self.store=BrowserStore(self.vault,prompt,lambda:self.locked,identity='synthetic-device')
        self.key=base64.b64encode(b'x'*32).decode()
        self.identifier='test-profile'
        self.store.put_connection(self.identifier,{'Name':'Test Zen','Key':self.key,'Sites':'[]'})
        self.store.authenticate(self.identifier,self.key)
        self.data={'id':self.identifier,'url':'https://example.invalid/login','submitUrl':'https://example.invalid/session','login':'tester','password':'synthetic-only'}
        self.transport.calls.clear()

    def test_no_save_or_update_without_approval(self):
        with self.assertRaises(BrowserError):self.store.save(self.data)
        self.assertNotIn('writeMap',self.transport.calls)
        self.answer={'approved':True};self.store.save(self.data)
        key=next(k for f,k in self.transport.entries if f==PERSONAL_FOLDER)
        before=self.transport.entries[(PERSONAL_FOLDER,key)]
        self.answer={'approved':False}
        with self.assertRaises(BrowserError):self.store.save(dict(self.data,password='changed-test-only',uuid=entry_id(key)))
        self.assertEqual(self.transport.entries[(PERSONAL_FOLDER,key)],before)
        self.assertTrue(all('password' not in p and 'synthetic-only' not in json.dumps(p) for p in self.proposals))

    def test_damaged_pairing_record_does_not_authorize_an_empty_key(self):
        self.store.put_connection(self.identifier,{'Name':'Test Zen','Sites':'[]'})
        with self.assertRaises(BrowserError):self.store.authenticate(self.identifier,'')

    def test_automatic_submission_still_requires_native_approval(self):
        result=self.store.save(dict(self.data,monetAutomatic=True))
        self.assertEqual(result,{'error':'cancelled','monetPrompted':True})
        self.assertNotIn('writeMap',self.transport.calls)
        self.answer={'approved':True}
        self.assertTrue(self.store.save(dict(self.data,monetAutomatic=True))['monetPrompted'])
        key=next(k for f,k in self.transport.entries if f==PERSONAL_FOLDER)
        before=self.transport.entries[(PERSONAL_FOLDER,key)]
        self.answer={'approved':False}
        result=self.store.save(dict(self.data,monetAutomatic=True,password='new-test-only'))
        self.assertEqual(result['error'],'cancelled')
        self.assertEqual(self.transport.entries[(PERSONAL_FOLDER,key)],before)

    def test_approved_save_update_and_identical_retry_use_one_account(self):
        self.answer={'approved':True};self.store.save(self.data);prompts=len(self.proposals)
        self.store.save(self.data);self.assertEqual(len(self.proposals),prompts)
        self.store.save(dict(self.data,password='new-test-only'))
        keys=[k for f,k in self.transport.entries if f==PERSONAL_FOLDER];self.assertEqual(len(keys),1)
        self.assertEqual(self.vault.read(PERSONAL_FOLDER,keys[0])['fields']['Password'],'new-test-only')
        self.assertEqual(self.proposals[-1]['kind'],'update')

    def test_same_site_autofill_and_different_sites_remain_empty(self):
        self.answer={'approved':True};self.store.save(self.data)
        self.answer={'approved':False}
        self.assertEqual(self.store.logins(self.data)[0]['password'],'synthetic-only')
        for site in ('https://other.invalid','https://sub.example.invalid','https://example.invalid:444'):
            self.assertEqual(self.store.logins(dict(self.data,url=site,submitUrl=site)),[])
        with self.assertRaises(BrowserError):self.store.logins(dict(self.data,submitUrl='https://other.invalid'))

    def test_manual_login_requires_site_permission_and_denial_returns_no_secret(self):
        self.vault.add('Manual','tester','synthetic-manual','https://example.invalid','')
        self.assertEqual(self.store.logins(self.data),[])
        self.answer={'approved':True,'remember':True};self.assertEqual(len(self.store.logins(self.data)),1)
        count=len(self.proposals);self.answer={'approved':False}
        self.assertEqual(len(self.store.logins(self.data)),1);self.assertEqual(len(self.proposals),count)

    def test_revocation_and_lock_win_over_inflight_approval(self):
        self.vault.add('Manual','tester','synthetic-manual','https://example.invalid','')
        def revoke(_):
            self.vault.revoke_browser(self.identifier)
            return {'approved':True,'remember':True}
        self.store.prompt=revoke
        with self.assertRaises(BrowserError):self.store.logins(self.data)
        self.locked=True;self.transport.calls.clear()
        with self.assertRaises(BrowserError):self.store.save(self.data)
        self.assertFalse(self.transport.calls)

    def test_update_race_does_not_overwrite_changes_from_desktop(self):
        self.answer={'approved':True};self.store.save(self.data)
        key=next(k for f,k in self.transport.entries if f==PERSONAL_FOLDER)
        def change(_):
            fields=self.vault.read(PERSONAL_FOLDER,key)['fields'];fields['Password']='changed-elsewhere'
            self.transport.entries[(PERSONAL_FOLDER,key)]=(3,pack_map(fields))
            return {'approved':True}
        self.store.prompt=change
        with self.assertRaises(VaultError):self.store.save(dict(self.data,password='late-update'))
        self.assertEqual(self.vault.read(PERSONAL_FOLDER,key)['fields']['Password'],'changed-elsewhere')

    def test_update_cannot_target_another_website_or_app_entry(self):
        other=self.vault.add('Other','tester','other-test-only','https://other.invalid','')
        with self.assertRaises(BrowserError):self.store.save(dict(self.data,uuid=entry_id(other['key'])))
        self.assertNotIn('readPassword',self.transport.calls)
        self.assertEqual(self.proposals,[])

    def test_connection_metadata_never_exposes_identification_keys_in_ui(self):
        rows=self.vault.browser_connections();self.assertEqual(rows[0]['name'],'Test Zen')
        self.assertNotIn('Key',json.dumps(rows));self.assertNotIn(self.key,json.dumps(rows))
        self.assertFalse(any(r['folder']==CONNECTIONS for r in self.vault.list_entries()))
        self.vault.revoke_browser(self.identifier)
        with self.assertRaises(BrowserError):self.store.authenticate(self.identifier,self.key)

    def test_pairing_requires_matching_session_key_and_explicit_approval(self):
        request={'key':self.key,'idKey':base64.b64encode(b'y'*32).decode()}
        with self.assertRaises(BrowserError):self.store.associate(request,self.key)
        self.answer={'approved':True,'name':'Zen test'}
        with self.assertRaises(BrowserError):self.store.associate(request,'wrong-key')
        identifier=self.store.associate(request,self.key)
        self.assertEqual(self.store.connection(identifier)['Name'],'Zen test')

    def test_strict_origin_normalization(self):
        self.assertEqual(origin('HTTPS://EXAMPLE.invalid:443/path?q=x'),'https://example.invalid')
        self.assertEqual(origin('http://[::1]:8765/'),'http://[::1]:8765')
        for url in ('http://example.invalid','javascript:alert(1)','https://example.invalid@evil.invalid','https://example.invalid\\@evil.invalid',
                    'https://example.invalid:bad','https://%65xample.invalid','https://example.invalid\n','https://example.invalid:0'):
            with self.assertRaises(BrowserError,msg=url):origin(url)

    def test_setup_preserves_other_preferences_and_refuses_another_host(self):
        text='user_pref("custom.setting", true);\n'
        updated=configured_user_js(text)
        self.assertEqual(configured_user_js(updated),updated)
        self.assertIn(text,updated)
        self.assertNotIn('marionette',updated);self.assertNotIn('signatures',updated)
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory);host=home/'host';host.write_text('fixture');host.chmod(0o700)
            root=home/'.var/app/app.zen_browser.zen/.zen';(root/'default').mkdir(parents=True)
            (root/'profiles.ini').write_text('[Profile0]\nDefault=1\nIsRelative=1\nPath=default\n')
            files=plan(host,home);self.assertEqual(len(files),2)
            manifest=home/'.mozilla/native-messaging-hosts/org.keepassxc.keepassxc_browser.json'
            manifest.parent.mkdir(parents=True);manifest.write_text('{"path":"/another/manager"}')
            with self.assertRaises(ValueError):plan(host,home)

    def test_failed_browser_permission_change_rolls_back_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            home=Path(directory);host=home/'host';host.write_text('fixture');host.chmod(0o700)
            root=home/'.var/app/app.zen_browser.zen/.zen';profile=root/'default';profile.mkdir(parents=True)
            (root/'profiles.ini').write_text('[Profile0]\nDefault=1\nIsRelative=1\nPath=default\n')
            prefs=profile/'user.js';prefs.write_text('user_pref("fixture", true);\n')
            override=home/'.local/share/flatpak/overrides/app.zen_browser.zen';override.parent.mkdir(parents=True)
            override.write_text('[Context]\nfixture=preserve\n')
            before={p:p.read_bytes() for p in (prefs,override)}
            with patch('browser_setup.importlib.util.find_spec',return_value=object()), patch('browser_setup.subprocess.run',side_effect=OSError()):
                with self.assertRaises(ValueError):apply(host,home)
            for path,data in before.items():self.assertEqual(path.read_bytes(),data)
            self.assertFalse((home/'.mozilla/native-messaging-hosts/org.keepassxc.keepassxc_browser.json').exists())

@unittest.skipUnless(NACL,'PyNaCl required for native browser protocol')
class BrowserProtocol(unittest.TestCase):
    def setUp(self):
        self.backend=FakeWallet();self.vault=Vault(self.backend)
        self.store=BrowserStore(self.vault,lambda _: {'approved':True,'name':'Protocol fixture'},lambda:False,identity='fixture')
        self.protocol=Protocol(self.store);self.client=PrivateKey.generate();self.client_id=b64(b'c'*24)
        nonce=b'n'*24
        response=self.protocol.handle({'action':'change-public-keys','clientID':self.client_id,'nonce':b64(nonce),'publicKey':b64(bytes(self.client.public_key))})
        self.assertEqual(response['nonce'],b64(increment(nonce)))
        self.box=Box(self.client,PublicKey(base64.b64decode(response['publicKey'])))
    def message(self,action,**fields):
        nonce=os.urandom(24);data={'action':action,**fields}
        return {'action':action,'clientID':self.client_id,'nonce':b64(nonce),'message':b64(self.box.encrypt(json.dumps(data).encode(),nonce).ciphertext)}
    def call(self,action,**fields):
        req=self.message(action,**fields);res=self.protocol.handle(req)
        self.assertNotIn('errorCode',res,res)
        self.assertEqual(res['nonce'],b64(increment(base64.b64decode(req['nonce']))))
        value=json.loads(self.box.decrypt(base64.b64decode(res['message']),base64.b64decode(res['nonce'])))
        self.assertEqual(value['success'],'true');return value
    def test_real_encrypted_pair_save_fill_and_update(self):
        self.call('get-databasehash')
        identity=b64(b'i'*32)
        identifier=self.call('associate',key=b64(bytes(self.client.public_key)),idKey=identity)['id']
        self.call('test-associate',id=identifier,key=identity)
        data=dict(id=identifier,url='https://example.invalid',login='tester',password='synthetic-browser')
        self.call('set-login',**data)
        result=self.call('get-logins',id=identifier,url=data['url'],keys=[{'id':identifier,'key':identity}])
        self.assertEqual(result['entries'][0]['password'],data['password'])
        self.call('set-login',**dict(data,password='synthetic-updated',uuid=result['entries'][0]['uuid']))
        self.assertEqual(len([k for f,k in self.backend.entries if f==PERSONAL_FOLDER]),1)
    def test_replay_wrong_client_tampering_and_action_confusion_fail_closed(self):
        req=self.message('get-databasehash');self.assertIn('message',self.protocol.handle(req))
        self.assertEqual(self.protocol.handle(req)['errorCode'],4)
        req=self.message('get-databasehash');req['clientID']=b64(b'z'*24)
        self.assertEqual(self.protocol.handle(req)['errorCode'],10)
        req=self.message('get-databasehash');req['message']=b64(b'bad')
        self.assertEqual(self.protocol.handle(req)['errorCode'],4)
        req=self.message('get-databasehash');req['action']='set-login'
        self.assertEqual(self.protocol.handle(req)['errorCode'],4)
        self.assertFalse(any(c.startswith('write') for c in self.backend.calls))
    def test_unpaired_requests_never_return_credentials(self):
        req=self.message('get-logins',id='unknown',url='https://example.invalid',keys=[])
        self.assertEqual(self.protocol.handle(req)['errorCode'],10)
        self.assertFalse(any(c.startswith('read') for c in self.backend.calls))
    def test_native_framing_limits_truncation_and_roundtrip(self):
        stream=io.BytesIO();write_message(stream,{'action':'test'});stream.seek(0)
        self.assertEqual(read_message(stream),{'action':'test'});self.assertIsNone(read_message(stream))
        for raw in (b'x',struct.pack('@I',1024*1024),struct.pack('@I',4)+b'{}',struct.pack('@I',2)+b'[]'):
            with self.assertRaises(BrowserError):read_message(io.BytesIO(raw))

if __name__=='__main__':unittest.main()
