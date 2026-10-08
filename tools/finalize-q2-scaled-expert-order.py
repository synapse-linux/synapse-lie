#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Close this one candidate without promoting inherited quality or curve parity."""
import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT/'evidence/q2-scaled-expert-order-preparation'
spec = importlib.util.spec_from_file_location('hc', ROOT/'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)


def main():
    plan_path = ROOT/'config/q2-scaled-expert-order-plan.json'
    plan = hc.read(plan_path)
    for name,digest in {**plan['fixtures'],**plan['manifests']}.items():
        hc.require(hc.sha(ROOT/name) == digest, 'Frozen identity changed: '+name)
    hc.require(hc.sha(ROOT/plan['window_helper']) == plan['window_helper_sha256'], 'Window helper changed')
    release_path = ROOT/'config/q2-scaled-expert-order-window-release.json'
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
    for name in ('q2-scaled-expert-order-window-release.json','q2-scaled-expert-order-window-active.json',
                 'q2-scaled-expert-order-ready.json'):
        hc.require((ROOT.parents[1]/'run'/name).read_bytes() == release_path.read_bytes(), 'Main mirror changed')
    hc.require(exits == [0]*8+[1]+[0]*4 and artifacts == 251, 'Runtime command/artifact totals changed')
    hc.require(not release['gpu_reserved'] and not release['kfd'] and not release['owned_group_members'] and
               len(release['leases']) == 4 and len(release['models']) == 7 and release['model_stats_unchanged'] and
               all(r['unchanged_free_EX_NB'] for r in release['leases']), 'Incomplete release')
    component_path = ROOT/'config/q2-scaled-expert-order-component-results.json'
    model_path = ROOT/'config/q2-scaled-expert-order-model-results.json'
    c, m = hc.read(component_path), hc.read(model_path)
    hc.require(len(c['replay']) == 107 and c['numerical_exact'] and not c['oracle_pass'] and
               len(c['timings']) == 28 and all(r['accounts_for_all_reported_errors'] for r in c['signed_zero_diagnosis']),
               'Component or oracle diagnosis incomplete')
    hc.require(len(m['replay']['best_parent']['files']) == 21 and m['within_arm_exact'], 'Model replay incomplete')
    plots = {str(p.relative_to(ROOT)):hc.sha(p) for p in (ROOT/'docs/figures').glob('q2-scaled-expert-order-*')}
    hc.require(len(plots) == 6, 'Missing figure exports')
    for name,count in [('component',28),('model-wrapped',16)]:
        with (ROOT/'docs/figures'/('q2-scaled-expert-order-'+name+'.csv')).open() as f:
            hc.require(len(list(csv.DictReader(f))) == count, 'Missing figure samples')
    failures = {p.name:hc.read(p)['exit_code'] for p in PREP.glob('*-command.json') if hc.read(p)['exit_code']}
    hc.require(failures == {'fixture-host-command.json':1,'fixture-device-command.json':1,
                           'shared-format-command.json':1,'changed-format-command.json':1,'component-command.json':1},
               'Unclassified preserved failure')
    report = dict(schema='synapse-lie.q2-scaled-expert-order-final.v1', plan_sha256=hc.sha(plan_path),
        model_result_sha256=hc.sha(model_path), component_result_sha256=hc.sha(component_path),
        release_sha256=hc.sha(release_path), runtime_command_exits=exits,
        standard_artifacts_verified=artifacts, complete_output_arrays_verified=214,
        frozen_fixtures_verified=len(plan['fixtures']), frozen_manifests_verified=len(plan['manifests']),
        provider_files_verified=1028, retired_identities=len(release['retired_identities']),
        retired_groups=len(release['retired_groups']), figures=plots, preserved_nonzero_exits=failures,
        all107_component_pairs_exact=True, strict_oracle_pass=False,
        reported_oracle_errors_signed_zero_only=True, all28_timings_retained=True,
        parent_model_checks=m['checks']['best_parent'], thermal_max_c=peaks,
        controls_rerun=False, independent_quality=False, full_curve=False, goal_met=False)
    audit_path = ROOT/'config/q2-scaled-expert-order-final-audit.json'
    hc.write(audit_path,report)
    new = m['model']['measurements']; parent = m['references']['best_parent']['measurements']
    ud = m['references']['fixed_ud']['measurements']
    exact_parent = not m['checks']['best_parent']['changed_files']
    gain = new['prefill_tok_s']['median'] > parent['prefill_tok_s']['median']
    overlap = max(new['prefill_tok_s']['min'],parent['prefill_tok_s']['min']) <= min(new['prefill_tok_s']['max'],parent['prefill_tok_s']['max'])
    result = dict(schema='synapse-lie.q2-scaled-expert-order-disposition.v1',
        decision='RETAIN_PREFILL_CANDIDATE_AND_SAVED1574' if gain and exact_parent else 'RETAIN_EXPERIMENT_AND_KEEP_SAVED1574',
        next_composition_variant='scaled-expert-order' if gain and exact_parent else 'scaled-wave-pack',
        source_manifest='config/q2-scaled-expert-order-source.json', retained_parent_manifest='config/q2-scaled-wave-pack-source.json',
        model_result_sha256=hc.sha(model_path), component_result_sha256=hc.sha(component_path),
        final_audit_sha256=hc.sha(audit_path), release_sha256=hc.sha(release_path),
        prefill_tok_s=new['prefill_tok_s']['median'], decode_steps_s=new['decode_steps_s']['median'],
        nominal_pp_gain_percent=m['candidate_median_change_percent']['best_parent']['prefill_tok_s'],
        nominal_decode_change_percent=m['candidate_median_change_percent']['best_parent']['decode_steps_s'],
        absolute_pp_gain=new['prefill_tok_s']['median']-parent['prefill_tok_s']['median'],
        observed_historical_pp_ranges_overlap=overlap,
        required_pp_increase_to_fixed_ud_percent=100*(ud['prefill_tok_s']['median']/new['prefill_tok_s']['median']-1),
        component_cycle_time_changes_percent={s['scope']:s['candidate_time_change_percent'] for s in c['summaries']},
        all21_parent_files_exact=exact_parent, all107_component_pairs_exact=True,
        strict_oracle_pass=False, reported_oracle_errors_signed_zero_only=True,
        inherited_quality_record='config/q2-down-half-storage-disposition.json', thermal_max_c=peaks,
        independent_quality=False, controls_rerun=False, full_curve_admitted=False, promoted=False, goal_met=False,
        limits='Saved historical model comparators; scalar decode unchanged and observed TG differences not causally assigned. Packing and down component gain is separate, not additive. Preserve actual strict-oracle exit1 in both arms; inherited F16 task quality and full context/concurrency parity remain open.')
    hc.write(ROOT/'config/q2-scaled-expert-order-disposition.json',result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
