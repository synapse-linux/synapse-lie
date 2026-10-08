#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export every focused model sample, both controls and separate cache timings."""
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    source = ROOT/'config/q2-norm-point-results.json'
    output = ROOT/'config/q2-norm-point-comparison.json'
    directory = ROOT/'docs/figures/q2-norm-point'
    if output.exists() or directory.exists():
        raise ValueError('Refusing to overwrite retained focused results')
    data = json.loads(source.read_text())
    if set(data['arms']) != {'before','norm','after','ud'}:
        raise ValueError('Incomplete focused comparison')
    rows, summaries = [], {}
    metrics = ('pp_tps','tg_tps','ttft_seconds','wall_seconds')
    for name, arm in data['arms'].items():
        raw = ROOT/arm['directory']/'results/native-curve.jsonl'
        requests = [json.loads(line) for line in raw.read_text().splitlines()
                    if json.loads(line)['event'] == 'request']
        if [(p['depth'],p['rep']) for p in arm['rows']] != [(0,0),(0,1),(0,2)]:
            raise ValueError('Unexpected measured points')
        for point in arm['rows']:
            t = requests[point['request_index']]['observation']['server_timings']
            rows.append(dict(arm=name, depth=point['depth'], rep=point['rep'],
                **{k:point[k] for k in ('prefill_tokens','output_tokens',*metrics,
                                      'completion_sha256','request_sha256')},
                **{k:t[k] for k in ('cached_tokens','prefill_ms','decode_ms','prefill_calls',
                                   'decode_calls','cache_capture_ms','cache_restore_ms')}))
        summaries[name] = {metric: dict(median=statistics.median(p[metric] for p in arm['rows']),
            minimum=min(p[metric] for p in arm['rows']), maximum=max(p[metric] for p in arm['rows']))
            for metric in metrics}
    comparisons = {reference:{metric:100*(summaries['norm'][metric]['median']/
            summaries[reference][metric]['median']-1) for metric in metrics}
            for reference in ('before','after','ud')}
    per_sample = {reference:{metric:[100*(b[metric]/a[metric]-1) for a,b in
        zip(data['arms'][reference]['rows'],data['arms']['norm']['rows'])]
        for metric in metrics} for reference in ('before','after','ud')}
    prior_path = ROOT/'config/q2-native-row-curve-results.json'
    prior = json.loads(prior_path.read_text())
    canonical_replay = {}
    for name in ('before','norm','after','ud'):
        expected = [r for r in prior['arms']['ud' if name == 'ud' else 'after']['history'] if r['depth'] == 0]
        observed = [r for r in data['arms'][name]['history'] if r['rep'] == 0]
        canonical_replay[name] = observed == expected
    geometry = []
    for point in (r for r in rows if r['arm'] == 'norm'):
        count = point['prefill_tokens']
        chunks = [2048]*(count//2048) + ([count%2048] if count%2048 else [])
        geometry.append(dict(rep=point['rep'],prefill_tokens=count,
            observed_prefill_calls=point['prefill_calls'],inferred_chunks=chunks,
            newly_eligible_rows=sum(n for n in chunks if 96 <= n < 2048),
            note='Chunk sizes inferred from frozen chunk2048 worker policy; this is not an instrumented kernel trace.'))
    report = dict(schema='synapse-lie.q2-norm-point-comparison.v1',result_sha256=sha(source),
        summaries=summaries,candidate_change_percent=comparisons,
        per_sample_change_percent=per_sample,history_matches=data['history_matches'],
        prior_canonical_report_sha256=sha(prior_path),original_d0_history_matches=canonical_replay,
        dispatch_geometry=geometry,
        unchanged_control_pp_drift_percent=100*(summaries['after']['pp_tps']['median']/summaries['before']['pp_tps']['median']-1),
        disposition='EXPLORATORY_PAIRED_PROMPT_OBSERVATIONS_ONLY',
        fixed_reference='config/q2-fixed-prefill-reference.json',
        fixed_reference_improvement_measured=False,
        scope='Three native canonical d0 repetitions per arm; different deterministic prose by repetition, identical corresponding Q2 histories required. Positive throughput changes are faster; positive duration changes are slower.',
        limits='Different prompts are not identical-input repetitions. Medians are descriptive only and do not update the fixed reference. Preserve order/cache effects and all original numerical failures. This does not establish repeatability, fixed-reference improvement or full-curve parity.',
        preflight_linux_cached_gib={k:a['preflight_linux_cached_gib'] for k,a in data['arms'].items()},
        model_inference=True,independent_model_quality='Open',promoted=False,goal_met=False)
    with output.open('x') as stream: stream.write(json.dumps(report,indent=2,allow_nan=False)+'\n')
    directory.mkdir(parents=True)
    with (directory/'samples.csv').open('x') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
        writer.writeheader();writer.writerows(rows)
    os.environ.setdefault('MPLCONFIGDIR',str(ROOT/'evidence/q2-norm-point-matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matplotlib.rcParams['svg.hashsalt']='q2-norm-point'
    fig,axes=plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    labels=dict(before='Q2 before',norm='Q2 paired norm',after='Q2 after',ud='UD')
    for axis,metric,title in zip(axes,('pp_tps','tg_tps'),('Prefill','Decode')):
        for name,arm in data['arms'].items():
            axis.plot([p['rep']+1 for p in arm['rows']],[p[metric] for p in arm['rows']],
                      marker='o',label=labels[name])
        axis.set(title=title,xlabel='Measured repetition',ylabel='Tokens / second',xticks=[1,2,3])
        axis.grid(alpha=.2);axis.legend()
    fig.suptitle('Canonical d0 only — pp2048 / tg128, all three samples and both controls')
    for suffix in ('png','svg'):
        fig.savefig(directory/f'point.{suffix}',dpi=160,
                    metadata={'Date':None} if suffix=='svg' else None)
    p=directory/'point.svg';p.write_text('\n'.join(s.rstrip() for s in p.read_text().splitlines())+'\n')
    plt.close(fig)
    print(json.dumps(dict(summaries=summaries,comparisons=comparisons,
                         original_d0_history_matches=canonical_replay,disposition=report['disposition'])))


if __name__ == '__main__':
    main()
