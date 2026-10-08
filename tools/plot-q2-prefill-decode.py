#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export measured PP/TG without joining the fixed TG128 and full-prefix TG8 scopes."""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/figures/q2-full-prefill128'
REPORT = ROOT / 'config/q2-full-prefill128-decode-results.json'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def semantic(request):
    return {k: v for k, v in request.items() if k not in ('stream', 'stream_options')}


def decode(sample, tokens):
    timing = sample['server_timings']
    require(sample['request']['max_tokens'] == 8 and
            sample['usage']['completion_tokens'] == 8 and
            sample['usage']['prompt_tokens'] == tokens and
            sample['full_output_budget'] and sample['finish_reason'] == 'length',
            'Incomplete or different output budget')
    require(timing['valid'] and timing['scope'] == 'synchronous_executor_calls' and
            timing['decode_mode'] == 'ar' and timing['cached_tokens'] == 0 and
            timing['prefill_tokens'] == tokens and
            timing['decode_tokens'] == timing['decode_calls'] == 8 and
            math.isfinite(timing['decode_ms']) and timing['decode_ms'] > 0,
            'Decode count, phase or timer differs')
    seconds = timing['decode_ms'] / 1000
    rate = 8 / seconds
    require(math.isclose(rate, timing['decode_tokens_per_second'], rel_tol=1e-12),
            'Reported decode rate differs from count/time')
    return seconds, rate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--redraw', action='store_true',
                        help='Redraw derived figures only after verifying the saved report and CSVs.')
    args = parser.parse_args()
    targets = [REPORT, OUT / 'pp-tg.csv', OUT / 'fixed-2k-pp-tg.csv',
               OUT / 'pp-tg.png', OUT / 'pp-tg.svg']
    require(all(p.exists() for p in targets) if args.redraw else not any(p.exists() for p in targets),
            'Redraw requires complete exports; initial export requires unused paths')
    pp_path = ROOT / 'config/q2-full-prefill128-results.json'
    pp = read(pp_path)
    history = read(ROOT / 'config/q2-historical-full-prefill.json')
    sources = {str(pp_path.relative_to(ROOT)): sha(pp_path)}
    current = {}
    for cohort in pp['cohorts']:
        path = ROOT / 'evidence' / cohort['label'] / 'results/full-prefill.jsonl'
        require(sha(path) == cohort['samples_sha256'], 'Current raw data changed')
        sources[str(path.relative_to(ROOT))] = sha(path)
        for line in path.read_text().splitlines():
            event = json.loads(line)
            if event['event'] == 'sample' and '-prefix-' in event['case']:
                key = event['usage']['prompt_tokens']
                require(key not in current, 'Ambiguous current prefix')
                current[key] = event
    historical = {}
    for arm, artifact in history['artifacts'].items():
        path = ROOT / artifact['path']
        require(sha(path) == artifact['sha256'], 'Historical raw data changed')
        sources[artifact['path']] = sha(path)
        historical[arm] = {}
        for line in path.read_text().splitlines():
            event = json.loads(line)
            if event.get('phase') == 'prefix':
                key = (event['depth'], event['attempt'])
                require(key not in historical[arm], 'Ambiguous historical prefix')
                historical[arm][key] = event['observation']

    rows = []
    for old_row in pp['rows']:
        row = dict(old_row, context_capacity=133760, output_tokens=8, decode_calls=8)
        sample = current[row['tokens']]
        row['current_decode_seconds'], row['current_decode_tps'] = decode(sample, row['tokens'])
        for arm in ('before', 'after', 'ud'):
            old = historical[arm][(row['depth'], row['attempt'])]
            require(semantic(old['request']) == semantic(sample['request']),
                    'Model messages or generation settings differ')
            row[arm + '_decode_seconds'], row[arm + '_decode_tps'] = decode(old, row['tokens'])
        rows.append(row)
    require(len(rows) == len(current) == 8, 'Missing full-prefix observations')

    fixed_path = ROOT / 'config/q2-fixed-prefill-reference.json'
    model_path = ROOT / 'config/q2-iq2-fixed-bounds-model-results.json'
    fixed = read(fixed_path)
    model = read(model_path)
    for path in (fixed_path, model_path):
        sources[str(path.relative_to(ROOT))] = sha(path)
    require(fixed['protocol']['context_capacity'] == 9216 and
            fixed['protocol']['physical_prompt_tokens'] == 2048 and
            fixed['protocol']['output_tokens'] == 128 and
            fixed['protocol']['timed_decode_calls'] == 127,
            'Fixed reference conditions changed')
    fixed_rows = []
    for label, measurement in (
        ('Initial Q2', fixed['arms']['mixed']['measurements']),
        ('Latest Q2', model['model']['measurements']),
        ('UD', fixed['arms']['ud']['measurements']),
    ):
        fixed_rows.append(dict(label=label, tokens=2048, context_capacity=9216,
                               output_tokens=128, decode_calls=127,
                               prefill_tps=measurement['prefill_tok_s']['median'],
                               decode_tps=measurement['decode_steps_s']['median'],
                               prefill_seconds=measurement['prefill_s']['median'],
                               decode_seconds=measurement['decode_s']['median']))

    report = dict(schema='synapse-lie.q2-full-prefill128-decode.v1', rows=rows,
                  fixed_reference=fixed_rows, sources=sources,
                  new_gpu_run=False, new_measurements=False,
                  curve_TG128_available=False,
                  limits='The long-prefix curve has eight output tokens and eight timed decode calls per request. '
                         'The separate fixed 2K reference retains its original TG128/127-call observations and aggregation. '
                         'Archived references; SSE differs from historical JSON prefix transport. '
                         '64K/128K used separate cooled sessions. The low saved UD TG8 at64K is retained without smoothing. '
                         'No TG128 curve, stable speedup, or quality conclusion follows.')

    exports = (('pp-tg.csv', rows), ('fixed-2k-pp-tg.csv', fixed_rows))
    if args.redraw:
        require(read(REPORT) == report, 'Saved report differs from raw evidence')
        for filename, data in exports:
            with (OUT / filename).open(newline='') as f:
                require(list(csv.DictReader(f)) == [{k: str(v) for k, v in row.items()} for row in data],
                        'Saved CSV differs from raw evidence')

    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'evidence/q2-full-prefill128-final-preparation/mplconfig'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['svg.hashsalt'] = 'q2-full-prefill128-pp-tg'
    fig, axes = plt.subplots(2, 2, figsize=(14, 9), gridspec_kw={'width_ratios': [1.1, 3.3]})
    fig.subplots_adjust(left=.06, right=.985, top=.82, bottom=.25, hspace=.38, wspace=.25)
    colors = ['#8a8e9a', '#087f8c', '#c05224']
    styles = [('current', 'Latest Q2', '#087f8c', '-'), ('ud', 'Saved UD', '#c05224', '--'),
              ('before', 'Saved Q2 1', '#8a8e9a', ':'), ('after', 'Saved Q2 2', '#566079', ':')]
    labels = [str(r['depth'] // 1024) + 'K' + (' #' + str(r['attempt'] + 1) if r['depth'] == 8192 else '') for r in rows]
    for i, (field, unit, top) in enumerate((('prefill_tps', 'Prefill tokens/s', 1800),
                                          ('decode_tps', 'Decode tokens/s', 30))):
        ax = axes[i, 0]
        values = [r[field] for r in fixed_rows]
        ax.bar(range(3), values, color=colors, width=.6)
        ax.set_xticks(range(3), ['Initial\nQ2', 'Latest\nQ2', 'UD'])
        for x, value in enumerate(values):
            ax.text(x, value + top * .018, f'{value:.2f}', ha='center', fontsize=9)
        ax.set_title('Saved exact 2K / capacity 9216' if i == 0 else 'Saved 2K / TG128, 127 timed calls', fontsize=10)
        ax.set_ylabel(unit)
        ax.set_ylim(0, top)
        ax.grid(axis='y', alpha=.2)
        ax.set_axisbelow(True)
        ax = axes[i, 1]
        for key, label, color, line in styles:
            ax.plot(range(len(rows)), [r[key + '_' + field] for r in rows], label=label,
                    color=color, linestyle=line, marker='o', markersize=4)
        ax.set_xticks(range(len(rows)), labels)
        ax.set_ylim(0, top)
        ax.set_ylabel(unit)
        ax.set_title('Complete uncached prefill / capacity 133760' if i == 0 else
                     'Original prefix replies: TG8 / 8 timed calls (not TG128)', fontsize=10)
        ax.grid(alpha=.2)
    axes[1, 1].set_xlabel('Original requested prefix depth; both saved 8K attempts retained')
    axes[1, 1].annotate('Saved UD: 8-token sample', xy=(6, rows[6]['ud_decode_tps']),
                        xytext=(3.6, 8), arrowprops={'arrowstyle': '-', 'color': '#c05224'}, fontsize=8)
    handles, legend_labels = axes[0, 1].get_legend_handles_labels()
    fig.legend(handles, legend_labels, loc='upper center', bbox_to_anchor=(.64, .9), ncol=4)
    fig.suptitle('.157 GPU — latest retained Q2: measured prefill and decode', fontsize=14, y=.98)
    fig.text(.5, .93, 'Separate workloads: fixed 2048/TG128 at left; complete historical prefixes/TG8 at right.',
             ha='center', fontsize=10)
    fig.text(.5, .075, 'Exact saved inputs. Original 2048-token prefill chunks plus the natural final remainder.\n'
             'Archived controls; one sample per full prefix. 64K/128K recovered in separate cooled sessions.\n'
             'No new GPU run. TG8 observations do not qualify a TG128 curve or a sustained speedup.',
             ha='center', fontsize=9, linespacing=1.5)
    for ext in ('png', 'svg'):
        fig.savefig(OUT / ('pp-tg.' + ext), dpi=160, metadata={'Date': None} if ext == 'svg' else None)
    plt.close(fig)
    svg = OUT / 'pp-tg.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
    if not args.redraw:
        REPORT.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
        for filename, data in exports:
            with (OUT / filename).open('x', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=list(data[0]), lineterminator='\n')
                writer.writeheader()
                writer.writerows(data)
    print(json.dumps(dict(full_prefix_points=len(rows), fixed_points=len(fixed_rows),
                          new_measurements=False, curve_decode_output_tokens=8,
                          graph=str((OUT / 'pp-tg.png').relative_to(ROOT)))))


if __name__ == '__main__':
    main()
