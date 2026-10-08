#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate all 176 Q2/UD full-prefill points and render exact tables and PP/TG plots."""
import csv
import hashlib
import json
import os
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT/'evidence/q2-counting-curve128-r1'
ARMS = (('q2', 2048), ('ud', 2048), ('q2', 4096), ('q2', 8192))


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan_path = ROOT/'config/q2-counting-curve128-plan.json'
    plan = read(plan_path)
    summary = read(EVIDENCE/'results/native-result.json')
    assert summary['state'] == 'COMPLETE' and summary['plan_sha256'] == sha(plan_path)
    assert read(EVIDENCE/'run-command.json')['exit_code'] == 0
    assert sha(EVIDENCE/'synapse-lie-bench') == plan['staged_sha256']['synapse-lie-bench']
    rows, inputs, texts, outputs, raw_hashes = [], {}, {}, {}, {}
    for index, (model, chunk) in enumerate(ARMS):
        tag = f'{index:02d}-{model}-c{chunk}'
        path = EVIDENCE/'results'/(tag+'.jsonl')
        records = [json.loads(line) for line in path.read_text().splitlines()]
        raw_hashes[str(path.relative_to(ROOT))] = sha(path)
        assert records[-1] == {'event': 'complete', 'exit_code': 0}
        child = read(EVIDENCE/'results'/(tag+'.child.json'))
        assert child['exit_code'] == 0
        model_path = plan['model_stats'][1 if model == 'ud' else 0]['path']
        assert child['argv'][child['argv'].index('--model')+1] == model_path
        identity = records[0]
        assert identity['synthetic'] is False and identity['suite'] == 'fresh'
        assert identity['measurement_contract'] == 'full-prefill-v1'
        assert identity['prompt_contract'] == 'exact-counting-chat-v1'
        assert identity['decode_contract'] == 'completed-forward-per-emitted-token-v1'
        assert identity['execution'] == 'LIE-reactive-ready-batch'
        assert identity['mode'] == 'ar' and identity['prefill_chunk'] == chunk
        assert identity['warmups'] == identity['repetitions'] == 1
        targets = list(range(chunk, 131073, chunk))
        prompts = [r for r in records if r['event'] == 'input']
        sources = [r for r in records if r['event'] == 'prompt_source']
        samples = [r for r in records if r['event'] == 'sample']
        assert len(prompts) == len(sources) == len(targets)
        assert len(samples) == 2*len(targets)
        for point, (n, prompt, source) in enumerate(zip(targets, prompts, sources)):
            assert prompt['point'] == point and prompt['depth'] == 0 and prompt['users'] == 1
            assert prompt['prompt_tokens'] == prompt['target_prompt_tokens'] == n
            assert prompt['context_capacity'] == 133760 and len(prompt['physical_ids']) == n
            ids = struct.pack('<'+'i'*n, *prompt['physical_ids'])
            digest = hashlib.sha256(ids).hexdigest()
            assert digest == prompt['physical_ids_sha256'] == source['physical_ids_sha256']
            assert inputs.setdefault(n, digest) == digest
            assert texts.setdefault(n, source['text_sha256']) == source['text_sha256']
            if n == 2048:
                assert digest == '75343e606f5b815fe01f69ddc6ce50a997e2de96d8a20304a82a7f24f1180b35'
            pair = [s for s in samples if s['point'] == point]
            assert len(pair) == 2 and [s['warmup'] for s in pair] == [1, 0]
            for rep, sample in enumerate(pair):
                assert sample['rep'] == rep and sample['users'] == 1
                assert sample['depth'] == sample['cache_tokens'] == 0
                assert sample['prefill_tokens_per_user'] == n
                assert sample['prefill_calls_per_user'] == n//chunk and sample['prefill_tail_tokens'] == 0
                assert sample['finite_frontiers'] == 1
                emitted = sample['output_tokens_per_user']
                assert 0 < emitted <= 128 and emitted == sample['decode_single_calls']
                assert len(sample['output_ids']) == emitted
                assert sample['full_output_budget'] == int(emitted == 128)
                values = {}
                for phase, count in [('prefill', n), ('decode', emitted)]:
                    elapsed = sample[phase+'_end_monotonic_ns']-sample[phase+'_begin_monotonic_ns']
                    assert elapsed == sample[phase+'_ns'] and elapsed > 0
                    rate = count*1e9/elapsed
                    assert abs(rate-sample[phase+'_tps']) < 1e-7
                    values[phase+'_seconds'] = elapsed/1e9
                    values[phase+'_tps'] = rate
                rows.append(dict(model=model, prompt_tokens=n, prefill_chunk=chunk, context_capacity=133760,
                                 repetition=rep, warmup=bool(sample['warmup']),
                                 prefill_calls=n//chunk, output_tokens=emitted,
                                 full_output_budget=bool(sample['full_output_budget']),
                                 physical_ids_sha256=digest, **values))
                if not sample['warmup']:
                    outputs[(n, model, chunk)] = sample['output_ids']
    measured = [row for row in rows if not row['warmup']]
    assert len(measured) == 176 and len(rows) == 352
    output_differences = []
    for (n, model, chunk), ids in outputs.items():
        if (model, chunk) != ('q2', 2048) and ids != outputs[(n, 'q2', 2048)]:
            output_differences.append(dict(model=model, prompt_tokens=n, chunk=chunk))
    result = dict(schema='synapse-lie.q2-counting-curve128-analysis.v1',
                  plan_sha256=sha(plan_path), binary_sha256=plan['staged_sha256']['synapse-lie-bench'],
                  full_128k_curve=True, measured_points=176, total_samples=352,
                  original_reference_replaced=False, source_evidence_sha256=raw_hashes,
                  shared_physical_inputs_identical=True,
                  full_output_budget_points=sum(row['full_output_budget'] for row in measured),
                  output_differences_from_chunk2048=output_differences, samples=rows)
    (ROOT/'config/q2-counting-curve128-results.json').write_text(json.dumps(result, indent=2)+'\n')
    with (ROOT/'docs/figures/q2-counting-curve128.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    plot_config = ROOT/'.deps/q2-curve128-matplotlib'
    plot_config.mkdir(parents=True, exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(plot_config)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True, layout='constrained')
    for model, chunk in ARMS:
        points = [r for r in measured if r['model'] == model and r['prefill_chunk'] == chunk]
        x = [r['prompt_tokens']/1024 for r in points]
        for ax, metric in zip(axes, ('prefill_tps', 'decode_tps')):
            ax.plot(x, [r[metric] for r in points], marker='.', markersize=5,
                    linewidth=1.4, linestyle='--' if model=='ud' else '-',
                    label=f'{model.upper()} chunk {chunk//1024}K')
    axes[0].set(ylabel='Full prefill (token/s)', title='Q2 and UD: exact counting prompts, full prefill from empty state')
    axes[1].set(ylabel='Decode (token/s)', xlabel='Exact prompt length (1024 tokens per K)')
    for ax in axes:
        ax.grid(True, alpha=.25); ax.legend(); ax.set_xlim(0, 130)
    axes[1].set_xticks([2, 8, 16, 32, 48, 64, 80, 96, 112, 128])
    fig.suptitle('synapse-lie-bench · .157 GPU · IOMMU enabled · C1 greedy AR · warm1 + measured1')
    for extension in ('png', 'svg'):
        fig.savefig(ROOT/'docs/figures'/('q2-counting-curve128.'+extension), dpi=160)
    plt.close(fig)
    lookup = {(r['prompt_tokens'], r['model'], r['prefill_chunk']): r for r in measured}
    lines = ['<!-- SPDX-License-Identifier: MIT -->', '', '# Complete Q2 and UD full-prefill curves through 128K', '',
             'All 176 requested points complete on the .157 GPU with IOMMU enabled: 112 Q2 and 64 UD.',
             'Retained numerical executable; exact repeated counting chat; capacity 133760;',
             'C1 reactive greedy AR, MTP off, no prefix-cache restore, TG limit 128.',
             'One warmup and one measured repetition per point, with no inserted pause.',
             'Each point starts empty and times all its chunks between initial/final monotonic timestamps.',
             'Each model stays loaded through its curve. Q2 chunks: 2048/4096/8192; UD chunk: 2048.',
             'A dash means that prompt length is not a multiple of the corresponding chunk size.', '',
             '| Exact prompt tokens | Q2 PP2K | Q2 TG2K | UD PP2K | UD TG2K | Q2 PP4K | Q2 TG4K | Q2 PP8K | Q2 TG8K |',
             '| ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for n in range(2048, 131073, 2048):
        cells = [str(n)]
        for model, chunk in ARMS:
            r = lookup.get((n, model, chunk))
            cells.extend([f"{r['prefill_tps']:.6f}", f"{r['decode_tps']:.6f}"] if r else ['—', '—'])
        lines.append('| '+' | '.join(cells)+' |')
    lines += ['', 'All rates are token/s. [Exact CSV with complete phase durations and warmups](figures/q2-counting-curve128.csv).',
              f"Full TG128 measured points: {result['full_output_budget_points']}/176.",
              f"UD or larger-chunk measured continuations differing from Q2 chunk2K at the same input: {len(output_differences)}.",
              'Identical physical inputs are verified at every common prompt length.',
              'Counting continuations alone do not establish broad model quality or numerical equivalence.',
              'Historical fixed-2K and incremental/cached-depth results remain separate, unchanged records.', '',
              '![Full-prefill and decode curves](figures/q2-counting-curve128.png)', '',
              '[PNG](figures/q2-counting-curve128.png), [SVG](figures/q2-counting-curve128.svg).', '']
    (ROOT/'docs/Q2-COUNTING-CURVE128.md').write_text('\n'.join(lines))
    print(json.dumps({k: v for k, v in result.items() if k != 'samples'}))


if __name__ == '__main__':
    main()
