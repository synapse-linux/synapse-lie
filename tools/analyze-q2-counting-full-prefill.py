#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Keep every sample; compare chunk sizes only at the same full counting input."""
import csv
import hashlib
import json
from pathlib import Path
import statistics
import struct

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT/'evidence/q2-counting-full-prefill-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan_path = ROOT/'config/q2-counting-full-prefill-plan.json'
    plan = json.loads(plan_path.read_text())
    summary = json.loads((EVIDENCE/'results/native-result.json').read_text())
    assert summary['state'] == 'COMPLETE' and summary['plan_sha256'] == sha(plan_path)
    rows, inputs, arms = [], {}, []
    for i, arm in enumerate(plan['order']):
        path = EVIDENCE/f'results/{i:02d}-{arm}.jsonl'
        records = [json.loads(line) for line in path.read_text().splitlines()]
        assert records[-1] == {'event':'complete','exit_code':0}
        identity = records[0]
        assert identity['suite'] == 'fresh' and identity['synthetic'] is False
        assert identity['measurement_contract'] == 'full-prefill-v1'
        assert identity['prompt_contract'] == 'exact-counting-chat-v1'
        assert identity['warmups'] == 1 and identity['repetitions'] == 3
        prompt, = [r for r in records if r['event'] == 'input']
        source, = [r for r in records if r['event'] == 'prompt_source']
        samples = [r for r in records if r['event'] == 'sample']
        assert len(samples) == 4 and [r['warmup'] for r in samples] == [1,0,0,0]
        n, chunk = prompt['prompt_tokens'], identity['prefill_chunk']
        ids = prompt['physical_ids']
        digest = hashlib.sha256(struct.pack('<'+'i'*len(ids),*ids)).hexdigest()
        assert digest == prompt['physical_ids_sha256'] == source['physical_ids_sha256']
        assert len(ids) == n == prompt['target_prompt_tokens'] and not n % chunk
        assert inputs.setdefault(n,ids) == ids
        if n == 2048:
            assert digest == '75343e606f5b815fe01f69ddc6ce50a997e2de96d8a20304a82a7f24f1180b35'
        for rep, sample in enumerate(samples):
            assert sample['depth'] == sample['cache_tokens'] == 0
            assert sample['prefill_tokens_per_user'] == n and sample['prefill_calls_per_user'] == n//chunk
            assert sample['prefill_tail_tokens'] == 0
            elapsed = sample['prefill_end_monotonic_ns']-sample['prefill_begin_monotonic_ns']
            assert elapsed == sample['prefill_ns'] and elapsed > 0
            pp = n*1e9/elapsed
            assert abs(pp-sample['prefill_tps']) < 1e-7
            assert sample['decode_single_calls'] == sample['output_tokens_per_user'] == 128
            rows.append(dict(arm=arm,prompt_tokens=n,chunk=chunk,
                             context_capacity=prompt['context_capacity'],rep=rep,warmup=bool(sample['warmup']),
                             prefill_calls=n//chunk,prefill_seconds=elapsed/1e9,prefill_tps=pp,
                             decode_seconds=sample['decode_ns']/1e9,decode_tps=sample['decode_tps'],
                             output_tokens=128,physical_ids_sha256=digest))
        measured=[r for r in rows if r['arm']==arm and not r['warmup']]
        arms.append(dict(arm=arm,prompt_tokens=n,chunk=chunk,context_capacity=prompt['context_capacity'],
                         prefill_median_tps=statistics.median(r['prefill_tps'] for r in measured),
                         decode_median_tps=statistics.median(r['decode_tps'] for r in measured),
                         prefill_seconds=[r['prefill_seconds'] for r in measured],
                         prefill_tps=[r['prefill_tps'] for r in measured],
                         decode_tps=[r['decode_tps'] for r in measured],output_ids=samples[1]['output_ids']))
    result=dict(schema='synapse-lie.q2-counting-full-prefill-results.v1',plan_sha256=sha(plan_path),
                binary_sha256=plan['staged_sha256']['synapse-lie-bench'],scope='entire prompt from empty sequence',
                old_reference_replaced=False,full_128k_curve=False,
                outputs_equal_across_arms=all(a['output_ids']==arms[0]['output_ids'] for a in arms),
                arms=arms,samples=rows)
    (ROOT/'config/q2-counting-full-prefill-results.json').write_text(json.dumps(result,indent=2)+'\n')
    with (ROOT/'docs/figures/q2-counting-full-prefill.csv').open('w') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
    lines=['<!-- SPDX-License-Identifier: MIT -->','','# Focused full-prefill counting diagnostic','',
           'Original Q2 on .157, IOMMU enabled, retained numerical provider, C1 greedy AR.',
           'Each sample includes all prompt tokens between its initial/final monotonic timestamps.',
           'One warmup and three measured repetitions per arm; no per-repetition pause.',
           'At a common prompt length all physical IDs are identical. TG uses 128 completed calls.',
           'This is a focused subset, not the pending complete curve through 128K.', '',
           '| Prompt | Chunk | Allocated context | PP samples (token/s) | Full PP elapsed (s) | TG samples (token/s) |',
           '| ---: | ---: | ---: | --- | --- | --- |']
    for arm in arms:
        lines.append('| '+f"{arm['prompt_tokens']} | {arm['chunk']} | {arm['context_capacity']} | "+
                     ', '.join(f'{n:.2f}' for n in arm['prefill_tps'])+' | '+
                     ', '.join(f'{n:.6f}' for n in arm['prefill_seconds'])+' | '+
                     ', '.join(f'{n:.2f}' for n in arm['decode_tps'])+' |')
    lines+=['','All warmup/measured samples and phase durations are in the [CSV](figures/q2-counting-full-prefill.csv).',
            'All 128-token continuations match across the five arms. Different prefill',
            'chunk boundaries produce different logits hashes; this counting task does',
            'not establish broad task-quality or numerical equivalence.',
            'At the same 8192-token input, larger chunks are slower in all three measured',
            'samples. Allocating 133760 instead of 9216 tokens does not reproduce the',
            'large earlier discrepancy on the 2048-token counting input. These findings',
            'do not isolate the cause of the raw-corpus result or establish long-context rates.',
            'The 923 GPU functions are unchanged: this is a corrected workload comparison,',
            'not a measured numerical-kernel optimization.', '',
            'The old 1587.893545 observation is preserved on its own harness: it includes',
            '15-second pauses, a different numerical-provider revision, and 127 timed decode forwards.',
            'No strict historical performance delta or quality equivalence is claimed.',
            '[Measurement correction and source references](Q2-BENCHMARK-CORRECTION.md).', '',
            'Run 2026-10-08 00:20:53–00:25:04 UTC; all five children and runner exit 0.',
            'All 71 artifacts verify before release at 00:26:00; strong closure at 00:26:28',
            'finds 63 retired process/group identities, empty KFD, five free original leases',
            'and unchanged model stats. CPU peak 90.875 C; IOMMU remains enabled.',
            'Release SHA-256: `d5be8bf0bcff502102dbaf6d89995d236ad46796ac927b3ac3ad0ef74fc7eda9`.',
            'No remote cleanup, model mutation, reboot or tuning occurred.','']
    (ROOT/'docs/Q2-COUNTING-FULL-PREFILL.md').write_text('\n'.join(lines))
    print(json.dumps({k:v for k,v in result.items() if k not in ('samples','arms')}))
    for arm in arms:
        print(json.dumps({k:v for k,v in arm.items() if k!='output_ids'}))


if __name__ == '__main__':
    main()
