#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU-only evidence-reader fixtures; no GPU or model execution."""
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('hc_report',
    Path(__file__).resolve().parents[1] / 'tools/analyze-q2-hc-up.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def event():
    return dict(event='hc_up_fused', label='hc-up-n1-p0-i1-h1', values=2560,
                exact_mixed=True, exact_inject=True, exact_half=True,
                mix_oracle_values=280, inject_oracle_values=12,
                mix_rrms=0.0, mix_scaled_max=0.0, inject_rrms=0.0,
                inject_scaled_max=0.0, independent_pass=True)


def result():
    return dict(state=report.SUCCESS, mode='hc-up-operators', model_access=False,
                postflight_kfd=[], binary_sha256='synthetic-fixture',
                binary_sha256_after='synthetic-fixture', commands=[{'exit_code': 0}])


def fixture(directory, changed=False):
    root = directory / 'results'
    root.mkdir()
    e = event()
    r = result()
    for suffix, kind, count in (('.f32', 'f', 2560), ('.f16', 'e', 2560),
                                ('-inject.f32', 'f', 12)):
        for arm in ('reference', 'fused'):
            values = [1.25] * count
            if changed and arm == 'fused' and suffix == '.f32':
                values[3] = 1.5
            (root / (e['label'] + '-' + arm + suffix)).write_bytes(struct.pack('<' + kind * count, *values))
    if changed:
        e['exact_mixed'] = False
        r['state'] = 'FAILED'
        r['commands'][0]['exit_code'] = 1
    marker = ('FAIL' if changed else 'PASS') + report.END_MARKER
    (root / '01.log').write_text(json.dumps(e) + '\n' + marker + '\n')
    r['artifacts'] = {p.name: {'bytes': p.stat().st_size,
                              'sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
                      for p in root.iterdir()}
    (root / 'result.json').write_text(json.dumps(r))
    return root


class HcReportTests(unittest.TestCase):
    def test_complete_bytes_and_numerical_failure_are_distinct(self):
        with patch.object(report, 'CASES', ((1, 0, True, True),)):
            for changed in (False, True):
                with tempfile.TemporaryDirectory() as value:
                    directory = Path(value)
                    fixture(directory, changed)
                    got = report.analyze(directory)
                    self.assertEqual(got['numerical_pass'], not changed)
                    self.assertEqual(got['state'], 'FAILED' if changed else report.SUCCESS)
                    self.assertEqual(got['command_exits'], [1] if changed else [0])
                    self.assertEqual(len(got['buffers']), 3)
                    mixed = next(r for r in got['buffers'] if r['output'] == 'mixed')
                    self.assertEqual(mixed['changed_values'], int(changed))
                    self.assertEqual(mixed['max_absolute_delta'], .25 if changed else 0)

    def test_tampered_artifact_is_refused(self):
        with tempfile.TemporaryDirectory() as value:
            root = fixture(Path(value))
            path = next(root.glob('*-fused.f32'))
            path.write_bytes(path.read_bytes()[:-4])
            with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
                report.analyze(Path(value))

    def test_nonfinite_and_partial_buffers_are_refused(self):
        good = struct.pack('<f', 1)
        for bad in (b'', good + good, struct.pack('<f', float('nan')),
                    struct.pack('<f', float('inf'))):
            with self.assertRaises(ValueError):
                report.compare_buffer(good, bad, 'f', 1)
        zeros = report.compare_buffer(struct.pack('<e', 0.0), struct.pack('<e', -0.0), 'e', 1)
        self.assertFalse(zeros['exact'])
        self.assertEqual(zeros['changed_values'], 0)

    def test_missing_oracle_and_inconsistent_flags_are_refused(self):
        with patch.object(report, 'CASES', ((1, 0, True, True),)):
            for rows in ([], [event(), event()]):
                with self.assertRaisesRegex(ValueError, 'inventory'):
                    report.cases(rows)
            for key, value in (('mix_oracle_values', 0), ('inject_oracle_values', 0),
                               ('mix_rrms', float('nan')), ('mix_rrms', .1),
                               ('exact_mixed', 'true')):
                e = event()
                e[key] = value
                with self.assertRaises(ValueError):
                    report.cases([e])

    def test_runtime_failure_cannot_be_called_numerical(self):
        marker = 'FAIL' + report.END_MARKER
        for key, value in (('thermal_stop', [1]), ('postflight_error', 'failure'),
                           ('postflight_kfd', [123])):
            r = result()
            r.update(state='FAILED', commands=[{'exit_code': 1}])
            r[key] = value
            with self.assertRaises(ValueError):
                report.validate_completion(r, marker)
        for command in ({'exit_code': 1, 'timeout': True}, {'exit_code': -15},
                        {'exit_code': 1, 'foreign_kfd': [123]}):
            r = result()
            r.update(state='FAILED', commands=[command])
            with self.assertRaises(ValueError):
                report.validate_completion(r, marker)
        r = result()
        with self.assertRaises(ValueError):
            report.validate_completion(r, '')
        r['commands'].insert(0, {'exit_code': None})
        with self.assertRaises(ValueError):
            report.validate_completion(r, 'PASS' + report.END_MARKER)


if __name__ == '__main__':
    unittest.main()
