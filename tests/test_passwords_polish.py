"""Synthetic account exports only; no real browser profiles or keyrings."""
import csv
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tests.test_native_passwords import FakeWallet, Vault, VaultError, PERSONAL_FOLDER
from login_import import read_csv

class PasswordPolish(unittest.TestCase):
    def setUp(self):
        self.backend = FakeWallet(); self.vault = Vault(self.backend); self.vault.unlock('fixture')
        self.directory = tempfile.TemporaryDirectory(); self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name)/'synthetic.csv'

    def export(self, rows, headers=('url','username','password','name','note')):
        with self.path.open('w', newline='') as file:
            writer=csv.writer(file);writer.writerow(headers);writer.writerows(rows)
        return str(self.path)

    def test_duplicate_folders_and_keys_display_once_without_secret_reads(self):
        original = self.backend.call
        def duplicate(method, *args):
            result = original(method, *args)
            return result*2 if method in ('folderList', 'entryList') else result
        self.backend.call = duplicate
        self.assertEqual(len(self.vault.list_entries()), 4)
        self.assertFalse(any(c.startswith('read') for c in self.backend.calls))

    def test_internal_keys_are_explained_without_reading_their_values(self):
        for folder,key in [('xdg-desktop-portal','app.zen_browser.zen'), ('Chromium Keys','Chromium Safe Storage')]:
            self.backend.entries[(folder,key)] = (2,'synthetic-internal-key')
            entry=self.vault.select(folder,key)
            self.assertTrue(entry['internal']);self.assertEqual(entry['fields'],{})
            self.assertFalse(entry['editable'])
            with self.assertRaises(VaultError): self.vault.delete()
        self.assertFalse(any(c.startswith('read') for c in self.backend.calls))

    def test_csv_import_retries_duplicates_and_changed_passwords_preserve_original(self):
        self.export([['https://example.invalid','tester','synthetic','Example','line1\nline2']])
        self.assertEqual(self.vault.prepare_import(self.path)['count'],1)
        self.assertEqual(self.vault.import_logins()['added'],1)
        self.vault.prepare_import(self.path)
        result=self.vault.import_logins();self.assertEqual(result['added'],0);self.assertEqual(result['skipped'],1)
        self.export([['https://example.invalid','tester','changed-synthetic','Example','line1\nline2']])
        self.vault.prepare_import(self.path);self.assertEqual(self.vault.import_logins()['added'],1)
        self.assertEqual(len([f for f,k in self.backend.entries if f==PERSONAL_FOLDER]),2)

    def test_empty_and_duplicate_rows_are_not_fake_passwords(self):
        row=['https://example.invalid','tester','synthetic','','']
        self.export([row,row,['https://empty.invalid','tester','','','']])
        records,skipped=read_csv(self.path);self.assertEqual(len(records),1);self.assertEqual(skipped,2)

    def test_firefox_bom_quoted_csv_and_invalid_headers(self):
        self.path.write_text('\ufeff"url","username","password"\n"https://example.invalid","a,b","test-only"\n')
        self.assertEqual(read_csv(self.path)[0][0]['username'],'a,b')
        for text in ('url,username\nx,y\n','url,username,password,password\nx,y,z,z\n','url,username,password\nx,y,z,extra\n'):
            self.path.write_text(text)
            with self.assertRaises(VaultError):read_csv(self.path)
        self.assertNotIn('writeMap', self.backend.calls)

    def test_import_bounds_and_cancel_do_not_write(self):
        self.export([['https://example.invalid','tester','test-only','','']])
        with patch('login_import.MAX_FILE',8):
            with self.assertRaises(VaultError):read_csv(self.path)
        self.vault.prepare_import(self.path);self.vault.import_cancelled.set()
        self.assertTrue(self.vault.import_logins()['incomplete']);self.assertNotIn('writeMap',self.backend.calls)
        self.vault.prepare_import(self.path);self.vault.forget();self.assertEqual(self.vault.pending_import,[])

    def test_partial_failure_reports_verified_writes_and_can_retry(self):
        self.export([['https://one.invalid','','test-only','',''],['https://two.invalid','','test-only','','']])
        self.vault.prepare_import(self.path)
        original=self.backend.call
        def fail_second(method,*args):
            if method=='writeMap' and args[2].startswith('two.'):return -1
            return original(method,*args)
        self.backend.call=fail_second
        result=self.vault.import_logins();self.assertTrue(result['incomplete']);self.assertEqual(result['added'],1)
        self.backend.call=original
        self.vault.prepare_import(self.path);result=self.vault.import_logins()
        self.assertEqual(result['added'],1);self.assertEqual(result['skipped'],1)

if __name__=='__main__':unittest.main()
