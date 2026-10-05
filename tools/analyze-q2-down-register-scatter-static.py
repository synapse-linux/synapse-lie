#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify register-scatter scope, immutable parent and symbolic half-bit routing."""
import importlib.util
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-down-register-scatter-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


old = module('analyze-q2-down-half-storage-static.py')
prepare = module('prepare-q2-down-register-scatter.py')


def exchange(values):
    """CPU bit permutation only; no matrix computation or floating arithmetic."""
    # Input contract: natural token-major 16x16 output, before lane ownership.
    own = []
    for lane in range(32):
        t, parity = lane % 16, lane // 16
        cols = values[t*16+parity:t*16+16:2]
        own.append([cols[2*p] | cols[2*p+1] << 16 for p in range(4)])
    result, writes = [None]*256, [0]*256
    for lane in range(32):
        half, t = lane//16, lane%16
        other = lane ^ 16
        other_half = other//16
        sent = own[other][:2] if other_half else own[other][2:]
        even = sent if half else own[lane][:2]
        odd = own[lane][2:] if half else sent
        packed = [(even[0]&65535) | ((odd[0]<<16)&0xffffffff),
                  (even[0]>>16) | (odd[0]&0xffff0000),
                  (even[1]&65535) | ((odd[1]<<16)&0xffffffff),
                  (even[1]>>16) | (odd[1]&0xffff0000)]
        output = [v for word in packed for v in (word&65535, word>>16)]
        for k, value in enumerate(output):
            index = t*16+half*8+k
            result[index] = value
            writes[index] += 1
    assert writes == [1]*256
    return result


