#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only ownership/restore fixtures. Commands and observations are mocked."""
import importlib.util
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
        with patch.object(c, 'command', return_value=subprocess.CompletedProcess(
                [], 0, stdout=json.dumps({'Id': 'sha256:'+'b'*64, 'Architecture': 'amd64'}))):
            with self.assertRaisesRegex(ValueError, 'identity'): c.image_and_rocm()
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

if __name__ == '__main__': unittest.main()
