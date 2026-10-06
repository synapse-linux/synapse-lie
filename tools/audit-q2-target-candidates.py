#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind new HC preparation to fixed references without projecting performance."""
import ast
import datetime
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    paths = {key: ROOT / name for key, name in (
        ('fixed_reference', 'config/q2-fixed-prefill-reference.json'),
        ('retained_model', 'config/q2-ssm-fixed-bounds-model-results.json'),
        ('previous_queue', 'config/q2-target-priorities-hc-lds-update.json'),
        ('injection_component_source', 'config/q2-hc-inject-reuse-component-source-v2.json'),
        ('injection_component_preparation', 'config/q2-hc-inject-reuse-component-preparation-v2.json'),
        ('norm_owner_source', 'config/q2-hc-norm-owner-draft.json'),
        ('norm_owner_static', 'config/q2-hc-norm-owner-draft-static.json'),
        ('producer_boundary', 'config/q2-producer-fusion-boundary.json'),
        ('last_release', 'config/q2-down-register-palette-v2-window-release.json'))}
    data = {key: json.loads(path.read_text()) for key, path in paths.items()}
    refs, parent = data['fixed_reference'], data['retained_model']['model']
    pp = parent['measurements']['prefill_tok_s']['median']
    tg = parent['measurements']['decode_steps_s']['median']
    ud = refs['arms']['ud']['measurements']['prefill_tok_s']['median']
    assert (pp, tg, ud) == (1585.308983, 25.16079073, 1685.777092)
    assert parent['input_sha256'] == refs['input']['sha256']
    assert refs['protocol']['physical_prompt_tokens'] == 2048
    assert refs['protocol']['timed_decode_calls'] == 127
    prepared = data['injection_component_preparation']
    assert prepared['source_manifest_sha256'] == sha(paths['injection_component_source'])
    assert prepared['all_165_fixture_kernel_bodies_operands_resources_exact_to_draft']
    assert not prepared['host_checks_run'] and not prepared['GPU_run']
    assert prepared['commands']['core-handover']['actual_exit'] == 255
    for path, digest in prepared['fixtures'].items():
        assert sha(ROOT / path) == digest, path
    for item in prepared['commands'].values():
        assert sha(ROOT / item['path']) == item['sha256']
    previous = data['previous_queue']
    assert previous['retained_PP'] == pp and previous['fixed_UD_PP'] == ud
    norm = data['norm_owner_static']
    assert norm['manifest_sha256'] == sha(paths['norm_owner_source'])
    assert norm['original_kernel_bodies_operands_resources_exact'] == 162
    assert norm['extra_block_barriers'] == 1 and norm['extra_shared_source_bytes'] == 16
    assert all(v['draft']['resources']['next_free_vgpr'] == 65 and
               v['parent']['resources']['next_free_vgpr'] == 84 and
               v['draft_compiler']['Occupancy'] == v['parent_compiler']['Occupancy'] == 16
               for v in norm['comparisons'].values())
    combine_ms = sum(r['total_ns'] for r in norm['regions_from_saved1571_profile'].values()) / 1e6
    assert abs(combine_ms - 145.803160) < 1e-9
    assert sha(paths['last_release']) == prepared['last_verified_release_sha256']
    gap_ms = (parent['measurements']['prefill_s']['median'] -
              refs['arms']['ud']['measurements']['prefill_s']['median']) * 1000
    new_files = ('tools/audit-q2-target-candidates.py',
        'tools/prepare-q2-hc-norm-owner-draft.py', 'tools/analyze-q2-hc-norm-owner-draft.py',
        'experiments/q2-hc-norm-owner-draft.inc', 'docs/Q2-HC-TARGET-CANDIDATES.md',
        'third_party/gufo/LIE-Q2-HC-NORM-OWNER-DRAFT.md')
    for name in new_files:
        if name.endswith('.py'):
            ast.parse((ROOT / name).read_text(), filename=name)
    report = dict(schema='synapse-lie.q2-target-candidates-update.v1',
        at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        inputs={key: dict(path=str(path.relative_to(ROOT)), sha256=sha(path))
                for key, path in paths.items()},
        new_files={name: sha(ROOT / name) for name in new_files},
        retained_variant='ssm-fixed-bounds', retained_PP=pp, retained_TG=tg,
        fixed_UD_PP=ud, required_PP_increase_percent=(ud / pp - 1) * 100,
        required_prefill_saving_ms=gap_ms,
        ranking_is_engineering_judgment_not_numerical_probability=True,
        profile_is_fresh1585=False,
        priorities=[dict(order=1, mechanism='HC normalized input/injection coefficient reuse',
            separate_injection_ms=previous['current_regions_from_saved1571_profile']['injection_ms'],
            affected_mix_ms=previous['current_regions_from_saved1571_profile']['affected_mix_ms'],
            complete_fixture_prepared=True, runtime_qualification=False),
            dict(order=2, mechanism='Four-owner final RMS scale calculation',
                whole_combine_region_ms=combine_ms, kernel_probes_compiled=True,
                numerical_source_sequence_preserved=True, runtime_qualification=False,
                extra_barrier=1, extra_shared_bytes=16, parent_VGPR=84, draft_VGPR=65,
                compiler_occupancy_changed=False),
            dict(order=3, mechanism='Whole640 producer/packing ownership',
                implementation_prepared=False,
                whole_row_scale_and_producer_reuse_required=True)],
        injection_alone_cannot_close_gap=True,
        whole_region_is_not_a_removable_time_estimate=True,
        existing_negative_sources_and_evidence_preserved=True,
        saved_comparators_rebuilt_or_rerun=False, full_curve=False, Q4=False,
        independent_quality=False, GPU_run=False, GPU_reserved=False,
        remote_state='SSH255_NO_ROUTE_TO_HOST_BEFORE_CORE_CHECK_CONNECTION',
        host_checks_run=False, model_inference=False, production_provider_changed=False,
        borrowed_executor_scratch_qualified=False, performance_increment_found=False,
        projected_model_rate=None, waiter_or_retry_scheduled=False,
        remote_cleanup=False, goal_met=False)
    with (ROOT / 'config/q2-target-candidates-update.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(retained_PP=pp, fixed_UD_PP=ud,
        required_prefill_saving_ms=gap_ms, priorities=[r['mechanism'] for r in report['priorities']],
        GPU_run=False, goal_met=False)))


if __name__ == '__main__':
    main()
