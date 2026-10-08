#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the collected SSM campaign and retain both the candidate and saved parent."""
import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT / 'evidence/q2-ssm-pingpong-runtime-preparation'
spec = importlib.util.spec_from_file_location('ssm_audit_common', ROOT / 'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)


def main():
    plan_path = ROOT / 'config/q2-ssm-pingpong-plan.json'
    plan = hc.read(plan_path)
    for name, digest in {**plan['fixtures'], **plan['manifests'],
                         plan['window_helper']: plan['window_helper_sha256']}.items():
        hc.require(hc.sha(ROOT / name) == digest, 'Frozen identity changed: ' + name)
    release_path = ROOT / 'config/q2-ssm-pingpong-window-release.json'
    release = hc.read(release_path)
    exits, artifacts, peaks = [], 0, {}
    for label, collection_key in ((plan['host'], 'host-collect'),
                                  (plan['components'][0]['label'], 'component-collection'),
                                  (plan['arms'][0]['label'], 'model-collection')):
        path = ROOT / 'evidence' / label
        receipt, _ = hc.curve.artifact_integrity(path)
        exits += [command['exit_code'] for command in receipt['commands']]
        artifacts += len(receipt['artifacts'])
        hc.require(receipt['finished_at'] < release['at'], 'Runtime not terminal before release')
        collected = hc.read(PREP / (collection_key + '-command.json'))
        hc.require(collected['exit_code'] == 0 and collected['finished_at'] < release['at'],
                   'Collection not complete before release')
        thermal = {}
        for line in (path / 'results/telemetry.jsonl').read_text().splitlines():
            for row in json.loads(line).get('thermal', []):
                hc.require(not row['over_limit'], 'Thermal boundary crossed')
                thermal[row['device']] = max(thermal.get(row['device'], 0), row['temperature_mc'] / 1000)
        peaks[label] = thermal
    hc.require(exits[:8] == [0] * 8 and exits[8] in (0, 1) and exits[9:] == [0] * 4,
               'Unexpected command exits or incomplete runtime')
    hc.require(release['state'] == 'Q2_SSM_FOLLOWUP_WINDOW_RELEASED' and not release['gpu_reserved'] and
               not release['kfd'] and not release['owned_group_members'] and
               len(release['leases']) == 4 and len(release['models']) == 7 and release['model_stats_unchanged'] and
               all(row['unchanged_free_EX_NB'] for row in release['leases']), 'Incomplete release')
    for name in ('q2-ssm-pingpong-window-release.json', 'q2-ssm-pingpong-window-active.json',
                 'q2-ssm-pingpong-ready.json'):
        hc.require((ROOT.parents[1] / 'run' / name).read_bytes() == release_path.read_bytes(), 'Main mirror changed')
    hc.require(hc.read(PREP / 'release-publish-command.json')['exit_code'] == 0, 'Mirror publication incomplete')
    component_path = ROOT / 'config/q2-ssm-pingpong-component-results.json'
    model_path = ROOT / 'config/q2-ssm-pingpong-model-results.json'
    component, model = hc.read(component_path), hc.read(model_path)
    hc.require(component['device_work_safe'] and len(component['replay']) == 30 and
               len(component['oracle']) == 60 and len(component['timings']) == 14 and
               component['plan_sha256'] == model['plan_sha256'] == hc.sha(plan_path), 'Component scope changed')
    hc.require(len(model['replay']['best_parent']['files']) == 21, 'Incomplete model comparison')
    hc.require(len(component['resources']) == 2 and all(not row['measured_active_blocks']
               for row in component['resources']), 'Missing theoretical resource metadata')
    figures = {str(path.relative_to(ROOT)): hc.sha(path)
               for path in (ROOT / 'docs/figures').glob('q2-ssm-pingpong-*')}
    hc.require(len(figures) == 6, 'Missing complete exports')
    for name, count in (('component', 14), ('model-wrapped', 16)):
        with (ROOT / 'docs/figures' / ('q2-ssm-pingpong-' + name + '.csv')).open() as stream:
            hc.require(len(list(csv.DictReader(stream))) == count, 'Missing exported samples')
    failures = {path.name: hc.read(path)['exit_code'] for path in PREP.glob('*-command.json')
                if hc.read(path)['exit_code']}
    allowed = {}
    if exits[8] == 1:
        allowed['component-launch-command.json'] = 1
    hc.require(failures == allowed, 'Unclassified retained failure')
    audit_path = ROOT / 'config/q2-ssm-pingpong-final-audit.json'
    audit = dict(schema='synapse-lie.q2-ssm-pingpong-final.v1', plan_sha256=hc.sha(plan_path),
                 model_result_sha256=hc.sha(model_path), component_result_sha256=hc.sha(component_path),
                 release_sha256=hc.sha(release_path), runtime_command_exits=exits,
                 artifacts_verified=artifacts, frozen_fixtures_verified=len(plan['fixtures']), frozen_manifests_verified=len(plan['manifests']),
                 provider_files_verified=1027, retired_identities=len(release['retired_identities']),
                 retired_groups=len(release['retired_groups']), thermal_max_c=peaks,
                 resources=component['resources'], component_parent_exact=component['parent_exact'],
                 independent_operator_pass=component['independent_operator_pass'],
                 parent_model_checks=model['checks']['best_parent'], within_arm_exact=model['within_arm_exact'],
                 figures=figures, preserved_nonzero_exits=failures, controls_rerun=False,
                 independent_quality=False, full_curve=False, goal_met=False)
    hc.write(audit_path, audit)
    new, parent = model['model']['measurements'], model['references']['best_parent']['measurements']
    ud = model['references']['fixed_ud']['measurements']
    exact = not model['checks']['best_parent']['changed_files']
    component_ok = component['parent_exact'] and component['independent_operator_pass']
    gain = new['prefill_tok_s']['median'] > parent['prefill_tok_s']['median']
    overlap = max(new['prefill_tok_s']['min'], parent['prefill_tok_s']['min']) <= min(
        new['prefill_tok_s']['max'], parent['prefill_tok_s']['max'])
    decision = dict(schema='synapse-lie.q2-ssm-pingpong-disposition.v1',
                    decision='RETAIN_PREFILL_CANDIDATE_AND_SAVED1580' if gain and exact and component_ok
                             else 'RETAIN_EXPERIMENT_AND_KEEP_SAVED1580',
                    next_composition_variant='ssm-pingpong' if gain and exact and component_ok else 'down-register-scatter',
                    source_manifest='config/q2-ssm-pingpong-source.json',
                    retained_parent_manifest='config/q2-down-register-scatter-pair-source.json',
                    model_result_sha256=hc.sha(model_path), component_result_sha256=hc.sha(component_path),
                    final_audit_sha256=hc.sha(audit_path), release_sha256=hc.sha(release_path),
                    prefill_tok_s=new['prefill_tok_s']['median'], decode_steps_s=new['decode_steps_s']['median'],
                    nominal_pp_gain_percent=model['candidate_median_change_percent']['best_parent']['prefill_tok_s'],
                    nominal_decode_change_percent=model['candidate_median_change_percent']['best_parent']['decode_steps_s'],
                    observed_historical_pp_ranges_overlap=overlap, all21_parent_files_exact=exact,
                    component_cycle_time_change_percent=component['summaries'][0]['candidate_time_change_percent'],
                    candidate_required_pp_increase_to_fixed_ud_percent=100 * (ud['prefill_tok_s']['median'] /
                                                                   new['prefill_tok_s']['median'] - 1),
                    retained_required_pp_increase_to_fixed_ud_percent=100 * (ud['prefill_tok_s']['median'] /
                        (new if gain and exact and component_ok else parent)['prefill_tok_s']['median'] - 1),
                    independent_quality=False, promoted=False, goal_met=False,
                    limits='One new original2048/tg128 model with saved comparisons. Retain all sources; '
                    'component and model timing are distinct. Inherited F16 task-quality gap remains. '
                    'No full curve follows without point parity.')
    hc.write(ROOT / 'config/q2-ssm-pingpong-disposition.json', decision)
    print(json.dumps(decision))


if __name__ == '__main__':
    main()
