#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Render exact corpus frontiers and both measured GPU phases."""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT/'evidence/q2-exact-bench-preparation/matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    result=json.loads((ROOT/'config/q2-exact-bench128-results.json').read_text())
    matplotlib.rcParams['svg.hashsalt']='q2-exact-bench128'
    fig, axes=plt.subplots(1,2,figsize=(14,6))
    for chunk,color in zip((2048,4096,8192),('#2563eb','#d97706','#059669')):
        rows=[r for r in result['rows'] if r['chunk']==chunk]
        for ax,metric in zip(axes,('prefill_tps','decode_tps')):
            ax.plot([r['prompt_tokens'] for r in rows],[r[metric] for r in rows],
                    marker='o',color=color,label=f"Chunk {chunk:,} (128K: {rows[-1][metric]:,.2f})")
    for ax,title in zip(axes,('Incremental prefill — completed final chunk','AR decode — actual completed tokens')):
        ax.set_title(title); ax.set_xscale('log',base=2)
        ax.set_xticks([2048,4096,8192,16384,32768,65536,131072],['2K','4K','8K','16K','32K','64K','128K'])
        ax.set_xlabel('Exact prompt tokens before generation'); ax.set_ylabel('Tokens / second')
        ax.set_xlim(1800,150000); ax.grid(alpha=.25); ax.legend()
    fig.suptitle('Historical final-chunk timings — NOT a full-prefill comparison',fontsize=15)
    fig.text(.5,.045,'Native synapse-lie-bench; same raw corpus token prefixes; no partial prefill calls.\n'
             'Prefix replay outside PP/TG timers; C1 reactive AR; requested TG128; one measured run per point.\n'
             'IOMMU enabled; performance / 120 W. No comparison against the earlier HTTP corpus.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.12,1,.94))
    for suffix in ('png','svg'):
        path=ROOT/('docs/figures/q2-exact-bench128.'+suffix)
        fig.savefig(path,dpi=170)
        if suffix=='svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
    plt.close(fig)


if __name__ == '__main__':
    main()
