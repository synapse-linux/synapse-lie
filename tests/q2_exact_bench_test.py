#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Exercise exact native prompt/phase accounting with a synthetic executor."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile

binary = Path(sys.argv[1]).resolve()
corpus = Path(sys.argv[2]).resolve()
checks = 0


def run(args, expected=0):
    global checks
    result = subprocess.run([str(binary), *args], capture_output=True, text=True)
    checks += 1
    if result.returncode != expected:
        raise AssertionError((args, result.returncode, result.stdout[-1000:], result.stderr[-3000:]))
    return result


with tempfile.TemporaryDirectory(prefix='lie-exact-bench-') as directory:
    temp = Path(directory)
    sources = {}
    for chunk in (2048, 4096, 8192):
        sizes = [chunk, chunk * 2, chunk * 4, 131072]
        output = temp / f'fresh-{chunk}.jsonl'
        run(['--suite', 'fresh', '--model', ':fixture:', '--prompt-file', str(corpus),
             '--output', str(output), '--sizes', ','.join(map(str, sizes)),
             '--prefill-chunk', str(chunk), '--tg', '8', '--warmups', '0',
             '--context-capacity', '133760'])
        rows = [json.loads(line) for line in output.read_text().splitlines()]
        assert rows[-1]['event'] == 'complete' and rows[-1]['exit_code'] == 0
        identity = rows[0]
        assert identity['synthetic'] is True and identity['prefill_chunk'] == chunk
        assert identity['prompt_contract'] == 'exact-token-prefix-v1'
        corpora = [r for r in rows if r['event'] == 'corpus']
        assert len(corpora) == 1
        assert corpora[0]['text_sha256'] == hashlib.sha256(corpus.read_bytes()).hexdigest()
        assert corpora[0]['tokens'] == corpus.stat().st_size // 4 + 1
        assert corpora[0]['required_tokens'] == 131072
        inputs = [r for r in rows if r['event'] == 'input']
        samples = [r for r in rows if r['event'] == 'sample']
        assert len(inputs) == len(samples) == len(sizes)
        for n, prompt, sample in zip(sizes, inputs, samples):
            assert prompt['target_prompt_tokens'] == prompt['prompt_tokens'] == n
            assert prompt['physical_ids'] == [i % 256 for i in range(n)]
            assert sample['prefill_tokens_per_user'] == n
            assert sample['prefill_calls_per_user'] == n // chunk
            assert sample['prefill_tail_tokens'] == 0
            assert sample['output_tokens_per_user'] == 8
            assert sample['decode_single_calls'] == 8
        sources[chunk] = rows
        run(['--suite', 'report', '--input', str(output), '--output', str(temp / f'report-{chunk}')])

        # The same corpus supports a fixed new prefill interval at depth.
        output = temp / f'interval-{chunk}.jsonl'
        run(['--suite', 'single', '--model', ':fixture:', '--prompt-file', str(corpus),
             '--output', str(output), '--pp', str(chunk), '--depths', f'0,{chunk},{131072-chunk}',
             '--tg', '8', '--warmups', '0', '--context-capacity', '133760'])
        rows = [json.loads(line) for line in output.read_text().splitlines()]
        assert rows[0]['prefill_chunk'] == chunk
        for sample in (r for r in rows if r['event'] == 'sample'):
            assert sample['prefill_tokens_per_user'] == chunk
            assert sample['prefill_calls_per_user'] == 1 and sample['prefill_tail_tokens'] == 0
            assert sample['prompt_tokens'] == sample['depth'] + chunk

        # Reject unsupported grids before opening a model or producing evidence.
        for number in (chunk - 1, chunk + 1, 130925):
            output = temp / f'reject-{chunk}-{number}.jsonl'
            run(['--suite', 'fresh', '--model', ':load-failure:', '--prompt-file', str(corpus),
                 '--output', str(output), '--sizes', str(number), '--prefill-chunk', str(chunk)], 2)
            assert not output.exists()

    # Missing/short inputs must not become invented padding or partial samples.
    short = temp / 'short.txt'
    short.write_text('A short corpus.\n')
    output = temp / 'short.jsonl'
    run(['--suite', 'fresh', '--model', ':fixture:', '--prompt-file', str(short),
         '--output', str(output), '--sizes', '2048', '--warmups', '0'], 1)
    rows = [json.loads(line) for line in output.read_text().splitlines()]
    assert rows[-1]['event'] == 'failed'
    assert not any(r['event'] in ('input', 'sample') for r in rows)
    assert 'need at least 2048' in rows[-1]['error']

    output = temp / 'no-file.jsonl'
    run(['--suite', 'fresh', '--model', ':load-failure:', '--output', str(output)], 2)
    assert not output.exists()

    # Replay/report must independently reject altered settings and counters.
    for index, (kind, key, value) in enumerate([
        ('input', 'target_prompt_tokens', 2049),
        ('sample', 'prefill_calls_per_user', 2),
        ('sample', 'prefill_tail_tokens', 1),
    ]):
        rows = copy.deepcopy(sources[2048])
        next(r for r in rows if r['event'] == kind)[key] = value
        output = temp / f'tampered-{index}.jsonl'
        output.write_text(''.join(json.dumps(r) + '\n' for r in rows))
        run(['--suite', 'report', '--input', str(output), '--output', str(temp / f'tampered-report-{index}')], 1)

print(json.dumps({'state': 'PASS', 'cli_invocations': checks,
                  'chunks': [2048, 4096, 8192], 'maximum_prompt_tokens': 131072,
                  'synthetic': True, 'model_inference': False}))
