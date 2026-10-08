#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Admission validation rejects missing/stale/mismatched scope before SSH."""
import hashlib,importlib.util,json,subprocess,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('phase',ROOT/'tools/q2-down-register-palette-phase.py')
phase=importlib.util.module_from_spec(spec);spec.loader.exec_module(phase)
class AdmissionTest(unittest.TestCase):
 def test_missing_admission(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);plan=root/'plan.json';plan.write_text('{}')
   with patch.object(phase.subprocess,'run',side_effect=AssertionError('No SSH')) as call:
    with self.assertRaises(FileNotFoundError):phase.validate(plan,root/'missing.json')
    call.assert_not_called()
 def test_failed_remote_admission_never_launches_component(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   plan=dict(components=[dict(label='fresh-component',mode='component',variant='down-register-palette')],arms=[])
   args=['phase','component','--plan',str(root/'plan.json'),'--admission',str(root/'admission.json')]
   with patch.object(phase,'ROOT',root),patch.object(sys,'argv',args),\
        patch.object(phase,'validate',return_value=(plan,{},'digest')),\
        patch.object(phase.subprocess,'run',return_value=subprocess.CompletedProcess(['ssh'],255)) as call:
    self.assertEqual(phase.main(),255)
    self.assertEqual(call.call_count,1)
    self.assertEqual(call.call_args.args[0][0],'ssh')
 def test_existing_cohort_is_preserved_before_ssh(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);target=root/'evidence'/'failed-component';target.mkdir(parents=True)
   marker=target/'transport.json';marker.write_text('preserve failure')
   plan=dict(components=[dict(label='failed-component')],arms=[])
   args=['phase','component','--plan',str(root/'plan.json'),'--admission',str(root/'admission.json')]
   with patch.object(phase,'ROOT',root),patch.object(sys,'argv',args),\
        patch.object(phase,'validate',return_value=(plan,{},'digest')),\
        patch.object(phase.subprocess,'run',side_effect=AssertionError('No SSH')) as call:
    with self.assertRaisesRegex(ValueError,'Cohort exists'):phase.main()
    call.assert_not_called();self.assertEqual(marker.read_text(),'preserve failure')
 def test_successful_admission_then_one_component_launch(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td)
   plan=dict(components=[dict(label='fresh-component',mode='component',variant='down-register-palette')],arms=[])
   args=['phase','component','--plan',str(root/'plan.json'),'--admission',str(root/'admission.json')]
   with patch.object(phase,'ROOT',root),patch.object(sys,'argv',args),\
        patch.object(phase,'validate',return_value=(plan,{},'digest')),\
        patch.object(phase.subprocess,'run',side_effect=[subprocess.CompletedProcess(['ssh'],0),
            subprocess.CompletedProcess(['remote'],1)]) as call:
    self.assertEqual(phase.main(),1);self.assertEqual(call.call_count,2)
    self.assertEqual(call.call_args_list[0].args[0][0],'ssh')
    self.assertEqual(call.call_args_list[1].args[0],[sys.executable,str(root/'tools/q2-remote.py'),
        'component','fresh-component','--source-variant','down-register-palette'])
 def test_valid_and_changed_scope(self):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);helper=root/'helper';helper.write_text('bound')
   receipt=dict(state='Q2_DOWN_REGISTER_PALETTE_WINDOW_ADMITTED',gpu_reserved=True,owner='synapse-lie-q2',
    previous_release_sha256='previous',planned_labels=['new-component','new-model'])
   plan=dict(previous_release_sha256='previous',components=[dict(label='new-component')],arms=[dict(label='new-model')],
    window_helper='helper',window_helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(),fixtures={},manifests={})
   pp=root/'plan.json';rp=root/'admission.json';pp.write_text(json.dumps(plan));rp.write_text(json.dumps(receipt))
   with patch.object(phase,'ROOT',root),patch.object(phase.subprocess,'run',side_effect=AssertionError('No SSH')) as call:
    self.assertEqual(phase.validate(pp,rp)[:2],(plan,receipt));call.assert_not_called()
    for change in (dict(state='Q2_DOWN_REGISTER_PALETTE_WINDOW_RELEASED'),dict(gpu_reserved=False),
                   dict(owner='foreign'),dict(previous_release_sha256='changed'),dict(planned_labels=['wrong'])):
     rp.write_text(json.dumps({**receipt,**change}))
     with self.assertRaises(ValueError):phase.validate(pp,rp)
    rp.write_text(json.dumps(receipt));helper.write_text('changed')
    with self.assertRaises(ValueError):phase.validate(pp,rp)
    call.assert_not_called()
if __name__=='__main__':unittest.main()
