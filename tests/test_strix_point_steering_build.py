# SPDX-License-Identifier: MIT
"""HOST oracle/coordination checks. Frozen/native rows are NOT-INFERENCE.

No GPU, remote host, original weights or real service is used. Optional native
checks invoke only the synthetic C17 borrowed-row fixture supplied explicitly.
"""
import base64
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec); spec.loader.exec_module(result)
    return result
gate = module('steering_build_gate', ROOT/'tools/strix-point-steering-build-gate.py')
point = module('steering_build_campaign', ROOT/'tools/strix-point-campaign.py')
FROZEN = json.loads((ROOT/'tests/fixtures/steering-build-receipts.json').read_text())
CLIENT = os.environ.get('LIE_STEERING_GATE_NATIVE_CLIENT')


class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.output = self.root/'capture'
        self.output.mkdir()
        self.rows = copy.deepcopy(FROZEN['journal'])
        self.settings = dict(FROZEN['settings'])
        self.exit = 0
        self.restore()
        self.sources, self.pairs = gate.input_pair(self.output, self.settings['max_pairs'])

    def tearDown(self):
        self.tmp.cleanup()

    def restore(self):
        for path in self.output.iterdir():
            if path.is_dir() and not path.is_symlink(): shutil.rmtree(path)
            else: path.unlink()
        for name, data in FROZEN['files'].items():
            (self.output/name).write_bytes(base64.b64decode(data))
        self.write_journal()

    def write_journal(self):
        (self.output/'build.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in self.rows))

    def review(self, synthetic=True):
        return gate.validate(self.output, self.settings, self.sources, self.pairs, self.exit,
                             FROZEN['identity']['build_id'], 'synthetic-only', ':ok:',
                             expected_synthetic=synthetic)

    def edit(self, event, key, value):
        next(row for row in self.rows if row['event'] == event)[key] = value
        self.write_journal()

    def test_native_frozen_analytic_rows_reconstruct_both_banks(self):
        self.assertEqual(FROZEN['classification'], 'SYNTHETIC_C17_BORROWED_ROW_FIXTURE_NOT_INFERENCE')
        result = self.review()
        self.assertEqual(result['classification'], 'SYNTHETIC_HOST_ORACLE_NOT_INFERENCE')
        self.assertEqual(result['captured_rows'], 16)
        self.assertFalse(result['model_generation_or_quality_tested'])
        for name, bank in result['banks'].items():
            self.assertEqual(struct.unpack('<4f', (self.output/name).read_bytes()),
                             struct.unpack('<4f', struct.pack('<4f', .6, .8, -.8, .6)))
            self.assertEqual(bank['independent_max_absolute_error'], 0)

    def test_fixture_never_qualifies_original_capture(self):
        with self.assertRaises(RuntimeError): self.review(False)

    def test_actual_nonzero_exit_refuses_complete_files(self):
        self.exit = 1
        with self.assertRaises(RuntimeError): self.review()

    def test_rows_before_failed_full_prefill_do_not_qualify(self):
        self.edit('prompt_end', 'prefill_status', 11)
        with self.assertRaises(RuntimeError): self.review()

    def test_incomplete_or_bool_completion_refuses(self):
        for event, key, value in (('prompt_end','completed_prefix_tokens',4),
                                  ('prompt_end','accepted',False), ('complete','exit_code',False),
                                  ('pair_accepted','accepted_pairs',True)):
            with self.subTest(event=event, key=key):
                self.rows = copy.deepcopy(FROZEN['journal']); self.restore(); self.edit(event,key,value)
                with self.assertRaises(RuntimeError): self.review()

    def test_duplicate_missing_refused_or_wrong_position_rows(self):
        for key, value in (('layer',99), ('token_position',0), ('capture_status',1),
                           ('offset_bytes',4), ('branches',1), ('values',True)):
            with self.subTest(key=key):
                self.rows = copy.deepcopy(FROZEN['journal']); self.restore(); self.edit('activation_row',key,value)
                with self.assertRaises(RuntimeError): self.review()
        self.rows = copy.deepcopy(FROZEN['journal']); self.restore()
        at = next(i for i,row in enumerate(self.rows) if row['event']=='activation_row')
        self.rows.insert(at+1, copy.deepcopy(self.rows[at])); self.write_journal()
        with self.assertRaises(RuntimeError): self.review()
        self.rows = copy.deepcopy(FROZEN['journal']); self.rows.pop(at); self.write_journal()
        with self.assertRaises(RuntimeError): self.review()

    def test_typed_physical_ids_and_input_controls(self):
        for event,key,value in (('prompt_begin','token_ids',[True]*5), ('prompt_begin','physical_tokens',True),
                               ('identity','context',True), ('identity','build_id','unbound'),
                               ('identity','source_pin','different'), ('geometry','layers',True)):
            with self.subTest(event=event,key=key):
                self.rows = copy.deepcopy(FROZEN['journal']); self.restore(); self.edit(event,key,value)
                with self.assertRaises(RuntimeError): self.review()

    def test_raw_nan_truncation_and_trailing_bytes_refuse(self):
        original = (self.output/'activations.f32le').read_bytes()
        for data in (struct.pack('<f',float('nan'))+original[4:], original[:-4], original+b'\0'*4):
            with self.subTest(bytes=len(data)):
                self.rows = copy.deepcopy(FROZEN['journal']); self.restore()
                (self.output/'activations.f32le').write_bytes(data)
                self.edit('raw_complete','sha256',hashlib.sha256(data).hexdigest())
                with self.assertRaises(RuntimeError): self.review()

    def test_self_consistent_forged_unit_bank_refuses_independent_oracle(self):
        data = struct.pack('<4f', .8, .6, -.6, .8)
        (self.output/'direction.ffn.f32').write_bytes(data)
        self.edit('bank','sha256',hashlib.sha256(data).hexdigest())
        with self.assertRaisesRegex(RuntimeError,'independent raw-row direction'): self.review()

    def test_bank_nonfinite_and_wrong_payload_size_refuse(self):
        for data in (struct.pack('<4f',float('inf'),.8,-.8,.6), b'\0'*20):
            with self.subTest(bytes=len(data)):
                self.rows = copy.deepcopy(FROZEN['journal']); self.restore()
                (self.output/'direction.ffn.f32').write_bytes(data)
                self.edit('bank','sha256',hashlib.sha256(data).hexdigest())
                with self.assertRaises(RuntimeError): self.review()

    def test_duplicate_json_keys_missing_terminal_and_extra_event_refuse(self):
        raw = (self.output/'build.jsonl').read_text()
        for data in (raw.replace('"event": "identity"','"event": "identity", "event": "identity"',1),
                     '\n'.join(raw.splitlines()[:-1])+'\n', raw+'{"event":"predictor_row"}\n', raw[:-1]):
            (self.output/'build.jsonl').write_text(data)
            with self.assertRaises(RuntimeError): self.review()

    def test_partial_file_and_changed_source_copies_refuse(self):
        (self.output/'direction.ffn.f32.partial').write_bytes(b'partial')
        with self.assertRaises(RuntimeError): self.review()
        (self.output/'direction.ffn.f32.partial').unlink()
        (self.output/'target-prompts.txt').write_bytes(b'Tchanged\nTbbb\n')
        with self.assertRaises(RuntimeError): self.review()

    def test_regular_file_boundary_never_blocks_fifo_or_follows_symlink(self):
        target = self.output/'activations.f32le'; target.unlink()
        os.mkfifo(target)
        with self.assertRaises(RuntimeError): self.review()
        target.unlink(); target.symlink_to(self.output/'direction.ffn.f32')
        with self.assertRaises(RuntimeError): self.review()

    def test_settings_and_input_limits_admit_before_model_work(self):
        for key,value in (('context',True), ('components',[]), ('rope',None),
                          ('prefill_chunk',33), ('max_pairs',129), ('timeout_seconds',0),
                          ('max_output_bytes',2**30)):
            with self.subTest(key=key):
                selected = dict(self.settings); selected[key]=value
                with self.assertRaises(ValueError): gate.validate_settings(selected)
        for data in (b'\n', b'T\0\n', b'\xff\n', b'T\n', b'T'*65537+b'\n'):
            (self.output/'target-prompts.txt').write_bytes(data)
            with self.assertRaises((RuntimeError,UnicodeDecodeError)): gate.input_pair(self.output,2)

    def test_streamed_raw_replacement_refuses_and_releases_descriptor(self):
        previous = gate.RawRows.values
        descriptors = []

        def replace_after_read(raw, offset, count):
            values = previous(raw, offset, count)
            if not descriptors:
                descriptors.append(raw.fd)
                saved = self.root/'retained-original-raw'
                raw.path.rename(saved)
                shutil.copyfile(saved, raw.path)
            return values

        with patch.object(gate.RawRows, 'values', replace_after_read):
            with self.assertRaisesRegex(RuntimeError, 'changed during review'):
                self.review()
        with self.assertRaises(OSError):
            os.fstat(descriptors[0])

    def test_raw_row_reads_are_bounded_and_posthash_truncation_refuses(self):
        with patch.object(gate.os, 'pread', wraps=os.pread) as read:
            result = self.review()
        self.assertEqual(result['captured_rows'], 16)
        self.assertTrue(read.call_args_list)
        self.assertTrue(all(0 < call.args[1] <= gate.RawRows.BLOCK_BYTES for call in read.call_args_list))
        path = self.output/'activations.f32le'
        descriptor = None
        with self.assertRaisesRegex(RuntimeError, 'changed during review'):
            with gate.RawRows(path, self.settings['max_output_bytes']) as raw:
                descriptor = raw.fd
                path.write_bytes(b'\0' * 4)
                raw.values(4, 1)
        with self.assertRaises(OSError):
            os.fstat(descriptor)

    def campaign(self):
        work = self.root/'campaign'; work.mkdir()
        (work/'manifest.json').write_text('{}')
        helper = work/'steering-build-gate.py'; shutil.copyfile(ROOT/'tools/strix-point-steering-build-gate.py',helper)
        for name in ('target-prompts.txt','contrast-prompts.txt'):
            shutil.copyfile(self.output/name,work/name)
        manifest = {'authorization':'SYNTHETIC HOST FIXTURE; no remote or service grant',
                    'bench_profile':'modern-steering-build','stack':'rocm10-fedora43','transport':'distrobox',
                    'runtime_build_id':FROZEN['identity']['build_id'],'runtime_source_pin':'synthetic-only',
                    'artifacts':{'runtime/bin/lie-steering-build':'mocked'},'steering_build':self.settings,
                    'steering_build_inputs':self.sources,'steering_build_gate_sha256':hashlib.sha256(helper.read_bytes()).hexdigest(),
                    'model_plan':{'files':[{'name':'model.gguf'}]},'bundle':str(self.root/'bundle')}
        return point.Campaign(work,manifest)

    def test_campaign_route_does_not_fall_back_to_generic_bench(self):
        c = self.campaign()
        with patch.object(c,'modern_steering_build') as route:
            c.bench(); route.assert_called_once_with()

    def test_campaign_refuses_predictor_helper_and_dataset_drift_before_model(self):
        for change in ('predictor','helper','dataset','settings','existing'):
            with self.subTest(change=change):
                c = self.campaign()
                if change=='predictor': c.m['predictor_plan']={}
                if change=='helper': c.m['steering_build_gate_sha256']='0'*64
                if change=='dataset': (c.root/'target-prompts.txt').write_bytes(b'Tnew\nTbbb\n')
                if change=='settings': c.m['steering_build']['timeout_seconds']=0
                if change=='existing': (c.root/'steering-build').mkdir()
                with patch.object(point,'BASE',self.root), patch.object(c,'verified_model') as model:
                    with self.assertRaises(ValueError): c.modern_steering_build()
                    model.assert_not_called()
                shutil.rmtree(c.root)
                self.settings = dict(FROZEN['settings'])

    def test_campaign_direct_native_command_and_model_check_after_success_or_failure(self):
        for failed in (False, True):
            with self.subTest(failed=failed):
                c = self.campaign()
                rows = [{'classification':'SYNTHETIC_MODEL_STAT_FIXTURE'}]
                reviewer = Mock(return_value={'state':'PASSED','classification':'SYNTHETIC_MOCKED_COORDINATION_NOT_INFERENCE'})
                imported = SimpleNamespace(validate_settings=gate.validate_settings, input_pair=gate.input_pair, validate=reviewer)
                spec = SimpleNamespace(loader=SimpleNamespace(exec_module=lambda _module:None))
                def child(command, bundle, timeout, model):
                    self.assertEqual(command[0],'/bundle/runtime/bin/lie-steering-build')
                    self.assertEqual(command[command.index('--model')+1],'/model/model.gguf')
                    self.assertNotIn('--timeout-seconds',command)
                    self.assertEqual(timeout,self.settings['timeout_seconds'])
                    output = c.root/'steering-build'; shutil.copytree(self.output,output)
                    c.r['child_exit_code'] = 1 if failed else 0
                    if failed: raise RuntimeError('Synthetic native process failure')
                with patch.object(point,'BASE',self.root), patch.object(c,'verified_model',return_value=(self.root/'model',rows)), \
                     patch.object(c,'run_container',side_effect=child) as run, patch.object(c,'check_model_after') as after, \
                     patch.object(point.importlib.util,'spec_from_file_location',return_value=spec), \
                     patch.object(point.importlib.util,'module_from_spec',return_value=imported):
                    if failed:
                        with self.assertRaisesRegex(RuntimeError,'Synthetic native process failure'): c.modern_steering_build()
                        reviewer.assert_not_called()
                        self.assertNotIn('steering_build_result',c.r)
                    else:
                        c.modern_steering_build()
                        reviewer.assert_called_once()
                        self.assertEqual(reviewer.call_args.args[4],0)
                        self.assertEqual(c.r['steering_build_result']['classification'],'SYNTHETIC_MOCKED_COORDINATION_NOT_INFERENCE')
                    after.assert_called_once_with(rows)
                    run.assert_called_once()
                    self.assertIn('journal_sha256',c.r['steering_build_partial'])
                shutil.rmtree(c.root)


@unittest.skipUnless(CLIENT, 'Explicit synthetic C17 native client not supplied')
class NativeTests(unittest.TestCase):
    def test_one_hundred_native_pairs_use_the_same_independent_oracle(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root/'target-prompts.txt').write_bytes(b'Texample\n' * 100)
            (root/'contrast-prompts.txt').write_bytes(b'Cexample\n' * 100)
            settings = dict(FROZEN['settings'], max_pairs=100, max_output_bytes=2**20)
            argv = [CLIENT, '--model', ':ok:', '--target-prompts', str(root/'target-prompts.txt'),
                    '--contrast-prompts', str(root/'contrast-prompts.txt'), '--output-dir', str(root/'output')]
            for key, value in settings.items():
                if key != 'timeout_seconds':
                    argv.extend(('--' + key.replace('_', '-'), str(value)))
            process = subprocess.run(argv, capture_output=True, text=True, timeout=30)
            self.assertEqual(process.returncode, 0, process.stderr)
            sources, pairs = gate.input_pair(root, 100)
            result = gate.validate(root/'output', settings, sources, pairs, process.returncode,
                                   os.environ['LIE_STEERING_GATE_NATIVE_BUILD_ID'], 'synthetic-only',
                                   ':ok:', expected_synthetic=True)
            self.assertEqual(result['pairs'], 100)
            self.assertEqual(result['captured_rows'], 800)
            self.assertFalse(result['model_generation_or_quality_tested'])
            for name, bank in result['banks'].items():
                self.assertEqual(struct.unpack('<4f', (root/'output'/name).read_bytes()),
                                 struct.unpack('<4f', struct.pack('<4f', .6, .8, -.8, .6)))
                self.assertEqual(bank['independent_max_absolute_error'], 0)

    def test_actual_native_fixture_raw_chat_components_and_one_token_tails(self):
        for format_,component,chunk in (('raw','ffn',2), ('chat','attention',2), ('chat','both',1)):
            with self.subTest(format=format_,component=component), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                for name in ('target-prompts.txt','contrast-prompts.txt'):
                    (root/name).write_bytes(base64.b64decode(FROZEN['files'][name]))
                settings = dict(FROZEN['settings'],prompt_format=format_,components=component,prefill_chunk=chunk)
                argv = [CLIENT,'--model',':ok:','--target-prompts',str(root/'target-prompts.txt'),
                        '--contrast-prompts',str(root/'contrast-prompts.txt'),'--output-dir',str(root/'output')]
                for key,value in settings.items():
                    if key!='timeout_seconds': argv.extend(('--'+key.replace('_','-'),str(value)))
                process = subprocess.run(argv,capture_output=True,text=True,timeout=30)
                self.assertEqual(process.returncode,0,process.stderr)
                sources,pairs = gate.input_pair(root,2)
                result = gate.validate(root/'output',settings,sources,pairs,process.returncode,
                                       os.environ['LIE_STEERING_GATE_NATIVE_BUILD_ID'],'synthetic-only',':ok:',expected_synthetic=True)
                self.assertTrue(any(row['one_token_tail'] for row in result['prompts']))
                self.assertEqual(set(result['banks']),{gate.BANKS[c] for c in (1,2) if c&gate.COMPONENTS[component]})


if __name__ == '__main__': unittest.main()
