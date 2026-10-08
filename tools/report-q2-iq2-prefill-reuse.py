#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Combine audited prefill probes with the repeated reference; export all samples."""
import csv
import importlib.util
import json
import os
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location('epilogue', ROOT/'tools/analyze-q2-iq2-live-epilogue.py')
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    read, require, sha = audit.read, audit.require, audit.sha
    plan = read(ROOT/'config/q2-iq2-prefill-reuse-plan.json')
    output = ROOT/'config/q2-iq2-prefill-reuse-results.json'
    require(not output.exists(), 'Refusing to overwrite retained results')
    reports = {name: read(ROOT/f'config/q2-iq2-prefill-reuse-{name}-results.json')
               for name in ('scale', 'grid')}
    require(reports['scale']['arms']['reference'] == reports['grid']['arms']['reference'],
            'Different first references')
    arms = dict(before=reports['scale']['arms']['reference'],
                scale=reports['scale']['arms']['candidate'],
                grid=reports['grid']['arms']['candidate'])
    host = ROOT/'evidence'/plan['host']
    arms['after'] = audit.arm(ROOT/'evidence'/plan['arms'][3]['label'], False, host)
    names = list(audit.cases())
    rows, cells = [], {}
    for key, arm in arms.items():
        require(arm['weights'] == arms['before']['weights'], 'Different weights')
        for name, case in arm['cases'].items():
            require(case['geometry'] == arms['before']['cases'][name]['geometry'],
                    'Different inputs or route geometry')
            require(case['median_us'] == statistics.median(
                s['microseconds_per_call'] for s in case['samples'] if not s['warmup']),
                'Median differs from retained samples')
            for s in case['samples']:
                rows.append(dict(arm=key, case=name, sample=s['sample'], warmup=s['warmup'],
                                 calls=s['calls'], microseconds_per_call=s['microseconds_per_call']))
    inventory = audit.output_inventory()
    before = ROOT/arms['before']['directory']/'results'
    after = ROOT/arms['after']['directory']/'results'
    require({p.name for p in after.iterdir() if p.suffix in ('.f32', '.u32')} == inventory.keys(),
            'Repeated reference output inventory differs')
    repeat_pairs = {}
    for name, count in inventory.items():
        a, b = (before/name).read_bytes(), (after/name).read_bytes()
        require(len(a) == len(b) == count*4, 'Incomplete repeated reference array')
        repeat_pairs[name] = dict(exact=a == b, values=count,
                                 before_sha256=sha(before/name), after_sha256=sha(after/name))
    for name in names:
        values = {key: arm['cases'][name]['median_us'] for key, arm in arms.items()}
        cells[name] = dict(median_us=values,
            reference_drift_percent=100*(values['after']/values['before']-1),
            candidates={key: dict(time_change_vs_before_percent=100*(values[key]/values['before']-1),
                                 time_change_vs_after_percent=100*(values[key]/values['after']-1))
                        for key in ('scale', 'grid')})
    exact = all(r['exact'] for r in reports.values()) and all(p['exact'] for p in repeat_pairs.values())
    numerical = all(arm['completion']['numerical_pass'] for arm in arms.values())
    result = dict(schema='synapse-lie.q2-iq2-prefill-reuse-results.v1',
        scope='Complete component cycles with canonical routing histograms and synthetic operands',
        plan_sha256=sha(ROOT/'config/q2-iq2-prefill-reuse-plan.json'),
        audits={name: sha(ROOT/f'config/q2-iq2-prefill-reuse-{name}-results.json') for name in reports},
        arms=arms, cells=cells, repeated_reference_pairs=repeat_pairs,
        exact=exact, numerical_pass=numerical, model_inference=False,
        promoted=False, goal_met=False, samples=len(rows),
        comparison_note='Two sequential reference arms bound observed drift; this is not a confidence interval.')
    require(len(rows) == 140, 'Incomplete sample inventory')
    output.write_text(json.dumps(result, indent=2, allow_nan=False)+'\n')
    figures = ROOT/'docs/figures/q2-iq2-prefill-reuse'
    figures.mkdir(parents=True, exist_ok=True)
    with (figures/'samples.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 3, figsize=(13, 7.5))
    labels = ['Reference\nbefore', 'Scale\nreuse', 'Codebook\nLDS', 'Reference\nafter']
    titles = ['Depth 0 / layer 6 / tile 128', 'Depth 0 / layer 0 / tile 64',
              'Depth 128K / layer 16 / tile 128', 'Depth 128K / layer 6 / tile 64',
              'Full 128-row tiles / control']
    for ax, name, title in zip(axes.flat, names, titles):
        values = [cells[name]['median_us'][key]/1000 for key in arms]
        bars = ax.bar(labels, values, color=['#486fa9', '#389878', '#d18b36', '#8b65aa'])
        ax.bar_label(bars, fmt='%.3f', padding=4, fontsize=8)
        maximum = max(values)
        for i, arm in enumerate(arms.values()):
            for s in arm['cases'][name]['samples']:
                value = s['microseconds_per_call']/1000
                maximum = max(maximum, value)
                ax.scatter(i+(s['sample']-3)*.035, value, s=14,
                           facecolors='none' if s['warmup'] else '#222222', edgecolors='#222222')
        ax.set_ylim(0, maximum*1.17)
        ax.set_title(title, fontsize=10)
        ax.set_ylabel('Milliseconds / complete cycle')
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
    axes.flat[-1].axis('off')
    axes.flat[-1].text(.05, .8, 'Lower is faster.\nBars: median of five samples.\nHollow dots: two warmups.\nFilled dots: five measured samples.\nEight complete calls per sample.\n\nSynthetic weights and activations.\nRecorded short/128K routing counts.\nNo model prefill rate or parity claim.',
                       va='top', fontsize=11, linespacing=1.6)
    fig.suptitle('IQ2 prefill reuse on .157 — complete cycle, two unchanged controls')
    fig.tight_layout(rect=(0, 0, 1, .95))
    for suffix in ('svg', 'png'):
        fig.savefig(figures/f'cycles.{suffix}', dpi=150)
    svg = figures/'cycles.svg'
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines)+'\n')
    print(json.dumps(dict(exact=exact, numerical_pass=numerical, samples=len(rows), cells=cells)))
    raise SystemExit(0 if exact and numerical else 1)


if __name__ == '__main__':
    main()
