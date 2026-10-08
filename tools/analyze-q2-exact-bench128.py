#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate and publish the exact Promessi sposi curve, without old baselines."""
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/q2-exact-bench128-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan_path = ROOT / 'config/q2-exact-bench128-plan.json'
    plan = json.loads(plan_path.read_text())
    summary = json.loads((EVIDENCE / 'results/native-result.json').read_text())
    assert summary['state'] == 'COMPLETE' and summary['plan_sha256'] == sha(plan_path)
    rows, inputs, outputs, variants = [], {}, {}, {}
    for index, arm in enumerate(plan['order']):
        chunk = int(arm)
        path = EVIDENCE / f'results/{index:02d}-{arm}.jsonl'
        records = [json.loads(line) for line in path.read_text().splitlines()]
        assert records[-1] == {'event': 'complete', 'exit_code': 0}
        identity = records[0]
        assert identity['synthetic'] is False and identity['prompt_contract'] == 'exact-token-prefix-v1'
        assert identity['prefill_chunk'] == chunk and identity['suite'] == 'single'
        assert identity['warmups'] == 0 and identity['repetitions'] == 1
        corpus, = [r for r in records if r['event'] == 'corpus']
        assert corpus['text_sha256'] == plan['staged_sha256']['promessi_sposi.txt']
        prompts = [r for r in records if r['event'] == 'input']
        samples = [r for r in records if r['event'] == 'sample']
        targets = [n for n in (2048,4096,8192,16384,32768,65536,131072) if n >= chunk]
        assert len(prompts) == len(samples) == len(targets)
        for target, prompt, sample in zip(targets, prompts, samples):
            assert prompt['prompt_tokens'] == prompt['target_prompt_tokens'] == target
            assert len(prompt['physical_ids']) == target
            # Every arm uses exactly the same token prefix at a common frontier.
            previous = inputs.setdefault(target, prompt['physical_ids'])
            assert previous == prompt['physical_ids']
            assert sample['prompt_tokens'] == target and sample['depth'] == target - chunk
            assert sample['prefill_tokens_per_user'] == chunk
            assert sample['prefill_calls_per_user'] == 1 and sample['prefill_tail_tokens'] == 0
            assert sample['prefill_ns'] > 0 and sample['decode_ns'] > 0
            assert sample['output_tokens_per_user'] == sample['decode_single_calls']
            assert 0 < sample['output_tokens_per_user'] <= 128
            reference_output = outputs.setdefault(target, sample['output_ids'])
            variants[chunk,target] = sample['output_ids']
            first_difference = next((i for i,(a,b) in enumerate(zip(reference_output,sample['output_ids'])) if a!=b), None)
            pp = chunk * 1e9 / sample['prefill_ns']
            tg = sample['output_tokens_per_user'] * 1e9 / sample['decode_ns']
            assert abs(pp-sample['prefill_tps']) < 1e-7 and abs(tg-sample['decode_tps']) < 1e-7
            rows.append(dict(prompt_tokens=target, chunk=chunk, prior_tokens=target-chunk,
                             prefill_calls=1, tail_tokens=0, prefill_ns=sample['prefill_ns'],
                             prefill_tps=pp, output_tokens=sample['output_tokens_per_user'],
                             decode_ns=sample['decode_ns'], decode_tps=tg,
                             output_equal_to_2k=reference_output==sample['output_ids'],
                             first_output_difference_to_2k=first_difference))
    result = dict(schema='synapse-lie.q2-exact-bench128-results.v1',
                  comparison_status='withdrawn-for-full-prefill-and-optimization-comparisons',
                  plan_sha256=sha(plan_path), corpus_sha256=plan['staged_sha256']['promessi_sposi.txt'],
                  binary_sha256=plan['staged_sha256']['synapse-lie-bench'],
                  scope='Incremental completed final chunk at exact raw corpus frontier; preceding prefix replay outside phase timers.',
                  iommu='on', repetitions=1, warmups=0, rows=rows,
                  all_shared_frontier_ids_exact=True,
                  outputs_4k_8k_equal=all(variants[4096,n]==variants[8192,n] for n in inputs if n>=8192),
                  all_decode_budgets_completed=all(r['output_tokens']==128 for r in rows))
    (ROOT / 'config/q2-exact-bench128-results.json').write_text(json.dumps(result,indent=2)+'\n')
    with (ROOT / 'docs/figures/q2-exact-bench128.csv').open('w') as out:
        writer=csv.DictWriter(out,fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    text = ['<!-- SPDX-License-Identifier: MIT -->', '', '# Exact Promessi sposi PP/TG curves', '',
            '**Withdrawn as a full-prefill or optimization comparison (2026-10-08).**',
            'These are final-chunk timings after untimed prefix replay, on a different',
            'corpus from the retained counting reference. Exact counts do not make these',
            'scopes comparable. Preserve this historical table and its raw evidence;',
            'see [measurement correction](Q2-BENCHMARK-CORRECTION.md).', '',
            'Original Q2 on .157; IOMMU enabled; performance/120 W; C1 reactive AR.',
            'Each prefill measurement covers the final complete 2048/4096/8192-token block',
            'at the stated exact prompt frontier. Prior-prefix replay is outside PP/TG timers.',
            'One measured run per point, no warmup or averaging; all shared frontiers use identical physical IDs.',
            'Source checkpoint `032323df`; candidate binary `23b53980` reuses all 923 retained device functions.',
            'Corpus SHA-256 `'+result['corpus_sha256']+'`.', '',
            '| Prompt tokens | PP 2K | PP 4K | PP 8K | TG 2K | TG 4K | TG 8K |',
            '| ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for target in sorted(inputs):
        selected={r['chunk']:r for r in rows if r['prompt_tokens']==target}
        values=[f"{selected[c][metric]:.2f}" if c in selected else '—'
                for metric in ('prefill_tps','decode_tps') for c in (2048,4096,8192)]
        text.append('| '+str(target)+' | '+' | '.join(values)+' |')
    text += ['', 'All rates are token/s. A dash means the frontier is smaller than the chunk.',
             'TG uses actual completed tokens; requested budget is 128. Completed budgets: '+
             str(sum(r['output_tokens']==128 for r in rows))+'/'+str(len(rows))+'.', '',
             '## Output consistency', '']
    for chunk in (4096,8192):
        subset=[r for r in rows if r['chunk']==chunk]
        different=[r['prompt_tokens'] for r in subset if not r['output_equal_to_2k']]
        text.append(f"Chunk {chunk}: {len(subset)-len(different)}/{len(subset)} generated token arrays match chunk 2048; differing frontiers: {different}.")
    text += ['', 'The 4K and 8K outputs match each other at all five common frontiers: '+str(result['outputs_4k_8k_equal'])+'.',
             'Compared with 2K, the first differing token is between zero-based positions 3 and 22; all first output tokens match.',
             'Output differences are reported separately from throughput and are not an independent quality verdict.',
             'These results do not measure an engine optimization over the earlier HTTP corpus.',
             'No reference baseline is replaced, and no IOMMU-off comparison has been performed.', '',
             '[Combined PP/TG graph](figures/q2-exact-bench128.png) · [CSV](figures/q2-exact-bench128.csv) ·',
             '[Benchmark contract and command](Q2-EXACT-BENCH.md)', '',
             'Evidence: `evidence/q2-exact-bench128-r1`; plan: `config/q2-exact-bench128-plan.json`.',
             'The native executable also emits validated JSON/CSV/SVG/PNG reports for each arm.', '']
    (ROOT/'docs/Q2-EXACT-BENCH-RESULTS.md').write_text('\n'.join(text))
    print(json.dumps(dict(points=len(rows), all_decode_budgets_completed=result['all_decode_budgets_completed'])))


if __name__ == '__main__':
    main()
