#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare the one new scalar HC model with its frozen historical references."""

import array
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/q2-hc-scalar-model-r1'
PARENT = ROOT / 'evidence/q2-iq2-fixed-bounds-model-r1/results'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def compare(a, b):
    aa, bb = a.read_bytes(), b.read_bytes()
    report = {'exact': aa == bb, 'reference_sha256': hashlib.sha256(aa).hexdigest(),
              'candidate_sha256': hashlib.sha256(bb).hexdigest()}
    if a.suffix == '.f32':
        av, bv = array.array('f'), array.array('f')
        av.frombytes(aa)
        bv.frombytes(bb)
        require(len(av) == len(bv), 'Frontier dimensions differ')
        report['finite'] = all(math.isfinite(x) for v in (av, bv) for x in v)
        if report['finite'] and aa != bb:
            error = sum((x - y) ** 2 for x, y in zip(av, bv))
            norm = sum(x * x for x in av)
            report['relative_rms'] = math.sqrt(error / max(norm, 1e-60))
            report['max_absolute_error'] = max(abs(x - y) for x, y in zip(av, bv))
    return report


def main():
    plan = read(ROOT / 'config/q2-hc-scalar-model-plan.json')
    require(sha(EVIDENCE / 'plan.json') == sha(ROOT / 'config/q2-hc-scalar-model-plan.json'),
            'Frozen plan differs')
    artifacts = read(EVIDENCE / 'artifact-hashes.json')
    for name, digest in artifacts.items():
        require(sha(EVIDENCE / name) == digest, 'Collected evidence differs: ' + name)
    for name, digest in plan['staged_sha256'].items():
        require(sha(EVIDENCE / name) == digest, 'Staged source or binary differs: ' + name)
    for name, digest in plan['saved_parent_artifacts'].items():
        require(sha(PARENT / name) == digest, 'Saved parent differs: ' + name)
    require(sha(ROOT / 'config/q2-iq2-fixed-bounds-model-results.json') ==
            plan['saved_parent_results_sha256'], 'Saved parent timing differs')
    require(sha(ROOT / 'config/q2-fixed-prefill-reference.json') ==
            plan['fixed_reference_sha256'], 'Fixed reference differs')
    result = read(EVIDENCE / 'result.json')
    release = read(EVIDENCE / 'release.json')
    require(result['complete'] and result['plan_sha256'] == sha(EVIDENCE / 'plan.json')
            and len(result['arms']) == 1, 'Model window did not complete')
    arm = result['arms'][0]
    require(arm['exit_code'] == 0 and arm['stop_reason'] is None and
            arm['original_input_match'], 'Model command failed or input changed')
    work = EVIDENCE / arm['name']
    require(sha(work / 'stdout') == arm['stdout_sha256'] and
            sha(work / 'stderr') == arm['stderr_sha256'], 'Model logs differ')
    require(release['result_sha256'] == sha(EVIDENCE / 'result.json') and
            release['plan_sha256'] == sha(EVIDENCE / 'plan.json') and
            release['kfd'] == [] and release['leases_free'] == 5 and
            release['models_unchanged'] == 7 and not release['gpu_reserved'],
            'Window closure differs')
    for label in ('cpu-test', 'preflight'):
        require(read(EVIDENCE / (label + '-command.json'))['exit_code'] == 0,
                'CPU/preflight gate failed')
    rows = [json.loads(line) for line in (work / 'stdout').read_text().splitlines()
            if line.startswith('{')]
    loaded = next(r for r in rows if r['event'] == 'loaded')
    require(loaded['max_context'] == 9216 and loaded['prefill_chunk'] == 2048 and
            loaded['mtp'] is False and rows[-1]['event'] == 'complete' and
            rows[-1]['finite_frontiers'] and rows[-1]['semantic_smoke'],
            'Model scope or finite completion differs')
    samples = [r for r in rows if r['event'] == 'sample' and r['label'] == 'pp2048']
    require(len(samples) == 4 and [r['rep'] for r in samples] == [0, 1, 2, 3] and
            all(r['warmup'] == (r['rep'] == 0) and r['prompt_tokens'] == 2048 and
                r['output_tokens'] == 128 and r['decode_steps'] == 127 and
                not r['eos'] for r in samples), 'Frozen measurement scope differs')
    outputs = work / 'results'
    require(set(arm['files']) == set(plan['saved_parent_artifacts']),
            'Original-model artifact set differs')
    replay = {}
    for name, binding in arm['files'].items():
        require(sha(outputs / name) == binding['sha256'] and
                (outputs / name).stat().st_size == binding['bytes'], 'Model artifact differs')
        replay[name] = compare(PARENT / name, outputs / name)
    within = {f'{rep}-{phase}': compare(outputs / f'pp2048-0-{phase}',
                                      outputs / f'pp2048-{rep}-{phase}')
              for rep in (1, 2, 3) for phase in ('prefill.f32', 'last.f32', 'output.u32')}
    parent = read(ROOT / 'config/q2-iq2-fixed-bounds-model-results.json')['model']
    fixed = read(ROOT / 'config/q2-fixed-prefill-reference.json')['arms']
    measurements = {}
    for key in ('prefill_tok_s', 'decode_steps_s'):
        values = [r[key] for r in samples if not r['warmup']]
        reference = parent['measurements'][key]['median']
        value = statistics.median(values)
        measurements[key] = {'samples': values, 'median': value,
                             'saved_parent_median': reference,
                             'change_percent': 100 * (value / reference - 1),
                             'fixed_q2_median': fixed['mixed']['measurements'][key]['median'],
                             'fixed_ud_median': fixed['ud']['measurements'][key]['median']}
    report = {
        'schema': 'synapse-lie.q2-hc-scalar-model-results.v1',
        'plan_sha256': sha(EVIDENCE / 'plan.json'), 'source_commit': plan['source_commit'],
        'binary_sha256': result['binary_sha256'], 'model_exit_code': arm['exit_code'],
        'artifacts_collected': len(artifacts), 'samples': samples, 'loaded': loaded,
        'measurements': measurements, 'parent_replay': replay, 'within_arm_replay': within,
        'all_parent_files_exact': all(r['exact'] for r in replay.values()),
        'all_within_arm_files_exact': all(r['exact'] for r in within.values()),
        'all_frontiers_finite': all(r.get('finite', True) for r in replay.values()),
        'precision_reduced_by_this_change': False,
        'inherited_parent_task_quality_qualified': False,
        'controls_rerun': False, 'contemporaneous_control': False,
        'native_long_context_measured': False, 'goal_met': False,
        'peak_cpu_mc': arm['peak_cpu_mc'], 'peak_gpu_mc': arm['peak_gpu_mc'],
        'release_at': release['at'], 'release_sha256': sha(EVIDENCE / 'release.json'),
        'retired_identities': len(release['retired_identities']),
        'retired_groups': len(release['retired_groups']),
    }
    (ROOT / 'config/q2-hc-scalar-model-results.json').write_text(
        json.dumps(report, indent=2, allow_nan=False) + '\n')
    with (ROOT / 'docs/figures/q2-hc-scalar-model-samples.csv').open('w') as out:
        writer = csv.writer(out)
        writer.writerow(['arm', 'rep', 'warmup', 'prefill_tok_s', 'decode_steps_s',
                         'prefill_s', 'decode_s'])
        for label, cohort in (('saved_parent', parent['samples']), ('hc_scalar', samples)):
            for row in cohort:
                if row['label'] == 'pp2048':
                    writer.writerow([label, *[row[k] for k in
                        ('rep', 'warmup', 'prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s')]])
    print(json.dumps({k: v for k, v in report.items() if k not in
                      ('parent_replay', 'within_arm_replay', 'samples')}, indent=2))


if __name__ == '__main__':
    main()
