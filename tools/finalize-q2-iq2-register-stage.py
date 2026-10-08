#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify collected IQ2 evidence and choose the next composition source."""
import csv
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREP = ROOT/'evidence/q2-iq2-register-stage-preparation'
spec = importlib.util.spec_from_file_location('component', ROOT/'tools/analyze-q2-iq2-register-stage-component.py')
component_analysis = importlib.util.module_from_spec(spec)
spec.loader.exec_module(component_analysis)
hc = component_analysis.hc
read, require, sha = hc.read, hc.require, hc.sha


def main():
    plan_path = ROOT/'config/q2-iq2-register-stage-plan.json'
    plan = read(plan_path)
    for name,digest in {**plan['fixtures'],**plan['manifests'],
                        plan['window_helper']:plan['window_helper_sha256']}.items():
        require(sha(ROOT/name)==digest,'Frozen identity changed: '+name)
    source = read(ROOT/plan['source_variant_manifest'])['variants']['iq2-register-stage']
    require({str(p.relative_to(ROOT/source['source'])):sha(p)
             for p in (ROOT/source['source']).rglob('*') if p.is_file()} == source['files'],
            'Provider inventory changed')
    release_path = ROOT/'config/q2-iq2-register-stage-window-release.json'
    release = read(release_path)
    labels = [plan['host'],plan['components'][0]['label'],plan['arms'][0]['label']]
    exits, artifacts, thermal = [],0,{}
    for label in labels:
        path = ROOT/'evidence'/label
        result,_ = hc.curve.artifact_integrity(path)
        require(result['finished_at'] < release['at'],'Unfinished cohort at release')
        binding = hc.capsule(path,plan['fixtures'], None if label==plan['host'] else source['files'])
        require(binding['fixture_files_verified']==118,'Incomplete fixture binding')
        exits += [c['exit_code'] for c in result['commands']]
        artifacts += len(result['artifacts'])
        peaks = {}
        for line in (path/'results/telemetry.jsonl').read_text().splitlines():
            for row in json.loads(line).get('thermal',[]):
                require(not row['over_limit'],'Thermal stop')
                peaks[row['device']] = max(peaks.get(row['device'],0),row['temperature_mc']/1000)
        thermal[label] = peaks
    require(sha(ROOT/'evidence'/plan['host']/'results/result.json') == plan['host_result_sha256'],
            'Fresh host receipt changed')
    # The host collection is already bound by the frozen pre-admission plan.
    for name in ('component-collect','model-collect'):
        receipt=read(PREP/(name+'-command.json'))
        require(receipt['exit_code']==0 and receipt['finished_at'] < release['at'],
                'Collection did not precede release')
    require(exits[:8]==[0]*8 and exits[8] in (0,1) and exits[9:]==[0]*4,'Unexpected runtime exits')
    require(release['state']=='Q2_IQ2_REGISTER_STAGE_WINDOW_RELEASED' and not release['gpu_reserved'] and
            not release['kfd'] and not release['owned_group_members'] and len(release['leases'])==4 and
            len(release['models'])==7 and release['model_stats_unchanged'] and
            all(r['unchanged_free_EX_NB'] for r in release['leases']) and
            {r['label'] for r in release['cohorts']}==set(labels),'Incomplete window release')
    for name in ('q2-iq2-register-stage-window-release.json','q2-iq2-register-stage-window-active.json',
                 'q2-iq2-register-stage-ready.json'):
        require((ROOT.parents[1]/'run'/name).read_bytes()==release_path.read_bytes(),'Main mirror differs')
    require(read(PREP/'publish-release-command.json')['exit_code']==0,'Remote mirrors not published')
    component_path=ROOT/'config/q2-iq2-register-stage-component-results.json'
    model_path=ROOT/'config/q2-iq2-register-stage-model-results.json'
    component,model=read(component_path),read(model_path)
    require(component==component_analysis.analyze(),'Component raw evidence differs')
    require(component['plan_sha256']==model['plan_sha256']==sha(plan_path) and
            model['component_result_sha256']==sha(component_path) and
            model['release_sha256']==sha(release_path),'Reports bound to different campaign')
    root, raw = hc.prior.shared.arm(ROOT/'evidence'/labels[-1],'iq2-register-stage')
    require(all(model['model'][k]==v for k,v in raw.items()),'Raw model timing/replay differs')
    for key,label,variant in (
        ('fixed_q2','q2-counting-regression-mixed-r1','curve-iq2-mixed-q2'),
        ('fixed_ud','q2-counting-regression-ud-r1','qualified'),
        ('best_parent','q2-ssm-fixed-bounds-model-r1','ssm-fixed-bounds')):
        ref_root,ref=hc.prior.shared.arm(ROOT/'evidence'/label,variant)
        require(ref==model['references'][key],'Historical comparison changed')
        require(hc.prior.comparison(ref_root,root)==model['replay'][key],'Raw full-logit comparison changed')
    require(len(model['replay']['best_parent']['files'])==21,'Incomplete parent outputs')
    figures={str(p.relative_to(ROOT)):sha(p) for p in (ROOT/'docs/figures').glob('q2-iq2-register-stage-*')}
    require(len(figures)==6,'Missing sample exports')
    for name,count in (('component',70),('model',16)):
        with (ROOT/f'docs/figures/q2-iq2-register-stage-{name}.csv').open() as f:
            require(len(list(csv.DictReader(f)))==count,'Missing exported samples')
    failures={p.name:read(p)['exit_code'] for p in PREP.glob('*-command.json') if read(p)['exit_code']}
    require(failures == {'static-audit-command.json':1, 'checkpoint-whitespace-command.json':2},
            'Unclassified preparation/analysis failure')
    audit_path=ROOT/'config/q2-iq2-register-stage-final-audit.json'
    audit=dict(schema='synapse-lie.q2-iq2-register-stage-final.v1',plan_sha256=sha(plan_path),
        model_result_sha256=sha(model_path),component_result_sha256=sha(component_path),
        release_sha256=sha(release_path),runtime_command_exits=exits,artifacts_verified=artifacts,
        host_reused=False,frozen_fixtures_verified=118,frozen_manifests_verified=12,
        provider_files_verified=1028,retired_identities=len(release['retired_identities']),
        retired_groups=len(release['retired_groups']),thermal_max_c=thermal,classified_preparation_failures=failures,
        component_parent_exact=component['numerical_exact'],parent_model_checks=model['checks']['best_parent'],
        within_arm_exact=model['within_arm_exact'],figures=figures,raw_model_reanalysis=True,
        controls_rerun=False,full_curve=False,independent_quality=False,goal_met=False)
    hc.write(audit_path,audit)
    new,parent=model['model']['measurements'],model['references']['best_parent']['measurements']
    ud=model['references']['fixed_ud']['measurements']
    exact=not model['checks']['best_parent']['changed_files'] and model['within_arm_exact'] and component['numerical_exact']
    gain=new['prefill_tok_s']['median']>parent['prefill_tok_s']['median']
    retain=exact and gain
    decision=dict(schema='synapse-lie.q2-iq2-register-stage-disposition.v1',
        decision='RETAIN_PREFILL_CANDIDATE_AND_SAVED1585' if retain else 'RETAIN_EXPERIMENT_AND_KEEP_SAVED1585',
        next_composition_variant='iq2-register-stage' if retain else 'ssm-fixed-bounds',
        source_manifest=plan['source_variant_manifest'],retained_parent_manifest=source['parent_manifest'],
        model_result_sha256=sha(model_path),component_result_sha256=sha(component_path),
        final_audit_sha256=sha(audit_path),release_sha256=sha(release_path),
        prefill_tok_s=new['prefill_tok_s']['median'],decode_steps_s=new['decode_steps_s']['median'],
        nominal_pp_gain_percent=model['candidate_median_change_percent']['best_parent']['prefill_tok_s'],
        nominal_decode_change_percent=model['candidate_median_change_percent']['best_parent']['decode_steps_s'],
        observed_historical_pp_ranges_overlap=max(new['prefill_tok_s']['min'],parent['prefill_tok_s']['min']) <=
            min(new['prefill_tok_s']['max'],parent['prefill_tok_s']['max']),
        all21_parent_files_exact=not model['checks']['best_parent']['changed_files'],
        within_arm_exact=model['within_arm_exact'],component_parent_exact=component['numerical_exact'],
        retained_required_pp_increase_to_fixed_ud_percent=100*(ud['prefill_tok_s']['median']/
            (new if retain else parent)['prefill_tok_s']['median']-1),
        independent_quality=False,promoted=False,goal_met=False,
        limits='One new original2048/tg128 model with saved comparisons. Retention is a composition decision, '
            'not a claim of contemporaneous causal repeatability or full-curve/independent-quality acceptance.')
    hc.write(ROOT/'config/q2-iq2-register-stage-disposition.json',decision)
    print(json.dumps(decision))


if __name__ == '__main__':
    main()
