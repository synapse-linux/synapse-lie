#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare bounded GPU Q8-to-half weight mirrors preserving Q8 WMMA order."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'src/models/qwen38_flash_next/kernels/rocm/'
spec = importlib.util.spec_from_file_location('prior', ROOT / 'tools/prepare-q2-iq2-fused-grid.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
sha, inventory, once = prior.sha, prior.inventory, prior.once


def main():
    parent_path = ROOT / 'config/q2-iq2-raw-prefetch-source.json'
    parent = json.loads(parent_path.read_text())['variants']['iq2-raw-prefetch']
    base = ROOT / parent['source']
    if inventory(base) != parent['files']:
        raise ValueError('Measured parent inventory changed')
    files = ('kernels.hip.cpp', 'kernels.hpp', 'device_model.hpp', 'device_model.cpp', 'executor.cpp')
    original = {name:(base / PREFIX / name).read_text() for name in files}
    text = original['kernels.hip.cpp']
    text = once(text, 'bool kHalfWeights = false, bool kHcUpChains = false>',
                'bool kHalfWeights = false, bool kHcUpChains = false, bool kQ8Mirror = false>')
    start = text.index('template<int BM, int BN, int BK, int WM, int WN, int kRowGroup = 1,')
    end = text.index('\nbool AttentionF16Gemm(', start)
    kernel = text[start:end]
    if kernel.count('kHalfWeights && !kHcUpChains') != 4:
        raise ValueError('Original single/split K16 conditions changed')
    kernel = kernel.replace('kHalfWeights && !kHcUpChains', 'kHalfWeights && !kHcUpChains && !kQ8Mirror')
    kernel = once(kernel, '  static_assert(WM * WN == 8, "256 threads is 8 waves");',
        '  // SPDX-License-Identifier: MIT\n'
        '  // A Q8-derived F16 mirror keeps the Q8 low/high single chain.\n'
        '  static_assert(!kQ8Mirror || (kHalfWeights && !kHcMix && !kHcUpChains));\n'
        '  static_assert(WM * WN == 8, "256 threads is 8 waves");')
    text = text[:start] + kernel + text[end:]
    text = once(text, '\nbool AttentionF16Gemm(',
        '\n// SPDX-License-Identifier: MIT\n#include "' + PREFIX + 'lie_q8_mirror.inc"\n\nbool AttentionF16Gemm(')
    changed = {'kernels.hip.cpp':text}
    declarations = '''// SPDX-License-Identifier: MIT
// GPU-only, exact encoded-Q8 mirror; original Q8 weights remain for decode.
bool ConvertQ8Mirror(const void* weights, void* half, std::size_t elements,
                      hipStream_t stream);
bool DenseQ8MirrorGemm(const void* w, const __half* x, float* out,
                        std::size_t batch, std::size_t m, std::size_t k,
                        hipStream_t stream);
bool DenseQ8MirrorSsmGemm(const void* w, const __half* x, const float* conv_w,
                           const float* history, float* qkvz, float* convolved,
                           std::uint32_t n_tokens, std::uint32_t m, std::uint32_t k,
                           std::uint32_t channels, std::uint32_t kernel,
                           hipStream_t stream);
bool AttentionQ8MirrorGemm(const void* w, const __half* input,
                            const float* q_gamma, const float* k_gamma,
                            float* query, float* gate, __half* keys, __half* values,
                            std::uint32_t n_tokens, const std::uint32_t* position,
                            float theta, float eps, hipStream_t stream,
                            const qwen::vision::DeviceRope* rope);

'''
    changed['kernels.hpp'] = once(original['kernels.hpp'], 'bool AttentionF16Gemm(', declarations + 'bool AttentionF16Gemm(')
    text = once(original['device_model.hpp'], '  void* data{nullptr};',
        '  void* data{nullptr};\n'
        '  // SPDX-License-Identifier: MIT\n'
        '  // Read-only auxiliary mirror, published only with the completed model.\n'
        '  void* prefill_half{nullptr};')
    text = once(text, '  std::size_t bytes_{0};',
        '  std::size_t bytes_{0};\n  std::size_t q8_mirror_bytes_{0};')
    changed['device_model.hpp'] = text
    text = once(original['device_model.cpp'], '#include <initializer_list>',
        '#include <initializer_list>\n#include <limits>\n\n'
        '// SPDX-License-Identifier: MIT\n#include "' + PREFIX + 'lie_q8_mirror_policy.h"')
    anchor = '''  return m;
}

}  // namespace gufo::models::qwen38_flash_next::rocm'''
    mirror = '''  // SPDX-License-Identifier: MIT
  // Upload is complete before any conversion. Keep original Q8 allocations
  // for decode; all mirrors join the same model allocation/byte ownership.
  const auto mirror = [&](DeviceTensor& tensor) {
    lie_q8_mirror_plan plan;
    const int admitted = lie_q8_mirror_admit(tensor.rows, tensor.cols,
        tensor.experts, tensor.type == core::GgmlType::kQ8_0,
        m->q8_mirror_bytes_, &plan);
    if (admitted == 0)
      return true;
    if (admitted < 0 || tensor.empty() ||
        plan.allocation_bytes > std::numeric_limits<std::size_t>::max() - m->bytes_) {
      up.Fail("Q8 prefill mirror resource admission failed");
      return false;
    }
    void* half = nullptr;
    if (hipMalloc(&half, plan.allocation_bytes) != hipSuccess) {
      up.Fail("Q8 prefill mirror allocation failed");
      return false;
    }
    m->allocations_.push_back(half);
    m->bytes_ += plan.allocation_bytes;
    m->q8_mirror_bytes_ = plan.next_mirror_bytes;
    if (hipMemsetAsync(static_cast<std::uint8_t*>(half) + plan.payload_bytes,
          0, LIE_Q8_MIRROR_TAIL_BYTES, nullptr) != hipSuccess ||
        !ConvertQ8Mirror(tensor.data, half, plan.elements, nullptr)) {
      up.Fail("Q8 prefill mirror conversion launch failed");
      return false;
    }
    tensor.prefill_half = half;
    return true;
  };
  for (auto& layer : m->layers_) {
    if (!mirror(layer.ssm_in) || !mirror(layer.ssm_out) ||
        !mirror(layer.attn_qkv) || !mirror(layer.attn_out)) {
      (void)hipDeviceSynchronize();
      return nullptr;
    }
  }
  const auto mirror_status = hipDeviceSynchronize();
  if (mirror_status != hipSuccess) {
    up.Fail("Q8 prefill mirror conversion failed: " +
            std::string(hipGetErrorString(mirror_status)));
    return nullptr;
  }
  // Only this fully synchronized return publishes any mirror to an executor.
  return m;
}

}  // namespace gufo::models::qwen38_flash_next::rocm'''
    changed['device_model.cpp'] = once(text, anchor, mirror)
    text = original['executor.cpp']
    text = once(text, '''        if (!DenseF16Gemm(w.data, static_cast<const __half*>(s_.x_half),
                          out + static_cast<std::size_t>(r0) * w.rows, rows,
                          w.rows, w.cols, stream_)) {''',
        '''        // SPDX-License-Identifier: MIT
        const bool mirror = w.prefill_half != nullptr && rows >= 1024;
        const bool launched = mirror
            ? DenseQ8MirrorGemm(w.prefill_half, static_cast<const __half*>(s_.x_half),
                out + static_cast<std::size_t>(r0) * w.rows, rows, w.rows, w.cols, stream_)
            : DenseF16Gemm(w.data, static_cast<const __half*>(s_.x_half),
                out + static_cast<std::size_t>(r0) * w.rows, rows, w.rows, w.cols, stream_);
        if (!launched) {''')
    text = once(text, '      convolved = DenseF16SsmGemm(\n          l.ssm_in.data,',
        '      // SPDX-License-Identifier: MIT\n'
        '      const bool mirror = l.ssm_in.prefill_half != nullptr;\n'
        '      convolved = (mirror ? DenseQ8MirrorSsmGemm : DenseF16SsmGemm)(\n'
        '          mirror ? l.ssm_in.prefill_half : l.ssm_in.data,')
    text = once(text, '''    if (!DenseF16Gemm(l.ssm_out.data, out_half, out, n_tokens, l.ssm_out.rows,
                      l.ssm_out.cols, stream_)) {''',
        '''    // SPDX-License-Identifier: MIT
    const bool mirror = l.ssm_out.prefill_half != nullptr && n_tokens >= 1024;
    if (!(mirror ? DenseQ8MirrorGemm : DenseF16Gemm)(
            mirror ? l.ssm_out.prefill_half : l.ssm_out.data, out_half, out,
            n_tokens, l.ssm_out.rows, l.ssm_out.cols, stream_)) {''')
    text = once(text, '      prepared = AttentionF16Gemm(\n          l.attn_qkv.data,',
        '      // SPDX-License-Identifier: MIT\n'
        '      const bool mirror = l.attn_qkv.prefill_half != nullptr;\n'
        '      prepared = (mirror ? AttentionQ8MirrorGemm : AttentionF16Gemm)(\n'
        '          mirror ? l.attn_qkv.prefill_half : l.attn_qkv.data,')
    changed['executor.cpp'] = text
    generated = {
      'lie_q8_mirror.inc':(ROOT / 'experiments/q2_q8_mirror_kernels.inc').read_text(),
      'lie_q8_mirror_policy.h':(ROOT / 'experiments/q2_q8_mirror_policy.h').read_text()}
    source = ROOT / '.deps/gufo-q2-q8-mirror-run'
    manifest = ROOT / 'config/q2-q8-mirror-source.json'
    patch = ROOT / 'experiments/q2-q8-mirror.patch'
    if any(p.exists() for p in (source, manifest, patch)):
        raise ValueError('Refusing to overwrite retained source')
    formatted = {}
    for name, body in {**changed, **generated}.items():
        result = subprocess.run(['/opt/rocm/llvm/bin/clang-format',
          '--style=file:' + str(base / '.clang-format'), '--assume-filename=' + str(base / PREFIX / name)],
          input=body, text=True, capture_output=True)
        if result.returncode:
            raise ValueError('Formatting failed: ' + result.stderr)
        formatted[PREFIX + name] = result.stdout
    shutil.copytree(base, source)
    for name, body in formatted.items():
        (source / name).write_text(body)
    provider = inventory(source)
    delta = [name for name in provider if provider[name] != parent['files'].get(name)]
    if len(provider) != 1027 or delta != sorted(formatted):
        raise ValueError('Unexpected provider delta')
    with patch.open('x') as stream:
        stream.write('// SPDX-License-Identifier: MIT\n')
        for name in sorted(formatted):
            stream.write(''.join(difflib.unified_diff((base / name).read_text().splitlines(True)
               if (base / name).exists() else [], formatted[name].splitlines(True),
               fromfile='a/' + name, tofile='b/' + name)))
    variant = dict(source=str(source.relative_to(ROOT)), files=provider, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-iq2-raw-prefetch-model-results.json',
        measured_parent_sha256=sha(ROOT / 'config/q2-iq2-raw-prefetch-model-results.json'),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch),
        mirror_resource_policy='experiments/q2_q8_mirror_policy.h',
        mirror_resource_policy_sha256=sha(ROOT / 'experiments/q2_q8_mirror_policy.h'),
        mechanism='Once-per-upload GPU Q8-to-F16 mirrors for large plain/SSM/attention projections; native single-chain Q8 WMMA order and epilogues retained.',
        numerical_contract='Same CodesToHalves operands/rounding and per-output low/high K16 updates; original weights and all decode/narrow routes retained.',
        mirror_budget_bytes=6 * 1024**3, expected_q2_mirror_payload_bytes=5347737600,
        expected_q2_mirror_allocation_bytes=5347737600 + 96 * 4096,
        affected='Three new mirror dense bodies and model upload/prefill dispatch; all original kernels/weights retained.',
        risks='Twice the dense weight traffic and extra resident memory may offset removed repeated decode. Original F16 split-chain route cannot be substituted. Upload cost changes and must be recorded.',
        prior_negative_upstream='Persistent packed Q8 impacts decode; transient F16 staging and hipBLASLt were slower. This keeps original decode and amortizes conversion at load, not per prefill.',
        public_c_abi_unchanged=True, model_file_conversion=False, cpu_model_forward=False,
        additional_streams=0, numerical_acceptance=False, full_model_measured=False, gpu_run=False, goal_met=False)
    with manifest.open('x') as stream:
        json.dump(dict(schema='synapse-lie.q2-q8-mirror-source.v1', variants={'q8-mirror':variant},
                       gpu_run=False, goal_met=False), stream, indent=2); stream.write('\n')
    print(json.dumps(dict(provider_files=len(provider),changed_files=delta,mirror_budget_bytes=variant['mirror_budget_bytes'],expected_extra_bytes=variant['expected_q2_mirror_allocation_bytes'],gpu_run=False)))


if __name__ == '__main__':
    main()
