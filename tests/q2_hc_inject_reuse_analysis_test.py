#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Counter regression: invalid HIP elapsed values retain complete-cycle wall evidence."""
import importlib.util
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('analysis',
    ROOT / 'tools/analyze-q2-hc-inject-reuse-component.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
sys.path.insert(0, str(ROOT / 'tools'))
phase_spec = importlib.util.spec_from_file_location('phase',
    ROOT / 'tools/q2-hc-inject-reuse-phase.py')
phase = importlib.util.module_from_spec(phase_spec)
phase_spec.loader.exec_module(phase)


def samples(raw=0, bits=0):
    # Production emits alternating arms. These synthetic records exercise the
    # counter parser, never a kernel, model or performance qualification.
    rows = []
    for mode in range(3):
        for rep in range(7):
            for order in range(2):
                candidate = (rep + order) % 2 != 0
                rows.append(dict(case=f'n2048-m{mode}-p0-half', rep=rep, order=order,
                    candidate=candidate, warmup=rep < 2, iterations=6,
                    rotating_weight_bytes=39321600,
                    wall_us_per_cycle=(900 if candidate else 1000) + rep,
                    hip_ms_raw=raw, hip_ms_raw_bits=bits, hip_timer_valid=False))
    return rows


class CounterRegressionTest(unittest.TestCase):
    def test_zero_HIP_values_do_not_discard_independent_wall_time(self):
        result = analysis.timing_groups(samples())
        self.assertEqual(len(result), 3)
        for row in result:
            self.assertEqual(row['reference']['wall_median_us'], 1004)
            self.assertEqual(row['candidate']['wall_median_us'], 904)
            self.assertLess(row['wall_cycle_time_change_percent'], 0)
            self.assertFalse(row['reference']['HIP_measured_valid'])
            self.assertIsNone(row['candidate']['HIP_us_per_cycle'])
            self.assertFalse(row['pure_GPU_timing_claim'])

    def test_nonfinite_and_signed_zero_bits_are_retained_as_invalid(self):
        for raw, bits in ((None, 0x7fc00000), (None, 0x7f800000),
                          (None, 0xff800000), (0, 0x80000000)):
            with self.subTest(bits=bits):
                result = analysis.timing_groups(samples(raw, bits))
                self.assertEqual(result[0]['candidate']['HIP_raw_bits'], [bits] * 5)
                self.assertFalse(result[0]['candidate']['HIP_measured_valid'])

    def test_printed_binary32_duration_recovers_its_raw_value(self):
        bits = 0x3f800001
        raw = struct.unpack('<f', struct.pack('<I', bits))[0]
        printed = float(format(raw, '.12g'))
        self.assertNotEqual(printed, raw)
        rows = samples(printed, bits)
        for row in rows:
            row['hip_timer_valid'] = True
        result = analysis.timing_groups(rows)
        self.assertTrue(result[0]['candidate']['HIP_measured_valid'])
        self.assertEqual(result[0]['candidate']['HIP_raw_bits'], [bits] * 5)

    def test_changed_raw_duration_or_falsely_valid_zero_is_refused(self):
        for change in (dict(hip_timer_valid=True), dict(hip_ms_raw=1),
                       dict(hip_ms_raw_bits=-1), dict(wall_us_per_cycle=0),
                       dict(wall_us_per_cycle=float('nan')),
                       dict(rotating_weight_bytes=39321600 - 1)):
            with self.subTest(change=change):
                rows = samples()
                rows[0].update(change)
                with self.assertRaises(ValueError):
                    analysis.timing_groups(rows)

    def test_missing_duplicate_and_reordered_cycles_are_refused(self):
        for change in ('missing', 'duplicate', 'reordered', 'arm_order'):
            with self.subTest(change=change):
                rows = samples()
                if change == 'missing':
                    rows.pop()
                elif change == 'duplicate':
                    rows[-1] = rows[0].copy()
                elif change == 'arm_order':
                    rows[0], rows[1] = rows[1], rows[0]
                else:
                    rows[0], rows[2] = rows[2], rows[0]
                with self.assertRaises(ValueError):
                    analysis.timing_groups(rows)


class AdmissionRegressionTest(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.patch = mock.patch.object(phase, 'ROOT', self.root)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        helper = self.root / 'window.py'
        helper.write_text('# fixture\n')
        self.plan = self.root / 'plan.json'
        self.admission = self.root / 'admission.json'
        self.payload = dict(schema='synapse-lie.q2-hc-inject-reuse-plan.v1', arms=[],
            components=[dict(label='q2-hc-inject-reuse-component-r1',
                             mode='hc-inject-reuse-check', variant='hc-inject-reuse-draft')],
            fixtures={}, manifests={}, window_helper='window.py',
            window_helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(),
            previous_release_sha256='a' * 64)
        self.plan.write_text(json.dumps(self.payload))
        self.receipt = dict(state='Q2_HC_INJECT_REUSE_WINDOW_ADMITTED', gpu_reserved=True,
            owner='synapse-lie-q2', plan_sha256=phase.sha(self.plan),
            previous_release_sha256='a' * 64, at='2026-10-06T00:00:00+00:00',
            planned_labels=['q2-hc-inject-reuse-component-r1'])
        self.admission.write_text(json.dumps(self.receipt))

    def test_missing_changed_and_released_admission_never_connect(self):
        for change in ('missing', 'plan', 'release', 'scope', 'helper'):
            with self.subTest(change=change), mock.patch.object(phase.subprocess, 'run') as runner:
                if change == 'missing':
                    path = self.root / 'missing.json'
                else:
                    path = self.admission
                    receipt = dict(self.receipt)
                    if change == 'plan':
                        receipt['plan_sha256'] = 'b' * 64
                    elif change == 'release':
                        receipt['state'] = 'Q2_HC_INJECT_REUSE_WINDOW_RELEASED'
                    elif change == 'scope':
                        receipt['planned_labels'] = []
                    else:
                        (self.root / 'window.py').write_text('# changed\n')
                    path.write_text(json.dumps(receipt))
                with self.assertRaises((OSError, ValueError)):
                    phase.run('component', self.plan, path)
                runner.assert_not_called()

    def test_failed_remote_check_does_not_launch_component(self):
        with mock.patch.object(phase.subprocess, 'run',
                               return_value=subprocess.CompletedProcess([], 255)) as runner:
            self.assertEqual(phase.run('component', self.plan, self.admission), 255)
            self.assertEqual(runner.call_count, 1)
            self.assertEqual(runner.call_args.args[0][0], 'ssh')

    def test_existing_failed_cohort_is_preserved(self):
        target = self.root / 'evidence/q2-hc-inject-reuse-component-r1'
        target.mkdir(parents=True)
        failure = target / 'failure.txt'
        failure.write_text('SSH exit255\n')
        with mock.patch.object(phase.subprocess, 'run') as runner:
            with self.assertRaises(ValueError):
                phase.run('component', self.plan, self.admission)
            runner.assert_not_called()
        self.assertEqual(failure.read_text(), 'SSH exit255\n')

    def test_successful_check_launches_only_one_component(self):
        with mock.patch.object(phase.subprocess, 'run',
                               side_effect=[subprocess.CompletedProcess([], 0),
                                            subprocess.CompletedProcess([], 1)]) as runner:
            self.assertEqual(phase.run('component', self.plan, self.admission), 1)
            self.assertEqual(runner.call_count, 2)
            argv = runner.call_args.args[0]
            self.assertEqual(argv[2:], ['hc-inject-reuse-check',
                'q2-hc-inject-reuse-component-r1', '--source-variant', 'hc-inject-reuse-draft'])
            self.assertNotIn('--rebuild-mmq', argv)

    def test_model_phase_and_model_plan_are_refused(self):
        with mock.patch.object(phase.subprocess, 'run') as runner:
            with self.assertRaises(ValueError):
                phase.run('model', self.plan, self.admission)
            runner.assert_not_called()
        self.payload['arms'] = [dict(mode='q2-original-baseline')]
        self.plan.write_text(json.dumps(self.payload))
        with self.assertRaises(ValueError):
            phase.validate(self.plan, self.admission)

if __name__ == '__main__':
    unittest.main()
