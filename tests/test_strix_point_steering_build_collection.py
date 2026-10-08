# SPDX-License-Identifier: MIT
"""HOST collection lifetimes/large synthetic rows; no remote host or model."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value
collect = module('steering_build_collection', ROOT/'tools/strix-point-steering-build-collect.py')
gate = module('steering_collection_native_review', ROOT/'tools/strix-point-steering-build-gate.py')
NATIVE = os.environ.get('LIE_STEERING_GATE_NATIVE_CLIENT')


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.manifest = {'action': 'bench', 'bench_profile': 'modern-steering-build',
            'steering_build': {'components': 'ffn', 'max_output_bytes': 512*2**20}}
        self.result = {'state': 'PASSED', 'exit_code': 0, 'child_exit_code': 0,
            'ended_at': '2026-10-08T00:00:00+00:00', 'lease_released_at': '2026-10-08T00:00:01+00:00'}
        self.write_metadata()
        for name in ('runner.py', 'steering-build-gate.py', 'target-prompts.txt', 'contrast-prompts.txt', 'telemetry.jsonl', 'steering-build-review.json'):
            (self.root/name).write_bytes(b'SYNTHETIC HOST collection fixture\n')
        self.native = self.root/'steering-build'
        self.native.mkdir()
        for name in ('build.jsonl', 'activations.f32le', 'target-prompts.txt', 'contrast-prompts.txt', 'direction.ffn.f32'):
            (self.native/name).write_bytes(b'SYNTHETIC HOST fixture\n')

    def tearDown(self):
        self.temp.cleanup()

    def write_metadata(self):
        payload = json.dumps(self.manifest).encode()
        (self.root/'manifest.json').write_bytes(payload)
        self.expected = hashlib.sha256(payload).hexdigest()
        self.result['manifest_sha256'] = self.expected
        (self.root/'result.json').write_text(json.dumps(self.result))

    def test_complete_ffn_only_and_selected_component_requirements(self):
        found = collect.inventory(self.root, self.expected)
        self.assertEqual(found['state'], 'PASSED')
        self.assertIn('steering-build/direction.ffn.f32', found['files'])
        self.assertNotIn('steering-build/direction.attention.f32', found['files'])
        self.assertFalse(found['learning_quality_or_strong_closure_qualified'])
        self.manifest['steering_build']['components'] = 'both'; self.write_metadata()
        with self.assertRaises(RuntimeError): collect.inventory(self.root, self.expected)
        (self.native/'direction.attention.f32').write_bytes(b'HOST bank')
        self.assertEqual(collect.inventory(self.root, self.expected)['state'], 'PASSED')
        self.manifest['steering_build']['components'] = 'attention'; self.write_metadata()
        (self.native/'direction.ffn.f32').unlink()
        self.assertNotIn('steering-build/direction.ffn.f32', collect.inventory(self.root, self.expected)['files'])

    def test_failed_partial_capture_is_retained_without_acceptance(self):
        self.result.update(state='FAILED', exit_code=1, child_exit_code=-15); self.write_metadata()
        (self.native/'direction.ffn.f32').rename(self.native/'direction.ffn.f32.partial')
        (self.root/'steering-build-review.json').unlink()
        found = collect.inventory(self.root, self.expected)
        self.assertEqual(found['actual_child_exit_code'], -15)
        self.assertIn('steering-build/direction.ffn.f32.partial', found['files'])
        self.assertFalse(found['learning_quality_or_strong_closure_qualified'])

    def test_live_unreleased_drifted_or_contradictory_terminal_refuses(self):
        for key, value in (('state', 'RUNNING_DISTROBOX'), ('ended_at', None), ('ended_at', True),
                ('lease_released_at', None), ('manifest_sha256', '0'*64), ('exit_code', False),
                ('exit_code', 1), ('child_exit_code', True), ('child_exit_code', -15)):
            with self.subTest(key=key, value=value):
                old = self.result[key]; self.result[key] = value
                (self.root/'result.json').write_text(json.dumps(self.result))
                with self.assertRaises(RuntimeError): collect.inventory(self.root, self.expected)
                self.result[key] = old

    def test_duplicate_nonfinite_and_oversized_metadata_refuse(self):
        for payload in (b'{"action":"bench","action":"bench"}', b'{"x":NaN}'):
            (self.root/'manifest.json').write_bytes(payload)
            with self.assertRaises(ValueError): collect.inventory(self.root, hashlib.sha256(payload).hexdigest())
        for output in (True, 512*2**20+1):
            self.manifest['steering_build']['max_output_bytes'] = output; self.write_metadata()
            with self.assertRaises(RuntimeError): collect.inventory(self.root, self.expected)

    def test_symlink_fifo_directory_and_unknown_native_artifact_refuse(self):
        path = self.native/'activations.f32le'; saved = path.read_bytes()
        path.unlink(); path.symlink_to(self.root/'target-prompts.txt')
        with self.assertRaises(RuntimeError): collect.inventory(self.root, self.expected)
        path.unlink(); os.mkfifo(path)
        with self.assertRaises(RuntimeError): collect.inventory(self.root, self.expected)
        path.unlink(); path.mkdir()
        with self.assertRaises(RuntimeError): collect.inventory(self.root, self.expected)
        path.rmdir(); path.write_bytes(saved)
        (self.native/'foreign-model.gguf').write_bytes(b'Never collect model files')
        with self.assertRaises(RuntimeError): collect.inventory(self.root, self.expected)

    def test_65mib_synthetic_rows_stream_in_bounded_reads(self):
        path = self.native/'activations.f32le'
        with path.open('wb') as stream: stream.truncate(65*2**20)
        with patch.object(collect.os, 'read', wraps=os.read) as reads:
            found = collect.inventory(self.root, self.expected)
        self.assertEqual(found['files']['steering-build/activations.f32le']['bytes'], 65*2**20)
        self.assertGreater(len(reads.call_args_list), 65)
        self.assertTrue(all(0 < call.args[1] <= 2**20 for call in reads.call_args_list))

    def test_same_byte_inode_replacement_refuses_and_descriptor_retires(self):
        path = self.native/'direction.ffn.f32'; real_read = os.read; descriptors = []
        changed = False
        def replace(fd, size):
            nonlocal changed
            data = real_read(fd, size)
            descriptors.append(fd)
            if not changed:
                changed = True; other = path.with_name('replacement')
                other.write_bytes(path.read_bytes()); other.replace(path)
            return data
        with patch.object(collect.os, 'read', side_effect=replace):
            with self.assertRaises(RuntimeError): collect.artifact(path, 2**20)
        with self.assertRaises(OSError): os.fstat(descriptors[0])

    def test_copy_existing_match_skips_scp_and_drift_never_overwrites(self):
        path = self.root/'runner.py'; identity = collect.artifact(path, 2**20)[1]
        with patch.object(collect.subprocess, 'run') as run:
            collect.copy_artifact(self.root, '/owned/job', path.name, identity, [])
            run.assert_not_called(); path.write_bytes(b'changed')
            with self.assertRaises(RuntimeError): collect.copy_artifact(self.root, '/owned/job', path.name, identity, [])
            run.assert_not_called()

    def test_verified_copy_publishes_without_partial_or_overwrite(self):
        payload = b'HOST copied native output'; commands = []
        expected = {'bytes': len(payload), 'sha256': hashlib.sha256(payload).hexdigest()}
        def scp(argv, **_kwargs):
            Path(argv[-1]).write_bytes(payload)
            return subprocess.CompletedProcess(argv, 0, '', '')
        with patch.object(collect.subprocess, 'run', side_effect=scp):
            collect.copy_artifact(self.root, '/owned/job', 'corpus.json', expected, commands)
        self.assertEqual((self.root/'corpus.json').read_bytes(), payload)
        self.assertEqual(commands[0]['exit_code'], 0)
        self.assertFalse(list(self.root.glob('.collection-*')))

    def test_scp_failure_hash_mismatch_timeout_keep_owned_partial(self):
        expected = {'bytes': 4, 'sha256': hashlib.sha256(b'good').hexdigest()}
        for failure in ('exit', 'hash', 'timeout'):
            with self.subTest(failure=failure):
                commands = []
                def scp(argv, **_kwargs):
                    Path(argv[-1]).write_bytes(b'bad!')
                    if failure == 'timeout': raise subprocess.TimeoutExpired(argv, 240)
                    return subprocess.CompletedProcess(argv, 1 if failure == 'exit' else 0, '', 'HOST error')
                with patch.object(collect.subprocess, 'run', side_effect=scp):
                    with self.assertRaises((RuntimeError, subprocess.TimeoutExpired)):
                        collect.copy_artifact(self.root, '/owned/job', failure+'.json', expected, commands)
                self.assertFalse((self.root/(failure+'.json')).exists())
                self.assertEqual(commands[0]['exit_code'], None if failure == 'timeout' else 1 if failure == 'exit' else 0)
                self.assertTrue(list(self.root.glob('.collection-'+failure+'.json-*')))

    def test_destination_created_during_copy_is_preserved(self):
        expected = {'bytes': 4, 'sha256': hashlib.sha256(b'good').hexdigest()}
        def race(argv, **_kwargs):
            Path(argv[-1]).write_bytes(b'good'); (self.root/'corpus.json').write_bytes(b'preexisting')
            return subprocess.CompletedProcess(argv, 0, '', '')
        with patch.object(collect.subprocess, 'run', side_effect=race):
            with self.assertRaises(FileExistsError): collect.copy_artifact(self.root, '/owned/job', 'corpus.json', expected, [])
        self.assertEqual((self.root/'corpus.json').read_bytes(), b'preexisting')

    def test_copy_path_and_content_controls_refuse_before_any_child(self):
        for name, expected in (('../model.gguf', {'bytes': 1, 'sha256': '0'*64}),
                ('bank.json', {'bytes': True, 'sha256': '0'*64}),
                ('bank.json', {'bytes': 1, 'sha256': 'not-a-hash'})):
            with patch.object(collect.subprocess, 'run') as run:
                with self.assertRaises(ValueError): collect.copy_artifact(self.root, '/owned/job', name, expected, [])
                run.assert_not_called()

    def test_serialized_remote_inventory_executes_only_on_local_synthetic_files(self):
        program = collect.inventory_program(str(self.root), self.expected)
        result = subprocess.run([sys.executable, '-B', '-'], input=program, capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), collect.inventory(self.root, self.expected))

    def test_cli_success_rechecks_all_local_content_and_refuses_receipt_replay(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp).resolve(); job = workspace/'evidence/host-r1'
            shutil.copytree(self.root, job)
            remote = collect.inventory(job, self.expected)
            completed = subprocess.CompletedProcess([], 0, json.dumps(remote), '')
            with patch.object(collect, 'ROOT', workspace), patch.object(sys, 'argv', ['collector', 'host-r1']), \
                    patch.object(collect.subprocess, 'run', return_value=completed) as run:
                self.assertEqual(collect.main(), 0)
                receipt = json.loads((job/'collection.json').read_text())
                self.assertTrue(receipt['all_local_content_reverified'])
                self.assertFalse(receipt['learning_quality_or_strong_closure_qualified'])
                run.assert_called_once()
                with self.assertRaises(SystemExit): collect.main()
                run.assert_called_once()

    def test_cli_remote_failure_records_actual_exit_and_preserves_existing_files(self):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp).resolve(); job = workspace/'evidence/host-r1'
            shutil.copytree(self.root, job)
            before = (job/'result.json').read_bytes()
            completed = subprocess.CompletedProcess([], 7, '', 'HOST remote failure')
            with patch.object(collect, 'ROOT', workspace), patch.object(sys, 'argv', ['collector', 'host-r1']), \
                    patch.object(collect.subprocess, 'run', return_value=completed):
                self.assertEqual(collect.main(), 1)
            receipt = json.loads((job/'collection.json').read_text())
            self.assertEqual(receipt['commands'][0]['exit_code'], 7)
            self.assertEqual(receipt['exit_code'], 1)
            self.assertEqual((job/'result.json').read_bytes(), before)

    @unittest.skipUnless(NATIVE, 'Explicit synthetic C17 builder required')
    def test_native_100pair_ffn_only_output_and_independent_oracle_collect(self):
        shutil.rmtree(self.native)
        for side, prefix in (('target', 'T'), ('contrast', 'C')):
            (self.root/(side+'-prompts.txt')).write_text((prefix+'example\n')*100)
        settings = {'context': 8192, 'prefill_chunk': 256, 'components': 'ffn', 'rope': 'native',
            'prompt_format': 'chat', 'max_pairs': 100, 'max_host_bytes': 2**20,
            'max_output_bytes': 2**20, 'timeout_seconds': 30}
        argv = [NATIVE, '--model', ':ok:', '--target-prompts', str(self.root/'target-prompts.txt'),
            '--contrast-prompts', str(self.root/'contrast-prompts.txt'), '--output-dir', str(self.native)]
        for key, value in settings.items():
            if key != 'timeout_seconds': argv += ['--'+key.replace('_', '-'), str(value)]
        result = subprocess.run(argv, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = [json.loads(line) for line in (self.native/'build.jsonl').read_text().splitlines()]
        identity = next(row for row in rows if row['event'] == 'identity')
        sources, pairs = gate.input_pair(self.root, 100)
        proof = gate.validate(self.native, settings, sources, pairs, result.returncode,
            identity['build_id'], 'synthetic-only', ':ok:', expected_synthetic=True)
        self.assertEqual((proof['pairs'], proof['captured_rows']), (100, 400))
        self.assertEqual((self.native/'direction.ffn.f32').read_bytes(), struct.pack('<4f', .6, .8, -.8, .6))
        self.assertFalse(proof['model_generation_or_quality_tested'])
        (self.root/'steering-build-review.json').write_text(json.dumps(proof))
        self.manifest['steering_build'] = settings; self.write_metadata()
        found = collect.inventory(self.root, self.expected)
        self.assertNotIn('steering-build/direction.attention.f32', found['files'])
        self.assertFalse(found['learning_quality_or_strong_closure_qualified'])


if __name__ == '__main__':
    unittest.main()
