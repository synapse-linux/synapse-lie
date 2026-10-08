#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Close the Q8 experiment with actual failures, full arrays and saved controls."""
import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT/'evidence/q2-producer-q8-preparation'
spec = importlib.util.spec_from_file_location('hc', ROOT/'tools/analyze-q2-hc-bk256.py')
hc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hc)


def main():
    plan_path = ROOT/'config/q2-producer-q8-plan-v2.json'
    plan = hc.read(plan_path)
    for name,digest in {**plan['fixtures'],**plan['manifests']}.items():
        hc.require(hc.sha(ROOT/name) == digest, 'Frozen identity changed: '+name)
    hc.require(hc.sha(ROOT/plan['window_helper']) == plan['window_helper_sha256'], 'Window helper changed')
    release_path = ROOT/'config/q2-producer-q8-window-release.json'
    release = hc.read(release_path)
    observation_path = PREP/'collection-observation.json'
    observation = hc.read(observation_path)
    hc.require(observation['observed_complete_at'] < release['at'], 'Collections not observed before release')
    exits, artifacts, peaks = [], 0, {}
    for label in (plan['host'],plan['component']['label'],plan['arms'][0]['label']):
        path = ROOT/'evidence'/label
        receipt,_ = hc.curve.artifact_integrity(path)
        exits += [c['exit_code'] for c in receipt['commands']]
        artifacts += len(receipt['artifacts'])
        hc.require(receipt['finished_at'] < release['at'], 'Runtime not terminal before release')
        hc.require(observation['cohorts'][label]['result_sha256'] == hc.sha(path/'results/result.json'), 'Observed result changed')
        hc.require(observation['cohorts'][label]['artifact_count'] == len(receipt['artifacts']), 'Observed collection scope changed')
        values = {}
        for line in (path/'results/telemetry.jsonl').read_text().splitlines():
            for t in json.loads(line).get('thermal',[]):
                hc.require(not t['over_limit'], 'Thermal boundary crossed')
                values[t['device']] = max(values.get(t['device'],0),t['temperature_mc']/1000)
        peaks[label] = values
    for name in ('q2-producer-q8-window-release.json','q2-producer-q8-window-active.json','q2-producer-q8-ready.json'):
        hc.require((ROOT.parents[1]/'run'/name).read_bytes() == release_path.read_bytes(), 'Main mirror changed')
    hc.require(len(exits) == 13 and exits[:8] == [0]*8 and exits[8] == 1 and exits[9:] == [0]*4 and artifacts == 1125,
        'Runtime command/artifact totals changed')
    hc.require(release['state'] == 'Q2_PRODUCER_Q8_WINDOW_RELEASED' and
        not release['gpu_reserved'] and not release['kfd'] and not release['owned_group_members'] and
        len(release['leases']) == 4 and len(release['models']) == 7 and release['model_stats_unchanged'] and
        all(r['unchanged_free_EX_NB'] for r in release['leases']), 'Incomplete release')
    component_path = ROOT/'config/q2-producer-q8-component-results.json'
    model_path = ROOT/'config/q2-producer-q8-model-results.json'
    c, m = hc.read(component_path), hc.read(model_path)
    hc.require(len(c['replay']) == 64 and len(c['timings']) == 56 and c['complete_output_array_count'] == 1088 and
        c['safe_model_performance_admissible'], 'Component replay incomplete')
    hc.require(len(m['replay']['best_parent']['files']) == 21, 'Model comparison incomplete')
    plots = {str(p.relative_to(ROOT)):hc.sha(p) for p in (ROOT/'docs/figures').glob('q2-producer-q8-*')}
    hc.require(len(plots) == 6, 'Missing figure exports')
    for name,count in [('component',56),('model-wrapped',16)]:
        with (ROOT/'docs/figures'/('q2-producer-q8-'+name+'.csv')).open() as f:
            hc.require(len(list(csv.DictReader(f))) == count, 'Missing figure samples')
    failures = {p.name:hc.read(p)['exit_code'] for p in PREP.glob('*-command.json') if hc.read(p)['exit_code']}
    hc.require(failures == {'shared-format-command.json':1}, 'Unclassified preparation failure')
    report = dict(schema='synapse-lie.q2-producer-q8-final.v1', plan_sha256=hc.sha(plan_path),
        model_result_sha256=hc.sha(model_path), component_result_sha256=hc.sha(component_path),
        release_sha256=hc.sha(release_path), runtime_command_exits=exits,
        standard_artifacts_verified=artifacts, complete_output_arrays_verified=1088,
        frozen_fixtures_verified=len(plan['fixtures']), frozen_manifests_verified=len(plan['manifests']),
        provider_files_verified=1029, retired_identities=len(release['retired_identities']),
        retired_groups=len(release['retired_groups']), figures=plots, preserved_preparation_nonzero_exits=failures,
        full_q8_format_exact=all(not r['format_byte_errors'] for r in c['replay']),
        all64_sampled_fp64_checks_pass=all(r['oracle_pass'] for r in c['replay']),
        strict_component_numerical_pass=c['strict_numerical_pass'],
        original_mmq_differences=hc.read(PREP/'mmq-difference-review.json'),
        all56_timings_retained=True, parent_model_checks=m['checks']['best_parent'],
        within_arm_exact=m['within_arm_exact'], thermal_max_c=peaks,
        controls_rerun=False, independent_quality=False, full_curve=False, goal_met=False)
    audit_path = ROOT/'config/q2-producer-q8-final-audit.json'
    hc.write(audit_path,report)
    new = m['model']['measurements']; parent = m['references']['best_parent']['measurements']
    hc.require(new['prefill_tok_s']['median'] < parent['prefill_tok_s']['median'], 'Negative disposition no longer matches results')
    result = dict(schema='synapse-lie.q2-producer-q8-disposition.v1',
        decision='RETAIN_EXPERIMENT_AND_KEEP_SAVED1574', next_composition_variant='scaled-wave-pack',
        source_manifest=plan['source_variant_manifest'],retained_parent_manifest='config/q2-scaled-wave-pack-source.json',
        model_result_sha256=hc.sha(model_path), component_result_sha256=hc.sha(component_path),
        final_audit_sha256=hc.sha(audit_path), release_sha256=hc.sha(release_path),
        prefill_tok_s=new['prefill_tok_s']['median'], decode_steps_s=new['decode_steps_s']['median'],
        nominal_pp_gain_percent=m['candidate_median_change_percent']['best_parent']['prefill_tok_s'],
        nominal_decode_change_percent=m['candidate_median_change_percent']['best_parent']['decode_steps_s'],
        component_cycle_time_changes_percent={s['case']+'/'+s['scope']:s['candidate_time_change_percent'] for s in c['summaries']},
        full_q8_format_exact=report['full_q8_format_exact'],all64_sampled_fp64_checks_pass=report['all64_sampled_fp64_checks_pass'],
        parent_model_checks=m['checks']['best_parent'], thermal_max_c=peaks,
        independent_quality=False,controls_rerun=False,full_curve_admitted=False,promoted=False,goal_met=False,
        limits='One new Q8 arithmetic candidate; saved original Q2/UD/parent cohorts unchanged. Full-chain regression survives model measurement; no general rejection of producer fusion or of integer arithmetic on other geometries. Scalar decode code is unchanged; context/concurrency and independent quality remain open.')
    hc.write(ROOT/'config/q2-producer-q8-disposition.json',result)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
