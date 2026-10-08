#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate and tabulate the completed .157 Q2 DS4-walk against the frozen full-prefill probe."""
import csv
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/q2-ds4-walk-promessi-r1'
OLD = ROOT / 'evidence/q2-promessi-short-r1/results/00-q2-c2048.jsonl'
FIGURES = ROOT / 'docs/figures'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def records(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def checked(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    plan_path = ROOT / 'config/q2-ds4-walk-promessi-plan.json'
    plan = read(plan_path)
    checked(sha(EVIDENCE / 'plan.json') == sha(plan_path) ==
            '462194c89f8f741b35452d86a2014aee0d246d41a7ac54ce4f0863b8d7eb6019',
            'Frozen plan differs')
    for name, digest in plan['staged_sha256'].items():
        if name == 'synapse-lie-bench':
            path = ROOT / '.deps/build-ds4-walk-gpu/core/synapse-lie-bench'
        elif name == 'promessi_sposi.txt':
            path = ROOT / 'evidence/q2-promessi-short-r1/promessi_sposi.txt'
        else:
            path = EVIDENCE / name
        checked(sha(path) == digest, 'Staged input differs: ' + name)
    files = []
    for line in (EVIDENCE / 'results.sha256').read_text().splitlines():
        digest, name = line.split('  ', 1)
        checked(sha(EVIDENCE / name) == digest, 'Collected result differs: ' + name)
        files.append(name)
    checked(len(files) == 15, 'Incomplete result collection')
    release = read(EVIDENCE / 'release.json')
    closure = read(EVIDENCE / 'strong-closure.json')
    checked(release['state'] == 'Q2_DS4_WALK_PROMESSI_RELEASED' and
            release['pair_state'] == 'COMPLETE' and not release['gpu_reserved'] and
            sha(EVIDENCE / 'release.json') == closure['release_sha256'] and
            closure['kfd_empty'] and closure['original_five_leases_free'] and
            closure['reference_model_stats_unchanged'] and
            closure['glm_model_stats_unchanged'], 'GPU release/closure differs')

    new_path = EVIDENCE / 'results/00-q2-c2048.jsonl'
    new, old = records(new_path), records(OLD)
    identity, old_identity = new[0], old[0]
    checked(new[-1] == {'event': 'complete', 'exit_code': 0} and
            identity['suite'] == 'ds4-walk' and
            identity['measurement_contract'] == 'ds4-walk-v1' and
            identity['warmups'] == 0 and identity['repetitions'] == 1 and
            identity['synthetic'] is False and
            identity['source_pin'] == old_identity['source_pin'] and
            old_identity['suite'] == 'fresh' and old_identity['warmups'] == 1,
            'Measurement identities differ')
    corpus = [row for row in new if row['event'] == 'corpus']
    checked(len(corpus) == 1 and
            corpus[0]['text_sha256'] == plan['staged_sha256']['promessi_sposi.txt'],
            'Promessi corpus differs')
    targets = plan['sizes']
    inputs = [row for row in new if row['event'] == 'input']
    samples = [row for row in new if row['event'] == 'sample']
    restores = [row for row in new if row['event'] == 'frontier_restore']
    old_inputs = {row['prompt_tokens']: row for row in old if row['event'] == 'input'}
    old_measured = {row['prompt_tokens']: row for row in old if
                    row['event'] == 'sample' and not row['warmup']}
    checked(len(inputs) == len(samples) == len(restores) == len(targets) == 4,
            'Four complete frontiers required')
    output = []
    for point, target in enumerate(targets):
        inp, sample, restore = inputs[point], samples[point], restores[point]
        previous = targets[point - 1] if point else 0
        prior = old_measured[target]
        raw = b''.join(int(token).to_bytes(4, 'little', signed=True)
                       for token in inp['physical_ids'])
        checked(inp['point'] == sample['point'] == restore['point'] == point and
                inp['prompt_tokens'] == sample['prompt_tokens'] == target and
                inp['depth'] == sample['depth'] == previous and
                inp['physical_ids_sha256'] == old_inputs[target]['physical_ids_sha256'] ==
                hashlib.sha256(raw).hexdigest() and
                inp['physical_ids'][:previous] ==
                (inputs[point - 1]['physical_ids'] if point else []),
                'Prompt/count/prefix differs')
        checked(sample['prefill_tokens_per_user'] == target - previous == 2048 and
                sample['prefill_calls_per_user'] == 1 and
                sample['prefill_tail_tokens'] == 0 and
                sample['cache_tokens'] == previous and
                sample['output_tokens_per_user'] == 128 and
                sample['full_output_budget'] == 1 and
                sample['prefill_ns'] == sample['prefill_end_monotonic_ns'] -
                                        sample['prefill_begin_monotonic_ns'] and
                sample['decode_ns'] == sample['decode_end_monotonic_ns'] -
                                       sample['decode_begin_monotonic_ns'] and
                sample['sample_begin_monotonic_ns'] <=
                sample['prefill_begin_monotonic_ns'] <
                sample['prefill_end_monotonic_ns'] <=
                sample['decode_begin_monotonic_ns'] <
                sample['decode_end_monotonic_ns'], 'Phase timing/count differs')
        checked(abs(sample['prefill_tps'] - 2048e9 / sample['prefill_ns']) < 1e-9 and
                abs(sample['decode_tps'] - 128e9 / sample['decode_ns']) < 1e-9 and
                restore['mode'] in (('none',) if point == 3 else ('snapshot', 'replay')) and
                sample['prefill_logits_sha256'] == prior['prefill_logits_sha256'] and
                sample['decode_logits_sha256'] == prior['decode_logits_sha256'] and
                sample['output_ids'] == prior['output_ids'],
                'Rate, restore or numerical continuation differs')
        output.append(dict(context_tokens=target,walk_prefill_tokens=2048,
                           walk_prefill_seconds=sample['prefill_ns'] / 1e9,
                           walk_prefill_tps=sample['prefill_tps'],
                           walk_decode_tokens=128,
                           walk_decode_seconds=sample['decode_ns'] / 1e9,
                           walk_decode_tps=sample['decode_tps'],
                           full_prefill_tokens=target,
                           full_prefill_seconds=prior['prefill_ns'] / 1e9,
                           full_prefill_tps=prior['prefill_tps'],
                           full_decode_tps=prior['decode_tps'],
                           restore=restore['mode'],
                           snapshot_bytes=restore['snapshot_bytes'],
                           physical_ids_sha256=inp['physical_ids_sha256'],
                           output_matches_full_prefill=True))

    summary = dict(schema='synapse-lie.q2-ds4-walk-promessi-results.v1',
                   state='COMPLETE_RELEASED', plan_sha256=sha(plan_path),
                   binary_sha256=plan['staged_sha256']['synapse-lie-bench'],
                   raw_jsonl_sha256=sha(new_path), old_jsonl_sha256=sha(OLD),
                   release_sha256=closure['release_sha256'],
                   strong_closure=closure, collected_files=len(files),
                   exact_steps=True, all_full_output_budget=True,
                   numerical_continuations_match_full_prefill=True,
                   comparison_contract='different prefill numerators: new 2048 each step, old complete prompt',
                   rows=output)
    (ROOT / 'config/q2-ds4-walk-promessi-results.json').write_text(
        json.dumps(summary, indent=2) + '\n')
    FIGURES.mkdir(exist_ok=True)
    with (FIGURES / 'q2-ds4-walk-promessi.csv').open('w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(output[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(output)
    source = EVIDENCE / 'results/00-q2-c2048-report'
    for suffix in ('png', 'svg'):
        shutil.copyfile(source / ('benchmark.' + suffix),
                        FIGURES / ('q2-ds4-walk-promessi.' + suffix))
    print(json.dumps(dict(state=summary['state'], rows=output,
                          release_sha256=summary['release_sha256'])))


if __name__ == '__main__':
    main()
