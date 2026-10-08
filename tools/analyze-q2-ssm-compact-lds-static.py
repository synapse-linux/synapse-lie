#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the SSM compact transpose and retain resource/synchronization tradeoffs."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/q2-ssm-compact-lds-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


group = module('analyze-q2-ssm-row-group-compose-static.py')
prepare = module('prepare-q2-ssm-compact-lds.py')
ssm, old = group.ssm, group.old


def main():
    manifest = ROOT / 'config/q2-ssm-compact-lds-source.json'
    source = json.loads(manifest.read_text())['variants']['ssm-compact-lds']
    for key in ('parent_manifest', 'measured_parent', 'patch'):
        assert ssm.sha(ROOT / source[key]) == source[key + '_sha256'], key
    parent = json.loads((ROOT / source['parent_manifest']).read_text())['variants']['down-register-scatter']
    for provider in (source, parent):
        assert ssm.inventory(ROOT / provider['source']) == provider['files']
    assert prepare.layout_checks() == source['source_layout_proof']
    before_source = (ROOT / parent['source'] / ssm.REL).read_text()
    after_source = (ROOT / source['source'] / ssm.REL).read_text()
    literal = (ssm.function(before_source, 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,') +
               ssm.function(before_source, 'bool DenseF16SsmGemm('))
    control_path = ROOT / 'experiments/q2-ssm-row-group-control.inc'
    control = control_path.read_text().split('\n', 2)[2].replace('DenseSsmRowGroupControlKernel', 'DenseF16GEMMKernel').replace(
        'DenseSsmRowGroupControl', 'DenseF16SsmGemm')
    assert literal == control
    before_wrapper = ssm.function(before_source, 'bool DenseF16SsmGemm(')
    after_wrapper = ssm.function(after_source, 'bool DenseF16SsmGemm(')
    assert before_wrapper.replace('DenseF16GEMMKernel<256, 128, 2, 8, 1, 1, false, true>',
        'DenseF16GEMMKernel<256, 128, 1, 8, 1, 1, false, true>') == after_wrapper
    for fragment in ('float SsmConv4Value(', '__global__ void SsmConvBoundaryKernel('):
        assert ssm.function(before_source, fragment) == ssm.function(after_source, fragment)
    oracle_path = ROOT / 'experiments/q2-ssm-compact-lds-oracle.inc'
    assert oracle_path.read_text().replace('ssm_compact_lds_oracle', 'ssm_row_group_oracle') == (
        ROOT / 'experiments/q2-ssm-row-group-oracle.inc').read_text()
    # Numerical fixture logic remains literal apart from event/file names,
    # formatting and the new resource query before any fixture operations.
    fixture_path = ROOT / 'tests/q2_ssm_compact_lds.hip'
    fixture = fixture_path.read_text().replace('ssm_compact_lds_', 'ssm_row_group_').replace(
        'ssm-compact-lds-', 'ssm-row-group-')
    previous_fixture = (ROOT / 'tests/q2_ssm_row_group.hip').read_text()
    normalize = lambda value: re.sub(r'\s+', '', value)
    for prefix in ('static void Launch(', 'static bool Pair(', 'static bool Case('):
        assert normalize(ssm.function(fixture, prefix)) == normalize(ssm.function(previous_fixture, prefix))
    previous_main = ssm.function(previous_fixture, 'int main() {')
    assert normalize(ssm.function(fixture, 'int main() {').replace('    Resources();\n', '')) == normalize(previous_main)
    saved = json.loads((ROOT / 'config/q2-down-register-scatter-static.json').read_text())
    parent_asm = ROOT / saved['candidate_assembly_path']
    assert ssm.sha(parent_asm) == saved['candidate_assembly_sha256']
    candidate_asm = OUT / 'candidate.s'
    a, b = old.isa.parse(parent_asm), old.isa.parse(candidate_asm)
    removed, added = a.keys() - b.keys(), b.keys() - a.keys()
    assert len(a) == len(b) == 162 and len(removed) == len(added) == 1
    control_symbol, candidate_symbol = next(iter(removed)), next(iter(added))
    assert control_symbol.replace('ILi256ELi128ELi2ELi8', 'ILi256ELi128ELi1ELi8') == candidate_symbol
    before, after = parent_asm.read_text(), candidate_asm.read_text()
    for symbol in a.keys() & b.keys():
        assert old.instructions(before, symbol) == old.instructions(after, symbol), symbol
        assert a[symbol]['resources'] == b[symbol]['resources'], symbol
    assert [a[control_symbol]['resources']['group_segment_fixed_size'],
            b[candidate_symbol]['resources']['group_segment_fixed_size']] == [49152, 32768]
    assert a[control_symbol]['resources']['private_segment_fixed_size'] == 0
    assert b[candidate_symbol]['resources']['private_segment_fixed_size'] == 0
    with TemporaryDirectory(dir=OUT, prefix='reconstruct-') as tmp:
        target = Path(tmp) / ssm.REL
        target.parent.mkdir(parents=True)
        target.write_text(before_source)
        result = subprocess.run(['patch', '--batch', '-p1', '-i', str(ROOT / source['patch'])],
                                cwd=tmp, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert ssm.sha(target) == source['files'][ssm.REL]
    commands = {name: json.loads((OUT / (name + '-command.json')).read_text())
                for name in ('generation', 'assembly', 'fixture-host', 'fixture-device')}
    assert all(row['exit_code'] == 0 for row in commands.values())
    frozen_path = ROOT / 'config/q2-ssm-row-group-plan.json'
    frozen = json.loads(frozen_path.read_text())
    for p, digest in {**frozen['fixtures'], **frozen['manifests'],
                      frozen['window_helper']: frozen['window_helper_sha256']}.items():
        assert ssm.sha(ROOT / p) == digest, p
    report = dict(schema='synapse-lie.q2-ssm-compact-lds-static.v1',
        source_manifest_sha256=ssm.sha(manifest), source_files=1027,
        parent_assembly_path=str(parent_asm.relative_to(ROOT)), parent_assembly_sha256=ssm.sha(parent_asm),
        candidate_assembly_path=str(candidate_asm.relative_to(ROOT)), candidate_assembly_sha256=ssm.sha(candidate_asm),
        parent_recompiled=False, source_reconstruction_exact=True,
        other_kernels_instruction_operand_resource_exact=161,
        control_literal_parent_exact=True, grid_and_boundary_kernel_unchanged=True,
        parent_kernel=dict(symbol=control_symbol, **a[control_symbol], compiler_comments=group.static.compiler_comments(before, control_symbol)),
        candidate_kernel=dict(symbol=candidate_symbol, **b[candidate_symbol], compiler_comments=group.static.compiler_comments(after, candidate_symbol)),
        source_layout_proof=source['source_layout_proof'],
        fixture_contract=dict(fixture=str(fixture_path.relative_to(ROOT)), fixture_sha256=ssm.sha(fixture_path),
            control_include=str(control_path.relative_to(ROOT)), control_include_sha256=ssm.sha(control_path),
            oracle=str(oracle_path.relative_to(ROOT)), oracle_sha256=ssm.sha(oracle_path),
            oracle_arithmetic_unchanged=True, numerical_shapes=[1024, 1025, 1057, 2048, 2049],
            full_output_pairs=30, sampled_fp64_checks=60, samples_per_fp64_check=24,
            relative_rms_limit=.002, scaled_error_limit=.002,
            timing_rows=14, timed_tokens=2048, weight_rotations=3, rotated_weight_bytes=133693440,
            resource_api_rows=2, resource_api_does_not_measure_active_blocks=True,
            numerical_exit=1, unsafe_runtime_exit=2, timing_after_safe_numerical_rejection=True,
            launchers_changed=False, completed_gpu_checks=0),
        frozen_ssm_plan_sha256=ssm.sha(frozen_path), frozen_fixtures=88, frozen_manifests=5,
        frozen_campaign_unchanged=True, commands=commands,
        limits='BK1 doubles source K-stage barriers. Compact storage and compiler occupancy do not '
               'establish actual residency or speed. Integer address checks do not establish GPU '
               'memory safety or floating equivalence. GPU/operator/original-model runs remain pending.',
        gpu_run=False, model_inference=False, numerical_acceptance=False, performance_gain=False, goal_met=False)
    with (ROOT / 'config/q2-ssm-compact-lds-static.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(other_kernels_exact=161, shared_bytes=[49152, 32768],
        actual_vgprs=[report['parent_kernel']['compiler_comments']['NumVgprs'],
                     report['candidate_kernel']['compiler_comments']['NumVgprs']],
        scratch_bytes=0, fixture_pairs=30, oracle_checks=60, timing_rows=14,
        frozen_campaign_unchanged=True, gpu_run=False)))


if __name__ == '__main__':
    main()
