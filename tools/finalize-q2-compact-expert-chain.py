#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Close this one candidate without promoting inherited quality or curve parity."""
import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT/'evidence/q2-compact-expert-chain-preparation'
spec = importlib.util.spec_from_file_location('hc', ROOT/'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)


def main():
    plan_path = ROOT/'config/q2-compact-expert-chain-plan.json'
    plan = hc.read(plan_path)
    for name,digest in {**plan['fixtures'],**plan['manifests']}.items():
        hc.require(hc.sha(ROOT/name) == digest, 'Frozen identity changed: '+name)
    hc.require(hc.sha(ROOT/plan['window_helper']) == plan['window_helper_sha256'], 'Window helper changed')
    release_path = ROOT/'config/q2-compact-expert-chain-window-release.json'
    release = hc.read(release_path)
    exits, artifacts, peaks = [], 0, {}
    for label,key in [(plan['host'],'host-collect'),(plan['component']['label'],'component-collection'),
                      (plan['arms'][0]['label'],'model-collection')]:
        path = ROOT/'evidence'/label
        receipt,_ = hc.curve.artifact_integrity(path)
        exits += [c['exit_code'] for c in receipt['commands']]
        artifacts += len(receipt['artifacts'])
        hc.require(receipt['finished_at'] < release['at'], 'Runtime not terminal before release')
        collection = hc.read(PREP/(key+'-command.json'))
        hc.require(collection['exit_code'] == 0 and collection['finished_at'] < release['at'],
                   'Collection not complete before release')
        values = {}
        for line in (path/'results/telemetry.jsonl').read_text().splitlines():
            for t in json.loads(line).get('thermal',[]):
                hc.require(not t['over_limit'], 'Thermal boundary crossed')
                values[t['device']] = max(values.get(t['device'],0),t['temperature_mc']/1000)
        peaks[label] = values
    for name in ('q2-compact-expert-chain-window-release.json','q2-compact-expert-chain-window-active.json',
                 'q2-compact-expert-chain-ready.json'):
        hc.require((ROOT.parents[1]/'run'/name).read_bytes() == release_path.read_bytes(), 'Main mirror changed')
    hc.require(len(exits) == 13 and exits[:8] == [0]*8 and exits[8] in (0,1) and exits[9:] == [0]*4 and artifacts == 469, 'Runtime command/artifact totals changed')
    hc.require(not release['gpu_reserved'] and not release['kfd'] and not release['owned_group_members'] and
               len(release['leases']) == 4 and len(release['models']) == 7 and release['model_stats_unchanged'] and
               all(r['unchanged_free_EX_NB'] for r in release['leases']), 'Incomplete release')
    component_path = ROOT/'config/q2-compact-expert-chain-component-results.json'
    model_path = ROOT/'config/q2-compact-expert-chain-model-results.json'
    c, m = hc.read(component_path), hc.read(model_path)
    hc.require(len(c['replay']) == 96 and len(c['timings']) == 56 and len(c['routing']) == 48 and
               len(c['independent_packing']) == 48 and c['complete_output_array_count'] == 432,
               'Component replay incomplete')
    hc.require(len(m['replay']['best_parent']['files']) == 21 and m['within_arm_exact'], 'Model replay incomplete')
    plots = {str(p.relative_to(ROOT)):hc.sha(p) for p in (ROOT/'docs/figures').glob('q2-compact-expert-chain-*')}
    hc.require(len(plots) == 6, 'Missing figure exports')
    for name,count in [('component',56),('model-wrapped',16)]:
        with (ROOT/'docs/figures'/('q2-compact-expert-chain-'+name+'.csv')).open() as f:
            hc.require(len(list(csv.DictReader(f))) == count, 'Missing figure samples')
    failures = {p.name:hc.read(p)['exit_code'] for p in PREP.glob('*-command.json') if hc.read(p)['exit_code']}
    expected_failures = {'prepare-command.json':1,'shared-format-command.json':1}
    if exits[8]: expected_failures['component-command.json'] = exits[8]
    hc.require(failures == expected_failures, 'Unclassified preserved failure')
    report = dict(schema='synapse-lie.q2-compact-expert-chain-final.v1', plan_sha256=hc.sha(plan_path),
        model_result_sha256=hc.sha(model_path), component_result_sha256=hc.sha(component_path),
        release_sha256=hc.sha(release_path), runtime_command_exits=exits,
        standard_artifacts_verified=artifacts, complete_output_arrays_verified=432,
        frozen_fixtures_verified=len(plan['fixtures']), frozen_manifests_verified=len(plan['manifests']),
        provider_files_verified=1028, retired_identities=len(release['retired_identities']),
        retired_groups=len(release['retired_groups']), figures=plots, preserved_nonzero_exits=failures,
        non_runtime_preview_failure=hc.read(PREP/'preview-log-failure.json'),
        all96_component_pairs_exact=c['numerical_exact'], strict_oracle_pass=c['oracle_pass'],
        reported_oracle_errors_signed_zero_only=all(o['half_errors']==o['negative_zero_to_positive_zero'] and not o['scale_errors'] for o in c['independent_packing']), all56_timings_retained=True,
        parent_model_checks=m['checks']['best_parent'], thermal_max_c=peaks,
        controls_rerun=False, independent_quality=False, full_curve=False, goal_met=False)
    audit_path = ROOT/'config/q2-compact-expert-chain-final-audit.json'
    hc.write(audit_path,report)
    new = m['model']['measurements']; parent = m['references']['best_parent']['measurements']
    ud = m['references']['fixed_ud']['measurements']
    exact_parent = not m['checks']['best_parent']['changed_files']
    gain = new['prefill_tok_s']['median'] > parent['prefill_tok_s']['median']
    overlap = max(new['prefill_tok_s']['min'],parent['prefill_tok_s']['min']) <= min(new['prefill_tok_s']['max'],parent['prefill_tok_s']['max'])
    result = dict(schema='synapse-lie.q2-compact-expert-chain-disposition.v1',
        decision='RETAIN_PREFILL_CANDIDATE_AND_SAVED1574' if gain and exact_parent else 'RETAIN_EXPERIMENT_AND_KEEP_SAVED1574',
        next_composition_variant='compact-expert-chain' if gain and exact_parent else 'scaled-wave-pack',
        source_manifest='config/q2-compact-expert-chain-source.json', retained_parent_manifest='config/q2-scaled-wave-pack-source.json',
        model_result_sha256=hc.sha(model_path), component_result_sha256=hc.sha(component_path),
        final_audit_sha256=hc.sha(audit_path), release_sha256=hc.sha(release_path),
        prefill_tok_s=new['prefill_tok_s']['median'], decode_steps_s=new['decode_steps_s']['median'],
        nominal_pp_gain_percent=m['candidate_median_change_percent']['best_parent']['prefill_tok_s'],
        nominal_decode_change_percent=m['candidate_median_change_percent']['best_parent']['decode_steps_s'],
        absolute_pp_gain=new['prefill_tok_s']['median']-parent['prefill_tok_s']['median'],
        observed_historical_pp_ranges_overlap=overlap,
        required_pp_increase_to_fixed_ud_percent=100*(ud['prefill_tok_s']['median']/new['prefill_tok_s']['median']-1),
        component_cycle_time_changes_percent={s['case']+'/'+s['scope']:s['candidate_time_change_percent'] for s in c['summaries']},
        all21_parent_files_exact=exact_parent, all96_component_pairs_exact=c['numerical_exact'],
        strict_oracle_pass=c['oracle_pass'], reported_oracle_errors_signed_zero_only=all(o['half_errors']==o['negative_zero_to_positive_zero'] and not o['scale_errors'] for o in c['independent_packing']),
        inherited_quality_record='config/q2-down-half-storage-disposition.json', thermal_max_c=peaks,
        independent_quality=False, controls_rerun=False, full_curve_admitted=False, promoted=False, goal_met=False,
        limits='Saved historical model comparators; scalar decode unchanged and observed TG differences not causally assigned. Component cycle gains are separate, not additive. Preserve actual numerical exits and complete-array diagnoses; inherited F16 task quality and full context/concurrency parity remain open.')
    hc.write(ROOT/'config/q2-compact-expert-chain-disposition.json',result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
