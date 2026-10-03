#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export the complete Q2/UD HTTP curve with physical counts and durations."""
import argparse
import csv
import json
import os
from pathlib import Path
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('report', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    assert report['schema'] == 'synapse-lie.q2-ud-canonical-comparison.v1'
    args.output.mkdir(parents=True, exist_ok=False)
    cache = tempfile.TemporaryDirectory(prefix='q2-curve-mpl-')
    os.environ.setdefault('MPLCONFIGDIR', cache.name)
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fields = ['variant', 'depth', 'cached_prompt_tokens', 'prefill_tokens', 'completion_tokens',
              'prefill_calls', 'decode_calls', 'prefill_seconds', 'decode_seconds',
              'cache_capture_ms', 'cache_restore_ms', 'ssd_read_ms', 'request_wall_ms',
              'prefill_tokens_per_second', 'decode_tokens_per_second', 'completion_sha256']
    with (args.output/'samples.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator='\n')
        writer.writeheader()
        for variant, group in report['models'].items():
            for row in group['rows']:
                out = {k:row[k] for k in fields if k in row}
                out.update(variant=variant, prefill_seconds=row['prefill_ms']/1000,
                           decode_seconds=row['decode_ms']/1000)
                writer.writerow(out)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
    labels = ['0', '4K', '8K', '12K', '16K', '32K', '64K', '128K']
    for ax, metric, title in zip(axes, ('prefill_tokens_per_second', 'decode_tokens_per_second'),
                               ('New-turn prefill', 'Completed AR decode')):
        for variant, color in (('q2', '#007f8b'), ('ud', '#d66a28')):
            rows = report['models'][variant]['rows']
            ax.plot(range(8), [r[metric] for r in rows], 'o-', color=color, label=variant.upper())
        ax.set(title=title, xlabel='Cached-prefix target', ylabel='tokens / second',
               xticks=range(8), xticklabels=labels)
        ax.grid(alpha=.2)
        ax.legend(frameon=False)
    fig.suptitle('Q2 / UD: Gufo prose workload over C17 HTTP', fontsize=16)
    fig.text(.06, .04, 'C1 AR, thinking/MTP off; approximately 2048 new tokens + 128 outputs; capacity 133760.\n'
             'One warmed sample per depth; actual counts and durations in CSV. LIE executor-call timers; numerical acceptance remains open.',
             fontsize=9)
    fig.subplots_adjust(top=.85, bottom=.22, wspace=.25)
    fig.savefig(args.output/'curve.png', dpi=170)
    fig.savefig(args.output/'curve.svg')
    svg = args.output/'curve.svg'
    svg.write_text('\n'.join(x.rstrip() for x in svg.read_text().splitlines())+'\n')
    cache.cleanup()
    print(json.dumps({'rows':16,'output':str(args.output)}))


if __name__ == '__main__':
    main()
