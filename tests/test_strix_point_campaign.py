#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only ownership/restore fixtures. Commands and observations are mocked."""
import importlib.util
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('point', Path(__file__).resolve().parents[1]/'tools/strix-point-campaign.py')
point = importlib.util.module_from_spec(spec)
spec.loader.exec_module(point)

def observation(*_args):
    return {'at': 'fixture', 'kfd': [], 'dri': [], 'kernel_kfd': [], 'denied_fd': 0,
            'memory': {}, 'temperatures': [{'name': 'k10temp', 'value_c': 35, 'limit_c': 85}]}

class Fixture(point.Campaign):
    active = True
    fail_stop = False
    def command(self, argv, check=True, timeout=30):
        del check, timeout
        self.r['commands'].append(argv)
        assert argv[:2] == ['systemctl', '--user'], argv
        if argv[2] == 'stop':
            self.active = False
            if self.fail_stop: raise RuntimeError('fixture stop interrupted after service exit')
        if argv[2] == 'start': self.active = True
        output = 'ActiveState='+('active' if self.active else 'inactive')+'\nSubState=fixture\nMainPID=999999999\n'
        return subprocess.CompletedProcess(argv, 0, stdout=output, stderr='')

class Tests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.base = Path(self.directory.name)
        self.patches = [patch.object(point, 'BASE', self.base), patch.object(point, 'observe', observation)]
        for p in self.patches: p.start()
    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        self.directory.cleanup()
    def campaign(self, name='run'):
        root = self.base/name; root.mkdir()
        (root/'manifest.json').write_text('{}')
        return Fixture(root, {'authorization': 'CPU fixture; not an actual grant'})
    def test_restore_and_release(self):
        c = self.campaign(); c.enter()
        self.assertFalse(c.active)
        c.finish()
        self.assertTrue(c.active)
        self.assertFalse(c.r['cleanup_failures'])
        self.assertIn('lease_released_at', c.r)
    def test_interrupted_stop_restores(self):
        c = self.campaign(); c.fail_stop = True
        with self.assertRaises(RuntimeError): c.enter()
        c.finish()
        self.assertTrue(c.active)
    def test_inactive_service_stays_inactive(self):
        c = self.campaign(); c.active = False
        c.enter(); c.finish()
        self.assertFalse(c.active)
        self.assertFalse(any('start' in cmd for cmd in c.r['commands']))
    def test_contended_lease_never_stops_service(self):
        first = self.campaign(); second = self.campaign('second')
        try:
            first.enter()
            with self.assertRaises(BlockingIOError): second.enter()
            second.finish()
            self.assertFalse(any('stop' in cmd for cmd in second.r['commands']))
            self.assertNotIn('lease_released_at', second.r)
        finally: first.finish()
    def test_foreign_kfd_refused_and_service_restored(self):
        c = self.campaign()
        bad = observation(); bad['kernel_kfd'] = [123]
        with patch.object(point, 'observe', return_value=bad):
            with self.assertRaisesRegex(RuntimeError, 'Foreign'): c.enter()
        c.finish(); self.assertTrue(c.active)
    def test_owned_kfd_retirement_does_not_mask_a_foreign_client(self):
        c = self.campaign()
        c.cid = 'a'*64
        owner = {'pid': 999999998, 'start_ticks': 12,
                 'cgroup': '/docker/'+c.cid, 'devices': ['/dev/kfd']}
        active = observation()
        active['kfd'] = [owner]
        active['dri'] = [owner]
        active['kernel_kfd'] = [owner['pid']]
        with patch.object(point, 'observe', return_value=active): c.sample()
        retired = observation()
        retired['kernel_kfd'] = [owner['pid']]
        with patch.object(point, 'observe', return_value=retired): c.sample()
        # A live PID, including a reused one, must not inherit the exception.
        with patch.object(point, 'observe', return_value=retired), \
             patch.object(point.Path, 'exists', return_value=True):
            with self.assertRaisesRegex(RuntimeError, 'Foreign'): c.sample()
        retired['kernel_kfd'].append(999999997)
        with patch.object(point, 'observe', return_value=retired):
            with self.assertRaisesRegex(RuntimeError, 'Foreign'): c.sample()
    def test_owned_gpu_retirement_wait_is_bounded(self):
        c = self.campaign()
        waiting = observation(); waiting['kernel_kfd'] = [999999998]
        with patch.object(c, 'sample', side_effect=[waiting, observation()]) as sample, \
             patch.object(point.time, 'sleep'):
            c.wait_owned_gpu_retirement()
            self.assertEqual(sample.call_count, 2)
        with patch.object(c, 'sample', return_value=waiting), \
             patch.object(point.time, 'monotonic', side_effect=[0, 5.1]):
            with self.assertRaisesRegex(RuntimeError, 'retirement deadline'):
                c.wait_owned_gpu_retirement()
    def test_thermal_and_interruption_stop_admission(self):
        c = self.campaign()
        bad = observation(); bad['temperatures'][0]['value_c'] = 85
        with patch.object(point, 'observe', return_value=bad):
            with self.assertRaisesRegex(RuntimeError, 'Thermal'): c.sample()
        c.interrupted = 15
        with self.assertRaisesRegex(RuntimeError, 'Interrupted'): c.sample()
    def test_100c_ceiling_requires_exact_operator_override(self):
        root = self.base/'thermal'; root.mkdir()
        (root/'manifest.json').write_text('{}')
        manifest = {'authorization': 'fixture', 'thermal_ceiling_c': 100}
        with self.assertRaisesRegex(ValueError, 'operator 100 C'):
            Fixture(root, manifest)
        manifest['thermal_override_quote'] = point.THERMAL_OVERRIDE_QUOTE
        c = Fixture(root, manifest)
        self.assertEqual(c.thermal_ceiling_c, 100)
        with patch.object(point, 'observe', return_value=observation()) as read:
            c.sample()
            read.assert_called_once_with(100.0)
        manifest['thermal_ceiling_c'] = 101
        with self.assertRaisesRegex(ValueError, 'Unsupported thermal ceiling'):
            Fixture(root, manifest)
    def test_cpu_guard_records_gpu_without_stopping_and_guards_nvme(self):
        root = self.base/'cpu-guard'; root.mkdir()
        (root/'manifest.json').write_text('{}')
        manifest = {'authorization': 'fixture', 'thermal_policy': point.CPU_GUARD_POLICY,
                    'thermal_ceiling_c': 98}
        with self.assertRaisesRegex(ValueError, 'CPU guard'):
            Fixture(root, manifest)
        manifest['thermal_policy_quote'] = point.CPU_GUARD_QUOTE
        c = Fixture(root, manifest)
        hot = observation()
        hot['temperatures'] = [
            {'name': 'k10temp', 'value_c': 97, 'limit_c': 98, 'guarded': True},
            {'name': 'amdgpu', 'value_c': 103, 'limit_c': 98, 'guarded': False},
            {'name': 'nvme', 'value_c': 84, 'limit_c': 85, 'guarded': True},
        ]
        with patch.object(point, 'observe', return_value=hot) as read:
            c.sample()
            read.assert_called_once_with(98.0, gpu_observation_only=True)
            hot['temperatures'][0]['value_c'] = 98
            with self.assertRaisesRegex(RuntimeError, 'Thermal'): c.sample()
            hot['temperatures'][0]['value_c'] = 97
            hot['temperatures'][2]['value_c'] = 85
            with self.assertRaisesRegex(RuntimeError, 'Thermal'): c.sample()
    def test_kernel_retirement_waits_before_admission(self):
        c = self.campaign()
        before = observation()
        before['kfd'] = [{'pid': 999999999, 'start_ticks': 12}]
        pending = observation(); pending['kernel_kfd'] = [999999999]
        with patch.object(point, 'observe', side_effect=[before, pending, observation()]), patch.object(point.time, 'sleep') as sleep:
            c.enter()
            sleep.assert_called_once_with(0.1)
            self.assertEqual(c.r['admission']['kernel_kfd'], [])
        c.finish()
    def test_owned_container_threads_are_written_to_telemetry(self):
        c = self.campaign(); c.cid = 'test-owned-container'
        row = observation()
        row['dri'] = [{'pid': point.os.getpid(), 'start_ticks': point.ticks(point.os.getpid()),
                       'cgroup': c.cid, 'devices': ['/dev/kfd']}]
        row['kfd'] = row['dri']; row['kernel_kfd'] = [point.os.getpid()]
        with patch.object(point, 'observe', return_value=row): c.sample()
        saved = json.loads((c.root/'telemetry.jsonl').read_text())
        self.assertIn('Threads', saved['dri'][0]['status'])
    def test_container_exit_race_waits_for_final_docker_state(self):
        for pid in (0, 12345):
            with self.subTest(pid=pid):
                c = self.campaign(f'exit-{pid}')
                states = iter(({'Running': True, 'Pid': pid},
                               {'Running': False, 'Pid': 0, 'ExitCode': 0, 'OOMKilled': False}))
                def command(argv, check=True, timeout=30):
                    del check, timeout
                    if argv[1] == 'create': output = 'a'*64
                    elif argv[1] == 'inspect': output = json.dumps(next(states))
                    else: output = ''
                    return subprocess.CompletedProcess(argv, 0, stdout=output, stderr='')
                with patch.object(c, 'command', side_effect=command), \
                     patch.object(point, 'ticks', side_effect=FileNotFoundError), \
                     patch.object(point.time, 'sleep'):
                    c.execute_container(['docker', 'create'], 2)
                self.assertEqual(c.r['child_exit_code'], 0)
                self.assertNotIn('container_start_ticks', c.r)
    def test_failed_core_keeps_model_identity_and_error_evidence(self):
        c = self.campaign(); model = self.base/'model'; model.mkdir()
        path = model/'fixture.gguf'; path.write_bytes(b'tiny fixture')
        st = path.stat()
        row = {'path': str(path), 'bytes': st.st_size, 'device': st.st_dev, 'inode': st.st_ino,
               'mtime_ns': st.st_mtime_ns, 'ctime_ns': st.st_ctime_ns, 'sha256': point.sha(path)}
        plan = {'destination': str(model), 'files': [{'name': path.name, 'sha256': row['sha256']}]}
        (model/'SOURCE.json').write_text(json.dumps({'result': {'state': 'VERIFIED', 'files': [row]}, 'plan': plan}))
        c.m.update(model_plan=plan, bundle=str(self.base), settings={'context':4096,'chunk':2048,'users':1,'tg':32,'warmups':1,'repetitions':3})
        def failure(*args):
            (c.root/'measurements.jsonl').write_text('{"event":"failed","error":"synthetic load failure"}\n')
            raise RuntimeError('fixture GPU child failure')
        with patch.object(c, 'run_container', failure):
            with self.assertRaises(RuntimeError): c.core()
        self.assertTrue(c.r['model_stat_unchanged'])
        self.assertIn('synthetic load failure', c.r['measurements_raw'])
    def test_direct_bench_keeps_partial_failure_and_model_identity(self):
        c = self.campaign(); model = self.base/'model'; model.mkdir()
        shard = model/'fixture.gguf'; shard.write_bytes(b'fixture model identity')
        st = shard.stat()
        row = {'path': str(shard), 'bytes': st.st_size, 'device': st.st_dev, 'inode': st.st_ino,
               'mtime_ns': st.st_mtime_ns, 'ctime_ns': st.st_ctime_ns,
               'sha256': point.sha(shard)}
        plan = {'destination': str(model), 'files': [{'name': shard.name, 'sha256': row['sha256']}]}
        (model/'SOURCE.json').write_text(json.dumps({'result': {'state': 'VERIFIED', 'files': [row]}, 'plan': plan}))
        c.m.update(model_plan=plan, bundle=str(self.base), bench_profile='single')
        def failure(argv, bundle, timeout, model_path):
            self.assertEqual(argv[argv.index('--suite')+1], 'single')
            self.assertEqual(argv[argv.index('--depths')+1], '0,4096,8192,12288,16384,32768,65536,131072')
            self.assertEqual(argv[argv.index('--tg')+1], '128')
            self.assertEqual(timeout, 3600)
            self.assertEqual(model_path, model)
            (c.root/'measurements.jsonl').write_text('{"event":"failed","error":"synthetic thermal stop"}\n')
            raise RuntimeError('fixture child failed')
        with patch.object(c, 'run_container', failure):
            with self.assertRaisesRegex(RuntimeError, 'fixture child failed'): c.bench()
        self.assertTrue(c.r['model_stat_unchanged'])
        self.assertEqual(c.r['bench_partial']['measurements_sha256'], point.sha(c.root/'measurements.jsonl'))
        self.assertNotIn('bench_result', c.r)
        c.m['bench_profile'] = 'arbitrary'
        with self.assertRaisesRegex(ValueError, 'fixed benchmark'): c.bench()
        c.m['bench_profile'] = 'single'
        c.m['bench_impl'] = 'gufo'
        def reference_failure(argv, bundle, timeout, model_path):
            self.assertEqual(argv[0], '/bundle/runtime/bin/synapse-lie-bench-gufo-reference')
            self.assertNotIn('--execution', argv)
            raise RuntimeError('reference fixture failure')
        with patch.object(c, 'run_container', reference_failure):
            with self.assertRaisesRegex(RuntimeError, 'reference fixture failure'): c.bench()
        c.m['bench_impl'] = 'unexpected'
        with self.assertRaisesRegex(ValueError, 'implementation'): c.bench()
    def test_modern_core_ar_and_mtp_require_real_output_and_predictor_identity(self):
        def plan(directory, name):
            directory.mkdir()
            path = directory/name; path.write_bytes(b'fixture '+name.encode())
            st = path.stat()
            row = {'path': str(path), 'bytes': st.st_size, 'device': st.st_dev,
                   'inode': st.st_ino, 'mtime_ns': st.st_mtime_ns, 'ctime_ns': st.st_ctime_ns,
                   'sha256': point.sha(path)}
            result = {'destination': str(directory), 'files': [{'name': name, 'sha256': row['sha256']}]}
            (directory/'SOURCE.json').write_text(json.dumps({'result': {'state': 'VERIFIED', 'files': [row]},
                                                               'plan': result}))
            return result
        model = plan(self.base/'model', 'target.gguf')
        predictor = plan(self.base/'predictor', 'mtp.gguf')
        for mode in ('ar', 'mtp'):
            with self.subTest(mode=mode):
                c = self.campaign('modern-'+mode)
                tokens = c.root/'tokens.json'; tokens.write_text('[1,2,3]')
                c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                           bench_profile='modern-core', decode_mode=mode, bundle=str(self.base),
                           model_plan=model, tokens_sha256=point.sha(tokens), prompt_tokens_expected=3,
                           runtime_build_id='rocm10-point-modern-r1-runtime',
                           settings={'context':4096,'chunk':2048,'users':1,'tg':32,'warmups':0,'repetitions':1})
                if mode == 'mtp': c.m['predictor_plan'] = predictor
                def run(command, _bundle, _timeout, _model):
                    self.assertEqual('--model-mtp' in command, mode == 'mtp')
                    rows = [{'event':'identity','schema':'synapse-lie.core-bench.v1',
                             'mode':mode,'synthetic':False,'cache_policy':'off',
                             'build_id':'rocm10-point-modern-r1-runtime'},
                            {'event':'job','prompt_tokens':3,'output_tokens':32,
                             'mtp_drafted_tokens':4 if mode=='mtp' else 0,
                             'mtp_accepted_tokens':3 if mode=='mtp' else 0},
                            {'event':'sample'}, {'event':'complete','exit_code':0}]
                    (c.root/'measurements.jsonl').write_text(''.join(json.dumps(row)+'\n' for row in rows))
                with patch.object(c, 'run_container', side_effect=run): c.bench()
                self.assertTrue(c.r['model_stat_unchanged'])
                self.assertEqual(c.r['bench_result']['accepted'], 3 if mode=='mtp' else 0)
        c.m['mtp_draft_tokens'] = 8
        with self.assertRaisesRegex(ValueError, 'draft bound'): c.bench()
    def test_modern_mtp_ram_gate_requires_a_measured_prefix_restore(self):
        c = self.campaign('modern-ram')
        tokens = c.root/'tokens.json'; tokens.write_text('[1,2,3]')
        c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                   bench_profile='modern-core-ram', decode_mode='mtp',
                   bundle=str(self.base), tokens_sha256=point.sha(tokens),
                   prompt_tokens_expected=3,
                   runtime_build_id='rocm10-point-modern-r3-runtime',
                   settings={'context':4096,'chunk':2048,'users':1,'tg':32,
                             'warmups':1,'repetitions':1},
                   model_plan={'files':[{'name':'target.gguf'}]})
        rows = [{'event':'identity','schema':'synapse-lie.core-bench.v1',
                 'mode':'mtp','synthetic':False,'cache_policy':'ram',
                 'build_id':'rocm10-point-modern-r3-runtime'},
                {'event':'job','warmup':1,'prompt_tokens':3,'output_tokens':32,
                 'cached_tokens':0,'mtp_drafted_tokens':4,'mtp_accepted_tokens':3},
                {'event':'sample','warmup':1,'cache_hits':0},
                {'event':'job','warmup':0,'prompt_tokens':3,'output_tokens':32,
                 'cached_tokens':3,'mtp_drafted_tokens':4,'mtp_accepted_tokens':3},
                {'event':'sample','warmup':0,'cache_hits':1},
                {'event':'complete','exit_code':0}]
        def run(command, _bundle, _timeout, _model):
            self.assertEqual(command[command.index('--kv-cache-ram-mb')+1], '4096')
            self.assertEqual(command[command.index('--kv-cache-policy')+1], 'ds4')
            self.assertIn('--model-mtp', command)
            (c.root/'measurements.jsonl').write_text(
                ''.join(json.dumps(row)+'\n' for row in rows))
        with patch.object(c, 'verified_model', return_value=(self.base/'model', [])), \
             patch.object(c, 'verified_predictor', return_value=(self.base/'mtp.gguf', {})), \
             patch.object(c, 'check_model_after'), \
             patch.object(c, 'run_container', side_effect=run):
            c.bench()
            self.assertEqual(c.r['bench_result']['measured_cached_tokens'], 3)
            self.assertEqual(c.r['bench_result']['measured_cache_hits'], 1)
            rows[3]['cached_tokens'] = 0
            with self.assertRaisesRegex(RuntimeError, 'did not restore'):
                c.bench()
    def test_modern_direct_reactive_probe_requires_peer_progress_and_cancel(self):
        for mode in ('ar', 'mtp'):
            with self.subTest(mode=mode):
                c = self.campaign('modern-reactive-'+mode)
                tokens = c.root/'tokens.json'; tokens.write_text('[1,2,3]')
                c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                           bench_profile='modern-core-reactive-probe', decode_mode=mode,
                           bundle=str(self.base), tokens_sha256=point.sha(tokens),
                           prompt_tokens_expected=3,
                           runtime_build_id='rocm10-point-modern-r4-runtime',
                           settings={'context':4096,'chunk':2048,'users':2,'tg':32,
                                     'warmups':0,'repetitions':1},
                           model_plan={'files':[{'name':'target.gguf'}]})
                if mode == 'mtp': c.m['predictor_plan'] = {'files':[{'name':'mtp.gguf'}]}
                reactive = {'event':'reactive','scope':'direct-c-core-held-loan-peer-cancel',
                            'synthetic':False,'peer_output_tokens':32,'held_output_tokens':8,
                            'held_borrowed_tokens':1,'held_output_blocked':1,
                            'completed_delta':1,'cancelled_delta':1,'decode_batches_delta':4,
                            'mtp_drafted_delta':6 if mode=='mtp' else 0,
                            'mtp_accepted_delta':2 if mode=='mtp' else 0}
                def run(command, _bundle, _timeout, _model):
                    self.assertIn('--reactive-probe', command)
                    self.assertEqual(command[command.index('--users')+1], '2')
                    self.assertEqual('--model-mtp' in command, mode == 'mtp')
                    rows = [{'event':'identity','schema':'synapse-lie.core-bench.v1',
                             'mode':mode,'synthetic':False,'cache_policy':'off',
                             'reactive_probe':True,'build_id':'rocm10-point-modern-r4-runtime'},
                            {'event':'core_ready'},reactive,{'event':'complete','exit_code':0}]
                    (c.root/'measurements.jsonl').write_text(
                        ''.join(json.dumps(row)+'\n' for row in rows))
                with patch.object(c, 'verified_model', return_value=(self.base/'model', [])), \
                     patch.object(c, 'verified_predictor', return_value=(self.base/'mtp.gguf', {})), \
                     patch.object(c, 'check_model_after'), \
                     patch.object(c, 'run_container', side_effect=run):
                    c.bench()
                    self.assertEqual(c.r['bench_result']['reactive'], reactive)
                    reactive['held_output_blocked'] = 0
                    with self.assertRaisesRegex(RuntimeError, 'reactive GPU probe'):
                        c.bench()
                    reactive['held_output_blocked'] = 1
                    c.m['settings']['users'] = 1
                    with self.assertRaisesRegex(ValueError, 'C2'):
                        c.bench()
    def test_modern_vision_gate_uses_pinned_image_and_real_output(self):
        fixture = point.vision_fixture_png()
        self.assertEqual(fixture[:8], b'\x89PNG\r\n\x1a\n')
        self.assertEqual(hashlib.sha256(fixture).hexdigest(),
                         '93fb5acb49b2a7f77581f957663f3e4572ccb1dbd8f496dcc163f6eca5c8b76e')
        for mode in ('ar', 'mtp'):
            with self.subTest(mode=mode):
                c = self.campaign('modern-vision-'+mode)
                c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                           bench_profile='modern-core-vision', decode_mode=mode,
                           bundle=str(self.base), runtime_build_id='rocm10-point-modern-r4-runtime',
                           model_plan={'files':[{'name':'target.gguf'}]},
                           projector_plan={'files':[{'name':'projector.gguf'}]},
                           vision_fixture_sha256=hashlib.sha256(fixture).hexdigest(),
                           vision_prompt_sha256=hashlib.sha256(point.VISION_PROMPT.encode()).hexdigest(),
                           settings={'context':8192,'chunk':2048,'users':1,'tg':32,
                                     'warmups':0,'repetitions':1})
                if mode == 'mtp': c.m['predictor_plan'] = {'files':[{'name':'mtp.gguf'}]}
                def run(command, _bundle, _timeout, _model):
                    self.assertEqual(command[command.index('--model-vision')+1], '/vision/projector.gguf')
                    self.assertEqual('--model-mtp' in command, mode == 'mtp')
                    self.assertEqual((c.root/'image.png').read_bytes(), fixture)
                    self.assertEqual((c.root/'prompt.txt').read_text(), point.VISION_PROMPT)
                    rows = [{'event':'identity','schema':'synapse-lie.core-bench.v1',
                             'mode':'mtp+vision' if mode=='mtp' else 'vision',
                             'synthetic':False,'input_kind':'messages-with-image',
                             'image_sha256':c.m['vision_fixture_sha256'],
                             'vision_model':'/vision/projector.gguf','cache_policy':'off',
                             'build_id':'rocm10-point-modern-r4-runtime'},
                            {'event':'input','prompt_tokens':150,'physical_ids_sha256':'a'*64},
                            {'event':'job','output_tokens':2,'prefill_tokens':150,
                             'output_ids':[4,5],'mtp_accepted_tokens':1 if mode=='mtp' else 0,
                             'mtp_drafted_tokens':2 if mode=='mtp' else 0},
                            {'event':'sample'}, {'event':'complete','exit_code':0}]
                    (c.root/'measurements.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
                with patch.object(c, 'verified_model', return_value=(self.base/'model', [])), \
                     patch.object(c, 'verified_projector', return_value=(self.base/'projector.gguf', {})), \
                     patch.object(c, 'verified_predictor', return_value=(self.base/'mtp.gguf', {})), \
                     patch.object(c, 'check_model_after'), \
                     patch.object(c, 'run_container', side_effect=run):
                    c.bench()
                    self.assertEqual(c.r['bench_result']['output_ids'], [4,5])
    def test_modern_mtp_ssd_gate_is_explicit_and_requires_disk_hit(self):
        c = self.campaign('modern-ssd')
        tokens = c.root/'tokens.json'; tokens.write_text('[1,2,3]')
        c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                   bench_profile='modern-core-ssd', decode_mode='mtp',
                   bundle=str(self.base), tokens_sha256=point.sha(tokens),
                   prompt_tokens_expected=3,
                   runtime_build_id='rocm10-point-modern-r3-runtime',
                   settings={'context':4096,'chunk':2048,'users':1,'tg':32,
                             'warmups':1,'repetitions':1},
                   model_plan={'files':[{'name':'target.gguf'}]})
        def run(command, _bundle, _timeout, _model):
            self.assertEqual(command[command.index('--kv-cache-ram-mb')+1], '0')
            self.assertEqual(command[command.index('--kv-disk-dir')+1], '/work/kv')
            self.assertEqual(command[command.index('--kv-disk-space-mb')+1], '4096')
            self.assertTrue((c.root/'kv').is_dir())
            rows = [{'event':'identity','schema':'synapse-lie.core-bench.v1',
                     'mode':'mtp','synthetic':False,'cache_policy':'ssd',
                     'build_id':'rocm10-point-modern-r3-runtime'},
                    {'event':'job','warmup':1,'prompt_tokens':3,'output_tokens':32,
                     'cached_tokens':0,'ssd_cached_tokens':0,
                     'mtp_drafted_tokens':4,'mtp_accepted_tokens':3},
                    {'event':'sample','warmup':1,'ssd_hits':0,'ssd_errors':0},
                    {'event':'job','warmup':0,'prompt_tokens':3,'output_tokens':32,
                     'cached_tokens':3,'ssd_cached_tokens':3,
                     'mtp_drafted_tokens':4,'mtp_accepted_tokens':3},
                    {'event':'sample','warmup':0,'ssd_hits':1,'ssd_errors':0},
                    {'event':'complete','exit_code':0}]
            (c.root/'measurements.jsonl').write_text(
                ''.join(json.dumps(row)+'\n' for row in rows))
        with patch.object(c, 'verified_model', return_value=(self.base/'model', [])), \
             patch.object(c, 'verified_predictor', return_value=(self.base/'mtp.gguf', {})), \
             patch.object(c, 'check_model_after'), \
             patch.object(c, 'run_container', side_effect=run):
            c.bench()
        self.assertEqual(c.r['bench_result']['measured_ssd_cached_tokens'], 3)
        self.assertEqual(c.r['bench_result']['measured_ssd_hits'], 1)
    def test_modern_http_gate_checks_original_wire_result_and_helper_identity(self):
        for mode in ('ar', 'mtp'):
            with self.subTest(mode=mode):
                c = self.campaign('modern-http-'+mode)
                helper = c.root/'http-gate.py'
                helper.write_bytes(b'fixture HTTP helper')
                c.m.update(action='bench', stack='rocm10-fedora43',
                           transport='distrobox', bench_profile='modern-http',
                           decode_mode=mode, bundle=str(self.base),
                           model_plan={'files':[{'name':'target.gguf'}]},
                           http_gate_sha256=point.sha(helper))
                if mode == 'mtp': c.m['predictor_plan'] = {'files':[{'name':'mtp.gguf'}]}
                write = {'enabled': True}
                def run(command, _bundle, _timeout, _model):
                    self.assertEqual(command[:3], ['/usr/bin/python3','-B','/work/http-gate.py'])
                    self.assertEqual('/mtp/mtp.gguf' in command, mode == 'mtp')
                    self.assertEqual(_timeout, 1200)
                    if write['enabled']:
                        (c.root/'http-result.json').write_text(json.dumps({
                            'schema':'synapse-lie.point-http-original.v1',
                            'state':'PASSED','mode':mode,'server_exit_code':0,
                            'passed':['models','chat_json','chat_sse',
                                      'responses_json','responses_sse']}))
                with patch.object(c, 'verified_model', return_value=(self.base/'model', [])), \
                     patch.object(c, 'verified_predictor', return_value=(self.base/'mtp.gguf', {})), \
                     patch.object(c, 'check_model_after'), \
                     patch.object(c, 'run_container', side_effect=run):
                    c.bench()
                    self.assertEqual(c.r['http_result']['mode'], mode)
                    helper.write_bytes(b'changed')
                    with self.assertRaisesRegex(ValueError, 'helper drift'): c.bench()
                    helper.write_bytes(b'fixture HTTP helper')
                    run_result = json.loads((c.root/'http-result.json').read_text())
                    run_result['passed'].remove('responses_sse')
                    (c.root/'http-result.json').write_text(json.dumps(run_result))
                    write['enabled'] = False
                    with self.assertRaisesRegex(RuntimeError, 'Incomplete original-weight HTTP'):
                        c.bench()
    def test_modern_ssd_restart_requires_a_cross_process_disk_hit(self):
        c = self.campaign('modern-ssd-restart')
        helper = c.root/'ssd-restart-gate.py'; helper.write_bytes(b'fixture restart helper')
        tokens = c.root/'tokens.json'; tokens.write_text(json.dumps([1]*8192))
        c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                   bench_profile='modern-core-ssd-restart', decode_mode='mtp',
                   bundle=str(self.base), model_plan={'files':[{'name':'target.gguf'}]},
                   predictor_plan={'files':[{'name':'mtp.gguf'}]},
                   ssd_restart_gate_sha256=point.sha(helper), tokens_sha256=point.sha(tokens))
        write = {'enabled': True}
        def run(command, _bundle, timeout, _model):
            self.assertEqual(command[:3], ['/usr/bin/python3','-B','/work/ssd-restart-gate.py'])
            self.assertIn('/mtp/mtp.gguf', command)
            self.assertEqual(timeout, 1500)
            if write['enabled']:
                (c.root/'ssd-restart-result.json').write_text(json.dumps({
                    'schema':'synapse-lie.point-ssd-restart.v1','state':'PASSED',
                    'mode':'mtp','cold_exit_code':0,'hot_exit_code':0,
                    'hot_cached_tokens':8192,'hot_prefill_tokens':0,
                    'hot_ssd_cached_tokens':8192,'hot_ssd_hits':1,
                    'ssd_errors':0,'output_ids_equal':True}))
        with patch.object(c, 'verified_model', return_value=(self.base/'model', [])), \
             patch.object(c, 'verified_predictor', return_value=(self.base/'mtp.gguf', {})), \
             patch.object(c, 'check_model_after'), \
             patch.object(c, 'run_container', side_effect=run):
            c.bench()
            self.assertEqual(c.r['ssd_restart_result']['hot_cached_tokens'], 8192)
            self.assertTrue((c.root/'kv').is_dir())
            helper.write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError, 'helper or tokens drift'): c.bench()
            helper.write_bytes(b'fixture restart helper')
            value = json.loads((c.root/'ssd-restart-result.json').read_text())
            value['hot_ssd_hits'] = 0
            (c.root/'ssd-restart-result.json').write_text(json.dumps(value))
            write['enabled'] = False
            with self.assertRaisesRegex(RuntimeError, 'Incomplete original-weight SSD restart'):
                c.bench()
    def test_rocm_stack_identity_is_explicit(self):
        c = self.campaign()
        self.assertEqual(c.image_and_rocm(), (point.IMAGE, point.ROCM))
        c.m['stack'] = 'rocm10-fedora43'
        c.m['image'] = 'unversioned-image'
        with self.assertRaisesRegex(ValueError, 'pinned'): c.image_and_rocm()
        image = 'sha256:'+'a'*64
        c.m['image'] = image
        with patch.object(c, 'command', return_value=subprocess.CompletedProcess(
                [], 0, stdout=json.dumps({'Id': image, 'Architecture': 'amd64'}))):
            self.assertEqual(c.image_and_rocm(), (image, None))
            c.m['stack'] = 'rocm10-fedora44-rpm'
            self.assertEqual(c.image_and_rocm(), (image, None))
            c.m['stack'] = 'rocm10-almalinux10-rpm'
            self.assertEqual(c.image_and_rocm(), (image, None))
        with patch.object(c, 'command', return_value=subprocess.CompletedProcess(
                [], 0, stdout=json.dumps({'Id': 'sha256:'+'b'*64, 'Architecture': 'amd64'}))):
            with self.assertRaisesRegex(ValueError, 'identity'): c.image_and_rocm()
    def test_distrobox_benchmark_transport_is_explicit(self):
        c = self.campaign(); bundle = self.base/'bundle'; bundle.mkdir()
        (bundle/'probe').write_bytes(b'fixture')
        model = self.base/'model'; model.mkdir()
        c.m.update(action='bench', stack='rocm10-fedora43', transport='distrobox',
                   distrobox_name='lie-test', artifacts={'probe': point.sha(bundle/'probe')})
        image = 'sha256:'+'a'*64
        with patch.object(c, 'image_and_rocm', return_value=(image, None)), \
             patch.object(c, 'execute_distrobox') as execute:
            c.run_container(['/bench'], bundle, 10, model)
            execute.assert_called_once_with(['/bench'], bundle, model, image, 10)
        c.m['transport'] = 'unknown'
        with patch.object(c, 'image_and_rocm', return_value=(image, None)):
            with self.assertRaisesRegex(ValueError, 'transport'):
                c.run_container(['/bench'], bundle, 10, model)
        c.m['transport'] = 'distrobox'; c.m['distrobox_name'] = 'foreign-name'
        with self.assertRaisesRegex(ValueError, 'explicit ROCm 10 name'):
            c.execute_distrobox(['/bench'], bundle, model, image, 10)
    def test_rocm10_build_has_no_gpu_devices_or_network(self):
        c = self.campaign()
        source = self.base/'rocm10-fedora-161'/'source'
        (source/'tools').mkdir(parents=True)
        (source.parent/'source.tar.gz').write_bytes(b'fixture source archive')
        helper = source/'tools/strix-point-rocm10-compile.py'
        helper.write_bytes(b'fixture compile helper')
        c.m.update(stack='rocm10-fedora43',
                   source_archive_sha256=point.sha(source.parent/'source.tar.gz'),
                   compile_helper_sha256=point.sha(helper))
        image = 'sha256:'+'c'*64
        def run(argv, timeout, model_attempted=False):
            self.assertEqual(timeout, 7200)
            self.assertFalse(model_attempted)
            self.assertNotIn('--device', argv)
            self.assertEqual(argv[argv.index('--network')+1], 'none')
            self.assertEqual(argv[argv.index('--entrypoint')+1], '/usr/bin/python3')
            receipt = source/'evidence/rocm10-point-compile-r1/result.json'
            receipt.parent.mkdir(parents=True)
            receipt.write_text('{"state":"BUILT_NOT_GPU_TESTED","exit_code":0}')
        with patch.object(point, 'ROCM10_SOURCE', source), \
             patch.object(c, 'image_and_rocm', return_value=(image, None)), \
             patch.object(c, 'execute_container', side_effect=run):
            c.build()
        self.assertEqual(c.r['build_result']['exit_code'], 0)
    def test_modern_rocm10_build_is_sealed_and_device_free(self):
        c = self.campaign()
        label = 'rocm10-point-modern-r1'
        commit = 'abcdef0123456789'
        source = self.base/'rocm10-fedora-161'/'source-modern-r1'
        helper = source/'cmake/point/Build.cmake'
        helper.parent.mkdir(parents=True)
        helper.write_bytes(b'fixture CMake helper')
        (source/'SOURCE-COMMIT.txt').write_text(commit+'\n')
        inventory = source/'SOURCE-FILES.sha256'
        inventory.write_text(''.join(f'{point.sha(source/name)}  ./{name}\n'
                                     for name in ('SOURCE-COMMIT.txt','cmake/point/Build.cmake')))
        archive = source.with_suffix('.tar.gz')
        archive.write_bytes(b'sealed source fixture')
        c.m.update(stack='rocm10-fedora43', build_flavor='modern-cmake',
                   build_label=label, source_commit=commit,
                   source_archive_sha256=point.sha(archive),
                   source_files_sha256=point.sha(inventory),
                   compile_helper_sha256=point.sha(helper))
        image = 'sha256:'+'d'*64
        def run(argv, timeout, model_attempted=False):
            self.assertEqual(timeout, 7200)
            self.assertFalse(model_attempted)
            self.assertNotIn('--device', argv)
            self.assertEqual(argv[argv.index('--network')+1], 'none')
            self.assertEqual(argv[argv.index('--entrypoint')+1], '/usr/bin/cmake')
            self.assertIn('-DLABEL='+label, argv)
            binary_dir = source/'build'/f'{label}-runtime'
            binary_dir.mkdir()
            names = ('synapse-lie-server','synapse-lie-bench',
                     'synapse-lie-bench-gufo-reference','lie-hip-probe')
            binaries = {}
            for name in names:
                file = binary_dir/name
                file.write_bytes(name.encode())
                binaries[name] = point.sha(file)
            receipt = source/'evidence'/f'{label}-compile'/'result.json'
            receipt.parent.mkdir()
            receipt.write_text(json.dumps({'state':'BUILT_NOT_GPU_TESTED',
                                           'exit_code':0,'source_commit':commit,
                                           'label':label,'hip_architecture':'gfx1150',
                                           'checkpoint_compression':True,
                                           'binaries':binaries}))
        with patch.object(c, 'image_and_rocm', return_value=(image, None)), \
             patch.object(c, 'execute_container', side_effect=run):
            c.build()
        self.assertEqual(c.r['build_result']['source_commit'], commit)
    def test_seccomp_override_requires_explicit_rocm10_manifest(self):
        c = self.campaign()
        bundle = self.base/'bundle'; bundle.mkdir()
        (bundle/'probe').write_bytes(b'fixture')
        c.m.update(artifacts={'probe': point.sha(bundle/'probe')},
                   rocm10_seccomp_unconfined=True)
        with patch.object(point, 'kfd_group', return_value=1000), \
             patch.object(c, 'image_and_rocm', return_value=(point.IMAGE, point.ROCM)):
            with self.assertRaisesRegex(ValueError, 'ROCm 10 only'):
                c.run_container(['/probe'], bundle, 1)
        c = self.campaign('rocm10')
        c.m.update(artifacts={'probe': point.sha(bundle/'probe')},
                   rocm10_seccomp_unconfined=True, stack='rocm10-fedora43')
        with patch.object(point, 'kfd_group', return_value=1000), \
             patch.object(c, 'image_and_rocm', return_value=('sha256:'+'a'*64, None)), \
             patch.object(c, 'execute_container') as execute:
            c.run_container(['/probe'], bundle, 1)
        argv = execute.call_args.args[0]
        self.assertIn('seccomp=unconfined', argv)
        self.assertNotIn('dst=/opt/rocm,readonly', argv)
    def test_diagnostic_retains_hip_failure(self):
        c = self.campaign()
        c.m.update(bundle=str(self.base))
        def run(*_args):
            (c.root/'stdout.log').write_text(json.dumps({
                'scope': 'GPU_RUNTIME_DIAGNOSTIC_NO_MODEL',
                'steps': [{'step': 'copy_pageable_h2d_32', 'code': 1,
                           'name': 'hipErrorInvalidValue'}]}))
        with patch.object(c, 'run_container', side_effect=run):
            with self.assertRaisesRegex(RuntimeError, 'HIP errors'): c.diagnostic()
        self.assertEqual(c.r['diagnostic']['steps'][0]['name'], 'hipErrorInvalidValue')
    def test_almalinux_native_diagnostic_uses_compiled_binary(self):
        c = self.campaign()
        c.m.update(stack='rocm10-almalinux10-rpm', diagnostic_impl='native', bundle=str(self.base))
        def run(command, *_args):
            self.assertEqual(command, ['/opt/lie/hip-smoke'])
            (c.root/'stdout.log').write_text(json.dumps({
                'scope': 'GPU_RUNTIME_DIAGNOSTIC_NO_MODEL', 'device_count': 1,
                'steps': [{'step': 'copy_pageable_h2d_32', 'code': 0}],
                'output': [1, 3, 2, 4, 5, 7, 6, 8]}))
        with patch.object(c, 'image_and_rocm', return_value=('sha256:'+'a'*64, None)), \
             patch.object(c, 'run_container', side_effect=run):
            c.diagnostic()
        self.assertEqual(c.r['diagnostic_impl'], 'native')
        c.m['stack'] = 'rocm10-fedora44-rpm'
        with patch.object(c, 'image_and_rocm', return_value=('sha256:'+'a'*64, None)):
            with self.assertRaisesRegex(ValueError, 'implementation'): c.diagnostic()
    def test_diagnostic_requires_exact_round_trip(self):
        c = self.campaign()
        c.m.update(bundle=str(self.base))
        def run(*_args):
            (c.root/'stdout.log').write_text(json.dumps({
                'scope': 'GPU_RUNTIME_DIAGNOSTIC_NO_MODEL', 'device_count': 1,
                'steps': [{'step': 'copy_d2h_32', 'code': 0}], 'output': [0]*8}))
        with patch.object(c, 'image_and_rocm', return_value=('sha256:'+'a'*64, None)), \
             patch.object(c, 'run_container', side_effect=run):
            with self.assertRaisesRegex(RuntimeError, 'HIP errors'): c.diagnostic()
    def test_almalinux_image_build_checks_native_source_hash(self):
        c = self.campaign()
        context = self.base/'alma'; context.mkdir()
        (context/'Dockerfile').write_text('FROM scratch\n')
        (context/'hip-smoke.cpp').write_text('// fixture\n')
        c.m.update(stack='rocm10-almalinux10-rpm',
                   dockerfile_sha256=point.sha(context/'Dockerfile'),
                   hip_smoke_sha256='0'*64)
        with patch.object(point, 'ROCM10_ALMA_CONTEXT', context):
            with self.assertRaisesRegex(ValueError, 'smoke source drift'): c.image_build()
            c.m['hip_smoke_sha256'] = point.sha(context/'hip-smoke.cpp')
            (context/'unexpected').write_text('fixture')
            with self.assertRaisesRegex(ValueError, 'context contents'): c.image_build()
    def test_full_rocm10_profile_is_diagnostic_only_and_explicit(self):
        c = self.campaign()
        bundle = self.base/'bundle'; bundle.mkdir()
        (bundle/'probe').write_bytes(b'fixture')
        c.m.update(action='diagnostic', stack='rocm10-fedora44-rpm',
                   artifacts={'probe': point.sha(bundle/'probe')},
                   rocm10_diagnostic_full_profile=True)
        with patch.object(point, 'kfd_group', return_value=1000), \
             patch.object(c, 'image_and_rocm', return_value=('sha256:'+'a'*64, None)):
            with self.assertRaisesRegex(ValueError, 'requires explicit'):
                c.run_container(['/probe'], bundle, 1)
            c.m.update(rocm10_seccomp_unconfined=True,
                       rocm10_published_container_profile=True)
            with patch.object(c, 'execute_container') as execute:
                c.run_container(['/probe'], bundle, 1)
            argv = execute.call_args.args[0]
            self.assertNotIn('--read-only', argv)
            self.assertNotIn('--cap-drop', argv)
            self.assertNotIn('no-new-privileges', argv)
            self.assertEqual(argv[argv.index('--ipc')+1], 'host')
            self.assertIn('SYS_PTRACE', argv)
            self.assertIn('LD_LIBRARY_PATH=/bundle/runtime/lib:/opt/rocm/core/lib/rocm_sysdeps/lib:/opt/rocm/lib', argv)
            c.m['action'] = 'bench'
            with self.assertRaisesRegex(ValueError, 'requires explicit'):
                c.run_container(['/probe'], bundle, 1)

if __name__ == '__main__': unittest.main()
