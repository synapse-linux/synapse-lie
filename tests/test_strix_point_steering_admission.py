#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Host-only evidence refusal oracles and fixture construction; no model forward."""
import copy
import hashlib
import importlib.util
import math
from pathlib import Path
import stat
import struct
import tempfile
import unittest
from unittest.mock import patch

TOOLS = Path(__file__).resolve().parents[1] / 'tools'
spec = importlib.util.spec_from_file_location('admission', TOOLS / 'strix-point-steering-admission-gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class Tests(unittest.TestCase):
    def setUp(self):
        self.bank = {'bytes': 32, 'sha256': 'af' * 32}
        self.ids = [43, 44, 45]

    def identity(self, mode, requested, ffn, attention):
        return {'event': 'identity', 'schema': 'synapse-lie.core-bench.v1',
                'synthetic': False, 'mode': mode, 'execution': 'shared-reactive-core',
                'cache_policy': 'off', 'prefix_cache_bytes': 0, 'input_kind': 'raw-text',
                'context_capacity': 4096, 'prefill_chunk': 256, 'users': 1, 'warmups': 0,
                'repetitions': 1, 'eos_policy': 'ignore', 'generation': {'temperature': 0},
                'steering': {'requested': requested, 'ffn': ffn, 'attention': attention, 'schedule': []}}

    def refusal(self, case, mode='ar'):
        return [self.identity(mode, True, 1, 0.5),
                {'event': 'failed', 'exit_code': 1,
                 'error': 'core readiness failed: ' + gate.expected_error(case)}]

    def success(self, phase='zero', mode='ar'):
        return [self.identity(mode, phase != 'absent', 0, 0),
                {'event': 'core_ready', 'steering': {'admitted': phase != 'absent',
                 'ffn': 0, 'attention': 0,
                 'host_vector_bytes': 0 if phase == 'absent' else self.bank['bytes'],
                 'device_vector_bytes': 0 if phase == 'absent' else self.bank['bytes'],
                 'bank_file_sha256': '' if phase == 'absent' else self.bank['sha256']}},
                {'event': 'input', 'physical_ids': self.ids, 'prompt_tokens': len(self.ids),
                 'physical_ids_sha256': gate.ids_digest(self.ids)},
                {'event': 'job', 'prompt_tokens': len(self.ids), 'prefill_tokens': len(self.ids),
                 'cached_tokens': 0, 'ssd_cached_tokens': 0, 'output_tokens': gate.OUTPUT,
                 'output_ids': list(range(gate.OUTPUT)), 'finish': 'length',
                 'mtp_drafted_tokens': 14 if mode == 'mtp' else 0,
                 'mtp_accepted_tokens': 3 if mode == 'mtp' else 0},
                {'event': 'sample', 'output_tokens': gate.OUTPUT, 'ssd_hits': 0, 'ssd_errors': 0},
                {'event': 'complete', 'exit_code': 0}]

    def parsed(self, mode='ar'):
        successes = {phase: gate.parse_success(self.success(phase, mode), 0, mode, phase, self.bank)
                     for phase in gate.SUCCESS}
        refusals = [gate.parse_refusal(self.refusal(case, mode), 1, mode, case) for case in gate.CASES]
        return successes, refusals

    def test_exact_native_failures_are_preserved_as_exit_one(self):
        for mode in ('ar', 'mtp'):
            for case in gate.CASES:
                with self.subTest(mode=mode, case=case):
                    row = gate.parse_refusal(self.refusal(case, mode), 1, mode, case)
                    self.assertEqual(row['actual_native_exit_code'], 1)
                    self.assertFalse(row['core_ready'])
                    self.assertFalse(row['numerical_job'])

    def test_other_exit_codes_cannot_count_as_expected_refusal(self):
        for actual in (0, 2, -6, -9, 124):
            with self.subTest(actual=actual), self.assertRaisesRegex(RuntimeError, 'exact diagnostic'):
                gate.parse_refusal(self.refusal('empty'), actual, 'ar', 'empty')

    def test_late_load_or_job_failure_is_not_admission_refusal(self):
        for event in ('core_ready', 'input', 'job', 'sample'):
            rows = self.refusal('empty'); rows.insert(1, {'event': event})
            with self.subTest(event=event), self.assertRaisesRegex(RuntimeError, 'readiness'):
                gate.parse_refusal(rows, 1, 'ar', 'empty')

    def test_wrong_error_complete_or_missing_identity_is_refused(self):
        cases = [self.refusal('empty')[1:],
                 [self.identity('ar', True, 1, 0.5), {'event': 'complete', 'exit_code': 1}],
                 self.refusal('nan-first')]
        for rows in cases:
            with self.assertRaises(RuntimeError):
                gate.parse_refusal(rows, 1, 'ar', 'empty')

    def test_omitted_or_inactive_bank_is_not_a_malformed_bank_request(self):
        for key, value in (('requested', False), ('ffn', 0), ('attention', 0),
                           ('schedule', [{'position': 1, 'ffn': 1, 'attention': 0}])):
            rows = self.refusal('empty'); rows[0]['steering'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'request'):
                gate.parse_refusal(rows, 1, 'ar', 'empty')

    def test_synthetic_cache_or_wrong_mode_cannot_qualify(self):
        for key, value in (('synthetic', True), ('mode', 'mtp'), ('cache_policy', 'ssd'),
                           ('prefix_cache_bytes', 1), ('input_kind', 'physical-tokens'), ('users', 2)):
            rows = self.success(); rows[0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'identity'):
                gate.parse_success(rows, 0, 'ar', 'zero', self.bank)

    def test_absent_zero_and_fresh_core_recovery_match_in_ar_and_mtp(self):
        for mode in ('ar', 'mtp'):
            row = gate.compare(*self.parsed(mode))
            self.assertTrue(row['output_ids_equal'])
            self.assertTrue(row['physical_input_ids_equal'])
            self.assertTrue(row['fresh_core_after_refusals'])
            self.assertEqual(row['expected_refusals'], 12)

    def test_nonzero_or_unadmitted_bank_cannot_be_zero_scale_control(self):
        for key, value in (('admitted', False), ('ffn', 1), ('attention', 0.5),
                           ('host_vector_bytes', 0), ('device_vector_bytes', 0),
                           ('bank_file_sha256', 'bc' * 32)):
            rows = self.success(); rows[1]['steering'][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(RuntimeError, 'admission'):
                gate.parse_success(rows, 0, 'ar', 'zero', self.bank)

    def test_bool_negative_and_overflow_physical_ids_are_refused(self):
        for value in (True, -1, 2147483648):
            rows = self.success(); rows[2]['physical_ids'] = [value]
            with self.subTest(value=value), self.assertRaisesRegex(RuntimeError, 'physical input'):
                gate.parse_success(rows, 0, 'ar', 'zero', self.bank)

    def test_digest_prefill_cache_and_output_must_be_complete(self):
        for index, key, value in ((2, 'physical_ids_sha256', '0' * 64),
                                 (3, 'prefill_tokens', 2), (3, 'cached_tokens', 1),
                                 (3, 'ssd_cached_tokens', 1), (3, 'output_ids', [1]),
                                 (3, 'finish', 'stop'), (4, 'ssd_errors', 1)):
            rows = self.success(); rows[index][key] = value
            with self.subTest(key=key), self.assertRaises(RuntimeError):
                gate.parse_success(rows, 0, 'ar', 'zero', self.bank)

    def test_duplicate_missing_and_nonzero_terminal_exit_are_refused(self):
        for rows, actual in ((self.success() + [self.success()[1]], 0),
                             (self.success()[0:3] + self.success()[4:], 0),
                             (self.success(), 1),
                             (self.success()[:-1] + [{'event': 'failed', 'exit_code': 1}], 1)):
            with self.assertRaises(RuntimeError):
                gate.parse_success(rows, actual, 'ar', 'zero', self.bank)

    def test_mtp_must_draft_and_accept_and_ar_must_not(self):
        for mode, key, value in (('mtp', 'mtp_drafted_tokens', 0),
                                 ('mtp', 'mtp_accepted_tokens', 0),
                                 ('ar', 'mtp_accepted_tokens', 1), ('ar', 'mtp_drafted_tokens', 1)):
            rows = self.success(mode=mode); rows[3][key] = value
            with self.subTest(mode=mode, key=key), self.assertRaisesRegex(RuntimeError, 'MTP'):
                gate.parse_success(rows, 0, mode, 'zero', self.bank)

    def test_output_and_input_mismatch_or_missing_refusals_cannot_pass(self):
        for field, key in (('job', 'output_ids'), ('input', 'physical_ids')):
            success, refusal = self.parsed()
            success['recovery'] = copy.deepcopy(success['recovery'])
            success['recovery'][field][key][0] += 1
            with self.subTest(field=field), self.assertRaisesRegex(RuntimeError, 'differ'):
                gate.compare(success, refusal)
        success, refusal = self.parsed()
        for bad in (refusal[:-1], refusal[::-1], refusal + refusal[:1]):
            with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
                gate.compare(success, bad)

    def test_actual_fixtures_change_only_required_bytes_or_file_kind(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            valid = root / 'valid.f32'
            original = struct.pack('<8f', 0.125, 0, 0, 0, 0, 0.125, 0, 0)
            valid.write_bytes(original)
            paths = gate.create_cases(root / 'banks', valid)
            self.assertEqual(paths['empty'].read_bytes(), b'')
            self.assertEqual(paths['truncated'].read_bytes(), original[:-4])
            self.assertEqual(paths['oversized'].read_bytes(), original + b'\0' * 4)
            for case, index, bits in (('nan-first', 0, 0x7fc00000), ('nan-last', 7, 0x7fc00000),
                                       ('snan-middle', 4, 0x7f800001),
                                       ('positive-infinity', 0, 0x7f800000),
                                       ('negative-infinity', 7, 0xff800000)):
                raw = paths[case].read_bytes()
                self.assertEqual(struct.unpack_from('<I', raw, index * 4)[0], bits)
                self.assertFalse(math.isfinite(struct.unpack_from('<f', raw, index * 4)[0]))
                self.assertEqual(raw[:index * 4], original[:index * 4])
                self.assertEqual(raw[index * 4 + 4:], original[index * 4 + 4:])
            self.assertTrue(paths['directory'].is_dir())
            self.assertTrue(paths['symlink'].is_symlink())
            self.assertTrue(stat.S_ISFIFO(paths['fifo'].lstat().st_mode))
            self.assertFalse(paths['missing'].exists())
            self.assertEqual(valid.read_bytes(), original)
            with self.assertRaises(FileExistsError):
                gate.create_cases(root / 'banks', valid)

    def test_case_bindings_never_open_fifo_symlink_directory_or_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); valid = root / 'valid.f32'
            valid.write_bytes(struct.pack('<8f', *([0.125] * 8)))
            cases = gate.create_cases(root / 'banks', valid)
            original_read = Path.read_bytes
            def read_regular(path):
                self.assertTrue(stat.S_ISREG(path.lstat().st_mode))
                return original_read(path)
            with patch.object(Path, 'read_bytes', read_regular):
                bindings = gate.case_metadata(cases)
            self.assertEqual(bindings['fifo']['kind'], 'fifo')
            self.assertEqual(bindings['symlink']['kind'], 'symlink')
            self.assertEqual(bindings['directory']['kind'], 'directory')
            self.assertEqual(bindings['missing']['kind'], 'missing')
            self.assertEqual(bindings['empty']['sha256'], hashlib.sha256(b'').hexdigest())


if __name__ == '__main__':
    unittest.main()
