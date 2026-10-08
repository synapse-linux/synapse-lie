#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Synthetic scoring guards, never model-quality evidence."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

MODULE = Path(__file__).resolve().parents[1] / 'tools/analyze-q2-terminal.py'
spec = importlib.util.spec_from_file_location('terminal_analysis', MODULE)
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


class Scores(unittest.TestCase):
    def read(self, rewards, *, denominator=1, completed=True, summary_pass=None):
        with tempfile.TemporaryDirectory(prefix='q2-score-fixture-') as name:
            root = Path(name)
            passed = any(x == 1 for x in rewards)
            result = {'task': 'fixture', 'completed': completed, 'passed': passed,
                      'attempts': [{'attempt': i + 1, 'reward': reward, 'duration_ms': 1}
                                   for i, reward in enumerate(rewards)],
                      'evaluation_profile': {}, 'task_provenance': {}}
            summary = {'suite': {'id': 'core19'}, 'quant': 'Q2',
                       'results': ['result.json'], 'total_tasks': denominator,
                       'passed_tasks': int(passed) if summary_pass is None else summary_pass}
            (root / 'result.json').write_text(json.dumps(result))
            (root / 'summary.json').write_text(json.dumps(summary))
            return analysis.read_arm(root, ['fixture'])

    def test_partial_rewards_are_not_passes(self):
        result = self.read([0.8, 0.999])
        self.assertEqual((result['pass_at_1'], result['pass_at_2']), (0, 0))

    def test_conditional_recovery_keeps_first_attempt_failure(self):
        result = self.read([0, 1])
        self.assertEqual((result['pass_at_1'], result['pass_at_2']), (0, 1))

    def test_pending_second_attempt_cannot_be_a_final_score(self):
        with self.assertRaisesRegex(ValueError, 'second attempt'):
            self.read([0])

    def test_repeated_success_cannot_inflate_attempt_budget(self):
        with self.assertRaisesRegex(ValueError, 'repeated'):
            self.read([1, 1])

    def test_smoke_result_cannot_use_full_denominator(self):
        with self.assertRaisesRegex(ValueError, 'denominator'):
            self.read([1], denominator=19)

    def test_incomplete_or_inconsistent_exports_fail(self):
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            self.read([1], completed=False)
        with self.assertRaisesRegex(ValueError, 'Aggregate'):
            self.read([1], summary_pass=0)


if __name__ == '__main__':
    unittest.main()
