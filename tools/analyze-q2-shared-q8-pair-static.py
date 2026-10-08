#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify preserved production bodies and the isolated shared-Q8 addition."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'evidence/q2-shared-q8-pair-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    previous = module('analyze-q2-down-half-storage-static.py')
    prepare = module('prepare-q2-shared-q8-pair.py')
    sha = previous.isa.sha
    manifest = ROOT/'config/q2-shared-q8-pair-source.json'
    source = json.loads(manifest.read_text())['variants']['shared-q8-pair']
    assert prepare.inventory(ROOT/source['source']) == source['files']
    for key in ('parent_manifest', 'measured_parent', 'patch'):
        assert sha(ROOT/source[key]) == source[key+'_sha256'], key
    saved = json.loads((ROOT/'config/q2-half-consumer-eight-static.json').read_text())
    parent_path = ROOT/saved['candidate_assembly_path']
    assert sha(parent_path) == saved['candidate_assembly_sha256']
    candidate_path = OUT/'candidate.s'
    parent, candidate = previous.isa.parse(parent_path), previous.isa.parse(candidate_path)
    assert len(parent) == 161 and len(candidate) == 162
    before, after = parent_path.read_text(), candidate_path.read_text()
    for symbol in parent:
        assert previous.instructions(before, symbol) == previous.instructions(after, symbol), symbol
        assert parent[symbol]['resources'] == candidate[symbol]['resources'], symbol
    symbols = set(candidate) - set(parent)
    assert len(symbols) == 1 and 'SharedQ8PairKernel' in next(iter(symbols))
    addition = candidate[next(iter(symbols))]
    assert addition['resources']['private_segment_fixed_size'] == 0
    assert addition['resources']['next_free_vgpr'] == 180
    assert addition['resources']['group_segment_fixed_size'] == 18432
    retained = []
    for name, suffix in (('initial', '-initial'), ('fenced', '-fenced')):
        old = json.loads((OUT/(name+'-source.json')).read_text())['variants']['shared-q8-pair']
        actual_path = ROOT/(old['source']+suffix)
        assert prepare.inventory(actual_path) == old['files']
        assembly = OUT/(name+'-candidate.s')
        kernels = previous.isa.parse(assembly)
        new = [v for k, v in kernels.items() if 'SharedQ8PairKernel' in k]
        assert len(new) == 1 and new[0]['resources']['private_segment_fixed_size'] == 148
        retained.append(dict(name=name, source=str(actual_path.relative_to(ROOT)),
                             assembly_sha256=sha(assembly), resources=new[0]['resources'],
                             compile_succeeded=True, gpu_run=False))
    commands = {n: json.loads((OUT/(n+'-command.json')).read_text()) for n in
                ('prepare-v3', 'assembly-v3', 'fixture-host', 'fixture-device', 'executor', 'launcher-guards')}
    assert all(c['exit_code'] == 0 for c in commands.values())
    report = dict(schema='synapse-lie.q2-shared-q8-pair-static.v1',
        source_manifest_sha256=sha(manifest), provider_files=1027,
        parent_assembly_sha256=sha(parent_path), parent_recompiled=False,
        candidate_assembly_path=str(candidate_path.relative_to(ROOT)),
        candidate_assembly_sha256=sha(candidate_path), original_kernels_exact=161,
        new_kernel=addition, retained_compiled_preparations=retained, commands=commands,
        numerical_contract=source['numerical_contract'], gpu_run=False,
        numerical_acceptance=False, independent_quality=False, goal_met=False)
    with (ROOT/'config/q2-shared-q8-pair-static.json').open('x') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps(dict(original_kernels_exact=161, new_kernel=addition['resources'],
                          retained_spilling_versions=2, gpu_run=False)))


if __name__ == '__main__':
    main()
