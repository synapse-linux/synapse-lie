#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare compact expert-output storage from the measured 1511 Q2 provider."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
ROCM = 'src/models/qwen38_flash_next/kernels/rocm/'
spec = importlib.util.spec_from_file_location('literal', ROOT/'tools/prepare-q2-iq2-halfstage.py')
literal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(literal)
sha, inventory, once, function = literal.sha, literal.inventory, literal.once, literal.function


def main():
    parent_path = ROOT/'config/q2-iq2-live-compose-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-live-compose']
    base = ROOT/parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured source inventory changed')
    out = ROOT/'.deps/gufo-q2-down-half-storage-run'
    manifest = ROOT/'config/q2-down-half-storage-source.json'
    patch = ROOT/'experiments/q2-down-half-storage.patch'
    if any(p.exists() for p in (out, manifest, patch)):
        raise ValueError('Refusing to overwrite retained experiment')
    original = {name:(base/(ROCM+name)).read_text() for name in
                ('kernels.hip.cpp', 'kernels.hpp', 'executor.cpp', 'executor.hpp', 'batch.cpp',
                 'q2_scaled_input.inc', 'q2_hc_moe_deferred.inc')}
    kernel = function(original['kernels.hip.cpp'],
        'template<WeightType kType, int BM, int BN, int BK, bool kPair = false,')
    kernel = kernel.replace('RoutedF16GEMMKernel', 'RoutedQ2HalfStorageKernel')
    kernel = once(kernel, '  constexpr bool kResidual = kQ2 && !kScaled;',
        '  static_assert(kQ2 && kScaled && !kPair && !kPacked);\n'
        '  constexpr bool kResidual = kQ2 && !kScaled;')
    kernel = once(kernel,
        '              if constexpr (kScaled)\n'
        '                out[o] = v * static_cast<const float*>(w_up)[dst];\n'
        '              else\n'
        '                out[o] = v;',
        '              // Preserve the original F32 inverse-scale product,\n'
        '              // then introduce one explicit storage rounding.\n'
        '              float restored = v * static_cast<const float*>(w_up)[dst];\n'
        '              asm("" : "+v"(restored));\n'
        '              reinterpret_cast<__half*>(out)[o] = __float2half_rn(restored);')
    launch = function(original['q2_scaled_input.inc'], 'template<int BN>\nvoid LaunchRoutedQ2Scaled(')
    launch = launch.replace('LaunchRoutedQ2Scaled', 'LaunchRoutedQ2HalfStorage')
    launch = launch.replace('RoutedF16GEMMKernel', 'RoutedQ2HalfStorageKernel')
    launch = once(launch, 'float* out, std::size_t m', '__half* out, std::size_t m')
    launch = once(launch, 'slots, slots, nullptr, out, nullptr, m, k,',
                  'slots, slots, nullptr, reinterpret_cast<float*>(out), nullptr, m, k,')
    dispatch = function(original['q2_scaled_input.inc'], 'bool RoutedQ2ScaledGemm(')
    dispatch = dispatch.replace('RoutedQ2ScaledGemm', 'RoutedQ2ScaledHalfGemm')
    dispatch = dispatch.replace('LaunchRoutedQ2Scaled', 'LaunchRoutedQ2HalfStorage')
    dispatch = once(dispatch, 'float* out, std::size_t m', '__half* out, std::size_t m')
    combine = function(original['q2_hc_moe_deferred.inc'], '__global__ void HcCombineMoeDeferredNormKernel(')
    combine = combine.replace('HcCombineMoeDeferredNormKernel', 'HcCombineMoeHalfDeferredNormKernel')
    combine = once(combine, 'const float* expert_out', 'const __half* expert_out')
    combine = once(combine, '    const float* rows =', '    const __half* rows =')
    wrapper = function(original['q2_hc_moe_deferred.inc'], 'bool HcCombineMoeDeferredNorm(')
    wrapper = wrapper.replace('HcCombineMoeDeferredNorm', 'HcCombineMoeHalfDeferredNorm')
    wrapper = once(wrapper, 'const float* expert_out', 'const __half* expert_out')
    include = ('// SPDX-License-Identifier: MIT\n'
        '// Isolated experiment derived from the retained official Gufo provider.\n'
        '// Encoded weights and ordered F32 arithmetic stay intact; the down\n'
        '// result is explicitly rounded to F16 before the original combine.\n'
        '// Existing F32 specializations remain available as literal controls.\n\n'
        + kernel + '\n' + launch + '\n' + dispatch + '\n' + combine + '\n' + wrapper)
    changed = {'q2_down_half_storage.inc':include}
    changed['kernels.hip.cpp'] = once(original['kernels.hip.cpp'],
        '#include "q2_hc_moe_deferred.inc"',
        '#include "q2_hc_moe_deferred.inc"\n#include "q2_down_half_storage.inc"')
    declarations = '\n// Experimental F16 storage between Q2 down and ordered MoE combine.\n'
    declarations += dispatch[:dispatch.index(' {')] + ';\n'
    declarations += wrapper[:wrapper.index(' {')] + ';\n'
    changed['kernels.hpp'] = once(original['kernels.hpp'],
        '}  // namespace gufo::models::qwen38_flash_next::rocm',
        declarations+'}  // namespace gufo::models::qwen38_flash_next::rocm')
    executor = once(original['executor.cpp'],
        '  if (!RouteHints(n_tokens, error_msg, iq2_wmma)) {',
        '  // Only the measured wide Q2 path changes its transient storage.\n'
        '  // Reuse the existing F16-pending lifetime and keep F32 allocation capacity.\n'
        '  const bool compact_down = iq2_wmma && !wide_mixer_ &&\n'
        '      n_tokens == 2048 && c.hc_count == 4 && c.hc_low_rank == 320 &&\n'
        '      c.num_experts_used > 0 && c.num_experts_used <= 32 &&\n'
        '      out == s_.block_out;\n'
        '  if (!RouteHints(n_tokens, error_msg, iq2_wmma)) {')
    old = '''        !RoutedQ2ScaledGemm(l.ffn_down_exps.data, scaled, inverse,
                            s_.routed_tiles, routed_n_tiles_, routed_tile_rows_,
                            s_.routed_bounds, s_.rows_slot, s_.down_e,
                            c.hidden_size, c.expert_ff, stream_)) {'''
    new = '''        !(compact_down
          ? RoutedQ2ScaledHalfGemm(l.ffn_down_exps.data, scaled, inverse,
                s_.routed_tiles, routed_n_tiles_, routed_tile_rows_,
                s_.routed_bounds, s_.rows_slot,
                reinterpret_cast<__half*>(s_.down_e),
                c.hidden_size, c.expert_ff, stream_)
          : RoutedQ2ScaledGemm(l.ffn_down_exps.data, scaled, inverse,
                s_.routed_tiles, routed_n_tiles_, routed_tile_rows_,
                s_.routed_bounds, s_.rows_slot, s_.down_e,
                c.hidden_size, c.expert_ff, stream_))) {'''
    executor = once(executor, old, new)
    executor = once(executor, '  if (wmma_experts) {\n    // The combine',
        '  if (wmma_experts || compact_down) {\n    // The combine')
    executor = once(executor, '    moe_pending_ = out == s_.block_out;',
        '    moe_pending_ = out == s_.block_out;\n'
        '    moe_q2_half_pending_ = compact_down && moe_pending_;')
    anchor = '    const auto* down = reinterpret_cast<const __half*>(s_.down_e);\n'
    executor = once(executor, anchor, anchor+'''    const bool q2_half = moe_q2_half_pending_;
    moe_q2_half_pending_ = false;
    if (q2_half && produce_half && c.hc_low_rank == 320) {
      float* scales = s_.hc_gate + std::size_t(n_tokens) * c.hc_low_rank;
      if (HcCombineMoeHalfDeferredNorm(res, down, s_.weights, s_.shexp_out,
            s_.router + c.num_experts, c.num_experts + 1, c.num_experts_used,
            s_.inject, inject_parts_, gamma, scales, n_tokens, c.hidden_size,
            c.hc_count, c.rms_eps, stream_, norm_half)) {
        lie_q2_deferred_norm_publish(&deferred_norm_, res, gamma, scales, n_tokens);
        publish_half();
        return;
      }
    }
''')
    changed['executor.cpp'] = executor
    changed['executor.hpp'] = once(original['executor.hpp'],
        '  mutable bool moe_pending_{false};',
        '  mutable bool moe_pending_{false};\n'
        '  // Marks only the experimental Q2 half-output producer.\n'
        '  mutable bool moe_q2_half_pending_{false};')
    changed['batch.cpp'] = once(original['batch.cpp'],
        '  moe_pending_ = false;',
        '  moe_pending_ = false;\n  moe_q2_half_pending_ = false;')
    shutil.copytree(base, out)
    patch_text = '// SPDX-License-Identifier: MIT\n'
    for name, text in changed.items():
        (out/(ROCM+name)).write_text(text)
        patch_text += ''.join(difflib.unified_diff(original.get(name,'').splitlines(True),
            text.splitlines(True), fromfile='a/'+ROCM+name, tofile='b/'+ROCM+name))
    patch.write_text(patch_text)
    files = inventory(out)
    delta = sorted(name for name in files if files[name] != parent['files'].get(name))
    assert len(files) == 1026 and len(delta) == 6
    measured = ROOT/'config/q2-iq2-live-compose-model-results.json'
    variant = dict(source=str(out.relative_to(ROOT)),files=files,changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)),parent_manifest_sha256=sha(parent_path),
        measured_parent=str(measured.relative_to(ROOT)),measured_parent_sha256=sha(measured),
        patch=str(patch.relative_to(ROOT)),patch_sha256=sha(patch),
        logical_output_bytes_before=209715200,logical_output_bytes_after=104857600,
        allocation_capacity_unchanged=True,additional_runtime_allocations=0,
        additional_streams=0,model_weight_bytes_unchanged=True,
        dispatch='Only original Q2 wide2048, HC4/rank320, block-output consumer; F16 pending lifetime plus explicit Q2 storage marker reset on consume/scratch replacement. Other shapes and scalar decode retain original dispatch.',
        mechanism='Store the final inverse-scaled down outputs as F16 and consume them directly in the original ordered F32 MoE/deferred-norm chain.',
        numerical_contract='An explicit F32-to-F16 rounding is introduced at expert output. This is NOT byte-exact to the parent. All WMMA/scale/ordered combine arithmetic and weights otherwise remain.',
        risks='Rounding/underflow/overflow can change logits or task quality. Conversion cost and write transactions may erase the logical traffic saving. No allocation-peak or throughput gain inferred.',
        component_requirement='Check every output against independent RN-even F16 conversion of retained F32 down; compare half consumer against original consumer fed expanded halves, retain actual parent error, guards, all writes and complete-cycle timings.',
        controls_rerun=False,gpu_run=False,model_inference=False,promoted=False,goal_met=False)
    manifest.write_text(json.dumps(dict(schema='synapse-lie.q2-down-half-storage-source.v1',
        variants={'down-half-storage':variant},gpu_run=False,goal_met=False),indent=2)+'\n')
    print(json.dumps(dict(provider_files=len(files),changed_files=delta,gpu_run=False)))


if __name__ == '__main__':
    main()
