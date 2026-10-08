#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Record the last selective family's model test without rewriting failures."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT/name).read_text())


def sha(name):
    return hashlib.sha256((ROOT/name).read_bytes()).hexdigest()


def main():
    output = ROOT/'config/q2-rejected-recovery-scaled-update.json'
    if output.exists():
        raise ValueError('Refusing to overwrite recovery evidence')
    inventory = read('config/q2-rejected-test-reaudit.json')
    for candidate in inventory['candidates']:
        if sha(candidate['result']) != candidate['source_sha256']:
            raise ValueError('Original report changed: '+candidate['result'])
    previous = read('config/q2-rejected-recovery-moe-update.json')
    result = read('config/q2-scaled-selective-model-results.json')
    if (previous['remaining_selective_integration_families'] != ['scaled-tiles'] or
        result['controls_rerun'] or result['component_rerun'] or
        result['model']['command_exits'] != [0,0,0,0] or
        result['checks']['best_parent']['changed_files'] or
        result['routing_summary']['calls'] != 192):
        raise ValueError('Recovery scope, actual model execution or replay differs')
    counts = previous['disposition_family_counts'].copy()
    counts['new_composition_measured'] += 1
    counts['new_selective_integration_pending'] -= 1
    model = result['model']['measurements']
    pp = model['prefill_tok_s']['median']
    ud = result['references']['fixed_ud']['measurements']['prefill_tok_s']['median']
    report = dict(schema='synapse-lie.q2-rejected-recovery-scaled-update.v1',
        previous_recovery_status_sha256=sha('config/q2-rejected-recovery-moe-update.json'),
        original_inventory_sha256=sha('config/q2-rejected-test-reaudit.json'),
        original_reports_verified=len(inventory['candidates']),
        new_family='scaled-tiles', new_disposition='new_composition_measured',
        previous_disposition='new_selective_integration_pending',
        remaining_selective_integration_families=[], disposition_family_counts=counts,
        new_model_result_sha256=sha('config/q2-scaled-selective-model-results.json'),
        source_manifest_sha256=sha('config/q2-scaled-selective-source.json'),
        original_component_result_sha256=sha('config/q2-scaled-tiles-results.json'),
        candidate_prefill_tok_s=pp, candidate_decode_steps_s=model['decode_steps_s']['median'],
        new_prefill_change_percent=result['candidate_median_change_percent']['best_parent']['prefill_tok_s'],
        combined_prefill_change_percent=result['candidate_median_change_percent']['fixed_q2']['prefill_tok_s'],
        candidate_prefill_gap_to_ud_percent=result['candidate_median_change_percent']['fixed_ud']['prefill_tok_s'],
        candidate_prefill_increase_needed_for_ud_percent=100*(ud/pp-1),
        confirmed_false_format_rejection_families=previous['confirmed_false_format_rejection_families'],
        all_nineteen_false_confirmed=False, qualified_controls_rerun=False, component_rerun=False,
        original_failures_preserved=True, original_tester_unchanged=True,
        independent_additive_gains_established=False, historical_pp_ranges_overlap=True,
        stable_increment_over_parent_established=False, exact_parent_model_files=21,
        numerical_acceptance=False, independent_model_quality_complete=False,
        entire_reaudit_complete=False, goal_met=False, full_curve_admitted=False,
        limits='All eleven families have a measured/model-composed disposition or already belong to '
        'fixed Q2. This closes the pending selective model integration, not original numerical '
        'acceptance, independent quality or parity. New median differs marginally within historical variation.')
    with output.open('x') as stream:
        json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps(dict(original_reports_verified=report['original_reports_verified'],
                         family_counts=counts, pp=pp, needed_for_ud_percent=report['candidate_prefill_increase_needed_for_ud_percent'])))


if __name__ == '__main__':
    main()
