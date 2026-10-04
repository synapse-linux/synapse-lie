#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot the audited four-arm native C model comparison and export every point."""
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
report = json.loads((ROOT/'config/q2-native-scale-curve-results.json').read_text())
cache_rows = json.loads((ROOT/'config/q2-native-scale-cache-timings.json').read_text())['rows']
cache = {(r['arm'],r['depth']):r for r in cache_rows}
if len(cache) != 32 or len(cache_rows) != 32:
    raise ValueError('Expected all 32 separate cache timing observations')
out = ROOT/'docs/figures/q2-native-scale-curve'
out.mkdir(parents=True, exist_ok=True)
labels = {'before':'Q2 reference before', 'scale':'Q2 scale reuse',
          'after':'Q2 reference after', 'ud':'UD'}
colors = {'before':'#79869b', 'scale':'#157e80', 'after':'#53608c', 'ud':'#bf582e'}
columns = ['arm','depth','cached_tokens','prefill_tokens','output_tokens',
           'prefill_ms','decode_ms','pp_tps','tg_tps','ttft_seconds',
           'wall_seconds','output_over_wall_tps','completion_sha256','request_sha256',
           'cache_capture_ms','cache_restore_ms','prefill_calls','decode_calls']
with (out/'points.csv').open('w', newline='') as stream:
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
    writer.writeheader()
    for arm,data in report['arms'].items():
        for point in data['rows']:
            row = dict(point, **{k:v for k,v in cache[(arm,point['depth'])].items()
                                if k not in ('depth','raw_sha256')})
            writer.writerow({k:row[k] for k in columns})
matplotlib.rcParams['svg.hashsalt'] = 'q2-native-scale-curve'
fig, axes = plt.subplots(2,2,figsize=(12,8),layout='constrained')
for ax,metric,title,unit in zip(axes.flat,
        ('pp_tps','tg_tps','ttft_seconds','wall_seconds'),
        ('Prefill — completed executor calls','Decode — completed executor calls',
         'Time to first output — HTTP client','Complete request — HTTP client'),
        ('Tokens/s','Tokens/s','Seconds','Seconds')):
    for arm,data in report['arms'].items():
        ax.plot(range(len(data['rows'])),[p[metric] for p in data['rows']],
                marker='o',markersize=4,color=colors[arm],label=labels[arm],
                linestyle='--' if arm in ('before','after') else '-')
    ax.set_xticks(range(8),['0','4K','8K','12K','16K','32K','64K','128K'])
    ax.set_xlabel('Requested cached-prefix depth (tokens)')
    ax.set_ylabel(unit)
    ax.set_title(title,fontsize=11)
    ax.grid(alpha=.2)
axes[0,0].legend(fontsize=8)
fig.suptitle('.157 — synapse-lie-bench native C, canonical prose pp2048/tg128\n'
             'One warmup and one measured point; both unchanged Q2 controls retained',fontsize=12)
for suffix in ('svg','png'):
    fig.savefig(out/f'curve.{suffix}',dpi=170,
                metadata={'Date':None} if suffix=='svg' else None)
svg=out/'curve.svg'
svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
plt.close(fig)
print(out)
