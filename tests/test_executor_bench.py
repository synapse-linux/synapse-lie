#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only benchmark contract checks; the executable links a distinct fixture."""
import copy
import json
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import unittest

BINARY = str(Path(sys.argv.pop(1)).resolve())
BENCH = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'tools/bench-model.py'))


class BenchmarkContract(unittest.TestCase):
    def run_case(self, mode, expected_code):
        with tempfile.TemporaryDirectory(prefix='lie-bench-test-') as tmp:
            out = Path(tmp) / 'data.jsonl'
            p = subprocess.run([BINARY, '--model', mode, '--output', str(out)],
                               capture_output=True, text=True, timeout=10)
            self.assertEqual(p.returncode, expected_code, p.stderr)
            data = [json.loads(line) for line in out.read_text().splitlines()]
            self.assertTrue(data[0]['synthetic'])
            self.assertEqual(data[0]['engine'], 'bench-fixture-NOT-INFERENCE')
            self.assertEqual(data[-1]['event'], 'complete' if expected_code == 0 else 'failed')
            return data

    def test_completed_work_and_fixed_order(self):
        data = self.run_case(':fixture:', 0)
        inputs = {x['profile']: x for x in data if x['event'] == 'input'}
        rows = [x for x in data if x['event'] == 'sample']
        self.assertEqual([(r['rep'], r['profile']) for r in rows],
                         [(rep, i) for rep in range(4) for i in ([2, 1, 0] if rep == 2 else [0, 1, 2])])
        for r in rows:
            p = inputs[r['profile']]
            self.assertEqual(len(p['physical_ids']), r['prompt_tokens'])
            self.assertLessEqual(r['prompt_tokens'], r['requested_prompt_target'])
            self.assertEqual(r['completed_decode_tokens'], 128)
            self.assertEqual(len(r['output_ids']), 128)
            self.assertEqual(r['final_position'], r['prompt_tokens'] + 128)
            self.assertEqual(r['warmup'], r['rep'] == 0)
            self.assertEqual(r['matches_warmup'], r['rep'] != 0)
            self.assertTrue(r['finite_logits'])
            self.assertGreater(r['prefill_ns'], 0)
            self.assertGreater(r['decode_ns'], 0)
            self.assertEqual(len(r['prefill_logits_sha256']), 64)

    def test_eos_is_honored_without_padding_or_rerun(self):
        rows = [r for r in self.run_case(':eos:', 0) if r['event'] == 'sample']
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(r['completed_decode_tokens'] == 7 and r['stop'] == 1 for r in rows))

    def test_nonfinite_logits_refused(self):
        data = self.run_case(':nan:', 1)
        self.assertIn('nonfinite', data[-1]['error'])
        self.assertFalse(any(x['event'] == 'sample' for x in data))

    def test_repeatability_mismatch_is_not_averaged(self):
        data = self.run_case(':drift:', 1)
        self.assertIn('repeatability mismatch', data[-1]['error'])
        self.assertEqual(sum(x['event'] == 'sample' for x in data), 3)

    def test_mutating_failure_is_not_retried(self):
        data = self.run_case(':failure:', 1)
        self.assertIn('no retry', data[-1]['error'])
        self.assertEqual(sum(x['event'] == 'sample_begin' for x in data), 1)

    def test_incorrect_frontier_refused(self):
        data = self.run_case(':frontier:', 1)
        self.assertIn('frontier', data[-1]['error'])

    def test_no_output_overwrite(self):
        with tempfile.TemporaryDirectory(prefix='lie-bench-test-') as tmp:
            out = Path(tmp) / 'data.jsonl'
            out.write_text('preserved\n')
            p = subprocess.run([BINARY, '--model', ':fixture:', '--output', str(out)], capture_output=True, timeout=10)
            self.assertEqual(p.returncode, 1)
            self.assertEqual(out.read_text(), 'preserved\n')

    def test_summary_keeps_all_samples_and_actual_counts(self):
        result = BENCH['summarize'](self.run_case(':eos:', 0))
        self.assertEqual(result['samples_retained'], 9)
        self.assertEqual(result['warmups_excluded'], 3)
        self.assertEqual(result['outliers_removed'], 0)
        self.assertTrue(all(p['completed_decode_tokens'] == 7 for p in result['profiles']))
        self.assertTrue(all(len(p['decode_tps']['all']) == 3 for p in result['profiles']))

    def test_summary_refuses_missing_invalid_or_inconsistent_data(self):
        original = self.run_case(':fixture:', 0)
        sample = next(i for i, x in enumerate(original) if x['event'] == 'sample' and x['rep'] == 1)
        for field, value in [('decode_ns', 0), ('prefill_ns', float('inf')),
                             ('completed_decode_tokens', 127), ('finite_logits', False),
                             ('decode_logits_sha256', 'different')]:
            bad = copy.deepcopy(original)
            bad[sample][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                BENCH['summarize'](bad)
        bad = copy.deepcopy(original)
        del bad[sample]
        with self.assertRaises(ValueError):
            BENCH['summarize'](bad)
        with self.assertRaises(ValueError):
            BENCH['summarize'](original[:-1])

    def test_optional_power_attribute_is_recorded_as_unavailable(self):
        with tempfile.TemporaryDirectory(prefix='lie-power-test-') as tmp:
            present, absent = Path(tmp) / 'governor', Path(tmp) / 'missing'
            present.write_text('powersave\n')
            observed = BENCH['read_power_settings']([present, absent])
            self.assertEqual(observed[str(present)], {'value': 'powersave', 'error': None})
            self.assertIsNone(observed[str(absent)]['value'])
            self.assertEqual(observed[str(absent)]['error']['errno'], 2)
            self.assertFalse(absent.exists())

    def test_build_info_opens_no_model(self):
        p = subprocess.run([BINARY, '--build-info'], capture_output=True, text=True, timeout=10)
        self.assertEqual(p.returncode, 0)
        self.assertEqual(json.loads(p.stdout)['context'], 9216)


if __name__ == '__main__':
    unittest.main()
