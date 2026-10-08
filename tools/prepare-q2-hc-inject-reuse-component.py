#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Freeze a component-only HC draft against the retained original provider."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parent_path = ROOT / 'config/q2-ssm-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    draft_path = ROOT / 'config/q2-hc-inject-reuse-draft-v3.json'
    draft = json.loads(draft_path.read_text())
    static_path = ROOT / 'config/q2-hc-inject-reuse-draft-static-v3.json'
    static = json.loads(static_path.read_text())
    assert static['draft_manifest_sha256'] == sha(draft_path)
    assert draft['parent_manifest_sha256'] == sha(parent_path)
    assert sha(ROOT / draft['include']) == draft['include_sha256']
    base = ROOT / parent['source']
    assert {str(p.relative_to(base)): sha(p) for p in base.rglob('*') if p.is_file()} == parent['files']
    variant = dict(source=parent['source'], files=parent['files'],
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-ssm-fixed-bounds-model-results.json',
        measured_parent_sha256=sha(ROOT / 'config/q2-ssm-fixed-bounds-model-results.json'),
        draft_manifest=str(draft_path.relative_to(ROOT)), draft_manifest_sha256=sha(draft_path),
        draft_static=str(static_path.relative_to(ROOT)), draft_static_sha256=sha(static_path),
        numerical_include=draft['include'], numerical_include_sha256=draft['include_sha256'],
        fixture='tests/q2_hc_inject_reuse.hip', fixture_sha256=sha(ROOT / 'tests/q2_hc_inject_reuse.hip'),
        generator='tools/prepare-q2-hc-inject-reuse-component.py', generator_sha256=sha(Path(__file__)),
        mode='hc-inject-reuse-check', production_provider=False, model_mode=False,
        parent_source_changed=False, parent_recompiled=False,
        contract='Complete original raw/raw-Q8/deferred mix/injection vs private LDS-coefficient draft; preserve safe numerical failures and full cycle timings',
        rotations=6, rotating_up_weight_bytes=6 * 4 * 2560 * 320 * 2,
        cases=42, replay_sets=57, full_output_records=200, timings=42,
        timers='Monotonic complete-cycle wall time plus raw HIP elapsed validity; allocation/uploads/hash/output outside',
        borrowed_executor_scratch_qualified=False, independent_quality=False,
        GPU_run=False, performance_measured=False, goal_met=False)
    report = dict(schema='synapse-lie.q2-hc-inject-reuse-component-source.v1',
        official_gufo_pin='f783fedb9bea2ec7de941f6da4e02f4a4596b29e',
        variants={'hc-inject-reuse-draft': variant})
    with (ROOT / 'config/q2-hc-inject-reuse-component-source.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(variant='hc-inject-reuse-draft', source_files=len(parent['files']),
                         parent_unchanged=True, component_only=True, GPU_run=False)))


if __name__ == '__main__':
    main()
