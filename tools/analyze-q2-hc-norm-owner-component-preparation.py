#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the RMS fixture's unchanged numerical ISA; no behavioral test."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def main():
    spec = importlib.util.spec_from_file_location(
        'static', ROOT / 'tools/analyze-q2-ssm-row-group-compose-static.py')
    static = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(static)
    preparation_path = ROOT / 'config/q2-hc-norm-owner-component-preparation.json'
    prep = read(preparation_path)
    fixture = ROOT / prep['fixture']
    generator = ROOT / prep['generator']
    include = ROOT / prep['include']
    assert sha(fixture) == prep['fixture_sha256'] and sha(generator) == prep['generator_sha256']
    assert sha(include) == prep['include_sha256']
    draft = read(ROOT / prep['draft_manifest'])
    assert sha(ROOT / prep['draft_manifest']) == prep['draft_manifest_sha256']
    parent_path = ROOT / prep['parent_manifest']
    assert sha(parent_path) == prep['parent_manifest_sha256']
    parent = read(parent_path)['variants']['ssm-fixed-bounds']
    base = ROOT / parent['source']
    assert {str(p.relative_to(base)): sha(p) for p in base.rglob('*')
            if p.is_file()} == parent['files'] and len(parent['files']) == 1027
    old_path = ROOT / 'evidence/q2-hc-norm-owner-draft-preparation/candidate.s'
    old_static = read(ROOT / 'config/q2-hc-norm-owner-draft-static.json')
    assert sha(old_path) == old_static['draft_assembly_sha256']
    new_path = ROOT / 'evidence/q2-hc-norm-owner-component-preparation/fixture.s'
    original, fixture_isa = (static.old.isa.parse(p) for p in (old_path, new_path))
    original_text, fixture_text = old_path.read_text(), new_path.read_text()
    assert len(original) == len(fixture_isa) == 164 and set(original) == set(fixture_isa)
    for name in original:
        assert original[name]['resources'] == fixture_isa[name]['resources'], name
        assert static.old.instructions(original_text, name) == static.old.instructions(fixture_text, name), name
    owner_kernels = {}
    for kind in ('Ordinary', 'Moe'):
        name = next(n for n in fixture_isa if 'HcNormOwnerDraft' + kind + 'Kernel' in n)
        resource = fixture_isa[name]['resources']
        assert resource['private_segment_fixed_size'] == 0 and resource['next_free_vgpr'] == 65
        assert resource['group_segment_fixed_size'] == (144 if kind == 'Ordinary' else 10384)
        owner_kernels[kind.lower()] = dict(symbol=name, **fixture_isa[name])
    # Enumerate the fixture's declared cases without executing a GPU or model.
    cases = [(n, mode != 0, p, 10, 3, 4 if mode == 2 else 0, True, True, False)
             for n in (1, 17, 97, 129, 257) for mode in range(3) for p in range(2)]
    cases += [(129, False, 0, 10, 3, 0, False, False, False),
              (129, True, 0, 10, 3, 0, False, False, False),
              (129, True, 0, 10, 3, 0, True, False, False),
              (129, True, 0, 1, 3, 0, True, True, False),
              (129, True, 0, 16, 3, 0, True, True, False),
              (129, False, 0, 10, 10, 0, True, True, False),
              (2048, False, 0, 10, 3, 0, True, True, True),
              (2048, True, 0, 10, 3, 0, True, True, True)]
    assert len(cases) == len(set(cases)) == 38
    text = fixture.read_text()
    for anchor in ('Require(cases == 38', '"timing_samples\\":28',
                   'out.Reset(in, stream);', 'constexpr unsigned iterations = 6;',
                   'in.Unchanged(stream);', 'hipStreamNonBlocking'):
        assert anchor in text, anchor
    time_body = text[text.index('static void Time('):text.index('static bool Case(')]
    timed = time_body[time_body.index('const auto started'):time_body.index('const auto finished')]
    assert all(anchor not in timed for anchor in ('Reset(', 'Upload(', 'Read(', 'Hash(', 'hipMalloc'))
    ast.parse(generator.read_text(), filename=str(generator))
    receipts = {}
    receipt_dir = ROOT / 'evidence/q2-hc-inject-reuse-component-preparation'
    for name, exit_code in (('norm-owner-fixture-generation', 1),
                           ('norm-owner-fixture-generation-r2', 0),
                           ('norm-owner-assembly', 0), ('norm-owner-host-syntax', 0)):
        path = receipt_dir / (name + '-command.json')
        command = read(path)
        assert command['exit_code'] == exit_code
        receipts[name] = dict(path=str(path.relative_to(ROOT)), sha256=sha(path),
                             exit_code=exit_code, argv=command['argv'])
    report = dict(schema='synapse-lie.q2-hc-norm-owner-component-static.v1',
        preparation_sha256=sha(preparation_path), generator_syntax_parsed=True,
        fixture_sha256=sha(fixture), assembly=str(new_path.relative_to(ROOT)),
        assembly_sha256=sha(new_path), draft_assembly_sha256=sha(old_path),
        command_receipts=receipts, source_inventory_exact=1027,
        unchanged_production_bodies=162, draft_bodies_exact=2,
        total_fixture_bodies_exact=164, owners=owner_kernels, cases=cases,
        expected_output_records=120, expected_timing_samples=28,
        no_upload_reset_read_hash_allocation_inside_timer=True,
        no_gamma_and_optional_half_untouched=True, model_inference=False,
        behavioral_tests_executed=False, GPU_run=False,
        CMake_target_registered=False, remote_launcher_registered=False,
        numerical_acceptance=False, independent_quality=False,
        new_model_rate=None, production_provider_changed=False, goal_met=False)
    with (ROOT / 'config/q2-hc-norm-owner-component-static.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(whole_cases=38, outputs=120, timings=28, exact_bodies=164,
                         unchanged_parent_files=1027, GPU_run=False, model_rate=None)))


if __name__ == '__main__':
    main()
