#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Integrate the retained MoE-only deferred norm into the best measured provider."""
import difflib
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
REL = 'src/models/qwen38_flash_next/kernels/rocm/'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inventory(folder):
    return {str(p.relative_to(folder)): sha(p) for p in sorted(folder.rglob('*')) if p.is_file()}


def once(text, before, after):
    if text.count(before) != 1:
        raise ValueError('Unexpected source anchor: ' + before[:100])
    return text.replace(before, after, 1)


def function(text, signature):
    if text.count(signature) != 1:
        raise ValueError('Expected one function: ' + signature)
    start = text.index(signature)
    opening = text.index('{', start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[start:end] + '\n'


def main():
    parent_path = ROOT / 'config/q2-hc-bk256-run-source.json'
    parent = json.loads(parent_path.read_text())
    base = parent['variants']['hc-bk256-bounded']
    source = ROOT / base['source']
    if inventory(source) != base['files']:
        raise ValueError('Measured bounded provider changed')
    donor_path = ROOT / 'config/q2-hc-deferred-norm-source.json'
    donor_info = json.loads(donor_path.read_text())
    donor = ROOT / donor_info['output'] / (REL + 'kernels.hip.cpp')
    if sha(donor) != donor_info['changed_files'][REL + 'kernels.hip.cpp']['candidate_sha256']:
        raise ValueError('Retained deferred-norm port changed')
    candidate = ROOT / '.deps/gufo-q2-hc-moe-deferred-run'
    output = ROOT / 'config/q2-hc-moe-deferred-source.json'
    patch_path = ROOT / 'experiments/q2-hc-moe-deferred.patch'
    if any(p.exists() for p in (candidate, output, patch_path)):
        raise ValueError('Refusing to overwrite a retained candidate')
    text = donor.read_text()
    fragments = [function(text, signature) for signature in (
        '__device__ __forceinline__ float4 DeferredHcNormValue(',
        '__device__ __forceinline__ float4 LoadDeferredHcNorm(',
        '__global__ void HcCombineMoeDeferredNormKernel(',
        '__global__ void ReconstructHcNormKernel(',
        '__global__ void HcInjectDeferredNormKernel(',
        '__launch_bounds__(512) __global__ void HcMixDeferredNormKernel(',
        'bool HcCombineMoeDeferredNorm(', 'bool ReconstructHcNorm(', 'bool HcMixDeferredNorm(')]
    fragments[4] = 'template<typename XnT, bool kMix = true>\n' + fragments[4]
    for i in (6, 7, 8):
        fragments[i] = once(fragments[i], '  return true;\n',
                            '  return hipGetLastError() == hipSuccess;\n')
    fragments[8] = once(fragments[8], '  if (inject_w != nullptr) {',
                        '  if (hipGetLastError() != hipSuccess) return false;\n  if (inject_w != nullptr) {')
    include = '// SPDX-License-Identifier: MIT\n// Retained official-Gufo-derived numerical experiment; MoE only.\n'
    include += '// No ordinary deferred producer or Q8 consumer is selected.\n' + '\n'.join(fragments)
    replacements = {REL + 'q2_hc_moe_deferred.inc': include,
                    REL + 'lie_q2_deferred_norm_state.h': (ROOT / 'experiments/q2_deferred_norm_state.h').read_text()}
    kernels = (source / (REL + 'kernels.hip.cpp')).read_text()
    replacements[REL + 'kernels.hip.cpp'] = once(kernels, '\nbool UnquantizedF16Gemm(',
        '\n#include "q2_hc_moe_deferred.inc"\n\nbool UnquantizedF16Gemm(')
    declarations = ''.join(fragments[i][:fragments[i].index('{')].rstrip() + ';\n' for i in (6, 7, 8))
    header = (source / (REL + 'kernels.hpp')).read_text()
    replacements[REL + 'kernels.hpp'] = once(header,
        '}  // namespace gufo::models::qwen38_flash_next::rocm',
        '// Experimental MoE deferred norm: all inputs/scales survive both consumers.\n' + declarations +
        '}  // namespace gufo::models::qwen38_flash_next::rocm')
    executor_h = (source / (REL + 'executor.hpp')).read_text()
    executor_h = once(executor_h, '#include <hip/hip_fp16.h>',
                     '#include "lie_q2_deferred_norm_state.h"\n\n#include <hip/hip_fp16.h>')
    executor_h = once(executor_h, '  mutable bool xn_half_{false};',
        '  mutable bool xn_half_{false};\n'
        '  mutable lie_q2_deferred_norm_state deferred_norm_{};')
    replacements[REL + 'executor.hpp'] = executor_h
    executor = (source / (REL + 'executor.cpp')).read_text()
    executor = once(executor, '  // Wide batches hand the next mixer',
        '  lie_q2_deferred_norm_clear(&deferred_norm_);\n  // Wide batches hand the next mixer')
    executor = once(executor, '    if (!xn_half_) {\n      const bool combined =', '''    if (!xn_half_) {
      if (produce_half && c.hc_low_rank == 320) {
        // Low-rank F16 input occupies the prefix. Four F32 scales per token
        // live beyond it; the fused up/inject consumers never overwrite them.
        float* scales = s_.hc_gate + std::size_t(n_tokens) * c.hc_low_rank;
        if (HcCombineMoeDeferredNorm(res, s_.down_e, s_.weights, s_.shexp_out,
              s_.router + c.num_experts, c.num_experts + 1, c.num_experts_used,
              s_.inject, inject_parts_, gamma, scales, n_tokens, c.hidden_size,
              c.hc_count, c.rms_eps, stream_, norm_half)) {
          lie_q2_deferred_norm_publish(&deferred_norm_, res, gamma, scales, n_tokens);
          publish_half();
          return;
        }
      }
      const bool combined =''')
    executor = once(executor, '  if (!normed) {\n    xn_half_ = false;',
        '  if (!normed) {\n    lie_q2_deferred_norm_clear(&deferred_norm_);\n    xn_half_ = false;')
    executor = once(executor, '  if (fused_projection) {\n    // The up projection', '''  const auto deferred = deferred_norm_;
  const bool consume_deferred = deferred.rows != 0 && normed && !xn_half_ &&
      fused_raw_projection && !produce_q8;
  if (deferred.rows != 0) {
    if (!lie_q2_deferred_norm_matches(&deferred, res, m.norm.f32(), n_tokens)) {
      lie_q2_deferred_norm_clear(&deferred_norm_);
      AssignError(error_msg, "deferred HC norm identity changed");
      return false;
    }
    if (!consume_deferred &&
        !ReconstructHcNorm(res, deferred.scales, deferred.gamma, s_.xn, n_tokens, stream_)) {
      lie_q2_deferred_norm_clear(&deferred_norm_);
      AssignError(error_msg, "deferred HC norm reconstruction failed");
      return false;
    }
    // The local snapshot stays live through both same-stream consumers.
    lie_q2_deferred_norm_clear(&deferred_norm_);
  }
  if (fused_projection) {
    // The up projection''')
    executor = once(executor, '  } else if (fused_raw_projection && produce_q8) {', '''  } else if (consume_deferred) {
    if (!HcMixDeferredNorm(m.up.data, reinterpret_cast<const __half*>(s_.hc_gate),
            res, fused_inject ? m.inject.f32() : nullptr, mixed,
            static_cast<__half*>(s_.x_half), inject, n_tokens, c.hidden_size,
            c.hc_low_rank, stream_, deferred.scales, deferred.gamma)) {
      AssignError(error_msg, "deferred raw F16 HC projection failed");
      return false;
    }
    half_src_ = mixed;
    half_rows_ = n_tokens;
    half_cols_ = c.hidden_size;
    half_bf16_ = false;
  } else if (fused_raw_projection && produce_q8) {''')
    replacements[REL + 'executor.cpp'] = executor
    shutil.copytree(source, candidate)
    for name, value in replacements.items():
        (candidate / name).write_text(value)
    files = inventory(candidate)
    changed = [name for name, digest in files.items() if base['files'].get(name) != digest]
    if set(changed) != set(replacements) or len(files) != 1025:
        raise ValueError('Unexpected source delta')
    patch = '// SPDX-License-Identifier: MIT\n'
    for name in changed:
        before = (source / name).read_text() if (source / name).exists() else ''
        patch += ''.join(difflib.unified_diff(before.splitlines(True),
                    (candidate / name).read_text().splitlines(True), fromfile='a/' + name, tofile='b/' + name))
    with patch_path.open('x') as stream:
        stream.write(patch)
    variant = dict(source=str(candidate.relative_to(ROOT)), files=files, changed_files=changed,
                   unchanged_files=len(files) - len(changed), parent_variant='hc-bk256-bounded',
                   parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
                   donor_manifest=str(donor_path.relative_to(ROOT)), donor_manifest_sha256=sha(donor_path),
                   donor_kernel_sha256=sha(donor), patch=str(patch_path.relative_to(ROOT)), patch_sha256=sha(patch_path),
                   c17_state_header_sha256=sha(ROOT / 'experiments/q2_deferred_norm_state.h'),
                   mo_e_only=True, fixed_rows=2048, additional_device_allocations=0, additional_streams=0,
                   scales_per_token=4, scale_bytes_at_2048=32768,
                   skipped_f32_norm_bytes_at_2048=83886080,
                   scale_offset_float_elements='rows * hc_low_rank; beyond the F16 low-rank prefix',
                   fallback='Materialize reconstructed F32 before unsupported consumers; refuse changed identities',
                   original_parent_down_unchanged=True, ordinary_producer_unchanged=True,
                   q8_consumer_unchanged=True, producer_consumer_arithmetic_exactness=False,
                   gpu_run=False, model_forward=False, numerical_qualification=False, performance_qualification=False)
    report = dict(schema='synapse-lie.q2-hc-moe-deferred-source.v1', variants={'hc-moe-deferred': variant},
                  control_files=parent['control_files'], control_parent=parent['control_parent'],
                  control_parent_manifest=parent['control_parent_manifest'],
                  control_parent_manifest_sha256=parent['control_parent_manifest_sha256'],
                  measured_parent='config/q2-hc-bk256-fixed-model-results.json',
                  measured_parent_sha256=sha(ROOT / 'config/q2-hc-bk256-fixed-model-results.json'),
                  gpu_run=False, model_forward=False, goal_met=False)
    with output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print(json.dumps(dict(files=len(files), changed=changed, c17_state=True, model_wired=True,
                          new_allocation_bytes=0, gpu_run=False)))


if __name__ == '__main__':
    main()
