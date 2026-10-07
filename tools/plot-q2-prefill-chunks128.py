#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Render the measured chunk curves, preserving the original prompt lengths."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'evidence/q2-prefill-chunks-preparation/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    result = json.loads((ROOT / 'config/q2-prefill-chunks128-results.json').read_text())
    matplotlib.rcParams['svg.hashsalt'] = 'q2-prefill-chunks128'
    fig, axes = plt.subplots(1, 2, figsize=(14, 6))
    for arm, color in zip(result['order'], ('#2563eb', '#d97706', '#059669')):
        # Both original 8K attempts are preserved. Preparation is an isolated
        # cross, not a prefix-curve point or the separate fixed2048/tg128 test.
        rows = result['curves'][arm][3:]
        preparation = result['curves'][arm][2]
        for ax, metric in zip(axes, ('prefill_tps', 'decode_tps')):
            ax.plot([r['tokens'] for r in rows], [r[metric] for r in rows],
                    marker='o', color=color,
                    label=f"Chunk {int(arm):,} (128K: {rows[-1][metric]:,.2f})")
            ax.scatter([preparation['tokens']], [preparation[metric]],
                       marker='x', color=color, s=55)
    for ax, title in zip(axes, ('Full prefill', 'AR decode (8 calls per prompt)')):
        ax.set_title(title)
        ax.set_xscale('log', base=2)
        ax.set_xticks([2048, 4096, 8192, 16384, 32768, 65536, 131072],
                      ['2K*', '4K', '8K', '16K', '32K', '64K', '128K'])
        ax.set_xlabel('Actual original prompt tokens (nominal tick labels)')
        ax.set_ylabel('Tokens / second')
        ax.set_xlim(1800, 150000)
        ax.grid(alpha=.25)
        ax.legend()
    fig.suptitle('Q2 on .157 — prefill chunks 2K / 4K / 8K — IOMMU enabled', fontsize=15)
    fig.text(.5, .04,
             'Same server and native synapse-lie-bench; C1 AR, zero prefix reuse; original final prompt 130,925 tokens.\n'
             'One curve per chunk; original natural tails; performance / 120 W. No reboot or new weight quantization.\n'
             '* Isolated crosses: original 2,055-token preparation, 16 decode calls; not the fixed2048/tg128 benchmark.',
             ha='center', fontsize=9)
    fig.tight_layout(rect=(0, .12, 1, .94))
    for suffix in ('png', 'svg'):
        fig.savefig(ROOT / ('docs/figures/q2-prefill-chunks128.' + suffix), dpi=170)
    plt.close(fig)


if __name__ == '__main__':
    main()
