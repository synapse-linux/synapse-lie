#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind the no-spill revision to retained parent and original dot arithmetic."""
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'evidence/q2-producer-q8-preparation'


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / name)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def tokens(source):
    source = re.sub(r'//[^\n]*|/\*.*?\*/', '', source, flags=re.S)
    return re.findall(r'\w+|[^\w\s]', source)


def main():
    previous = module('analyze-q2-down-half-storage-static.py')
    prepare = module('prepare-q2-producer-q8.py')
    manifest = ROOT / 'config/q2-producer-q8-source-v2.json'
    source = json.loads(manifest.read_text())['variants']['producer-q8']
    provider = ROOT / source['source']
    assert prepare.inventory(provider) == source['files']
    for key in ('parent_manifest', 'measured_parent', 'patch', 'initial_source_manifest'):
        assert previous.isa.sha(ROOT / source[key]) == source[key + '_sha256'], key
    initial_manifest = ROOT / source['initial_source_manifest']
    initial = json.loads(initial_manifest.read_text())['variants']['producer-q8']
    rel = prepare.REL + 'mmq/q2_producer_q8.hip.cpp'
    assert [n for n in source['files'] if source['files'][n] != initial['files'][n]] == [rel]
    old_report_path = ROOT / 'config/q2-producer-q8-static.json'
    old_report = json.loads(old_report_path.read_text())
    assert old_report['source_manifest_sha256'] == previous.isa.sha(initial_manifest)
    assert old_report['original_kernels_instruction_operand_resource_exact'] == 162
    assert previous.isa.sha(ROOT / old_report['candidate_assembly_path']) == old_report['candidate_assembly_sha256']
    original = prepare.function((provider / (prepare.REL + 'mmq/mmq.hpp')).read_text(),
        'template <int mmq_x, int mmq_y>\nstatic __device__ __forceinline__ void vec_dot_q2_K_q8_1_mma(')
    current_text = (provider / rel).read_text()
    start = current_text.index('template<int mmq_x, int mmq_y>')
    current = prepare.function(current_text[start:], 'template<int mmq_x, int mmq_y>')
    current = current.replace('ProducerQ8Dot', 'vec_dot_q2_K_q8_1_mma')
    current = current.replace('#pragma unroll 1', '')
    assert tokens(original) == tokens(current), 'Dot arithmetic tokens changed'
    down_path = OUT / 'down-v2.s'
    down = previous.isa.parse(down_path)
    assert len(down) == 6 and all('Q2ProducerQ8DownKernel' in s for s in down)
    assert all(v['resources']['private_segment_fixed_size'] == 0 for v in down.values())
    commands = {n: json.loads((OUT / (n + '-command.json')).read_text()) for n in (
        'bounded-preparation', 'down-v2', 'fixture-host', 'fixture-device',
        'reference-host', 'reference-device')}
    assert all(c['exit_code'] == 0 for c in commands.values())
    report = dict(schema='synapse-lie.q2-producer-q8-bounded-static.v1',
        source_manifest_sha256=previous.isa.sha(manifest), provider_files=len(source['files']),
        parent_recompiled=False, original_kernels_instruction_operand_resource_exact=162,
        initial_static_report_sha256=previous.isa.sha(old_report_path),
        producer_assembly_sha256=old_report['candidate_assembly_sha256'],
        down_assembly_path=str(down_path.relative_to(ROOT)), down_assembly_sha256=previous.isa.sha(down_path),
        original_dot_arithmetic_tokens_exact=True, added_down_kernels=down,
        commands=commands, gpu_run=False, model_inference=False,
        quality_accepted=False, goal_met=False)
    with (ROOT / 'config/q2-producer-q8-bounded-static.json').open('x') as f:
        json.dump(report, f, indent=2)
        f.write('\n')
    print(json.dumps(dict(original_kernels_exact=162, dot_arithmetic_tokens_exact=True,
        down_kernels=6, private_bytes=0, gpu_run=False)))


if __name__ == '__main__':
    main()
