#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare compressed expert slots using the antirez/ds4 streaming mechanism."""
import difflib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'src/models/qwen38_flash_next/kernels/rocm/'
spec = importlib.util.spec_from_file_location('prepare_cache', ROOT / 'tools/prepare-q2-expert-cache.py')
prior = importlib.util.module_from_spec(spec)
spec.loader.exec_module(prior)
once, sha, inventory = prior.once, prior.sha, prior.inventory


def indexed_kernel(text, name):
    start = text.rfind('template<WeightType', 0, text.index('void ' + name + '('))
    end = text.index('\n}\n', start) + 3
    body = text[start:end]
    body = once(body, 'bool kPacked = false, bool kScaled = false>',
                'bool kPacked = false, bool kScaled = false, bool kSlots = false>')
    needle = '  const auto* w_expert = static_cast<const std::uint8_t*>(w) +\n                         static_cast<std::size_t>(expert) * m * row_bytes;'
    replacement = '''  // Only address resolution changes; all encoded bytes and arithmetic remain.
  struct SlotView { const void* base; const std::int32_t* map; };
  int weight_expert = expert;
  const void* weight_base = w;
  const void* up_base = w_up;
  if constexpr (kSlots) {
    const auto* view = static_cast<const SlotView*>(w);
    weight_expert = view->map[expert];
    weight_base = view->base;
    if constexpr (kPair) up_base = static_cast<const SlotView*>(w_up)->base;
  }
  const auto* w_expert = static_cast<const std::uint8_t*>(weight_base) +
                         static_cast<std::size_t>(weight_expert) * m * row_bytes;'''
    body = once(body, needle, replacement)
    if name == 'RoutedF16GEMMKernel':
        body = once(body, 'weights = static_cast<const std::uint8_t*>(w_up) +\n                  static_cast<std::size_t>(expert) * m * row_bytes;',
                    'weights = static_cast<const std::uint8_t*>(up_base) +\n                  static_cast<std::size_t>(weight_expert) * m * row_bytes;')
    return text[:start] + body + text[end:]


