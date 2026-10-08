#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare every matched ON/OFF sample after the two complete curve audits."""
import csv
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARMS = (('q2', 2048), ('ud', 2048), ('q2', 4096), ('q2', 8192))


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cohort(suffix):
    prefix = 'q2-counting-curve128'+suffix
    path = ROOT/'config'/(prefix+'-results.json')
    result = read(path)
    plan_path = ROOT/'config'/(prefix+'-plan.json')
    plan = read(plan_path)
    assert result['plan_sha256'] == sha(plan_path)
    assert result['full_128k_curve'] and result['measured_points'] == 176
    assert result['total_samples'] == 352
    assert result['shared_physical_inputs_identical']
    outputs = {}
    for name, digest in result['source_evidence_sha256'].items():
        raw = ROOT/name
        assert sha(raw) == digest
        records = [json.loads(line) for line in raw.read_text().splitlines()]
        model = 'ud' if '-ud-' in raw.name else 'q2'
        chunk = records[0]['prefill_chunk']
        for row in records:
            if row['event'] == 'sample':
                key = (model, chunk, row['prompt_tokens'], row['rep'])
                assert key not in outputs
                outputs[key] = row['output_ids']
    base = ROOT/'evidence'/(prefix+'-r1')
    host = read(base/'results/host-configuration.json')
    off = 'amd_iommu=off' in host['cmdline'].split()
    assert off == bool(suffix)
    assert (host['iommu_groups'] == 0) == off
    rows = {(r['model'], r['prefill_chunk'], r['prompt_tokens'], r['repetition']): r
            for r in result['samples']}
    assert len(rows) == len(outputs) == 352
    return dict(plan=plan, result=result, rows=rows, outputs=outputs,
                result_sha256=sha(path), base=base)


