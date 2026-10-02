#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot retained HC component/model observations and their measured ranges."""
import argparse
import csv
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True, help='Output stem')
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(args.output.resolve().parent / '.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    groups = [('HC down: 100 MiB rotating weights', 'Microseconds / call', [
        (label, report['micro'][key]['us_per_launch'])
        for label, key in [('Original', 'reference'), ('Four wave', 'candidate')]])]
    if report['model']:
        for metric, title, unit in [('prefill_tok_s', 'Prefill: 2048 tokens', 'Tokens / second'),
                                    ('decode_steps_s', 'Decode: 127 calls', 'Calls / second')]:
            groups.append((title, unit, [(label + f" (n={report['model'][key]['measured_samples']})", report['model'][key]['measurements'][metric])
                for label, key in [('Q2', 'reference'), ('Q2 HC', 'candidate'), ('UD', 'ud')]]))
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
    fig.suptitle('Q2 HC exploration: median and observed range\n'
                 'Isolated requests; reference thermally interrupted; comparison incomplete'
                 if report['model'] and not report['model']['comparison_complete'] else
                 'Q2 HC exploration: median and observed range\n15 s untimed idle intervals'
                 if report['model'] else 'Q2 HC component exploration\nMedian and observed range')
    for extension in ('svg', 'png'):
        fig.savefig(args.output.with_suffix('.' + extension), dpi=150)
    svg = args.output.with_suffix('.svg')
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines) + '\n')
    with args.output.with_suffix('.csv').open('w') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)


if __name__ == '__main__':
    main()
