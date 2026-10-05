#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Place scaled half activations in the existing padded expert-row order."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/'
spec = importlib.util.spec_from_file_location('literal', ROOT/'tools/prepare-q2-iq2-halfstage.py')
literal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(literal)
sha, inventory, once, function = literal.sha, literal.inventory, literal.once, literal.function


def main():
    parent_path = ROOT/'config/q2-scaled-wave-pack-source.json'
    parent = json.loads(parent_path.read_text())['variants']['scaled-wave-pack']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Retained1574 provider changed')
    out = ROOT/'.deps/gufo-q2-scaled-expert-order-run'
    manifest = ROOT/'config/q2-scaled-expert-order-source.json'
    patch = ROOT/'experiments/q2-scaled-expert-order.patch'
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Refusing to overwrite an experiment')
    pack = function((base/(REL+'q2_scaled_input.inc')).read_text(),
                    '__global__ void PackQ2ScaledWaveRowsKernel(')
    pack = pack.replace('PackQ2ScaledWaveRowsKernel', 'PackQ2ExpertOrderKernel')
    pack = once(pack, 'float* inverse, std::uint32_t rows)',
                'float* inverse, const std::int32_t* slots, std::uint32_t rows)')
    pack = once(pack, '  const float* src = x + row * cols;', '''  const int slot = slots[row];
  if (slot < 0) {
    // Padded bucket rows may be staged by the existing WMMA consumer.
    // Write every half explicitly; no stale or poisoned padding reaches it.
    for (unsigned c = lane * 4; c < cols; c += 32 * 4)
      *reinterpret_cast<uint2*>(out + row * cols + c) = make_uint2(0u, 0u);
    return;
  }
  const float* src = x + std::size_t(slot) * cols;''')
    pack = once(pack, 'inverse[row] =', 'inverse[slot] =')
    pack_wrapper = '''bool PackQ2ExpertOrder(const float* x, __half* out, float* inverse,
                        const std::int32_t* slots, std::uint32_t rows,
                        hipStream_t stream) {
  if (!x || !out || !inverse || !slots || !rows ||
      reinterpret_cast<std::uintptr_t>(out) % 8 != 0)
    return false;
  hipLaunchKernelGGL(PackQ2ExpertOrderKernel, dim3((rows - 1) / 8 + 1),
                     dim3(256), 0, stream, x, out, inverse, slots, rows);
  return hipGetLastError() == hipSuccess;
}
'''
    half_source = (base/(REL+'q2_down_half_storage.inc')).read_text()
    kernel = function(half_source, 'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    kernel = kernel.replace('RoutedQ2HalfStorageKernel', 'RoutedQ2ExpertOrderKernel')
    kernel = once(kernel, '? rows_in[bucket_begin + c_row]', '? bucket_begin + c_row')
    launch = function(half_source, 'template<int BN>\nvoid LaunchRoutedQ2HalfStorage(')
    launch = launch.replace('LaunchRoutedQ2HalfStorage', 'LaunchRoutedQ2ExpertOrder')
    launch = launch.replace('RoutedQ2HalfStorageKernel', 'RoutedQ2ExpertOrderKernel')
    dispatch = function(half_source, 'bool RoutedQ2ScaledHalfGemm(')
    dispatch = dispatch.replace('RoutedQ2ScaledHalfGemm', 'RoutedQ2ExpertOrderGemm')
    dispatch = dispatch.replace('LaunchRoutedQ2HalfStorage', 'LaunchRoutedQ2ExpertOrder')
    include = ('// SPDX-License-Identifier: MIT\n'
        '// Retained scaled-half arithmetic; expert-ordered activation storage.\n'
        '// Original token-slot scale/output ordering and encoded weights remain.\n'
        + pack+'\n'+pack_wrapper+'\n'+kernel+'\n'+launch+'\n'+dispatch)
    changed = {'q2_scaled_expert_order.inc': include}
    original = {n:(base/(REL+n)).read_text()
                for n in ('kernels.hip.cpp', 'kernels.hpp', 'executor.cpp')}
    changed['kernels.hip.cpp'] = once(original['kernels.hip.cpp'],
        '#include "q2_down_half_storage.inc"',
        '#include "q2_down_half_storage.inc"\n#include "q2_scaled_expert_order.inc"')
    declarations = '\n// Private expert-ordered Q2 activation representation.\n'
    declarations += pack_wrapper[:pack_wrapper.index(' {')]+';\n'
    declarations += dispatch[:dispatch.index(' {')]+';\n'
    changed['kernels.hpp'] = once(original['kernels.hpp'],
        '}  // namespace gufo::models::qwen38_flash_next::rocm',
        declarations+'}  // namespace gufo::models::qwen38_flash_next::rocm')
    executor = once(original['executor.cpp'],
        '    auto* inverse = reinterpret_cast<float*>(\n'
        '        scaled + static_cast<std::size_t>(n_tokens) * used * c.expert_ff);',
        '''    const std::size_t ordered_rows = RoutedCompactRows(slots, c.num_experts);
    // The existing F32 up allocation owns both halves and slot-ordered scales.
    // Capacity is checked explicitly; other shapes retain the original layout.
    const bool ordered_down = compact_down &&
        ordered_rows * c.expert_ff * sizeof(__half) + slots * sizeof(float) <=
            std::size_t(slots) * c.expert_ff * sizeof(float);
    auto* inverse = reinterpret_cast<float*>(
        scaled + (ordered_down ? ordered_rows : slots) * c.expert_ff);''')
    executor = once(executor,
        '!PackQ2ScaledRows(s_.gate_e, scaled, inverse, n_tokens * used,\n'
        '                          c.expert_ff, stream_)',
        '''!(ordered_down
              ? PackQ2ExpertOrder(s_.gate_e, scaled, inverse, s_.rows_slot,
                                  ordered_rows, stream_)
              : PackQ2ScaledRows(s_.gate_e, scaled, inverse, n_tokens * used,
                                  c.expert_ff, stream_))''')
    executor = once(executor, '? RoutedQ2ScaledHalfGemm(',
                    '? (ordered_down ? RoutedQ2ExpertOrderGemm : RoutedQ2ScaledHalfGemm)(')
    changed['executor.cpp'] = executor
    shutil.copytree(base, out)
    patches = []
    for name, value in changed.items():
        value = subprocess.run(['/opt/rocm/llvm/bin/clang-format', '--sort-includes=false',
                                '--assume-filename='+str(base/(REL+name))],
                               input=value, text=True, capture_output=True, check=True).stdout
        old = (base/(REL+name)).read_text() if (base/(REL+name)).exists() else ''
        (out/(REL+name)).write_text(value)
        patches.extend(difflib.unified_diff(old.splitlines(True), value.splitlines(True),
                      fromfile='a/'+REL+name, tofile='b/'+REL+name))
    patch.write_text('// SPDX-License-Identifier: MIT\n'+''.join(patches))
    files = inventory(out)
    delta = [p for p in files if files[p] != parent['files'].get(p)]
    assert len(files) == 1028 and len(delta) == 4
    measured = ROOT/'config/q2-scaled-wave-pack-model-results.json'
    variant = dict(source=str(out.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)), measured_parent_sha256=sha(measured),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        mechanism='Gather slot-major F32 once during scaled packing; store padded expert-major F16 rows so down uses contiguous activation rows. Preserve slot-major inverse scales and outputs.',
        numerical_contract='Original full640-row maximum/scaling/RN half; unchanged Q2 weight decode, WMMA K order, scale restoration, RN half output and ordered consumer.',
        capacity_bytes_2048_top10_512=28160*640*2+20480*4,
        existing_up_capacity_bytes=20480*640*4,
        additional_allocations=0, additional_streams=0,
        risks='Gather cost moves into packing; padded zero rows add writes. Sorted rows do not prove cache/transaction savings. Full-cycle and model measurements are required.',
        independent_quality=False, gpu_run=False, goal_met=False)
    manifest.write_text(json.dumps(dict(schema='synapse-lie.q2-scaled-expert-order-source.v1',
        variants={'scaled-expert-order':variant}, gpu_run=False, goal_met=False), indent=2)+'\n')
    print(json.dumps(dict(provider_files=len(files), changed_files=delta, gpu_run=False)))


if __name__ == '__main__':
    main()