def main():
    on, off = cohort(''), cohort('-off')
    assert off['plan']['control_plan_sha256'] == on['result']['plan_sha256']
    assert on['result']['binary_sha256'] == off['result']['binary_sha256']
    assert on['rows'].keys() == off['rows'].keys()
    for key in ('order', 'output_tokens', 'warmups', 'repetitions', 'context_capacity',
                'prompt_limit', 'arm_timeout_seconds', 'total_points', 'total_samples'):
        assert on['plan'][key] == off['plan'][key], key
    for a, b in zip(on['plan']['model_stats'], off['plan']['model_stats'], strict=True):
        assert {k:v for k,v in a.items() if k != 'device'} == {k:v for k,v in b.items() if k != 'device'}
    for index, (model, chunk) in enumerate(ARMS):
        tag = f'{index:02d}-{model}-c{chunk}'
        commands = []
        for c in (on, off):
            child = read(c['base']/'results'/(tag+'.child.json'))
            assert child['exit_code'] == 0
            argv = list(child['argv'])
            argv[0] = Path(argv[0]).name
            for flag in ('--output', '--graphs'):
                i = argv.index(flag)+1
                argv[i] = Path(argv[i]).name
            commands.append(argv)
        assert commands[0] == commands[1], tag
    rows = []
    for key, a in on['rows'].items():
        b = off['rows'][key]
        for field in ('model', 'prefill_chunk', 'prompt_tokens', 'context_capacity',
                      'repetition', 'warmup', 'prefill_calls', 'physical_ids_sha256'):
            assert a[field] == b[field], (key, field)
        row = {field: a[field] for field in ('model', 'prefill_chunk', 'prompt_tokens',
               'repetition', 'warmup', 'physical_ids_sha256')}
        row['output_ids_equal'] = on['outputs'][key] == off['outputs'][key]
        for state, sample in (('on', a), ('off', b)):
            row['output_tokens_'+state] = sample['output_tokens']
            for phase in ('prefill', 'decode'):
                row[phase+'_tps_'+state] = sample[phase+'_tps']
                row[phase+'_seconds_'+state] = sample[phase+'_seconds']
        for phase in ('prefill', 'decode'):
            row[phase+'_delta_percent'] = (b[phase+'_tps']/a[phase+'_tps']-1)*100
        rows.append(row)
    measured = [r for r in rows if not r['warmup']]
    assert len(measured) == 176
    result = dict(schema='synapse-lie.q2-iommu-comparison.v1', measured_points=176,
                  total_matched_samples=352, binary_sha256=on['result']['binary_sha256'],
                  on_analysis_sha256=on['result_sha256'], off_analysis_sha256=off['result_sha256'],
                  all_physical_inputs_identical=True, all_normalized_commands_identical=True,
                  measured_output_differences=sum(not r['output_ids_equal'] for r in measured),
                  warmup_output_differences=sum(not r['output_ids_equal'] for r in rows if r['warmup']),
                  samples=rows)
    (ROOT/'config/q2-iommu-comparison-results.json').write_text(json.dumps(result, indent=2)+'\n')
    destination = ROOT/'docs/figures/q2-iommu-comparison.csv'
    with destination.open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)
    config = ROOT/'.deps/q2-curve128-matplotlib'
    config.mkdir(parents=True, exist_ok=True)
    os.environ['MPLCONFIGDIR'] = str(config)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(4, 2, figsize=(13, 13), layout='constrained')
    lines = ['<!-- SPDX-License-Identifier: MIT -->', '', '# Complete IOMMU ON/OFF comparison through 128K', '',
             'All 176 requested points are matched using the same retained native executable and model files.',
             'Exact repeated counting prompts, every intermediate multiple, complete prefill from empty sequence state.',
             'Identical arm order, capacity133760, C1 reactive greedy AR, MTP off, TG128, warm1 + measured1.',
             'The model remains loaded throughout each curve; every point starts empty. No inserted pauses.',
             'Performance120W, fan82 and thermal gates are unchanged; IOMMU differs across the two boots.',
             'PP and TG rates are token/s; delta is (OFF / ON - 1) × 100.',
             'One measured repetition per point is retained: these differences do not establish run-to-run variance.',
             'Counting continuation agreement does not establish broad model quality.', '',
             f"Measured output differences: {result['measured_output_differences']}/176; warmup differences: {result['warmup_output_differences']}/176.", '',
             '[ON full table](Q2-COUNTING-CURVE128.md), [OFF full table](Q2-COUNTING-CURVE128-OFF.md),',
             '[all samples and complete phase durations (CSV)](figures/q2-iommu-comparison.csv).', '']
    for index, (model, chunk) in enumerate(ARMS):
        points = [r for r in measured if r['model'] == model and r['prefill_chunk'] == chunk]
        assert [r['prompt_tokens'] for r in points] == list(range(chunk, 131073, chunk))
        label = f'{model.upper()} chunk {chunk//1024}K'
        lines += [f'## {label}', '',
                  '| Exact prompt tokens | PP ON | PP OFF | PP delta % | TG ON | TG OFF | TG delta % |',
                  '| ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
        for row in points:
            cells = [str(row['prompt_tokens'])]
            for phase in ('prefill', 'decode'):
                cells.extend([f"{row[phase+'_tps_on']:.6f}", f"{row[phase+'_tps_off']:.6f}",
                              f"{row[phase+'_delta_percent']:+.6f}"])
            lines.append('| '+' | '.join(cells)+' |')
        lines.append('')
        for ax, phase in zip(axes[index], ('prefill', 'decode')):
            for state, style in (('on', '--'), ('off', '-')):
                ax.plot([r['prompt_tokens']/1024 for r in points],
                        [r[phase+'_tps_'+state] for r in points], style,
                        marker='.', linewidth=1.3, markersize=4, label='IOMMU '+state.upper())
            ax.set(title=label, ylabel=('Full prefill' if phase == 'prefill' else 'Decode')+' (token/s)',
                   xlabel='Exact prompt length (1024 tokens per K)', xlim=(0, 130))
            ax.grid(alpha=.25); ax.legend()
    fig.suptitle('synapse-lie-bench · .157 GPU · exact matched ON/OFF 128K curves · all 176 measured points')
    for ext in ('png', 'svg'):
        output = ROOT/'docs/figures'/('q2-iommu-comparison.'+ext)
        fig.savefig(output, dpi=160)
        if ext == 'svg':
            output.write_text('\n'.join(line.rstrip() for line in output.read_text().splitlines())+'\n')
    plt.close(fig)
    lines += ['![Matched prefill and decode curves](figures/q2-iommu-comparison.png)', '',
              '[PNG](figures/q2-iommu-comparison.png), [SVG](figures/q2-iommu-comparison.svg).', '']
    (ROOT/'docs/Q2-IOMMU-COMPARISON.md').write_text('\n'.join(lines))
    print(json.dumps({k:v for k,v in result.items() if k != 'samples'}))


if __name__ == '__main__':
    main()
