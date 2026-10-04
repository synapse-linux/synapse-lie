#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit complete raw-HC/shared-Q8 cycles without claiming model throughput."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    output = ROOT/'config/q2-shared-q8-producer-r3-results.json'
    if output.exists():
        raise ValueError('Refusing to overwrite retained results')
    plan_path = ROOT/'config/q2-shared-q8-producer-r3-plan.json'
    plan = read(plan_path)
    for name, expected in {**plan['manifests'], **plan['fixtures']}.items():
        if sha(ROOT/name) != expected:
            raise ValueError('Frozen identity changed: '+name)
    if sha(ROOT/'tools/q2-shared-q8-producer-r3-window.py') != plan['window_helper_sha256']:
        raise ValueError('Frozen window helper changed')
    arm = plan['arms'][0]
    path = ROOT/'evidence'/arm['label']
    transport = read(path/'transport.json')
    collection = read(path/'collection.json')
    receipt = read(path/'results/result.json')
    if (receipt['mode'] != arm['mode'] or receipt['model_access'] or
            transport['source_variant'] != arm['variant'] or
            sha(path/'source.tar.gz') != transport['capsule_sha256'] or
            sha(path/'results.tar.gz') != collection['sha256']):
        raise ValueError('Component scope or capsule differs')
    for name, meta in receipt['artifacts'].items():
        payload = path/'results'/name
        if payload.stat().st_size != meta['bytes'] or sha(payload) != meta['sha256']:
            raise ValueError('Artifact integrity mismatch: '+name)
    provider = read(ROOT/'config/q2-shared-q8-producer-source.json')
    with tarfile.open(path/'source.tar.gz') as archive:
        files = {m.name[7:]: hashlib.sha256(archive.extractfile(m).read()).hexdigest()
                 for m in archive.getmembers() if m.isfile() and m.name.startswith('source/')}
        if files != provider['files']:
            raise ValueError('Provider inventory differs')
        for name, expected in plan['fixtures'].items():
            if hashlib.sha256(archive.extractfile(name).read()).hexdigest() != expected:
                raise ValueError('Measured fixture differs: '+name)
    commands = receipt['commands']
    if len(commands) != 3 or any(c['exit_code'] for c in commands[:2]):
        raise ValueError('Configure/build did not complete')
    if receipt['binary_sha256'] != receipt['binary_sha256_after']:
        raise ValueError('Component binary changed')
    maxima = {}
    for line in (path/'results/telemetry.jsonl').read_text().splitlines():
        for sensor in json.loads(line)['thermal']:
            if sensor['over_limit']:
                raise ValueError('Thermal stop retained')
            name = sensor['device']
            maxima[name] = max(maxima.get(name, -273000), sensor['temperature_mc'])
    records = [json.loads(line) for line in (path/'results/03.log').read_text().splitlines()
               if line.startswith('{')]
    samples = [r for r in records if r['event'] == 'shared_q8_timing']
    groups = {}
    for scope in ('producer', 'complete'):
        values = [[r for r in samples if r['scope'] == scope and r['order'] == order]
                  for order in range(3)]
        for order, rows in enumerate(values):
            if [r['rep'] for r in rows] != list(range(15)):
                raise ValueError('Incomplete chronological sample sequence')
            if any(r['n'] != 2048 or r['launches'] != 16 or
                   r['weight_bytes'] != plan['protocol']['rotating_weight_bytes'] or
                   r['fused'] != (order == 1) or
                   not math.isfinite(r['us_per_cycle']) or r['us_per_cycle'] <= 0 for r in rows):
                raise ValueError('Component sample scope differs')
        medians = [statistics.median(r['us_per_cycle'] for r in rows) for rows in values]
        wins = sum(values[1][i]['us_per_cycle'] < min(values[0][i]['us_per_cycle'],
                                                    values[2][i]['us_per_cycle']) for i in range(15))
        groups[scope] = dict(median_us=dict(zip(('before','candidate','after'), medians)),
            candidate_time_change_percent={name:100*(medians[1]/medians[i]-1)
                                           for name,i in (('before',0),('after',2))},
            unchanged_control_drift_percent=100*(medians[2]/medians[0]-1),
            paired_wins_against_both= wins, repetitions=15)
    exact = [r for r in records if r['event'] == 'shared_q8_exact']
    oracles = [r for r in records if r['event'] == 'shared_q8_gpu_oracle']
    hc = [r for r in records if r['event'] == 'hc_up_fused']
    numerical = (len(exact) == 50 and all(r['exact'] for r in exact) and
                 [r['n'] for r in oracles] == [96,97,127,129,2048] and
                 all(r['exact'] for r in oracles) and len(hc) == 2 and
                 all(r['independent_pass'] and r['exact_mixed'] and r['exact_half'] and
                     r['exact_inject'] for r in hc))
    timing = (all(delta < 0 for g in groups.values()
                  for delta in g['candidate_time_change_percent'].values()) and
              groups['complete']['paired_wins_against_both'] >= 12)
    report = dict(schema='synapse-lie.q2-shared-q8-producer-r3-results.v1',
        scope='Synthetic GPU producer and complete shared-expert cycles, physical2048,16 rotating weight sets; not original-weight model throughput.',
        plan_sha256=sha(plan_path), source_capsule_sha256=transport['capsule_sha256'],
        archive_sha256=collection['sha256'], source_files_verified=len(files),
        artifacts_verified=collection['verified_artifacts'], binary_sha256=receipt['binary_sha256'],
        command_exits=[c['exit_code'] for c in commands], thermal_max_mc=maxima,
        samples=samples,groups=groups,exact_checks=exact,independent_gpu_q8=oracles,
        independent_hc=hc,cpu_diagnostics=[r for r in records if r['event']=='shared_q8_cpu_diagnostic'],
        component_numerical_gate=numerical, component_timing_gate=timing,
        next_fixed_model_point_admitted=numerical and timing and commands[-1]['exit_code']==0,
        component_candidate_retained=True, retained_r1_r2_failures=True,
        norm_candidate_composed=False, whole_control_binary_replay_implemented=False,
        model_throughput_measured=False, model_quality_qualified=False,
        promoted=False,goal_met=False,full_curve_admitted=False)
    with output.open('x') as stream:
        stream.write(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps(dict(groups=groups,numeric=numerical,timing=timing,
        next_fixed_model_point=report['next_fixed_model_point_admitted'],
        artifacts=report['artifacts_verified'],model_throughput=False,goal_met=False)))


if __name__ == '__main__':
    main()
