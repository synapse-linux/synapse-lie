#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Retain the first Q8 chain and bound the integer dot loop's live registers."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('initial', ROOT / 'tools/prepare-q2-producer-q8.py')
initial = importlib.util.module_from_spec(spec)
spec.loader.exec_module(initial)


def main():
    old_manifest = ROOT / 'config/q2-producer-q8-source.json'
    source = json.loads(old_manifest.read_text())['variants']['producer-q8']
    before = ROOT / source['source']
    assert initial.inventory(before) == source['files']
    out = ROOT / '.deps/gufo-q2-producer-q8-bounded-run'
    manifest = ROOT / 'config/q2-producer-q8-source-v2.json'
    patch = ROOT / 'experiments/q2-producer-q8-bounded.patch'
    assert not any(p.exists() for p in (out, manifest, patch))
    rel = initial.REL + 'mmq/q2_producer_q8.hip.cpp'
    helper = initial.function((before / (initial.REL + 'mmq/mmq.hpp')).read_text(),
        'template <int mmq_x, int mmq_y>\nstatic __device__ __forceinline__ void vec_dot_q2_K_q8_1_mma(')
    helper = helper.replace('vec_dot_q2_K_q8_1_mma', 'ProducerQ8Dot')
    helper = initial.once(helper, '    for (int k01 = 0;',
        '    #pragma unroll 1\n    for (int k01 = 0;')
    value = (before / rel).read_text()
    value = initial.once(value, '__global__ void Q2ProducerQ8DownKernel(',
        '__global__ __launch_bounds__(128, 2) void Q2ProducerQ8DownKernel(')
    value = initial.once(value, '  for (int kb = 0;',
        '  #pragma unroll 1\n  for (int kb = 0;')
    value = initial.once(value, '#include "mmq.hpp"', '#include "mmq.hpp"\n' + helper)
    value = value.replace('vec_dot_q2_K_q8_1_mma<BN, BM>', 'ProducerQ8Dot<BN, BM>')
    value = subprocess.run(['/opt/rocm/llvm/bin/clang-format', '--sort-includes=false',
        '--assume-filename=' + str(before / rel)], input=value, text=True,
        capture_output=True, check=True).stdout
    shutil.copytree(before, out)
    (out / rel).write_text(value)
    files = initial.inventory(out)
    assert [n for n in files if files[n] != source['files'][n]] == [rel]
    parent = json.loads((ROOT / source['parent_manifest']).read_text())['variants']['scaled-wave-pack']
    base = ROOT / parent['source']
    assert initial.inventory(base) == parent['files']
    diff = []
    for name in source['changed_files']:
        original = (base / name).read_text() if (base / name).exists() else ''
        diff.extend(difflib.unified_diff(original.splitlines(True),
            (out / name).read_text().splitlines(True), fromfile='a/' + name, tofile='b/' + name))
    patch.write_text('// SPDX-License-Identifier: MIT\n' + ''.join(diff))
    source.update(source=str(out.relative_to(ROOT)), files=files,
        patch=str(patch.relative_to(ROOT)), patch_sha256=initial.sha(patch),
        initial_source_manifest=str(old_manifest.relative_to(ROOT)),
        initial_source_manifest_sha256=initial.sha(old_manifest),
        scheduling_change='Keep ordered K loops rolled in a literal MMQ Q2 dot copy; bound CTA to128 threads. No arithmetic statement or order changed.',
        initial_source_preserved=True)
    manifest.write_text(json.dumps(dict(schema='synapse-lie.q2-producer-q8-source.v2',
        variants={'producer-q8': source}, gpu_run=False, goal_met=False), indent=2) + '\n')
    print(json.dumps(dict(files=len(files), initial_source_preserved=True, gpu_run=False)))


if __name__ == '__main__':
    main()
