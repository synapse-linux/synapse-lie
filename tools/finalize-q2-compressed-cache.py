#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Close the bounded cache experiment using collected evidence and saved controls."""
import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / 'evidence/q2-compressed-cache-preparation'
spec = importlib.util.spec_from_file_location('expert_cache', ROOT / 'tools/analyze-q2-compressed-cache.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
hc = analysis.hc


def main():
    plan, source = analysis.bound()
    component_path = ROOT / 'config/q2-compressed-cache-component-results.json'
    model_path = ROOT / 'config/q2-compressed-cache-model-results.json'
    component, model = hc.read(component_path), hc.read(model_path)
    hc.require(component == analysis.component(plan, source), 'Component report changed')
    hc.require(model == analysis.model(plan, source), 'Model report changed')
    release_path = ROOT / plan['release_path']
    release = hc.read(release_path)
    hc.require(release['state'] == 'Q2_COMPRESSED_CACHE_WINDOW_RELEASED' and
               not release['gpu_reserved'] and not release['kfd'] and not release['owned_group_members'] and
               release['model_stats_unchanged'] and len(release['models']) == 7 and
               len(release['leases']) == 4 and all(r['unchanged_free_EX_NB'] for r in release['leases']),
               'Incomplete release')
    for suffix in ('window-release.json', 'window-active.json', 'ready.json'):
        hc.require((ROOT.parents[1] / 'run' / ('q2-compressed-cache-' + suffix)).read_bytes() ==
                   release_path.read_bytes(), 'Main mirror changed')
    hc.require(hc.read(PREP / 'release-publish-command.json')['exit_code'] == 0,
               'Remote mirror publication incomplete')
    exits, artifacts, peaks = [], 0, {}
    for kind in ('host', 'component', 'model'):
        path = ROOT / 'evidence' / plan[kind]
        receipt, _ = hc.curve.artifact_integrity(path)
        collected = hc.read(PREP / (('host-r2' if kind == 'host' else kind) + '-collection-command.json'))
        hc.require(receipt['finished_at'] < release['at'] and collected['exit_code'] == 0 and
                   collected['finished_at'] < release['at'], 'Release preceded collection')
        exits += [c['exit_code'] for c in receipt['commands']]
        artifacts += len(receipt['artifacts'])
        if kind == 'host':
            hc.require(hc.sha(path / 'results/result.json') == plan['host_result_sha256'],
                       'Frozen host receipt changed')
        thermal = {}
        for line in (path / 'results/telemetry.jsonl').read_text().splitlines():
            for row in json.loads(line).get('thermal', []):
                hc.require(not row['over_limit'], 'Thermal boundary crossed')
                thermal[row['device']] = max(thermal.get(row['device'], 0), row['temperature_mc'] / 1000)
        peaks[plan[kind]] = thermal
    hc.require(len(exits) == 13 and exits[:8] == [0] * 8 and exits[8] in (0, 1) and
               exits[9:] == [0] * 4 and artifacts == 37, 'Unexpected runtime scope')
    figures = {str(p.relative_to(ROOT)): hc.sha(p) for p in
               (ROOT / 'docs/figures').glob('q2-compressed-cache-*')}
    hc.require(len(figures) == 6, 'Incomplete exports')
    for name, count in (('component', 56), ('model', 16)):
        with (ROOT / 'docs/figures' / ('q2-compressed-cache-' + name + '.csv')).open() as f:
            rows = list(csv.DictReader(f))
        hc.require(len(rows) == count, 'Incomplete CSV')
        if name == 'component':
            hc.require([float(r['us']) for r in rows] == [r['us'] for r in component['timings']],
                       'Exported component samples changed')
        else:
            arms = [model['references'][k] for k in ('fixed_q2', 'best_parent')]
            arms += [model['model'], model['references']['fixed_ud']]
            for field in ('prefill_tok_s', 'decode_steps_s', 'prefill_s', 'decode_s'):
                hc.require([float(r[field]) for r in rows] ==
                           [r[field] for arm in arms for r in arm['samples']], 'Exported model samples changed')
    failures = {p.name: hc.read(p)['exit_code'] for p in PREP.glob('*-command.json')
                if hc.read(p)['exit_code']}
    allowed = {}
    if exits[8] == 1:
        allowed['component-launch-command.json'] = 1
    hc.require(failures == allowed, 'Unclassified retained failure')
    preliminary_path = ROOT / 'evidence/q2-compressed-cache-host-r1'
    preliminary, _ = hc.curve.artifact_integrity(preliminary_path)
    preliminary_exits = [c['exit_code'] for c in preliminary['commands']]
    hc.require(preliminary_exits == [0]*6 and preliminary['finished_at'] < release['at'],
               'Preliminary host not retired')
    hc.require(hc.read(PREP/'host-collection-command.json')['exit_code'] == 0,
               'Preliminary host not collected')
    exact = not model['checks']['best_parent']['changed_files']
    gain = model['candidate_median_change_percent']['best_parent']['prefill_tok_s'] > 0
    report = dict(schema='synapse-lie.q2-compressed-cache-final.v1', plan_sha256=hc.sha(analysis.PLAN),
                  model_result_sha256=hc.sha(model_path), component_result_sha256=hc.sha(component_path),
                  release_sha256=hc.sha(release_path), runtime_command_exits=exits, artifacts_verified=artifacts,
                  preliminary_host_exits=preliminary_exits, preliminary_host_artifacts=len(preliminary['artifacts']),
                  all_campaign_artifacts=artifacts+len(preliminary['artifacts']),
                  frozen_fixtures_verified=len(plan['fixtures']), frozen_manifests_verified=len(plan['manifests']),
                  provider_files_verified=len(source['files']), host_reused=False,
                  retired_identities=len(release['retired_identities']), retired_groups=len(release['retired_groups']),
                  thermal_max_c=peaks, figures=figures, preserved_nonzero_exits=failures,
                  failure_classification={},
                  component_numerical_pass=component['numerical_pass'], parent_model_checks=model['checks']['best_parent'],
                  within_arm_exact=model['within_arm_exact'], cache=model['cache'], cache_stats=model['cache_stats'],
                  candidate_median_change_percent=model['candidate_median_change_percent'],
                  decision='RETAIN_COMPRESSED_CACHE_CANDIDATE_AND_PARENT' if gain and exact and component['numerical_pass']
                           else 'RETAIN_EXPERIMENT_KEEP_SAVED1585',
                  next_composition_variant='compressed-cache' if gain and exact and component['numerical_pass']
                                           else 'ssm-fixed-bounds',
                  controls_rerun=False, independent_model_quality=False, full_curve=False, promoted=False,
                  goal_met=False)
    output = ROOT / 'config/q2-compressed-cache-final-audit.json'
    hc.require(not output.exists(), 'Refusing to overwrite final audit')
    hc.write(output, report)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