def main():
    parent_path = ROOT / 'config/q2-ssm-fixed-bounds-source.json'
    parent = json.loads(parent_path.read_text())['variants']['ssm-fixed-bounds']
    base = ROOT / parent['source']
    assert inventory(base) == parent['files']
    source = ROOT / '.deps/gufo-q2-compressed-cache-r2-run'
    manifest = ROOT / 'config/q2-compressed-cache-source-v2.json'
    patch = ROOT / 'experiments/q2-compressed-cache-v2.patch'
    if any(p.exists() for p in (source, manifest, patch)):
        raise ValueError('Refusing source overwrite')
    original = {n: (base / PREFIX / n).read_text() for n in
                ('kernels.hip.cpp', 'kernels.hpp', 'q2_down_half_storage.inc',
                 'device_model.hpp', 'device_model.cpp', 'executor.cpp')}
    kernels = indexed_kernel(original['kernels.hip.cpp'], 'RoutedF16GEMMKernel')
    half = indexed_kernel(original['q2_down_half_storage.inc'], 'RoutedQ2HalfStorageKernel')
    a = kernels.index('template<int BN, bool kPacked = false>\nvoid LaunchRoutedIQ2(')
    b = kernels.index('\nbool RoutedGatedIQ2GemmPacked(', a)
    gate = kernels[a:b].replace('LaunchRoutedIQ2', 'LaunchSlottedIQ2').replace(
        'RoutedGatedIQ2Gemm', 'RoutedSlottedIQ2Gemm').replace(
        '2, true, kPacked>', '2, true, kPacked, false, true>')
    scaled = (base / PREFIX / 'q2_scaled_input.inc').read_text()
    down = scaled[scaled.index('template<int BN>\nvoid LaunchRoutedQ2Scaled('):]
    down = down.replace('LaunchRoutedQ2Scaled', 'LaunchSlottedQ2Scaled').replace(
        'RoutedQ2ScaledGemm', 'RoutedSlottedQ2ScaledGemm').replace(
        '2, false, false, true>', '2, false, false, true, true>')
    a = half.index('template<int BN>\nvoid LaunchRoutedQ2HalfStorage(')
    b = half.index('\n__global__ void HcCombineMoeHalfDeferredNormKernel(', a)
    half_wrap = half[a:b].replace('LaunchRoutedQ2HalfStorage', 'LaunchSlottedQ2HalfStorage').replace(
        'RoutedQ2ScaledHalfGemm', 'RoutedSlottedQ2ScaledHalfGemm').replace(
        '2, false, false, true>', '2, false, false, true, true>')
    kernels = once(kernels, '#include "q2_down_half_storage.inc"',
                   '#include "q2_down_half_storage.inc"\n#include "lie_q2_compressed_kernels.inc"')
    header = original['kernels.hpp']
    declarations = ''
    for name in ('RoutedGatedIQ2Gemm', 'RoutedQ2ScaledGemm', 'RoutedQ2ScaledHalfGemm'):
        a = header.index('bool ' + name + '('); b = header.index(';', a) + 1
        declarations += header[a:b].replace(name, name.replace('RoutedGatedIQ2', 'RoutedSlottedIQ2').replace('RoutedQ2', 'RoutedSlottedQ2')) + '\n'
    header = once(header, 'bool RoutedGatedIQ2Gemm(', declarations + '\nbool RoutedGatedIQ2Gemm(')
    mh = original['device_model.hpp']
    mh = once(mh, '#include <cstddef>', '#include <cstddef>\n#include <hip/hip_runtime_api.h>')
    mh = once(mh, '  void* data{nullptr};', '  void* data{nullptr};\n  void* compressed_view{nullptr};')
    mh = once(mh, 'struct DeviceLayer {', 'struct DeviceLayer {\n  std::uint32_t cache_layer{UINT32_MAX};')
    mh = once(mh, 'class DeviceModel {', '''class CompressedExpertCache;
class CompressedExpertLease {
public:
  ~CompressedExpertLease();
  DeviceLayer layer;
  const std::int32_t* ids{nullptr};
private:
  friend class DeviceModel;
  CompressedExpertLease();
  struct State;
  std::unique_ptr<State> state_;
};
class DeviceModel {''')
    mh = once(mh, '  const Config& config() const noexcept', '''  bool has_compressed_cache() const noexcept { return compressed_cache_ != nullptr; }
  std::unique_ptr<CompressedExpertLease> AcquireExperts(
      const DeviceLayer&, const std::int32_t*, std::size_t, hipStream_t, std::string*) const;
  const Config& config() const noexcept''')
    mh = once(mh, '  Config config_;', '  std::unique_ptr<CompressedExpertCache> compressed_cache_;\n  Config config_;')
    mh = once(mh, '[[nodiscard]] std::size_t resident_bytes() const noexcept { return bytes_; }',
              '[[nodiscard]] std::size_t resident_bytes() const noexcept;')
    model = once(original['device_model.cpp'], '#include <initializer_list>',
                 '#include <initializer_list>\n#include <cstdio>\n#include <mutex>\n#include "lie_q2_compressed_cache.h"')
    model = once(model, '  bool ok{true};', '  bool ok{true};\n  bool stream_experts{false};')
    model = once(model, '  DeviceTensor Copy(const TensorRef& t) {', '''  DeviceTensor Expert(const TensorRef& t) {
    if (!stream_experts) return Copy(t);
    DeviceTensor d;
    d.type = t.type; d.cols = static_cast<std::uint32_t>(t.cols);
    d.rows = static_cast<std::uint32_t>(t.rows); d.experts = static_cast<std::uint32_t>(t.experts);
    return d;
  }
  DeviceTensor Copy(const TensorRef& t) {''')
    for field in ('gate', 'up', 'down'):
        model = once(model, f'd.ffn_{field}_exps = Copy(l.ffn_{field}_exps);',
                     f'd.ffn_{field}_exps = Expert(l.ffn_{field}_exps);')
    model = once(model, 'DeviceModel::~DeviceModel() {',
                 '#include "lie_q2_compressed_runtime.inc"\n\nDeviceModel::~DeviceModel() {\n  compressed_cache_.reset();')
    model = once(model, '  m->token_embd_ = up.Copy(w.token_embd);', '''  // Explicit experiment budget. Keep the original resident path when all
  // experts fit; smaller budgets cache original bytes, never dequantized copies.
  constexpr std::size_t cache_budget = std::size_t(32) << 30;
  bool supported_cache = w.config.num_layers == 48 && w.config.num_experts == 512 &&
                         w.config.hidden_size == 2560 && w.config.expert_ff == 640;
  std::size_t expert_bytes = 0;
  for (const auto& l : w.layers) {
    supported_cache = supported_cache && l.ffn_gate_exps.type == core::GgmlType::kIQ2_XXS &&
        l.ffn_up_exps.type == core::GgmlType::kIQ2_XXS && l.ffn_down_exps.type == core::GgmlType::kQ2_K &&
        l.ffn_gate_exps.cols == 2560 && l.ffn_gate_exps.rows == 640 && l.ffn_gate_exps.experts == 512 &&
        l.ffn_up_exps.cols == 2560 && l.ffn_up_exps.rows == 640 && l.ffn_up_exps.experts == 512 &&
        l.ffn_down_exps.cols == 768 && l.ffn_down_exps.rows == 2560 && l.ffn_down_exps.experts == 512;
    expert_bytes += l.ffn_gate_exps.SizeBytes() + l.ffn_up_exps.SizeBytes() + l.ffn_down_exps.SizeBytes();
  }
  up.stream_experts = supported_cache && expert_bytes > cache_budget;
  m->token_embd_ = up.Copy(w.token_embd);''')
    model = once(model, '    m->layers_.push_back(up.Layer(l));', '''    m->layers_.push_back(up.Layer(l));
    if (up.stream_experts) m->layers_.back().cache_layer = static_cast<std::uint32_t>(m->layers_.size() - 1);''')
    model = once(model, '    up.shard_base = shard_count;', '    up.shard_base = shard_count;\n    up.stream_experts = false;')
    model = once(model, '  return m;\n}\n\n}  // namespace', '''  if (supported_cache && expert_bytes > cache_budget) {
    m->compressed_cache_ = std::make_unique<CompressedExpertCache>();
    if (!m->compressed_cache_->Init(w, shards, cache_budget, error_msg)) {
      if (error_msg && error_msg->empty()) *error_msg = "compressed expert cache initialization failed";
      return nullptr;
    }
    m->bytes_ += m->compressed_cache_->bytes + 512 * sizeof(std::int32_t) + 3 * sizeof(CompressedExpertCache::View);
  }
  return m;
}

}  // namespace''')
    executor = original['executor.cpp']
    executor = once(executor, 'bool Executor::MoeExperts(const DeviceLayer& l,',
                    'bool Executor::MoeExperts(const DeviceLayer& original,')
    marker = '  const bool iq2_wmma = ExpertMatrixRows(n_tokens) &&'
    executor = once(executor, marker, '''  std::unique_ptr<CompressedExpertLease> cache;
  if (model_->has_compressed_cache() && original.cache_layer != UINT32_MAX) {
    cache = model_->AcquireExperts(original, s_.ids, slots, stream_, error_msg);
    if (!cache) return false;
  }
  const auto& l = cache ? cache->layer : original;
  const auto* expert_ids = cache ? cache->ids : s_.ids;
''' + marker)
    executor = once(executor, '      return RoutedGatedIQ2Gemm(l.ffn_gate_exps.data, l.ffn_up_exps.data,',
        '      return (cache ? RoutedSlottedIQ2Gemm : RoutedGatedIQ2Gemm)(\n'
        '          cache ? l.ffn_gate_exps.compressed_view : l.ffn_gate_exps.data,\n'
        '          cache ? l.ffn_up_exps.compressed_view : l.ffn_up_exps.data,')
    executor = once(executor, '              ? RoutedQ2ScaledHalfGemm(\n                    l.ffn_down_exps.data,',
        '              ? (cache ? RoutedSlottedQ2ScaledHalfGemm : RoutedQ2ScaledHalfGemm)(\n'
        '                    cache ? l.ffn_down_exps.compressed_view : l.ffn_down_exps.data,')
    executor = once(executor, '              : RoutedQ2ScaledGemm(l.ffn_down_exps.data,',
        '              : (cache ? RoutedSlottedQ2ScaledGemm : RoutedQ2ScaledGemm)(\n'
        '                    cache ? l.ffn_down_exps.compressed_view : l.ffn_down_exps.data,')
    executor = once(executor, 'GatedExperts(l.ffn_gate_exps, l.ffn_up_exps, x, s_.ids, s_.gate_e,',
                    'GatedExperts(l.ffn_gate_exps, l.ffn_up_exps, x, expert_ids, s_.gate_e,')
    executor = once(executor, 'Experts(l.ffn_down_exps, s_.gate_e, s_.ids, s_.down_e, slots, 1,',
                    'Experts(l.ffn_down_exps, s_.gate_e, expert_ids, s_.down_e, slots, 1,')
    assert executor.count('  const bool graph = ') == 2
    executor = executor.replace('  const bool graph = ', '  const bool graph = !model_->has_compressed_cache() && ')
    changed = {'kernels.hip.cpp': kernels, 'kernels.hpp': header, 'q2_down_half_storage.inc': half,
        'device_model.hpp': mh, 'device_model.cpp': model, 'executor.cpp': executor,
        'lie_q2_compressed_kernels.inc': '// SPDX-License-Identifier: MIT\n' + gate + down + half_wrap,
        'lie_q2_compressed_cache.h': (ROOT / 'experiments/q2_compressed_cache.h').read_text(),
        'lie_q2_compressed_runtime.inc': (ROOT / 'experiments/q2_compressed_cache_runtime.inc').read_text()}
    formatted = {}
    for name, body in changed.items():
        result = subprocess.run(['/opt/rocm/llvm/bin/clang-format', '--sort-includes=false',
            '--style=file:' + str(base / '.clang-format'), '--assume-filename=' + str(base / PREFIX / name)],
            input=body, text=True, capture_output=True, check=True)
        formatted[PREFIX + name] = result.stdout
    shutil.copytree(base, source)
    for name, body in formatted.items(): (source / name).write_text(body)
    files = inventory(source)
    delta = sorted(n for n in files if files[n] != parent['files'].get(n))
    assert delta == sorted(formatted)
    with patch.open('x') as f:
        f.write('// SPDX-License-Identifier: MIT\n')
        for name, body in sorted(formatted.items()):
            f.write(''.join(difflib.unified_diff((base / name).read_text().splitlines(True)
                if (base / name).exists() else [], body.splitlines(True),
                fromfile='a/' + name if (base / name).exists() else '/dev/null', tofile='b/' + name)))
    variant = dict(source=str(source.relative_to(ROOT)), files=files, changed_files=delta,
        parent_manifest=str(parent_path.relative_to(ROOT)), parent_manifest_sha256=sha(parent_path),
        measured_parent='config/q2-ssm-fixed-bounds-model-results.json',
        measured_parent_sha256=sha(ROOT / 'config/q2-ssm-fixed-bounds-model-results.json'),
        patch=str(patch.relative_to(ROOT)), patch_sha256=sha(patch), budget_bytes=32 * 1024**3,
        reference_repository='https://github.com/antirez/ds4',
        reference_commit='0aaea5a238fb41a35106a551e73c8409dfb751ac',
        mechanism='Bounded original-byte expert slots; protect selected hits, LRU eviction, disk-load misses, GPU completion before reuse. Full resident fast path when the expert set fits.',
        model_dispatch_changed=True, gpu_run=False, numerical_acceptance=False)
    with manifest.open('x') as f:
        json.dump(dict(schema='synapse-lie.q2-compressed-cache-source.v1', variants={'compressed-cache': variant}), f, indent=2)
        f.write('\n')
    print(json.dumps(dict(provider_files=len(files), changed=delta, gpu_run=False)))


if __name__ == '__main__': main()
