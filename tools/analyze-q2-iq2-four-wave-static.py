#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare the four-wave source/ISA with retained1585, without rebuilding it."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-iq2-four-wave-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


group = module('analyze-q2-ssm-row-group-compose-static.py')
prepare = module('prepare-q2-iq2-four-wave.py')
sha = prepare.sha


def main():
    manifest_path = ROOT/'config/q2-iq2-four-wave-source.json'
    source = json.loads(manifest_path.read_text())['variants']['iq2-four-wave']
    for key, digest in source.items():
        if key.endswith('_sha256'):
            assert sha(ROOT/source[key[:-7]]) == digest, key
    parent = json.loads((ROOT/source['parent_manifest']).read_text())['variants']['ssm-fixed-bounds']
    for provider in (parent, source):
        assert prepare.inventory(ROOT/provider['source']) == provider['files']
    assert prepare.ownership() == source['symbolic_ownership']
    original = (ROOT/parent['source']/prepare.REL).read_text()
    control = (ROOT/source['control_include']).read_text()
    assert prepare.function(original, prepare.PREFIX) == prepare.function(
        control, prepare.PREFIX).replace('RoutedIq2FourWaveControlKernel','RoutedF16GEMMKernel')
    metadata_path = ROOT/'config/q2-ssm-fixed-bounds-static.json'
    metadata = json.loads(metadata_path.read_text())
    before_path = ROOT/metadata['candidate_assembly_path']
    assert sha(before_path) == metadata['candidate_assembly_sha256']
    after_path = OUT/'candidate.s'
    before, after = before_path.read_text(), after_path.read_text()
    a, b = group.old.isa.parse(before_path), group.old.isa.parse(after_path)
    assert len(a) == len(b) == 162
    pairs, changed = {}, []
    for symbol in b:
        old = (re.sub('ELb[01]EEEv', 'EEEv', symbol, count=1)
               if 'RoutedF16GEMMKernel' in symbol else symbol)
        assert old in a and old not in pairs
        pairs[old] = symbol
        body = group.old.instructions(after, symbol).replace(symbol, old)
        if body != group.old.instructions(before, old) or a[old]['resources'] != b[symbol]['resources']:
            changed.append((old, symbol))
    assert set(pairs) == set(a) and len(changed) == 1
    old, new = changed[0]
    assert 'WeightTypeE16ELi128ELi64ELi2ELb1ELb0ELb0ELb1EEEv' in new
    p, c = a[old], b[new]
    for item in (p, c):
        assert item['resources']['group_segment_fixed_size'] == 17536
        assert item['resources']['private_segment_fixed_size'] == 0
        assert item['resources']['wavefront_size32'] == 1
    assert c['mnemonics']['v_wmma_f32_16x16x16_f16'] == 2*p['mnemonics']['v_wmma_f32_16x16x16_f16']
    assert [p['mnemonics']['s_barrier'], c['mnemonics']['s_barrier']] == [10, 2]
    with TemporaryDirectory(dir=OUT, prefix='reconstruct-') as temporary:
        dest = Path(temporary)/prepare.REL
        dest.parent.mkdir(parents=True)
        dest.write_text(original)
        result = subprocess.run(['patch', '--batch', '-p1', '-i', str(ROOT/source['patch'])],
                                cwd=temporary, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert sha(dest) == source['files'][prepare.REL]
    commands = {name: json.loads((OUT/(name+'-command.json')).read_text()) for name in
                ('generation', 'assembly', 'fixture-host', 'fixture-device', 'launcher-guards')}
    assert all(c['exit_code'] == 0 for c in commands.values())
    assert [v.replace('q2-iq2-four-wave','q2-ssm-fixed-bounds') for v in
            json.loads((OUT/'assembly-argv.json').read_text())] == json.loads(
                (before_path.parent/'assembly-argv.json').read_text())
    report = dict(schema='synapse-lie.q2-iq2-four-wave-static.v1',
        source_manifest_sha256=sha(manifest_path), provider_files=1027,
        parent_static_metadata_sha256=sha(metadata_path),
        parent_assembly_path=str(before_path.relative_to(ROOT)), parent_assembly_sha256=sha(before_path),
        candidate_assembly_path=str(after_path.relative_to(ROOT)), candidate_assembly_sha256=sha(after_path),
        parent_recompiled=False, compiler_arguments_match_except_paths=True,
        source_patch_reconstruction_exact=True, literal_control_current_parent_exact=True,
        other_kernels_instruction_operand_resource_exact=161,
        normalization='Only added private template boolean in symbol, assembler comments and local label function numbers; instruction operands retained.',
        symbolic_ownership=source['symbolic_ownership'],
        parent_kernel=dict(symbol=old, **p, compiler_comments=group.static.compiler_comments(before, old)),
        candidate_kernel=dict(symbol=new, **c, compiler_comments=group.static.compiler_comments(after, new)),
        fixture='tests/q2_iq2_four_wave.hip', fixture_sha256=sha(ROOT/'tests/q2_iq2_four_wave.hip'),
        expected_output_pairs=96, expected_timing_samples=42, commands=commands,
        limits='Fewer waves and unchanged LDS do not establish active occupancy, speed or compiled numerical equivalence. VGPR rises104 to193. Static instruction totals are per-wave bodies with different work, not runtime instruction counts. GPU component and original model remain required.',
        gpu_run=False, model_inference=False, numerical_acceptance=False, performance_gain=False, goal_met=False)
    with (ROOT/'config/q2-iq2-four-wave-static.json').open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(kernels=162, unchanged=161,
        resources=[p['resources'],c['resources']], instruction_counts=[p['instructions'],c['instructions']],
        static_block_barriers=[10,2], gpu_run=False)))


if __name__ == '__main__':
    main()
