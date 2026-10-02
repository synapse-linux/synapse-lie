#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot retained baseline/candidate/UD medians with observed ranges."""
import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(Path(__file__).resolve().parents[1] / 'run' / 'plot-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(10, 4), layout='constrained')
    labels = {'baseline': 'Original Q2 port', 'candidate': 'Q2 compensated WMMA down', 'ud': 'UD original'}
    for axis, metric, title in zip(axes, ('prefill_tok_s', 'decode_steps_s'), ('Fresh prefill', 'Decode (127 calls)')):
        for arm, label in labels.items():
            rows = [r for r in report['measurements'] if r['arm'] == arm]
            medians = [r[metric]['median'] for r in rows]
            axis.errorbar([r['prompt_tokens'] for r in rows], medians,
                          yerr=[[r[metric]['median'] - r[metric]['min'] for r in rows],
                                [r[metric]['max'] - r[metric]['median'] for r in rows]],
                          marker='o', capsize=4, label=label)
        axis.set_xscale('log', base=2)
        axis.set_xticks([512, 2048, 8192], ['512', '2K', '8K'])
        axis.set_ylim(bottom=0)
        axis.set_xlabel('Physical prompt tokens')
        axis.set_ylabel('Tokens/s' if metric == 'prefill_tok_s' else 'Decode calls/s')
        axis.set_title(title)
        axis.grid(alpha=.25)
        axis.legend(fontsize=8)
    gate = 'PASS' if report['bounded_numerical_gate_pass'] else 'FAIL'
    fig.suptitle('Q2 down experiment: unprofiled C1; bounded numerical gate ' + gate)
    fig.savefig(args.output.with_suffix('.png'), dpi=150)
    svg = args.output.with_suffix('.svg')
    fig.savefig(svg)
    lines = svg.read_text().splitlines()
    lines.insert(1, '<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines) + '\n')


if __name__ == '__main__':
    main()
