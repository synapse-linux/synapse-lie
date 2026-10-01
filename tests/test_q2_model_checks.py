# SPDX-License-Identifier: MIT
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import q2_model_checks as q

def fixture():
    data=[{'event':'identity','engine':'gufo-q2-model-test-f783fedb','context':9216,'chunk':2048},
          {'event':'memory_admission',**q.MEMORY,'available':100000000000,'admitted':True},
          {'event':'loaded','load_ns':100,'hip_bytes_requested_cumulative':50000000000}]
    for i,limit in enumerate((16,128)):
        data += [{'event':'sample_begin','sample':i,'output_limit':limit,'prompt_tokens':31,'physical_input_ids':[1]*31},
                 {'event':'sample','sample':i,'prompt_tokens':31,'decode_tokens':1,'final_position':32,'output_ids':[2],
                  'stop':1,'finite_frontiers':True,'prefill_ns':1000000000,'decode_ns':1000000000,
                  'prefill_tok_s':31.,'decode_tok_s':1.,'output_utf8_hex':'34','expected_answer_match':True}]
    data += [{'event':'complete','exit_code':0,'hip_bytes_requested_cumulative':51000000000}]
    return data

class Checks(unittest.TestCase):
    def test_complete_cold_samples_are_not_performance_qualification(self):
        r=q.summarize(fixture())
        self.assertFalse(r['performance_regression_assessed'])
        self.assertFalse(r['memory_fit_qualified'])
    def test_refuse_incomplete_reordered_and_failed(self):
        d=fixture()
        for bad in (d[:-1], [d[0],d[2],d[1],*d[3:]], [*d[:-1],{'event':'failed','exit_code':1}]):
            with self.assertRaises(ValueError): q.summarize(bad)
    def test_refuse_wrong_output_counts_nan_and_nonfinite_frontier(self):
        for k,v in [('output_utf8_hex','35'),('decode_tokens',2),('prefill_tok_s',float('nan')),
                    ('finite_frontiers',False),('final_position',34),('output_ids',[248320])]:
            d=fixture();d[4][k]=v
            with self.assertRaises(ValueError):q.summarize(d)
    def test_no_quota_but_no_silent_plan_drift(self):
        d=fixture();d[-1]['hip_bytes_requested_cumulative']=110000000000
        q.summarize(d) # cumulative requested bytes are NOT live residency
        d[1]['system_reserve']=34359738368
        with self.assertRaises(ValueError):q.summarize(d)
    def test_explicit_current_authorization_required(self):
        m={'authorization':{'model_run_authorized':True,'dedicated_machine':True,'retry_or_fallback':False},
           'memory_envelope':q.MEMORY,'lock_order':[x[0] for x in q.LOCKS],
           'models':[{'path':'/home/paperboy/ds4-launcher/models/gguf/Qwen3.8-Flash-Next-Q2.gguf','bytes':147207127040}]}
        q.admission(m)
        for key in ('model_run_authorized','dedicated_machine'):
            bad=copy.deepcopy(m);bad['authorization'][key]=False
            with self.assertRaises(ValueError):q.admission(bad)
        bad=copy.deepcopy(m);bad['lock_order'].reverse()
        with self.assertRaises(ValueError):q.admission(bad)

if __name__=='__main__':unittest.main()
