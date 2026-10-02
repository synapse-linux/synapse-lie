#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot Q2 expert measurements; export all samples, rates and durations."""
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
    matplotlib.rcParams['svg.hashsalt'] = 'q2-expert-stack'
    arms = [('hc', 'Q2 HC\nprior'), ('stack', 'Q2 HC +\nQ2 down'),
            ('iq2_pair', 'Q2 + paired\nIQ2 gate/up'), ('ud_historical', 'UD\nhistorical')]
    metrics = [('prefill_tok_s', 'Prefill: 2048 tokens', 'Tokens / second'),
               ('decode_steps_s', 'Decode: 127 calls', 'Calls / second')]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout='constrained')
    for axis, (metric, title, unit) in zip(axes, metrics):
        rows = [report['arms'][key]['measurements'][metric] for key, _ in arms]
        medians = [row['median'] for row in rows]
        errors = [[row['median'] - row['min'] for row in rows],
                  [row['max'] - row['median'] for row in rows]]
        bars = axis.bar([label for _, label in arms], medians, yerr=errors,
                        capsize=4, color=['#8195a5', '#4974a5', '#39845a', '#bc8347'])
        for index in (0, 3):
            bars[index].set_hatch('//')
        axis.set_title(title)
        axis.set_ylabel(unit)
        axis.set_ylim(0, max(medians) * 1.2)
        axis.set_axisbelow(True)
        axis.yaxis.grid(True, alpha=0.2)
        for i, value in enumerate(medians):
            axis.text(i, value + max(medians) * 0.04, f'{value:,.2f}', ha='center')
    fig.suptitle('Q2 expert kernels: median and observed min/max, three measured requests\n'
                 'C1, 15 s idle outside timing; hatched controls are historical; numerical drift retained')
    for extension in ('svg', 'png'):
        fig.savefig(args.output.with_suffix('.' + extension), dpi=150,
                    metadata={'Date': None} if extension == 'svg' else None)
    plt.close(fig)
    svg = args.output.with_suffix('.svg')
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines) + '\n')
    data = []
    for key, _ in arms:
        for metric, values in report['arms'][key]['measurements'].items():
            data.append(dict(arm=key, historical=key in ('hc', 'ud_historical'),
                             metric=metric, minimum=values['min'], median=values['median'],
                             maximum=values['max'], **{f'sample_{i}': value
                                 for i, value in enumerate(values['samples'], 1)}))
    with args.output.with_suffix('.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(data[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(data)


if __name__ == '__main__':
    main()
