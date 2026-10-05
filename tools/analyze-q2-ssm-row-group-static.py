#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit the isolated SSM group4 source, grid ownership and compiled resources."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-ssm-row-group-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


prep = module('prepare-q2-ssm-row-group.py')
old = module('analyze-q2-down-half-storage-static.py')


def mapped_tiles(nx, group):
    for by in range(64):
        for bx in range(nx):
            within = (by % group)*nx+bx
            yield (by//group)*group+within % group, within//group


def mapping_checks():
    # This tests integer tile ownership, not CPU model inference.
    batches = sorted(set(range(1024, 2306)) | {
        4095, 4096, 4097, 8192, 16384, 32768, 65536, 131072, 262144, 1048576})
    counts = []
    for n in batches:
        nx = (n+127)//128
        seen = bytearray(64*nx)
        for row, token in mapped_tiles(nx, 4):
            assert 0 <= row < 64 and 0 <= token < nx
            index = row*nx+token
            assert not seen[index]
            seen[index] = 1
        assert all(seen)
        counts.append(64*nx)
    # Same 32-token convolution windows, sparse raw-output mask and history
    # dependencies. The boundary kernel executes after the complete projection.
    mask_checks = 0
    for n in (1024, 1025, 1055, 1056, 1151, 1152, 2047, 2048, 2049, 4097):
        raw = [t % 32 < 3 or t % 32 >= 29 or t+3 >= n for t in range(n)]
        interior = {t for t in range(n) if t % 32 >= 3}
        boundary = {t for tile in range((n+31)//32) for j in range(3)
                    if (t := tile*32+j) < n}
        assert not (interior & boundary)
        assert interior | boundary == set(range(n))
        for t in boundary:
            for src in range(t-3, t+1):
                assert src < 0 or raw[src]
        for t in interior:
            assert (t-3)//32 == t//32
        # Remaining6144 channels are raw projection output for every token.
        mask_checks += n*2
    sequence = {str(g):list(mapped_tiles(16, g)) for g in (1, 4)}
    return dict(grid_shapes=len(batches), tiles_checked=sum(counts),
        token_range=[min(batches), max(batches)], convolution_mask_class_checks=mask_checks,
        fixed2048_blocks=1024,
        first16_grid_enumerated_tiles={k:v[:16] for k,v in sequence.items()},
        fixed2048_tile_sets_equal=set(sequence['1']) == set(sequence['4']),
        hardware_execution_order_tested=False, floating_arithmetic_tested=False)


def compiler_comments(text, symbol):
    start = text.index(symbol+':')
    end = text.index('\n\t.end_amdhsa_kernel', start)
    info = text.index('; Kernel info:', end)
    next_start = text.index('\n\t.section\t.text', info)
    section = text[info:next_start]
    result = {}
    for field in ('NumVgprs', 'TotalNumSgprs', 'NumVGPRsForWavesPerEU', 'Occupancy'):
        match = re.search(r';\s*'+field+r':\s*(\d+)', section)
        assert match, (symbol, field)
        result[field] = int(match[1])
    return result


def main():
    source_path = ROOT/'config/q2-ssm-row-group-source.json'
    source = json.loads(source_path.read_text())['variants']['ssm-row-group']
    for key in ('parent_manifest', 'measured_parent', 'patch'):
        assert prep.sha(ROOT/source[key]) == source[key+'_sha256']
    parent_source = json.loads((ROOT/source['parent_manifest']).read_text())['variants']['scaled-wave-pack']
    for variant in (source, parent_source):
        assert prep.inventory(ROOT/variant['source']) == variant['files']
    before_source = (ROOT/parent_source['source']/prep.REL).read_text()
    after_source = (ROOT/source['source']/prep.REL).read_text()
    assert prep.once(prep.once(after_source, prep.ASSERT_AFTER, prep.ASSERT_BEFORE),
                     prep.LAUNCH_AFTER, prep.LAUNCH_BEFORE) == before_source
    for fragment in (
        'const unsigned row_group = blockIdx.y / kRowGroup;',
        'const unsigned within = (blockIdx.y % kRowGroup) * gridDim.x + blockIdx.x;',
        'const int r_block = (row_group * kRowGroup + within % kRowGroup) * BM;',
        'const int t_block = (within / kRowGroup) * BN;',
        'if (n_tokens < 1024 || m != 16384 || k != 2560 || channels != 10240 ||',
        'constexpr unsigned kSsmProjectionTileTokens = 32;'):
        assert fragment in before_source and fragment in after_source
    with TemporaryDirectory(dir=OUT, prefix='reconstruct-') as tmp:
        target = Path(tmp)/prep.REL
        target.parent.mkdir(parents=True)
        target.write_text(before_source)
        result = subprocess.run(['patch', '--batch', '-p1', '-i', str(ROOT/source['patch'])],
                                cwd=tmp, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
        assert prep.sha(target) == source['files'][prep.REL]
    saved = json.loads((ROOT/'config/q2-scaled-wave-pack-static.json').read_text())
    parent_path = ROOT/saved['candidate_assembly_path']
    assert prep.sha(parent_path) == saved['candidate_assembly_sha256']
    candidate_path = OUT/'candidate.s'
    a, b = old.isa.parse(parent_path), old.isa.parse(candidate_path)
    assert len(a) == len(b) == 162
    removed, added = set(a)-set(b), set(b)-set(a)
    assert len(removed) == len(added) == 1
    control, candidate = next(iter(removed)), next(iter(added))
    assert 'DenseF16GEMMKernel' in control
    assert 'ILi256ELi128ELi2ELi8ELi1ELi1ELb0ELb1' in control
    assert control.replace('ELi8ELi1ELi1ELb0ELb1', 'ELi8ELi1ELi4ELb0ELb1') == candidate
    before, after = parent_path.read_text(), candidate_path.read_text()
    for symbol in set(a) & set(b):
        assert old.instructions(before, symbol) == old.instructions(after, symbol), symbol
        assert a[symbol]['resources'] == b[symbol]['resources'], symbol
    # Resource and instruction differences are observations, not a speed gate.
    assert b[candidate]['resources']['private_segment_fixed_size'] == 0
    invariant_counts = ('v_wmma_f32_16x16x16_f16', 's_barrier', 'global_load_b128',
                        'ds_load_b128', 'ds_store_b128')
    counts = {name:[a[control]['mnemonics'].get(name,0), b[candidate]['mnemonics'].get(name,0)]
              for name in invariant_counts}
    checks = mapping_checks()
    commands = {name:json.loads((OUT/(name+'-command.json')).read_text())
                for name in ('generation', 'assembly')}
    assert all(c['exit_code'] == 0 for c in commands.values())
    initial = ROOT/'config/q2-ssm-row-group-static-initial.json'
    failure = OUT/'static-command.json'
    report = dict(schema='synapse-lie.q2-ssm-row-group-static.v2',
        source_manifest_sha256=prep.sha(source_path), provider_files=1027,
        literal_source_changes=2, source_reconstruction_exact=True,
        parent_assembly_path=str(parent_path.relative_to(ROOT)), parent_assembly_sha256=prep.sha(parent_path),
        candidate_assembly_path=str(candidate_path.relative_to(ROOT)), candidate_assembly_sha256=prep.sha(candidate_path),
        parent_recompiled=False, other_kernels_instruction_operand_resource_exact=161,
        parent_kernel=dict(symbol=control, **a[control], compiler_comments=compiler_comments(before,control)),
        candidate_kernel=dict(symbol=candidate, **b[candidate], compiler_comments=compiler_comments(after,candidate)),
        selected_instruction_counts=counts, symbolic_mapping=checks, commands=commands,
        retained_initial_report=dict(path=str(initial.relative_to(ROOT)), sha256=prep.sha(initial)),
        retained_initial_checker_failure=json.loads(failure.read_text()),
        checker_corrections='Initial symbol check expected ELi at the first template argument instead of ILi. The next successful report stopped before compiler comments; this additive report reads the actual per-kernel comment section. Neither fix changes the candidate or assembly.',
        compiler_metadata_is_not_measured_hardware_occupancy=True,
        logical_weight_activation_output_bytes_unchanged=True,
        cpu_checks_are_not_gpu_or_model_evidence=True,
        gpu_run=False, model_inference=False, numerical_acceptance=False,
        performance_gain=False, goal_met=False)
    with (ROOT/'config/q2-ssm-row-group-static.json').open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(other_kernels_exact=161, symbolic_mapping=checks,
        parent_resources=a[control]['resources'], candidate_resources=b[candidate]['resources'],
        instructions_before=a[control]['instructions'], instructions_after=b[candidate]['instructions'],
        selected_instruction_counts=counts, gpu_run=False)))


if __name__ == '__main__':
    main()
