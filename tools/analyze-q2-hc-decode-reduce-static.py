#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Audit scalar HC generated code; never interpret static counts as speedup."""
import collections
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'evidence/q2-hc-decode-reduce-static'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def kernel(path, name):
    text = path.read_text()
    symbol = next(line.split(':')[0] for line in text.splitlines()
                  if line.startswith('_Z') and name in line and ': ;' in line)
    start = text.index(symbol + ':')
    end = text.index('\n\t.section\t.rodata', start)
    body = text[start:end]
    metadata = text[end:text.index('\n\t.end_amdhsa_kernel', end)]
    resources = {key:int(re.search(r'\.amdhsa_' + key + r' (\d+)', metadata)[1]) for key in
                 ('group_segment_fixed_size', 'private_segment_fixed_size',
                  'wavefront_size32', 'next_free_vgpr', 'next_free_sgpr')}
    mnemonics = re.findall(r'^\t([a-z][a-z_0-9]+)(?:\s|$)', body, re.M)
    counts = dict(sorted(collections.Counter(mnemonics).items()))
    fmas = [line.strip() for line in body.splitlines() if '\tv_fma_mix_f32 ' in line]
    loop = re.search(r'\.LBB\d+_1:.*?\n\ts_cbranch_execnz \.LBB\d+_1', body, re.S)[0]
    loop = re.sub(r'\.LBB\d+_', '.LBB_', loop)
    return body, loop, dict(symbol=symbol, resources=resources, static_assembly_instructions=len(mnemonics),
        mnemonics=counts, fma_sequence=fmas, body_sha256=hashlib.sha256(body.encode()).hexdigest(),
        loop_sha256=hashlib.sha256(loop.encode()).hexdigest())


def main():
    source = json.loads((ROOT / 'config/q2-hc-decode-reduce-source.json').read_text())
    commands = json.loads((ROOT / 'config/q2-hc-decode-reduce-static-commands.json').read_text())
    for name, digest in commands['input_hashes'].items():
        assert sha(ROOT / name) == digest
    for row in commands['checks']:
        if 'assembly_sha256' in row:
            assert row['exit_code'] == 0
            assert sha(ROOT / row['argv'][-1]) == row['assembly_sha256']
    base, candidate = (ROOT / source[k] for k in ('base', 'candidate'))
    actual = {str(p.relative_to(candidate)):sha(p) for p in candidate.rglob('*') if p.is_file()}
    assert actual == source['source_file_hashes']
    original, original_loop, ref = kernel(EVIDENCE/'reference.s', 'HcDownF16VecKernel')
    preserved, preserved_loop, control = kernel(EVIDENCE/'candidate.s', 'HcDownF16VecKernel')
    changed, changed_loop, cand = kernel(EVIDENCE/'candidate.s', 'HcDownF16ReduceKernel')
    assert original == preserved and original_loop == preserved_loop == changed_loop
    assert ref['resources'] == control['resources'] == cand['resources']
    assert cand['resources']['wavefront_size32'] == 1
    assert ref['fma_sequence'] == cand['fma_sequence']
    assert ref['mnemonics']['ds_bpermute_b32'] == 10
    assert cand['mnemonics'].get('ds_bpermute_b32', 0) == 0
    assert cand['mnemonics']['ds_swizzle_b32'] == 2
    assert ref['mnemonics']['global_load_b64'] == cand['mnemonics']['global_load_b64'] == 1
    assert ref['mnemonics']['global_load_b128'] == cand['mnemonics']['global_load_b128'] == 1
    assert ref['mnemonics']['s_barrier'] == cand['mnemonics']['s_barrier'] == 1
    assert ref['mnemonics']['buffer_gl0_inv'] == cand['mnemonics']['buffer_gl0_inv'] == 1
    assert re.findall(r'row_xmask:(\d+)', changed) == ['8','4','2','1']*2
    reconstructed = ROOT / '.deps/gufo-q2-bench-hc-decode-reduce-reconstructed'
    checks = []
    if not reconstructed.exists():
        shutil.copytree(base, reconstructed)
        argv = ['patch', '--batch', '--fuzz=0', '-p1', '-i', str(ROOT/'experiments/q2-hc-decode-reduce.patch')]
        result = subprocess.run(argv, cwd=reconstructed, capture_output=True, text=True)
        (EVIDENCE/'reconstruct.log').write_text(result.stdout+result.stderr)
        checks.append(dict(argv=argv, exit_code=result.returncode))
        result.check_returncode()
    assert {str(p.relative_to(reconstructed)):sha(p) for p in reconstructed.rglob('*') if p.is_file()} == actual
    report = dict(scope='Editing-host source/device-only assembly checks, no runtime or GPU execution',
        previous_goal_turn='Progress: e6f425e corrected the benchmark and measured fresh Q2/UD baseline replay',
        reference=ref, preserved_control=control, candidate=cand,
        source_reconstruction_exact=True, source_files_reconstructed=len(actual),
        preserved_control_assembly_exact=True, multiply_load_loop_exact=True,
        assembly={name:sha(EVIDENCE/name) for name in ('reference.s','candidate.s')},
        checks=checks,
        compilation=commands,
        hypothesis='Use immediate XOR16 and four row-DPP additions in each HC down wave reduction. No dynamic memory-traffic or speedup conclusion follows from static counts.',
        runtime_tests='Pending .157 host cohort and paired component after core handover',
        numerical_pass=None, performance_pass=None, promoted=False, goal_met=False)
    (ROOT/'config/q2-hc-decode-reduce-static.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(dict(reference_instructions=ref['static_assembly_instructions'],
        candidate_instructions=cand['static_assembly_instructions'],resources=cand['resources'],
        source_files_reconstructed=len(actual), preserved_control_assembly_exact=True,
        multiply_load_loop_exact=True),indent=2))


if __name__ == '__main__':
    main()
