#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""CPU parser rejection tests; synthetic rows are never benchmark evidence."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('analysis', ROOT/'tools/analyze-q2-ssm-stage-q8.py')
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)


def fixture():
    shapes = ['ssm1024','ssm1025','ssm1057','ssm2048','ssm2049']
    rows = []
    for shape in shapes + [f'ssm2048-timed-r{i}' for i in range(8)]:
        for rotation in range(3):
            for field in ('projection','convolution'):
                identity = dict(shape=shape,rotation=rotation,field=field)
                rows.append(dict(event='ssm_stage_q8_replay',**identity,exact=True,
                                 guards_exact=True,nonfinite_values=0,unwritten_values=0,
                                 unexpected_unused_values=0))
                for arm in ('reference','candidate'):
                    rows.append(dict(event='ssm_resident_oracle',**identity,arm=arm,
                                     samples=24,relative_rms=0.,scaled_error=0.,limit=.002,
                                     **{'pass':True}))
    rows += [dict(event='ssm_stage_q8_pack_check',exact=True,bytes=44564480) for _ in range(40)]
    rows.append(dict(event='ssm_stage_q8_pack_domain',exact=True,scale_patterns=65536,
                     all_codes=256,allocation_end_input=True))
    rows += [dict(event='ssm_stage_q8_case',shape=s,guards_finite_written=True,
                  inputs_unchanged=True) for s in shapes]
    rows += [dict(event='ssm_stage_q8_resources',candidate=c) for c in (False,True)]
    for rep in range(8):
        for order in range(2):
            candidate = bool((rep+order)%2)
            rows.append(dict(event='ssm_stage_q8_timing',rep=rep,order=order,candidate=candidate,
                             warmup=rep<2,shape='ssm2048',tokens=2048,output_rows=16384,inner=2560,
                             iterations=3,weight_bytes=133693440,completed_wall_us=100-candidate,
                             gpu_event_valid=True,gpu_event_us=99-candidate))
    rows.append(dict(event='ssm_stage_q8_complete',safe_completion=True,timing_retained=True,
                     model_inference=False,numerical_pass=True))
    return rows


class AnalysisTest(unittest.TestCase):
    def test_complete(self):
        result = a.analyze(fixture(),0)
        self.assertEqual(result['output_pairs'],78)
        self.assertFalse(result['model_throughput_gain'])

    def test_safe_difference_retains_timing(self):
        rows = fixture();rows[0]['exact']=False;rows[-1]['numerical_pass']=False
        result = a.analyze(rows,1)
        self.assertFalse(result['numerical_pass'])
        self.assertEqual(len(result['timing_scopes']['gpu_event_us']['pairs']),6)

    def test_zero_events_are_not_gpu_timings(self):
        rows=fixture()
        for r in rows:
            if r['event']=='ssm_stage_q8_timing':
                r.update(gpu_event_valid=False,gpu_event_us=0.)
        result=a.analyze(rows,0)
        self.assertNotIn('gpu_event_us',result['timing_scopes'])
        self.assertIn('completed_wall_us',result['timing_scopes'])

    def test_duplicate_comparison_rejected(self):
        rows=fixture();rows[0]=rows[3].copy()
        with self.assertRaises(ValueError): a.analyze(rows,0)

    def test_unsafe_output_rejected(self):
        rows=fixture();rows[0]['unwritten_values']=1
        with self.assertRaises(ValueError): a.analyze(rows,0)

    def test_false_oracle_pass_rejected(self):
        rows=fixture();rows[1]['relative_rms']=.01
        with self.assertRaises(ValueError): a.analyze(rows,0)

    def test_actual_exit_not_hidden(self):
        with self.assertRaises(ValueError): a.analyze(fixture(),1)

    def test_timing_identity_not_changed(self):
        rows=fixture()
        next(r for r in rows if r['event']=='ssm_stage_q8_timing')['tokens']=2047
        with self.assertRaises(ValueError): a.analyze(rows,0)


if __name__=='__main__':
    unittest.main()
