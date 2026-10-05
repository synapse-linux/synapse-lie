#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify untouched parent instructions and account for new Q8 chain bodies."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/q2-producer-q8-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    old = module('analyze-q2-down-half-storage-static.py')
    prepare = module('prepare-q2-producer-q8.py')
    manifest = ROOT / 'config/q2-producer-q8-source.json'
    source = json.loads(manifest.read_text())['variants']['producer-q8']
    assert prepare.inventory(ROOT / source['source']) == source['files']
    for key in ('parent_manifest', 'measured_parent', 'patch'):
        assert old.isa.sha(ROOT / source[key]) == source[key + '_sha256'], key
    saved = json.loads((ROOT / 'config/q2-scaled-wave-pack-static.json').read_text())
    parent_path = ROOT / saved['candidate_assembly_path']
    assert old.isa.sha(parent_path) == saved['candidate_assembly_sha256']
    path, down_path = OUT / 'candidate.s', OUT / 'down.s'
    parent, candidate = old.isa.parse(parent_path), old.isa.parse(path)
    down = old.isa.parse(down_path)
    before, after = parent_path.read_text(), path.read_text()
    assert len(parent) == 162 and len(candidate) == 166
    assert parent.keys() <= candidate.keys()
    for symbol in parent:
        assert old.instructions(before, symbol) == old.instructions(after, symbol), symbol
        assert parent[symbol]['resources'] == candidate[symbol]['resources'], symbol
    added = {s: candidate[s] for s in sorted(candidate.keys() - parent.keys())}
    assert len(added) == 4 and all('RoutedIQ2ProducerQ8Kernel' in s for s in added)
    assert len(down) == 6 and all('Q2ProducerQ8DownKernel' in s for s in down)
    report = dict(schema='synapse-lie.q2-producer-q8-static.v1',
        source_manifest_sha256=old.isa.sha(manifest), provider_files=len(source['files']),
        parent_assembly_sha256=old.isa.sha(parent_path), parent_recompiled=False,
        candidate_assembly_path=str(path.relative_to(ROOT)), candidate_assembly_sha256=old.isa.sha(path),
        down_assembly_path=str(down_path.relative_to(ROOT)), down_assembly_sha256=old.isa.sha(down_path),
        original_kernels_instruction_operand_resource_exact=len(parent),
        added_producer_kernels=added, added_down_kernels=down,
        arithmetic_change=source['arithmetic_change'],
        gpu_run=False, quality_accepted=False, goal_met=False)
    with (ROOT / 'config/q2-producer-q8-static.json').open('x') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps(dict(original_kernels_exact=len(parent),
        new_resources={s: v['resources'] for s, v in (added | down).items()}, gpu_run=False)))


if __name__ == '__main__':
    main()
