#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the private model kernels to the already measured HC-up component."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('prior', ROOT / 'tools/analyze-q2-ssm-row-group-compose-static.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sha = prior.ssm.sha


def main():
    manifest = ROOT / 'config/q2-hc-up-short-chain-model-source.json'
    variant = json.loads(manifest.read_text())['variants']['hc-up-short-chain']
    base = ROOT / variant['source']
    assert prior.ssm.inventory(base) == variant['files'] and len(variant['files']) == 1029
    for key in ('parent_manifest', 'measured_parent', 'component_qualification',
                'qualified_include', 'patch', 'generator'):
        assert sha(ROOT / variant[key]) == variant[key + '_sha256']
    static = json.loads((ROOT / 'config/q2-hc-up-short-chain-static.json').read_text())
    selected = static['variants']['hc-up-short-chain-phased']
    measured = ROOT / selected['assembly_path']
    candidate = ROOT / 'evidence/q2-hc-up-short-chain-model-preparation/candidate.s'
    assert sha(measured) == selected['assembly_sha256']
    a, b = (prior.old.isa.parse(p) for p in (measured, candidate))
    assert set(a) == set(b) and len(a) == 166
    at, bt = measured.read_text(), candidate.read_text()
    for name in a:
        assert a[name]['resources'] == b[name]['resources'], name
        assert prior.old.instructions(at, name) == prior.old.instructions(bt, name), name
    command = ROOT / 'evidence/q2-hc-up-short-chain-model-preparation/assembly-command.json'
    assert json.loads(command.read_text())['exit_code'] == 0
    report = dict(schema='synapse-lie.q2-hc-up-short-chain-model-static.v1',
        source_manifest_sha256=sha(manifest), provider_files=1029,
        original_device_bodies_exact=164, measured_candidate_device_bodies_exact=2,
        all_device_bodies_exact=166, candidate_assembly=str(candidate.relative_to(ROOT)),
        candidate_assembly_sha256=sha(candidate), measured_assembly_sha256=sha(measured),
        compile_receipt_sha256=sha(command), original_model_run=False,
        scalar_dispatch_unchanged=True, raw_Q8_dispatch_unchanged=True,
        original_weight_bits_unchanged=True, deliberately_changed_FP32_reduction=True,
        extra_device_or_persistent_bytes=0, model_performance_unmeasured=True, goal_met=False)
    with (ROOT / 'config/q2-hc-up-short-chain-model-static.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
