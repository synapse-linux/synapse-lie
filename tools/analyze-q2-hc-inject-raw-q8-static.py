#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the model integration to saved parent and component device instructions."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    prepare = module('prepare-q2-hc-inject-raw-q8.py')
    isa = module('analyze-q2-ssm-row-group-compose-static.py').old
    sha = prepare.sha
    manifest = ROOT / 'config/q2-hc-inject-raw-q8-source.json'
    source = json.loads(manifest.read_text())['variants']['hc-inject-raw-q8']
    for key in ('parent_manifest', 'measured_parent', 'component_qualification',
                'qualified_include', 'policy', 'patch', 'generator'):
        assert sha(ROOT / source[key]) == source[key + '_sha256'], key
    assert prepare.inventory(ROOT / source['source']) == source['files']
    parent = json.loads((ROOT / 'config/q2-iq2-fixed-bounds-static.json').read_text())
    component = json.loads((ROOT / 'config/q2-hc-inject-reuse-draft-static-v3.json').read_text())
    parent_path = ROOT / parent['candidate_assembly_path']
    qualified_path = ROOT / component['candidate_assembly']
    assert sha(parent_path) == parent['candidate_assembly_sha256']
    assert sha(qualified_path) == component['candidate_assembly_sha256']
    candidate_path = ROOT / 'evidence/q2-hc-inject-raw-q8-preparation/candidate.s'
    a, q, b = [isa.isa.parse(path) for path in (parent_path, qualified_path, candidate_path)]
    at, qt, bt = [path.read_text() for path in (parent_path, qualified_path, candidate_path)]
    assert len(a) == 164 and len(b) == 166 and set(a) <= set(b)
    for name in a:
        assert a[name]['resources'] == b[name]['resources'], name
        assert isa.instructions(at, name) == isa.instructions(bt, name), name
    extra = set(b) - set(a)
    assert len(extra) == 2 and all('HcInjectReuseLdsDraft' in name for name in extra)
    for name in extra:
        assert name in q and q[name]['resources'] == b[name]['resources'], name
        assert isa.instructions(qt, name) == isa.instructions(bt, name), name
    report = dict(schema='synapse-lie.q2-hc-inject-raw-q8-static.v1',
        source_manifest_sha256=sha(manifest), provider_file_count=1030,
        parent_assembly=str(parent_path.relative_to(ROOT)), parent_assembly_sha256=sha(parent_path),
        qualified_assembly=str(qualified_path.relative_to(ROOT)), qualified_assembly_sha256=sha(qualified_path),
        candidate_assembly=str(candidate_path.relative_to(ROOT)), candidate_assembly_sha256=sha(candidate_path),
        retained_parent_bodies_exact=164, qualified_component_bodies_exact=2,
        resources={name: b[name] for name in sorted(extra)},
        parent_recompiled=False, component_rerun=False, new_device_bytes=0,
        scratch_identity_and_capacity_host_gate_required=True,
        borrowed_scratch='Original down_e allocation, no offset view, no pending MoE reads. Combine/producer/reducer/next MoE use the same stream. No borrow identity survives HcMix.',
        failed_launch_policy='Return terminal failure before publishing half/Q8 cache identities; never retry fallback after writes.',
        finite_component_arithmetic_difference_preserved=True,
        model_inference=False, numerical_acceptance=False, model_gain=False, goal_met=False)
    path = ROOT / 'config/q2-hc-inject-raw-q8-static.json'
    with path.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(parent_bodies_exact=164, qualified_component_bodies_exact=2,
        provider_files=1030, component_rerun=False, new_device_bytes=0)))


if __name__ == '__main__':
    main()
