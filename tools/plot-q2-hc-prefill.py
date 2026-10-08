#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot HC prefill component/model measurements and observed ranges."""
import argparse
import csv
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Output stem')
    parser.add_argument('--reference-label', help='Override the reference label in both scopes')
    parser.add_argument('--candidate-label', help='Override the candidate label in both scopes')
    parser.add_argument('--ud-label', default='UD prior')
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(args.output.resolve().parent / '.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    groups = []
    for shape, title in [('320x10240', 'HC down prefill'), ('10240x320', 'HC up prefill')]:
        groups.append((title, 'Microseconds / call', [
            (label, report['micro'][key]['shapes'][shape]['us_per_launch'])
            for label, key in [(args.reference_label or 'hipBLASLt', 'reference'),
                               (args.candidate_label or 'WMMA', 'candidate')]]))
    if report['model']:
        for metric, title, unit in [('prefill_tok_s', 'Prefill: 2048 tokens', 'Tokens / second'),
                                    ('decode_steps_s', 'Decode: 127 calls', 'Calls / second')]:
            groups.append((title, unit, [(label, report['model'][key]['measurements'][metric])
                for label, key in [(args.reference_label or 'Q2 HC4', 'reference'),
                                   (args.candidate_label or 'Q2 HC4+PP', 'candidate'),
                                   (args.ud_label, 'ud')]
                if key in report['model']]))
    fig, axes = plt.subplots(1, len(groups), figsize=(4.4 * len(groups), 4), squeeze=False,
                             layout='constrained')
    data = []
    for axis, (title, unit, rows) in zip(axes[0], groups):
        labels = [label for label, _ in rows]
        medians = [value['median'] for _, value in rows]
        errors = [[value['median'] - value['min'] for _, value in rows],
                  [value['max'] - value['median'] for _, value in rows]]
        axis.bar(labels, medians, yerr=errors, capsize=4, color=['#4974a5', '#39845a', '#bc8347'][:len(rows)])
        axis.set_title(title)
        axis.set_ylabel(unit)
        axis.set_ylim(0, max(medians) * 1.18)
        for i, value in enumerate(medians):
            axis.text(i, value + max(medians) * 0.04, f'{value:.2f}', ha='center')
        for label, values in rows:
            data.append(dict(scope=title, arm=label, unit=unit,
                             minimum=values['min'], median=values['median'], maximum=values['max']))
    qualification = 'Original F16 weights; numerical results reported separately'
    if report['model']:
        qualification += '; 15 s idle before model requests'
    fig.suptitle('Q2 HC prefill exploration: medians and observed ranges\n' + qualification)
    for extension in ('svg', 'png'):
        fig.savefig(args.output.with_suffix('.' + extension), dpi=150)
    svg = args.output.with_suffix('.svg')
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines) + '\n')
    with args.output.with_suffix('.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(data)


if __name__ == '__main__':
    main()
