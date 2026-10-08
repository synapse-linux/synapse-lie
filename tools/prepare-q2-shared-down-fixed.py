#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Add fixed-shape Q8/F16 shared-down arms to separate indexing from caching."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssm', ROOT / 'tools/prepare-q2-ssm-row-group.py')
ssm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ssm)


def main():
    previous_path = ROOT / 'config/q2-shared-down-mirror-source.json'
    previous = json.loads(previous_path.read_text())['variants']['shared-down-mirror']
    base = ROOT / previous['source']
    assert ssm.inventory(base) == previous['files']
    rel = str(Path(ssm.REL).parent / 'q2_shared_down_mirror.inc')
    original = (base / rel).read_text()
    body = ssm.function(original, 'template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    changed = body.replace('SharedDownMirrorKernel', 'SharedDownFixedKernel')
    changed = ssm.once(changed,
        'float* __restrict__ y, std::size_t batch, std::size_t m, std::size_t k,',
        'float* __restrict__ y, std::size_t batch, std::size_t runtime_m, std::size_t runtime_k,')
    changed = ssm.once(changed, '    AttentionProjectionOutput attention = {}) {\n',
        '    AttentionProjectionOutput attention = {}) {\n'
        '  static_assert(BM == 256 && BN == 128 && BK == 1 && WM == 4 && WN == 2);\n'
        '  static_assert(kRowGroup == 1 && !kHcMix && !kSsmConv && !kAttention && !kHcUpChains);\n'
        '  constexpr std::size_t m = 2560, k = 640;\n')
    changed = ssm.once(changed, '    a_live[p] = idx < kAUnits && r < m_i;',
                       '    a_live[p] = true; // The wrapper launches ten complete256-row blocks.')
    changed = ssm.once(changed, '      const bool live = a_live[p] && kb < num_kb;',
                       '      const bool live = true; // BK1 traverses exactly twenty K32 blocks.')
    changed = ssm.once(changed, '      if (b_ptr[p] != nullptr && kb < num_kb) {',
                       '      if (b_ptr[p] != nullptr) {')
    old_epilogue = '''          if (tok < batch && r0 + 32 <= m && ((tok * m) % 4 == 0)) {
            auto* dst = reinterpret_cast<float4*>(
                y + (tok * m) + r0 + static_cast<std::size_t>(row_l));
#pragma unroll
            for (int q = 0; q < 4; ++q) {
              dst[q] = src[q];
            }
          } else if (tok < batch) {
#pragma unroll
            for (int q = 0; q < 16; ++q) {
              const std::size_t r = r0 + static_cast<std::size_t>(row_l + q);
              if (r < m) {
                y[(tok * m) + r] =
                    tile_scratch[(tok_l * kOutputStride) + row_l + q];
              }
            }
          }'''
    new_epilogue = '''          // Full256-row blocks and M2560 guarantee every aligned float4 store.
          if (tok < batch) {
            auto* dst = reinterpret_cast<float4*>(
                y + (tok * m) + r0 + static_cast<std::size_t>(row_l));
#pragma unroll
            for (int q = 0; q < 4; ++q) dst[q] = src[q];
          }'''
    changed = ssm.once(changed, old_epilogue, new_epilogue)
    stores = 0
    for block in range(10):
        for wave in range(8):
            for i in (0, 2):
                for lane in range(32):
                    for v in range(4):
                        row = block * 256 + ((wave // 2) * 4 + i) * 16 + (lane & 1) * 16 + v * 4
                        assert row % 4 == 0 and row + 3 < 2560
                        stores += 1
    assert all(block * 256 + tid < 2560 for block in range(10) for tid in range(256))
    extra = '\n' + changed
    for half, suffix in ((False, 'Q8'), (True, 'F16')):
        extra += '''
bool SharedDownFixed%sGemm(const void* weights, const __half* x, float* out,
                           std::size_t batch, std::size_t m, std::size_t k,
                           hipStream_t stream) {
  if (batch < 96 || m != 2560 || k != 640 || weights == nullptr ||
      x == nullptr || out == nullptr) return false;
  hipLaunchKernelGGL(
      (SharedDownFixedKernel<256, 128, 1, 4, 2, 1, false, false, false, %s>),
      dim3((batch + 127) / 128, 10), dim3(256), 0, stream,
      weights, x, out, batch, m, k);
  return hipGetLastError() == hipSuccess;
}
''' % (suffix, str(half).lower())
    destination = ROOT / '.deps/gufo-q2-shared-down-fixed-run'
    manifest = ROOT / 'config/q2-shared-down-fixed-source.json'
    patch = ROOT / 'experiments/q2-shared-down-fixed.patch'
    assert not any(p.exists() for p in (destination, manifest, patch))
    shutil.copytree(base, destination)
    (destination / rel).write_text(original + extra)
    parent = json.loads((ROOT / previous['parent_manifest']).read_text())['variants']['down-register-scatter']
    files = ssm.inventory(destination)
    delta = [p for p in files if files[p] != parent['files'].get(p)]
    assert len(files) == 1028 and delta == previous['changed_files']
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        for name in delta:
            before = ROOT / parent['source'] / name
            stream.write(''.join(difflib.unified_diff(before.read_text().splitlines(True)
                if before.exists() else [], (destination / name).read_text().splitlines(True),
                fromfile='a/' + name if before.exists() else '/dev/null', tofile='b/' + name)))
    variant = dict(previous)
    variant.update(source=str(destination.relative_to(ROOT)), files=files,
        patch=str(patch.relative_to(ROOT)), patch_sha256=ssm.sha(patch),
        preceding_local_manifest=str(previous_path.relative_to(ROOT)), preceding_local_manifest_sha256=ssm.sha(previous_path),
        mechanism='Component-only four-arm comparison: original Q8, generic mirror, fixed-shape Q8, '
                  'fixed-shape mirror. Fixed arms expose M2560/K640 and full-row aligned stores; '
                  'token tails and original single K16 chain remain.',
        symbolic_bounds=dict(weight_fetch_owners=2560, k_blocks=20, float4_store_owners=stores,
                             token_tail_guards_retained=True),
        candidate_arms=['generic-f16', 'fixed-q8', 'fixed-f16'])
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-shared-down-fixed-source.v1',
                       variants={'shared-down-fixed': variant}, goal_met=False), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(provider_files=len(files), bounds=variant['symbolic_bounds'], gpu_run=False)))


if __name__ == '__main__':
    main()
