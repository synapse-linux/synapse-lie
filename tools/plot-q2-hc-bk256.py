#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export every retained HC component/model sample and zero-based plots."""
import argparse
import csv
import json
import os
from pathlib import Path


def save_csv(path, rows):
    with path.open('x') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    model = json.loads((root/'config/q2-hc-bk256-fixed-model-results.json').read_text())
    component = json.loads((root/'config/q2-hc-bk256-component-results.json').read_text())
    if (model['schema'] != 'synapse-lie.q2-hc-bk256-fixed-model.v1' or
            component['schema'] != 'synapse-lie.q2-hc-bk256-component.v1' or model['controls_rerun']):
        raise ValueError('Expected candidate-only HC reports')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(root/'evidence/.mpl-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    labels = {'fixed_q2':'Fixed Q2\nhistorical', 'parent_q8_row':'Q8 + row\nhistorical',
              'bounded':'New bounded HC', 'fixed_ud':'Fixed UD\nhistorical'}
    arms = dict(model['references'], bounded=model['model'])
    metrics = [('prefill_tok_s','Prefill','Tokens / second'),
               ('decode_steps_s','Decode: 127 timed calls','Calls / second'),
               ('prefill_s','Prefill duration','Seconds'), ('decode_s','Decode duration','Seconds')]
    rows = []
    for key in labels:
        arm = arms[key]
        for sample in arm['samples']:
            rows.append(dict(arm=key, historical=key!='bounded', source=arm['path'],
                repetition=sample['rep'], warmup=sample['warmup'],
                prompt_tokens=sample['prompt_tokens'], output_tokens=sample['output_tokens'],
                decode_steps=sample['decode_steps'], **{m:sample[m] for m,_,_ in metrics}))
        for metric,_,_ in metrics:
            measured = [s[metric] for s in arm['samples'] if not s['warmup']]
            if measured != arm['measurements'][metric]['samples'] or len(measured)!=3:
                raise ValueError('Model sample sequence differs')
    save_csv(args.output.with_name(args.output.name+'-model.csv'), rows)
    fig, axes = plt.subplots(2,2,figsize=(13,9))
    for ax,(metric,title,unit) in zip(axes.flat,metrics):
        medians = [arms[k]['measurements'][metric]['median'] for k in labels]
        ax.bar(list(labels.values()), medians, color=['#486fa9','#74acbb','#389878','#d18b36'])
        maximum=max(medians)
        for x,key in enumerate(labels):
            values=[s[metric] for s in arms[key]['samples']]
            maximum=max(maximum,*values)
            ax.scatter([x-.09],[values[0]],facecolors='none',edgecolors='black',s=30,zorder=4,
                       label='Warmup' if x==0 else None)
            ax.scatter([x-.055,x,x+.055],values[1:],c='black',s=17,zorder=4,
                       label='Measured samples' if x==0 else None)
            ax.annotate(f'{medians[x]:.3f}',(x,max(values)),xytext=(0,6),textcoords='offset points',ha='center')
        ax.set_ylim(0,maximum*1.3)
        ax.set_ylabel(unit)
        ax.set_title(title)
        ax.grid(axis='y',alpha=.2)
        ax.set_axisbelow(True)
        ax.legend(loc='upper left',fontsize=8)
    fig.suptitle('New original-F16 HC-down on .157 — unchanged exact2048 model test')
    fig.text(.5,.025,'Only the bounded model is new; fixed Q2, parent and UD are saved historical measurements.\n'
             'Bars: three-sample medians, all warmups shown. Changed logits, unchanged greedy tokens; numerical rejection retained.',
             ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.09,1,.95))
    save_figure(fig,args.output.with_name(args.output.name+'-model'))
    plt.close(fig)
    rows=[]
    for key,arm in component['arms'].items():
        for sample in arm['timings']:
            rows.append(dict(candidate=key,source=arm['label'],**sample))
    if len(rows)!=112:
        raise ValueError('Component samples incomplete')
    save_csv(args.output.with_name(args.output.name+'-component.csv'),rows)
    fig,axes=plt.subplots(2,2,figsize=(13,9))
    for ax,(moe,complete) in zip(axes.flat,[(False,False),(False,True),(True,False),(True,True)]):
        medians=[]
        names=[]
        for key in ('initial','bounded'):
            arm=component['arms'][key]
            scope=next(s for s in arm['summaries'] if s['moe']==moe and s['complete']==complete)
            for native in (False,True):
                medians.append(scope['native' if native else 'library']['median'])
                names.append(key+'\n'+('native' if native else 'library'))
        ax.bar(names,medians,color=['#74acbb','#b35c57','#74acbb','#389878'])
        maximum=max(medians)
        for x,(key,native) in enumerate([('initial',False),('initial',True),('bounded',False),('bounded',True)]):
            selected=[s for s in component['arms'][key]['timings'] if s['moe']==moe and
                      s['complete']==complete and s['native']==native]
            values=[s['us_per_iteration'] for s in selected]
            maximum=max(maximum,*values)
            ax.scatter([x-.08,x+.08],values[:2],facecolors='none',edgecolors='black',s=25,zorder=4,
                       label='Two warmups' if x==0 else None)
            ax.scatter([x-.08,x-.04,x,x+.04,x+.08],values[2:],c='black',s=17,zorder=4,
                       label='Five measured samples' if x==0 else None)
            ax.annotate(f'{medians[x]:.2f}',(x,max(values)),xytext=(0,6),textcoords='offset points',ha='center')
        ax.set_ylim(0,maximum*1.3)
        ax.set_ylabel('Microseconds / iteration; lower is faster')
        ax.set_title(('MoE' if moe else 'Ordinary')+' — '+('producer + down' if complete else 'down only'))
        ax.grid(axis='y',alpha=.2)
        ax.set_axisbelow(True)
        ax.legend(loc='upper left',fontsize=8)
    fig.suptitle('HC components on .157 — original F16; 100 MiB rotating weights')
    fig.text(.5,.025,'Library is the unchanged measured recipe inside each new component test.\n'
             'Both component exits remain 1; complete timing is retained. Initial and bounded native outputs match exactly.',
             ha='center',fontsize=10)
    fig.tight_layout(rect=(0,.09,1,.95))
    save_figure(fig,args.output.with_name(args.output.name+'-component'))
    plt.close(fig)
    print(json.dumps(dict(model_samples=16,component_samples=len(rows),output=str(args.output))))


def save_figure(fig,path):
    for suffix in ('.svg','.png'):
        if path.with_suffix(suffix).exists():
            raise ValueError('Refusing to overwrite graph')
        fig.savefig(path.with_suffix(suffix),dpi=150)
    svg=path.with_suffix('.svg')
    lines=svg.read_text().splitlines()
    lines.insert(1,'<!-- SPDX-License-Identifier: MIT -->')
    svg.write_text('\n'.join(line.rstrip() for line in lines)+'\n')


if __name__=='__main__':
    main()
