#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Host-only refusal oracles for optional GPU evidence tooling; no model forward."""
import copy
import hashlib
import importlib.util
import io
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('steering_gate', Path(__file__).resolve().parents[1] /
                                            'tools/strix-point-steering-restart-gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


def gguf(entries):
    def string(value):
        raw = value.encode()
        return struct.pack('<Q', len(raw)) + raw
    raw = b'GGUF' + struct.pack('<IQQ', 3, 0, len(entries))
    for key, kind, value in entries:
        raw += string(key) + struct.pack('<I', kind)
        raw += string(value) if kind == 8 else struct.pack('<' + {4: 'I', 6: 'f', 7: '?', 10: 'Q'}[kind], value)
    return raw


class Tests(unittest.TestCase):
    def setUp(self):
        raw = gate.bank_bytes(2, 4)
        self.bank = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        self.ids = [43] * 256 + [71, 72, 73]
        self.steps = gate.steps_for(len(self.ids))

    def rows(self, mode, phase):
        scheduled = phase in gate.SCHEDULED
        disk = phase in ('saved', 'divergent', 'compatible')
        ids = [42, 71, 72, 73] if phase == 'calibration' else [42] * gate.PREFIX + [71, 72, 73] if phase == 'saved' else self.ids
        cached = gate.BOUNDARY if phase == 'compatible' else 0
        budget = gate.OUTPUT if scheduled else 1
        rows = [
            {'event': 'identity', 'schema': 'synapse-lie.core-bench.v1', 'synthetic': False, 'mode': mode,
             'execution': 'shared-reactive-core', 'cache_policy': 'ssd' if disk else 'off',
             'input_kind': 'physical-tokens' if phase == 'saved' else 'raw-text',
             'eos_policy': 'ignore', 'prefix_cache_bytes': 0, 'context_capacity': 4096,
             'prefill_chunk': 256, 'users': 1, 'warmups': 0, 'repetitions': 1,
             'generation': {'temperature': 0}, 'checkpoint_policy': 'ds4', 'cache_text_prefix': True,
             'cache_capture_finish': False, 'cache_cold_max_tokens': 128, 'cache_min_tokens': 128,
             'cache_continued_tokens': 0, 'cache_trim_tokens': 0, 'cache_align_tokens': 1,
             'steering': {'requested': True, 'ffn': 0, 'attention': 0, 'schedule': self.steps if scheduled else []}},
            {'event': 'core_ready', 'steering': {'admitted': True, 'ffn': 0, 'attention': 0,
             'host_vector_bytes': self.bank['bytes'], 'device_vector_bytes': self.bank['bytes'],
             'bank_file_sha256': self.bank['sha256']}},
            {'event': 'input', 'physical_ids': ids, 'prompt_tokens': len(ids), 'physical_ids_sha256': gate.ids_digest(ids)},
            {'event': 'job', 'prompt_tokens': len(ids), 'output_tokens': budget, 'output_ids': list(range(budget)),
             'finish': 'length', 'cached_tokens': cached, 'ssd_cached_tokens': cached, 'prefill_tokens': len(ids) - cached,
             'mtp_drafted_tokens': 28 if mode == 'mtp' and scheduled else 0,
             'mtp_accepted_tokens': 21 if mode == 'mtp' and scheduled else 0,
             'max_decode_output_tokens': 8 if mode == 'mtp' and scheduled else 1},
            {'event': 'sample', 'output_tokens': budget, 'ssd_hits': 1 if cached else 0, 'ssd_errors': 0},
        ]
        if scheduled:
            rows[3]['steering_schedule'] = {'terminal': True, 'completed': 3, 'applied': 3,
                'final_ffn': 0, 'final_attention': 0, 'history_epochs': 4, 'completed_positions': len(ids) + budget,
                'combined_scope_sha256': 'af' * 32,
                'steps': [dict(step, actual_position=step['position'], attempted=True, applied=True, status=0)
                          for step in self.steps]}
        if disk:
            rows.append({'event': 'ssd_drained', 'pending': 0, 'errors': 0, 'disk_bytes': 4096, 'writes': 2})
        return rows + [{'event': 'complete', 'exit_code': 0}]

    def parse(self, rows, mode='ar', phase='divergent'):
        return gate.parse(rows, mode, phase, self.bank, self.steps)

    def observations(self, mode='ar'):
        return {phase: self.parse(self.rows(mode, phase), mode, phase) for phase in gate.PHASES}

    def test_geometry_uses_architecture_and_accepts_order_independent_dimensions(self):
        for arch in ('qwen35moe', 'model_other'):
            entries = [(arch + '.embedding_length', 10, 4), ('general.architecture', 8, arch),
                       (arch + '.block_count', 4, 2)]
            self.assertEqual(gate.geometry(io.BytesIO(gguf(entries))), (arch, 2, 4))

    def test_geometry_refuses_truncation_bad_magic_and_version(self):
        raw = gguf([('general.architecture', 8, 'qwen'), ('qwen.block_count', 4, 2), ('qwen.embedding_length', 4, 4)])
        for bad in (raw[:3], raw[:-1], b'FAIL' + raw[4:], raw[:4] + struct.pack('<I', 1) + raw[8:]):
            with self.assertRaises(RuntimeError):
                gate.geometry(io.BytesIO(bad))

    def test_geometry_refuses_noninteger_zero_and_oversized_dimensions(self):
        for kind, layers, width in ((6, 2.0, 4), (7, True, 4), (4, 0, 4), (4, 1025, 4), (4, 1024, 65536)):
            raw = gguf([('general.architecture', 8, 'qwen'), ('qwen.block_count', kind, layers),
                        ('qwen.embedding_length', 4, width)])
            with self.assertRaisesRegex(RuntimeError, 'geometry'):
                gate.geometry(io.BytesIO(raw))

    def test_metadata_string_length_refused_before_payload_read(self):
        raw = b'GGUF' + struct.pack('<IQQQ', 3, 0, 1, 65537)
        with self.assertRaisesRegex(RuntimeError, 'string exceeds bound'):
            gate.geometry(io.BytesIO(raw))

    def test_bank_is_exact_little_endian_sparse_nonzero(self):
        self.assertEqual(struct.unpack('<8f', gate.bank_bytes(2, 4)), (0.125, 0, 0, 0, 0, 0.125, 0, 0))

    def test_schedule_has_prefill_and_generation_boundaries(self):
        self.assertEqual([step['position'] for step in self.steps], [128, 260, 266])
        for count in (0, 128, 2048):
            with self.assertRaises(RuntimeError):
                gate.steps_for(count)

    def test_six_phase_AR_MTP_complete_comparison(self):
        for mode in ('ar', 'mtp'):
            result = gate.compare(self.observations(mode))
            self.assertEqual(result['divergent_cached_tokens'], 0)
            self.assertEqual(result['compatible_cached_tokens'], 128)
            self.assertTrue(result['scheduled_output_ids_equal'])

    def test_original_identity_is_required(self):
        for key, value in (('synthetic', True), ('execution', 'cpu-fixture'), ('cache_min_tokens', 512), ('users', 2)):
            rows = self.rows('ar', 'divergent');rows[0][key] = value
            with self.assertRaisesRegex(RuntimeError, 'identity'):
                self.parse(rows)

    def test_bank_admission_hash_and_device_bytes_are_required(self):
        for key, value in (('bank_file_sha256', '00' * 32), ('device_vector_bytes', 0), ('admitted', False)):
            rows = self.rows('ar', 'divergent');rows[1]['steering'][key] = value
            with self.assertRaisesRegex(RuntimeError, 'bank'):
                self.parse(rows)

    def test_token_IDs_digest_and_type_are_checked(self):
        for value in (True, -1, 2147483648, '43', 44):
            rows = self.rows('ar', 'divergent');rows[2]['physical_ids'] = rows[2]['physical_ids'].copy()
            rows[2]['physical_ids'][0] = value
            with self.assertRaisesRegex(RuntimeError, 'input witness'):
                self.parse(rows)

    def test_completion_and_unique_witnesses_are_required(self):
        rows = self.rows('ar', 'divergent')
        for bad in (rows[:-1], rows[:-1] + [rows[2], rows[-1]]):
            with self.assertRaises(RuntimeError):
                self.parse(bad)

    def test_exact_output_budget_is_required(self):
        rows = self.rows('ar', 'divergent');rows[3]['output_ids'].pop()
        with self.assertRaisesRegex(RuntimeError, 'output'):
            self.parse(rows)

    def test_divergent_restore_and_compatible_boundary_are_exact(self):
        for phase, wrong in (('divergent', 2048), ('compatible', 129), ('compatible', 0)):
            rows = self.rows('ar', phase);rows[3]['cached_tokens'] = wrong
            with self.assertRaisesRegex(RuntimeError, 'frontier'):
                self.parse(rows, phase=phase)

    def test_SSD_drain_failure_is_refused(self):
        for key in ('pending', 'errors'):
            rows = self.rows('ar', 'divergent');rows[-2][key] = 1
            with self.assertRaisesRegex(RuntimeError, 'drained'):
                self.parse(rows)

    def test_actual_steering_boundary_and_settings_are_exact(self):
        for key, value in (('actual_position', 129), ('ffn', 1), ('applied', False), ('status', 1)):
            rows = self.rows('ar', 'divergent');rows[3]['steering_schedule']['steps'][0][key] = value
            with self.assertRaisesRegex(RuntimeError, 'boundary'):
                self.parse(rows)

    def test_completed_mixed_history_is_required(self):
        for key, value in (('terminal', False), ('completed', 2), ('history_epochs', 1), ('completed_positions', 0)):
            rows = self.rows('ar', 'divergent');rows[3]['steering_schedule'][key] = value
            with self.assertRaisesRegex(RuntimeError, 'history'):
                self.parse(rows)

    def test_MTP_requires_accepted_burst(self):
        for key in ('mtp_accepted_tokens', 'mtp_drafted_tokens', 'max_decode_output_tokens'):
            rows = self.rows('mtp', 'divergent');rows[3][key] = 0
            with self.assertRaisesRegex(RuntimeError, 'accepted burst'):
                self.parse(rows, mode='mtp')

    def test_cross_process_inputs_outputs_and_policy_must_match(self):
        observations = self.observations()
        for event, key in (('input', 'physical_ids'), ('job', 'output_ids'), ('job', 'steering_schedule')):
            changed = copy.deepcopy(observations)
            changed['compatible'][event][key] = [] if key != 'steering_schedule' else {}
            with self.assertRaises(RuntimeError):
                gate.compare(changed)


if __name__ == '__main__':
    unittest.main()
