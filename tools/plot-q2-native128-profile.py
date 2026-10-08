#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Plot diagnostic kernel costs, never profiled token throughput."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
data = json.loads((ROOT/'config/q2-native128-profile-results.json').read_text())
assert data['profile_only'] and not data['headline_eligible']
assert data['trace_validation']['csv_rocpd_all_timestamps_exact']
plt.rcParams.update({'font.size': 10, 'svg.fonttype': 'none',
                     'svg.hashsalt': 'synapse-lie-q2-native128-profile'})
fig = plt.figure(figsize=(15, 10), layout='constrained')
grid = fig.add_gridspec(2, 2, height_ratios=[1.2, 1])
for col, phase in enumerate(('prefill', 'decode')):
    ax = fig.add_subplot(grid[0, col])
    summary = data['summaries'][phase]
    values = summary['groups_total_ms']
    ranked = sorted(values.items(), key=lambda item: -item[1])
    unit = 1000 if phase == 'prefill' else 8
    selected = ranked[:7]
    selected.append(('Remaining kernel groups', sum(value for _, value in ranked[7:])))
    names = [name for name, _ in selected][::-1]
    costs = [value/unit for _, value in selected][::-1]
    ax.barh(names, costs, color='#276fbf' if phase == 'prefill' else '#008c80')
    for index, cost in enumerate(costs):
        ax.text(cost+max(costs)*.018, index, f'{cost:.2f}', va='center')
    ax.set_xlim(0, max(costs)*1.19)
    ax.grid(axis='x', alpha=.2)
    ax.set_axisbelow(True)
    ax.set_title('Complete 130,925-token prefill' if phase == 'prefill' else 'Decode: all 8 measured forwards')
    ax.set_xlabel('Summed kernel duration (seconds)' if phase == 'prefill' else 'Mean kernel duration per forward (ms)')
ax = fig.add_subplot(grid[1, 0])
quarters = data['quartiles']
names = ('Dense GEMM projections', 'HC mixing and normalization', 'Attention', 'Attention selection')
for name in names:
    ax.plot(range(4), [q['mean_groups_ms'][name] for q in quarters], marker='o', label=name)
ax.set_xticks(range(4), ['0–32K', '32–64K', '64–96K', '96–128K*'])
ax.set_ylabel('Mean kernel duration per chunk (ms)')
ax.set_title('Costs by position in the same prefill')
ax.grid(alpha=.2)
ax.legend(fontsize=8, loc='center left')
ax = fig.add_subplot(grid[1, 1])
rows = data['decode']
busy = [r['traced_busy_union_ms'] for r in rows]
uncovered = [r['not_covered_by_traced_kernels_or_copies_ms'] for r in rows]
ax.bar(range(1, 9), busy, label='Traced kernels/copies (interval union)', color='#008c80')
ax.bar(range(1, 9), uncovered, bottom=busy, label='Time outside traced device intervals', color='#dadada')
ax.set_xticks(range(1, 9))
ax.set_xlabel('Original decode forward')
ax.set_ylabel('Embedding submission to final synchronization (ms)')
ax.set_title('Every decode call retained, including startup overhead')
ax.legend(fontsize=8)
ax.grid(axis='y', alpha=.2)
ax.set_axisbelow(True)
fig.suptitle('Q2 / retained R3 — original 128K GPU attribution\nDiagnostic only: this is not a new throughput benchmark', fontsize=16)
fig.supxlabel('gfx1151 / .157 · C1 AR · chunk 2048 · cache hits 0 · *Final chunk: original 1901 tokens\nLoading, preparation and post-forward KV copies excluded. Client exit 0; profiled server shutdown timed out (−9).', fontsize=10)
for extension in ('png', 'svg'):
    path = ROOT/f'docs/figures/q2-native128-profile.{extension}'
    fig.savefig(path, dpi=160, metadata={'Date': None} if extension == 'svg' else None)
    if extension == 'svg':
        path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines())+'\n')
