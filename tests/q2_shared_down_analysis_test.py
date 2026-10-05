# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('shared_down_analysis', ROOT/'tools/analyze-q2-shared-down-component.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)


def events():
    rows = []
    for n in analysis.SHAPES:
        for r in range(24 if n == 2048 else 3):
            rows.append(dict(event='shared_down_mirror_format', tokens=n, rotation=r, values=2560*640,
                             guards_exact=True, unwritten=0, changed=0, **{'pass': True}))
            for arm in analysis.ARMS:
                rows.append(dict(event='shared_down_mirror_oracle', tokens=n, rotation=r, arm=arm,
                                 samples=24, finite=True, relative_rms=.0001, scaled_error=.0001,
                                 limit=.002, **{'pass': True}))
                if arm != 'original-q8':
                    rows.append(dict(event='shared_down_mirror_pair', tokens=n, rotation=r, arm=arm,
                                     changed=0, nonfinite=0, unwritten=0, guards_exact=True,
                                     reference_sha256='a'*64, candidate_sha256='a'*64, exact=True))
    for rep in range(7):
        for order in range(4):
            rows.append(dict(event='shared_down_mirror_timing', tokens=2048, rep=rep, order=order,
                             arm=analysis.ARMS[(rep+order)%4], warmup=rep<2, iterations=24,
                             q8_weight_bytes=41779200, mirror_weight_bytes=78643200,
                             us_per_iteration=100+order))
    rows.append(dict(event='shared_down_mirror_complete', numerical_pass=True,
                     timing_retained=True, model_inference=False))
    return rows


class SharedDownAnalysis(unittest.TestCase):
    def test_complete_scope_and_timings(self):
        result = analysis.analyze_events(events(), 0)
        self.assertTrue(result['numerical_pass'])
        self.assertEqual(len(result['replay']), 126)
        self.assertEqual(len(result['oracle']), 168)
        self.assertEqual(len(result['timings']), 28)

    def test_safe_numeric_rejection_preserves_all_timings(self):
        rows = events()
        row = next(r for r in rows if r['event'].endswith('_oracle'))
        row.update(relative_rms=.004, **{'pass': False})
        rows[-1]['numerical_pass'] = False
        result = analysis.analyze_events(rows, 1)
        self.assertFalse(result['numerical_pass'])
        self.assertEqual(len(result['timings']), 28)

    def test_missing_writes_and_scope_changes_rejected(self):
        for key, value, message in [('unwritten', 1, 'Unsafe or missing'),
                                    ('tokens', 4096, 'Incomplete output')]:
            rows = events()
            next(r for r in rows if r['event'].endswith('_pair'))[key] = value
            with self.assertRaisesRegex(Exception, message):
                analysis.analyze_events(rows, 0)
        rows = events()
        next(r for r in rows if r['event'].endswith('_timing'))['iterations'] = 1
        with self.assertRaisesRegex(Exception, 'Changed timed scope'):
            analysis.analyze_events(rows, 0)


if __name__ == '__main__':
    unittest.main()