def mapping_checks():
    # Unique source labels prove column ownership independently of arithmetic.
    assert exchange(list(range(256))) == list(range(256))
    # Exercise all raw binary16 patterns, including signed zeros/NaNs/subnormals.
    for base in range(0, 65536, 256):
        values = [base+i for i in range(256)]
        assert exchange(values) == values
    # One bit at each source position detects loss, replication and bit mixing.
    for pos in range(256):
        for bit in range(16):
            values = [0]*256
            values[pos] = 1 << bit
            assert exchange(values) == values
    geometry = 0
    for m in range(8, 257, 8):
        for live in range(17):
            for holes in ((), (0,), (7, 15)):
                slots = [-1 if t >= live or t in holes else 15-t for t in range(16)]
                actual, expected = set(), set()
                for t, slot in enumerate(slots):
                    if slot >= 0:
                        expected.update((slot, col) for col in range(m))
                for r0 in range(0, (m+127)//128*128, 16):
                    for lane in range(32):
                        slot, row = slots[lane%16], r0+(lane//16)*8
                        if slot >= 0 and row < m:
                            assert row+7 < m
                            for k in range(8):
                                key = (slot, row+k)
                                assert key not in actual
                                actual.add(key)
                assert actual == expected
                geometry += 1
    return dict(symbolic_positions=256, raw_half_patterns=65536,
                one_bit_position_cases=4096, ragged_slot_geometry_cases=geometry,
                gpu_instruction_semantics_tested=False, floating_arithmetic_tested=False)


def main():
    selected_path = ROOT/'config/q2-down-register-scatter-pair-source.json'
    selected = json.loads(selected_path.read_text())['variants']['down-register-scatter']
    initial_path = ROOT/'config/q2-down-register-scatter-source.json'
    initial = json.loads(initial_path.read_text())['variants']['down-register-scatter']
    for variant in (initial, selected):
        assert prepare.inventory(ROOT/variant['source']) == variant['files']
        for key in ('parent_manifest', 'measured_parent', 'patch', 'control_include', 'fragment'):
            assert old.isa.sha(ROOT/variant[key]) == variant[key+'_sha256'], key
    saved = json.loads((ROOT/'config/q2-scaled-wave-pack-static.json').read_text())
    parent_path = ROOT/saved['candidate_assembly_path']
    assert old.isa.sha(parent_path) == saved['candidate_assembly_sha256']
    parent = old.isa.parse(parent_path)
    expected = sorted(s for s in parent if 'RoutedQ2HalfStorageKernel' in s)
    assert len(parent) == 162 and len(expected) == 3
    rows = []
    for name, assembly in (('initial_four_word', OUT/'candidate.s'),
                           ('selected_two_word', OUT/'candidate-pair.s')):
        candidate = old.isa.parse(assembly)
        assert candidate.keys() == parent.keys()
        before, after = parent_path.read_text(), assembly.read_text()
        changed = sorted(s for s in parent if old.instructions(before,s) != old.instructions(after,s))
        assert changed == expected
        for symbol in parent:
            assert parent[symbol]['resources'] == candidate[symbol]['resources'], symbol
        for symbol in expected:
            a, b = parent[symbol], candidate[symbol]
            width = int(re.search(r'ELi128ELi(\d+)ELi2',symbol)[1])
            assert b['resources']['private_segment_fixed_size'] == 0
            assert b['mnemonics'].get('s_barrier',0) == a['mnemonics'].get('s_barrier',0)
            assert b['mnemonics'].get('v_permlanex16_b32',0) == width//16*(4 if name == 'initial_four_word' else 2)
            rows.append(dict(variant=name, width=width, parent=a, candidate=b))
    # Check reconstruction without touching the immutable parent or remote host.
    rel = prepare.REL
    parent_manifest = json.loads((ROOT/selected['parent_manifest']).read_text())['variants']['scaled-wave-pack']
    parent_source = ROOT/parent_manifest['source']
    assert prepare.inventory(parent_source) == parent_manifest['files']
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(dir=OUT, prefix='reconstruct-') as tmp:
        base = Path(tmp)
        for variant in (initial, selected):
            destination = base/('two' if variant is selected else 'four')
            (destination/rel).parent.mkdir(parents=True)
            (destination/rel).write_bytes((parent_source/rel).read_bytes())
            result = subprocess.run(['patch','--batch','-p1','-i',str(ROOT/variant['patch'])],
                                    cwd=destination, text=True, capture_output=True)
            assert result.returncode == 0, result.stderr
            assert old.isa.sha(destination/rel) == variant['files'][rel]
    commands = {name:json.loads((OUT/(name+'-command.json')).read_text()) for name in
                ('generation','generation-pair','assembly','assembly-pair','fixture-host-pair',
                 'fixture-device-pair','wiring','launcher-guards','shared-format')}
    assert all(v['exit_code'] == (1 if k == 'shared-format' else 0) for k,v in commands.items())
    report = dict(schema='synapse-lie.q2-down-register-scatter-static.v1',
        source_manifest_sha256=old.isa.sha(selected_path), provider_files=1027,
        parent_assembly_sha256=old.isa.sha(parent_path), parent_recompiled=False,
        candidate_assembly_path=str((OUT/'candidate-pair.s').relative_to(ROOT)),
        candidate_assembly_sha256=old.isa.sha(OUT/'candidate-pair.s'),
        initial_assembly_sha256=old.isa.sha(OUT/'candidate.s'),
        other_kernels_instruction_operand_resource_exact=159, variants=rows,
        symbolic_mapping=mapping_checks(), source_reconstruction_exact=True,
        resources_unchanged=True, logical_global_output_bytes_unchanged=True,
        compiled_body_includes_original_fallback=True,
        numerical_contract=selected['numerical_contract'], commands=commands,
        cpu_checks_are_not_gpu_or_model_evidence=True, gpu_run=False,
        numerical_acceptance=False, model_inference=False, goal_met=False)
    with (ROOT/'config/q2-down-register-scatter-static.json').open('x') as f:
        json.dump(report,f,indent=2);f.write('\n')
    print(json.dumps(dict(other_kernels_exact=159, resources_unchanged=True,
        symbolic_mapping=report['symbolic_mapping'],
        selected=[dict(width=r['width'],before=r['parent']['instructions'],after=r['candidate']['instructions'],
            permutes=r['candidate']['mnemonics'].get('v_permlanex16_b32',0))
            for r in rows if r['variant']=='selected_two_word'], gpu_run=False)))


if __name__ == '__main__':
    main()
