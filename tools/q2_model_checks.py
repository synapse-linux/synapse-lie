# SPDX-License-Identifier: MIT
"""First-model-test supervision only. Does not qualify performance or parity."""
import math

MEMORY = {'ple_addressed': 102400491520, 'weight_upper': 44952325888,
          'allocation_limit': 0, 'host_allowance': 0,
          'system_reserve': 0, 'required_available': 44952325888}
D = '/home/paperboy/workspace/projects/cachyos/ai/ds4-gufo/qualification/.pipeline.lock'
W = '/home/paperboy/.local/state/ds4-kernel-work/20260927T161150Z-qwen-hip-prefill'
LOCKS = [(D, 52, 3232146), (W+'/download-gufo-native/download.lock', 52, 3206482),
         (W+'/.qualification.lock', 52, 3228451), ('/tmp/synapse-lie-ds4-gpu.lock', 55, 45067)]

def admission(m):
    a = m['authorization']
    if (a.get('model_run_authorized') is not True or
        a.get('dedicated_machine') is not True or
        a.get('retry_or_fallback') is not False or
        m.get('memory_envelope') != MEMORY):
        raise ValueError('Q2 model test needs explicit job/dedicated-machine authorization')
    if (m['lock_order'] != [x[0] for x in LOCKS] or len(m['models']) != 1 or
        m['models'][0]['path'] != '/home/paperboy/ds4-launcher/models/gguf/Qwen3.8-Flash-Next-Q2.gguf' or
        m['models'][0]['bytes'] != 147207127040):
        raise ValueError('Q2 test lease/model scope mismatch')

def summarize(data):
    if [x.get('event') for x in data] != ['identity','memory_admission','loaded',
                                         'sample_begin','sample','sample_begin','sample','complete']:
        raise ValueError('incomplete or reordered first Q2 test')
    ident, mem, loaded = data[:3]
    if (ident.get('engine') != 'gufo-q2-model-test-f783fedb' or
        ident.get('context') != 9216 or ident.get('chunk') != 2048 or
        data[-1].get('exit_code') != 0):
        raise ValueError('Q2 test identity/completion mismatch')
    if (mem.get('admitted') is not True or any(mem.get(k) != v for k,v in MEMORY.items()) or
        mem.get('available',0) < MEMORY['required_available']):
        raise ValueError('Q2 memory admission mismatch')
    if loaded.get('load_ns',0) <= 0:
        raise ValueError('missing completed model load')
    for item in (loaded, data[-1]):
        if not 0 < item.get('hip_bytes_requested_cumulative',0) <= 2**64-1:
            raise ValueError('Q2 allocation accounting missing')
    for i, limit in enumerate((16,128)):
        begin, row = data[3+2*i:5+2*i]
        if (begin.get('sample') != i or row.get('sample') != i or begin.get('output_limit') != limit or
            row.get('finite_frontiers') is not True):
            raise ValueError('Q2 sample identity/frontier mismatch')
        n, count = row.get('prompt_tokens',0), row.get('decode_tokens',0)
        if (not 0 < n <= 8192 or n != begin.get('prompt_tokens') or
            len(begin.get('physical_input_ids',[])) != n or not 0 < count <= limit or
            len(row.get('output_ids',[])) != count or row.get('final_position') != n+count or
            row.get('stop') not in (0,1) or (count < limit and row['stop'] != 1)):
            raise ValueError('Q2 physical token/position mismatch')
        if any(type(t) is not int or not 0 <= t < 248320
               for t in begin['physical_input_ids'] + row['output_ids']):
            raise ValueError('Q2 token out of vocabulary')
        for phase, tokens in (('prefill',n), ('decode',count)):
            ns, rate = row.get(phase+'_ns'), row.get(phase+'_tok_s')
            if (type(ns) is not int or ns <= 0 or not isinstance(rate,(int,float)) or
                not math.isfinite(rate) or not math.isclose(rate,tokens*1e9/ns,rel_tol=1e-12)):
                raise ValueError('Q2 completed-call timing mismatch')
        text = bytes.fromhex(row['output_utf8_hex'])
        if not text or (i == 0 and (text != b'4' or row.get('expected_answer_match') is not True)):
            raise ValueError('Q2 arithmetic smoke answer mismatch')
    return {'state': 'Q2_FIRST_MODEL_SMOKE_PASS_COLD_SAMPLES_NOT_MATCHED_BENCHMARK',
            'samples': [data[4],data[6]], 'load_ns': loaded['load_ns'],
            'numerical_parity_qualified': False, 'performance_regression_assessed': False,
            'memory_fit_qualified': False, 'scope': 'real-model smoke and two fresh cold completed-call samples'}
