#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind local SSM preparation and confirm the existing GPU campaign is unchanged."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-ssm-row-group-preparation'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    fixture_path = ROOT/'config/q2-ssm-row-group-fixture.json'
    fixture = json.loads(fixture_path.read_text())
    for name in ('fixture', 'control_include', 'oracle', 'derived_from', 'source_manifest'):
        assert sha(ROOT/fixture[name]) == fixture[name+'_sha256'], name
    source = json.loads((ROOT/fixture['source_manifest']).read_text())['variants']['ssm-row-group']
    static_path = ROOT/'config/q2-ssm-row-group-static.json'
    static = json.loads(static_path.read_text())
    assert static['source_manifest_sha256'] == fixture['source_manifest_sha256']
    assert static['other_kernels_instruction_operand_resource_exact'] == 161
    for arm in ('parent', 'candidate'):
        assert sha(ROOT/static[arm+'_assembly_path']) == static[arm+'_assembly_sha256']
        assert static[arm+'_kernel']['compiler_comments']['NumVgprs'] == 222
        assert static[arm+'_kernel']['compiler_comments']['NumVGPRsForWavesPerEU'] == 241
    spec = importlib.util.spec_from_file_location('literal', ROOT/'tools/prepare-q2-ssm-row-group.py')
    literal = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(literal)
    assert literal.inventory(ROOT/source['source']) == source['files']
    parent = json.loads((ROOT/source['parent_manifest']).read_text())['variants']['scaled-wave-pack']
    assert literal.inventory(ROOT/parent['source']) == parent['files']
    original = (ROOT/parent['source']/literal.REL).read_text()
    kernel = literal.function(original, 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    wrapper = literal.function(original, 'bool DenseF16SsmGemm(')
    restored = (ROOT/fixture['control_include']).read_text().split('\n',2)[2].replace(
        'DenseSsmRowGroupControlKernel','DenseF16GEMMKernel').replace('DenseSsmRowGroupControl','DenseF16SsmGemm')
    assert restored == kernel+wrapper
    commands = {p.name:json.loads(p.read_text()) for p in sorted(OUT.glob('*-command.json'))}
    expected = {'generation':0, 'assembly':0, 'static':1, 'static-r2':0,
                'static-r3':0, 'fixture-generation':0, 'fixture-host':0, 'fixture-device':0}
    for label, code in expected.items():
        assert commands[label+'-command.json']['exit_code'] == code
    frozen_path = ROOT/'config/q2-down-register-scatter-plan.json'
    frozen = json.loads(frozen_path.read_text())
    for kind in ('fixtures', 'manifests'):
        for name, expected_sha in frozen[kind].items():
            assert sha(ROOT/name) == expected_sha, name
    assert len(frozen['fixtures']) == 85 and len(frozen['manifests']) == 4
    assert sha(ROOT/frozen['window_helper']) == frozen['window_helper_sha256']
    tools = ['tools/prepare-q2-ssm-row-group.py',
             'tools/prepare-q2-ssm-row-group-fixture.py',
             'tools/analyze-q2-ssm-row-group-static.py',
             'tools/verify-q2-ssm-row-group-preparation.py']
    for name in tools:
        ast.parse((ROOT/name).read_text(), filename=name)
    report = dict(schema='synapse-lie.q2-ssm-row-group-preparation.v1',
        fixture_manifest_sha256=sha(fixture_path), static_report_sha256=sha(static_path),
        scripts={name:sha(ROOT/name) for name in tools}, commands=commands,
        provider_files_verified=1027, literal_parent_control_verified=True,
        frozen_register_scatter_plan_sha256=sha(frozen_path),
        frozen_register_scatter_fixture_hashes_unchanged=85,
        frozen_register_scatter_manifest_hashes_unchanged=4,
        compiler_actual_vgprs=222, compiler_descriptor_next_free_vgpr=241,
        compiler_static_occupancy=4, measured_hardware_occupancy=False,
        numerical_gpu_checks_executed=False, gpu_run=False, model_inference=False,
        remote_staging=False, launcher_wiring=False, goal_met=False,
        remaining='New isolated fixture requires launcher/plan/host qualification and fresh coordinated .157 admission before GPU/model. Existing register-scatter campaign remains first and unchanged.')
    with (ROOT/'config/q2-ssm-row-group-preparation.json').open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(provider_files=1027, literal_control_exact=True,
        frozen_existing_fixtures_exact=85, frozen_existing_manifests_exact=4,
        host_device_syntax_pass=True, gpu_run=False, launcher_wiring=False)))


if __name__ == '__main__':
    main()
