#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Pair IQ2 gate/up in four waves without widening the output block."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/kernels.hip.cpp'
PREFIX = 'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,'
spec = importlib.util.spec_from_file_location('wide', ROOT/'tools/prepare-q2-iq2-wide-pair.py')
wide = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wide)
sha, inventory, once = wide.sha, wide.inventory, wide.replace_once
function = wide.lane.prior.prior.literal.function


def ownership():
    """Enumerate fetch, LDS, WMMA row and epilogue ownership, without a GPU."""
    maps = {}
    for threads in (256, 128):
        fetch_rows = threads // 2
        units = 128 // fetch_rows
        weights, code, scales, activations, accumulators = {}, {}, {}, {}, {}
        for tid in range(threads):
            wave, lane = divmod(tid, 32)
            for unit in range(units):
                row = tid // 2 + unit * fetch_rows
                key = (row, tid % 2)
                assert key not in weights
                weights[key] = (row // 64, row % 64, tid % 2)
                scale = (tid % 2) * 128 + row
                assert scale not in scales
                scales[scale] = key
                part = lane % 4
                for owner in range(4):
                    peer = (tid & ~3) + owner
                    peer_row = peer // 2 + unit * fetch_rows
                    chunk = 2 * (peer % 2) + part // 2
                    slot = (peer_row * 4 + (chunk ^ ((peer_row >> 1) & 3))) * 2 + part % 2
                    assert slot not in code
                    code[slot] = (peer_row, peer % 2, part)
                # Duplicate WMMA A lanes are intentional; output lanes are unique.
                for token_tile in range(4):
                    for value in range(8):
                        key = (wave * 16 + unit * fetch_rows,
                               token_tile * 16 + lane % 16,
                               2 * value + lane // 16)
                        assert key not in accumulators
                        accumulators[key] = (key[0] // 64, key[0] % 64 + key[2], key[1])
            for index in range(512 // threads):
                chunk = tid + index * threads
                token, quarter = divmod(chunk, 8)
                slot = quarter * 65 + token
                assert slot not in activations
                activations[slot] = (token, quarter)
        assert len(weights) == 256 and len(code) == 1024 and len(scales) == 256
        assert len(activations) == 512 and len(accumulators) == 8192
        maps[threads] = (weights, code, scales, activations, accumulators)
    assert maps[256] == maps[128]
    # Gate and up now belong to the same wave, with independent scratch planes.
    scratch, outputs = set(), set()
    for wave in range(4):
        for lane in range(32):
            for value in range(8):
                slot = wave * 288 + (lane % 16) * 18 + 2 * value + lane // 16
                assert slot not in scratch
                scratch.add(slot)
            for unit in range(4):
                flat = (unit * 32 + lane) * 2
                for component in range(2):
                    token, row = flat // 16, wave * 16 + flat % 16 + component
                    assert (token, row) not in outputs
                    outputs.add((token, row))
                    slot = wave * 288 + token * 18 + flat % 16 + component
                    assert wave * 288 <= slot < (wave + 1) * 288
    assert len(outputs) == 1024 and len(scratch) == 1024
    for token, row in outputs:
        assert (row // 16) * 288 + token * 18 + row % 16 in scratch
    guarded = 0
    for m in (1, 63, 64, 65, 127, 128, 129, 639, 640):
        for n in (1, 15, 16, 17, 49, 63, 64):
            actual = {(token, start + row) for start in range(0, m, 64)
                      for j in range(4) for t, row in outputs
                      if (token := j * 16 + t) < n and start + row < m}
            assert actual == {(t, r) for t in range(n) for r in range(m)}
            guarded += 1
    return dict(weight_group_owners=256, compact_eight_byte_owners=1024,
                scale_owners=256, activation_chunk_owners=512,
                accumulator_owners=8192, wave_scratch_owners=1024,
                complete_ragged_output_shapes=guarded, block_threads=[256, 128],
                logical_output_rows=[64, 64], stage_lds_bytes=[17536, 17536],
                global_activation_payload_bytes_per_stage=[8192, 8192],
                activation_fragment_loads_per_stage_full_tile=[256, 128],
                k_stage_block_barriers_preserved=True,
                numerical_equivalence_established=False)


def main():
    parent_path = ROOT/'config/q2-ssm-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    base = ROOT/parent['source']
    assert inventory(base) == parent['files']
    original = (base/REL).read_text()
    kernel = function(original, PREFIX)
    changed = once(kernel,
        '         bool kPacked = false, bool kScaled = false>\n__launch_bounds__(256)',
        '         bool kPacked = false, bool kScaled = false, bool kFourWave = false>\n'
        '__launch_bounds__(kFourWave ? 128 : 256)')
    changed = once(changed,
        '  constexpr int kWaveRowTiles = BM / 128;  // 16-row tiles per wave',
        '  constexpr int kBlockThreads = kFourWave ? 128 : 256;\n'
        '  constexpr int kFetchRows = kBlockThreads / 2;\n'
        '  constexpr int kWaveRowTiles = BM / kFetchRows;  // 16-row tiles per wave')
    changed = once(changed,
        '  constexpr bool kIQ2 = kType == WeightType::kIQ2_XXS;',
        '  constexpr bool kIQ2 = kType == WeightType::kIQ2_XXS;\n'
        '  static_assert(!kFourWave || (kIQ2 && kPair && !kPacked && BM == 128 && BN == 64));')
    changed = once(changed,
        '        r_block + (kPair ? (tid >> 1) % kRows : (tid >> 1) + (u * 128));',
        '        r_block + (kPair ? ((tid >> 1) + u * kFetchRows) % kRows\n'
        '                         : (tid >> 1) + u * kFetchRows);')
    changed = once(changed, '      if ((tid >> 1) >= kRows) {',
        '      if ((tid >> 1) + u * kFetchRows >= kRows) {')
    assert changed.count('(u * 128)') == 5
    changed = changed.replace('(u * 128)', '(u * kFetchRows)')
    changed = once(changed, '  constexpr int kActFetch = BN <= 64 ? 2 : 4;',
        '  constexpr int kActFetch = kFourWave ? 4 : (BN <= 64 ? 2 : 4);')
    changed = once(changed, '  static_assert(kActChunks <= kActFetch * 256);',
        '  static_assert(kActChunks <= kActFetch * kBlockThreads);')
    changed = once(changed, '    const int chunk = tid + (i * 256);',
        '    const int chunk = tid + (i * kBlockThreads);')
    changed = changed.replace('"eight waves, 16-row tiles"', '"16-row wave tiles"')
    changed = changed.replace('row = tid / 2 + 128 u', 'row = tid / 2 + kFetchRows u')
    changed = changed.replace('each thread fetches consecutive 256-chunk\n  // strides, up to four for a 128-token tile.',
        'each thread fetches kBlockThreads-chunk\n  // strides. Four-wave BN64 uses four fetches per thread.')
    # Reuse the already-reviewed wave-local transpose expression, not its BM256 geometry.
    wide_source = (ROOT/'tools/prepare-q2-iq2-wide-pair.py').read_text()
    epilogue = wide_source.split("    epilogue = '''", 1)[1].split("'''", 1)[0]
    epilogue = epilogue.replace('kPair && BM == 256', 'kFourWave').replace(
        'static_assert(8 * plane * sizeof(float)', 'static_assert(4 * plane * sizeof(float)')
    changed = once(changed,
        '  if constexpr (kPair) {\n    // Four waves compute gate rows and four compute the matching up rows.',
        epilogue + '  if constexpr (kPair) {\n    // Four waves compute gate rows and four compute the matching up rows.')
    candidate = once(original, kernel, changed)
    old_launch = '''  const dim3 grid(static_cast<unsigned>((m + 63) / 64), n_tiles);
  hipLaunchKernelGGL(
      (RoutedF16GEMMKernel<WeightType::kIQ2_XXS, 128, BN, 2, true, kPacked>),
      grid, dim3(kThreads), 0, stream, gate, x, tiles, bounds, rows_token,'''
    new_launch = '''  constexpr bool kFourWave = BN == 64 && !kPacked;
  const dim3 grid(static_cast<unsigned>((m + 63) / 64), n_tiles);
  hipLaunchKernelGGL(
      (RoutedF16GEMMKernel<WeightType::kIQ2_XXS, 128, BN, 2, true, kPacked,
                           false, kFourWave>),
      grid, dim3(kFourWave ? 128 : kThreads), 0, stream, gate, x, tiles, bounds, rows_token,'''
    candidate = once(candidate, old_launch, new_launch)
    out = ROOT/'.deps/gufo-q2-iq2-four-wave-run'
    manifest = ROOT/'config/q2-iq2-four-wave-source.json'
    patch = ROOT/'experiments/q2-iq2-four-wave.patch'
    control = ROOT/'experiments/q2-iq2-four-wave-control.inc'
    if any(p.exists() for p in (out, manifest, patch, control)):
        raise ValueError('Refusing to overwrite experiment')
    proof = ownership()
    shutil.copytree(base, out)
    (out/REL).write_text(candidate)
    control.write_text('// SPDX-License-Identifier: MIT\n'
        '// Literal retained1585 IQ2 kernel; only its private function name changes.\n'
        + kernel.replace('RoutedF16GEMMKernel', 'RoutedIq2FourWaveControlKernel') + '\n')
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
        generator='tools/prepare-q2-iq2-four-wave.py', generator_sha256=sha(Path(__file__)),
        epilogue_reference='tools/prepare-q2-iq2-wide-pair.py',
        epilogue_reference_sha256=sha(ROOT/'tools/prepare-q2-iq2-wide-pair.py'),
        mechanism='Nonpacked IQ2 BN64: four waves share B fragments across gate/up; same BM128, logical64-row grid and LDS, wave-local final transpose.',
        numerical_contract='Retained raw groups, signed half bytes, rounded scales, ordered WMMA per dot and explicit original F32 SwiGLU product/value boundaries.',
        unchanged='BN16/48/128, packed IQ2, Q2 down, dense, vector decode, routing and allocations; static assembly comparison pending.',
        symbolic_ownership=proof, additional_runtime_allocations=0,
        risks='More per-thread accumulators and prefetch may reduce occupancy; static ownership is not GPU safety or numerical qualification.',
        gpu_run=False, full_model_measured=False, numerical_acceptance=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-iq2-four-wave-source.v1',
                       variants={'iq2-four-wave':variant}), stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(files=len(files), changed_files=delta, symbolic_ownership=proof)))


if __name__ == '__main__':
    main()
