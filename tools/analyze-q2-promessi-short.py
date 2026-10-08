#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit and report every retained sample from the requested four-point run."""
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'evidence/q2-promessi-short-r1'
PREP = ROOT/'evidence/q2-promessi-short-preparation'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan_path = ROOT/'config/q2-promessi-short-plan.json'
    plan = read(plan_path)
    collection = read(PREP/'collection.json')
    for name, item in collection['files'].items():
        path = BASE/name
        assert path.stat().st_size == item['bytes'] and sha(path) == item['sha256'], name
    assert read(BASE/'run-command.json')['exit_code'] == 0
    assert read(BASE/'results/00-q2-c2048.child.json')['exit_code'] == 0
    assert read(BASE/'results/native-result.json')['state'] == 'COMPLETE'
    assert sha(BASE/'synapse-lie-bench') == plan['staged_sha256']['synapse-lie-bench']
    strong = read(BASE/'strong-closure.json')
    assert strong['kfd_empty'] and strong['original_five_leases_free'] and not strong['gpu_reserved']
    assert strong['release_sha256'] == sha(BASE/'release.json')
    assert 'amd_iommu=off' in read(BASE/'results/host-configuration.json')['cmdline'].split()
    source = BASE/'results/00-q2-c2048.jsonl'
    records = [json.loads(line) for line in source.read_text().splitlines()]
    identity = records[0]
    assert records[-1] == {'event': 'complete', 'exit_code': 0}
    assert identity['synthetic'] is False and identity['suite'] == 'fresh'
    assert identity['measurement_contract'] == 'full-prefill-v1'
    assert identity['prompt_contract'] == 'exact-token-prefix-v1'
    assert identity['prefill_chunk'] == 2048 and identity['timing_clock'] == 'CLOCK_MONOTONIC'
    corpus = next(r for r in records if r['event'] == 'corpus')
    assert corpus['text_sha256'] == sha(BASE/'promessi_sposi.txt') == plan['staged_sha256']['promessi_sposi.txt']
    inputs = [r for r in records if r['event'] == 'input']
    samples = [r for r in records if r['event'] == 'sample']
    assert [r['prompt_tokens'] for r in inputs] == [2048, 4096, 6144, 8192]
    assert len(samples) == 8
    rows = []
    for point, prompt in enumerate(inputs):
        n = prompt['prompt_tokens']
        ids = prompt['physical_ids']
        assert prompt['target_prompt_tokens'] == n == len(ids)
        assert prompt['context_capacity'] == 133760 and prompt['depth'] == 0
        assert ids == inputs[-1]['physical_ids'][:n]
        assert hashlib.sha256(struct.pack('<'+'i'*n, *ids)).hexdigest() == prompt['physical_ids_sha256']
        pair = [r for r in samples if r['point'] == point]
        assert [(r['rep'], r['warmup']) for r in pair] == [(0, 1), (1, 0)]
        for sample in pair:
            assert sample['prompt_tokens'] == sample['prefill_tokens_per_user'] == n
            assert sample['depth'] == sample['cache_tokens'] == sample['prefill_tail_tokens'] == 0
            assert sample['prefill_calls_per_user'] == n//2048
            assert sample['output_tokens_per_user'] == sample['decode_single_calls'] == len(sample['output_ids']) == 128
            row = dict(prompt_tokens=n, warmup=sample['warmup'], repetition=sample['rep'],
                       prefill_calls=n//2048, output_tokens=128, physical_ids_sha256=prompt['physical_ids_sha256'])
            for phase, tokens in [('prefill', n), ('decode', 128)]:
                ns = sample[phase+'_ns']
                assert ns > 0 and ns == sample[phase+'_end_monotonic_ns']-sample[phase+'_begin_monotonic_ns']
                rate = sample[phase+'_tps']
                assert math.isfinite(rate) and math.isclose(rate, tokens*1e9/ns, rel_tol=1e-12)
                row[phase+'_seconds'] = ns/1e9
                row[phase+'_tps'] = rate
            rows.append(row)
    result = dict(schema='synapse-lie.q2-promessi-short-results.v1', state='COMPLETE_RELEASED',
                  plan_sha256=sha(plan_path), binary_sha256=sha(BASE/'synapse-lie-bench'),
                  source_sha256=sha(source), identity=identity, corpus=corpus,
                  measured_points=4, total_samples=8, exact_prefixes=True, all_full_output_budget=True,
                  strong_closure=strong, samples=rows)
    (ROOT/'config/q2-promessi-short-results.json').write_text(json.dumps(result, indent=2)+'\n')
    destination = ROOT/'docs/figures/q2-promessi-short.csv'
    with destination.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    lines = ['<!-- SPDX-License-Identifier: MIT -->', '', '# Q2 with I promessi sposi: exact 2K through 8K', '',
             'Requested GPU .157 test, 2026-10-08; IOMMU off. Native child and runner exit0.',
             'Original raw book text, starting with the title and introduction; exact prefixes of one tokenized corpus.',
             'Chunk2048, capacity133760, C1 reactive greedy AR, MTP off, TG128, warm1 + measured1.',
             'Every sample starts with an empty sequence and times the complete prefill across all chunks.',
             'Loading, tokenization and sequence allocation occur outside the prefill interval.',
             'One model load serves all four points. No inserted pauses or prefix-cache restoration.',
             'One measured repetition per point; every warmup is reported separately below.', '',
             f"Corpus: {corpus['bytes']} bytes, {corpus['tokens']} raw tokens, SHA256 `{corpus['text_sha256']}`.", '',
             '[Frozen plan](../config/q2-promessi-short-plan.json), [validated results](../config/q2-promessi-short-results.json),',
             '[all eight samples with full precision (CSV)](figures/q2-promessi-short.csv).', '']
    for warmup, title in [(0, 'Measured samples'), (1, 'Warmup samples')]:
        lines += [f'## {title}', '',
                  '| Exact prompt tokens | Prefill calls | PP token/s | Full PP seconds | TG token/s | TG seconds | Output tokens |',
                  '| ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
        for row in rows:
            if row['warmup'] == warmup:
                lines.append(f"| {row['prompt_tokens']} | {row['prefill_calls']} | {row['prefill_tps']:.6f} | {row['prefill_seconds']:.9f} | {row['decode_tps']:.6f} | {row['decode_seconds']:.9f} | {row['output_tokens']} |")
        lines.append('')
    os.environ['MPLCONFIGDIR'] = str(ROOT/'.deps/q2-curve128-matplotlib')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    figure, axes = plt.subplots(1, 2, figsize=(12, 4), layout='constrained')
    for axis, phase in zip(axes, ('prefill', 'decode')):
        for warmup, label, color, style in [(0, 'Measured sample', '#1769aa', '-'),
                                          (1, 'Warmup', '#777777', '--')]:
            points = [r for r in rows if r['warmup'] == warmup]
            axis.plot([r['prompt_tokens'] for r in points], [r[phase+'_tps'] for r in points],
                      style, marker='o', color=color, label=label)
        axis.set(xlabel='Exact prompt tokens', ylabel=phase.capitalize()+' (token/s)',
                 xticks=[2048, 4096, 6144, 8192], ylim=(0, None))
        axis.grid(alpha=.25); axis.legend()
    figure.suptitle('Q2 · I promessi sposi · .157 GPU · chunk 2048 · IOMMU OFF · all eight samples')
    for extension in ('png', 'svg'):
        path = ROOT/'docs/figures'/('q2-promessi-short.'+extension)
        figure.savefig(path, dpi=160)
        if extension == 'svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    plt.close(figure)
    lines += ['![Every measured and warmup PP/TG sample](figures/q2-promessi-short.png)', '',
              'The remaining counting-prompt curves were stopped at the owner\'s request; they are not resumed by this test.',
              '[Stopped campaign](Q2-IOMMU-COMPARISON.md).', '']
    (ROOT/'docs/Q2-PROMESSI-SHORT.md').write_text('\n'.join(lines))
    print(json.dumps({k:v for k,v in result.items() if k not in ('samples', 'identity')}))


if __name__ == '__main__':
    main()
