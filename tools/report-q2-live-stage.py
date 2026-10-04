#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit three complete IQ2 stage-mask component arms and retain every sample."""
import csv
import importlib.util
import json
import os
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]


def main():
    spec = importlib.util.spec_from_file_location('audit', ROOT/'tools/analyze-q2-iq2-live-epilogue.py')
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)
    read, sha, require = audit.read, audit.sha, audit.require
    plan_path = ROOT/'config/q2-live-stage-plan.json'
    output = ROOT/'config/q2-live-stage-results.json'
    require(not output.exists(), 'Refusing to overwrite retained evidence')
    plan = read(plan_path)
    require(sha(ROOT/'config/q2-live-stage-host-reuse.json') == plan['host_reuse_sha256'],
            'Host reuse identity changed')
    for name, digest in plan['fixtures'].items():
        require(sha(ROOT/name) == digest, 'Frozen fixture changed: '+name)
    for name, digest in plan['source_manifests'].items():
        require(sha(ROOT/'config'/name) == digest, 'Provider manifest changed')
    host = ROOT/'evidence'/plan['host']
    qualification = audit.common.artifacts(host)
    require(qualification['state'] == 'CPU_FIXTURES_PASS_NO_MODEL_INFERENCE'
            and qualification['model_access'] is False and len(qualification['commands']) == 6,
            'Missing retained host qualification')
    for name in ('03.log','06.log'):
        require('100% tests passed out of 22' in (host/'results'/name).read_text(),
                'Host test count changed')
    routing = audit.verify_routing_provenance()
    keys = ('before','stage','after')
    arms = {key: audit.arm(ROOT/'evidence'/row['label'], key == 'stage', host)
            for key,row in zip(keys,plan['arms'])}
    samples = []
    for key, arm in arms.items():
        require(arm['source_variant'] == plan['arms'][keys.index(key)]['variant'],
                'Wrong planned variant')
        require(arm['weights'] == arms['before']['weights'], 'Weight operands differ')
        for name, case in arm['cases'].items():
            require(case['geometry'] == arms['before']['cases'][name]['geometry'],
                    'Input or routing geometry differs')
            require(case['median_us'] == statistics.median(
                s['microseconds_per_call'] for s in case['samples'] if not s['warmup']),
                'Median differs from retained samples')
            samples.extend(dict(arm=key,case=name,
                                **{k:s[k] for k in ('sample','warmup','calls','microseconds_per_call')})
                           for s in case['samples'])
        telemetry = [json.loads(s) for s in
                     (Path(arm['directory'])/'results/telemetry.jsonl').read_text().splitlines()]
        require(telemetry and all(not t['over_limit'] for s in telemetry for t in s['thermal']),
                'Thermal stop in retained observations')
        arm['thermal_peaks_c'] = {
            device: max(t['temperature_mc'] for s in telemetry for t in s['thermal']
                        if t['device'] == device)/1000
            for device in {t['device'] for s in telemetry for t in s['thermal']}}
    expected = audit.output_inventory()
    pairs = {key:{} for key in ('stage','after')}
    for arm in arms.values():
        directory = Path(arm['directory'])/'results'
        require({p.name for p in directory.iterdir() if p.suffix in ('.f32','.u32')}
                == expected.keys(), 'Incomplete output inventory')
    for name,count in expected.items():
        paths = {key: Path(arm['directory'])/'results'/name for key,arm in arms.items()}
        data = {key:p.read_bytes() for key,p in paths.items()}
        require(all(len(v) == count*4 for v in data.values()), 'Incomplete output array')
        for key in pairs:
            pairs[key][name] = dict(exact=data['before'] == data[key],values=count,
                                   reference_sha256=sha(paths['before']),sha256=sha(paths[key]))
    cells = {}
    for name in audit.cases():
        values = {key:arm['cases'][name]['median_us'] for key,arm in arms.items()}
        drift = 100*(values['after']/values['before']-1)
        bound = max(1.,2*abs(drift))
        changes = {key:100*(values['stage']/values[key]-1) for key in ('before','after')}
        passes = (all(v <= bound for v in changes.values()) if name == 'full-tiles'
                  else all(v < -bound for v in changes.values()))
        cells[name] = dict(median_us=values,reference_drift_percent=drift,
                           time_change_percent=changes,selection_bound_percent=bound,
                           passes_frozen_performance_selection=passes)
    exact = all(p['exact'] for group in pairs.values() for p in group.values())
    numerical = all(arm['completion']['numerical_pass'] for arm in arms.values())
    followup = exact and numerical and all(c['passes_frozen_performance_selection'] for c in cells.values())
    require(len(samples) == 105, 'Incomplete sample inventory')
    result = dict(schema='synapse-lie.q2-live-stage-results.v1',plan_sha256=sha(plan_path),
        scope=plan['scope'],routing_provenance=routing,arms=arms,cells=cells,pairs=pairs,
        samples=len(samples),exact=exact,numerical_pass=numerical,
        disposition='SELECT_FOR_FURTHER_PROFILING' if followup else 'NO_FURTHER_MODEL_RUN_FROM_THIS_COMPONENT',
        selection_note='The two observed controls are not a confidence interval. This gate selects work; it does not prove a model speedup.',
        model_inference=False,promoted=False,goal_met=False)
    with output.open('x') as stream:
        stream.write(json.dumps(result,indent=2,allow_nan=False)+'\n')
    directory = ROOT/'docs/figures/q2-live-stage'
    directory.mkdir(parents=True,exist_ok=True)
    with (directory/'samples.csv').open('x') as stream:
        writer = csv.DictWriter(stream,fieldnames=list(samples[0]),lineterminator='\n')
        writer.writeheader()
        writer.writerows(samples)
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'evidence/q2-live-stage-matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['svg.hashsalt'] = 'q2-live-stage'
    fig, axes = plt.subplots(2,3,figsize=(12,7.5),layout='constrained')
    labels = ['Reference\nbefore','Stage\nmask','Reference\nafter']
    for ax,(name,cell) in zip(axes.flat,cells.items()):
        values = [cell['median_us'][key]/1000 for key in keys]
        bars = ax.bar(labels,values,color=['#6177a8','#23857b','#9674a3'])
        ax.bar_label(bars,fmt='%.3f',padding=4,fontsize=8)
        maximum = max(values)
        for i,key in enumerate(keys):
            for s in arms[key]['cases'][name]['samples']:
                value = s['microseconds_per_call']/1000
                maximum = max(maximum,value)
                ax.scatter(i+(s['sample']-3)*.035,value,s=14,
                           facecolors='none' if s['warmup'] else '#222222',edgecolors='#222222')
        ax.set_ylim(0,maximum*1.15)
        ax.set_title(name)
        ax.set_ylabel('Milliseconds / complete cycle')
        ax.grid(axis='y',alpha=.2)
        ax.set_axisbelow(True)
    axes.flat[-1].axis('off')
    axes.flat[-1].text(.05,.9,'Lower is faster.\nBars: median of five samples.\nHollow dots: two warmups.\nEight complete calls per sample.\n\nSynthetic operands.\nRecorded short/128K routing.\nNot model prefill rates.',va='top',linespacing=1.6)
    fig.suptitle('IQ2 live-stage masking on .157 — complete cycle, both unchanged controls')
    for suffix in ('png','svg'):
        fig.savefig(directory/f'cycles.{suffix}',dpi=160,
                    metadata={'Date':None} if suffix=='svg' else None)
    svg=directory/'cycles.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)
    print(json.dumps({key:result[key] for key in ('disposition','exact','numerical_pass','samples','cells')}))
    raise SystemExit(0 if exact and numerical else 1)


if __name__ == '__main__':
    main()
