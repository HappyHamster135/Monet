"""Local usage accounting: no duplicate snapshots, inherited tokens or prompt text."""
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'linux/share/monet/utilities'))
import agent_history as history


class History(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory(); self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.db = history.database(self.root/'cache/usage.sqlite'); self.addCleanup(self.db.close)
        self.now = datetime.now().replace(hour=12,minute=0,second=0,microsecond=0)
        self.path = self.root/'session.jsonl'

    def token(self, input=100, cached=80, output=10, at=None, **info):
        return dict(type='event_msg', timestamp=(at or self.now).isoformat(), payload=dict(type='token_count', info=dict(
            total_token_usage=dict(input_tokens=input,cached_input_tokens=cached,output_tokens=output,reasoning_output_tokens=4), **info)))

    def write(self, rows, mode='w'):
        with self.path.open(mode) as f:
            for row in rows: f.write(json.dumps(row)+'\n')

    def index(self, provider='codex'):
        return history.index_file(self.db,self.path,provider,time.monotonic()+5)

    def result(self):
        return history.overview(self.db,self.now.timestamp()+60)

    def test_cumulative_deltas_duplicates_model_changes_and_no_prompt_storage(self):
        self.write([dict(type='session_meta',payload=dict(id='one',base_instructions='PRIVATE PROMPT')),
                    dict(type='turn_context',payload=dict(model='gpt-6.2-astra',instructions='PRIVATE PROMPT')),
                    self.token(), self.token(),
                    dict(type='response_item',payload=dict(text='PRIVATE PROMPT')),
                    dict(type='turn_context',payload=dict(model='gpt-6.1-sol')),
                    self.token(150,110,20)])
        self.index(); data=self.result()['periods']['today']
        self.assertEqual((data['total']['input'],data['total']['output'],data['total']['cached'],data['total']['requests']),(150,20,110,2))
        self.assertEqual([r['name'] for r in data['models']],['gpt-6.1-sol','gpt-6.2-astra'])
        self.assertAlmostEqual(data['total']['cost'],(20*8+80*.4+10*40+20*2+30*.1+10*10)/1e6)
        self.assertNotIn('PRIVATE', ''.join(self.db.iterdump()))
        with patch.object(history,'consume',side_effect=AssertionError('reread unchanged log')):
            self.index()
        duplicate=self.root/'archived.jsonl';duplicate.write_bytes(self.path.read_bytes())
        history.index_file(self.db,duplicate,'codex',time.monotonic()+5)
        self.assertEqual(self.result()['periods']['today']['total'],data['total'])

    def test_partial_append_rotation_truncation_and_deleted_source(self):
        self.write([dict(type='turn_context',payload=dict(model='gpt-6-astra')),self.token()])
        with self.path.open('a') as f:f.write(json.dumps(self.token(150,120,15))[:-1])
        self.assertTrue(self.index()[1]); self.assertEqual(self.result()['periods']['today']['total']['input'],100)
        with self.path.open('a') as f:f.write('}\n')
        self.assertFalse(self.index()[1]); self.assertEqual(self.result()['periods']['today']['total']['input'],150)
        replacement=self.path.with_suffix('.new');replacement.write_text(json.dumps(self.token(30,10,3))+'\n');replacement.replace(self.path)
        self.index();self.assertEqual(self.result()['periods']['today']['total']['input'],30)
        self.write([self.token(2,0,1)]);self.index();self.assertEqual(self.result()['periods']['today']['total']['input'],2)
        self.path.unlink();history.scan(self.db,[('codex',self.root)])
        self.assertEqual(self.result()['periods']['today']['total']['tokens'],0)

    def test_fork_inheritance_is_not_charged_again_and_unknown_model_is_unpriced(self):
        self.write([dict(type='session_meta',payload=dict(id='fork',history_base=dict(thread_id='parent'))),
                    dict(type='turn_context',payload=dict(model='unpublished-model')),
                    self.token(1000,800,100,last_token_usage=dict(input_tokens=100,cached_input_tokens=80,output_tokens=10)),
                    self.token(1050,830,105)])
        self.index();total=self.result()['periods']['today']['total']
        self.assertEqual((total['input'],total['output'],total['unpriced']),(150,15,2))
        self.assertEqual(total['cost'],0)

    def test_claude_stream_fragments_merge_cache_creation_without_double_counting(self):
        def message(usage):
            return dict(type='assistant',timestamp=self.now.isoformat(),sessionId='session',message=dict(
                id='message',model='claude-sonnet-4-6',content=[{'text':'PRIVATE PROMPT'}],usage=usage,stop_reason='end_turn'))
        self.write([message(dict(input_tokens=10,output_tokens=1,cache_read_input_tokens=20,
                                cache_creation_input_tokens=10,cache_creation=dict(ephemeral_1h_input_tokens=5))),
                    message(dict(output_tokens=3))])
        self.index('claude');total=self.result()['periods']['today']['total']
        self.assertEqual((total['input'],total['output'],total['requests'],total['write'],total['long_write']),(40,3,1,5,5))
        self.assertAlmostEqual(total['cost'],(10*3+20*.3+5*3.75+5*6+3*15)/1e6)
        self.assertNotIn('PRIVATE', ''.join(self.db.iterdump()))

    def test_periods_use_local_days_and_reasoning_is_not_added_to_output_twice(self):
        self.write([dict(type='turn_context',payload=dict(model='gpt-6-astra')),
                    self.token(10,0,2,at=self.now-timedelta(days=20)),self.token(30,0,5,at=self.now-timedelta(days=3)),self.token(60,0,9)])
        self.index();p=self.result()['periods']
        self.assertEqual([p[k]['total']['tokens'] for k in ('today','week','month')],[34,57,69])
        self.assertEqual([p[k]['total']['activeDays'] for k in ('today','week','month')],[1,2,3])
        self.assertEqual([len(p[k]['buckets']) for k in ('today','week','month')],[24,7,30])

    def test_nonregular_and_symlink_sources_do_not_block_or_get_indexed(self):
        os.mkfifo(self.path)
        self.index();self.assertEqual(self.db.execute('SELECT count(*) FROM files').fetchone()[0],0)
        self.path.unlink();self.path.symlink_to('/dev/zero')
        history.scan(self.db,[('codex',self.root)])
        self.assertEqual(self.db.execute('SELECT count(*) FROM files').fetchone()[0],0)

    def test_long_context_standard_price_and_dated_model_alias(self):
        usage=dict(input=300000,cached=250000,write=0,long_write=0,output=1000,reasoning=100)
        cost,saved=history.estimate('gpt-6.2-astra-2026-11-19',usage)
        self.assertAlmostEqual(cost,(50000*16+250000*.8+1000*60)/1e6)
        self.assertAlmostEqual(saved,250000*(16-.8)/1e6)
