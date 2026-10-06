#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Host-only rejection tests for SSD text restart evidence; no model forward."""
import copy
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    'point_ssd_text_restart', Path(__file__).resolve().parents[1] /
    'tools/strix-point-ssd-text-restart-gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class Tests(unittest.TestCase):
    def rows(self, mode, phase):
        disk = phase in ('cold', 'hot')
        ids = [42] * gate.PREFIX_TOKENS if disk else [42] if phase == 'calibration' else [43] * 256
        output = gate.OUTPUT_TOKENS if disk else 1
        cached = gate.PREFIX_TOKENS if phase == 'hot' else 0
        rows = [
            {'event': 'identity', 'schema': 'synapse-lie.core-bench.v1',
             'synthetic': False, 'mode': mode, 'cache_policy': 'ssd' if disk else 'off',
             'input_kind': 'physical-tokens' if phase == 'cold' else 'raw-text',
             'execution': 'shared-reactive-core', 'eos_policy': 'ignore', 'prefix_cache_bytes': 0,
             'generation': {'temperature': 0}, 'checkpoint_policy': 'ds4', 'cache_text_prefix': True,
             'cache_capture_finish': False, 'cache_continued_tokens': 0,
             'cache_trim_tokens': 0, 'cache_align_tokens': 1,
             'prefill_chunk': 256, 'context_capacity': 4096,
             'users': 1, 'warmups': 0, 'repetitions': 1},
            {'event': 'core_ready', 'load_to_ready_ns': 1},
            {'event': 'input', 'physical_ids': ids, 'prompt_tokens': len(ids),
             'physical_ids_sha256': gate.digest_ids(ids)},
            {'event': 'job', 'prompt_tokens': len(ids), 'output_tokens': output,
             'output_ids': list(range(output)), 'finish': 'length',
             'cached_tokens': cached, 'ssd_cached_tokens': cached,
             'prefill_tokens': len(ids) - cached,
             'mtp_drafted_tokens': output if mode == 'mtp' else 0,
             'mtp_accepted_tokens': output if mode == 'mtp' else 0},
            {'event': 'sample', 'output_tokens': output, 'ssd_errors': 0,
             'ssd_hits': 1 if phase == 'hot' else 0},
        ]
        if disk:
            rows.append({'event': 'ssd_drained', 'pending': 0, 'errors': 0,
                         'disk_bytes': 2048, 'writes': 1 if phase == 'cold' else 0})
        return rows + [{'event': 'complete', 'exit_code': 0}]

    def phases(self, mode='ar'):
        return {phase: gate.parse_phase(self.rows(mode, phase), mode, phase) for phase in gate.PHASES}

    def test_saved_history_is_longer_and_outputs_match(self):
        for mode in ('ar', 'mtp'):
            result = gate.compare_phases(self.phases(mode))
            self.assertEqual(result['fresh_bpe_tokens'], 256)
            self.assertEqual(result['hot_ssd_cached_tokens'], gate.PREFIX_TOKENS)
            self.assertTrue(result['output_ids_equal'])

    def test_physical_digest_is_recomputed(self):
        rows = self.rows('ar', 'hot')
        rows[2]['physical_ids'][0] = 7
        with self.assertRaisesRegex(RuntimeError, 'Physical token witness'):
            gate.parse_phase(rows, 'ar', 'hot')

    def test_token_ids_refuse_bool_and_out_of_range(self):
        for invalid in (True, -1, 2147483648, '42'):
            rows = self.rows('ar', 'cold')
            rows[2]['physical_ids'][0] = invalid
            with self.assertRaisesRegex(RuntimeError, 'Physical token witness'):
                gate.parse_phase(rows, 'ar', 'cold')

    def test_cold_must_finish_persistence_and_hot_must_read(self):
        for phase, event, key, value in (
                ('cold', 'ssd_drained', 'pending', 1),
                ('cold', 'ssd_drained', 'writes', 0),
                ('hot', 'sample', 'ssd_hits', 0),
                ('hot', 'job', 'ssd_cached_tokens', 0),
                ('hot', 'job', 'prefill_tokens', 256)):
            rows = self.rows('ar', phase)
            next(row for row in rows if row['event'] == event)[key] = value
            with self.assertRaises(RuntimeError):
                gate.parse_phase(rows, 'ar', phase)

    def test_incomplete_duplicate_and_synthetic_processes_refused(self):
        for change in ('incomplete', 'duplicate', 'synthetic', 'wrong-kind'):
            rows = self.rows('ar', 'hot')
            if change == 'incomplete':
                rows.pop()
            elif change == 'duplicate':
                rows.insert(1, copy.deepcopy(rows[0]))
            elif change == 'synthetic':
                rows[0]['synthetic'] = True
            else:
                rows[0]['input_kind'] = 'physical-tokens'
            with self.assertRaises(RuntimeError):
                gate.parse_phase(rows, 'ar', 'hot')

    def test_same_visible_text_requires_a_real_bpe_difference(self):
        phases = self.phases()
        phases['fresh']['input']['physical_ids'] = [42] * gate.PREFIX_TOKENS
        with self.assertRaisesRegex(RuntimeError, 'Fresh BPE'):
            gate.compare_phases(phases)

    def test_saved_history_and_output_comparison_is_exact(self):
        for witness, key in (('input', 'physical_ids'), ('job', 'output_ids')):
            phases = self.phases()
            phases['hot'][witness][key][0] += 1
            with self.assertRaisesRegex(RuntimeError, 'Cross-process'):
                gate.compare_phases(phases)

    def test_mtp_requires_actual_draft_acceptance(self):
        rows = self.rows('mtp', 'hot')
        rows[3]['mtp_accepted_tokens'] = 0
        with self.assertRaisesRegex(RuntimeError, 'accept a draft'):
            gate.parse_phase(rows, 'mtp', 'hot')

    def test_ar_refuses_speculative_execution(self):
        rows = self.rows('ar', 'cold')
        rows[3]['mtp_drafted_tokens'] = 1
        with self.assertRaisesRegex(RuntimeError, 'AR process'):
            gate.parse_phase(rows, 'ar', 'cold')

    def test_unmatched_cache_and_execution_policies_refused(self):
        for key, value in (('execution', 'direct-executor'), ('prefix_cache_bytes', 4096),
                           ('cache_text_prefix', False), ('cache_trim_tokens', 32),
                           ('cache_capture_finish', True), ('eos_policy', 'stop')):
            rows = self.rows('ar', 'hot')
            rows[0][key] = value
            with self.assertRaisesRegex(RuntimeError, 'identity'):
                gate.parse_phase(rows, 'ar', 'hot')


if __name__ == '__main__':
    unittest.main()
