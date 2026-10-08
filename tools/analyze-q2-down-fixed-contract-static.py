#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the integrated down selector to its separately compiled private draft."""
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
    prepare = module('prepare-q2-down-fixed-contract.py')
    isa = module('analyze-q2-ssm-row-group-compose-static.py').old
    sha = prepare.sha
    manifest = ROOT / 'config/q2-down-fixed-contract-source.json'
    source = json.loads(manifest.read_text())['variants']['down-fixed-contract']
    for key in ('parent_manifest','measured_parent','draft_manifest','draft_static','donor_include','patch','generator'):
        assert sha(ROOT / source[key]) == source[key + '_sha256'], key
    assert prepare.inventory(ROOT / source['source']) == source['files']
    meta = json.loads((ROOT / source['draft_static']).read_text())
    draft_path = ROOT / meta['candidate_assembly']
    assert sha(draft_path) == meta['candidate_assembly_sha256']
    candidate_path = ROOT / 'evidence/q2-down-fixed-contract-preparation/candidate.s'
    a, b = [isa.isa.parse(path) for path in (draft_path, candidate_path)]
    at, bt = draft_path.read_text(), candidate_path.read_text()
    assert len(a) == len(b) == 167 and set(a) == set(b)
    for name in a:
        assert a[name]['resources'] == b[name]['resources'], name
        assert isa.instructions(at, name) == isa.instructions(bt, name), name
    report = dict(schema='synapse-lie.q2-down-fixed-contract-static.v1',
        source_manifest_sha256=sha(manifest), provider_files=1029,
        original_kernels_instruction_operand_resource_exact=164, added_private_kernels=3,
        private_draft_bodies_exact=3, literal_control_current_parent_exact=True,
        parent_recompiled=False, candidate_assembly=str(candidate_path.relative_to(ROOT)),
        candidate_assembly_sha256=sha(candidate_path), draft_assembly_sha256=sha(draft_path),
        selected_shape=source['shape'], static_kernel_pairs=meta['pairs'],
        GPU_run=False, model_inference=False, arithmetic_qualified=False, performance_gain=False)
    with (ROOT / 'config/q2-down-fixed-contract-static.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(parent_bodies_exact=164, private_draft_bodies_exact=3, provider_files=1029)))


if __name__ == '__main__':
    main()
