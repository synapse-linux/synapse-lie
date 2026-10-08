# SPDX-License-Identifier: MIT
"""CPU-only admission and launch checks; never execute a model or access a GPU."""
import ast
import contextlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
RUNNER = ROOT/'tools/q2-promessi-short-window.py'
BASE = ROOT/'tools/q2-counting-curve128-off-window.py'
PLAN = ROOT/'config/q2-promessi-short-plan.json'
if not RUNNER.exists():
    ROOT = Path(__file__).resolve().parent
    RUNNER, BASE, PLAN = ROOT/RUNNER.name, ROOT/BASE.name, ROOT/'plan.json'


class RequestedCorpus(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('corpus_fixture', RUNNER)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.plan = json.loads(PLAN.read_text())

    def test_retirement_leases_and_thermal_gates_unchanged(self):
        def functions(path):
            return {n.name: ast.dump(n, include_attributes=False)
                    for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}
        old, new = functions(BASE), functions(RUNNER)
        for name in ('leases', 'clear', 'assert_retired', 'identity', 'sensor',
                     'cpu_temp_mc', 'cool', 'power_check', 'validate_power'):
            self.assertEqual(old[name], new[name], name)

    def test_exact_requested_plan(self):
        self.assertEqual(self.plan['order'], ['q2-c2048'])
        self.assertEqual(self.plan['sizes'], [2048, 4096, 6144, 8192])
        self.assertEqual(self.plan['total_points'], 4)
        self.assertEqual(self.plan['total_samples'], 8)
        self.assertEqual(self.plan['staged_sha256']['synapse-lie-bench'],
                         'b701e948e8b0e1e241faf0197ebc40446720e7e96c0388d912231fe225f2ef62')

    def test_actual_argv_uses_corpus_and_full_prefill(self):
        class Captured(Exception):
            pass
        captured = []
        def capture(argv, **kwargs):
            captured.extend(argv)
            raise Captured()
        with tempfile.TemporaryDirectory(prefix='lie-corpus-launch-') as directory:
            here = Path(directory)
            with patch.object(self.m, 'HERE', here), patch.object(self.m, 'cool'), \
                 patch.object(self.m.subprocess, 'Popen', side_effect=capture), \
                 self.assertRaises(Captured):
                self.m.one_arm(self.plan, 0, 'q2-c2048', here, [])
            args = dict(zip(captured[1::2], captured[2::2]))
            self.assertEqual(args['--suite'], 'fresh')
            self.assertEqual(args['--prompt-file'], str(here/'promessi_sposi.txt'))
            self.assertEqual(args['--sizes'], '2048,4096,6144,8192')
            self.assertEqual(args['--prefill-chunk'], '2048')
            self.assertEqual(args['--context-capacity'], '133760')
            self.assertEqual(args['--tg'], '128')
            self.assertEqual((args['--warmups'], args['--repetitions']), ('1', '1'))
            self.assertEqual(args['--execution'], 'reactive')
            self.assertNotIn('--prompt-preset', args)
            self.assertNotIn('--depths', args)

    def test_wrong_boot_rejected_before_model_reads(self):
        with patch.object(Path, 'read_text', return_value='wrong-boot'), \
             self.assertRaisesRegex(ValueError, 'Boot changed'):
            self.m.source(self.plan)

    def test_wrong_predecessor_rejected_before_hardware(self):
        with patch.object(Path, 'exists', return_value=False), \
             patch.object(self.m, 'leases', return_value=contextlib.nullcontext()), \
             patch.object(self.m, 'registry_rows', return_value=[dict(
                 event='window_release', receipt_sha256='wrong-predecessor')]), \
             patch.object(self.m, 'clear') as clear, \
             self.assertRaisesRegex(ValueError, 'Intervening ownership event'):
            self.m.admit(self.plan, {})
        clear.assert_not_called()


if __name__ == '__main__':
    unittest.main()
