#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit retained three-arm component results; never label them model rates."""
import hashlib
import json
import math
from pathlib import Path
import statistics
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def arm(spec, plan, host):
    folder = ROOT/'evidence'/spec['label']
    result = read(folder/'results/result.json')
    transport = read(folder/'transport.json')
    collected = read(folder/'collection.json')
    require(result['mode'] == spec['mode'] and not result['model_access'], 'Wrong scope')
    require(transport['source_variant'] == spec['variant'], 'Wrong provider')
    require(transport['capsule_sha256'] == sha(folder/'source.tar.gz'), 'Changed capsule')
    require(not result.get('thermal_stop') and not result.get('postflight_error') and
            result['postflight_kfd'] == [] and result['preflight_kfd'] == [], 'Lifecycle failure')
    require(result['locks'] == result['postflight_locks'] and len(result['locks']) == 4,
            'Lease identity changed')
    require(result['binary_sha256'] == result['binary_sha256_after'], 'Binary changed')
    manifest_name = ('q2-scaled-row-reuse-source.json' if spec['variant'] == 'scaled-row-reuse'
                     else 'q2-iq2-signs-ordered-asm-source.json')
    manifest = read(ROOT/'config'/manifest_name)
    with tarfile.open(folder/'source.tar.gz') as capsule:
        for name, digest in host['qualified_files'].items():
            require(plan['harness_files'][name] == digest and
                    hashlib.sha256(capsule.extractfile(name).read()).hexdigest() == digest,
                    'Unqualified harness bytes: ' + name)
        files = {m.name.removeprefix('source/'): hashlib.sha256(capsule.extractfile(m).read()).hexdigest()
                 for m in capsule.getmembers() if m.isfile() and m.name.startswith('source/')}
        require(files == manifest['files'], 'Provider inventory changed')
    require(collected['sha256'] == sha(folder/'results.tar.gz') and
            collected['verified_artifacts'] == len(result['artifacts']), 'Collection changed')
    for name, meta in result['artifacts'].items():
        path = folder/'results'/name
        require(not Path(name).is_absolute() and '..' not in Path(name).parts, 'Unsafe artifact')
        require(path.stat().st_size == meta['bytes'] and sha(path) == meta['sha256'], 'Artifact changed')
    rows = [json.loads(line) for line in (folder/'results/03.log').read_text().splitlines()
            if line.startswith('{')]
    groups = {kind: [r for r in rows if r['event'] == kind]
              for kind in ('row_geometry', 'row_timing', 'row_pack', 'row_down', 'row_summary')}
    require([len(v) for v in groups.values()] == [5, 70, 42, 10, 1], 'Incomplete component')
    summary = groups['row_summary'][0]
    failures = sum(r['finite_mismatches'] != 0 for r in groups['row_pack']) + sum(
        r['relative_rms'] > .002 or r['error_over_peak'] > .002 for r in groups['row_down'])
    require(summary == dict(event='row_summary', cycles=5, small_cases=32,
                            model_inference=False, failures=failures), 'Incorrect numerical summary')
    exit_code = int(failures != 0)
    require([c['exit_code'] for c in result['commands']] == [0, 0, exit_code] and
            transport['exit_code'] == exit_code, 'Unexpected actual command exits')
    require(result['state'] == ('FAILED' if failures else 'SYNTHETIC_OPERATORS_PASS_NOT_MODEL_QUALIFIED'),
            'Incorrect result state')
    require(all(not c.get('timeout') for c in result['commands']), 'Command timed out')
    timing = {}
    for geometry in groups['row_geometry']:
        case = geometry['case']
        require(geometry['active_weight_bytes'] > 32*1024**2 and
                geometry['input_bytes_per_bank'] > 32*1024**2 and geometry['input_banks'] == 2,
                'Undersized component traffic')
        timing[case] = {}
        for scope in ('pack', 'pack-down'):
            samples = sorted([r for r in groups['row_timing']
                              if r['case'] == case and r['scope'] == scope], key=lambda r: r['sample'])
            require([r['sample'] for r in samples] == list(range(7)) and
                    all(r['warmup'] == (r['sample'] < 2) and r['calls'] == 8 and
                        math.isfinite(r['us_per_call']) and r['us_per_call'] > 0 for r in samples),
                    'Wrong timing samples')
            values = [r['us_per_call'] for r in samples if not r['warmup']]
            timing[case][scope] = dict(samples_us=values, median_us=statistics.median(values),
                                      minimum_us=min(values), maximum_us=max(values))
    return dict(label=spec['label'], command_exits=[c['exit_code'] for c in result['commands']],
                artifact_count=len(result['artifacts']), summary=summary, timing=timing,
                pack=groups['row_pack'], down=groups['row_down'], geometry=groups['row_geometry'],
                result_sha256=sha(folder/'results/result.json'))


def main():
    plan = read(ROOT/'config/q2-scaled-row-plan.json')
    host = read(ROOT/'config/q2-scaled-row-host-results.json')
    require(sha(ROOT/plan['source_manifest']) == plan['source_manifest_sha256'] and
            sha(ROOT/'config/q2-iq2-signs-ordered-asm-source.json') == plan['parent_manifest_sha256'],
            'Plan provider changed')
    arms = [arm(spec, plan, host) for spec in plan['arms']]
    comparisons = []
    for other in arms[1:]:
        # All elements participate in these digests, including zeros and NaNs.
        require(arms[0]['geometry'] == other['geometry'], 'Changed workload')
        left = ROOT/'evidence'/arms[0]['label']/'results'
        right = ROOT/'evidence'/other['label']/'results'
        names = sorted(p.name for p in left.glob('row-*'))
        require(len(names) == 74, 'Incomplete retained differential buffers')
        retained_equal = all((left/n).read_bytes() == (right/n).read_bytes() for n in names)
        comparisons.append(dict(label=other['label'], retained_files=74,
                                retained_files_exact=retained_equal,
                                complete_pack_exact=arms[0]['pack'] == other['pack'],
                                complete_down_exact=arms[0]['down'] == other['down']))
    deltas = {}
    for case in arms[0]['timing']:
        deltas[case] = {}
        for scope in ('pack', 'pack-down'):
            times = [a['timing'][case][scope]['median_us'] for a in arms]
            deltas[case][scope] = dict(before_us=times[0], candidate_us=times[1], after_us=times[2],
                candidate_vs_before_percent=100*(times[1]/times[0]-1),
                candidate_vs_after_percent=100*(times[1]/times[2]-1))
    result = dict(schema='synapse-lie.q2-scaled-row-results.v1',
        scope=plan['scope'], allocation=plan['allocation'], timing=plan['timing'],
        plan_sha256=sha(ROOT/'config/q2-scaled-row-plan.json'), arms=arms,
        comparisons=comparisons, medians=deltas, promoted=False, model_inference=False, goal_met=False,
        numeric_limit='Unchanged scalar conversion and 0.002 FP64 down RMS/peak checks; byte agreement is not independent quality.',
        negative_percent_means='Less component execution time; not model throughput')
    (ROOT/'config/q2-scaled-row-results.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(comparisons=comparisons, medians=deltas,
                          numerical_failures=[a['summary']['failures'] for a in arms]), indent=2))


if __name__ == '__main__':
    main()
