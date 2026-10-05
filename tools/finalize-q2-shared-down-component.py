#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit shared-down evidence, preserve the regressions and keep saved model 1585."""
import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT/'evidence/q2-shared-down-runtime-preparation'
spec = importlib.util.spec_from_file_location('shared_down', ROOT/'tools/analyze-q2-shared-down-component.py')
analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analysis)
hc = analysis.hc


def main():
    plan_path = ROOT/'config/q2-shared-down-component-plan.json'
    plan = hc.read(plan_path)
    for path, digest in {**plan['fixtures'], **plan['manifests'],
                         plan['window_helper']: plan['window_helper_sha256']}.items():
        hc.require(hc.sha(ROOT/path) == digest, 'Frozen identity changed: '+path)
    release_path = ROOT/plan['release_path']
    release = hc.read(release_path)
    hc.require(release['state'] == 'Q2_SHARED_DOWN_COMPONENT_WINDOW_RELEASED' and
               not release['gpu_reserved'] and not release['kfd'] and not release['owned_group_members'] and
               release['model_stats_unchanged'] and len(release['models']) == 7 and
               len(release['leases']) == 4 and all(r['unchanged_free_EX_NB'] for r in release['leases']),
               'Incomplete release')
    for suffix in ('window-release.json', 'window-active.json', 'ready.json'):
        hc.require((ROOT.parents[1]/'run'/('q2-shared-down-component-'+suffix)).read_bytes() ==
                   release_path.read_bytes(), 'Main mirror changed')
    hc.require(hc.read(PREP/'release-publish-command.json')['exit_code'] == 0, 'Remote mirror incomplete')
    exits, artifacts, peaks = [], 0, {}
    for label, key in ((plan['host'], 'host'), (plan['component']['label'], 'component')):
        path = ROOT/'evidence'/label
        receipt, _ = hc.curve.artifact_integrity(path)
        collected = hc.read(PREP/(key+'-collection-command.json'))
        hc.require(receipt['finished_at'] < release['at'] and collected['exit_code'] == 0 and
                   collected['finished_at'] < release['at'], 'Release preceded collection')
        exits += [c['exit_code'] for c in receipt['commands']]
        artifacts += len(receipt['artifacts'])
        thermal = {}
        for line in (path/'results/telemetry.jsonl').read_text().splitlines():
            for row in json.loads(line).get('thermal', []):
                hc.require(not row['over_limit'], 'Thermal boundary crossed')
                thermal[row['device']] = max(thermal.get(row['device'], 0), row['temperature_mc']/1000)
        peaks[label] = thermal
    hc.require(len(exits) == 9 and exits[:8] == [0]*8 and exits[8] in (0, 1), 'Unexpected runtime exits')
    result_path = ROOT/'config/q2-shared-down-component-results.json'
    result = hc.read(result_path)
    hc.require(result['device_work_safe'] and len(result['replay']) == 126 and
               len(result['oracle']) == 168 and len(result['formats']) == 42 and
               sum(r['values'] for r in result['formats']) == 68812800 and len(result['timings']) == 28,
               'Incomplete component scope')
    figures = {str(p.relative_to(ROOT)): hc.sha(p) for p in
               (ROOT/'docs/figures').glob('q2-shared-down-component.*')}
    hc.require(len(figures) == 3, 'Incomplete exports')
    with (ROOT/'docs/figures/q2-shared-down-component.csv').open() as f:
        hc.require(len(list(csv.DictReader(f))) == 28, 'Incomplete CSV')
    failures = {p.name: hc.read(p)['exit_code'] for p in PREP.glob('*-command.json') if hc.read(p)['exit_code']}
    allowed = {'runtime-checks-command.json': 1}
    if exits[-1] == 1:
        allowed['component-launch-command.json'] = 1
    hc.require(failures == allowed, 'Unclassified failure')
    report = dict(schema='synapse-lie.q2-shared-down-component-final.v1',
                  plan_sha256=hc.sha(plan_path), result_sha256=hc.sha(result_path),
                  release_sha256=hc.sha(release_path), runtime_command_exits=exits,
                  artifacts_verified=artifacts, host_reused=False,
                  frozen_fixtures_verified=len(plan['fixtures']), frozen_manifests_verified=len(plan['manifests']),
                  provider_files_verified=result['source_files_verified'],
                  retired_identities=len(release['retired_identities']), retired_groups=len(release['retired_groups']),
                  thermal_max_c=peaks, figures=figures, preserved_nonzero_exits=failures,
                  failure_classification={'runtime-checks-command.json':
                      'Initial local test label lacked q2- prefix; corrected test passes6. No GPU numerical failure.'},
                  numerical_pass=result['numerical_pass'], time_change_percent=result['time_change_percent'],
                  decision='RETAIN_COMPONENT_EVIDENCE_KEEP_SAVED1585',
                  retained_model=plan['saved_best'], controls_rerun=False, model_inference=False,
                  independent_model_quality=False, full_curve=False, promoted=False, goal_met=False)
    hc.write(ROOT/'config/q2-shared-down-component-final-audit.json', report)
    print(json.dumps(report))


if __name__ == '__main__':
    main()
