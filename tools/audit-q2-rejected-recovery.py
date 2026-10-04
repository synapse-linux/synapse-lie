#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the current recovery status without rewriting the nineteen old reports."""
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = 'config/q2-rejected-test-reaudit.json'
INVENTORY_SHA = '3a76a5bdef0bd3c26a8328fe0cfd04aed1f43a998447b4167ecc2a5d3083b9c0'

# Disposition describes recovery of performance mechanisms, not acceptance
# of their numerical output or proof that every historical rejection was false.
FAMILIES = {
    'hc-library-ragged': ('already_in_fixed_reference', 'Entire library dispatch file matches fixed Q2.'),
    'library-norm': ('already_in_fixed_reference', 'Paired norm bodies and fixed2048 dispatch match fixed Q2.'),
    'norm-ragged': ('already_in_fixed_reference', 'Fixed2048 pairing is already present; ragged extension adds nothing here.'),
    'scaled-input': ('already_in_fixed_reference', 'The same packing include is already in fixed Q2.'),
    'scaled-library': ('already_in_fixed_reference', 'Packing and original-F16 HC library route are already in fixed Q2.'),
    'shared-q8': ('new_composition_measured', 'Fixture race confirmed; production replay is exact and its gain is already composed.'),
    'scaled-row': ('new_composition_measured', 'Q8 plus row reuse fixed model measured with all21 replay files exact.'),
    'norm-fixed': ('new_composition_measured', 'Q8 plus row plus norm measured; prior norm logits reproduced, Q2 logits differ.'),
    'hc-sequence': ('performance_measured_regression', 'Ordinary/MoE complete cycles were timed despite numeric rejection and both slowed.'),
    'hc-deferred-norm': ('new_selective_integration_pending', 'MoE-only cycle advantage is marginal; feedback bytes differ and current consumers need integration.'),
    'scaled-tiles': ('new_selective_integration_pending', 'Tile64 helps only the64-active synthetic routing; no equivalent adaptive model selector is measured.'),
}


def sha(path):
    return hashlib.sha256((ROOT / path).read_bytes()).hexdigest()


def read(path):
    return json.loads((ROOT / path).read_text())


def require(value, message):
    if not value:
        raise ValueError(message)


def main():
    output = ROOT / 'config/q2-rejected-recovery-status.json'
    table = ROOT / 'docs/figures/q2-rejected-recovery-status.csv'
    require(not output.exists() and not table.exists(), 'Refusing to overwrite recovery evidence')
    require(sha(INVENTORY) == INVENTORY_SHA, 'Original inventory changed')
    inventory = read(INVENTORY)
    records = inventory['candidates']
    require(len(records) == 19, 'Expected nineteen original reports')
    verified = []
    for record in records:
        actual = sha(record['result'])
        require(actual == record['source_sha256'], 'Original report changed: ' + record['result'])
        verified.append(dict(path=record['result'], sha256=actual, family=record['family'], kind=record['kind']))
    candidates = [r for r in verified if r['kind'] == 'candidate']
    require(set(r['family'] for r in candidates) == set(FAMILIES), 'Candidate family inventory changed')
    require(len(candidates) == 15, 'Expected fifteen candidate records, four host/status records')
    oracle = read('config/q2-rejected-test-reaudit-oracle-update.json')
    require(oracle['confirmed_false_gpu_format_rejection_families'] == ['shared-q8'], 'Oracle classification changed')
    family_rows = [dict(family=key, disposition=status, original_report_count=sum(r['family'] == key for r in candidates),
                        confirmed_false_format_rejection=key in oracle['confirmed_false_gpu_format_rejection_families'],
                        observation=observation) for key, (status, observation) in FAMILIES.items()]
    model = read('config/q2-hc-bk256-fixed-model-results.json')
    require(model['original_tester_unchanged'] and not model['controls_rerun'], 'Fixed comparison changed')
    require(model['model']['input_sha256'] == '75343e606f5b815fe01f69ddc6ce50a997e2de96d8a20304a82a7f24f1180b35', 'Fixed input changed')
    require(not model['goal_met'] and not model['full_curve_admitted'], 'Unexpected goal verdict')
    measured = dict(best_q2=model['model']['measurements'],
                    fixed_q2=model['references']['fixed_q2']['measurements'],
                    fixed_ud=model['references']['fixed_ud']['measurements'])
    q2 = measured['best_q2']['prefill_tok_s']['median']
    ud = measured['fixed_ud']['prefill_tok_s']['median']
    for name in ('bk128', 'bn64'):
        selection = read('config/q2-hc-' + name + '-selection.json')
        require(not selection['model_selected'] and not selection['qualified_model_controls_rerun'], 'Geometry selection changed')
        component = read('config/q2-hc-' + name + '-component-results.json')
        require(not component['controls_rerun'] and not component['model_forward'], 'Unexpected model run')
        for arm in component['arms'].values():
            require(arm['parent_saved_tensors_exact'] == 40 and arm['parent_full_replay_hashes_exact'] == 22,
                    'Changed parent output: ' + name)
    paths = [INVENTORY, 'config/q2-rejected-test-reaudit-progress.json',
             'config/q2-rejected-test-reaudit-oracle-update.json', 'config/q2-rejected-test-reaudit-hc-update.json',
             'config/q2-reaudit-composition-results.json', 'config/q2-hc-bk256-fixed-model-results.json',
             'config/q2-hc-deferred-norm-results.json', 'config/q2-scaled-tiles-results.json',
             'config/q2-hc-bk128-component-results.json', 'config/q2-hc-bk128-selection.json',
             'config/q2-hc-bn64-component-results.json', 'config/q2-hc-bn64-selection.json',
             'config/q2-hc-bn64-run-window-release.json']
    report = dict(schema='synapse-lie.q2-rejected-recovery-status.v1',
                  original_inventory_sha256=INVENTORY_SHA, original_reports_verified=verified,
                  original_report_count=19, candidate_record_count=15, candidate_family_count=11,
                  non_candidate_record_count=4, families=family_rows,
                  disposition_family_counts=dict(Counter(r['disposition'] for r in family_rows)),
                  confirmed_false_format_rejection_families=['shared-q8'],
                  all_nineteen_false_confirmed=False, independent_additive_gains_established=False,
                  fixed_measurements=measured,
                  best_pp_gap_to_ud_percent=100 * (q2 / ud - 1),
                  best_pp_increase_needed_for_ud_percent=100 * (ud / q2 - 1),
                  bindings={path: sha(path) for path in paths},
                  gpu_run=False, model_run=False, qualified_controls_rerun=False,
                  original_failures_preserved=True, entire_reaudit_complete=False,
                  independent_model_quality_complete=False, goal_met=False,
                  limits='Recovery status is not numerical acceptance. Synthetic cycle gains are not additive model throughput. No exhaustive compilation-error audit or full context parity is claimed.')
    table.parent.mkdir(parents=True, exist_ok=True)
    with table.open('x') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(family_rows[0]), lineterminator='\n')
        writer.writeheader()
        writer.writerows(family_rows)
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(original_reports_verified=len(verified), family_counts=report['disposition_family_counts'],
                          confirmed_false_families=['shared-q8'], best_prefill=q2, fixed_ud_prefill=ud,
                          remaining_pp_increase_percent=report['best_pp_increase_needed_for_ud_percent'],
                          output=str(output))))


if __name__ == '__main__':
    main()
