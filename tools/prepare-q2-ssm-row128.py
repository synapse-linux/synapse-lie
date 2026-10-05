#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare one SSM row-tile candidate from the saved compact IQ2 provider."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
spec = importlib.util.spec_from_file_location('prepare', ROOT / 'tools/prepare-q2-q8-halfpair.py')
prepare = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prepare)
sha, inventory, once = prepare.sha, prepare.inventory, prepare.once


def main():
    parent_path = ROOT / 'config/q2-iq2-halfbyte-perm-formatted-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-halfbyte-perm']
    base = ROOT / parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured parent inventory changed')
    original = (base / REL).read_text()
    changed = once(original,
        'constexpr int kTransposeChunks = 8 * 16 * 36 * sizeof(float) / sizeof(uint4);',
        '''// SPDX-License-Identifier: MIT
  // The smaller SSM row stage still needs all eight 32-token epilogue planes.
  constexpr int kTransposeChunks =
      8 * (kSsmConv ? 32 : 16) * 36 * sizeof(float) / sizeof(uint4);''')
    changed = once(changed,
        '''          static_assert(BM == 256 && BN == 128 && BK == 2 && WM == 8 &&
                        WN == 1);''',
        '''          static_assert(BM == 128 && BN == 128 && BK == 2 && WM == 4 &&
                        WN == 2);''')
    changed = once(changed,
        '''hipLaunchKernelGGL((DenseF16GEMMKernel<256, 128, 2, 8, 1, 1, false, true>),
                     dim3((n_tokens + 127) / 128, m / 256), dim3(kThreads), 0,''',
        '''hipLaunchKernelGGL((DenseF16GEMMKernel<128, 128, 2, 4, 2, 1, false, true>),
                     dim3((n_tokens + 127) / 128, m / 128), dim3(kThreads), 0,''')
    source = ROOT / '.deps/gufo-q2-ssm-row128-run'
    patch = ROOT / 'experiments/q2-ssm-row128.patch'
    manifest = ROOT / 'config/q2-ssm-row128-source.json'
    if any(p.exists() for p in (source, patch, manifest)):
        raise ValueError('Refusing to overwrite a retained candidate')
    result = subprocess.run(['/opt/rocm/llvm/bin/clang-format',
        '--style=file:' + str(base / '.clang-format'), '--assume-filename=' + str(base / REL)],
        input=changed, capture_output=True, text=True)
    if result.returncode:
        raise ValueError('Formatting failed: ' + result.stderr)
    changed = result.stdout
    shutil.copytree(base, source)
    (source / REL).write_text(changed)
    files = inventory(source)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    if len(files) != 1025 or delta != [REL]:
        raise ValueError('Unexpected provider delta')
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        stream.write(''.join(difflib.unified_diff(original.splitlines(True), changed.splitlines(True),
            fromfile='a/' + REL, tofile='b/' + REL)))
    variant = dict(source=str(source.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-iq2-halfbyte-model-results.json',
        measured_parent_sha256=sha(ROOT / 'config/q2-iq2-halfbyte-model-results.json'),
        control_include='experiments/q2-q8-grouped-control.inc',
        control_include_sha256=sha(ROOT / 'experiments/q2-q8-grouped-control.inc'),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        parent_geometry=dict(BM=256, BN=128, BK=2, WM=8, WN=1, accumulators_per_lane=128, lds_bytes=49152),
        candidate_geometry=dict(BM=128, BN=128, BK=2, WM=4, WN=2, accumulators_per_lane=64, lds_bytes=36864),
        affected='DenseF16SsmGemm projection specialization only; minimum1024, dimensions16384x2560 and convolution10240x4 unchanged.',
        numerical_contract='Original signed Q8 F16 construction/scale/FMA and sequential K16 WMMA; identical32-token fused/boundary convolution and live raw-output mask.',
        risks='Two row blocks instead of one duplicate activation reads and block overhead; lower accumulator/LDS pressure does not imply a speedup.',
        additional_runtime_allocations=0, additional_streams=0, table_device_bytes=0,
        full_model_measured=False, numerical_acceptance=False, gpu_run=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-ssm-row128-source.v1', variants={'ssm-row128': variant},
                       gpu_run=False, goal_met=False), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(provider_files=len(files), changed_files=delta,
                         accumulators_per_lane=[128, 64], lds_bytes=[49152, 36864], gpu_run=False)))


if __name__ == '__main__':
    main()
