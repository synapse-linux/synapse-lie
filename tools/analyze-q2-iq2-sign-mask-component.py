#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain IQ2 differential verdict and actual rotated-weight timings separately."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('hc', ROOT/'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)
require, sha, read = hc.require, hc.sha, hc.read


def main():
    output = ROOT/'config/q2-iq2-sign-mask-component-results.json'
    require(not output.exists(), 'Refusing to overwrite component evidence')
    plan_path = ROOT/'config/q2-iq2-sign-mask-plan.json'
    plan = read(plan_path)
    for name, digest in {**plan['manifests'], **plan['fixtures']}.items():
        require(sha(ROOT/name) == digest, 'Frozen identity changed: '+name)
    arm = plan['component']
    path = ROOT/'evidence'/arm['label']
    result, transport = hc.curve.artifact_integrity(path)
    exits = [c['exit_code'] for c in result['commands']]
    require(exits in ([0,0,0], [0,0,1]) and result['finished_at'] and
            result['mode'] == transport['mode'] == arm['mode'] and
            transport['source_variant'] == arm['variant'] and not transport['rebuild_mmq'] and
            not result['model_access'] and result['binary_sha256'] == result['binary_sha256_after'],
            'Incomplete or changed component')
    require(result['locks'] == result['postflight_locks'] and len(result['locks']) == 4 and
            not result['preflight_kfd'] and not result['postflight_kfd'], 'Component ownership changed')
    source = read(ROOT/'config/q2-iq2-sign-mask-source.json')['variants'][arm['variant']]
    capsule = hc.capsule(path, plan['fixtures'], source['files'])
    log = (path/'results/03.log').read_text()
    events = [json.loads(line) for line in log.splitlines() if line.startswith('{"event"')]
    replay = [e for e in events if e['event'] == 'iq2_sign_mask_replay']
    timings = [e for e in events if e['event'] == 'iq2_sign_mask_timing']
    complete = [e for e in events if e['event'] == 'iq2_sign_mask_complete']
    require(len(replay) == 81 and len(timings) == 42 and len(complete) == 1 and
            complete[0]['timing_retained'] and not complete[0]['model_inference'],
            'Missing complete outputs or independent timing retention')
    require(all(e['exact'] == (e['changed_values'] == 0 and e['nonfinite_values'] == 0 and
                e['unwritten_values'] == 0 and e['guards_exact']) and
                (e['changed_values'] == 0) == (e['reference_sha256'] == e['candidate_sha256'])
                for e in replay), 'Replay flags differ')
    require(len({(e['case'], e['rotation']) for e in replay}) == 81 and
            all(e['guards_exact'] and e['rotation'] in (0,1,2) for e in replay),
            'Incomplete replay coverage or unsafe guards')
    formats = [e for e in events if e['event'] == 'iq2_sign_mask_format']
    require(len(formats) == 1 and formats[0]['entries'] == 32768 and
            formats[0]['checked_high_bytes'] == 262144 and formats[0]['guards_exact'] and
            formats[0]['unwritten_or_invalid'] == 0 and
            formats[0]['exact'] == (formats[0]['changed_bytes'] == 0), 'Unsafe/incomplete device-table replay')
    for key in ('candidate', 'reference'):
        data = (path / 'results' / ('iq2-sign-mask-format-' + key + '.u8')).read_bytes()
        require(len(data) == 262144 + 128 and data[:64] == bytes([0xd3])*64 and
                data[-64:] == bytes([0xd3])*64 and
                sha(path / 'results' / ('iq2-sign-mask-format-' + key + '.u8')) == formats[0][key + '_sha256'],
                'Device format bytes/guards/hash changed')
    numerical = formats[0]['exact'] and all(e['exact'] for e in replay)
    require(complete[0]['numerical_pass'] == numerical and exits[-1] == (0 if numerical else 1),
            'Numerical rejection or command exit lost')
    groups = []
    for active in (64,128,512):
        shape, m, k = 'mixed-e'+str(active), 640, 2560
        pair = {}
        for candidate in (False, True):
            rows = [t for t in timings if t['case'] == shape and t['candidate'] == candidate]
            require([r['rep'] for r in rows] == list(range(7)) and
                    [r['warmup'] for r in rows] == [True,True]+[False]*5 and
                    all(r['candidate'] == (((r['rep']+r['order'])%2) != 0) and
                        r['tokens'] == 2048 and r['output_rows'] == m and r['inner'] == k and
                        r['iterations'] == 3 and r['weight_bytes'] == plan['component_weight_rotation_bytes'][str(active)]
                        and r['active_experts'] == active and r['width'] == 0
                        and r['weight_bytes'] > 32*1024*1024 and r['us_per_iteration'] > 0 for r in rows),
                    'Changed component shape/order/rotation')
            pair['candidate' if candidate else 'reference'] = hc.shared.common.stats(
                [r['us_per_iteration'] for r in rows if not r['warmup']])
        groups.append(dict(case=shape, **pair, candidate_time_change_percent=
            100*(pair['candidate']['median']/pair['reference']['median']-1)))
    report = dict(schema='synapse-lie.q2-iq2-sign-mask-component.v1', **capsule,
        plan_sha256=sha(plan_path), command_exits=exits, artifact_count=len(result['artifacts']),
        binary_sha256=result['binary_sha256'], numerical_exact=numerical,
        replay=replay, timings=timings, summaries=groups, device_format=formats[0], model_inference=False,
        original_inputs_immutable_at_fixture_completion=True,
        control_scope='Literal parent numerical control inside new fixture; no qualified model/cohort rerun',
        independent_model_quality_qualification=False, full_model_speedup=False, goal_met=False,
        timing_scope=plan['component_time_scope'])
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(command_exits=exits, numerical_exact=numerical,
                         timings=len(timings), complete_outputs=len(replay), summaries=groups)))


if __name__ == '__main__':
    main()
