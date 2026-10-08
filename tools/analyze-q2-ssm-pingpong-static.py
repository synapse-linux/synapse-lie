#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit alternate SSM activation slots without claiming hardware race freedom."""
import importlib.util
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/q2-ssm-pingpong-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


group = module('analyze-q2-ssm-row-group-compose-static.py')
prepare = module('prepare-q2-ssm-pingpong.py')
ssm, old = group.ssm, group.old


def main():
    manifest = ROOT / 'config/q2-ssm-pingpong-source.json'
    source = json.loads(manifest.read_text())['variants']['ssm-pingpong']
    for key in ('parent_manifest', 'measured_parent', 'patch', 'preceding_local_manifest'):
        assert ssm.sha(ROOT / source[key]) == source[key + '_sha256'], key
    parent = json.loads((ROOT / source['parent_manifest']).read_text())['variants']['down-register-scatter']
    compact = json.loads((ROOT / source['preceding_local_manifest']).read_text())['variants']['ssm-compact-lds']
    for provider in (source, parent, compact):
        assert ssm.inventory(ROOT / provider['source']) == provider['files']
    assert prepare.schedule_checks() == source['synchronization_proof']
    assert source['inherited_compact_layout_proof'] == compact['source_layout_proof']
    expected_layout = dict(compact['source_layout_proof'],
        source_stage_bytes=[49152, 32768], source_barriers_per_block=[80, 81],
        block_barriers_per_k_stage=1, final_block_barriers=1, wave_barriers_per_k_stage=1)
    assert source['source_layout_proof'] == expected_layout
    correction = json.loads((OUT / 'manifest-metadata-correction.json').read_text())
    assert ssm.sha(OUT / 'initial-source-manifest.json') == correction['initial_sha256']
    assert ssm.sha(manifest) == correction['corrected_sha256']
    initial = json.loads((OUT / 'initial-source-manifest.json').read_text())['variants']['ssm-pingpong']
    assert initial['files'] == source['files'] and correction['source_changed'] is False
    code = (ROOT / source['source'] / ssm.REL).read_text()
    compact_code = (ROOT / compact['source'] / ssm.REL).read_text()
    for prefix in ('bool DenseF16SsmGemm(', 'float SsmConv4Value(', '__global__ void SsmConvBoundaryKernel('):
        assert ssm.function(code, prefix) == ssm.function(compact_code, prefix)
    assert 'static_assert(BK == 1 && WM == 8 && WN == 1 && kWaveRowTiles == 2);' in code
    assert '''  if constexpr (kSsmConv) {
    // The transpose reuses other waves' A/B bytes: retire the complete block.
    __syncthreads();
  }''' in code
    with TemporaryDirectory(dir=OUT, prefix='reconstruct-') as tmp:
        target = Path(tmp) / ssm.REL
        target.parent.mkdir(parents=True)
        target.write_bytes((ROOT / parent['source'] / ssm.REL).read_bytes())
        p = subprocess.run(['patch', '--batch', '-p1', '-i', str(ROOT / source['patch'])],
                           cwd=tmp, text=True, capture_output=True)
        assert p.returncode == 0, p.stderr
        assert ssm.sha(target) == source['files'][ssm.REL]
    saved = json.loads((ROOT / 'config/q2-down-register-scatter-static.json').read_text())
    parent_asm = ROOT / saved['candidate_assembly_path']
    assert ssm.sha(parent_asm) == saved['candidate_assembly_sha256']
    compact_report_path = ROOT / 'config/q2-ssm-compact-lds-static.json'
    compact_report = json.loads(compact_report_path.read_text())
    compact_asm = ROOT / compact_report['candidate_assembly_path']
    assert ssm.sha(compact_asm) == compact_report['candidate_assembly_sha256']
    candidate_asm = OUT / 'candidate.s'
    a, b, c = old.isa.parse(parent_asm), old.isa.parse(candidate_asm), old.isa.parse(compact_asm)
    removed, added = a.keys() - b.keys(), b.keys() - a.keys()
    assert len(a) == len(b) == 162 and len(removed) == len(added) == 1 and b.keys() == c.keys()
    control, candidate = next(iter(removed)), next(iter(added))
    before, after, compact_text = parent_asm.read_text(), candidate_asm.read_text(), compact_asm.read_text()
    for symbol in a.keys() & b.keys():
        assert old.instructions(before, symbol) == old.instructions(after, symbol), symbol
        assert a[symbol]['resources'] == b[symbol]['resources'], symbol
    assert b[candidate]['resources']['group_segment_fixed_size'] == 32768
    assert b[candidate]['resources']['private_segment_fixed_size'] == 0
    assert b[candidate]['resources']['wavefront_size32'] == 1
    contract = compact_report['fixture_contract']
    for key in ('fixture', 'control_include', 'oracle'):
        assert ssm.sha(ROOT / contract[key]) == contract[key + '_sha256']
    commands = {name: json.loads((OUT / (name + '-command.json')).read_text())
                for name in ('generation', 'assembly', 'fixture-host', 'fixture-device')}
    assert all(row['exit_code'] == 0 for row in commands.values())
    frozen_path = ROOT / 'config/q2-ssm-row-group-plan.json'
    frozen = json.loads(frozen_path.read_text())
    for p, digest in {**frozen['fixtures'], **frozen['manifests'],
                      frozen['window_helper']: frozen['window_helper_sha256']}.items():
        assert ssm.sha(ROOT / p) == digest, p
    report = dict(schema='synapse-lie.q2-ssm-pingpong-static.v1',
        source_manifest_sha256=ssm.sha(manifest), source_files=1027,
        parent_assembly_path=str(parent_asm.relative_to(ROOT)), parent_assembly_sha256=ssm.sha(parent_asm),
        candidate_assembly_path=str(candidate_asm.relative_to(ROOT)), candidate_assembly_sha256=ssm.sha(candidate_asm),
        compact_report_sha256=ssm.sha(compact_report_path), parent_recompiled=False,
        source_reconstruction_exact=True, other_kernels_instruction_operand_resource_exact=161,
        grid_boundary_and_convolution_helpers_unchanged=True,
        parent_kernel=dict(symbol=control, **a[control], compiler_comments=group.static.compiler_comments(before, control)),
        compact_kernel=dict(symbol=candidate, **c[candidate], compiler_comments=group.static.compiler_comments(compact_text, candidate)),
        candidate_kernel=dict(symbol=candidate, **b[candidate], compiler_comments=group.static.compiler_comments(after, candidate)),
        synchronization_proof=source['synchronization_proof'], source_layout_proof=source['source_layout_proof'],
        fixture_contract=contract, fixture_unchanged=True, metadata_correction=correction,
        frozen_ssm_plan_sha256=ssm.sha(frozen_path), frozen_fixtures=88, frozen_manifests=5,
        frozen_campaign_unchanged=True, commands=commands,
        limits='The integer scheduler validates an ownership/version model and detects unsafe controls. '
               'It does not prove compiler/device memory ordering, numerical equivalence or throughput. '
               'Source barrier counts and compiler occupancy are not measured active-wave or timing data.',
        gpu_run=False, model_inference=False, numerical_acceptance=False, performance_gain=False, goal_met=False)
    with (ROOT / 'config/q2-ssm-pingpong-static.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(other_kernels_exact=161, shared_bytes=32768,
        actual_vgprs=report['candidate_kernel']['compiler_comments']['NumVgprs'], scratch_bytes=0,
        modeled_schedules=129, source_block_barriers=[160, 81], frozen_campaign_unchanged=True, gpu_run=False)))


if __name__ == '__main__':
    main()
