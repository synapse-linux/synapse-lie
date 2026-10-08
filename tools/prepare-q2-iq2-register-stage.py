#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Keep the wide IQ2 weight stage inside its existing producer/consumer wave."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
PREFIX = 'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,'
spec = importlib.util.spec_from_file_location('prior', ROOT/'tools/prepare-q2-iq2-four-wave.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sha, inventory, once, function = prior.sha, prior.inventory, prior.once, prior.function


def ownership():
    """Enumerate logical stage ownership, not arithmetic or device behavior."""
    old, new, reads = {}, {}, set()
    private = True
    for tid in range(256):
        wave, lane = divmod(tid, 32)
        for owner in range(4):
            peer = (tid & ~3) + owner
            part = lane & 3
            key = (peer // 2, peer % 2, part)
            assert key not in old
            old[key] = wave
        row, kb = wave * 16 + lane % 16, lane // 16
        for part in range(4):
            key = (row, kb, part)
            assert key not in new
            new[key] = wave
    assert old == new and len(old) == 1024
    for wave in range(8):
        for lane in range(32):
            row = wave * 16 + lane % 16
            for kb in range(2):
                source_lane = lane if lane // 16 == kb else lane ^ 16
                assert source_lane % 16 == lane % 16 and source_lane // 16 == kb
                for word in range(8):
                    key = (row, kb, word // 2)
                    private &= old[key] == new[key] == wave
                    reads.add((wave, lane, kb, word))
    assert private and len(reads) == 4096
    fetch_before = {(tid // 2, tid % 2) for tid in range(256)}
    fetch_after = {(tid // 32 * 16 + tid % 16, tid % 32 // 16) for tid in range(256)}
    assert fetch_before == fetch_after and len(fetch_before) == 256
    return dict(weight_group_fetches_unchanged=256, eight_byte_groups=1024,
                weight_stage_producers_and_readers_wave_private=True,
                consumer_word_reads=4096, scale_groups=256,
                shared_weight_code_bytes_removed=8192,
                shared_weight_scale_bytes_removed=1024,
                activation_bytes_unchanged=16512,
                expected_stage_lds_bytes=[25728, 16512],
                waves_per_block_unchanged=8, accumulators_per_lane_unchanged=64,
                block_barriers_and_wmma_order_unchanged=True,
                logical_ownership_only=True, numerical_equivalence_established=False)


def main():
    parent_path = ROOT/'config/q2-ssm-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    base = ROOT/parent['source']
    assert inventory(base) == parent['files']
    original = (base/REL).read_text()
    kernel = function(original, PREFIX)
    changed = once(kernel,
        '         bool kPacked = false, bool kScaled = false>',
        '         bool kPacked = false, bool kScaled = false, bool kRegisterIQ2 = false>')
    changed = once(changed,
        '  constexpr bool kIQ2 = kType == WeightType::kIQ2_XXS;',
        '  constexpr bool kIQ2 = kType == WeightType::kIQ2_XXS;\n'
        '  static_assert(!kRegisterIQ2 || (kIQ2 && kPair && !kPacked && BN == 128));')
    changed = once(changed, '  constexpr int kCodeBytes = BM * kChunks * 16;',
        '  constexpr int kCodeBytes = kRegisterIQ2 ? 0 : BM * kChunks * 16;')
    changed = once(changed, '  constexpr int kScaleBytes = (kQ2 ? 4 : 1) * BK * BM * 4;',
        '  constexpr int kScaleBytes = kRegisterIQ2 ? 0 : (kQ2 ? 4 : 1) * BK * BM * 4;')
    changed = once(changed, '  const int f_c = tid & 1;',
        '  const int f_c = kRegisterIQ2 ? half_id : (tid & 1);\n'
        '  const int f_row = kRegisterIQ2 ? wave_id * 16 + sub_lane : (tid >> 1);')
    changed = once(changed,
        '        r_block + (kPair ? (tid >> 1) % kRows : (tid >> 1) + (u * 128));',
        '        r_block + (kPair ? f_row % kRows : f_row + (u * 128));')
    changed = once(changed, '      if ((tid >> 1) >= kRows) {',
        '      if (f_row >= kRows) {')
    changed = once(changed, '  __half f_iq2_d[kWaveRowTiles];',
        '  __half f_iq2_d[kWaveRowTiles];\n'
        '  std::uint32_t iq2_stage_codes[kWaveRowTiles][8];\n'
        '  std::uint32_t iq2_stage_scale[kWaveRowTiles];')
    commit = '''      if constexpr (kRegisterIQ2) {
        // SPDX-License-Identifier: MIT
        // The two half-waves own the two K32 groups of the same16 rows.
        // Decode once into registers; the matrix reader stays in this wave.
        const uint2 group = f_iq2_group[u];
        const __half d = f_iq2_d[u];
#pragma unroll
        for (int part = 0; part < 4; ++part) {
          const unsigned code = (group.x >> (8 * part)) & 255U;
          const unsigned sign = (group.y >> (7 * part)) & 127U;
          const uint2 magnitude =
              reinterpret_cast<const uint2*>(kIq2HalfHighGrid)[code];
          const uint2 mask = reinterpret_cast<const uint2*>(ksigns64)[sign];
          iq2_stage_codes[u][2 * part] = magnitude.x ^ (mask.x & 0x80808080U);
          iq2_stage_codes[u][2 * part + 1] = magnitude.y ^ (mask.y & 0x80808080U);
        }
        const float scale =
            __half2float(d) * float(2 * (group.y >> 28) + 1) * 0.125F;
        const std::uint32_t dm =
            __builtin_bit_cast(std::uint16_t, __float2half_rn(scale));
        iq2_stage_scale[u] = f_live[u] ? dm : 0U;
      } else if constexpr (kIQ2) {'''
    start = changed.index('  const auto commit_stage = [&]() {')
    changed = changed[:start] + once(changed[start:], '      if constexpr (kIQ2) {', commit)
    changed = once(changed, '      if constexpr (!kQ2)\n        s_scale',
        '      if constexpr (!kQ2 && !kRegisterIQ2)\n        s_scale')
    changed = once(changed, '  const auto compute_stage = [&]() {', '''  const auto register_word = [half_id](std::uint32_t own, int kb) {
    const auto peer = __builtin_amdgcn_permlanex16(
        own, own, 0x76543210U, 0xFEDCBA98U, false, false);
    return half_id == kb ? own : peer;
  };
  const auto compute_stage = [&]() {''')
    changed = once(changed,
        '                : __builtin_bit_cast(__half2, s_scale[(kb * BM) + row]);',
        '                : __builtin_bit_cast(__half2, kRegisterIQ2\n'
        '                      ? register_word(iq2_stage_scale[u], kb)\n'
        '                      : s_scale[(kb * BM) + row]);')
    changed = once(changed, '        if constexpr (kSigned || kQ2) {',
        '        if constexpr (kRegisterIQ2) {\n'
        '#pragma unroll\n'
        '          for (int i = 0; i < 8; ++i)\n'
        '            nib[i] = register_word(iq2_stage_codes[u][i], kb);\n'
        '        } else if constexpr (kSigned || kQ2) {')
    candidate = once(original, kernel, changed)
    candidate = once(candidate,
        '      (RoutedF16GEMMKernel<WeightType::kIQ2_XXS, 128, BN, 2, true, kPacked>),',
        '      (RoutedF16GEMMKernel<WeightType::kIQ2_XXS, 128, BN, 2, true, kPacked,\n'
        '                           false, BN == 128 && !kPacked>),')
    out = ROOT/'.deps/gufo-q2-iq2-register-stage-run'
    manifest = ROOT/'config/q2-iq2-register-stage-source.json'
    patch = ROOT/'experiments/q2-iq2-register-stage.patch'
    control = ROOT/'experiments/q2-iq2-register-stage-control.inc'
    if any(p.exists() for p in (out, manifest, patch, control)):
        raise ValueError('Refusing to overwrite experiment')
    proof = ownership()
    shutil.copytree(base, out)
    (out/REL).write_text(candidate)
    control.write_text('// SPDX-License-Identifier: MIT\n'
        '// Literal retained1585 kernel; only its private function name changes.\n'
        + kernel.replace('RoutedF16GEMMKernel', 'RoutedIq2RegisterStageControlKernel') + '\n')
    patch.write_text('// SPDX-License-Identifier: MIT\n' + ''.join(difflib.unified_diff(
        original.splitlines(True), candidate.splitlines(True), fromfile='a/'+REL, tofile='b/'+REL)))
    files = inventory(out)
    delta = [name for name in files if files[name] != parent['files'].get(name)]
    assert len(files) == 1027 and delta == [REL]
    variant = dict(source=str(out.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-ssm-fixed-bounds-model-results.json',
        measured_parent_sha256=sha(ROOT/'config/q2-ssm-fixed-bounds-model-results.json'),
        control_include=str(control.relative_to(ROOT)), control_include_sha256=sha(control),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        generator=str(Path(__file__).relative_to(ROOT)), generator_sha256=sha(Path(__file__)),
        mechanism='Nonpacked IQ2 BN128 only: replace wave-private code/scale LDS staging with registers and cross-half-wave exchange; same grid, eight waves, accumulators and activation stage.',
        numerical_contract='Original table/sign bits, rounded scale, half FMA, K16 WMMA order and anchored F32 SwiGLU epilogue retained. Compiled/runtime equivalence unproven.',
        unchanged='BN16/48/64, packed IQ2, Q2 down, dense, decode, descriptors, allocations and stream scheduling; assembly identity still requires verification.',
        symbolic_ownership=proof, additional_runtime_allocations=0,
        risks='Registers or exchange instructions can outweigh removed LDS work. Stage ownership is a symbolic proof only; no device safety/performance/quality acceptance.',
        gpu_run=False, full_model_measured=False, numerical_acceptance=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-register-stage-source.v1',
                       variants={'iq2-register-stage':variant}), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(files=len(files), changed_files=delta, symbolic_ownership=proof)))


if __name__ == '__main__':
    main()
