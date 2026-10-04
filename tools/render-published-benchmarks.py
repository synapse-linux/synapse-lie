#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regenerate the curated results page from retained GPU measurements; no inference."""
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/benchmarks/2026-10-01'
PAGE = ROOT / 'docs/benchmarks/models/qwen3.8-flash-next/strix-halo'
CHARTS = PAGE / 'charts'


def main():
    CHARTS.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'build/published-matplotlib-cache'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 11, 'svg.hashsalt': 'synapse-lie-published-v1'})
    sources = {}

    def read(name):
        path = EVIDENCE / name
        sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        return json.loads(path.read_text())

    single = read('single/summary.json')
    multi = read('reactive/multi/summary.json')
    gufo = read('multi/summary.json')['reference']
    fresh = read('comparable/fresh/summary.json')['primary']
    path = EVIDENCE / 'comparable/fresh/samples.csv'
    sources[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
    samples = list(csv.DictReader(path.read_text().splitlines()))
    # Only complete physical GPU workloads are eligible for this presentation.
    for data in [single['primary'], single['reference'], multi['primary'], multi['reference'], gufo, fresh]:
        if data['identity']['synthetic'] or not all(r['full_output_budget'] for r in data['configurations']):
            raise ValueError('published graphs require full-output GPU measurements')
    for a, b in zip(multi['primary']['configurations'], gufo['configurations'], strict=True):
        if any(a[k] != b[k] for k in ('users', 'context_capacity', 'physical_ids_sha256', 'output_ids')):
            raise ValueError('historical Gufo workload mismatch')

    axes_receipt = {}

    def chart(stem, title, series, xkey, xlabel, labels, note):
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained')
        for ax, metric, heading in zip(axes, ('prefill_tps', 'decode_tps'), ('Prefill', 'Generation')):
            for name, data, color, style, marker in series:
                rows = data['configurations']
                stats = [r[metric] for r in rows]
                positions = [r[xkey] for r in rows] if xkey == 'users' else range(len(rows))
                ax.errorbar(positions, [s['median'] for s in stats],
                            yerr=[[s['median'] - s['min'] for s in stats], [s['max'] - s['median'] for s in stats]],
                            color=color, linestyle=style, marker=marker, markersize=6, capsize=3, label=name)
            ax.set_ylim(bottom=0, top=ax.get_ylim()[1] * 1.08)
            ticks = [r[xkey] for r in series[0][1]['configurations']] if xkey == 'users' else range(len(labels))
            ax.set_xticks(ticks, labels, rotation=25 if len(labels) > 5 else 0)
            ax.set_xlabel(xlabel)
            ax.set_ylabel('Tokens / second')
            ax.set_title(heading)
            ax.grid(axis='y', alpha=.25)
            ax.spines[['top', 'right']].set_visible(False)
        axes[1].legend(fontsize=9, loc='lower right')
        fig.suptitle(title, fontsize=14)
        fig.supxlabel(note, fontsize=9)
        for ext in ('svg', 'png'):
            metadata = {'Date': None} if ext == 'svg' else {}
            fig.savefig(CHARTS / f'{stem}.{ext}', dpi=160, metadata=metadata)
            if ext == 'svg':
                svg = CHARTS / f'{stem}.{ext}'
                svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines()) + '\n')
        axes_receipt[stem] = {'y_limits': [list(ax.get_ylim()) for ax in axes],
                             'series': [s[0] for s in series], 'x_field': xkey,
                             'x_tick_spacing': 'numeric' if xkey == 'users' else 'categorical'}
        plt.close(fig)

    chart('single-ar', 'Qwen3.8 Flash Next · Strix Halo · AR context depth',
          [('LIE paired baseline', single['primary'], '#1267b1', '-', 'o'),
           ('Gufo local control', single['reference'], '#cd7a00', '--', 'x')],
          'depth', 'Occupied prefix (tokens; equally spaced test points)',
          ['0', '4,096', '8,192', '12,288', '16,384', '32,768', '65,536', '131,072'],
          '2026-10-01 · direct executor · about 2,048 new tokens + 128 generated · one measured repetition')
    chart('multi-ar', 'Qwen3.8 Flash Next · Strix Halo · AR concurrent sequences',
          [('LIE reactive (n=3)', multi['primary'], '#1267b1', '-', 'o'),
           ('LIE serial control (n=3)', multi['reference'], '#717171', ':', 's'),
           ('Gufo earlier run (n=1)', gufo, '#cd7a00', '--', 'x')],
          'users', 'Concurrent users', ['1', '2', '4', '6', '8'],
          '2,048 prompt + 128 output tokens/user · median and observed min/max · Gufo run is historical, not paired')
    chart('fresh-ar', 'Qwen3.8 Flash Next · Strix Halo · AR full prompt prefill',
          [('LIE fresh prompt (n=2)', fresh, '#1267b1', '-', 'o')],
          'prompt_tokens', 'Full prompt (tokens; equally spaced test points)',
          [f"{r['prompt_tokens']:,}" for r in fresh['configurations']],
          '2026-10-01 · empty sequence · context 262,144 · 128 output tokens · median and observed min/max')

    def rate(row, key):
        return f"{row[key]['median']:,.2f}"

    single_rows = []
    multi_rows = []
    fresh_rows = []
    for a, b in zip(single['primary']['configurations'], single['reference']['configurations'], strict=True):
        single_rows.append(f"| {a['depth']:,} | {a['prompt_tokens'] - a['depth']:,} | {rate(a, 'prefill_tps')} | {rate(b, 'prefill_tps')} | {rate(a, 'decode_tps')} | {rate(b, 'decode_tps')} |")
    for a, b, c in zip(multi['primary']['configurations'], multi['reference']['configurations'], gufo['configurations'], strict=True):
        multi_rows.append(f"| {a['users']} | {rate(a, 'prefill_tps')} | {rate(c, 'prefill_tps')} | {rate(a, 'decode_tps')} | {rate(c, 'decode_tps')} | {rate(b, 'decode_tps')} |")
    for row in fresh['configurations']:
        elapsed = statistics.median(int(s['prefill_ns']) / 1e9 for s in samples if int(s['point']) == row['point'])
        fresh_rows.append(f"| {row['prompt_tokens']:,} | {rate(row, 'prefill_tps')} | {elapsed:,.3f} | {rate(row, 'decode_tps')} |")

    page = '''<!-- SPDX-License-Identifier: MIT -->
# Qwen3.8 Flash Next — AMD Strix Halo

[All benchmarks](../../../README.md) · [Run these workloads](../../../../guides/BENCHMARKS.md)

Results, tables and graphs are collected here. **PP** is prefill throughput;
**TG** is generation throughput, both in tokens per second. All throughput axes
start at zero, with independent scales for PP and TG.

| Measurement setup | Value |
| --- | --- |
| Model | Unsloth UD-Q4_K_XL, four shards, revision `38bb39ee97821de2c9009abb7e93950eec396e66`. |
| Platform | AMD Strix Halo, HIP `gfx1151`, dedicated measurement host `.157`. |
| Provider | Embedded Gufo, pin `f783fedb`; autoregressive, greedy, no MTP. |
| Measurement date | October 1, 2026. The build for each dataset is identified below. |
| Timing | Direct GPU executor; HTTP and client latency are excluded. |

These are retained measurements of the listed builds, not a rerun of the latest
cache changes. The workloads follow the shape of Gufo's AR benchmarks; exact
reproduction of its published HTTP campaign is still incomplete.

## Single user: context depth through 128K

This test measures approximately 2,048 new prompt tokens **after** the occupied
prefix, then generates 128 tokens. The time to construct the prefix is excluded.
Use it to compare suffix prefill and decoding as the context grows.

| Prefix tokens | New PP tokens | LIE PP | Gufo PP | LIE TG | Gufo TG |
| ---: | ---: | ---: | ---: | ---: | ---: |
''' + '\n'.join(single_rows) + '''

![Single-user AR prefill and generation through 128K](charts/single-ar.svg)

Paired local baseline: LIE `openai-reactive-api-r3` and the direct Gufo reference,
one measured repetition after one warmup, capacity 133,760. This predates LIE's
reactive batching change. All eight pairs have matching physical inputs and
output tokens. A later reactive C1 check at depths 0, 16K and 128K stayed within
0.35% of serial median TG; the complete eight-depth reactive rerun is still pending.

## Multiple users: prefill and generation

Each sequence has 2,048 prompt tokens, 128 output tokens and capacity 4,096.
All sequences finish prefill before timed decode. TG is the combined output
count divided by the cohort's decode time. PP is aggregate prefill throughput.

| Users | LIE reactive PP | Gufo earlier PP | LIE reactive TG | Gufo earlier TG | LIE serial TG |
| ---: | ---: | ---: | ---: | ---: | ---: |
''' + '\n'.join(multi_rows) + '''

![Multi-user AR prefill and generation, with historical Gufo reference](charts/multi-ar.svg)

LIE `reactive-inference-r3` uses three measured repetitions after one warmup.
The Gufo column comes from the earlier direct-reference run, with one measured
repetition. It supplies context, not a paired speedup claim. Gufo's published
HTTP benchmark sums individual request rates, so its metric is also different.

At eight users, LIE native batching reaches **107.15 tok/s**, versus **26.08 tok/s**
for the matched LIE serial control: **4.11×**. The earlier native Gufo run reached
**107.03 tok/s**. These data do not establish a reactive speed advantage over
Gufo's native batching. “Eight users” means eight sequences, not eight inference
workers; the dispatcher has one device-owner caller. A total OS-thread count
was not recorded for this particular campaign.

## Full prompt prefill: through 258,794 tokens

This test starts from an empty sequence and measures the whole prompt. It shows
the actual wait for a new long input. It is a different workload from the
incremental prefill above or a cached conversation follow-up.

| Full prompt tokens | LIE PP (tok/s) | Prefill time (s) | LIE TG (tok/s) |
| ---: | ---: | ---: | ---: |
''' + '\n'.join(fresh_rows) + '''

![Full-prompt prefill and generation through 258794 tokens](charts/fresh-ar.svg)

Build `bench-comparable-r1`: two measured repetitions, no warmup, capacity
262,144, chunk 2,048, output 128. Values are medians; error bars show the observed
minimum and maximum. Time and rate are independently summarized across samples.
No matched Gufo or Halogen full-prefill run is available for this dataset.

## What is still missing from the Gufo comparison?

| Workload | Remaining work |
| --- | --- |
| Single-user AR. | Repeat all eight depths with the latest reactive/cache build and a paired Gufo control. |
| Multi-user AR over HTTP. | Implement and run the same per-request-rate protocol used by Gufo. |
| Single-user and multi-user MTP. | Integrate MTP before running these workloads. |
| Cold model loading. | Measure cold target files to HTTP readiness; current loading tests leave OS cache uncontrolled. |
| Peak HIP memory. | Measure allocation-exact peak memory; existing provider estimates are insufficient. |
| 512K–1M context. | Extend and qualify the provider beyond its native 262,144-token limit. |

## Reproduce and download

The [benchmark guide](../../../../guides/BENCHMARKS.md) contains the complete
commands for `single`, `multi`, `fresh`, local Gufo controls and graph export.
See Gufo's pinned [benchmarks](https://github.com/gufo-org/gufo/blob/f783fedb9bea2ec7de941f6da4e02f4a4596b29e/docs/models/qwen3.8-flash-next/BENCHMARKS.md)
and [method](https://github.com/gufo-org/gufo/blob/f783fedb9bea2ec7de941f6da4e02f4a4596b29e/docs/models/qwen3.8-flash-next/QUALITY.md#benchmark-method)
for the reference protocol.

Download the [full-precision CSV](charts/values.csv) or the
[plot data and source hashes](charts/data.json). SVG and PNG versions are in
[charts/](charts/). Rebuild this page and its figures without a GPU:

```sh
python3 tools/render-published-benchmarks.py
```

Internal correctness checks, cache experiments and older reports are available
in the [technical archive](../../../../archive/README.md). They are separate
from the performance results presented here.
'''
    (PAGE / 'README.md').write_text(page)
    data = {'schema': 'synapse-lie.published-charts.v1', 'sources_sha256': sources,
            'single': single, 'multi': multi, 'historical_gufo_multi': gufo, 'fresh': fresh,
            'axes': axes_receipt}
    (CHARTS / 'data.json').write_text(json.dumps(data, indent=2) + '\n')
    with (CHARTS / 'values.csv').open('w', newline='') as stream:
        writer = csv.writer(stream, lineterminator='\n')
        writer.writerow(['workload', 'series', 'depth', 'users', 'prompt_tokens', 'context_capacity', 'repetitions', 'pp_median_tps', 'pp_min_tps', 'pp_max_tps', 'tg_median_tps', 'tg_min_tps', 'tg_max_tps'])
        for workload, name, result in [('single', 'LIE paired baseline', single['primary']), ('single', 'Gufo paired control', single['reference']), ('multi', 'LIE reactive', multi['primary']), ('multi', 'LIE serial', multi['reference']), ('multi', 'Gufo historical', gufo), ('fresh', 'LIE fresh', fresh)]:
            for row in result['configurations']:
                writer.writerow([workload, name, *[row[k] for k in ('depth', 'users', 'prompt_tokens', 'context_capacity', 'repetitions')], *[row[k][s] for k in ('prefill_tps', 'decode_tps') for s in ('median', 'min', 'max')]])
    print('Published three figures, complete tables, CSV values and source hashes. No inference run.')


if __name__ == '__main__':
    main()
