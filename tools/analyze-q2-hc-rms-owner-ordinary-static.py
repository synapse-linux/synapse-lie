#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Match the model candidate's ordinary kernel to the GPU-qualified fixture."""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location(
        'static', ROOT / 'tools/analyze-q2-ssm-row-group-compose-static.py')
    static = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(static)
    manifest = ROOT / 'config/q2-hc-rms-owner-ordinary-source.json'
    variant = json.loads(manifest.read_text())['variants']['hc-rms-owner-ordinary']
    base = ROOT / variant['source']
    assert {str(p.relative_to(base)): sha(p) for p in base.rglob('*')
            if p.is_file()} == variant['files'] and len(variant['files']) == 1028
    for key in ('parent_manifest', 'measured_parent', 'component_qualification',
                'qualified_include', 'patch', 'generator'):
        assert sha(ROOT / variant[key]) == variant[key + '_sha256']
    qualification_static = json.loads((ROOT / 'config/q2-hc-norm-owner-component-static.json').read_text())
    qualified_path = ROOT / qualification_static['assembly']
    assert sha(qualified_path) == qualification_static['assembly_sha256']
    candidate_path = ROOT / 'evidence/q2-hc-rms-owner-ordinary-preparation/candidate.s'
    qualified, candidate = (static.old.isa.parse(p) for p in (qualified_path, candidate_path))
    qualified_text, candidate_text = qualified_path.read_text(), candidate_path.read_text()
    removed = {n for n in qualified if 'HcNormOwnerDraftMoeKernel' in n}
    assert len(qualified) == 164 and len(candidate) == 163 and len(removed) == 1
    assert set(candidate) == set(qualified) - removed
    for name in candidate:
        assert qualified[name]['resources'] == candidate[name]['resources'], name
        assert static.old.instructions(qualified_text, name) == static.old.instructions(candidate_text, name), name
    kernel = (base / 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp').read_text()
    start = kernel.index('bool HcCombineF32Half(')
    body = kernel[start:kernel.index('\nbool HcCombineMoeF32(', start)]
    assert 'if (n_tokens >= 96)' in body
    assert body.count('hipLaunchKernelGGL(HcNormOwnerDraftOrdinaryKernel') == 1
    assert body.count('hipLaunchKernelGGL(HcCombineF32HalfKernel') == 1
    commands = {}
    prep = ROOT / 'evidence/q2-hc-norm-owner-runtime-preparation'
    for label in ('ordinary-provider-generation', 'ordinary-provider-assembly'):
        path = prep / (label + '-command.json')
        command = json.loads(path.read_text())
        assert command['exit_code'] == 0
        commands[label] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path),
                               exit_code=0, argv=command['argv'])
    report = dict(schema='synapse-lie.q2-hc-rms-owner-ordinary-static.v1',
        source_manifest_sha256=sha(manifest), commands=commands,
        candidate_assembly=str(candidate_path.relative_to(ROOT)),
        candidate_assembly_sha256=sha(candidate_path),
        GPU_qualified_assembly_sha256=sha(qualified_path),
        original_production_bodies_exact=162, qualified_ordinary_body_exact=True,
        candidate_bodies_exact=163, provider_file_inventory_exact=1028,
        new_MoE_owner_body_omitted=True, MoE_dispatch_unchanged=True,
        n_below_96_dispatch_unchanged=True, new_persistent_bytes=0,
        executor_lifetimes_changed=False, callbacks_or_streams_changed=False,
        original_model_run=False, remote_model_variant_registered=False,
        model_plan_frozen=False, independent_quality=False, production_adopted=False,
        new_model_rate=None, goal_met=False)
    with (ROOT / 'config/q2-hc-rms-owner-ordinary-static.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(original_bodies_exact=162, qualified_ordinary_body_exact=True,
        provider_files=1028, original_model_run=False, new_model_rate=None)))


if __name__ == '__main__':
    main()
