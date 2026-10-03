#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain repeated whole-curve observations and their sample variability."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics

METRICS = ('prefill_tokens_per_second','decode_tokens_per_second')
DEPTHS = [0,4096,8192,12288,16384,32768,65536,131072]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('reports',nargs='+',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args = parser.parse_args()
    if args.output.exists() or len(args.reports) < 2:
        raise ValueError('Need multiple verified reports and a new output')
    reports = [json.loads(p.read_text()) for p in args.reports]
    for r in reports:
        if r['schema'] != 'synapse-lie.q2-ud-canonical-comparison.v1' or r.get('promoted'):
            raise ValueError('Expected an unpromoted paired canonical comparison')
        for key in ('q2','ud'):
            rows = r['models'][key]['rows']
            if [row['depth'] for row in rows] != DEPTHS or any(row['completion_tokens'] != 128 for row in rows):
                raise ValueError('Missing or different workload cells')
    models = {}
    for key in ('q2','ud'):
        rows = []
        for i,depth in enumerate(DEPTHS):
            samples = [r['models'][key]['rows'][i] for r in reports]
            metrics = {}
            for metric in METRICS:
                values = [s[metric] for s in samples]
                metrics[metric] = dict(samples=values,mean=statistics.mean(values),
                    sample_stddev=statistics.stdev(values),minimum=min(values),maximum=max(values))
            rows.append(dict(depth=depth,metrics=metrics,
                completion_sequences_exact=len({s['completion_sha256'] for s in samples})==1,
                physical_counts_exact=all(len({s[n] for s in samples})==1 for n in
                    ('cached_prompt_tokens','prefill_tokens','completion_tokens','decode_calls'))))
        models[key] = rows
    cells = []
    for q,u in zip(models['q2'],models['ud']):
        ratios = {m:q['metrics'][m]['mean']/u['metrics'][m]['mean'] for m in METRICS}
        cells.append(dict(depth=q['depth'],mean_ratios=ratios,mean_parity_observed=all(v>=1 for v in ratios.values())))
    result = dict(schema='synapse-lie.q2-curve-repeats.v1',observations_per_cell=len(reports),
        sources=[dict(path=str(p),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in args.reports],
        models=models,cells=cells,scope='Uninstrumented ordered HTTP sweeps; mean, sample standard deviation and observed range. No confidence interval or new implementation gain.',
        full_curve_mean_parity_observed=all(c['mean_parity_observed'] for c in cells),
        numerical_qualified=False,promoted=False,goal_met=False)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'cells':cells,'goal_met':False}))


if __name__ == '__main__':
    main()
