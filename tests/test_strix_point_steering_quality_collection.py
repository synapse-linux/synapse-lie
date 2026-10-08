# SPDX-License-Identifier: MIT
"""HOST transfer/ownership fixtures only; no model, GPU or remote operation."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'steering_response_collection', ROOT/'tools/strix-point-steering-quality-collect.py')
collect = importlib.util.module_from_spec(spec)
spec.loader.exec_module(collect)


class Tests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.helpers = (
            'strix-point-steering-quality-profile.py', 'strix-point-steering-quality-run.py',
            'strix-point-steering-quality-gate.py', 'strix-point-steering-build-gate.py',
            'strix-point-http-recall-gate.py')
        for name in (*self.helpers, 'runner.py', 'corpus.json', 'steering-training-receipt.json',
                     'steering-quality-settings.json', 'direction.ffn.f32', 'telemetry.jsonl',
                     'steering-quality-result.json', 'steering-quality-review.json'):
            (self.root/name).write_bytes(b'HOST SYNTHETIC collection bytes, not original inference\n')
        self.manifest = {
            'action': 'bench', 'bench_profile': 'modern-steering-quality',
            'runner_sha256': self.identity('runner.py')['sha256'],
            'steering_quality_settings_sha256': self.identity('steering-quality-settings.json')['sha256'],
            'steering_quality': {'bank_sha256': self.identity('direction.ffn.f32')['sha256']},
            'steering_quality_helpers': {name: self.identity(name)['sha256'] for name in self.helpers},
            'steering_quality_corpus': self.identity('corpus.json'),
            'steering_quality_training_receipt': self.identity('steering-training-receipt.json')}
        self.result = {'state': 'PASSED', 'exit_code': 0, 'child_exit_code': 0,
                       'ended_at': '2026-10-08T00:00:00+00:00',
                       'lease_released_at': '2026-10-08T00:00:01+00:00',
                       'steering_quality_result': {'state': 'PASSED'}}
        self.native = self.root/'steering-quality'
        self.native.mkdir()
        for name in ('target-prompts.txt', 'contrast-prompts.txt', 'snapshots.json',
                     'snapshots-raw.jsonl', 'execution.json'):
            (self.native/name).write_bytes(b'HOST SYNTHETIC artifact\n')
        for phase in ('absent', 'bank'):
            directory = self.native/phase
            directory.mkdir()
            for name in ('input.jsonl', 'requests.jsonl', 'measurements.jsonl',
                         'server.log', 'client.stdout.log', 'client.stderr.log'):
                (directory/name).write_bytes(('HOST SYNTHETIC '+phase+' '+name+'\n').encode())
        self.metadata()

    def tearDown(self):
        self.temporary.cleanup()

    def identity(self, name):
        payload = (self.root/name).read_bytes()
        return {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}

    def metadata(self):
        payload = json.dumps(self.manifest).encode()
        (self.root/'manifest.json').write_bytes(payload)
        self.expected = hashlib.sha256(payload).hexdigest()
        self.result['manifest_sha256'] = self.expected
        (self.root/'result.json').write_text(json.dumps(self.result))

    def test_complete_both_phase_wire_collected_without_quality_claim(self):
        found = collect.inventory(self.root, self.expected)
        self.assertEqual(found['response_quality_state'], 'PASSED')
        self.assertIn('steering-quality/absent/measurements.jsonl', found['files'])
        self.assertIn('steering-quality/bank/measurements.jsonl', found['files'])
        self.assertFalse(found['response_quality_or_strong_closure_qualified'])
        self.assertFalse(found['heavyweight_model_hash_or_GPU_operation'])

    def test_complete_quality_failure_keeps_all_wire_and_actual_exit(self):
        self.result.update(state='FAILED', exit_code=1, child_exit_code=1,
                           steering_quality_result={'state': 'QUALITY_FAILED'})
        self.metadata()
        found = collect.inventory(self.root, self.expected)
        self.assertEqual(found['response_quality_state'], 'QUALITY_FAILED')
        self.assertEqual(found['actual_child_exit_code'], 1)
        self.assertEqual(len(found['files']), 32)

    def test_infrastructure_failure_keeps_partial_wire(self):
        self.result.update(state='FAILED', exit_code=1, child_exit_code=-15)
        self.result.pop('steering_quality_result')
        self.metadata()
        (self.root/'steering-quality-review.json').unlink()
        shutil.rmtree(self.native/'bank')
        found = collect.inventory(self.root, self.expected)
        self.assertEqual(found['actual_child_exit_code'], -15)
        self.assertIsNone(found['response_quality_state'])
        self.assertIn('steering-quality/absent/measurements.jsonl', found['files'])

    def test_live_unreleased_drifted_and_contradictory_pass_refuse(self):
        for key, value in (('state', 'RUNNING'), ('ended_at', None),
                           ('lease_released_at', True), ('manifest_sha256', '0'*64),
                           ('exit_code', False), ('exit_code', 1), ('child_exit_code', True)):
            with self.subTest(key=key, value=value):
                previous = self.result[key]
                self.result[key] = value
                (self.root/'result.json').write_text(json.dumps(self.result))
                with self.assertRaises(RuntimeError):
                    collect.inventory(self.root, self.expected)
                self.result[key] = previous

    def test_complete_missing_phase_artifact_refuses(self):
        (self.native/'bank/measurements.jsonl').unlink()
        with self.assertRaises(RuntimeError): collect.inventory(self.root, self.expected)

    def test_changed_bound_input_or_missing_helper_refuses(self):
        for name in ('corpus.json', 'direction.ffn.f32', self.helpers[0]):
            with self.subTest(name=name):
                saved = (self.root/name).read_bytes()
                (self.root/name).write_bytes(b'different')
                with self.assertRaises(RuntimeError): collect.inventory(self.root, self.expected)
                (self.root/name).write_bytes(saved)
        self.manifest['steering_quality_helpers'].pop(self.helpers[-1])
        self.metadata()
        with self.assertRaises(RuntimeError): collect.inventory(self.root, self.expected)

    def test_nested_symlink_fifo_and_foreign_file_refuse(self):
        path = self.native/'bank/measurements.jsonl'
        saved = path.read_bytes()
        path.unlink(); path.symlink_to(self.root/'corpus.json')
        with self.assertRaises(RuntimeError): collect.inventory(self.root, self.expected)
        path.unlink(); os.mkfifo(path)
        with self.assertRaises(RuntimeError): collect.inventory(self.root, self.expected)
        path.unlink(); path.write_bytes(saved)
        (self.native/'bank/model.gguf').write_bytes(b'Never copy model files')
        with self.assertRaises(RuntimeError): collect.inventory(self.root, self.expected)

    def test_phase_directory_symlink_refuses(self):
        shutil.rmtree(self.native/'bank')
        (self.native/'bank').symlink_to(self.native/'absent', target_is_directory=True)
        with self.assertRaises(RuntimeError): collect.inventory(self.root, self.expected)

    def test_serialized_inventory_reproduces_native_local_metadata(self):
        program = collect.inventory_program(str(self.root), self.expected)
        run = subprocess.run([sys.executable, '-B', '-'], input=program,
                             capture_output=True, text=True, timeout=15)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(json.loads(run.stdout), collect.inventory(self.root, self.expected))

    def test_cli_transfers_missing_nested_file_and_rechecks_whole_inventory(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary).resolve()
            job = workspace/'evidence/host-quality-r1'
            shutil.copytree(self.root, job)
            remote = collect.inventory(self.root, self.expected)
            nested = 'steering-quality/bank/measurements.jsonl'
            (job/nested).unlink()
            calls = []
            def run(argv, **kwargs):
                calls.append(argv)
                if argv[0] == 'scp':
                    self.assertTrue(argv[-2].endswith('/'+nested))
                    Path(argv[-1]).write_bytes((self.root/nested).read_bytes())
                    return subprocess.CompletedProcess(argv, 0, '', '')
                return subprocess.CompletedProcess(argv, 0, json.dumps(remote), '')
            with patch.object(collect, 'ROOT', workspace), \
                 patch.object(sys, 'argv', ['collector', 'host-quality-r1']), \
                 patch.object(collect.subprocess, 'run', side_effect=run):
                self.assertEqual(collect.main(), 0)
                receipt = json.loads((job/'collection.json').read_text())
                self.assertTrue(receipt['all_local_content_reverified'])
                self.assertEqual(len(calls), 2)
                with self.assertRaises(SystemExit): collect.main()
                self.assertEqual(len(calls), 2)

    def test_remote_relative_path_refuses_before_parent_creation_or_transfer(self):
        expected = {'bytes': 4, 'sha256': hashlib.sha256(b'HOST').hexdigest()}
        for name in ('../foreign.json', '/absolute.json', 'steering-quality/../foreign.json',
                     'steering-quality/foreign/measurements.jsonl',
                     'steering-quality/bank/../../foreign.json'):
            with self.subTest(name=name), patch.object(collect.transfer, 'copy_artifact') as copy:
                with self.assertRaises(ValueError):
                    collect.copy_artifact(self.root, '/owned/job', name, expected, [])
                copy.assert_not_called()

    def test_cli_timeout_retains_actual_unknown_exit_without_launch_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary).resolve()
            job = workspace/'evidence/host-quality-r1'
            shutil.copytree(self.root, job)
            before = (job/'result.json').read_bytes()
            with patch.object(collect, 'ROOT', workspace), \
                 patch.object(sys, 'argv', ['collector', 'host-quality-r1']), \
                 patch.object(collect.subprocess, 'run',
                              side_effect=subprocess.TimeoutExpired(['ssh'], 120)) as run:
                self.assertEqual(collect.main(), 1)
                self.assertEqual(run.call_count, 1)
            receipt = json.loads((job/'collection.json').read_text())
            self.assertIsNone(receipt['commands'][0]['exit_code'])
            self.assertEqual(receipt['exit_code'], 1)
            self.assertEqual((job/'result.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
