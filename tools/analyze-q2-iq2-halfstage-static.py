#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Inspect retained local assemblies; static counts are not GPU timings."""
import collections
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-iq2-halfstage-preparation'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path):
    text = path.read_text()
    kernels = {}
    for match in re.finditer(r'^(_Z[^\s:]+):\s*;', text, re.M):
        start, symbol = match.start(), match[1]
        end = text.index('\n\t.section\t.rodata', start)
        metadata_end = text.index('\n\t.end_amdhsa_kernel', end)
        body, metadata = text[start:end], text[end:metadata_end]
        resources = {k:int(re.search(r'\.amdhsa_'+k+r' (\d+)', metadata)[1])
                     for k in ('group_segment_fixed_size', 'private_segment_fixed_size',
                               'next_free_vgpr', 'next_free_sgpr', 'wavefront_size32')}
        mnemonics = re.findall(r'^\t([a-z][a-z_0-9]+)(?:\s|$)', body, re.M)
        normalized = re.sub(r'\.LBB\d+_', '.LBB_', body)
        kernels[symbol] = dict(resources=resources, instructions=len(mnemonics),
            mnemonics=dict(sorted(collections.Counter(mnemonics).items())),
            body_sha256=hashlib.sha256(normalized.encode()).hexdigest())
    return kernels


def main():
    output = ROOT/'config/q2-iq2-halfstage-swizzled-static.json'
    if output.exists():
        raise ValueError('Refusing to overwrite static evidence')
    paths = {k:OUT/v for k,v in dict(parent='parent.s', initial='candidate.s',
                                    swizzled='candidate-swizzled.s').items()}
    assemblies = {k:parse(p) for k,p in paths.items()}
    parent = assemblies['parent']
    expected = [s for s in parent if 'RoutedF16GEMMKernel' in s and 'WeightTypeE16' in s]
    assert len(expected) == 8
    for name in ('initial', 'swizzled'):
        candidate = assemblies[name]
        assert parent.keys() == candidate.keys()
        changed = [s for s in parent if parent[s]['body_sha256'] != candidate[s]['body_sha256']]
        assert sorted(changed) == sorted(expected)
        for symbol in expected:
            assert candidate[symbol]['resources']['private_segment_fixed_size'] == 0
            bn = int(re.search(r'WeightTypeE16ELi128ELi(\d+)ELi2', symbol)[1])
            assert candidate[symbol]['resources']['group_segment_fixed_size'] == 16384 + bn * 128
    source_path = ROOT/'config/q2-iq2-halfstage-swizzled-source.json'
    source = json.loads(source_path.read_text())['variants']['iq2-halfstage']
    folder = ROOT/source['source']
    assert {str(p.relative_to(folder)):sha(p) for p in folder.rglob('*') if p.is_file()} == source['files']
    assert sha(ROOT/source['control_include']) == source['control_include_sha256']
    commands = json.loads((OUT/'commands.json').read_text())
    commands += json.loads((OUT/'fixture-commands.json').read_text())
    commands += json.loads((OUT/'swizzled-commands.json').read_text())
    assert all(c['exit_code'] == 0 for c in commands)
    report = dict(schema='synapse-lie.q2-iq2-halfstage-swizzled-static.v1',
        source_manifest_sha256=sha(source_path), source_files_verified=len(source['files']),
        assembly_hashes={k:sha(p) for k,p in paths.items()}, commands=commands,
        initial_guard_failure=json.loads((OUT/'guards-command.json').read_text()),
        initial_guard_failure_corrected='New provider was missing from the final source whitelist; refusal occurred before staging or SSH. Original exit1 retained.',
        kernels_total=len(parent), unaffected_bodies_exact=len(parent)-len(expected),
        changed_iq2_paired_bodies={s:{k:a[s] for k,a in assemblies.items()} for s in expected},
        gpu_run=False, model_inference=False, numerical_acceptance=False,
        performance_gain=False, goal_met=False)
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(kernels_total=len(parent), unchanged=len(parent)-len(expected),
                         iq2_changed=len(expected), source_files=len(source['files']))))


if __name__ == '__main__':
    main()
