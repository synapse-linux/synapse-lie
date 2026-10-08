#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export all IQ2 register-palette component or original-model samples."""
import csv
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    phase = sys.argv[1]
    if phase not in ('component','model'):
        raise SystemExit('Expected component/model')
    report = json.loads((ROOT/f'config/q2-down-register-palette-{phase}-results.json').read_text())
    output = ROOT/f'docs/figures/q2-down-register-palette-{phase}'
    if any(output.with_suffix(s).exists() for s in ('.csv','.svg','.png')):
        raise ValueError('Refusing to overwrite exports')
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    if phase == 'component':
        rows = report['timings']
        assert len(rows) == 70
        fig, axes = plt.subplots(2,3,figsize=(18,9))
        for ax, case, title in zip(axes.flat, ('uniform-e160-w48','control-e512-w64','real-layer0','real-layer3','real-layer22'), ('Uniform160 BN48 affected control','Uniform512 unchanged BN64 control','Captured layer 0','Captured layer 3','Captured layer 22')):
            for candidate, color, label in ((False,'#379878','Frozen parent down'),
                                           (True,'#c4844e','Register palette, same down map')):
                samples = [r for r in rows if r['case'] == case and r['candidate'] == candidate]
                ax.plot([r['rep'] for r in samples], [r['us_per_iteration'] for r in samples],
                        color=color, marker='o',label=label)
            ax.axvspan(-.2,1.5,color='grey',alpha=.12)
            ax.set_title(title)
            ax.set_xlabel('Sample (0 and 1 are warmups)')
            ax.set_ylabel('Complete cycle microseconds; lower is faster')
            ax.grid(alpha=.2)
            ax.legend(fontsize=8)
        axes.flat[-1].set_visible(False)
        foot = ('Three weight rotations beyond 32 MiB; actual captured counts, synthetic operands.\n'
                'Setup excluded. Component timing is not model throughput.')
    else:
        assert not report['controls_rerun'] and report['original_tester_unchanged']
        arms = {k:report['references'][k] for k in ('fixed_q2','best_parent')}
        arms['register-palette'] = report['model']
        arms['fixed_ud'] = report['references']['fixed_ud']
        labels = ['Fixed Q2','Retained Q2\n1585','New Q2\nregister-palette','Fixed UD']
        rows = [dict(candidate=key, historical=key!='register-palette',source=Path(arm['path']).name,
            **{field:sample[field] for field in ('rep','warmup','prompt_tokens','output_tokens',
                'decode_steps','prefill_s','decode_s','prefill_tok_s','decode_steps_s')})
                for key,arm in arms.items() for sample in arm['samples']]
        assert len(rows) == 16
        fig, axes = plt.subplots(1,2,figsize=(14,6))
        for ax,metric,title in zip(axes,('prefill_tok_s','decode_steps_s'),
                                   ('Prefill tokens/s','Decode forward calls/s')):
            values = [a['measurements'][metric]['median'] for a in arms.values()]
            ax.bar(labels,values,color=['#748fb5','#379878','#c4844e','#5b6477'])
            for x,arm in enumerate(arms.values()):
                warm = [s[metric] for s in arm['samples'] if s['warmup']]
                measured = [s[metric] for s in arm['samples'] if not s['warmup']]
                ax.scatter([x],warm,facecolors='none',edgecolors='black',zorder=4,
                           label='Warmup' if x==0 else None)
                ax.scatter([x-.06,x,x+.06],measured,c='black',s=24,zorder=4,
                           label='Three measured sessions' if x==0 else None)
                ax.annotate(f'{values[x]:.3f}',(x,max(*warm,*measured)),
                            xytext=(0,8),textcoords='offset points',ha='center')
            ax.set_ylim(0,max(s[metric] for a in arms.values() for s in a['samples'])*1.17)
            ax.set_title(title)
            ax.set_ylabel('Higher is faster')
            ax.grid(axis='y',alpha=.2)
            ax.set_axisbelow(True)
            ax.legend(loc='lower left',fontsize=8)
        foot = ('Original exact2048/tg128,127 timed decode calls; capacity9216/chunk2048.\n'
                'Four new and twelve saved samples. Controls not rerun; independent quality and full curve remain open.')
    with output.with_suffix('.csv').open('x') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)
    fig.suptitle(f'Q2 down register-palette {phase}: complete samples on .157')
    fig.text(.5,.02,foot,ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.10,1,.94))
    for suffix in ('.svg','.png'):
        fig.savefig(output.with_suffix(suffix),dpi=150)
    path=output.with_suffix('.svg')
    lines=path.read_text().splitlines()
    lines.insert(1,'<!-- SPDX-License-Identifier: MIT -->')
    path.write_text('\n'.join(line.rstrip() for line in lines)+'\n')
    print(json.dumps(dict(phase=phase,samples=len(rows),output=str(output))))


if __name__ == '__main__':
    main()
