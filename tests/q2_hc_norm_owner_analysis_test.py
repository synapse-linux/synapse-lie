#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Counter and launch-boundary regressions; synthetic CPU records, no model."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


analysis = module('owner_analysis', 'tools/analyze-q2-hc-norm-owner-component.py')
phase = module('owner_phase', 'tools/q2-hc-norm-owner-phase.py')
window = module('owner_window', 'tools/q2-hc-norm-owner-window.py')


def timings(raw=0, bits=0):
    return [dict(case=name, rep=rep, order=order, candidate=(rep + order) % 2 != 0,
        warmup=rep < 2, iterations=6, residual_payload_bytes=83886080,
        wall_us_per_cycle=(900 if (rep + order) % 2 else 1000) + rep,
        hip_ms_raw=raw, hip_ms_raw_bits=bits, hip_timer_valid=False)
        for name in analysis.coverage()[2] for rep in range(7) for order in range(2)]


class OwnerCounterTest(unittest.TestCase):
    def test_whole_coverage_includes_absent_and_post_outputs(self):
        outputs, inputs, timed = analysis.coverage()
        self.assertEqual((len(outputs), len(inputs), len(timed)), (120, 38, 2))
        self.assertEqual(sum(not v[2] for v in outputs.values()), 5)
        for name in timed:
            self.assertIn((name + '-post', 'residual'), outputs)

    def test_invalid_HIP_preserves_independent_positive_cycle_wall(self):
        for raw, bits in ((0, 0), (0, 0x80000000), (None, 0x7fc00000), (None, 0x7f800000)):
            groups = analysis.timing_groups(timings(raw, bits))
            self.assertEqual(len(groups), 2)
            self.assertEqual(groups[0]['reference']['wall_median_us'], 1004)
            self.assertEqual(groups[0]['candidate']['wall_median_us'], 904)
            self.assertFalse(groups[0]['candidate']['HIP_measured_valid'])
            self.assertEqual(groups[0]['candidate']['HIP_raw_bits'], [bits] * 5)

    def test_printed_positive_HIP_recovers_raw_binary32(self):
        bits = 0x3f800001
        raw = float(format(struct.unpack('<f', struct.pack('<I', bits))[0], '.12g'))
        rows = timings(raw, bits)
        for r in rows:
            r['hip_timer_valid'] = True
        self.assertTrue(analysis.timing_groups(rows)[0]['candidate']['HIP_measured_valid'])

    def test_changed_order_scope_bits_or_invalid_wall_are_refused(self):
        for update in (dict(order=1), dict(warmup=False), dict(candidate=True),
                       dict(hip_timer_valid=True), dict(hip_ms_raw=1), dict(hip_ms_raw_bits=-1),
                       dict(iterations=1), dict(residual_payload_bytes=32 * 1024**2),
                       dict(wall_us_per_cycle=0), dict(wall_us_per_cycle=float('nan'))):
            with self.subTest(update=update):
                rows = timings()
                rows[0].update(update)
                with self.assertRaises(ValueError):
                    analysis.timing_groups(rows)
        for rows in (timings()[:-1], timings() + [timings()[0]]):
            with self.assertRaises(ValueError):
                analysis.timing_groups(rows)


class OwnerPhaseTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.plan_path, self.receipt_path = self.root / 'plan.json', self.root / 'admission.json'
        (self.root / 'fixture').write_bytes(b'fixture')
        self.plan = dict(schema='synapse-lie.q2-hc-norm-owner-plan.v1', arms=[],
            components=[dict(label='component', mode='hc-norm-owner-check',
                             variant='hc-norm-owner-draft')],
            fixtures={'fixture': self.digest(self.root / 'fixture')}, manifests={},
            window_helper='fixture', window_helper_sha256=self.digest(self.root / 'fixture'),
            previous_release_sha256='previous')
        self.save()

    @staticmethod
    def digest(path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def save(self):
        self.plan_path.write_text(json.dumps(self.plan))
        self.receipt = dict(state='Q2_HC_NORM_OWNER_WINDOW_ADMITTED', gpu_reserved=True,
            owner='synapse-lie-q2', plan_sha256=self.digest(self.plan_path),
            previous_release_sha256='previous', planned_labels=['component'])
        self.receipt_path.write_text(json.dumps(self.receipt))

    def test_matching_frozen_component_boundary(self):
        with mock.patch.object(phase, 'ROOT', self.root):
            plan, receipt, digest = phase.validate(self.plan_path, self.receipt_path)
        self.assertEqual(plan['arms'], [])
        self.assertTrue(receipt['gpu_reserved'])
        self.assertEqual(digest, self.digest(self.receipt_path))

    def test_model_scope_and_changed_frozen_identity_are_refused(self):
        self.plan['arms'] = [dict(label='model')]
        self.save()
        with mock.patch.object(phase, 'ROOT', self.root), self.assertRaises(ValueError):
            phase.validate(self.plan_path, self.receipt_path)
        self.plan['arms'] = []
        self.save()
        (self.root / 'fixture').write_bytes(b'changed')
        with mock.patch.object(phase, 'ROOT', self.root), self.assertRaises(ValueError):
            phase.validate(self.plan_path, self.receipt_path)

    def test_released_admission_and_failed_check_never_launch_GPU(self):
        self.receipt['state'] = 'Q2_HC_NORM_OWNER_WINDOW_RELEASED'
        self.receipt_path.write_text(json.dumps(self.receipt))
        with mock.patch.object(phase, 'ROOT', self.root), self.assertRaises(ValueError):
            phase.validate(self.plan_path, self.receipt_path)
        self.save()
        with mock.patch.object(phase, 'ROOT', self.root), \
             mock.patch.object(phase.subprocess, 'run', return_value=mock.Mock(returncode=255)) as run:
            self.assertEqual(phase.run('component', self.plan_path, self.receipt_path), 255)
        self.assertEqual(run.call_count, 1)

    def test_existing_cohort_is_not_restarted(self):
        (self.root / 'evidence/component').mkdir(parents=True)
        with mock.patch.object(phase, 'ROOT', self.root), \
             mock.patch.object(phase.subprocess, 'run') as run, self.assertRaises(ValueError):
            phase.run('component', self.plan_path, self.receipt_path)
        run.assert_not_called()

    def test_failed_historical_CPU_receipt_is_retirement_only(self):
        result_path = self.root / 'cpu/results/result.json'
        result_path.parent.mkdir(parents=True)
        result_path.write_text(json.dumps(dict(finished_at='finished', model_access=False,
            state='FAILED', mode='cpu', pid=10,
            commands=[dict(pid=11, start_ticks=12, exit_code=8, process_group=11)])))
        with mock.patch.object(window, 'ROOT', self.root):
            identities, groups = {}, set()
            window.cohort('cpu', self.digest(result_path), identities, groups, retired_cpu=True)
            self.assertIn(11, groups)
            with self.assertRaises(ValueError):
                window.cohort('cpu', self.digest(result_path), {}, set(), host=True)


if __name__ == '__main__':
    unittest.main()
