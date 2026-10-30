"""Display changes are per-output, acknowledged, and initial defaults never replay."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from tests.test_look import quick_helper, ROOT


def output(name='eDP-1', scale=2, width=3840, height=2400, mm=(344,215)):
    return dict(name=name, enabled=True, scale=scale, size=dict(width=width,height=height),
                sizeMM=dict(width=mm[0],height=mm[1]))


class DisplayScaling(unittest.TestCase):
    def test_density_and_scale_are_independent_and_bad_metadata_is_ignored(self):
        q=quick_helper()
        outputs=[output(),output('DP-1',1.25,1920,1080,(530,300)),output('unknown',1,1920,1080,(0,0)),
                 dict(enabled=True,name='bad;exec',scale=2),dict(enabled=True,name='broken',scale='nan')]
        with patch.object(q,'run',return_value=json.dumps({'outputs':outputs})):
            displays=q.display_sizes()
        self.assertEqual([d['scale'] for d in displays],[200,125,100])
        self.assertEqual([d['highDensity'] for d in displays],[True,False,False])
        self.assertFalse(displays[-1]['densityKnown'])

    def test_only_selected_screen_changes_and_result_is_read_back(self):
        q=quick_helper()
        before=[output(),output('DP-1',1,1920,1080,(530,300))]
        after=[output(),output('DP-1',1.25,1920,1080,(530,300))]
        with patch.object(q,'run',side_effect=[json.dumps({'outputs':before}),'',json.dumps({'outputs':after})]) as run:
            result=q.set_scale(125,'DP-1')
        self.assertTrue(result['ok'])
        self.assertEqual(run.call_args_list[1].args,('kscreen-doctor','output.DP-1.scale.1.25'))
        self.assertEqual(result['displays'][0]['scale'],200)

    def test_failure_stale_result_and_removed_screen_cannot_report_success(self):
        q=quick_helper(); before=[dict(name='eDP-1',scale=200)]
        for code,after in ((None,before),('',before),('',[])):
            with self.subTest(code=code,after=after), patch.object(q,'display_sizes',side_effect=[before,after]), \
                    patch.object(q,'run',return_value=code):
                result=q.set_scale(125,'eDP-1')
                self.assertFalse(result['ok']);self.assertTrue(result['error'])

    def test_unknown_monitor_and_ambiguous_legacy_request_do_not_apply(self):
        q=quick_helper()
        with patch.object(q,'display_sizes',return_value=[dict(name='eDP-1',scale=200),dict(name='DP-1',scale=100)]), \
                patch.object(q,'run') as run:
            self.assertFalse(q.set_scale(125)['ok'])
            self.assertFalse(q.set_scale(125,'DP-1;reboot')['ok'])
            self.assertFalse(q.set_scale(130,'eDP-1')['ok'])
            run.assert_not_called()

    def test_new_account_125_default_respects_dense_small_custom_and_unknown_screens(self):
        q=quick_helper()
        with tempfile.TemporaryDirectory() as tmp, patch.object(q,'CONFIG',Path(tmp)):
            pending=Path(tmp)/'monet/display-defaults-pending';pending.parent.mkdir();pending.write_text('Monet display defaults v1\n')
            base=dict(name='normal',scale=100,width=1920,height=1080,densityKnown=True,highDensity=False)
            screens=[base,dict(base,name='dense',highDensity=True),dict(base,name='chosen',scale=150),
                     dict(base,name='small',height=768),dict(base,name='unknown',densityKnown=False)]
            with patch.object(q,'display_sizes',return_value=screens), patch.object(q,'set_scale',return_value={'ok':True}) as change:
                self.assertEqual(q.initial_display_sizes(),{'ok':True,'changed':['normal']})
                change.assert_called_once_with(125,'normal')
                self.assertFalse(pending.exists())
                q.initial_display_sizes();change.assert_called_once()

    def test_existing_accounts_untouched_and_no_display_keeps_first_login_pending(self):
        q=quick_helper()
        with tempfile.TemporaryDirectory() as tmp, patch.object(q,'CONFIG',Path(tmp)), \
                patch.object(q,'display_sizes',return_value=[]) as read, patch.object(q,'set_scale') as change:
            self.assertTrue(q.initial_display_sizes()['ok']);read.assert_not_called()
            pending=Path(tmp)/'monet/display-defaults-pending';pending.parent.mkdir();pending.touch()
            self.assertFalse(q.initial_display_sizes()['ok']);self.assertTrue(pending.exists());change.assert_not_called()
        install=(ROOT/'linux/install.sh').read_text()
        self.assertIn('/etc/skel/.config/monet/display-defaults-pending',install)
        self.assertIn('"$LIBEXECDIR/monet-quick" display-defaults',(ROOT/'linux/libexec/monet-session').read_text())
