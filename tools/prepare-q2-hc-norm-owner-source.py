#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind a component-only RMS owner provider to the unchanged measured parent."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    refs = dict(parent_manifest='config/q2-ssm-fixed-bounds-source.json',
        measured_parent='config/q2-ssm-fixed-bounds-model-results.json',
        draft_manifest='config/q2-hc-norm-owner-draft.json',
        draft_static='config/q2-hc-norm-owner-draft-static.json',
        numerical_include='experiments/q2-hc-norm-owner-draft.inc',
        fixture='tests/q2_hc_norm_owner.hip', generator='tools/prepare-q2-hc-norm-owner-source.py',
        fixture_preparation='config/q2-hc-norm-owner-component-preparation.json',
        fixture_static='config/q2-hc-norm-owner-component-static.json')
    parent = json.loads((ROOT / refs['parent_manifest']).read_text())['variants']['ssm-fixed-bounds']
    source = ROOT / parent['source']
    assert {str(p.relative_to(source)): sha(p) for p in source.rglob('*')
            if p.is_file()} == parent['files'] and len(parent['files']) == 1027
    prep = json.loads((ROOT / refs['fixture_preparation']).read_text())
    assert sha(ROOT / refs['fixture']) == prep['fixture_sha256']
    assert sha(ROOT / refs['numerical_include']) == prep['include_sha256']
    static = json.loads((ROOT / refs['fixture_static']).read_text())
    assert static['preparation_sha256'] == sha(ROOT / refs['fixture_preparation'])
    assert static['total_fixture_bodies_exact'] == 164
    variant = dict(source=parent['source'], files=parent['files'], **refs,
        **{k + '_sha256': sha(ROOT / v) for k, v in refs.items()},
        mode='hc-norm-owner-check', production_provider=False, model_mode=False,
        parent_source_changed=False, cases=38, full_output_records=120, timings=28,
        contract='Complete ordinary/MoE10 combines, four-owner final RMS scales; preserve safe differing arrays and timings',
        timer_scope='Six complete combines; reset/read/hash/allocation outside, event submission/terminal sync inside',
        no_executor_lifetime_change=True, GPU_run=False,
        numerical_acceptance=False, independent_quality=False, performance_measured=False,
        controls_rerun=False, goal_met=False)
    output = ROOT / 'config/q2-hc-norm-owner-component-source.json'
    with output.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-hc-norm-owner-component-source.v1',
            official_gufo_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
            variants={'hc-norm-owner-draft': variant}), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(provider_files=1027, cases=38, component_only=True, GPU_run=False)))


if __name__ == '__main__':
    main()
