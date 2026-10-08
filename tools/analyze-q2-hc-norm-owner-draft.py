#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit private HC norm ownership against saved parent ISA; no GPU claim."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location('static',
        ROOT / 'tools/analyze-q2-ssm-row-group-compose-static.py')
    static = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(static)
    manifest_path = ROOT / 'config/q2-hc-norm-owner-draft.json'
    draft = json.loads(manifest_path.read_text())
    for key in ('parent_manifest', 'measured_parent', 'include', 'compiler_probe', 'generator'):
        assert sha(ROOT / draft[key]) == draft[key + '_sha256'], key
    parent = json.loads((ROOT / draft['parent_manifest']).read_text())['variants']['ssm-fixed-bounds']
    base = ROOT / parent['source']
    assert {str(p.relative_to(base)): sha(p) for p in base.rglob('*')
            if p.is_file()} == parent['files']
    old_static = json.loads((ROOT / 'config/q2-ssm-fixed-bounds-static.json').read_text())
    before_path = ROOT / old_static['candidate_assembly_path']
    assert sha(before_path) == old_static['candidate_assembly_sha256']
    prep = ROOT / 'evidence/q2-hc-norm-owner-draft-preparation'
    after_path = prep / 'candidate.s'
    before, after = static.old.isa.parse(before_path), static.old.isa.parse(after_path)
    assert len(before) == 162 and len(after) == 164 and set(before) < set(after)
    before_text, after_text = before_path.read_text(), after_path.read_text()
    for name in before:
        assert before[name]['resources'] == after[name]['resources'], name
        assert static.old.instructions(before_text, name) == static.old.instructions(after_text, name), name
    comparisons = {}
    for kind, name in (('ordinary', 'HcCombineF32HalfKernel'),
                       ('moe', 'HcCombineMoeHalfDeferredNormKernel')):
        old = next(s for s in before if name in s)
        new = next(s for s in after if 'HcNormOwnerDraft' + kind.title() + 'Kernel' in s)
        a, b = before[old], after[new]
        assert b['resources']['private_segment_fixed_size'] == 0
        assert b['mnemonics']['s_barrier'] == a['mnemonics']['s_barrier'] + 1
        assert a['mnemonics']['v_rsq_f32_e32'] == 4
        assert b['mnemonics']['v_rsq_f32_e32'] == 1
        comparisons[kind] = dict(parent_symbol=old, draft_symbol=new, parent=a, draft=b,
            parent_compiler=static.static.compiler_comments(before_text, old),
            draft_compiler=static.static.compiler_comments(after_text, new))
    profile_path = ROOT / 'config/q2-current-best-profile-results.json'
    profile = json.loads(profile_path.read_text())
    regions = {}
    for kind, name in (('ordinary', 'HcCombineF32HalfKernel'),
                       ('moe', 'HcCombineMoeHalfDeferredNormKernel')):
        rows = [r for r in profile['phases']['prefill']['kernels'] if name in r['kernel']]
        assert len(rows) == 1
        regions[kind] = rows[0]
    command = json.loads((prep / 'assembly-command.json').read_text())
    assert command['exit_code'] == 0
    generation = ROOT / 'evidence/q2-hc-inject-reuse-component-preparation/norm-owner-generation-command.json'
    assert json.loads(generation.read_text())['exit_code'] == 0
    report = dict(schema='synapse-lie.q2-hc-norm-owner-draft-static.v1',
        manifest_sha256=sha(manifest_path), parent_source_files_exact=1027,
        parent_assembly_sha256=sha(before_path), draft_assembly=str(after_path.relative_to(ROOT)),
        draft_assembly_sha256=sha(after_path),
        original_kernel_bodies_operands_resources_exact=162,
        comparisons=comparisons, historical_profile_sha256=sha(profile_path),
        regions_from_saved1571_profile=regions, fresh1585_profile=False,
        dynamic_wave_count_unchanged=8, scale_owners_per_CTA=4,
        extra_block_barriers=1, extra_shared_source_bytes=16,
        scope='Only the ordered final wave-partial totals and scale calculation move to four owner threads. Whole combine costs are historical bounds, not all removable work.',
        occupancy_is_static_metadata=True, behavior_and_contraction_tested=False,
        command=dict(path=str((prep / 'assembly-command.json').relative_to(ROOT)),
                     sha256=sha(prep / 'assembly-command.json'), actual_exit=0),
        generation_command_sha256=sha(generation),
        parent_source_unchanged=True, qualified_parent_recompiled=False,
        GPU_run=False, GPU_reserved=False, production_provider=False,
        numerical_acceptance=False, performance_measured=False,
        full_curve=False, Q4=False, projected_model_rate=None, goal_met=False)
    with (ROOT / 'config/q2-hc-norm-owner-draft-static.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(original_bodies_exact=162,
        kernels={k: dict(parent_instructions=v['parent']['instructions'],
            draft_instructions=v['draft']['instructions'],
            resources=v['draft']['resources']) for k, v in comparisons.items()},
        GPU_run=False, performance_measured=False)))


if __name__ == '__main__':
    main()
