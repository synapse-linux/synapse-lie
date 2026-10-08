#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check complete timing boundaries against independent synthetic call traces."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile

binary = str(Path(sys.argv[1]).resolve())
checks = 0


def run(args, expected=0, trace=None):
    global checks
    env = dict(os.environ)
    env.pop('LIE_BENCH_TEST_TRACE', None)
    if trace:
        env['LIE_BENCH_TEST_TRACE'] = str(trace)
    p = subprocess.run([binary, *args], env=env, capture_output=True, text=True)
    checks += 1
    assert p.returncode == expected, (args, p.returncode, p.stdout[-1000:], p.stderr[-3000:])


with tempfile.TemporaryDirectory(prefix='lie-counting-test-') as directory:
    root = Path(directory)
    saved = {}
    for chunk in (2048, 4096, 8192):
        out, trace = root/f'{chunk}.jsonl', root/f'{chunk}.trace'
        # Deliberately omit suite and sizes: the default must be full prefill,
        # including every intermediate point, with no hidden replay.
        run(['--model', ':fixture:', '--prompt-preset', 'q2-counting',
             '--prefill-chunk', str(chunk), '--tg', '8', '--warmups', '0',
             '--output', str(out)], trace=trace)
        rows = [json.loads(line) for line in out.read_text().splitlines()]
        identity = rows[0]
        assert identity['suite'] == 'fresh'
        assert identity['measurement_contract'] == 'full-prefill-v1'
        assert identity['prompt_contract'] == 'exact-counting-chat-v1'
        assert identity['synthetic'] is True
        inputs = [r for r in rows if r['event'] == 'input']
        samples = [r for r in rows if r['event'] == 'sample']
        prompts = [r for r in rows if r['event'] == 'prompt_source']
        sizes = list(range(chunk, 131073, chunk))
        assert [r['prompt_tokens'] for r in inputs] == sizes
        assert len(inputs) == len(samples) == len(prompts) == len(sizes)
        calls = [list(map(int, line.split())) for line in trace.read_text().splitlines()]
        assert len(calls) == sum(n//chunk for n in sizes)
        for seq, (n, inp, sample, prompt) in enumerate(zip(sizes, inputs, samples, prompts), 1):
            assert inp['target_prompt_tokens'] == inp['prompt_tokens'] == n
            assert inp['context_capacity'] == 133760
            assert inp['depth'] == sample['depth'] == sample['cache_tokens'] == 0
            assert sample['prefill_tokens_per_user'] == n
            assert sample['prefill_calls_per_user'] == n//chunk
            assert sample['prefill_tail_tokens'] == 0
            ids = inp['physical_ids']
            assert len(ids) == n
            assert hashlib.sha256(struct.pack('<'+'i'*n, *ids)).hexdigest() == inp['physical_ids_sha256']
            assert prompt['physical_ids_sha256'] == inp['physical_ids_sha256']
            # Check the generator's actual text identity against the original
            # workload, independently of benchmark-provided token counters.
            text = ('Ignore this padding data:\n' + 'x '*prompt['padding_repetitions'] +
                    '\nCount from 1 to 200, separated by commas. Output only the numbers.')
            assert hashlib.sha256(text.encode()).hexdigest() == prompt['text_sha256']
            actual = [r for r in calls if r[0] == seq]
            assert [(r[1], r[2]) for r in actual] == [(i, i+chunk) for i in range(0, n, chunk)]
            assert all(sample['prefill_begin_monotonic_ns'] <= r[3] <= r[4] <=
                       sample['prefill_end_monotonic_ns'] for r in actual)
            assert sample['prefill_end_monotonic_ns']-sample['prefill_begin_monotonic_ns'] == sample['prefill_ns']
            assert abs(sample['prefill_tps']-n*1e9/sample['prefill_ns']) < 1e-6
            assert sample['output_tokens_per_user'] == sample['decode_single_calls'] == 8
            assert inp['physical_ids_sha256'] == saved.setdefault(n, inp['physical_ids_sha256'])
        assert rows[-1] == {'event': 'complete', 'exit_code': 0}
        run(['--suite', 'report', '--input', str(out), '--output', str(root/f'report-{chunk}')])
        if chunk == 8192:
            source = rows

    for i, extra in enumerate([
        ['--prompt-file', 'irrelevant'], ['--depths', '0,2048'],
        ['--sizes', '2047'], ['--sizes', '2048,2048'],
        ['--suite', 'single', '--sizes', '2048'],
    ]):
        out = root/f'invalid-{i}.jsonl'
        run(['--model', ':load-failure:', '--prompt-preset', 'q2-counting',
             '--output', str(out), *extra], 2)
        assert not out.exists()

    # Reject a formerly incremental result relabeled "fresh", even if its
    # internal input/sample depths agree. Also guard counters and contract IDs.
    mutations = [
        ('input', 'depth', 8192),
        ('sample', 'prefill_tokens_per_user', 8192),
        ('sample', 'prefill_calls_per_user', 1),
        ('identity', 'measurement_contract', 'incremental-prefill-v1'),
    ]
    for i, (kind, key, value) in enumerate(mutations):
        rows = copy.deepcopy(source)
        candidates = [r for r in rows if r['event'] == kind]
        candidates[-1][key] = value
        out = root/f'tampered-{i}.jsonl'
        out.write_text(''.join(json.dumps(r)+'\n' for r in rows))
        run(['--suite', 'report', '--input', str(out), '--output', str(root/f'tampered-report-{i}')], 1)

print(json.dumps(dict(state='PASS', cli_invocations=checks, points=112,
                      independent_prefill_call_timestamps=True,
                      synthetic=True, model_inference=False)))
