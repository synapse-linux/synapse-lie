#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate and plot the exact-prompt Q2 model-owned multi-user matrix."""
import argparse
import csv
import hashlib
import json
import os
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--results', type=Path, required=True)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    summary = json.loads((args.results / 'native-result.json').read_text())
    require(summary['state'] == 'COMPLETE' and
            summary['plan_sha256'] == sha(args.plan) and
            summary['order'] == plan['order'] and
            len(summary['arms']) == 20, 'Matrix incomplete or plan differs')
    table = []
    continuations = {}
    for index, (requested, arm) in enumerate(zip(plan['order'], summary['arms'])):
        size, users = requested['tokens'], requested['users']
        tag = f'{index:02d}-q2-p{size}-c{users}'
        path = args.results / (tag + '.jsonl')
        require((arm['tokens'], arm['users']) == (size, users) and
                arm['output_sha256'] == sha(path) and
                arm['binary_sha256'] == plan['binary_sha256'],
                'Arm identity or result hash differs')
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        require(rows[0]['synthetic'] is False and rows[0]['suite'] == 'core' and
                rows[0]['prefill_dispatch'] == 'single-model-owner-serial' and
                rows[0]['decode_dispatch'] == 'reactive-ready-native-batch' and
                rows[0]['cache_policy'] == 'off' and
                rows[-1] == {'event': 'complete', 'exit_code': 0},
                'Arm not qualified original-weight core inference')
        prompt = next(r for r in rows if r['event'] == 'input')
        physical = next(r for r in plan['inputs'] if r['tokens'] == size)
        require(prompt['prompt_tokens'] == size and
                prompt['physical_ids_sha256'] == physical['physical_ids_sha256'] and
                len(prompt['physical_ids']) == size, 'Physical input differs')
        jobs = [r for r in rows if r['event'] == 'job']
        sample = next(r for r in rows if r['event'] == 'sample')
        require(len(jobs) == users and all(j['prefill_tokens'] == size and
                j['prefill_calls'] == size // 2048 and
                j['output_tokens'] == 128 for j in jobs) and
                sample == arm['sample'] and
                sample['prefill_tokens_total'] == size * users and
                sample['output_tokens'] == users * 128 and
                sample['prefill_executor_ns_total'] == sum(j['prefill_ns'] for j in jobs),
                'Physical model accounting differs')
        require(all(j['output_ids'] == jobs[0]['output_ids'] for j in jobs),
                'Users in one arm produced different continuations')
        continuations[(size, users)] = jobs[0]['output_ids']
        table.append(dict(tokens=size, users=users,
                          prefill_tps=sample['prefill_executor_tps'],
                          decode_tps=sample['decode_executor_tps'],
                          wall_output_tps=sample['output_per_total_wall_tps'],
                          prefill_seconds=sample['prefill_executor_ns_total']/1e9,
                          decode_seconds=sample['decode_executor_ns_total']/1e9,
                          wall_seconds=sample['wall_ns']/1e9,
                          decode_batches=sample['decode_batches'],
                          decode_batch_rows=sample['decode_batch_rows'],
                          decode_single_calls=sample['decode_single_calls'],
                          physical_ids_sha256=prompt['physical_ids_sha256'],
                          result_sha256=sha(path)))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / 'matrix.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(table[0]))
        writer.writeheader(); writer.writerows(table)
    quality = []
    for size in (2048, 4096, 6144, 8192):
        reference = continuations[(size, 1)]
        for users in (1, 2, 4, 6, 8):
            output = continuations[(size, users)]
            first = next((i for i, (a, b) in enumerate(zip(reference, output))
                          if a != b), None)
            packed = b''.join(token.to_bytes(4, 'little', signed=True)
                              for token in output)
            quality.append(dict(tokens=size, users=users,
                                first_difference_zero_based=first,
                                exact_match_c1=first is None,
                                matching_positions=sum(a == b for a, b in
                                                       zip(reference, output)),
                                output_ids_sha256=hashlib.sha256(packed).hexdigest()))
    (args.output_dir / 'quality.json').write_text(json.dumps(quality, indent=2) + '\n')
    os.environ.setdefault('MPLCONFIGDIR', str(args.output_dir / '.matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5), constrained_layout=True)
    for size in (2048, 4096, 6144, 8192):
        points = [r for r in table if r['tokens'] == size]
        for ax, key in zip(axes, ('prefill_tps', 'decode_tps', 'wall_output_tps')):
            ax.plot([r['users'] for r in points], [r[key] for r in points],
                    marker='o', label=f'{size//1024}K')
    for ax, title in zip(axes, ('Serial model prefill', 'Native reactive decode',
                                 'Output / complete wall')):
        ax.set(title=title, xlabel='Concurrent users', ylabel='tokens/s')
        ax.set_xticks((1,2,4,6,8)); ax.grid(alpha=.3)
    axes[0].legend(title='Prompt per user')
    fig.savefig(args.output_dir / 'matrix.png', dpi=180)
    plt.close(fig)
    print(json.dumps({'points':len(table), 'csv':str(args.output_dir/'matrix.csv'),
                      'graph':str(args.output_dir/'matrix.png'),
                      'quality':str(args.output_dir/'quality.json')}))


if __name__ == '__main__':
    main()
