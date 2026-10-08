# SPDX-License-Identifier: MIT
"""CPU-only checks for the frozen IOMMU-off experiment; no model or GPU access."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
OFF = ROOT/'tools/q2-counting-curve128-off-window.py'
ON = ROOT/'tools/q2-counting-curve128-window.py'
PLAN = ROOT/'config/q2-counting-curve128-off-plan.json'
CONTROL = ROOT/'config/q2-counting-curve128-plan.json'
if not OFF.exists():
    ROOT = Path(__file__).resolve().parent
    OFF = ROOT/OFF.name
    ON = ROOT/ON.name
    PLAN = ROOT/'plan.json'
    CONTROL = ROOT/'control-plan.json'


class ComparisonContract(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location('off_fixture', OFF)
        self.m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.m)
        self.plan = json.loads(PLAN.read_text())

    def test_all_benchmark_and_measurement_functions_are_unchanged(self):
        def functions(path):
            return {n.name: ast.dump(n, include_attributes=False)
                    for n in ast.parse(path.read_text()).body if isinstance(n, ast.FunctionDef)}
        on, off = functions(ON), functions(OFF)
        self.assertEqual(set(on), set(off))
        # Only boot/IOMMU admission, its registry label, and the qualification
        # receipt change. The complete numerical launch, thermal gates, timing
        # validation, lease acquisition, and process retirement stay identical.
        self.assertEqual({k for k in on if on[k] != off[k]}, {'source', 'emit_event', 'admit', 'main'})

    def test_frozen_workload_and_model_files_match_control(self):
        on = json.loads(CONTROL.read_text())
        for key in ('order', 'output_tokens', 'warmups', 'repetitions',
                    'context_capacity', 'prompt_limit', 'arm_timeout_seconds',
                    'total_points', 'total_samples', 'source_manifest_sha256', 'cpu_tests'):
            self.assertEqual(self.plan[key], on[key], key)
        self.assertEqual(self.plan['staged_sha256']['synapse-lie-bench'], on['staged_sha256']['synapse-lie-bench'])
        for left, right in zip(on['model_stats'], self.plan['model_stats'], strict=True):
            self.assertEqual({k:v for k,v in left.items() if k != 'device'},
                             {k:v for k,v in right.items() if k != 'device'})
        self.assertEqual(self.plan['control_plan_sha256'], hashlib.sha256(CONTROL.read_bytes()).hexdigest())

    def test_wrong_boot_is_rejected_before_staged_or_model_reads(self):
        with patch.object(Path, 'read_text', return_value='wrong-boot'), \
             self.assertRaisesRegex(ValueError, 'Boot changed'):
            self.m.source(self.plan)

    def test_old_release_cannot_admit_the_new_window(self):
        # A historical window release with the correct digest is still not the
        # current-boot transition event; rejection must precede hardware checks.
        import contextlib
        with patch.object(Path, 'exists', return_value=False), \
             patch.object(self.m, 'leases', return_value=contextlib.nullcontext()), \
             patch.object(self.m, 'registry_rows', return_value=[dict(
                 event='window_release', receipt_sha256=self.plan['previous_release_sha256'])]), \
             patch.object(self.m, 'clear') as clear, \
             self.assertRaisesRegex(ValueError, 'Intervening ownership event'):
            self.m.admit(self.plan, {})
        clear.assert_not_called()


if __name__ == '__main__':
    unittest.main()
