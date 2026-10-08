#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the complete pack/projection/convolution component, without GPU work."""
import hashlib
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT/'evidence/q2-ssm-stage-q8-component-r1'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def analyze(rows, exit_code):
    def events(name):
        return [r for r in rows if r['event'] == name]
    replay = events('ssm_stage_q8_replay')
    oracle = events('ssm_resident_oracle')
    timings = events('ssm_stage_q8_timing')
    packs = events('ssm_stage_q8_pack_check')
    domain = events('ssm_stage_q8_pack_domain')
    complete = events('ssm_stage_q8_complete')
    cases = events('ssm_stage_q8_case')
    resources = events('ssm_stage_q8_resources')
    require(len(replay) == 78 and len(oracle) == 156 and len(timings) == 16,
            'Incomplete operator/timing evidence')
    shapes = ['ssm1024','ssm1025','ssm1057','ssm2048','ssm2049'] + [f'ssm2048-timed-r{i}' for i in range(8)]
    identities = {(s,r,f) for s in shapes for r in range(3) for f in ('projection','convolution')}
    require({(r['shape'],r['rotation'],r['field']) for r in replay} == identities,
            'Missing or duplicated complete comparison')
    require({(r['shape'],r['rotation'],r['field'],r['arm']) for r in oracle} ==
            {(*i,a) for i in identities for a in ('reference','candidate')},
            'Missing or duplicated independent comparison')
    require(len(packs) == 40 and all(r['exact'] and r['bytes'] == 44564480 for r in packs),
            'Incomplete or inexact packed bytes')
    require(len(domain) == 1 and domain[0]['exact'] and
            domain[0]['scale_patterns'] == 65536 and domain[0]['all_codes'] == 256 and
            domain[0]['allocation_end_input'], 'Scale/code packing domain differs')
    require(len(cases) == 5 and {r['shape'] for r in cases} ==
            {'ssm1024','ssm1025','ssm1057','ssm2048','ssm2049'} and
            all(r['guards_finite_written'] and r['inputs_unchanged'] for r in cases),
            'Case safety checks differ')
    require(len(resources) == 2 and {r['candidate'] for r in resources} == {False,True},
            'Missing launch resources')
    require(all(r['guards_exact'] and r['nonfinite_values'] == 0 and
                r['unwritten_values'] == 0 and r['unexpected_unused_values'] == 0
                for r in replay), 'Unsafe outputs')
    require(all(r['limit'] == 0.002 and r['samples'] == 24 and
                math.isfinite(r['relative_rms']) and math.isfinite(r['scaled_error']) and
                r['pass'] == (r['relative_rms'] <= r['limit'] and r['scaled_error'] <= r['limit'])
                for r in oracle), 'Independent numerical evidence differs')
    numerical = all(r['exact'] for r in replay) and all(r['pass'] for r in oracle)
    require(len(complete) == 1 and complete[0]['safe_completion'] and
            complete[0]['timing_retained'] and not complete[0]['model_inference'] and
            complete[0]['numerical_pass'] == numerical and
            exit_code == (0 if numerical else 1), 'Actual numerical exit differs')
    require(all(r['shape'] == 'ssm2048' and r['tokens'] == 2048 and
                r['output_rows'] == 16384 and r['inner'] == 2560 and
                r['iterations'] == 3 and r['weight_bytes'] == 133693440 and
                math.isfinite(r['completed_wall_us']) and r['completed_wall_us'] > 0
                for r in timings), 'Timed scope differs')
    require([(r['rep'],r['order'],r['candidate'],r['warmup']) for r in timings] ==
            [(rep,order,bool((rep+order)%2),rep<2) for rep in range(8) for order in range(2)],
            'Missing, duplicate or unbalanced chronological timing')
    valid_gpu = all(r['gpu_event_valid'] and r['gpu_event_us'] is not None and
                    math.isfinite(r['gpu_event_us']) and r['gpu_event_us'] > 0 for r in timings)
    measured = [r for r in timings if not r['warmup']]
    scopes = {}
    for key in ('completed_wall_us','gpu_event_us'):
        if key == 'gpu_event_us' and not valid_gpu:
            continue
        arms = {}
        for candidate, name in ((False,'retained'),(True,'stage_q8')):
            values = [r[key] for r in measured if r['candidate'] == candidate]
            arms[name] = dict(samples_us=values,mean_us=statistics.mean(values),
                              minimum_us=min(values),maximum_us=max(values))
        pairs = []
        for rep in range(2,8):
            a = {r['candidate']:r[key] for r in measured if r['rep'] == rep}
            pairs.append(dict(rep=rep,latency_change_percent=100*(a[True]/a[False]-1)))
        scopes[key] = dict(arms=arms,pairs=pairs,mean_latency_change_percent=100*
                          (arms['stage_q8']['mean_us']/arms['retained']['mean_us']-1))
    return dict(numerical_pass=numerical,component_exit_code=exit_code,
                exact_output_pairs=sum(r['exact'] for r in replay),output_pairs=len(replay),
                independent_checks=len(oracle),independent_checks_passed=sum(r['pass'] for r in oracle),
                packed_checks=len(packs),scale_patterns=65536,all_gpu_events_valid=valid_gpu,
                all_timings=timings,timing_scopes=scopes,resources=resources,
                packing_in_complete_timer=True,model_trial=False,
                model_throughput_gain=False,goal_met=False)


def main():
    plan = read(EVIDENCE/'plan.json')
    require(sha(EVIDENCE/'plan.json') == sha(ROOT/'config/q2-ssm-stage-q8-plan.json'),
            'Frozen plan differs')
    for name, digest in read(EVIDENCE/'artifact-hashes.json').items():
        require(sha(EVIDENCE/name) == digest, 'Collected artifact differs: '+name)
    for name, digest in plan['staged_sha256'].items():
        require(sha(EVIDENCE/name) == digest, 'Staged artifact differs: '+name)
    for mode in ('cpu-test','verify','admit','release'):
        require(read(EVIDENCE/(mode+'-command.json'))['exit_code'] == 0, 'Window command failed: '+mode)
    result = read(EVIDENCE/'result.json')
    release = read(EVIDENCE/'release.json')
    closure = read(EVIDENCE/'release-registry-check.json')
    collection = read(EVIDENCE/'local-collection-check.json')
    require(result['state'] == 'COMPLETE' and
            read(EVIDENCE/'run-command.json')['exit_code'] == result['exit_code'], 'Incomplete run')
    require(release['plan_sha256'] == sha(EVIDENCE/'plan.json') and
            release['component_result_sha256'] == sha(EVIDENCE/'result.json') and
            release['component_exit_code'] == result['exit_code'] and
            not release['gpu_reserved'] and all(release[k] for k in
            ('kfd_empty','original_leases_free','original_model_stats_unchanged')) and
            closure['registry_matches'] and closure['release_sha256'] == sha(EVIDENCE/'release.json') and
            collection['all_sha256_verified'] and collection['at'] < release['at'], 'Closure differs')
    rows = [json.loads(line) for line in (EVIDENCE/'component.stdout').read_text().splitlines()
            if line.startswith('{')]
    report = analyze(rows,result['exit_code'])
    report.update(schema='synapse-lie.q2-ssm-stage-q8-results.v1',
                  source_commit=plan['source_commit'],plan_sha256=sha(EVIDENCE/'plan.json'),
                  release_sha256=sha(EVIDENCE/'release.json'),release_at=release['at'])
    path = ROOT/'config/q2-ssm-stage-q8-results.json'
    with path.open('x') as stream:
        json.dump(report,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('all_timings','resources')}))


if __name__ == '__main__':
    main()
