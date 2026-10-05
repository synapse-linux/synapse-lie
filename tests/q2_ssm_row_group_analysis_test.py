#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU log-parser checks only; synthetic events are not GPU evidence."""
import copy
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'ssm_analysis', ROOT / 'tools/analyze-q2-ssm-row-group-component.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        self.plan = dict(component_shapes=[1024, 1025, 1057, 2048, 2049],
                         component_expected_output_pairs=30,
                         component_expected_oracle_checks=60,
                         component_expected_timing_samples=14,
                         component_weight_rotation_bytes=133693440)
        self.events = []
        for n in self.plan['component_shapes']:
            # Independent closed form: each full32-token window leaves26
            # interior raw rows, except rows needed by the final history tail.
            interior = (n // 32) * 26 + max(0, min(n % 32 - 3, 26))
            tail = sum(t % 32 in range(3, 29) for t in range(n - 3, n))
            for rotation in range(3):
                for field, width in [('projection', 16384), ('convolution', 10240)]:
                    unused = (interior - tail) * 10240 if field == 'projection' else 0
                    self.events.append(dict(
                        event='ssm_row_group_replay', shape='ssm' + str(n),
                        rotation=rotation, field=field, bytes=n * width * 4,
                        required_values=n * width - unused, expected_unused_values=unused,
                        changed_values=0, nonfinite_values=0, unwritten_values=0,
                        unexpected_unused_values=0, guards_exact=True, exact=True,
                        reference_sha256='a' * 64, candidate_sha256='a' * 64))
                    for arm in ('reference', 'candidate'):
                        self.events.append(dict(event='ssm_row_group_oracle',
                            shape='ssm' + str(n), rotation=rotation, field=field,
                            arm=arm, samples=24, relative_rms=0.0001,
                            scaled_error=0.0002, limit=0.002, **{'pass': True}))
        for rep in range(7):
            for order in range(2):
                candidate = bool((rep + order) % 2)
                self.events.append(dict(event='ssm_row_group_timing', shape='ssm2048',
                    rep=rep, order=order, candidate=candidate, warmup=rep < 2,
                    tokens=2048, output_rows=16384, inner=2560, iterations=3,
                    weight_bytes=133693440, us_per_iteration=95 if candidate else 100))
        self.events.append(dict(event='ssm_row_group_complete', numerical_pass=True,
                                timing_retained=True, model_inference=False))

    def run_analysis(self, code=0):
        return analysis.analyze_events(copy.deepcopy(self.events), self.plan, code)

    def test_complete_and_ragged_masks(self):
        result = self.run_analysis()
        self.assertTrue(result['numerical_pass'])
        self.assertAlmostEqual(result['summaries'][0]['candidate_time_change_percent'], -5)

    def test_safe_replay_failure_keeps_timings(self):
        self.events[0].update(changed_values=1, exact=False, candidate_sha256='b' * 64)
        self.events[-1]['numerical_pass'] = False
        result = self.run_analysis(1)
        self.assertFalse(result['parent_exact'])
        self.assertEqual(len(result['timings']), 14)

    def test_safe_operator_failure_keeps_timings(self):
        self.events[1].update(relative_rms=0.003, **{'pass': False})
        self.events[-1]['numerical_pass'] = False
        result = self.run_analysis(1)
        self.assertTrue(result['parent_exact'])
        self.assertFalse(result['independent_operator_pass'])
        self.assertEqual(len(result['timings']), 14)

    def test_missing_write_stops_admission(self):
        self.events[0].update(unwritten_values=1, exact=False)
        self.events[-1]['numerical_pass'] = False
        with self.assertRaises(ValueError):
            self.run_analysis(1)

    def test_missing_output_rejected(self):
        self.events.pop(0)
        with self.assertRaises(ValueError):
            self.run_analysis()

    def test_relaxed_operator_limit_rejected(self):
        self.events[1]['limit'] = 0.004
        with self.assertRaises(ValueError):
            self.run_analysis()

    def test_lost_exit_code_rejected(self):
        with self.assertRaises(ValueError):
            self.run_analysis(1)

    def test_timer_scope_change_rejected(self):
        next(e for e in self.events if e['event'] == 'ssm_row_group_timing')['tokens'] = 1024
        with self.assertRaises(ValueError):
            self.run_analysis()


if __name__ == '__main__':
    unittest.main()
