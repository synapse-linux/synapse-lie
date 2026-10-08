#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind exact compact IQ2 table reuse to saved parent ISA without rebuilding it."""
import importlib.util
import json
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/q2-iq2-table-lds-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


group = module('analyze-q2-ssm-row-group-compose-static.py')
prepare = module('prepare-q2-iq2-table-lds.py')
sha = prepare.sha


def main():
    manifest_path = ROOT / 'config/q2-iq2-table-lds-source.json'
    source = json.loads(manifest_path.read_text())['variants']['iq2-table-lds']
    for key in ('parent_manifest', 'measured_parent', 'patch', 'generator'):
        assert sha(ROOT / source[key]) == source[key + '_sha256'], key
    assert sha(ROOT / source['source'] / source['numerical_include']) == source['numerical_include_sha256']
    parent = json.loads((ROOT / source['parent_manifest']).read_text())['variants']['iq2-fixed-bounds']
    for provider in (parent, source):
        assert prepare.inventory(ROOT / provider['source']) == provider['files']
    original = (ROOT / parent['source'] / prepare.REL).read_text()
    candidate = (ROOT / source['source'] / prepare.REL).read_text()
    assert prepare.prepare.function(original, prepare.prepare.PREFIX) == prepare.prepare.function(candidate, prepare.prepare.PREFIX)
    control = (ROOT / 'experiments/q2-iq2-register-stage-control.inc').read_text()
    assert prepare.prepare.function(original, prepare.prepare.PREFIX) == prepare.prepare.function(
        control, prepare.prepare.PREFIX).replace('RoutedIq2RegisterStageControlKernel', 'RoutedF16GEMMKernel')
    metadata_path = ROOT / 'config/q2-iq2-fixed-bounds-static.json'
    metadata = json.loads(metadata_path.read_text())
    before_path = ROOT / metadata['candidate_assembly_path']
    assert sha(before_path) == metadata['candidate_assembly_sha256']
    after_path = OUT / 'candidate.s'
    before, after = before_path.read_text(), after_path.read_text()
    a, b = group.old.isa.parse(before_path), group.old.isa.parse(after_path)
    assert len(a) == len(b) == 164
    common = set(a) & set(b)
    assert len(common) == 162 and len(set(a) - set(b)) == 2
    for symbol in common:
        assert group.old.instructions(before, symbol) == group.old.instructions(after, symbol), symbol
        assert a[symbol]['resources'] == b[symbol]['resources'], symbol
    pairs = []
    for symbol in sorted(set(b) - set(a)):
        old = symbol.replace('23RoutedIq2TableLdsKernel', '26RoutedIq2FixedBoundsKernel')
        assert old in a and 'WeightTypeE16ELi128ELi' in old
        p, c = a[old], b[symbol]
        for key in ('private_segment_fixed_size', 'wavefront_size32'):
            assert p['resources'][key] == c['resources'][key], key
        assert c['resources']['private_segment_fixed_size'] == 0
        for opcode in ('v_pk_fma_f16', 'v_wmma_f32_16x16x16_f16', 'v_exp_f32_e32'):
            assert p['mnemonics'][opcode] == c['mnemonics'][opcode], opcode
        assert c['resources']['group_segment_fixed_size'] == p['resources']['group_segment_fixed_size'] + 3072
        assert c['mnemonics']['s_barrier'] == p['mnemonics']['s_barrier'] + 1
        assert c['mnemonics']['global_load_b64'] < p['mnemonics']['global_load_b64']
        assert c['mnemonics'].get('ds_bpermute_b32', 0) == p['mnemonics'].get('ds_bpermute_b32', 0)
        pairs.append(dict(parent=dict(symbol=old, **p), candidate=dict(symbol=symbol, **c,
            compiler_comments=group.static.compiler_comments(after, symbol))))
    with TemporaryDirectory(dir=OUT, prefix='reconstruct-') as temporary:
        dest = Path(temporary) / prepare.REL
        dest.parent.mkdir(parents=True)
        dest.write_text(original)
        result = subprocess.run(['patch', '--batch', '-p1', '-i', str(ROOT / source['patch'])],
                                cwd=temporary, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        for name in source['changed_files']:
            assert sha(Path(temporary) / name) == source['files'][name], name
    commands = {name: json.loads((OUT / (name + '-command.json')).read_text())
                for name in ('generation', 'assembly')}
    assert all(row['exit_code'] == 0 for row in commands.values())
    assert [v.replace('q2-iq2-table-lds', 'q2-iq2-fixed-bounds') for v in
            json.loads((OUT / 'assembly-argv.json').read_text())] == json.loads(
                (before_path.parent / 'assembly-argv.json').read_text())
    report = dict(schema='synapse-lie.q2-iq2-table-lds-static.v1',
        source_manifest_sha256=sha(manifest_path), provider_files=1029,
        parent_assembly_path=str(before_path.relative_to(ROOT)), parent_assembly_sha256=sha(before_path),
        candidate_assembly_path=str(after_path.relative_to(ROOT)), candidate_assembly_sha256=sha(after_path),
        parent_recompiled=False, compiler_arguments_match_except_paths=True,
        source_patch_reconstruction_exact=True, original_template_source_exact=True,
        literal_control_current_parent_exact=True, original_kernels_instruction_operand_resource_exact=162,
        added_private_kernels=2, replaced_parent_private_kernels=2, static_kernel_pairs=pairs, commands=commands,
        output_grid_rows_exact=640, output_grid_blocks=10, host_grid_mapping_proof='Every block0..9 owns64 rows; all row pairs are even and stay within640, output stride640 keeps float2 alignment.',
        limits='Static compiler/source/bounded grid evidence only. F16 FMA/WMMA/barrier counts alone do not establish numerical equality or a speedup. No GPU reservation.',
        gpu_run=False, model_inference=False, numerical_acceptance=False, performance_gain=False, goal_met=False)
    with (ROOT / 'config/q2-iq2-table-lds-static.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(original_bodies_exact=162, added=2, instructions=[
        [pair['parent']['instructions'], pair['candidate']['instructions']] for pair in pairs],
        spills=0, GPU_run=False)))


if __name__ == '__main__':
    main()
